from __future__ import annotations

from collections import deque
from typing import Any

from code_graph.graph import CodeGraph, GraphNode


class BoundedTraversal:
    """Cycle-safe, budgeted reverse traversal on a CodeGraph."""

    def __init__(
        self,
        graph: CodeGraph,
        max_depth: int = 10,
        max_visited: int = 5000,
    ) -> None:
        self._graph = graph
        self._max_depth = max_depth
        self._max_visited = max_visited

    def reverse_from(self, node_id: str) -> dict[str, Any]:
        """Find all callers (direct + indirect) of node_id, cycle-safe."""
        visited: set[str] = set()
        parents: dict[str, str | None] = {node_id: None}
        depths: dict[str, int] = {node_id: 0}
        queue: deque[str] = deque([node_id])

        unknown_count = 0

        while queue and len(visited) < self._max_visited:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            current_depth = depths.get(current, 0)
            if current_depth >= self._max_depth:
                continue

            callers = self._graph.get_callers(current)
            if not callers:
                continue

            for caller_id in callers:
                if caller_id not in visited:
                    parents[caller_id] = current
                    depths[caller_id] = current_depth + 1
                    queue.append(caller_id)

                node = self._graph.get_node(caller_id)
                if node and node.metadata.get("resolution") == "UNKNOWN":
                    unknown_count += 1

        paths = self._reconstruct_paths(node_id, parents, visited)

        return {
            "root": node_id,
            "visited": list(visited),
            "paths": paths,
            "max_depth_reached": max(depths.values()) if depths else 0,
            "unknown_resolution_count": unknown_count,
            "truncated": len(visited) >= self._max_visited,
        }

    def _reconstruct_paths(
        self,
        root: str,
        parents: dict[str, str | None],
        visited: set[str],
    ) -> list[list[str]]:
        paths: list[list[str]] = []
        for node_id in visited:
            if node_id == root:
                continue
            path: list[str] = []
            current: str | None = node_id
            while current is not None:
                path.append(current)
                current = parents.get(current)
            path.reverse()
            if path and path[-1] == root:
                paths.append(path)
        return paths


def reverse_traversal(
    graph: CodeGraph,
    node_id: str,
    max_depth: int = 10,
) -> dict[str, Any]:
    """Convenience function for one-off reverse traversal."""
    return BoundedTraversal(graph, max_depth=max_depth).reverse_from(node_id)
