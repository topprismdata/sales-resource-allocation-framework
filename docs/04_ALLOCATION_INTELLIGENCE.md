# SRAF Allocation Intelligence Specification v1.2

**Project:** Sales Resource Allocation Framework  
**Document:** `04_ALLOCATION_INTELLIGENCE.md`  
**Status:** Implementation Baseline v1.2  

**Upstream Specification:**
`00_PROJECT_CHARTER.md`, `01_WORLD_MODEL_SPEC.md`, `02_DECISION_ONTOLOGY.md`, `03_DECISION_PROBLEM_CONTRACTS.md`

---

## 1. Document Objectives

Allocation Intelligence answers:

```text
1. Is the current sales resource allocation healthy?
2. Where is there a Demand–Supply mismatch?
3. Why did this mismatch occur?
4. Is the problem important enough to justify re-decision?
5. Which Decision Problem should be created?
```

Core chain:

```text
WORLD STATE
    ↓
DERIVED ALLOCATION STATE
    ↓
ALLOCATION HEALTH
    ↓
GAP DETECTION
    ↓
ROOT CAUSE DIAGNOSIS
    ↓
MATERIALITY
    ↓
DECISION TRIGGER
    ↓
PROBLEM ROUTER
    ↓
DECISION CASE
```

It does not directly produce the final Territory, Headcount, or Schedule.

---

## 1A. Normative Ownership

This file is the sole owner of:

```text
Allocation Health dimensions
Gap subtype taxonomy
DiagnosticTest
DiagnosticHypothesis ranking rules
Materiality logic
DecisionTrigger rules
ProblemRouter
AllocationDecisionSignal
```

The `AllocationGap` base class and `DecisionCase` schema remain owned by 02.

---

## 2. Core Abstraction: Demand–Supply Matching

```text
MARKET SIDE
   ↓
Opportunity
   ↓
Coverage Need
   ↓
Workload Demand
   ↓
      MATCH
   ↑
Capacity Supply
   ↑
Resource Deployment
   ↑
RESOURCE SIDE
```

Demand includes at least Opportunity, Coverage, Workload, Capability, Spatial, and Temporal Demand.

Supply includes at least Capacity, Capability, Location, Availability, Mobility, ServiceChannel, and Responsibility Eligibility.

---

## 3. DerivedAllocationState

Standard derived states:

```text
OpportunityCoverage
CoverageAttainment
IntrinsicWorkload
NetworkWorkload
TotalWorkload
EffectiveCapacity
CapacityUtilization
TravelBurden
ServiceLevel
CapabilityFit
AssignmentStability
OpportunityAtRisk
UnfulfilledCoverage
```

All require calculation_version, input_snapshot, calculated_at, and confidence.

---

## 4. Multi-dimensional Health Profile

Do not default to generating only a single Territory Health Score.

Six dimensions:

```text
H1 Opportunity Health
H2 Service Health
H3 Capacity Health
H4 Spatial Efficiency Health
H5 Responsibility Health
H6 Stability & Confidence Health
```

Health Status: 

```text
Healthy
Watch
Degraded
Critical
Unknown
```

---

## 5. H1 Opportunity Health

Core:

```text
AddressableOpportunity
CoveredOpportunity
UncoveredOpportunity
OpportunityCoverageRate
OpportunityAtRisk
HighPriorityOpportunityCoverage
```

Opportunity is an Estimate, not confirmed sales revenue.

High Coverage Attainment does not equal high Opportunity Coverage.

---

## 6. H2 Service Health

Strictly distinguish:

```text
Coverage Need
      ↓
Coverage Commitment
      ↓
Scheduled Coverage
      ↓
Actual Coverage
```

A Gap may be, respectively, an Allocation Gap, Scheduling Gap, or Execution Gap.

---

## 7. H3 Capacity Health

Core:

```text
NominalCapacity
AvailableCapacity
EffectiveCapacity
CommittedCapacity
ResidualCapacity
CapacityUtilization
CapacityGap
```

Recommendation:

\[
Utilization =
AssignedWorkload / EffectiveCapacity
\]

Capacity Utilization must be interpreted jointly with Opportunity Coverage.

---

## 8. H4 Spatial Efficiency Health

Core:

```text
TravelBurden
NetworkWorkload
ServiceToTravelRatio
BaseLocationEfficiency
TerritoryAccessibility
CrossBoundaryTravel
RouteEfficiency
```

Compactness can only be an L1 proxy; for production decisions, prioritize Road Network; for major adjustments, Routing Simulation can be used.

---

## 9. H5 Responsibility Health

Core:

```text
AssignmentCompleteness
PrimaryOwnershipConflict
CapabilityFit
ResponsibilityOverlap
UnassignedResponsibility
OverlappingResponsibility
PersonnelFit
RelationshipContinuity
```

