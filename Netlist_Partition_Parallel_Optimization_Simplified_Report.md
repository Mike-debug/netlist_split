# EDA netlist 分割与并行优化简化版报告

> 定位：简化版说明，用于快速理解 netlist 分割方法和自研 EDA 落地思路  
> 核心问题：netlistOpt 很慢，能否把大网表拆成多个小块并行优化，同时不破坏时序和 PPA。

## 1. 一句话结论

netlist 分割不是简单把 `.v` 文件切成几份。主流算法真正处理的是图、超图或 EDA 内存数据库里的连接关系，再把这些连接关系拆成多个可并行优化的工作单元。

推荐路线是：

1. 用图/超图算法把强相关的逻辑尽量放在同一个分区；
2. 用 STA 信息保护关键路径，避免把低 slack 路径随便切开；
3. 给每个分区生成局部约束和 timing budget；
4. 多个分区并行做 netlistOpt；
5. 合并后重新跑全局 STA，检查 WNS/TNS、power、area 是否可接受；
6. 如果某个分区优化结果破坏全局 QoR，则只回滚或修复该分区。

这件事的目标不是“分割结果看起来漂亮”，而是让 netlistOpt 的总运行时间下降，同时把 PPA 风险控制住。

## 2. 为什么 netlistOpt 会慢

netlistOpt 通常会做 gate sizing、buffer insertion、logic rewriting、fanout repair、setup/hold repair 等操作。每做一个操作，都需要知道它对 timing、load、fanout、power、area 的影响。

慢的根因有三个：

| 原因 | 解释 |
| --- | --- |
| 全局依赖强 | 一个 cell 的变化可能影响跨层级、跨模块、跨 clock domain 的路径 |
| STA 计算慢 | STA 要计算 AAT、RAT、slack、slew、load，且需要考虑 corner/mode/exception |
| 优化候选多 | 优化器会反复尝试很多局部变换，每轮都要判断是否有效 |

如果所有操作都依赖全局 STA 串行判断，运行时间很容易成为瓶颈。

分割的价值是把大问题拆成多个相对独立的小问题，让多个 CPU 线程/进程并行工作。

## 3. 当前主流 netlist 分割方法

### 3.1 普通图分割

把 cell 看成点，把 cell 之间的连接看成边。

常见工具/算法：

- METIS
- Louvain 社区发现
- 谱分割
- KL / FM 的普通图版本

优点：

- 实现简单；
- 工具成熟；
- 速度快；
- 适合做 baseline。

缺点：

- netlist 里的一个 net 可能连接一个 driver 和多个 sink，普通图需要把它拆成很多二元边，会损失真实连接语义；
- 对高扇出 net、clock/reset/enable 等信号表达不够自然。

结论：普通图分割适合做快速验证和 baseline，不建议作为最终生产主算法。

### 3.2 超图分割

把 cell 看成点，把 net 看成超边。一个 net 可以同时连接多个 cell，这更符合真实电路结构。

主流工具：

| 工具 | 简要说明 |
| --- | --- |
| hMETIS | VLSI 领域经典超图分割工具，但当前官方渠道有授权限制 |
| PaToH | 经典超图分割器，学术/研究验证常见 |
| KaHyPar | 开源高质量超图分割框架，适合接入自研系统做实验 |
| Mt-KaHyPar | 多线程版本，更适合大规模设计 |
| TritonPart / OpenROAD par | 更贴近 EDA 约束驱动分割，适合参考工程实现 |

优点：

- 更符合 netlist 真实结构；
- 对 cut net、fanout、connectivity 的建模更准确；
- 适合大规模电路分割。

缺点：

- 工具集成成本高于普通图；
- 参数较多；
- 若只看 cut，不看 timing，仍然可能切坏关键路径。

结论：超图分割是公司后续落地的主路线。

### 3.3 多级分割

现代主流分割工具通常都采用多级思想：

```text
原始大图
  -> coarsening：把强相关 cell 合并成粗粒度节点
  -> initial partition：在小图上做初始分割
  -> uncoarsening/refinement：逐步展开，并持续微调分区
  -> 输出最终 partition
```

这类方法能在质量和速度之间取得较好平衡。

典型代表：

- METIS
- hMETIS
- PaToH
- KaHyPar
- Mt-KaHyPar
- TritonPart

结论：如果要支持百万级甚至千万级 instance，最终应该采用多级分割框架。

### 3.4 Timing-driven / constraint-driven 分割

