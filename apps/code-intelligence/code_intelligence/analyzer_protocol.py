from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from contracts.models.enums import ChangeType, EdgeType, Resolution


@dataclass
class SourceFile:
    path: str
    language: str
    content: str
    encoding: str = "utf-8"


@dataclass
class Symbol:
    id: str
    fully_qualified_name: str
    signature: str | None = None
    visibility: str = "public"
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    decorators: list[str] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)
    is_test: bool = False
    parse_confidence: float = 1.0
    language: str = "python"
    symbol_kind: str = "function"


@dataclass
class CodeEdge:
    run_id: str
    from_symbol_id: str
    to_symbol_id: str
    edge_type: EdgeType
    resolution: Resolution = Resolution.EXACT
    confidence: float = 1.0


@dataclass
class Entrypoint:
    symbol_id: str
    framework: str
    route: str | None = None
    method: str | None = None
    is_public: bool = True


@dataclass
class SymbolChange:
    symbol_id: str
    language: str
    change_type: ChangeType
    old_signature: str | None = None
    new_signature: str | None = None
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    semantic_delta: dict = field(default_factory=dict)
    analyzer_confidence: float = 1.0


@dataclass
class ParseResult:
    file_path: str
    language: str
    symbols: list[Symbol] = field(default_factory=list)
    edges: list[CodeEdge] = field(default_factory=list)
    entrypoints: list[Entrypoint] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    parse_confidence: float = 1.0
    errors: list[str] = field(default_factory=list)
    source_content: str = ""


class LanguageAnalyzer(Protocol):
    """Language-neutral analyzer contract."""

    language: str

    def parse(self, files: list[SourceFile]) -> list[ParseResult]: ...

    def symbols(self, parse: ParseResult) -> list[Symbol]: ...

    def edges(self, parse: ParseResult, symbols: list[Symbol]) -> list[CodeEdge]: ...

    def entrypoints(self, parse: ParseResult) -> list[Entrypoint]: ...

    def classify_change(self, base: ParseResult, head: ParseResult) -> list[SymbolChange]: ...
