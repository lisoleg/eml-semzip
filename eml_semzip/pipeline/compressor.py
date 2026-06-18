"""Compressor class for EML-SemZip.

Runs the five-stage compression pipeline and produces a compressed byte stream.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from ..kb.eml_lite_kb import EMLLiteKB
from ..models.hypergraph import EMLHypergraph
from ..pipeline.stages import (
    StageStats,
    stage1_dead_zero_prune,
    stage2_isomorphism_merge,
    stage3_mao_rui_weighting,
    stage4_ksnap_selection,
    stage5_ans_encode,
)
from ..utils.cycle_detection import find_closed_cycles


class Compressor:
    """Runs the five-stage EML-SemZip compression pipeline.

    Attributes:
        kb: Optional knowledge base for isomorphism merging.
        theta_dead: Threshold for dead-zero pruning.
        keep_ratio: Fraction of edges to keep in k-snap selection.
        stats: List of StageStats from the last compression.
    """

    def __init__(
        self,
        kb: Optional[EMLLiteKB] = None,
        theta_dead: float = 0.45,
        keep_ratio: float = 0.15,
    ) -> None:
        """Initialize the compressor.

        Args:
            kb: Knowledge base for pattern matching (default None).
            theta_dead: I_value threshold for pruning (default 0.45).
            keep_ratio: Fraction of edges to keep (default 0.15).
        """
        self.kb = kb
        self.theta_dead = theta_dead
        self.keep_ratio = keep_ratio
        self.stats: List[StageStats] = []

    def compress(self, hypergraph: EMLHypergraph) -> bytes:
        """Compress a hypergraph into bytes.

        Runs the five-stage pipeline:
        1. Dead-zero pruning
        2. Isomorphism merging
        3. Semantic weighting
        4. k-snap selection
        5. ANS encoding

        Args:
            hypergraph: The EMLHypergraph to compress.

        Returns:
            Compressed bytes.
        """
        self.stats = []
        edges = hypergraph.E

        # Stage 1: Dead-zero pruning
        kept, pruned_summary, stats1 = stage1_dead_zero_prune(
            edges, self.theta_dead
        )
        self.stats.append(stats1)

        # Stage 2: Isomorphism merging
        merged, absorb_records, stats2 = stage2_isomorphism_merge(
            kept, self.kb
        )
        self.stats.append(stats2)

        # Stage 3: Semantic weighting
        stats3 = stage3_mao_rui_weighting(merged)
        self.stats.append(stats3)

        # Stage 4: k-snap selection
        V_star, E_star, stats4 = stage4_ksnap_selection(
            merged, self.keep_ratio
        )
        self.stats.append(stats4)

        # Compute KB signature
        kb_sig = self.kb.compute_sig() if self.kb is not None else ""

        # Stage 5: ANS encoding
        result = stage5_ans_encode(
            V_star, E_star, self.theta_dead, kb_sig, pruned_summary, absorb_records
        )
        # Stats for stage5 are embedded in the payload; no separate StageStats

        return result

    def get_report(self) -> Dict[str, Any]:
        """Generate a report of the last compression.

        Returns:
            Dictionary with compression statistics.
        """
        report: Dict[str, Any] = {
            "theta_dead": self.theta_dead,
            "keep_ratio": self.keep_ratio,
            "stages": [],
        }
        for stats in self.stats:
            report["stages"].append({
                "stage_name": stats.stage_name,
                "input_count": stats.input_count,
                "output_count": stats.output_count,
                "elapsed_ms": stats.elapsed_ms,
                "details": stats.details,
            })
        return report
