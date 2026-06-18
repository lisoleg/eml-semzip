"""Node data class for EML hypergraph nodes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Node:
    """Represents a node in the EML hypergraph.

    Attributes:
        node_id: Unique identifier for the node.
        attributes: Dictionary of attribute key-value pairs.
    """

    node_id: str
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the node to a dictionary.

        Returns:
            A dictionary representation of the node.
        """
        return {"node_id": self.node_id, "attributes": dict(self.attributes)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        """Deserialize a node from a dictionary.

        Args:
            data: Dictionary containing node data.

        Returns:
            A new Node instance.
        """
        return cls(
            node_id=data["node_id"],
            attributes=dict(data.get("attributes", {})),
        )

    def __eq__(self, other: object) -> bool:
        """Check equality based on node_id."""
        if not isinstance(other, Node):
            return NotImplemented
        return self.node_id == other.node_id

    def __hash__(self) -> int:
        """Hash based on node_id for use in sets and dicts."""
        return hash(self.node_id)
