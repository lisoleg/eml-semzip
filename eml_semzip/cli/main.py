"""CLI entry point for EML-SemZip.

Provides compress, decompress, info, and batch subcommands via argparse.
Usage: python -m eml_semzip.cli.main <command> [options]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from ..io.report import CompressionReport
from ..kb.builtin_kb import create_builtin_kb, create_empty_kb
from ..models.hypergraph import EMLHypergraph
from ..pipeline import Compressor, Decompressor


def cmd_compress(args: argparse.Namespace) -> None:
    """Run the compress command.

    Args:
        args: Parsed CLI arguments.
    """
    start_time = time.time()

    # Load input hypergraph
    if args.input.endswith(".json"):
        graph = EMLHypergraph.from_json(args.input)
        original_bytes = os.path.getsize(args.input)
    else:
        graph = EMLHypergraph.from_pickle(args.input)
        original_bytes = os.path.getsize(args.input)

    # Initialize KB
    kb = None
    if args.kb:
        from ..kb.eml_lite_kb import EMLLiteKB
        kb = EMLLiteKB.load(args.kb)
    elif args.use_builtin_kb:
        kb = create_builtin_kb()

    # Compress
    compressor = Compressor(
        kb=kb,
        theta_dead=args.theta_dead,
        keep_ratio=args.keep_ratio,
    )
    compressed = compressor.compress(graph)

    # Write output
    with open(args.output, "wb") as f:
        f.write(compressed)

    elapsed_ms = (time.time() - start_time) * 1000

    # Report
    if args.report:
        # Count compressed edges from compressor stats
        compressed_edges = 0
        for stats in compressor.stats:
            if stats.stage_name == "stage4_ksnap_selection":
                compressed_edges = stats.output_count

        report = CompressionReport(
            original_nodes=graph.node_count(),
            original_edges=graph.edge_count(),
            compressed_bytes=len(compressed),
            original_bytes=original_bytes,
            theta_dead=args.theta_dead,
            keep_ratio=args.keep_ratio,
            compressed_edges=compressed_edges,
            stage_stats=[s.__dict__ for s in compressor.stats],
            elapsed_total_ms=elapsed_ms,
            timestamp=__import__("datetime").datetime.now().isoformat(),
        )
        if args.report_format == "json":
            with open(args.report, "w", encoding="utf-8") as f:
                f.write(report.to_json())
        else:
            with open(args.report, "w", encoding="utf-8") as f:
                f.write(report.to_text())

        # Print SCR summary to stdout
        print(f"Compression complete: {args.input} -> {args.output}")
        print(f"  Original: {original_bytes} bytes, {graph.edge_count()} edges")
        print(f"  Compressed: {len(compressed)} bytes")
        print(f"  SCR (anchor): {report.scr_anchor:.2f}x")
        print(f"  SCR (info): {report.scr_info:.2f}x")
        print(f"  Bit ratio: {report.bit_compression_ratio:.2f}x")


def cmd_decompress(args: argparse.Namespace) -> None:
    """Run the decompress command.

    Args:
        args: Parsed CLI arguments.
    """
    # Initialize KB
    kb = None
    if args.kb:
        from ..kb.eml_lite_kb import EMLLiteKB
        kb = EMLLiteKB.load(args.kb)
    elif args.use_builtin_kb:
        kb = create_builtin_kb()

    # Read compressed data
    with open(args.input, "rb") as f:
        data = f.read()

    # Decompress
    decompressor = Decompressor(kb=kb)
    graph = decompressor.decompress(data)

    # Write output
    if args.output.endswith(".json"):
        graph.to_json(args.output)
    else:
        graph.to_pickle(args.output)

    print(f"Decompression complete: {args.input} -> {args.output}")
    print(f"  Restored: {graph.node_count()} nodes, {graph.edge_count()} edges")


def cmd_batch_compress(args: argparse.Namespace) -> None:
    """Run batch compression on a directory.

    Args:
        args: Parsed CLI arguments.
    """
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all compressible files
    extensions = [".json", ".pickle"]
    files = []
    for ext in extensions:
        files.extend(input_dir.rglob(f"*{ext}"))

    if not files:
        print(f"No .json or .pickle files found in {input_dir}")
        return

    print(f"Found {len(files)} files to compress")

    # Initialize KB once
    kb = None
    if args.kb:
        from ..kb.eml_lite_kb import EMLLiteKB
        kb = EMLLiteKB.load(args.kb)
    elif args.use_builtin_kb:
        kb = create_builtin_kb()

    # Batch report
    batch_report = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "files": [],
        "summary": {
            "total_files": len(files),
            "total_original_bytes": 0,
            "total_compressed_bytes": 0,
            "total_original_edges": 0,
            "total_compressed_edges": 0,
        },
    }

    for file_path in files:
        relative_path = file_path.relative_to(input_dir)
        output_path = output_dir / relative_path.with_suffix(".esz")

        # Ensure output subdirectory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Load
            if file_path.suffix == ".json":
                graph = EMLHypergraph.from_json(str(file_path))
            else:
                graph = EMLHypergraph.from_pickle(str(file_path))

            original_bytes = file_path.stat().st_size

            # Compress
            compressor = Compressor(
                kb=kb,
                theta_dead=args.theta_dead,
                keep_ratio=args.keep_ratio,
            )
            compressed = compressor.compress(graph)

            # Write
            with open(output_path, "wb") as f:
                f.write(compressed)

            # Count compressed edges
            compressed_edges = 0
            for stats in compressor.stats:
                if stats.stage_name == "stage4_ksnap_selection":
                    compressed_edges = stats.output_count

            # File report
            file_report = {
                "input": str(relative_path),
                "output": str(output_path.relative_to(output_dir)),
                "original_bytes": original_bytes,
                "compressed_bytes": len(compressed),
                "original_edges": graph.edge_count(),
                "compressed_edges": compressed_edges,
                "scr_anchor": graph.edge_count() / compressed_edges if compressed_edges > 0 else 0,
                "success": True,
            }

            batch_report["files"].append(file_report)
            batch_report["summary"]["total_original_bytes"] += original_bytes
            batch_report["summary"]["total_compressed_bytes"] += len(compressed)
            batch_report["summary"]["total_original_edges"] += graph.edge_count()
            batch_report["summary"]["total_compressed_edges"] += compressed_edges

            print(f"  [OK] {relative_path} -> {output_path.name} "
                  f"({original_bytes} -> {len(compressed)} bytes, "
                  f"SCR: {file_report['scr_anchor']:.2f}x)")

        except Exception as e:
            print(f"  [FAIL] {relative_path}: {e}")
            batch_report["files"].append({
                "input": str(relative_path),
                "success": False,
                "error": str(e),
            })

    # Write batch report
    report_path = output_dir / "batch_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(batch_report, f, ensure_ascii=False, indent=2)

    print(f"\nBatch compression complete: {len(files)} files")
    print(f"  Total original: {batch_report['summary']['total_original_bytes']} bytes")
    print(f"  Total compressed: {batch_report['summary']['total_compressed_bytes']} bytes")
    print(f"  Overall SCR (anchor): "
          f"{batch_report['summary']['total_original_edges'] / batch_report['summary']['total_compressed_edges']:.2f}x"
          if batch_report['summary']['total_compressed_edges'] > 0 else "N/A")
    print(f"  Report saved to: {report_path}")


def cmd_info(args: argparse.Namespace) -> None:
    """Run the info command.

    Args:
        args: Parsed CLI arguments.
    """
    if args.file.endswith(".json") or args.file.endswith(".pickle"):
        # Info about hypergraph file
        if args.file.endswith(".json"):
            graph = EMLHypergraph.from_json(args.file)
        else:
            graph = EMLHypergraph.from_pickle(args.file)
        print(f"Nodes: {graph.node_count()}")
        print(f"Edges: {graph.edge_count()}")
        for edge in graph.E[:10]:
            print(f"  Edge {edge.edge_id}: I_value={edge.I_value:.4f}")
    else:
        # Info about compressed file
        with open(args.file, "rb") as f:
            data = f.read()
        from ..coding.sempkt import SemPkt
        if SemPkt.is_valid(data):
            print(f"Valid SemPkt: {len(data)} bytes")
        else:
            print("Not a valid SemPkt file")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="eml_semzip",
        description="EML-SemZip: Semantic compression for EML hypergraphs",
    )
    sub = parser.add_subparsers(dest="command")

    # Compress subcommand
    c = sub.add_parser("compress", help="Compress a hypergraph")
    c.add_argument("input", help="Input hypergraph file (.json or .pickle)")
    c.add_argument("output", help="Output compressed file (.esz)")
    c.add_argument("--theta-dead", type=float, default=0.45, help="Dead-zero threshold")
    c.add_argument("--keep-ratio", type=float, default=0.15, help="Keep ratio for k-snap")
    c.add_argument("--kb", help="KB file for isomorphism merging")
    c.add_argument("--use-builtin-kb", action="store_true", help="Use built-in KB")
    c.add_argument("--report", help="Write report to file")
    c.add_argument("--report-format", choices=["text", "json"], default="text")

    # Decompress subcommand
    d = sub.add_parser("decompress", help="Decompress a hypergraph")
    d.add_argument("input", help="Input compressed file (.esz)")
    d.add_argument("output", help="Output hypergraph file (.json or .pickle)")
    d.add_argument("--kb", help="KB file for reconstruction")
    d.add_argument("--use-builtin-kb", action="store_true", help="Use built-in KB")

    # Batch compress subcommand
    b = sub.add_parser("batch-compress", help="Batch compress hypergraphs in a directory")
    b.add_argument("input_dir", help="Input directory containing .json/.pickle files")
    b.add_argument("output_dir", help="Output directory for .esz files")
    b.add_argument("--theta-dead", type=float, default=0.45, help="Dead-zero threshold")
    b.add_argument("--keep-ratio", type=float, default=0.15, help="Keep ratio for k-snap")
    b.add_argument("--kb", help="KB file for isomorphism merging")
    b.add_argument("--use-builtin-kb", action="store_true", help="Use built-in KB")

    # Info subcommand
    i = sub.add_parser("info", help="Show file info")
    i.add_argument("file", help="Input file (.json, .pickle, or .esz)")

    # Web subcommand
    w = sub.add_parser("web", help="Start web UI server")
    w.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    w.add_argument("--port", type=int, default=8080, help="Port number (default: 8080)")

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """CLI entry point.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "compress":
        cmd_compress(args)
    elif args.command == "decompress":
        cmd_decompress(args)
    elif args.command == "batch-compress":
        cmd_batch_compress(args)
    elif args.command == "web":
        from ..web.server import run_server
        run_server(host=args.host, port=args.port)
    elif args.command == "info":
        cmd_info(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