只按连接关系切分是不够的。EDA 优化真正关心 PPA，尤其是 timing。

Timing-driven 分割会把 STA 结果加入分割目标：

| STA 信息 | 在分割中的作用 |
| --- | --- |
| 低 slack path | 尽量不要切开 |
| high fanout net | 单独建模，避免边界 load/slew 失真 |
| clock/reset/scan | 通常需要特殊保护 |
| AAT/RAT | 用于生成分区边界 timing budget |
| critical path group | 可以作为 fixed group 或高权重约束 |

结论：生产可用的 netlist 分割不能只做 min-cut，必须做 timing-aware。

### 3.5 Logic cone / MFFC 分割

对逻辑优化来说，一个自然的工作单元是 logic cone 或 MFFC。

直观理解：

- 一段逻辑 cone 内部关系很强；
- cone 的外部接口相对少；
- 在 cone 内做 rewriting 或局部替换，更容易控制影响范围。

优点：

- 非常适合逻辑优化；
- 边界接口清晰；
- 易于做局部 rollback。

缺点：

- cone 大小可能不均衡；
- 跨 cone 的 timing path 仍然需要 STA 保护。

结论：公司自研 netlistOpt 可以把超图分割和 cone-aware 分割结合起来。

## 4. 对公司自研 EDA 的核心设计思想

### 4.1 主流分割算法不是直接针对 `.v` 文件

Verilog `.v` 文件是 netlist 的一种文本表达，但主流分割算法通常不直接在 `.v` 文本上工作。

真实流程一般是：

```text
.v / DB / OpenDB / internal DesignDB
  -> 解析成 instance / net / pin / timing arc
  -> 抽取 graph 或 hypergraph
  -> 调用分割算法
  -> 得到每个 instance 的 partition_id
```

也就是说：

| 层次 | 作用 |
| --- | --- |
| `.v` 文件 | 输入/输出格式，便于交换和调试 |
| 内存 netlist 数据库 | 优化器真正操作的数据模型 |
| graph / hypergraph | 分割算法真正使用的数学模型 |
| partition_id | 分割结果，回写到内存对象或数据库对象上 |

因此，当前主流算法关注的是“cell 和 net 如何连接”，而不是 Verilog 文本本身。`.v` 可以作为数据来源，但不是算法的核心对象。

### 4.2 Adapter 层和 `.graph` / `.hgr` / `.u` 接口文件

公司自研 EDA 一开始不一定能识别 `.graph`、`.hgr`、`.u` 这些格式，这是正常的。这些格式不是要求 EDA 主流程天然支持的设计文件，而是外部分割工具的接口文件。

更合理的做法是增加一层 adapter：

```text
公司内部 DesignDB
  -> Adapter 抽取 instance / net / pin
  -> 导出 .graph / .hgr / .u 或直接构建 API 数组
  -> 调用 METIS / KaHyPar / Mt-KaHyPar / PaToH / TritonPart
  -> 读回 partition result
  -> 把 partition_id 写回公司内部 DesignDB
```

几个常见接口的含义如下：

| 接口文件 | 主要给谁用 | 含义 |
| --- | --- | --- |
| `.graph` | METIS | 普通图邻接表，描述 cell 与 cell 之间的连接 |
| `.hgr` | hMETIS / KaHyPar / Mt-KaHyPar | 超图格式，每一行通常表示一个 net 连接了哪些 cell |
| `.u` | PaToH | PaToH 自己的超图输入格式 |
| `.part` / partition result | 多数分割器 | 每个 cell 对应一个分区编号 |

这些格式的作用类似“翻译中间件”。公司 EDA 不需要把它们当作主数据模型，只需要 adapter 能导出和读回即可。

如果后续做生产化集成，更推荐走内存 API：

```text
DesignDB
  -> hyperedge index array
  -> pin list array
  -> cell weight array
  -> net weight array
  -> partitioner API
  -> partition_id array
```

这样可以减少文件 I/O，也更容易和内存中的 STA、优化器、ECO delta 机制结合。

### 4.3 不以 `.v` 文件作为公司自研流程的分割核心

在自研 EDA 中，真实优化对象通常不是 Verilog 文本文件，而是内存中的设计数据库。

也就是说，分割对象应该是：

```text
DesignDB / NetlistDB
  instance objects
  net objects
  pin objects
  timing arc objects
  constraint objects
  library cell objects
  parasitic / load / slew data
```

