"""Distributed compression for large-scale EML hypergraphs.

Partitions a large hypergraph across multiple workers (processes),
compresses each partition independently, then merges the results.

Uses Python multiprocessing (no external dependencies).
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..models.hypergraph import EMLHypergraph
from ..models.hyperedge import HyperEdge
from ..models.node import Node
from ..pipeline import Compressor, Decompressor
from ..kb.eml_lite_kb import EMLLiteKB
from ..constants import DEFAULT_THETA_DEAD, DEFAULT_KEEP_RATIO


def _graph_hash(g: EMLHypergraph) -> str:
    """Short hash for a hypergraph (used for partitioning)."""
    h = hashlib.md5()
    for nid in sorted(g.V.keys()):
        h.update(nid.encode())
    return h.hexdigest()[:8]


def _partition_graph(
    graph: EMLHypergraph,
    n_parts: int,
) -> List[EMLHypergraph]:
    """Partition a hypergraph into n_parts roughly equal shards.

    Strategy: hash-based partitioning.
    Each node is assigned to a partition based on hash(node_id).
    Edges follow their member nodes (assigned to the partition of their first member).
    """
    partitions: List[EMLHypergraph] = [EMLHypergraph() for _ in range(n_parts)]

    # Assign nodes
    node_partition: Dict[str, int] = {}
    for nid in graph.V:
        pid = int(hashlib.md5(nid.encode()).hexdigest()[:2], 16) % n_parts
        node_partition[nid] = pid
        partitions[pid].add_node(graph.V[nid])

    # Assign edges to the partition of their first member node
    for edge in graph.E:
        members = list(edge.nodes)
        if not members:
            continue
        pid = node_partition.get(members[0], 0)
        partitions[pid].add_edge(
            HyperEdge(
                edge.edge_id,
                set(edge.nodes),
                edge.I_value,
                edge.base_weight,
                edge.dir_factor,
                edge.predicate,
            )
        )

    return partitions


def _compress_partition(args_tuple) -> bytes:
    """Worker function: compress a single partition.

    Args:
        args_tuple: (partition_graph_dict, kb_dict_or_none, theta_dead, keep_ratio, worker_id)

    Returns:
        Tuple of (worker_id, compressed_bytes, report_dict)
    """
    graph_dict, kb_dict, theta_dead, keep_ratio, worker_id = args_tuple

    # Rebuild graph from dict
    g = EMLHypergraph()
    for nd in graph_dict.get("nodes", []):
        g.add_node(Node.from_dict(nd))
    for ed in graph_dict.get("edges", []):
        g.add_edge(HyperEdge.from_dict(ed))

    # Rebuild KB if provided
    kb = None
    if kb_dict is not None:
        kb = EMLLiteKB.from_dict(kb_dict)

    compressor = Compressor(kb=kb, theta_dead=theta_dead, keep_ratio=keep_ratio)
    compressed = compressor.compress(g)
    report = compressor.get_report()

    return (worker_id, compressed, report)


def _decompress_partition(args_tuple) -> EMLHypergraph:
    """Worker function: decompress a single partition."""
    compressed_bytes, kb_dict, worker_id = args_tuple

    kb = None
    if kb_dict is not None:
        kb = EMLLiteKB.from_dict(kb_dict)

    decompressor = Decompressor(kb=kb)
    return decompressor.decompress(compressed_bytes)


def compress_distributed(
    graph: EMLHypergraph,
    kb: Optional[EMLLiteKB] = None,
    n_workers: int = 4,
    theta_dead: float = DEFAULT_THETA_DEAD,
    keep_ratio: float = DEFAULT_KEEP_RATIO,
) -> List[bytes]:
    """Compress a large hypergraph using multiple worker processes.

    Args:
        graph: The hypergraph to compress.
        kb: Optional knowledge base.
        n_workers: Number of worker processes.
        theta_dead: Dead-zero threshold.
        keep_ratio: Semantic kernel keep ratio.

    Returns:
        List of compressed byte blobs (one per partition).
    """
    partitions = _partition_graph(graph, n_workers)

    # Prepare arguments for workers
    kb_dict = kb.to_dict() if kb is not None else None
    worker_args = [
        (p.to_dict(), kb_dict, theta_dead, keep_ratio, i)
        for i, p in enumerate(partitions)
    ]

    with mp.Pool(processes=n_workers) as pool:
        results = pool.map(_compress_partition, worker_args)

    # Sort by worker_id to maintain order
    results.sort(key=lambda x: x[0])
    return [r[1] for r in results]


def decompress_distributed(
    compressed_parts: List[bytes],
    kb: Optional[EMLLiteKB] = None,
) -> EMLHypergraph:
    """Decompress partitions and merge into a single hypergraph.

    Args:
        compressed_parts: List of compressed byte blobs from compress_distributed.
        kb: Optional knowledge base.

    Returns:
        Reconstructed EMLHypergraph.
    """
    kb_dict = kb.to_dict() if kb is not None else None
    worker_args = [(part, kb_dict, i) for i, part in enumerate(compressed_parts)]

    with mp.Pool(processes=len(worker_args)) as pool:
        partition_graphs = pool.map(_decompress_partition, worker_args)

    # Merge all partitions
    merged = EMLHypergraph()
    for pg in partition_graphs:
        for nid, node in pg.V.items():
            if nid not in merged.V:
                merged.add_node(node)
        for edge in pg.E:
            # Avoid duplicates
            if not any(e.edge_id == edge.edge_id for e in merged.E):
                merged.add_edge(edge)

    return merged


def compress_distributed_to_file(
    input_path: str,
    output_dir: str,
    kb: Optional[EMLLiteKB] = None,
    n_workers: int = 4,
    theta_dead: float = DEFAULT_THETA_DEAD,
    keep_ratio: float = DEFAULT_KEEP_RATIO,
) -> Dict[str, Any]:
    """Full pipeline: load graph, compress distributed, save partitions.

    Args:
        input_path: Path to input hypergraph (.json or .pickle).
        output_dir: Directory to save compressed partitions.
        kb: Optional knowledge base.
        n_workers: Number of worker processes.
        theta_dead: Dead-zero threshold.
        keep_ratio: Semantic kernel keep ratio.

    Returns:
        Summary dict with partition info.
    """
    # Load graph
    if input_path.endswith(".json"):
        graph = EMLHypergraph.from_json(input_path)
    else:
        graph = EMLHypergraph.from_pickle(input_path)

    # Compress
    parts = compress_distributed(graph, kb=kb, n_workers=n_workers,
                                   theta_dead=theta_dead, keep_ratio=keep_ratio)

    # Save partitions
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "input": input_path,
        "n_workers": n_workers,
        "n_partitions": len(parts),
        "total_original_nodes": graph.node_count(),
        "total_original_edges": graph.edge_count(),
        "partitions": [],
    }

    for i, compressed in enumerate(parts):
        part_path = out_dir / f"partition_{i:03d}.esz"
        with open(part_path, "wb") as f:
            f.write(compressed)
        summary["partitions"].append({
            "index": i,
            "path": str(part_path),
            "size_bytes": len(compressed),
        })

    # Save summary
    summary_path = out_dir / "distributed_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary
