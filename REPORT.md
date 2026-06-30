# netlistOpt 图分割调研报告与 Demo 落地方案

> 日期：2026-06-29  
> 目标场景：EDA 前端网表综合后，将全局网表拆成若干局部子图/子网表，利用局部 STA 信息并行做优化，在尽量保护 PPA 和 timing QoR 的前提下降低优化 wall time。

## 1. 执行摘要

网表优化阶段慢的根因通常不是单个局部变换本身，而是“全局依赖 + 全局 STA 更新 + 串行候选评估”叠加。将 gate-level netlist 建模为图或超图后，可以把优化问题改写为：

1. 尽量把强连接、同一逻辑 cone、同一关键 timing path 的单元放在同一分区；
2. 控制跨分区 net/cell 数量，降低边界约束和合并修复成本；
3. 保持分区面积、cell 数或 timing 负载均衡，让并行优化不会被单个大分区拖慢；
4. 在分区边界保留接口约束、slack budget 和回退机制，避免局部优化破坏全局 timing。

本报告建议 netlistOpt 采用“三层路线”：

- **短期 Demo / 工程验证**：自研轻量超图构建与分割脚本，验证 netlist -> hypergraph -> partition -> sub-netlist/partition report -> parallel optimization stub 的闭环。
- **中期落地**：接入 KaHyPar / Mt-KaHyPar 或 OpenROAD TritonPart，对真实 benchmark 做 cut、balance、runtime、QoR 对比。
- **长期优化**：引入 STA slack、critical path、MFFC/logic cone、cell class 多维权重与增量 STA，形成 timing-driven / constraint-driven 的生产化分割能力。

## 2. 总体技术路线

netlistOpt 的目标不是单独做一个高质量 partition，而是建立“分割、局部约束派生、局部 STA、并行优化、全局合并验证”的完整闭环。工程路线分为三个层次：

| 层次 | 目标 | 关键输出 |
| --- | --- | --- |
| 连接结构分割 | 将 netlist 建模为 graph/hypergraph，比较主流分割器的 cut、balance、runtime | partition assignment、cut net list、partition report |
| Timing-aware 分割 | 将 SDC/STA 信息转成 hyperedge 权重、group/fixed 约束、边界 budget | critical cut ratio、boundary AAT/RAT、partition SDC |
| 并行优化闭环 | 在每个 partition 内做局部 STA 与优化，合并后用完整顶层 STA 验证 | per-partition ECO、merge netlist、global WNS/TNS/QoR diff |

因此，本方案的核心判断标准不是单一 cut size，而是：

- partition 是否均衡，能否带来真实并行 wall-time 收益；
- cut boundary 是否可被 SDC/STA budget 准确建模；
- 局部优化结果 merge 后是否保持或改善全局 WNS/TNS、power、area；
- 当局部优化破坏全局 QoR 时，是否可以定位、修复或回滚。

## 3. 背景与问题定义

### 3.1 为什么需要分割

综合后的 netlist 优化通常包含 gate sizing、buffer insertion、logic rewriting、resubstitution、remapping、retiming、局部结构替换等操作。这些操作都依赖 timing、load、fanout、area、power 等上下文。若每次候选优化都触发大范围 STA 更新，运行时间会迅速变成瓶颈。

分割的目的不是简单“切开网表”，而是把全局优化拆成多个近似独立的局部优化任务：

```text
global netlist
  -> graph / hypergraph model
  -> timing / logic aware partitioning
  -> sub-netlists + boundary constraints
  -> parallel local optimization
  -> merge + incremental STA + repair
```

核心评价指标：

- **cut size / cut nets**：跨越多个分区的 net 数量，越低越好。
- **connectivity metric, λ-1**：一个 net 跨越 λ 个分区时贡献 λ-1，比单纯 cut 更能惩罚高扇出跨区。
- **balance**：各分区 cell/area/timing 负载是否均衡。
- **critical cut ratio**：关键路径或低 slack net 被切断的比例。
- **parallel speedup estimate**：理想上约等于 `global_runtime / max(partition_runtime)`，实际需扣除边界修复和合并成本。
- **QoR delta**：优化后 WNS/TNS、power、area 与未分割全局优化的差值。

### 3.2 图模型与超图模型

**普通图模型**通常把 cell 作为顶点，把两个 cell 之间的连接作为边。高扇出 net 会被展开成 clique、star 或 weighted edge。这种模型便于使用通用 graph partitioning 算法，但会丢失 net 的天然多端连接语义。

**超图模型**更符合网表本质：cell 是顶点，net 是 hyperedge，一个 net 可以连接 driver 和多个 sinks。VLSI/CAD 分割领域主流工具如 hMETIS、PaToH、KaHyPar、TritonPart 都以超图为核心模型。

| 模型 | 顶点 | 边/超边 | 优点 | 缺点 | 适用 |
| --- | --- | --- | --- | --- | --- |
| 普通图 | cell / instance | cell-cell edge | 算法多、实现简单 | 高扇出 net 展开失真 | Demo、快速近似 |
| 超图 | cell / instance | net hyperedge | 保留 net 多端结构 | 算法复杂、工具依赖更强 | 工业级 VLSI 分割候选 |
| 有向 DAG | logic node | fanin/fanout arc | 保留方向与 cone | 平衡 cut 优化较复杂 | MFFC、逻辑优化 |
| timing graph | pin / arc | timing arc | 适合 STA 约束 | 与 cell/net 分割需映射 | 关键路径保护 |

### 3.3 DesignDB Adapter 与分割器接口格式

公司自研 EDA 的内存数据模型通常与开源分割器不同，因此不能假设工具天然支持 `.graph`、`.hgr`、`.u` 等文件格式。实际工程中需要增加一层很薄的 **DesignDB Adapter**：

