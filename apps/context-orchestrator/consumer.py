from __future__ import annotations

import asyncio
import json
import logging
import os

import aio_pika

from context_orchestrator.builder import ContextBuilder

logger = logging.getLogger("context-orchestrator")

EXCHANGE_NAME = "rh.analysis"
QUEUE_NAME = "rh.context-orchestrator"
CONSUME_ROUTING_KEY = "code.graph.built.v1"
PUBLISH_ROUTING_KEY = "context.built.v1"


class ContextOrchestratorConsumer:
    def __init__(self) -> None:
        self._url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        self._builder = ContextBuilder()

    async def start(self) -> None:
        connection = await aio_pika.connect_robust(self._url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        exchange = await channel.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await channel.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=CONSUME_ROUTING_KEY)
        async with queue.iterator() as iterator:
            async for message in iterator:
                async with message.process():
                    await self._handle(exchange, message.body)

    async def _handle(self, exchange: aio_pika.Exchange, body: bytes) -> None:
        data = json.loads(body)
        sources = {item["path"]: item["content"] for item in data.get("changed_sources", [])}
        bundle = await self._builder.build(
            run_id=data["run_id"],
            repo=data.get("repository", ""),
            head_sha=data.get("head_sha", ""),
            change_summary={
                "symbols": data.get("symbols", []),
                "semantic_deltas": [],
                "entry_points": data.get("entrypoints", []),
                "file_deltas": data.get("file_deltas", []),
            },
            code_impact={"call_paths": data.get("code_graph_edges", []), "unknown_resolution_count": 0},
            symbols=data.get("symbols", []),
            imports=data.get("imports", []),
            source_content=sources,
        )
        payload = {"run_id": data["run_id"], "evidence_bundle": bundle.model_dump(mode="json")}
        await exchange.publish(
            aio_pika.Message(body=json.dumps(payload, default=str).encode(), content_type="application/json", delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=PUBLISH_ROUTING_KEY,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ContextOrchestratorConsumer().start())


if __name__ == "__main__":
    main()
