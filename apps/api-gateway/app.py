from __future__ import annotations

import hmac
import json
import os
import time
from typing import Any

import asyncpg
import aio_pika
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

POSTGRES_DSN = os.environ.get("POSTGRES_DSN", "postgresql://rh:rh_dev_password@localhost:5432/regression_hunter")
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
JWT_SECRET = os.environ.get("RH_JWT_SECRET", os.environ.get("JWT_SECRET", ""))
API_KEY = os.environ.get("RH_API_KEY", os.environ.get("API_KEY", ""))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "local").lower()
ENABLE_AUTH = os.environ.get("RH_ENABLE_AUTH", "true").lower() == "true"

_pool: asyncpg.Pool | None = None
_security = HTTPBearer(auto_error=False)


async def verify_token(credentials: HTTPAuthorizationCredentials | None = Depends(_security)) -> str:
    if not ENABLE_AUTH:
        return "anonymous"
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")

    token = credentials.credentials

    # API key check using constant-time comparison
    if API_KEY and hmac.compare_digest(token, API_KEY):
        return "api-key-user"

    # HS256 is intentionally the only shared-secret mode. Do not mix HS and RS
    # algorithms with the same configured key material.
    if JWT_SECRET:
        try:
            import jwt
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"require": ["exp", "sub"]})
            return str(payload.get("sub", "authenticated_user"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )

    # Fallback if authentication is enabled but no secret is configured
    if not JWT_SECRET and not API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is enabled but RH_JWT_SECRET or RH_API_KEY is not configured",
        )

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")



async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=2, max_size=10)
    return _pool


async def get_db() -> asyncpg.Connection:
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


class CreateRunRequest(BaseModel):
    repository: str
    pr_number: int
    head_sha: str
    base_sha: str
    author_login: str = "manual"
    trigger: str = "manual"


class OverrideRequest(BaseModel):
    auditor: str
    reason: str
    expiry_hours: int = 24


class ApprovalRequest(BaseModel):
    approver: str
    comment: str = ""


