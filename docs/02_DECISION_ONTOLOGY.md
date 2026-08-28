# SRAF Decision Ontology Specification v1.2

**项目：** Sales Resource Allocation Framework  
**简称：** SRAF  
**文档：** `02_DECISION_ONTOLOGY.md`  
**状态：** Implementation Baseline v1.2  
**上位规范：**

```text
00_PROJECT_CHARTER.md
01_WORLD_MODEL_SPEC.md
```

---

## 1. 文档目标

Decision Ontology 必须建立 World Model 与 Decision Engine 之间统一的业务语言。

核心链路：

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

因此 Decision Ontology 不描述：

```text
客户经纬度
员工姓名
门店地址
道路网络
```

这些属于 World Model。

它描述：

```text
哪里存在问题
问题为什么存在
问题是否值得解决
允许改变什么
有哪些候选方案
方案有什么影响
为什么选择某一个方案
如何实施
如何验证
```

---

## 2. Decision Ontology 的核心原则

Decision Ontology 必须遵循：

> **Problem before Solution.**

禁止：

```text
Territory Solver 发现更优结果
      ↓
创建一个“Territory Problem”
```

正确顺序：

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

即：

> Solver 不创造业务问题。

---

## 3. Decision 与 World State 分离

以下对象不属于 Canonical World Truth：

```text
DiagnosticHypothesis
DecisionCase
CandidateDecision
Scenario
CandidateTerritory
CandidateDeployment
SolverSolution
```

它们属于：

# Decision State

只有：

```text
Approved Decision
      ↓
Transition
      ↓
Confirmed World Event
```

以后，世界状态才真正改变。

---

## 4. Decision Ontology 一级对象

v1.2 固定以下一级对象：

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

这些对象共同形成一个完整 Decision Lifecycle。

---

## 5. AllocationHealth

`AllocationHealth` 表示：

> **当前销售资源配置状态在某个业务范围内的总体健康情况。**

它不是简单 Score。

结构：

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

Health 必须有明确 Scope。

例如：

```text
Market
Region
Territory
ResourcePool
Channel
CustomerSegment
Product
```

不能只有：

```text
health_score = 72
```

却不知道 72 指什么。

---

## 7. Health Metric

v1.2 至少允许：

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

这些大部分属于 Derived State。

Health 只是对这些 Derived State 的组合解释。

---

## 8. Health 不等于问题

例如：

```text
CapacityUtilization = 112%
```

只能说明：

```text
Metric abnormal
```

不能直接得出：

```text
Need 2 additional reps
```

因此：

\[
HealthSignal
\neq
DecisionProblem
\]

中间必须经过：

```text
Gap
Diagnosis
Materiality
```

---

## 9. AllocationGap

`AllocationGap` 是 Decision Ontology 的核心对象之一。

正式定义：

> **当前 Sales Resource Allocation 与某个业务要求、机会状态或可接受目标状态之间存在的可解释差异。**

统一结构：

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

v1.2 固定七类一级 Gap：

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

`02_DECISION_ONTOLOGY.md` 只定义七类 Gap 的上位语义。

`CoverageGap`、`CapacityGap`、`SpatialTravelGap` 等的进一步 subtype taxonomy 由 `04_ALLOCATION_INTELLIGENCE.md` 负责。

因此 02 不再重复维护另一套细分分类。

---

## 11. CoverageGap

表示：

> 业务需要的 Coverage 与可达到或实际完成的 Coverage 之间的差异。

例如：

\[
CoverageGap
=
RequiredCoverage
-
AchievableCoverage
\]

需要区分：

```text
PlannedCoverageGap
ActualCoverageGap
```

因为：

```text
计划本身不可行
```

和：

```text
计划合理但执行失败
```

是不同问题。

---

## 12. CapacityGap

表示：

\[
CapacityGap
=
RequiredResourceCapacity
-
AvailableResourceCapacity
\]

必须明确：

```text
ResourceType
Capability
Period
MarketScope
```

因此：

```text
整体不缺人
```

不意味着：

