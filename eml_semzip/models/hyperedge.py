"""HyperEdge data class for EML hypergraph edges."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, Set, Tuple

from ..constants import I_VALUE_EPSILON


@dataclass
class HyperEdge:
    """Represents a hyperedge in the EML hypergraph.

    A hyperedge connects multiple nodes and carries semantic metadata
    including information value, weights, and a predicate label.

    Attributes:
        edge_id: Unique identifier for the edge.
        nodes: Set of node IDs connected by this edge.
        I_value: Information value of the edge (higher = more important).
        base_weight: Base weight for d_sem computation (default 1.0).
        dir_factor: Directional factor for d_sem computation (default 1.0).
        predicate: Semantic predicate label (e.g. "causes", "part_of").
        d_sem: Semantic distance metric, computed via :meth:`compute_d_sem`.
        attr_types: Set of attribute type names across nodes (for canonical key).
    """

    edge_id: str
    nodes: Set[str] = field(default_factory=set)
    I_value: float = 0.0
    base_weight: float = 1.0
    dir_factor: float = 1.0
    predicate: str = ""
    d_sem: float = 0.0
    attr_types: Set[str] = field(default_factory=set)

    def compute_d_sem(self) -> float:
        """Compute the semantic distance metric d_sem.

        Formula: d_sem = (1.0 / (I_value + epsilon)) * base_weight * dir_factor

        The result is stored in ``self.d_sem`` and also returned.

        Returns:
            The computed d_sem value.
        """
        self.d_sem = (
            (1.0 / (self.I_value + I_VALUE_EPSILON))
            * self.base_weight
            * self.dir_factor
        )
        return self.d_sem

    def canonical_key(self) -> Tuple[str, int, FrozenSet[str]]:
        """Compute the canonical key for isomorphism matching.

        The key is a tuple of (predicate, node_count, frozenset_of_attr_types).
        Edges with the same canonical key are candidates for isomorphism.

        Returns:
            A tuple representing the canonical key.
        """
        return (self.predicate, len(self.nodes), frozenset(self.attr_types))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the edge to a dictionary.

        Returns:
            A dictionary representation of the edge.
        """
        return {
            "edge_id": self.edge_id,
            "nodes": sorted(self.nodes),
            "I_value": self.I_value,
            "base_weight": self.base_weight,
            "dir_factor": self.dir_factor,
            "predicate": self.predicate,
            "d_sem": self.d_sem,
            "attr_types": sorted(self.attr_types),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HyperEdge":
        """Deserialize an edge from a dictionary.

        Args:
            data: Dictionary containing edge data.

        Returns:
            A new HyperEdge instance.
        """
        return cls(
            edge_id=data["edge_id"],
            nodes=set(data.get("nodes", [])),
            I_value=float(data.get("I_value", 0.0)),
            base_weight=float(data.get("base_weight", 1.0)),
            dir_factor=float(data.get("dir_factor", 1.0)),
            predicate=data.get("predicate", ""),
            d_sem=float(data.get("d_sem", 0.0)),
            attr_types=set(data.get("attr_types", [])),
        )
