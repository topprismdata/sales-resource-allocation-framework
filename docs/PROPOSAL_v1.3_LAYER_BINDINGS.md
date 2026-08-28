# PROPOSAL v1.3 — Organizational Layer Instantiation Binding and Cross-Layer Interfaces (Layer Bindings & Interfaces)

- Status: Draft (proposal, proceeding with NORMATIVE_OWNERSHIP process; after approval, move to CHANGELOG v1.3)
- Date: 2026-08-28
- Proposer: zcode
- Affected specs: 03 (new §17A Layer Bindings + CP05), 07 (interface I-D/I-B belongs to Adapter boundary), 05 (cross-layer signaling goes through ProblemRouter)
- Basis: World Model v2.1 §2A three-level independent decision layers; user decision D10 "Each layer independent, do not interfere"

---

## 1. Problem Statement (Why this proposal is needed)

Spec v1.2's DP03/DP05/DP06/DP07 are **layer-agnostic abstractions**, but do not declare their instantiation binding in the distribution organization
Layer (manufacturer → dealer → field sales rep) **instantiation binding**. Consequences:

1. Implementers cannot determine whether "field sales rep beat design" should reuse DP03 or create a new problem (prior to this proposal, SRAF implementation skipped Layer-B directly for visit—error has been corrected)
2. Cross-layer handover (dealer store list → beat design → scheduling) lacks a formal interface contract, inter-layer coupling risk is uncontrolled
3. 04 diagnostic routing cannot "locate layer first then attribute" — missing layer registry

**This proposal does not add new DP** (reuses existing schema, conforming to "must not own another schema" rule), only adds: layer binding declarations, cross-layer interface contract, one Composite Problem.

---

## 2. Organizational Layer Registry (03 new §17A Layer Bindings)

```yaml
OrgLayer:
  Layer-D:
name: Dealer Region Layer
decision_owner: Manufacturer City Manager          # dedicated patch responsibility
    problems: [DP03@dealer, DP04@dealer]
    world_slice: [Contract, TerritoryDesign(F1/F2), MarketFeature,
ServiceLocation, SupplyEvent derived state]
    output_interface: I-D
  Layer-B:
name: Field Sales Rep Beat Layer
decision_owner: Dealer Owner + Supervisor        # Manufacturer Supervisor Co-visit Correction (no change of decision)
problems: [DP03@rep(Beat), DP05(frequency), beat_sequencing(DP07-L1)]
    world_slice: [OrgUnit, SalesRepRole, Beat, CoveragePolicy,
I-D output (immutable)]
    output_interface: I-B
  Layer-V:
name: Visit Scheduling Layer
decision_owner: Field Sales Rep / Scheduling System
    problems: [DP06, DP07]
    world_slice: [Calendar, Capacity, TravelMeasure,
I-B output (immutable)]
output: VisitSchedule (write-back to World Model as observation)
```

**Instantiation declaration**: `Territory`/`Responsibility`/`Resource` as layer generics —

```text
DP03@dealer: Territory=DealerTerritory(fence), Responsibility=Distribution Responsibility, Resource=dealer
DP03@rep:    Territory=Beat(beat),       Responsibility=Visit Responsibility,   Resource=field sales rep(SalesRepRole)
```

Schema completely reuses 03 §13, only binding differs; `TerritoryMembership` in the two instances
respectively correspond to fence membership relationship and beat membership relationship, not confused with each other

---

## 3. Interface Contract (07 new, Adapter boundary object)

```yaml
InterfaceContract:
  I-D:  # Layer-D → Layer-B
    payload:
store_dealer_assignment:      # store_id → dealer_id, includes effective interval
identity_snapshot_id:         # 08 §20 binding
direct_supply_flags:          # kind ∈ {DIRECT, DIRECT_IN} tag (does not enter B layer gap)
immutability: B layer must not modify assignments; when anomaly found → send Signal(layer=D) to 04 routing
versioning: world_snapshot_id binding; I-D change = E6 event, B layer full re-evaluation

  I-B:  # Layer-B → Layer-V
    payload:
      beat_assignment:              # store_id → beat_id → rep_id
coverage_policy:              # store_id → {min, preferred, max} frequency (DP05 schema)
beat_calendar:                # beat_id → visit day pattern
immutability: V layer must not change members/frequency; if cannot schedule → Signal(layer=B)
versioning: contract_version binding; I-B change = E11 event, V layer incremental reschedule
```

**Cross-layer discipline (incorporated into 03 §1 core principles)**:

```text
1. Upstream interface output = downstream immutable input (ProblemProjection's immutable_objects)
2. Downstream infeasible/anomaly → Signal(suspected layer) → 04 ProblemRouter locate layer → attribution within that layer
3. Each layer's objective function does not reference others (D layer does not optimize routing efficiency; V layer does not manage beat division)
4. In-layer events are handled within the layer: E6 → D layer, E10/E11 → B layer; cross-layer impact only via interface signals
5. Each layer independently goes through CandidateDecision → Approval → ApprovedDecision (02 process)
```

---

## 4. CP05 — Beat Design (03 new §21A)

```text
CP05 Beat Design = DP03@rep + DP05 + beat_sequencing(DP07 capability L1 tier)
mode: sequential (determine area → determine person → determine frequency → determine beat)
```

Answer the ten questions of 03 §2 (Layer-B main question):

```text
Business Problem: Within the dealer organization, how to allocate field sales rep beat routes (fixed point → fixed area → fixed person → fixed frequency → fixed route)
World State: I-D assignment (fixed) + field sales rep roster + store tier + existing beat routes (baseline)
Allowed changes: TerritoryMembership@rep, ResponsibilityAssignment@rep,
CoverageCommitment (frequency), beat sequence
Immutable: I-D assignment, field sales rep headcount (E10 other personnel), store identity, direct supply store assignment
Must satisfy: Each store belongs to exactly one beat (prevent overlap + prevent white area); load ≤ capacity (K-BENCH-003);
KA special assignment; frequency schedulable (DP06 oracle pre-check, 03 §8)
Optimization preference: compact territory, balanced load, minimal disruption (K-RULE-012 four principles)
Feasible: full assignment + capacity feasible + frequency schedule feasible
Better: balance ↑ compactness ↑ change ↓ (stability budget, K-CONST-002)
Explain to business: beat list + frequency table + change delta + per-store assignment rationale
Failure semantics: F1 prerequisite (I-D missing / identity low confidence not entering structural decision), F4 capacity infeasible,
F5 structural infeasible, F7 timeout — all classified per 03 §10, silent empty output prohibited
```

---

## 5. Impact on Existing Documents

| Document | Action |
|---|---|
| 03 | Add §17A tier binding, §21A CP05, §1 inter-tier discipline three lines |
| 07 | Add I-D/I-B interface object definition (Adapter boundary) |
| 05 | ProblemRouter add tier registry routing (Signal carries suspect_layer) |
| DESIGN.md | P0-1 status update |
| 04 Design | Diagnostic engine first step = tier localization (Signal.suspect_layer) |

## 6. Acceptance (Proposal Approval Criteria)

1. DP03@rep and DP03@dealer projection fields enumerable and schema same origin
2. I-D/I-B serializable, versionable, can serve as immutable projection entering downstream testing
3. A cross-tier case can be executed: D-layer change → Signal → B-layer reassessment → I-B v+1 → V-layer incremental rescheduling
4. 04 diagnostic output must contain `suspect_layer` field
