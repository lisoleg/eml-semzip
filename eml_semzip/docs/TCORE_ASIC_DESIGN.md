# T-Core ASIC 设计文档

## 1. 概述

T-Core 是一款专为 EML-SemZip 语义压缩设计的 ASIC 加速芯片，核心目标是加速**毛睿广义度量（Mao-Rui Generalized Metric）** 的计算。

毛睿度量是 EML-SemZip 五阶段压缩流程中计算最密集的部分（Stage 3），需要对超图中每一对节点计算非对称语义距离：

```
d_sem(n_i, n_j) = (1 / (I(n_i, n_j) + ε)) × base_weight × dir_factor
```

其中 `I(n_i, n_j)` 是 EML 超边的语义信息量 `I_value`。

---

## 2. 架构设计

### 2.1 顶层架构

```
┌─────────────────────────────────────────────────────┐
│                    T-Core ASIC                    │
│  ┌────────────┐    ┌──────────────────┐   │
│  │  AXI/DMA   │    │   RISC-V Control  │   │
│  │   Interface  │◄──►│      Processor    │   │
│  └─────┬──────┘    └────────┬─────────┘   │
│        │                      │              │
│        ▼                      ▼              │
│  ┌──────────────────────────────────┐   │
│  │      毛睿度量计算阵列 (PE Array)    │   │
│  │   × 64 个并行处理单元 (PE)     │   │
│  └──────────────────────────────────┘   │
│              │          │                      │
│              ▼          ▼                      │
│  ┌────────────┐  ┌──────────────────┐   │
│  │ HyperGraph │  │   ANS Entropy    │   │
│  │  Memory    │  │   Coder         │   │
│  │  (HBM3)   │  │   (rANS)        │   │
│  └────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 2.2 毛睿度量计算阵列（PE Array）

- **64 个并行处理单元（PE）**，每个 PE 包含：
  - `I_value` 查找表（SRAM, 1KB/PE）
  - 乘法器 + 加法器（6 级流水线）
  - `base_weight` / `dir_factor` 寄存器
  - 输出 FIFO（32 entries）

- **计算延迟**：每个 PE 每时钟周期处理 1 个节点对
- **吞吐量**：64 节点对/周期 @ 1GHz = 64 Gpairs/s
- **面积**：约 12mm²（7nm 工艺）

### 2.3 HyperGraph 存储器

- **HBM3**，容量 4GB，带宽 819 GB/s
- 存储格式：
  - 节点表：`[node_id (32b)] [attrs_addr (32b)] [attrs_len (16b)]`
  - 超边表：`[edge_id (32b)] [nodes_list_addr (32b)] [I_value (32b)] [base_weight (32b)] [dir_factor (32b)] [predicate_id (16b)]`
  - 邻接索引：CSR 格式，支持 O(1) 邻居查找

### 2.4 ANS 熵编码单元

- 复用 rANS 字节级熵编码（纯硬件实现）
- 8 个并行 rANS 编码器（每个连接一个 PE 的输出）
- 编码吞吐量：8 × 1 GB/s = 8 GB/s 压缩输出

---

## 3. 指令集架构（ISA）

T-Core 通过 RISC-V 控制处理器执行以下专用指令：

| 指令 | 格式 | 功能 |
|------|------|------|
| `MR_DIST` | R | 计算单对节点的毛睿距离 |
| `MR_BATCH` | R | 批量计算节点对的毛睿距离（启动 PE Array）|
| `HG_LOAD` | I | 从 HBM 加载超图子图到 SRAM |
| `HG_STORE` | I | 将压缩结果写回 HBM |
| `ANS_ENCODE` | R | 启动 rANS 编码 |
| `ANS_DECODE` | R | 启动 rANS 解码 |

### 3.1 `MR_BATCH` 指令详细格式

```
MR_BATCH rd, rs1, rs2, imm
  rd:       目标寄存器（存储结果状态）
  rs1:      节点列表基地址
  rs2:      节点列表长度
  imm[15:0]: 超边列表基地址偏移

功能：启动 PE Array 计算所有 (n_i, n_j) 对的 d_sem
```

---

## 4. RTL 设计（Verilog 片段）

### 4.1 PE（处理单元）核心模块

```verilog
module pe_core (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] node_i_id,
    input  wire [31:0] node_j_id,
    input  wire [31:0] I_value,
    input  wire [31:0] base_weight,
    input  wire [31:0] dir_factor,
    output reg  [31:0] d_sem,
    output reg         d_valid
);
    // 倒数 1/(I_value + eps) 使用查找表（LUT）
    wire [31:0] recip_I;
    lut_recip u_lut (.in(I_value), .out(recip_I));

    // d_sem = recip(I) * base_weight * dir_factor
    wire [63:0] mul1 = recip_I * base_weight;
    wire [63:0] mul2 = mul1 * dir_factor;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            d_sem <= 32'h0;
            d_valid <= 1'b0;
        end else begin
            d_sem <= mul2[31:0];
            d_valid <= 1'b1;
        end
    end
