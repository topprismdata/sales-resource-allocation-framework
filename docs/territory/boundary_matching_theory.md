# 边界重建算法理论支撑（v1.0，2026-08-29）

> 定位：四至围栏重建 = **异构线网 map matching**（候选线排序+全局路径选择）。
> 本文给出该设计的文献依据与公式映射，作为 `boundary_matcher` 实现的理论基准。

## 1. 问题重定义

| 旧范式（已证伪/降级） | 新范式 |
|---|---|
| 四至语义 → 模糊区域生成 → 多边形 | 四至语义 → 粗导引线 → **吸附到候选线网的全局最优路径** |

依据（本项目实测，2026-08-29）：
- P2-V 候选召回（全量 OSM 路网）：**median R@100 = 0.975，R@300 = 1.000**（n=39）
- 亨啡源北：街道+道路链描述重建 IoU 0.897；四至文本算法仅 0.49

## 2. 理论支柱

### 2.1 Newson & Krumm 2009 — HMM Map Matching
*"Hidden Markov Map Matching Through Noise and Sparseness", Microsoft Research, ACM GIS 2009.*

- **发射概率**（观测噪声 = 高斯）：
  $p(z_t \mid x_t) \propto \exp\left(-\tfrac{1}{2}\left(\tfrac{\|z_t - x_t\|}{\sigma}\right)^2\right)$
  映射：$z_t$ = 导引线第 t 个采样点；$x_t$ = 候选段上的吸附点。
  σ = 手绘噪声尺度，取 120 m（P2-V：R@100=0.975 支持该量级）。
- **转移概率**（合理绕行 = 指数）：
  $p(d_t) = \tfrac{1}{\beta}\exp(-d_t/\beta)$，$d_t = |\,\text{netdist}(x_t \to x_{t+1}) - \text{guide}(t \to t{+}1)\,|$
  映射：netdist = 候选线网上的最短路；guide = 导引线上相邻采样点的弧长。
  β 取采样间隔均值的量级（导引采样 ~200 m ⇒ β ≈ 200 m，按 Newson-Krumm 的经验标定法微调）。
- **全局求解 = Viterbi**：不逐步贪心。实测教训：亨啡源贪心链在一个岔口跳接 15.8 km。

### 2.2 Fréchet curve↔graph（理论保证与复杂度上界）
- Alt, Efrat, Rote, Wenk 2003, *Matching Planar Maps*：曲线 ↔ 图的 Fréchet 匹配存在多项式算法。
- Chen et al., ALENEX 2011：现实路网上近似 map matching 可高效实现。
- Driemel et al. / arXiv 2211.02951：现实输入图上 map matching 查询的复杂度界定。
- **Meulemans（arXiv 1306.2827）：要求匹配结果为 simple cycle 是 NP-complete。**
  ⇒ 工程对策：不在图搜索中强制简单环。做法 = 有界走廊（导引线 1–3 km）内按序 Viterbi，
  闭环由首尾采样重合天然形成，几何拼接后一次性去自交（shapely buffer(0)）。

### 2.3 线要素 conflation 的连通性约束
- Lei & Lei 2023, *Transactions in GIS*：仅局部几何相似会产生不一致匹配，加入
  connectivity 优化显著改善——对应我们的 transition 项（连续性不是可选项）。
- 2024 node-arc conflation（MDPI IJGI）：junction 与路段同时匹配，拓扑一致性减少假匹配
  ——对应我们在路口用网格吸附合并节点。

### 2.4 同题工作的工程先例
- 王跃、马祎程等 2026，《基于大模型语义理解与动态拓扑优化的四至边界精准提取方法》，
  《时空信息学报》33(2): 208–218（上海市大数据中心 + 中国地质大学）。
  流程：自然语言 → 道路/空间关系识别 → Text-to-SQL 找线 → 多级缓冲 → 动态拓扑优化 →
  自适应闭环检测。上海 3000+ 样本，总精度 83.93%。
  差异提示：他们以道路为主；我们另有河流、区/街道界、跨区大体量 territory——
  不可直接对比数字，但证明"实体检索+线拓扑选择+闭环"是可行工程路线。

## 3. 我们的算法（v1 规格）

```
输入: 导引线 G（V1c 粗边界，降级为 guide）+ 候选线网 N（admin6/admin8/road/river, 250m段）
1. 采样: G 上每 ~200m 取点 z_1..z_M（首尾重合 → 闭环）
2. 候选: 每个z_i 取 400m 内最近 k=5 段，投影得吸附点 c_ij（发射）
3. 转移: 相邻层 c_ij→c_{i+1,j'} 在线网图上的最短路长度（Dijkstra，受走廊限制）
4. Viterbi: max Σ log p(z_i|c_i) + Σ log p(d_i)，d_i=|netdist − guide_dist|
5. 拼接: 相邻吸附点间沿最短路取回几何 → 闭环 → buffer(0) 去自交
输出: 边界折线 / 多边形（对照真值评 IoU）
```

## 4. 与文献的偏差声明
- N-K 的 GPS 轨迹是时间序列；我们的导引线是空间序列——采样均匀化后同构。
- N-K 无闭环要求；我们首尾重合+闭合转移项处理（Meulemans 结论下的工程绕行）。
- 候选网含行政界与河流（异构源），发射项在 σ 之外叠加 source 先验权重
  （街道界/主干道优先于 footway），这是 conflation 文献的 standard practice。

## 5. 验收标准
- 亨啡源北（R@100=0.95）：IoU ≥ 0.90（对比：手工链 0.897、四至算法 0.49）
- 全量 39 家：median IoU ≥ 0.70（当前 V1c 0.493）
- 低召回组（R@100<0.4，~5 家）单独报告，不混入主表
