# D14: Multi-Component Territory Ontology (Rev 2)

**Status:** IMPLEMENTED 2026-08-29 (all §5.1 changes shipped, §7 gates green:
> 23 tests OK / 145 refs / 83 consistency / UI multi-block transfer verified in browser)
**Date:** 2026-08-29
**Related:** K-PRIN-006, K-PRIN-007, D11 (logical merge), D13 (CRS)
**Review:** agent D14Reviewer found 3 Critical + 6 Important + 4 Minor in Rev 1;
all addressed below. Original findings archived at `/tmp/oracle_ladder.json`.

---

## 1. Problem Statement

`World.fence_by_dealer: dict[str, Fence]` maps dealer → the LAST fence
record for that dealer. When a dealer has multiple fence records (multi-
component territory), all but the last are silently dropped from this
index. Every downstream consumer that uses `fence_by_dealer[dealer]`
operates on an arbitrary single component.

Verified: 合诚杰 has 2 fence records (8.38 + 163.69 = 172.07 km²);
`World.fences` list retains both, but `fence_by_dealer` keeps only the
last one. This is the sole collapse point — the fence records themselves
are correctly loaded and retained in `World.fences`.

## 2. Root Cause

The bug is **not** in the geometry format (region.json already stores
multiple fence records per dealer via separate entries). The bug is in
the **dealer→fence resolution index**:

```python
# world.py:90 — last-seen wins, earlier components silently dropped
self.fence_by_dealer = {f.dealer: f for f in self.fences}
```

Additionally, `_match_dealer` (adjust.py:63–82) resolves a dealer name
to a single Fence via the same collapsed index, which means both the
rules and LLM adjustment paths operate on an arbitrary single component.

## 3. Corrected Ontology

Following docs/01 §43 (Territory: "zero polygon / multiple polygons /
non-contiguous geography") and DESIGN.md D6 (F1 normative / F2 artifact /
F3 derived):

```text
Territory (dealer name string = LA_BAUnit-like administrative identity)
  ├── Component 1 (Fence: ring, area_km2, …)
  ├── Component 2 (Fence: ring, area_km2, …)  ← may be spatially disjoint
  └── …
```

The fix is to **replace the collapsed index with an honest 1:N mapping**:

```python
# BEFORE (world.py:90)
fence_by_dealer: dict[str, Fence]              # last-seen wins

# AFTER
fences_by_dealer: dict[str, list[Fence]]       # all components retained
```

### Scope limitation

docs/01 §43 also requires Territory to support "zero polygon" and
"nationwide account list" modes. This revision covers only **geographic
field territories** (1..N rings). Account-list and zero-polygon modes
remain out of scope (deferred to future work).

## 5. Impact Analysis (complete caller inventory)

### 5.1 Files that MUST change

| # | File | Function/Line | Current | Change |
|---|---|---|---|---|
| 1 | `intelligence/world.py:90` | `__init__` | `fence_by_dealer = {f.dealer: f}` | → `fences_by_dealer = defaultdict(list)`; also fix `with_stores:102` and `with_fences:113` which copy the same collapsed index |
| 2 | `intelligence/world.py:119-120` | `fence_stores()` | returns `by_dealer[dealer]` (stores, OK) | unchanged |
| 3 | `intelligence/adjust.py:63-82` | `_match_dealer()` | dedupes by dealer name, returns ONE Fence | must return dealer-scoped component list (or a DealerRef namedtuple) |
| 4 | `intelligence/adjust.py:233-264` | `parse_and_propose` → `build_proposal` | uses `_match_dealer` result as single Fence | accepts component list; `select_area` aggregates stores across all components |
| 5 | `intelligence/adjust.py:283-293` | `apply_proposal` | rebuilds ONE hull per dealer from remaining stores | rebuild N hulls via connected-component clustering of remaining store points (see §6.1) |
| 6 | `intelligence/adjust.py:262-263` | same-dealer guard | compares `area_id` | must compare `dealer` name (with N components, same-dealer/different-component would pass current check) |
| 7 | `intelligence/adjust.py:225-230` | `Proposal.sub_ring` | single ring | → `sub_rings: list[ring]` (MultiPolygon safe) |
| 8 | `intelligence/llm.py:88-89` | `llm_parse_command` | uses `_match_dealer` (shared) | inherits fix from #3 |
| 9 | `intelligence/impact.py:27-30` | `move_impact` | `density_per_km2` divides by ONE component's `area_km2` | sum component areas for dealer-level density |
| 10 | `tools/demo_server.py:350` | `fence_stores(orig)` in `/api/adjust` | uses single fence from collapsed index | use all fences of dealer |
| 11 | `tools/demo_server.py:560-562` | `/api/generate` area_est | from last-seen component only | sum across all components of dealer |
| 12 | `tools/demo_server.py:686` | `/api/apply` `pack['fence_areas']` | `{f.dealer: f.area_km2}` last-seen | sum or list per dealer |
| 13 | `tools/demo_server.py:394-395` | `/api/add_contract` | rejects second fence/contract for existing dealer | allow if different component (multi-component legal) |
| 14 | `tools/demo_server.py:349-351` | `/api/analysis` | `fence_health` on one component vs ALL dealer stores → density understated | aggregate across components |
| 15 | `tools/intel_report.py:52-57` | Q3 analysis | requires `len(src)==1`; fails on multi-component dealers | accept component list |

