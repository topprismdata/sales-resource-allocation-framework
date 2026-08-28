# SRAF Decision Orchestration Specification v1.2

**项目：** Sales Resource Allocation Framework  
**文档：** `05_DECISION_ORCHESTRATION.md`  
**状态：** Implementation Baseline v1.2  

**上位规范：**
`00_PROJECT_CHARTER.md`、`01_WORLD_MODEL_SPEC.md`、`02_DECISION_ONTOLOGY.md`、`03_DECISION_PROBLEM_CONTRACTS.md`、`04_ALLOCATION_INTELLIGENCE.md`

---

## 1. 文档目标

Decision Orchestration 回答：

> 当 DecisionCase 被确认后，以什么顺序、耦合方式调用哪些 Decision Problem、Solver、Oracle、Scenario 与 Human Review，最终形成可治理 Decision。

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

本文件唯一拥有：

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

`ScenarioAssumption` 的 Semantic Status 由 01 定义；其 workflow lifecycle 由 05 定义。

---

## 2. 为什么需要 Orchestrator

没有 Orchestrator，Sizing/Location/Territory/Scheduling/Routing 会退化成一组孤立 API，Composite Problem 与流程逻辑散落在 Controller，导致依赖、迭代、Oracle、Human Checkpoint、版本、Fallback 无法统一治理。

Decision Workflow 是 Framework 一级对象。

---

## 3. 三个概念分离

```text
Business Scenario
Decision Workflow
Decision Problem
```

Scenario 回答业务情境；Workflow 回答需要编排哪些步骤；Decision Problem 回答某一步允许改变什么业务变量。

同一 Expansion Scenario 可以因 Headcount 是否已由总部固定而走不同 Workflow。

---

## 4. WorkflowTemplate / WorkflowInstance

WorkflowTemplate：

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

WorkflowInstance：

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

标准类型：

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

Step 通过标准 Artifact 交换，不通过隐式临时表耦合。

Artifact 包括：

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

Step 应表达：

```text
requires
produces
blocks
invalidates
```

上游 Artifact 变化后，下游 Candidate 可被标记 STALE。

---

## 7. Composite Problem / DecompositionPlanner

Composite Problems：

```text
CP01 DeploymentDesign
CP02 CapacityExpansion
CP03 StructuralRebalancing
CP04 CoverageExecutionDesign
```

DecompositionPlanner 输入：

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

输出 SolutionStrategy：

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

Independent 可并行。

Sequential 如 Coverage → Scheduling。

Iterative 如 Territory ↔ Travel、Coverage ↔ SchedulingFeasibility。

Joint 如 Greenfield Sizing + Location + Territory，但求解后必须 Semantic Decomposition 回 ResourceRequirement、ResourceDeployment、ResponsibilityAssignment。

Joint 不是默认模式，需考虑 scale、runtime、data quality、explainability、optimality requirement。

---

## 9. Multi-stage Decomposition / Multi-fidelity

大规模问题可：

```text
Demand Aggregation
→ Macro Resource Design
→ Macro Territory
→ Micro Assignment
→ Routing Evaluation
→ Local Improvement
```

所有聚合都属于 ProblemProjection，不修改 World。

Evaluation：

```text
L1 Fast Proxy
L2 Network Evaluation
L3 Full Simulation
```

Candidate Funnel：

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

Oracle 统一返回：

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

Status：

```text
FEASIBLE
FEASIBLE_WITH_RISK
INFEASIBLE
UNKNOWN
```

Oracle 不得自动修改 Candidate，只提供 Feedback。

---

## 11. Feedback Contract / Iteration Stop

Iterative Workflow 必须声明：

```text
feedback_source
feedback_target
feedback_variables
```

停止条件：

```text
FeasibleSolutionFound
NoMaterialImprovement
ObjectiveImprovementBelowThreshold
BusinessDeltaBelowThreshold
MaxIterations
RuntimeBudgetReached
HumanStop
```

不允许无限循环或只追数学 objective。

---

## 12. SolverSelector

DecompositionPlanner 决定如何拆，SolverSelector 决定某一步用哪个具体 Solver。

输入：

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

InteractionMode：

```text
BatchPlanning
InteractiveWhatIf
ProductionOptimization
BenchmarkResearch
FeasibilityCheck
```

支持 Primary Solver、Fallback Solver、Fallback Heuristic；Fallback 不代表放松 Hard Constraint。

---

## 13. Human Checkpoints