```text
Internal DesignDB / NetlistDB
  -> DesignDBGraphExtractor
  -> graph / hypergraph / in-memory arrays
  -> PartitionToolRunner or C++ API
  -> partition result vector
  -> PartitionResultImporter
  -> write partition_id back to DesignDB
```

这里的 `.v` 文件只是输入/输出和调试格式，不是主流分割算法必须依赖的接口。主流分割器真正需要的是 cell/net/pin 连接关系、权重和约束：

| 接口形式 | 典型工具 | 作用 | 是否要求自研 EDA 原生支持 |
| --- | --- | --- | --- |
| `.graph` | METIS | 普通图邻接表，适合 graph baseline | 不要求；由 adapter 导出 |
| `.hgr` | hMETIS / KaHyPar / Mt-KaHyPar / OpenROAD hypergraph flow | 超图输入，每条 hyperedge 表示一个 net 连接的 cell 集合 | 不要求；由 adapter 导出 |
| `.u` | PaToH | PaToH 专用超图输入格式 | 不要求；由 adapter 导出 |
| partition result | METIS / KaHyPar / Mt-KaHyPar / PaToH / TritonPart | 每个 vertex/cell 对应一个 partition id | 不要求；由 adapter 读回并写入 DesignDB |
| C++ / Python API arrays | KaHyPar / Mt-KaHyPar 等 | 不落文件，直接传递 hyperedge index、pin list、weights | 推荐作为生产集成方向 |

因此，生产化集成建议优先实现 `DesignDBGraphExtractor`、`HypergraphExporter`、`PartitionResultImporter` 和 `PartitionIdWriter`。文件格式适合 demo、工具互通和问题复现；若自研 EDA 与分割器同进程集成，则更推荐直接通过 C++ API 或内存数组传递，减少 I/O 和格式转换成本。

## 4. 主流算法综述

### 4.1 随机 / 贪心基线

随机分割用于建立 baseline。贪心算法可以按 BFS、topological order、seed growing 或 affinity 逐步扩展分区，使强连接节点尽量留在一起。

- 优点：实现简单、速度快、便于 debug。
- 缺点：质量不稳定，容易被初始 seed 影响。
- netlistOpt 价值：作为工程回归基线，任何高级算法都应显著优于它。

### 4.2 Kernighan-Lin, KL

KL 是经典二分图启发式算法，初始给定两个均衡分区，然后反复选择一对跨分区顶点交换，使 cut gain 最大。每轮 pass 锁定已交换顶点，最后执行累计 gain 最大的交换前缀。

- 适合：中小规模图二分、局部 refinement。
- 复杂度：经典实现每 pass 约 `O(|V|^2 log |V|)` 或更高，实际依赖数据结构。
- 优点：概念清晰，能持续改进初始解。
- 缺点：原生是普通图二分，对超图、多约束、多路分割支持弱。
- EDA 适用性：常作为教学/demo 或 refinement 思想来源。

### 4.3 Fiduccia-Mattheyses, FM

FM 可视为 KL 面向 hypergraph / netlist 的高效改进。它每次移动单个顶点，而不是交换顶点对，并用 bucket structure 维护 gain，单 pass 可达到线性复杂度量级。

- 适合：超图二分、分割 refinement。
- 优点：VLSI netlist partitioning 的基础算法之一；适合处理大规模 netlist 的局部优化。
- 缺点：仍易陷入局部最优，依赖初始解；多路和多约束需扩展。
- EDA 适用性：非常高，hMETIS、KaHyPar、TritonPart 等多级框架的 refinement 阶段都能看到 FM 类思想。

### 4.4 谱分割

谱分割基于图 Laplacian 的特征向量，把顶点嵌入连续空间后再按阈值或聚类分区。它能捕获全局结构，常用于获得较好的初始 partition 或 embedding。

- 适合：普通图、需要全局结构的初始划分。
- 优点：理论基础强，能避免纯局部搜索的短视。
- 缺点：特征求解昂贵；超图需转换；timing/多约束集成不直接。
- EDA 适用性：可作为初始解或辅助特征，不建议单独作为生产主算法。

### 4.5 多级图/超图分割

多级框架是现代主流：

1. **Coarsening**：把强关联顶点聚合，形成更小的图/超图。
2. **Initial partitioning**：在最小层做初始 k-way 或 recursive bisection。
3. **Uncoarsening + refinement**：逐层展开，并在每层用 FM / greedy / flow-based refinement 改善 cut 和 balance。

- 代表：METIS、hMETIS、PaToH、KaHyPar、Mt-KaHyPar、TritonPart。
- 优点：可扩展到大规模设计；质量与 runtime 平衡好。
- 缺点：工程实现复杂；参数较多；需要 benchmark 调参。
- EDA 适用性：最高，建议作为中期主路线。

### 4.6 MFFC / cone-aware 分割

Maximum Fanout-Free Cone, MFFC 表示某个节点的 fanin cone 中“只服务于该节点”的逻辑。MFFC 对逻辑优化尤其有价值，因为 cone 内重写/替换更容易保持外部接口稳定。

- 优点：天然贴近逻辑优化；减少跨分区逻辑相关性；便于 parallel rewriting。
- 缺点：MFFC 大小分布可能极不均衡，需要再分割或合并；跨 cone 的 timing path 仍需保护。
- EDA 适用性：对 netlistOpt 非常值得重点跟进，尤其是逻辑优化阶段。

### 4.7 Timing-driven / constraint-driven 分割

仅最小化 cut 不足以保护 PPA。真实流程需要把 STA 信息转为分割约束：

- 关键 net / path 增大 hyperedge 权重，降低被切概率。
- 对低 slack cell/path 做 fixed group 或 group constraint。
- 对 FF、macro、clock domain、power domain 做多维 balance / fence constraint。
- 分区后给边界 pin 分配 slack budget，局部优化后做 incremental STA 和 repair。