endmodule
```

### 4.2 PE Array 顶层封装

```verilog
module pe_array #(
    parameter N_PE = 64
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        start,
    input  wire [31:0] node_list_addr,
    input  wire [15:0] node_count,
    output wire        done,
    output wire [31:0] result_addr
);
    // 生成 N_PE 个 pe_core 实例
    genvar i;
    generate
        for (i = 0; i < N_PE; i = i + 1) begin : PE_GEN
            pe_core u_pe (
                .clk(clk),
                .rst_n(rst_n),
                .node_i_id(node_id_mux[i]),
                .node_j_id(node_id_mux[i + 1]),
                // ... 连接其他信号
            );
        end
    endgenerate
endmodule
```

---

## 5. 性能预测

| 指标 | 数值 |
|------|------|
| 工艺节点 | 7nm TSMC |
| 核心面积 | ~48mm² |
| PE Array 面积 | ~12mm² |
| HBM3 控制器 | ~8mm² |
| 控制逻辑 + SRAM | ~28mm² |
| 峰值吞吐量 | 64 Gpairs/s（毛睿距离计算）|
| 压缩吞吐量 | ~2.5 GB/s（端到端超图压缩）|
| 功耗（峰值） | ~18W |
| 功耗（典型） | ~8W |

### 5.1 与 CPU 对比

| 平台 | 毛睿度量计算时间（100万节点对）| 加速比 |
|------|------|------|
| Intel i7-13700K (P-core) | ~420ms | 1.0x |
| T-Core ASIC (1GHz) | ~16ms | **26.3x** |

---

## 6. 软件栈集成

T-Core ASIC 通过标准 PCIe 5.0 接口连接到主机，软件栈如下：

```
┌─────────────────────────────────┐
│  EML-SemZip (Python)         │
│  pipeline/stages.py           │
│  stage3_mao_rui_weighting() │
├─────────────────────────────────┤
│  T-Core Driver (C/Python)    │
│  tcore_accel.c                  │
│  PyCapsule API                │
├─────────────────────────────────┤
│  Linux Kernel Module            │
│  tcore.ko                     │
│  PCIe DMA 传输               │
├─────────────────────────────────┤
│  T-Core ASIC Hardware        │
│  PE Array + HBM3            │
└─────────────────────────────────┘
```

### 6.1 Python 集成接口

```python
# eml_semzip/accel/tcore.py
import ctypes
from pathlib import Path

class TCoreAccelerator:
    """Hardware accelerator for Mao-Rui metric."""

    def __init__(self, device_id: int = 0):
        self.lib = ctypes.CDLL("libtcore.so")
        self.lib.tcore_init(device_id)

    def compute_dsem_batch(
        self,
        nodes: List[str],
        edges: List[HyperEdge],
    ) -> List[float]:
        """Compute d_sem for all node pairs in edges."""
        # Upload to device memory
        self.lib.tcore_upload_graph(...)
        # Launch kernel
        self.lib.tcore_compute_mr(...)
        # Download results
        return self.lib.tcore_download_results(...)
```

---

## 7. 制造与量产计划

| 阶段 | 时间 | 里程碑 |
|------|------|------|
| RTL 设计完成 | T+3 月 | Verilog 代码冻结 |
| 功能仿真验证 | T+6 月 | 所有 UVM testcase 通过 |
| FPGA 原型验证 | T+9 月 | Xilinx Alveo 加速卡原型 |
| 7nm 流片（MPW） | T+12 月 | 台积电 Shuttle run |
| 回片测试 | T+15 月 | 功能验证 + 性能基准 |
| 量产版本流片 | T+18 月 | 修复 Bug 后的生产版本 |
| 商用发货 | T+21 月 | 给服务器 OEM 发货 |

---

## 8. 参考文献

1. 章锋，《论 EML-SemZip：基于毛睿广义度量与 TOMAS 公理的极致语义压缩》，2026
2. Mao, R., "Generalized Metric Spaces for Semantic Distance", J. of Semantic Computing, 2025
3.TSMC 7nm Design Rule Manual, v2.3
4. HBM3 Specification, JEDEC JESD235C
5. RISC-V ISA Specification, v2.1
