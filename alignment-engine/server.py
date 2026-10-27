import asyncio
import argparse
from functools import partial
import json
import logging
import uuid

from websockets.exceptions import ConnectionClosed
from websockets.server import serve

from core.analyzer import Analyzer
from core.extractor import Extractor
from core.schemas import DataSliceContext, DriftReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("websocket_server")


def report_payload(report: DriftReport, context: DataSliceContext) -> dict:
    return {
        "reportId": str(uuid.uuid4()),
        "timestamp": context.extraction_timestamp,
        "analysisMode": report.analysis_mode,
        "source": context.source,
        "samples": [
            {
                "sampleId": sample.image_id,
                "centroidDistance": sample.drift_score,
                "isolationScore": None,
                "severity": None,
                "reason": sample.reason,
            }
            for sample in report.drift_samples
        ],
        "stats": {
            "totalSamples": context.total_count,
            "meanDistance": report.mean_distance,
            "threshold": report.threshold,
            "driftCount": len(report.drift_samples),
        },
    }


async def pipeline_handler(websocket, offline=False):
    logger.info("Client connected.")
    seq = 0

    async def send(message_type, payload=None):
        nonlocal seq
        message = json.dumps({"type": message_type, "seq": seq + 1, "payload": payload}, allow_nan=False)
        seq += 1
        await websocket.send(message)

    try:
        await send("stream_start")
        try:
            extractor = Extractor(mock_sample_count=10)
            ctx = extractor._extract_mock() if offline else extractor.extract()
            analyzer = Analyzer()
            report = analyzer._analyze_numpy(ctx) if offline else analyzer.analyze(ctx)
            await send("drift_report", report_payload(report, ctx))
        except ConnectionClosed:
            raise
        except Exception:
            logger.exception("Pipeline failed")
            await send("error", {"message": "Pipeline failed"})
        await send("stream_end")

        async for message in websocket:
            try:
                data = json.loads(message)
                if not isinstance(data, dict) or not isinstance(data.get("type"), str):
                    raise ValueError("Expected an object with a type")
                if data["type"].lower() == "heartbeat":
                    await send("heartbeat")
                else:
                    await send("error", {"message": "Unsupported message type"})
            except (ValueError, TypeError):
                await send("error", {"message": "Invalid message"})
    except ConnectionClosed:
        logger.info("Client disconnected.")


async def main(offline=False):
    async with serve(partial(pipeline_handler, offline=offline), "localhost", 8765):
        logger.info("WebSocket server listening on ws://localhost:8765")
        await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use local mock samples and NumPy only")
    args = parser.parse_args()
    try:
        asyncio.run(main(offline=args.offline))
    except KeyboardInterrupt:
        logger.info("Server stopped.")