TritonPart/OpenROAD `par` 的价值在于它把 VLSI 分割从普通 min-cut 推进到 constraints-driven framework，可直接面向 gate-level netlist 或 hypergraph。

## 5. 工具对比

| 工具 | 类型 | 核心能力 | 优点 | 风险/限制 | netlistOpt 建议 |
| --- | --- | --- | --- | --- | --- |
| METIS | 图分割 | 多级 graph partitioning | 成熟、快 | 不直接处理 hyperedge | 可做普通图 baseline |
| hMETIS | 超图分割 | 多级 hypergraph partitioning | VLSI 经典工具 | 许可证/集成限制 | 对照参考 |
| PaToH | 超图分割 | 多约束/高质量分割 | 学术界常用 | 集成和维护成本 | 对照参考 |
| KaHyPar | 超图分割 | n-level / multilevel，cut 与 λ-1 | 开源、高质量 | C++/Python 依赖需验证 | 中期推荐 |
| Mt-KaHyPar | 并行图/超图分割 | 多线程可扩展 | 大规模更合适 | 参数与构建复杂 | 大设计推荐 |
| TritonPart / OpenROAD par | VLSI constraint-driven 分割 | timing / embedding / constraints | 更贴近 EDA 落地 | 依赖 OpenROAD 生态 | 生产路线重点 |
| 自研 Python baseline | 教学/验证 | 解析简化 netlist、输出分区/子网表 | 轻、可控、可改 | 非生产质量 | 作为对照基线 |

## 6. 分割后的 SDC、STA 与并行优化流程

netlistOpt 不能只做结构分割。真实优化过程依赖 SDC 与 STA：SDC 定义时钟、例外路径、I/O delay、设计规则约束；STA 计算 AAT、RAT、slack，用于判断每个优化操作是否真正改善 timing。因此，分割后的每个 partition 都需要一份派生约束，并且局部 STA 结果必须最终回到全局 STA 中签核。

### 6.1 Partition SDC 的定义

分割后每个子模块不应直接复用完整顶层 SDC，而应生成独立的 partition SDC：

```text
partition SDC =
  顶层 SDC 中与该 partition 相关的约束子集
  + 跨 partition 边界 timing budget
  + 边界 slew/load/driving 信息
  + mode/corner/clock/exception 映射信息
```

partition SDC 需要覆盖：

- **时钟约束**：`create_clock`、`create_generated_clock`、clock latency、uncertainty、transition、propagated/ideal clock 状态。
- **输入边界约束**：`set_input_delay -max/-min`、`set_input_transition`，必要时补 `set_driving_cell`。
- **输出边界约束**：`set_output_delay -max/-min`、`set_load`。
- **时序例外**：只映射确实落在 partition 内或穿过该 partition 的 `set_false_path`、`set_multicycle_path`、`set_min_delay`、`set_max_delay`。
- **设计规则约束**：max slew、max capacitance、max fanout、dont_touch、dont_use。
- **边界保护约束**：对 cut port、跨 partition net、clock gating、reset、scan 等结构限制过度优化，必要时只允许边界 buffer 或边界 sizing。

所有 budget 必须按 `mode / corner / clock domain / rise-fall / setup-hold` 维度保存，不能把不同分析视图的 AAT/RAT 混用。

### 6.2 输入边界：用 AAT 派生 set_input_delay

当某条 cut net 的 driver 在其他 partition，sink 在当前 partition 时，当前 partition 看到的是一个输入端口。这个输入端口不是从 0 时刻到达，而是上游逻辑已经消耗了一部分 timing budget。

统一采用全局 STA 坐标系。设边界点为 `p`，launch clock edge 为 `E_L`：

```tcl
set_input_delay  -clock BCLK -max  [expr AAT_late(p)  - E_L] [get_ports p]
set_input_delay  -clock BCLK -min  [expr AAT_early(p) - E_L] [get_ports p]
set_input_transition <slew_from_global_sta> [get_ports p]
```

- `-max` 用于 setup，表示外部到 partition 输入端的最晚到达时间。
- `-min` 用于 hold，表示外部到 partition 输入端的最早到达时间。
- `-min` 可能为负值，不能简单截断为 0。
- 同一端口若受多个 clock/edge 约束，应生成 clock-specific 约束，并保留 rise/fall 维度。

### 6.3 输出边界：用 RAT 派生 set_output_delay

当某条 cut net 的 driver 在当前 partition，sink 在其他 partition 时，当前 partition 看到的是一个输出端口。这个输出端口需要为下游逻辑保留 required time。

设 capture clock edge 为 `E_C`：

```tcl
set_output_delay -clock BCLK -max [expr E_C_setup - RAT_late(p)]  [get_ports p]
set_output_delay -clock BCLK -min [expr E_C_hold  - RAT_early(p)] [get_ports p]
set_load <downstream_boundary_load> [get_ports p]
```

- `-max` 用于 setup，使 partition 输出端 latest required time 等价于全局 `RAT_late`。
- `-min` 用于 hold，使 partition 输出端 earliest allowed arrival time 等价于全局 `RAT_early`。
- `E_C_setup` 与 `E_C_hold` 必须考虑 multicycle、generated clock 相位、clock latency、uncertainty，不能简单使用默认同周期边。
- 输出 load 应来自下游 fanout pin capacitance、估算线载或已抽取 parasitic，而不是固定常数。

### 6.4 局部 STA 与全局 STA 的关系

完整 netlist、完整 SDC、Liberty、SPEF/估算 RC 下的全局 STA 负责计算真实 timing graph：