```text
不存在 CapacityGap
```

可能只是某类 Capability 缺失。

---

## 13. OpportunityGap

定义：

> **当前资源配置未能有效覆盖的可服务市场机会。**

不能写成：

```text
LostSales
```

因为 Opportunity 通常是 Estimate。

更准确的表达：

```text
UncoveredOpportunity
OpportunityAtRisk
IncrementalOpportunityGap
```

必须继承 OpportunityEstimate 的：

```text
confidence
model_version
evidence
```

---

## 14. SpatialTravelGap

回答：

> 资源是不是因为空间部署或责任划分不合理而浪费 Capacity？

例如：

```text
peer travel burden     18%
current territory      36%
```

或者：

```text
current base location
→ expected field capacity 91h

alternative location
→ expected field capacity 118h
```

这类问题原则上应该优先进入：

```text
ResourceLocation
TerritoryAlignment
```

而不是 Sizing。

---

## 15. CapabilityGap

表示：

\[
RequiredCapability
\not\subseteq
AvailableCapability
\]

例如：

```text
Available capacity = 120h
Required workload  = 90h
```

看似 Capacity 足够。

但：

```text
required capability = KA Negotiation
resource capability = Field Generalist
```

仍然不能完成责任。

---

## 16. LocalAllocationGap

`LocalAllocationGap` 表示：

> 全局 Demand 与 Supply 基本可行，但局部责任/资源配置不合理。

`AllocationGap` 保留为所有销售资源配置 Gap 的上位对象名称，禁止同时作为 subtype 名称。

例如：

```text
Total demand    = 4,200h
Total capacity  = 4,350h
```

总体够。

但是：

```text
Territory A = 126%
Territory B = 72%
Territory C = 83%
```

这属于：

```text
Local Allocation Mismatch / LocalAllocationGap
```

而不是：

```text
Global Capacity Shortage
```

---

## 17. StabilityGap

表示：

> Allocation 当前看起来可行，但改变频率或责任关系稳定性已经不可接受。

例如：

```text
Assignment changes / 12 months
Territory boundary changes
Rep transfers
Customer ownership changes
```

因此 Stable Allocation 本身也是一种价值。

---

## 18. Gap 可以同时存在

禁止假设：

```text
One symptom
=
One gap
```

例如：

```text
CoverageGap
+
CapacityGap
+
OpportunityGap
+
TravelGap
```

可以同时存在。

Decision Ontology 必须支持：

```text
GapSet
```

而不是强迫互斥分类。

---

## 19. DiagnosticHypothesis

Gap 只能说明：

> 哪里不对。

还不能说明：

> 为什么。

因此增加：

# `DiagnosticHypothesis`

定义：

> **针对一个或多个 Allocation Gap 的、可被证据支持或反驳的潜在原因解释。**

统一结构：

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

## 20. Hypothesis 不是 LLM 文本

例如禁止：

```text
reason =
“可能是人员不足，也可能是线路太远。”
```

而应该：

```text
Hypothesis H1
type = CapacityShortage
confidence = 0.31

Hypothesis H2
type = ExcessiveTravel
confidence = 0.82
```

并分别保存证据。

---

## 21. Root Cause Taxonomy

第一版至少包括：

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

`DataQualityIssue` 的身份侧 subtype 由本文件拥有
（判定规则与阈值见 `08` §10–§14）：

```text
IdentityDuplicate          同一对象多条未解析记录
IdentityFalseMatch         已被误并，覆盖被隐藏
IdentityUnresolved         候选未决，置信度上限受限
HierarchyMisattribution    Group 与其门店被重复计入
```

这四个 subtype 的意义在于：让 `04` 的 H-DATA 假设变成**可检验**的，
而不是一个兜底的垃圾桶标签。

---

## 22. EvidenceFor / EvidenceAgainst

这是 v1.2 强制要求。

例如：

```text
Hypothesis:
CapacityShortage
```

支持证据：

```text
utilization = 118%
missed required calls = high
```

反对证据：