`.v` 文件只是输入/输出格式之一，不应该作为并行优化的核心数据模型。

推荐原则：

- 分割算法输入的是内存对象 ID，而不是字符串形式的 Verilog；
- partition 结果写回到内存对象的 metadata；
- 子网表可以作为调试产物导出，但不是主流程必须依赖的中间格式；
- SDC 也不一定要写成文本 `.sdc` 文件，可以在内存中生成 constraint view。

### 4.4 建议的内存模型

建议在现有 EDA 数据库上增加一层 Partition Runtime Layer：

```text
Global Design Snapshot
  immutable netlist view
  immutable library view
  immutable top-level constraint view
  global STA baseline

Partition Runtime Layer
  partition_id for each instance
  boundary net table
  boundary pin table
  partition constraint view
  partition timing budget
  partition-local ECO delta
  rollback checkpoint

Merge / Signoff Layer
  apply selected ECO delta
  rebuild affected timing graph
  incremental global STA
  QoR comparison
```

关键点：

| 模块 | 建议 |
| --- | --- |
| Global Design Snapshot | 作为只读基线，所有分区共享，避免复制完整 netlist |
| Partition View | 只保存本分区 instance/net/pin 的 ID 集合，不复制完整对象 |
| Boundary Table | 记录 cut net、driver/sink 所属分区、边界 load/slew |
| Timing Budget Table | 记录每个边界 pin 的 AAT/RAT/slack budget |
| ECO Delta | 每个分区只记录自己的修改，不直接改全局数据库 |
| Rollback Checkpoint | 如果某个分区导致 QoR 变差，只回滚该分区 |

这种方式比“导出多个 `.v` 文件再读回来”更适合公司自研 EDA，因为它减少 I/O、减少解析成本，也更容易和 STA、优化器共享数据。

## 5. 分割后 SDC 怎么安排

### 5.1 顶层 SDC 不能直接复制给每个分区

顶层 SDC 描述的是完整设计。如果直接把完整 SDC 丢给每个分区，会有几个问题：

- 分区内看不到完整 clock source；
- 有些 false path / multicycle path 只对局部有效；
- 输入输出 delay 需要根据边界重新计算；
- 局部 STA 可能出现过约束或欠约束。

因此，每个分区需要的是 partition constraint view。

### 5.2 Partition SDC 的内容

每个 partition 的约束应包含：

| 类型 | 内容 |
| --- | --- |
| 时钟约束 | create_clock、generated clock、latency、uncertainty |
| 输入边界约束 | cut input pin 的 input delay、transition、driving 信息 |
| 输出边界约束 | cut output pin 的 output delay、load |
| timing exception | false path、multicycle path、min/max delay 的局部映射 |
| design rule | max slew、max cap、max fanout、dont_touch、dont_use |
| 边界保护 | clock/reset/scan/cut net 的保护策略 |

在公司自研系统中，这些内容可以不落成 `.sdc` 文本，而是内存里的 `ConstraintView`。

例如：

```text
PartitionConstraintView {
  partition_id
  clocks
  generated_clocks
  input_delay_budget
  output_delay_budget
  exception_mapping
  design_rule_constraints
  protected_boundary_objects
}
```

只有在 debug、复现、和第三方工具对接时，才需要把它导出成 `.sdc`。

## 6. 分割后 STA 怎么安排

### 6.1 全局 STA 与局部 STA 的关系

全局 STA 是最终裁判，局部 STA 是加速器。

| STA 类型 | 作用 |
| --- | --- |
| 全局 STA | 在完整设计上计算真实 timing，负责 signoff 和最终 QoR 判断 |
| 局部 STA | 在每个 partition 内快速评估优化操作是否值得做 |

局部 STA 不能替代全局 STA，因为跨分区路径、clock reconvergence、global parasitic 等信息只有全局视图最完整。

### 6.2 AAT/RAT 如何用于分区边界

对每个被切开的边界 pin，需要从全局 STA 抽取：

| 数据 | 含义 | 用途 |
| --- | --- | --- |
| AAT late | 最晚到达时间 | 生成输入边界 setup budget |
| AAT early | 最早到达时间 | 生成输入边界 hold budget |
| RAT late | 最晚要求时间 | 生成输出边界 setup budget |
| RAT early | 最早要求时间 | 生成输出边界 hold budget |
| slew | 边界信号斜率 | 局部 STA 计算 delay |
| load | 下游负载 | 局部 STA 计算输出影响 |

