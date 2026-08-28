# SRAF Reference Architecture Specification v1.2

**项目：** Sales Resource Allocation Framework  
**简称：** SRAF  
**文档：** `07_REFERENCE_ARCHITECTURE.md`  
**状态：** Implementation Baseline v1.2  

**上位规范：**

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

# 1. 文档目标

本文件负责把前述业务语义、决策模型与 Benchmark 规范收敛为一个可实施的参考架构。

它回答：

```text
SRAF 需要哪些工程模块？
各模块之间的边界是什么？
哪些能力由 SRAF 自己拥有？
哪些能力应优先复用成熟框架？
Agent 在哪里？
Solver 在哪里？
World Model 如何落地？
现有 visit-scheduling-optimizer 如何接入？
第一阶段应按什么顺序实现？
```

本文件不是详细代码设计。

它定义：

> **Reference Architecture + Module Boundaries + Integration Contracts + Implementation Sequence。**

---

# 2. 架构最高原则

SRAF 工程实现必须继续遵守：

```text
World before Optimization
Diagnosis before Optimization
Problem before Solver
Baseline before Change
Evidence before Automation
Decision before Transition
Observation before Learning
```

因此物理架构必须能够体现这些边界，而不是只在文档里存在。

---

# 3. SRAF Reference Architecture 总览

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

# 4. 架构分为四个平面

为了避免所有组件混在同一个“平台”概念中，v1.2 将 SRAF 分成四个工程平面：

```text
A. World Plane
B. Decision Plane
C. Computation Plane
D. Governance & Evidence Plane
```

---

# 5. A. World Plane

负责：

> **世界现在是什么。**

包含：

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

World Plane 不负责：

```text
候选方案
数学求解
审批
```

---

# 6. B. Decision Plane

负责：

> **哪里有问题、应该决定什么、有哪些候选。**

包含：

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

Decision Plane 不拥有具体 Solver 实现。

---

# 7. C. Computation Plane

负责：

> **如何计算候选配置与可行性。**

包含：

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

Computation Plane 不能直接修改真实 World State。

---

# 8. D. Governance & Evidence Plane

负责：

> **为什么相信、谁批准、实施后是否有效。**

包含：

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

这一平面贯穿 A/B/C，而不是一个末端模块。

---

# 9. v1.2 的核心技术选择

Reference Implementation 第一阶段建议：

```text
PostgreSQL + PostGIS
```

作为：

```text
Canonical State
Temporal State
Spatial Data
Policy
Assignment
Decision Metadata
Snapshot Metadata
```

的主存储。

原因：

- 关系模型适合强约束与事务一致性；
- PostGIS 足够承担第一阶段空间能力；
- 不需要一开始引入复杂图数据库；
- 便于 ProblemProjection、Benchmark 和 SQL 审计；
- 技术成熟、生态成熟。

---

# 10. Event / Observation Store

v1.2 不建议引入独立 Event Sourcing 平台作为强依赖。

第一阶段可使用：

```text
append-only PostgreSQL tables
```

记录：

```text
Observation
WorldEvent
DecisionEvent
TransitionEvent
```

只要满足：

```text
immutable
timestamped
causation
correlation
provenance
```

即可。

---

# 11. Graph Projection

v1.2 不建议 Graph Database 成为 Source of Truth；Phase 0–3 不把专用 Graph Database 作为依赖。

第一阶段可以采用：

```text
Materialized relational graph view
```

或轻量图索引。

后续只有在以下需求被验证后再引入专门图数据库：

```text
复杂 responsibility traversal
evidence graph navigation
agent graph reasoning
causal graph exploration
```

如果引入：

```text
Neo4j / Memgraph / similar
```

也只能作为 Projection。

---

# 12. Spatial / Routing Infrastructure

SRAF 不自建完整地图与路网引擎。

应通过：

```text
TravelProvider Adapter
```

使用成熟能力。

例如：

```text
OSRM
Valhalla
GraphHopper
commercial map APIs
enterprise GIS services
```

World Model 只保存：

```text
provider
network_version
routing_profile
calibration_version
```

不把整个道路网络本体塞入 Ontology。

---

# 13. Source Adapter Layer

每个外部数据源通过标准 Adapter 接入。

统一职责：

```text
read
normalize
map
validate
identity resolution
provenance attach
```

不允许 Source Adapter：

```text
直接生成 Territory
直接判断 Root Cause
直接修改 Coverage Policy
```

---

# 14. Source Contract

建议：

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

SRAF 需要：