- `AAT_late`：setup 分析中从 startpoint 到边界/endpoint 的最大 arrival time。
- `AAT_early`：hold 分析中从 startpoint 到边界/endpoint 的最小 arrival time。
- `RAT_late`：setup 分析中 endpoint 或边界点允许的最晚 arrival time。
- `RAT_early`：hold 分析中 endpoint 或边界点允许的最早 arrival time。
- setup slack：`RAT_late - AAT_late`。
- hold slack：`AAT_early - RAT_early`。

局部 STA 使用 partition SDC 重建近似 timing 环境。它的作用是快速筛选 gate sizing、buffer insertion、clone、rewriting、repair_timing 等候选优化，不能替代最终全局 STA。所有 partition ECO 合并后，必须重新读取完整顶层 SDC 和全局 parasitic，执行全局 STA 签核。

### 6.5 并行优化闭环

推荐工程流程：

1. **全局基线 STA**：读取完整 netlist、Liberty、顶层 SDC、SPEF/估算 RC，生成 `report_checks`、`report_wns`、`report_tns`，确认 unconstrained path 为 0。
2. **边界抽取**：枚举 cut net、boundary port、跨 partition path、clock domain、fanout load、input slew、AAT/RAT、exception 命中关系。
3. **SDC 分派**：为每个 partition 生成独立 SDC，并记录每条约束来自顶层 SDC 还是 timing budget，保证可追溯。
4. **partition 并行优化**：各 partition 独立运行 STA 与优化。典型操作包括修复 slew/cap/fanout、setup、hold。每轮变更后用增量 STA 更新 WNS/TNS 与边界 delta。
5. **merge**：合并所有 partition netlist/ECO，保持边界命名与连接一致，重建全局 timing graph。
6. **merge 后验证与修复**：若出现新增 violation，优先在边界附近做小范围 repair；若跨 partition path 大面积恶化，回滚对应 partition ECO 或重新分配 budget。
7. **rollback**：每个 partition 优化产物必须带版本号、timing 摘要、面积/功耗变化、边界 AAT/RAT delta。超过阈值的 partition 可以单独回滚，不影响其他 partition 结果。

### 6.6 关键风险

| 风险 | 说明 | 处理建议 |
| --- | --- | --- |
| false path / multicycle path 映射错误 | 映射过宽会隐藏真实 violation，映射过窄会造成过约束 | exception 必须按 from/to/through 和 setup/hold 维度精确裁剪 |
| generated clock 丢失 | 局部模块可能看不到 clock source 与 phase 关系 | 保留 generated clock 定义；必要时转换为 virtual clock 并加 margin |
| clock reconvergence | 局部 STA 看不到共同 clock path，CRPR/CPPR 可能失真 | 用 latency/uncertainty guardband 补偿，并在全局 STA 中复核 |
| high fanout net 被切 | clock/reset/scan/enable 等 net 会主导 cut 和 load | 分割时单独降权/固定/分组，优化时限制边界结构变化 |
| boundary load/slew 偏乐观 | 局部优化结果 merge 后 timing 可能恶化 | 对边界 load/slew 加 guardband，并记录实际 delta |
| cross-partition path 失真 | 局部 STA 看不到完整路径 | merge 后专门检查 top N critical cross-partition paths |

### 6.7 验收指标

- 约束覆盖：全局与 partition STA 均无 unconstrained endpoint；生产化验收目标是顶层 SDC 子集映射全部可追溯。
- 时序收敛：merge 后 setup/hold WNS 达到目标，TNS 不劣化或满足预设改善目标。
- 边界精度：merge 后实际 boundary AAT/RAT 与 budget 偏差不超过设定阈值，例如 `<= 20ps` 或 `<= 5% budget`。
- 设计规则：max slew、max cap、max fanout violation 达到签核目标，或不超过签核前 repair 阈值。
- 跨 partition 路径：top N critical cross-partition paths 均经过全局 STA 复核，无被 false/multicycle 误屏蔽路径。
- QoR 控制：面积、功耗、buffer 数量、cell resizing 数量不超过 partition 配额。
- 工程效率：partition 并行优化 wall time 相比全局串行优化有明确下降，且 rollback 次数、重跑次数可统计。

## 7. netlistOpt 推荐流程

```text
输入:
  gate-level netlist
  library area/power estimate
  optional STA report: critical paths / slack / fanout / load

建模:
  vertices = cells
  hyperedges = nets connecting driver/sinks
  vertex weights = area, delay proxy, cell class
  hyperedge weights = fanout weight + timing criticality weight

工具适配:
  Internal DesignDB -> adapter -> .graph/.hgr/.u or API arrays
  partition result -> adapter -> partition_id in DesignDB

分割:
  baseline: random / greedy
  demo: KL/FM-like refinement + multilevel-like seed growing
  production: KaHyPar / Mt-KaHyPar / TritonPart

输出:
  partition assignment
  sub-netlists
  boundary constraints
  metrics: cut, λ-1, balance, runtime, critical cuts

并行优化:
  each partition -> local optimizer with boundary timing budget
  merge -> incremental STA -> violation repair -> QoR compare
```

## 8. 实验设计

实验包含两个层次：

1. **主流工具实验：`classic_partition_demo.py`**
   - 真实调用 KaHyPar Python binding，使用官方 `km1_kKaHyPar_sea20.ini` / `cut_kKaHyPar_sea20.ini` 配置；
   - 导出 hMETIS `.hgr`、cell/net 映射表，并真实调用 OpenROAD Partition Manager / TritonPart；
   - 将超图投影为 weighted graph，并真实调用 METIS `gpmetis`；
   - 真实编译并调用 Mt-KaHyPar CLI，直接读取 hMETIS `.hgr` 超图输入；
   - 真实调用 PaToH v3.3 standalone CLI，使用 PaToH `.u` 输入格式并读取官方 `.part.K` 输出；
   - 用 PyTorch 实现一个小型 GCN-style partitioner，复现 CircuitPartitioning-GNN 的“图神经网络 + cut/balance loss”思路；
   - 实现 GL0AM-style logic cone grouping，复现其按逻辑 cone 分块映射 GPU block 的策略；
   - 增加 Louvain community pre-clustering 作为社区发现/预聚类 baseline。

2. **轻量 baseline demo：`netlist_split_demo.py`**
   - 用标准库实现 random/greedy/FM-style/multilevel-style baseline；
   - 用于和真实/经典工具结果对照，验证 netlist -> hypergraph -> partition -> sub-netlist 的闭环。

从公司自研 EDA 集成角度看，`classic_partition_demo.py` 中的 `.graph`、`.hgr`、`.u` 导出逻辑对应生产系统里的 adapter 层：它负责把内部 DesignDB 的 instance/net/pin 关系转成分割器可接受的 graph/hypergraph 输入，再把工具输出的 partition vector 写回内部对象。生产系统不需要让 EDA 核心数据库“原生识别”这些文件格式，只需要定义清晰的导出/导入边界。

运行方式：

```bash
PYTHONPATH=.tooling/python python3 classic_partition_demo.py --input sample_netlist.v --k 4 --backend all --out classic_results --run-openroad
python3 netlist_split_demo.py --input sample_netlist.v --k 2 --algo all --out results_k2
python3 netlist_split_demo.py --input sample_netlist.v --k 4 --algo all --out results_k4
PYTHONPATH=.tooling/python python3 -m unittest -v
```

当前环境说明：

- KaHyPar：已通过本地 `.tooling/python` Python binding 真实运行。
- OpenROAD/TritonPart：已在无 sudo 环境下从 GitHub release `.deb` 用户态解包到 `.tooling/openroad_extracted/`，并补齐本地动态库路径后真实运行 `triton_part_hypergraph`。官方 VaultLink 上存在更新的 Ubuntu 24.04 预编译包，但下载接口需要邮件注册授权，未做无交互下载。
- METIS：已从 Ubuntu apt 仓库下载 `metis` 包并用户态解包，真实运行 `.tooling/metis_extracted/usr/bin/gpmetis`。
- Mt-KaHyPar：已从 GitHub 源码 clone，使用 GCC 13、`-DKAHYPAR_DOWNLOAD_TBB=On` 编译 `MtKaHyPar` CLI，并真实运行。
- PaToH：已从官方页面下载 Linux x86_64 binary distribution，真实运行 standalone `patoh`。PaToH binary 可用于 demo/research 验证；商业或产品化使用需要单独确认 commercial license。
- hMETIS：根据 UMN Technology Commercialization 页面说明，hMETIS 当前属于 non-open、fee-based 工具，需要 License/Sponsored research/Co-development 授权流程；未使用非官方 binary，因此未做真实运行。
- ABKGroup/TritonPart standalone：仓库为 BSD-3-Clause 开源，仓库 license 本身未形成阻塞。已 clone 仓库并完成 CMake 配置；standalone `openroad` target 编译在 FastRoute 与当前 `fmt/spdlog` 版本组合处失败，未生成可执行文件，因此 standalone 仓库未完成真实运行。OpenROAD 集成版 `src/par` 已真实运行，结果见 9.1；standalone 构建日志见 `.tooling/src/TritonPart/openroad_build.log`。
- CircuitPartitioning-GNN：未直接 vendoring 原仓库代码；本 demo 用 PyTorch 复现其 GNN partitioning 思路，用于小网表可运行验证。
- GL0AM：GL0AM 本身是 GPU gate-level simulator，不是单独 partitioner；本 demo 复现其 README 中描述的 logic-cone grouping 分块策略。

## 9. Demo 实验结果

> 本节由 `classic_partition_demo.py` 和 `netlist_split_demo.py` 实际运行结果生成/校验。小型 demo 的指标用于比较算法趋势，不代表生产化 QoR。

### 9.1 经典/调研工具 demo 结果

| Benchmark | Backend | Tool Reality | k | Cells | Nets | Cut Nets | λ-1 | Balance Max/Avg | Runtime ms | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| sample_netlist.v | KaHyPar | 真实 Python binding | 4 | 14 | 21 | 8 | 11 | 1.14 | 5.422 | `km1_kKaHyPar_sea20.ini` |
| sample_netlist.v | OpenROAD/TritonPart | 真实 OpenROAD `par` 运行 | 4 | 14 | 21 | 10 | 14 | 1.14 | 387.052 | `v2.0-17198-g8396d0866` |
| sample_netlist.v | METIS | 真实 `gpmetis` 运行 | 4 | 14 | 21 | 7 | 9 | 1.14 | 5.581 | hypergraph projected to weighted graph |
| sample_netlist.v | Mt-KaHyPar | 真实 `MtKaHyPar` CLI 运行 | 4 | 14 | 21 | 8 | 8 | 1.14 | 38.096 | hMETIS `.hgr`，`objective=km1`，2 threads |
| sample_netlist.v | PaToH | 真实 `patoh` CLI 运行 | 4 | 14 | 21 | 8 | 8 | 1.14 | 2.895 | PaToH `.u`，`UM=O` connectivity-1 metric |
| sample_netlist.v | CircuitGNN-style | PyTorch GCN 思路复现 | 4 | 14 | 21 | 12 | 17 | 1.14 | 854.831 | 小数据上训练不占优，仅验证 GNN 流程 |
| sample_netlist.v | GL0AM-cone-style | logic cone 分块策略复现 | 4 | 14 | 21 | 11 | 16 | 1.14 | 0.081 | 适合 simulator block grouping，不以 min-cut 为唯一目标 |
| sample_netlist.v | Louvain precluster | NetworkX 社区发现 baseline | 4 | 14 | 21 | 9 | 10 | 1.14 | 1.928 | 可作为多级 coarsening/预聚类输入 |

