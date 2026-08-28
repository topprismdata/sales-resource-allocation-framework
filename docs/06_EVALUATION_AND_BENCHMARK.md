# SRAF Evaluation & Benchmark Specification v1.2

**项目：** Sales Resource Allocation Framework  
**简称：** SRAF  
**文档：** `06_EVALUATION_AND_BENCHMARK.md`  
**状态：** Implementation Baseline v1.2  

**上位规范：**

```text
00_PROJECT_CHARTER.md
01_WORLD_MODEL_SPEC.md
02_DECISION_ONTOLOGY.md
03_DECISION_PROBLEM_CONTRACTS.md
04_ALLOCATION_INTELLIGENCE.md
05_DECISION_ORCHESTRATION.md
```

---

## 1. 文档目标

SRAF 的评价目标不是证明：

> “Solver 能跑出一个结果。”

而是证明整个决策链：

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

在语义、诊断、数学、决策和业务结果五个层面都具有可验证性。

因此 SRAF v1.2 固定五级 Benchmark：

```text
B0 Semantic Correctness
B1 Diagnostic Correctness
B2 Mathematical / Solver Correctness
B3 Decision Quality
B4 Business Outcome Validation
```

并增加一个贯穿所有层级的横向维度：

```text
G — Governance / Auditability / Safety
```

---

## 2. 为什么不能只做 Solver Benchmark

一个销售资源配置系统可能出现：

```text
Solver status = OPTIMAL
```

但业务决策仍然错误。

例如：

- 把 Coverage Policy 问题误诊为 Headcount Shortage；
- 将错误经纬度导致的 Travel Gap 当成 Territory Gap；
- 数学上更平衡，但大量高价值客户被换负责人；
- Candidate objective 改善 2%，但 ChangeCost 高于收益；
- 历史回测使用了当时尚未知的数据，产生 Look-ahead Bias；
- 周期 workload 可行，但真实日期约束导致 Scheduling 无解；
- Territory 更紧凑，但道路网络导致实际 Travel 更差。

因此：

\[
SolverCorrectness
\neq
DecisionCorrectness
\]

更不等于：

\[
BusinessOutcomeImprovement
\]

---

## 3. Benchmark 总体架构

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

任何高层 Benchmark 失败，都必须能够下钻到低层。

---

# Part I — B0 Semantic Correctness

## 4. B0 的目标

B0 回答：

> **SRAF 是否正确表达了销售世界与决策世界？**

它不测试“方案好不好”。

它测试：

- Entity 是否具有正确 identity；
- Time 是否正确；
- Fact / Estimate / Assumption 是否区分；
- Responsibility 是否被错误压扁成 `owner_id`；
- Territory 是否被错误等同 Polygon；
- Scenario 是否污染 Observed World；
- Candidate 是否被错误写成 World Truth；
- Solver-specific fields 是否污染 Canonical Model。

---

## 5. B0 必须达到的原则

以下属于 Critical Semantic Invariant：

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

I20–I30（Canonical Identity 与实体解析）由
`08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §21 拥有，
同样属于 Critical Semantic Invariant：违反则 B0 直接失败。
其配套 Benchmark Case Family `ID01–ID20`、指标
（FalseMatchRate / BlockingRecall / UnmergeRate /
IdentityConfoundedGapRate / ReplayIdentityLeakageRate）
与 Identity Gate 见 08 §23。

Critical Invariant 违反时：

> Benchmark 直接失败，不进入更高层评价。

> 注：本文件 §6 Test 6.1–6.3 只规定「必须测什么」；
> 判定规则、阈值语义（错误率上界 λ/π）与人工权限矩阵由 08 规定。

---

## 6. Entity Identity Tests

至少测试：

### Test 6.1 — Multi-source Identity

同一客户存在：

```text
CRM_ID = 1001
ERP_ID = C882
External_POI_ID = POI_991
```

应解析到同一：

```text
CanonicalAccount
```

但保留三个 ExternalIdentifier。

---

### Test 6.2 — Source ID Collision

两个系统均存在：

```text
ID = 1001
```

但真实实体不同。

Canonical ID 不允许冲突。

---

### Test 6.3 — Location Change

同一 Account 搬迁：

```text
ServiceLocation A
→
ServiceLocation B
```

Account identity 不应改变。

---

## 7. Responsibility Semantic Tests

必须验证：

```text
Account A
Selling → Rep 1
Merchandising → Rep 2
KA Negotiation → KAM 3
```

能够同时成立。

系统不得将其压缩成：

```text
Account A owner = Rep1
```

---

## 7A. Resource Deployment Semantic Tests

必须验证：

```text
ResourceDeployment may exist while vacant
SalesResource may exist without being assigned to a deployment
DeploymentAssignment is temporal
Person.home_location does not equal Deployment.base_location
```

Greenfield Case 中应允许：

```text
ResourceRequirement
→ ResourceDeployment(planned/vacant)
→ later Personnel Matching
```

---

## 8. Territory Semantic Tests

至少测试：

### Geographic Territory

连续地理区域。

### Non-contiguous KA Territory

```text
Beijing
Shanghai
Guangzhou
Chengdu
```

仍然必须是合法 Territory。

### Overlay Territory

Field / KA / Merchandising / Product Specialist 同时存在。

如果 Ontology 无法表达，则 B0 失败。

---

## 9. Temporal Correctness

必须测试 Bitemporal 行为。

案例：

```text
Actual store close date:
2026-08-01

