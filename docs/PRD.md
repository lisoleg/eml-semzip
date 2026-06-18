# PRD — EML-SemZip 语义压缩解压软件

## 项目信息

| 字段 | 内容 |
|------|------|
| **Language** | 中文（简体） |
| **Programming Language** | Python 3.13 |
| **Project Name** | `eml_semzip` |
| **原始需求复述** | 基于章锋论文《论 EML-SemZip：基于毛睿广义度量与 TOMAS 公理的极致语义压缩》，实现一套语义压缩/解压软件。不压缩比特，而是压缩 EML 超图中的"无效超边"，通过五阶段管线（Dead-Zero 剪枝 → EML-Lite 同构归并 → 毛睿度量加权 → κ-Snap 语义核选取 → ANS 熵编码）实现 300×~10000× 语义压缩比。需同时实现逆向解压管线、EML 超图数据结构、EML-Lite KB 管理与 CLI 界面。 |

---

## 1. 产品目标

### 1.1 一句话定位

EML-SemZip 是一款基于 TOMAS 公理体系与毛睿广义度量空间的**语义级压缩/解压工具**——不压缩比特，而压缩 EML 超图中的无效超边，用最小的语义核还原最大信息量。

### 1.2 核心价值主张

- **极致压缩比**：通过五阶段管线（剪枝 → 归并 → 加权 → 选取 → 编码）剔除冗余超边，语义压缩比(SCR)达 300×~10000×，远超传统比特级压缩。
- **无损语义还原**：解压时基于 κ-锚点 + EML-Lite KB 指针重建完整超图，保证语义信息零丢失。
- **理论可信赖**：每一阶段均有公理支撑（毛睿 φ-过滤、伪度量、ℐ-加权、κ-Snap、ANS 熵编码），流程可解释、参数可审计。

---

## 2. 用户故事

1. **作为太极 OS 项目工程师**，我希望能用 CLI 一条命令将 EML 超图压缩为 `SemPkt` 数据包，以便在带宽受限的链路上传输语义数据。

2. **作为语义数据消费者**，我希望能在对端用解压命令从 `SemPkt` 还原出原始 EML 超图，以便下游系统直接消费完整语义信息而不感知压缩过程。

3. **作为算法调优者**，我希望能调整 `theta_dead`（剪枝阈值）、`keep_ratio`（κ-Snap 保留比例）等参数，以便在不同数据特征下平衡压缩比与还原保真度。

4. **作为知识库管理员**，我希望能加载/管理 EML-Lite KB（同构查找、吸收合并、签名校验），以便压缩时复用已有知识、解压时用 KB 指针重建冗余描述。

5. **作为批量处理用户**，我希望能对一批超图文件批量压缩并输出压缩比统计报告，以便评估管线整体效能。

---

## 3. 需求池（P0 / P1 / P2）

### P0 — 必须实现（Must Have）

| ID | 需求 | 验收标准 |
|----|------|----------|
| P0-1 | **EML 超图数据结构** | 支持 节点(V) + 超边(E) 数据结构；每条超边含 `I_value(ℐ)`、`base_weight`、`dir_factor`、`nodes`、`predicate` 字段；支持从 JSON/Pickle 加载与导出 |
| P0-2 | **五阶段压缩管线** | 完整实现 Dead-Zero 剪枝 → EML-Lite 同构归并 → 毛睿度量加权 → κ-Snap 语义核选取 → ANS 熵编码；输出 `SemPkt`；与论文伪码逻辑一致 |
| P0-3 | **解压（逆向）管线** | 输入 `SemPkt`，经 ANS 解码 → 读取 (V*, E*, ℐ, θ_dead, kb.sig) → 基于 κ-锚点与 EML-Lite KB 指针重建完整超图；还原后超边数/节点数/ℐ 值与压缩前一致（无损语义） |
| P0-4 | **ANS 熵编码/解码** | 实现序列化 `serialize(V*, E*, θ_dead, kb.sig)` → ANS 编码，及对应 ANS 解码 → 反序列化；编解码可逆 |
| P0-5 | **CLI 界面** | 支持 `compress`、`decompress`、`info` 三个子命令；参数见 UI 设计稿 |
| P0-6 | **参数可配置** | `theta_dead`（默认 0.45）、`keep_ratio`（默认 0.15）、`eml_kb_path` 可通过 CLI 参数指定 |

### P1 — 重要实现（Should Have）

| ID | 需求 | 验收标准 |
|----|------|----------|
| P1-1 | **EML-Lite KB 管理** | 支持 `find_isomorphic(e)` 同构查找、`absorb(e)` 合并、`sig` 签名生成与校验；KB 可持久化为文件并加载 |
| P1-2 | **压缩比统计报告** | 输出 SCR(语义压缩比)、比特等效压缩比、各阶段保留/丢弃超边数、κ-锚点数、闭环数等指标；支持文本/JSON 格式 |
| P1-3 | **批量处理** | 支持对目录批量压缩/解压；输出汇总报告 |
| P1-4 | **毛睿度量可审计** | 输出每条保留超边的 `d_sem` 值，支持排序查看，便于调参 |

### P2 — 可选实现（Nice to Have）

| ID | 需求 | 说明 |
|----|------|------|
| P2-1 | **Web UI** | 提供可视化界面上传超图、调参、查看压缩报告与超图拓扑图 |
| P2-2 | **IPv6 扩展头支持** | 将 SemPkt 封装进 IPv6 扩展头传输 |
| P2-3 | **T-Core ASIC 接口预留** | 预留硬件加速接口，供未来 T-Core 芯片加速压缩 |

---

