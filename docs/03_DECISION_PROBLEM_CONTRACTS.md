# SRAF Decision Problem Contracts Specification v1.2

**项目：** Sales Resource Allocation Framework  
**文档：** `03_DECISION_PROBLEM_CONTRACTS.md`  
**状态：** Implementation Baseline v1.2  

**上位规范：**
`00_PROJECT_CHARTER.md`、`01_WORLD_MODEL_SPEC.md`、`02_DECISION_ONTOLOGY.md`

---

## 1. 核心原则

任何 Decision Engine 都不能直接定义自己的业务问题：

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

Solver 接收的是已被业务语义定义清楚的问题，而不是一堆原始业务数据。

---

## 1A. Normative Ownership

本文件唯一拥有：

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

它引用 World / Decision / Workflow 对象，但不重新定义其 canonical schema。

---

## 2. Contract 必须回答的问题

每个 Contract 必须回答：

```text
1. 我在解决什么业务问题？
2. 当前世界状态是什么？
3. 哪些东西允许改变？
4. 哪些东西绝对不能改变？
5. 哪些规则必须满足？
6. 哪些只是优化倾向？
7. 什么样的结果才算可行？
8. 什么样的结果才算更好？
9. 输出怎样被解释回业务世界？
10. 如果失败，失败到底意味着什么？
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
    identity_snapshot_id:      # 所用身份决策集版本，见 08 §20
    min_identity_confidence:   # 低于此值的 subject 不得进入结构决策

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

## 4. ProblemProjection 是 Contract 与 Solver 的边界

WorldModel → ProblemProjection → SolverModel。

ProblemProjection 对世界进行目的限定的提取、聚合和转换，但不得改写 Canonical World。

---

## 5. Business Variable 与 Mathematical Variable 分离

Contract 声明业务变量，如 ResponsibilityAssignment、ResourceDeployment、CoverageCommitment 是否可改变。

`x[i,j]`、`y[k]`、`z[t]` 等只属于 Solver Model。

```text
Business Decision Variable
          ↓
Problem Compiler
          ↓
Mathematical Variable
```

求解后必须重新解释回业务对象。

---

## 6. Immutable Objects

每个 Contract 必须明确本次决策不允许改变什么。Solver 不得通过静默修改上游决策来“解决”本问题。

---

## 7. Feasibility 不等于 Optimality

先判断 Candidate 是否属于 FeasibleSet，再优化。Objective 好不能覆盖 Hard Constraint。

---

## 8. ProblemFeasibilityPrecheck

昂贵 Solver 前先检查显而易见的业务不可行性，例如 Required workload 显著高于 Available capacity 且 Coverage/Resource 均不可改变。

Precheck 的目的既是节省计算，也是区分“业务不可行”与“Solver/Model 出错”。

---

## 9. FeasibilityOracle

标准 Oracle：

```text
SchedulingFeasibilityOracle
RoutingFeasibilityOracle
PersonnelFeasibilityOracle
CapacityFeasibilityOracle
TravelFeasibilityOracle
PolicyFeasibilityOracle
```

Oracle 只返回可行性证据，不能自动修改 Candidate。

---

## 10. Infeasibility Taxonomy

禁止统一返回 `INFEASIBLE`。至少区分：

```text
F1 DATA_INFEASIBLE
F2 PROJECTION_INFEASIBLE
F3 POLICY_INFEASIBLE
F4 RESOURCE_INFEASIBLE
F5 STRUCTURAL_INFEASIBLE
F6 MODEL_INFEASIBLE
F7 SOLVER_FAILURE
```

`F1 DATA_INFEASIBLE` 的合法成因之一，
是 subject 身份未解析或存在被阻塞的身份冲突
（`08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §14）。
此时应路由 `GW01 WorldModelRepair`，
而**不得**在 `IdentityDuplicate` 未排除前
解释为 `F4 RESOURCE_INFEASIBLE`（假性缺人）。

Solver status 与 Business feasibility 分开：

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

分层为：

```text
Business Feasibility
        ↓
Model Feasibility
        ↓
Solver Success
```

---

# DP01 — Resource Sizing

## 11. 问题定义

> 当前市场机会与 Coverage Strategy 下，需要多少不同类型的销售资源？

Required Projection：

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

Mutable：

```text
ResourceRequirement
ResourceMix
ResourceEnvelope
```

Immutable by default：

```text
Market Definition
OpportunityEstimate
CoverageNeed
ResourceArchetype definition
```

Primary Objective：

```text
Maximize Addressable / Profitable Opportunity Coverage
```

Secondary：

```text
Minimize resource cost
Improve service level
Maintain utilization target
Reduce missed profitable coverage
```

Required Output：

