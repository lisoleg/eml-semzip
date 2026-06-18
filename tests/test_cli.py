"""Tests for eml_semzip.cli: CLI argument parsing and commands."""

import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eml_semzip.cli.main import build_parser, cmd_compress, cmd_decompress, cmd_info
from eml_semzip.models.hypergraph import EMLHypergraph
from eml_semzip.models.node import Node
from eml_semzip.models.hyperedge import HyperEdge
from eml_semzip.kb.builtin_kb import create_builtin_kb
from eml_semzip.coding.sempkt import SemPkt


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestCLIParser(unittest.TestCase):
    """Tests for CLI argument parser configuration."""

    def setUp(self):
        self.parser = build_parser()

    def test_compress_subcommand(self):
        args = self.parser.parse_args([
            "compress", "input.json", "output.esz",
        ])
        self.assertEqual(args.command, "compress")
        self.assertEqual(args.input, "input.json")
        self.assertEqual(args.output, "output.esz")
        self.assertEqual(args.theta_dead, 0.45)
        self.assertEqual(args.keep_ratio, 0.15)
        self.assertIsNone(args.kb)
        self.assertFalse(args.use_builtin_kb)

    def test_compress_with_options(self):
        args = self.parser.parse_args([
            "compress", "input.json", "output.esz",
            "--theta-dead", "0.6",
            "--keep-ratio", "0.3",
            "--kb", "kb.json",
            "--use-builtin-kb",
            "--report", "report.txt",
            "--report-format", "json",
        ])
        self.assertEqual(args.theta_dead, 0.6)
        self.assertEqual(args.keep_ratio, 0.3)
        self.assertEqual(args.kb, "kb.json")
        self.assertTrue(args.use_builtin_kb)
        self.assertEqual(args.report, "report.txt")
        self.assertEqual(args.report_format, "json")

    def test_decompress_subcommand(self):
        args = self.parser.parse_args([
            "decompress", "input.esz", "output.json",
        ])
        self.assertEqual(args.command, "decompress")
        self.assertEqual(args.input, "input.esz")
        self.assertEqual(args.output, "output.json")

    def test_info_subcommand(self):
        args = self.parser.parse_args(["info", "file.esz"])
        self.assertEqual(args.command, "info")
        self.assertEqual(args.file, "file.esz")