```text
travel burden = 39%
peer travel burden = 20%
```

则可能：

```text
CapacityShortage confidence ↓

SpatialInefficiency confidence ↑
```

这避免 Agent 只收集支持自己结论的证据。

---

## 23. Diagnostic Status

建议：

```text
Proposed
Supported
Contested
Rejected
Confirmed
```

只有达到：

```text
Supported / Confirmed
```

并满足 Confidence Gate，才允许自动进入部分 Decision Workflow。

---

## 24. Data / Model Hypothesis 必须存在

任何异常都必须允许：

```text
DataQualityIssue
```

成为合法根因。

例如：

```text
customer coordinates wrong
travel matrix stale
potential model drifted
service time inflated
duplicate accounts
```

不能默认：

> 数据一定正确，业务配置出了问题。

---

## 25. MaterialityAssessment

即使 Gap 与 Root Cause 都成立，也不意味着值得行动。

正式定义：

> **衡量一个已识别 Allocation Problem 是否达到值得组织进行决策或结构调整的业务重要性。**

结构：

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

## 26. Materiality 主要考虑

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

不能只按：

```text
metric > threshold
```

触发。

---

## 27. Persistence

必须明确：

```text
DetectedAt
Duration
ObservationCount
```

例如：

```text
110% utilization for one week
```

与：

```text
110% utilization for four months
```

语义不同。

---

## 28. Materiality Level

v1.2 建议：

```text
Informational
Monitor
Review
Actionable
Critical
```

例如：

### Informational

记录，但不需要动作。

### Monitor

持续观察。

### Review

进入人工/Agent Diagnosis。

### Actionable

允许创建 DecisionCase。

### Critical

可进入快速响应流程。

---

## 29. DecisionTrigger

DecisionTrigger 不是简单报警。

正式定义：

> **在明确 Gap、Diagnosis、Materiality 与治理条件满足以后，用于创建 Decision Case 的业务规则。**

结构：

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

必须允许：

```text
EntryThreshold
ExitThreshold
```

例如：

```text
enter review:
utilization > 110% for 6 weeks

exit review:
utilization < 100% for 4 weeks
```

避免：

# Decision Flapping

---

## 31. Cooldown

结构调整之后必须允许：

```text
cooldown_period
```

例如：

```text
Territory realignment:
120 days
```

除非出现 Critical Trigger，否则不再次启动结构调整。

这保证 Stability。

---

## 32. DecisionCase

这是整个 Decision Ontology 的中心对象。

正式定义：

> **围绕一个明确业务资源配置问题建立的、包含 Baseline、Evidence、Diagnosis、Objectives、Candidate Decisions、Review 与 Validation 的完整决策单元。**

它是 Agent 最主要的工作对象。

---

## 33. DecisionCase Schema

建议：

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

沿用 Charter：

```text
Strategic
Structural
Tactical
Operational
Execution
```

一个 DecisionCase 可以包含多个 Atomic Decision Problem，但必须声明主要 Horizon。

例如：

```text
Expansion
```

可能包含：

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

建议：

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

状态必须显式。

不能使用：

```text
is_done = true
```

代替 Decision Lifecycle。

---

## 36. BusinessObjective

业务目标不能直接写成 Solver objective。

正式定义：

> **组织希望通过该 Decision Case 改善的业务结果。**

例如：

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

第一版支持：

```text
Primary
Secondary
Supporting
Diagnostic
```

而不是一开始强迫：

```text
weight = 0.23
```

因为很多权重并没有真实业务依据。

---

## 39. DecisionRequirement

这一抽象用于统一：

```text
Invariant
HardConstraint
Guardrail
Preference
```

结构：

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

定义：

> **业务世界或核心语义不允许违反的规则。**

例如：

```text
同一 exclusive Primary Responsibility
不能同时存在两个 active owner
```

或者：

```text
CandidateDecision
不能直接修改 Observed World
```

Invariant 原则上不可通过普通业务审批绕过。

---

## 41. HardConstraint

表示：

> **当前 Decision Problem 中不能违反的业务要求。**

