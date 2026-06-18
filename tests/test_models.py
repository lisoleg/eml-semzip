"""Tests for eml_semzip.models: Node, HyperEdge, EMLHypergraph."""

import json
import os
import sys
import tempfile
import unittest

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eml_semzip.models.node import Node
from eml_semzip.models.hyperedge import HyperEdge
from eml_semzip.models.hypergraph import EMLHypergraph
from eml_semzip.constants import I_VALUE_EPSILON


class TestNode(unittest.TestCase):
    """Tests for Node data class."""

    def test_create_node(self):
        node = Node(node_id="n1", attributes={"name": "Alice"})
        self.assertEqual(node.node_id, "n1")
        self.assertEqual(node.attributes, {"name": "Alice"})

    def test_create_node_default_attrs(self):
        node = Node(node_id="n1")
        self.assertEqual(node.attributes, {})

    def test_to_dict(self):
        node = Node(node_id="n1", attributes={"type": "person"})
        d = node.to_dict()
        self.assertEqual(d["node_id"], "n1")
        self.assertEqual(d["attributes"], {"type": "person"})

    def test_from_dict(self):
        node = Node.from_dict({"node_id": "nx", "attributes": {"key": "val"}})
        self.assertEqual(node.node_id, "nx")
        self.assertEqual(node.attributes, {"key": "val"})

    def test_from_dict_no_attributes(self):
        node = Node.from_dict({"node_id": "nx"})
        self.assertEqual(node.attributes, {})

    def test_equality(self):
        n1 = Node(node_id="same")
        n2 = Node(node_id="same")
        n3 = Node(node_id="different")
        self.assertEqual(n1, n2)
        self.assertNotEqual(n1, n3)

    def test_hash(self):
        nodes = {Node("a"), Node("b"), Node("a")}
        self.assertEqual(len(nodes), 2)


class TestHyperEdge(unittest.TestCase):
    """Tests for HyperEdge data class."""

    def test_create_hyperedge(self):
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            I_value=0.9,
            predicate="knows",
        )
        self.assertEqual(edge.edge_id, "e1")
        self.assertEqual(edge.nodes, {"n1", "n2"})
        self.assertEqual(edge.I_value, 0.9)
        self.assertEqual(edge.predicate, "knows")

    def test_default_values(self):
        edge = HyperEdge(edge_id="e1")
        self.assertEqual(edge.nodes, set())
        self.assertEqual(edge.I_value, 0.0)
        self.assertEqual(edge.base_weight, 1.0)
        self.assertEqual(edge.dir_factor, 1.0)
        self.assertEqual(edge.predicate, "")
        self.assertEqual(edge.d_sem, 0.0)

    def test_compute_d_sem(self):
        edge = HyperEdge(
            edge_id="e1",
            I_value=0.5,
            base_weight=2.0,
            dir_factor=1.5,
        )
        d = edge.compute_d_sem()
        expected = (1.0 / (0.5 + I_VALUE_EPSILON)) * 2.0 * 1.5
        self.assertAlmostEqual(d, expected)
        self.assertAlmostEqual(edge.d_sem, expected)

    def test_compute_d_sem_zero_I_value(self):
        edge = HyperEdge(
            edge_id="e1",
            I_value=0.0,
            base_weight=1.0,
            dir_factor=1.0,
        )
        d = edge.compute_d_sem()
        self.assertAlmostEqual(d, 1.0 / I_VALUE_EPSILON)

    def test_canonical_key(self):
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            predicate="knows",
            attr_types={"name", "type"},
        )
        key = edge.canonical_key()
        self.assertEqual(key, ("knows", 2, frozenset({"name", "type"})))

    def test_canonical_key_empty(self):
        edge = HyperEdge(edge_id="e1")
        key = edge.canonical_key()
        self.assertEqual(key, ("", 0, frozenset()))

    def test_to_dict(self):
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            I_value=0.9,
            predicate="knows",
        )
        d = edge.to_dict()
        self.assertEqual(d["edge_id"], "e1")
        self.assertIn("n1", d["nodes"])
        self.assertIn("n2", d["nodes"])
        self.assertEqual(d["I_value"], 0.9)
        self.assertEqual(d["predicate"], "knows")

    def test_from_dict(self):
        data = {
            "edge_id": "e1",
            "nodes": ["n1", "n2"],
            "I_value": 0.9,
            "predicate": "knows",
        }
        edge = HyperEdge.from_dict(data)
        self.assertEqual(edge.edge_id, "e1")
        self.assertEqual(edge.nodes, {"n1", "n2"})
        self.assertEqual(edge.I_value, 0.9)
        self.assertEqual(edge.predicate, "knows")

    def test_from_dict_defaults(self):
        edge = HyperEdge.from_dict({"edge_id": "e1"})
        self.assertEqual(edge.nodes, set())
        self.assertEqual(edge.I_value, 0.0)
        self.assertEqual(edge.base_weight, 1.0)

    def test_roundtrip(self):
        edge = HyperEdge(
            edge_id="e_r",
            nodes={"a", "b", "c"},
            I_value=0.75,
            base_weight=1.5,
            dir_factor=0.8,
            predicate="collaborates",
            attr_types={"name", "type"},
        )
        edge.compute_d_sem()
        restored = HyperEdge.from_dict(edge.to_dict())
        self.assertEqual(restored.edge_id, edge.edge_id)
        self.assertEqual(restored.nodes, edge.nodes)
        self.assertAlmostEqual(restored.I_value, edge.I_value)
        self.assertAlmostEqual(restored.d_sem, edge.d_sem)
        self.assertEqual(restored.predicate, edge.predicate)
        self.assertEqual(restored.attr_types, edge.attr_types)


