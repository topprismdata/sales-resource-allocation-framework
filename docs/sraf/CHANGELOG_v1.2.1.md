# SRAF Specification Changelog — v1.2.1 (documentation hotfix)

v1.2.1 is a **documentation-only hotfix** on top of the v1.2 Implementation
Baseline. No architecture changes. The baseline stays **frozen** and ready
for the engineering phase.

## Why a hotfix and not v1.3

The v1.2 review found exactly one semantic residue and reprioritized the two
deferred gaps. Neither touches ownership, contracts, or the benchmark stack,
so this is a patch-level cleanup, not a new baseline.

---

## 1. Fixed — MissedOpportunity semantic residue (2 places in 02)

`MissedOpportunity` reads as "confirmed lost sales," which conflicts with the
frozen principle that **Opportunity is an Estimate**. 01 and 04 already use
only the estimate-correct terms; 02 had two leftovers.

```text
02 §7  Health Metric:
    MissedOpportunity        -> OpportunityAtRisk
02 §36 BusinessObjective example:
    ReduceMissedOpportunity  -> ReduceOpportunityAtRisk
```

Canonical estimate-correct vocabulary (01 §26 / 02 §13 / 04):

```text
UncoveredOpportunity
OpportunityAtRisk
UnderServedOpportunity
```

Not changed (correct as-is, not the forbidden term):

```text
02 §22  "missed required calls = high"   (service-execution evidence, not an
                                         opportunity metric name)
03 DP01 "Reduce missed profitable coverage"  (prose objective, coverage-framing)
```

## 2. Regression lock — added to consistency_check.py

```text
MissedOpportunity term eliminated (v1.2.1 hotfix)
UncoveredOpportunity/OpportunityAtRisk present in 02
```

The forbidden term now fails the check if it ever reappears in any spec.

## 3. Reprioritized the two deferred v1.2 gaps

The v1.2 CHANGELOG §8 listed both as generic backlog. Per review, they are
**not** equal priority:

```text
G1 Carryover / sales-response lag   -> ELEVATED to a DP01 Prerequisite Gate
G2 DP04 fairness & defensibility    -> stays deferred until DP04 production
```

### G1 → DP01 Prerequisite Gate (now written into 03 §DP01)

Sales effort affects sales across periods: current-year sales = this-year
effort + prior-year carryover. A sizing model that reads only the first year
systematically underestimates the long-run impact of a size change and
over-attributes prior effort to the current candidate.

New binding text in `03_DP01`:

- before implementing any DP01 Sizing Engine, `SalesResponseEstimate` /
  `OpportunityEstimate` must declare `impact_horizon` and `carryover_share`
  (or an equivalent lag parameter);
- `DecisionValidationPlan` (02 §86) must declare a `minimum_lag_window` so a
  delayed real effect is not mis-scored as `Failed`.

This is now a **Gate**, not a note: it blocks DP01 build, matching the
"must be resolved before entering DP01" requirement.

### G2 → still deferred (does not block)

The first vertical slice is DP06, not DP04, so DP04 fairness/defensibility
(currently a Preference; arguably an Invariant) stays parked until DP04
production work actually begins. Recorded here so it is not lost.

---

## Status after v1.2.1

```text
SRAF overall architecture            FREEZE
World / Decision / Problem ownership FREEZE
Identity foundation (08)             FREEZE, implementable
Engineering Envelope (07 §110A)      FREEZE
Governance Workflows (05 §14A)       FREEZE
Benchmark framework (06)             FREEZE
MissedOpportunity residue            FIXED (this hotfix)
Carryover                            GATED at DP01
DP04 fairness                        DEFERRED to DP04 production
Consistency check                    83/83 PASS
```

## Next task (unchanged)

Stop expanding SRAF docs. Enter **Step 4**: gap-analyze the existing
`visit-scheduling-optimizer` against `03` DP06 Contract and `07` Reference
Engine Contract (§48–51), item by item. This is the first real test of whether
the specs are implementable, rather than self-consistent on paper.
