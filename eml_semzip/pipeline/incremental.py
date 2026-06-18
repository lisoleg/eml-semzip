"""Incremental/differential compression for EML hypergraphs.

Supports diff compression after incremental updates:
- compute_delta(old_graph, new_graph) -> Delta object
- apply_delta(old_graph, delta) -> new_graph
- compress_incremental(old_graph, new_graph, kb) -> bytes
- decompress_incremental(old_graph, delta_bytes, kb) -> new_graph

The delta JSON is compressed directly with zlib (lossless, fast).
"""

from __future__ import annotations

import hashlib
import json
import time
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..models.hypergraph import EMLHypergraph
from ..models.hyperedge import HyperEdge
from ..models.node import Node
from ..constants import DEFAULT_THETA_DEAD, DEFAULT_KEEP_RATIO, DELTA_MAGIC, DELTA_VERSION


@dataclass
class HypergraphDelta:
    """Represents the difference between two hypergraphs."""

    added_nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    removed_nodes: Set[str] = field(default_factory=set)
    modified_nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    added_edges: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    removed_edges: Set[str] = field(default_factory=set)
    modified_edges: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    old_graph_sig: str = ""
    new_graph_sig: str = ""
    timestamp: str = ""

    def is_empty(self) -> bool:
        return (
            not self.added_nodes
            and not self.removed_nodes
            and not self.modified_nodes
            and not self.added_edges
            and not self.removed_edges
            and not self.modified_edges
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": "eml-semzip-delta",
            "version": DELTA_VERSION,
            "old_graph_sig": self.old_graph_sig,
            "new_graph_sig": self.new_graph_sig,
            "timestamp": self.timestamp,
            "added_nodes": self.added_nodes,
            "removed_nodes": sorted(self.removed_nodes),
            "modified_nodes": self.modified_nodes,
            "added_edges": self.added_edges,
            "removed_edges": sorted(self.removed_edges),
            "modified_edges": self.modified_edges,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HypergraphDelta":
        delta = cls()
        delta.old_graph_sig = data.get("old_graph_sig", "")
        delta.new_graph_sig = data.get("new_graph_sig", "")
        delta.timestamp = data.get("timestamp", "")
        delta.added_nodes = data.get("added_nodes", {})
        delta.removed_nodes = set(data.get("removed_nodes", []))
        delta.modified_nodes = data.get("modified_nodes", {})
        delta.added_edges = data.get("added_edges", {})
        delta.removed_edges = set(data.get("removed_edges", []))
        delta.modified_edges = data.get("modified_edges", {})
        return delta

    @classmethod
    def from_json(cls, json_str: str) -> "HypergraphDelta":
        return cls.from_dict(json.loads(json_str))


def compute_delta(
    old_graph: EMLHypergraph,
    new_graph: EMLHypergraph,
) -> HypergraphDelta:
    """Compute the delta between two hypergraphs."""
    delta = HypergraphDelta()
    delta.old_graph_sig = _graph_signature(old_graph)
    delta.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    old_node_ids = set(old_graph.V.keys())
    new_node_ids = set(new_graph.V.keys())

    for nid in new_node_ids - old_node_ids:
        delta.added_nodes[nid] = {"node_id": nid, "attributes": dict(new_graph.V[nid].attributes)}

    delta.removed_nodes = old_node_ids - new_node_ids

    for nid in old_node_ids & new_node_ids:
        if old_graph.V[nid].attributes != new_graph.V[nid].attributes:
            delta.modified_nodes[nid] = dict(new_graph.V[nid].attributes)

    old_edge_ids = {e.edge_id for e in old_graph.E}
    new_edge_ids = {e.edge_id for e in new_graph.E}
    new_edges_map = {e.edge_id: e for e in new_graph.E}

    for eid in new_edge_ids - old_edge_ids:
        delta.added_edges[eid] = new_edges_map[eid].to_dict()

    delta.removed_edges = old_edge_ids - new_edge_ids

    old_edges_map = {e.edge_id: e for e in old_graph.E}
    for eid in old_edge_ids & new_edge_ids:
        if _edge_changed(old_edges_map[eid], new_edges_map[eid]):
            delta.modified_edges[eid] = new_edges_map[eid].to_dict()

    delta.new_graph_sig = _graph_signature(new_graph)
    return delta


def apply_delta(
    base_graph: EMLHypergraph,
    delta: HypergraphDelta,
) -> EMLHypergraph:
    """Apply a delta to a base hypergraph."""
    result = EMLHypergraph()

    for nid, node in base_graph.V.items():
        result.add_node(Node(nid, dict(node.attributes)))

    for edge in base_graph.E:
        result.add_edge(
            HyperEdge(
                edge.edge_id,
                set(edge.nodes),
                edge.I_value,
                edge.base_weight,
                edge.dir_factor,
                edge.predicate,
            )
        )

    for nid in delta.removed_nodes:
        result.V.pop(nid, None)

    result.E = [e for e in result.E if e.edge_id not in delta.removed_edges]

    for nid, ndata in delta.added_nodes.items():
        attrs = ndata.get("attributes", {})
        result.add_node(Node(nid, dict(attrs)))

    for nid, attrs in delta.modified_nodes.items():
        if nid in result.V:
            result.V[nid].attributes = dict(attrs)

    for eid, edata in delta.added_edges.items():
        result.add_edge(HyperEdge.from_dict(edata))

    for eid, edata in delta.modified_edges.items():
        result.E = [e for e in result.E if e.edge_id != eid]
        result.add_edge(HyperEdge.from_dict(edata))

    return result


def compress_incremental(
    old_graph: EMLHypergraph,
    new_graph: EMLHypergraph,
    kb=None,
    theta_dead: float = DEFAULT_THETA_DEAD,
    keep_ratio: float = DEFAULT_KEEP_RATIO,
) -> bytes:
    """Compress the delta between two hypergraphs using zlib."""
    delta = compute_delta(old_graph, new_graph)

    if delta.is_empty():
        return _make_empty_delta_pkt(delta.old_graph_sig)

    delta_json = delta.to_json()
    compressed = zlib.compress(delta_json.encode("utf-8"), level=9)
    return _make_delta_pkt(compressed, delta)


def decompress_incremental(
    old_graph: EMLHypergraph,
    delta_bytes: bytes,
    kb=None,
) -> EMLHypergraph:
    """Decompress an incremental delta and apply to base graph."""
    if not _is_delta_pkt(delta_bytes):
        # Legacy full-graph format
        from ..pipeline.decompressor import Decompressor
        decompressor = Decompressor(kb=kb)
        return decompressor.decompress(delta_bytes)

    payload = _extract_delta_payload(delta_bytes)
    delta_json_bytes = zlib.decompress(payload)
    delta = HypergraphDelta.from_json(delta_json_bytes.decode("utf-8"))
    return apply_delta(old_graph, delta)


def _graph_signature(graph: EMLHypergraph) -> str:
    """Compute a short hash signature for a hypergraph."""
    hasher = hashlib.sha256()
    for nid in sorted(graph.V.keys()):
        hasher.update(nid.encode())
        hasher.update(json.dumps(graph.V[nid].attributes, sort_keys=True).encode())
    for edge in sorted(graph.E, key=lambda e: e.edge_id):
        hasher.update(edge.edge_id.encode())
        hasher.update(json.dumps(sorted(edge.nodes)).encode())
        hasher.update(str(edge.I_value).encode())
        hasher.update(edge.predicate.encode())
    return hasher.hexdigest()[:16]


def _edge_changed(e1: HyperEdge, e2: HyperEdge) -> bool:
    return (
        e1.nodes != e2.nodes
        or abs(e1.I_value - e2.I_value) > 1e-9
        or e1.base_weight != e2.base_weight
        or e1.dir_factor != e2.dir_factor
        or e1.predicate != e2.predicate
    )


def _make_delta_pkt(compressed_data: bytes, delta: HypergraphDelta) -> bytes:
    """Prepend delta header to compressed data."""
    import struct
    header = struct.pack(
        "<4sBB16s16s",
        DELTA_MAGIC,
        DELTA_VERSION,
        0x00,
        delta.old_graph_sig.encode()[:16].ljust(16, b'\x00'),
        delta.new_graph_sig.encode()[:16].ljust(16, b'\x00'),
    )
    return header + compressed_data


def _make_empty_delta_pkt(old_sig: str) -> bytes:
    import struct
    return struct.pack(
        "<4sBB16s16s",
        DELTA_MAGIC,
        DELTA_VERSION,
        0x01,
        old_sig.encode()[:16].ljust(16, b'\x00'),
        old_sig.encode()[:16].ljust(16, b'\x00'),
    )


def _is_delta_pkt(data: bytes) -> bool:
    return data[:4] == DELTA_MAGIC


def _extract_delta_payload(data: bytes) -> bytes:
    """Header is 4 + 1 + 1 + 16 + 16 = 38 bytes."""
    return data[38:]
