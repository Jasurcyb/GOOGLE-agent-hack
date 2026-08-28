from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import json


@dataclass
class CorpusEntry:
    pr_id: str
    repository: str
    pr_number: int
    head_sha: str
    merged_at: datetime
    features: dict[str, Any]
    predicted_score: int
    predicted_probability: float
    actual_outcome: str
    incident_severity: str | None = None
    rollback: bool = False
    tags: list[str] = field(default_factory=list)


class EvaluationCorpus:
    """Benchmark corpus of historical PRs linked to actual outcomes."""

    def __init__(self) -> None:
        self._entries: list[CorpusEntry] = []

    def add(self, entry: CorpusEntry) -> None:
        self._entries.append(entry)

    def load_from_json(self, path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            return
        data = json.loads(p.read_text(encoding="utf-8"))
        for item in data.get("entries", []):
            self.add(CorpusEntry(
                pr_id=item["pr_id"],
                repository=item["repository"],
                pr_number=item["pr_number"],
                head_sha=item["head_sha"],
                merged_at=datetime.fromisoformat(item["merged_at"]),
                features=item.get("features", {}),
                predicted_score=item.get("predicted_score", 0),
                predicted_probability=item.get("predicted_probability", 0.0),
                actual_outcome=item.get("actual_outcome", "no_incident"),
                incident_severity=item.get("incident_severity"),
                rollback=item.get("rollback", False),
                tags=item.get("tags", []),
            ))

    def save_to_json(self, path: str | Path) -> None:
        data = {
            "entries": [
                {
                    "pr_id": e.pr_id,
                    "repository": e.repository,
                    "pr_number": e.pr_number,
                    "head_sha": e.head_sha,
                    "merged_at": e.merged_at.isoformat(),
                    "features": e.features,
                    "predicted_score": e.predicted_score,
                    "predicted_probability": e.predicted_probability,
                    "actual_outcome": e.actual_outcome,
                    "incident_severity": e.incident_severity,
                    "rollback": e.rollback,
                    "tags": e.tags,
                }
                for e in self._entries
            ]
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def split_by_repo_and_time(
        self,
        test_repos: list[str] | None = None,
        cutoff_date: datetime | None = None,
    ) -> tuple[list[CorpusEntry], list[CorpusEntry]]:
        """Split to prevent leakage: by repository and time."""
        if test_repos is None:
            test_repos = []

        train: list[CorpusEntry] = []
        test: list[CorpusEntry] = []

        for entry in self._entries:
            if entry.repository in test_repos:
                test.append(entry)
            elif cutoff_date and entry.merged_at >= cutoff_date:
                test.append(entry)
            else:
                train.append(entry)

        return train, test

    @property
    def size(self) -> int:
        return len(self._entries)

    @property
    def entries(self) -> list[CorpusEntry]:
        return list(self._entries)
