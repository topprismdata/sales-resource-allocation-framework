# SRAF Reference Architecture Specification v1.2

**Project:** Sales Resource Allocation Framework
**Abbreviation:** SRAF
**Document:** `07_REFERENCE_ARCHITECTURE.md`
**Status:** Implementation Baseline v1.2

**Upper-level Specifications:**

```text
00_PROJECT_CHARTER.md
01_WORLD_MODEL_SPEC.md
02_DECISION_ONTOLOGY.md
03_DECISION_PROBLEM_CONTRACTS.md
04_ALLOCATION_INTELLIGENCE.md
05_DECISION_ORCHESTRATION.md
06_EVALUATION_AND_BENCHMARK.md
```

---

# 1. Document Objectives

This document is responsible for converging the aforementioned business semantics, decision models, and Benchmark specifications into an actionable reference architecture.

It answers:

```text
What engineering modules does SRAF need?
What are the boundaries between modules?
Which capabilities are owned by SRAF itself?
Which capabilities should prioritize reusing mature frameworks?
Where is the Agent?
Where is the Solver?
How is the World Model implemented?
How does the existing visit-scheduling-optimizer connect?
What sequence should be implemented in the first phase?
```

This document is not detailed code design.

It defines:

> **Reference Architecture + Module Boundaries + Integration Contracts + Implementation Sequence。**

---

# 2. Architecture Top-level Principles

SRAF engineering implementation must continue to comply with:

```text
World before Optimization
Diagnosis before Optimization
Problem before Solver
Baseline before Change
Evidence before Automation
Decision before Transition
Observation before Learning
```

Therefore, the physical architecture must reflect these boundaries, not just exist in documents.

---

# 3. SRAF Reference Architecture Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL / SOURCE SYSTEMS                    │
│ CRM / SFA / HR / ERP / POS / POI / Maps / Road / Market Data  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 01. SOURCE ADAPTER & CANONICALIZATION                           │
│ ingestion / identity / mapping / validation / provenance        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 02. SALES WORLD MODEL                                           │
│ canonical state / temporal state / evidence / events / spatial  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
               ┌────────────────┴─────────────────┐
               ▼                                  ▼
┌──────────────────────────────┐     ┌─────────────────────────────┐
│ 03. DERIVED STATE ENGINE     │     │ 04. SEMANTIC / GRAPH VIEW   │
│ opportunity/workload/capacity│     │ graph projection / evidence │
└───────────────┬──────────────┘     └─────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 05. ALLOCATION INTELLIGENCE                                    │
│ health / gap / diagnosis / materiality / trigger / router       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 06. DECISION CASE & ONTOLOGY                                   │
│ objective / requirement / baseline / candidate / change cost    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 07. DECISION ORCHESTRATION                                     │
│ workflow / scenario / decomposition / oracle / human checkpoint │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 08. PROBLEM PROJECTION & DECISION COMPILER                     │
│ world projection / business variables / math model compiler     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
               ┌────────────────┴─────────────────┐
               ▼                                  ▼
┌──────────────────────────────┐     ┌─────────────────────────────┐
│ 09. SOLVER REGISTRY          │     │ 10. ORACLE / SIMULATION    │
│ CP-SAT/MILP/heuristic/etc.   │     │ scheduling/routing/etc.    │
└───────────────┬──────────────┘     └──────────────┬──────────────┘
                └────────────────┬───────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. CANDIDATE INTERPRETER & EVALUATION                         │
│ candidate / delta / uncertainty / guardrail / trade-off         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 12. HUMAN GOVERNANCE                                           │
│ review / override / approval / exception                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 13. TRANSITION & EXECUTION CONNECTOR                           │
│ transition plan / event / CRM-SFA integration                   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ 14. OBSERVATION / VALIDATION / BENCHMARK                       │
│ outcome / replay / shadow / pilot / learning signal             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                └───────────────→ World Model
```

---

# 4. Architecture Divided into Four Planes

To avoid all components being mixed in the same "platform" concept, v1.2 divides SRAF into four engineering planes:

```text
A. World Plane
B. Decision Plane
C. Computation Plane
D. Governance & Evidence Plane
```

---

# 5. A. World Plane

Responsible for:

> **What the world is now.**

Contains:

```text
Source Adapter
Canonical World State
Temporal State
Evidence
Observation
Event
Spatial Reference
Derived State
Graph Projection
```

World Plane is not responsible for:

```text
Candidate solutions
Mathematical solving
Approval
```

---

# 6. B. Decision Plane

Responsible for:

> **Where the problems are, what should be decided, what candidates exist.**

Contains:

```text
Allocation Intelligence
Decision Ontology
DecisionCase
Problem Router
Scenario
Workflow
CandidateDecision
DeltaEvaluation
```

Decision Plane does not own specific Solver implementations.

---

# 7. C. Computation Plane

Responsible for:

> **How to calculate candidate configurations and feasibility.**

Contains:

```text
ProblemProjection
DecisionCompiler
SolverRegistry
SolverAdapter
FeasibilityOracle
Simulation
Routing
Scheduling
```

Computation Plane cannot directly modify the real World State.

---

# 8. D. Governance & Evidence Plane

Responsible for:

> **Why believe it, who approves, and whether it is effective after implementation.**

Contains:

```text
Provenance
HumanReview
HumanOverride
Approval
TransitionPlan
DecisionValidation
Benchmark
Audit
```

This plane runs through A/B/C, rather than being an end module.

---

# 9. v1.2 Core Technology Selection

Reference Implementation first phase recommendation:

```text
PostgreSQL + PostGIS
```

As:

```text
Canonical State
Temporal State
Spatial Data
Policy
Assignment
Decision Metadata
Snapshot Metadata
```

as the primary storage.

Reasons:

- Relational model is suitable for strong constraints and transactional consistency;
- PostGIS is sufficient for first-phase spatial capabilities;
- No need to introduce complex graph databases at the beginning;
- Facilitates ProblemProjection, Benchmark, and SQL auditing;
- Mature technology and ecosystem.

---

# 10. Event / Observation Store

v1.2 does not recommend introducing an independent Event Sourcing platform as a strong dependency.

First phase can use:

```text
append-only PostgreSQL tables
```

Records:

```text
Observation
WorldEvent
DecisionEvent
TransitionEvent
```

As long as it meets:

```text
immutable
timestamped
causation
correlation
provenance
```

it suffices.

---

# 11. Graph Projection

v1.2 does not recommend Graph Database as Source of Truth; Phase 0–3 does not use dedicated Graph Database as a dependency.

First phase can adopt:

```text
Materialized relational graph view
```

or lightweight graph index.

Later, only introduce a dedicated graph database after the following requirements are validated:

```text
Complex responsibility traversal
evidence graph navigation
agent graph reasoning
causal graph exploration
```

If introduced:

```text
Neo4j / Memgraph / similar
```

it can only serve as a Projection.

---

# 12. Spatial / Routing Infrastructure

SRAF does not build its own complete map and road network engine.

Should through:

```text
TravelProvider Adapter
```

use mature capabilities.

For example:

```text
OSRM
Valhalla
GraphHopper
commercial map APIs
enterprise GIS services
```

World Model only saves:

```text
provider
network_version
routing_profile
calibration_version
```

Do not stuff the entire road network ontology into the Ontology.

---

# 13. Source Adapter Layer

Each external data source connects through standard Adapters.

Unified responsibilities:

```text
read
normalize
map
validate
identity resolution
provenance attach
```

Source Adapter is not allowed to:

```text
Directly generate Territory
Directly determine Root Cause
Directly modify Coverage Policy
```

---

# 14. Source Contract

Recommendations:

```yaml
SourceAdapter:
  source_id:
  source_type:
  schema_version:

  entity_mapping:
  identity_mapping:
  temporal_mapping:

  semantic_status:
  provenance_rule:

  validation_rules:
  conflict_policy:
