可以。基于你现在的 38 份真实合同、人工手绘真值以及三轮实验，我认为研究问题已经可以被更精确地重新表述为：

Four-Bounds Reconstruction 不是"4 条文本 → 4 条线 → Polygon"的问题，而是一个由自然语言触发的、带有不完备约束的"边界解释 + 拓扑补全 + 区域选择"问题。

## 重要新发现：2026 中国直接相关论文

王跃等 2026《基于大模型语义理解与动态拓扑优化的四至边界精准提取方法》
DOI 10.20117/j.jsti.202602013
- 从自然语言四至描述直接生成边界，3056 个上海道路四至样本
- 动态缓冲拓扑修复：5m→1000m 多级动态缓冲搜索
- 总体 OA 83.93%；封闭道路样本 97%，非闭合样本 47.32%
- 但主要处理"道路围合型四至"，未系统处理 river + admin-boundary arc + vague term 混合

## 总体结论表
Q1: 最合理形式化 = 定向选择的边界参照物 + 局部 side constraint + barrier topology + soft reference field（混合语义，非三选一）
Q2: 番禺区边缘 = 已知闭合 polygon boundary 上未知起终点的 arc-selection 问题（这是整个项目的中心问题）
Q3: 拓扑确定性用 Erwig–Schneider kernel/conjecture；连续语义评分用 fuzzy membership。工程上二层并存
Q4: 不能无条件 snap；五级 repair hierarchy（exact→snap→semantic continuation→conflation→least-cost bridge→dynamic buffer）
Q5: 4 个 half-plane 必为凸集；真正限制是"每个 reference 允许贡献多少 boundary arcs"+ 缺 arc 端点+组合顺序
Q6: 中国既有工程方向是 geometry→四至文字（CASS/专利/ObjectARX），不是反向。2026 才出现 text→boundary 工作但仍主要道路围合
Q7: IoU + Boundary IoU + HD95 + ASD + PoLiS + topology + per-boundary attribution + membership MAE + human ceiling

## 关键文献（新增）
- Frank 1996 cardinal directions IJGIS DOI 10.1080/02693799608902079
- Yan et al 2008 fuzzy cardinal directional relations DOI 10.1016/j.knosys.2008.03.017
- Deng & Li 2008 statistical directional relations DOI 10.1007/s10707-007-0031-2
- Buchin et al 2011 splitting line model DOI 10.1145/2093973.2093994
- Erwig & Schneider 1997 Vague Regions SSD LNCS 1262:298-320
- Alt & Godau 1995 Fréchet DOI 10.1142/S0218195995000064
- Buchin/Buchin/Wang 2009 partial curve matching
- Lei & Lei 2023 linear feature conflation DOI 10.1111/tgis.13062
- Cheng et al 2021 Boundary IoU CVPR DOI 10.1109/CVPR46437.2021.01508
- Avbelj/Müller/Bamler 2015 PoLiS DOI 10.1109/LGRS.2014.2330695
- Dilo/de By/Stein 2007 vague spatial metrics DOI 10.1109/FUZZY.2007.4295469
- 王跃等 2026 四至边界精准提取 DOI 10.20117/j.jsti.202602013
- GB/T 37346-2019 不动产单元（是编码规范，非 text→geometry）
- GB/T 42547-2023 地籍调查规程（geometry→四至，非反向）
- CN105677843A 自动获取宗地四至属性专利（反向）

## Q2 中心问题：Arc Selection 算法
function select_admin_arc(A, B1, B2, d, c):
    Gamma = boundary(A)
    p1 = intersection_or_projection(B1, Gamma)
    p2 = intersection_or_projection(B2, Gamma)
    for arc in [path_cw(Gamma,p1,p2), path_ccw(Gamma,p1,p2)]:
        score = directional_score(arc,d,c) + closure_score(arc,B1,B2)
              + side_consistency(arc,c) - excessive_length_penalty(arc)
    return argmax(score)

