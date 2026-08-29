# Four-Bounds Reconstruction: Benchmark & Algorithm Specification v1.0

**Status:** Implementation specification (engineering layer)
**Date:** 2026-08-29
**Data:** 38 Guangzhou distributor contracts + hand-drawn ground-truth
fences (GCJ-02 → WGS-84) + OSM road/river/admin layers
**Grounded in:** oracle-ladder experiments (`analysis/FOUR_BOUNDS_LADDER_2026-08-29.md`),
independent research review (`analysis/CHATGPT_DEEP_RESEARCH_four_bounds.md`)
**Related:** D11 (logical merge), D13 (CRS), D14 (multi-component), K-PRIN-006/007
**Note:** This is NOT part of the v1.2.1 FROZEN normative spec set; it
specifies the geometry-reconstruction engineering layer built on top.

------------------------------------------------------------------------

## 1. Problem Restatement

Four-bounds reconstruction is **NOT** `text → 4 lines → intersect →
polygon`. It is an under-specified boundary-reference interpretation
problem:

> **Geometry Reconstruction from Under-Specified Boundary References:**
> text → reference objects → boundary arcs → constraint graph →
> minimum-cost closed cycle

The three experiments to date (median IoU 0.069 → 0.153 → 0.493)
show the decisive factor is **not** corner geometry or fuzzy-function
tuning, but **topology closure** and **reference→arc interpretation**.

## 2. Formal Semantics of a Four-Bound Clause

A single clause (e.g. "北至珠江后航道" / north bounded by Pearl River
Back Channel) encodes THREE distinct facts, which prior implementations
conflated:

```text
clause = (direction, entity, arc, mode, side, confidence)
```

1. The named entity L is a **candidate boundary support** — not the whole
   boundary, but the source of one arc.
2. The territory interior lies on a specific **side** of L.
3. Only a **sub-curve (arc)** S ⊆ L actually participates in the boundary.

Formally, for the north clause with local tangent at nearest point:

```text
s(x) = n(π(x))ᵀ (x − π(x))         # signed cross-product side test
μ(x | L) = σ((s(x)+b)/τ) · decay(d(x,L))   # side membership × distance
```

The four clauses combine as a **conjunctive** contract (`min` t-norm,
weakest constraint wins), NOT a product (which over-penalizes as clause
count grows). Topological feasibility (connected component of
Ω ∖ barriers) is Layer 1; fuzzy scoring is Layer 2 ranking only.

## 3. Reference-Object Taxonomy & Side Determination

| Type | Canonical geometry | Side rule |
|---|---|---|
| ROAD | centerline (merge carriageways) | local tangent at nearest point (NOT whole-line orientation) |
| RIVER | centerline or bank polygon | local tangent; bank vs center is a `boundary_mode` |
| ADMIN | polygon boundary ∂A | arc selection on ∂A (see §4) |
| VAGUE ("区边缘","附近") | arc of a known polygon | modeled via visible-exit rays |

**Linear side determination:** for a curved/extended reference, do not
use a single global orientation. Take the nearest point p*, use its
local tangent, compute signed side. (Frank 1996 cone model is for
candidate disambiguation, not geometry generation — Buchin 2011
splitting-line model is the correct extended-object form.)

## 4. Administrative Boundary Arc Selection (central problem)

"南到番禺区边缘" = **select an unknown arc [start,end] from a KNOWN
closed polygon boundary ∂A**, not a fuzzy region.

Recommended algorithm — **Directional Visible-Exit Arc**:

```text
function select_admin_arc(A, adj_bounds, direction, seed):
    Γ = boundary(A)
    endpoints = []
    for side in {prev, next}:
        # arc endpoints come from adjacency, not from ∂A alone
        endpoints[side] = intersect_or_project(adj_bounds[side], Γ)
    for arc in {Γ[cw](p_prev, p_next), Γ[ccw](p_prev, p_next)}:
        score(arc) = directional_coverage(arc, direction, seed)
                   + side_consistency(arc, seed)
                   + closure_contribution(arc, adj_bounds)
                   − excessive_length_penalty(arc)
    return argmax(score)
```

The whole ∂A must NOT be rasterized as a barrier — that imports
hundreds of km of constraint the contract never expressed.

## 5. Barrier Gap Repair (five-level hierarchy)

