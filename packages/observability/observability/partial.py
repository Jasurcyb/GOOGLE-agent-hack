from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PartialResult:
    """Represents a partial analysis result when nonessential enrichment fails."""
    run_id: str
    completed_stages: list[str] = field(default_factory=list)
    failed_stages: list[dict[str, str]] = field(default_factory=list)
    has_core_result: bool = False
    fallback_message: str = ""

    def add_completed(self, stage: str) -> None:
        self.completed_stages.append(stage)

    def add_failed(self, stage: str, error: str) -> None:
        self.failed_stages.append({"stage": stage, "error": error})

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "completed_stages": self.completed_stages,
            "failed_stages": self.failed_stages,
            "has_core_result": self.has_core_result,
            "fallback_message": self.fallback_message,
        }


def build_partial_result(
    run_id: str,
    completed: list[str],
    failed_stage: str,
    error: str,
) -> PartialResult:
    return PartialResult(
        run_id=run_id,
        completed_stages=completed,
        failed_stages=[{"stage": failed_stage, "error": error}],
        has_core_result="risk_engine" in completed,
        fallback_message=f"Analysis partially completed. Stage '{failed_stage}' failed: {error}. Core risk assessment is available.",
    )