System learned:
2026-08-12
```

查询：

```text
knowledge_time = 2026-08-05
```

不得看到“门店已经关闭”的未来信息。

---

## 10. Look-ahead Leakage Test

历史 Decision Replay 必须使用：

```text
known_at <= decision_time
```

禁止使用：

```text
future closure
future sales
future opportunity label
future road update
future account correction
```

这是 B0 与 B4 历史回测共同的强制 Gate。

---

## 11. Scenario Isolation Test

创建：

```text
Scenario:
+6 resources
```

必须验证：

```text
Observed World resource count unchanged
```

Scenario 被删除后不能残留：

```text
Deployment
Assignment
CoverageCommitment
Territory
```

等状态。

---

## 12. Candidate Isolation Test

Solver 产生：

```text
CandidateTerritory V1
```

Canonical World 中 active Territory 不应变化。

只有：

```text
Candidate
→ Approval
→ Transition
→ Event
```

之后才允许改变。

---

## 13. Semantic Status Tests

同一业务陈述必须允许不同状态：

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

例如：

```text
Account A potential = High
```

如果来自模型，应标记：

```text
ModelEstimate
```

不能变成：

```text
MasterDataFact
```

---

## 14. Provenance Completeness

以下对象至少需要 Provenance：

```text
OpportunityEstimate
TravelEstimate
RelationshipStrengthEstimate
DerivedWorkload
AllocationGap
CandidateDecision
ProblemRun
```

Benchmark 报告：

```text
ProvenanceCompletenessRate
```

Critical production objects 原则上要求完整。

---

## 15. B0 Property-based / Metamorphic Tests

建议加入属性测试。

### Input Order Invariance

改变输入记录顺序，不应改变 deterministic semantic result。

### ID Relabeling Invariance

仅重新命名内部测试 ID，不应改变决策语义。

### Scenario Isolation

Scenario changes must not mutate baseline.

### Graph Rebuild

删除 Graph Projection 后，应能由 Canonical State 重建。

### Snapshot Immutability

已建立 WorldSnapshot 后，原引用状态不得被静默修改。

---

# Part II — B1 Diagnostic Correctness

## 16. B1 的目标

B1 回答：

> **系统是否正确判断“到底是什么问题”？**

这是 SRAF 与普通 Territory Optimizer 最重要的 Benchmark 层之一。

必须特别防止：

```text
销售跑不过来
→ 缺人
```

这种未经诊断的直接跳跃。

---

## 17. B1 Benchmark 的 Ground Truth

真实业务数据中 Root Cause 往往没有绝对 Ground Truth。

因此 B1 使用三类真值：

```text
T1 Constructed Ground Truth
T2 Expert-adjudicated Ground Truth
T3 Outcome-supported Ground Truth
```

---

## 18. T1 Constructed Ground Truth

通过 synthetic / semi-synthetic 数据主动制造问题。

例如：

```text
保持总 Capacity 不变
只将 Territory 负载人为打乱
```

那么 Ground Truth：

```text
AllocationImbalance
```

是已知的。

这种 Benchmark 最适合验证 Problem Router。

---

## 19. T2 Expert-adjudicated Ground Truth

对于历史真实案例，由多个业务/OR专家独立判断：

```text
Primary Root Cause
Contributing Causes
Not Supported Causes
```

若专家不一致：

```text
Contested
```

而不是强造唯一标签。

---

## 20. T3 Outcome-supported Ground Truth

例如历史上：

```text
没有增员
只调整 Territory
```

之后 Gap 显著下降。

这可以作为：

```text
TerritoryImbalance
```

的支持证据。

但不能视为严格因果真值，除非实验设计足够强。

---

## 21. B1 Canonical Benchmark Cases

v1.2 至少固定以下 Case Family。

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

构造：

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

期望：

```text
Primary route:
DP01 ResourceSizing / CapacityExpansion
```

---

## 23. D02 — Local Territory Imbalance

构造：

```text
Global capacity >= demand

T1 = 130%
T2 = 65%
T3 = 80%
```

Travel 正常。

期望：

```text
Primary:
DP03 TerritoryAlignment
```

而不是 DP01。

---

## 24. D03 — Resource Location Mismatch

构造：

```text
Total intrinsic workload feasible

Current base location far from demand