实验解读：

- KaHyPar 是主流超图分割器，在 k=4 上 cut nets=8、λ-1=11，结果较均衡。
- OpenROAD/TritonPart 已完成实际运行。安装方式为：下载 GitHub release `openroad_2.0-17198-g8396d0866_amd64-ubuntu-22.04.deb`，用 `dpkg-deb -x` 解包到 `.tooling/openroad_extracted/`，再用本地 `LD_LIBRARY_PATH` 补齐 `libortools`、`tcl-tclreadline`、`libQt5Charts`、`libpython3.10`。本机执行的版本为 `v2.0-17198-g8396d0866`。
- OpenROAD `par` 对本样例生成 `classic_results/openroad_tritonpart/demo_top.hgr.part.4`，根据该 solution 文件回算 cut nets=10、λ-1=14。日志见 `classic_results/openroad_tritonpart/openroad_run.log`。
- METIS 对超图投影后的 weighted graph 运行 `gpmetis -ptype=rb`，cut nets=7、λ-1=9。由于 METIS 优化的是 graph edgecut，不是原生 hypergraph cut-net，结果只能作为 graph baseline 与预聚类参考，不能直接替代 KaHyPar/TritonPart 的超图目标。
- Mt-KaHyPar 已完成源码编译和真实 CLI 运行。第一次构建使用默认编译器时遇到 LTO 版本不匹配，切换 GCC 13 并关闭 IPO 后构建通过；CLI 直接读取 `classic_results/mt_kahypar/demo_top.hgr`，生成 `demo_top.hgr.part4.epsilon0.03.seed7.KaHyPar`，回算 cut nets=8、λ-1=8。
- PaToH 已完成官方 binary 真实运行。demo 将 hMETIS 超图转换为 PaToH `.u` 格式，执行 `patoh demo_top.u 4 UM=O PQ=D WI=1`，生成 `demo_top.u.part.4`，回算 cut nets=8、λ-1=8。日志提示 balance not tight enough；本样例实际分区为 4/3/4/3，作为对照实验可接受，后续可调 imbalance / 多约束参数。PaToH 可用于 demo/research 验证，商业或产品化使用需单独确认授权。
- hMETIS 未真实运行。原因不是技术接口缺失，而是当前官方渠道将 hMETIS 定位为 non-open、fee-based 工具，需要向 UMN 走 License/Sponsored research/Co-development 授权流程；本实验未使用未授权二进制。许可证证据记录见 `classic_results/license_evidence.md`。
- ABKGroup/TritonPart standalone 未真实运行。CMake 已通过，最终在 `src/grt/src/fastroute/src/utility.cpp` 编译失败，错误为 `fmt` 9 对 `grt::RouteType` 参数缺少 formatter specialization。该问题属于老 standalone OpenROAD/TritonPart 与当前系统依赖版本不兼容，不是商业授权限制；若需要继续推进，建议使用仓库年代匹配的 Ubuntu 20.04/22.04 容器或固定旧版 `fmt/spdlog` 依赖。构建日志见 `.tooling/src/TritonPart/openroad_build.log`，状态记录见 `classic_results/tritonpart_standalone/status.json`。
- GNN-style demo 证明图神经网络分割流程可跑，但在 14-cell 小样例上没有质量优势；GNN 类方法需要更多训练样本和 benchmark 才有意义。
- GL0AM-style cone grouping 的目标更偏 GPU simulation locality，而不是单纯 min-cut；cut 较高是可解释的。
- Louvain precluster 能快速找到社区结构，可作为 KaHyPar/TritonPart coarsening guide，而不是最终生产化约束分割器。

### 9.2 轻量 baseline demo 结果

| Benchmark | Algorithm | k | Cells | Nets | Cut Nets | λ-1 | Balance Max/Avg | Runtime ms | Estimated Parallel Speedup |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sample_netlist.v | random | 2 | 14 | 21 | 9 | 9 | 1.00 | 0.050 | 1.52x |
| sample_netlist.v | greedy | 2 | 14 | 21 | 8 | 8 | 1.00 | 0.277 | 1.55x |
| sample_netlist.v | fm | 2 | 14 | 21 | 8 | 8 | 1.00 | 0.439 | 1.55x |
| sample_netlist.v | multilevel | 2 | 14 | 21 | 8 | 8 | 1.00 | 0.456 | 1.55x |
| sample_netlist.v | random | 4 | 14 | 21 | 10 | 13 | 1.14 | 0.053 | 1.82x |
| sample_netlist.v | greedy | 4 | 14 | 21 | 9 | 10 | 1.14 | 0.242 | 1.90x |
| sample_netlist.v | fm | 4 | 14 | 21 | 9 | 10 | 1.14 | 1.809 | 1.90x |
| sample_netlist.v | multilevel | 4 | 14 | 21 | 8 | 9 | 1.14 | 3.228 | 1.99x |

`Estimated Parallel Speedup` 不是实测 wall-time 加速，而是 demo 中的启发式估算值，用于观察 cut/balance 对并行收益的影响。公式来自 `netlist_split_demo.py`：

```text
serial_fraction = min(0.95, 0.05 + 0.03 * cut_net_count)
balance_penalty = max(1.0, balance_max_over_avg)
estimated_speedup = k / (1.0 + serial_fraction * (k - 1) + (balance_penalty - 1.0))
```

含义：

- `0.05` 表示固定串行开销，例如任务调度、分区读写、merge、全局检查；
- `0.03 * cut_net_count` 表示跨分区 net 越多，边界约束、通信、合并修复成本越高；
- `balance_penalty` 表示分区不均衡会让最大分区拖慢并行 wall time；
- 因此该列是评估计算值，不是 OpenROAD/STA/netlistOpt 真实运行数据。

列头含义：

