from __future__ import annotations

import pytest

from code_graph.graph import CodeGraph, GraphNode
from code_graph.traversal import BoundedTraversal, reverse_traversal


class TestCodeGraph:
    def test_add_nodes_and_edges(self):
        g = CodeGraph("run-1")
        g.add_node(GraphNode(id="a", fqn="mod.a"))
        g.add_node(GraphNode(id="b", fqn="mod.b"))
        g.add_node(GraphNode(id="c", fqn="mod.c"))

        from code_graph.graph import GraphEdge
        from contracts.models.enums import EdgeType
        g.add_edge(GraphEdge(source="a", target="b", edge_type=EdgeType.CALLS))
        g.add_edge(GraphEdge(source="b", target="c", edge_type=EdgeType.CALLS))

        assert g.node_count == 3
        assert g.edge_count == 2
        assert g.get_callers("b") == ["a"]
        assert g.get_callees("a") == ["b"]

    def test_truncation(self):
        g = CodeGraph("run-1", max_nodes=2)
        g.add_node(GraphNode(id="a", fqn="mod.a"))
        g.add_node(GraphNode(id="b", fqn="mod.b"))
        assert g.add_node(GraphNode(id="c", fqn="mod.c")) is False
        assert g.truncated is True

    def test_reverse_traversal(self):
        g = CodeGraph("run-1")
        g.add_node(GraphNode(id="a", fqn="mod.a", is_entrypoint=True))
        g.add_node(GraphNode(id="b", fqn="mod.b"))
        g.add_node(GraphNode(id="c", fqn="mod.c"))

        from code_graph.graph import GraphEdge
        from contracts.models.enums import EdgeType
        g.add_edge(GraphEdge(source="a", target="b", edge_type=EdgeType.CALLS))
        g.add_edge(GraphEdge(source="b", target="c", edge_type=EdgeType.CALLS))

        result = reverse_traversal(g, "c", max_depth=5)
        assert "a" in result["visited"]
        assert "b" in result["visited"]
        assert result["max_depth_reached"] == 2

    def test_cycle_safe(self):
        g = CodeGraph("run-1")
        g.add_node(GraphNode(id="a", fqn="mod.a"))
        g.add_node(GraphNode(id="b", fqn="mod.b"))

        from code_graph.graph import GraphEdge
        from contracts.models.enums import EdgeType
        g.add_edge(GraphEdge(source="a", target="b", edge_type=EdgeType.CALLS))
        g.add_edge(GraphEdge(source="b", target="a", edge_type=EdgeType.CALLS))

        result = reverse_traversal(g, "a", max_depth=10)
        assert "a" in result["visited"]
        assert "b" in result["visited"]

    def test_source_ranges(self):
        g = CodeGraph("run-1")
        g.add_node(GraphNode(id="a", fqn="mod.a", file_path="src/a.py", start_line=10, end_line=20))
        ranges = g.get_source_ranges(["a"])
        assert ranges[0]["file_path"] == "src/a.py"
        assert ranges[0]["start_line"] == 10
