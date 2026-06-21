# Changelog

All notable changes to EML-SemZip are documented here.

## [Unreleased]

### Planned
- T-Core ASIC tape-out (TSMC 5nm, target Q4 2026)
- W3C EML hypergraph JSON standardization
- Real KG (DBpedia/Wikidata) full-scale evaluation

---

## [v2.2] - 2026-06-19

### Added
- **CLIP Encoder** (`multimodal/clip_encoder.py`): OpenAI CLIP-ViT-B/32 integration for patch-level semantic embedding extraction; cosine-similarity hyperedge construction; `compute_fidelity_score()` for semantic fidelity evaluation
- **ViT Encoder** (`multimodal/vit_encoder.py`): Google ViT-B/16 integration with attention-based connectivity; multi-head attention hyperedge builder
- **Real KG Evaluation Script** (`benchmarks/bench_real_kg.py`): Compares semantic vs. random knowledge graph compression; reports SCR, per-stage contribution, baseline comparison
- **KB Auto-Learning Evaluation Script** (`benchmarks/bench_kb_learning.py`): Progressive KG pattern coverage evaluation; reports pattern coverage rate, novelty rate, KB growth curve, compression improvement

### Changed
- Paper (`docs/paper.md`, `eml_semzip/docs/paper.md`): Marked CLIP/ViT enhancement, real KG eval, and KB learning eval as implemented (moved from Future Work to Implemented)
- README.md: Added v2.2 section, updated version badge to v2.2
- `eml_semzip/README.md`: Added v2.2 features, updated optional dependencies (`transformers`, `accelerate`)

### Fixed
- English paper (`eml_semzip/docs/paper.md`): Corrected duplicate "#4" numbering in Future Work section; updated Stage 4 description to reflect BFS optimization

### Dependencies
- Optional: `pip install transformers accelerate` (for CLIP/ViT encoders)

---

## [v2.1] - 2026-06-19

### Added
- **KB Auto-Learning** (`kb/auto_learning.py`): `KBAutoLearner` class for frequent predicate pattern mining from unlabeled hypergraphs; incremental `EMLLiteKB` updates
- **Differentiable Compression** (`pipeline/diff_compressor.py`): `DiffCompressor` with PyTorch-based gradient flow through compression cost (cross-entropy loss); supports end-to-end optimization of compression ratio
- **BFS-Optimized κ-Snap** (`pipeline/stages.py`, `utils/cycle_detection.py`): Replaced O(|E|³) DFS cycle detection with O(|E|·d_avg) BFS node-expansion; stage4 now handles 2000-edge hypergraphs in <2ms

### Changed
- Paper: Updated Section 7.2 with real experimental data (Tiny/Small/Medium datasets); updated Section 8.3 Future Work to mark implemented features
- README.md / `eml_semzip/README.md`: Updated to v2.1 with new feature sections and real experiment data tables
- `utils/cycle_detection.py`: Added 5-second timeout to `find_closed_cycles()` as safety fallback

### Fixed
- Stage 4 performance: Eliminated combinatorial explosion that caused hangs on |E| > 500
- Paper: Replaced all `*pending*` placeholders with real benchmark data
- `eml_semzip/docs/paper.md`: Fixed Stage 4 complexity description (was incorrectly stating O(|E|³) bottleneck still existed)

### Experimental Data
| Dataset | JSON Size | EML-SemZip | gzip | bzip2 |
|---------|-----------|-------------|-------|--------|
| Tiny (20N, 30E) | 5,982B | 3,109B / 1.92× | 576B / 10.39× | 559B / 10.70× |
| Small (200N, 500E) | 93,887B | 42,827B / 2.19× | 6,786B / 13.84× | 4,401B / 21.33× |
| Medium (500N, 2000E) | 358,899B | 172,117B / 2.09× | 25,947B / 13.83× | 16,517B / 21.73× |

---

## [v2.0] - 2026-06-18

### Added
- **Incremental Compression** (`pipeline/incremental.py`): `compress_incremental()` / `decompress_incremental()`; delta-based re-compression with zlib fallback
- **Distributed Compression** (`pipeline/distributed.py`): Multiprocessing parallel compression with automatic graph partitioning
- **Multi-Modal Extension** (`multimodal/__init__.py`): `image_to_hypergraph()` (patch features) and `audio_to_hypergraph()` (spectrogram features)
- **T-Core ASIC Design** (`docs/TCORE_ASIC_DESIGN.md`): RTL design with 64 parallel PEs; estimated 26.3× speedup vs. Intel i7-13700K
- **Web UI Enhancement**: D3.js force-directed visualization; real-time node/hyperedge editing
- **CLI Enhancement**: `incremental-compress` / `incremental-decompress` / `image-to-graph` / `audio-to-graph` commands

### Changed
- Paper: Expanded to 691 lines with T-Core ASIC section; upgraded to top-journal standard
- `eml_lite_kb.py`: Added 5 new built-in patterns (total 15)

### Dependencies
- Optional: `pip install Pillow` (for multi-modal image support)
- Optional: `pip install torch` (for future differentiable compression)

---

## [v1.0] - 2026-06-18

### Added
- **5-Stage Compression Pipeline** (`pipeline/stages.py`):
  1. Dead-Zero Pruning (θ_dead filter)
  2. EML-Lite Isomorphism Merge (KB pattern matching)
  3. Mao-Rui Metric Weighting (asymmetric semantic distance)
  4. κ-Snap Semantic Core Selection (DFS cycle detection, later optimized in v2.1)
  5. rANS Entropy Coding
- **EML-Lite KB** (`kb/eml_lite_kb.py`, `kb/builtin_kb.py`): 10 built-in predicate patterns (expanded to 15 in v2.0)
- **CLI Tool** (`cli/main.py`): `compress` / `decompress` / `batch-compress` / `info` / `web` commands
- **Web UI** (`web/server.py`, `web/templates/index.html`): Upload/download, online compress/decompress, SCR real-time display
- **rANS Coder** (`coding/ans_coder.py`): Symmetric rANS encoder/decoder
- **SemPkt Format** (`coding/sempkt.py`): Binary packet format with anchor nodes/edges, info-encoded deltas, and rANS stream
- **Test Suite** (`tests/`): 127 test cases, 100% pass rate

### Technical Details
- Pure standard library implementation (zero external dependencies for core functionality)
- Python 3.13+ required
- Compression report with SCR (Semantic Compression Ratio) calculation
- Support for JSON/LIST/DICT/EMC input formats

---

## Version Numbering

- **v1.x**: Core algorithm and basic functionality
- **v2.x**: Advanced features (incremental, distributed, multi-modal, ASIC)
- **v3.x** (planned): Real KG integration, T-Core tape-out, W3C standardization

---

**Maintainers**: 章锋¹, 李宗海²  
**Contact**: [GitHub Issues](https://github.com/lisoleg/eml-semzip/issues)
