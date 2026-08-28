from __future__ import annotations

import asyncio
import json
import logging
import os

import aio_pika

from repo_worker.worker import RepoWorker

logger = logging.getLogger("repo-worker")

EXCHANGE_NAME = "rh.analysis"
QUEUE_NAME = "rh.repo-worker"
CONSUME_ROUTING_KEY = "pr.received.v1"
PUBLISH_ROUTING_KEY = "repository.ready.v1"


class RepoWorkerConsumer:
    def __init__(self, worker: RepoWorker | None = None) -> None:
        self._worker = worker or RepoWorker()
        self._url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    async def start(self) -> None:
        conn = await aio_pika.connect_robust(self._url)
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=1)

        exchange = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await ch.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=CONSUME_ROUTING_KEY)

        logger.info("RepoWorker consuming on %s", CONSUME_ROUTING_KEY)

        async with queue.iterator() as queue_iter:
            async for msg in queue_iter:
                async with msg.process():
                    await self._handle(msg.body)
                    await self._publish_ready(ch, exchange, msg.body)

    async def _handle(self, body: bytes) -> None:
        data = json.loads(body)
        run_id = data["run_id"]
        repo = data["repository"]
        head_sha = data["head_sha"]
        base_sha = data.get("base_sha", "")

        logger.info("Processing run %s for %s#%s", run_id, repo, data.get("pr_number"))

        snapshot = await self._worker.process(run_id, repo, head_sha, base_sha)
        self._snapshot = snapshot

    async def _publish_ready(self, ch, exchange, body: bytes) -> None:
        data = json.loads(body)
        snapshot = getattr(self, "_snapshot", None)
        if snapshot is None:
            return

        payload = {
            "run_id": data["run_id"],
            "repository": data["repository"],
            "head_sha": data["head_sha"],
            "source_snapshot_uri": snapshot.snapshot_uri,
            "snapshot_sha256": snapshot.sha256,
            "file_count": snapshot.file_count,
            "diff_text": snapshot.diff_text,
            "diff_truncated": snapshot.diff_truncated,
            "changed_sources": snapshot.changed_sources or [],
        }
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload).encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=PUBLISH_ROUTING_KEY,
        )
        logger.info("Published repository.ready for run %s", data["run_id"])


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = RepoWorkerConsumer()
    asyncio.run(consumer.start())


if __name__ == "__main__":
    main()
