from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
from contracts.models.enums import EdgeKind, NodeKind


@dataclass
class ImpactResult:
    run_id: str
    nodes: list[dict]
    edges: list[dict]
    blast_radius_score: float
    max_depth: int
    truncated: bool
    weighted_downstream_assets: float
    node_count: int
    edge_count: int


WEIGHTS: dict[str, int] = {
    "DASHBOARD": 1,
    "DATA_JOB": 2,
    "DATASET": 2,
    "CODE_SYMBOL": 0,
    "ML_MODEL": 4,
    "ML_FEATURE": 3,
    "OWNER": 0,
    "REPORT": 1,
}


class ImpactAnalyzer:
    """Builds a bounded blast-radius subgraph using NetworkX."""

    def __init__(
        self,
        max_nodes: int = 10000,
        max_edges: int = 50000,
        max_depth: int = 5,
    ) -> None:
        self._max_nodes = max_nodes
        self._max_edges = max_edges
        self._max_depth = max_depth

    def analyze(
        self,
        run_id: str,
        changed_symbols: list[str],
        code_graph_edges: list[dict] | None = None,
        datahub_bindings: list[dict] | None = None,
        datahub_lineage: list[dict] | None = None,
        datahub_assets: list[dict] | None = None,
    ) -> ImpactResult:
        G = nx.DiGraph()
        truncated = False

        for sym_id in changed_symbols:
            G.add_node(sym_id, kind=NodeKind.CODE_SYMBOL.value, distance=0)

        for edge in code_graph_edges or []:
            src = edge.get("from", "")
            tgt = edge.get("to", "")
            if src and tgt:
                G.add_edge(src, tgt, kind=EdgeKind.CODE_TO_CODE.value, hop=1)
            if G.number_of_nodes() > self._max_nodes:
                truncated = True
                break

        for binding in datahub_bindings or []:
            sym_id = binding.get("symbol_id", "")
            urn = binding.get("datahub_urn", "")
            if sym_id and urn:
                G.add_node(urn, kind=binding.get("entity_type", "DATASET"), distance=1, criticality=binding.get("criticality", 0))
                G.add_edge(sym_id, urn, kind=EdgeKind.CODE_TO_ASSET.value, hop=1, evidence=binding.get("evidence", ""))

        for link in datahub_lineage or []:
            upstream = link.get("from", link.get("upstream", ""))
            downstream = link.get("to", link.get("downstream", ""))
            if upstream and downstream:
                if downstream not in G:
                    G.add_node(downstream, kind="DATASET", distance=2)
                if upstream not in G:
                    G.add_node(upstream, kind="DATASET", distance=2)
                G.add_edge(upstream, downstream, kind=EdgeKind.ASSET_TO_ASSET.value, hop=link.get("hop", 1))
            if G.number_of_edges() > self._max_edges:
                truncated = True
                break

        for asset in datahub_assets or []:
            urn = asset.get("urn", "")
            if urn and urn not in G:
                G.add_node(urn, kind=asset.get("type", "DATASET"), distance=asset.get("distance", 2), criticality=asset.get("criticality", 0))

        max_depth = 0
        for sym_id in changed_symbols:
            if sym_id in G:
                lengths = nx.single_source_shortest_path_length(G, sym_id, cutoff=self._max_depth)
                if lengths:
                    max_depth = max(max_depth, max(lengths.values()))

        weighted = self._compute_weighted_downstream(G, changed_symbols)
        blast_radius = min(20.0, 4.0 * math.log(1 + weighted))

        nodes_out: list[dict] = []
        for node_id, data in G.nodes(data=True):
            nodes_out.append({
                "node_key": node_id,
                "node_kind": data.get("kind", "UNKNOWN"),
                "datahub_urn": node_id if data.get("kind") != NodeKind.CODE_SYMBOL.value else None,
                "distance": data.get("distance", 0),
                "criticality": data.get("criticality", 0.0),
                "owners": data.get("owners", []),
                "evidence": data.get("evidence", {}),
            })

        edges_out: list[dict] = []
        for u, v, data in G.edges(data=True):
            edges_out.append({
                "from_node": u,
                "to_node": v,
                "edge_kind": data.get("kind", EdgeKind.CODE_TO_CODE.value),
                "hop": data.get("hop", 1),
                "evidence": data.get("evidence", {}),
            })

        return ImpactResult(
            run_id=run_id,
            nodes=nodes_out,
            edges=edges_out,
            blast_radius_score=blast_radius,
            max_depth=max_depth,
            truncated=truncated,
            weighted_downstream_assets=weighted,
            node_count=G.number_of_nodes(),
            edge_count=G.number_of_edges(),
        )

    def _compute_weighted_downstream(self, G: nx.DiGraph, roots: list[str]) -> float:
        total_weight = 0.0
        visited: set[str] = set()

        for root in roots:
            if root not in G:
                continue
            for node in nx.descendants(G, root):
                if node in visited:
                    continue
                visited.add(node)
                kind = G.nodes[node].get("kind", "DATASET")
                total_weight += WEIGHTS.get(kind, 1)

        return total_weight
