"""Compression report output for EML-SemZip.

Provides CompressionReport dataclass with text and JSON output formats.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CompressionReport:
    """Report of a compression operation.

    Attributes:
        original_nodes: Number of nodes in original hypergraph.
        original_edges: Number of edges in original hypergraph.
        compressed_bytes: Size of compressed output in bytes.
        theta_dead: Dead-zero threshold used.
        keep_ratio: Keep ratio used.
        stage_stats: List of stage statistics.
        elapsed_total_ms: Total elapsed time in milliseconds.
        timestamp: ISO-format timestamp string.
        original_bytes: Original file size in bytes.
        compressed_edges: Number of edges in semantic kernel (anchors).
        kb_reuse_edges: Number of edges reusable from KB.
    """

    original_nodes: int = 0
    original_edges: int = 0
    compressed_bytes: int = 0
    theta_dead: float = 0.0
    keep_ratio: float = 0.0
    stage_stats: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_total_ms: float = 0.0
    timestamp: str = ""
    original_bytes: int = 0
    compressed_edges: int = 0
    kb_reuse_edges: int = 0

    @property
    def scr_anchor(self) -> float:
        """SCR (anchor dimension) = original edges / anchor edges.

        Measures semantic compression ratio based on anchor retention.

        Returns:
            SCR value, or 0.0 if compressed_edges is zero.
        """
        if self.compressed_edges == 0:
            return 0.0
        return self.original_edges / self.compressed_edges

    @property
    def scr_info(self) -> float:
        """SCR (information dimension) = original edges / (anchor + KB-reuse).

        Measures semantic compression ratio including KB reuse.

        Returns:
            SCR value, or 0.0 if total is zero.
        """
        total = self.compressed_edges + self.kb_reuse_edges
        if total == 0:
            return 0.0
        return self.original_edges / total

    @property
    def bit_compression_ratio(self) -> float:
        """Bit compression ratio = original bytes / compressed bytes.

        Returns:
            Ratio value, or 0.0 if compressed_bytes is zero.
        """
        if self.compressed_bytes == 0:
            return 0.0
        return self.original_bytes / self.compressed_bytes

    def to_text(self) -> str:
        """Format the report as human-readable text.

        Returns:
            Plain-text report string.
        """
        lines = [
            "=" * 60,
            "EML-SemZip Compression Report",
            "=" * 60,
            f"Timestamp: {self.timestamp}",
            f"Original nodes: {self.original_nodes}",
            f"Original edges: {self.original_edges}",
            f"Compressed size: {self.compressed_bytes} bytes",
            f"Original size: {self.original_bytes} bytes",
            f"Theta_dead: {self.theta_dead}",
            f"Keep ratio: {self.keep_ratio}",
            f"Total elapsed: {self.elapsed_total_ms:.2f} ms",
            "",
            "--- Semantic Compression Ratios (SCR) ---",
            f"SCR (anchor dimension): {self.scr_anchor:.2f}x",
            f"SCR (information dimension): {self.scr_info:.2f}x",
            f"Bit compression ratio: {self.bit_compression_ratio:.2f}x",
            "-" * 60,
            "Stage Details:",
        ]
        for stage in self.stage_stats:
            lines.append(
                f"  [{stage.get('stage_name', 'unknown')}] "
                f"in={stage.get('input_count', 0)} "
                f"out={stage.get('output_count', 0)} "
                f"{stage.get('elapsed_ms', 0.0):.2f} ms"
            )
            details = stage.get("details", {})
            for k, v in details.items():
                lines.append(f"    {k}: {v}")
        lines.append("=" * 60)
        return "\n".join(lines)

    def to_json(self) -> str:
        """Format the report as JSON.

        Returns:
            JSON string of the report.
        """
        return json.dumps(
            {
                "original_nodes": self.original_nodes,
                "original_edges": self.original_edges,
                "compressed_bytes": self.compressed_bytes,
                "original_bytes": self.original_bytes,
                "theta_dead": self.theta_dead,
                "keep_ratio": self.keep_ratio,
                "scr_anchor": round(self.scr_anchor, 4),
                "scr_info": round(self.scr_info, 4),
                "bit_compression_ratio": round(self.bit_compression_ratio, 4),
                "stage_stats": self.stage_stats,
                "elapsed_total_ms": self.elapsed_total_ms,
                "timestamp": self.timestamp,
            },
            ensure_ascii=False,
            indent=2,
        )
