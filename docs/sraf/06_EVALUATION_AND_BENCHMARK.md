# SRAF Evaluation & Benchmark Specification v1.2

**Project:** Sales Resource Allocation Framework
**Abbreviation:** SRAF
**Document:** `06_EVALUATION_AND_BENCHMARK.md`
**Status:** Implementation Baseline v1.2

**Upper-level Specification:**

```text
00_PROJECT_CHARTER.md
01_WORLD_MODEL_SPEC.md
02_DECISION_ONTOLOGY.md
03_DECISION_PROBLEM_CONTRACTS.md
04_ALLOCATION_INTELLIGENCE.md
05_DECISION_ORCHESTRATION.md
```

---

## 1. Document Objectives

SRAF's evaluation goal is not to prove:

> "Solver can produce a result."

but to prove the entire decision chain:

```text
World
  ↓
Diagnosis
  ↓
Problem Framing
  ↓
Candidate Generation
  ↓
Decision Evaluation
  ↓
Execution
  ↓
Observed Outcome
```

It is verifiable at five levels: semantic, diagnostic, mathematical, decision, and business result.

Therefore SRAF v1.2 fixes a five-level Benchmark:

```text
B0 Semantic Correctness
B1 Diagnostic Correctness
B2 Mathematical / Solver Correctness
B3 Decision Quality
B4 Business Outcome Validation
```

and adds a horizontal dimension that traverses all levels:

```text
G — Governance / Auditability / Safety
```

---

## 2. Why Can't We Only Do a Solver Benchmark

A sales resource allocation system may exhibit:

```text
Solver status = OPTIMAL
```

but business decisions remain incorrect.

For example:

- Misdiagnosing a Coverage Policy issue as a Headcount Shortage;
- Treating a Travel Gap caused by erroneous latitude/longitude as a Territory Gap;
- Being mathematically more balanced, but many high-value customers are reassigned;
- Candidate objective improves by 2%, but ChangeCost exceeds the benefit;
- Historical backtesting uses data that was not yet known at the time, causing Look-ahead Bias;
- Periodic workload is feasible, but real-date constraints lead to Scheduling being unsolvable;
- Territory is more compact, but the road network results in worse actual Travel.

Therefore:

\[
SolverCorrectness
\neq
DecisionCorrectness
\]

does not equal:

\[
BusinessOutcomeImprovement
\]

---

## 3. Benchmark Overall Architecture

```text
                   SRAF BENCHMARK STACK

┌──────────────────────────────────────────────┐
│ B4 BUSINESS OUTCOME VALIDATION               │
│ Did the real business improve?               │
├──────────────────────────────────────────────┤
│ B3 DECISION QUALITY                          │
│ Is this a good decision vs baseline?         │
├──────────────────────────────────────────────┤
│ B2 MATHEMATICAL / SOLVER CORRECTNESS         │
│ Was the framed problem solved correctly?     │
├──────────────────────────────────────────────┤
│ B1 DIAGNOSTIC CORRECTNESS                    │
│ Did we identify the right problem and cause? │
├──────────────────────────────────────────────┤
│ B0 SEMANTIC CORRECTNESS                      │
│ Did we represent the world correctly?        │
└──────────────────────────────────────────────┘

Cross-cutting:
Governance / Evidence / Reproducibility / Safety
```

Any high-level Benchmark failure must be drillable down to lower levels.

---

# Part I — B0 Semantic Correctness

## 4. B0 Objectives

B0 answers:

> **Is SRAF correctly expressing the sales world and decision world?**

It does not test "whether the plan is good".

It tests:

- Whether Entity has correct identity;
- Whether Time is correct;
- Whether Fact / Estimate / Assumption are distinguished;
- Whether Responsibility is incorrectly flattened into `owner_id`;
- Whether Territory is incorrectly equated with Polygon;
- Whether Scenario pollutes Observed World;
- Whether Candidate is incorrectly written as World Truth;
- Solver-specific fields pollute Canonical Model.

---

## 5. B0 Must meet the principles

The following belong to Critical Semantic Invariant:

```text
I01 Canonical ID independent from source-system ID
I02 Account != ServiceLocation
I03 Person != SalesResource
I04 home_location != deployment_location
I05 CoverageNeed != CoverageCommitment
I06 OpportunityEstimate requires provenance
I07 DerivedState requires calculation version
I08 ResponsibilityAssignment is temporal
I09 Territory != Geometry
I10 Scenario != Observed World
I11 SolverSolution != CandidateDecision
I12 CandidateDecision != ApprovedDecision
I13 ApprovedDecision != WorldState until transition
I14 Bitemporal historical query prevents future leakage
I15 Graph Projection is rebuildable from canonical truth
I16 ResourceDeployment != SalesResource
I17 DeploymentAssignment links ResourceDeployment to SalesResource temporally
I18 TerritoryMembership links Territory to Responsibility, not ResponsibilityAssignment
I19 LocalAllocationGap != AllocationGap base class
```