```text
CanonicalIdentityService
```

负责：

```text
Account
ServiceLocation
Person
Organization
Resource
```

跨系统映射。

MVP 不要求构建完整企业级 MDM。

但其**业务语义、判定规则、权限矩阵与 Benchmark** 不在本文件定义，
由 `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` 拥有。
本文件只规定它作为工程模块如何落位。

至少要实现（细则见 08）：

```text
stable canonical ID + identity_domain      → 08 §5
SourceRecord / ExternalIdentifier 保留     → 08 §6–7
三态 MatchDecision + λ/π 阈值              → 08 §11
MERGE / UNMERGE / SPLIT / SUPERSEDE        → 08 §12–13
append-only IdentityResolutionRecord       → 08 §15
ImpactAnalysis + Trigger 阻断              → 08 §14
```

工程落位（对应 §70 推荐结构）：

```text
src/domain/identity/     CanonicalIdentity / MatchDecision / Resolution
                         （属 World Plane，不依赖任何 Solver）
adapters/sources/        提供 SourceRecord 与 ExternalIdentifier
benchmark/identity/      ID01–ID20 case + 噪声注入器 + ground truth
```

存储约束：

```text
identity_resolution 为 append-only（PostgreSQL 即可，§9–10 选择不变）
不引入专用图数据库；图仍是 Projection（§11）
WorldSnapshot 必须固化 applied resolution_id 集合（08 §15.2 TI-2）
```

若客户已有企业级 MDM，`CanonicalIdentityService` 退化为
**消费方 + 冲突上报方**（上报走 `05 GW01`），
SRAF 不得重建第二套主数据；
但 `08 §23` 的 Identity Gate 仍必须对上游 MDM 的产出跑通，
否则等价于接受未经检验的身份真值。

---

# 16. Canonical World API

所有上层模块不应直接依赖各 Source System。

统一通过：

```text
Canonical World API
```

获取：

```text
Current State
Historical State
Snapshot
Scenario View
Evidence
```

这样 Source System 更换不会污染 Decision Engine。

---

# 17. Snapshot Service

建议独立：

```text
WorldSnapshotService
```

职责：

```text
freeze decision baseline
resolve valid_time
resolve known_time
track schema/data versions
```

所有正式 DecisionCase 必须引用 Snapshot。

---

# 18. Scenario Service

建议：

```text
ScenarioService
```

只做：

```text
Baseline
+
ScenarioAssumption
=
Scenario World View
```

禁止复制整套生产数据库。

可以通过：

```text
overlay / delta model
```

实现。

---

# 19. Derived State Engine

负责统一计算：

```text
OpportunityCoverage
CoverageAttainment
WorkloadDemand
EffectiveCapacity
CapacityUtilization
TravelBurden
Stability
```

避免每个 Solver 自己重复计算业务指标。

---

# 20. Derived State Contract

每个 Derived Metric 应至少声明：

```text
metric_id
definition
inputs
unit
calculation_version
valid_scope
confidence_rule
```

例如：

```text
CapacityUtilization
```

不能在不同模块中出现三种不同公式。

---

# 21. Metric Registry

建议建立：

```text
MetricRegistry
```

统一管理：

```text
OpportunityCoverage
Workload
Capacity
Travel
ChangeCost
ServiceLevel
Stability
```

这对 Benchmark 与 Production 一致性很重要。

---

# 22. Allocation Intelligence Service

建议逻辑上拆成五个组件：

```text
HealthEvaluator
GapDetector
DiagnosticEngine
MaterialityEvaluator
ProblemRouter
```

但 v1.2 可以在一个服务/模块中实现。

逻辑分离即可。

---

# 23. HealthEvaluator

输入：

```text
WorldSnapshot
DerivedAllocationState
```

输出：

```text
HealthProfile
```

不输出：

```text
Decision
```

---

# 24. GapDetector

输入：

```text
HealthProfile
PolicyTarget
HistoricalBaseline
PeerBenchmark
```

输出：

```text
GapSet
```

必须明确 Reference。

---

# 25. DiagnosticEngine

MVP 采用：

```text
DiagnosticTest Library
+
Rule / Statistical Comparison
+
Counterfactual Calls
```

而不是 LLM end-to-end。

输出：

```text
DiagnosticHypothesis[]
EvidenceFor
EvidenceAgainst
Confidence
```

---

# 26. MaterialityEvaluator

输入：

```text
Gap
BusinessImpact
Persistence
Confidence
ChangeCostEstimate
```

输出：