例如：

```text
Distributor contractual boundary

Mandatory KA ownership

Regulatory service constraint
```

Hard Constraint 可以因 DecisionCase 不同而不同。

---

## 42. Guardrail

这是非常重要的中间语义。

例如：

```text
ReassignedRevenue <= 10%
```

可能原则上不希望超过。

但如果：

```text
business gain is extremely high
```

管理层可以审批例外。

因此 Guardrail：

```text
可以违反
但必须产生 Exception
并需要明确 Approval
```

---

## 43. Preference

表示：

> 在多个可行方案中倾向于更好的方向。

例如：

```text
lower travel
more compact
less churn
more balanced workload
```

Preference 不是业务事实。

也不是 Hard Constraint。

---

## 43A. RequirementExceptionProposal

当现有 Requirement 在当前 DecisionCase 中造成不可接受的业务冲突时，系统可以生成：

```text
RequirementExceptionProposal
```

它不是 Solver 自动 relax。

最小结构：

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

适用场景包括：

```text
temporary hard-constraint exception
guardrail exception
temporary policy exception
```

只有在原 `DecisionRequirement` 明确允许 exception，且满足审批权限后，Proposal 才能影响新的 Candidate / Problem Projection。

---

## 44. 为什么一定要四层

假设统一写成：

```text
constraint
```

开发人员很容易：

```text
经理说最好不要跨区
→ hard constraint
```

然后模型无解。

也可能：

```text
真正合同边界
→ soft penalty
```

产生违法业务方案。

所以必须先做 Semantic Classification。

---

## 45. DecisionProblem

DecisionProblem 正式定义：

> **在一个明确 DecisionCase 和 World Baseline 下，需要改变某些可控业务变量、同时满足 Requirements 并改善 Business Objectives 的决策问题。**

---

## 46. Atomic Decision Problem

v1.2 固定七类：

```text
DP01 ResourceSizing
DP02 ResourceLocation
DP03 ResponsibilityTerritoryAlignment
DP04 PersonnelMatching
DP05 CoverageChannelAllocation
DP06 VisitScheduling
DP07 DailyRouting
```

这里再次强调：

> Problem Type 是业务语义，不是 Solver Type。

---

## 47. AtomicProblem Contract

至少：

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

正式定义：

> **由多个 Atomic Decision Problems 共同构成的高层业务配置问题。**

第一版：

```text
CP01 DeploymentDesign
CP02 CapacityExpansion
CP03 StructuralRebalancing
CP04 CoverageExecutionDesign
```

---

## 49. Composite Problem 不拥有新业务变量

这是一个重要规则。

例如：

```text
CapacityExpansion
```

不是再创造一个：

```text
expansion_variable
```

而是编排：

```text
IncrementalSizing
Location
Territory
Personnel
```

已有 Atomic Problem 的变量。

---

## 50. CouplingMode

Composite Problem 必须声明：

```text
Independent
Sequential
Iterative
Joint
```

---

## 51. Independent

各 Atomic Problem 之间几乎没有实质依赖。

---

## 52. Sequential

例如：

```text
Coverage Commitment
      ↓
Visit Scheduling
```

前一结果是后一输入。

---

## 53. Iterative

例如：

```text
Territory Candidate
      ↓
Routing Evaluation
      ↓
Territory Improvement
```

循环直到：

```text
convergence
budget exhausted
no material improvement
```

---

## 54. Joint

数学层面联合求解：

```text
Sizing
+
Location
+
Territory
```

但输出仍必须恢复成三个独立业务 Decision Objects。

即：

> Mathematical jointness does not erase semantic boundaries.

---

## 55. CandidateDecision

Solver、Heuristic、Human、Rule Engine 或 Scenario 都可以产生：

# CandidateDecision

它不是正式 Decision。

结构：

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

例如：

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

这是 v1.2 强制 Candidate。

对于 Structural DecisionCase：

```text
Candidate A
=
Maintain Current State
```

原则上必须存在。

这样才能真正回答：