Never snap unconditionally (real dead-ends exist). Apply, in order:

| Level | Method | Gate |
|---|---|---|
| L0 | exact-topology merge | d < ε_numeric |
| L1 | endpoint snapping | d < τ_d AND \|Δθ\| < τ_θ AND class-compatible |
| L2 | semantic continuation | name changes but class+bearing continuous |
| L3 | road-network conflation | shape+connectivity+topology joint (Ting Lei 2023) |
| L4 | least-cost bridge | constrained to Buffer(p1p2, r), NOT global |

Thresholds must be **scale-adaptive**: τ = f(road_class, resolution,
local_density, boundary_type). Wang 2026 uses 5 m→1000 m multi-level
dynamic buffer for road gaps — a strong baseline, but tuned to
road-only enclosure, not our river+admin mix. Bbox closure is a
candidate generator, never a final principle.

## 6. Expressiveness Ceiling & Contract Slots

**Theorem A:** four straight half-planes → intersection is convex →
cannot represent concave / L-shape / holes / multi-component. (This
explains the 0.069 ceiling: hypothesis class wrong, not untuned.)

**Theorem B:** four arbitrary curve barriers + ONE seed can produce
concave regions (seed selects one face) but CANNOT recover: which arc
of each feature, boundary_mode, repeated landmark arcs, holes, or
additional components.

**Information-theoretic:** an ordered boundary needs O(m) decisions
(γ_i = reference, start, end, orientation, mode, offset); classic
four-bounds supplies only 4 reference IDs. Compression ⇒ loss.

**Minimal high-value contract extension** (two slots):

```text
arc endpoints (start_anchor, end_anchor) + boundary_mode
boundary_mode ∈ {ON_FEATURE, FEATURE_SIDE, ADMIN_ARC,
                 OFFSET_FROM_FEATURE, CONNECT_TO, CROSS_FEATURE}
```

## 7. Empirical Case Audit (37 valid Guangzhou cases, V1c semantics)

Per-clause landmark geometry found: 100% (typed admin layer wired).
Barrier leak (no natural closure): **36/37**. Closure is universal —
bbox is never the real answer.

**Pearson r(fidelity, IoU) = 0.46** — fidelity (share of hand-drawn
perimeter within 150 m of a named landmark) is the dominant predictor
of reconstruction accuracy, stronger than block count.

**Reframe (see §7.2):** the V1c ≈ 0.49 ceiling is partly the
hand-drawing noise floor, not purely a text/algorithm deficiency.

**Key counter-intuitive result: multi-block ≠ hard.** 国之林 has 3
disconnected blocks but IoU 0.806 (large suburban, boundary hugs admin
line, fidelity 0.687). 穗穗盛 has 2 blocks but IoU 0.115 (dense urban,
fidelity 0.323). Difficulty tracks **low fidelity + urban complexity**,
not component count.

### 7.1 P6 Expressiveness Audit (real data)

| Class | Definition | n | IoU median | Action |
|---|---|---|---|---|
| A | single block, fidelity ≥ 0.5 | 3 | 0.78 | near-unique from four-bounds |
| B | single block, high fid, needs endpoint | 0 | — | (empty at this data density) |
| C | low fidelity (< 0.5) | 25 | 0.50 | see §7.2 decomposition — mostly drawing noise, not text deficiency |
| D | multi-component | 9 | 0.41 | needs component slots; but see 国之林 |

### 7.2 Fidelity Decomposition (business-owner insight + audit, 2026-08-29)

Business owner: *"when the human boundary is not strict, it is usually
caused by the difficulty of manual drawing."* Verified by distance-signature
audit on all 37 cases. Median 88% of hand-drawn vertices sit > 500 m from
the clause-named landmark. Where do those deviating vertices actually lie?

| Component | Share | Meaning |
|---|---|---|
| On a DIFFERENT real OSM road/river (±80 m) | **~47%** | the drawn boundary follows secondary features the contract never named — real spatial information absent from the text |
| On no OSM feature at all | **~53%** | **drawing noise**: hand-tracing a winding river/road in a CRM requires hundreds of clicks; humans shortcut, straighten, and draw by impression at their screen scale |

Convex-hull ratio median 1.34 (vs 1.0 = perfectly convex): the true
boundary is substantially non-convex — the deviation is structured
approximation, not random jitter.