---

## 10. H6 Stability & Confidence Health

Stability: 

```text
AssignmentChurn
TerritoryChurn
RepMovement
CustomerOwnershipChange
TransitionFrequency
```

Confidence: 

```text
OpportunityConfidence
LocationQuality
TravelModelQuality
CoverageDataQuality
ResponsibilityEvidenceQuality
IdentityConfidence      (08 §16; whether the subject count is credible)
```

Low confidence must not trigger large-scale structural adjustments.

`IdentityConfidence` is special because it is **a prerequisite for other confidence levels**:
If the subject itself may be a duplicate or incorrectly merged,
then the high or low values of OpportunityConfidence and Workload have no decision significance.
Therefore H6 must first perform Identity Resolution, then interpret the other dimensions.

---

## 11. Gap Detection Contract

A Gap must answer:

```text
What?
Where?
How large?
Since when?
Compared with what?
Business impact?
Confidence?
```

Reference Type: 

```text
PolicyTarget
BaselineState
PeerBenchmark
HistoricalNorm
CapacityLimit
BusinessCommitment
ScenarioTarget
ModelExpectedValue
```

Gap Severity integrates Magnitude, Persistence, BusinessImpact, and Confidence.

---

## 11A. Coverage Gap v1.2 Subtypes

`CoverageGap` is uniformly subdivided along the Coverage Funnel into:

```text
CoverageAllocationGap
SchedulingCoverageGap
ExecutionCoverageGap
```

Corresponds to:

```text
CoverageNeed → CoverageCommitment
CoverageCommitment → ScheduledCoverage
ScheduledCoverage → ActualCoverage
```

02 defines only the parent object `CoverageGap`; this file is the normative owner of concrete subtypes.

---

## 12. Seven Types of Gap

```text
G1 CoverageGap
G2 CapacityGap
G3 OpportunityGap
G4 SpatialTravelGap
G5 CapabilityGap
G6 LocalAllocationGap
G7 StabilityGap
```

CoverageGap distinguishes CoverageCommitmentGap, SchedulingCoverageGap, and ExecutionCoverageGap.

CapacityGap distinguishes Global, Local, ResourceType, and Temporal.

`LocalAllocationGap` specifically refers to a case where global resources are generally feasible but local responsibility/resource allocation is imbalanced; it must not be abbreviated to the subtype `AllocationGap`.

OpportunityGap distinguishes Unserved, UnderServed, and Misallocated.

SpatialTravelGap distinguishes BaseLocation, TerritoryShape, RoadNetwork, CrossBoundaryTravel, and RouteStructure.

---

## 13. Diagnostic Causal Graph

The first version is a "business diagnostic map with assumed causal directions," not a strict scientific causal model.

```text
                  OPPORTUNITY GAP
                         ↑
                    COVERAGE GAP
                         ↑
        ┌────────────────┼─────────────────┐
        │                │                 │
   CAPACITY GAP     ALLOCATION GAP    CAPABILITY GAP
        ↑                ↑                 ↑
 RESOURCE      TRAVEL / LOCATION       RESOURCE
 SHORTAGE            / TERRITORY       SKILL GAP
        ↑
   COVERAGE POLICY
```

Data / Model Quality is always present on the outside.

---

## 14. DiagnosticHypothesis Test

Each Hypothesis should have:

```text
RequiredEvidence
SupportingTests
ContradictingTests
MinimumConfidence
AlternativeExplanation
```

It cannot rely solely on free LLM reasoning.

---

## 15. H-CAP: Capacity Shortage

Support:

```text
Global effective capacity < required workload
Multiple territories overloaded
Travel normal
Allocation balance normal
Capability fit acceptable
Coverage policy validated
Persistent opportunity at risk
```

Oppose:

```text
Total capacity sufficient
Travel abnormal
Neighbor idle capacity
Coverage policy inflated
Scheduling concentration explains gap
```

Utilization > 100% itself is insufficient to prove understaffing.

---

## 16. H-ALLOC: Territory / Allocation Imbalance

Support:

```text
Global capacity sufficient
Local utilization variance high
Opportunity/workload distribution uneven
Reallocation materially reduces gap
```

When all Territories are uniformly overloaded, it is more like Global Capacity Shortage.

---

## 17. H-LOC: Resource Location Mismatch

Support:

```text
Travel burden abnormal
Demand far from deployment base
Alternative deployment releases capacity
Territory shape not primary issue
```

Recommend calculating Capacity Released by Relocation.

---

## 18. ResourceEquivalent

`ResourceEquivalent` is a **Derived Metric** in `MetricRegistry`, not a Resource Entity, Headcount, or new World class.

