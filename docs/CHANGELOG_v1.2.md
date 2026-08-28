# SRAF Specification Changelog — v1.2

v1.2 is the **second implementation baseline** after external review of v1.1 Implementation Baseline.

This version does not add features, but fills foundations and fixes hard errors.

---

## P0 changes applied

### 1. New addition `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`

World Model's "identity truth" foundation. Core content:

```text
Four unconfusable boundaries
    Identity Resolution  != Deduplication
    Entity Merge         != Source Record Merge
    Account              != ServiceLocation
    Identity Confidence  != Business Truth

Conceptual hierarchy L1 Evidence / L2 Linkage / L3 Semantic / L4 Governance

Decision rules for eight real-world scenarios
    Same Entity / Duplicate / Same Account+Different Location
    Relocation / Rename / Split / Merge / False Match(Unmerge)

Supersede vs Merge separation
Hierarchical and group identity (chain: Group / store / location three layers + PART_OF temporal validity)

MatchDecision three-state + threshold defined by error rate (λ/π) instead of raw score
Survivorship decoupled from identity (fields can be automatic, identity cannot be automatic)
Anti-chaining constraint (prohibiting unconstrained transitive closure clustering)
Temporal Identity (resolution append-only + snapshot solidifies identity decision set)
IdentityConfidence compositionalization + prohibiting confidence loss on derivation chain

Identity Invariants I20–I30 (merged into B0, violation means Benchmark failure)
Identity Benchmark ID01–ID20 + Identity Gate
```

Key design consequence: **`04`'s H-DATA assumption changes from unverifiable to verifiable**.
Before this, `DataQualityIssue` was a catch-all label;
Now there are subtypes, tests, thresholds, and blocking rules.

### 2. Fix schema-level typos

```text
02 §80  approved_approved_decision_id
     -> approved_decision_id
```

### 3. Unify version wording

Eliminate mixed `v1.0` / `v1.1` in body text (46 occurrences across 00/01/02/04/05/06/07),
Normative statements unified to current baseline version.

Retained `v1.0` mentions are only in two categories, both correct usage:

```text
Historical references in CHANGELOG / README / CONSISTENCY REPORT
06 §108 Benchmark Case's own version example (case v1.0 -> case v1.1),
with note explaining it is unrelated to specification document version
```

---

## P1 changes applied

### 4. Supplement `v1 Engineering Envelope` (07 §110A)

Not a system upper limit, but an engineering contract for DecompositionPlanner / SolverRegistry /
Projection Cache / Benchmark:

```text
S  Interactive            <=5k Resp Units / <=50 Res      seconds
M  City/Regional Planning 5k-50k / 50-300                 minutes
L  Structural Batch       50k-200k / 300-1,000             tens of min - hours
```

Also binding Phase 0–3 minimum commitment tiers, each tier's computation strategy switching,
and "exceeding L tier triggers Aggregation/Sampling review instead of silently degrading precision".

`06 §55 Scale Benchmark` adds constraint:
reported scale must cover corresponding Phase tier upper bound.

### 5. Supplement 3 Governance Workflow minimum semantics (05 §14A)

```text
GW01 WorldModelRepair
GW02 ModelGovernance
GW03 PolicyReview
```

Unified discipline: default A0/A1, prohibit A2/A3, no direct modification to Canonical World,
output "correction proposal + governance decision" instead of resource allocation Candidate,
must trigger downstream Artifact STALE.

Clarify boundary between `GW03` and `RequirementExceptionProposal`:
Proposal is exception within single Case, GW03 is cross-Case Policy semantic revision entry point.

`02 §93/§94` routing table synchronously supplements `ModelGovernance` and points to §14A.

### 6. Cross-reference closure