```text
ResourceRequirement
ResourceCoverageFrontier
MarginalCapacityCurve
ExpectedUtilization
ExpectedOpportunityCoverage
ExpectedServiceLevel
UncertaintyRange
```

Sizing 默认 Frontier First，而不是只输出单点人数。

允许与 Coverage Allocation、Resource Location、Territory 进行 Iterative / Joint Coupling。

> **DP01 Prerequisite Gate（v1.2.1）**：销售努力对销量的影响存在跨期
> carryover（当年销量 = 当年努力 + 往年结转；见 CHANGELOG_v1.2.1）。
> 在 SalesResponseEstimate / OpportunityEstimate 契约中显式声明
> `impact_horizon` 与 `carryover_share`（或等效滞后参数）之前，
> **不得启动 DP01 Sizing Engine 的实现**；
> 否则边际产能曲线与 MarginalValue 会把往年努力的产出记入本年 Candidate 名下，
> Frontier 与增员建议系统性偏高。B4 Validation 亦必须声明
> `minimum_lag_window`，避免把滞后效应对错观察窗而误判 Failed。

---

# DP02 — Resource Location

## 12. 问题定义

> 销售能力应该部署在哪里？

Required Projection：

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

Mutable：

```text
ResourceDeployment.base_location
ResourceDeployment.capacity_commitment
DeploymentOpenCloseStatus
```

Immutable by default：

```text
Resource Headcount
Opportunity
Coverage
```

输出：

```text
CandidateDeployments
ExpectedTravelBurden
Reachability
ServiceReach
EffectiveCapacity
RelocationImpact
PersonnelFeasibility
```

需要同时支持 IdealDeployment 与 ExistingPersonnelFeasibleDeployment。

---

# DP03 — Responsibility / Territory Alignment

## 13. 问题定义

> 在既定 Resource Envelope 和 Coverage Context 下，销售责任应如何分配和组织？

Required Projection：

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

Mutable：

```text
ResponsibilityAssignment
TerritoryMembership
```


其中：

```text
TerritoryMembership
=
Territory ↔ Responsibility
```

不得将 `ResponsibilityAssignment` 当作 Territory membership；Assignment 只表示当前由谁承担 Responsibility。

Immutable by default：

```text
ResourceCount
CoveragePolicy
OpportunityEstimate
ResourceCapability
```

Invariants：

```text
Every mandatory responsibility is assigned
Exclusive primary responsibility has at most one active owner
Resource eligibility cannot be violated
Temporal overlap rules remain valid
```

Hard Constraints 可包含 Contractual distributor boundary、Mandatory KA ownership、Legal geography、Fixed personnel assignment。

Guardrails 可包含 Reassigned revenue、Account churn、Utilization 等，违反时必须 flag exception + impact + approval。

Preferences：

```text
lower travel
better workload balance
better opportunity coverage
greater spatial coherence
less disruption
```

Travel Evaluation Fidelity：

```text
L1 Geometric
L2 Network
L3 Routing Simulation
```

输出：

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

## 14. 问题定义

> 谁应该承担已经确定的 Resource Deployment / Territory Responsibility？

Required Projection：

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

Mutable：

```text
DeploymentAssignment
```

`ResourceDeployment` 表示需要被填充的部署位；`SalesResource` 表示实际能力实例；DP04 通过 `DeploymentAssignment` 将两者在时间上关联。

目标：

```text
Capability Fit
Location Fit
Relationship Continuity
Personnel Stability
Fairness
Retention Risk
```

禁止未经校正直接把 Raw Sales Performance 作为人员匹配核心目标；历史 performance 需要 territory-normalized 或明确局限。

---

# DP05 — Coverage & Channel Allocation

## 15. 问题定义

> 不同 Account / Opportunity 应该投入什么销售活动、多少努力、通过何种 Sales Resource / Channel 完成？

Required Projection：

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

Mutable：

```text
CoverageCommitment
ServiceChannel
ResourceTypeAllocation
ActivityMix
```

Coverage 必须支持：

```text
minimum
preferred
maximum
```

并调用 SchedulingFeasibilityOracle，避免 workload nominally feasible 但 temporal schedule infeasible。

输出需要表达多资源/多渠道服务，而不是单一 frequency。

---

# DP06 — Visit Scheduling

## 16. 问题定义

> 已经确定的 CoverageCommitment 应在具体周期/日期如何安排？

Required Projection：

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

Mutable：

```text
VisitPeriodAssignment
VisitDayAssignment
```

Immutable：

```text
Territory ownership
Coverage commitment
Resource location
Opportunity
```

目标：

```text
maximize committed visit feasibility
balance daily workload
respect spacing
reduce schedule instability
reduce travel burden
```

无法全部安排时必须输出：

```text
UnfulfilledCoverageCommitment
reason
severity
upstream implication
```