Travel burden = 38%
Peer = 18%
```

替代驻点释放：

```text
+0.6 RE
```

期望：

```text
DP02 ResourceLocation
```

---

## 25. D04 — Coverage Policy Over-allocation

构造：

```text
low opportunity accounts
consume large field capacity
```

Coverage stress scenario：

```text
workload -20%
opportunity coverage -2%
```

期望：

```text
DP05 CoverageAllocation
or
PolicyReview
```

而不是加人。

---

## 26. D05 — Capability Mismatch

构造：

```text
Total capacity = sufficient
KA eligible capacity = insufficient
Generalist idle capacity = high
```

期望：

```text
DP04 PersonnelMatching
or
ResourcePool / capability action
```

---

## 27. D06 — Temporal Scheduling Infeasibility

构造：

```text
Monthly workload <= monthly capacity
```

但：

```text
Tuesday-only
spacing
time windows
fixed-area day
```

冲突。

期望：

```text
DP06 VisitScheduling
TEMPORAL_STRUCTURAL_INFEASIBILITY
```

不能诊断为 Global Capacity Shortage。

---

## 28. D07 — Daily Routing Inefficiency

构造：

```text
Daily stop set is feasible
```

但随机差序导致：

```text
travel +40%
```

期望：

```text
DP07 DailyRouting
```

---

## 29. D08 — Data Quality Corruption

例如：

```text
20% coordinates shifted
duplicate accounts inserted
stale service times
```

期望：

```text
WorldModelRepair
```

不能触发 Structural Decision。

---

## 30. D09 — Model Quality Error

数据正确，但：

```text
Opportunity model systematically
overpredicts remote accounts
```

期望：

```text
ModelGovernance
```

---

## 31. D10 — Policy Conflict

两条 Hard Policy 无法同时满足。

期望：

```text
POLICY_INFEASIBLE
PolicyReview
```

而不是 Solver Failure。

---

## 32. D11 — Temporary Seasonal Overload

构造：

```text
4-week promotion spike
```

历史季节模式说明之后恢复。

期望：

```text
TemporaryGap
Monitor / temporary support
```

而不是 Territory Realignment。

---

## 33. D12 — High ChangeCost / Maintain Preferred

构造：

Candidate：

```text
Travel -3%
Opportunity +1%
```

但：

```text
40% key accounts reassigned
relationship disruption high
```

期望：

```text
MaintainCurrentState
```

至少应该保留为强候选。

---

## 34. D13 — Mixed Cause

例如：

```text
Capacity shortage 40%
Travel inefficiency 35%
Territory imbalance 25%
```

系统应允许：

```text
Primary
Contributing
Alternative
```

而不是强迫一个唯一标签。

---

## 35. D14 — Insufficient Evidence

当：

```text
Opportunity confidence low
travel data stale
```

期望：

```text
RequestMoreEvidence
```

而不是硬给 Root Cause。

---

## 36. B1 核心指标

至少报告：

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

定义：

> 本不需要新增资源的 Case 中，被错误建议进入 Expansion 的比例。

这是 SRAF v1.2 强制报告指标。

因为：

```text
忙
→ 加人
```

是销售资源配置中高成本的典型误诊。

---

## 38. False Structural Trigger Rate

定义：

> 临时、数据、模型或执行问题，被错误升级为 Structural Decision 的比例。

尤其测试：

```text
seasonality
promotion
temporary absence
bad data
route delay
```

---

## 39. Confidence Calibration

如果系统输出：

```text
TerritoryImbalance confidence = 0.8
```

长期来看，类似置信区间的判断质量应与真实正确率大致一致。

v1.2 不要求复杂概率校准模型，但必须避免：

> 所有结论都 0.9 以上。

---

# Part III — B2 Mathematical / Solver Correctness

## 40. B2 的目标

B2 回答：

> **在 Decision Problem 已经被正确框定后，数学模型和 Solver 是否正确解决了这个问题？**

这里必须严格区分：

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

手工可计算。

例如：

```text
2 resources
4 accounts
simple workload
known travel
```

人工知道唯一最优解。

要求：

```text
model result == analytical result
```

适合检查：

```text
constraint encoding
objective direction
unit conversion
```

---

## 43. M1 — Exact Small Instances

对小规模问题使用 Exact Solver 得到：

```text
OptimalSolution
```

然后比较：

```text
Heuristic
CP-SAT
Local Search
Metaheuristic
```

的 gap。

---

## 44. Optimality Claim Test

如果 Engine 声称：

```text
OPTIMAL
```

必须有 Solver proof / exact certificate 或框架认可的证明。

Heuristic 不允许标记：

```text
optimal
```

只能：

```text
FEASIBLE_HEURISTIC
BEST_KNOWN
BOUNDED_GAP
```

---

## 45. Feasibility Preservation

任何 Candidate 必须重新执行独立 Validation：

```text
InvariantChecker
HardConstraintChecker
```

不能只相信 Solver 自己报告。

---

## 46. Independent Constraint Checker

建议 Solver Model 之外实现独立：

```text
CandidateConstraintValidator
```

用于验证：

```text
coverage
assignment cardinality
capacity
boundary
eligibility
temporal overlap
```

这样可发现 Model Encoding Bug。

---

## 47. Infeasibility Classification Benchmark

必须专门测试：

```text
DATA_INFEASIBLE
PROJECTION_INFEASIBLE
POLICY_INFEASIBLE
RESOURCE_INFEASIBLE
STRUCTURAL_INFEASIBLE
MODEL_INFEASIBLE
SOLVER_FAILURE
```

目标不仅是“发现无解”，还要：

> 分类正确。

---

## 48. Solver Failure ≠ Business Infeasible Test

人为设置：

```text
runtime = 1 ms
```

使 Solver timeout。

系统必须返回：

```text
SOLVER_FAILURE / TIME_LIMIT
```

不能返回：

```text
RESOURCE_INFEASIBLE
```

---

## 49. Policy Conflict Test

构造 mutually exclusive hard policies。

Precheck / policy checker 应在 Solver 前发现。

目标：

```text
solver_not_called = true
```

---

## 50. Resource Infeasibility Test

构造：

```text
required workload = 1000
capacity = 500
coverage immutable
```

应在 Precheck 阶段识别。

---

## 51. Structural Infeasibility Test

全局资源够，但由于：

```text
boundary
capability
location
```

局部无解。

要求与 Global Capacity Shortage 区分。

---

## 52. Mathematical Metamorphic Tests

在满足适用条件时测试。

### Record Order Invariance

输入顺序变化不改变 deterministic optimum。

### Label Permutation Invariance

资源 ID / Account ID 置换后，结果应同构。

### Constraint Relaxation Monotonicity

仅放松 constraint 时，最优目标不应变差。

### Optional Capacity Monotonicity

在“新增 capacity 可选择不用”的模型中，增加可用 capacity 不应降低最佳可达 objective。

### Feasible-set Restriction

新增 Hard Constraint 后，原 infeasible candidate 不得仍被判定 feasible。

---

## 53. Random Seed Reproducibility

Heuristic / metaheuristic：

```text
same snapshot
same projection
same code
same params
same seed
```

应可复现同一结果或定义的 deterministic trace。

---

## 54. Stochastic Stability

不同 seed：

```text
N runs
```

报告：

```text
best
median
P90 runtime
objective distribution
constraint violation rate
```

不能只展示最好的一次。

---

## 55. Scale Benchmark

每个 Solver Adapter 必须声明测试规模。

例如：

```text
accounts:
1k / 10k / 50k / 100k

