# netlistOpt 图分割调研报告与 Demo 落地方案

> 交付日期：2026-06-24  
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
- **长期优化**：引入 STA slack、critical path、MFFC/logic cone、cell class 多维权重与增量 STA，形成 timing-driven / constraint-driven 的生产级分割器。

## 2. 任务压缩策略

原计划是 14 天调研 + Demo + 报告。本次期限为 2 天，因此采用以下压缩：

| 原计划模块 | 2 天内交付方式 | 验收物 |
| --- | --- | --- |
| 资料搜集与精读 | 聚焦核心论文、主流工具、开源文档 | 本报告第 4、5、10 节 |
| 方案设计 | 直接输出 netlistOpt 分区流程和工程路线 | 第 7、8、9 节 |
| Demo 环境 | 不强依赖重型 EDA 工具，标准 Python 可跑 | `netlist_split_demo.py`、样例 netlist、测试 |
| 实验结果 | 小型 synthetic benchmark 跑通多算法、多 k | 第 9 节实验表 |
| 最终报告 | Markdown 版本放在当前目录 | `REPORT.md` |

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
| 超图 | cell / instance | net hyperedge | 保留 net 多端结构 | 算法复杂、工具依赖更强 | 生产级 VLSI 分割 |
| 有向 DAG | logic node | fanin/fanout arc | 保留方向与 cone | 平衡 cut 优化较复杂 | MFFC、逻辑优化 |
| timing graph | pin / arc | timing arc | 适合 STA 约束 | 与 cell/net 分割需映射 | 关键路径保护 |

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
| 自研 Python demo | 教学/验证 | 解析简化 netlist、输出分区/子网表 | 轻、可控、可改 | 非生产质量 | 本次交付 |

## 6. Timing 保护与 Slack 恢复策略

推荐把 timing-driven 分割拆成 5 个工程层次：

1. **静态权重层**：依据 net fanout、cell type、是否在 timing-critical list 中设置 hyperedge weight。
2. **路径保护层**：对低 slack path 上连续 cell 加 group constraint 或 high affinity。
3. **边界预算层**：跨区边界 pin 记录 arrival/required/slack budget，局部优化不得消耗超过阈值。
4. **合并修复层**：并行优化后 merge，做 incremental STA，对 WNS/TNS 退化 path 触发 repair。
5. **回退层**：若某分区导致 QoR 退化超过阈值，回滚该分区优化结果，或重新调整 k/权重。

建议第一阶段先实现“关键 net 高权重 + cut critical nets 指标”，第二阶段接入真实 STA 后再做 path-level group。

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

## 8. Demo 设计

本次最终交付包含两个层次的 demo：

1. **经典/调研工具 demo：`classic_partition_demo.py`**
   - 真实调用 KaHyPar Python binding，使用官方 `km1_kKaHyPar_sea20.ini` / `cut_kKaHyPar_sea20.ini` 配置；
   - 导出 hMETIS `.hgr`、cell/net 映射表，并生成 OpenROAD Partition Manager / TritonPart Tcl；
   - 用 PyTorch 实现一个小型 GCN-style partitioner，复现 CircuitPartitioning-GNN 的“图神经网络 + cut/balance loss”思路；
   - 实现 GL0AM-style logic cone grouping，复现其按逻辑 cone 分块映射 GPU block 的策略；
   - 增加 Louvain community pre-clustering 作为社区发现/预聚类 baseline。

2. **轻量 baseline demo：`netlist_split_demo.py`**
   - 用标准库实现 random/greedy/FM-style/multilevel-style baseline；
   - 用于和真实/经典工具结果对照，验证 netlist -> hypergraph -> partition -> sub-netlist 的闭环。

运行方式：

```bash
PYTHONPATH=.tooling/python python3 classic_partition_demo.py --input sample_netlist.v --k 4 --backend all --out classic_results
python3 netlist_split_demo.py --input sample_netlist.v --k 4 --algo all --out results_k4
PYTHONPATH=.tooling/python python3 -m unittest -v
```

当前环境说明：

- KaHyPar：已通过本地 `.tooling/python` Python binding 真实运行。
- OpenROAD/TritonPart：当前机器未安装 `openroad` 可执行文件，因此本 demo 生成可复现 Tcl 和 `.hgr` 输入；在装有 OpenROAD 的机器上可直接执行。
- CircuitPartitioning-GNN：未直接 vendoring 原仓库代码；本 demo 用 PyTorch 复现其 GNN partitioning 思路，用于小网表可运行验证。
- GL0AM：GL0AM 本身是 GPU gate-level simulator，不是单独 partitioner；本 demo 复现其 README 中描述的 logic-cone grouping 分块策略。

