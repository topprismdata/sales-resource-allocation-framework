# SRAF Decision Ontology Specification v1.2

**Project:** Sales Resource Allocation Framework
**Abbreviation:** SRAF
**Document:** `02_DECISION_ONTOLOGY.md`
**Status:** Implementation Baseline v1.2
**Upper-level Specification:**

```text
00_PROJECT_CHARTER.md
01_WORLD_MODEL_SPEC.md
```

---

## 1. Document Objectives

Decision Ontology must establish a unified business language between World Model and Decision Engine.

Core Chain:

```text
World State
    ↓
Allocation Health
    ↓
Allocation Gap
    ↓
Diagnostic Hypothesis
    ↓
Decision Trigger
    ↓
Decision Case
    ↓
Decision Problem
    ↓
Candidate Decision
    ↓
Delta Evaluation
    ↓
Review / Approval
    ↓
Transition Plan
    ↓
Execution
    ↓
Decision Validation
```

Therefore, Decision Ontology does not describe:

```text
Customer latitude and longitude
Employee name
Store address
Road network
```

These belong to the World Model.

It describes:

```text
Where the problem exists
Why the problem exists
Whether the problem is worth solving
What changes are allowed
What candidate solutions exist
What impact the solution has
Why a particular solution is chosen
How to implement
How to verify
```

---

## 2. Core Principles of Decision Ontology

Decision Ontology must comply with:

> **Problem before Solution.**

Prohibited:

```text
Territory Solver discovers better results
      ↓
Create a 'Territory Problem'
```

Correct order:

```text
World State
      ↓
Gap
      ↓
Diagnosis
      ↓
Decision Need
      ↓
Problem Definition
      ↓
Solver
```

i.e.:

> Solver does not create business problems.

---

## 3. Separation of Decision and World State

The following objects do not belong to Canonical World Truth:

```text
DiagnosticHypothesis
DecisionCase
CandidateDecision
Scenario
CandidateTerritory
CandidateDeployment
SolverSolution
```

They belong to:

# Decision State

Only:

```text
Approved Decision
      ↓
Transition
      ↓
Confirmed World Event
```

After that, the world state truly changes.

---

## 4. Decision Ontology First-level Objects

v1.2 fixes the following first-level objects:

```text
DECISION WORLD
│
├── AllocationHealth
├── AllocationGap
├── DiagnosticHypothesis
├── MaterialityAssessment
├── DecisionTrigger
├── DecisionCase
│
├── BusinessObjective
├── DecisionRequirement
├── DecisionProblem
├── CompositeDecisionProblem
│
├── CandidateDecision
├── DeltaEvaluation
├── ChangeCost
│
├── HumanReview
├── HumanOverride
├── RequirementExceptionProposal
├── Approval
├── ApprovedDecision
│
├── TransitionPlan
└── DecisionValidationPlan
```

These objects together form a complete Decision Lifecycle.

---

## 5. AllocationHealth

`AllocationHealth` represents:

> **The overall health status of the current sales resource allocation state within a certain business scope.**

It is not a simple score.

Structure:

```text
AllocationHealth

health_id

scope
period
baseline_snapshot

metrics

health_status
confidence

calculation_version
calculated_at
```

---

## 6. Health Scope

Health must have a clear Scope.

For example:

```text
Market
Region
Territory
ResourcePool
Channel
CustomerSegment
Product
```

Cannot have only:

```text
health_score = 72
```

but not knowing what 72 refers to.

---

## 7. Health Metric

v1.2 allows at least:

```text
OpportunityCoverage
CoverageAttainment
CapacityUtilization
OpportunityAtRisk
TravelBurden
WorkloadBalance
PotentialDistribution
CapabilityFit
AssignmentStability
TerritoryStability
ServiceLevel
DataConfidence
```

Most of these belong to Derived State.

Health is just a combined interpretation of these Derived State.

---

## 8. Health does not equal problem

For example:

```text
CapacityUtilization = 112%
```

It can only indicate:

```text
Metric abnormal
```

Cannot directly conclude:

```text
Need 2 additional reps
```

Therefore:

\[
HealthSignal
\neq
DecisionProblem
\]

Must go through:

```text
Gap
Diagnosis
Materiality
```

---

## 9. AllocationGap

`AllocationGap` is one of the core objects of Decision Ontology.

Formal definition:

> **Current Sales Resource Allocation with respect to a certain business requirement, opportunity status, or acceptable target state is an explicable difference.**

Unified structure:

```text
AllocationGap

gap_id
gap_type

scope
period

observed_value
reference_value
gap_value
unit

severity
persistence

business_impact

confidence
evidence

baseline_snapshot
calculation_version
```

---

## 10. Gap Type

v1.2 fixes seven first-level Gap categories:

```text
CoverageGap
CapacityGap
OpportunityGap
SpatialTravelGap
CapabilityGap
LocalAllocationGap
StabilityGap
```

---

## 10A. Gap Taxonomy Ownership

