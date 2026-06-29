下面给你一个**14天内可执行、可量化**的 netlistOpt 图分割调研+方案报告计划，按天划分，并明确每个阶段的产出和验收标准。你可以直接按这个计划执行和汇报进度。

---

## 一、整体目标与验收标准
**最终目标（14天后）：**

1. 完成一份 **netlistOpt 图分割调研报告 + 落地方案**（PPT/PDF，15–25 页）。
2. 完成一个 **最小可运行的 demo / 开源库验证**：
    - 能对一个小型 netlist 做超图分割；
    - 能生成若干子网表；
    - 能跑一个简单的并行优化（或至少演示“可并行”的流程）。
3. 给出一个 **可落地的工程推进路线**（短期/中期/长期）。

**验收标准：**

+ 报告：
    - 有清晰的背景、问题定义、方法分类、工具对比、时序保护与 Slack 恢复策略、落地方案。
    - 至少包含一个 demo 实验结果或明确实验计划。
+ Demo：
    - 能跑通一个从 netlist → 超图 → 分割 → 子网表生成的流程；
    - 有至少 1–2 个 benchmark 的结果（runtime / cut size / 分区数等）。
+ 推进路线：
    - 明确 1–2 个月、3–6 个月、6 个月+ 的工作内容和里程碑。

---

## 二、阶段划分（14天）
整体分为 4 个阶段：

1. **阶段1：资料搜集与初步理解（Day 1–3）**
2. **阶段2：方案设计与 Demo 设计（Day 4–5）**
3. **阶段3：Demo / 开源库验证与实验（Day 6–10）**
4. **阶段4：报告撰写与评审准备（Day 11–14）**

---

## 三、详细计划（按天）
### 阶段1：资料搜集与初步理解（Day 1–3）
#### Day 1：目标确认 + 资料清单整理
**目标：**

+ 明确报告纲要和资料清单；
+ 完成初步资料搜索和整理。

**任务：**

1. 确认报告结构（使用之前给的大纲）。
    - 产出：报告大纲（1 页，列出章节标题和每节要写什么）。
