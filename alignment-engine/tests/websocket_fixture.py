import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
from core.analyzer import Analyzer
from core.schemas import DataSliceContext, SampleRecord


class Socket:
    def __init__(self, incoming=()):
        self.incoming = incoming
        self.sent = []

    async def send(self, message):
        self.sent.append(message)

    def __aiter__(self):
        self.iterator = iter(self.incoming)
        return self

    async def __anext__(self):
        try:
            return next(self.iterator)
        except StopIteration:
            raise StopAsyncIteration


def context():
    return DataSliceContext(
        source="fixture",
        extraction_timestamp="2026-10-27T00:00:00+00:00",
        total_count=3,
        sample_records=[
            SampleRecord(image_id=name, label="fixture", embedding=[value] * 128)
            for name, value in [("near-a", 0.0), ("near-b", 1.0), ("far", 5.0)]
        ],
    )


def run(incoming=()):
    class FixtureExtractor:
        def __init__(self, **kwargs):
            pass

        def extract(self):
            return context()

    class FixtureAnalyzer(Analyzer):
        def analyze(self, ctx):
            return self._analyze_numpy(ctx)

    original_extractor, original_analyzer = server.Extractor, server.Analyzer
    server.Extractor, server.Analyzer = FixtureExtractor, FixtureAnalyzer
    try:
        socket = Socket(incoming)
        asyncio.run(server.pipeline_handler(socket))
        return socket.sent
    finally:
        server.Extractor, server.Analyzer = original_extractor, original_analyzer


if __name__ == "__main__":
    print(json.dumps(run(['{"type":"heartbeat"}'])))