I20–I30 (Canonical Identity and Entity Resolution) are owned by
`08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §21 owns,
Also belongs to Critical Semantic Invariant: violation directly fails B0.
Its associated Benchmark Case Family `ID01–ID20`, metrics
(FalseMatchRate / BlockingRecall / UnmergeRate /
IdentityConfoundedGapRate / ReplayIdentityLeakageRate)
and Identity Gate see 08 §23.

When Critical Invariant is violated:

> Benchmark fails directly, does not enter higher-level evaluation.

> Note: This document §6 Test 6.1–6.3 only specifies 'what must be tested';
> Judgment rules, threshold semantics (error rate upper bound λ/π) and human permission matrix are specified by 08.

---

## 6. Entity Identity Tests

At least test:

### Test 6.1 — Multi-source Identity

The same customer exists:

```text
CRM_ID = 1001
ERP_ID = C882
External_POI_ID = POI_991
```

Should resolve to the same:

```text
CanonicalAccount
```

but keep three ExternalIdentifiers.

---

### Test 6.2 — Source ID Collision

Both systems exist:

```text
ID = 1001
```

but the real entities are different.

Canonical ID must not conflict.

---

### Test 6.3 — Location Change

The same Account is relocated:

```text
ServiceLocation A
→
ServiceLocation B
```

Account identity should not change.

---

## 7. Responsibility Semantic Tests

Must verify:

```text
Account A
Selling → Rep 1
Merchandising → Rep 2
KA Negotiation → KAM 3
```

Can be simultaneously true.

System must not compress it into:

```text
Account A owner = Rep1
```

---

## 7A. Resource Deployment Semantic Tests

Must verify:

```text
ResourceDeployment may exist while vacant
SalesResource may exist without being assigned to a deployment
DeploymentAssignment is temporal
Person.home_location does not equal Deployment.base_location
```

Greenfield case should allow:

```text
ResourceRequirement
→ ResourceDeployment(planned/vacant)
→ later Personnel Matching
```

---

## 8. Territory Semantic Tests

At least test:

### Geographic Territory

Continuous geographic area.

### Non-contiguous KA Territory

```text
Beijing
Shanghai
Guangzhou
Chengdu
```

Must still be a legal Territory.

### Overlay Territory

Field / KA / Merchandising / Product Specialist must exist simultaneously.

If the Ontology cannot express it, B0 fails.

---

## 9. Temporal Correctness

Must test bitemporal behavior.

Case:

```text
Actual store close date:
2026-08-01

System learned:
2026-08-12
```

Query:

```text
knowledge_time = 2026-08-05
```

Must not see future information about "store already closed".

---

## 10. Look-ahead Leakage Test

Historical Decision Replay must use:

```text
known_at <= decision_time
```

Prohibited from using:

```text
future closure
future sales
future opportunity label
future road update
future account correction
```

This is the mandatory Gate for B0 and B4 historical backtesting.

---

## 11. Scenario Isolation Test

Create:

```text
Scenario:
+6 resources
```

Must verify:

```text
Observed World resource count unchanged
```

Scenario must not leave residuals after deletion:

```text
Deployment
Assignment
CoverageCommitment
Territory
```

Wait for status.

---

## 12. Candidate Isolation Test

Solver generates:

```text
CandidateTerritory V1
```

In the Canonical World, active Territory should not change.

Only:

```text
Candidate
→ Approval
→ Transition
→ Event
```

Changes are allowed only thereafter.

---

## 13. Semantic Status Tests

The same business statement must allow different states:

```text
ObservedFact
MasterDataFact
ExternalFact
ModelEstimate
HumanJudgment
PolicyDefinition
DerivedState
DecisionOutput
ScenarioAssumption
```

For example:

```text
Account A potential = High
```

If coming from the model, should be marked:

```text
ModelEstimate
```

Cannot become:

```text
MasterDataFact
```

---

## 14. Provenance Completeness

The following objects require at least Provenance:

```text
OpportunityEstimate
TravelEstimate
RelationshipStrengthEstimate
DerivedWorkload
AllocationGap
CandidateDecision
ProblemRun
```

Benchmark report:

```text
ProvenanceCompletenessRate
```

Critical production objects require completeness in principle.

---

## 15. B0 Property-based / Metamorphic Tests

Suggest adding attribute tests.

### Input Order Invariance

Changing the order of input records should not change the deterministic semantic result.

### ID Relabeling Invariance

Merely renaming internal test IDs should not change decision semantics.

### Scenario Isolation

Scenario changes must not mutate baseline.

### Graph Rebuild

After deleting a Graph Projection, it should be reconstructible from the Canonical State.

### Snapshot Immutability

After a WorldSnapshot is established, the original referenced state must not be silently modified.

---

# Part II — B1 Diagnostic Correctness

## 16. B1 Goal

B1 answers:

> **Is the system correctly judging "what exactly is the problem"?**

This is one of the most important Benchmark layers of SRAF compared with ordinary Territory Optimizer.

Must specially prevent:

```text
Sales cannot keep up.
→ lacking personnel.
```

This kind of direct jump without diagnosis.

---

## 17. B1 Benchmark Ground Truth

In real business data, Root Cause often lacks an absolute Ground Truth.

Therefore B1 uses three types of ground truth:

```text
T1 Constructed Ground Truth
T2 Expert-adjudicated Ground Truth
T3 Outcome-supported Ground Truth
```

---

## 18. T1 Constructed Ground Truth

Actively create problems via synthetic / semi-synthetic data.

For example:

```text
Keep total Capacity unchanged.
Only artificially disrupt the Territory load.
```

Then the Ground Truth:

```text
AllocationImbalance
```

is known.

This kind of Benchmark is most suitable for validating the Problem Router.

---

## 19. T2 Expert-adjudicated Ground Truth

For historical real cases, multiple business/OR experts independently judge:

```text
Primary Root Cause
Contributing Causes
Not Supported Causes
```

If experts disagree:

```text
Contested
```

rather than forcing a single label.

---

## 20. T3 Outcome-supported Ground Truth

For example historically:

```text
no staff increase.
only adjust Territory.
```

after which Gap drops significantly.

This can serve as:

```text
TerritoryImbalance
```

supporting evidence.

However it cannot be regarded as a strict causal ground truth unless the experimental design is strong enough.

---

## 21. B1 Canonical Benchmark Cases

v1.2 must fix at least the following Case Family.

```text
D01 True Capacity Shortage
D02 Local Territory Imbalance
D03 Resource Location Mismatch
D04 Coverage Policy Over-allocation
D05 Capability Mismatch
D06 Temporal Scheduling Infeasibility
D07 Daily Routing Inefficiency
D08 Data Quality Corruption
D09 Model Quality Error
D10 Policy Conflict
D11 Temporary Seasonal Overload
D12 High ChangeCost / Maintain Preferred
D13 Mixed Cause
D14 Unknown / Insufficient Evidence
```

---

## 22. D01 — True Capacity Shortage

Construct:

```text
All territories:
110%–125% utilization

Travel:
normal

Coverage policy:
validated

Capability:
sufficient