`02_DECISION_ONTOLOGY.md` only defines the upper-level semantics of the seven Gap categories.

`CoverageGap`, `CapacityGap`, `SpatialTravelGap`, etc.'s further subtype taxonomy is handled by `04_ALLOCATION_INTELLIGENCE.md`.

Therefore 02 no longer repeats maintenance of another set of detailed classifications.

---

## 11. CoverageGap

Indicates:

> The difference between the Coverage required by the business and the Coverage that can be achieved or actually achieved.

For example:

\[
CoverageGap
=
RequiredCoverage
-
AchievableCoverage
\]

Need to distinguish:

```text
PlannedCoverageGap
ActualCoverageGap
```

Because:

```text
The plan itself is not feasible
```

and:

```text
The plan is reasonable but execution fails
```

Are different problems.

---

## 12. CapacityGap

Indicates:

\[
CapacityGap
=
RequiredResourceCapacity
-
AvailableResourceCapacity
\]

Must be clear:

```text
ResourceType
Capability
Period
MarketScope
```

Therefore:

```text
Overall there is no shortage of personnel
```

Does not mean:

```text
There is no CapacityGap
```

May just be a missing certain type of Capability.

---

## 13. OpportunityGap

Definition:

> **Current resource allocation fails to effectively cover the serviceable market opportunity.**

Cannot be written as:

```text
LostSales
```

Because Opportunity is usually an Estimate.

A more accurate expression:

```text
UncoveredOpportunity
OpportunityAtRisk
IncrementalOpportunityGap
```

Must inherit from OpportunityEstimate:

```text
confidence
model_version
evidence
```

---

## 14. SpatialTravelGap

Answer:

> Is the resource being wasted due to unreasonable spatial deployment or responsibility division?

For example:

```text
peer travel burden     18%
current territory      36%
```

Or:

```text
current base location
→ expected field capacity 91h

alternative location
→ expected field capacity 118h
```

Such issues should in principle be prioritized into:

```text
ResourceLocation
TerritoryAlignment
```

rather than Sizing.

---

## 15. CapabilityGap

Indicates:

\[
RequiredCapability
\not\subseteq
AvailableCapability
\]

For example:

```text
Available capacity = 120h
Required workload  = 90h
```

Seems Capacity is sufficient.

But:

```text
required capability = KA Negotiation
resource capability = Field Generalist
```

Still cannot fulfill the responsibility.

---

## 16. LocalAllocationGap

`LocalAllocationGap` indicates:

> Global Demand and Supply are basically feasible, but local responsibility/resource allocation is unreasonable.

Keep `AllocationGap` as the supertype name for all sales resource allocation Gaps, and prohibit it from also being used as a subtype name.

For example:

```text
Total demand    = 4,200h
Total capacity  = 4,350h
```

Overall sufficient.

However:

```text
Territory A = 126%
Territory B = 72%
Territory C = 83%
```

This belongs to:

```text
Local Allocation Mismatch / LocalAllocationGap
```

Rather than:

```text
Global Capacity Shortage
```

---

## 17. StabilityGap

Indicates:

> Allocation currently appears feasible, but the change frequency or stability of responsibility relationships has become unacceptable.

For example:

```text
Assignment changes / 12 months
Territory boundary changes
Rep transfers
Customer ownership changes
```

Therefore Stable Allocation itself is also a value.

---

## 18. Gaps Can Coexist

Prohibition of assuming:

```text
One symptom
=
One gap
```

For example:

```text
CoverageGap
+
CapacityGap
+
OpportunityGap
+
TravelGap
```

Can coexist.

Decision Ontology must support:

```text
GapSet
```

Rather than forcing mutually exclusive classification.

---

## 19. DiagnosticHypothesis

Gap can only indicate:

> Where it is wrong.

Cannot yet explain:

> Why.

Therefore add:

# `DiagnosticHypothesis`

Definition:

> **A potential cause explanation for one or more Allocation Gaps that can be supported or refuted by evidence.**

Unified structure:

```text
DiagnosticHypothesis

hypothesis_id

target_gap_ids

hypothesis_type

statement

evidence_for
evidence_against

confidence

alternative_hypotheses

status
created_at
```

---

## 20. Hypothesis Is Not LLM Text

For example, prohibited:

```text
reason =
"May be due to insufficient staff, or the beat route being too long."
```

Instead should:

```text
Hypothesis H1
type = CapacityShortage
confidence = 0.31

Hypothesis H2
type = ExcessiveTravel
confidence = 0.82
```

And save evidence separately.

---

## 21. Root Cause Taxonomy

The first version should include at least:

```text
CapacityShortage
CapacitySurplus

TerritoryImbalance
ResourceLocationMismatch

CapabilityMismatch

CoveragePolicyMismatch
CoverageAllocationMismatch

SchedulingInfeasibility
RoutingInefficiency

MarketShift
PortfolioShift

PersonnelConstraint

DataQualityIssue
ModelQualityIssue
PolicyConflict
```

