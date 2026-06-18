"""Pipeline subpackage: compression stages, Compressor, Decompressor, incremental compression."""

from .stages import (
    StageStats,
    stage1_dead_zero_prune,
    stage2_isomorphism_merge,
    stage3_mao_rui_weighting,
    stage4_ksnap_selection,
    stage5_ans_encode,
)
from .compressor import Compressor
from .decompressor import Decompressor
from .incremental import (
    HypergraphDelta,
    compute_delta,
    apply_delta,
    compress_incremental,
    decompress_incremental,
)

__all__ = [
    "StageStats",
    "stage1_dead_zero_prune",
    "stage2_isomorphism_merge",
    "stage3_mao_rui_weighting",
    "stage4_ksnap_selection",
    "stage5_ans_encode",
    "Compressor",
    "Decompressor",
    "HypergraphDelta",
    "compute_delta",
    "apply_delta",
    "compress_incremental",
    "decompress_incremental",
]
