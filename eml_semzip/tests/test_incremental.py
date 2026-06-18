"""Tests for incremental/differential compression (pipeline/incremental.py)."""

import json
import time
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from eml_semzip.models.node import Node
from eml_semzip.models.hyperedge import HyperEdge
from eml_semzip.models.hypergraph import EMLHypergraph
from eml_semzip.pipeline.incremental import (
    HypergraphDelta,
    compute_delta,
    apply_delta,
    compress_incremental,
    decompress_incremental,
    _graph_signature,
)
from eml_semzip.kb.builtin_kb import create_builtin_kb


def make_test_graph():
    """Create a test hypergraph with known structure."""
    g = EMLHypergraph()
    g.add_node(Node("n1", {"type": "person", "name": "Alice"}))
    g.add_node(Node("n2", {"type": "person", "name": "Bob"}))
    g.add_node(Node("n3", {"type": "concept", "name": "friendship"}))
    g.add_edge(HyperEdge("e1", {"n1", "n2"}, I_value=0.9, base_weight=1.0, dir_factor=1.0, predicate="knows"))
    g.add_edge(HyperEdge("e2", {"n1", "n3"}, I_value=0.8, base_weight=1.0, dir_factor=1.0, predicate="likes"))
    return g


def make_modified_graph():
    """Create a modified version of the test graph."""
    g = EMLHypergraph()
    # n1 unchanged
    g.add_node(Node("n1", {"type": "person", "name": "Alice"}))
    # n2 modified (name changed)
    g.add_node(Node("n2", {"type": "person", "name": "Robert"}))
    # n3 removed
    # n4 added
    g.add_node(Node("n4", {"type": "person", "name": "Carol"}))
    # e1 unchanged
    g.add_edge(HyperEdge("e1", {"n1", "n2"}, I_value=0.9, base_weight=1.0, dir_factor=1.0, predicate="knows"))
    # e2 removed
    # e3 added
    g.add_edge(HyperEdge("e3", {"n1", "n4"}, I_value=0.85, base_weight=1.0, dir_factor=1.0, predicate="knows"))
    return g


def test_compute_delta():
    """Test that compute_delta correctly identifies changes."""
    print("  [test] compute_delta...")
    old = make_test_graph()
    new = make_modified_graph()
    delta = compute_delta(old, new)

    # Check added nodes
    assert "n4" in delta.added_nodes, f"Expected n4 in added_nodes, got {delta.added_nodes}"
    # Check removed nodes
    assert "n3" in delta.removed_nodes, f"Expected n3 in removed_nodes"
    # Check modified nodes
    assert "n2" in delta.modified_nodes, f"Expected n2 in modified_nodes"
    # Check added edges
    assert "e3" in delta.added_edges, f"Expected e3 in added_edges"
    # Check removed edges
    assert "e2" in delta.removed_edges, f"Expected e2 in removed_edges"

    print("  [PASS] compute_delta")


def test_apply_delta():
    """Test that apply_delta correctly reconstructs the new graph."""
    print("  [test] apply_delta...")
    old = make_test_graph()
    new = make_modified_graph()
    delta = compute_delta(old, new)
    reconstructed = apply_delta(old, delta)

    # Check nodes
    assert "n1" in reconstructed.V, "n1 should exist"
    assert "n2" in reconstructed.V, "n2 should exist"
    assert "n3" not in reconstructed.V, "n3 should be removed"
    assert "n4" in reconstructed.V, "n4 should be added"
    assert reconstructed.V["n2"].attributes["name"] == "Robert", f"n2 name should be Robert, got {reconstructed.V['n2'].attributes['name']}"

    # Check edges
    edge_ids = {e.edge_id for e in reconstructed.E}
    assert "e1" in edge_ids, "e1 should exist"
    assert "e2" not in edge_ids, "e2 should be removed"
    assert "e3" in edge_ids, "e3 should be added"

    print("  [PASS] apply_delta")