```

---

# 15. Identity Resolution

SRAF needs:

```text
CanonicalIdentityService
```

Responsible for:

```text
Account
ServiceLocation
Person
Organization
Resource
```

Cross-system mapping.

MVP does not require building a complete enterprise-level MDM.

However, its **business semantics, decision rules, permission matrix, and Benchmark** are not defined in this document,
owned by `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`.
This document only specifies how it is positioned as an engineering module.

At minimum must implement (see 08 for details):

```text
stable canonical ID + identity_domain      → 08 §5
SourceRecord / ExternalIdentifier preservation     → 08 §6–7
Three-state MatchDecision + λ/π thresholds              → 08 §11
MERGE / UNMERGE / SPLIT / SUPERSEDE        → 08 §12–13
append-only IdentityResolutionRecord       → 08 §15
ImpactAnalysis + Trigger blocking              → 08 §14
```

Engineering positioning (corresponding to §70 recommended structure):

```text
src/domain/identity/     CanonicalIdentity / MatchDecision / Resolution
(belongs to World Plane, does not depend on any Solver)
adapters/sources/        provides SourceRecord and ExternalIdentifier
benchmark/identity/      ID01–ID20 case + noise injector + ground truth
```

Storage constraints:

```text
identity_resolution is append-only (PostgreSQL suffices, §9–10 choices remain unchanged)
Do not introduce dedicated graph database; graph is still Projection (§11)
WorldSnapshot must solidify the applied resolution_id set (08 §15.2 TI-2)
```

If the customer already has enterprise-level MDM, `CanonicalIdentityService` degrades to
**Consumer + Conflict Reporter** (reporting goes through `05 GW01`),
SRAF must not rebuild a second set of master data;
But the Identity Gate in `08 §23` must still pass through upstream MDM output,
otherwise it is equivalent to accepting unverified identity truth.

---

# 16. Canonical World API

All upper modules should not directly depend on each Source System.

Unified through:

```text
Canonical World API
```

obtain:

```text
Current State
Historical State
Snapshot
Scenario View
Evidence
```

So that Source System replacement does not pollute the Decision Engine.

---

# 17. Snapshot Service

Recommend independence:

```text
WorldSnapshotService
```

Responsibilities:

```text
freeze decision baseline
resolve valid_time
resolve known_time
track schema/data versions
```

All formal DecisionCase must reference Snapshot.

---

# 18. Scenario Service

Recommendations:

```text
ScenarioService
```

Only do:

```text
Baseline
+
ScenarioAssumption
=
Scenario World View
```

Prohibit copying the entire production database.

Can achieve through:

```text
overlay / delta model
```

implementation.

---

# 19. Derived State Engine

Responsible for unified calculation:

```text
OpportunityCoverage
CoverageAttainment
WorkloadDemand
EffectiveCapacity
CapacityUtilization
TravelBurden
Stability
```

Avoid each Solver repeatedly calculating business metrics.

---

# 20. Derived State Contract

Each Derived Metric should at least declare:

```text
metric_id
definition
inputs
unit
calculation_version
valid_scope
confidence_rule
```

For example:

```text
CapacityUtilization
```

Cannot have three different formulas appearing in different modules.

---

# 21. Metric Registry

Recommend establishing:

```text
MetricRegistry
```

Unified management:

```text
OpportunityCoverage
Workload
Capacity
Travel
ChangeCost
ServiceLevel
Stability
```

This is important for Benchmark and Production consistency.

---

# 22. Allocation Intelligence Service

Recommend logically splitting into five components:

```text
HealthEvaluator
GapDetector
DiagnosticEngine
MaterialityEvaluator
ProblemRouter
```

But v1.2 can implement in one service/module.

Logical separation is sufficient.

---

# 23. HealthEvaluator

Input:

```text
WorldSnapshot
DerivedAllocationState
```

Output:

```text
HealthProfile
```

Not output:

```text
Decision
```

---

# 24. GapDetector

Input:

```text
HealthProfile
PolicyTarget
HistoricalBaseline
PeerBenchmark
```

Output:

```text
GapSet
```

Reference must be explicit.

---

# 25. DiagnosticEngine

MVP adopts:

```text
DiagnosticTest Library
+
Rule / Statistical Comparison
+
Counterfactual Calls
```

instead of LLM end-to-end.

Output:

```text
DiagnosticHypothesis[]
EvidenceFor
EvidenceAgainst
Confidence
```

---

# 26. MaterialityEvaluator

Input:

```text
Gap
BusinessImpact
Persistence
Confidence
ChangeCostEstimate
```

Output:

```text
Monitor
Review
Actionable
Critical
```

---

# 27. ProblemRouter

Input:

```text
DiagnosticHypothesis
Materiality
Policy
```

Output:

```text
PrimaryDecisionProblem
AlternativeDecisionProblems
NoAction / Monitor / Repair
```

ProblemRouter does not select Solver.

---

# 27A. Resource Deployment Architecture Contract

Reference implementation must maintain:

```text
ResourceArchetype
      ↓
