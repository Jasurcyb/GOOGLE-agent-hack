from __future__ import annotations

import asyncio
import json
import logging
import os

import aio_pika

from reasoning_agent.agent import ReasoningAgent
from reasoning_agent.state import AgentState

logger = logging.getLogger("reasoning-agent")

EXCHANGE_NAME = "rh.analysis"
QUEUE_NAME = "rh.reasoning-agent"
CONSUME_ROUTING_KEY = "assessment.scored.v1"
PUBLISH_ROUTING_KEY = "recommendations.ready.v1"


class ReasoningAgentConsumer:
    def __init__(self) -> None:
        self._agent = ReasoningAgent()
        self._url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    async def start(self) -> None:
        conn = await aio_pika.connect_robust(self._url)
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=1)

        exchange = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await ch.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=CONSUME_ROUTING_KEY)

        logger.info("ReasoningAgent consuming on %s", CONSUME_ROUTING_KEY)

        async with queue.iterator() as queue_iter:
            async for msg in queue_iter:
                async with msg.process():
                    await self._handle(ch, exchange, msg.body)

    async def _handle(self, ch, exchange, body: bytes) -> None:
        data = json.loads(body)
        run_id = data["run_id"]

        evidence_bundle = data.get("evidence_bundle", {})

        result = await self._agent.reason(evidence_bundle)

        payload = {
            "run_id": run_id,
            "risk_score": data.get("risk_score", 0),
            "risk_level": data.get("risk_level", "low"),
            "regression_probability": data.get("regression_probability", 0.0),
            "impact_severity": data.get("impact_severity", 0.0),
            "confidence": data.get("confidence", 50),
            "requires_human_review": data.get("requires_human_review", True),
            "hypotheses": result.get("hypotheses", []),
            "affected_assets": result.get("affected_assets", data.get("affected_assets", [])),
            "recommended_tests": result.get("recommended_tests", []),
            "review_summary": result.get("review_summary", ""),
            "business_impact": result.get("business_impact", ""),
            "root_cause": result.get("root_cause", ""),
            "unverified_count": result.get("unverified_count", 0),
        }

        routing_key = PUBLISH_ROUTING_KEY if result.get("recommended_tests") else "analysis.partial.v1"

        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload, default=str).encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
        logger.info("Published recommendations.ready for run %s", run_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = ReasoningAgentConsumer()
    asyncio.run(consumer.start())


if __name__ == "__main__":
    main()
