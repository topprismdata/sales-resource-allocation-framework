# SRAF Allocation Intelligence Specification v1.2

**项目：** Sales Resource Allocation Framework  
**文档：** `04_ALLOCATION_INTELLIGENCE.md`  
**状态：** Implementation Baseline v1.2  

**上位规范：**
`00_PROJECT_CHARTER.md`、`01_WORLD_MODEL_SPEC.md`、`02_DECISION_ONTOLOGY.md`、`03_DECISION_PROBLEM_CONTRACTS.md`

---

## 1. 文档目标

Allocation Intelligence 回答：

```text
1. 当前销售资源配置是否健康？
2. 哪里存在 Demand–Supply mismatch？
3. 为什么出现这种 mismatch？
4. 问题是否重要到值得重新决策？
5. 应该创建哪一种 Decision Problem？
```

核心链：

```text
WORLD STATE
    ↓
DERIVED ALLOCATION STATE
    ↓
ALLOCATION HEALTH
    ↓
GAP DETECTION
    ↓
ROOT CAUSE DIAGNOSIS
    ↓
MATERIALITY
    ↓
DECISION TRIGGER
    ↓
PROBLEM ROUTER
    ↓
DECISION CASE
```

它不直接产生最终 Territory、Headcount 或 Schedule。

---

## 1A. Normative Ownership

本文件唯一拥有：

```text
Allocation Health dimensions
Gap subtype taxonomy
DiagnosticTest
DiagnosticHypothesis ranking rules
Materiality logic
DecisionTrigger rules
ProblemRouter
AllocationDecisionSignal
```

`AllocationGap` 基类与 `DecisionCase` schema 仍由 02 拥有。

---

## 2. 核心抽象：Demand–Supply Matching

```text
MARKET SIDE
   ↓
Opportunity
   ↓
Coverage Need
   ↓
Workload Demand
   ↓
      MATCH
   ↑
Capacity Supply
   ↑
Resource Deployment
   ↑
RESOURCE SIDE
```

Demand 至少包含 Opportunity、Coverage、Workload、Capability、Spatial、Temporal Demand。

Supply 至少包含 Capacity、Capability、Location、Availability、Mobility、ServiceChannel、Responsibility Eligibility。

---

## 3. DerivedAllocationState

标准派生状态：

```text
OpportunityCoverage
CoverageAttainment
IntrinsicWorkload
NetworkWorkload
TotalWorkload
EffectiveCapacity
CapacityUtilization
TravelBurden
ServiceLevel
CapabilityFit
AssignmentStability
OpportunityAtRisk
UnfulfilledCoverage
```

均需 calculation_version、input_snapshot、calculated_at、confidence。

---

## 4. Multi-dimensional Health Profile

禁止默认只生成单一 Territory Health Score。

六个维度：

```text
H1 Opportunity Health
H2 Service Health
H3 Capacity Health
H4 Spatial Efficiency Health
H5 Responsibility Health
H6 Stability & Confidence Health
```

Health Status：

```text
Healthy
Watch
Degraded
Critical
Unknown
```

---

## 5. H1 Opportunity Health

核心：

```text
AddressableOpportunity
CoveredOpportunity
UncoveredOpportunity
OpportunityCoverageRate
OpportunityAtRisk
HighPriorityOpportunityCoverage
```

Opportunity 是 Estimate，不是确定销售额。

Coverage Attainment 高不等于 Opportunity Coverage 高。

---

## 6. H2 Service Health

严格区分：

```text
Coverage Need
      ↓
Coverage Commitment
      ↓
Scheduled Coverage
      ↓
Actual Coverage
```

Gap 分别可能是 Allocation Gap、Scheduling Gap、Execution Gap。

---

## 7. H3 Capacity Health

核心：

```text
NominalCapacity
AvailableCapacity
EffectiveCapacity
CommittedCapacity
ResidualCapacity
CapacityUtilization
CapacityGap
```

建议：

\[
Utilization =
AssignedWorkload / EffectiveCapacity
\]

Capacity Utilization 必须与 Opportunity Coverage 联合解释。

---

## 8. H4 Spatial Efficiency Health

核心：

```text
TravelBurden
NetworkWorkload
ServiceToTravelRatio
BaseLocationEfficiency
TerritoryAccessibility
CrossBoundaryTravel
RouteEfficiency
```

Compactness 只能是 L1 proxy，生产判断优先 Road Network，重大调整可用 Routing Simulation。

---

## 9. H5 Responsibility Health

核心：

```text
AssignmentCompleteness
PrimaryOwnershipConflict
CapabilityFit
ResponsibilityOverlap
UnassignedResponsibility
OverlappingResponsibility
PersonnelFit
RelationshipContinuity
```