> 调整值得吗？

而不是：

> 哪个调整方案最好？

---

## 58. CandidateChange

每一个 Candidate 应明确表达：

```text
What changes?
```

而不是存一个黑盒 Solution Blob。

例如：

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

必须知道来源：

```text
Solver
Heuristic
Human
Rule
ImportedPlan
Baseline
Hybrid
```

如果来自 Solver：

```text
solver_id
solver_version
run_id
```

应进入 Provenance。

---

## 60. SolverSolution 与 CandidateDecision

两者不能合并。

```text
SolverSolution
      ↓
Decision Interpreter
      ↓
CandidateDecision
```

Solver 中可能：

```text
x_17_92 = 1
```

Candidate 中应该变成：

```text
Responsibility 92
assigned to
Deployment 17
```

---

## 61. DeltaEvaluation

所有 Structural/Tactical Candidate 应与 Baseline 比较。

正式定义：

> **描述 Candidate Decision 相对于 Baseline 在业务指标、风险、成本和稳定性上的变化。**

结构：

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

## 62. Delta 是核心，不是 Candidate Score

例如：

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| Opportunity Coverage | 81% | 87% | +6pp |
| Travel Burden | 24% | 19% | -5pp |
| Utilization Balance | 0.72 | 0.89 | +0.17 |
| Accounts Reassigned | 0 | 1,820 | +1,820 |
| Relationship Risk | 0 | High | ↑ |

不能只生成：

```text
Candidate Score = 87.3
```

---

## 63. ChangeCost

这是 Decision Ontology 的一级对象。

SRAF 将其进一步一般化。

---

## 64. ChangeCost Type

至少：

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

## 65. ChangeCost 允许定量与定性

例如：

```text
expected revenue impact = -¥500k
```

也可以：

```text
customer relationship risk = High
```

但都必须声明：

```text
estimate method
confidence
evidence
```

---

## 66. ChangeCost ≠ Penalty Weight

World/Decision Ontology 中表达：

```text
CustomerRelationshipRisk = High
```

Problem Compiler 以后可以映射成：

```text
penalty = ...
```

但 Ontology 本身不能存：

```text
lambda_disruption = 0.32
```

这种 solver-specific 参数。

---

## 67. Decision Evaluation Level

我建议所有 Candidate 使用三级评价：

```text
L1 Feasibility
L2 Efficiency
L3 Effectiveness
```

---

## 68. L1 Feasibility

回答：

> 方案能不能执行？

例如：

```text
Hard constraints satisfied
Capacity feasible
Personnel feasible
Scheduling feasible
```

---

## 69. L2 Efficiency

回答：

> 同样的资源投入是否更高效？

例如：

```text
Travel
Idle capacity
Route efficiency
Change cost
```

---

## 70. L3 Effectiveness

回答：

> 是否真正把资源投到了更值得的 Opportunity？

例如：

```text
Opportunity coverage
Incremental value
Strategic account protection
Growth support
```

因此：

\[
GoodDecision
\neq
BalancedTerritory
\]

更准确：

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

Candidate 不只是：

```text
expected improvement = 8%
```

还应该知道：

```text
confidence
```

例如：

```text
Opportunity model confidence = 0.58
Travel estimate confidence = 0.92
Relationship risk confidence = 0.41
```

Decision Evaluation 可以建立：

```text
DecisionConfidence
```

但禁止创造虚假的精确度。

---

## 72. UncertaintyModel

每个 Problem / Candidate 可以声明：

```text
Deterministic
ScenarioBased
Robust
Stochastic
```

例如：

```text
Potential Low / Base / High
```

分别评价 Candidate。

---

## 73. Scenario Robustness

Candidate 可以有：

```text
expected case
downside case
upside case
```

例如：

| Candidate | Low | Base | High |
|---|---:|---:|---:|
| Maintain | 80 | 81 | 82 |
| Add 2 Reps | 79 | 87 | 93 |
| Rebalance | 83 | 86 | 88 |

这会帮助管理层看到：

