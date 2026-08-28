# Sales Resource Allocation Framework

## Project Charter v1.2

**Project Name:** Sales Resource Allocation Framework
**Abbreviation:** SRAF
**Chinese Name:** Sales Resource Allocation Decision Framework
**Document Version:** v1.2
**Document Type:** Project Top‑Level Direction Specification (Project Charter)

---

## 1. Project Background

Enterprise sales resource allocation is usually fragmented across multiple independent problems:

- How many people does the sales team need;
- Where should sales personnel be deployed;
- Who should be responsible for each customer;
- How should Territory be divided;
- How much sales resource should be invested in different customers;
- How often should they be visited;
- How to schedule periodic visits;
- How to execute the daily beat route.

Traditional systems usually productize one of these problems individually, for example:

```text
Territory Management
Route Planning
Visit Scheduling
Sales Force Sizing
Coverage Planning
```

This fragmentation has its rationale, but it also leads to a fundamental problem:

> **Different optimization problems lack a unified sales world semantics and resource allocation logic.**

A "visit scheduling cannot be done" problem may not be a scheduling algorithm issue; it could stem from Territory imbalance, incorrect sales resource deployment location, overly high Coverage Policy, insufficient Capacity, capability mismatch, excessive Travel burden, or erroneous data/potential models.

The goal of SRAF is to establish:

```text
Business World
      ↓
Problem Diagnosis
      ↓
Decision Framing
      ↓
Appropriate Decision Problem
      ↓
Candidate Decisions
      ↓
Business Evaluation
```

rather than:

```text
Business Problem
      ↓
Solver-specific Model
      ↓
local mathematical optimum
```

---

## 2. External Theoretical Foundations

SRAF is based on classic theories and practices such as sales force design, Territory Alignment, resource allocation, districting, scheduling and routing, but does not directly copy traditional product forms.

The business essence of Territory Alignment is the assignment of accounts and their related selling activities to a salesperson / sales team, not merely the drawing of map polygons. Good Territory Alignment simultaneously affects customer coverage, sales, productivity, fairness, morale and travel efficiency.

On this basis, SRAF establishes a unified business World Model, Decision Ontology, Decision Problem Contract, diagnostics, Orchestration, Evaluation & Benchmark, and governance system.

---

## 3. SRAF Extended Design

SRAF unifies the sales resource allocation problem into:

> **Continuously forming explainable, verifiable, and executable resource allocation decisions among market opportunities, customer service demands, sales resource capabilities, organizational policies, and real‑world constraints.**

Formal expression:

\[
AllocationDecision
=
f(
MarketOpportunity,
CoverageDemand,
ResourceCapacity,
Capability,
Geography,
Policy,
ExistingState
)
\]

The core is not:

\[
Accounts \rightarrow Territories
\]

but:

\[
MarketOpportunity
\rightarrow
SalesResource
\rightarrow
Responsibility
\rightarrow
Coverage
\rightarrow
Execution
\]

---

## 4. Core Project Proposition

> **Allocate the right sales capacity to the right market opportunity, at the right level of responsibility and time horizon.**

Chinese:

> **At the correct time scale and responsibility level, allocate the appropriate sales capacity to the market opportunities most worthy of investment.**

Use Sales Capacity rather than Salesperson, because resources can include:

```text
Field Sales
Merchandiser
Key Account Manager
Inside Sales
Distributor Resource
Specialist
Digital Agent
```

---

## 5. What SRAF Is Not

### 5.1 Not a Territory Drawing Tool

Territory geometry is the spatial projection of responsibility assignment.

\[
Territory \neq Polygon
\]

More akin to:

\[
Territory
=
Collection(Responsibility)
\]

### 5.2 Not a Super Solver

SRAF does not attempt to solve Sizing, Location, Territory, Coverage, Scheduling, and Routing simultaneously with a single model.

> **Semantic Separation, Computational Coupling.**

### 5.3 Not a Traditional CRM / SFA

CRM/SFA mainly records customers, responsibilities, and activities; SRAF asks whether these sales responsibilities should be configured in this way, and whether a better resource allocation method exists.

SRAF is a Decision Layer, not a Transaction System of Record.

### 5.4 Not a Pure GIS Framework

Spatial information is an important input, but one must also understand Opportunity, Workload, Capacity, Capability, Responsibility, Policy, and ChangeCost.

### 5.5 Not an LLM Planner

LLM/Agent can understand problems, query the World Model, form diagnostic hypotheses, invoke solvers, compare scenarios, explain decisions and support human review, but must not freely generate unverified mathematical configuration results and directly write them into the business system.

---

## 6. Core Architecture Principles

### P1. World Before Optimization

First establish a unified representation of the Sales World, then optimize.

### P2. Territory Is Responsibility, Not Geometry

Territory first represents a set of sales responsibilities; spatial boundaries are a derived expression.

### P3. Opportunity Is Not Sales