### 5.2 Files verified NOT to break

| File | Reason |
|---|---|
| `intelligence/health.py` | iterates `w.fences` (flat list) — unchanged |
| `intelligence/classify.py` | iterates stores — unchanged |
| `intelligence/roadsem.py` | OSM barriers — unchanged |
| `intelligence/knowledge.py` | loads KB — unchanged |
| `intelligence/coords.py` | per-coordinate-pair conversion — unchanged |
| `intelligence/geom.py` | pure geometry — unchanged |

### 5.3 Knowledge / governance rollout

| File | Change |
|---|---|
| `knowledge_base/knowledge_items.json` | add K-PRIN-007; bump `_meta.version` to 0.4.0 |
| `knowledge_base/KNOWLEDGE_BASE.md` | add K-PRIN-007 row; bump version |
| `docs/DESIGN.md` §5 | add D14 ADR row |
| `README.md` | update "D1–D13" mentions to "D1–D14" |
| `AGENTS.md` | K-PRIN-007 reference already present; no change needed |

## 6. Downstream Semantic Changes

### 6.1 Transfer (adjust.py `apply_proposal`)

**Before:** drop src/dst fences, rebuild ONE hull per dealer from remaining stores.

**After:**
1. Move stores in affected components from src to dst
2. For each affected dealer, re-derive components from remaining stores:
   - Cluster store points by spatial proximity (connected components
     within `r` km, `r` = 2.0 km default, tunable)
   - Each cluster → one TerritoryComponent (convex hull ring)
   - This is a **refinement of D11**: D11 said "convex hull of stores"
     (singular). We extend to "convex hull per spatially-disconnected
     store cluster" (plural). The principle (store reassignment = only
     fact, hull = derived view) is unchanged.
3. Zero-store dealers → zero components (fences removed)
4. `area_id` policy: reuse original first-record `area_id` for component 0;
   new components get `{area_id}-2`, `{area_id}-3`, etc.

### 6.2 Area selector

`select_area` operates on the **union polygon** of all components of the
source dealer (spatial union, not per-component). Stores are selected
from this union as before. This ensures that "entire region" and
"half-region" selectors work across components.

### 6.3 Proposal contract change

```python
# BEFORE
sub_ring: tuple[tuple[float,float], ...]  # single ring

# AFTER
sub_rings: list[list[tuple[float,float]]]  # list of rings (MultiPolygon safe)
```

API payload `/api/adjust` changes from `sub_ring` to `sub_rings` (list).
`demo_page.html` renders each ring as a separate polygon.

### 6.4 Same-dealer guard

`parse_and_propose` currently guards `src.area_id == dst.area_id`.
With dealer-scoped resolution, this becomes `src_dealer == dst_dealer`
(string comparison), which is correct at component level.

### 6.5 Impact / density