> 最大收益方案是否高度依赖 Opportunity Forecast。

---

## 74. HumanReview

Human-in-the-loop 必须成为正式 Decision Object。

结构：

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

SRAF 将其规范化为：

```text
Central Candidate
        ↓
Local Review
        ↓
Evidence / Exception
        ↓
Re-evaluation
```

而不是：

```text
经理拖地图
→ 直接覆盖模型
```

---

## 76. HumanOverride

正式定义：

> **人工对 Candidate Decision 进行明确修改，并记录原因、证据和预期影响。**

结构：

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

第一版可以包含：

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

## 78. Override 必须保留原 Candidate

不要：

```text
Candidate V1
被人工覆盖
```

而应该：

```text
Candidate V1
     ↓
HumanOverride
     ↓
Candidate V1.1
```

原始方案仍可追溯。

---

## 79. Approval

正式 Decision 必须来自：

```text
Candidate
      ↓
Approval
      ↓
ApprovedDecision
```

Approval 至少：

```text
approval_id
candidate_id
authority
decision
conditions
timestamp
```

例如：

```text
Approved
ApprovedWithConditions
Rejected
Deferred
```

---

## 80. ApprovedDecision

`ApprovedDecision` 是：

> **经治理流程确认、允许进入 Transition 的 CandidateDecision 的正式批准结果。**

标准链路：

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

`Decision` 只作为概念性总称，不作为与 `ApprovedDecision` 并列的第二套 canonical class。

结构至少包括：

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

一个 Target Allocation 正确，不代表：

> 明天全部切换。

因此：

# `TransitionPlan`

必须独立存在。

结构：

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

例如：

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

## 83. Structural Decision 与 Transition 必须分离

目标：

```text
T2027Q1
```

可能是最佳 Territory。

但如果需要：

```text
3个月客户交接
```

则：

```text
Target State
```

不能立即成为：

```text
Current State
```

---

## 84. Transition Event

Transition Plan 最终产生：

```text
World Events
```

例如：

```text
DeploymentActivated
ResponsibilityTransferred
CoverageCommitmentChanged
TerritoryActivated
```

然后才更新 World Model。

---

## 85. Rollback

大型结构调整必须允许：

```text
RollbackCondition
```

例如：

```text
Critical account loss
Service level collapse
Unexpected personnel loss
Data defect discovered
```

Rollback 本身也是一个新的 Decision / Transition。

不能直接数据库回滚。

---

## 86. DecisionValidationPlan

这是 SRAF 与传统 Optimization Project 拉开差距的关键对象。

正式定义：

> **在 Decision 实施前定义未来将如何使用真实执行结果判断这项决策是否有效。**

结构：

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

例如：

```text
Territory rebalancing
will reduce travel burden
without reducing high-potential coverage.
```

具体：

```text
Travel -10%
HighPotentialCoverage >= baseline
```

---

## 88. Validation Window

Structural Decision 不应该：

```text
实施第二天
```

就判断成败。

例如：

```text
30 days stabilization
+
90 days validation
```

应该由 Decision 类型声明。

---

## 89. Control / Comparison

当条件允许时，Validation 应支持：

```text
Before / After
Matched Control
Holdout Region
Staggered Rollout
A/B
Synthetic Control
```

具体采用哪一种属于 Benchmark Specification。

---

## 90. Decision Outcome

最终：

```text
DecisionOutcome

Expected
Observed
Delta

ValidationResult
Confidence
```

可以是：

```text
Validated
PartiallyValidated
Failed
Inconclusive
```

---

## 91. Failed Decision 不是系统异常

如果：

```text
DecisionFailed
```

但当初：

```text
Evidence
Assumptions
Decision Process
```

都是合理的，

它仍然是有价值的学习样本。

真正的问题是：

> 无法解释为什么当时做出这个 Decision。

---

## 92. LearningSignal

Decision Validation 可以生成：

```text
LearningSignal
```

例如：

```text
OpportunityModelOverestimated
TravelModelUnderestimated
ChangeCostIgnored
LocalKnowledgeMissing
CoverageResponseWeak
```