Historical sales volume is only one piece of evidence for an Opportunity. Opportunity must preserve source, evidence, confidence, valid_time, model_version.

### P4. Workload Is Derived

Workload is derived from CoverageNeed, SalesActivity, ServiceTime, Travel, etc.; distinguish between Intrinsic Workload and Network Workload.

### P5. Resource Is Not Person

Use the SalesResource abstraction, and distinguish ResourceArchetype, ResourceRequirement, ResourceDeployment, DeploymentAssignment, SalesResource, ResourcePool.

### P6. Responsibility Is Explicit

Do not simplify core relationships into Account.owner_id. Use ResponsibilityAssignment to express Resource, Subject, Role, Activity, ProductScope, ResponsibilityScope, EffectiveTime, Source.

### P7. Policy Is Not Constraint

Business Policy is transformed by the Problem Compiler into concrete mathematical Constraints.

### P8. Decision Problem Is Not Solver

Problem is business semantics; MILP/CP-SAT/heuristics etc. are solution methods.

### P9. Semantic Separation, Computational Coupling

The boundaries of a business problem must not be determined by the algorithm implementation method. Allow computational coupling such as Sequential, Iterative, Joint, Bilevel, etc.

### P10. Solver State Is Never World Truth

```text
Solver Solution
      ↓
Decision Interpreter
      ↓
Candidate Decision
      ↓
Evaluation
      ↓
Review / Approval
      ↓
Transition
      ↓
Observed World
```

### P11. Baseline Before Change

Structural Decision must be compared with the Baseline and consider ChangeCost, Disruption, Uncertainty, TransitionCost, ImplementationRisk.

### P12. Do Nothing Is a Valid Decision

MaintainCurrentState must be a legal Candidate.

### P13. Diagnosis Before Optimization

Observed Symptom → Allocation Gap → Root Cause Diagnosis → Materiality → Decision Trigger → Problem Classification. 

### P14. Evidence Before Automation

Important judgments must be labeled with Semantic Status such as ObservedFact, MasterDataFact, ExternalFact, ModelEstimate, HumanJudgment, PolicyDefinition, DerivedState, DecisionOutput, ScenarioAssumption, etc.

### P15. Human Override Must Become Evidence

Manual adjustments must record Change, Reason, Evidence, ExpectedImpact, Approver, Timestamp, and feed into subsequent learning.

### P16. Change Has Cost

ChangeCost must include at least CustomerRelationshipCost, SalespersonIncomeImpact, RelocationCost, LearningCost, TerritoryTransitionCost, ManagementChangeCost.

### P17. Stability Is a Business Objective

Continuously evaluate AssignmentChurn, TerritoryChurn, RelationshipDisruption, TransitionFrequency, and support Persistence, Hysteresis, Cooldown, Minimum Improvement Threshold.

### P18. Different Horizons Require Different Decisions

```text
Strategic
Structural
Tactical
Operational
Execution
```

A lower-level Solver must not silently change upper-level decisions.

### P19. Optimize Opportunity Allocation, Not Geometric Beauty

Territory compactness is merely a proxy. Travel evaluation is divided into L1 Geometric, L2 Road Network, L3 Operational Routing Simulation.

### P20. Reuse Before Reinvent

SRAF itself focuses on building Ontology, World Model, Decision Problem Contract, Allocation Intelligence, Problem Compiler, Evaluation, Decision Governance, Evidence, Orchestration. Mature GIS, routing, solver, workflow, etc. are prioritized for reuse.


### P21. Single Normative Owner

Each core business concept must have exactly one formal specification that holds its canonical schema.

Other specifications may reference the concept, but must not define a different set of schemas.

The formal ownership of v1.2 is:

```text
00 Charter        → direction / principles / non-goals
01 World Model    → canonical world / time / evidence / snapshot
02 Decision       → decision case / candidate / approval / transition
03 Problem        → atomic problem / projection / failure semantics
04 Intelligence   → health / gap taxonomy / diagnosis / router
05 Orchestration  → scenario workflow / coupling / governance
06 Benchmark      → validation gates / benchmark protocol
07 Architecture   → implementation boundaries / adapters / runtime
08 Identity       → canonical identity / entity resolution / merge-split governance
```

P21's concretization in v1.2: the **principles** regarding Canonical ID in `01 §9–10` remain valid,
but its canonical schema and decision/governance rules belong to `08`;
`01` becomes a reference and must not maintain a second set of field definitions.

---

## 7. Core World Model

```text
Market Signal
      ↓
Opportunity Estimate
      ↓
Coverage Need
      ↓
Coverage Allocation
      ↓
Coverage Commitment
      ↓
Workload Demand
      ↓
         MATCH
      ↑
Capacity Supply
      ↑
Resource Deployment
      ↑
Sales Resource
      ↓
Responsibility Assignment
      ↓
Territory
      ↓
Execution
      ↓
Observation
      ↓
World State
```

