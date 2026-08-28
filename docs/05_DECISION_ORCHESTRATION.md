# SRAF Decision Orchestration Specification v1.2

**Project:** Sales Resource Allocation Framework
**Document:** `05_DECISION_ORCHESTRATION.md`
**Status:** Implementation Baseline v1.2

**Upper-level Specification:**
`00_PROJECT_CHARTER.md`, `01_WORLD_MODEL_SPEC.md`, `02_DECISION_ONTOLOGY.md`, `03_DECISION_PROBLEM_CONTRACTS.md`, `04_ALLOCATION_INTELLIGENCE.md`

---

## 1. Document Objective

Decision Orchestration answers:

> When a DecisionCase is confirmed, in what order and coupling manner are which Decision Problems, Solvers, Oracles, Scenarios, and Human Reviews invoked, ultimately forming a governable Decision.

```text
DecisionCase
      ↓
Scenario Classification
      ↓
Decision Workflow
      ↓
Problem Decomposition
      ↓
Atomic / Composite Problem
      ↓
Coupling Strategy
      ↓
Problem Projection
      ↓
Solver / Oracle Execution
      ↓
Candidate Alternatives
      ↓
Cross-Problem Evaluation
      ↓
Human Review
      ↓
Decision
      ↓
Transition
```

---

## 1A. Normative Ownership

This file uniquely has:

```text
Scenario
ScenarioAssumption lifecycle
WorkflowTemplate
WorkflowInstance
WorkflowStep
CouplingMode execution semantics
GovernanceWorkflow GW01-GW03 semantics
ArtifactDependency
OrchestrationPolicy
DecisionRisk
AutomationLevel
OrchestrationRun
```

`ScenarioAssumption`'s Semantic Status is defined by 01; its workflow lifecycle is defined by 05.

---

## 2. Why Orchestrator is Needed

Without an Orchestrator, Sizing/Location/Territory/Scheduling/Routing will degrade into a set of isolated APIs; Composite Problems and process logic are scattered in the Controller, resulting in dependencies, iterations, Oracles, Human Checkpoints, versioning, and Fallback unable to be governed uniformly.

Decision Workflow is a first-level object of the Framework.

---

## 3. Three Concept Separation

```text
Business Scenario
Decision Workflow
Decision Problem
```

Scenario answers the business context; Workflow answers which steps need to be orchestrated; Decision Problem answers what business variables are allowed to change at a given step.

The same Expansion Scenario may follow different Workflows depending on whether the Headcount has been fixed by headquarters.

---

## 4. WorkflowTemplate / WorkflowInstance

WorkflowTemplate: 

```text
workflow_template_id
scenario_type
version
entry_conditions
required_steps
optional_steps
dependencies
allowed_coupling_modes
human_checkpoints
exit_conditions
failure_routes
```

WorkflowInstance: 

```text
workflow_instance_id
decision_case_id
template_version
active_steps
completed_steps
skipped_steps
current_state
created_at
updated_at
```

---

## 5. WorkflowStep

Standard types:

```text
DiagnosisStep
ProblemStep
ScenarioStep
OracleStep
EvaluationStep
HumanReviewStep
ApprovalStep
TransitionPlanningStep
```

Step exchanges via standard Artifacts, not via implicit temporary table coupling.

Artifacts include:

```text
WorldSnapshot
AllocationDecisionSignal
DecisionCase
ProblemProjection
CandidateDecision
DeltaEvaluation
OracleResult
HumanReview
```

---

## 6. Dependency

Step should express:

```text
requires
produces
blocks
invalidates
```

After an upstream Artifact changes, downstream Candidate can be marked STALE.

---

## 7. Composite Problem / DecompositionPlanner

Composite Problems: 

```text
CP01 DeploymentDesign
CP02 CapacityExpansion
CP03 StructuralRebalancing
CP04 CoverageExecutionDesign
```

DecompositionPlanner input:

```text
CompositeProblem
WorldSnapshot
ProblemScale
RuntimeBudget
DataQuality
SolverCapabilities
DecisionHorizon
OptimalityRequirement
```

Output SolutionStrategy:

```text
problem_ids
coupling_mode
execution_order
iteration_plan
oracle_plan
solver_plan
aggregation_level
evaluation_fidelity
stopping_rule
```

---

## 8. Coupling Mode

```text
Independent
Sequential
Iterative
Joint
```

Independent can be parallelized.

Sequential such as Coverage → Scheduling.

Iterative such as Territory ↔ Travel, Coverage ↔ SchedulingFeasibility.