ResourceRequirement
      ↓
ResourceDeployment
      ↓
DeploymentAssignment
      ↓
SalesResource
      ↓ realized by
Person / Team / Partner / Agent
```

`DP02 Resource Location` operates Deployment; `DP04 Personnel Matching` operates DeploymentAssignment.

Prohibit directly treating `Person` as a deployment node within the Location Engine.

---

# 28. Decision Case Service

Recommend unified management:

```text
DecisionCase
BusinessObjective
Requirement
Baseline
Candidate
DeltaEvaluation
Review
Approval
ValidationPlan
```

This is the Agent's primary structured interface.

---

# 29. Agent Runtime Positioning

Agent does not belong to World Plane, nor to Solver Plane.

It is located at:

# Decision Interaction Layer

Logically:

```text
User / Manager
      ↕
Sales Allocation Decision Agent
      ↕
Decision Case Service
      ↕
Allocation Intelligence / Orchestrator / Tools
```

---

# 30. Agent's Main Capabilities

Agent can:

```text
Explain Allocation Signal
Query Evidence
Propose Diagnostic Test
Create Scenario
Invoke allowed Workflow
Compare Candidate
Explain Trade-off
Collect Human Evidence
Assist forming Review
Generate Transition Narrative
```

---

# 31. Things Agent is prohibited from doing directly

```text
Write Canonical World State
Create Hard Constraint without source
Silently change Objective
Write Hypothesis as Fact
Directly approve High-risk Decision
Bypass Orchestrator to invoke Structural Solver
Automatically relax Hard Constraint
```

---

# 32. Agent Tool Contract

Agent can only invoke standard capabilities:

```text
world.query
evidence.query
allocation.health
allocation.diagnose
scenario.create
decision_case.create
workflow.run
candidate.compare
review.submit
```

Actual function names may differ.

Key principle:

> Agent faces Business Contract, not database and Solver internal variables.

---

# 33. Decision Orchestrator

Recommended independent modules:

```text
DecisionOrchestrator
```

Responsible for:

```text
WorkflowTemplate
WorkflowInstance
StepState
ArtifactDependency
Coupling
HumanCheckpoint
FailureRouting
```

v1.2 does not require self-developed general BPMN engine; Phase 0 can first use a persistent state machine to prove Decision Semantics.

---

# 34. Workflow Engine Reuse Principle

If a mature Workflow framework can meet:

```text
state persistence
retry semantics
human wait state
versioning
artifact reference
```

Should be preferred.

Candidate directions may include:

```text
Temporal
Dagster
Prefect
Camunda
existing enterprise workflow infrastructure
```

Selection should be determined by the implementation environment.

SRAF itself owns:

```text
Workflow Semantics
Decision Step Types
Failure Semantics
```

rather than must own the Workflow Runtime.

---

# 35. Decision Compiler

This is one of SRAF's core owned capabilities.

Recommended logical split:

```text
DecisionCompiler
├── ProjectionBuilder
├── RequirementCompiler
├── DecompositionPlanner
├── MathematicalModelBuilder
└── SolutionInterpreter
```

---

# 36. ProjectionBuilder

Convert:

```text
WorldSnapshot
DecisionCase
ProblemContract
```

to:

```text
ProblemProjection
```

It is responsible for:

```text
scope
aggregation
unit conversion
quality gate
temporal consistency
```

---

# 37. RequirementCompiler

Convert:

```text
Invariant
HardConstraint
Guardrail
Preference
```

Map to Solver-understood constraint/objective structure.

Must preserve:

```text
business requirement ID
→ mathematical constraint ID
```

Mapping.

So that Solver Conflict can explain back to business language.

---

# 38. Constraint Provenance

If Solver reports:

```text
constraint C882 conflicts
```

The system must be able to map to:

```text
Policy P17
"Distributor boundary cannot be crossed"
```

instead of just giving engineers a math constraint ID.

---

# 39. DecompositionPlanner

Responsible for large-scale / Composite Problem solving strategies.

It chooses:

```text
Sequential
Iterative
Joint
Aggregation
Multi-stage
```

instead of a specific Solver.

---

# 40. MathematicalModelBuilder

Responsible for:

```text
business variables
→
x / y / z
```

and generate Solver-specific Model.

This layer is the last SRAF-owned semantic boundary before Solver Adapter.

---

# 41. SolutionInterpreter

Responsible for:

```text
x_17_92 = 1
```

Restore to:

```text
Responsibility R92
assigned to Deployment D17
```

Then form:

```text
CandidateDecision
```

SolverSolution itself is never directly exposed as a business result.

---

# 42. Solver Registry

Recommend:

```text
SolverRegistry
```

Maintain all available Solver capabilities.

Each Adapter declares:

```text
supported_problem_types
scale
constraint_support
multi_objective
warm_start
optimality
runtime
license
```

---

# 43. v1.2 priority reuse Solver / Library

Do not bind to a specific implementation, but recommend evaluating first:

```text
OR-Tools CP-SAT
SCIP
HiGHS
Gurobi (if the customer environment permits)
Pyomo / OR-Tools modeling
NetworkX / graph tooling
H3
mature routing engines
```

Should not develop a generic Solver in-house in the first phase.

---

# 44. Solver Adapter

Unified interface concept:

```yaml
SolverAdapter:
  build():
  solve():
  status():
  incumbent():
  optimality_claim():
  diagnostics():
  provenance():
