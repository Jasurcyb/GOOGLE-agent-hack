from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CloudEvent(BaseModel):
    specversion: str = "1.0"
    id: str = Field(default_factory=lambda: str(uuid4()))
    source: str
    type: str
    subject: str | None = None
    time: datetime = Field(default_factory=_utcnow)
    datacontenttype: str = "application/json"
    data: BaseModel

    model_config = {"arbitrary_types_allowed": True}


class PRReceivedData(BaseModel):
    run_id: str
    repository: str
    pr_number: int
    head_sha: str
    base_sha: str
    author_login: str
    action: str


class PRReceivedEvent(BaseModel):
    data: PRReceivedData

    @classmethod
    def envelope(cls, data: PRReceivedData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/pr-listener",
            type="com.regressionhunter.pr.received.v1",
            subject=f"github/{data.repository}#{data.pr_number}",
            data=data,
        )


class RepositoryReadyData(BaseModel):
    run_id: str
    repository: str
    head_sha: str
    source_snapshot_uri: str


class RepositoryReadyEvent(BaseModel):
    data: RepositoryReadyData

    @classmethod
    def envelope(cls, data: RepositoryReadyData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/repo-worker",
            type="com.regressionhunter.repository.ready.v1",
            subject=data.run_id,
            data=data,
        )


class DiffAnalyzedData(BaseModel):
    run_id: str
    files_changed: int
    symbols_changed: int
    renames_detected: int


class DiffAnalyzedEvent(BaseModel):
    data: DiffAnalyzedData

    @classmethod
    def envelope(cls, data: DiffAnalyzedData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/diff-analyzer",
            type="com.regressionhunter.diff.analyzed.v1",
            subject=data.run_id,
            data=data,
        )


class CodeGraphBuiltData(BaseModel):
    run_id: str
    node_count: int
    edge_count: int
    entry_points: int
    unknown_resolution_count: int


class CodeGraphBuiltEvent(BaseModel):
    data: CodeGraphBuiltData

    @classmethod
    def envelope(cls, data: CodeGraphBuiltData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/code-intelligence",
            type="com.regressionhunter.code.graph.built.v1",
            subject=data.run_id,
            data=data,
        )


class ImpactResolvedData(BaseModel):
    run_id: str
    impact_nodes: int
    impact_edges: int
    max_depth: int
    truncated: bool


class ImpactResolvedEvent(BaseModel):
    data: ImpactResolvedData

    @classmethod
    def envelope(cls, data: ImpactResolvedData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/impact-analyzer",
            type="com.regressionhunter.impact.resolved.v1",
            subject=data.run_id,
            data=data,
        )


class ContextBuiltData(BaseModel):
    run_id: str
    bundle_uri: str
    bundle_version: str = "1.0"
    authoritative_bindings: int
    discovered_bindings: int
    redaction_report: dict = Field(default_factory=dict)


class ContextBuiltEvent(BaseModel):
    data: ContextBuiltData

    @classmethod
    def envelope(cls, data: ContextBuiltData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/context-orchestrator",
            type="com.regressionhunter.context.built.v1",
            subject=data.run_id,
            data=data,
        )


class AssessmentScoredData(BaseModel):
    run_id: str
    risk_score: int
    risk_level: str
    regression_probability: float
    impact_severity: float
    confidence: int
    requires_review: bool


class AssessmentScoredEvent(BaseModel):
    data: AssessmentScoredData

    @classmethod
    def envelope(cls, data: AssessmentScoredData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/risk-engine",
            type="com.regressionhunter.assessment.scored.v1",
            subject=data.run_id,
            data=data,
        )


class RecommendationsReadyData(BaseModel):
    run_id: str
    recommendation_count: int
    generated_artifacts: int


class RecommendationsReadyEvent(BaseModel):
    data: RecommendationsReadyData

    @classmethod
    def envelope(cls, data: RecommendationsReadyData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/test-agent",
            type="com.regressionhunter.recommendations.ready.v1",
            subject=data.run_id,
            data=data,
        )


class PublishRequestedData(BaseModel):
    run_id: str
    targets: list[str]
    idempotency_key: str


class PublishRequestedEvent(BaseModel):
    data: PublishRequestedData

    @classmethod
    def envelope(cls, data: PublishRequestedData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/risk-engine",
            type="com.regressionhunter.publish.requested.v1",
            subject=data.run_id,
            data=data,
        )


class PublishedData(BaseModel):
    run_id: str
    destination: str
    external_id: str | None = None
    status: str


class PublishedEvent(BaseModel):
    data: PublishedData

    @classmethod
    def envelope(cls, data: PublishedData) -> CloudEvent:
        return CloudEvent(
            source="regression-hunter/publisher",
            type="com.regressionhunter.published.v1",
            subject=data.run_id,
            data=data,
        )
