from __future__ import annotations

from pydantic import BaseModel, Field


class PolicyFloor(BaseModel):
    conditions: list[str]
    floor_score: int
    description: str


class PolicyConfig(BaseModel):
    version: str = "v1"
    risk_thresholds: dict[str, tuple[int, int]] = Field(
        default_factory=lambda: {
            "low": (0, 29),
            "medium": (30, 59),
            "high": (60, 79),
            "critical": (80, 100),
        }
    )
    policy_floors: list[PolicyFloor] = Field(
        default_factory=lambda: [
            PolicyFloor(
                conditions=[
                    "breaking_change",
                    "authoritative_payment_or_regulated_path",
                    "no_regression_test",
                ],
                floor_score=85,
                description="Breaking change with authoritative path to regulated/payment asset and no relevant regression test",
            )
        ]
    )
    confidence_neutral_threshold: int = 70
    allowed_actions: list[str] = Field(
        default_factory=lambda: [
            "github_check_run",
            "github_label",
            "github_comment_upsert",
            "datahub_report_document",
            "datahub_assessment_entity",
            "datahub_structured_properties",
            "datahub_at_risk_tag",
            "datahub_assertion_candidate",
        ]
    )
    lineage_default_depth: int = 3
    lineage_max_depth: int = 5
    max_tool_calls: int = 12
    max_lineage_expansions: int = 3
    token_ceiling: int = 80000
    graph_max_nodes: int = 10000
    graph_max_edges: int = 50000
