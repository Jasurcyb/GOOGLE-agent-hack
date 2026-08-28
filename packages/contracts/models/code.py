from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from contracts.models.enums import (
    ChangeType,
    EdgeType,
    EdgeKind,
    NodeKind,
    Resolution,
)


class Symbol(BaseModel):
    id: str
    fully_qualified_name: str
    signature: str | None = None
    visibility: str = "public"
    file_path: str
    start_line: int
    end_line: int
    decorators: list[str] = Field(default_factory=list)
    is_test: bool = False
    parse_confidence: float = 1.0
    language: str = "python"


class SymbolChange(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol_id: str
    language: str
    change_type: ChangeType
    old_signature: str | None = None
    new_signature: str | None = None
    file_path: str
    start_line: int
    end_line: int
    semantic_delta: dict = Field(default_factory=dict)
    analyzer_confidence: float = 1.0


class CodeEdge(BaseModel):
    run_id: str
    from_symbol_id: str
    to_symbol_id: str
    edge_type: EdgeType
    resolution: Resolution = Resolution.EXACT
    confidence: float = 1.0


class Entrypoint(BaseModel):
    symbol_id: str
    framework: str
    route: str | None = None
    method: str | None = None
    is_public: bool = True


class ImpactNode(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: str
    node_key: str
    node_kind: NodeKind
    datahub_urn: str | None = None
    distance: int = 0
    criticality: float = 0.0
    owners: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


class ImpactEdge(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    run_id: str
    from_node: str
    to_node: str
    edge_kind: EdgeKind
    hop: int
    evidence: dict = Field(default_factory=dict)
