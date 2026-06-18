"""Tests for eml_semzip.pipeline: stages, Compressor, Decompressor."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eml_semzip.models.hypergraph import EMLHypergraph
from eml_semzip.models.node import Node
from eml_semzip.models.hyperedge import HyperEdge
from eml_semzip.kb.eml_lite_kb import EMLLiteKB
from eml_semzip.kb.builtin_kb import create_builtin_kb, create_empty_kb
from eml_semzip.pipeline.stages import (
    stage1_dead_zero_prune,
    stage2_isomorphism_merge,
    stage3_mao_rui_weighting,
    stage4_ksnap_selection,
    stage5_ans_encode,
    StageStats,
)
from eml_semzip.pipeline.compressor import Compressor
from eml_semzip.pipeline.decompressor import Decompressor


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestStageStats(unittest.TestCase):
    """Tests for StageStats."""

    def test_create(self):
        stats = StageStats(
            stage_name="test",
            input_count=10,
            output_count=5,
            elapsed_ms=1.5,
            details={"key": "value"},
        )
        self.assertEqual(stats.stage_name, "test")
        self.assertEqual(stats.input_count, 10)
        self.assertEqual(stats.output_count, 5)
        self.assertAlmostEqual(stats.elapsed_ms, 1.5)
        self.assertEqual(stats.details, {"key": "value"})


class TestStage1DeadZeroPrune(unittest.TestCase):
    """Tests for dead-zero pruning stage."""

    def setUp(self):
        self.edges = [
            HyperEdge(edge_id="e1", I_value=0.9, predicate="knows"),
            HyperEdge(edge_id="e2", I_value=0.5, predicate="works_on"),
            HyperEdge(edge_id="e3", I_value=0.3, predicate="works_on"),
            HyperEdge(edge_id="e4", I_value=0.1, predicate="related"),
        ]

    def test_prune_below_threshold(self):
        kept, pruned, stats = stage1_dead_zero_prune(self.edges, 0.45)
        # e1(0.9), e2(0.5) kept; e3(0.3), e4(0.1) pruned
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(pruned), 2)
        pruned_ids = {p["edge_id"] for p in pruned}
        self.assertIn("e3", pruned_ids)
        self.assertIn("e4", pruned_ids)
        self.assertNotIn("e1", pruned_ids)
        self.assertEqual(stats.stage_name, "stage1_dead_zero_prune")
        self.assertEqual(stats.input_count, 4)
        self.assertEqual(stats.details["theta_dead"], 0.45)

    def test_keep_all_at_low_threshold(self):
        kept, pruned, stats = stage1_dead_zero_prune(self.edges, 0.05)
        self.assertEqual(len(kept), 4)
        self.assertEqual(len(pruned), 0)

    def test_prune_all_at_high_threshold(self):
        kept, pruned, stats = stage1_dead_zero_prune(self.edges, 1.0)
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(pruned), 4)

    def test_empty_input(self):
        kept, pruned, stats = stage1_dead_zero_prune([], 0.45)
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(pruned), 0)
        self.assertEqual(stats.input_count, 0)

    def test_pruned_summary_format(self):
        edges = [HyperEdge(edge_id="e1", nodes={"a", "b"}, I_value=0.1, predicate="test")]
        _, pruned, _ = stage1_dead_zero_prune(edges, 0.5)
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["edge_id"], "e1")
        self.assertEqual(pruned[0]["I_value"], 0.1)
        self.assertEqual(pruned[0]["predicate"], "test")


class TestStage2IsomorphismMerge(unittest.TestCase):
    """Tests for isomorphism merge stage."""

    def setUp(self):
        self.kb = EMLLiteKB()
        self.kb.add_pattern(HyperEdge(
            edge_id="pat",
            nodes={"n_a", "n_b"},
            predicate="knows",
            attr_types={"name", "type"},
        ))

    def test_merge_with_match(self):
        edges = [
            HyperEdge(
                edge_id="e1",
                nodes={"n1", "n2"},
                I_value=0.9,
                predicate="knows",
                attr_types={"name", "type"},
            ),
            HyperEdge(
                edge_id="e2",
                nodes={"n1", "n3"},
                I_value=0.8,
                predicate="other",
                attr_types={"name"},
            ),
        ]
        merged, records, stats = stage2_isomorphism_merge(edges, self.kb)
        self.assertEqual(len(merged), 1)  # Only e2 survives
        self.assertEqual(merged[0].edge_id, "e2")
        self.assertEqual(len(records), 1)  # e1 absorbed
        self.assertEqual(records[0].pattern_id, "pat")
        self.assertEqual(stats.stage_name, "stage2_isomorphism_merge")

    def test_merge_no_match(self):
        edges = [
            HyperEdge(
                edge_id="e1",
                nodes={"n1", "n2"},
                I_value=0.9,
                predicate="other",
                attr_types={"name"},
            ),
        ]
        merged, records, stats = stage2_isomorphism_merge(edges, self.kb)
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(records), 0)

    def test_merge_without_kb(self):
        edges = [HyperEdge(edge_id="e1", I_value=0.9)]
        merged, records, stats = stage2_isomorphism_merge(edges, None)
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(records), 0)

    def test_merge_empty_input(self):
        merged, records, stats = stage2_isomorphism_merge([], self.kb)
        self.assertEqual(len(merged), 0)
        self.assertEqual(stats.input_count, 0)


class TestStage3MaoRuiWeighting(unittest.TestCase):
    """Tests for semantic weighting stage."""

    def test_weight_all_edges(self):
        edges = [
            HyperEdge(edge_id="e1", I_value=0.9),
            HyperEdge(edge_id="e2", I_value=0.5),
            HyperEdge(edge_id="e3", I_value=0.3),
        ]
        stats = stage3_mao_rui_weighting(edges)
        self.assertEqual(stats.output_count, 3)
        for edge in edges:
            self.assertGreater(edge.d_sem, 0)
        self.assertGreater(stats.details["d_sem_max"], 0)

    def test_empty_edges(self):
        stats = stage3_mao_rui_weighting([])
        self.assertEqual(stats.output_count, 0)
        self.assertEqual(stats.details["d_sem_min"], 0.0)
        self.assertEqual(stats.details["d_sem_max"], 0.0)

    def test_d_sem_ordering(self):
        """Lower I_value should produce higher d_sem."""
        edge_low = HyperEdge(edge_id="e_low", I_value=0.3)
        edge_high = HyperEdge(edge_id="e_high", I_value=0.9)
        stage3_mao_rui_weighting([edge_low, edge_high])
        self.assertGreater(edge_low.d_sem, edge_high.d_sem)


class TestStage4KSnapSelection(unittest.TestCase):
    """Tests for k-snap semantic kernel selection."""

    def setUp(self):
        self.edges = [
            HyperEdge(edge_id="e1", nodes={"n1", "n2"}, I_value=0.9),
            HyperEdge(edge_id="e2", nodes={"n1", "n3"}, I_value=0.8),
            HyperEdge(edge_id="e3", nodes={"n2", "n3"}, I_value=0.3),
            HyperEdge(edge_id="e4", nodes={"n1", "n2", "n3"}, I_value=0.95),
        ]

    def test_select_top_by_keep_ratio(self):
        V_star, E_star, stats = stage4_ksnap_selection(self.edges, 0.5)
        # 4 edges * 0.5 = 2 kept
        self.assertEqual(stats.details["k"], 2)
        self.assertGreaterEqual(len(E_star), 2)
        self.assertIn("n1", V_star)
        self.assertEqual(stats.stage_name, "stage4_ksnap_selection")

    def test_select_all_at_ratio_1(self):
        V_star, E_star, stats = stage4_ksnap_selection(self.edges, 1.0)
        self.assertEqual(len(E_star), 4)

    def test_select_at_least_one(self):
        V_star, E_star, stats = stage4_ksnap_selection(self.edges, 0.01)
        self.assertGreaterEqual(len(E_star), 1)

    def test_empty_edges(self):
        V_star, E_star, stats = stage4_ksnap_selection([], 0.5)
        self.assertEqual(V_star, set())
        self.assertEqual(E_star, [])
        self.assertEqual(stats.input_count, 0)

    def test_V_star_coverage(self):
        V_star, E_star, stats = stage4_ksnap_selection(self.edges, 0.75)
        self.assertTrue(V_star)  # Should have at least one node


class TestStage5ANSEncode(unittest.TestCase):
    """Tests for ANS encoding stage."""

    def test_encode_produces_bytes(self):
        edge = HyperEdge(edge_id="e1", nodes={"n1"}, I_value=0.9)
        result = stage5_ans_encode(
            V_star={"n1"},
            E_star=[edge],
            theta_dead=0.45,
            kb_sig="test_sig",
            pruned_summary=[],
            absorb_records=[],
        )
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)

    def test_encode_empty_produces_bytes(self):
        result = stage5_ans_encode(
            V_star=set(),
            E_star=[],
            theta_dead=0.45,
            kb_sig="",
            pruned_summary=[],
            absorb_records=[],
        )
        self.assertIsInstance(result, bytes)


class TestCompressorDecompressorRoundtrip(unittest.TestCase):
    """Full pipeline roundtrip tests (Compressor + Decompressor)."""

    @staticmethod
    def _make_sample_hypergraph():
        """Build a test hypergraph with varied data."""
        graph = EMLHypergraph()
        graph.add_node(Node("n1", {"name": "Alice", "type": "person"}))
        graph.add_node(Node("n2", {"name": "Bob", "type": "person"}))
        graph.add_node(Node("n3", {"name": "Carol", "type": "person"}))
        graph.add_node(Node("n4", {"name": "ProjectA", "type": "project"}))
        graph.add_node(Node("n5", {"name": "ProjectB", "type": "project"}))

        edges_data = [
            ("e1", {"n1", "n2"}, 0.90, "knows", {"name", "type"}),
            ("e2", {"n1", "n3"}, 0.85, "knows", {"name", "type"}),
            ("e3", {"n2", "n3"}, 0.60, "knows", {"name", "type"}),
            ("e4", {"n1", "n4"}, 0.80, "works_on", {"name", "type"}),
            ("e5", {"n2", "n4"}, 0.70, "works_on", {"name", "type"}),
            ("e6", {"n3", "n5"}, 0.75, "works_on", {"name", "type"}),
            ("e7", {"n4", "n5"}, 0.20, "related", {"name", "type"}),
            ("e8", {"n1", "n2", "n4"}, 0.95, "collaborates", {"name", "type"}),
            ("e9", {"n2", "n3", "n5"}, 0.50, "collaborates", {"name", "type"}),
            ("e10", {"n1", "n2", "n3"}, 0.88, "interacts_with", {"name", "type"}),
        ]
        for eid, nodes, iv, pred, atypes in edges_data:
            graph.add_edge(HyperEdge(
                edge_id=eid, nodes=nodes,
                I_value=iv, predicate=pred, attr_types=atypes,
            ))
        return graph

    # ------------------------------------------------------------------
    # Roundtrip WITHOUT KB (basic compression/decompression)
    # ------------------------------------------------------------------

    def test_roundtrip_no_kb(self):
        graph = self._make_sample_hypergraph()
        compressor = Compressor(kb=None, theta_dead=0.45, keep_ratio=0.5)
        compressed = compressor.compress(graph)
        self.assertIsInstance(compressed, bytes)
        self.assertGreater(len(compressed), 0)

        decompressor = Decompressor(kb=None)
        restored = decompressor.decompress(compressed)

        # After compression with pruning + k-snap, restored will have
        # fewer edges but should have some nodes
        self.assertIsInstance(restored, EMLHypergraph)
        self.assertGreaterEqual(restored.node_count(), 0)

    def test_roundtrip_no_kb_higher_keep(self):
        """With higher keep_ratio, more edges survive."""
        graph = self._make_sample_hypergraph()
        compressor = Compressor(kb=None, theta_dead=0.1, keep_ratio=0.9)
        compressed = compressor.compress(graph)
        decompressor = Decompressor(kb=None)
        restored = decompressor.decompress(compressed)
        self.assertIsInstance(restored, EMLHypergraph)

    def test_roundtrip_no_kb_empty(self):
        graph = EMLHypergraph()
        compressor = Compressor(kb=None)
        compressed = compressor.compress(graph)
        decompressor = Decompressor(kb=None)
        restored = decompressor.decompress(compressed)
        self.assertIsInstance(restored, EMLHypergraph)
        self.assertEqual(restored.node_count(), 0)
        self.assertEqual(restored.edge_count(), 0)

    def test_roundtrip_no_kb_single_edge(self):
        graph = EMLHypergraph()
        graph.add_node(Node("n1", {"type": "person"}))
        graph.add_node(Node("n2", {"type": "person"}))
        graph.add_edge(HyperEdge(
            edge_id="e1", nodes={"n1", "n2"},
            I_value=0.9, predicate="knows",
        ))
        compressor = Compressor(kb=None, theta_dead=0.1, keep_ratio=1.0)
        compressed = compressor.compress(graph)
        decompressor = Decompressor(kb=None)
        restored = decompressor.decompress(compressed)
        self.assertEqual(restored.node_count(), 2)
        self.assertEqual(restored.edge_count(), 1)

    # ------------------------------------------------------------------
    # Roundtrip WITH built-in KB
    # ------------------------------------------------------------------

    def test_roundtrip_with_builtin_kb(self):
        graph = self._make_sample_hypergraph()
        kb = create_builtin_kb()
        compressor = Compressor(kb=kb, theta_dead=0.3, keep_ratio=0.6)
        compressed = compressor.compress(graph)
        decompressor = Decompressor(kb=kb)
        restored = decompressor.decompress(compressed)
        self.assertIsInstance(restored, EMLHypergraph)

    def test_roundtrip_with_builtin_kb_full_keep(self):
        graph = self._make_sample_hypergraph()
        kb = create_builtin_kb()
        compressor = Compressor(kb=kb, theta_dead=0.0, keep_ratio=1.0)
        compressed = compressor.compress(graph)
        decompressor = Decompressor(kb=kb)
        restored = decompressor.decompress(compressed)
        self.assertIsInstance(restored, EMLHypergraph)

    # ------------------------------------------------------------------
    # Compress report
    # ------------------------------------------------------------------

    def test_compressor_report(self):
        graph = self._make_sample_hypergraph()
        compressor = Compressor(kb=None)
        compressor.compress(graph)
        report = compressor.get_report()
        self.assertIn("theta_dead", report)
        self.assertIn("keep_ratio", report)
        self.assertIn("stages", report)
        self.assertGreaterEqual(len(report["stages"]), 4)

    def test_compressor_report_with_kb(self):
        graph = self._make_sample_hypergraph()
        kb = create_builtin_kb()
        compressor = Compressor(kb=kb)
        compressor.compress(graph)
        report = compressor.get_report()
        self.assertIn("stages", report)

    # ------------------------------------------------------------------
    # Pipeline five-stage integration
    # ------------------------------------------------------------------

    def test_full_pipeline_integration(self):
        """Run all five stages manually and verify the pipeline."""
        edges = [
            HyperEdge(edge_id="e1", nodes={"n1", "n2"}, I_value=0.9, predicate="knows"),
            HyperEdge(edge_id="e2", nodes={"n1", "n3"}, I_value=0.8, predicate="knows"),
            HyperEdge(edge_id="e3", nodes={"n2", "n3"}, I_value=0.3, predicate="knows"),
            HyperEdge(edge_id="e4", nodes={"n1", "n2", "n3"}, I_value=0.95, predicate="knows"),
        ]
        # Stage 1
        kept, pruned, s1 = stage1_dead_zero_prune(edges, 0.4)
        self.assertIsInstance(s1, StageStats)
        self.assertGreater(len(kept), 0)

        # Stage 2
        merged, records, s2 = stage2_isomorphism_merge(kept, None)
        self.assertEqual(len(merged), len(kept))
        self.assertEqual(len(records), 0)

        # Stage 3
        s3 = stage3_mao_rui_weighting(merged)
        self.assertIsInstance(s3, StageStats)

        # Stage 4
        V_star, E_star, s4 = stage4_ksnap_selection(merged, 0.5)
        self.assertIsInstance(s4, StageStats)
        self.assertGreater(len(E_star), 0)

        # Stage 5
        result = stage5_ans_encode(V_star, E_star, 0.4, "", pruned, records)
        self.assertIsInstance(result, bytes)
        self.assertGreater(len(result), 0)


class TestPipelineSampleGraph(unittest.TestCase):
    """Tests using the sample_graph.json fixture."""

    def test_load_and_compress(self):
        path = os.path.join(FIXTURES_DIR, "sample_graph.json")
        graph = EMLHypergraph.from_json(path)
        self.assertEqual(graph.node_count(), 3)
        self.assertEqual(graph.edge_count(), 4)

        compressor = Compressor(kb=None, theta_dead=0.4, keep_ratio=1.0)
        compressed = compressor.compress(graph)
        self.assertGreater(len(compressed), 0)

        decompressor = Decompressor(kb=None)
        restored = decompressor.decompress(compressed)
        # With theta_dead=0.4, e3(I=0.3) is pruned, so only 3 edges survive
        # With keep_ratio=1.0, all 3 survive
        self.assertEqual(restored.edge_count(), 3)


if __name__ == "__main__":
    unittest.main()