```

---

# 45. Solver Status Standardization

All Adapters must map uniformly to:

```text
OPTIMAL
FEASIBLE
FEASIBLE_WITH_GAP
TIME_LIMIT
MEMORY_LIMIT
MODEL_ERROR
NUMERICAL_FAILURE
UNKNOWN
```

and with:

```text
BusinessInfeasibility
```

completely separate.

---

# 46. Feasibility Oracle Registry

Maintain separately from SolverRegistry:

```text
OracleRegistry
```

Typical:

```text
CapacityFeasibilityOracle
PersonnelFeasibilityOracle
SchedulingFeasibilityOracle
RoutingFeasibilityOracle
PolicyFeasibilityOracle
```

---

# 47. An Engine can serve as both Solver and Oracle

For example:

```text
visit-scheduling-optimizer
```

Can register simultaneously:

```text
DP06 VisitScheduling Engine
```

and:

```text
SchedulingFeasibilityOracle
```

but the two invocation modes must be different:

```text
run_purpose
output_contract
runtime_budget
```

---

# 48. Formal integration point of visit-scheduling-optimizer

Recommend:

```text
Reference Engine ID:
visit-scheduling-optimizer

Primary Problem:
DP06 VisitScheduling

Oracle:
SchedulingFeasibilityOracle

Optional Diagnostic Use:
SchedulingFeasibilityTest
```

---

# 49. visit-scheduling-optimizer no longer owns upstream semantics

In the future, the following logic should be gradually moved out or consolidated:

```text
whether a customer is worth a visit
Coverage frequency policy
Territory ownership
Headcount decision
Resource location decision
```

These are provided by SRAF upstream Contract.

---

# 50. Visit Scheduling Standard Input

```text
VisitSchedulingProblemProjection

