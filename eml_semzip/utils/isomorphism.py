"""Hyperedge isomorphism matching via canonical signatures.

Provides canonical key computation, index building, and matching functions
for determining structural similarity between hyperedges.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Optional, Tuple

from ..models.hyperedge import HyperEdge
from ..models.hypergraph import EMLHypergraph


def compute_attr_types(edge: HyperEdge, graph: EMLHypergraph) -> FrozenSet[str]:
    """Compute the set of attribute type names across all nodes in the edge.

    Args:
        edge: The hyperedge to examine.
        graph: The hypergraph containing the nodes.

    Returns:
        A frozenset of attribute key names from all nodes in the edge.
    """
    attr_types: Set[str] = set()
    for node_id in edge.nodes:
        node = graph.V.get(node_id)
        if node is not None:
            attr_types.update(node.attributes.keys())
    return frozenset(attr_types)


def canonical_key(
    edge: HyperEdge,
    graph: Optional[EMLHypergraph] = None,
) -> Tuple[str, int, FrozenSet[str]]:
    """Compute the canonical key for an edge.

    If a graph is provided, attribute types are computed from the graph's
    nodes. Otherwise, the edge's stored ``attr_types`` field is used.

    Args:
        edge: The hyperedge to compute the key for.
        graph: Optional hypergraph for attribute type lookup.

    Returns:
        A tuple of (predicate, node_count, frozenset_of_attr_types).
    """
    if graph is not None:
        attr_types = compute_attr_types(edge, graph)
    else:
        attr_types = frozenset(edge.attr_types)
    return (edge.predicate, len(edge.nodes), attr_types)


def build_index(
    edges: List[HyperEdge],
    graph: Optional[EMLHypergraph] = None,
) -> Dict[Tuple[str, int, FrozenSet[str]], List[HyperEdge]]:
    """Build an index dictionary mapping canonical keys to edge lists.

    Args:
        edges: List of hyperedges to index.
        graph: Optional hypergraph for attribute type lookup.

    Returns:
        A dictionary mapping canonical keys to lists of matching edges.
    """
    index: Dict[Tuple[str, int, FrozenSet[str]], List[HyperEdge]] = {}
    for edge in edges:
        key = canonical_key(edge, graph)
        index.setdefault(key, []).append(edge)
    return index


def match(
    edge: HyperEdge,
    index: Dict[Tuple[str, int, FrozenSet[str]], List[HyperEdge]],
    graph: Optional[EMLHypergraph] = None,
) -> Optional[HyperEdge]:
    """Find an isomorphic match for an edge in the index.

    Matching is based on canonical key equality (predicate, node count,
    attribute types). Returns the first matching edge from the index.

    Args:
        edge: The edge to find a match for.
        index: The index dictionary built by :func:`build_index`.
        graph: Optional hypergraph for attribute type lookup.

    Returns:
        A matching :class:`HyperEdge` from the index, or ``None`` if no match.
    """
    key = canonical_key(edge, graph)
    candidates = index.get(key, [])
    if candidates:
        return candidates[0]
    return None
