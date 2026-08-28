from __future__ import annotations

import asyncio
import json
import logging
import os

import aio_pika

from test_agent.planner import TestPlanner, TestPlan
from test_agent.sandbox import SandboxValidator

logger = logging.getLogger("test-agent")

EXCHANGE_NAME = "rh.analysis"
QUEUE_NAME = "rh.test-agent"
CONSUME_ROUTING_KEY = "recommendations.ready.v1"
PUBLISH_ROUTING_KEY = "publish.requested.v1"


class TestAgentConsumer:
    def __init__(self) -> None:
        self._planner = TestPlanner()
        self._sandbox = SandboxValidator()
        self._url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

    async def start(self) -> None:
        conn = await aio_pika.connect_robust(self._url)
        ch = await conn.channel()
        await ch.set_qos(prefetch_count=1)

        exchange = await ch.declare_exchange(EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True)
        queue = await ch.declare_queue(QUEUE_NAME, durable=True)
        await queue.bind(exchange, routing_key=CONSUME_ROUTING_KEY)

        logger.info("TestAgent consuming on %s", CONSUME_ROUTING_KEY)

        async with queue.iterator() as queue_iter:
            async for msg in queue_iter:
                async with msg.process():
                    await self._handle(ch, exchange, msg.body)

    async def _handle(self, ch, exchange, body: bytes) -> None:
        data = json.loads(body)
        run_id = data["run_id"]

        hypotheses = data.get("hypotheses", [])
        affected_assets = data.get("affected_assets", [])

        plans = self._planner.plan_tests(hypotheses, affected_assets)

        validated_plans: list[dict] = []
        for plan in plans:
            val_res = self._sandbox.validate(plan.body, framework=plan.framework)
            plan_dict = {
                "kind": plan.kind,
                "framework": plan.framework,
                "title": plan.title,
                "body": plan.body,
                "target_path": plan.target_path,
                "priority": plan.priority,
                "assertions": plan.assertions,
                "negative_case": plan.negative_case,
                "mock_boundaries": plan.mock_boundaries,
                "traceability_id": plan.traceability_id,
                "setup": plan.setup,
                "approval_required": plan.approval_required,
                "validation": {
                    "valid": val_res.valid,
                    "sha256": val_res.sha256,
                    "errors": val_res.errors,
                    "lint_passed": val_res.lint_passed,
                    "parse_passed": val_res.parse_passed,
                    "test_passed": val_res.test_passed,
                },
            }
            validated_plans.append(plan_dict)


        payload = {
            "run_id": run_id,
            "risk_score": data.get("risk_score", 0),
            "risk_level": data.get("risk_level", "low"),
            "regression_probability": data.get("regression_probability", 0.0),
            "impact_severity": data.get("impact_severity", 0.0),
            "confidence": data.get("confidence", 50),
            "requires_human_review": data.get("requires_human_review", True),
            "affected_assets": affected_assets,
            "recommended_tests": validated_plans,
            "review_summary": data.get("review_summary", ""),
            "business_impact": data.get("business_impact", ""),
            "root_cause": data.get("root_cause", ""),
            "hypotheses": hypotheses,
            "targets": ["github", "datahub"],
            "idempotency_key": f"publish-{run_id}",
        }

        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(payload, default=str).encode("utf-8"),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=PUBLISH_ROUTING_KEY,
        )
        logger.info("Published publish.requested for run %s (%d test plans)", run_id, len(validated_plans))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    consumer = TestAgentConsumer()
    asyncio.run(consumer.start())


if __name__ == "__main__":
    main()