`move_impact`'s `density_per_km2` must divide dealer store count by the
SUM of all component areas, not one component's area.

## 7. Validation Plan (exercises the changed code)

### 7.1 New unit tests (target: tests/test_multicomponent.py)

| Test | Verifies |
|---|---|
| `test_fences_of_returns_all_components` | World with 2 fences for same dealer → `fences_of(dealer)` returns 2 |
| `test_match_dealer_returns_list` | `_match_dealer` with multi-component dealer → component list |
| `test_transfer_single_component` | 1-component src transfer → dst gains stores, src loses |
| `test_transfer_multi_component` | 2-component src transfer → all affected stores move |
| `test_transfer_zero_store_removal` | 0-store dealer after transfer → 0 fences |
| `test_proposal_multi_ring` | build_proposal on multi-component src → `sub_rings` has N rings |
| `test_persist_roundtrip_multi` | `_persist_pack` writes N records per dealer; `_load_pack` reads them back |
| `test_same_dealer_guard` | src and dst are same dealer (different components) → rejected |
| `test_density_multi_component` | impact density uses summed area, not single component |
| `test_store_dealers_pip_consistency` | `store.dealers` matches geometric PIP against all components |

### 7.2 Integration smoke (via demo_server)

1. Start server on data/gz
2. `/api/bootstrap` → verify all rings emitted for multi-component dealers
3. `/api/adjust` with 合诚杰 (2-component dealer) → proposal succeeds
4. `/api/apply` → fence_areas contains all components
5. `/api/switch` back → verify round-trip
6. `intel_report --q3 --fence 合诚杰` → passes (currently fails with "匹配歧义")

### 7.3 Existing gates (must not regress)

| Gate | Expected |
|---|---|
| `ref_check.py` | 145 refs |
| `consistency_check.py` | 83/83 |
| `unittest discover tests` | 13 pass |
| `gen_compare_data.py` | 38 dealers, median IoU ≈ 0.495 |
| Browser `/compare` | multi-block dealers render all components |

## 8. Known Conflicts Resolved

### 8.1 D11 amendment (fence rebuild semantics)

D11 originally: "Territory fence = convex hull of the dealer's stores
(derived view)" — singular. **Amended to:** "Each spatially-disconnected
cluster of the dealer's stores → one convex hull component (derived
view)." The clustering rule (§6.1 step 2, r=2.0 km connected components)
is the only addition. The principle (store reassignment = only fact,
fence = derived view) is unchanged.

### 8.2 Area conservation clarification

D11 conserves **store count** (each store assigned to exactly 1 dealer).
Area (km²) is a statistical view of the derived hulls and is NOT
conserved (hulls may overlap other territories). §7.6 of the previous
revision incorrectly cited D11 for area conservation. Corrected.

### 8.3 F2 citation correction

§3 previously cited "docs/01 §F2". The three-layer fence ontology
(F1 normative / F2 artifact / F3 derived) is defined in **DESIGN.md
D6**, not as a numbered section in docs/01. The multi-polygon
requirement is docs/01 **§43** ("multiple polygons / non-contiguous
geography"). Corrected to cite §43 and D6.

### 8.4 Evidence correction

合诚杰 total is **172.07 km²** (8.38 + 163.69), not "163 km²" as
previously stated.

### 8.5 Terminology note

`D14` is already used in docs/06 as a cause code ("Unknown /
Insufficient Evidence"). This ADR's D14 is a DESIGN.md decision number
— the collision is inherited from the existing D10–D13 ADR numbering
and is noted but not renamed.

### 8.6 Out of scope (explicit)

- Account-list / zero-polygon territory modes (docs/01 §43)
- Rep fences crossing dealer boundaries (reps.json has no dealer key;
  join is analysis, not world model)
- Cross-pack CRS (impossible within one pack per D13)
- LADM / ISO 19152 (land administration, not commercial territory)

## 9. Rollback

`git revert` of the implementation commit. Data files unchanged.
Single-component dealers (the majority) unaffected: `fences_of(dealer)`
returns `[Fence]` (list of 1), and callers that unwrap the single
element behave identically to the previous direct reference.
