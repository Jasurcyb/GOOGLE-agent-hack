from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
from typing import Any

import aio_pika

from code_intelligence.analyzer_protocol import SourceFile
from code_intelligence.python_analyzer.analyzer import PythonAnalyzer

logger = logging.getLogger("code-intelligence")

EXCHANGE_NAME = "rh.analysis"
QUEUE_NAME = "rh.code-intelligence"
CONSUME_ROUTING_KEY = "diff.analyzed.v1"
PUBLISH_ROUTING_KEY = "code.graph.built.v1"


class CodeIntelligenceConsumer:
    """Builds a normalized code graph from bounded, changed source files."""

    def __init__(self) -> None:
        self._url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
        self._analyzers = {"python": PythonAnalyzer()}

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
        sources = data.get("changed_sources", [])
        symbols: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        imports: list[str] = []
        entrypoints: list[dict[str, Any]] = []

        for item in sources:
            path, content = item.get("path", ""), item.get("content", "")
            language = self._language_for_path(path)
            analyzer = self._analyzers.get(language)
            if analyzer is None:
                continue
            for parsed in analyzer.parse([SourceFile(path=path, language=language, content=content)]):
                imports.extend(parsed.imports)
                symbols.extend(dataclasses.asdict(symbol) for symbol in parsed.symbols)
                entrypoints.extend(dataclasses.asdict(point) for point in parsed.entrypoints)
                for edge in analyzer.edges(parsed, parsed.symbols):
                    edge_dict = dataclasses.asdict(edge)
                    edge_dict["run_id"] = data["run_id"]
                    edges.append(edge_dict)

        payload = {
            "run_id": data["run_id"],
            "repository": data.get("repository", ""),
            "head_sha": data.get("head_sha", ""),
            "base_sha": data.get("base_sha", ""),
            "source_snapshot_uri": data.get("source_snapshot_uri"),
            "changed_sources": sources,
            "symbols": symbols,
            "changed_symbols": [symbol["id"] for symbol in symbols],
            "code_graph_edges": edges,
            "imports": imports,
            "entrypoints": entrypoints,
            "file_deltas": data.get("file_deltas", []),
            "diff_truncated": data.get("diff_truncated", False),
        }
        await exchange.publish(
            aio_pika.Message(body=json.dumps(payload, default=str).encode(), content_type="application/json", delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=PUBLISH_ROUTING_KEY,
        )

    @staticmethod
    def _language_for_path(path: str) -> str:
        return "python" if path.lower().endswith(".py") else "unknown"


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(CodeIntelligenceConsumer().start())


if __name__ == "__main__":
    main()
