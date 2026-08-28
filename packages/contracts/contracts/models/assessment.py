from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from contracts.models.enums import RiskLevel


class AffectedAsset(BaseModel):
    urn: str
    type: str
    impact: str
    distance: int
    evidence_refs: list[str] = Field(default_factory=list)


class EvidenceCoverage(BaseModel):
    authoritative_bindings: int = 0
    lineage_freshness_hours: float | None = None


class RiskFactor(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    factor_code: str
    feature_value: float
    points: float
    evidence_refs: list[str] = Field(default_factory=list)


class GeneratedArtifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    recommendation_id: UUID
    artifact_type: str
    sha256: str | None = None
    object_uri: str | None = None
    validation: dict = Field(default_factory=dict)
    status: str = "pending"


class Recommendation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    assessment_id: UUID
    kind: str
    priority: int = 0
    title: str
    body: str
    target_path: str | None = None
    target_urn: str | None = None
    status: str = "proposed"
    evidence_refs: list[str] = Field(default_factory=list)
    approval_required: bool = True


class RiskAssessment(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: str
    risk_score: int
    risk_level: RiskLevel
    regression_probability: float
    impact_severity: float
    confidence: int
    model_version: str = "v1"
    decision: dict = Field(default_factory=dict)
    requires_review: bool = False
    factors: list[RiskFactor] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)


class RegressionAssessment(BaseModel):
    run_id: str
    risk_score: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    regression_probability: float = 0.0
    impact_severity: float = 0.0
    confidence: int = 0
    affected_assets: list[AffectedAsset] = Field(default_factory=list)
    affected_dashboards: list[AffectedAsset] = Field(default_factory=list)
    affected_datasets: list[AffectedAsset] = Field(default_factory=list)
    affected_ml_models: list[AffectedAsset] = Field(default_factory=list)
    affected_jobs: list[AffectedAsset] = Field(default_factory=list)
    recommended_tests: list[Recommendation] = Field(default_factory=list)
    review_summary: str = ""
    business_impact: str = ""
    root_cause: str = ""
    requires_human_review: bool = False
    evidence_coverage: EvidenceCoverage = Field(default_factory=EvidenceCoverage)

