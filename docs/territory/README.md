# SRAF Specification v1.2.1 — Implementation Baseline

This package is the normalized implementation baseline after the v1.1
external review. It adds the missing identity foundation and fixes the
hard errors found in v1.1.

## Normative specs

- `00_PROJECT_CHARTER.md`
- `01_WORLD_MODEL_SPEC.md`
- `02_DECISION_ONTOLOGY.md`
- `03_DECISION_PROBLEM_CONTRACTS.md`
- `04_ALLOCATION_INTELLIGENCE.md`
- `05_DECISION_ORCHESTRATION.md`
- `06_EVALUATION_AND_BENCHMARK.md`
- `07_REFERENCE_ARCHITECTURE.md`
- `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`

## Supporting files

- `NORMATIVE_OWNERSHIP.md`
- `CHANGELOG_v1.1.md` (historical)
- `CHANGELOG_v1.2.md`
- `CHANGELOG_v1.2.1.md` (documentation hotfix)
- `CHANGELOG_v1.2.2.md` (implementation: area-first adjust + logical fence merge)
- `CHANGELOG_v1.2.3.md` (documentation language normalization to English)
- `CHANGELOG_v1.2.4.md` (implementation: D14 multi-component territory)
- `CONSISTENCY_CHECK_REPORT.md`
- `SHA256SUMS.md`

## Status

Architecture is **FROZEN** and ready for the engineering phase.

Implementation progress on top of the baseline lives in `DESIGN.md`
(living design document). The 00-08 specs themselves are unchanged.


Use **v1.2.4** as the current state of the **v1.2 Implementation Baseline**.
v1.2.1 was a documentation-only hotfix; v1.2.2 records implementation progress;
v1.2.3 normalizes the documentation language to English with zero semantic
change (specs 00-08 content unchanged).

v1.0 is the historical design record. v1.1 was the first implementation
baseline after the v1.0 consistency review.

## What v1.2 adds

```text
08 Canonical Identity & Entity Resolution  (new normative spec)
   Identity Resolution != Deduplication
   Entity Merge != Source Record Merge
   Account != ServiceLocation
   Identity Confidence != Business Truth
   Eight real-world identity cases with decision rules
   Three-way MatchDecision bounded by error rates, not raw scores
   Identity Invariants I20-I30 and Benchmark ID01-ID20
   Makes 04's H-DATA hypothesis testable

07 §110A v1 Engineering Envelope           (S / M / L + Phase binding)
05 §14A  Governance Workflows GW01-GW03    (repair / model / policy)
02 §80   approved_decision_id typo fix
02 §21   four DataQualityIssue identity subtypes
Whole-set version wording normalized to v1.2
```

## Open items after freeze

Not architecture work — these are gates/deferrals tracked against the build
sequence:

```text
G1 Carryover / sales-response lag
   ELEVATED to a DP01 Prerequisite Gate (now written into 03 §DP01):
   must declare impact_horizon + carryover_share, and
   DecisionValidationPlan.minimum_lag_window, before DP01 Sizing is built.

G2 DP04 fairness & defensibility
   Deferred until DP04 production work begins (first vertical slice is DP06,
   so this does not block).
```

Details in `CHANGELOG_v1.2.1.md`.

## Implementation restraint

```text
Modular Monolith First
No dedicated graph DB in Phase 0-3
No generic BPMN requirement in Phase 0
No new solver platform before the vertical slice proves need
No enterprise MDM rebuild; Identity Gate still must pass on upstream output
```

## Next step

Step 4 of the agreed sequence: gap analysis of the existing
`visit-scheduling-optimizer` against `03` DP06 Contract and `07` §48-51,
then Vertical Slice v1.