Joint such as Greenfield Sizing + Location + Territory, but after solving it must Semantic Decomposition back to ResourceRequirement, ResourceDeployment, ResponsibilityAssignment.

Joint is not the default mode; scale, runtime, data quality, explainability, and optimality requirement must be considered.

---

## 9. Multi-stage Decomposition / Multi-fidelity

Large-scale problems can:

```text
Demand Aggregation
→ Macro Resource Design
→ Macro Territory
→ Micro Assignment
→ Routing Evaluation
→ Local Improvement
```

All aggregations belong to ProblemProjection and do not modify World.

Evaluation: 

```text
L1 Fast Proxy
L2 Network Evaluation
L3 Full Simulation
```

Candidate Funnel: 

```text
Generate
→ L1 Screen
→ Top N
→ L2
→ Top K
→ L3
→ Review
```

---

## 10. Feasibility Oracle Orchestration

Oracle returns uniformly:

```text
oracle_type
candidate_id
status
violations
risk
explanation
confidence
runtime
recommendation
```

Status: 

```text
FEASIBLE
FEASIBLE_WITH_RISK
INFEASIBLE
UNKNOWN
```

Oracle must not automatically modify Candidate, only provide Feedback.

---

## 11. Feedback Contract / Iteration Stop

Iterative Workflow must declare:

```text
feedback_source
feedback_target
feedback_variables
```

Stopping condition:

```text
FeasibleSolutionFound
NoMaterialImprovement
ObjectiveImprovementBelowThreshold
BusinessDeltaBelowThreshold
MaxIterations
RuntimeBudgetReached
HumanStop
```

Infinite loops or pursuing only mathematical objectives are not allowed.

---

## 12. SolverSelector

DecompositionPlanner decides how to decompose, and SolverSelector decides which concrete Solver to use at a given step.

Input:

```text
ProblemContract
ProblemScale
RuntimeBudget
OptimalityRequirement
UncertaintyMode
WarmStartAvailability
InteractionMode
SolverRegistry
```

InteractionMode: 

```text
BatchPlanning
InteractiveWhatIf
ProductionOptimization
BenchmarkResearch
FeasibilityCheck
```

Supports Primary Solver, Fallback Solver, Fallback Heuristic; Fallback does not imply relaxing Hard Constraints.

---

## 13. Human Checkpoints

```text
H1 Problem Framing Review
H2 Candidate Review
H3 Exception / Override Review
H4 Final Approval
```

Human Review can submit HumanEvidence; Override requires versioning and re-evaluation.

---

## 14. Automation Level

```text
A0 Advisory
A1 Human-approved execution
A2 Auto-execute within guardrails
A3 Autonomous
```

Structural Decision defaults to A0/A1; low-risk routing/scheduling can reach A2 under strict Policy.

WorkflowPolicy declares allowed_automation_level, required_human_checkpoints, approval_authority.

---

## 14A. Governance Workflows (GW01–GW03) 

`WorldModelRepair`, `ModelGovernance`, `PolicyReview` are produced by Problem Router,
but **are not** DP01–DP07, nor registered in SolverRegistry.

This file has its lowest Workflow semantics (reuse §4 WorkflowTemplate / §5 WorkflowStep /
§22 Workflow Status / §14 Automation Level), without introducing a new independent engine.

Unified constraints:

```text
entry_artifact        AllocationDecisionSignal / DecisionCase
executor              manual governance role + platform task (non-Decision Compiler)
automation_level      defaults to A0/A1; prohibits A2/A3
forbidden             direct modification of Canonical World; silent modification of Policy/Requirement
output                correction proposal + governance decision + impact scope
post_effect           triggers downstream Artifact STALE marking (§21)
reintegration         Correction completed → return to Diagnosis and recalculate Health/Gap
```

### GW01 WorldModelRepair

Handle data defects (coordinate errors, duplicate entities, stale travel, responsibility conflicts).

```text
DefectTriage          Severity × impact scope classification
RepairAction          Entity Merge/Split/Supersede see 08; attribute corrections see this process
ImpactAnalysis        Affected Opportunity / Coverage / Workload list
Verification          After correction, recalculate Health, and whether Gap disappears
```

Identity-type repair must go through `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`
Human Resolution authority, GW01 must not bypass.

### GW02 ModelGovernance

Handle systematic model bias

```text
EvidenceReview        Residual / Distribution Drift / calibration report
VersionDecision       Retrain / Replace Features / Downgrade Usage / Retain
Reprojection          new model_version recomputes historical Derived State
```

GW02 does not automatically reweight objective; any weight changes entering Candidate
Still follows `02` Objective governance.

### GW03 PolicyReview