resources:
10 / 50 / 200 / 500
```

报告：

```text
runtime
memory
feasible time
final gap
candidate quality
```

reported scale 必须覆盖 `07_REFERENCE_ARCHITECTURE.md` §110A
v1 Engineering Envelope 中对应实施 Phase 的档位上界（S/M/L），
不得只在玩具实例报告性能。
---

## 56. Time-to-First-Feasible

对于业务交互尤其重要。

不仅报告：

```text
time to final
```

还应报告：

```text
time_to_first_feasible
```

因为季度规划与 Interactive What-if 对响应时间要求不同。

---

## 57. Oracle Correctness

Feasibility Oracle 本身也需要 Benchmark。

例如 Scheduling Oracle：

```text
Oracle says FEASIBLE
```

之后完整 Scheduler 应能实际生成可行 schedule。

统计：

```text
FalseFeasibleRate
FalseInfeasibleRate
```

---

## 58. Multi-fidelity Correlation

例如 Territory：

```text
L1 compactness
L2 network travel
L3 routing simulation
```

应测量：

> L1 / L2 对 L3 的排序相关性。

如果 L1 与真实 Routing 几乎无关，就不能作为有效筛选 Proxy。

---

## 59. Solver Adapter Contract Test

每个 Solver Adapter 必须通过：

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

一致性测试。

---

# Part IV — B3 Decision Quality

## 60. B3 的目标

B3 回答：

> **即使 Solver 正确，这个 Candidate 相对于 Baseline 是否是值得采用的业务决策？**

核心原则：

```text
Candidate
≠
Decision
```

以及：

```text
better mathematical score
≠
worth changing
```

---

## 61. B3 必须始终有 Baseline

Structural / Tactical Decision 至少比较：

```text
Baseline
MaintainCurrentState
Candidate A
Candidate B
...
```

如果没有 Baseline：

> B3 无法通过。

---

## 62. Shared Decision Evaluation Space

不同 Problem 产生的 Candidate 应映射到共享指标：

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

## 63. 不允许默认 Universal Score

Benchmark 默认输出：

```text
metric profile
objective attainment
guardrail status
trade-offs
```

不强制：

```text
DecisionScore = 86.3
```

如果具体项目使用 weighted score，必须：

```text
document weight source
run sensitivity analysis
```

---

## 64. B3 Feasibility

首先：

```text
Invariant satisfied
Hard constraints satisfied
```

否则：

```text
Candidate rejected
```

不进入后续优劣比较。

---

## 65. Guardrail Evaluation

Candidate 可以违反 Guardrail，但必须：

```text
flag
quantify impact
require exception review
```

Benchmark 检查：

> Guardrail violation 是否被正确显式暴露。

---

## 66. ChangeCost Evaluation

至少覆盖：

```text
Account reassignment
Revenue reassignment
Customer relationship risk
Personnel relocation
Learning / handover
Transition effort
```

没有 ChangeCost 的 Structural Candidate 不允许声称：

> “业务更优”。

---

## 67. Decision Regret

在 Scenario / historical replay 中可以计算：

\[
Regret
=
Value(BestAvailableDecision)
-
Value(ChosenDecision)
\]

尤其用于比较：

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

对于：

```text
Low / Base / High
```

Opportunity Scenario，Candidate 应报告：

```text
downside
base
upside
```

避免选出只在单一预测点上表现极好的脆弱方案。

---

## 69. Robustness Metric

可以报告：

```text
WorstCasePerformance
ScenarioVariance
ProbabilityOfGuardrailViolation
OpportunityCoverageP10
```

具体是否使用概率取决于 Uncertainty Model。

---

## 70. Stability vs Gain Frontier

Structural Candidate 建议画：

```text
Business Gain
      ↑
      │      C
      │   B
      │ A
      └────────────→ Change / Disruption