---

## 10. H6 Stability & Confidence Health

Stability：

```text
AssignmentChurn
TerritoryChurn
RepMovement
CustomerOwnershipChange
TransitionFrequency
```

Confidence：

```text
OpportunityConfidence
LocationQuality
TravelModelQuality
CoverageDataQuality
ResponsibilityEvidenceQuality
IdentityConfidence      （08 §16；subject 计数是否可信）
```

低置信度不能触发大规模结构调整。

`IdentityConfidence` 的特殊性在于它是**其他置信度的前提**：
若 subject 本身可能是重复或误并，
则 OpportunityConfidence 与 Workload 的数值高低都不具备决策意义。
因此 H6 必须先解析身份，再解释其余维度。

---

## 11. Gap Detection Contract

Gap 必须回答：

```text
What?
Where?
How large?
Since when?
Compared with what?
Business impact?
Confidence?
```

Reference Type：

```text
PolicyTarget
BaselineState
PeerBenchmark
HistoricalNorm
CapacityLimit
BusinessCommitment
ScenarioTarget
ModelExpectedValue
```

Gap Severity 综合 Magnitude、Persistence、BusinessImpact、Confidence。

---

## 11A. Coverage Gap v1.2 子类型

`CoverageGap` 统一沿 Coverage Funnel 细分为：

```text
CoverageAllocationGap
SchedulingCoverageGap
ExecutionCoverageGap
```

对应：

```text
CoverageNeed → CoverageCommitment
CoverageCommitment → ScheduledCoverage
ScheduledCoverage → ActualCoverage
```

02 只定义 `CoverageGap` 上位对象，具体 subtype 以本文件为 normative owner。

---

## 12. 七类 Gap

```text
G1 CoverageGap
G2 CapacityGap
G3 OpportunityGap
G4 SpatialTravelGap
G5 CapabilityGap
G6 LocalAllocationGap
G7 StabilityGap
```

CoverageGap 区分 CoverageCommitmentGap、SchedulingCoverageGap、ExecutionCoverageGap。

CapacityGap 区分 Global、Local、ResourceType、Temporal。

`LocalAllocationGap` 专指全局资源基本可行但局部责任/资源配置失衡；不得简称成 subtype `AllocationGap`。

OpportunityGap 区分 Unserved、UnderServed、Misallocated。

SpatialTravelGap 区分 BaseLocation、TerritoryShape、RoadNetwork、CrossBoundaryTravel、RouteStructure。

---

## 13. Diagnostic Causal Graph

第一版是“带因果方向假设的业务诊断图”，不是严格科学因果模型。

```text
                  OPPORTUNITY GAP
                         ↑
                    COVERAGE GAP
                         ↑
        ┌────────────────┼─────────────────┐
        │                │                 │
   CAPACITY GAP     ALLOCATION GAP    CAPABILITY GAP
        ↑                ↑                 ↑
 RESOURCE      TRAVEL / LOCATION       RESOURCE
 SHORTAGE            / TERRITORY       SKILL GAP
        ↑
   COVERAGE POLICY
```

外侧始终存在 Data / Model Quality。

---

## 14. DiagnosticHypothesis Test

每个 Hypothesis 应具有：

```text
RequiredEvidence
SupportingTests
ContradictingTests
MinimumConfidence
AlternativeExplanation
```

不能只依靠 LLM 自由推理。

---

## 15. H-CAP：Capacity Shortage

支持：

```text
Global effective capacity < required workload
Multiple territories overloaded
Travel normal
Allocation balance normal
Capability fit acceptable
Coverage policy validated
Persistent opportunity at risk
```

反对：

```text
Total capacity sufficient
Travel abnormal
Neighbor idle capacity
Coverage policy inflated
Scheduling concentration explains gap
```

Utilization > 100% 本身不足以证明缺人。

---

## 16. H-ALLOC：Territory / Allocation Imbalance

支持：

```text
Global capacity sufficient
Local utilization variance high
Opportunity/workload distribution uneven
Reallocation materially reduces gap
```

所有 Territory 都均匀过载时，更像 Global Capacity Shortage。

---

## 17. H-LOC：Resource Location Mismatch

支持：

```text
Travel burden abnormal
Demand far from deployment base
Alternative deployment releases capacity
Territory shape not primary issue
```

建议计算 Capacity Released by Relocation。

---

## 18. ResourceEquivalent

`ResourceEquivalent` 是 `MetricRegistry` 中的 **Derived Metric**，不是 Resource Entity、Headcount 或新的 World class。

它用于将不同改善方式转换成可比较 Capacity Effect：

