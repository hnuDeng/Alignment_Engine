import asyncio
import json
import sys
from pathlib import Path

import server
sys.path.insert(0, str(Path(__file__).parent))
from websocket_fixture import Socket, context, run


def test_report_sequence_preserves_real_analyzer_result_and_heartbeat():
    messages = [json.loads(message) for message in run(['{"type":"heartbeat"}'])]
    assert [m["type"] for m in messages] == ["stream_start", "drift_report", "stream_end", "heartbeat"]
    assert [m["seq"] for m in messages] == [1, 2, 3, 4]
    report = messages[1]["payload"]
    assert report["analysisMode"] == "mock_numpy"
    assert report["stats"]["totalSamples"] == 3
    assert report["stats"]["driftCount"] == 2
    assert [s["sampleId"] for s in report["samples"]] == ["far", "near-a"]
    assert report["samples"][0]["centroidDistance"] == 33.941125
    assert report["samples"][0]["isolationScore"] is None
    assert report["samples"][0]["severity"] is None
    assert report["samples"][0]["reason"]


def test_bad_messages_return_errors_and_do_not_end_heartbeat_loop():
    messages = [json.loads(message) for message in run(['not-json', '[]', '{"type":"unknown"}', '{"type":"HEARTBEAT"}'])]
    assert [m["type"] for m in messages] == ["stream_start", "drift_report", "stream_end", "error", "error", "error", "heartbeat"]
    assert [m["seq"] for m in messages] == list(range(1, 8))


def test_pipeline_failure_is_reported_to_client(monkeypatch):
    class BrokenExtractor:
        def __init__(self, **kwargs):
            pass

        def extract(self):
            raise RuntimeError("internal detail")

    monkeypatch.setattr(server, "Extractor", BrokenExtractor)
    socket = Socket()
    asyncio.run(server.pipeline_handler(socket))
    messages = [json.loads(message) for message in socket.sent]
    assert [m["type"] for m in messages] == ["stream_start", "error", "stream_end"]
    assert [m["seq"] for m in messages] == [1, 2, 3]
    assert "internal detail" not in json.dumps(messages)


def test_offline_mode_uses_only_mock_extraction_and_numpy(monkeypatch):
    class OfflineExtractor:
        def __init__(self, **kwargs):
            pass

        def _extract_mock(self):
            return context()

        def extract(self):
            raise AssertionError("offline mode must not launch FiftyOne")

    class OfflineAnalyzer:
        def _analyze_numpy(self, ctx):
            from core.analyzer import Analyzer
            return Analyzer()._analyze_numpy(ctx)

        def analyze(self, ctx):
            raise AssertionError("offline mode must not attempt CUDA")

    monkeypatch.setattr(server, "Extractor", OfflineExtractor)
    monkeypatch.setattr(server, "Analyzer", OfflineAnalyzer)
    socket = Socket()
    asyncio.run(server.pipeline_handler(socket, offline=True))
    messages = [json.loads(message) for message in socket.sent]
    assert [m["type"] for m in messages] == ["stream_start", "drift_report", "stream_end"]


def test_local_websocket_transport_sends_report_and_recovers_from_bad_input():
    from functools import partial
    from websockets import connect
    from websockets.server import serve

    async def exchange():
        async with serve(partial(server.pipeline_handler, offline=True), "127.0.0.1", 0) as listener:
            port = listener.sockets[0].getsockname()[1]
            async with connect(f"ws://127.0.0.1:{port}") as client:
                messages = [json.loads(await client.recv()) for _ in range(3)]
                await client.send("not-json")
                messages.append(json.loads(await client.recv()))
                await client.send('{"type":"heartbeat"}')
                messages.append(json.loads(await client.recv()))
                return messages

    messages = asyncio.run(exchange())
    assert [m["type"] for m in messages] == ["stream_start", "drift_report", "stream_end", "error", "heartbeat"]
    assert [m["seq"] for m in messages] == [1, 2, 3, 4, 5]
    assert messages[1]["payload"]["source"] == "mock"