resources
responsibilities
coverage_commitments
calendar
capacity
service_time
spacing_policy
visit_windows
travel_estimate
fixed_day_policy
```

---

# 51. Visit Scheduling Standard Output

```text
CandidateSchedule
FeasibilityStatus
UnfulfilledCommitments
ConstraintConflictEvidence
CapacityUtilization
ScheduleStability
TravelEstimate
OptimalityStatus
RunProvenance
```

---

# 52. Candidate Evaluation Service

All Candidates regardless of which Solver they come from enter the unified:

```text
CandidateEvaluationService
```

Responsible for:

```text
Baseline Delta
Shared Metrics
Guardrail
ChangeCost
Uncertainty
Downstream Feasibility
```

---

# 53. Shared Evaluation Space

unified:

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

Cannot directly compare objective_value of different Solvers.

---

# 54. Change Cost Service

Recommend independent logic:

```text
ChangeCostEvaluator
```

In the first phase, rule-based calculation can be used:

```text
accounts moved
revenue moved
resources relocated
relationship risk
handover volume
```

Later expand to model-based estimation.

---

# 55. Human Governance Service

At least manage:

```text
HumanReview
HumanOverride
ExceptionApproval
FinalApproval
```

There is no need to build a complex organizational approval platform from the start.

Can be through:

```text
enterprise approval/workflow adapter
```

Integrate with existing systems.

---

# 56. Human Override Versioning

Must:

```text
Candidate V1
→ Override
→ Candidate V1.1
→ Re-evaluation
```

Cannot overwrite V1.

---

# 57. Transition Service

Responsible for turning:

```text
ApprovedDecision
```

into:

```text
TransitionPlan
```

Then generate per stage:

```text
WorldEvent
```

---

# 58. Transition is not data synchronization

Structural adjustment may require:

```text
handover
effective date
temporary overlap
training
communication
freeze window
```

Therefore Transition cannot be simplified to:

```text
update territory table
```

---

# 59. Execution Connector

SRAF itself is not SFA.

Actual execution usually occurs at:

```text
CRM
SFA
HR
ERP
route app
mobile sales app
```

SRAF via:

```text
ExecutionConnector
```

Push approved structure/plan.

---

# 60. Execution write principle

Only:

```text
Approved
+
TransitionReady
```

Only a status can produce external writes.

Solver / Candidate / Scenario must never write.

---

# 61. Observation Connector

After execution, flow back from business system:

```text
visit completion
travel
sales
account status
resource availability
ownership changes
```

Form:

```text
Observation
```

After validation, enter World State.

---

# 62. Validation Service

Responsible for execution:

```text
DecisionValidationPlan
```

Support:

```text
BeforeAfter
MatchedControl
DifferenceInDifferences
StaggeredRollout
A/B
```

Specific analysis modules can reuse mature statistical libraries.

---

# 63. Benchmark Service

Production and Benchmark use the same:

```text
WorldSnapshot
DecisionProblemContract
SolverAdapter
Evaluation
```

Benchmark Service only responsible for:

```text
case management
dataset version
run matrix
metrics
regression
reporting
```

---

# 64. Benchmark should not build a separate set of research code

Forbidden:

```text
notebook implementation
≠
production implementation
```

Core Contract and Engine must reuse production implementation.

Can add on the Benchmark side:

```text
synthetic generator
case injector
ground truth
evaluation harness
```

---

# 65. Audit / Provenance

Recommend unifying:

```text
RunProvenance
```

Association:

```text
WorldSnapshot
DecisionCase
Workflow
ProblemProjection
CompilerVersion
SolverRun
OracleRun
Candidate
HumanReview
Decision
Transition
Outcome
```

---

# 66. Observability

Besides technical logs, Decision Observability is required.

At least be able to answer:

```text
Why was this DecisionCase created?
Why was it routed to DP03?
Why was this Solver selected?
Why is Candidate B ranked before A?
Who modified the Candidate?
Which data versions were used?
What is the final effect?
```

---

# 67. Technical logs and business evidence are separated

For example:

```text
CPU usage
stack trace
HTTP error
```

Belongs to Technical Observability.

While:

```text
CoverageGap evidence
Policy conflict
Candidate trade-off
Human override reason
```

Belongs to Decision Evidence.

The two cannot be mixed as one log.

---

# 68. API Boundary

SRAF v1.2 recommends using clear domain APIs / service interfaces.

It is not required to fully microservice in the first phase.

Can first:

```text
modular monolith
```

But module boundaries must be clear.

---

# 69. Not recommended to directly microservice in v1.2

Reasons:

- World / Decision Contract is still evolving rapidly;
- Prematurely splitting microservices will solidify erroneous boundaries;
- Increases operational complexity;
- Benchmark and local development become more difficult.

Recommend:

# Modular Monolith First

After maturity, split according to load and organizational boundaries.

---

# 70. Recommended Repo structure

The logical modules in 07 are still retained, but **MVP is not mechanically split into a dozen services according to logical modules**.

v1.2 recommends first converging to six packages:

```text
sales-resource-allocation-framework/
│
├── docs/
│
├── src/
│   ├── domain/
│   │   ├── world/
│   │   ├── evidence/
│   │   ├── temporal/
│   │   └── metrics/
│   │
│   ├── decision/
│   │   ├── ontology/
│   │   ├── cases/
│   │   ├── requirements/
│   │   └── candidates/
│   │
│   ├── intelligence/
│   │   ├── health/
│   │   ├── gaps/
│   │   ├── diagnosis/
│   │   └── router/
│   │
│   ├── orchestration/
│   │
│   ├── computation/
│   │   ├── projection/
│   │   ├── compiler/
│   │   ├── solvers/
│   │   └── oracles/
│   │
│   └── evaluation/
│       ├── delta/
│       ├── validation/
│       └── benchmark/
│
├── adapters/
│   ├── visit_scheduling/
│   ├── routing/
│   └── sources/
│
├── schemas/
├── benchmark/
└── tests/
```

Principles:

> **Logical module boundary ≠ deployment service boundary。**

The first phase still adopts Modular Monolith First.


---

# 71. Whether to share with the existing visit-scheduling-optimizer

v1.2 recommends:

> **Do not merge immediately.**

SRAF maintains as a Framework:

```text
VisitSchedulingAdapter
```

Call existing repositories through standard Contract.

Reasons:

- Validate boundaries first;
- Avoid rewriting stable capabilities;
- Keep solver evolving independently;
- Verify "Decision Problem ≠ Solver".

Only consider monorepo if subsequent engineering benefits exist.

---

# 72. Principles for existing project transformation

For `visit-scheduling-optimizer`, large-scale refactoring is not recommended in the first phase.

Prioritize:

```text
Adapter
Input Contract
Output Contract
Failure Semantics
Run Provenance
Feasibility Mode
```

These five items.

First make it a SRAF-compliant Decision Engine.

---

# 73. Strategy for Territory Engine

SRAF v1.2 should not self-develop a large Territory Optimizer immediately in the first phase.

Suggested order:

```text
1. Simple baseline heuristic
2. Existing open-source / OR formulations
3. Exact small-instance reference solver
4. Scale heuristic
5. Routing-in-the-loop evaluation
```

First prove the Decision Framework, then pursue algorithmic leadership.

---

# 74. Territory Engine Baseline

The first version can even use:

```text
balanced clustering
graph partitioning
local swap heuristic
```

as a Candidate Generator.

As long as:

```text
Contract
Baseline
ChangeCost
Travel
Opportunity
Evaluation
```

Complete.

---

# 75. Strategy for DP01 Sizing Engine

In the first phase, prioritize outputting:

```text
Resource-Coverage Frontier
```

rather than the sole Headcount.

Can initially use:

```text
workload/capacity model
+
geographic travel approximation
+
scenario enumeration
```

Later enhance the location-allocation joint model.

---

# 76. Strategy for DP02 Location Engine

Prioritize reusing:

```text
facility location
p-median
location-allocation
```

Mature OR modeling approaches.

SRAF itself adds:

```text
personnel feasibility
change cost
responsibility semantics
```

---

# 77. Strategy for DP04 Personnel Matching

Can start from:

```text
assignment / matching
```

model.

Prioritize ensuring:

```text
capability
eligibility
location
relationship
fairness
```

Semantic correctness.

No need to do complex ML first.

---

# 78. Strategy for DP05 Coverage Allocation

May need:

```text
response curves
priority rules
resource substitution
```

MVP can start from:

```text
minimum/preferred/maximum
+
opportunity priority
+
capacity envelope
```

Start.

---

# 79. Strategy for DP07 Routing Engine

SRAF does not self-develop routing core.

Prioritize reusing:

```text
OR-Tools routing
OSRM/Valhalla/GraphHopper network
```

Use it as:

```text
Decision Engine
+
Oracle
```

---

# 80. Dependency direction

Engineering must keep:

```text
World
  ↑