## 4. UI 设计稿（CLI 交互流程）

### 4.1 命令总览

```
eml-semzip <command> [options]

commands:
  compress      压缩 EML 超图为 SemPkt
  decompress    解压 SemPkt 还原 EML 超图
  info          查看 SemPkt / 超图文件的元信息
```

### 4.2 compress 子命令

```
eml-semzip compress -i <input> -o <output> [options]

必选参数:
  -i, --input        输入文件路径（.json / .pkl 超图）
  -o, --output       输出 SemPkt 文件路径

可选参数:
  --theta-dead       Dead-Zero 剪枝阈值，默认 0.45
  --keep-ratio       κ-Snap 保留比例，默认 0.15
  --kb               EML-Lite KB 文件路径
  --report           输出压缩比统计报告路径（.json / .txt）
  --quiet            静默模式，仅输出结果路径
```

**输出示例：**

```
$ eml-semzip compress -i graph.json -o graph.sempkt --report report.json

[EML-SemZip] 压缩管线启动
  Stage 1/5  Dead-Zero 剪枝        θ_dead=0.45  超边: 1024 → 612 (-412)
  Stage 2/5  EML-Lite 同构归并      KB=eml_lite.pkl  超边: 612 → 487 (-125)
  Stage 3/5  毛睿度量加权          已计算 d_sem
  Stage 4/5  κ-Snap 语义核选取      keep_ratio=0.15  保留锚点: 73 (含闭环: 18)
  Stage 5/5  ANS 熵编码            SemPkt: 1.2 KB

[结果]
  输入超边数:   1024
  输出锚点数:   73
  语义压缩比:   14.0×（锚点维度）/ 300×（含 KB 复用，信息维度）
  比特压缩比:   8533×
  输出文件:     graph.sempkt
  报告文件:     report.json
```

### 4.3 decompress 子命令

```
eml-semzip decompress -i <input> -o <output> [options]

必选参数:
  -i, --input        输入 SemPkt 文件路径
  -o, --output       输出还原超图文件路径（.json / .pkl）

可选参数:
  --kb               EML-Lite KB 文件路径（解压重建需要）
  --quiet            静默模式
```

**输出示例：**

```
$ eml-semzip decompress -i graph.sempkt -o graph_restored.json --kb eml_lite.pkl

[EML-SemZip] 解压管线启动
  ANS 解码          → V*=42, E*=73, θ_dead=0.45, kb.sig=0x7f3a...
  κ-锚点展开        → 节点: 42 → 870
  EML-Lite KB 重建   → 超边: 73 → 1024
  毛睿度量重算      → d_sem 已恢复

[结果]
  还原超边数:   1024  (与原始一致 ✓)
  还原节点数:   870   (与原始一致 ✓)
  输出文件:     graph_restored.json
```

### 4.4 info 子命令

```
eml-semzip info -i <input>

说明: 自动识别文件类型（SemPkt / 超图），输出对应元信息。
```

**SemPkt 输出示例：**

```
[EML-SemZip] SemPkt 元信息
  文件大小:        1.2 KB
  V* (锚节点):     42
  E* (锚超边):     73
  ℐ 值范围:        [0.46, 0.98]
  θ_dead:          0.45
  KB 签名:         0x7f3a...
  闭环数:          18
```

### 4.5 错误处理

- 输入文件格式不支持 → 提示支持的格式并退出码 2
- KB 签名不匹配 → 提示 KB 不兼容并退出码 3
- 解压时缺少 KB → 提示需要 `--kb` 参数并退出码 4
- 参数缺失/非法 → 打印用法说明并退出码 1

---

## 5. 待确认问题（Open Questions）

| # | 问题 | 影响范围 | 倾向性建议 |
|---|------|----------|------------|
| Q1 | EML 超图输入文件的标准格式如何定义？JSON 还是自定义二进制？建议用 JSON（可读、易调试）+ Pickle（高效）双支持 | P0-1, P0-2 | JSON 主格式，Pickle 备选 |
| Q2 | EML-Lite KB 的初始内容从哪来？是否需要提供一份示例 KB（含常见谓词的模板超边）？ | P0-2, P1-1 | 提供示例 KB + 空白 KB 两种 |
| Q3 | "无损语义还原"的判定标准是什么？是超边/节点数量一致，还是需逐条比对 ℐ、d_sem 等字段完全相等？ | P0-3 | 数量一致 + ℐ 容差内相等 |
| Q4 | ANS 熵编码用自实现还是依赖第三方库（如 `range-coders`）？自实现可控但需自测 | P0-4 | 自实现，便于审计与硬件预留 |
| Q5 | 毛睿度量 `d_sem` 中的 `base_weight` 和 `dir_factor` 默认值如何确定？是否每条超边都需要显式提供？ | P0-2 | 默认 base_weight=1.0, dir_factor=1.0，可被超边覆盖 |
| Q6 | κ-Snap 中"闭环(≥3节点)"的检测算法用哪种？DFS 还是 union-find？对大超图性能要求如何？ | P0-2 | DFS，先满足正确性 |
| Q7 | 压缩比统计中"语义压缩比(SCR)"的确切计算公式？是 原始超边数/锚点数，还是 原始比特数/SemPkt 比特数？ | P1-2 | 同时输出两种定义 |
| Q8 | 目标运行环境：纯标准库 Python 3.13，还是允许引入 numpy 等依赖？太极 OS 环境约束如何？ | 全局 | 默认纯标准库，零外部依赖 |

---

*PRD 版本：v1.0  |  撰写人：许清楚（Alice，产品经理）  |  状态：待团队评审*