Handle `POLICY_INFEASIBLE` and mutually exclusive Hard Policy.

```text
ConflictExposition    Which two Policies, in which scope,
AuthorityRouting      upgrade per policy owner (must not be relaxed by engineering side by default)
Resolution            change Policy / apply for exception / accept local non-coverage
```

GW03 and `RequirementExceptionProposal` (02 §43A) relationship:
Proposal is an exception **within a single DecisionCase**;
GW03 is the entry point for revising the **Policy semantics across Cases**. Their approval permissions differ.

---

# Standard Scenario Workflows

## 15. SC01 Greenfield Deployment

```text
Market Definition
→ Opportunity Validation
→ Coverage Demand Construction
→ DP01 Resource Sizing
↕ DP05 Coverage Allocation
→ DP02 Resource Location
↕ DP03 Territory Alignment
→ DP04 Personnel Matching / Hiring Plan
→ DP06 Scheduling Feasibility
→ Cross-Problem Evaluation
→ Human Review
→ Transition / Launch Plan
```

Sizing ↔ Coverage needs to generate a Resource–Coverage Frontier.

Location ↔ Territory is usually Iterative; large-scale can be Macro Joint + Micro Iterative.

Default Ideal Deployment → Personnel/Hiring, rather than forcibly designing the market around existing personnel positions.

---

## 16. SC02 Capacity Expansion

Entry: 

```text
Persistent Capacity Gap
Opportunity Gap
Market Growth
New Product
New Channel
Management-approved envelope
```

Workflow: 

```text
Allocation Gap Confirmation
→ Root Cause Confirmation
→ Is additional capacity actually needed?
   ├─ NO → route elsewhere
   └─ YES
      → DP01 Incremental Sizing
      → Marginal Value
      → DP02 Resource Location
      ↕ DP03 Territory Reallocation
      → DP04 Personnel Matching
      → DP05 Coverage Reallocation
      → Delta Evaluation
      → Transition Planning
```

Before entering DP01, must pass at least GlobalCapacity, TravelBenchmark, LocalImbalance, CoveragePolicyStress, etc.

Must compare:

```text
Maintain
Rebalance Existing Capacity
Reduce Low-value Coverage
Relocate Existing Resource
Add Incremental Capacity
Hybrid
```

Cannot just compare adding a few people.

---

## 17. SC03 Capacity Reduction / Downsizing

Workflow: 

```text
Target Resource Envelope
→ Reassess Opportunity & Coverage Priority
→ DP05 Coverage Reallocation
↕ DP01 Resource Envelope
→ DP02 Resource Location
→ DP03 Territory Consolidation
→ DP04 Personnel Matching
→ Scheduling Feasibility
→ Change / Business Impact
→ Human Governance
→ Transition
```

The logic is Market Need → Required Deployment → Required Capability → Personnel Matching, rather than first deciding who stays.

---

## 18. SC04 Structural Rebalancing

First ask Should we change?

```text
Current Baseline
→ Allocation Health
→ Gap & Diagnosis
→ Materiality
→ Maintain Candidate + Rebalance Candidates
→ DP03 Territory Alignment
↕ DP02 Location Evaluation
↕ DP04 Personnel Feasibility
→ Routing / Scheduling Evaluation
→ ChangeCost
→ Delta Evaluation
→ Local Review
→ Approval
→ Transition
```

Maintain is mandatory.

Minor / Major Rebalance can be categorized by accounts/revenue/resources/territory changes, and affect approval, transition, validation.

---

## 19. ChangeBudget / Central Benchmark / Local Adjustment

`ChangeBudget` **is not a new canonical Entity**.

It is expressed by a set of `DecisionRequirement / Guardrail` in `DecisionCase / WorkflowPolicy`, for example:

ChangeBudget can restrict:

```text
Max reassigned accounts
Max reassigned revenue
Max moved resources
Max transition cost
```

Structural Workflow recommends consistently generating CentralBenchmarkCandidate.

LocalAdjustedCandidate must form a Delta based on Central Benchmark; after HumanOverride recalculate Opportunity, Workload, Travel, Capacity, ChangeCost, Constraint Status.

---

## 20. Scenario Fork / Cross-Problem Evaluation

Create Scenario Overlay on Baseline, do not copy/modify production World.

Different Solver Candidates project into a unified Business Evaluation Space:

```text
Opportunity Coverage
Service Level
Capacity Utilization
Travel Burden
Resource Cost
Change Cost
Stability
Business Risk
Implementation Complexity
```

v1.2 does not default to Universal Score; can retain Pareto Candidate Set.

Recommendation ≠ Decision. 

---

