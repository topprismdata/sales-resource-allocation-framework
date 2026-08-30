# SRAF Decision Problem Contracts Specification v1.2

**Project:** Sales Resource Allocation Framework
**Document:** `03_DECISION_PROBLEM_CONTRACTS.md`
**Status:** Implementation Baseline v1.2

**Parent Specification:**
`00_PROJECT_CHARTER.md`, `01_WORLD_MODEL_SPEC.md`, `02_DECISION_ONTOLOGY.md`

---

## 1. Core Principles

No Decision Engine may directly define its own business problem:

```text
DecisionCase
      ↓
DecisionProblemContract
      ↓
ProblemProjection
      ↓
ProblemCompiler
      ↓
Solver
```

Solver receives a problem that has been clearly defined by business semantics, rather than a pile of raw business data.

---

## 1A. Normative Ownership

This document uniquely has:

```text
AtomicDecisionProblem
CompositeDecisionProblem
DecisionProblemContract
ProblemProjection
FeasibilityOracle Contract
Failure Semantics
SolverCapabilityRequirement
ProblemRun
```

It references World / Decision / Workflow objects, but does not redefine their canonical schema.

---

## 2. Questions a Contract Must Answer

Each Contract must answer:

```text
1. What business problem am I solving?
2. What is the current world state?
3. What is allowed to change?
4. What is absolutely not allowed to change?
5. What rules must be satisfied?
6. Which are merely optimization preferences?
7. What results are considered feasible?
8. What results are considered better?
9. How should the output be interpreted back into the business world?
10. If it fails, what does the failure actually mean?
```

---

## 3. Canonical Contract

```yaml
DecisionProblemContract:
  identity:
    problem_id:
    problem_type:
    contract_version:

  context:
    decision_case_id:
    decision_horizon:
    baseline_id:
    scenario_id:

  world_projection:
    required_entities:
    required_relations:
    required_derived_states:
    data_quality_requirements:
    temporal_context:
identity_snapshot_id:      # version of the identity decision set used, see 08 §20
min_identity_confidence:   # subjects with confidence below this value must not enter structural decisions

  decision_scope:
    mutable_objects:
    immutable_objects:
    decision_variables:

  requirements:
    invariants:
    hard_constraints:
    guardrails:
    preferences:

  objectives:
    primary:
    secondary:
    diagnostic_metrics:

  feasibility:
    prechecks:
    feasibility_oracles:
    acceptance_rules:

  uncertainty:
    uncertainty_mode:
    required_confidence:
    scenarios:

  output:
    candidate_schema:
    required_explanations:
    required_deltas:

  evaluation:
    evaluation_metrics:
    baseline_comparison:
    validation_contract:

  solver_requirements:
    capability_requirements:
    runtime_budget:
    optimality_requirement:
    reproducibility_requirement:

  failure_semantics:
    allowed_failure_types:
```

---

## 4. ProblemProjection Is the Boundary Between Contract and Solver

WorldModel → ProblemProjection → SolverModel. 

ProblemProjection performs purpose‑limited extraction, aggregation, and transformation of the world, but must not rewrite the Canonical World.

---

## 5. Separation of Business Variables and Mathematical Variables

Contract declares business variables, such as ResponsibilityAssignment, ResourceDeployment, CoverageCommitment, and whether they can change.

`x[i,j]`, `y[k]`, `z[t]`, etc. belong only to the Solver Model.

```text
Business Decision Variable
          ↓
Problem Compiler
          ↓
Mathematical Variable
```

After solving, they must be re‑interpreted back to business objects.

---

## 6. Immutable Objects

Each Contract must explicitly state what is not allowed to change for this decision. The Solver must not "solve" the problem by silently modifying upstream decisions.

---

## 7. Feasibility Does Not Equal Optimality

First determine whether a Candidate belongs to the FeasibleSet, then optimize. A good Objective cannot override a Hard Constraint.

---

## 8. ProblemFeasibilityPrecheck

Before invoking an expensive Solver, first check for obvious business infeasibility, such as Required workload significantly higher than Available capacity while both Coverage/Resource cannot be changed.

The purpose of Precheck is both to save computation and to distinguish "business infeasibility" from "Solver/Model error".

---

## 9. FeasibilityOracle

Standard Oracle:

```text
SchedulingFeasibilityOracle
RoutingFeasibilityOracle
PersonnelFeasibilityOracle
CapacityFeasibilityOracle
TravelFeasibilityOracle
PolicyFeasibilityOracle
```

Oracle only returns feasibility evidence and must not automatically modify a Candidate.

---

## 10. Infeasibility Taxonomy

Do not uniformly return `INFEASIBLE`. Distinguish at least:

```text
F1 DATA_INFEASIBLE
F2 PROJECTION_INFEASIBLE
F3 POLICY_INFEASIBLE
F4 RESOURCE_INFEASIBLE
F5 STRUCTURAL_INFEASIBLE
F6 MODEL_INFEASIBLE
F7 SOLVER_FAILURE
```

`F1 DATA_INFEASIBLE` is one of the legitimate causes,
subject identity not resolved or there is a blocked identity conflict.
 (`08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §14) . 
In this case, route to `GW01 WorldModelRepair`,
and **must not** before `IdentityDuplicate` is excluded
interpret it as `F4 RESOURCE_INFEASIBLE` (false manpower shortage).

Separate Solver status from Business feasibility:

```text
OPTIMAL
FEASIBLE
FEASIBLE_WITH_GAP
UNKNOWN
TIME_LIMIT
MEMORY_LIMIT
MODEL_ERROR
NUMERICAL_FAILURE
```

Layer as follows:

```text
Business Feasibility
        ↓
Model Feasibility
        ↓
Solver Success
```

---

# DP01 — Resource Sizing

## 11. Problem Definition

> Under the current market opportunity and Coverage Strategy, how many different types of sales resources are needed?

Required Projection: 

```text
DemandSurface
OpportunityEstimate
CoverageNeed
ResourceArchetype
CapacityModel
TravelApproximation
CostModel
BusinessPolicy
```

Mutable: 

```text
ResourceRequirement
ResourceMix
ResourceEnvelope
```

Immutable by default: 

```text
Market Definition
OpportunityEstimate
CoverageNeed
ResourceArchetype definition
```

Primary Objective: 

```text
Maximize Addressable / Profitable Opportunity Coverage
```

Secondary: 

```text
Minimize resource cost
Improve service level
Maintain utilization target
Reduce missed profitable coverage
```

Required Output: 

```text
ResourceRequirement
ResourceCoverageFrontier
MarginalCapacityCurve
ExpectedUtilization
ExpectedOpportunityCoverage
ExpectedServiceLevel
UncertaintyRange
```

Sizing defaults to Frontier First, rather than only outputting a single‑point headcount.

Allow iterative / joint coupling with Coverage Allocation, Resource Location, and Territory.

> **DP01 Prerequisite Gate (v1.2.1)**: sales effort has a cross‑period impact on sales volume (carryover: current year sales = current year effort + prior‑year carryover; see CHANGELOG_v1.2.1)
> carryover (current year sales = current year effort + previous years' carryover; see CHANGELOG_v1.2.1).
> In the SalesResponseEstimate / OpportunityEstimate contract, explicitly declare
> before `impact_horizon` and `carryover_share` (or equivalent lag parameters),
> **must not start the implementation of the DP01 Sizing Engine**;
> Otherwise, the marginal capacity curve and MarginalValue will credit the output of previous years' efforts to this year's Candidate,
> Frontier and staffing recommendations are systematically overestimated. B4 Validation must also declare
> `minimum_lag_window`, to avoid misclassifying the lag effect due to a mismatched observation window as Failed.

---

# DP02 — Resource Location

## 12. Problem Definition

> Where should sales capacity be deployed?

Required Projection: 

```text
DemandSurface
OpportunitySurface
TravelNetworkReference
ResourceRequirement
CandidateLocations
ExistingDeployment
ChangeCost
BusinessBoundary
```

Mutable: 

```text
ResourceDeployment.base_location
ResourceDeployment.capacity_commitment
DeploymentOpenCloseStatus
```

Immutable by default: 

```text
Resource Headcount
Opportunity
Coverage
```

Output:

```text
CandidateDeployments
ExpectedTravelBurden
Reachability
ServiceReach
EffectiveCapacity
RelocationImpact
PersonnelFeasibility
```

Must simultaneously support IdealDeployment and ExistingPersonnelFeasibleDeployment.

---

# DP03 — Responsibility / Territory Alignment

## 13. Problem Definition

> Given a fixed Resource Envelope and Coverage Context, how should sales responsibilities be allocated and organized?

Required Projection: 

```text
ResponsibilityUnit
Opportunity
CoverageCommitment / Need
IntrinsicWorkload
CapacitySupply
ResourceDeployment
TravelMeasure
ExistingAssignment
BusinessBoundary
CapabilityEligibility
ChangeCost
```

Mutable: 

```text
ResponsibilityAssignment
TerritoryMembership
```


Among them:

```text
TerritoryMembership
=
Territory ↔ Responsibility
```

The `ResponsibilityAssignment` must not be treated as territory membership; an Assignment only indicates who currently bears the Responsibility.

Immutable by default: 

```text
ResourceCount
CoveragePolicy
OpportunityEstimate
ResourceCapability
```

Invariants: 

```text
Every mandatory responsibility is assigned
Exclusive primary responsibility has at most one active owner
Resource eligibility cannot be violated
Temporal overlap rules remain valid
```

Hard Constraints may include contractual distributor boundaries, mandatory KA ownership, legal geography, and fixed personnel assignments.

Guardrails may include reassigned revenue, account churn, utilization, etc.; violations must be flagged with exception + impact + approval.

Preferences: 

```text
lower travel
better workload balance
better opportunity coverage
greater spatial coherence
less disruption
```

Travel Evaluation Fidelity: 

```text
L1 Geometric
L2 Network
L3 Routing Simulation
```

Output:

```text
ResponsibilityAssignments
TerritoryDefinitions
TerritoryProjection
OpportunityDistribution
WorkloadDistribution
CapacityUtilization
TravelEstimate
ChangeCost
Exceptions
UnassignedResponsibilities
```

---

# DP04 — Personnel Matching

## 14. Problem Definition

> Who should bear the already determined Resource Deployment / Territory Responsibility?

Required Projection: 

```text
SalesResource
Person
Capability
Availability
HomeLocation
ResourceDeployment
CurrentDeploymentAssignment
Territory
RelationshipState
PerformanceEvidence
RelocationPreference
EmploymentPolicy
```

Mutable: 

```text
DeploymentAssignment
```

`ResourceDeployment` denotes a deployment slot that needs to be filled; `SalesResource` denotes an actual capability instance; DP04 links the two temporally via `DeploymentAssignment`.

Goal:

```text
Capability Fit
Location Fit
Relationship Continuity
Personnel Stability
Fairness
Retention Risk
```

Prohibit directly using raw sales performance as the core objective for personnel matching without correction; historical performance must be territory-normalized or explicitly bounded.

---

# DP05 — Coverage & Channel Allocation

## 15. Problem Definition

> What sales activities, how much effort, and through which Sales Resource / Channel should be invested for different Accounts / Opportunities?

Required Projection: 

```text
Account / Prospect
OpportunityEstimate
CoverageNeed
SalesActivity
ResourceArchetype
ResourcePool
ChannelCapability
SalesResponseEstimate
Policy
ResourceEnvelope
```

Mutable: 

```text
CoverageCommitment
ServiceChannel
ResourceTypeAllocation
ActivityMix
```

Coverage must support:

```text
minimum
preferred
maximum
```

And invoke SchedulingFeasibilityOracle to avoid a workload that is nominally feasible but temporally infeasible.

The output must express multi-resource / multi-channel service rather than a single frequency.

---

# DP06 — Visit Scheduling

## 16. Problem Definition

> How should a confirmed CoverageCommitment be scheduled for a specific period/date?

Required Projection: 

```text
ResponsibilityAssignment
CoverageCommitment
SalesResource
ResourceDeployment
Calendar
Capacity
SpacingPolicy
VisitWindows
TravelEstimate
FixedDayPolicy
```

Mutable: 

```text
VisitPeriodAssignment
VisitDayAssignment
```

Immutable: 

```text
Territory ownership
Coverage commitment
Resource location
Opportunity
```

Goal:

```text
maximize committed visit feasibility
balance daily workload
respect spacing
reduce schedule instability
reduce travel burden
```

When not all can be scheduled, it must output:

```text
UnfulfilledCoverageCommitment
reason
severity
upstream implication
```

If monthly workload <= monthly capacity but the schedule has no solution, `TEMPORAL_STRUCTURAL_INFEASIBILITY` should be identified, not a global capacity shortage.

---

# DP07 — Daily Routing

## 17. Problem Definition

> After a set of visits for a given day is determined, in what order and path should they be executed?

Required Projection: 

```text
DailyVisitSet
Start / End Location
TravelNetwork
TimeWindows
ServiceTimes
Vehicle / Mobility
BreakRules
```

Mutable: 

```text
VisitSequence
Route
ArrivalTime
```

Immutable: 

```text
Long-term Territory
Monthly Coverage
Cycle Assignment
```

Output:

```text
RouteSequence
TravelTime
Distance
ServiceTime
RouteDuration
TimeWindowViolations
UnservedStops
FeasibilityStatus
```

The Routing Engine can also serve as a Feasibility Oracle for DP03/DP06.

---

# Composite Problems

## 18. CP01 Deployment Design

```text
Sizing + Location + Territory
```

Common in greenfield scenarios, supporting Sequential / Iterative / Joint.

## 19. CP02 Capacity Expansion

```text
Incremental Sizing + Location + Territory + Personnel
```

The core evaluation is IncrementalValue - ChangeCost.

## 20. CP03 Structural Rebalancing

```text
Territory + Personnel + ChangeCost
```

Baseline and Maintain Candidate are mandatory.

## 21. CP04 Coverage Execution Design

```text
Coverage + Scheduling + Routing
```

A typical iterative loop.

---

## 22. Coupling Contract

```yaml
coupling:
  mode: sequential | iterative | joint
  upstream_problem:
  downstream_problem:
  feedback_variables:
  stopping_rule:
  maximum_iterations:
  convergence_metric:
```

Stopping conditions may use objective improvement, business delta, max iterations, runtime budget, etc., and must not just write `until optimal`.

---

## 23. Solver Capability Contract

Decision Problems are not bound to a Solver; they only declare capability requirements:

```text
problem_types
scale
variable_support
constraint_support
multi_objective
uncertainty
warm_start
incremental_solve
optimality
explainability
reproducibility
runtime_class
```

Maintain SolverRegistry; separate ProblemRouter and SolverSelector.

---

## 24. Optimality Contract

Solver Result must be explicit:

```text
Exact Optimal
Provable Gap
Feasible Heuristic
Best Known Candidate
No Guarantee
```

Heuristics must not claim global optimum at the business layer.

---

## 25. Candidate Explainability Contract

Candidate must at least answer:

```text
What changed?
Why did it improve?
Which objectives improved?
Which metrics got worse?
Which guardrails are close or violated?
Which assumptions matter most?
```

Explanations are based on Structured Decision Evidence, and LLM only converts them into business language.

---

## 26. Evaluation Contract

Atomic Problems must declare Primary, Secondary, Guardrail, and Diagnostic Metrics.

Unified Shared Evaluation Space across Problems:

```text
Opportunity Coverage
Service Level
Resource Cost
Capacity Utilization
Travel Burden
Change Cost
Stability
Business Risk
```

---

## 27. Validation Contract

Each Problem Type declares its real observation validation metrics after implementation.

---

## 28. Versioning / Reproducibility

Candidate traceable:

```text
WorldSnapshot
ProblemProjection Version
ProblemContract Version
Compiler Version
Solver Version
Parameters
Random Seed
Run ID
```

Define ProblemRun as a technical Provenance object; a Run can produce multiple Candidates.

Benchmark and Production must use the same Contract.

---

## 29. Shadow Decision / Dry Run

DryRun only computes Candidate, does not enter Execution.

ShadowDecision does not execute, but continues to use future real Observations to validate prediction, feasibility, and diagnostic stability.

---

## 30. Failure Recovery

```text
DATA_INFEASIBLE → Data Quality Review
POLICY_INFEASIBLE → Policy Conflict Review
RESOURCE_INFEASIBLE → Sizing / Coverage Review
STRUCTURAL_INFEASIBLE → Composite Allocation Review
MODEL_INFEASIBLE → Model Engineering Review
SOLVER_FAILURE → Alternate Solver / runtime strategy
```

Prohibit Solver from automatically turning a Hard Constraint into soft after infeasibility. If relaxation is allowed, a ConstraintRelaxationProposal must be generated and approved.

---

## 31. Reference Engine — visit-scheduling-optimizer

Registration:

```text
engine_id: visit-scheduling-optimizer
supported_problem: DP06 VisitScheduling
oracle_capabilities: SchedulingFeasibilityOracle
```

Standard input comes from VisitSchedulingProblemProjection.

Standard output must at least include:

```text
FeasibilityStatus
UnfulfilledCommitments
ConstraintConflictEvidence
CapacityUtilization
ScheduleStability
TravelEstimate
OptimalityStatus
```

---

## 32. Architecture Gates

In principle, reject:

```text
Solver directly queries the entire World Model.
Solver interprets business fields by itself.
Mixing Business Decision Variables with mathematical variables.
A Problem silently modifies upstream decisions.
Scheduling automatically changes Coverage.
Territory automatically changes Headcount.
Running an expensive Solver without a Precheck.
All infeasible cases return the same status.
Solver timeout is interpreted as business unsolvable.
Policy conflict is interpreted as mathematically unsolvable.
Insufficient resources are treated as a Territory Solver failure.
Automatic soft relaxation after hard constraint infeasibility.
Heuristic candidate is called a global optimum.
Candidate only stores the objective score.
No Baseline delta.
No optimality claim.
No run provenance.
Benchmark and production use different contracts.
Solver-specific data is written back to the World Model.
```

---

## 33. MVP Sequence and DoD

First vertical slice:

```text
World Model
→ CoverageCommitment
→ DP06 VisitSchedulingProblem
→ ProblemProjection
→ visit-scheduling-optimizer
→ CandidateSchedule
→ Evaluation
```

Second item adds Allocation Health / Gap / Diagnosis / Problem Routing.

Third item implements a simplified DP03 Territory Rebalance.

Demonstrate at least five types of Cases:

```text
Business Feasible
Resource Infeasible
Temporal Structural Infeasible
Solver Failure
Policy Infeasible
```

and correctly classify them.