**Consequences for this benchmark (corrects Rev-1 interpretation):**

1. Low fidelity ≠ "contracts are under-specified." The contract defines
   a **coarse-grained intent**; the hand-drawn fence is a **noisy
   fine-grained realization**. They are not supposed to agree at pixel
   level. Chasing IoU→0.8 against hand-drawn noise is the wrong target.
2. The correct evaluation target is **agreement with contract intent
   within a tolerance band** — exactly what the Erwig core/plus model
   (Q3) provides: the hand-drawn polygon should fall inside our plus
   zone; its exact edge is unknowable and does not need to be known.
2a. **CORRECTION after P1 (2026-08-29):** the self-simplify noise proxy
   (1 km → IoU 0.86) only bounds *wiggle smoothness*, not *placement
   error*. 穗穗盛-type failures (model area 2.6× truth, IoU 0.12) are
   region-SELECTION errors that no amount of human drawing noise
   explains — a human re-draw would still cover roughly the right
   area. So Class C low fidelity decomposes further: (a) drawing
   wiggle ≤ 14%, (b) wrong-face region selection (the fixable,
   dominant part), (c) genuine secondary-feature references absent from
   text. Do not use "drawing noise" to explain away the 0.49 plateau;
   P1 proves algorithmic headroom remains.

3. This makes **P0 (human re-draw ceiling) the decisive experiment**:
   three humans drawing from the same contract will disagree with each
   other at the same noise scale. If human-vs-human IoU is ~0.55, a
   model at 0.493 is already near human-equivalent — and the headline
   metric must be reported against that ceiling, never against 1.0.
4. The ~47% secondary-feature component IS text deficiency — that part
   is recoverable by the minimal contract slots (§6: arc endpoints +
   boundary_mode + secondary-feature naming), and OSM context can
   partially infer it without new slots (a visible-exit ray that hits a
   river justifies snapping the arc there).

## 8. Recommended Pipeline (9 steps)

```text
1  coordinate normalization            (done: D13, GCJ→WGS, pack_from_disk)
2  four-bounds semantic parse           direction/entity/type/boundary_mode/confidence
3  reference resolution                 OSM candidate retrieval + ranking (LLM normalizes, never emits coords)
4  reference canonicalization           road centerline merge / river bank / admin ∂A → canonical linear ref
5  boundary arc inference               Subcurve(Γ, a, b), anchors from adjacent-boundary intersections   ← NEW, highest value
6  gap repair / conflation              levels 0–4, local to selected arcs only
7  constraint graph build               nodes=endpoints/intersections, edges=features+bridges, cost per edge
8  closed boundary inference            constrained min-cost CYCLE containing seed, satisfying all 4 sides  ← replaces bbox
9  uncertainty + evaluation              polygon + confidence + evidence_trace + insufficiency_flags
```

## 9. Evaluation Metrics (multi-dimensional; no single score)

| Dim | Metric | Threshold convention |
|---|---|---|
| Area | IoU, Dice | median + IQR + ≥0.5/0.7/0.8 rate |
| Boundary | Boundary IoU @10/25/50/100 m (Cheng 2021) | report per-band |
| Distance | HD95, Average Symmetric Boundary Distance | meters |
| Shape | PoLiS (Avbelj 2015) | robust to vertex-count mismatch |
| Topology | closure rate, component error, hole count, self-intersection | leakage is first-class |
| Semantic | per-boundary attribution (N/S/E/W accuracy; segment recall; boundary adherence) | isolate the failing stage |
| Repair | synthetic bridge length / repair ratio | penalize fake closure |
| Uncertainty | membership MAE / Brier / calibration | only if fuzzy output |
| Human | inter-annotator agreement ceiling | §10 |

**No universal "IoU>0.8 = human" threshold exists** — human digitization
has large operator variability (reported inter-expert IoU ranges 0.47–
0.79 across segmentation tasks). Define your own ceiling (below).

## 10. Prioritized Experiments (by information gain)

**P0 — Human Ceiling Benchmark** (do first, gates everything else)
Draw 12 cases (4 easy / 4 medium / 4 hard), have 3 domain staff
independently re-draw fences from the same contract text WITHOUT seeing
ground truth. Report IoU / BIoU / HD95 / PoLiS pairwise. This defines
the reachable ceiling and the human-tolerance noise floor. **Any model
result must be normalized to this.**

