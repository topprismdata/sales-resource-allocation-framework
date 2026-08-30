# SRAF Changelog — v1.2.2 (Implementation Baseline Update: Demo Intelligence Layer)

v1.2.2 is **Implementation Layer Update**. Specification set 00-08 stays **v1.2.1 FROZEN**, this document
only records Demo / Allocation Intelligence implementation (`intelligence/` + `tools/`) landing onto v1.2 semantics
new facts above. See overall implementation design in repository root `DESIGN.md` v0.6.

Date: 2026-08-28 | Code commit anchor: `1c13b12` (region-first) → `a07b248` (Demo layout fix)

---

## 1. Adjusted Semantics Established: Region-First (K-PRIN-006)

Business side corrected the Decision Ontology: **the object of region adjustment is [region/sub-area] (F2 fence),
not the store**. "Store" is a side effect — stores follow the sub-area; if only changing a store, directly in
CRM can be changed, no need for this system.

- Instruction form: `transfer <src>'s <sub-area> to <dst>` / `<src> no longer does it, all region to <dst>`
- Sub-area selector: entire region / east/west/north/south half / district or street name / OOF (cross-boundary supply) / store name vicinity
- `intelligence/adjust.py` and LLM parsing path (`intelligence/llm.py`) both go through
`build_proposal`, rule path dominates (<1s), LLM only as fallback for free-form sentences.

## 2. Fence Logic Consolidation (Polygon Surgery Removal)

Application transfer = **logical operation**, not physical cutting:

- Unique fact = store assignment (`store.dealers` reassignment, quantity conservation trivially holds)
- Fence = derived view: each dealer’s fence geometry = convex hull of its store point set; after transfer
only recalculate convex hulls of src/dst two dealers
- Deprecated: `union/difference` polygon surgery, fragment/dangling detection, single ring `-2/-3`
multi-block numbering, area conservation check. Original `GeometryCollection` crash, km² conversion
caliber mismatch (~9% systemic bias) etc. a whole class of bugs disappeared
- `km2()` conversion by centroid latitude (1°lat≈110.574, 1°lon≈111.320·cos(lat)),
only used for statistical display, not participating in any conservation semantics
- Proposal preview: `sub_ring` (moving store convex hull) rendered as orange dashed ring on the independent `proposalLayer`
`proposalLayer`; automatically cleared after reject/apply, base map untouched

## 3. Interaction and Resilience

- `@` mention engine: typing `@` pops dealer list (color tag + short name + full name, ↑↓/Enter/Tab
select), **after selection inserts full name** — LLM/rules always see only the full name
- Dealer matching deduplicates by dealer name (multiple fence blocks of the same dealer no longer mistakenly judged as "multiple dealers")
- Added `POST /api/reject`: rejection immediately invalidates the server-side pending proposal, preventing
rejecting then clicking old proposal "Confirm Apply" to accept an expired proposal
- Demo layout fix: `#p-adj` missing closing causes the map to be squeezed into a 440px sidebar
(large blank area on the right); at boot, viewport fits to the fence's actual extent via `fitBounds`
(no longer using fixed center), `zoomSnap: 0.25`, after rejecting a proposal the view returns to the whole region

## 4. Knowledge Base v0.

| New | Content |
|---|---|
| K-PRIN-005 | Hierarchical mirror organization: D/B/V three-level independence, interface-only handovers, cross-level interference prohibited |
| K-PRIN-006 | Region adjustment decision object = region; store assignment is a derived effect (core correction of this round) |
| K-RULE-011/012 | Layer-B five-step route determination method / four beat-route principles |
| K-BENCH-005 | Layer-B/V process benchmarks (visit achievement rate redline 90%, etc.) |

The human‑readable index of `KNOWLEDGE_BASE.md` has been synchronized and supplemented with the above entries. |

## 5. Coordinate System Contract (D13, new in this round) |

Data packages (`data/<region>`) declare the coordinate system via `meta.crs` — default **GCJ-02** |
(Gaode/Tencent business data), `WGS84` is used for front‑end point‑selection generated born‑WGS packages |
(Hangzhou test / fs). Server‑side boundaries are normalized in one step: |

- `_load_pack` → `pack_from_disk`: GCJ→WGS (fence/store/contract center/meta center) |
- `_persist_pack` → `pack_for_disk`: WGS→declared system written to disk, round‑trip lossless |
- Internal geometry (four‑boundary verification/road semantics/PIP/OSM matching/map) = pure WGS‑84 |

Evidence for discrimination (Guangzhou measurement): GCJ→WGS system offset ≈623 m (east −549/north +293); |
Fence vertex → OSM road median distance 338 m (GCJ direct comparison) → 123 m (after conversion) — |
The business fence is indeed drawn by the Gaode system; when directly mixed with OSM, the four‑boundary road‑based determination suffers systematic distortion.
Store↔Fence kind classification on both sides belongs to the same system, unaffected (kind count conversion remains consistent before and after, empirically verified).

## 6. Demo Capability List (as of v1.2.2)

Three‑step process: ① Contract → Region generation (four‑boundary reconstruction + road semantics + visual final review + conflict detection)
② Region semantic adjustment (@ full name + sub‑area selector + proposal evidence chain + apply/reject)
③ Analysis (Q1 fence health / Q2 gap four‑class classification / covering gaps).
Region data package hot switch (`/api/regions` + `/api/switch`), default Guangzhou
(38 fences / 33,109 stores / 33 contracts), see `data/README.md`.

---

## Invariants

- Specification set 00-08 v1.2.1: FROZEN, zero changes
- Layer discipline: adjustments only generate Layer‑D proposals, I‑B/I‑V expressed via Signal, human approval (GW)
- Knowledge governance three‑iron rules, anti‑Cherry‑pick, evidence chain hard acceptance (04/06)
