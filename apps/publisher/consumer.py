from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any

import aio_pika

from publisher.datahub_publisher import DataHubPublisher
from publisher.github_publisher import GitHubPublisher

logger = logging.getLogger("publisher")

EXCHANGE_NAME = "rh.analysis"
DELIVERY_EXCHANGE = "rh.delivery"
QUEUE_NAME = "rh.publisher"
CONSUME_ROUTING_KEY = "publish.requested.v1"

INITIAL_BACKOFF = 1.0
MAX_BACKOFF = 60.0
MAX_RETRIES = 5


class DeliveryLedger:
    """In-memory idempotent delivery ledger (replace with PostgreSQL in production)."""

    def __init__(self) -> None:
        self._deliveries: dict[str, dict[str, Any]] = {}

    def is_delivered(self, idempotency_key: str, target: str) -> bool:
        key = f"{idempotency_key}:{target}"
        entry = self._deliveries.get(key)
        return entry is not None and entry.get("status") == "published"

    def record(self, idempotency_key: str, target: str, status: str, external_id: str | None = None) -> None:
        key = f"{idempotency_key}:{target}"
        self._deliveries[key] = {
            "status": status,
            "external_id": external_id,
            "attempt_count": self._deliveries.get(key, {}).get("attempt_count", 0) + 1,
            "timestamp": time.time(),
        }

    def get_status(self, idempotency_key: str, target: str) -> str | None:
        key = f"{idempotency_key}:{target}"
        return self._deliveries.get(key, {}).get("status")


class PublisherConsumer:
    def __init__(self) -> None:
        self._datahub_pub = DataHubPublisher()
        self._github_pub = GitHubPublisher()
        self._ledger = DeliveryLedger()
        self._url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    async def start(self) -> None:
        conn = await aio_pika.connect_robust(self._url)
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=1)

        exchange = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
        delivery_exchange = await ch.declare_exchange(
            DELIVERY_EXCHANGE, aio_pika.ExchangeType.TOPIC, durable=True
        )
        queue = await ch.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=CONSUME_ROUTING_KEY)

        logger.info("Publisher consuming on %s", CONSUME_ROUTING_KEY)

        async with queue.iterator() as queue_iter:
            async for msg in queue_iter:
                async with msg.process():
                    await self._handle(ch, delivery_exchange, msg.body)

    async def _handle(self, ch, delivery_exchange, body: bytes) -> None:
        data = json.loads(body)
        run_id = data["run_id"]
        idempotency_key = data.get("idempotency_key", f"publish-{run_id}")

        targets = data.get("targets", ["github", "datahub"])
        deliveries: list[dict[str, Any]] = []

        if "datahub" in targets:
            dh_deliveries = await self._retry_delivery(
                idempotency_key, "datahub",
                self._datahub_pub.publish,
                run_id=run_id,
                repo=data.get("repository", ""),
                pr_number=data.get("pr_number", 0),
                head_sha=data.get("head_sha", ""),
                assessment=data,
            )
            deliveries.extend(dh_deliveries)

        if "github" in targets:
            gh_deliveries = await self._retry_delivery(
                idempotency_key, "github",
                self._github_pub.publish,
                repo=data.get("repository", ""),
                pr_number=data.get("pr_number", 0),
                head_sha=data.get("head_sha", ""),
                assessment=data,
            )
            deliveries.extend(gh_deliveries)

        for d in deliveries:
            d["run_id"] = run_id
            await delivery_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(d, default=str).encode("utf-8"),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key="published.v1",
            )

        logger.info("Publisher completed for run %s: %d deliveries", run_id, len(deliveries))

    async def _retry_delivery(
        self,
        idempotency_key: str,
        target: str,
        publish_fn: Any,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if self._ledger.is_delivered(idempotency_key, target):
            logger.info("Delivery %s:%s already published — skipping", idempotency_key, target)
            return [{"target": target, "status": "duplicate", "idempotency_key": idempotency_key}]

        backoff = INITIAL_BACKOFF
        for attempt in range(MAX_RETRIES):
            try:
                results = await publish_fn(**kwargs)
                for r in results:
                    self._ledger.record(idempotency_key, r.get("target", target), r.get("status", "unknown"))
                return results
            except Exception as e:
                logger.warning("Delivery attempt %d for %s failed: %s", attempt + 1, target, e)
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF)
                else:
                    self._ledger.record(idempotency_key, target, "failed")
                    return [{"target": target, "status": "failed", "error": str(e)}]

        return [{"target": target, "status": "failed"}]


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = PublisherConsumer()
    asyncio.run(consumer.start())


if __name__ == "__main__":
    main()