---

## 8. Allocation Intelligence

```text
Allocation Health
      ↓
Gap Detection
      ↓
Root Cause Diagnosis
      ↓
Materiality Assessment
      ↓
Decision Trigger
      ↓
Problem Router
```

Core Gap includes:

```text
Coverage Gap
Capacity Gap
Opportunity Gap
Spatial / Travel Gap
Capability Gap
Allocation Gap
Stability Gap
```

---

## 9. Atomic Decision Problem Library

```text
DP01 Resource Sizing
DP02 Resource Location
DP03 Responsibility / Territory Alignment
DP04 Personnel Matching
DP05 Coverage & Channel Allocation
DP06 Visit Scheduling
DP07 Daily Routing
```

A new Atomic Problem must prove that it cannot be reasonably expressed by an existing Contract.

---

## 10. Composite Decision Problems

```text
CP01 Deployment Design
     Sizing + Location + Territory

CP02 Capacity Expansion
     Incremental Sizing + Location + Territory + Personnel

CP03 Structural Rebalancing
     Territory + Personnel + ChangeCost

CP04 Coverage Execution Design
     Coverage + Scheduling + Routing
```

Coupling Mode: 

```text
Independent
Sequential
Iterative
Joint
```

---

## 11. Separation of Business Scenario and Decision Problem

Business Scenario is Context; Decision Problem is a business problem with changeable variables. Expansion is not a Solver Problem, but may orchestrate Incremental Sizing, Location, Territory, Personnel Matching, etc.

---

## 12. Decision Lifecycle

```text
Detected
   ↓
Framed
   ↓
Proposed
   ↓
Reviewed
   ↓
Approved
   ↓
Transitioning
   ↓
Active
   ↓
Evaluating
   ↓
Validated / Failed
   ↓
Retired
```

Improvement of Solver Objective is not the ultimate criterion for Decision success.

---

## 13. Decision Validation

Important Structural / Tactical Decision must define a DecisionValidationPlan synchronously upon creation:

```text
Expected Effect
Metrics
Baseline
Validation Window
Control / Comparison
Success Threshold
Failure Condition
```

---

## 14. Role of the Agent

Agent is a Sales Allocation Decision Agent:

```text
Observe
   ↓
Interpret
   ↓
Diagnose
   ↓
Frame Decision Problem
   ↓
Select Tools
   ↓
Generate Alternatives
   ↓
Explain Trade-offs
   ↓
Support Human Decision
   ↓
Observe Outcome
```

Where World Model = Environment; Ontology = Language; Allocation Intelligence = Diagnostic Substrate; Decision Engines = Tools; Evaluation = Evidence; Human = Governance.

---

## 15. Relationship with the Existing Visit Scheduling Optimizer

`visit-scheduling-optimizer` is registered in SRAF as:

> **Reference Decision Engine — DP06 Visit Scheduling**

It can also serve as a Scheduling Feasibility Oracle.

In principle, it is not responsible for deciding upstream issues such as Headcount, Territory, Opportunity, Resource Location, etc.

---

## 16. Project Success Criteria

SRAF v1.x must at least demonstrate:

- semantic consistency;
- problem classification capability;
- Baseline vs Candidate comparability;
- Solver replaceability;
- Evidence Traceability; 
- real verifiability after implementation.

---

## 17. Non-Goals

v1.2 does not prioritize the following:

```text
Full CRM
Full SFA
Full map platform
LLM Foundation Model
General MLOps
Self-developed Routing Engine
Self-developed General MILP Solver
Real-time automatic rebalancing of all Territories
Fully unmanned resource allocation
```

---

## 18. Final Architecture Direction

```text
SALES WORLD MODEL
What is the world?
        ↓
ALLOCATION INTELLIGENCE
What is wrong and why?
        ↓
DECISION SCENARIO ORCHESTRATOR
What decision needs to be made?
        ↓
DECISION PROBLEM LIBRARY
What can be changed?
        ↓
DECISION COMPILER
How should the problem be solved?
        ↓
SOLVER / SIMULATION TOOLS
Compute candidate solutions
        ↓
EVALUATION & GOVERNANCE
Should we actually do it?
        ↓
EXECUTION / OBSERVATION LOOP
Did it really work?
```

---

## 19. Charter-level Architecture Gates

The following situations are in principle rejected:

```text
Account.owner_id is treated as the sole responsibility model
Territory is directly modeled as a Polygon
Potential is equated with historical sales
Workload is written as a fixed store field
Policy is hard-coded directly into the Solver
Decision Problem is bound to a specific Solver
Solver Solution directly writes real business state
Perform structural adjustments without a Baseline
Evaluate Territory without a ChangeCost
Coverage Need and Coverage Commitment are conflated
Scheduling automatically corrects upstream Coverage Policy
Agent can autonomously change Territory without Evidence
```