Decision
  ↑
Orchestration
  ↑
Compiler
  ↑
Solver Adapter
```

More precisely:

> Lower-layer computing modules depend on Contracts defined by upper layers, but must not reversely have business semantics.

---

# 81. Prohibit reverse dependencies

For example:

```text
world.Account
```

Must not have:

```text
cp_sat_variable_index
```

Similarly:

```text
DecisionCase
```

Should not know:

```text
GurobiModel
```

---

# 82. Contract-first Development

For each new Engine, the order is fixed:

```text
1. Define Decision Problem Contract
2. Define Problem Projection
3. Define Failure Semantics
4. Define Evaluation
5. Define Validation
6. Implement Adapter / Solver
```

Prohibit:

```text
Writing algorithm first
→ then think about what it computes
```

---

# 83. Schema-first / Type-safe

It is recommended that core object definitions use a unified schema.

For example, can adopt:

```text
Pydantic / JSON Schema / protobuf
```

Depends on the technology stack.

The key point is:

```text
WorldSnapshot
DecisionCase
ProblemProjection
CandidateDecision
OracleResult
```

Must be an explicit Contract, not an arbitrary dict.

---

# 84. Versioning strategy

All core Contracts:

```text
World Schema
Decision Ontology
Problem Contract
Workflow Template
Solver Adapter
Metric Definition
Benchmark Case
```

Must be versioned.

---

# 85. Compatibility Policy

Recommendation:

```text
patch:
implementation fix, semantic unchanged

minor:
backward-compatible field / rule extension

major:
semantic meaning changed
```

For example:

```text
CoverageNeed.frequency
```

Semantic changes must increment the major version.

---

# 86. Migration

When upgrading World Schema, must provide:

```text
migration
backfill
version compatibility
```

Historical Snapshots should not be silently reinterpreted.

---

# 87. Historical Reproducibility

When v2.0 appears, still should be able to answer:

> Why did v1.2 make this Decision?

Therefore historical Run references:

```text
schema_version
contract_version
compiler_version
solver_version
```

Must be retained.

---

# 88. Security / Authorization

SRAF Decision Risks differ, permissions differ.

For example:

```text
View health
Run scenario
Generate candidate
Submit override
Approve territory
Approve downsizing
Execute transition
```

Should be authorized separately.

---

# 89. Agent Permission

Agent permissions are controlled by Tool Policy.

Agent should not inherit all database permissions of the user.

For example:

```text
Agent may:
read world
run scenario

Agent may not:
approve downsizing
write HR
activate territory
```

---

# 90. Data Privacy

Separating Sales Resource and Person still has engineering value:

> Solver often only needs Resource Capacity / Capability, not all personal information of employees.

ProblemProjection should follow the minimum data principle.

---

# 91. Personal Data Minimization

For example, Territory Solver may only need:

```text
deployment location
capability
relocation feasibility
```

Does not need:

```text
full HR profile
phone
personal address details
```

---

# 92. Performance Architecture

v1.2 prioritizes:

```text
Snapshot
Projection cache
Travel matrix cache
Derived state cache
Scenario artifact reuse
```

rather than premature distributed computing.

---

# 93. Projection Cache

Cache Key must include at least:

```text
snapshot_id
scenario_id
problem_contract_version
projection_version
scope
```

Avoid using stale Projection.

---

# 94. Artifact Invalidation

When dependent objects change:

```text
CoverageCommitment changed
```

Automatically invalidate:

```text
ScheduleCandidate
RouteCandidate
```

Mark:

```text
STALE
```

Orchestrator must not continue approving stale artifact.

---

# 95. Travel Matrix Cache

Should bind:

```text
network_version
routing_profile
time context
location_version
```

Otherwise:

> Location changes but still uses old travel matrix.

---

# 96. Deployment mode

First phase recommendation:

```text
single service
or modular monolith
+
external solver workers
```

Complex Solver can use independent Worker.

No requirement for full modules to be independently deployed.

---

# 97. Long-running Solver

Structural Solver can:

```text
async job
```

Orchestrator keeps:

```text
run_id
status
artifact
```

Agent does not need to maintain long connections.

---

# 98. Interactive What-if

Interactive Mode can choose:

```text
fast heuristic
cached projection
reduced fidelity
```

Output must be marked:

```text
evaluation_fidelity
optimality_claim
```

Cannot wrap a 5-second heuristic result as the final nationwide plan.

---

# 99. Production Structural Run

Can use:

```text
higher fidelity
longer runtime
full constraint validation
routing simulation
human review
```

---

# 100. Benchmark Environment

Benchmark should support:

```text
fixed seed
fixed snapshot
fixed dependency version
isolated run
```

Ensure reproducibility.

---

# 101. CI Architecture Gates

It is recommended to convert key Architecture Gates in the preceding document into automated checks.

For example:

```text
Schema check
Dependency check
Contract check
Provenance check
Snapshot isolation
Scenario isolation
Candidate isolation
```

---

# 102. Static Dependency Gate

Can explicitly prohibit:

```text
world/
```

Dependencies:

```text
solver_registry/
```

Or:

```text
decision/
```

import a specific Solver SDK.

This can be realized through module dependency testing.

---

# 103. Contract Compliance Test

Each Engine Adapter must run:

```text
standard input test
standard output test
status mapping test
failure mapping test
provenance test
```

to register SolverRegistry.

---

# 104. Reference Vertical Slice v1

The first truly implemented Vertical Slice of SRAF should be fixed as:

```text
Source Data
    ↓
World Model
    ↓
CoverageCommitment
    ↓
VisitSchedulingProblem
    ↓
