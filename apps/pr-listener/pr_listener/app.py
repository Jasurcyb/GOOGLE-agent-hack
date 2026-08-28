from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException, Request, status

from github_adapter import parse_webhook_event, verify_webhook_signature

from pr_listener.models import (
    make_outbox_event,
    make_pr_record,
    make_run_key,
    make_run_record,
)
from pr_listener.mq_publisher import RabbitMQPublisher
from pr_listener.postgres_repo import PostgresRunRepository
from pr_listener.rate_limiter import SlidingWindowRateLimiter

logger = logging.getLogger("pr-listener")

WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "rh_webhook_secret_dev")
ENABLE_PERSISTENCE = os.environ.get("RH_ENABLE_PERSISTENCE", "false").lower() == "true"
_rate_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo: PostgresRunRepository | None = None
    publisher: RabbitMQPublisher | None = None

    if ENABLE_PERSISTENCE:
        repo = PostgresRunRepository()
        app.state.repo = repo
        logger.info("PostgreSQL persistence enabled")
    else:
        app.state.repo = None
        app.state._deliveries: set[str] = set()
        logger.info("Persistence disabled — running in memory mode")

    try:
        publisher = RabbitMQPublisher()
        app.state.publisher = publisher
        logger.info("RabbitMQ publisher initialized")
    except Exception as exc:
        app.state.publisher = None
        logger.warning("RabbitMQ publisher not available: %s", exc)

    yield

    if repo:
        await repo.close()
    if publisher:
        await publisher.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Regression Hunter — PR Listener",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> dict[str, int]:
        return {"webhooks_received": 0, "webhooks_accepted": 0, "webhooks_duplicated": 0}

    @app.post("/v1/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
    async def github_webhook(
        request: Request,
        x_hub_signature_256: str = Header(..., alias="X-Hub-Signature-256"),
        x_github_event: str = Header(..., alias="X-GitHub-Event"),
        x_github_delivery: str = Header(..., alias="X-GitHub-Delivery"),
    ) -> dict:
        client_host = request.client.host if request.client else "unknown"
        if not _rate_limiter.allow(client_host):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        content_length = request.headers.get("content-length")
        max_bytes = 10 * 1024 * 1024
        if content_length and content_length.isdigit() and int(content_length) > max_bytes:
            raise HTTPException(status_code=413, detail="Payload too large")

        body_chunks = []
        total_size = 0
        async for chunk in request.stream():
            total_size += len(chunk)
            if total_size > max_bytes:
                raise HTTPException(status_code=413, detail="Payload too large")
            body_chunks.append(chunk)

        raw_body = b"".join(body_chunks)

        if not WEBHOOK_SECRET:
            logger.error("GITHUB_WEBHOOK_SECRET is not set — rejecting webhook")
            raise HTTPException(status_code=503, detail="Webhook secret not configured")

        if not verify_webhook_signature(raw_body, x_hub_signature_256, WEBHOOK_SECRET):
            raise HTTPException(status_code=403, detail="Invalid signature")

        repo = request.app.state.repo
        publisher = request.app.state.publisher

        if repo is not None:
            if await repo.delivery_seen(x_github_delivery):
                return {"status": "duplicate", "delivery_id": x_github_delivery}
        else:
            deliveries: set[str] = getattr(request.app.state, "_deliveries", set())
            if len(deliveries) > 10000:
                deliveries.clear()
            if x_github_delivery in deliveries:
                return {"status": "duplicate", "delivery_id": x_github_delivery}
            deliveries.add(x_github_delivery)

        try:
            payload_data = json.loads(raw_body)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        payload_data["event_type"] = x_github_event
        event = parse_webhook_event(json.dumps(payload_data).encode("utf-8"))

        if event is None:
            return {"status": "ignored", "event_type": x_github_event}

        if event.event_type == "pull_request" and event.action in ("opened", "synchronize", "reopened"):
            run_key = make_run_key(event.repository, event.pr_number, event.head_sha)

            if repo is not None:
                pr = make_pr_record(
                    installation_id=event.installation_id or "",
                    repo=event.repository,
                    pr_number=event.pr_number,
                    head_sha=event.head_sha,
                    base_sha=event.base_sha,
                    author_login=event.author_login,
                )
                pr = await repo.upsert_pr(pr)

                existing_run = await repo.get_run_by_key(run_key)
                if existing_run:
                    return {
                        "status": "duplicate_run",
                        "run_id": existing_run.id,
                        "run_key": run_key,
                    }

                run = make_run_record(pr_id=pr.id, run_key=run_key)
                await repo.create_run(run)

                outbox = make_outbox_event(
                    run_id=run.id,
                    event_type="com.regressionhunter.pr.received.v1",
                    payload={
                        "run_id": run.id,
                        "repository": event.repository,
                        "pr_number": event.pr_number,
                        "head_sha": event.head_sha,
                        "base_sha": event.base_sha,
                        "author_login": event.author_login,
                        "delivery_id": x_github_delivery,
                    },
                )
                await repo.append_outbox(outbox)

                if publisher:
                    await publisher.publish(
                        event_type="com.regressionhunter.pr.received.v1",
                        payload={
                            "run_id": run.id,
                            "repository": event.repository,
                            "pr_number": event.pr_number,
                            "head_sha": event.head_sha,
                            "base_sha": event.base_sha,
                            "author_login": event.author_login,
                            "event_id": outbox.payload.get("event_id", ""),
                        },
                    )
                    await repo.mark_outbox_published(outbox.id)

                return {
                    "status": "accepted",
                    "run_id": run.id,
                    "run_key": run_key,
                    "repository": event.repository,
                    "pr_number": event.pr_number,
                    "head_sha": event.head_sha,
                }
            else:
                import uuid

                run_id = str(uuid.uuid4())
                if publisher:
                    await publisher.publish(
                        event_type="com.regressionhunter.pr.received.v1",
                        payload={
                            "run_id": run_id,
                            "repository": event.repository,
                            "pr_number": event.pr_number,
                            "head_sha": event.head_sha,
                            "base_sha": event.base_sha,
                            "author_login": event.author_login,
                            "delivery_id": x_github_delivery,
                        },
                    )

                return {
                    "status": "accepted",
                    "run_id": run_id,
                    "run_key": run_key,
                    "repository": event.repository,
                    "pr_number": event.pr_number,
                    "head_sha": event.head_sha,
                }

        return {"status": "ignored", "action": getattr(event, "action", "")}

    return app
