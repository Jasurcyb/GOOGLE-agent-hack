from __future__ import annotations

import asyncio
import json
import logging
import os

import aio_pika

from risk_engine.scorer import RiskFeatures, score

from domain.policy import PolicyConfig

logger = logging.getLogger("risk-engine")

EXCHANGE_NAME = "rh.analysis"
QUEUE_NAME = "rh.risk-engine"
CONSUME_ROUTING_KEY = "context.built.v1"
PUBLISH_ROUTING_KEY = "assessment.scored.v1"


class RiskEngineConsumer:
    def __init__(self, policy: PolicyConfig | None = None) -> None:
        self._policy = policy or PolicyConfig()
        self._url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    async def start(self) -> None:
        conn = await aio_pika.connect_robust(self._url)
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=1)

        exchange = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await ch.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=CONSUME_ROUTING_KEY)

        logger.info("RiskEngine consuming on %s", CONSUME_ROUTING_KEY)

        async with queue.iterator() as queue_iter:
            async for msg in queue_iter:
                async with msg.process():
                    await self._handle(ch, exchange, msg.body)

    async def _handle(self, ch, exchange, body: bytes) -> None:
        data = json.loads(body)
        run_id = data["run_id"]

        features = RiskFeatures.from_bundle(data)
        assessment = score(run_id, features, self._policy)

        payload = {
            "run_id": run_id,
            "evidence_bundle": data.get("evidence_bundle", {}),
            "affected_assets": data.get("evidence_bundle", {}).get("datahub_impact", {}).get("assets", []),
            "risk_score": assessment.risk_score,
            "risk_level": assessment.risk_level.value,
            "regression_probability": assessment.regression_probability,
            "impact_severity": assessment.impact_severity,
            "confidence": assessment.confidence,
            "requires_review": assessment.requires_review,
            "model_version": assessment.model_version,
            "decision": assessment.decision,
            "factors": [
                {
                    "factor_code": f.factor_code,
                    "feature_value": f.feature_value,
                    "points": f.points,
                    "evidence_refs": f.evidence_refs,
                }
                for f in assessment.factors
            ],
        }

        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload, default=str).encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=PUBLISH_ROUTING_KEY,
        )
        logger.info(
            "Published assessment.scored for run %s — score=%d level=%s",
            run_id, assessment.risk_score, assessment.risk_level.value,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = RiskEngineConsumer()
    asyncio.run(consumer.start())


if __name__ == "__main__":
    main()