def create_app() -> FastAPI:
    app = FastAPI(
        title="Regression Hunter — API Gateway",
        version="0.1.0",
    )

    if not ENABLE_AUTH and ENVIRONMENT not in {"local", "test", "development"}:
        raise RuntimeError("RH_ENABLE_AUTH=false is permitted only in local/test/development")

    @app.on_event("shutdown")
    async def close_pool() -> None:
        global _pool
        if _pool is not None:
            await _pool.close()
            _pool = None

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        try:
            pool = await get_pool()
            await pool.fetchval("SELECT 1")
        except Exception as exc:
            raise HTTPException(status_code=503, detail="database_unavailable") from exc
        return {"status": "ready"}

    @app.get("/metrics")
    async def metrics() -> dict[str, int]:
        return {"runs_total": 0, "runs_active": 0}

    @app.post("/v1/runs", status_code=status.HTTP_202_ACCEPTED)
    async def create_run(
        req: CreateRunRequest,
        conn: asyncpg.Connection = Depends(get_db),
        user: str = Depends(verify_token),
    ) -> dict[str, Any]:
        run_key = f"{req.repository}:{req.pr_number}:{req.head_sha}:v1"

        pr_row = await conn.fetchrow(
            """
            INSERT INTO pull_requests
                (id, github_installation_id, repository_full_name,
                 pr_number, head_sha, base_sha, author_login, state)
            VALUES (gen_random_uuid(), 'manual', $1, $2, $3, $4, $5, 'open')
            ON CONFLICT (repository_full_name, pr_number, head_sha)
            DO UPDATE SET state = EXCLUDED.state
            RETURNING id
            """,
            req.repository, req.pr_number, req.head_sha, req.base_sha, req.author_login,
        )
        pr_id = str(pr_row["id"])

        import uuid

        run_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO analysis_runs (id, pr_id, run_key, status, trigger, policy_version)
            VALUES ($1, $2, $3, 'pending', $4, 'v1')
            ON CONFLICT (run_key) DO NOTHING
            """,
            run_id, pr_id, run_key, req.trigger,
        )

        existing = await conn.fetchval(
            "SELECT id FROM analysis_runs WHERE run_key = $1",
            run_key,
        )
        actual_run_id = str(existing) if existing else run_id

        return {"run_id": actual_run_id, "status": "pending", "run_key": run_key}

    @app.get("/v1/runs/{run_id}")
    async def get_run(
        run_id: str,
        conn: asyncpg.Connection = Depends(get_db),
        user: str = Depends(verify_token),
    ) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT r.id, r.run_key, r.status, r.trigger, r.policy_version,
                   r.source_snapshot_uri, r.started_at, r.completed_at, r.failure_code,
                   p.repository_full_name, p.pr_number, p.head_sha, p.base_sha, p.author_login
            FROM analysis_runs r
            JOIN pull_requests p ON r.pr_id = p.id
            WHERE r.id = $1
            """,
            run_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Run not found")

        assessment = await conn.fetchrow(
            "SELECT risk_score, risk_level, regression_probability, impact_severity, confidence, requires_review FROM risk_assessments WHERE run_id = $1",
            run_id,
        )

        return {
            "run_id": str(row["id"]),
            "run_key": row["run_key"],
            "status": row["status"],
            "trigger": row["trigger"],
            "repository": row["repository_full_name"],
            "pr_number": row["pr_number"],
            "head_sha": row["head_sha"],
            "risk_assessment": {
                "risk_score": assessment["risk_score"],
                "risk_level": assessment["risk_level"],
                "regression_probability": float(assessment["regression_probability"]),
                "impact_severity": float(assessment["impact_severity"]),
                "confidence": assessment["confidence"],
                "requires_review": assessment["requires_review"],
            } if assessment else None,
        }

    @app.get("/v1/runs/{run_id}/graph")
    async def get_run_graph(
        run_id: str,
        view: str = Query("impact", regex="^(impact|code|full)$"),
        conn: asyncpg.Connection = Depends(get_db),
        user: str = Depends(verify_token),
    ) -> dict[str, Any]:
        nodes = await conn.fetch(
            "SELECT node_key, node_kind, datahub_urn, distance, criticality, owners, evidence FROM impact_nodes WHERE run_id = $1 ORDER BY distance LIMIT 500",
            run_id,
        )
        edges = await conn.fetch(
            "SELECT from_node, to_node, edge_kind, hop, evidence FROM impact_edges WHERE run_id = $1 LIMIT 1000",
            run_id,
        )

        return {
            "run_id": run_id,
            "view": view,
            "nodes": [
                {
                    "id": r["node_key"],
                    "kind": r["node_kind"],
                    "urn": r["datahub_urn"],
                    "distance": r["distance"],
                    "criticality": float(r["criticality"]),
                    "owners": r["owners"],
                }
                for r in nodes
            ],
            "edges": [
                {
                    "source": r["from_node"],
                    "target": r["to_node"],
                    "kind": r["edge_kind"],
                    "hop": r["hop"],
                }
                for r in edges
            ],
        }

    @app.get("/v1/pull-requests/{repo}/{number}/latest")
    async def get_latest_for_pr(
        repo: str,
        number: int,
        conn: asyncpg.Connection = Depends(get_db),
        user: str = Depends(verify_token),
    ) -> dict[str, Any]:
        row = await conn.fetchrow(
            """
            SELECT r.id, r.run_key, r.status, r.started_at, r.completed_at,
                   p.head_sha, p.base_sha, p.author_login
            FROM analysis_runs r
            JOIN pull_requests p ON r.pr_id = p.id
            WHERE p.repository_full_name = $1 AND p.pr_number = $2
            ORDER BY r.started_at DESC LIMIT 1
            """,
            repo, number,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="No analysis found for this PR")

        return {
            "run_id": str(row["id"]),
            "run_key": row["run_key"],
            "status": row["status"],
            "head_sha": row["head_sha"],
            "author": row["author_login"],
            "started_at": str(row["started_at"]),
            "completed_at": str(row["completed_at"]) if row["completed_at"] else None,
        }

    @app.get("/v1/runs/{run_id}/events")
    async def stream_events(
        run_id: str,
        user: str = Depends(verify_token),
    ) -> StreamingResponse:
        async def event_stream():
            yield f"event: connected\ndata: {json.dumps({'run_id': run_id})}\n\n"
            while True:
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': int(time.time())})}\n\n"
                await __import__("asyncio").sleep(15)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/v1/recommendations/{rec_id}/approve")
    async def approve_recommendation(
        rec_id: str,
        req: ApprovalRequest,
        conn: asyncpg.Connection = Depends(get_db),
        user: str = Depends(verify_token),
    ) -> dict[str, Any]:
        result = await conn.execute(
            "UPDATE recommendations SET status = 'approved' WHERE id = $1",
            rec_id,
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Recommendation not found")

        return {"status": "approved", "recommendation_id": rec_id, "approver": user}

    @app.post("/v1/runs/{run_id}/publish")
    async def retry_publish(
        run_id: str,
        conn: asyncpg.Connection = Depends(get_db),
        user: str = Depends(verify_token),
    ) -> dict[str, Any]:
        return {"status": "publish_requested", "run_id": run_id}

    @app.post("/v1/runs/{run_id}/override")
    async def override_risk(
        run_id: str,
        req: OverrideRequest,
        conn: asyncpg.Connection = Depends(get_db),
        user: str = Depends(verify_token),
    ) -> dict[str, Any]:
        if not req.reason.strip():
            raise HTTPException(status_code=422, detail="reason is required")

        return {
            "status": "overridden",
            "run_id": run_id,
            "auditor": user,
            "reason": req.reason,
            "expiry_hours": req.expiry_hours,
        }

    return app


app = create_app()