No meaningful idle capacity nearby
```

Expect:

```text
Primary route:
DP01 ResourceSizing / CapacityExpansion
```

---

## 23. D02 — Local Territory Imbalance

Construct:

```text
Global capacity >= demand

T1 = 130%
T2 = 65%
T3 = 80%
```

Travel normal.

Expect:

```text
Primary:
DP03 TerritoryAlignment
```

instead of DP01.

---

## 24. D03 — Resource Location Mismatch

Construct:

```text
Total intrinsic workload feasible

Current base location far from demand

Travel burden = 38%
Peer = 18%
```

Substitute station release:

```text
+0.6 RE
```

Expect:

```text
DP02 ResourceLocation
```

---

## 25. D04 — Coverage Policy Over-allocation

Construct:

```text
low opportunity accounts
consume large field capacity
```

Coverage stress scenario: 

```text
workload -20%
opportunity coverage -2%
```

Expect:

```text
DP05 CoverageAllocation
or
PolicyReview
```

instead of adding personnel.

---

## 26. D05 — Capability Mismatch

Construct:

```text
Total capacity = sufficient
KA eligible capacity = insufficient
Generalist idle capacity = high
```

Expect:

```text
DP04 PersonnelMatching
or
ResourcePool / capability action
```

---

## 27. D06 — Temporal Scheduling Infeasibility

Construct:

```text
Monthly workload <= monthly capacity
```

However:

```text
Tuesday-only
spacing
time windows
fixed-area day
```

conflict.

Expect:

```text
DP06 VisitScheduling
TEMPORAL_STRUCTURAL_INFEASIBILITY
```

Cannot diagnose as Global Capacity Shortage.

---

## 28. D07 — Daily Routing Inefficiency

Construct:

```text
Daily stop set is feasible
```

but random ordering leads to:

```text
travel +40%
```

Expect:

```text
DP07 DailyRouting
```

---

## 29. D08 — Data Quality Corruption

For example:

```text
20% coordinates shifted
duplicate accounts inserted
stale service times
```

Expect:

```text
WorldModelRepair
```

Cannot trigger Structural Decision.

---

## 30. D09 — Model Quality Error

Data is correct, but:

```text
Opportunity model systematically
overpredicts remote accounts
```

Expected:

```text
ModelGovernance
```

---

## 31. D10 — Policy Conflict

Two Hard Policies cannot be satisfied simultaneously.

Expected:

```text
POLICY_INFEASIBLE
PolicyReview
```

instead of Solver Failure.

---

## 32. D11 — Temporary Seasonal Overload

Construct:

```text
4-week promotion spike
```

Historical seasonal pattern indicates recovery after.

Expected:

```text
TemporaryGap
Monitor / temporary support
```

instead of Territory Realignment.

---

## 33. D12 — High ChangeCost / Maintain Preferred

Construct:

Candidate: 

```text
Travel -3%
Opportunity +1%
```

But:

```text
40% key accounts reassigned
relationship disruption high
```

Expected:

```text
MaintainCurrentState
```

At least should be retained as a strong candidate.

---

## 34. D13 — Mixed Cause

For example:

```text
Capacity shortage 40%
Travel inefficiency 35%
Territory imbalance 25%
```

System should allow:

```text
Primary
Contributing
Alternative
```

instead of forcing a unique label.

---

## 35. D14 — Insufficient Evidence

When:

```text
Opportunity confidence low
travel data stale
```

Expected:

```text
RequestMoreEvidence
```

instead of hard assign Root Cause.

---

## 36. B1 Core Metrics

Report at least:

```text
ProblemRoutingAccuracy
PrimaryRootCauseAccuracy
RootCauseRecall@K
FalseExpansionRecommendationRate
FalseStructuralTriggerRate
DataVsBusinessDiagnosisAccuracy
NoActionCorrectness
EvidenceCompleteness
CalibrationByConfidence
```

---

## 37. False Expansion Recommendation Rate

Definition:

> In cases that do not require new resources, the proportion incorrectly suggested to enter Expansion.

This is a mandatory reporting metric in SRAF v1.2.

Because:

```text
Busy
→ Add personnel
```

It is a typical misdiagnosis of high-cost sales resource allocation.

---

## 38. False Structural Trigger Rate

Definition:

> Proportion of temporary, data, model, or execution issues incorrectly escalated to Structural Decision.

Especially test:

```text
seasonality
promotion
temporary absence
bad data
route delay
```

---

## 39. Confidence Calibration

If the system outputs:

```text
TerritoryImbalance confidence = 0.8
```

In the long term, the quality of judgments similar to confidence intervals should roughly match the true accuracy.

v1.2 does not require complex probability calibration models, but must avoid:

> All conclusions above 0.9.

---

# Part III — B2 Mathematical / Solver Correctness

## 40. B2 Goal

B2 answers:

> **After the Decision Problem has been correctly framed, has the mathematical model and Solver correctly solved the problem?**

Here must strictly distinguish:

```text
Business Feasibility
Model Feasibility
Solver Success
```

---

## 41. B2 Test Pyramid

```text
M0 Analytical Toy Cases
M1 Exact Small Instances
M2 Synthetic Scale Tests
M3 Historical Problem Projections
M4 Stress / Failure Tests
```

---

## 42. M0 — Analytical Toy Cases

Manually computable.

For example:

```text
2 resources
4 accounts
simple workload
known travel
```

The human knows the unique optimal solution.

Requirement:

```text
model result == analytical result
```

Suitable for checking:

```text
constraint encoding
objective direction
unit conversion
```

---

## 43. M1 — Exact Small Instances

Use Exact Solver on small-scale problems to obtain:

```text
OptimalSolution
```

Then compare:

```text
Heuristic
CP-SAT
Local Search
Metaheuristic
```

gap.

---

## 44. Optimality Claim Test

If the Engine claims:

```text
OPTIMAL
```

Must have Solver proof / exact certificate or framework-approved proof.

Heuristic is not allowed to mark:

```text
optimal
```

Can only:

```text
FEASIBLE_HEURISTIC
BEST_KNOWN
BOUNDED_GAP
```

---

## 45. Feasibility Preservation

Any Candidate must re-execute independent Validation:

```text
InvariantChecker
HardConstraintChecker
```

Cannot solely trust the Solver's own report.

---

## 46. Independent Constraint Checker

Recommend implementing independent outside the Solver Model:

```text
CandidateConstraintValidator
```

Used to verify:

```text
coverage
assignment cardinality
capacity
boundary
eligibility
temporal overlap
```

This can discover Model Encoding Bug.

---

## 47. Infeasibility Classification Benchmark

Must specifically test:

```text
DATA_INFEASIBLE
PROJECTION_INFEASIBLE
POLICY_INFEASIBLE
RESOURCE_INFEASIBLE
STRUCTURAL_INFEASIBLE
MODEL_INFEASIBLE
SOLVER_FAILURE
```

Goal is not only to 'find infeasibility', but also to:

> Classification correct.

---

## 48. Solver Failure ≠ Business Infeasible Test

Artificially set:

```text
runtime = 1 ms
```

Cause Solver timeout.

System must return:

```text
SOLVER_FAILURE / TIME_LIMIT
```

Cannot return:

```text
RESOURCE_INFEASIBLE
```

---

## 49. Policy Conflict Test

Construct mutually exclusive hard policies.

Precheck / policy checker should be discovered before Solver.

Goal:

```text
solver_not_called = true
```

---

## 50. Resource Infeasibility Test

Construct:

```text
required workload = 1000
capacity = 500
coverage immutable
```

Should be identified in the Precheck phase.

---

## 51. Structural Infeasibility Test

Global resources are sufficient, but due to:

```text
boundary
capability
location
```

Locally infeasible.

Must be distinguished from Global Capacity Shortage.

---

## 52. Mathematical Metamorphic Tests

Test when applicable conditions are met.

### Record Order Invariance

Input order changes do not change deterministic optimum.

### Label Permutation Invariance

After swapping Resource ID / Account ID, results should be isomorphic.

### Constraint Relaxation Monotonicity

When only relaxing constraints, the optimal objective should not worsen.

### Optional Capacity Monotonicity

In the model where 'new capacity can be optionally unused', increasing available capacity should not reduce the best achievable objective.

### Feasible-set Restriction

After adding a new Hard Constraint, the originally infeasible candidate must not still be judged feasible.

---

## 53. Random Seed Reproducibility

Heuristic / metaheuristic: 

```text
same snapshot
same projection
same code
same params
same seed
```

Should be able to reproduce the same result or defined deterministic trace.

---

## 54. Stochastic Stability

Different seed:

```text
N runs
```

Report:

```text
best
median
P90 runtime
objective distribution
constraint violation rate
```

Cannot only show the best run.

---

## 55. Scale Benchmark

Each Solver Adapter must declare test scale.

For example:

```text
accounts:
1k / 10k / 50k / 100k

