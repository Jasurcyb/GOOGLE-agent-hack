from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel

from contracts.models.enums import RunStatus


class RunRecord(BaseModel):
    id: str
    run_key: str
    pr_id: str
    status: RunStatus = RunStatus.PENDING
    trigger: str = "webhook"
    policy_version: str = "v1"
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


from pydantic import Field


class OutboxEvent(BaseModel):
    id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    schema_version: str = "1.0"
    payload: dict
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: datetime | None = None


class PRRecord(BaseModel):
    id: str
    github_installation_id: str
    repository_full_name: str
    pr_number: int
    head_sha: str
    base_sha: str
    author_login: str
    state: str = "open"


def make_run_key(repo: str, pr_number: int, head_sha: str, policy_version: str = "v1") -> str:
    return f"{repo}:{pr_number}:{head_sha}:{policy_version}"


def make_pr_record(
    installation_id: str,
    repo: str,
    pr_number: int,
    head_sha: str,
    base_sha: str,
    author_login: str,
) -> PRRecord:
    return PRRecord(
        id=str(uuid.uuid4()),
        github_installation_id=installation_id,
        repository_full_name=repo,
        pr_number=pr_number,
        head_sha=head_sha,
        base_sha=base_sha,
        author_login=author_login,
    )


def make_run_record(pr_id: str, run_key: str, trigger: str = "webhook") -> RunRecord:
    return RunRecord(
        id=str(uuid.uuid4()),
        run_key=run_key,
        pr_id=pr_id,
        trigger=trigger,
    )


def make_outbox_event(run_id: str, event_type: str, payload: dict) -> OutboxEvent:
    return OutboxEvent(
        id=str(uuid.uuid4()),
        aggregate_type="analysis_run",
        aggregate_id=run_id,
        event_type=event_type,
        payload={**payload, "event_id": str(uuid.uuid4())},
    )
