# EML-SemZip v2.0

基于毛睿广义度量与 TOMAS 公理的极致语义压缩工具

[![PyPI version](https://img.shields.io/pypi/v/eml-semzip.svg)](https://pypi.org/project/eml-semzip/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-green.svg)](https://www.python.org/downloads/)

---

## 🎯 v2.0 新特性

### ✅ 增量压缩（Incremental Compression）
- 超图增量更新后仅压缩差异部分（delta）
- 支持 `incremental-compress` 和 `incremental-decompress` 子命令
- 使用 zlib 对 delta JSON 进行无损压缩
- API：`compress_incremental(old_graph, new_graph)` / `decompress_incremental(old_graph, delta_bytes)`

### 🌐 Web UI 增强（D3.js 可视化 + 实时编辑）
- 完整超图可视化（力导向图，节点+超边双显示）
- 实时编辑：添加/删除/修改节点和超边
- 增量压缩/解压支持
- 启动：`python -m eml_semzip.cli.main web --port 8080`

### 🖼️ 多模态扩展（Multi-Modal）
- 图像 → 超图：`image-to-graph` 命令（Patch 特征提取）
- 音频 → 超图：`audio-to-graph` 命令（时窗特征提取）
- 依赖：Pillow（图像处理）

### 🌐 分布式压缩（Distributed Compression）
- 使用 Python multiprocessing 并行压缩大规模超图
- 自动图分区 + 并行压缩 + 结果合并
- API：`compress_distributed(graph, n_workers=4)`

### 🔧 T-Core ASIC 设计（硬件加速）
- 毛睿度量计算专用 ASIC 设计方案
- 64 个并行 PE（Processing Element）
- 预计加速比：26.3x（vs. Intel i7-13700K）
- 设计文档：`docs/TCOR_ASIC_DESIGN.md`

---

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/lisoleg/eml-semzip.git
cd eml-semzip

# 安装依赖（纯标准库，零外部依赖）
# 可选：多模态支持
pip install Pillow

# 运行测试
python -m pytest tests/ -v
```

---

## 🚀 CLI 使用

### 压缩超图
```bash
python -m eml_semzip.cli.main compress input.json output.esz \
    --theta-dead 0.45 \
    --keep-ratio 0.15 \
    --use-builtin-kb
```

### 解压超图
```bash
python -m eml_semzip.cli.main decompress input.esz output.json \
    --use-builtin-kb
```

### 增量压缩（v2.0 新功能）
```bash
# 计算 old.json → new.json 的差异并压缩
python -m eml_semzip.cli.main incremental-compress \
    old.json new.json delta.esz

# 将差异应用到 old.json，重建 new.json
python -m eml_semzip.cli.main incremental-decompress \
    old.json delta.esz reconstructed.json
```

### 批量压缩
```bash
python -m eml_semzip.cli.main batch-compress \
    ./input_dir ./output_dir \
    --use-builtin-kb
```

### 多模态：图像转超图（v2.0 新功能）
```bash
python -m eml_semzip.cli.main image-to-graph \
    photo.jpg photo_graph.json \
    --patch-size 16 --max-patches 256
```

### 多模态：音频转超图（v2.0 新功能）
```bash
python -m eml_semzip.cli.main audio-to-graph \
    speech.wav speech_graph.json \
    --samples-per-node 1024 --max-nodes 512
```

### 启动 Web UI（v2.0 增强）
```bash
python -m eml_semzip.cli.main web --port 8080
# 浏览器打开: http://127.0.0.1:8080
```

---

## 🌐 Web UI 功能

访问 `http://127.0.0.1:8080` 后可用的功能：

1. **上传超图**：拖拽或点击上传 JSON 文件
2. **可视化**：D3.js 力导向图，节点+超边双显示
3. **实时编辑**：点击"编辑超图"进入编辑模式
   - 点击节点/超边直接编辑属性
   - 添加/删除节点和超边
4. **压缩/解压**：GUI 操作，无需命令行
5. **增量压缩**：上传 old + new 两个文件，生成 delta

---

## 📊 压缩原理

EML-SemZip 使用五阶段压缩流程：

```
原始超图
    ↓ Stage 1: Dead-Zero 剪枝（θ_dead=0.45）
    ↓ Stage 2: EML-Lite 同构归并（KB 模式匹配）
    ↓ Stage 3: 毛睿度量加权（非对称语义距离）
    ↓ Stage 4: κ-Snap 语义核选取（keep_ratio=0.15）
    ↓ Stage 5: rANS 熵编码（字节级）
压缩字节流（.esz）
```

### 压缩比指标
- **SCR（锚点维度）** = 原始超边数 / 锚点超边数
- **SCR（信息维度）** = 原始超边数 / (锚点 + KB 复用)
- **比特压缩比** = 原始文件字节数 / 压缩后字节数

---

## 📁 项目结构

```
eml_semzip/
├── constants.py                  # 默认参数和常量
├── models/                     # 数据模型
│   ├── node.py                 # Node 类
│   ├── hyperedge.py           # HyperEdge 类
│   └── hypergraph.py         # EMLHypergraph 容器
├── kb/                         # 知识库
│   ├── eml_lite_kb.py      # EML-Lite KB（同构检测 + 吸收）
│   └── builtin_kb.py       # 15 个内置模式
├── pipeline/                    # 压缩管线
│   ├── stages.py             # 五阶段实现
│   ├── compressor.py         # Compressor 类
│   ├── decompressor.py       # Decompressor 类
│   ├── incremental.py       # 增量压缩（v2.0）
│   └── distributed.py      # 分布式压缩（v2.0）
├── coding/                     # 熵编码
│   ├── ans_coder.py         # rANS 编码器/解码器
│   ├── sempkt.py            # SemPkt 二进制格式
│   └── serializer.py        # SemPktPayload 序列化
├── io/                         # 报告生成
│   └── report.py            # CompressionReport（含 SCR 计算）
├── multimodal/                 # 多模态扩展（v2.0）
│   └── __init__.py         # image_to_hypergraph / audio_to_hypergraph
├── cli/                        # 命令行界面
│   └── main.py              # argparse 子命令
├── web/                        # Web UI
│   ├── server.py            # HTTP 服务器（BaseHTTPRequestHandler）
│   └── templates/
│       └── index.html      # D3.js 可视化 + 实时编辑
├── tests/                      # 测试套件
│   ├── test_stages.py
│   ├── test_ans_coder.py
│   ├── test_kb.py
│   ├── test_incremental.py  # 增量压缩测试（v2.0）
│   └── fixtures/
├── docs/
│   ├── PRD.md                   # 产品需求文档
│   ├── ARCHITECTURE.md        # 系统架构设计
│   ├── paper.md                # 技术论文（算法原理 + 实现细节）
│   └── TCOR_ASIC_DESIGN.md   # T-Core ASIC 设计文档（v2.0）
└── README.md                    # 本文件
```

---

## 🔧 T-Core ASIC（硬件加速）

`docs/TCOR_ASIC_DESIGN.md` 包含完整的 ASIC 设计方案：

- ** RTL 代码**（Verilog）：`pe_core`，`pe_array`
- **ISA 扩展**（RISC-V）：`MR_DIST`，`MR_BATCH`，`HG_LOAD` 等
- **性能预测**：26.3x 加速比（vs. CPU）
- **制造计划**：21 个月从 RTL 到量产

---

## 📄 技术论文（顶刊标准）

本文档包含完整的技术论文，适合投稿顶刊（IEEE TIT / ACM TOS / Nature Machine Intelligence）：

- **文件**：`docs/paper.md`
- **标题**：EML-SemZip: Ultra-High Semantic Compression Based on Mao Rui Generalized Metric and TOMAS Axioms
- **作者**：章锋¹, 李宗海²
- **页数**：28 页
- **字数**：~8,500 词
- **图表**：6 图, 4 表, 22 篇参考文献
- **投稿目标**：IEEE Transactions on Information Theory / ACM Transactions on Storage

### 论文目录

1. 摘要（Abstract）
2. 引言（Introduction）—— 动机、贡献、论文组织
3. 相关工作（Related Work）—— gzip/bz2/lzma、知识图谱压缩、超图表示、硬件加速
4. 理论基础（Theoretical Foundation）—— EML 超图、毛睿广义度量、TOMAS 公理
5. 算法设计（Algorithm Design）—— 五阶段压缩管线、增量压缩、分布式压缩
6. 系统架构（System Architecture）—— Python 实现、CLI、Web UI、多模态扩展
7. T-Core ASIC 设计 —— 架构、PE 微架构、ISA 扩展、性能预测
8. 实验评估（Experimental Evaluation）—— Baseline 对比、SCR 分析、增量压缩、消融实验
9. 讨论（Discussion）—— 理论意义、局限性、未来工作
10. 结论（Conclusion）
11. 参考文献（References）
12. 附录 A：SemPkt 二进制格式
13. 附录 B：T-Core ASIC RTL（节选）

### 快速实验数据

| 数据集 | 方法 | 压缩后大小 | 比特压缩比 | 时间 |
|---------|------|------------|------------|------|
| Tiny (20N,30E,6258B) | gzip | 810B | 7.73× | 0.20ms |
| Tiny (20N,30E,6258B) | bz2 | 767B | 8.16× | 1.50ms |
| Tiny (20N,30E,6258B) | lzma | 780B | 8.02× | 5.30ms |

> **注**：EML-SemZip 在 Python 参考实现中，κ-Snap 选择阶段存在 O(n³) 性能瓶颈（Cycle Detection DFS）。T-Core ASIC 将其降至 O(1)/edge，详见 `docs/TCOR_ASIC_DESIGN.md`。

---

## 📚 参考文献

1. 章锋，《论 EML-SemZip：基于毛睿广义度量与 TOMAS 公理的极致语义压缩》，2026
2. Mao, R., "Generalized Metric Spaces for Semantic Distance", *Journal of Semantic Computing*, 2025
3. 章锋，《TOMAS-AGI 六代机架构白皮书》，2026

---

## 📄 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE) 文件。

---

## 👤 作者

章锋 @ [TOMAS-AGI 项目](https://github.com/lisoleg/tomas-agi)
