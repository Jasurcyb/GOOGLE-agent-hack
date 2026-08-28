from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import aio_pika


@dataclass
class ReplayEntry:
    event_type: str
    payload: dict[str, Any]
    timestamp: float
    error: str | None = None
    retries: int = 0


class ReplayConsole:
    """Dead-letter queue replay console for failed events."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        self._dlq_entries: list[ReplayEntry] = []

    def record_failure(self, event_type: str, payload: dict[str, Any], error: str) -> None:
        self._dlq_entries.append(ReplayEntry(
            event_type=event_type,
            payload=payload,
            timestamp=time.time(),
            error=error,
        ))

    def list_failures(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            {
                "event_type": e.event_type,
                "payload": e.payload,
                "timestamp": e.timestamp,
                "error": e.error,
                "retries": e.retries,
            }
            for e in self._dlq_entries[:limit]
        ]

    async def replay(self, index: int) -> dict[str, Any]:
        if index < 0 or index >= len(self._dlq_entries):
            return {"status": "error", "message": "Invalid index"}

        entry = self._dlq_entries[index]
        entry.retries += 1

        conn = await aio_pika.connect_robust(self._url)
        async with conn:
            ch = await conn.channel()
            exchange = await ch.declare_exchange(
                "rh.analysis", aio_pika.ExchangeType.TOPIC, durable=True
            )

            routing_key = entry.event_type
            await exchange.publish(
                aio_pika.Message(
                    body=json.dumps(entry.payload, default=str).encode("utf-8"),
                    content_type="application/json",
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=routing_key,
            )

        return {"status": "replayed", "event_type": entry.event_type, "retries": entry.retries}

    async def replay_all(self) -> dict[str, Any]:
        replayed = 0
        failed = 0

        for i in range(len(self._dlq_entries)):
            try:
                await self.replay(i)
                replayed += 1
            except Exception:
                failed += 1

        return {"replayed": replayed, "failed": failed, "total": len(self._dlq_entries)}

    def clear(self) -> None:
        self._dlq_entries.clear()