这些信号进入后续：

```text
Model Review
Policy Review
World Model Improvement
```

但不会让 Agent 自行修改核心 Ontology。

---

## 93. Problem Router

Allocation Intelligence 最终输出：

```text
DecisionCase
      ↓
ProblemRouter
```

第一版映射：

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

## 94. `WorldModelRepair` 为什么不属于 7 个 Decision Problem

因为：

```text
Data problem
```

不是 Sales Resource Allocation Decision。

因此：

```text
WorldModelRepair
```

属于 Governance Workflow（见 `05_DECISION_ORCHESTRATION.md` §14A，GW01）。

不能为了所有异常都塞进 Decision Problem Library。

同理：

```text
PotentialModelRetraining
```

属于 Model Governance（GW02）。

`Policy mismatch` 属于 Policy Review（GW03）。

三者都不占用 DP01–DP07 编号，不得注册为 Atomic Decision Problem，
也不得由 Solver 执行；它们的产出是**修正提案 + 治理决定**，不是资源配置 Candidate。

---

## 95. Decision Case Example

例如：

```text
CASE:
长沙河西高潜餐饮 Coverage Gap
```

可以表达：

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

这就是完整的 Decision Case。

---

## 96. Decision Case 与 Agent 的关系

Agent 的标准接口不应该是：

```text
给我一堆客户数据
```

而应该优先是：

```text
DecisionCase
```

Agent 查询：

```text
World Snapshot
Gap
Evidence
Hypothesis
Policy
Candidate
Evaluation
```

然后调用具体 Tool。

---

## 97. Agent 不拥有 Objective

Agent 不允许自行决定：

```text
“我觉得 workload fairness 最重要”
```

Objective 必须来自：

```text
BusinessObjective
DecisionPolicy
Human Decision
```

Agent 可以指出目标冲突。

不能擅自重新定义组织目标。

---

## 98. Agent 不拥有 Hard Constraint

同样禁止：

```text
LLM:
“这个区域看起来最好不要跨河。”
```

然后直接成为 Hard Constraint。

它最多可以生成：

```text
Candidate Diagnostic Hypothesis
```

或者：

```text
Proposed Preference
```

经过 Evidence / Human Review 后才能成为 Requirement。

---

## 99. Decision Ontology 核心关系图

最终核心关系可以表达为：

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

`02_DECISION_ONTOLOGY` 实现中，出现以下情况应该作为架构问题拒绝：

```text
Metric abnormal 直接等同 Decision Problem

AllocationGap 没有 Baseline / reference

Diagnosis 没有 Evidence Against

LLM 文本直接成为 Root Cause Truth

DecisionCase 没有 Baseline

Structural Decision 不包含 Maintain Candidate

Objective 直接保存 solver weight

Policy 与 Hard Constraint 不区分

Guardrail 被当成不可违反规则

Candidate Solution 直接等于 Decision

SolverSolution 直接成为 Candidate World State

Candidate 没有 Provenance

Candidate 只保存总分、不保存 Delta

Territory 调整不计算 ChangeCost

Human Override 静默覆盖原 Candidate

Human Override 不记录原因

Target State 与 Transition Plan 合并

Decision 实施前没有 Validation Plan

Solver Objective Improvement 被当作业务成功

Failed Decision 被删除

Agent 可以自由修改 Objective / Constraint
```

---

## 101. MVP 范围

为了防止 v1.2 做得过重，第一版 Decision Ontology 最少实现：

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

暂时可以简化：

```text
复杂 approval hierarchy
复杂 stochastic object
复杂 causal graph engine
自动 ontology learning
```

---

## 102. Definition of Done

Decision Ontology v1.2 不能以：

> 类和表已经创建

作为完成。

必须至少跑通这样一个真实 Case：

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

这条链完整跑通以后，Decision Ontology 才真正成立。

---

## 103. 与 `01_WORLD_MODEL_SPEC` 的最终边界

可以压缩成一句：

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

或者更加工程化：

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
