# ChatGPT 研究结论：四至→围栏重建理论框架（2026-08-29）

> 来源：ChatGPT Web (browser relay) 独立研究
> 输入：38 合同 + 手绘真值 + 三轮实验数据
> 输出：18608 字符理论框架

## 核心理论

四至不是四条边，而是四个带方向标签的空间参照约束。区域重建 = 在参照物构成的空间分割中，结合模糊语义、拓扑闭合和内部种子，识别最符合约束的区域分量。

形式定义：FourBounds = Directional Constraint + Reference Field + Topological Barrier

## 三级语义

1. 方向约束（Frank cone model）：候选参照段是否在正确方向锥内
2. 参照场（fuzzy directional field）：每点距参照物多远、在哪个方向（梯形membership函数）
3. 屏障拓扑（connected component）：删除屏障后的连通分量

## Q2 关键发现：Directional Visible Exit Arc

从中心向南方向锥发射线，取每条射线第一次退出行政区的位置，合并为连续弧段。
这比"整个行政区边界当barrier"或"MBR最南端"都合理。

## Q3 聚合函数：min 而非 product

μ(x) = min_d μ_d(x) — 合同语义是合取，一边严重违反不应被其他三边补偿。
Erwig vague region 的 AND: K* = ∩Ki, U* = ∩Ui, B* = U* - K*

## Q4 屏障修复：minimum-cost s-t cut

不做 bbox closure（证明必要但不是正确方法）。
构建 planar graph，source = anchor，sink = AOI boundary，
barrier edges 低 cost，gap edges 中 cost，任意空间高 cost。
最小割 = 自动找到"最便宜的闭合方式"。

## Q5 表达力定理

定理1：4个半平面交集必为凸集 → 无法表达凹/L形/多块/洞
定理2：4个arbitrary barrier + 1 seed → 可表达凹形但最多选择一个face → 无法表达MultiPolygon
推论：MultiPolygon 必须通过增加合同槽位（component结构）解决

## 实验优先级（按信息增益排序）

A: Semantic Oracle（人工指定OSM对象）→ IoU ceiling
B: Segment Oracle（人工指定哪段是真边界）
C: Perfect Topology Oracle（保证闭合）
D: 自动 Visible Arc
E: Topology Repair (snap/extend/conflation)
F: Minimum-Cost Cut（替换bbox closure）
G: Vague Kernel + Boundary

## 指标体系（7层）

L1: IoU (median/IQR/≥0.5/≥0.7/≥0.8)
L2: Boundary IoU / HD95 / PoLiS
L3: Topology (valid rate / component error / self-intersection)
L4: Leakage (escape / area leak / undercoverage)
L5: Semantic Accuracy (reference entity acc / segment recall / boundary adherence)
L6: Repair Cost (synthetic gap count / repair ratio)
L7: Expressivity (oracle IoU / regret / ambiguity rate)
