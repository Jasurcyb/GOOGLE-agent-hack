from __future__ import annotations

import asyncio
import json
import logging
import os
import re

import aio_pika

from diff_analyzer.analyzer import (
    DiffResult,
    FileChangeType,
    classify_delta,
    parse_git_diff,
)

SHA_RE = re.compile(r'^[0-9a-f]{7,40}$')

logger = logging.getLogger("diff-analyzer")

EXCHANGE_NAME = "rh.analysis"
QUEUE_NAME = "rh.diff-analyzer"
CONSUME_ROUTING_KEY = "repository.ready.v1"
PUBLISH_ROUTING_KEY = "diff.analyzed.v1"


class DiffAnalyzerConsumer:
    def __init__(self) -> None:
        self._url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    async def start(self) -> None:
        conn = await aio_pika.connect_robust(self._url)
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=1)

        exchange = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await ch.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=CONSUME_ROUTING_KEY)

        logger.info("DiffAnalyzer consuming on %s", CONSUME_ROUTING_KEY)

        async with queue.iterator() as queue_iter:
            async for msg in queue_iter:
                async with msg.process():
                    await self._handle(ch, exchange, msg.body)

    async def _handle(self, ch, exchange, body: bytes) -> None:
        data = json.loads(body)
        run_id = data["run_id"]

        diff_text = str(data.get("diff_text", ""))

        deltas = parse_git_diff(diff_text)

        result = DiffResult(
            run_id=run_id,
            files=deltas,
            total_added=sum(d.added_lines for d in deltas),
            total_deleted=sum(d.deleted_lines for d in deltas),
            renames=sum(1 for d in deltas if d.change_type == FileChangeType.RENAMED),
            new_files=sum(1 for d in deltas if d.change_type == FileChangeType.ADDED),
            deleted_files=sum(1 for d in deltas if d.change_type == FileChangeType.DELETED),
        )

        payload = {
            "run_id": run_id,
            "files_changed": len(deltas),
            "symbols_changed": 0,
            "renames_detected": result.renames,
            "new_files": result.new_files,
            "deleted_files": result.deleted_files,
            "total_added": result.total_added,
            "total_deleted": result.total_deleted,
            "file_deltas": [classify_delta(d) for d in deltas],
            "diff_truncated": bool(data.get("diff_truncated", False)),
            "source_snapshot_uri": data.get("source_snapshot_uri"),
            "repository": data.get("repository"),
            "head_sha": data.get("head_sha"),
            "base_sha": data.get("base_sha"),
            "changed_sources": data.get("changed_sources", []),
        }

        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=PUBLISH_ROUTING_KEY,
        )
        logger.info("Published diff.analyzed for run %s (%d files)", run_id, len(deltas))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = DiffAnalyzerConsumer()
    asyncio.run(consumer.start())


if __name__ == "__main__":
    main()