直观理解：

- 如果一个信号从别的分区进入当前分区，当前分区需要知道“这个信号已经花掉了多少时间”；
- 如果一个信号从当前分区输出到别的分区，当前分区需要知道“必须给下游留下多少时间”。

这就是 timing budget。

### 6.3 局部 STA 的运行方式

每个分区可以独立运行局部 STA：

```text
Partition i
  input:
    partition netlist view
    partition constraint view
    boundary timing budget
    local parasitic/load estimate
  run:
    local STA
    local netlistOpt
    incremental STA
  output:
    ECO delta
    local WNS/TNS delta
    boundary AAT/RAT delta
```

每个分区优化完成后，不直接宣布成功，而是交给全局 merge 验证。

## 7. 并行优化整体流程

推荐流程如下：

```text
1. 建立全局基线
   读取 netlist / liberty / SDC / parasitic
   跑全局 STA，得到 baseline WNS/TNS/area/power

2. 构建分割图
   从内存 DesignDB 抽取 instance/net/pin/timing path
   构建 graph/hypergraph

3. 加入 timing 权重
   critical path 提高权重
   clock/reset/scan 特殊处理
   high fanout net 单独建模

4. 执行分割
   得到 partition_id
   生成 boundary net/pin table

5. 分派约束和 timing budget
   生成 PartitionConstraintView
   生成 BoundaryTimingBudget

6. 并行优化
   每个 partition 独立做局部 STA 和 netlistOpt
   生成 ECO delta

7. 合并验证
   将 ECO delta 合并到全局设计
   跑 incremental/global STA
   检查 WNS/TNS/area/power

8. 修复或回滚
   如果 QoR 变差，定位责任 partition
   局部修复、重分配 budget 或 rollback
```

## 8. 推荐落地架构

建议把系统拆成 7 个模块：

| 模块 | 主要职责 |
| --- | --- |
| Partition Graph Builder | 从内存 netlist/STA 中构建 graph/hypergraph |
| Partition Engine Adapter | 对接 KaHyPar/Mt-KaHyPar/TritonPart/METIS，负责 API 或 `.graph`/`.hgr`/`.u` 文件交互 |
| Boundary Extractor | 识别 cut net、boundary pin、cross-partition path |
| Constraint Dispatcher | 生成每个分区的约束视图和 timing budget |
| Parallel Optimizer Scheduler | 调度多个 partition 并行运行 netlistOpt |
| ECO Merge Manager | 合并各分区 ECO delta，处理冲突和版本 |
| Global QoR Validator | 跑全局 STA/PPA 检查，决定接受、修复或回滚 |

建议的数据流：

```text
DesignDB + STA baseline
  -> Partition Graph Builder
  -> Partition Engine
  -> Boundary Extractor
  -> Constraint Dispatcher
  -> Parallel Optimizer Scheduler
  -> ECO Merge Manager
  -> Global QoR Validator
```

## 9. 内存与并发策略

### 9.1 不建议每个分区复制一份完整 DesignDB

完整复制有几个问题：

- 内存占用过大；
- 多份数据容易不一致；
- merge 复杂；
- STA cache 难复用。

更推荐：

```text
共享只读全局设计 + 每个分区自己的增量修改
```

也就是：

| 数据 | 共享还是私有 |
| --- | --- |
| cell/net/pin 基础对象 | 全局共享，只读 |
| liberty / cell delay model | 全局共享，只读 |
| 顶层 SDC 原始约束 | 全局共享，只读 |
| partition membership | 全局共享，可版本化 |
| partition constraint view | 分区私有 |
| local STA cache | 分区私有 |
| ECO delta | 分区私有 |
| final merged design | 全局统一提交 |

### 9.2 ECO Delta 模型

每个分区不直接修改全局 netlist，而是输出修改记录：

```text
EcoDelta {
  partition_id
  added_cells
  removed_cells
  resized_cells
  inserted_buffers
  reconnected_nets
  changed_attributes
  local_timing_summary
  boundary_delta
}
```

好处：

- 可以做 code review 式的 merge；
- 可以检查两个分区是否同时修改同一个边界对象；
- 可以局部 rollback；
- 可以记录每次优化的收益和风险。

### 9.3 边界对象的并发规则

跨分区边界是最容易出问题的地方。建议规则：