```text
Monitor
Review
Actionable
Critical
```

---

# 27. ProblemRouter

输入：

```text
DiagnosticHypothesis
Materiality
Policy
```

输出：

```text
PrimaryDecisionProblem
AlternativeDecisionProblems
NoAction / Monitor / Repair
```

ProblemRouter 不选择 Solver。

---

# 27A. Resource Deployment Architecture Contract

Reference implementation 必须保持：

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

`DP02 Resource Location` 操作 Deployment；`DP04 Personnel Matching` 操作 DeploymentAssignment。

禁止在 Location Engine 内直接把 `Person` 当成 deployment node。

---

# 28. Decision Case Service

建议统一管理：

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

这是 Agent 最主要的结构化接口。

---

# 29. Agent Runtime 的定位

Agent 不属于 World Plane，也不属于 Solver Plane。

它位于：

# Decision Interaction Layer

逻辑上：

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

# 30. Agent 的主要能力

Agent 可以：

```text
解释 Allocation Signal
查询 Evidence
提出 Diagnostic Test
创建 Scenario
调用允许的 Workflow
比较 Candidate
解释 Trade-off
收集 Human Evidence
帮助形成 Review
生成 Transition Narrative
```

---

# 31. Agent 禁止直接做的事情

```text
写 Canonical World State
创建无来源 Hard Constraint
静默改变 Objective
把 Hypothesis 写成 Fact
直接批准 High-risk Decision
绕过 Orchestrator 调 Structural Solver
自动 Relax Hard Constraint
```

---

# 32. Agent Tool Contract

Agent 只能调用标准能力：

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

实际函数名可以不同。

关键原则是：

> Agent 面向业务 Contract，不面向数据库和 Solver 内部变量。

---

# 33. Decision Orchestrator

建议独立模块：

```text
DecisionOrchestrator
```

负责：

```text
WorkflowTemplate
WorkflowInstance
StepState
ArtifactDependency
Coupling
HumanCheckpoint
FailureRouting
```

v1.2 不需要自研通用 BPMN 引擎；Phase 0 可以先使用持久化 state machine 证明 Decision Semantics。

---

# 34. Workflow Engine 复用原则

如果成熟 Workflow 框架能够满足：

```text
state persistence
retry semantics
human wait state
versioning
artifact reference
```

应优先采用。

候选方向可以包括：

```text
Temporal
Dagster
Prefect
Camunda
existing enterprise workflow infrastructure
```

选择应由实施环境决定。

SRAF 自己拥有：

```text
Workflow Semantics
Decision Step Types
Failure Semantics
```

而不是必须拥有 Workflow Runtime。

---

# 35. Decision Compiler

这是 SRAF 核心自有能力之一。

建议逻辑拆分：

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

将：

```text
WorldSnapshot
DecisionCase
ProblemContract
```

转成：

```text
ProblemProjection
```

它负责：

```text
scope
aggregation
unit conversion
quality gate
temporal consistency
```

---

# 37. RequirementCompiler

将：

```text
Invariant
HardConstraint
Guardrail
Preference
```

映射到 Solver 可理解的约束/目标结构。

必须保存：

```text
business requirement ID
→ mathematical constraint ID
```

映射。

这样 Solver Conflict 才能解释回业务语言。

---

# 38. Constraint Provenance

如果 Solver 报告：

```text
constraint C882 conflicts
```

系统必须能够映射到：

```text
Policy P17
"Distributor boundary cannot be crossed"
```

而不是只给工程人员一个数学 constraint ID。

---

# 39. DecompositionPlanner

负责大规模 / Composite Problem 的求解策略。

它选择：

```text
Sequential
Iterative
Joint
Aggregation
Multi-stage
```

而不是具体 Solver。

---

# 40. MathematicalModelBuilder

负责：

```text
business variables
→
x / y / z
```

并生成 Solver-specific Model。

这一层是 Solver Adapter 前最后一个 SRAF-owned semantic boundary。

---

# 41. SolutionInterpreter

负责：

```text
x_17_92 = 1
```

恢复为：

```text
Responsibility R92
assigned to Deployment D17
```

然后形成：

```text
CandidateDecision
```

SolverSolution 本身永远不直接暴露为业务结果。

---

# 42. Solver Registry

建议：

```text
SolverRegistry
```

维护所有可用 Solver Capability。

每个 Adapter 声明：

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

# 43. v1.2 优先复用的 Solver / Library

不绑定具体实现，但建议优先评估：

