"""Compression pipeline stages for EML-SemZip.

Implements the five-stage compression pipeline:
1. Dead-Zero Pruning
2. EML-Lite Isomorphism Merge
3. Mao-Rui Semantic Weighting
4. k-Snap Semantic Kernel Selection
5. ANS Entropy Encoding
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from ..models.hyperedge import HyperEdge
from ..utils.cycle_detection import find_closed_cycles


@dataclass
class StageStats:
    """Statistics for a pipeline stage.

    Attributes:
        stage_name: Name of the stage.
        input_count: Number of items input to the stage.
        output_count: Number of items output from the stage.
        elapsed_ms: Elapsed time in milliseconds.
        details: Additional stage-specific details.
    """

    stage_name: str
    input_count: int
    output_count: int
    elapsed_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


def stage1_dead_zero_prune(
    edges: List[HyperEdge], theta_dead: float
) -> Tuple[List[HyperEdge], List[Dict[str, Any]], StageStats]:
    """Dead-Zero Pruning - filter edges with I_value < theta_dead.

    Args:
        edges: List of hyperedges to prune.
        theta_dead: Threshold for I_value; edges with I_value < theta_dead are pruned.

    Returns:
        A tuple of (kept_edges, pruned_summary, stats).
    """
    start = time.perf_counter()
    kept = []
    pruned_summary = []

    for edge in edges:
        if edge.I_value >= theta_dead:
            kept.append(edge)
        else:
            pruned_summary.append({
                "edge_id": edge.edge_id,
                "I_value": edge.I_value,
                "predicate": edge.predicate,
                "nodes": sorted(edge.nodes),
            })

    elapsed = (time.perf_counter() - start) * 1000.0
    stats = StageStats(
        stage_name="stage1_dead_zero_prune",
        input_count=len(edges),
        output_count=len(kept),
        elapsed_ms=elapsed,
        details={
            "theta_dead": theta_dead,
            "pruned_count": len(pruned_summary),
        },
    )
    return kept, pruned_summary, stats


def stage2_isomorphism_merge(
    edges_pruned: List[HyperEdge], kb: Any
) -> Tuple[List[HyperEdge], List[Any], StageStats]:
    """EML-Lite Isomorphism Merge - absorb edges that match KB patterns.

    Args:
        edges_pruned: List of pruned hyperedges.
        kb: EMLLiteKB instance for pattern matching.

    Returns:
        A tuple of (merged_edges, absorb_records, stats).
    """
    start = time.perf_counter()
    merged = []
    absorb_records = []
    matched_ids = set()

    for edge in edges_pruned:
        if kb is not None:
            pattern = kb.find_isomorphic(edge)
            if pattern is not None:
                record = kb.absorb(edge)
                absorb_records.append(record)
                matched_ids.add(edge.edge_id)
                continue
        merged.append(edge)

    elapsed = (time.perf_counter() - start) * 1000.0
    stats = StageStats(
        stage_name="stage2_isomorphism_merge",
        input_count=len(edges_pruned),
        output_count=len(merged),
        elapsed_ms=elapsed,
        details={
            "absorbed_count": len(absorb_records),
            "kb_patterns": len(kb.patterns) if kb is not None else 0,
        },
    )
    return merged, absorb_records, stats


def stage3_mao_rui_weighting(edges_merged: List[HyperEdge]) -> StageStats:
    """Mao-Rui Semantic Weighting - compute d_sem for all edges.

    Args:
        edges_merged: List of merged hyperedges.

    Returns:
        StageStats with weighting details.
    """
    start = time.perf_counter()
    weighted_count = 0

    for edge in edges_merged:
        edge.compute_d_sem()
        weighted_count += 1

    elapsed = (time.perf_counter() - start) * 1000.0
    stats = StageStats(
        stage_name="stage3_mao_rui_weighting",
        input_count=len(edges_merged),
        output_count=weighted_count,
        elapsed_ms=elapsed,
        details={
            "d_sem_min": min((e.d_sem for e in edges_merged), default=0.0),
            "d_sem_max": max((e.d_sem for e in edges_merged), default=0.0),
        },
    )
    return stats


def stage4_ksnap_selection(
    edges_merged: List[HyperEdge],
    keep_ratio: float,
    cycle_detector: Any = None,
) -> Tuple[set, List[HyperEdge], StageStats]:
    """k-Snap Semantic Kernel Selection - select top edges by I_value.

    Args:
        edges_merged: List of merged hyperedges.
        keep_ratio: Fraction of edges to keep (0.0 - 1.0).
        cycle_detector: Optional cycle detector (unused, kept for API compatibility).

    Returns:
        A tuple of (V_star, E_star, stats).
    """
    start = time.perf_counter()

    if not edges_merged:
        stats = StageStats(
            stage_name="stage4_ksnap_selection",
            input_count=0,
            output_count=0,
            elapsed_ms=0.0,
            details={"keep_ratio": keep_ratio},
        )
        return set(), [], stats

    # Sort by I_value descending
    sorted_edges = sorted(edges_merged, key=lambda e: e.I_value, reverse=True)
    k = max(1, int(len(sorted_edges) * keep_ratio))

    # Select top-k edges
    selected_edges = sorted_edges[:k]
    E_star = selected_edges

    # Build V_star: all nodes in selected edges
    V_star = set()
    for edge in E_star:
        V_star.update(edge.nodes)

    # Ensure closed cycles: add edges that form cycles with >= 3 nodes
    cycles = find_closed_cycles(edges_merged, min_length=3)
    for cycle in cycles:
        cycle_nodes = set()
        for edge_id in cycle:
            for edge in edges_merged:
                if edge.edge_id == edge_id:
                    cycle_nodes.update(edge.nodes)
                    break
        if len(cycle_nodes) >= 3:
            V_star.update(cycle_nodes)
            for edge_id in cycle:
                for edge in edges_merged:
                    if edge.edge_id == edge_id and edge not in E_star:
                        E_star.append(edge)

    elapsed = (time.perf_counter() - start) * 1000.0
    stats = StageStats(
        stage_name="stage4_ksnap_selection",
        input_count=len(edges_merged),
        output_count=len(E_star),
        elapsed_ms=elapsed,
        details={
            "keep_ratio": keep_ratio,
            "k": k,
            "V_star_size": len(V_star),
            "cycles_found": len(cycles),
        },
    )
    return V_star, E_star, stats


def stage5_ans_encode(
    V_star: set,
    E_star: List[HyperEdge],
    theta_dead: float,
    kb_sig: str,
    pruned_summary: List[Dict[str, Any]],
    absorb_records: List[Any],
) -> bytes:
    """ANS Entropy Encoding - serialize payload and encode with ANS.

    Args:
        V_star: Set of selected node IDs.
        E_star: List of selected hyperedges.
        theta_dead: Dead-zero threshold used in pruning.
        kb_sig: Knowledge base signature.
        pruned_summary: List of pruned edge summaries.
        absorb_records: List of absorption records.

    Returns:
        Encoded bytes (SemPkt format).
    """
    from ..coding.serializer import SemPktPayload, serialize
    from ..coding.sempkt import SemPkt

    payload = SemPktPayload(
        V_star=V_star,
        E_star=E_star,
        theta_dead=theta_dead,
        kb_sig=kb_sig,
        pruned_summary=pruned_summary,
        absorb_records=absorb_records,
    )

    serialized = serialize(payload)
    pkt = SemPkt(payload=serialized)
    return pkt.to_bytes()