```text
Reduce travel = +0.42 RE
Relax low-value coverage = +0.31 RE
Cross-territory support = +0.18 RE
Add one new rep = +1.00 RE
```

\[
ResourceEquivalent = GapWorkload / EffectiveCapacity_{Archetype}
\]

必须同 ResourceArchetype、Capability、Time Horizon。

RE 不等于 Headcount。

---

## 19. H-CAPABILITY

Total capacity 足够但 Eligible capacity 不足时，路由 Personnel Matching、Skill/Pool/Channel Substitution 等，而不是整体加人。

---

## 20. H-COVERAGE

若 Coverage commitment 驱动 overload，且低价值客户占用大量 capacity，Stress Scenario 显示 workload 大幅下降而 Opportunity Coverage 轻微下降，则更可能是 Coverage Allocation / Policy 问题。

---

## 21. H-SCHED / H-ROUTE

Monthly workload 可行但 weekday/spacing/time-window 冲突 → DP06 Visit Scheduling。

Daily assignment reasonable 但 sequence/traffic/time-window 导致 travel 过高 → DP07 Daily Routing。

---

## 22. H-DATA / H-MODEL

DataQualityIssue 必须始终是顶层 Alternative Hypothesis。

数据正确但 Opportunity/Travel/ServiceTime 模型系统性偏差 → Model Governance。

**Identity 子假设**：

`DataQualityIssue` 的身份侧 subtype
（`IdentityDuplicate` / `IdentityFalseMatch` /
`IdentityUnresolved` / `HierarchyMisattribution`）
由 `02 §21` 拥有；判定规则、阈值与人工权限由 `08` 拥有。
本文件只负责**如何检验它们**（见 §24 `IdentityIntegrityTest`）。

没有这些 subtype，H-DATA 只是一个不可检验的垃圾桶标签。

诊断顺序要求：在支持 H-CAPACITY 之前，
必须先执行 `IdentityIntegrityTest` 并证明无显著 `IdentityDuplicate`。
否则「忙 → 加人」的误诊只是把身份缺陷转成了编制决策。

---

## 23. Diagnosis Engine

v1.2 推荐：

```text
Rule / Statistical Tests
+
Simulation
+
Comparative Benchmark
+
LLM Explanation
```

而非 LLM end-to-end diagnosis。

---

## 24. DiagnosticTest Library

MVP 建议：

```text
GlobalCapacityTest
LocalImbalanceTest
TravelBurdenBenchmarkTest
BaseLocationCounterfactualTest
CoveragePolicyStressTest
CapabilityEligibilityTest
SchedulingFeasibilityTest
DataCompletenessTest
OpportunityConfidenceTest
AssignmentConflictTest
IdentityIntegrityTest
```

其中 `IdentityIntegrityTest` 至少包含（判定规则与阈值见 08 §11、§14）：

```text
DuplicateSuspectTest       同址/同品牌高相似且同期双活
HierarchyOverlapTest       group 与 store 是否被重复求和
IdentityCoverageTest       处于 UNRESOLVED / CONTESTED 的 subject 占比
FalseMatchProbeTest        已合并簇内是否存在冲突强信号
```

Materiality 联动：`IdentityUnresolved` 比例超过阈值时，
该 scope 内任何 Gap 的 `materiality_level` 不得高于 `Review`，
不得直接进入 `Actionable`（08 §14.2）。

---

## 25. Hypothesis Ranking

允许：

```text
Primary Hypothesis
Contributing Hypothesis
Alternative Hypothesis
```

未来可扩展 causal contribution decomposition。

---

## 26. Materiality

至少考虑：

```text
Magnitude
Persistence
OpportunityImpact
StrategicImportance
Confidence
ExpectedDecisionValue
ChangeCost
```

EDV 可粗略表示：

\[
ExpectedDecisionValue
=
ExpectedImprovement
-
ExpectedChangeCost
\]

目的不是精确财务建模，而是阻止“只要有 gap 就优化”。

Materiality：

```text
Informational
Monitor
Review
Actionable
Critical
```

---

## 27. Decision Trigger

综合：

```text
Gap
Hypothesis
Materiality
Confidence
Persistence
Cooldown
```

Trigger 只创建 DecisionCase，绝不自动修改 Territory。

---

## 28. Problem Router