resources:
10 / 50 / 200 / 500
```

Report:

```text
runtime
memory
feasible time
final gap
candidate quality
```

reported scale must cover `07_REFERENCE_ARCHITECTURE.md` §110A
In v1 Engineering Envelope, the upper bound of the tier (S/M/L) corresponding to the implementation Phase,
Must not report performance only on toy instances.
---

## 56. Time-to-First-Feasible

Especially important for business interactions.

Not only report:

```text
time to final
```

Should also report:

```text
time_to_first_feasible
```

Because quarterly planning and Interactive What-if have different response time requirements.

---

## 57. Oracle Correctness

Feasibility Oracle itself also needs Benchmark.

For example Scheduling Oracle:

```text
Oracle says FEASIBLE
```

Then the full Scheduler should be able to actually generate a feasible schedule.

Statistics:

```text
FalseFeasibleRate
FalseInfeasibleRate
```

---

## 58. Multi-fidelity Correlation

For example Territory:

```text
L1 compactness
L2 network travel
L3 routing simulation
```

Should measure:

> Correlation of L1 / L2 rankings with L3.

If L1 is almost unrelated to the real Routing, it cannot serve as an effective screening Proxy.

---

## 59. Solver Adapter Contract Test

Each Solver Adapter must pass:

```text
input schema
status mapping
infeasibility mapping
optimality mapping
timeout handling
seed handling
provenance
candidate interpretation
```

Consistency test.

---

# Part IV — B3 Decision Quality

## 60. B3 Goal

B3 answers:

> **Even if the Solver is correct, is this Candidate worth adopting as a business decision relative to the Baseline?**

Core principle:

```text
Candidate
≠
Decision
```

and:

```text
better mathematical score
≠
worth changing
```

---

## 61. B3 Must Always Have a Baseline

Structural / Tactical Decision at least compare:

```text
Baseline
MaintainCurrentState
Candidate A
Candidate B
...
```

If there is no Baseline:

> B3 cannot pass.

---

## 62. Shared Decision Evaluation Space

Candidates generated from different Problems should be mapped to shared metrics:

```text
OpportunityCoverage
ServiceLevel
CapacityUtilization
TravelBurden
ResourceCost
ChangeCost
Stability
BusinessRisk
ImplementationComplexity
DecisionConfidence
```

---

## 63. No Default Universal Score Allowed

Benchmark default output:

```text
metric profile
objective attainment
guardrail status
trade-offs
```

Not mandatory:

```text
DecisionScore = 86.3
```

If a specific project uses a weighted score, must:

```text
document weight source
run sensitivity analysis
```

---

## 64. B3 Feasibility

First:

```text
Invariant satisfied
Hard constraints satisfied
```

Otherwise:

```text
Candidate rejected
```

Does not enter subsequent comparative ranking.

---

## 65. Guardrail Evaluation

Candidate may violate Guardrail, but must:

```text
flag
quantify impact
require exception review
```

Benchmark check:

> Whether Guardrail violation is correctly explicitly exposed.

---

## 66. ChangeCost Evaluation

Cover at least:

```text
Account reassignment
Revenue reassignment
Customer relationship risk
Personnel relocation
Learning / handover
Transition effort
```

Structural Candidate without ChangeCost is not allowed to claim:

> "Business is better".

---

## 67. Decision Regret

Can be calculated in Scenario / historical replay:

\[
Regret
=
Value(BestAvailableDecision)
-
Value(ChosenDecision)
\]

Especially used for comparison:

```text
Add Resource
vs
Rebalance
vs
Coverage Change
vs
Maintain
```

---

## 68. Robustness under Opportunity Uncertainty

For:

```text
Low / Base / High
```

Opportunity Scenario, Candidate should report:

```text
downside
base
upside
```

Avoid selecting fragile solutions that perform extremely well only at a single prediction point.

---

## 69. Robustness Metric

Can report:

```text
WorstCasePerformance
ScenarioVariance
ProbabilityOfGuardrailViolation
OpportunityCoverageP10
```

Whether to use probability depends on the Uncertainty Model.

---

## 70. Stability vs Gain Frontier

Structural Candidate recommends drawing:

```text
Business Gain
      ↑
      │      C
      │   B
      │ A
      └────────────→ Change / Disruption
