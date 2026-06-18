"""Tests for eml_semzip.kb: EMLLiteKB, AbsorbRecord."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eml_semzip.kb.eml_lite_kb import AbsorbRecord, EMLLiteKB
from eml_semzip.kb.builtin_kb import create_builtin_kb, create_empty_kb
from eml_semzip.models.hyperedge import HyperEdge


class TestAbsorbRecord(unittest.TestCase):
    """Tests for AbsorbRecord."""

    def test_create(self):
        record = AbsorbRecord(
            pattern_id="pat1",
            node_mapping={"n_a": "n1", "n_b": "n2"},
            I_value=0.9,
            base_weight=1.0,
            dir_factor=1.0,
            predicate="knows",
        )
        self.assertEqual(record.pattern_id, "pat1")
        self.assertEqual(record.node_mapping, {"n_a": "n1", "n_b": "n2"})
        self.assertEqual(record.I_value, 0.9)
        self.assertEqual(record.predicate, "knows")

    def test_to_dict(self):
        record = AbsorbRecord(
            pattern_id="pat1",
            node_mapping={"a": "x"},
            I_value=0.5,
            base_weight=2.0,
            dir_factor=0.8,
            predicate="test",
        )
        d = record.to_dict()
        self.assertEqual(d["pattern_id"], "pat1")
        self.assertEqual(d["node_mapping"], {"a": "x"})
        self.assertEqual(d["I_value"], 0.5)
        self.assertEqual(d["base_weight"], 2.0)
        self.assertEqual(d["dir_factor"], 0.8)
        self.assertEqual(d["predicate"], "test")

    def test_from_dict(self):
        data = {
            "pattern_id": "pat1",
            "node_mapping": {"a": "x"},
            "I_value": 0.5,
            "base_weight": 2.0,
            "dir_factor": 0.8,
            "predicate": "test",
        }
        record = AbsorbRecord.from_dict(data)
        self.assertEqual(record.pattern_id, "pat1")
        self.assertEqual(record.node_mapping, {"a": "x"})
        self.assertAlmostEqual(record.I_value, 0.5)

    def test_roundtrip(self):
        original = AbsorbRecord(
            pattern_id="pat1",
            node_mapping={"a": "x", "b": "y"},
            I_value=0.75,
            base_weight=1.5,
            dir_factor=0.6,
            predicate="collaborates",
        )
        restored = AbsorbRecord.from_dict(original.to_dict())
        self.assertEqual(restored.pattern_id, original.pattern_id)
        self.assertEqual(restored.node_mapping, original.node_mapping)
        self.assertAlmostEqual(restored.I_value, original.I_value)


class TestEMLLiteKB(unittest.TestCase):
    """Tests for EMLLiteKB."""

    def setUp(self):
        self.kb = EMLLiteKB()

    # -- Pattern management --

    def test_add_pattern(self):
        edge = HyperEdge(
            edge_id="p1",
            nodes={"a", "b"},
            predicate="knows",
            attr_types={"name"},
        )
        self.kb.add_pattern(edge)
        self.assertEqual(len(self.kb.patterns), 1)

    def test_add_multiple_patterns(self):
        for i in range(5):
            self.kb.add_pattern(HyperEdge(
                edge_id=f"p{i}",
                nodes={"a", "b"},
                predicate=f"pred_{i}",
                attr_types={"name"},
            ))
        self.assertEqual(len(self.kb.patterns), 5)

    # -- Isomorphic matching --

    def test_find_isomorphic_match(self):
        pattern = HyperEdge(
            edge_id="pat",
            nodes={"n_a", "n_b"},
            predicate="knows",
            attr_types={"name", "type"},
        )
        self.kb.add_pattern(pattern)

        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            predicate="knows",
            attr_types={"name", "type"},
        )
        match = self.kb.find_isomorphic(edge)
        self.assertIsNotNone(match)
        self.assertEqual(match.edge_id, "pat")

    def test_find_isomorphic_no_match_predicate(self):
        pattern = HyperEdge(
            edge_id="pat",
            nodes={"a", "b"},
            predicate="knows",
            attr_types={"name"},
        )
        self.kb.add_pattern(pattern)

        edge = HyperEdge(
            edge_id="e1",
            nodes={"x", "y"},
            predicate="different",
            attr_types={"name"},
        )
        match = self.kb.find_isomorphic(edge)
        self.assertIsNone(match)

    def test_find_isomorphic_no_match_attr_types(self):
        pattern = HyperEdge(
            edge_id="pat",
            nodes={"a", "b"},
            predicate="knows",
            attr_types={"name", "type"},
        )
        self.kb.add_pattern(pattern)

        edge = HyperEdge(
            edge_id="e1",
            nodes={"x", "y"},
            predicate="knows",
            attr_types={"name", "age"},
        )
        match = self.kb.find_isomorphic(edge)
        self.assertIsNone(match)

    def test_find_isomorphic_no_match_node_count(self):
        pattern = HyperEdge(
            edge_id="pat",
            nodes={"a", "b", "c"},
            predicate="collaborates",
            attr_types={"name"},
        )
        self.kb.add_pattern(pattern)

        edge = HyperEdge(
            edge_id="e1",
            nodes={"x", "y"},
            predicate="collaborates",
            attr_types={"name"},
        )
        match = self.kb.find_isomorphic(edge)
        self.assertIsNone(match)

    # -- Absorb --

    def test_absorb_success(self):
        pattern = HyperEdge(
            edge_id="pat",
            nodes={"n_a", "n_b"},
            predicate="knows",
            attr_types={"name", "type"},
        )
        self.kb.add_pattern(pattern)

        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            I_value=0.9,
            base_weight=1.5,
            dir_factor=0.7,
            predicate="knows",
            attr_types={"name", "type"},
        )
        record = self.kb.absorb(edge)
        self.assertEqual(record.pattern_id, "pat")
        self.assertAlmostEqual(record.I_value, 0.9)
        self.assertAlmostEqual(record.base_weight, 1.5)
        self.assertEqual(len(self.kb.absorbed_records), 1)

    def test_absorb_no_match_raises(self):
        edge = HyperEdge(
            edge_id="e1",
            nodes={"n1", "n2"},
            predicate="knows",
        )
        with self.assertRaises(ValueError):
            self.kb.absorb(edge)

    # -- Signature --

    def test_compute_sig_empty(self):
        sig = self.kb.compute_sig()
        self.assertEqual(len(sig), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in sig))

    def test_compute_sig_deterministic(self):
        edges = [
            HyperEdge(edge_id="a", nodes={"x"}, predicate="p1", attr_types={"name"}),
            HyperEdge(edge_id="b", nodes={"x"}, predicate="p2", attr_types={"name"}),
        ]
        for e in edges:
            self.kb.add_pattern(e)
        sig1 = self.kb.compute_sig()
        sig2 = self.kb.compute_sig()
        self.assertEqual(sig1, sig2)

    def test_compute_sig_order_independent(self):
        kb1 = EMLLiteKB()
        kb2 = EMLLiteKB()
        edges = [
            HyperEdge(edge_id="a", nodes={"x"}, predicate="p1", attr_types={"name"}),
            HyperEdge(edge_id="b", nodes={"x"}, predicate="p2", attr_types={"name"}),
        ]
        kb1.add_pattern(edges[0])
        kb1.add_pattern(edges[1])
        kb2.add_pattern(edges[1])
        kb2.add_pattern(edges[0])
        self.assertEqual(kb1.compute_sig(), kb2.compute_sig())

    def test_verify_sig(self):
        edges = [
            HyperEdge(edge_id="a", nodes={"x"}, predicate="p1", attr_types={"name"}),
        ]
        for e in edges:
            self.kb.add_pattern(e)
        sig = self.kb.compute_sig()
        self.assertTrue(self.kb.verify_sig(sig))
        self.assertFalse(self.kb.verify_sig("invalid"))

    # -- Rebuild edges --

    def test_rebuild_edges(self):
        pattern = HyperEdge(
            edge_id="pat",
            nodes={"n_a", "n_b"},
            predicate="knows",
            attr_types={"name", "type"},
        )
        self.kb.add_pattern(pattern)

        records = [
            AbsorbRecord(
                pattern_id="pat",
                node_mapping={"n_a": "n1", "n_b": "n2"},
                I_value=0.9,
                base_weight=1.0,
                dir_factor=1.0,
                predicate="knows",
            ),
            AbsorbRecord(
                pattern_id="pat",
                node_mapping={"n_a": "n3", "n_b": "n4"},
                I_value=0.5,
                base_weight=2.0,
                dir_factor=0.8,
                predicate="knows",
            ),
        ]
        edges = self.kb.rebuild_edges(records)
        self.assertEqual(len(edges), 2)
        self.assertEqual(edges[0].predicate, "knows")
        self.assertIn("n1", edges[0].nodes)
        self.assertAlmostEqual(edges[1].I_value, 0.5)
        self.assertGreater(edges[0].d_sem, 0)
        self.assertGreater(edges[1].d_sem, 0)

    def test_rebuild_edges_missing_pattern(self):
        records = [
            AbsorbRecord(
                pattern_id="nonexistent",
                node_mapping={"a": "x"},
                I_value=0.9,
                base_weight=1.0,
                dir_factor=1.0,
                predicate="test",
            ),
        ]
        edges = self.kb.rebuild_edges(records)
        self.assertEqual(len(edges), 0)

    def test_rebuild_edges_empty(self):
        edges = self.kb.rebuild_edges([])
        self.assertEqual(edges, [])

    # -- Persistence --

    def test_save_load(self):
        pattern = HyperEdge(
            edge_id="pat",
            nodes={"a", "b"},
            predicate="knows",
            attr_types={"name"},
        )
        self.kb.add_pattern(pattern)
        self.kb.compute_sig()

        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False, encoding="utf-8"
        ) as f:
            path = f.name
        try:
            self.kb.save(path)
            loaded = EMLLiteKB.load(path)
            self.assertEqual(len(loaded.patterns), 1)
            self.assertEqual(loaded.sig, self.kb.sig)
        finally:
            os.unlink(path)


class TestBuiltinKB(unittest.TestCase):
    """Tests for built-in KB factory functions."""

    def test_create_empty_kb(self):
        kb = create_empty_kb()
        self.assertEqual(len(kb.patterns), 0)
        self.assertEqual(len(kb.index), 0)

    def test_create_builtin_kb(self):
        kb = create_builtin_kb()
        self.assertEqual(len(kb.patterns), 4)
        self.assertTrue(len(kb.sig) > 0)

    def test_builtin_kb_has_signature(self):
        kb = create_builtin_kb()
        self.assertEqual(len(kb.sig), 64)

    def test_builtin_kb_verify_own_sig(self):
        kb = create_builtin_kb()
        self.assertTrue(kb.verify_sig(kb.sig))


if __name__ == "__main__":
    unittest.main()