## 9. Demo 实验结果

> 本节由 `classic_partition_demo.py` 和 `netlist_split_demo.py` 实际运行结果生成/校验。小型 demo 的指标用于比较算法趋势，不代表生产级 QoR。

### 9.1 经典/调研工具 demo 结果

| Benchmark | Backend | Tool Reality | k | Cells | Nets | Cut Nets | λ-1 | Balance Max/Avg | Runtime ms | Notes |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| sample_netlist.v | KaHyPar | 真实 Python binding | 4 | 14 | 21 | 8 | 11 | 1.14 | 3.591 | `km1_kKaHyPar_sea20.ini` |
| sample_netlist.v | OpenROAD/TritonPart | 生成 `.hgr` + Tcl，当前环境未安装 `openroad` | 4 | 14 | 21 | - | - | - | - | `classic_results/openroad_tritonpart/run_tritonpart_hypergraph.tcl` |
| sample_netlist.v | CircuitGNN-style | PyTorch GCN 思路复现 | 4 | 14 | 21 | 12 | 17 | 1.14 | 711.183 | 小数据上训练不占优，仅验证 GNN 流程 |
| sample_netlist.v | GL0AM-cone-style | logic cone 分块策略复现 | 4 | 14 | 21 | 11 | 16 | 1.14 | 0.084 | 适合 simulator block grouping，不以 min-cut 为唯一目标 |
| sample_netlist.v | Louvain precluster | NetworkX 社区发现 baseline | 4 | 14 | 21 | 9 | 10 | 1.14 | 1.530 | 可作为多级 coarsening/预聚类输入 |

实验解读：

- KaHyPar 是本次 demo 中真正调用的主流超图分割器，在 k=4 上 cut nets=8，是 classic demo 中 cut-net 最优。
- OpenROAD/TritonPart 已完成输入与脚本生成；由于当前环境没有 `openroad` 二进制，未执行实际 partition。脚本使用 `triton_part_hypergraph -hypergraph_file ... -num_parts 4 ...`，和 OpenROAD `par` 文档一致。
- GNN-style demo 证明图神经网络分割流程可跑，但在 14-cell 小样例上没有质量优势；GNN 类方法需要更多训练样本和 benchmark 才有意义。
- GL0AM-style cone grouping 的目标更偏 GPU simulation locality，而不是单纯 min-cut；cut 较高是可解释的。
- Louvain precluster 能快速找到社区结构，可作为 KaHyPar/TritonPart coarsening guide，而不是最终生产级约束分割器。

### 9.2 轻量 baseline demo 结果

| Benchmark | Algorithm | k | Cells | Nets | Cut Nets | λ-1 | Balance Max/Avg | Runtime ms | Estimated Parallel Speedup |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sample_netlist.v | random | 2 | 14 | 21 | 9 | 9 | 1.00 | 0.065 | 1.52x |
| sample_netlist.v | greedy | 2 | 14 | 21 | 8 | 8 | 1.00 | 0.406 | 1.55x |
| sample_netlist.v | fm | 2 | 14 | 21 | 8 | 8 | 1.00 | 0.394 | 1.55x |
| sample_netlist.v | multilevel | 2 | 14 | 21 | 8 | 8 | 1.00 | 0.536 | 1.55x |
| sample_netlist.v | random | 4 | 14 | 21 | 10 | 13 | 1.14 | 0.079 | 1.82x |
| sample_netlist.v | greedy | 4 | 14 | 21 | 9 | 10 | 1.14 | 0.297 | 1.90x |
| sample_netlist.v | fm | 4 | 14 | 21 | 9 | 10 | 1.14 | 1.776 | 1.90x |
| sample_netlist.v | multilevel | 4 | 14 | 21 | 8 | 9 | 1.14 | 8.523 | 1.99x |

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

验收：真实设计上获得可观 wall-time 降低，且 WNS/TNS/area/power 退化在可控阈值内。

### 6 个月以上：生产级 timing-driven netlistOpt

- 接入增量 STA，形成 path-level slack budget。
- 关键路径 group constraint 与边界 repair 自动化。
- MFFC/cone-aware 与 hypergraph partitioning 混合。
- 建立分区参数自动调优：k、imbalance、critical weight、max boundary ratio。
- 与现有优化器闭环：失败回滚、局部重分割、QoR gate。