如果 monthly workload <= monthly capacity 但 schedule 无解，应识别 `TEMPORAL_STRUCTURAL_INFEASIBILITY`，而非 Global Capacity Shortage。

---

# DP07 — Daily Routing

## 17. 问题定义

> 已确定某日访问集合后，以什么顺序与路径执行？

Required Projection：

```text
DailyVisitSet
Start / End Location
TravelNetwork
TimeWindows
ServiceTimes
Vehicle / Mobility
BreakRules
```

Mutable：

```text
VisitSequence
Route
ArrivalTime
```

Immutable：

```text
Long-term Territory
Monthly Coverage
Cycle Assignment
```

输出：

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

Routing Engine 同时可作为 DP03/DP06 的 Feasibility Oracle。

---

# Composite Problems

## 18. CP01 Deployment Design

```text
Sizing + Location + Territory
```

Greenfield 常见，支持 Sequential / Iterative / Joint。

## 19. CP02 Capacity Expansion

```text
Incremental Sizing + Location + Territory + Personnel
```

核心评价是 IncrementalValue - ChangeCost。

## 20. CP03 Structural Rebalancing

```text
Territory + Personnel + ChangeCost
```

Baseline 与 Maintain Candidate 强制。

## 21. CP04 Coverage Execution Design

```text
Coverage + Scheduling + Routing
```

典型 Iterative Loop。

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

停止条件可使用 objective improvement、business delta、max iterations、runtime budget 等，不能只写 `until optimal`。

---

## 23. Solver Capability Contract

Decision Problem 不绑定 Solver，只声明 Capability Requirement：

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

维护 SolverRegistry；ProblemRouter 与 SolverSelector 分离。

---

## 24. Optimality Contract

Solver Result 必须明确：

```text
Exact Optimal
Provable Gap
Feasible Heuristic
Best Known Candidate
No Guarantee
```

Heuristic 不得在业务层声称 global optimum。

---

## 25. Candidate Explainability Contract

Candidate 至少回答：

```text
What changed?
Why did it improve?
Which objectives improved?
Which metrics got worse?
Which guardrails are close or violated?
Which assumptions matter most?
```

解释以 Structured Decision Evidence 为基础，LLM 只负责转成业务语言。

---

## 26. Evaluation Contract

Atomic Problem 必须声明 Primary、Secondary、Guardrail、Diagnostic Metrics。

跨 Problem 统一 Shared Evaluation Space：

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

每个 Problem Type 事先声明实施后的真实 Observation 验证指标。

---

## 28. Versioning / Reproducibility

Candidate 可追踪：

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

定义 ProblemRun 作为技术 Provenance 对象，一个 Run 可产生多个 Candidate。

Benchmark 与 Production 必须使用同一 Contract。

---

## 29. Shadow Decision / Dry Run

DryRun 只计算 Candidate，不进入 Execution。

ShadowDecision 不执行，但继续使用未来真实 Observation 验证预测、可行性和诊断稳定性。

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

禁止 Solver infeasible 后自动把 Hard Constraint 变 soft。若允许放松，必须产生 ConstraintRelaxationProposal 并审批。

---

## 31. Reference Engine — visit-scheduling-optimizer

注册：

```text
engine_id: visit-scheduling-optimizer
supported_problem: DP06 VisitScheduling
oracle_capabilities: SchedulingFeasibilityOracle
```

标准输入来自 VisitSchedulingProblemProjection。

标准输出至少包括：

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

原则上拒绝：

```text
Solver 直接查询全部 World Model
Solver 自己解释业务字段
Business Decision Variable 与数学变量混用
一个 Problem 静默修改上游决策
Scheduling 自动改变 Coverage
Territory 自动改变 Headcount
无 Precheck 直接跑昂贵 Solver
所有 infeasible 返回同一状态
Solver timeout 被解释为业务无解
Policy conflict 被解释为数学无解
资源不足被当成 Territory Solver failure
Hard constraint infeasible 后自动 soft relaxation
Heuristic candidate 被称为 global optimum
Candidate 只保存 objective score
没有 Baseline delta
没有 optimality claim
没有 run provenance
Benchmark 与 production 使用不同 contract
Solver-specific 数据写回 World Model
```

---

## 33. MVP 顺序与 DoD

第一条 Vertical Slice：

```text
World Model
→ CoverageCommitment
→ DP06 VisitSchedulingProblem
→ ProblemProjection
→ visit-scheduling-optimizer
→ CandidateSchedule
→ Evaluation
```

第二条增加 Allocation Health / Gap / Diagnosis / Problem Routing。

第三条实现 DP03 简版 Territory Rebalance。

至少演示五类 Case：

```text
Business Feasible
Resource Infeasible
Temporal Structural Infeasible
Solver Failure
Policy Infeasible
```

并正确分类。