## Q3 Erwig 交集定义
(u∩v)_k = u_k ∩ v_k
(u∩v)_c = (u_c∩v_c) ∪ (u_k∩v_c) ∪ (u_c∩v_k)
推荐二层：Layer1 hard topology (feasible components)，Layer2 fuzzy score (min t-norm 主，product 辅)

## Q4 五级 Repair Hierarchy
L0 exact topology merge / L1 snapping (d<τ_d AND angle<τ_θ) / L2 semantic continuation (name变化但class+bearing连续) / L3 road conflation (shape+connectivity+topology) / L4 least-cost bridge (限制在 local corridor)
不能全局 morphological closing；bbox 只做 candidate generator

## Q5 表达力（精化）
定理A：4个凸half-space交集必为凸
但curved side-field可出现concavity → 真正限制是：
- 一条road哪段参与？缺[start,end]
- road穿过territory？缺boundary_mode
- 同一landmark出现两次（两段分离river arc）？单"北至珠江"无法表达
- holes？四至无exclude(A)
- MultiPolygon？1个center只能选含它的component
信息论：把 O(m) 个 boundary decisions 压缩成 4 个 reference id，必然丢失

## 最小扩充槽位（收益最大的两个）
arc_endpoints (start_anchor, end_anchor) + boundary_mode (ON_FEATURE/FEATURE_SIDE/ADMIN_ARC/OFFSET/CONNECT_TO/CROSS_FEATURE)

## 9步 Pipeline
1 coordinate normalization
2 four-bounds semantic parsing (direction/reference/type/boundary_mode/confidence)
3 reference resolution (OSM candidate retrieval, LLM只做semantic normalization不允许生成坐标)
4 reference geometry canonicalization (road centerline merge / river bank / admin boundary → canonical linear reference)
5 boundary arc inference (Subcurve(Γ,a,b), anchors from adjacent bounds intersection) ← 最缺的一层
6 gap repair/conflation (仅selected arcs周围)
7 constraint graph construction (nodes=endpoints/intersections, edges=features+budgeted)
8 closed boundary inference (constrained min-cost cycle，非connected component)
9 uncertainty + evaluation (输出 polygon+confidence+evidence_trace+insufficiency_flags)

## 实验优先级（P0最高）
P0 Human Ceiling Benchmark: 抽12份(4easy/4med/4hard)×3人独立画，IoU/BIoU/HD95/PoLiS，确定真实上限
P1 Oracle Arc Endpoint: 人工标每条reference boundary的[start,end]，其他全自动 → 判断瓶颈是算法还是信息缺失（最关键的证伪实验）
P2 Oracle Reference Geometry: 人工告诉"珠江就是这条geometry"但不给endpoints
P3 Gap Repair Ablation: A无修复/B snap/C snap+conflation/D+least-cost/E+dynamic-buffer
P4 Admin Arc Ablation: A整polygon clip/B bbox/C nearest/D two-anchor shortest/E two-anchor direction-aware/F cycle-optimized
P5 Min vs Product vs Kernel: 报告calibration和candidate ranking accuracy
P6 Expressiveness Audit: 逐份标CLASS A(4ref唯一确定)/B(需endpoint)/C(需include-exclude)/D(多块不可恢复)
P7 Graph-Cycle vs 2026 Dynamic Buffer baseline

## 三个研究判断
1. 0.493 不说明四至只能到0.5，说明加入正确admin topology后已从错误formulation进入正确formulation
2. 下一阶段最应研究reference→boundary arc（Q2是中心问题），不是fuzzy参数
3. 尽快做P1 Oracle Arc Endpoint：用极低成本回答瓶颈是算法还是信息缺失

## 理论命名
"Geometry Reconstruction from Underspecified Boundary References"
核心representation: Text→ReferenceObjects→BoundaryArcs→ConstraintGraph→Minimum-costClosedCycle

## 建议产出
整理成 "Four-Bounds Reconstruction Benchmark & Algorithm Specification v1.0"