```text
OR-Tools CP-SAT
SCIP
HiGHS
Gurobi（若客户环境许可）
Pyomo / OR-Tools modeling
NetworkX / graph tooling
H3
mature routing engines
```

不应第一阶段自研通用 Solver。

---

# 44. Solver Adapter

统一接口概念：

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

所有 Adapter 必须统一映射到：

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

并与：

```text
BusinessInfeasibility
```

完全分开。

---

# 46. Feasibility Oracle Registry

与 SolverRegistry 分开维护：

```text
OracleRegistry
```

典型：

```text
CapacityFeasibilityOracle
PersonnelFeasibilityOracle
SchedulingFeasibilityOracle
RoutingFeasibilityOracle
PolicyFeasibilityOracle
```

---

# 47. 一个 Engine 可以兼任 Solver 与 Oracle

例如：

```text
visit-scheduling-optimizer
```

可以同时注册：

```text
DP06 VisitScheduling Engine
```

和：

```text
SchedulingFeasibilityOracle
```

但两个调用模式必须有不同：

```text
run_purpose
output_contract
runtime_budget
```

---

# 48. visit-scheduling-optimizer 的正式接入位置

建议：

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

# 49. visit-scheduling-optimizer 不再拥有上游语义

未来应逐步把以下逻辑移出或收敛：

```text
客户是否值得拜访
Coverage frequency policy
Territory ownership
Headcount decision
Resource location decision
```

这些由 SRAF 上游 Contract 提供。

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

所有 Candidate 无论来自哪个 Solver，都进入统一：

```text
CandidateEvaluationService
```

负责：

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

统一：

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

不能直接比较不同 Solver 的 objective_value。

---

# 54. Change Cost Service

建议独立逻辑：

```text
ChangeCostEvaluator
```

第一阶段可以规则化计算：

```text
accounts moved
revenue moved
resources relocated
relationship risk
handover volume
```

后续再扩展模型化估计。

---

# 55. Human Governance Service

至少管理：

```text
HumanReview
HumanOverride
ExceptionApproval
FinalApproval
```

不需要一开始自建复杂组织审批平台。

可以通过：

```text
enterprise approval/workflow adapter
```

接入现有系统。

---

# 56. Human Override Versioning

必须：

```text
Candidate V1
→ Override
→ Candidate V1.1
→ Re-evaluation
```

不能覆盖 V1。

---

# 57. Transition Service

负责把：

```text
ApprovedDecision
```

变成：

```text
TransitionPlan
```

然后按阶段生成：

```text
WorldEvent
```

---

# 58. Transition 不是数据同步

结构调整可能需要：

```text
handover
effective date
temporary overlap
training
communication
freeze window
```

因此 Transition 不能简化成：

```text
update territory table
```

---

# 59. Execution Connector

SRAF 本身不是 SFA。

实际执行通常发生在：

```text
CRM
SFA
HR
ERP
route app
mobile sales app
```

SRAF 通过：

```text
ExecutionConnector
```

推送已批准的结构/计划。

---

# 60. Execution 写入原则

只有：

```text
Approved
+
TransitionReady
```

状态才能产生外部写入。

Solver / Candidate / Scenario 一律不能写。

---

# 61. Observation Connector

执行后从业务系统回流：

```text
visit completion
travel
sales
account status
resource availability
ownership changes
```

形成：

```text
Observation
```

再经过验证进入 World State。

---

# 62. Validation Service

负责执行：

```text
DecisionValidationPlan
```

支持：

```text
BeforeAfter
MatchedControl
DifferenceInDifferences
StaggeredRollout
A/B
```

具体分析模块可复用成熟统计库。

---

# 63. Benchmark Service

Production 与 Benchmark 使用同一：

```text
WorldSnapshot
DecisionProblemContract
SolverAdapter
Evaluation
```

Benchmark Service 只负责：

```text
case management
dataset version
run matrix
metrics
regression
reporting
```

---

# 64. Benchmark 不应该另建一套研究代码

禁止：

```text
notebook implementation
≠
production implementation
```

核心 Contract 与 Engine 必须复用生产实现。

可以在 Benchmark 侧增加：

```text
synthetic generator
case injector
ground truth
evaluation harness
```

---

# 65. Audit / Provenance

建议统一：

```text
RunProvenance
```

关联：

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

除了技术日志，需要 Decision Observability。

至少能够回答：

```text
为什么创建了这个 DecisionCase？
为什么路由到 DP03？
为什么选择这个 Solver？
为什么 Candidate B 排在 A 前面？
谁修改了 Candidate？
哪些数据版本被使用？
最终效果如何？
```