```

让管理层看到：

> 为了多 2% Opportunity Coverage，需要牺牲多少稳定性。

---

## 71. Maintain Decision Benchmark

专门构造：

```text
small theoretical improvement
high disruption
```

确保系统能够选择：

```text
MaintainCurrentState
```

而不是“只要运行优化器就一定变”。

---

## 72. Cross-Problem Alternative Benchmark

同一个 DecisionCase 必须允许比较：

```text
Territory Rebalance
Add Resource
Coverage Adjustment
Resource Relocation
Hybrid
Maintain
```

这是 SRAF 判断能力是否超越单一 Solver 的重要 Benchmark。

---

## 73. Feasibility Oracle in B3

最终 Candidate 应通过适当下游验证。

例如 Territory：

```text
PersonnelFeasibility
SchedulingFeasibility
RoutingEvaluation
```

如果高层 Candidate 在 downstream 无法执行：

> Decision Quality 不合格。

---

## 74. Multi-fidelity Candidate Funnel Benchmark

检查：

```text
Generate N
→ L1 shortlist
→ L2 shortlist
→ L3 final
```

是否会过早淘汰真正优质 Candidate。

报告：

```text
TopKRecall
```

---

## 75. Human Override Quality

人工 Override 后：

```text
Candidate V1
→ HumanOverride
→ Candidate V1.1
```

必须重新评价。

Benchmark 检查：

```text
feasibility
objective delta
change cost
guardrail
```

是否全部刷新。

---

## 76. Local Knowledge Value

长期可比较：

```text
Central Candidate
vs
Local Adjusted Candidate
```

在实际结果中的表现。

用于回答：

> 哪些类型 Local Override 真正增加价值？

---

## 77. Override Harm Rate

同时需要检测：

> 人工 Override 是否反而破坏方案。

可报告：

```text
OverrideBenefitRate
OverrideHarmRate
OverrideNeutralRate
```

这不是为了消灭人工，而是形成 Evidence。

---

## 78. Decision Explainability Benchmark

每个 Candidate 至少能回答：

```text
What changed?
Why?
What improved?
What worsened?
Which assumptions matter?
Which guardrails are close?
What evidence supports this?
```

Benchmark 检查 Structured Evidence 是否完整。

---

## 79. Counterfactual Sensitivity

改变关键假设：

```text
Opportunity ±10%
Travel +20%
ServiceTime +15%
ChangeCost ×2
```

观察 Candidate ranking 是否剧烈变化。

如果是：

```text
DecisionSensitivity = HIGH
```

必须向审批人展示。

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

## 81. B4 的目标

B4 回答：

> **决策真正实施后，业务是否按照预期改善？**

这是 SRAF 的最终证据层。

Solver Objective 不能替代 B4。

---

## 82. DecisionValidationPlan 必须事前定义

实施前就应记录：

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

不能看到结果以后再挑指标。

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

Structural Decision 通常先验证 Leading，再等待 Lagging。

---

## 84. Validation Design Hierarchy

从证据强度由弱到强：

```text
V0 Before / After
V1 Matched Comparison
V2 Difference-in-Differences
V3 Staggered Rollout
V4 Randomized / A-B where feasible
V5 Replicated Multi-market Evidence
```

不是所有 Territory 决策都适合 Randomized Test。

但必须尽量提高证据强度。

---

## 85. Before / After 的局限

简单：

```text
Before
vs
After
```

容易受到：

```text
seasonality
promotion
competitor action
macro changes
personnel turnover
```

影响。

所以只适合作为低强度证据。

---

## 86. Matched Control

选择业务特征接近、未调整的区域作为比较。

匹配变量可能：

```text
market size
channel mix
opportunity
historical growth
seasonality
resource level
```

参考实证：Zoltners / Sinha / Lorimer, *Sales Force Design for Strategic
Advantage* (2004), Table 8.3 —— 某工业分销商以 test（realignment 后更换
负责人）vs control（未更换）账户组测量 disruption 冲击，结果显示影响
**仅集中于中等体量账户**（$50–100k），小账户与超大账户均不显著。

两点规范性含义：

```text
1. Matched Control 在销售区域决策中真实可行（V1 证据不是纯理论）。
2. ChangeCost.CustomerRelationshipCost 必须按 account size /
   relationship strength 分段估计，
   禁止使用单一全局 disruption 系数（见 §66、02 §64–65）。