def test_delta_roundtrip():
    """Test full roundtrip: old -> delta -> apply -> new."""
    print("  [test] delta roundtrip...")
    old = make_test_graph()
    new = make_modified_graph()
    delta = compute_delta(old, new)
    reconstructed = apply_delta(old, delta)

    # Compare reconstructed with new
    assert reconstructed.node_count() == new.node_count(), \
        f"Node count mismatch: {reconstructed.node_count()} vs {new.node_count()}"
    assert reconstructed.edge_count() == new.edge_count(), \
        f"Edge count mismatch: {reconstructed.edge_count()} vs {new.edge_count()}"

    # Check node attributes
    for nid, node in new.V.items():
        assert nid in reconstructed.V, f"Node {nid} missing in reconstructed"
        assert reconstructed.V[nid].attributes == node.attributes, \
            f"Node {nid} attrs mismatch: {reconstructed.V[nid].attributes} vs {node.attributes}"

    # Check edges
    new_edges_map = {e.edge_id: e for e in new.E}
    recon_edges_map = {e.edge_id: e for e in reconstructed.E}
    for eid, edge in new_edges_map.items():
        assert eid in recon_edges_map, f"Edge {eid} missing in reconstructed"
        assert recon_edges_map[eid].I_value == edge.I_value
        assert recon_edges_map[eid].nodes == edge.nodes

    print("  [PASS] delta roundtrip")


def test_compress_decompress_incremental():
    """Test incremental compress/decompress cycle."""
    print("  [test] compress_decompress_incremental...")
    old = make_test_graph()
    new = make_modified_graph()
    kb = create_builtin_kb()

    # Compress incrementally
    delta_bytes = compress_incremental(old, new, kb=kb)

    # Decompress incrementally
    reconstructed = decompress_incremental(old, delta_bytes, kb=kb)

    # Verify
    assert reconstructed.node_count() == new.node_count(), \
        f"Node count mismatch: {reconstructed.node_count()} vs {new.node_count()}"
    assert reconstructed.edge_count() == new.edge_count(), \
        f"Edge count mismatch: {reconstructed.edge_count()} vs {new.edge_count()}"

    print(f"    Delta size: {len(delta_bytes)} bytes")
    print("  [PASS] compress_decompress_incremental")


def test_empty_delta():
    """Test that empty delta (no changes) is handled correctly."""
    print("  [test] empty delta...")
    old = make_test_graph()
    # new is identical to old
    new = EMLHypergraph()
    for nid, node in old.V.items():
        new.add_node(Node(nid, dict(node.attributes)))
    for edge in old.E:
        new.add_edge(HyperEdge(edge.edge_id, set(edge.nodes), edge.I_value, edge.base_weight, edge.dir_factor, edge.predicate))

    delta = compute_delta(old, new)
    assert delta.is_empty(), "Delta should be empty for identical graphs"

    print("  [PASS] empty delta")


def test_delta_serialization():
    """Test delta to_dict/from_dict serialization."""
    print("  [test] delta serialization...")
    old = make_test_graph()
    new = make_modified_graph()
    delta = compute_delta(old, new)

    # Serialize and deserialize
    d = delta.to_dict()
    delta2 = HypergraphDelta.from_dict(d)

    assert delta.added_nodes == delta2.added_nodes
    assert delta.removed_nodes == delta2.removed_nodes
    assert delta.added_edges.keys() == delta2.added_edges.keys()

    print("  [PASS] delta serialization")


if __name__ == "__main__":
    print("Running incremental compression tests...")
    start = time.time()
    passed = 0
    failed = 0

    tests = [
        test_compute_delta,
        test_apply_delta,
        test_delta_roundtrip,
        test_compress_decompress_incremental,
        test_empty_delta,
        test_delta_serialization,
    ]

    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    elapsed = time.time() - start
    print(f"\nResults: {passed} passed, {failed} failed ({elapsed:.2f}s)")
    sys.exit(0 if failed == 0 else 1)
