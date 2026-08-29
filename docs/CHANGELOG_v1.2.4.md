# SRAF Changelog — v1.2.4 (implementation: D14 multi-component territory)

Date: 2026-08-29. Normative spec set 00–08 unchanged (v1.2.1 FROZEN,
language normalized in v1.2.3). This records the D14 ontology fix.

## What changed (D14)

1. **Index**: `World.fences_by_dealer` (1:N, all blocks) + `fences_of(dealer)`;
   `fence_by_dealer` retained for backward compat (first block).
2. **Transfer semantics** (`adjust.py`): area resolution is dealer-scoped;
   `select_area` runs over the UNION of all blocks; `apply_proposal` re-clusters
   remaining stores into N hulls (2 km connected components) — no span-hull.
3. **Proposal contract**: `sub_ring` → `sub_rings: list[ring]`; API/frontend
   render each ring separately (multi-ring safe).
4. **Density**: `impact.py` and `health.py` divide by summed territory area
   (`territory_area_km2`), not one block; `run_q1` one report per dealer.
5. **Guard**: same-dealer check compares dealer names (blocks can share dealer).
6. **Consumers**: `demo_server` 6 sites (analysis/generate/adjust payload/
   apply fence_areas·fence_blocks/add_contract now allows extra block);
   `llm.py` guard; `intel_report --q3` dedupes by dealer.

## Evidence

- 10 new unit tests (`tests/test_multicomponent.py`); external
  `market_partition` tests now skip cleanly (23 tests: 21 pass + 2 skip).
- All gates: ref_check 145, consistency 83/83, browser UI multi-block
  transfer verified (合诚杰 2 blocks → cleared, target +1 block, 38→37,
  no span-hull, store count conserved 33,109).
- Real-data finding recorded: 9/37 dealers multi-block; 国之林 3 blocks
  IoU 0.81 ⇒ multi ≠ hard; the dominant IoU limiter is LOW FIDELITY
  (25/37 Class C), see docs/FOUR_BOUNDS_RECONSTRUCTION_SPEC.md.

## Knowledge base

K-PRIN-007 (multi-component is legal; continuity is preference) added,
v0.4.0, 32 entries.