```

Let management see:

> To gain an additional 2% Opportunity Coverage, how much stability must be sacrificed.

---

## 71. Maintain Decision Benchmark

Specifically construct:

```text
small theoretical improvement
high disruption
```

Ensure the system can select:

```text
MaintainCurrentState
```

Rather than "as long as the optimizer runs it will definitely change".

---

## 72. Cross-Problem Alternative Benchmark

The same DecisionCase must allow comparison:

```text
Territory Rebalance
Add Resource
Coverage Adjustment
Resource Relocation
Hybrid
Maintain
```

This is an important benchmark for whether SRAF's decision capability exceeds that of a single Solver.

---

## 73. Feasibility Oracle in B3

The final Candidate should pass appropriate downstream validation.

For example, Territory:

```text
PersonnelFeasibility
SchedulingFeasibility
RoutingEvaluation
```

If a high-level Candidate cannot be executed downstream:

> Decision Quality is unqualified.

---

## 74. Multi-fidelity Candidate Funnel Benchmark

Check:

```text
Generate N
→ L1 shortlist
→ L2 shortlist
→ L3 final
```

Will it prematurely eliminate truly high-quality Candidates.

Report:

```text
TopKRecall
```

---

## 75. Human Override Quality

After manual Override:

```text
Candidate V1
→ HumanOverride
→ Candidate V1.1
```

Must be re-evaluated.

Benchmark check:

```text
feasibility
objective delta
change cost
guardrail
```

whether to refresh all.

---

## 76. Local Knowledge Value

Long-term comparable:

```text
Central Candidate
vs
Local Adjusted Candidate
```

performance in actual results.

Used to answer:

> Which types of Local Override truly add value?

---

## 77. Override Harm Rate

At the same time need to detect:

> Does manual Override instead break the solution.

Can report:

```text
OverrideBenefitRate
OverrideHarmRate
OverrideNeutralRate
```

This is not to eliminate humans, but to form Evidence.

---

## 78. Decision Explainability Benchmark

Each Candidate must be able to answer at least:

```text
What changed?
Why?
What improved?
What worsened?
Which assumptions matter?
Which guardrails are close?
What evidence supports this?
```

Benchmark checks whether Structured Evidence is complete.

---

## 79. Counterfactual Sensitivity

Change key assumptions:

```text
Opportunity ±10%
Travel +20%
ServiceTime +15%
ChangeCost ×2
```

Observe whether Candidate ranking changes drastically.

If so:

```text
DecisionSensitivity = HIGH
```

Must be shown to the approver.

---

## 80. B3 Problem-specific Metrics

### DP01 Resource Sizing

```text
Resource-Coverage Frontier
MarginalValue
Cost
OpportunityCoverage
False Expansion Risk
Robustness
```

### DP02 Resource Location

```text
TravelBurden
CapacityReleased
ServiceReach
RelocationCost
PersonnelFeasibility
```

### DP03 Territory Alignment

```text
OpportunityCoverage
WorkloadBalance
CapacityUtilization
NetworkTravel
AssignmentChurn
ChangeCost
UnassignedResponsibilities
```

### DP04 Personnel Matching

```text
CapabilityFit
LocationFit
RelationshipContinuity
Stability
Fairness
RetentionRisk
```

### DP05 Coverage Allocation

```text
Opportunity per Resource Unit
CoverageROI
ServiceLevel
ChannelMix
SchedulingFeasibility
```

### DP06 Visit Scheduling

```text
CommitmentFulfillment
SpacingCompliance
DailyWorkload
TemporalFeasibility
ScheduleStability
TravelEstimate
```

### DP07 Daily Routing

```text
TravelTime
Distance
OnTimeRate
UnservedStops
RouteDuration
ExecutionFeasibility
```

---

# Part V — B4 Business Outcome Validation

## 81. B4 Goal

B4 answers:

> **After the decision is truly implemented, does the business improve as expected?**

This is the final evidence layer of SRAF.

Solver Objective cannot replace B4.

---

## 82. DecisionValidationPlan must be defined in advance

Should be recorded before implementation:

```text
Hypothesis
Primary Metrics
Secondary Metrics
Baseline
Comparison Design
Stabilization Window
Validation Window
Success Threshold
Failure Threshold
```

Cannot select metrics after seeing results.

---

## 83. Leading vs Lagging Metrics

### Leading

```text
Travel
Coverage
Visit completion
Capacity utilization
Unfulfilled commitments
```

### Lagging

```text
Sales
Gross margin
Customer retention
Distribution
Market penetration
```

Structural Decision typically validates Leading first, then waits for Lagging.

---

## 84. Validation Design Hierarchy

From weak to strong evidence strength:

```text
V0 Before / After
V1 Matched Comparison
V2 Difference-in-Differences
V3 Staggered Rollout
V4 Randomized / A-B where feasible
V5 Replicated Multi-market Evidence
```

Not all Territory decisions are suitable for Randomized Test.

However must try to increase evidence strength as much as possible.

---

## 85. Limitations of Before / After

Simple:

```text
Before
vs
After
```

Easily affected by:

```text
seasonality
promotion
competitor action
macro changes
personnel turnover
```

impact.

So only suitable as low-strength evidence.

---

## 86. Matched Control

Choose regions with similar business characteristics and no adjustment as comparators.

Matching variables may:

```text
market size
channel mix
opportunity
historical growth
seasonality
resource level
```

Reference empirical: Zoltners / Sinha / Lorimer, *Sales Force Design for Strategic
Advantage* (2004), Table 8.3 — an industrial distributor using test (realignment after replacement
of the person) vs control (not replaced) account groups measured disruption impact, results show impact.
**only concentrated in medium-sized accounts** ($50–100k), small accounts and super-large accounts are not significant.

Two normative implications:

```text
1. Matched Control is truly feasible in sales territory decisions (V1 evidence is not purely theoretical).
2. ChangeCost.CustomerRelationshipCost must be estimated by account size /
relationship strength segmentation,
Prohibit using a single global disruption coefficient (see §66, 02 §64–65).
```

---

## 87. Difference-in-Differences

When there are treatment and control groups and reasonable trend conditions are met, they can be compared:

\[
(After-Before)_{Treatment}
-
(After-Before)_{Control}
\]

to reduce the impact of common external shocks.

---

## 88. Staggered Rollout

For multi-city rollout, can:

```text
City A first
City B later
City C later
```

both control implementation risk and form better Validation Evidence.

---

## 89. Applicability limits of A/B

Suitable:

```text
Coverage strategy
sales cadence
some routing/scheduling policy
```

However Territory structure adjustment has:

```text
spillover
manager interaction
customer overlap
```

Therefore cannot mechanically apply store-level A/B.

---

## 90. Interference / Spillover

Sales Territory decisions naturally have cross-regional impact.

For example:

```text
Rep A territory shrinks
```

may cause:

```text
Rep B workload grows
```

Therefore experimental design must consider:

> Treatment Unit is not necessarily an Account.

May be:

```text
territory
district
city
region
```

---

## 91. Stabilization Window

After structural adjustment usually requires:

```text
handover
learning
relationship rebuilding
```

Therefore should distinguish:

```text
Transition
Stabilization
Validation
```

Cannot treat the transition period directly as the final effect.

---

## 92. Validation Outcome

Unify:

```text
Validated
PartiallyValidated
Failed
Inconclusive
```

`Inconclusive` is a legitimate result.

Cannot force all Decision to be:

```text
success / failure
```

dichotomized.

---

## 93. Value of Failed Decision

After failure, should generate:

```text
LearningSignal
```

For example:

```text
OpportunityModelOverestimated
TravelBenefitOverestimated
ChangeCostUnderestimated
LocalRelationshipImpactMissing
CoverageResponseWeak
ExecutionNoncompliance
```

These enter:

```text
ModelReview
PolicyReview
WorldModelImprovement
```

---

## 94. Cannot equate Decision Failure with Agent Failure

If based on evidence available at the time:

```text
decision rational
```

but future unexpected market changes cause failure,

it does not necessarily indicate a Decision Framework error.

Therefore B4 should distinguish:

```text
DecisionProcessQuality
OutcomeRealization
ExternalShock
```

---

## 95. Historical Replay Benchmark

for the past time point:

```text
t0
```

freeze the data that could be known at that time:

```text
knowledge_time <= t0
```

let SRAF re-decide.

Then use:

```text
t0 + future observations
```

for evaluation.

But future observations can only be used for Evaluation, cannot enter t0 input.

---

## 96. Two types of problems with Replay

### Policy Replay

Question:

> If SRAF had been used at that time, what would have been recommended?

### Candidate Outcome Replay

Question:

> Is a certain type of Candidate more reasonable under similar historical conditions?

Since real Counterfactual cannot be directly observed, the second type can only be interpreted with caution.

---

## 97. Shadow Validation

In Production:

```text
SRAF generates candidate
```

but does not execute.

Then observe the real world.

Shadow can verify:

```text
feasibility
prediction calibration
travel estimate
capacity estimate
diagnosis stability
```

but cannot directly prove:

> Candidate will definitely be better after implementation.

---

## 98. Pilot Validation

Important Structural Decision recommendation:

```text
1–2 pilot markets
→ validate
→ refine
→ scale
```

Especially suitable for new Territory / Coverage methodology.

---

## 99. Replication

A single city success cannot directly prove that the Framework is scalable.

Should test:

```text
different market density
different channel structure
different geography
different sales model
different data quality
```

Observe whether the Decision Logic remains effective.

---

# Part VI — Benchmark Dataset Strategy

## 100. Benchmark Data Layering

Suggest fixed six levels:

```text
L0 Toy Deterministic
L1 Fully Synthetic
L2 Semi-synthetic
L3 Historical Replay
L4 Shadow Production
L5 Pilot / Production
```

---

## 101. L0 Toy Deterministic

Objective:

```text
semantic
constraint
analytical correctness
```

The data scale is very small.

Results can be manually verified.

---

## 102. L1 Fully Synthetic

Generate:

```text
accounts
opportunity
coverage
resources
travel
policies
```

And proactively inject Root Cause.

Advantage:

> Ground Truth is known.

---

## 103. L2 Semi-synthetic

Using real/anonymized space and business structure,

Manual injection:

```text
capacity shortage
territory imbalance
location error
coverage excess
data corruption
```

More realistic than pure synthetic.

---

## 104. L3 Historical Replay

Use historical Snapshot.

Requirement:

```text
bitemporal integrity
no look-ahead
```

Suitable for testing:

```text
diagnosis
candidate plausibility
forecast calibration
```

---

## 105. L4 Shadow Production

Real current data, real workflow, but Candidate does not execute.

Focus:

```text
operational reliability
diagnostic stability
human acceptance
prediction calibration
```

---

## 106. L5 Pilot / Production

Real Decision implementation.

Used for B4.

All major experiments must have:

```text
DecisionValidationPlan
```

---

# Part VII — Benchmark Suite Design

## 107. Benchmark Case Schema

Recommendation:

```yaml
benchmark_case:
  case_id:
  version:

  layer:
  problem_family:

  world_snapshot:
  scenario:

  injected_condition:
  expected_semantics:

  expected_gaps:
  expected_hypotheses:
  expected_routes:

  allowed_alternatives:

  expected_failure_type:

  evaluation_metrics:

  ground_truth_type:

  evidence_level:
```

---

## 108. Case must be versioned

If data or expected label changes:

```text
case v1.0
→
case v1.1
```

Here the version number is **Benchmark Case's own version**,
Unrelated to the specification document version, does not change with document bumps.

Cannot be silently modified.

Otherwise historical Benchmark cannot be compared.

---

## 109. Case Families

Recommend the first version directory:

```text
semantic/
diagnosis/
sizing/
location/
territory/
personnel/
coverage/
scheduling/
routing/
orchestration/
governance/
historical_replay/
```

---

## 110. Negative Cases

Benchmark cannot have only:

> "There is a problem here, please find the problem."

Must contain a large amount of:

```text
Healthy
NoAction
Monitor
InsufficientEvidence
```

Case。

Otherwise the system will form:

> As long as testing must find problems

deviation.

---

## 111. Adversarial Cases

Need proactive testing:

```text
corrupt location
stale model
contradictory policy
duplicate accounts
extreme outliers
missing evidence
seasonal spike
near-threshold flapping
```

---

## 112. Boundary Cases

For example:

```text
utilization = 109.9%
110.0%
110.1%
```

Combine:

```text
hysteresis
persistence
cooldown
```

Test whether the Decision Trigger is stable.

---

# Part VIII — Orchestration Benchmark

## 113. Workflow Correctness

At least test:

```text
CorrectWorkflowRouting
StepDependency
ArtifactInvalidation
ScenarioIsolation
FailureRecovery
HumanCheckpoint
IterationStop
SolverFallback
```

---

## 114. Artifact Invalidation Test

If:

```text
CoverageCommitment changes
```

Already have:

```text
ScheduleCandidate
RouteCandidate
```

Must mark:

```text
STALE
```

Cannot continue to be used for Approval.

---

## 115. Failure Routing Test

For example:

```text
RESOURCE_INFEASIBLE
```

Orchestrator should:

```text
route upstream
```

instead of:

```text
retry scheduler 3 times
```

---

## 116. Generic Retry Prohibition Test

For:

```text
POLICY_INFEASIBLE
```

Verify that the system will not retry Solver.

---

## 117. Iterative Convergence Test

Coverage ↔ Scheduling: 

```text
max_iterations
business_delta_threshold
runtime_budget
```

Must be able to trigger stop.

Cannot loop infinitely.

---

## 118. Human Override Re-evaluation Test

After modifying Candidate:

```text
constraint
travel
workload
opportunity
change cost
```

Must recalculate.

---

# Part IX — Governance / Safety Benchmark

## 119. Governance is a horizontal Benchmark

All levels must be tested:

```text
Auditability
Reproducibility
Human Control
Evidence
Authorization
Transition Safety
```

---

## 120. Agent Authority Test

Agent not allowed:

```text
create hard constraint without policy
change objective silently
approve structural decision
write world state directly
```

---

## 121. Human Approval Test

High-risk Structural Decision must go through the prescribed Approval.

If missing:

```text
Transition blocked
```

---

## 122. Guardrail Exception Test

Candidate exceeds Guardrail:

```text
ReassignedRevenue = 13%
limit = 10%
```

Must:

```text
ExceptionReview
```

Cannot pass automatically.

---

## 123. Transition Safety Test

Approved Decision must not:

```text
directly overwrite all assignments
```

Must go through:

```text
TransitionPlan
```

Produce a clear World Event.

---

## 124. Rollback Test

Simulate:

```text
critical post-transition issue
```

Ensure:

```text
Rollback Decision / Transition
```

Can be created and audited.

---

## 125. Reproducibility Package

Each Benchmark Run must save at least:

```text
WorldSnapshot ID
Scenario ID
ProblemContract Version
Projection Version
Compiler Version
Solver Version
Parameters
Seed
Workflow Version
Run IDs
Candidate IDs
Evaluation Version
```

---

# Part X — Acceptance Gates

## 126. Gate 0 — Semantic Gate

Before entering any Solver Benchmark:

```text
Critical semantic invariants = PASS
Scenario isolation = PASS
Temporal replay = PASS
```

---

## 127. Gate 1 — Diagnosis Gate

Before entering Structural Candidate Benchmark, prove at least:

```text
True shortage
Territory imbalance
Location mismatch
Coverage mismatch
Data problem
```

Five categories can be correctly distinguished.

It is not recommended for v1.2 to directly set a global percentage threshold.

But must fully report:

```text
confusion matrix
false expansion rate
false structural trigger rate
no-action correctness
```

---

## 128. Gate 2 — Solver Gate

At least:

```text
toy analytical cases exact
small exact instances validated
independent constraint checker pass
failure semantics pass
reproducibility pass
```

Heuristic must disclose:

```text
optimality claim
```

---

## 129. Gate 3 — Decision Gate

Structural Candidate must:

```text
have baseline
include Maintain
report delta
report ChangeCost
report uncertainty
pass downstream feasibility
```

Otherwise not allowed to enter formal Human Approval.

---

## 130. Gate 4 — Production Evidence Gate

From Shadow to Pilot:

Must have:

```text
stable workflow
diagnostic quality
prediction calibration
human review process
rollback plan
```

From Pilot to Scale:

Must exist:

```text
DecisionValidation result
```

Instead of only looking at model backtest.

---

# Part XI — Benchmark Report

## 131. Standard Benchmark Report

Each round must output:

```text
1. Scope
2. Dataset / Snapshot
3. Ground Truth Type
4. Problem Contract
5. Solver / Workflow Version
6. Semantic Gate Result
7. Diagnostic Result
8. Solver Result
9. Decision Quality
10. Governance Result
11. Failure Cases
12. Regression vs Previous Version
13. Known Limitations
```

---

## 132. No Cherry-pick allowed

If the same algorithm runs multiple times:

```text
best
median
worst / P90
```

All should report applicable metrics.

Cannot only show the best Seed.

---

## 133. Regression Benchmark

Each significant version upgrade must rerun the fixed:

# `SRAF Core Benchmark Suite`

At least include:

```text
semantic core
diagnostic core
solver toy set
workflow core
governance core
```

---

## 134. Decision Regression

Not only test:

```text
code output changed?
```

Also test:

> Has the Candidate recommendation changed at the business level?

For example:

```text
v1:
Rebalance