```text
H1 Problem Framing Review
H2 Candidate Review
H3 Exception / Override Review
H4 Final Approval
```

Human Review 可以提交 HumanEvidence；Override 需要版本化并重新评价。

---

## 14. Automation Level

```text
A0 Advisory
A1 Human-approved execution
A2 Auto-execute within guardrails
A3 Autonomous
```

Structural Decision 默认 A0/A1；低风险 routing/scheduling 可在严格 Policy 下达到 A2。

WorkflowPolicy 声明 allowed_automation_level、required_human_checkpoints、approval_authority。

---

## 14A. Governance Workflows（GW01–GW03）

`WorldModelRepair`、`ModelGovernance`、`PolicyReview` 由 Problem Router 产出，
但**不是** DP01–DP07，也不注册进 SolverRegistry。

本文件拥有其最低 Workflow 语义（复用 §4 WorkflowTemplate / §5 WorkflowStep /
§22 Workflow Status / §14 Automation Level），不新增一套独立引擎。

统一约束：

```text
entry_artifact        AllocationDecisionSignal / DecisionCase
executor              人工治理角色 + 平台任务（非 Decision Compiler）
automation_level      默认 A0/A1；禁止 A2/A3
forbidden             直接修改 Canonical World；静默改 Policy/Requirement
output                修正提案 + 治理决定 + 影响范围
post_effect           触发下游 Artifact STALE 标记（§21）
reintegration         修正完成 → 回到 Diagnosis 重算 Health/Gap
```

### GW01 WorldModelRepair

处理数据缺陷（坐标错误、重复实体、过期 travel、责任冲突）。

```text
DefectTriage          严重度 × 影响范围分级
RepairAction          Entity Merge/Split/Supersede 见 08；属性更正见本流程
ImpactAnalysis        受影响 Opportunity / Coverage / Workload 清单
Verification          修正后 Health 重算，Gap 是否消失
```

Identity 类修复必须经 `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`
的 Human Resolution 权限，GW01 不得绕过。

### GW02 ModelGovernance

处理系统性模型偏差（Opportunity 高估、ServiceTime 失真、Travel 漂移）。

```text
EvidenceReview        残差 / 分布漂移 / calibration 报告
VersionDecision       重训 / 换特征 / 降级使用 / 保留
Reprojection          新 model_version 重算历史 Derived State
```

GW02 不自动 reweight objective；任何进入 Candidate 的权重变化
仍走 `02` 的 Objective 治理。

### GW03 PolicyReview

处理 `POLICY_INFEASIBLE` 与互斥 Hard Policy。

```text
ConflictExposition    哪两条 Policy、在哪个 scope、为何不可同真
AuthorityRouting      按 policy owner 升级（不得由工程侧默认放宽）
Resolution            改 Policy / 申请例外 / 接受局部不覆盖
```

GW03 与 `RequirementExceptionProposal`（02 §43A）的关系：
Proposal 是**单个 DecisionCase 内**的例外；
GW03 是**跨 Case 的 Policy 语义本身**的修订入口。两者审批权限不同。

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

Sizing ↔ Coverage 需要生成 Resource–Coverage Frontier。

Location ↔ Territory 通常 Iterative；大规模可 Macro Joint + Micro Iterative。

默认 Ideal Deployment → Personnel/Hiring，而不是围绕现有人位置强行设计市场。

---

## 16. SC02 Capacity Expansion

Entry：

```text
Persistent Capacity Gap
Opportunity Gap
Market Growth
New Product
New Channel
Management-approved envelope
```

Workflow：

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

进入 DP01 前至少经过 GlobalCapacity、TravelBenchmark、LocalImbalance、CoveragePolicyStress 等测试。

必须比较：

```text
Maintain
Rebalance Existing Capacity
Reduce Low-value Coverage
Relocate Existing Resource
Add Incremental Capacity
Hybrid
```

不能只比较加几个人。

---

## 17. SC03 Capacity Reduction / Downsizing

Workflow：

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

逻辑是 Market Need → Required Deployment → Required Capability → Personnel Matching，而不是先决定谁留下。

---

## 18. SC04 Structural Rebalancing

先问 Should we change?

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

Maintain 强制。

Minor / Major Rebalance 可按 accounts/revenue/resources/territory changed 分类，并影响 approval、transition、validation。

---

## 19. ChangeBudget / Central Benchmark / Local Adjustment

`ChangeBudget` **不作为新的 canonical Entity**。