```

---

## 87. Difference-in-Differences

当存在处理组与对照组，并满足合理趋势条件时，可比较：

\[
(After-Before)_{Treatment}
-
(After-Before)_{Control}
\]

用于降低共同外部冲击影响。

---

## 88. Staggered Rollout

对于多城市推广，可以：

```text
City A first
City B later
City C later
```

既控制实施风险，又形成更好的 Validation Evidence。

---

## 89. A/B 的适用边界

适合：

```text
Coverage strategy
sales cadence
some routing/scheduling policy
```

但 Territory 结构调整存在：

```text
spillover
manager interaction
customer overlap
```

因此不能机械套用店级 A/B。

---

## 90. Interference / Spillover

Sales Territory 决策天然存在跨区域影响。

例如：

```text
Rep A territory shrinks
```

可能使：

```text
Rep B workload grows
```

所以实验设计必须考虑：

> Treatment Unit 不一定是 Account。

可能是：

```text
territory
district
city
region
```

---

## 91. Stabilization Window

结构调整后通常需要：

```text
handover
learning
relationship rebuilding
```

因此应区分：

```text
Transition
Stabilization
Validation
```

不能把过渡期直接当最终效果。

---

## 92. Validation Outcome

统一：

```text
Validated
PartiallyValidated
Failed
Inconclusive
```

`Inconclusive` 是合法结果。

不能为了闭环强迫所有 Decision：

```text
success / failure
```

二元化。

---

## 93. Failed Decision 的价值

失败后应生成：

```text
LearningSignal
```

例如：

```text
OpportunityModelOverestimated
TravelBenefitOverestimated
ChangeCostUnderestimated
LocalRelationshipImpactMissing
CoverageResponseWeak
ExecutionNoncompliance
```

这些进入：

```text
ModelReview
PolicyReview
WorldModelImprovement
```

---

## 94. 不能把 Decision Failure 等同 Agent Failure

如果基于当时可得 Evidence：

```text
decision rational
```

但未来市场意外变化导致失败，

它不一定说明 Decision Framework 错误。

所以 B4 应区分：

```text
DecisionProcessQuality
OutcomeRealization
ExternalShock
```

---

## 95. Historical Replay Benchmark

对过去时间点：

```text
t0
```

冻结当时可知数据：

```text
knowledge_time <= t0
```

让 SRAF 重新做决策。

然后使用：

```text
t0 + future observations
```

进行评价。

但 future observations 只能用于 Evaluation，不能进入 t0 输入。

---

## 96. Replay 的两种问题

### Policy Replay

问：

> 当时如果使用 SRAF，会建议什么？

### Candidate Outcome Replay

问：

> 某类 Candidate 在类似历史条件下是否更合理？

由于真实 Counterfactual 不可直接观察，第二类只能谨慎解释。

---

## 97. Shadow Validation

Production 中：

```text
SRAF generates candidate
```

但不执行。

之后观察真实世界。

Shadow 可验证：

```text
feasibility
prediction calibration
travel estimate
capacity estimate
diagnosis stability
```

但不能直接证明：

> Candidate 实施后一定更好。

---

## 98. Pilot Validation

重要 Structural Decision 建议：

```text
1–2 pilot markets
→ validate
→ refine
→ scale
```

尤其适合新 Territory / Coverage methodology。

---

## 99. Replication

单一城市成功不能直接证明 Framework 可推广。

应测试：

```text
different market density
different channel structure
different geography
different sales model
different data quality
```

观察 Decision Logic 是否保持有效。

---

# Part VI — Benchmark Dataset Strategy

## 100. Benchmark 数据分层

建议固定六级：

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

目标：

```text
semantic
constraint
analytical correctness
```

数据规模很小。

结果人工可验证。

---

## 102. L1 Fully Synthetic

生成：

```text
accounts
opportunity
coverage
resources
travel
policies
```

并主动植入 Root Cause。

优势：

> Ground Truth 已知。

---

## 103. L2 Semi-synthetic

使用真实/匿名化空间与业务结构，

人为注入：

```text
capacity shortage
territory imbalance
location error
coverage excess
data corruption
```

比纯 synthetic 更接近现实。

---

## 104. L3 Historical Replay

使用历史 Snapshot。

要求：

```text
bitemporal integrity
no look-ahead
```

适合测试：

```text
diagnosis
candidate plausibility
forecast calibration
```

---

## 105. L4 Shadow Production

真实当前数据、真实工作流，但 Candidate 不执行。

重点：

```text
operational reliability
diagnostic stability
human acceptance
prediction calibration
```

---

## 106. L5 Pilot / Production

真实 Decision 实施。

用于 B4。

所有重大实验必须有：

```text
DecisionValidationPlan
```

---

# Part VII — Benchmark Suite Design

## 107. Benchmark Case Schema

建议：

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

## 108. Case 必须版本化

如果数据或预期标签变化：

```text
case v1.0
→
case v1.1
```

此处版本号是 **Benchmark Case 自身版本**，
与规范文档版本无关，不随文档 bump 而改变。

不能静默修改。

否则历史 Benchmark 不可比较。

---

## 109. Case Families

建议第一版目录：

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

Benchmark 不能只有：

> “这里有问题，请找问题。”

必须包含大量：

```text
Healthy
NoAction
Monitor
InsufficientEvidence
```

Case。

否则系统会形成：

> 只要测试就必须发现问题

的偏差。

---

## 111. Adversarial Cases

需要主动测试：

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

例如：

```text
utilization = 109.9%
110.0%
110.1%
```

结合：

```text
hysteresis
persistence
cooldown
```

测试 Decision Trigger 是否稳定。

---

# Part VIII — Orchestration Benchmark

## 113. Workflow Correctness

至少测试：

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

如果：

```text
CoverageCommitment changes
```

已有：

```text
ScheduleCandidate
RouteCandidate
```

必须标记：

```text
STALE
```

不能继续用于 Approval。

---

## 115. Failure Routing Test

例如：

```text
RESOURCE_INFEASIBLE
```

Orchestrator 应：

```text
route upstream
```

而不是：

```text
retry scheduler 3 times
```

---

## 116. Generic Retry Prohibition Test

对：

```text
POLICY_INFEASIBLE
```

验证系统不会重试 Solver。

---

## 117. Iterative Convergence Test

Coverage ↔ Scheduling：

```text
max_iterations
business_delta_threshold
runtime_budget
```

必须能触发停止。

不能无限循环。

---

## 118. Human Override Re-evaluation Test

修改 Candidate 后：

```text
constraint
travel
workload
opportunity
change cost
```

必须重新计算。

---

# Part IX — Governance / Safety Benchmark

## 119. Governance 是横向 Benchmark

所有层级都必须测试：

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

Agent 不允许：

```text
create hard constraint without policy
change objective silently
approve structural decision
write world state directly
```

---

## 121. Human Approval Test

High-risk Structural Decision 必须经过规定 Approval。

如果缺失：

```text
Transition blocked
```

---

## 122. Guardrail Exception Test

Candidate 超过 Guardrail：

```text
ReassignedRevenue = 13%
limit = 10%
```

必须：

```text
ExceptionReview
```

不能自动通过。

---

## 123. Transition Safety Test

Approved Decision 不得：

```text
directly overwrite all assignments
```

必须通过：

```text
TransitionPlan
```

产生明确 World Event。

---

## 124. Rollback Test

模拟：

```text
critical post-transition issue
```

确保：

```text
Rollback Decision / Transition
```

可被创建和审计。

---

## 125. Reproducibility Package

每次 Benchmark Run 至少保存：

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

进入任何 Solver Benchmark 前：

```text
Critical semantic invariants = PASS
Scenario isolation = PASS
Temporal replay = PASS
```

---

## 127. Gate 1 — Diagnosis Gate

进入 Structural Candidate Benchmark 前，至少证明：

```text
True shortage
Territory imbalance
Location mismatch
Coverage mismatch
Data problem
```

五类能被正确区分。

不建议 v1.2 直接设置一个全局百分比阈值。

但必须完整报告：

```text
confusion matrix
false expansion rate
false structural trigger rate
no-action correctness
```

---

## 128. Gate 2 — Solver Gate

至少：

```text
toy analytical cases exact
small exact instances validated
independent constraint checker pass
failure semantics pass
reproducibility pass
```

Heuristic 必须披露：

```text
optimality claim
```

---

## 129. Gate 3 — Decision Gate

Structural Candidate 必须：

```text
have baseline
include Maintain
report delta
report ChangeCost
report uncertainty
pass downstream feasibility
```

否则不允许进入正式 Human Approval。

---

## 130. Gate 4 — Production Evidence Gate

从 Shadow 进入 Pilot：

必须有：

```text
stable workflow
diagnostic quality
prediction calibration
human review process
rollback plan
```

从 Pilot 进入 Scale：

必须存在：

```text
DecisionValidation result
```

而不是只看模型回测。

---

# Part XI — Benchmark Report

## 131. 标准 Benchmark Report

每轮必须输出：

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

## 132. 不允许 Cherry-pick

若同一算法运行多次：

```text
best
median
worst / P90
```

都应报告适用指标。

不能只展示最好 Seed。

---

## 133. Regression Benchmark

每次重要版本升级必须重跑固定：

# `SRAF Core Benchmark Suite`

至少包含：

```text
semantic core
diagnostic core
solver toy set
workflow core
governance core
```

---

## 134. Decision Regression

不仅测试：

```text
code output changed?
```

还要测试：

> Candidate recommendation 是否发生业务级变化？

例如：

```text
v1:
Rebalance