2. 整理资料清单：
    - 必读书目/论文：
        * “Recent directions in netlist partitioning: a survey” [vlsicad.ucsd](https://vlsicad.ucsd.edu/Publications/Journals/j19.pdf)
        * TritonPart 论文（ICCAD 2023） [wteb.njit](https://web.njit.edu/~ikoutis/papers/iccad23.pdf)
        * MFFC 论文 [cecs.uci](https://www.cecs.uci.edu/~papers/compendium94-03/papers/1995/aspdac95/pdffiles/8a_1.pdf)
        * 逻辑优化框架评述（MFFC + 自适应分割 + KaHyPar + 并行优化） [themoonlight](https://www.themoonlight.io/zh/review/an-open-source-end-to-end-logic-optimization-framework-for-large-scale-boolean-network-with-reinforcement-learning)
    - 必逛 GitHub：
        * TritonPart: [https://github.com/ABKGroup/TritonPart](https://github.com/ABKGroup/TritonPart) [github](https://github.com/ABKGroup/TritonPart)
        * KaHyPar: [https://github.com/kahypar/kahypar](https://github.com/kahypar/kahypar) [kahypar github]
        * OpenROAD src/par
        * GL0AM: [https://github.com/NVlabs/GL0AM](https://github.com/NVlabs/GL0AM) [github](https://github.com/NVlabs/GL0AM)
        * CircuitPartitioning-GNN: [https://github.com/AnitaSoroush/CircuitPartitioning-GNN](https://github.com/AnitaSoroush/CircuitPartitioning-GNN) [github](https://github.com/AnitaSoroush/CircuitPartitioning-GNN)
    - 工具：
        * hMETIS / METIS（下载或查找文档）。
3. 建立资料库：
    - 在本地创建文件夹：
        * `papers/`：PDF 论文
        * `github/`：相关仓库链接 + 简要说明
        * `notes/`：读书笔记
4. 产出：
    - 报告大纲（1 页）；
    - 资料清单 + 下载链接表（1 页）。

**量化指标：**

+ 报告大纲 1 份；
+ 资料清单 1 份（至少 10 条：论文 + GitHub + 工具）；
+ 至少下载/收藏 3 篇核心论文 PDF。

---

#### Day 2：精读综述 + 理解问题定义
**目标：**

+ 读完综述，建立对网表分割问题的整体认知；
+ 明确问题形式化、方法分类。

**任务：**

1. 精读：
    - “Recent directions in netlist partitioning: a survey” 。 [sciencedirect](https://www.sciencedirect.com/science/article/pii/0167926095000084)
2. 笔记重点：
    - 问题形式化：
        * min-cut / ratio-cut / multi-way / constraint-driven；
    - 方法分类：
        * move-based / spectral / combinatorial / clustering；
    - benchmark 和评价指标：
        * cut size、connectivity、area balance、timing 等。
3. 产出：
    - 读书笔记 1–2 页（可以用 Markdown 或 Word）；
    - 在报告草稿中写“背景与问题定义”部分的初稿（1–2 页）。

**量化指标：**

+ 完成 1 篇综述精读；
+ 读书笔记 ≥ 1 页；
+ 报告“背景与问题定义”部分初稿 ≥ 1 页。

---

#### Day 3：精读 TritonPart + MFFC + 逻辑优化框架
**目标：**

+ 理解时序驱动分割 + 约束驱动分割；
+ 理解 MFFC + 自适应分割 + 并行优化的思路。

**任务：**

1. 精读：
    - TritonPart 论文（ICCAD 2023）： [ieeexplore.ieee](https://ieeexplore.ieee.org/document/10323975/)
        * 关注 timing-driven rating function、constraint 支持；
    - MFFC 论文 ： [cecs.uci](https://www.cecs.uci.edu/~papers/compendium94-03/papers/1995/aspdac95/pdffiles/8a_1.pdf)
        * MFFC 定义、构造方法、在聚类/分割中的应用；
    - 逻辑优化框架评述 ： [themoonlight](https://www.themoonlight.io/zh/review/an-open-source-end-to-end-logic-optimization-framework-for-large-scale-boolean-network-with-reinforcement-learning)
        * 自适应分割 + MFFC + KaHyPar/DagP + 并行优化流程。
2. 笔记重点：
    - TritonPart：
        * 如何把 timing 信息融入分割；
        * 有哪些 constraint 类型；
    - MFFC：
        * 如何作为逻辑结构单元；
        * 与超图分割如何结合；
    - 逻辑优化框架：
        * “分割 → 子电路并行优化 → 合并”的完整流程。
3. 产出：
    - 3 篇笔记，每篇 0.5–1 页；
    - 在报告草稿中写“时序关键路径保护 + Slack 恢复”部分的初稿（1–2 页）。

**量化指标：**

+ 完成 3 篇核心论文/评述精读；
+ 笔记总页数 ≥ 2 页；
+ 报告“时序保护 + Slack 恢复”部分初稿 ≥ 1 页。

---

### 阶段2：方案设计与 Demo 设计（Day 4–5）
#### Day 4：设计总体方案 + 选择 Demo 技术路线
**目标：**

+ 明确 netlistOpt 的图分割整体方案；
+ 确定 Demo 使用的工具和流程。

**任务：**

1. 设计总体方案：
    - 参考之前给的“分区后并行优化流程设计思路”章节；
    - 决定：
        * 使用哪个分割器（TritonPart / KaHyPar / 两者都试）；
        * 是否启用 timing-driven；
        * 分区数 k 的取值（如 2, 4, 8）。
2. 选择 Demo 技术路线：
    - 推荐方案：
        * 使用 TritonPart 或 KaHyPar；
        * 使用开源 benchmark（如 EPFL、OPDB、VTR）或一个小 netlist；
        * 用 Python/C++ 写一个简单 wrapper，把 netlist → 超图 → 分割 → 子网表。
    - 备选方案：
        * 直接研究 OpenROAD 的 `src/par`，跑 OpenROAD 流程。
3. 产出：
    - 方案蓝图（1 页）：
        * 流程：netlist → 超图 → 分割 → 子 netlist → 并行优化 → 合并；
        * 工具选择理由；
        * 关键设计点（timing protection, slack recovery, 回退机制）。
    - Demo 设计文档（1–2 页）：
        * 输入：benchmark 名称、规模；
        * 工具：TritonPart/KaHyPar + 语言；
        * 指标：cut size、分区数、runtime；
        * 实验变量：k = 2/4/8。

**量化指标：**

+ 方案蓝图 ≥ 1 页；
+ Demo 设计文档 ≥ 1 页；
+ 明确工具选择（至少 1 个）。

---

#### Day 5：准备 Demo 环境 + 数据 + 简单脚本
**目标：**

+ 完成 Demo 环境搭建；
+ 准备 1–2 个 netlist / 超图数据；
+ 写出最简单的 netlist → 超图 → 分割脚本框架。

**任务：**

1. 环境准备：
    - 安装：
        * KaHyPar（C++/Python）或 TritonPart（基于 OpenROAD）；
        * 若用 Python：安装相关依赖；
        * 确保能运行示例命令。
2. 数据准备：
    - 找 1–2 个开源 benchmark：
        * 如 EPFL logic synthesis benchmarks；
        * 或任何 small gate-level netlist（Verilog）；
    - 如无法直接拿到 netlist，先用开源综合工具（如 Yosys）从 RTL 生成 gate-level netlist。
3. 脚本框架：
    - 写一个简单脚本（Python/C++）：
        * 读取 netlist；
        * 构建超图（顶点=单元，超边=net）；
        * 调用 KaHyPar/TritonPart 做分割；
        * 输出分区信息和子网表（至少能打印每个分区包含哪些单元）。
4. 产出：
    - 环境搭建笔记（1 页）：
        * 安装步骤、命令、遇到的问题；
    - Demo 脚本 v0.1（能跑通最小流程）；
    - 1–2 个 benchmark 数据。

**量化指标：**

+ 完成环境搭建，能成功运行工具示例；
+ 有 1–2 个 benchmark；
+ Demo 脚本 v0.1 能跑通一个最小流程（netlist → 分割 → 输出分区）。

---

### 阶段3：Demo / 开源库验证与实验（Day 6–10）
#### Day 6：Demo 跑通 + 初步结果
**目标：**

+ 跑通完整流程；
+ 得到初步实验结果。

**任务：**

1. 运行 Demo：
    - 对 1 个 benchmark：
        * k = 2, 4；
    - 记录：
        * 超图规模（顶点数、超边数）；
        * 分区结果（cut size、每个分区大小）；
        * runtime。
2. 简单分析：
    - cut size 随 k 变化的趋势；
    - 分区是否均衡。
3. 产出：
    - 实验结果表（1 页）：
        * benchmark、k、cut size、分区大小、runtime；
    - Demo 脚本 v0.2（稍微整理，增加日志输出）。

**量化指标：**

+ 对至少 1 个 benchmark 跑通流程；
+ 有 2–3 组实验结果（不同 k）；
+ 实验结果表 ≥ 0.5 页。

---

#### Day 7：增加 benchmark + 多组实验
**目标：**

+ 增加 benchmark 数量；
+ 得到更充分的实验数据。

**任务：**

1. 对 2–3 个 benchmark：
    - k = 2, 4, 8；
2. 记录：
    - cut size、分区大小、runtime；
    - 超图规模。
3. 简单画图（可选）：
    - k vs cut size；
    - k vs runtime。
4. 产出：
    - 实验结果表扩展（1 页）；
    - Demo 脚本 v0.3（支持批量实验）。

**量化指标：**

+ benchmark 数量 ≥ 2；
+ 实验组数 ≥ 6；
+ 实验结果表 ≥ 1 页。

---

#### Day 8：尝试 timing-driven / 简单时序保护（可选）
**目标：**

+ 如果工具支持 timing-driven，尝试加入简单时序保护；
+ 或至少设计一个简单策略。

**任务：**

1. 若 TritonPart/KaHyPar 支持 timing：
    - 尝试：
        * 给关键 net 高权重；
        * 或启用 timing constraint。
2. 若不支持：
    - 设计一个简单策略：
        * 在构建超图时，对某些 net 设置高权重；
        * 观察 cut size 和分区变化。
3. 产出：
    - timing-driven 实验笔记（0.5–1 页）；
    - Demo 脚本 v0.4（支持权重调整）。

**量化指标：**

+ 至少尝试 1 组 timing-driven 或权重调整实验；
+ 有对比结果（普通 vs timing-driven）。

---

#### Day 9：分析实验结果 + 提炼结论
**目标：**

+ 系统分析实验结果；
+ 提炼对 netlistOpt 有意义的结论。

**任务：**

1. 分析：
    - runtime 随 k 变化的趋势；
    - cut size 随 k 变化的趋势；
    - 分区均衡性；
    - timing-driven / 权重调整的效果。
2. 结论：
    - 在什么情况下分区加速效果好；
    - 什么情况下 cut size 过大，可能影响 QoR；
    - timing-driven 对关键路径保护的效果。
3. 产出：
    - 实验分析笔记（1–2 页）；
    - 在报告草稿中写“实验结果与初步分析”部分（1–2 页）。

**量化指标：**

+ 实验分析笔记 ≥ 1 页；
+ 报告“实验结果”部分初稿 ≥ 1 页。

---

#### Day 10：整理 Demo + 准备进入报告阶段
**目标：**

+ 整理 Demo 代码和结果；
+ 确保报告中有清晰的 Demo 描述和结果。

**任务：**

1. 整理：
    - Demo 脚本 v1.0（加注释、README）；
    - 实验结果和图（CSV/表格/简单图）。
2. 写 Demo 说明：
    - 1 页 README：
        * 环境、依赖、如何运行、输入输出、指标。
3. 产出：
    - Demo v1.0（代码 + README）；
    - Demo 说明文档 1 页；
    - 报告“开源工具与 Demo 方案对比”和"Demo 实验设计”部分初稿（各 1 页）。

**量化指标：**

+ Demo v1.0 可运行；
+ README 1 页；
+ 报告相关部分初稿 ≥ 2 页。

---

### 阶段4：报告撰写与评审准备（Day 11–14）
#### Day 11：完成报告主体章节
**目标：**

+ 完成报告大部分内容（除结论和附录）。

**任务：**

1. 按之前大纲，完成以下章节的完整稿：
    - 背景与动机；
    - 网表与图模型；
    - 网表分割问题定义与主流方法分类；
    - 关键图分割算法与工具综述；
    - 时序关键路径保护与 Slack 恢复策略；
    - 分区后并行优化流程设计思路；
    - 开源工具与 Demo 方案对比；
    - Demo / 实验设计；
    - 实验结果与初步分析。
2. 插入：
    - Demo 结果表；
    - 简单图（可选）。
3. 产出：
    - 报告主体 ≥ 15 页（PPT 或 PDF）。

**量化指标：**

+ 报告主体章节完成 ≥ 80%；
+ 页数 ≥ 15 页。

---

#### Day 12：完成落地方案 + 风险 + 总结
**目标：**

+ 补充“落地方案建议”、“风险与挑战”、“总结与后续工作”；
+ 完成报告整体。

**任务：**

1. 写：
    - 落地方案建议（1–2 页）：
        * 短期/中期/长期路线图；
    - 风险与挑战（1 页）；
    - 总结与后续工作（0.5–1 页）；
    - 附录：参考资料 & 工具清单（1 页）。
2. 整合：
    - 统一格式、字体、图表编号；
    - 检查逻辑连贯性。
3. 产出：
    - 报告完整版（15–25 页）。

**量化指标：**

+ 报告完整版本完成；
+ 页数在 15–25 页之间。

---

#### Day 13：内部评审 + 修改
**目标：**

+ 找同事/老板快速评审；
+ 根据反馈修改。

**任务：**

1. 内部评审：
    - 找 1–2 位同事或老板，快速过一遍报告；
    - 收集反馈：
        * 哪些部分不够清楚；
        * 哪些落地方案需要调整。
2. 修改：
    - 根据反馈调整：
        * 文字表述；
        * 图表；
        * 落地方案细节。
3. 产出：
    - 报告修改版 v1.1。

**量化指标：**

+ 至少 1 次内部评审；
+ 根据反馈完成至少 3 处明显修改。

---

#### Day 14：最终版 + 汇报准备
**目标：**

+ 完成报告最终版；
+ 准备汇报 PPT / 讲稿。

**任务：**

1. 最终版：
    - 检查：
        * 图表清晰度；
        * 引用和标注；
        * 页面编号、目录。
    - 产出：报告最终版 PDF/PPT。
2. 汇报准备：
    - 写一个 5–10 分钟的汇报提纲：
        * 背景与动机；
        * 核心结论；
        * Demo 结果；
        * 落地方案。
    - 准备 1 页“一页纸总结”（给老板看的摘要）。
3. 产出：
    - 报告最终版；
    - 汇报提纲 1 页；
    - 一页纸总结 1 页。

**量化指标：**

+ 报告最终版完成；
+ 汇报提纲 ≥ 1 页；
+ 一页纸总结 ≥ 1 页。

---

## 四、关键里程碑与检查点
+ **Day 3 结束：**
    - 完成资料搜集 + 3 篇核心论文精读；
    - 报告“背景”和“时序保护”部分初稿。
+ **Day 5 结束：**
    - 完成 Demo 环境 + 脚本 v0.1；
    - 方案蓝图 + Demo 设计文档。
+ **Day 10 结束：**
    - Demo v1.0 + 实验结果表 + 实验分析；
    - 报告主体章节完成 ≥ 80%。
+ **Day 14 结束：**
    - 报告最终版 + 汇报提纲 + 一页纸总结。

---

如果你愿意，我可以在下一步帮你：

+ 把这份计划压缩成一张 **14天甘特图表格**（每天一行，任务 + 产出 + 量化指标）；
+ 或者直接帮你写 **报告一页纸总结** 的模板，方便你 Day 14 快速填充。