The identity-side subtypes of `DataQualityIssue` are owned by this document
(judgment rules and thresholds are in `08` §10–§14):

```text
IdentityDuplicate          Multiple unresolved records for the same object
IdentityFalseMatch         Already merged by mistake, with coverage hidden
IdentityUnresolved         Candidate undecided, confidence ceiling limited
HierarchyMisattribution    Group and its stores are double-counted
```

The purpose of these four subtypes is to make the H-DATA hypothesis in `04` **verifiable**,
rather than a catch-all garbage bin label.

---

## 22. EvidenceFor / EvidenceAgainst

This is a v1.2 mandatory requirement.

For example:

```text
Hypothesis:
CapacityShortage
```

Supporting evidence:

```text
utilization = 118%
missed required calls = high
```

Contradicting evidence:

```text
travel burden = 39%
peer travel burden = 20%
```

Then possibly:

```text
CapacityShortage confidence ↓

SpatialInefficiency confidence ↑
```

This prevents the Agent from only collecting evidence that supports its conclusion.

---

## 23. Diagnostic Status

Recommendation:

```text
Proposed
Supported
Contested
Rejected
Confirmed
```

Only when reaching:

```text
Supported / Confirmed
```

And satisfying the Confidence Gate, is it allowed to automatically enter part of the Decision Workflow.

---

## 24. Data / Model Hypothesis Must Exist

Any anomaly must allow:

```text
DataQualityIssue
```

To become a legitimate root cause.

Example:

```text
customer coordinates wrong
travel matrix stale
potential model drifted
service time inflated
duplicate accounts
```

Cannot assume:

> Data must be correct; the business configuration is problematic.

---

## 25. MaterialityAssessment

Even if both Gap and Root Cause are valid, it does not mean it is worth taking action.

Formal definition:

> **Measure whether an identified Allocation Problem has reached a business importance that justifies the organization to make a decision or adjust its structure.**

Structure:

```text
MaterialityAssessment

subject_gap_set

magnitude
persistence
business_impact
strategic_relevance
confidence

expected_decision_value

materiality_level
recommendation
```

---

## 26. Materiality Key Considerations

\[
Materiality
=
f(
Magnitude,
Persistence,
BusinessImpact,
Confidence,
StrategicImportance
)
\]

Cannot base solely on:

```text
metric > threshold
```

Trigger.

---

## 27. Persistence

Must clarify:

```text
DetectedAt
Duration
ObservationCount
```

For example:

```text
110% utilization for one week
```

With:

```text
110% utilization for four months
```

Semantics differ.

---

## 28. Materiality Level

v1.2 recommendation:

```text
Informational
Monitor
Review
Actionable
Critical
```

For example:

### Informational

Record, but no action required.

### Monitor

Continue to monitor.

### Review

Enter manual/Agent Diagnosis.

### Actionable

Allow creation of DecisionCase.

### Critical

Can enter the rapid response process.

---

## 29. DecisionTrigger

DecisionTrigger is not a simple alarm.

Formal definition:

> **A business rule used to create a DecisionCase after Gap, Diagnosis, Materiality, and governance conditions are satisfied.**

Structure:

```text
DecisionTrigger

trigger_id
trigger_type
scope

required_gap
required_hypothesis

entry_threshold
exit_threshold

persistence

confidence_gate
materiality_gate

cooldown

allowed_problem_types

policy_reference
```

---

## 30. Hysteresis

Must allow:

```text
EntryThreshold
ExitThreshold
```

For example:

```text
enter review:
utilization > 110% for 6 weeks

exit review:
utilization < 100% for 4 weeks
```

Avoid:

# Decision Flapping

---

## 31. Cooldown

After structural adjustment must allow:

```text
cooldown_period
```

For example:

```text
Territory realignment:
120 days
```

Unless a Critical Trigger occurs, do not restart structural adjustment.

This ensures Stability.

---

## 32. DecisionCase

This is the central object of the entire Decision Ontology.

Formal definition:

> **A complete decision unit built around a clear business resource allocation problem, containing Baseline, Evidence, Diagnosis, Objectives, Candidate Decisions, Review, and Validation.**

It is the Agent's primary work object.

---

## 33. DecisionCase Schema

Recommendation:

```text
DecisionCase

case_id

title
business_context

scope
decision_horizon

baseline_id

gap_ids
hypothesis_ids
materiality_id
trigger_id

business_objectives
decision_requirements

problem_types

status

owner
reviewers

created_at
closed_at
```

---

## 34. Decision Horizon

Follow the Charter:

```text
Strategic
Structural
Tactical
Operational
Execution
```

A DecisionCase can contain multiple Atomic Decision Problems, but must declare the primary Horizon.

For example:

```text
Expansion
```

May include:

```text
Strategic:
Incremental Sizing

Structural:
Location
Territory
Personnel
```

---

## 35. DecisionCase Status

Recommendation:

```text
Detected
Diagnosing
Framed
Solving
Reviewing
Approved
Rejected
Transitioning
Active
Evaluating
Validated
Failed
Closed
```

State must be explicit.

Cannot use:

```text
is_done = true
```

as a substitute for Decision Lifecycle.

---

## 36. BusinessObjective

Business objectives cannot be directly written as Solver objectives.

Formal definition:

> **The business outcome that the organization hopes to improve through this DecisionCase.**

For example:

```text
IncreaseHighPotentialCoverage
ReduceOpportunityAtRisk
ImproveServiceLevel
ReduceTravelBurden
ImproveCapacityUtilization
ProtectCustomerRelationships
ReduceOperatingCost
ImproveAllocationFairness
```

---

## 37. BusinessObjective Schema

```text
BusinessObjective

objective_id
objective_type

scope

direction
target
minimum_improvement

priority

measurement_metric

evaluation_window
```

---

## 38. Objective Priority

First version supports:

```text
Primary
Secondary
Supporting
Diagnostic
```

Instead of forcing from the start:

```text
weight = 0.23
```

Because many weights do not have real business justification.

---

## 39. DecisionRequirement

This abstraction is used for unification:

```text
Invariant
HardConstraint
Guardrail
Preference
```

Structure:

```text
DecisionRequirement

requirement_id
requirement_type

scope
semantic_rule

source_policy

priority

exception_allowed
exception_authority
```

---

## 40. Invariant

Definition:

> **Rules that the business world or core semantics do not allow to be violated.**

Examples:

```text
The same exclusive Primary Responsibility
Cannot have two active owners simultaneously.
```

or:

```text
CandidateDecision
Cannot directly modify Observed World
```

Invariant in principle cannot be bypassed through ordinary business approval.

---

## 41. HardConstraint

Indicates:

> **Business requirements that must not be violated in the current Decision Problem.**

Examples:

```text
Distributor contractual boundary

Mandatory KA ownership

Regulatory service constraint
```

Hard Constraint can differ depending on the DecisionCase.

---

## 42. Guardrail

This is a very important intermediate semantics.

Examples:

```text
ReassignedRevenue <= 10%
```

Possibly, in principle, we do not want to exceed.

but if:

```text
business gain is extremely high
```

Management can approve exceptions.

Therefore Guardrail:

```text
can be violated
but must generate an Exception
and requires explicit Approval
```

---

## 43. Preference

Indicates:

> Prefers a better direction among multiple feasible solutions.

Examples:

```text
lower travel
more compact
less churn
more balanced workload
```

Preference is not a business fact.

Nor is it a Hard Constraint.

---

## 43A. RequirementExceptionProposal

When the existing Requirement causes unacceptable business conflict in the current DecisionCase, the system can generate:

```text
RequirementExceptionProposal
```

It is not automatically relaxed by the Solver.

Minimal structure:

```text
proposal_id
decision_case_id
requirement_id

proposed_exception
scope
valid_period

business_reason
evidence
expected_impact

required_authority
status
```

Applicable scenarios include:

```text
temporary hard-constraint exception
guardrail exception
temporary policy exception
```

Only when the original `DecisionRequirement` explicitly allows an exception and the approval authority is satisfied can the Proposal affect the new Candidate / Problem Projection.

---

## 44. Why Must It Be Four Layers

Suppose we write it uniformly as:

```text
constraint
```

Developers can easily:

```text
Manager says it is best not to cross regions
→ hard constraint
```

Then the model has no solution.

It may also:

```text
Actual contract boundaries
→ soft penalty
```

Generate non-compliant business solutions.

Therefore, Semantic Classification must be performed first.

---

## 45. DecisionProblem

DecisionProblem formal definition:

> **A decision problem that, under a clear DecisionCase and World Baseline, requires changing certain controllable business variables while satisfying Requirements and improving Business Objectives.**

---

## 46. Atomic Decision Problem

v1.2 fixes seven categories:

```text
DP01 ResourceSizing
DP02 ResourceLocation
DP03 ResponsibilityTerritoryAlignment
DP04 PersonnelMatching
DP05 CoverageChannelAllocation
DP06 VisitScheduling
DP07 DailyRouting
```

Here we emphasize again:

> Problem Type is a business semantic, not a Solver Type.

---

## 47. AtomicProblem Contract

At least:

```text
problem_id
problem_type

decision_case_id

baseline
scenario

decision_horizon

required_world_projection

decision_variables

invariants
hard_constraints
guardrails
preferences

business_objectives

evaluation_metrics

solver_capability_requirements

validation_requirement
```

---

## 48. CompositeDecisionProblem

Formal definition:

> **A high-level business configuration problem composed of multiple Atomic Decision Problems.**

Version 1:

```text
CP01 DeploymentDesign
CP02 CapacityExpansion
CP03 StructuralRebalancing
CP04 CoverageExecutionDesign
```

---

## 49. Composite Problem does not have new business variables

This is an important rule.

