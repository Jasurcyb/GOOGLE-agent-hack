from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceIndexEntry(BaseModel):
    source: str
    uri: str
    trust: str = "AUTHORITATIVE"


class DataHubImpact(BaseModel):
    assets: list[dict] = Field(default_factory=list)
    lineage_paths: list[dict] = Field(default_factory=list)
    owners: list[dict] = Field(default_factory=list)
    quality: list[dict] = Field(default_factory=list)


class RedactionManifest(BaseModel):
    secret_count: int = 0
    restricted_assets_removed: int = 0
    pii_fields_redacted: int = 0


class EvidenceBundle(BaseModel):
    bundle_version: str = "1.0"
    run: dict
    change_summary: dict = Field(default_factory=dict)
    code_impact: dict = Field(default_factory=dict)
    datahub_impact: DataHubImpact = Field(default_factory=DataHubImpact)
    historical_signals: dict = Field(default_factory=dict)
    risk_features: dict = Field(default_factory=dict)
    policy: dict = Field(default_factory=dict)
    evidence_index: dict[str, EvidenceIndexEntry] = Field(default_factory=dict)
    redaction_manifest: RedactionManifest = Field(default_factory=RedactionManifest)
