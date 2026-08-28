from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from domain.enums import RiskLevel, RunStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PullRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    github_installation_id: str
    repository_full_name: str
    pr_number: int
    head_sha: str
    base_sha: str
    author_login: str
    state: str = "open"


class AnalysisRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    pr_id: UUID
    run_key: str
    status: RunStatus = RunStatus.PENDING
    trigger: str = "webhook"
    policy_version: str = "v1"
    source_snapshot_uri: str | None = None
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    failure_code: str | None = None


class Delivery(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    destination: str
    idempotency_key: str
    external_id: str | None = None
    payload_hash: str | None = None
    status: str = "pending"
    attempt_count: int = 0
    last_error: str | None = None


class Recommendation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    assessment_id: UUID
    kind: str
    priority: int
    title: str
    body: str
    target_path: str | None = None
    target_urn: str | None = None
    status: str = "proposed"
    evidence_refs: list[str] = Field(default_factory=list)
    approval_required: bool = True