它由 `DecisionCase / WorkflowPolicy` 中的一组 `DecisionRequirement / Guardrail` 表达，例如：

ChangeBudget 可限制：

```text
Max reassigned accounts
Max reassigned revenue
Max moved resources
Max transition cost
```

Structural Workflow 建议固定产生 CentralBenchmarkCandidate。

LocalAdjustedCandidate 必须基于 Central Benchmark 形成 Delta；HumanOverride 后重新计算 Opportunity、Workload、Travel、Capacity、ChangeCost、Constraint Status。

---

## 20. Scenario Fork / Cross-Problem Evaluation

Baseline 上创建 Scenario Overlay，不复制/修改生产 World。

不同 Solver Candidate 投影到统一 Business Evaluation Space：

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

v1.2 不默认 Universal Score；可保留 Pareto Candidate Set。

Recommendation ≠ Decision。

---

## 21. Workflow Restart / Artifact Invalidation

新 Evidence 或上游改变可从指定 Step 重启。

依赖变化后旧 Artifact 标记 STALE，禁止继续审批。

WorkflowTemplate 与 OrchestrationRun 都版本化。

---

## 21A. Run Hierarchy

v1.2 统一技术执行记录：

```text
OrchestrationRun
  ├── ProblemRun
  │     └── SolverRun
  ├── OracleRun
  └── EvaluationRun
```

`ProblemRun` 由 03 定义，`OrchestrationRun` 由 05 定义。

不再使用一个语义含糊的统一 run 名称覆盖所有层级。

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

WAITING_FOR_DATA 不是 failure；POLICY_INFEASIBLE 等可使 Workflow BLOCKED。

Retry 必须基于 FailureType，禁止 Generic Retry。

---

## 23. Agent 与 Orchestrator 边界

Agent：

```text
interpret
suggest scenario
request diagnostic tests
explain candidates
collect human input
```

Orchestrator：

```text
workflow state
dependency
artifact validity
allowed transition
tool invocation
checkpoint
retry/fallback
```

Agent 不靠对话记忆管理复杂 Workflow 状态。

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

Budget：

```text
ComputeBudget
ChangeBudget
TimeBudget
HumanReviewBudget
CandidateBudget
```

---

## 25. Cross-Horizon Escalation / Freeze Window

Operational Failure 持续且 root cause structural 才创建 Structural Review。

上层结构变化可触发 Scheduling/ Routing refresh。

支持 StructuralFreezeWindow（promotion、quarter close、peak season）。

---

## 26. Transition / Validation

Approved Decision → TransitionPlan → Execution → Stabilization → Validation → DecisionOutcome。

Structural Workflow 不在 Transition 后直接 Closed。

支持 ShadowWorkflow、Pilot、StagedTransitionPlan。

---

## 27. DecisionRisk

```text
Low
Medium
High
Critical
```

考虑 BusinessImpact、ChangeScale、Uncertainty、CustomerRelationshipImpact、PersonnelImpact、Reversibility、DataConfidence。

高风险/关键结构决策必须更高级 Human Governance。

---

## 28. Architecture Gates

原则上拒绝：

```text
Business Scenario 与 Solver 一一绑定
Expansion = 一个 Expansion Solver
Workflow 顺序硬编码在 Controller
Composite Problem 创造重复业务变量
Joint Solver 输出无法恢复 Atomic Semantics
Oracle 自动修改 Candidate
Iterative Loop 没有停止条件
所有 Candidate 都跑最高成本 Simulation
SolverSelector 与 ProblemRouter 合并
Solver timeout 自动放松 Hard Constraint
Human Review 后不重新评价
HumanOverride 静默替换 Candidate
依赖变化后旧 Candidate 仍有效
Workflow 无版本
Scenario 修改生产 World
Structural Decision 不允许 Maintain
Expansion 不比较 Rebalance/Coverage alternatives
Downsizing 先决定人员再决定市场
一次 Operational Failure 就升级 Territory
Generic Retry
Agent 自己维护 Workflow State
Approval 后跳过 Transition
Transition 后不做 Validation
```

---

## 29. MVP 顺序 / DoD

最小 Orchestration：

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

第一条 Workflow：DP06 Scheduling Reference Integration。

第二条：Coverage ↔ Scheduling Iterative Loop。

第三条：Structural Rebalancing（Baseline + Maintain + Rebalance + HumanOverride + Re-evaluation）。

至少验证：

```text
Sequential
Iterative
Failure Routing
Human Override
Scenario Isolation
```

完整 Pipeline：

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
