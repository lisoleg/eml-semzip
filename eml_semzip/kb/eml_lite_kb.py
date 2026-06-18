"""EML-Lite Knowledge Base for isomorphic pattern absorption.

Stores reusable hyperedge patterns and provides isomorphic matching,
absorption recording, signature computation, and persistence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..models.hyperedge import HyperEdge
from ..utils.isomorphism import build_index, match

# Canonical key type alias
_CanonicalKey = Tuple[str, int, frozenset]


@dataclass
class AbsorbRecord:
    """Record of an edge absorbed into a KB pattern.

    When an edge matches an isomorphic pattern in the KB, the edge's
    data is recorded so it can be reconstructed during decompression.

    Attributes:
        pattern_id: The edge_id of the matching KB pattern.
        node_mapping: Mapping from pattern node IDs to actual node IDs.
        I_value: Information value of the original edge.
        base_weight: Base weight of the original edge.
        dir_factor: Directional factor of the original edge.
        predicate: Predicate label of the original edge.
    """

    pattern_id: str
    node_mapping: Dict[str, str]
    I_value: float
    base_weight: float
    dir_factor: float
    predicate: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the record to a dictionary."""
        return {
            "pattern_id": self.pattern_id,
            "node_mapping": dict(self.node_mapping),
            "I_value": self.I_value,
            "base_weight": self.base_weight,
            "dir_factor": self.dir_factor,
            "predicate": self.predicate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AbsorbRecord":
        """Deserialize a record from a dictionary."""
        return cls(
            pattern_id=data["pattern_id"],
            node_mapping=dict(data.get("node_mapping", {})),
            I_value=float(data.get("I_value", 0.0)),
            base_weight=float(data.get("base_weight", 1.0)),
            dir_factor=float(data.get("dir_factor", 1.0)),
            predicate=data.get("predicate", ""),
        )


class EMLLiteKB:
    """EML-Lite Knowledge Base for pattern storage and isomorphic matching.

    The KB stores reusable hyperedge patterns and provides:
    - Isomorphic pattern lookup via canonical key indexing.
    - Absorption of edges into patterns (recording metadata for reconstruction).
    - SHA-256 signature computation for integrity verification.
    - JSON persistence.

    Attributes:
        patterns: List of :class:`HyperEdge` patterns stored in the KB.
        index: Dictionary mapping canonical keys to pattern lists.
        sig: SHA-256 signature of the KB contents.
        absorbed_records: List of :class:`AbsorbRecord` entries.
    """

    def __init__(self) -> None:
        """Initialize an empty KB."""
        self.patterns: List[HyperEdge] = []
        self.index: Dict[_CanonicalKey, List[HyperEdge]] = {}
        self.sig: str = ""
        self.absorbed_records: List[AbsorbRecord] = []

    def add_pattern(self, edge: HyperEdge) -> None:
        """Add a pattern to the KB and rebuild the index.

        Args:
            edge: The :class:`HyperEdge` pattern to add.
        """
        self.patterns.append(edge)
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild the isomorphism index from patterns."""
        self.index = build_index(self.patterns)

    def find_isomorphic(self, edge: HyperEdge) -> Optional[HyperEdge]:
        """Find an isomorphic pattern in the KB for the given edge.

        Args:
            edge: The edge to find a match for.

        Returns:
            A matching :class:`HyperEdge` pattern, or ``None`` if no match.
        """
        return match(edge, self.index)

    def absorb(self, edge: HyperEdge) -> AbsorbRecord:
        """Absorb an edge into the KB by finding its isomorphic pattern.

        Creates an :class:`AbsorbRecord` documenting the absorption and
        appends it to ``self.absorbed_records``.

        Args:
            edge: The edge to absorb.

        Returns:
            An :class:`AbsorbRecord` documenting the absorption.

        Raises:
            ValueError: If no isomorphic pattern is found.
        """
        pattern = self.find_isomorphic(edge)
        if pattern is None:
            raise ValueError(
                f"No isomorphic pattern found for edge {edge.edge_id}"
            )

        # Build node mapping: sorted pattern nodes -> sorted actual nodes
        pattern_nodes = sorted(pattern.nodes)
        actual_nodes = sorted(edge.nodes)
        node_mapping = dict(zip(pattern_nodes, actual_nodes))

        record = AbsorbRecord(
            pattern_id=pattern.edge_id,
            node_mapping=node_mapping,
            I_value=edge.I_value,
            base_weight=edge.base_weight,
            dir_factor=edge.dir_factor,
            predicate=edge.predicate,
        )
        self.absorbed_records.append(record)
        return record

    def compute_sig(self) -> str:
        """Compute the SHA-256 signature of the KB.

        The signature is computed over patterns sorted by canonical key,
        then JSON-serialized. This ensures deterministic signatures
        regardless of pattern insertion order.

        Returns:
            The SHA-256 hex digest string.
        """
        sorted_patterns = sorted(
            self.patterns,
            key=lambda e: (e.predicate, len(e.nodes), sorted(e.attr_types)),
        )
        serialized = json.dumps(
            [p.to_dict() for p in sorted_patterns],
            ensure_ascii=False,
            sort_keys=True,
        )
        self.sig = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return self.sig

    def verify_sig(self, expected: str) -> bool:
        """Verify that the KB signature matches the expected value.

        Args:
            expected: The expected SHA-256 hex digest.

        Returns:
            ``True`` if signatures match, ``False`` otherwise.
        """
        actual = self.compute_sig()
        return actual == expected

    def rebuild_edges(self, records: List[AbsorbRecord]) -> List[HyperEdge]:
        """Rebuild edges from absorbed records using KB patterns.

        Each record is matched to a KB pattern by ``pattern_id``, and a new
        :class:`HyperEdge` is constructed using the record's metadata and
        the pattern's attribute types.

        Args:
            records: List of :class:`AbsorbRecord` entries.

        Returns:
            A list of reconstructed :class:`HyperEdge` objects.
        """
        pattern_map: Dict[str, HyperEdge] = {
            p.edge_id: p for p in self.patterns
        }
        edges: List[HyperEdge] = []
        for idx, record in enumerate(records):
            pattern = pattern_map.get(record.pattern_id)
            if pattern is None:
                continue
            actual_nodes = set(record.node_mapping.values())
            edge = HyperEdge(
                edge_id=f"reabsorbed_{record.pattern_id}_{idx}",
                nodes=actual_nodes,
                I_value=record.I_value,
                base_weight=record.base_weight,
                dir_factor=record.dir_factor,
                predicate=record.predicate,
                attr_types=set(pattern.attr_types),
            )
            edge.compute_d_sem()
            edges.append(edge)
        return edges

    def save(self, path: str) -> None:
        """Save the KB to a JSON file.

        Args:
            path: File path for the output JSON.
        """
        data = {
            "patterns": [p.to_dict() for p in self.patterns],
            "sig": self.compute_sig(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str) -> "EMLLiteKB":
        """Load a KB from a JSON file.

        Args:
            path: Path to the JSON file.

        Returns:
            A new :class:`EMLLiteKB` instance.
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        kb = cls()
        for p_data in data.get("patterns", []):
            kb.patterns.append(HyperEdge.from_dict(p_data))
        kb._rebuild_index()
        kb.sig = data.get("sig", "")
        return kb
