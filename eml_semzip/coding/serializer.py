"""Serializer for SemPkt payload.

Provides SemPktPayload dataclass and JSON-based serialization/deserialization.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from ..kb.eml_lite_kb import AbsorbRecord
from ..models.hyperedge import HyperEdge


@dataclass
class SemPktPayload:
    """Payload carried inside a SemPkt.

    Attributes:
        V_star: Set of selected node IDs.
        E_star: List of selected hyperedges.
        theta_dead: Dead-zero threshold used in compression.
        kb_sig: Knowledge base signature.
        pruned_summary: List of pruned edge summaries.
        absorb_records: List of absorption records.
    """

    V_star: Set[str] = field(default_factory=set)
    E_star: List[HyperEdge] = field(default_factory=list)
    theta_dead: float = 0.0
    kb_sig: str = ""
    pruned_summary: List[Dict[str, Any]] = field(default_factory=list)
    absorb_records: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the payload to a dictionary.

        Returns:
            Dictionary representation of the payload.
        """
        return {
            "V_star": sorted(self.V_star),
            "E_star": [e.to_dict() for e in self.E_star],
            "theta_dead": self.theta_dead,
            "kb_sig": self.kb_sig,
            "pruned_summary": list(self.pruned_summary),
            "absorb_records": [
                r.to_dict() if hasattr(r, "to_dict") else r
                for r in self.absorb_records
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemPktPayload":
        """Deserialize a payload from a dictionary.

        Args:
            data: Dictionary containing payload data.

        Returns:
            A new SemPktPayload instance.
        """
        return cls(
            V_star=set(data.get("V_star", [])),
            E_star=[
                HyperEdge.from_dict(e) for e in data.get("E_star", [])
            ],
            theta_dead=float(data.get("theta_dead", 0.0)),
            kb_sig=data.get("kb_sig", ""),
            pruned_summary=list(data.get("pruned_summary", [])),
            absorb_records=[
                AbsorbRecord.from_dict(r) if isinstance(r, dict) else r
                for r in data.get("absorb_records", [])
            ],
        )


def serialize(payload: SemPktPayload) -> bytes:
    """Serialize a SemPktPayload to JSON bytes.

    Args:
        payload: The SemPktPayload to serialize.

    Returns:
        UTF-8 encoded JSON bytes.
    """
    return json.dumps(
        payload.to_dict(), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")


def deserialize(data: bytes) -> SemPktPayload:
    """Deserialize JSON bytes to a SemPktPayload.

    Args:
        data: UTF-8 encoded JSON bytes.

    Returns:
        A new SemPktPayload instance.
    """
    obj = json.loads(data.decode("utf-8"))
    return SemPktPayload.from_dict(obj)