ProblemProjection
    ↓
visit-scheduling-optimizer
    ↓
CandidateSchedule
    ↓
Delta / Feasibility
```

---

# 105. Goals of Vertical Slice v1

Not to improve scheduling algorithm performance.

But to prove:

```text
World Contract
→ Decision Contract
→ Existing Solver Adapter
→ Candidate
→ Evaluation
```

End

---

# 106. Vertical Slice v2

Add:

```text
Allocation Health
Gap
Diagnosis
Problem Router
```

Goal:

> When scheduling fails, the system can determine whether to continue DP06 or escalate to Coverage / Territory / Sizing.

---

# 107. Vertical Slice v3

Add:

```text
Coverage ↔ Scheduling
```

Iterative Coupling。

Proof:

```text
Oracle feedback
artifact invalidation
stopping rule
```

---

# 108. Vertical Slice v4

Add simplified version:

```text
Territory Rebalancing
```

Only need:

```text
Baseline
Maintain
Simple Rebalance
Travel
Workload
Opportunity
ChangeCost
```

Do not pursue advanced algorithms for now.

---

# 109. Vertical Slice v5

Add:

```text
Resource Location / Sizing
```

Start forming a complete:

```text
Greenfield / Expansion
```

Composite Workflow。

---

# 110. Implementation Phase Recommendations

## Phase 0 — Contracts & Harness

Goal:

```text
schemas
snapshot
decision case
problem projection
benchmark harness
```

First make all core objects serializable and testable.

---

## Phase 1 — Scheduling Reference Integration

Goal:

```text
DP06 adapter
failure semantics
candidate interpreter
```

Reuse existing engine.

---

## Phase 2 — Allocation Intelligence MVP

Goal:

```text
5 diagnostic cases
problem router
false expansion benchmark
```

---

## Phase 3 — Structural Decision MVP

Goal:

```text
DP03 baseline
maintain candidate
change cost
human override
```

---

## Phase 4 — Composite Decision

Goal:

```text
Coverage ↔ Scheduling
Expansion
Greenfield
```

Gradually increase Coupling.

---

## Phase 5 — Production Validation

Goal:

```text
shadow
pilot
decision validation
```

---

## 110A. v1 Engineering Envelope (Phase 0–3 Scale and SLA)

This is not a system upper limit statement, but an engineering contract for `DecompositionPlanner / SolverRegistry /
Projection Cache / Benchmark` engineering contract:

> Under what scale tier, what compute strategy and response time is expected.

| Tier | Responsibility Units | Resources | Target Response | Typical Scenario |
|---|---|---|---|---|
| **S — Interactive** | ≤ 5k | ≤ 50 | seconds | What-if, local Rebalance, DP06/DP07 |
| **M — City/Regional Planning** | 5k–50k | 50–300 | minutes | DP01/DP02/DP03 planning batch |
| **L — Structural Batch** | 50k–200k | 300–1,000 | tens of minutes–hours | CP01/CP02 structural batch processing |

Minimum committed tier for each Phase:

```text
Phase 0  Contracts        S (schema/snapshot correctness first, no performance requirement)
Phase 1  DP06 Reference   S must meet; M best effort (report time-to-first-feasible)
Phase 2  Intelligence     S–M (Health/Gap/Router full derivation, minutes)
Phase 3  Structural MVP   M must meet; L allowed Iterative/Multi-stage decomposition
```

Compute strategy switches with tier (must explicitly declare `evaluation_fidelity`):

```text
S   exact Solver or high-iteration heuristic; full L2 Network Travel
M   CP-SAT/MILP + warm start; L1 coarse filter + L2 re-evaluation funnel
L   Macro aggregation → decomposition solving → Micro backfill; prohibit naive joint;
Travel uses precomputed matrix cache (bound to network_version)
```

Engineering implications:

1. Benchmark scale test (06 §55) reported scale must cover the corresponding Phase tier upper bound,
Must not report performance only on toy instances.
2. Projection Cache / Travel Matrix Cache memory and invalidation budget designed for L tier capacity.
3. Exceeding L tier is not considered SRAF failure, but triggers
`Aggregation / Sampling Strategy` review (new ProblemProjection semantics,
follow §84 version strategy); before that, must not silently degrade accuracy.

---
# 111. Work not recommended for the first phase

```text
Self-developed general-purpose Workflow Engine
Self-developed graph database
Self-developed routing engine
Self-developed MILP Solver
Complex RDF/OWL reasoner
End-to-end LLM decision-making
Nationwide real-time Territory automatic rebalancing
Complex multi-agent society
Full MLOps platform
```

None of these are SRAF v1.2 core.

---

# 112. SRAF's own core assets

Must be owned internally:

```text
Sales World Ontology
Decision Ontology
Allocation Intelligence
Decision Problem Contracts
Problem Projection Semantics
Decision Compiler Contract
Evaluation Model
ChangeCost Semantics
Decision Governance
Benchmark Cases
```

These are the true IP of the Framework.

---

# 113. Prioritize reuse of assets

Should first integrate:

```text
Database
GIS
Routing
Solver
Workflow Runtime
Experiment Statistics
Visualization
LLM Runtime
```

Mature capabilities.

---

# 114. Agentic architecture principles

Agentic does not mean:

> All modules are agentified.

Where it truly is Agentic:

```text
Understanding DecisionCase
Organizing Evidence
Proposing Hypothesis
Choosing allowed Tool
Creating Scenario
Comparing Candidate
Collaborating with Human
```

Whereas:

```text
constraint validation
capacity calculation
routing
MILP solve
snapshot semantics
```

Should remain deterministic/governed.

---

# 115. Deterministic Core + Agentic Shell

SRAF recommends:

```text
              AGENTIC INTERACTION
                      │
                      ▼