v2:
Add 2 reps
```

即使两版代码都“通过单元测试”，也必须触发 Decision Regression Review。

---

## 135. Explanation Regression

若核心 Recommendation 不变，但解释 Evidence 改变，也应检查：

```text
provenance
hypothesis ranking
trade-off
```

是否合理。

---

# Part XII — v1.2 MVP Benchmark Plan

## 136. 第一阶段不要测试全部 7 个 Engine

建议以已经具备基础能力的 Visit Scheduling vertical slice 为第一条线。

---

## 137. MVP Benchmark Slice A — Scheduling

测试：

```text
CoverageCommitment
→ Scheduling Precheck
→ Scheduler
→ Candidate
→ UnfulfilledCommitment
```

Cases：

```text
A feasible
B global capacity infeasible
C temporal structural infeasible
D policy conflict
E solver timeout
```

重点：

> 五种状态必须正确区分。

---

## 138. MVP Benchmark Slice B — Diagnosis

使用 5 个 Canonical Case：

```text
True Capacity Shortage
Territory Imbalance
Location Mismatch
Coverage Over-allocation
Data Corruption
```

重点：

```text
Problem Router
False Expansion Recommendation
```

---

## 139. MVP Benchmark Slice C — Structural Rebalance

先不追求先进 Territory Solver。

使用：

```text
Baseline
Maintain
Simple Rebalance
```

比较：

```text
workload
opportunity
travel
change cost
```

重点验证：

```text
Decision Contract
Delta Evaluation
Maintain Candidate
Human Override
```

---

## 140. MVP Benchmark Slice D — Orchestration

验证：

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

建议以后每一个 SRAF 能力都标注其证据等级：

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

## 142. E0 不允许宣传为“已验证业务能力”

例如：

```text
Territory Solver prototype
```

如果只有 E1：

> 可以说“算法在 synthetic benchmark 通过”。

不能说：

> “已证明提升销售”。

---

## 143. E5 与 E6

### E5 Pilot Validated

一个真实市场验证。

### E6 Replicated Production

在多个不同市场重复验证。

这才接近：

> 可复用方法论

的证据标准。

---

# Part XIV — Architecture Gates

## 144. 以下情况直接视为 Evaluation 架构问题

```text
只做 Solver objective benchmark