| 列名 | 含义 |
| --- | --- |
| Benchmark | 输入网表文件 |
| Algorithm | 使用的轻量 baseline 算法 |
| k | 请求分区数 |
| Cells | 被分割的 cell/instance 数量，`assign` 也作为一个 cell 处理 |
| Nets | netlist 中参与建模的 net 数量 |
| Cut Nets | 跨越两个或更多 partition 的 net 数量 |
| λ-1 | connectivity metric；一个 net 跨越 λ 个 partition，则贡献 λ-1 |
| Balance Max/Avg | 最大分区 cell 数 / 平均分区 cell 数，越接近 1 越均衡 |
| Runtime ms | 该 demo 算法自身的 Python 运行时间，不包含真实优化/STA |
| Estimated Parallel Speedup | 基于 cut nets 和 balance 的并行收益估算，不是实测加速 |

实验解读：

- random 作为下界，cut nets 和 λ-1 都最高，说明仅做均衡分配不足以保留局部逻辑结构。
- k=2 时 greedy/FM/multilevel 都能把 cut nets 从 9 降到 8，且保持完全均衡。
- k=4 时 multilevel proxy 的 cut nets=8、λ-1=9，是本 demo 中最优；代价是 runtime 高于 greedy/FM。这个趋势符合多级/全局排序方法“质量更好但常数更高”的直觉。
- 估计并行收益从 k=2 的约 1.55x 增加到 k=4 的约 1.9-2.0x，但没有线性达到 4x，原因是 cut nets 带来的串行边界/合并成本会抵消部分并行收益。
- `results_k2/` 与 `results_k4/` 已生成每个算法的 `metrics.json`、`partitions.tsv` 和 `partition_<n>.v` 子网表骨架，可作为后续并行优化 wrapper 的输入。

## 10. 资料清单与核心结论

| 资料 | 结论 | 链接 |
| --- | --- | --- |
| Alpert & Kahng, Recent Directions in Netlist Partitioning: a Survey | 经典综述，覆盖问题定义、min-cut/ratio-cut/multi-way、move-based/spectral/clustering 等方向 | https://vlsicad.ucsd.edu/Publications/Journals/index.html |
| Kernighan-Lin, 1970 | 图二分启发式经典算法，适合理解 gain-based refinement | https://ieeexplore.ieee.org/document/6771089/ |
| Fiduccia-Mattheyses, 1982 | 面向网络/超图分割的线性时间 pass 启发式，是 VLSI 分割基础 | https://dl.acm.org/doi/10.5555/800263.809204 |
| hMETIS | 多级超图分割经典工具，面向 VLSI 电路超图 | https://karypis.github.io/glaros/files/sw/hmetis/manual.pdf |
| KaHyPar | 开源高质量超图分割框架，支持 cut 和 λ-1、recursive bisection/direct k-way | https://kahypar.org/ |
| Mt-KaHyPar | 多线程 graph/hypergraph partitioner，适合更大规模 | https://github.com/kahypar/mt-kahypar |
| TritonPart / OpenROAD par | 约束驱动分割器，可用于 hypergraph 或 gate-level netlist，贴近 EDA 生产落地 | https://openroad.readthedocs.io/en/latest/main/src/par/README.html |
| TritonPart ICCAD 2023 | timing-aware partitioning 能减少关键路径 cut，提出 constraint-driven framework | https://vlsicad.ucsd.edu/Publications/Conferences/401/c401_camera.pdf |
| MFFC 相关逻辑优化 | MFFC 表示可独立替换/重写的逻辑 cone，适合并行逻辑优化分割 | https://people.eecs.berkeley.edu/~alanmi/publications/2007/iwls07_ifs.pdf |
| Hypergraph Partitioning and Clustering | 说明逻辑电路可自然映射为 hypergraph：gates->vertices, nets->hyperedges | https://web.eecs.umich.edu/~imarkov/pubs/book/part_survey.pdf |

## 11. 落地路线图

### 1-2 个月：验证闭环

- 完成 Python demo 到真实小 benchmark 的适配。
- 支持 ISCAS/EPFL/Yosys 输出的 gate-level Verilog 子集。
- 加入 critical net weight 输入文件。
- 输出 partition report、cut net list、子网表、边界 pin list。
- 与 random/greedy/FM/multilevel baseline 做稳定回归。

验收：至少 3 个 benchmark、k=2/4/8、cut/balance/runtime 表格完整。

### 3-6 个月：接入工业级分割器

- 接入 KaHyPar / Mt-KaHyPar。
- 评估 OpenROAD `par` / TritonPart 是否可直接吃现有 netlist。
- 引入 multi-dimensional weight：cell area、FF/LUT/DSP 或 stdcell class、timing load。
- 建立分割后并行优化 stub：每个分区独立跑局部优化脚本，merge 后跑全局检查。

验收：在真实设计上量化 wall-time 变化，并将 WNS/TNS/area/power 变化控制在预设阈值内。

### 6 个月以上：生产化 timing-driven netlistOpt

- 接入增量 STA，形成 path-level slack budget。
- 关键路径 group constraint 与边界 repair 自动化。
- MFFC/cone-aware 与 hypergraph partitioning 混合。
- 建立分区参数自动调优：k、imbalance、critical weight、max boundary ratio。
- 与现有优化器闭环：失败回滚、局部重分割、QoR gate。

验收：在多设计、多 corner、多 PVT 条件下量化收益与风险，评估是否具备默认开启的 netlistOpt 并行优化条件。

## 12. 风险与对策