┌───────────────────────────────────────┐
│        GOVERNED DECISION APIs         │
├───────────────────────────────────────┤
│ Allocation Intelligence               │
│ Decision Orchestrator                 │
│ Scenario / Candidate / Evidence       │
├───────────────────────────────────────┤
│        DETERMINISTIC CORE             │
│ World Model / Contract / Solver       │
│ Evaluation / Temporal / Policy        │
└───────────────────────────────────────┘
```

This is the v1.2 recommended architecture.

---

# 116. Why not "Agent directly calls database + Solver"

Because that would lead to:

```text
business semantics
hidden in prompt

constraint meaning
hidden in code

world truth
mixed with model estimate

workflow state
stored in conversation

decision evidence
unreproducible
```

This is contrary to SRAF goals.

---

# 117. API / UI is not v1.2 core

v1.2 first delivers Framework / Agent-callable APIs.

Management UI, map UI can be built later.

But output objects should natively support:

```text
map projection
candidate comparison
decision explanation
```

---

# 118. Territory Visualization

Map is only:

```text
TerritoryProjection
```

a visual representation.

UI cannot directly modify Canonical Territory by dragging Polygon.

Drag result should generate:

```text
HumanOverride
```

or:

```text
CandidateChange
```

Then re-evaluate.

---

# 119. Reference Deployment Example

Minimal production architecture can be:

```text
PostgreSQL/PostGIS
        │
SRAF Application
├── World
├── Allocation Intelligence
├── Decision
├── Orchestrator
├── Compiler
└── Evaluation
        │
        ├── visit-scheduling-optimizer
        ├── routing provider
        └── OR solver worker
        │
Agent / API
        │
Human Review
```

No need for massive infrastructure.

---

# 120. Architecture evolution conditions

Only split when clear evidence appears:

### Independent Graph DB

When:

```text
relationship traversal
```

becomes the main performance bottleneck.

### Independent Event Platform

When:

```text
event volume / integration
```

exceeds relational DB capabilities.

### Distributed Solver Platform

When:

```text
concurrent structural optimization
```

becomes a bottleneck.

### Independent Workflow Platform

When:

```text
long-running workflows
human tasks
enterprise integration
```

proves existing capabilities insufficient.

---

# 121. Architecture Decision Record

All important technology selections are recommended to use:

```text
ADR
```

For example:

```text
ADR-001 Canonical State uses PostgreSQL
ADR-002 Graph is projection, not source of truth
ADR-003 Existing scheduling engine integrated via adapter
ADR-004 Modular monolith before microservices
```

Avoid future teams not understanding "why".

---

# 122. Critical Architecture Gates

If the following designs appear, they should be rejected in principle:

```text
Solver reads Source System directly

Agent writes Canonical World directly

Territory = Polygon table

Account.owner_id as the sole responsibility model

Opportunity score without provenance

DecisionCase without Snapshot

Scenario copies and modifies production state

Decision Engine computes a separate set of metrics

Solver-specific variable writes into World schema

Problem Router directly binds Solver

Workflow State resides in Agent dialogue

HumanOverride overrides original Candidate

Candidate directly pushes to SFA

Approval without TransitionPlan

Benchmark uses a different business Schema

Graph becomes the sole Source of Truth

New infrastructure added without capability gap verification
```

---

# 123. Definition of Done

`07_REFERENCE_ARCHITECTURE.md` first-phase rollout cannot be considered complete with:

> "Service framework is ready"

as completion.

At minimum must prove:

```text
1. World Snapshot can be created
2. Scenario can fork without pollution
3. DecisionCase can reference Baseline
4. ProblemProjection can be generated
5. Existing Scheduling Engine can be called via Adapter
6. Solver result can become CandidateDecision
7. Candidate can be evaluated against Baseline
8. Failure semantics can route correctly
9. HumanOverride creates versioned candidate
10. Approved Decision requires Transition
11. Observation can flow back to Validation
12. Benchmark reuses the same contracts
```

---

# 124. v1.2 Reference Architecture final convergence

SRAF should not be implemented as:

```text
Territory SaaS
+
Scheduler
+
Agent Chatbot
```

but should be implemented as:

# **Sales Resource Allocation Decision Infrastructure**

Its truly stable core is:

```text
World Semantics
      ↓
Allocation Diagnosis
      ↓
Decision Framing
      ↓
Problem Contracts
      ↓
Computational Tools
      ↓
Candidate Futures
      ↓
Governance
      ↓
Observed Outcome
```

---

# 125. Final relationship with existing capabilities

Existing `visit-scheduling-optimizer`:

```text
is not SRAF
```

but:

```text
SRAF's first Reference Decision Engine
```

Future Territory, Sizing, Location, Coverage, Routing also follow the same principles:

> **Engine is replaceable, Decision Semantics cannot be defined by Engine.**

---

# 126. Minimum conditions for project to enter engineering phase

When the following documents and Vertical Slice are both available, it is recommended to formally enter large-scale implementation:

```text
01 World Model
02 Decision Ontology
03 Problem Contracts
04 Allocation Intelligence
05 Orchestration
06 Benchmark
07 Reference Architecture

+
Scheduling Reference Vertical Slice
+
5-case Diagnostic Benchmark
```

After that, algorithm extensions will have stable upper-layer semantics.

---

# 127. v1.2 main architecture conclusion

SRAF ultimately does not center on a specific algorithm, but on:

# `Decision Case`

as the core work unit of the system.

Complete closed loop:

```text
Observed World
      ↓
Allocation Signal
      ↓
Decision Case
      ↓
Candidate Future Worlds
      ↓
Human-governed Decision
      ↓
Transition
      ↓
Observed Outcome
      ↓
Evidence
      ↓
Next Decision
```

This is the S1.2 Reference Architecture baseline.
