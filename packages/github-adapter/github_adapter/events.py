from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WebhookEvent:
    event_type: str
    action: str
    repository: str
    pr_number: int | None
    head_sha: str | None
    base_sha: str | None
    author_login: str | None
    installation_id: str | None
    raw: dict[str, Any]


def parse_webhook_event(payload: bytes) -> WebhookEvent | None:
    data: dict[str, Any] = json.loads(payload)
    event_type = data.get("event_type", "")

    if event_type == "pull_request":
        pr = data.get("pull_request", {})
        repo = data.get("repository", {}).get("full_name", "")
        return WebhookEvent(
            event_type="pull_request",
            action=data.get("action", ""),
            repository=repo,
            pr_number=pr.get("number"),
            head_sha=pr.get("head", {}).get("sha"),
            base_sha=pr.get("base", {}).get("sha"),
            author_login=pr.get("user", {}).get("login"),
            installation_id=str(data.get("installation", {}).get("id", "")),
            raw=data,
        )

    if event_type == "push":
        repo = data.get("repository", {}).get("full_name", "")
        return WebhookEvent(
            event_type="push",
            action="push",
            repository=repo,
            pr_number=None,
            head_sha=data.get("after"),
            base_sha=data.get("before"),
            author_login=data.get("sender", {}).get("login"),
            installation_id=str(data.get("installation", {}).get("id", "")),
            raw=data,
        )

    return None