验收：在多设计、多 corner、多 PVT 条件下稳定收益，形成默认可开启的 netlistOpt 并行优化模式。

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
2. KL/FM 是理解和实现 refinement 的基础；生产级应采用多级超图分割框架。
3. KaHyPar/Mt-KaHyPar 适合作为开源高质量 backend；TritonPart/OpenROAD `par` 更贴近 EDA 约束驱动落地。
4. 对 netlistOpt 来说，单纯 min-cut 不够，必须引入 timing criticality、MFFC/logic cone、cell weight、边界 slack budget。
5. 分区后并行优化的真正验收标准不是 cut 最小，而是 wall-time 降低与 PPA/QoR 退化可控。

## 14. 质量质检报告

### 14.1 系统总览

本次压缩执行采用以下 Agent 协作：

| Agent | 职责 | 产出 |
| --- | --- | --- |
| PM/架构 Agent | 将 14 天计划压缩为 2 天交付路线，定义验收物 | 报告结构、Demo 验收标准、路线图 |
| 调研 Agent | 调研 graph/hypergraph、KL/FM/谱/多级/社区发现/timing-driven | 算法与工具对比、参考资料 |
| Demo 编码 Agent | 实现经典工具 demo 与轻量 baseline | `classic_partition_demo.py`、`netlist_split_demo.py`、`sample_netlist.v`、`README.md` |
| 集成/QA Agent | 跑单测和示例实验，补齐输出目录能力 | `classic_results/`、`results_k2/`、`results_k4/`、真实实验表 |
| 评审/安全 Agent | 检查依赖、可复现性、风险边界 | 最终签字结论 |

### 14.2 QA 测试结果

已执行：

```bash
PYTHONPATH=.tooling/python python3 -m unittest -v
PYTHONPATH=.tooling/python python3 classic_partition_demo.py --input sample_netlist.v --k 4 --backend all --out classic_results
python3 netlist_split_demo.py --input sample_netlist.v --k 2 --algo all --out results_k2
python3 netlist_split_demo.py --input sample_netlist.v --k 4 --algo all --out results_k4
```

结果：

- 单元测试：`Ran 6 tests ... OK`
- KaHyPar：真实 Python binding 运行成功，k=4 时 cut nets=8、λ-1=11。
- OpenROAD/TritonPart：`.hgr` 与 Tcl 脚本生成成功；当前环境未安装 `openroad`，未本机执行。
- CircuitGNN-style / GL0AM-cone-style / Louvain baseline：均运行成功并生成 `metrics.json`、`partitions.tsv`、子网表骨架。
- k=2 示例：4 个算法全部运行成功，生成 8 个子网表文件。
- k=4 示例：4 个算法全部运行成功，生成 16 个子网表文件。
- 依赖状态：baseline demo 无第三方依赖；classic demo 使用本地 `.tooling/python/kahypar`、系统已有 `torch` 与 `networkx`。

### 14.3 评审签字结论

- **功能完整性**：通过。Demo 已覆盖 netlist 解析、hMETIS/KaHyPar 超图导出、真实 KaHyPar 分割、OpenROAD/TritonPart Tcl 生成、GNN-style 分割、GL0AM-style cone grouping、指标输出、结果目录与子网表骨架生成。
- **报告完整性**：通过。已覆盖背景、问题定义、主流算法、工具对比、timing 保护、并行优化流程、实验结果、路线图和风险。
- **工程风险**：可接受。当前 demo 不承诺生产级 Verilog 完整解析或真实 STA QoR；OpenROAD/TritonPart 需要在安装 OpenROAD 的环境中执行；这些已在路线图中列为中长期工作。
- **最终结论**：可以作为 netlistOpt 图分割方向的 2 天压缩交付版本，用于内部技术评审和后续 PoC 立项。

## 15. 参考链接

- https://vlsicad.ucsd.edu/Publications/Journals/index.html
- https://vlsicad.ucsd.edu/Publications/Conferences/401/c401_camera.pdf
- https://openroad.readthedocs.io/en/latest/main/src/par/README.html
- https://github.com/ABKGroup/TritonPart
- https://kahypar.org/
- https://github.com/kahypar/kahypar
- https://github.com/kahypar/mt-kahypar
- https://karypis.github.io/glaros/files/sw/hmetis/manual.pdf
- https://dl.acm.org/doi/10.5555/800263.809204
- https://ieeexplore.ieee.org/document/6771089/
- https://people.eecs.berkeley.edu/~alanmi/publications/2007/iwls07_ifs.pdf
- https://web.eecs.umich.edu/~imarkov/pubs/book/part_survey.pdf
