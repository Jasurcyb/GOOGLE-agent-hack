from __future__ import annotations

from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    COLLECTING = "collecting"
    GROUNDED = "grounded"
    SCORED = "scored"
    RECOMMENDING = "recommending"
    PUBLISHED = "published"
    PARTIAL = "partial"
    FAILED = "failed"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ChangeType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


class EdgeType(StrEnum):
    CALLS = "calls"
    IMPORTS = "imports"
    OVERRIDES = "overrides"
    IMPLEMENTS = "implements"
    READS_DATASET = "reads_dataset"
    WRITES_DATASET = "writes_dataset"
    PUBLISHES_TOPIC = "publishes_topic"
    CONSUMES_TOPIC = "consumes_topic"
    SCHEDULED_BY = "scheduled_by"
    EXPOSED_BY = "exposed_by"


class EdgeKind(StrEnum):
    CODE_TO_CODE = "code_to_code"
    CODE_TO_ASSET = "code_to_asset"
    ASSET_TO_ASSET = "asset_to_asset"


class NodeKind(StrEnum):
    CODE_SYMBOL = "code_symbol"
    DATASET = "dataset"
    DASHBOARD = "dashboard"
    DATA_JOB = "data_job"
    ML_MODEL = "ml_model"
    ML_FEATURE = "ml_feature"
    OWNER = "owner"
    REPORT = "report"


class BindingType(StrEnum):
    AUTHORITATIVE = "authoritative"
    DISCOVERED = "discovered"


class Resolution(StrEnum):
    EXACT = "exact"
    HEURISTIC = "heuristic"
    UNKNOWN = "unknown"