| 对象 | 并发策略 |
| --- | --- |
| 分区内部 cell | 当前分区可自由优化 |
| 分区内部 net | 当前分区可自由优化 |
| boundary pin | 需要受 timing budget 约束 |
| cut net driver | 只能由 driver 所在分区或全局 repair 修改 |
| cut net sink | sink 所在分区可优化 sink 侧 load，但不能破坏接口 |
| clock/reset/scan net | 默认只允许全局 repair 或专门 pass 修改 |

## 10. 三阶段规划

### 阶段一：先证明闭环能跑

周期：1 到 2 个月。

目标：

- 从内存 netlist 抽取 graph/hypergraph；
- 支持 k=2/4/8 分割；
- 输出 partition_id、cut net、boundary pin；
- 接入一个开源分割器，例如 KaHyPar 或 Mt-KaHyPar；
- 构造 PartitionConstraintView 的雏形；
- 并行跑一个简单 netlistOpt stub；
- merge 后跑全局 STA 验证。

验收：

- 3 个真实设计可跑通；
- 结果可复现；
- 能看到分区均衡、cut net、runtime、QoR delta。

### 阶段二：做 timing-aware 并行优化

周期：3 到 6 个月。

目标：

- 接入真实 STA AAT/RAT/slack；
- 给 critical path / high fanout / clock/reset 加权；
- 生成较完整的 partition constraint view；
- 局部优化使用局部 STA 快速判断收益；
- merge 后支持增量全局 STA；
- 建立回滚策略。

验收：

- 与不分割的全局 netlistOpt 对比；
- wall time 有明确下降；
- WNS/TNS/area/power 在可控阈值内；
- 失败 case 可以定位到具体 partition。

### 阶段三：生产化

周期：6 个月以上。

目标：

- 多 mode、多 corner 支持；
- 更完整的 exception 映射；
- 增量 STA cache 复用；
- partition 参数自动调优；
- 支持局部重分割；
- 支持 QoR gate 和自动 rollback；
- 与现有优化器深度融合。

验收：

- 多个真实项目稳定收益；
- 有完整日志、指标和回归；
- 可以作为 netlistOpt 的可选并行模式上线。

## 11. 简化版报告建议关注的关键指标

| 指标 | 为什么重要 |
| --- | --- |
| wall time | 最直接的业务收益 |
| WNS/TNS delta | 确认没有破坏 timing |
| area/power delta | 确认没有用面积/功耗换速度 |
| cut net 数量 | cut 越多，边界越复杂 |
| critical cut ratio | 关键路径被切太多会增加风险 |
| balance | 分区不均衡会拖慢并行速度 |
| rollback 次数 | 反映局部优化是否稳定 |
| memory overhead | 分区并行后内存不能失控 |

## 12. 风险与控制

| 风险 | 说明 | 控制方法 |
| --- | --- | --- |
| 分区切坏关键路径 | WNS/TNS 变差 | critical path 加权，merge 后全局 STA |
| SDC 派生错误 | 局部 STA 误判 | 约束映射可追溯，建立 constraint diff |
| 边界 load/slew 不准 | 局部优化结果合并后失真 | 边界加 guardband，全局复核 |
| 内存复制过多 | 并行后内存爆炸 | 共享只读 DesignDB，分区只存 delta |
| ECO 冲突 | 多个分区同时改边界 | boundary ownership 和 merge manager |
| 工具集成成本高 | 影响上线速度 | 先定义统一 adapter，再替换后端 |
| 小设计收益不明显 | 并行调度成本超过收益 | 设置启用阈值，只对大设计开启 |

## 13. 建议的最终路线

短期不建议一上来就做复杂的全自动 timing-driven partitioner。更稳妥的路线是：

1. 先把内存 netlist 抽图、分割、打 partition_id、生成 boundary table 做扎实；
2. 接入 KaHyPar/Mt-KaHyPar 作为主分割后端，METIS 做 graph baseline；
3. 把 STA 的 AAT/RAT/slack 接入 boundary timing budget；
4. 让每个分区先跑保守的局部优化，只允许分区内部 ECO；
5. merge 后必须全局 STA 验证；
6. 再逐步放开更激进的边界优化和跨分区 repair。

用一句话概括：

```text
先把 netlist 分得稳，再把 STA budget 分得准，最后再把并行优化放开。
```

这样最适合公司自研 EDA：既能复用已有内存数据库和 STA，又能逐步获得并行加速，不需要把流程退化成“反复导出/导入 .v 文件”的低效模式。