It is used to convert different improvement approaches into comparable Capacity Effect:

```text
Reduce travel = +0.42 RE
Relax low-value coverage = +0.31 RE
Cross-territory support = +0.18 RE
Add one new rep = +1.00 RE
```

\[
ResourceEquivalent = GapWorkload / EffectiveCapacity_{Archetype}
\]

Must be within the same ResourceArchetype, Capability, and Time Horizon.

RE is not Headcount.

---

## 19. H-CAPABILITY

When Total capacity is sufficient but Eligible capacity is insufficient, route to Personnel Matching, Skill/Pool/Channel Substitution, etc., rather than adding headcount overall.

---

## 20. H-COVERAGE

If Coverage commitment drives overload, and low-value customers occupy large capacity, and Stress Scenario shows workload significantly decreases while Opportunity Coverage decreases slightly, then it is more likely a Coverage Allocation / Policy problem.

---

## 21. H-SCHED / H-ROUTE

Monthly workload feasible but weekday/spacing/time-window conflicts → DP06 Visit Scheduling.

Daily assignment reasonable but sequence/traffic/time-window cause travel too high → DP07 Daily Routing.

---

## 22. H-DATA / H-MODEL

DataQualityIssue must always be a top-level Alternative Hypothesis.

Data is correct but Opportunity/Travel/ServiceTime models have systematic bias → Model Governance.

**Identity sub-hypotheses**:

Identity-side subtypes of `DataQualityIssue`
 (`IdentityDuplicate` / `IdentityFalseMatch` /
`IdentityUnresolved` / `HierarchyMisattribution`) 
Owned by `02 §21`; judgment rules, thresholds, and human permissions are owned by `08`.
This file is only responsible for **how to test them** (see §24 `IdentityIntegrityTest`).

Without these subtypes, H-DATA is only an untestable garbage-bin label.

Diagnostic ordering requirement: before supporting H-CAPACITY,
`IdentityIntegrityTest` must first be executed and prove no significant `IdentityDuplicate`.
Otherwise the misdiagnosis of "busy → add headcount" merely turns identity defects into staffing decisions.

---

## 23. Diagnosis Engine

v1.2 recommendation:

```text
Rule / Statistical Tests
+
Simulation
+
Comparative Benchmark
+
LLM Explanation
```

rather than LLM end-to-end diagnosis.

---

## 24. DiagnosticTest Library

MVP recommendation:

```text
GlobalCapacityTest
LocalImbalanceTest
TravelBurdenBenchmarkTest
BaseLocationCounterfactualTest
CoveragePolicyStressTest
CapabilityEligibilityTest
SchedulingFeasibilityTest
DataCompletenessTest
OpportunityConfidenceTest
AssignmentConflictTest
IdentityIntegrityTest
```

of which `IdentityIntegrityTest` at least includes (judgment rules and thresholds see 08 §11, §14):

```text
DuplicateSuspectTest       same-address/same-brand high similarity and concurrently active in same period
HierarchyOverlapTest       whether group and store are double-counted
IdentityCoverageTest       proportion of subjects in UNRESOLVED / CONTESTED
FalseMatchProbeTest        whether conflicting strong signals exist within already-merged clusters
```

Materiality linkage: when the proportion of `IdentityUnresolved` exceeds the threshold,
the `materiality_level` of any Gap within that scope must not be higher than `Review`,
and must not enter `Actionable` directly (08 §14.2).

---

## 25. Hypothesis Ranking

Allowed:

```text
Primary Hypothesis
Contributing Hypothesis
Alternative Hypothesis
```

In the future, causal contribution decomposition may be extended.

---

## 26. Materiality

At least consider:

```text
Magnitude
Persistence
OpportunityImpact
StrategicImportance
Confidence
ExpectedDecisionValue
ChangeCost
```

EDV can be roughly represented as:

\[
ExpectedDecisionValue
=
ExpectedImprovement
-
ExpectedChangeCost
\]

The purpose is not precise financial modeling, but to prevent "optimize whenever there is a gap."

Materiality: 

```text
Informational
Monitor
Review
Actionable
Critical
```

---

## 27. Decision Trigger

Synthesis:

```text
Gap
Hypothesis
Materiality
Confidence
Persistence
Cooldown
```

Trigger only creates DecisionCase, never automatically modifies Territory.

---

## 28. Problem Router

| Diagnosis | Primary Route |
|---|---|
| Global Capacity Shortage | DP01 Resource Sizing |
| Capacity Surplus | DP01 / Downsizing |
| Base Location Mismatch | DP02 Resource Location |
| Local Allocation Imbalance | DP03 Territory Alignment |
| Personnel / Skill Fit | DP04 Personnel Matching |
| Coverage / Channel Mismatch | DP05 Coverage Allocation |
| Temporal Feasibility | DP06 Visit Scheduling |
| Daily Route Inefficiency | DP07 Daily Routing |
| Data Quality Issue | World Model Repair |
| Model Quality Issue | Model Governance |
| Policy Conflict | Policy Review |