class TestEMLHypergraph(unittest.TestCase):
    """Tests for EMLHypergraph."""

    def setUp(self):
        self.graph = EMLHypergraph()

    def _build_sample(self):
        """Build the sample graph from fixtures."""
        self.graph.add_node(Node("n1", {"name": "Alice", "type": "person"}))
        self.graph.add_node(Node("n2", {"name": "Bob", "type": "person"}))
        self.graph.add_node(Node("n3", {"name": "ProjectX", "type": "project"}))
        self.graph.add_edge(HyperEdge(
            edge_id="e1", nodes={"n1", "n2"},
            I_value=0.9, base_weight=1.0, dir_factor=1.0, predicate="knows",
        ))
        self.graph.add_edge(HyperEdge(
            edge_id="e2", nodes={"n1", "n3"},
            I_value=0.8, predicate="works_on",
        ))
        self.graph.add_edge(HyperEdge(
            edge_id="e3", nodes={"n2", "n3"},
            I_value=0.3, predicate="works_on",
        ))
        self.graph.add_edge(HyperEdge(
            edge_id="e4", nodes={"n1", "n2", "n3"},
            I_value=0.95, base_weight=1.2, predicate="collaborates",
        ))

    # -- CRUD --

    def test_empty_graph(self):
        self.assertEqual(self.graph.node_count(), 0)
        self.assertEqual(self.graph.edge_count(), 0)
        self.assertEqual(self.graph.get_nodes(), [])

    def test_add_node(self):
        node = Node("n1", {"name": "Alice"})
        self.graph.add_node(node)
        self.assertEqual(self.graph.node_count(), 1)
        self.assertIn("n1", self.graph.V)

    def test_add_node_replace(self):
        self.graph.add_node(Node("n1", {"name": "Alice"}))
        self.graph.add_node(Node("n1", {"name": "Alice2"}))
        self.assertEqual(self.graph.node_count(), 1)
        self.assertEqual(self.graph.V["n1"].attributes["name"], "Alice2")

    def test_add_edge(self):
        edge = HyperEdge(edge_id="e1", nodes={"n1", "n2"})
        self.graph.add_edge(edge)
        self.assertEqual(self.graph.edge_count(), 1)
        self.assertIn(edge, self.graph.E)

    def test_remove_edge_existing(self):
        edge = HyperEdge(edge_id="e1", nodes={"n1"})
        self.graph.add_edge(edge)
        removed = self.graph.remove_edge("e1")
        self.assertIs(removed, edge)
        self.assertEqual(self.graph.edge_count(), 0)

    def test_remove_edge_not_found(self):
        removed = self.graph.remove_edge("nonexistent")
        self.assertIsNone(removed)

    def test_get_edges_by_node(self):
        self._build_sample()
        edges_n1 = self.graph.get_edges_by_node("n1")
        self.assertEqual(len(edges_n1), 3)  # e1, e2, e4
        edge_ids = {e.edge_id for e in edges_n1}
        self.assertEqual(edge_ids, {"e1", "e2", "e4"})

    def test_get_edges_by_node_none(self):
        edges = self.graph.get_edges_by_node("nonexistent")
        self.assertEqual(edges, [])

    def test_get_nodes(self):
        self._build_sample()
        nodes = self.graph.get_nodes()
        self.assertEqual(len(nodes), 3)
        node_ids = {n.node_id for n in nodes}
        self.assertEqual(node_ids, {"n1", "n2", "n3"})

    def test_node_count_edge_count(self):
        self._build_sample()
        self.assertEqual(self.graph.node_count(), 3)
        self.assertEqual(self.graph.edge_count(), 4)

    # -- Serialization --

    def test_to_dict(self):
        self._build_sample()
        d = self.graph.to_dict()
        self.assertIn("nodes", d)
        self.assertIn("edges", d)
        self.assertEqual(len(d["nodes"]), 3)
        self.assertEqual(len(d["edges"]), 4)

    def test_from_dict(self):
        self._build_sample()
        d = self.graph.to_dict()
        g2 = EMLHypergraph.from_dict(d)
        self.assertEqual(g2.node_count(), 3)
        self.assertEqual(g2.edge_count(), 4)

    def test_from_dict_empty(self):
        g = EMLHypergraph.from_dict({})
        self.assertEqual(g.node_count(), 0)
        self.assertEqual(g.edge_count(), 0)

    def test_json_roundtrip(self):
        self._build_sample()
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False, encoding="utf-8"
        ) as f:
            path = f.name
        try:
            self.graph.to_json(path)
            loaded = EMLHypergraph.from_json(path)
            self.assertEqual(loaded.node_count(), 3)
            self.assertEqual(loaded.edge_count(), 4)
            self.assertEqual(set(loaded.V.keys()), {"n1", "n2", "n3"})
        finally:
            os.unlink(path)

    def test_pickle_roundtrip(self):
        self._build_sample()
        with tempfile.NamedTemporaryFile(
            suffix=".pickle", mode="wb", delete=False
        ) as f:
            path = f.name
        try:
            self.graph.to_pickle(path)
            loaded = EMLHypergraph.from_pickle(path)
            self.assertEqual(loaded.node_count(), 3)
            self.assertEqual(loaded.edge_count(), 4)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