```text
00 P21        Assignment table joins 08
01 §1.1       ExternalIdentifier / IdentityResolutionRecord -> 08
01 §9/§10     Canonical ID principle retained, schema deduplication and points to 08 (eliminating P21 violation)
01 §71        New addition IdentityConfidence / IdentityStatus quality status
01 §72        AssertionConflict's identity conflict form -> 08
02 §21        Has 4 DataQualityIssue identity subtypes
03 §3         Contract new addition identity_snapshot_id / min_identity_confidence
03 §10        F1 DATA_INFEASIBLE's identity cause + prohibit misdiagnosis as F4
04 §10        H6 new addition IdentityConfidence (and prerequisite for other confidences)
04 §22        H-DATA references 02/08, no redundant definition
04 §24        Add IdentityIntegrityTest (4 sub-tests) + Materiality linkage
05 §1A        Ownership added to GovernanceWorkflow GW01–GW03
06 §5         Add I20–I30 pointer + §6 decision rule attribution description
06 §55        Reference 07 §110A
06 §86        Supplement Matched Control industrial empirical source (see §7)
07 §15        Point to 08 + module placement + storage constraints + degradation rules when MDM already exists
```

---

## 7. Literature Anchoring (new, improve defensibility)

`06 §86` supplement a real industrial comparative study as normative basis:

```text
Zoltners, Sinha & Lorimer,
Sales Force Design for Strategic Advantage (Palgrave Macmillan, 2004),
Table 8.3 + p.318-319
```

This study uses after realignment the 'change of responsible person' test account group vs
unreplaced control account group measures disruption impact,
Results show impact **only concentrated in medium-sized accounts** ($50–100k),
Small accounts and super-large accounts are not significant.

Thus two normative implications arise:

```text
1. Matched Control (V1 evidence design) is truly feasible in sales territory decisions,
not a purely theoretical requirement.
2. ChangeCost.CustomerRelationshipCost must be estimated by account size /
relationship strength segmented estimation, prohibiting a single global disruption coefficient.
```

`08 §26` additionally provides the external reference list for this specification:
Fellegi–Sunter three-state decision and error rate upper bound, Papadakis/Christen ER review,
Papadakis 2023 criticism of 'overly easy' ER benchmarks (→ enforce hard negative examples),
MDM golden-record survivorship / unmerge lineage practice,
Snodgrass bitemporal and Kimball late-arriving dimension.

---

## 8. Known Gaps (v1.3 candidate, this version only registers, does not implement)

After detailed reading of the above monograph, two SRAF missing components were found, unrelated to Identity,
Therefore not merged into this version, but must be explicitly charged to avoid loss:

> Update (v1.2.1): these two items have been re-graded in `CHANGELOG_v1.2.1.md`——
> G1 upgraded to DP01 pre-gate, G2 postponed to DP04 production. This section remains as historical record.

```text
G1 Carryover / response lag not modeled
Monograph Ch7 (Fig 7.3, Table 7.3/7.9):
This year's sales = this year's effort + prior-year carryover;
In high carryover environment, only looking at single-year impact systematically underestimates the long-term effect of size changes.
Risk: If SalesResponseEstimate attributes 'last year's effort output' to
this year's Candidate -> DP01/DP05 gain inflated,
B4 Validation observation window mismatch (treating lag effect as invalid).
Suggestion: OpportunityEstimate / SalesResponseEstimate add
impact_horizon and carryover_share declarations;
DecisionValidationPlan enforces minimum_lag_window.

G2 DP04 fairness and compliance risk level insufficient
Monograph p.329-330 explicitly: personnel matching must use
'consistent, objective, defensible' standards, and point out legal risk.
SRAF currently classifies fairness as Preference (03 DP04 / 02 §43).
Suggestion: raise 'prohibit raw performance without territory correction as target'
from convention to DP04 Invariant example,
and require protected-attribute related rules to enter the Requirement layer
rather than scattered in heuristics.
```

---

## 9. Not Done This Round (explicitly excluded)

```text
Not entering visit-scheduling-optimizer code Gap Analysis (Step 4)
No new DP08 or any new Atomic Decision Problem added
No new storage component introduced (identity still resides in PostgreSQL)
No modification to the principle set of 00 Charter (only supplemented row 08 of the attribution table)
```

---

## Implementation restraint (inherits v1.1 and strengthens)

```text
Modular Monolith First
No dedicated graph DB in Phase 0–3
No generic BPMN requirement in Phase 0
No new solver platform before the vertical slice proves need
No enterprise MDM rebuild: When an MDM already exists, SRAF acts as a consumer.
But Identity Gate still must run through upstream outputs (07 §15 / 08 §23.4)
```