---

# 67. 技术日志与业务证据分开

例如：

```text
CPU usage
stack trace
HTTP error
```

属于 Technical Observability。

而：

```text
CoverageGap evidence
Policy conflict
Candidate trade-off
Human override reason
```

属于 Decision Evidence。

两者不能混为一种 log。

---

# 68. API Boundary

SRAF v1.2 推荐使用清晰的 domain APIs / service interfaces。

不要求第一阶段全部微服务化。

可以先：

```text
modular monolith
```

但模块边界必须清楚。

---

# 69. 不建议 v1.2 直接微服务化

原因：

- World / Decision Contract 仍在快速演进；
- 过早拆微服务会固化错误边界；
- 增加运维复杂度；
- Benchmark 与本地开发更困难。

推荐：

# Modular Monolith First

成熟后再按负载与组织边界拆分。

---

# 70. 推荐 Repo 结构

07 中的逻辑模块仍然保留，但 **MVP 不按逻辑模块机械拆成十几个服务**。

v1.2 推荐先收敛为六个 package：

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

原则：

> **Logical module boundary ≠ deployment service boundary。**

第一阶段仍采用 Modular Monolith First。


---

# 71. 是否与现有 visit-scheduling-optimizer 合仓

v1.2 建议：

> **不要立即合仓。**

SRAF 作为 Framework 维护：

```text
VisitSchedulingAdapter
```

通过标准 Contract 调用现有仓库。

原因：

- 先验证边界；
- 避免重写稳定能力；
- 保留 solver 独立演进；
- 验证“Decision Problem ≠ Solver”。

只有后续确有工程收益再考虑 monorepo。

---

# 72. 现有项目改造原则

对 `visit-scheduling-optimizer` 第一阶段不建议大规模重构。

优先做：

```text
Adapter
Input Contract
Output Contract
Failure Semantics
Run Provenance
Feasibility Mode
```

这五项。

先让它成为 SRAF-compliant Decision Engine。

---

# 73. Territory Engine 的策略

SRAF v1.2 不应第一阶段立即自研大型 Territory Optimizer。

建议顺序：

```text
1. Simple baseline heuristic
2. Existing open-source / OR formulations
3. Exact small-instance reference solver
4. Scale heuristic
5. Routing-in-the-loop evaluation
```

先证明 Decision Framework，再追求算法领先。

---

# 74. Territory Engine Baseline

第一版甚至可以使用：

```text
balanced clustering
graph partitioning
local swap heuristic
```

作为 Candidate Generator。

只要：

```text
Contract
Baseline
ChangeCost
Travel
Opportunity
Evaluation
```

完整。

---

# 75. DP01 Sizing Engine 策略

第一阶段优先输出：

```text
Resource-Coverage Frontier
```

而不是唯一 Headcount。

可先使用：

```text
workload/capacity model
+
geographic travel approximation
+
scenario enumeration
```

后续再增强 location-allocation joint model。

---

# 76. DP02 Location Engine 策略

优先复用：

```text
facility location
p-median
location-allocation
```

成熟 OR 建模思路。

SRAF 自己增加：

```text
personnel feasibility
change cost
responsibility semantics
```

---

# 77. DP04 Personnel Matching 策略

可以从：

```text
assignment / matching
```

模型开始。

优先保证：

```text
capability
eligibility
location
relationship
fairness
```

语义正确。

不必先做复杂 ML。

---

# 78. DP05 Coverage Allocation 策略

可能需要：

```text
response curves
priority rules
resource substitution
```

MVP 可以从：

```text
minimum/preferred/maximum
+
opportunity priority
+
capacity envelope
```

开始。

---

# 79. DP07 Routing Engine 策略

SRAF 不自研路由核心。

优先复用：

```text
OR-Tools routing
OSRM/Valhalla/GraphHopper network
```

将其作为：

```text
Decision Engine
+
Oracle
```

---

# 80. 依赖方向

工程上必须保持：

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

更准确说：

> 下层计算模块依赖上层定义的 Contract，但不能反向拥有业务语义。

---

# 81. 禁止反向依赖

例如：

```text
world.Account
```

不能出现：

```text
cp_sat_variable_index
```

同理：

```text
DecisionCase
```

不应知道：

```text
GurobiModel
```

---

# 82. Contract-first Development

每新增一个 Engine，顺序固定：

```text
1. Define Decision Problem Contract
2. Define Problem Projection
3. Define Failure Semantics
4. Define Evaluation
5. Define Validation
6. Implement Adapter / Solver
```