**P1 — Oracle Arc Endpoint** — ✅ DONE 2026-08-29
(`tools/bench_p1.py`, `tools/visualize_p1.py`, `/p1` page,
`/tmp/p1_results.json`). Oracle = barrier clipped to the landmark
segments actually within 300 m of the true boundary (cheating arc
selection), same bbox closure as V1c.

**Result: Δ(P1−V1c) median −0.036; arc selection is NOT the lever.**
Per-case (|Δ|>0.02 on 23/34):

| Direction | Example | Geometry (visual+numeric audit) |
|---|---|---|
| oracle HURTS (up to −0.47) | 胜意隆 0.82→0.49 | truth is large concave admin-area (934 km²); V1c's FULL-LINE barriers happen to fence it tightly (area ratio 1.0×); pruning arcs opens gaps → flood back to raw bbox (1.6×) |
| oracle HELPS (up to +0.21) | 穗穗盛 0.12→0.32 | named landmarks CROSS THE INTERIOR of the truth (珠江西/后航道 cut ~3 km inside): full-line barriers slice the owner's own territory → seed component loses the far side; pruning restores it |
| both miss badly | 穗穗盛 | both V1c and P1 cover 2.6–2.8× truth area — bbox closure carries most of the IoU, not the barriers |

**Conclusions:**
1. Do NOT chase arc-endpoint contract slots as the primary fix — with
   the current closure mechanism, oracle arcs add nothing (median −0.04).
2. The binding constraint is **closure + region selection**: full-line
   barriers are simultaneously too strong (cutting internal rivers,
   穗穗盛) and too weak (gap-flooding to bbox, 胜意隆). Both symptoms
   trace to the same root: barrier semantics has no notion of SIDE
   (signed distance field) — a river crossing the interior should
   constrain sides, not sever connectivity.
3. Noise floor (truth self-simplified 1 km) = 0.86, convex-hull = 0.73
   → the 0.49 plateau is BELOW the human noise floor; there is real
   algorithmic headroom left. Next lever = pipeline steps 5→8 proper:
   side-membership fields + constrained min-cost cycle (§8), i.e. P3/P4.
4. The `/p1` page (demo_server) renders truth/V1c/oracle/noise-floor per
   dealer sorted by Δ for human inspection.

**P2 — Oracle Reference Geometry**: hand-tell the algorithm exactly which
OSM object each clause refers to (no endpoints). Measures entity-
resolution ceiling.

**P3 — Gap Repair Ablation**: {none / snap / snap+conflation /
+least-cost / +dynamic-buffer}. Report IoU, leakage, synthetic length,
false-closure rate. Tests whether Wang-2026 dynamic buffer transfers to
Guangzhou's river+admin mix.

**P4 — REDESIGNED after refutation of its premise (2026-08-29)**

Original P4 assumed a territory ≈ an admin-district polygon to clip
against. Store-side audit kills that premise: **25/37 dealers span
multiple districts; 10/11 districts are subdivided among dealers
(白云 16, 番禺 15, 天河 12); exactly 1 dealer exclusively holds a whole
district (从化).** A district is NOT a territory container — clipping by
it would sever legitimate territory exactly where K-RULE-002 says
fences live (shared district boundaries).

Correct role: **admin boundaries are boundary LINES — arc candidates
of the same class as roads and rivers.** "南到番禺区边缘" means "south
boundary = some arc of ∂Panyu", not "territory ⊆ Panyu".

