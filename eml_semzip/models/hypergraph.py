"""EMLHypergraph: hypergraph container with CRUD and persistence."""

from __future__ import annotations

import json
import pickle
from typing import Any, Dict, List, Optional

from .node import Node
from .hyperedge import HyperEdge


class EMLHypergraph:
    """EML hypergraph containing nodes and hyperedges.

    The hypergraph stores nodes in a dictionary keyed by ``node_id`` and
    edges in a flat list. Provides CRUD operations and JSON/Pickle IO.

    Attributes:
        V: Dictionary mapping node_id to :class:`Node` objects.
        E: List of :class:`HyperEdge` objects.
    """

    def __init__(self) -> None:
        """Initialize an empty hypergraph."""
        self.V: Dict[str, Node] = {}
        self.E: List[HyperEdge] = []

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        """Add or replace a node in the hypergraph.

        If a node with the same ``node_id`` already exists, it is replaced.

        Args:
            node: The :class:`Node` to add.
        """
        self.V[node.node_id] = node

    def add_edge(self, edge: HyperEdge) -> None:
        """Add a hyperedge to the hypergraph.

        Args:
            edge: The :class:`HyperEdge` to add.
        """
        self.E.append(edge)

    def remove_edge(self, edge_id: str) -> Optional[HyperEdge]:
        """Remove and return a hyperedge by ID.

        Args:
            edge_id: The ID of the edge to remove.

        Returns:
            The removed :class:`HyperEdge`, or ``None`` if not found.
        """
        for i, e in enumerate(self.E):
            if e.edge_id == edge_id:
                return self.E.pop(i)
        return None

    def get_edges_by_node(self, node_id: str) -> List[HyperEdge]:
        """Get all edges that contain the given node.

        Args:
            node_id: The node ID to search for.

        Returns:
            A list of edges containing the node.
        """
        return [e for e in self.E if node_id in e.nodes]

    def get_nodes(self) -> List[Node]:
        """Get all nodes as a list.

        Returns:
            A list of all :class:`Node` objects in the hypergraph.
        """
        return list(self.V.values())

    def edge_count(self) -> int:
        """Return the number of edges."""
        return len(self.E)

    def node_count(self) -> int:
        """Return the number of nodes."""
        return len(self.V)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the hypergraph to a dictionary.

        Returns:
            A dictionary with ``nodes`` and ``edges`` keys.
        """
        return {
            "nodes": [n.to_dict() for n in self.V.values()],
            "edges": [e.to_dict() for e in self.E],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EMLHypergraph":
        """Deserialize a hypergraph from a dictionary.

        Args:
            data: Dictionary with ``nodes`` and ``edges`` keys.

        Returns:
            A new :class:`EMLHypergraph` instance.
        """
        g = cls()
        for n_data in data.get("nodes", []):
            g.add_node(Node.from_dict(n_data))
        for e_data in data.get("edges", []):
            g.add_edge(HyperEdge.from_dict(e_data))
        return g

    def to_json(self, path: str) -> None:
        """Save the hypergraph to a JSON file.

        Args:
            path: File path for the output JSON.
        """
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, path: str) -> "EMLHypergraph":
        """Load a hypergraph from a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            A new :class:`EMLHypergraph` instance.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_pickle(self, path: str) -> None:
        """Save the hypergraph to a pickle file.

        Args:
            path: File path for the output pickle.
        """
        with open(path, "wb") as f:
            pickle.dump(self.to_dict(), f)

    @classmethod
    def from_pickle(cls, path: str) -> "EMLHypergraph":
        """Load a hypergraph from a pickle file.

        Args:
            path: Path to the pickle file.

        Returns:
            A new :class:`EMLHypergraph` instance.
        """
        with open(path, "rb") as f:
            data = pickle.load(f)
        return cls.from_dict(data)