禁止：

```text
先写算法
→ 再想它算的是什么
```

---

# 83. Schema-first / Type-safe

建议核心对象定义统一 schema。

例如可以采用：

```text
Pydantic / JSON Schema / protobuf
```

具体取决于技术栈。

重点是：

```text
WorldSnapshot
DecisionCase
ProblemProjection
CandidateDecision
OracleResult
```

必须是明确 Contract，而不是任意 dict。

---

# 84. 版本策略

所有核心 Contract：

```text
World Schema
Decision Ontology
Problem Contract
Workflow Template
Solver Adapter
Metric Definition
Benchmark Case
```

都必须版本化。

---

# 85. Compatibility Policy

建议：

```text
patch:
implementation fix, semantic unchanged

minor:
backward-compatible field / rule extension

major:
semantic meaning changed
```

例如：

```text
CoverageNeed.frequency
```

含义改变必须 major version。

---

# 86. Migration

World Schema 升级时必须提供：

```text
migration
backfill
version compatibility
```

历史 Snapshot 不应该被静默重新解释。

---

# 87. Historical Reproducibility

当 v2.0 出现时，仍应能够回答：

> v1.2 当时为什么做出这个 Decision？

因此历史 Run 引用：

```text
schema_version
contract_version
compiler_version
solver_version
```

必须保留。

---

# 88. Security / Authorization

SRAF Decision Risk 不同，权限不同。

例如：

```text
View health
Run scenario
Generate candidate
Submit override
Approve territory
Approve downsizing
Execute transition
```

应分别授权。

---

# 89. Agent Permission

Agent 权限通过 Tool Policy 控制。

Agent 不应继承用户所有数据库权限。

例如：

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

Sales Resource 与 Person 分离还有工程价值：

> Solver 很多时候只需要 Resource Capacity / Capability，不需要员工全部个人信息。

ProblemProjection 应遵循最小数据原则。

---

# 91. Personal Data Minimization

例如 Territory Solver 可能只需要：

```text
deployment location
capability
relocation feasibility
```

不需要：

```text
full HR profile
phone
personal address details
```

---

# 92. Performance Architecture

v1.2 优先考虑：

```text
Snapshot
Projection cache
Travel matrix cache
Derived state cache
Scenario artifact reuse
```

而不是过早分布式计算。

---

# 93. Projection Cache

Cache Key 至少包括：

```text
snapshot_id
scenario_id
problem_contract_version
projection_version
scope
```

避免使用过期 Projection。

---

# 94. Artifact Invalidation

当依赖对象变化：

```text
CoverageCommitment changed
```

自动使：

```text
ScheduleCandidate
RouteCandidate
```

标记：

```text
STALE
```

Orchestrator 不允许继续审批 stale artifact。

---

# 95. Travel Matrix Cache

应绑定：

```text
network_version
routing_profile
time context
location_version
```

否则会发生：

> 地点变化但仍使用旧 travel matrix。

---

# 96. Deployment 模式

第一阶段建议：

```text
single service
or modular monolith
+
external solver workers
```

复杂 Solver 可使用独立 Worker。

不要求全模块独立部署。

---

# 97. Long-running Solver

Structural Solver 可以：

```text
async job
```

Orchestrator 保存：

```text
run_id
status
artifact
```

Agent 不需要保持长连接。

---

# 98. Interactive What-if

Interactive Mode 可以选择：

```text
fast heuristic
cached projection
reduced fidelity
```

输出必须标记：

```text
evaluation_fidelity
optimality_claim
```

不能把 5 秒 heuristic 结果包装成最终全国方案。

---

# 99. Production Structural Run

可使用：

```text
higher fidelity
longer runtime
full constraint validation
routing simulation
human review
```

---

# 100. Benchmark Environment

Benchmark 应支持：

```text
fixed seed
fixed snapshot
fixed dependency version
isolated run
```

保证可复现。

---

# 101. CI Architecture Gates

建议把前面文档中的关键 Architecture Gates 转成自动检查。

例如：

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

可以明确禁止：

```text
world/
```

依赖：

```text
solver_registry/
```

或者：

```text
decision/
```

import 某具体 Solver SDK。

具体可通过模块依赖测试实现。

---

# 103. Contract Compliance Test

每个 Engine Adapter 必须运行：

```text
standard input test
standard output test
status mapping test
failure mapping test
provenance test
```

才能注册 SolverRegistry。

---