v2:
Add 2 reps
```

Even if both versions of the code "pass unit tests", they must trigger a Decision Regression Review.

---

## 135. Explanation Regression

If the core Recommendation remains unchanged but the explanation Evidence changes, also check:

```text
provenance
hypothesis ranking
trade-off
```

Whether it is reasonable.

---

# Part XII — v1.2 MVP Benchmark Plan

## 136. Do not test all 7 Engines in the first phase

It is recommended to use the Visit Scheduling vertical slice that already has basic capabilities as the first line.

---

## 137. MVP Benchmark Slice A — Scheduling

Test:

```text
CoverageCommitment
→ Scheduling Precheck
→ Scheduler
→ Candidate
→ UnfulfilledCommitment
```

Cases: 

```text
A feasible
B global capacity infeasible
C temporal structural infeasible
D policy conflict
E solver timeout
```

Focus:

> Five states must be correctly distinguished.

---

## 138. MVP Benchmark Slice B — Diagnosis

Use 5 canonical cases:

```text
True Capacity Shortage
Territory Imbalance
Location Mismatch
Coverage Over-allocation
Data Corruption
```

Focus:

```text
Problem Router
False Expansion Recommendation
```

---

## 139. MVP Benchmark Slice C — Structural Rebalance

Do not pursue advanced Territory Solver first.

Use:

```text
Baseline
Maintain
Simple Rebalance
```

Compare:

```text
workload
opportunity
travel
change cost
```

Focus on verifying:

```text
Decision Contract
Delta Evaluation
Maintain Candidate
Human Override
```

---

## 140. MVP Benchmark Slice D — Orchestration

Verify:

```text
Sequential
Iterative
Failure Routing
Artifact Invalidation
Scenario Isolation
Human Override
```

---

# Part XIII — Reference Evidence Levels

## 141. Evidence Level

It is recommended that each SRAF capability be annotated with its evidence level in the future:

```text
E0 Conceptual
E1 Synthetic Validated
E2 Semi-synthetic Validated
E3 Historical Replay
E4 Shadow Production
E5 Pilot Validated
E6 Replicated Production
```

---

## 142. E0 must not be advertised as "verified business capability"

For example:

```text
Territory Solver prototype
```

If only E1 is present:

> It can be said "the algorithm passed the synthetic benchmark".

Cannot say:

> "It has been proven to increase sales".

---

## 143. E5 and E6

### E5 Pilot Validated

A real market verification.

### E6 Replicated Production

Repeated verification across multiple different markets.

This is close to:

> A reusable methodology

evidence standard.

---

# Part XIV — Architecture Gates

## 144. The following situations are directly considered Evaluation architecture problems

```text
Only perform Solver objective benchmark

