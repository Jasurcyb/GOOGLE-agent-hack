from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from pr_listener.models import (
    OutboxEvent,
    PRRecord,
    RunRecord,
    make_outbox_event,
)
from domain.enums import RunStatus


class PostgresRunRepository:
    def __init__(self, dsn: str | None = None) -> None:
        self._dsn = dsn or os.environ.get(
            "POSTGRES_DSN",
            "postgresql://rh:rh_dev_password@localhost:5432/regression_hunter",
        )
        self._pool: asyncpg.Pool | None = None

    async def _ensure_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def upsert_pr(self, pr: PRRecord) -> PRRecord:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO pull_requests
                    (id, github_installation_id, repository_full_name,
                     pr_number, head_sha, base_sha, author_login, state)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (repository_full_name, pr_number, head_sha)
                DO UPDATE SET state = EXCLUDED.state, author_login = EXCLUDED.author_login
                RETURNING id
                """,
                pr.id,
                pr.github_installation_id,
                pr.repository_full_name,
                pr.pr_number,
                pr.head_sha,
                pr.base_sha,
                pr.author_login,
                pr.state,
            )
            pr.id = str(row["id"])
        return pr

    async def get_pr_by_repo_number_sha(
        self, repo: str, pr_number: int, head_sha: str
    ) -> PRRecord | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, github_installation_id, repository_full_name,
                       pr_number, head_sha, base_sha, author_login, state
                FROM pull_requests
                WHERE repository_full_name = $1 AND pr_number = $2 AND head_sha = $3
                """,
                repo,
                pr_number,
                head_sha,
            )
            if row is None:
                return None
            return PRRecord(
                id=str(row["id"]),
                github_installation_id=str(row["github_installation_id"]),
                repository_full_name=row["repository_full_name"],
                pr_number=row["pr_number"],
                head_sha=row["head_sha"],
                base_sha=row["base_sha"],
                author_login=row["author_login"],
                state=row["state"],
            )

    async def create_run(self, run: RunRecord) -> RunRecord:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO analysis_runs
                    (id, pr_id, run_key, status, trigger, policy_version, started_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (run_key) DO NOTHING
                """,
                run.id,
                run.pr_id,
                run.run_key,
                run.status.value,
                run.trigger,
                run.policy_version,
                run.started_at,
            )
        return run

    async def get_run_by_key(self, run_key: str) -> RunRecord | None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, pr_id, run_key, status, trigger, policy_version
                FROM analysis_runs WHERE run_key = $1
                """,
                run_key,
            )
            if row is None:
                return None
            return RunRecord(
                id=str(row["id"]),
                run_key=row["run_key"],
                pr_id=str(row["pr_id"]),
                status=RunStatus(row["status"]),
                trigger=row["trigger"],
                policy_version=row["policy_version"],
            )

    async def append_outbox(self, event: OutboxEvent) -> OutboxEvent:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO outbox_events
                    (id, aggregate_type, aggregate_id, event_type,
                     schema_version, payload, occurred_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT DO NOTHING
                """,
                event.id,
                event.aggregate_type,
                event.aggregate_id,
                event.event_type,
                event.schema_version,
                json.dumps(event.payload),
                event.occurred_at,
            )
        return event

    async def mark_outbox_published(self, event_id: str) -> None:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE outbox_events SET published_at = now() WHERE id = $1",
                event_id,
            )

    async def get_unpublished_outbox(self, limit: int = 100) -> list[OutboxEvent]:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, aggregate_type, aggregate_id, event_type,
                       schema_version, payload, occurred_at
                FROM outbox_events
                WHERE published_at IS NULL
                ORDER BY occurred_at
                LIMIT $1
                """,
                limit,
            )
            return [
                OutboxEvent(
                    id=str(r["id"]),
                    aggregate_type=r["aggregate_type"],
                    aggregate_id=str(r["aggregate_id"]),
                    event_type=r["event_type"],
                    schema_version=r["schema_version"],
                    payload=r["payload"] if isinstance(r["payload"], dict) else json.loads(r["payload"]),
                    occurred_at=r["occurred_at"],
                )
                for r in rows
            ]

    async def delivery_seen(self, delivery_id: str) -> bool:
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM outbox_events WHERE payload->>'delivery_id' = $1 LIMIT 1",
                delivery_id,
            )
            return row is not None

    async def record_delivery(self, delivery_id: str) -> None:
        if not delivery_id:
            raise ValueError("delivery_id is required")