# 104. Reference Vertical Slice v1

SRAF 第一个真正实现的 Vertical Slice 应固定为：

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

# 105. Vertical Slice v1 的目标

不是提高排班算法性能。

而是证明：

```text
World Contract
→ Decision Contract
→ Existing Solver Adapter
→ Candidate
→ Evaluation
```

全链正确。

---

# 106. Vertical Slice v2

加入：

```text
Allocation Health
Gap
Diagnosis
Problem Router
```

目标：

> 当排班失败时，系统能判断是否应该继续 DP06，还是升级到 Coverage / Territory / Sizing。

---

# 107. Vertical Slice v3

加入：

```text
Coverage ↔ Scheduling
```

Iterative Coupling。

证明：

```text
Oracle feedback
artifact invalidation
stopping rule
```

---

# 108. Vertical Slice v4

加入简版：

```text
Territory Rebalancing
```

只需要：

```text
Baseline
Maintain
Simple Rebalance
Travel
Workload
Opportunity
ChangeCost
```

先不追求先进算法。

---

# 109. Vertical Slice v5

加入：

```text
Resource Location / Sizing
```

开始形成完整：

```text
Greenfield / Expansion
```

Composite Workflow。

---

# 110. 实施阶段建议

## Phase 0 — Contracts & Harness

目标：

```text
schemas
snapshot
decision case
problem projection
benchmark harness
```

先让所有核心对象可序列化、可测试。

---

## Phase 1 — Scheduling Reference Integration

目标：

```text
DP06 adapter
failure semantics
candidate interpreter
```

复用现有引擎。

---

## Phase 2 — Allocation Intelligence MVP

目标：

```text
5 diagnostic cases
problem router
false expansion benchmark
```

---

## Phase 3 — Structural Decision MVP

目标：

```text
DP03 baseline
maintain candidate
change cost
human override
```

---

## Phase 4 — Composite Decision

目标：

```text
Coverage ↔ Scheduling
Expansion
Greenfield
```

逐步增加 Coupling。

---

## Phase 5 — Production Validation

目标：

```text
shadow
pilot
decision validation
```

---

## 110A. v1 Engineering Envelope（Phase 0–3 规模与 SLA）

这不是系统上限声明，而是给 `DecompositionPlanner / SolverRegistry /
Projection Cache / Benchmark` 的工程契约：

> 在什么规模档位下，期待什么计算策略和响应时间。

| 档位 | Responsibility Units | Resources | 目标响应 | 典型场景 |
|---|---|---|---|---|
| **S — Interactive** | ≤ 5k | ≤ 50 | seconds | What-if、局部 Rebalance、DP06/DP07 |
| **M — City/Regional Planning** | 5k–50k | 50–300 | minutes | DP01/DP02/DP03 规划批次 |
| **L — Structural Batch** | 50k–200k | 300–1,000 | tens of minutes–hours | CP01/CP02 结构批处理 |

各 Phase 的最低承诺档位：

```text
Phase 0  Contracts        S（schema/snapshot 正确性优先，不设性能要求）
Phase 1  DP06 Reference   S 必达；M 尽力（报告 time-to-first-feasible）
Phase 2  Intelligence     S–M（Health/Gap/Router 全量派生，minutes）
Phase 3  Structural MVP   M 必达；L 允许 Iterative/Multi-stage 分解
```

计算策略随档位切换（必须显式声明 `evaluation_fidelity`）：

```text
S   精确 Solver 或高迭代 heuristic；全量 L2 Network Travel
M   CP-SAT/MILP + warm start；L1 粗筛 + L2 复评漏斗
L   Macro 聚合 → 分解求解 → Micro 回填；禁止天真 Joint；
    Travel 走预计算矩阵缓存（绑定 network_version）
```

工程含义：

1. Benchmark 规模测试（06 §55）的 reported scale 必须覆盖对应 Phase 档位上界，
   不得只在玩具实例报性能。
2. Projection Cache / Travel Matrix Cache 的内存与失效预算按 L 档容量设计。
3. 超出 L 档不视为 SRAF 失败，而是触发
   `Aggregation / Sampling Strategy` 评审（新增 ProblemProjection 语义，
   走 §84 版本策略）；在此之前不得静默降精度。

---
# 111. 不建议第一阶段做的工作

```text
自研通用 Workflow Engine
自研图数据库
自研路由引擎
自研 MILP Solver
复杂 RDF/OWL reasoner
端到端 LLM 决策
全国实时 Territory 自动重划
复杂多智能体社会
全量 MLOps 平台
```