| 风险 | 影响 | 对策 |
| --- | --- | --- |
| cut 太多导致边界约束复杂 | 并行收益被合并/修复抵消 | 增大关键 net 权重，限制高扇出 net cut，使用 λ-1 指标 |
| 关键路径被切断 | WNS/TNS 退化 | critical path group、slack budget、merge 后 repair |
| 分区不均衡 | 并行 wall time 被最大分区决定 | 多维 weight balance，限制 max/avg ratio |
| 局部优化错失全局机会 | area/power/timing 不如全局优化 | MFFC/cone-aware 分区、周期性全局 cleanup |
| 工具集成成本高 | Demo 到生产迁移慢 | 先用 Python demo 固化接口，再替换 backend partitioner |
| Verilog 解析复杂 | 子网表生成不完整 | 短期限制输入子集，中期接入 Yosys/RTLIL/DEF/OpenDB |

## 13. 一页纸结论

1. 网表分割应优先采用超图模型，普通图只适合 baseline 和轻量 demo。
2. KL/FM 是理解和实现 refinement 的基础；生产化路线应采用多级超图分割框架。
3. KaHyPar/Mt-KaHyPar 适合作为开源高质量 backend；TritonPart/OpenROAD `par` 更贴近 EDA 约束驱动落地。
4. 对 netlistOpt 来说，单纯 min-cut 不够，必须引入 timing criticality、MFFC/logic cone、cell weight、边界 slack budget。
5. 分区后并行优化的真正验收标准不是 cut 最小，而是 wall-time 降低与 PPA/QoR 退化可控。

## 14. 实验复现与质量检查

### 14.1 复现命令

已执行：

```bash
PYTHONPATH=.tooling/python python3 -m unittest -v
PYTHONPATH=.tooling/python python3 classic_partition_demo.py --input sample_netlist.v --k 4 --backend all --out classic_results --run-openroad
python3 netlist_split_demo.py --input sample_netlist.v --k 2 --algo all --out results_k2
python3 netlist_split_demo.py --input sample_netlist.v --k 4 --algo all --out results_k4
```

### 14.2 验证结果

结果：

- 单元测试：`Ran 11 tests ... OK`
- KaHyPar：真实 Python binding 运行成功，k=4 时 cut nets=8、λ-1=11。
- OpenROAD/TritonPart：本地用户态 OpenROAD 运行成功，k=4 时 cut nets=10、λ-1=14，日志见 `classic_results/openroad_tritonpart/openroad_run.log`。
- METIS：真实 `gpmetis` 运行成功，k=4 时 cut nets=7、λ-1=9。
- Mt-KaHyPar：源码编译后的 `MtKaHyPar` CLI 真实运行成功，k=4 时 cut nets=8、λ-1=8，日志见 `classic_results/mt_kahypar/mtkahypar.log`。
- PaToH：官方 binary `patoh` 真实运行成功，k=4 时 cut nets=8、λ-1=8，日志见 `classic_results/patoh/patoh.log`；商业使用需单独确认授权。
- hMETIS：未真实运行，原因是官方发布渠道为 non-open、fee-based 授权模式，不适合在未授权状态下纳入 demo。
- ABKGroup/TritonPart standalone：未真实运行。CMake 已通过，`openroad` target 编译在 FastRoute 与当前 `fmt/spdlog` 版本不兼容处失败；OpenROAD 集成版 `src/par` 已真实运行并可作为 TritonPart 工程路线验证。
- CircuitGNN-style / GL0AM-cone-style / Louvain baseline：均运行成功并生成 `metrics.json`、`partitions.tsv`、子网表骨架。
- k=2 示例：4 个算法全部运行成功，生成 8 个子网表文件。
- k=4 示例：4 个算法全部运行成功，生成 16 个子网表文件。
- 依赖状态：baseline demo 无第三方依赖；classic demo 使用本地 `.tooling/python/kahypar`、`.tooling/metis_extracted`、`.tooling/openroad_extracted`、`.tooling/src/mt-kahypar/build_gcc13`、`.tooling/patoh_extracted`，以及系统已有 `torch` 与 `networkx`。

### 14.3 实验结论

- 代码已覆盖 netlist 解析、hMETIS `.hgr` 格式导出、KaHyPar/Mt-KaHyPar 超图输入导出、PaToH `.u` 导出、真实 KaHyPar 分割、真实 OpenROAD/TritonPart hypergraph 分割、真实 METIS graph 分割、真实 Mt-KaHyPar 分割、真实 PaToH 分割、GNN-style 分割、GL0AM-style cone grouping、指标输出、结果目录与子网表骨架生成。
- 报告已覆盖背景、问题定义、主流算法、工具对比、SDC/STA 边界约束、并行优化流程、实验结果、路线图和风险。
- 当前 demo 不承诺生产化 Verilog 完整解析或真实 STA QoR；OpenROAD 使用的是可无注册下载的旧 GitHub release，更新的 26Q2 Ubuntu 24.04 包需要 VaultLink 邮件授权。
- 下一阶段重点应放在真实 benchmark、真实 SDC/SPEF、partition SDC generator、局部 STA/优化 wrapper 与 merge 后全局 STA 验证。

## 15. 参考链接

- https://vlsicad.ucsd.edu/Publications/Journals/index.html
- https://vlsicad.ucsd.edu/Publications/Conferences/401/c401_camera.pdf
- https://openroad.readthedocs.io/en/latest/main/src/par/README.html
- https://github.com/ABKGroup/TritonPart
- https://kahypar.org/
- https://github.com/kahypar/kahypar
- https://github.com/kahypar/mt-kahypar
- https://faculty.cc.gatech.edu/~umit/PaToH/manual.pdf
- https://license.umn.edu/product/hmetis-version-15
- https://karypis.github.io/glaros/files/sw/hmetis/manual.pdf
- https://dl.acm.org/doi/10.5555/800263.809204
- https://ieeexplore.ieee.org/document/6771089/
- https://people.eecs.berkeley.edu/~alanmi/publications/2007/iwls07_ifs.pdf
- https://web.eecs.umich.edu/~imarkov/pubs/book/part_survey.pdf
