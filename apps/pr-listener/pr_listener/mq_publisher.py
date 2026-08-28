from __future__ import annotations

import json
import os
from typing import Any

import aio_pika

EXCHANGE_NAME = "rh.analysis"
ROUTING_KEY = "pr.received.v1"


class RabbitMQPublisher:
    def __init__(self, url: str | None = None) -> None:
        self._url = url or os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.RobustChannel | None = None
        self._exchange: aio_pika.RobustExchange | None = None

    async def _ensure_channel(self) -> aio_pika.RobustChannel:
        if self._connection is None or self._connection.is_closed:
            self._connection = await aio_pika.connect_robust(self._url)
        if self._channel is None or self._channel.is_closed:
            self._channel = await self._connection.channel()
            await self._channel.declare_exchange(
                EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
            )
            self._exchange = await self._channel.get_exchange(EXCHANGE_NAME)
        return self._channel

    async def publish(self, event_type: str, payload: dict[str, Any], routing_key: str | None = None) -> None:
        ch = await self._ensure_channel()
        rk = routing_key or ROUTING_KEY
        body = json.dumps(payload, default=str).encode("utf-8")
        if self._exchange is None:
            raise RuntimeError("RabbitMQ exchange was not initialized")
        await self._exchange.publish(
            aio_pika.Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=rk,
        )

    async def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