这些都不是 SRAF v1.2 核心。

---

# 112. SRAF 自有核心资产

必须自己掌握：

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

这些才是 Framework 的真正 IP。

---

# 113. 优先复用资产

应优先集成：

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

成熟能力。

---

# 114. Agentic 架构原则

Agentic 不意味着：

> 所有模块都 Agent 化。

真正 Agentic 的地方是：

```text
理解 DecisionCase
组织 Evidence
提出 Hypothesis
选择允许的 Tool
创建 Scenario
比较 Candidate
与 Human 协作
```

而：

```text
constraint validation
capacity calculation
routing
MILP solve
snapshot semantics
```

应保持 deterministic / governed。

---

# 115. Deterministic Core + Agentic Shell

SRAF 推荐：

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

这是 v1.2 推荐架构。

---

# 116. 为什么不是“Agent 直接调用数据库 + Solver”

因为那会导致：

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

这与 SRAF 目标相反。

---

# 117. API / UI 不是 v1.2 核心

v1.2 首先做 Framework / Agent-callable APIs。

管理 UI、地图 UI 可以后续构建。

但输出对象应天然支持：

```text
map projection
candidate comparison
decision explanation
```

---

# 118. Territory Visualization

地图只是：

```text
TerritoryProjection
```

的视觉表达。

UI 不能通过拖 Polygon 直接修改 Canonical Territory。

拖动结果应生成：

```text
HumanOverride
```

或：

```text
CandidateChange
```

再重新评价。

---

# 119. Reference Deployment Example

最小生产架构可为：

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

不需要大量基础设施。

---

# 120. 架构演进条件

只有出现明确证据时再拆分：

### 独立 Graph DB

当：

```text
relationship traversal
```

成为主要性能瓶颈。

### 独立 Event Platform

当：

```text
event volume / integration
```

超出关系库能力。

### 分布式 Solver Platform

当：

```text
concurrent structural optimization
```

成为瓶颈。

### 独立 Workflow Platform

当：

```text
long-running workflows
human tasks
enterprise integration
```

证明现有能力不足。

---

# 121. Architecture Decision Record

所有重要技术选型建议使用：

```text
ADR
```

例如：

```text
ADR-001 Canonical State uses PostgreSQL
ADR-002 Graph is projection, not source of truth
ADR-003 Existing scheduling engine integrated via adapter
ADR-004 Modular monolith before microservices
```

避免后续团队不知道“为什么”。

---

# 122. 关键 Architecture Gates

出现以下设计，应原则上拒绝：

```text
Solver 直接读 Source System

Agent 直接写 Canonical World

Territory = Polygon table

Account.owner_id 作为唯一责任模型

Opportunity score 无 provenance

DecisionCase 无 Snapshot

Scenario 复制并修改生产状态

Decision Engine 自己计算一套不同指标

Solver-specific variable 写入 World schema

Problem Router 直接绑定 Solver

Workflow State 存在 Agent 对话中

HumanOverride 覆盖原 Candidate

Candidate 直接推送 SFA

Approval 后无 TransitionPlan

Benchmark 使用另一套业务 Schema

Graph 成为唯一 Source of Truth

新增基础设施却没有经过能力缺口验证
```

---

# 123. Definition of Done

`07_REFERENCE_ARCHITECTURE.md` 的第一阶段落地不能以：

> “服务框架搭好了”

为完成。

至少必须证明：

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

# 124. v1.2 Reference Architecture 最终收敛

SRAF 不应该被实现成：

```text
Territory SaaS
+
Scheduler
+
Agent Chatbot
```

而应该实现成：

# **Sales Resource Allocation Decision Infrastructure**

其真正稳定的核心是：

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

# 125. 与现有能力的最终关系

现有 `visit-scheduling-optimizer`：

```text
不是 SRAF
```

而是：

```text
SRAF 的第一个 Reference Decision Engine
```

未来 Territory、Sizing、Location、Coverage、Routing 也都遵循同样原则：

> **Engine 可替换，Decision Semantics 不可被 Engine 定义。**

---

# 126. 项目进入工程阶段的最低条件

当以下文档和 Vertical Slice 都具备后，才建议正式进入大规模实现：

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

此后算法扩展才有稳定上层语义。

---

# 127. v1.2 主架构结论

SRAF 最终不以某个算法作为中心，而以：

# `Decision Case`

作为系统的核心工作单元。

完整闭环：

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

这就是 SRAF v1.2 的 Reference Architecture 基线。