No B0 Semantic Test

Historical backtest uses future information

Diagnostic Benchmark lacks NoAction Case

All test cases have problems

No DataQuality Root Cause Case

No Policy Conflict Case

Do not differentiate Resource Infeasible from Solver Failure

Heuristic is called Optimal

Only report the best Seed

Candidate lacks Baseline

Structural Benchmark does not include Maintain Candidate

No ChangeCost when evaluating Territory

Only use compactness to evaluate travel

Oracle itself has no accuracy Benchmark

No re-evaluation after HumanOverride

Business Outcome only does Before/After but claims causality

Pilot lacks ValidationPlan

Failed Decision is deleted

Benchmark and Production use different Contracts

No Decision Regression after version upgrade
```

---

# Part XV — Definition of Done

## 145. Implementation DoD of `06_EVALUATION_AND_BENCHMARK.md` v1.2

The first phase must at least complete:

### B0

```text
Canonical Identity
Temporal Replay
Scenario Isolation
Candidate Isolation
Semantic Status
```

Testing.

### B1

Correctly distinguish:

```text
True Capacity Shortage
Territory Imbalance
Location Mismatch
Coverage Mismatch
Data Quality Issue
```

### B2

Correctly distinguish:

```text
Business Infeasible
Model Infeasible
Solver Failure
```

And verify mathematical correctness on toy instances.

### B3

At least for:

```text
Maintain
Rebalance
Add Capacity
```

Perform a unified Delta Evaluation.

### B4

At least define a real Pilot's:

```text
DecisionValidationPlan
```

Even if v1.2 has not yet truly completed the Pilot.

---

## 146. Final Evaluation Principles

The evidence chain of SRAF should be:

```text
Semantic Correct
      ↓
Diagnostically Correct
      ↓
Mathematically Correct
      ↓
Decision Better Than Baseline
      ↓
Observed Business Outcome Supports It
```

Missing any layer, one cannot equate:

> "System runs successfully"

with:

> "Sales resource allocation decision is correct".

---

## 147. v1.2 Core Conclusion

The core issue of SRAF Benchmark is not:

> "How much faster is the algorithm than the Baseline?"

But rather:

> **Whether the system, under the premise of correctly understanding the world, identifies the correct problem, invokes the correct decision model, generates a plan worth changing, and is ultimately supported by real business outcomes.**

Therefore, the core benchmark unit of SRAF is not a single Solver Run, but should be gradually upgraded to:

# `Decision Case`

Comprehensive evaluation:

```text
World Snapshot
→ Diagnosis
→ Problem Route
→ Candidate Set
→ Decision
→ Outcome
```

This is the proper validation object of the Sales Resource Allocation Decision Intelligence Framework.