class TestCLICompressDecompress(unittest.TestCase):
    """Integration tests for CLI compress/decompress commands."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _build_graph(self):
        graph = EMLHypergraph()
        graph.add_node(Node("n1", {"name": "Alice", "type": "person"}))
        graph.add_node(Node("n2", {"name": "Bob", "type": "person"}))
        graph.add_node(Node("n3", {"name": "ProjectX", "type": "project"}))
        graph.add_edge(HyperEdge(
            edge_id="e1", nodes={"n1", "n2"},
            I_value=0.9, predicate="knows",
        ))
        graph.add_edge(HyperEdge(
            edge_id="e2", nodes={"n1", "n3"},
            I_value=0.8, predicate="works_on",
        ))
        return graph

    def test_compress_to_bytes(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.json")
        graph.to_json(input_path)

        output_path = os.path.join(self.temp_dir, "output.esz")
        from eml_semzip.cli.main import main as cli_main
        cli_main([
            "compress", input_path, output_path,
            "--theta-dead", "0.1",
            "--keep-ratio", "1.0",
        ])

        self.assertTrue(os.path.exists(output_path))
        self.assertGreater(os.path.getsize(output_path), 0)

    def test_compress_decompress_roundtrip(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.json")
        graph.to_json(input_path)

        compress_path = os.path.join(self.temp_dir, "compressed.esz")
        decompress_path = os.path.join(self.temp_dir, "output.json")

        from eml_semzip.cli.main import main as cli_main
        cli_main([
            "compress", input_path, compress_path,
            "--theta-dead", "0.1",
            "--keep-ratio", "1.0",
        ])
        cli_main([
            "decompress", compress_path, decompress_path,
        ])

        restored = EMLHypergraph.from_json(decompress_path)
        self.assertIsInstance(restored, EMLHypergraph)
        self.assertEqual(restored.node_count(), 3)
        self.assertEqual(restored.edge_count(), 2)

    def test_compress_with_builtin_kb(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.json")
        graph.to_json(input_path)
        output_path = os.path.join(self.temp_dir, "output.esz")

        from eml_semzip.cli.main import main as cli_main
        cli_main([
            "compress", input_path, output_path,
            "--use-builtin-kb",
            "--theta-dead", "0.1",
            "--keep-ratio", "1.0",
        ])

        self.assertTrue(os.path.exists(output_path))

    def test_compress_with_report_text(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.json")
        graph.to_json(input_path)
        output_path = os.path.join(self.temp_dir, "output.esz")
        report_path = os.path.join(self.temp_dir, "report.txt")

        from eml_semzip.cli.main import main as cli_main
        cli_main([
            "compress", input_path, output_path,
            "--report", report_path,
            "--report-format", "text",
            "--theta-dead", "0.1",
            "--keep-ratio", "1.0",
        ])

        self.assertTrue(os.path.exists(report_path))
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("EML-SemZip Compression Report", content)

    def test_compress_with_report_json(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.json")
        graph.to_json(input_path)
        output_path = os.path.join(self.temp_dir, "output.esz")
        report_path = os.path.join(self.temp_dir, "report.json")

        from eml_semzip.cli.main import main as cli_main
        cli_main([
            "compress", input_path, output_path,
            "--report", report_path,
            "--report-format", "json",
            "--theta-dead", "0.1",
            "--keep-ratio", "1.0",
        ])

        self.assertTrue(os.path.exists(report_path))
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        self.assertIn("original_nodes", report)
        self.assertIn("compressed_bytes", report)

    def test_info_on_json(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.json")
        graph.to_json(input_path)

        from eml_semzip.cli.main import main as cli_main
        saved_stdout = sys.stdout
        try:
            sys.stdout = io.StringIO()
            cli_main(["info", input_path])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = saved_stdout
        self.assertIn("Nodes:", output)
        self.assertIn("Edges:", output)

    def test_info_on_compressed(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.json")
        graph.to_json(input_path)
        output_path = os.path.join(self.temp_dir, "output.esz")

        from eml_semzip.cli.main import main as cli_main
        cli_main(["compress", input_path, output_path,
                  "--theta-dead", "0.1", "--keep-ratio", "1.0"])

        saved_stdout = sys.stdout
        try:
            sys.stdout = io.StringIO()
            cli_main(["info", output_path])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = saved_stdout
        self.assertIn("Valid SemPkt", output)

    def test_compress_from_pickle(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.pickle")
        graph.to_pickle(input_path)
        output_path = os.path.join(self.temp_dir, "output.esz")

        from eml_semzip.cli.main import main as cli_main
        cli_main(["compress", input_path, output_path,
                  "--theta-dead", "0.1", "--keep-ratio", "1.0"])
        self.assertTrue(os.path.exists(output_path))

    def test_decompress_to_pickle(self):
        graph = self._build_graph()
        input_path = os.path.join(self.temp_dir, "input.json")
        graph.to_json(input_path)
        compress_path = os.path.join(self.temp_dir, "compressed.esz")
        output_path = os.path.join(self.temp_dir, "output.pickle")

        from eml_semzip.cli.main import main as cli_main
        cli_main(["compress", input_path, compress_path,
                  "--theta-dead", "0.1", "--keep-ratio", "1.0"])
        cli_main(["decompress", compress_path, output_path])

        self.assertTrue(os.path.exists(output_path))
        restored = EMLHypergraph.from_pickle(output_path)
        self.assertEqual(restored.node_count(), 3)
        self.assertEqual(restored.edge_count(), 2)


if __name__ == "__main__":
    unittest.main()