For example:

```text
CapacityExpansion
```

Do not recreate a new one:

```text
expansion_variable
```

But orchestrate:

```text
IncrementalSizing
Location
Territory
Personnel
```

The variables of existing Atomic Problems.

---

## 50. CouplingMode

Composite Problem must declare:

```text
Independent
Sequential
Iterative
Joint
```

---

## 51. Independent

There is almost no substantial dependency between Atomic Problems.

---

## 52. Sequential

For example:

```text
Coverage Commitment
      ↓
Visit Scheduling
```

The previous result is the next input.

---

## 53. Iterative

For example:

```text
Territory Candidate
      ↓
Routing Evaluation
      ↓
Territory Improvement
```

Loop until:

```text
convergence
budget exhausted
no material improvement
```

---

## 54. Joint

Joint solution at the mathematical level:

```text
Sizing
+
Location
+
Territory
```

But the output must still be restored to three independent business Decision Objects.

That is:

> Mathematical jointness does not erase semantic boundaries.

---

## 55. CandidateDecision

Solver, Heuristic, Human, Rule Engine or Scenario can all produce:

# CandidateDecision

It is not a formal Decision.

Structure:

```text
CandidateDecision

candidate_id
decision_case_id

problem_id

candidate_type
origin

world_snapshot
scenario_id

changes

predicted_effects
uncertainty

constraint_status

change_cost

evaluation

created_at
```

---

## 56. Candidate Type

For example:

```text
MaintainCurrentState
MinorAdjustment
MajorReallocation
Expansion
Contraction
PolicyChange
LocationChange
CoverageChange
ScheduleChange
```

---

## 57. MaintainCurrentState

This is a v1.2 mandatory Candidate.

For Structural DecisionCase:

```text
Candidate A
=
Maintain Current State
```

Must exist in principle.

Only then can it truly answer:

> Is the adjustment worthwhile?

instead of:

> Which adjustment plan is best?

---

## 58. CandidateChange

Each Candidate should explicitly express:

```text
What changes?
```

rather than storing a black-box Solution Blob.

For example:

```text
ResourceDeployment D17
  Changsha North → Changsha West

Responsibility R28
  Rep12 → Rep17

Coverage C883
  2/month → 3/month
```

---

## 59. Candidate Origin

Must know the source:

```text
Solver
Heuristic
Human
Rule
ImportedPlan
Baseline
Hybrid
```

If it comes from a Solver:

```text
solver_id
solver_version
run_id
```

It should go into Provenance.

---

## 60. SolverSolution and CandidateDecision

The two cannot be merged.

```text
SolverSolution
      ↓
Decision Interpreter
      ↓
CandidateDecision
```

In Solver it may:

```text
x_17_92 = 1
```

In Candidate it should become:

```text
Responsibility 92
assigned to
Deployment 17
```

---

## 61. DeltaEvaluation

All Structural/Tactical Candidates should be compared with Baseline.

Formal definition:

> **Describes the change of Candidate Decision relative to Baseline in business metrics, risk, cost, and stability.**

Structure:

```text
DeltaEvaluation

candidate_id
baseline_id

metric_deltas

objective_attainment

guardrail_status
constraint_status

change_cost

uncertainty

evaluation_version
```

---

## 62. Delta is core, not Candidate Score

For example:

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| Opportunity Coverage | 81% | 87% | +6pp |
| Travel Burden | 24% | 19% | -5pp |
| Utilization Balance | 0.72 | 0.89 | +0.17 |
| Accounts Reassigned | 0 | 1,820 | +1,820 |
| Relationship Risk | 0 | High | ↑ |

Cannot only generate:

```text
Candidate Score = 87.3
```

---

## 63. ChangeCost

This is a first-level object of the Decision Ontology.

SRAF further generalizes it.

---

## 64. ChangeCost Type

At least:

```text
CustomerRelationshipCost
SalespersonIncomeImpact
RelocationCost
LearningCost
HandoverCost
TerritoryTransitionCost
ManagementChangeCost
SystemChangeCost
OrganizationalRisk
```

---

## 65. ChangeCost allows quantitative and qualitative

For example:

```text
expected revenue impact = -¥500k
```

Also possible:

```text
customer relationship risk = High
```

But all must be declared:

```text
estimate method
confidence
evidence
```

---

## 66. ChangeCost ≠ Penalty Weight

Expressed in World/Decision Ontology:

```text
CustomerRelationshipRisk = High
```

After Problem Compiler can be mapped to:

```text
penalty = ...
```

However the Ontology itself cannot store:

```text
lambda_disruption = 0.32
```

These solver-specific parameters.

---

## 67. Decision Evaluation Level

I suggest all Candidates use three-level evaluation:

```text
L1 Feasibility
L2 Efficiency
L3 Effectiveness
```

---

## 68. L1 Feasibility

Answer:

> Can the solution be executed?

For example:

```text
Hard constraints satisfied
Capacity feasible
Personnel feasible
Scheduling feasible
```

