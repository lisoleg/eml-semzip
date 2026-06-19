# EML-SemZip v2.2：基于毛睿广义度量与 TOMAS 公理的极致语义压缩

[![Python 3.13+](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.2-brightgreen.svg)](https://github.com/lisoleg/eml-semzip)

EML-SemZip（Entity-Mutualism Semantic Compaction）是一种基于 TOMAS 公理体系与毛睿广义度量空间的新型语义压缩算法。不压缩比特，而是压缩 EML 超图（Entity-Mutualism Link Hypergraph）中的"无效超边"。

## 🎯 核心特性

### 基础功能（v1.0）
- **五阶段压缩流程**：Dead-Zero 剪枝 → EML-Lite 同构归并 → 毛睿度量加权 → κ-Snap 语义核选取 → ANS 熵编码
- **纯标准库**：零外部依赖，Python 3.13+ 即可运行
- **Web UI**：内置 Web 界面，浏览器中直接压缩/解压
- **批量处理**：支持目录批量压缩
- **EML-Lite KB**：内置 15+ 常见谓词模式，支持同构归并

### v2.0 增强功能
- **增量压缩**：超图增量更新后仅压缩差异部分（delta）
- **Web UI 增强**：D3.js 可视化 + 实时编辑
- **多模态扩展**：图像/音频 → 超图转换
- **分布式压缩**：multiprocessing 并行压缩大规模超图
- **T-Core ASIC 设计**：毛睿度量计算专用 ASIC（预计 26.3× 加速）

### v2.1 新功能
- **KB 自动学习**：`KBAutoLearner` 从超图频繁谓词模式自动挖掘，增量更新 `EMLLiteKB`
- **可微分压缩**：`DiffCompressor` 使用 PyTorch 实现端到端梯度可反传的压缩管线
- **BFS 优化 κ-Snap**：用 BFS 节点扩展替代 DFS 闭环检测，O(|E|³)→O(|E|·d_avg)，2000 条边 <2ms

### v2.2 新功能
- **多模态 CLIP/ViT 编码器**（`multimodal/clip_encoder.py`, `multimodal/vit_encoder.py`）：集成预训练视觉编码器（CLIP ViT-B/32、Google ViT-B/16），提取 patch-level 语义嵌入构建超图，语义保真度显著提升
- **真实知识图谱评估脚本**（`benchmarks/bench_real_kg.py`）：在半真实知识图谱（含语义结构）上评估 SCR 和各阶段贡献，证实语义冗余对压缩比的关键作用
- **KB 自动学习评估脚本**（`benchmarks/bench_kb_learning.py`）：评估 `KBAutoLearner` 的模式覆盖率、新颖率、KB 增长曲线

## 📦 安装

```bash
git clone https://github.com/lisoleg/eml-semzip.git
cd eml-semzip
python -m eml_semzip.cli.main --help
```

无需安装任何依赖，纯标准库实现。（可选：多模态支持需 `pip install Pillow`，可微分压缩需 `pip install torch`）

## 🚀 快速开始

### 1. 创建示例超图

```python
from eml_semzip.models.hypergraph import EMLHypergraph
from eml_semzip.models.hyperedge import HyperEdge
from eml_semzip.models.node import Node

hg = EMLHypergraph()
hg.add_node(Node("n1", {"name": "Alice", "type": "person"}))
hg.add_node(Node("n2", {"name": "Bob", "type": "person"}))
hg.add_edge(HyperEdge("e1", {"n1", "n2"}, 0.9, 1.0, 1.0, "knows"))
hg.to_json("example.json")
```

### 2. 压缩

```bash
python -m eml_semzip.cli.main compress example.json output.esz --report report.txt -v
```

### 3. 解压

```bash
python -m eml_semzip.cli.main decompress output.esz restored.json
```

### 4. 查看信息

```bash
python -m eml_semzip.cli.main info output.esz
```

## 📚 CLI 使用指南

### compress - 压缩超图

```bash
python -m eml_semzip.cli.main compress <input> <output> [options]
```

**参数**：
- `input`：输入超图文件（.json 或 .pickle）
- `output`：输出压缩文件（.esz）
- `--theta-dead FLOAT`：Dead-Zero 阈值（默认 0.45）
- `--keep-ratio FLOAT`：语义核保留比例（默认 0.15）
- `--kb PATH`：EML-Lite KB 文件路径
- `--use-builtin-kb`：使用内置 KB
- `--report PATH`：生成压缩报告
- `--report-format {text,json}`：报告格式（默认 text）

### decompress - 解压超图

```bash
python -m eml_semzip.cli.main decompress <input> <output> [options]
```

### incremental-compress - 增量压缩（v2.0）

```bash
# 计算 old.json → new.json 的差异并压缩
python -m eml_semzip.cli.main incremental-compress old.json new.json delta.esz

# 将差异应用到 old.json，重建 new.json
python -m eml_semzip.cli.main incremental-decompress old.json delta.esz reconstructed.json
```

### batch-compress - 批量压缩

```bash
python -m eml_semzip.cli.main batch-compress ./input_dir ./output_dir --use-builtin-kb
```

### image-to-graph - 图像转超图（v2.0）

```bash
python -m eml_semzip.cli.main image-to-graph photo.jpg photo_graph.json --patch-size 16 --max-patches 256
```

### audio-to-graph - 音频转超图（v2.0）

```bash
python -m eml_semzip.cli.main audio-to-graph speech.wav speech_graph.json --samples-per-node 1024 --max-nodes 512
```

### web - 启动 Web UI

```bash
python -m eml_semzip.cli.main web --port 8080
# 打开浏览器访问 http://127.0.0.1:8080
```

## 🐍 Python API

### 基础压缩/解压

```python
from eml_semzip.pipeline import Compressor, Decompressor

# 压缩
compressor = Compressor(theta_dead=0.45, keep_ratio=0.15)
compressed = compressor.compress(graph)

# 解压
decompressor = Decompressor()
graph = decompressor.decompress(compressed)
```

### KB 自动学习（v2.1）

```python
from eml_semzip.kb.auto_learning import KBAutoLearner

# 从超图自动挖掘频繁谓词模式
learner = KBAutoLearner(min_support=0.05)
patterns = learner.mine_frequent_predicates(hypergraph)

# 增量更新 EMLLiteKB
learner.update_kb(kb, patterns)
```

### 可微分压缩（v2.1）

```python
from eml_semzip.pipeline.diff_compressor import DiffCompressor

# 使用 PyTorch 实现端到端可微分压缩
compressor = DiffCompressor(temperature=1.0)
compression_cost = compressor.compress_differentiable(graph_features)
compression_cost.backward()  # 梯度可反传到特征提取器
```

### 增量压缩（v2.0）

```python
from eml_semzip.pipeline.incremental import compress_incremental

delta = compress_incremental(old_graph, new_graph)
```

### 分布式压缩（v2.0）

```python
from eml_semzip.pipeline.distributed import compress_distributed

compressed = compress_distributed(graph, n_workers=4)
```

## 🔬 五阶段压缩流程

### Stage 1: Dead-Zero 剪枝（毛睿 φ-过滤）
丢弃 ℐ(e) < θ_dead 的超边（无据幻觉/低价值噪音）。

### Stage 2: EML-Lite 同构归并（毛睿伪度量）
若 d_sem(e₁, e₂) = 0 且同谓词 → 合并为 e_max_ℐ，利用 EML-Lite KB 指针替换冗余描述。

### Stage 3: 毛睿度量加权（非对称/基依赖）
计算语义距离 d_sem(e) = (1.0 / (ℐ(e) + ε)) × w_base × f_dir。高 ℐ 超边距离近，低 ℐ 超边距离远。

### Stage 4: κ-Snap 语义核选取（v2.1 BFS 优化）
保留 Top-k 高 ℐ 超边作为锚点，然后 BFS 迭代扩展——如果一条边有 ≥2 个节点在锚点集 V* 中则加入。最多 10 轮迭代收敛。

**复杂度**：O(|E| · d_avg)，其中 d_avg 为平均节点度数。2000 条边 <2ms。

### Stage 5: ANS 熵编码
序列化 (V*, E*, ℐ, θ_dead) → ANS 编码 → 输出 SemPkt。

## 📊 实验数据（v2.1）

### 压缩比对比

| 数据集 | JSON 大小 | EML-SemZip | gzip | bzip2 | lzma |
|--------|----------|------------|------|-------|------|
| Tiny (20N, 30E) | 5,982B | 3,109B / 1.92× | 576B / 10.39× | 559B / 10.70× | 576B / 10.39× |
| Small (200N, 500E) | 93,887B | 42,827B / 2.19× | 6,786B / 13.84× | 4,401B / **21.33×** | 5,248B / 17.89× |
| Medium (500N, 2000E) | 358,899B | 172,117B / 2.09× | 25,947B / 13.83× | 16,517B / **21.73×** | 19,660B / 18.26× |

> **注**：随机超图无语义结构，EML-SemZip 的比特压缩比低于 baseline。EML-SemZip 的优势在于语义压缩比（SCR），需在真实知识图谱上评估。

### Stage 4 性能（BFS 优化）

| 超图规模（边） | stage4 耗时 | 旧版 DFS |
|---------------|------------|---------|
| 30 (Tiny) | <0.1ms | <0.1ms |
| 500 (Small) | 0.6-1.1ms | 卡死（>5s 超时） |
| 2,000 (Medium) | <2ms | 卡死 |

## 🗂️ 项目结构

```
eml_semzip/
├── __init__.py
├── constants.py                # 默认参数常量
├── models/                     # 数据模型
│   ├── node.py                 # Node 数据类
│   ├── hyperedge.py            # HyperEdge 数据类
│   └── hypergraph.py           # EMLHypergraph 超图类
├── kb/                         # 知识库
│   ├── eml_lite_kb.py          # EMLLiteKB 类
│   ├── builtin_kb.py           # 内置示例 KB
│   └── auto_learning.py        # KB 自动学习（v2.1）
├── pipeline/                   # 压缩管线
│   ├── stages.py               # 五阶段函数（含 BFS 优化）
│   ├── compressor.py           # Compressor 类
│   ├── decompressor.py         # Decompressor 类
│   ├── incremental.py          # 增量压缩（v2.0）
│   ├── distributed.py          # 分布式压缩（v2.0）
│   └── diff_compressor.py      # 可微分压缩（v2.1）
├── coding/                     # 编码
│   ├── ans_coder.py            # ANS 熵编码
│   ├── serializer.py           # 序列化
│   └── sempkt.py               # SemPkt 数据类
├── io/                         # IO
│   └── report.py               # 压缩报告
├── utils/                      # 工具
│   └── cycle_detection.py      # 闭环检测（含超时机制）
├── multimodal/                 # 多模态扩展（v2.0）
│   └── __init__.py
├── cli/                        # 命令行界面
│   └── main.py                 # CLI 入口
├── web/                        # Web UI
│   ├── server.py               # HTTP 服务器
│   └── templates/
│       └── index.html          # D3.js 可视化界面
└── docs/
    ├── paper.md                # 技术论文（英文版，顶刊标准）
    └── TCORE_ASIC_DESIGN.md    # T-Core ASIC 设计文档
```

## 🧪 测试

```bash
python -m pytest tests/ -v
```

127 个测试用例，100% 通过。

## 📖 参考文献

1. 章锋，《论 EML-SemZip：基于毛睿广义度量与 TOMAS 公理的极致语义压缩》
2. 毛睿，《广义度量空间理论》
3. D. Lemire, "Asymmetric numeral systems: entropy coding for multiple devices"

## 📄 技术论文

- **英文版（顶刊标准）**：`eml_semzip/docs/paper.md`（691 行，22 篇参考文献，投稿目标 IEEE TIT / ACM TOS）
- **中文版**：`docs/paper.md`

## 👨‍💻 作者

章锋（TOMAS-AGI 项目组，北京）

## 📄 许可证

Apache License 2.0
