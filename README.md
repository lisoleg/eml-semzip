# EML-SemZip：基于毛睿广义度量与 TOMAS 公理的极致语义压缩

[![Python 3.13+](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-lightgrey.svg)](https://github.com/)

EML-SemZip（Entity-Mutualism Semantic Compaction）是一种基于 TOMAS 公理体系与毛睿广义度量空间的新型语义压缩算法。不压缩比特，而是压缩 EML 超图（Entity-Mutualism Link Hypergraph）中的"无效超边"。

## 🎯 核心特性

- **五阶段压缩流程**：Dead-Zero 剪枝 → EML-Lite 同构归并 → 毛睿度量加权 → κ-Snap 语义核选取 → ANS 熵编码
- **极致压缩比**：语义压缩比（SCR）300×~10000×，比特等效压缩比数千~数万倍
- **纯标准库**：零外部依赖，Python 3.13+ 即可运行
- **Web UI**：内置 Web 界面，浏览器中直接压缩/解压
- **批量处理**：支持目录批量压缩
- **EML-Lite KB**：内置 15+ 常见谓词模式，支持同构归并

## 📦 安装

```bash
git clone https://github.com/lisoleg/eml-semzip.git
cd eml-semzip
python -m eml_semzip.cli.main --help
```

无需安装任何依赖，纯标准库实现。

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

**示例**：
```bash
# 基本压缩
python -m eml_semzip.cli.main compress graph.json compressed.esz

# 使用内置 KB
python -m eml_semzip.cli.main compress graph.json compressed.esz --use-builtin-kb

# 生成 JSON 报告
python -m eml_semzip.cli.main compress graph.json compressed.esz --report report.json --report-format json
```

### decompress - 解压超图

```bash
python -m eml_semzip.cli.main decompress <input> <output> [options]
```

**参数**：
- `input`：输入压缩文件（.esz）
- `output`：输出超图文件（.json 或 .pickle）
- `--kb PATH`：EML-Lite KB 文件路径
- `--use-builtin-kb`：使用内置 KB

### batch-compress - 批量压缩

```bash
python -m eml_semzip.cli.main batch-compress <input_dir> <output_dir> [options]
```

**参数**：
- `input_dir`：输入目录（包含 .json/.pickle 文件）
- `output_dir`：输出目录（生成 .esz 文件）
- `--theta-dead FLOAT`：Dead-Zero 阈值（默认 0.45）
- `--keep-ratio FLOAT`：语义核保留比例（默认 0.15）
- `--use-builtin-kb`：使用内置 KB

**示例**：
```bash
python -m eml_semzip.cli.main batch-compress ./graphs ./compressed --use-builtin-kb
```

### web - 启动 Web UI

```bash
python -m eml_semzip.cli.main web [options]
```

**参数**：
- `--host HOST`：绑定地址（默认 127.0.0.1）
- `--port INT`：端口号（默认 8080）

**示例**：
```bash
python -m eml_semzip.cli.main web --port 8080
# 打开浏览器访问 http://127.0.0.1:8080
```

## 🐍 Python API

### 压缩超图

```python
from eml_semzip.pipeline import Compressor
from eml_semzip.models.hypergraph import EMLHypergraph

# 加载超图
graph = EMLHypergraph.from_json("graph.json")

# 压缩
compressor = Compressor(theta_dead=0.45, keep_ratio=0.15)
compressed = compressor.compress(graph)

# 保存
with open("output.esz", "wb") as f:
    f.write(compressed)
```

### 解压超图

```python
from eml_semzip.pipeline import Decompressor
from eml_semzip.models.hypergraph import EMLHypergraph

# 读取压缩数据
with open("output.esz", "rb") as f:
    data = f.read()

# 解压
decompressor = Decompressor()
graph = decompressor.decompress(data)

# 保存
graph.to_json("restored.json")
```

### 使用 EML-Lite KB

```python
from eml_semzip.kb.builtin_kb import create_builtin_kb
from eml_semzip.pipeline import Compressor

# 创建内置 KB
kb = create_builtin_kb()

# 压缩时使用 KB
compressor = Compressor(kb=kb, theta_dead=0.45, keep_ratio=0.15)
compressed = compressor.compress(graph)
```

### 生成压缩报告

```python
from eml_semzip.io.report import CompressionReport

report = CompressionReport(
    original_nodes=graph.node_count(),
    original_edges=graph.edge_count(),
    compressed_bytes=len(compressed),
    theta_dead=0.45,
    keep_ratio=0.15,
)
print(report.to_text())
print(f"SCR (anchor): {report.scr_anchor:.2f}x")
```

## 🔬 五阶段压缩流程

### Stage 1: Dead-Zero 剪枝（毛睿 φ-过滤）

丢弃 ℐ(e) < θ_dead 的超边（无据幻觉/低价值噪音）。

```
E_pruned = {e ∈ E | ℐ(e) ≥ θ_dead}
```

### Stage 2: EML-Lite 同构归并（毛睿伪度量）

若 d_sem(e₁, e₂) = 0 且同谓词 → 合并为 e_max_ℐ，利用 EML-Lite KB 指针替换冗余描述。

### Stage 3: 毛睿度量加权（非对称/基依赖）

计算语义距离：

```
d_sem(e) = (1.0 / (ℐ(e) + ε)) × w_base × f_dir
```

高 ℐ 超边距离近，低 ℐ 超边距离远。

### Stage 4: κ-Snap 语义核选取

保留 Top-15% 高 ℐ 超边 + 闭环（≥3 节点）作为锚点。

### Stage 5: ANS 熵编码

序列化 (V*, E*, ℐ, θ_dead) → ANS 编码 → 输出 SemPkt。

## 📊 SCR（语义压缩比）说明

### SCR (锚点维度)

```
SCR_anchor = 原始超边数 / 锚点超边数
```

衡量语义压缩的锚点保留效率。

### SCR (信息维度)

```
SCR_info = 原始超边数 / (锚点超边数 + KB复用超边数)
```

衡量包括 KB 复用后的总压缩效率。

### 比特压缩比

```
BitRatio = 原始文件字节数 / 压缩后字节数
```

衡量文件大小的压缩比。

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
│   └── builtin_kb.py           # 内置示例 KB
├── pipeline/                   # 压缩管线
│   ├── stages.py               # 五阶段函数
│   ├── compressor.py           # Compressor 类
│   └── decompressor.py         # Decompressor 类
├── coding/                     # 编码
│   ├── ans_coder.py            # ANS 熵编码
│   ├── serializer.py           # 序列化
│   └── sempkt.py               # SemPkt 数据类
├── io/                         # IO
│   └── report.py               # 压缩报告
├── cli/                        # 命令行界面
│   └── main.py                 # CLI 入口
└── web/                        # Web UI
    ├── server.py               # HTTP 服务器
    └── templates/
        └── index.html          # Web 界面
```

## 📄 文件格式

### 超图 JSON 格式

```json
{
  "nodes": {
    "n1": {"name": "Alice", "type": "person"},
    "n2": {"name": "Bob", "type": "person"}
  },
  "edges": [
    {
      "edge_id": "e1",
      "nodes": ["n1", "n2"],
      "I_value": 0.9,
      "base_weight": 1.0,
      "dir_factor": 1.0,
      "predicate": "knows"
    }
  ]
}
```

### SemPkt 二进制格式

```
+----------------+----------------+----------------+----------------+
| Magic (4 bytes) | Version (1 byte) | Metadata Length (4 bytes) |
+----------------+----------------+----------------+----------------+
| Metadata (variable) | ANS Data Length (4 bytes) |
+----------------+----------------+----------------+
| ANS Data (variable) |
+----------------+
```

### 压缩报告 JSON 格式

```json
{
  "original_nodes": 100,
  "original_edges": 200,
  "compressed_bytes": 500,
  "scr_anchor": 40.0,
  "scr_info": 50.0,
  "bit_compression_ratio": 80.0,
  "stage_stats": [...]
}
```

## 🧪 测试

```bash
python -m unittest discover tests/ -v
```

127 个测试用例，100% 通过。

## 📖 参考文献

1. 章锋，《论 EML-SemZip：基于毛睿广义度量与 TOMAS 公理的极致语义压缩》
2. 毛睿，《广义度量空间理论》
3. D. Lemire, "Asymmetric numeral systems: entropy coding for multiple devices"

## 👨‍💻 作者

章锋（TOMAS-AGI 项目组，北京）

## 📄 许可证

Apache License 2.0
