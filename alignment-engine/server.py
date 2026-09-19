import asyncio
import json
import logging
import sys
from websockets.server import serve
from schemas import DataSliceContext, DriftReport, ReviewDecision
from core.extractor import Extractor
from core.analyzer import Analyzer
from core.reviewer import Reviewer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("websocket_server")

async def pipeline_handler(websocket):
    logger.info("Client connected.")
    try:
        # Start Pipeline
        await websocket.send(json.dumps({"type": "STREAM_START"}))
        
        extractor = Extractor(mock_sample_count=10)
        ctx = extractor.extract()
        
        # We can run Analyzer and Reviewer here or just mock it for now
        analyzer = Analyzer()
        report = analyzer.analyze(ctx)
        
        # Send drift report
        await websocket.send(json.dumps({
            "type": "DRIFT_REPORT",
            "seq": 1,
            "payload": {
                "drift_score": report.drift_score,
                "anomalous_ids": report.anomalous_ids,
                "reasons": report.reasons
            }
        }))
        
        # Send end of stream
        await websocket.send(json.dumps({"type": "STREAM_END"}))
        
        # Keep connection open for heartbeats
        async for message in websocket:
            data = json.loads(message)
            logger.info(f"Received: {data}")
            if data.get("type") == "heartbeat":
                await websocket.send(json.dumps({"type": "HEARTBEAT"}))
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        logger.info("Client disconnected.")

async def main():
    async with serve(pipeline_handler, "localhost", 8765):
        logger.info("WebSocket server listening on ws://localhost:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped.")