Router can output Composite Problem, Alternative Route, Monitor, RequestMoreEvidence, NoAction.

---

## 29. AllocationDecisionSignal

Standard output:

```text
scope
world_snapshot
health_profile
gap_set
diagnostic_hypotheses
materiality
recommended_route
alternative_routes
decision_trigger_status
confidence
evidence_summary
```

DecisionCase is created only after Trigger conditions are met.

---

## 30. Agent Boundary

Allocation Intelligence is responsible for structured detection, calculation, comparison, diagnostic tests, and evidence organization.

Agent is responsible for semantic interpretation, hypothesis exploration, interactive analysis, Scenario invocation, and decision support.

Agent does not replace Gap calculation, Business thresholds, or Hard diagnostic tests.

---

## 31. Central Benchmark + Local Knowledge

```text
Central Allocation Intelligence
          ↓
Evidence-backed Diagnosis
          ↓
Local Review
          ↓
Local Evidence / Exception
          ↓
Hypothesis Update
          ↓
DecisionCase
```

Local knowledge must enter governance structures such as Assertion / Evidence / ChangeCost / Guardrail, and may not freely override.

---

## 32. Counterfactual Diagnosis

Asking "If only X changes, how much would Gap decrease?" may invoke Diagnostic Solver, but it must be distinguished from the run_purpose of formal Candidate Generation.

ProblemRun is recommended to support:

```text
diagnostic
feasibility
candidate_generation
validation
benchmark
```

---

## 33. Fast / Slow Allocation Intelligence

Fast: 

```text
coverage
schedule
execution
route
day/week
```

Slow: 

```text
sizing
location
territory
personnel
month/quarter
```

Escalate upward only when Operational Failure persists and Root Cause is structural.

---

## 34. Decision Suppression / Seasonality / Structurality

Support Suppression:

```text
Recent structural change
Data quality low
Seasonal anomaly
Temporary promotion
Known one-off event
Transition period
```

Gap categories:

```text
TemporaryGap
StructuralGap
Unknown
```

Avoid misjudging peak season or promotional peaks as structural staffing shortages.

---

## 35. Management View

Outputs should be upgraded from metrics to business conclusions, for example:

```text
A persistent high-potential coverage gap exists.
The gap is approximately 0.6 Field Rep Equivalent.
The main cause is uneven Territory allocation, not a shortage of personnel across the whole market.
Evidence: whole-market Capacity is sufficient, adjacent Territory has releasable Capacity, and Travel is normal.
Recommendation: first assess Territory Rebalancing, and do not directly add headcount for now.
```

---

## 36. Architecture Gates

Principled refusals:

```text
Health has only a single total score
Metric anomalies directly generate DecisionProblem
When Utilization > threshold, it immediately recommends adding headcount
CoverageGap does not distinguish Need/Commitment/Schedule/Actual
Global/Local Capacity Gap are conflated
Capability Gap is treated as an ordinary Capacity Gap
Compactness is directly treated as Travel Root Cause
Root Cause lacks Evidence Against
LLM freely generates Root Cause without a Diagnostic Test
DataQualityIssue is not allowed to become Root Cause
Opportunity Gap has no confidence
Temporary peaks trigger Territory Realignment
There is no Persistence/Cooldown/Suppression
Problem Router and Solver Selector are merged
All issues are routed to Territory Solver
Router does not allow NoAction
Agent itself decides Business Threshold
Diagnostic Solver Result is treated as a formal Candidate
```

---

## 37. MVP Scope / Benchmark

MVP: 

```text
DerivedAllocationState
6-dimensional Health Profile
7 Gap Types
5 Diagnostic Hypotheses:
  CapacityShortage
  AllocationImbalance
  TravelMismatch
  CoverageMismatch
  DataQualityIssue
Materiality
DecisionTrigger
ProblemRouter
```

Add five Diagnostic Tests:

```text
GlobalCapacityTest
LocalImbalanceTest
TravelBenchmarkTest
CoveragePolicyStressTest
SchedulingFeasibilityTest
```

Validate with at least five Cases:

```text
True staffing shortage
Territory imbalance
Location issue
Coverage issue
Data issue
```

Core Benchmark:

```text
Problem Routing Accuracy
Root Cause Recall
False Structural Trigger Rate
False Expansion Recommendation Rate
Data-vs-Business Diagnosis Accuracy
Evidence Completeness
Decision Suppression Correctness
```
