from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any


@dataclass
class IncidentRecord:
    urn: str
    title: str
    severity: str
    start_time: str
    description: str = ""


@dataclass
class HistoricalSignals:
    """Aggregated historical signals for risk scoring."""
    prior_incidents: list[IncidentRecord] = field(default_factory=list)
    deploy_frequency_per_week: float = 0.0
    coverage_percentage: float = 0.0
    ownership_gap: bool = False
    oncall_gap: bool = False
    recurrent_incident: bool = False
    recent_rollbacks: int = 0

    def to_features(self) -> dict[str, Any]:
        return {
            "recurrent_incident": self.recurrent_incident,
            "high_deploy_frequency": self.deploy_frequency_per_week > 10,
            "ownership_gap": self.ownership_gap,
            "oncall_gap": self.oncall_gap,
            "coverage_percentage": self.coverage_percentage,
            "deploy_frequency_per_week": self.deploy_frequency_per_week,
            "recent_rollbacks": self.recent_rollbacks,
            "prior_incident_count": len(self.prior_incidents),
        }


def extract_historical_signals(
    datahub_incidents: list[dict],
    deploy_history: list[dict] | None = None,
    coverage_data: dict | None = None,
    owners: list[dict] | None = None,
) -> HistoricalSignals:
    """Extract historical signals from DataHub and application history."""
    signals = HistoricalSignals()

    for inc in datahub_incidents:
        signals.prior_incidents.append(IncidentRecord(
            urn=inc.get("urn", ""),
            title=inc.get("title", ""),
            severity=inc.get("severity", ""),
            start_time=inc.get("start_time", ""),
            description=inc.get("description", ""),
        ))

    if datahub_incidents:
        sev_set = {i.severity.upper() for i in signals.prior_incidents}
        signals.recurrent_incident = bool(sev_set & {"SEV1", "SEV2"})

    if deploy_history:
        cutoff = datetime.now(timezone.utc) - timedelta(weeks=1)
        recent = [
            d for d in deploy_history
            if d.get("deployed_at")
            and datetime.fromisoformat(d["deployed_at"]) > cutoff
        ]
        signals.deploy_frequency_per_week = len(recent)
        signals.recent_rollbacks = sum(1 for d in recent if d.get("rolled_back", False))

    if coverage_data:
        signals.coverage_percentage = coverage_data.get("percentage", 0.0)

    if owners is not None:
        signals.ownership_gap = len(owners) == 0
        has_oncall = any(
            any(o.get("type", "").upper() in ("ONCALL", "ON_CALL") for o in owner_list)
            if isinstance(owner_list, list)
            else False
            for owner_list in [owners]
        )
        signals.oncall_gap = not has_oncall

    return signals