---

## 69. L2 Efficiency

Answer:

> Is the same resource investment more efficient?

For example:

```text
Travel
Idle capacity
Route efficiency
Change cost
```

---

## 70. L3 Effectiveness

Answer:

> Is the resource truly invested into a more valuable Opportunity?

For example:

```text
Opportunity coverage
Incremental value
Strategic account protection
Growth support
```

Therefore:

\[
GoodDecision
\neq
BalancedTerritory
\]

More accurate:

\[
GoodDecision
=
Feasible
+
Efficient
+
Effective
+
Governable
\]

---

## 71. Decision Confidence

Candidate is not only:

```text
expected improvement = 8%
```

but also should know:

```text
confidence
```

For example:

```text
Opportunity model confidence = 0.58
Travel estimate confidence = 0.92
Relationship risk confidence = 0.41
```

Decision Evaluation can establish:

```text
DecisionConfidence
```

but prohibits creating false precision.

---

## 72. UncertaintyModel

Each Problem / Candidate can declare:

```text
Deterministic
ScenarioBased
Robust
Stochastic
```

For example:

```text
Potential Low / Base / High
```

Evaluate Candidates separately.

---

## 73. Scenario Robustness

Candidate can have:

```text
expected case
downside case
upside case
```

For example:

| Candidate | Low | Base | High |
|---|---:|---:|---:|
| Maintain | 80 | 81 | 82 |
| Add 2 Reps | 79 | 87 | 93 |
| Rebalance | 83 | 86 | 88 |

This will help management see:

> Is the maximum benefit plan highly dependent on the Opportunity Forecast?

---

## 74. HumanReview

Human-in-the-loop must become a formal Decision Object.

Structure:

```text
HumanReview

review_id
decision_case_id
candidate_id

reviewer
review_scope

assessment
comments
evidence

review_status
created_at
```

---

## 75. Local Knowledge Review

SRAF normalizes it as:

```text
Central Candidate
        ↓
Local Review
        ↓
Evidence / Exception
        ↓
Re-evaluation
```

rather than:

```text
Manager drags the map
→ directly overwrites the model
```

---

## 76. HumanOverride

Formal definition:

> **Human explicitly modifies a Candidate Decision, and records reasons, evidence, and expected impact.**

Structure:

```text
HumanOverride

override_id

candidate_id
affected_object

old_value
new_value

reason_code
reason_text

evidence

expected_impact

author
approver

created_at
```

---

## 77. Override Reason Taxonomy

The first version can include:

```text
CustomerRelationship
LocalAccessConstraint
DistributorRelationship
LocalMarketKnowledge
PersonnelConstraint
ContractualRequirement
TemporaryCondition
DataCorrection
ModelLimitation
ManagementPreference
Other
```

---

## 78. Override must retain the original Candidate

Do not:

```text
Candidate V1
be overridden by humans
```

instead should:

```text
Candidate V1
     ↓
HumanOverride
     ↓
Candidate V1.1
```

The original plan remains traceable.

---

## 79. Approval

A formal Decision must come from:

```text
Candidate
      ↓
Approval
      ↓
ApprovedDecision
```

Approval at least:

```text
approval_id
candidate_id
authority
decision
conditions
timestamp
```

For example:

```text
Approved
ApprovedWithConditions
Rejected
Deferred
```

---

## 80. ApprovedDecision

`ApprovedDecision` is:

> **Formal approval result of a CandidateDecision confirmed by the governance process and allowed to enter Transition.**

Standard chain:

```text
DecisionCase
    ↓
CandidateDecision
    ↓
Approval
    ↓
ApprovedDecision
    ↓
TransitionPlan
```

`Decision` is used only as a conceptual umbrella term, not as a second set of canonical classes alongside `ApprovedDecision`.

Structure must include at least:

```text
approved_decision_id
decision_case_id
candidate_id
approval_id

effective_intent
conditions

approved_at
approved_by
```

---

## 81. TransitionPlan

A correct Target Allocation does not imply:

> Switch everything tomorrow.

Therefore:

# `TransitionPlan`

Must exist independently.

Structure:

```text
TransitionPlan

transition_id
approved_decision_id

target_state

phases
effective_dates

handover_actions
communication_actions
training_actions
compensation_actions

rollback_condition

transition_metrics

owner
```

---

## 82. Transition Phase

For example:

```text
Phase 1
Personnel preparation

Phase 2
Joint account handover

Phase 3
Ownership change

Phase 4
Stabilization

Phase 5
Post-transition evaluation
```

---

## 83. Structural Decision and Transition Must Be Separated

Objective:

```text
T2027Q1
```

May be the optimal Territory.

But if needed:

```text
3‑month customer handover
```

Then:

```text
Target State
```

Cannot immediately become:

```text
Current State
```

---

## 84. Transition Event

Transition Plan ultimately produces:

```text
World Events
```

For example:

```text
DeploymentActivated
ResponsibilityTransferred
CoverageCommitmentChanged
TerritoryActivated
```

Only then update the World Model.

---

## 85. Rollback

Large‑scale structural adjustments must allow:

```text
RollbackCondition
```

For example:

```text
Critical account loss
Service level collapse
Unexpected personnel loss
Data defect discovered
```

Rollback itself is also a new Decision/Transition.

Cannot directly roll back the database.

---

## 86. DecisionValidationPlan

This is the key object that differentiates SRAF from traditional Optimization Projects.

Formal definition:

> **Define, before the Decision is implemented, how the real execution results will be used to judge whether this decision is effective.**

Structure:

```text
DecisionValidationPlan

validation_id
approved_decision_id

hypothesis

primary_metrics
secondary_metrics

baseline

comparison_design

validation_window

success_threshold
failure_threshold

data_requirements

evaluation_method
```

---

## 87. Validation Hypothesis

For example:

```text
Territory rebalancing
will reduce travel burden
without reducing high-potential coverage.
```

Specifics:

```text
Travel -10%
HighPotentialCoverage >= baseline
```

---

## 88. Validation Window

Structural Decision should not:

```text
Implement on the second day
```

judge success or failure.

For example:

```text
30 days stabilization
+
90 days validation
```

Should be declared by the Decision type.

---

## 89. Control / Comparison

When conditions allow, Validation should support:

```text
Before / After
Matched Control
Holdout Region
Staggered Rollout
A/B
Synthetic Control
```

Which specific one to use is part of the Benchmark Specification.

---

## 90. Decision Outcome

Ultimately:

```text
DecisionOutcome

Expected
Observed
Delta

ValidationResult
Confidence
```

Can be:

```text
Validated
PartiallyValidated
Failed
Inconclusive
```

---

## 91. Failed Decision Is Not a System Anomaly

If:

```text
DecisionFailed
```

But at the time:

```text
Evidence
Assumptions
Decision Process
```

were all reasonable,

It is still a valuable learning sample.

The real problem is:

> Cannot explain why this Decision was made at that time.

---

## 92. LearningSignal

Decision Validation can generate:

```text
LearningSignal
```

For example:

```text
OpportunityModelOverestimated
TravelModelUnderestimated
ChangeCostIgnored
LocalKnowledgeMissing
CoverageResponseWeak
```

These signals feed into subsequent:

```text
Model Review
Policy Review
World Model Improvement
```

But will not allow the Agent to modify the core Ontology on its own.

---

## 93. Problem Router

Allocation Intelligence final output:

```text
DecisionCase
      ↓
ProblemRouter
```

First version mapping:

```text
Global Capacity Shortage
→ ResourceSizing / CapacityExpansion

Capacity Surplus
→ ResourceSizing / Downsizing

Wrong Resource Location
→ ResourceLocation

Local Allocation Imbalance
→ TerritoryAlignment

Personnel Capability / Fit
→ PersonnelMatching

Opportunity-Coverage mismatch
→ CoverageAllocation

Operational cycle infeasibility
→ VisitScheduling

Daily travel inefficiency
→ DailyRouting

Data quality
→ WorldModelRepair

Model quality
→ ModelGovernance

Policy mismatch
→ PolicyReview
```

---

## 94. Why does `WorldModelRepair` not belong to the 7 Decision Problems

Because:

```text
Data problem
```

It is not a Sales Resource Allocation Decision.

Therefore:

```text
WorldModelRepair
```

It belongs to Governance Workflow (see `05_DECISION_ORCHESTRATION.md` §14A, GW01).

You cannot stuff every exception into the Decision Problem Library.

Similarly:

```text
PotentialModelRetraining
```

It belongs to Model Governance (GW02).

`Policy mismatch` belongs to Policy Review (GW03).

None of the three occupy DP01–DP07 numbering and may not be registered as an Atomic Decision Problem,
nor may they be executed by a Solver; their output is **correction proposal + governance decision**, not a resource allocation Candidate.

---

## 95. Decision Case Example

For example:

```text
CASE:
Changsha Hexi high-potential catering Coverage Gap
```

Can be expressed as:

```text
Baseline:
2026-Q3 World Snapshot

Observed Gap:
Coverage Gap = 24%
Opportunity At Risk = ¥4.2m

Hypotheses:
H1 Capacity Shortage        0.31
H2 Travel Inefficiency      0.68
H3 Territory Imbalance      0.79

Materiality:
Actionable

Recommended Problems:
Territory Alignment
+
Resource Location Evaluation

Candidates:
A Maintain
B Minor Rebalance
C Major Rebalance
D Add 1 Resource

Primary Objective:
High Potential Coverage

Guardrails:
Reassigned Revenue < 10%
Customer Relationship Risk <= Medium
```

This is a complete Decision Case.

---

## 96. Relationship between Decision Case and Agent

The standard interface of an Agent should not be:

```text
Give me a bunch of customer data
```

Instead, the priority should be:

```text
DecisionCase
```

