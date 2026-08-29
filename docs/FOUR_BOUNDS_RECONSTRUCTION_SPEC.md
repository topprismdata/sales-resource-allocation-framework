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

**P1 — Oracle Arc Endpoint** (the pivotal falsification test)
Hand-annotate each clause's true [start, end] on the reference feature;
everything else automatic. If IoU jumps 0.49 → 0.75+, the bottleneck is
arc-endpoint information (→ add the slot to the contract). If it barely
moves, the bottleneck is reference geometry/topology, not the text.
This single experiment decides the whole engineering direction — higher
priority than any algorithm tuning.

**P2 — Oracle Reference Geometry**: hand-tell the algorithm exactly which
OSM object each clause refers to (no endpoints). Measures entity-
resolution ceiling.

**P3 — Gap Repair Ablation**: {none / snap / snap+conflation /
+least-cost / +dynamic-buffer}. Report IoU, leakage, synthetic length,
false-closure rate. Tests whether Wang-2026 dynamic buffer transfers to
Guangzhou's river+admin mix.

**P4 — Admin Arc Ablation**: {whole-polygon-clip / bbox / nearest /
two-anchor-shortest / two-anchor-direction-aware / cycle-joint}.
Predicted winner: direction-aware two-anchor + cycle optimization.

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