## 21. Workflow Restart / Artifact Invalidation

New Evidence or upstream changes can restart from a specified Step.

After dependency changes, old Artifacts are marked STALE; further approval is prohibited.

Both WorkflowTemplate and OrchestrationRun are versioned.

---

## 21A. Run Hierarchy

v1.2 unifies technical execution records:

```text
OrchestrationRun
  ├── ProblemRun
  │     └── SolverRun
  ├── OracleRun
  └── EvaluationRun
```

`ProblemRun` is defined by 03, `OrchestrationRun` is defined by 05.

No longer use a semantically vague unified run name to cover all layers.

---

## 22. Workflow Status

```text
CREATED
RUNNING
WAITING_FOR_HUMAN
WAITING_FOR_DATA
BLOCKED
COMPLETED
FAILED
CANCELLED
```

WAITING_FOR_DATA is not a failure; POLICY_INFEASIBLE etc. can cause Workflow to be BLOCKED.

Retry must be based on FailureType; Generic Retry is prohibited.

---

## 23. Agent and Orchestrator Boundary

Agent: 

```text
interpret
suggest scenario
request diagnostic tests
explain candidates
collect human input
```

Orchestrator: 

```text
workflow state
dependency
artifact validity
allowed transition
tool invocation
checkpoint
retry/fallback
```

Agent does not rely on conversational memory to manage complex Workflow state.

---

## 24. OrchestrationPolicy / Budget Governance

```text
allowed_problem_types
allowed_solvers
runtime_budget
max_iterations
automation_level
human_checkpoints
failure_policy
scenario_limit
```

Budget: 

```text
ComputeBudget
ChangeBudget
TimeBudget
HumanReviewBudget
CandidateBudget
```

---

## 25. Cross-Horizon Escalation / Freeze Window

Operational Failure is continuous and root cause structural triggers Structural Review creation.

Upper-level structural changes can trigger Scheduling/ Routing refresh.

Supports StructuralFreezeWindow (promotion, quarter close, peak season).

---

## 26. Transition / Validation

Approved Decision → TransitionPlan → Execution → Stabilization → Validation → DecisionOutcome. 

Structural Workflow is not directly Closed after Transition.

Supports ShadowWorkflow, Pilot, StagedTransitionPlan.

---

## 27. DecisionRisk

```text
Low
Medium
High
Critical
```

Consider BusinessImpact, ChangeScale, Uncertainty, CustomerRelationshipImpact, PersonnelImpact, Reversibility, DataConfidence.

High-risk/critical structural decisions must require higher-level Human Governance.

---

## 28. Architecture Gates

In principle, reject:

```text
Business Scenario is bound one-to-one with a Solver.
Expansion = one Expansion Solver.
Workflow order is hardcoded in Controller.
Composite Problem creates duplicate business variables.
Joint Solver output cannot restore Atomic Semantics.
Oracle automatically modifies Candidate.
Iterative Loop has no stopping condition.
All Candidates run the highest-cost Simulation.
SolverSelector is merged with ProblemRouter.
Solver timeout automatically relaxes Hard Constraint.
After Human Review, do not re-evaluate.
HumanOverride silently replaces Candidate.
After dependency changes, old Candidate remains valid.
Workflow has no versioning.
Scenario modification creates World.
Structural Decision does not allow Maintain.
Expansion does not compare Rebalance/Coverage alternatives.
Downsizing first decides on personnel, then decides on market.
One Operational Failure escalates Territory.
Generic Retry
Agent self-maintains Workflow State.
After Approval, skip Transition.
After Transition, do not perform Validation.
```

---

## 29. MVP Order / DoD

Minimum Orchestration:

```text
WorkflowTemplate
WorkflowInstance
WorkflowStep
Artifact Dependency
ProblemStep
OracleStep
EvaluationStep
HumanCheckpoint
Sequential
Iterative
```

First Workflow: DP06 Scheduling Reference Integration.

Second Workflow: Coverage ↔ Scheduling Iterative Loop.

Third Workflow: Structural Rebalancing (Baseline + Maintain + Rebalance + HumanOverride + Re-evaluation).

At least verify:

```text
Sequential
Iterative
Failure Routing
Human Override
Scenario Isolation
```

Complete Pipeline:

```text
Sales World Model
→ Allocation Intelligence
→ Decision Case
→ Scenario Orchestrator
→ Decomposition Planner
→ Problem Projection
→ Solver / Oracle / Simulation
→ Candidate Decision
→ Cross-Problem Evaluation
→ Human Review
→ Decision
→ Transition
→ Execution
→ Observation
→ Validation
→ World Model
```