Agent queries:

```text
World Snapshot
Gap
Evidence
Hypothesis
Policy
Candidate
Evaluation
```

Then calls the specific Tool.

---

## 97. Agent Does Not Own Objective

Agent is not allowed to decide on its own:

```text
"I think workload fairness is the most important"
```

Objective must come from:

```text
BusinessObjective
DecisionPolicy
Human Decision
```

Agent can point out goal conflicts.

It cannot redefine organizational goals on its own.

---

## 98. Agent Does Not Own Hard Constraint

Similarly prohibited:

```text
LLM:
"This region looks like it should not cross the river."
```

Then directly becomes a Hard Constraint.

At most it can generate:

```text
Candidate Diagnostic Hypothesis
```

or:

```text
Proposed Preference
```

After Evidence / Human Review can it become a Requirement.

---

## 99. Decision Ontology Core Relationship Diagram

The final core relationship can be expressed as:

```text
               WORLD SNAPSHOT
                     │
                     ↓
             AllocationHealth
                     │
                     ↓
               AllocationGap
                     │
                     ↓
          DiagnosticHypothesis
                     │
                     ↓
          MaterialityAssessment
                     │
                     ↓
              DecisionTrigger
                     │
                     ↓
               DecisionCase
                     │
         ┌───────────┼───────────┐
         ↓           ↓           ↓
   Objective     Requirement   Baseline
         │           │           │
         └───────────┼───────────┘
                     ↓
              DecisionProblem
                     │
                     ↓
              ProblemProjection
                     │
                     ↓
                   Solver
                     │
                     ↓
               SolverSolution
                     │
                     ↓
             CandidateDecision
                     │
                     ↓
              DeltaEvaluation
                     │
              ┌──────┴──────┐
              ↓             ↓
         HumanReview      Maintain
              │
              ↓
            Approval
              │
              ↓
             Decision
              │
              ↓
         TransitionPlan
              │
              ↓
            Execution
              │
              ↓
          Observation
              │
              ↓
     DecisionValidationPlan
              │
              ↓
        DecisionOutcome
```

---

## 100. Architecture Gates

In the implementation of `02_DECISION_ONTOLOGY`, the following situations should be rejected as architectural issues:

```text
Metric abnormal directly equates to Decision Problem

AllocationGap has no Baseline / reference

Diagnosis has no Evidence Against

LLM text directly becomes Root Cause Truth

DecisionCase has no Baseline

Structural Decision does not contain Maintain Candidate

Objective directly saves solver weight

Policy and Hard Constraint are not distinguished

Guardrail is treated as an inviolable rule

Candidate Solution directly equals Decision

SolverSolution directly becomes Candidate World State

Candidate has no Provenance

Candidate only stores total score, does not store Delta

Territory adjustment does not compute ChangeCost

Human Override silently overwrites the original Candidate

Human Override does not record reason

Target State merges with Transition Plan

Decision has no Validation Plan before implementation

Solver Objective Improvement is considered business success

Failed Decision is deleted

Agent can freely modify Objective / Constraint
```

---

## 101. MVP Scope

To prevent v1.2 from being overly heavy, the first version of Decision Ontology must at least implement:

```text
AllocationGap
DiagnosticHypothesis
MaterialityAssessment
DecisionCase

BusinessObjective
DecisionRequirement

AtomicDecisionProblem

CandidateDecision
DeltaEvaluation
ChangeCost

HumanReview
HumanOverride

Decision
TransitionPlan
DecisionValidationPlan
```

For now, it can be simplified:

```text
Complex approval hierarchy
Complex stochastic object
Complex causal graph engine
Automated ontology learning
```

---

## 102. Definition of Done

Decision Ontology v1.2 cannot use as:

> Classes and tables have been created

as completion.

Must at least run through such a real Case:

```text
World Snapshot
      ↓
Detect Territory Capacity Imbalance
      ↓
Create AllocationGap
      ↓
Generate 3 DiagnosticHypotheses
      ↓
Evidence-backed Diagnosis
      ↓
Materiality = Actionable
      ↓
Create DecisionCase
      ↓
Frame TerritoryAlignmentProblem
      ↓
Generate:
  Maintain
  Minor Rebalance
  Major Rebalance
      ↓
Delta Evaluation
      ↓
Human Override
      ↓
Approval
      ↓
TransitionPlan
      ↓
Observed Outcome
      ↓
Decision Validation
```

After this chain is fully traversed, Decision Ontology is truly established.

---

## 103. Final Boundary with `01_WORLD_MODEL_SPEC`

Can be compressed into one sentence:

```text
WORLD MODEL
=
What exists and what is true/estimated now?

DECISION ONTOLOGY
=
What is wrong, what may change,
why should it change,
and how do we know the decision worked?
```

Or more engineering-oriented:

```text
Observed World
     ↓
Decision Case
     ↓
Candidate Future Worlds
     ↓
Approved Transition
     ↓
Observed World
```
