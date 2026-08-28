from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from contracts.models.enums import EdgeType, Resolution


@dataclass
class GraphNode:
    id: str
    fqn: str
    kind: str = "function"
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    language: str = ""
    is_test: bool = False
    is_entrypoint: bool = False
    entrypoint_framework: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    edge_type: EdgeType
    resolution: Resolution = Resolution.EXACT
    confidence: float = 1.0


class CodeGraph:
    """Language-neutral in-memory code graph with bounded traversal."""

    def __init__(self, run_id: str, max_nodes: int = 10000, max_edges: int = 50000) -> None:
        self.run_id = run_id
        self._max_nodes = max_nodes
        self._max_edges = max_edges
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adjacency: dict[str, list[str]] = {}
        self._reverse_adjacency: dict[str, list[str]] = {}
        self._truncated = False

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)

    @property
    def truncated(self) -> bool:
        return self._truncated

    def add_node(self, node: GraphNode) -> bool:
        if len(self._nodes) >= self._max_nodes:
            self._truncated = True
            return False
        self._nodes[node.id] = node
        return True

    def add_edge(self, edge: GraphEdge) -> bool:
        if len(self._edges) >= self._max_edges:
            self._truncated = True
            return False
        self._edges.append(edge)
        self._adjacency.setdefault(edge.source, []).append(edge.target)
        self._reverse_adjacency.setdefault(edge.target, []).append(edge.source)
        return True

    def get_node(self, node_id: str) -> GraphNode | None:
        return self._nodes.get(node_id)

    def get_callers(self, node_id: str) -> list[str]:
        return self._reverse_adjacency.get(node_id, [])

    def get_callees(self, node_id: str) -> list[str]:
        return self._adjacency.get(node_id, [])

    def get_entrypoints(self) -> list[GraphNode]:
        return [n for n in self._nodes.values() if n.is_entrypoint]

    def get_all_nodes(self) -> list[GraphNode]:
        return list(self._nodes.values())

    def get_all_edges(self) -> list[GraphEdge]:
        return list(self._edges)

    def get_source_ranges(self, node_ids: list[str]) -> list[dict]:
        """Return source ranges (not whole files) for LLM context."""
        ranges: list[dict] = []
        for nid in node_ids:
            node = self._nodes.get(nid)
            if node:
                ranges.append({
                    "symbol_id": node.id,
                    "fqn": node.fqn,
                    "file_path": node.file_path,
                    "start_line": node.start_line,
                    "end_line": node.end_line,
                    "language": node.language,
                })
        return ranges