| Diagnosis | Primary Route |
|---|---|
| Global Capacity Shortage | DP01 Resource Sizing |
| Capacity Surplus | DP01 / Downsizing |
| Base Location Mismatch | DP02 Resource Location |
| Local Allocation Imbalance | DP03 Territory Alignment |
| Personnel / Skill Fit | DP04 Personnel Matching |
| Coverage / Channel Mismatch | DP05 Coverage Allocation |
| Temporal Feasibility | DP06 Visit Scheduling |
| Daily Route Inefficiency | DP07 Daily Routing |
| Data Quality Issue | World Model Repair |
| Model Quality Issue | Model Governance |
| Policy Conflict | Policy Review |

Router 可输出 Composite Problem、Alternative Route、Monitor、RequestMoreEvidence、NoAction。

---

## 29. AllocationDecisionSignal

标准输出：

```text
scope
world_snapshot
health_profile
gap_set
diagnostic_hypotheses
materiality
recommended_route
alternative_routes
decision_trigger_status
confidence
evidence_summary
```

满足 Trigger 后才创建 DecisionCase。

---

## 30. Agent 边界

Allocation Intelligence 负责结构化检测、计算、对比、诊断测试、证据组织。

Agent 负责语义解释、假设探索、交互式分析、Scenario 调用、决策支持。

Agent 不替代 Gap calculation、Business thresholds、Hard diagnostic tests。

---

## 31. Central Benchmark + Local Knowledge

```text
Central Allocation Intelligence
          ↓
Evidence-backed Diagnosis
          ↓
Local Review
          ↓
Local Evidence / Exception
          ↓
Hypothesis Update
          ↓
DecisionCase
```

Local knowledge 要进入 Assertion / Evidence / ChangeCost / Guardrail 等治理结构，不可自由覆盖。

---

## 32. Counterfactual Diagnosis

问“只改变 X，Gap 会减少多少？”可调用 Diagnostic Solver，但必须与正式 Candidate Generation 的 run_purpose 区分。

ProblemRun 建议支持：

```text
diagnostic
feasibility
candidate_generation
validation
benchmark
```

---

## 33. Fast / Slow Allocation Intelligence

Fast：

```text
coverage
schedule
execution
route
day/week
```

Slow：

```text
sizing
location
territory
personnel
month/quarter
```

Operational Failure 持续且 Root Cause 结构性时才向上升级。

---

## 34. Decision Suppression / Seasonality / Structurality

支持 Suppression：

```text
Recent structural change
Data quality low
Seasonal anomaly
Temporary promotion
Known one-off event
Transition period
```

Gap 分类：

```text
TemporaryGap
StructuralGap
Unknown
```

避免把旺季或促销峰值误判为结构性缺人。

---

## 35. Management View

输出应从指标升级为业务结论，例如：

```text
存在持续性高潜覆盖缺口。
缺口约 0.6 Field Rep Equivalent。
主要原因是 Territory 分配不均，而非全市场人员不足。
证据：全市场 Capacity 充足、相邻 Territory 有可释放 Capacity、Travel 正常。
建议：先评估 Territory Rebalancing，暂不直接增员。
```

---

## 36. Architecture Gates

原则上拒绝：

```text
Health 只有一个总分
Metric 异常直接生成 DecisionProblem
Utilization > threshold 就建议加人
CoverageGap 不区分 Need/Commitment/Schedule/Actual
Global/Local Capacity Gap 混淆
Capability Gap 被当普通 Capacity Gap
Compactness 直接当 Travel Root Cause
Root Cause 没有 Evidence Against
LLM 自由生成 Root Cause 而无 Diagnostic Test
DataQualityIssue 不允许成为 Root Cause
Opportunity Gap 无 confidence
临时峰值触发 Territory Realignment
没有 Persistence/Cooldown/Suppression
Problem Router 与 Solver Selector 合并
所有问题都路由 Territory Solver
Router 不允许 NoAction
Agent 自己决定 Business Threshold
Diagnostic Solver Result 被当正式 Candidate
```

---

## 37. MVP Scope / Benchmark

MVP：

```text
DerivedAllocationState
6-dimensional Health Profile
7 Gap Types
5 Diagnostic Hypotheses:
  CapacityShortage
  AllocationImbalance
  TravelMismatch
  CoverageMismatch
  DataQualityIssue
Materiality
DecisionTrigger
ProblemRouter
```

加五个 Diagnostic Tests：

```text
GlobalCapacityTest
LocalImbalanceTest
TravelBenchmarkTest
CoveragePolicyStressTest
SchedulingFeasibilityTest
```

至少用五个 Case 验证：

```text
真缺人
Territory失衡
Location问题
Coverage问题
Data问题
```

核心 Benchmark：

```text
Problem Routing Accuracy
Root Cause Recall
False Structural Trigger Rate
False Expansion Recommendation Rate
Data-vs-Business Diagnosis Accuracy
Evidence Completeness
Decision Suppression Correctness
```
