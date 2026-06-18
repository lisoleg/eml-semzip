"""DFS-based closed cycle detection for hyperedges.

A closed cycle is a sequence of hyperedges where each consecutive pair
shares at least one node, and the last edge connects back to the first.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Set

from ..constants import MAX_CYCLE_DEPTH
from ..models.hyperedge import HyperEdge


def build_line_graph(edges: List[HyperEdge]) -> Dict[str, Set[str]]:
    """Build a line graph from hyperedges.

    In the line graph, each node represents a hyperedge, and an edge connects
    two nodes if the corresponding hyperedges share at least one node.

    Args:
        edges: List of hyperedges.

    Returns:
        A dictionary mapping edge_id to a set of adjacent edge_ids.
    """
    graph: Dict[str, Set[str]] = {}
    for e in edges:
        graph.setdefault(e.edge_id, set())

    n = len(edges)
    for i in range(n):
        e1 = edges[i]
        for j in range(i + 1, n):
            e2 = edges[j]
            if e1.nodes & e2.nodes:
                graph[e1.edge_id].add(e2.edge_id)
                graph[e2.edge_id].add(e1.edge_id)
    return graph


def find_closed_cycles(
    edges: List[HyperEdge],
    min_length: int = 3,
    max_depth: int = MAX_CYCLE_DEPTH,
) -> List[List[str]]:
    """Find closed cycles in the hyperedge set.

    A closed cycle is a sequence of edges (represented by edge_ids) where each
    consecutive pair shares at least one node, the sequence has length >=
    ``min_length``, and the last edge connects back to the first.

    Uses DFS backtracking search on the line graph. Cycles are deduplicated
    by their frozenset of edge IDs.

    Args:
        edges: List of hyperedges to search.
        min_length: Minimum number of edges in a cycle.
        max_depth: Maximum search depth to prevent runaway computation.

    Returns:
        A list of cycles, each represented as a list of edge_ids.
    """
    if len(edges) < min_length:
        return []

    line_graph = build_line_graph(edges)

    found_cycles: Set[FrozenSet[str]] = set()
    result: List[List[str]] = []

    def _dfs(start: str, current: str, path: List[str]) -> None:
        """Depth-first search for cycles starting at ``start``."""
        if len(path) > max_depth:
            return
        for neighbor in line_graph.get(current, set()):
            if neighbor == start and len(path) >= min_length:
                cycle_key = frozenset(path)
                if cycle_key not in found_cycles:
                    found_cycles.add(cycle_key)
                    result.append(list(path))
            elif neighbor not in path:
                _dfs(start, neighbor, path + [neighbor])

    for edge in edges:
        _dfs(edge.edge_id, edge.edge_id, [edge.edge_id])

    return result