Granularity ladder (user direction, 2026-08-29): use BOTH
- 区界 (district ∂, admin_level 6) — base framework arcs;
- 街道办/镇界 (subdistrict/town ∂, admin_level 8) — finer atomic
  cells (China's natural building blocks, Zoltners-style). Old-city
  "一区切 3~6 块" most plausibly partitions on subdistrict lines.

**P4b — three changes, testable independently:**
1. ∂district + ∂subdistrict arcs = first-class barrier candidates
   alongside road/river arcs (same side-field + cycle machinery);
2. joint partition reconstruction: one planar subdivision (faces from
   arcs), faces globally assigned to dealers — each shared border
   decided once; explains the P1 paradox (国之林 V1c succeeded because
   full-line barriers + neighbor clauses accidentally closed a face);
3. face-atom hypothesis test: old-city boundaries coincide more with
   ∂subdistrict than with roads? If yes, faces = subdistrict polygons
   and side constraints degenerate into face assignments.

**GPT cross-review verdict (2026-08-29, docs/reviews/2026-08-29_gpt_p4b_partition_review_raw.md)**
Endorses P4b-2 as the top-level hypothesis, with corrections:
1. Do NOT planarize all OSM — face explosion (dual carriageways, river
   banks, sliver polys → 10⁵+ faces). Only contract-mentioned features +
   admin-6 + admin-8 + gap-repair connectors enter the candidate set.
2. **NEXT SINGLE EXPERIMENT = P4b-O Global Oracle Atomic Partition**
   (ceiling before solver — same discipline that made P1 decisive):
   four atomizations {O1 street polys (admin-8), O2 road-block faces,
   O3 contract-mentioned arc arrangement, O4 hybrid}; assign every face
   to argmax_k Area(f∩GT_k) (pure representation, no NLP/solver);
   report per-atomization Median IoU / Q25-75 / worst-5 /
   BoundaryF1@50/100/300m / component counts. Decision rule: if even
   the best ceiling ≈ V1c's 0.49 → representation dead, need finer
   atoms; if ≥0.7 → build the face-assignment solver.
3. Report IoU decomposition (final / no-bbox / bbox-only / fallback
   rate) from now on — bbox was masking the real signal (P1 lesson).
4. Semantics: landmarks demoted from hard barriers to (a) unary side
   potentials μ_k,b(f) per clause + (b) pairwise boundary rewards ρ_fg
   (low cost to cut ALONG a named river/road, never forced). Face
   labels x_f ∈ {dealers} ∪ {∅}; hard tiling only after a topology
   audit of GT (enclaves / carve-outs / water measured first).
5. P4b-3 confound alert: street boundaries follow roads by census
   rule — boundary-distance tests give false positives; use the Atomic
   Unit Oracle Test (can uncut street polygons reproduce GT), n=37,
   territory-level clustered bootstrap.
6. Guard 8 failure modes: face explosion; atoms too coarse (street
   split by 3 dealers = unrecoverable); tiling not strict (keep ∅
   label); inter-contract contradictions (slack); connectivity soft
   until GT component audit; center = strong prior not hard seed;
   evidence double-counting (street-along-road → dissolve + provenance
   tags); time mismatch (valid_from/to on admin evidence).
7. Data note: NBS 12-digit codes are entity lists, NOT geometry, and
   no longer public since 2024-10 — level-8 geometry must come from an
   OSM refetch (our admin-6 layer has open chains; polygonize closed
   only 5/11) or licensed sources. Prerequisite task for O1/O4.

**P2-V — Candidate Boundary Choice Oracle — ✅ DONE 2026-08-29**
(`tools/bench_p2v_recall.py`, `data/gz/p2v_recall.json`). Candidate
network = admin-6 + admin-8 + roads + rivers cut into 250m segments
(88,725 segs). GT boundary length fraction within 100/300m of any
candidate:

- **Median Recall@300 = 0.935** → the real boundary overwhelmingly
  EXISTS in the available line networks. GPT cross-review reframe
  accepted: problem ≈ heterogeneous line-network map matching
  (candidate ranking + path selection), NOT polygon generation.
- **DATA FIX (user diagnosis, 2026-08-29):** the original fetch only
  captured motorway–secondary named ways and clipped admin fragments.
  Refetched via Geofabrik guangdong-latest.osm.pbf (164MB, pyosmium,
  ALL highway classes): 188,301 road ways / 8,672 waterways / 228
  admin-8 / 21 admin-6 → gz_osm_full.json. Re-run:
  **Median Recall@100 = 0.975, Recall@300 = 1.000 (n=39).** Gate
  (>0.9) PASSED. The 0.49 plateau was substantially a DATA problem —
  street-level roads were absent so the candidate network could not
  express the true boundary.
- Median Recall@100 = 0.707 → strict snap needs per-dealer handling:
  top half of dealers ≈0.95–1.0 (亨啡源 0.95/1.0, confirming its 0.897
  street+road reconstruction); bottom ~15% (彩弘 0.10, 鸿欣 0.12,
  华新 0.29) have boundaries genuinely absent from the network.
- **Architecture decision**: main line = Boundary Choice
  (candidate recall → segment features [name/side/orientation/distance/
  continuity] → path optimization, HMM/Viterbi-style, cf. Newson &
  Krumm 2009; NOT greedy — one wrong junction derails the chain, as
  observed on 亨啡源). Face assignment / global partition (P4b-2)
  DEMOTED to a fallback only for low-recall dealers.

**P5 — Aggregation (min vs product vs kernel)**: report calibration and
candidate-cycle ranking accuracy, not just final IoU. Expected: min for
semantics, product as evidence score, Erwig kernel for hard feasibility.

**P6 — Expressiveness Audit**: DONE (see §7.1) — 3 A / 0 B / 25 C / 9 D.
Extensible with human re-annotation of which real cases are truly
unique.

**P7 — Graph-Cycle vs 2026 Dynamic-Buffer**: final baseline set
{half-plane, barrier-CC, admin+bbox, Wang-2026, proposed arc+cycle}.

## 11. Engineering Consequences for This Repo

1. **D14 stays valid**: multi-component is a real business pattern
   (9/37 dealers), but is NOT the primary IoU limiter — P6 shows Class C
   (low fidelity) dominates.
2. **The four-bounds rebuild's realistic near-term target** is to lift
   median IoU from 0.49 toward the P0 human ceiling, via pipeline steps
   5 (arc inference) + 8 (min-cost cycle), NOT step-3 entity work
   (already adequate: V2 oracle-arc was worse than V1).
3. **Honest product boundary**: with classic four-bounds text alone,
   ~25/37 territories are under-determined. Output must carry
   insufficiency flags + a per-clause human-review ticket (arc endpoint
   / boundary-mode questions), exactly like ArcGIS COGO exposes misclose
   for surveyor correction. The demo's `interpretation: draft` is the
   right posture.


## §12 基础单元分配范式（2026-08-29，用户提出并验证）✅

**用户论断：分配一定是用基础单元组合，而不是切割。** 数据完全证实：

- 数据源：《边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson》
  （GCJ-02，已转 WGS 入库 `data/gz/basic_units_wgs.json`）
- **2,675 个路网基础单元**：四级行政归属（省/市/区县编码+街道），11 区
  173 街道全覆盖，合计 7,221 km²（市域 97%+），互斥（重叠 0.01 km²）
- **验证**：业代片区 11/11 片覆盖率中位 100.0%（残差 0.00 km²）；
  经销商手绘 31 家（除佛山）覆盖中位 99.5%，27 家 ≥95%

**架构重写**：
```
旧: 四至文本 → 导引线 → map matching / min-cut → 边界折线   (复杂、噪声敏感)
新: 四至文本 + 中心 → 单元选择(约束满足/优化) → 单元并集     (离散、精确)
```
- 分配 = 集合赋值：每单元已带区/街道属性，四至约束变成单元筛选规则
- NL 合并/拆分 = 单元组操作（合并=并集，拆分=沿线分桶）
- map matching / min-cut / HMM 全部降级为备用（仅当出现非单元边界的围栏）
- 验收从 IoU 变为 **单元集一致率**（可 100% 精确）

**开放问题**：合同语料如何映射到单元筛选规则（街道名→街道内单元、
路名→路侧单元、方向→方位筛选）；P2-X 实验设计待定。


### §12.1 V2 单元分配器第一版：负结果与正解（2026-08-29 深夜）

实现 `tools/unit_allocator.py`（方向标量界线过滤 + BFS 连通）+
语料 v2（`data/gz/contracts_v2_corpus.json`：沿真值边界反查 32 家的
方位贴边命名道路，如亨啡源=北广连高速/南华观路/东广汕二路/西华南快速）。

**评估：失败**（中位 IoU 0.005，多数案例单元并集灌满全市）。
根因：**标量界线约束无法表达"边界是这条具体的路"**——
道路是弧线，标量带状过滤挡不住同纬度/同经度的全域泄漏；
且锚定路只覆盖边界的一部分，弧外无约束。

**正解（下一实现的规格）**：
1. 线侧性约束：单元相对锚定弧的有向侧（signed side），非标量带
2. 连通性：分配集必须在单元邻接图上连通（BFS/flow）
3. 全局优化：Zoltners set-partitioning / min-cut，目标=平衡+最小边界
4. 语料 v2 已备好（真实路名、有区分度），单元库 v3_clean 已备好