没有 B0 Semantic Test

历史回测使用未来信息

Diagnostic Benchmark 没有 NoAction Case

所有测试案例都存在问题

没有 DataQuality Root Cause Case

没有 Policy Conflict Case

不区分 Resource Infeasible 与 Solver Failure

Heuristic 被称为 Optimal

只汇报最好 Seed

Candidate 没有 Baseline

Structural Benchmark 不包含 Maintain Candidate

没有 ChangeCost 就评价 Territory

只用 compactness 评价 travel

Oracle 自己没有正确率 Benchmark

HumanOverride 后不重新评估

Business Outcome 只做 Before / After 却声称因果

Pilot 没有 ValidationPlan

Failed Decision 被删除

Benchmark 与 Production 使用不同 Contract

版本升级后不做 Decision Regression
```

---

# Part XV — Definition of Done

## 145. `06_EVALUATION_AND_BENCHMARK.md` v1.2 的实现 DoD

第一阶段必须至少完成：

### B0

```text
Canonical Identity
Temporal Replay
Scenario Isolation
Candidate Isolation
Semantic Status
```

测试。

### B1

正确区分：

```text
True Capacity Shortage
Territory Imbalance
Location Mismatch
Coverage Mismatch
Data Quality Issue
```

### B2

正确区分：

```text
Business Infeasible
Model Infeasible
Solver Failure
```

并在 toy instances 验证数学正确性。

### B3

至少对：

```text
Maintain
Rebalance
Add Capacity
```

做统一 Delta Evaluation。

### B4

至少定义一个真实 Pilot 的：

```text
DecisionValidationPlan
```

即使 v1.2 尚未真正完成 Pilot。

---

## 146. 最终评价原则

SRAF 的证据链应该是：

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

缺任何一层，都不能把：

> “系统运行成功”

等同于：

> “销售资源配置决策正确”。

---

## 147. v1.2 核心结论

SRAF Benchmark 的核心问题不是：

> “算法比 Baseline 快多少？”

而是：

> **系统是否在正确理解世界的前提下，识别了正确的问题，调用了正确的决策模型，生成了值得改变的方案，并最终被真实业务结果支持。**

因此 SRAF 的核心 Benchmark 单位不是单个 Solver Run，而应该逐步升级为：

# `Decision Case`

完整评价：

```text
World Snapshot
→ Diagnosis
→ Problem Route
→ Candidate Set
→ Decision
→ Outcome
```

这才是 Sales Resource Allocation Decision Intelligence Framework 应有的验证对象。
