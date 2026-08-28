# Sales Resource Allocation Framework

## Project Charter v1.2

**项目名称：** Sales Resource Allocation Framework  
**简称：** SRAF  
**中文名称：** 销售资源配置决策框架  
**文档版本：** v1.2  
**文档性质：** 项目最高层方向规范（Project Charter）

---

## 1. 项目背景

企业销售资源配置通常被拆散在多个彼此独立的问题中：

- 销售团队需要多少人；
- 销售人员应该部署在哪里；
- 客户应该由谁负责；
- Territory 应如何划分；
- 不同客户应该投入多少销售资源；
- 应该多久拜访一次；
- 周期拜访如何安排；
- 每日线路如何执行。

传统系统通常将其中某一个问题单独产品化，例如：

```text
Territory Management
Route Planning
Visit Scheduling
Sales Force Sizing
Coverage Planning
```

这种拆分有其合理性，但也导致一个根本问题：

> **不同优化问题缺乏统一的销售世界语义和资源配置逻辑。**

一个“拜访排不出来”的问题，可能并不是排班算法的问题，而可能来源于 Territory 失衡、销售资源部署位置错误、Coverage Policy 过高、Capacity 不足、Capability 不匹配、Travel burden 过高，或数据/潜力模型错误。

SRAF 的目标，是建立：

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

而不是：

```text
Business Problem
      ↓
Solver-specific Model
      ↓
局部数学最优
```

---

## 2. 外部理论基础

SRAF 以销售队伍设计、Territory Alignment、resource allocation、districting、scheduling 与 routing 等经典理论和实践为基础，但不照搬传统产品形态。

Territory Alignment 的业务本质是对 accounts 及其相关 selling activities 向 salesperson / sales team 的分配，而不仅仅是地图 Polygon 的绘制。良好的 Territory Alignment 同时影响 customer coverage、sales、productivity、fairness、morale 与 travel efficiency。

SRAF 在此基础上建立统一的业务世界模型、决策本体、问题契约、诊断、编排、评价与治理体系。

---

## 3. SRAF 的扩展设计

SRAF 将销售资源配置问题统一抽象为：

> **在市场机会、客户服务需求、销售资源能力、组织政策和现实约束之间，持续形成可解释、可验证、可执行的资源配置决策。**

形式化表达：

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

核心不是：

\[
Accounts \rightarrow Territories
\]

而是：

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

## 4. 项目核心命题

> **Allocate the right sales capacity to the right market opportunity, at the right level of responsibility and time horizon.**

中文：

> **在正确的时间尺度和责任层级上，将合适的销售能力配置到最值得投入的市场机会。**

使用 Sales Capacity，而不是 Salesperson，是因为资源可以包括：

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

## 5. SRAF 不是什么

### 5.1 不是 Territory Drawing Tool

Territory geometry 是责任配置的空间投影。

\[
Territory \neq Polygon
\]

更接近：

\[
Territory
=
Collection(Responsibility)
\]

### 5.2 不是一个超级 Solver

SRAF 不试图用单一模型同时解决 Sizing、Location、Territory、Coverage、Scheduling、Routing。

> **Semantic Separation, Computational Coupling.**

### 5.3 不是传统 CRM / SFA

CRM/SFA 主要记录客户、责任、活动；SRAF 的问题是这些销售责任是否应该这样配置，以及是否存在更好的资源配置方式。

SRAF 是 Decision Layer，不是 Transaction System of Record。

### 5.4 不是单纯 GIS Framework

空间信息是重要输入，但必须同时理解 Opportunity、Workload、Capacity、Capability、Responsibility、Policy、ChangeCost。

### 5.5 不是 LLM Planner

LLM/Agent 可以理解问题、查询 World Model、形成诊断假设、调用 Solver、比较 Scenario、解释 Decision 和支持 Human Review，但不得自由生成未经验证的数学配置结果并直接写入业务系统。

---

## 6. 核心架构原则

### P1. World Before Optimization

先建立销售世界统一表示，再优化。

### P2. Territory Is Responsibility, Not Geometry

Territory 首先表示一组销售责任，空间边界是派生表达。

### P3. Opportunity Is Not Sales

历史销售额只是 Opportunity 的证据之一。Opportunity 必须保存 source、evidence、confidence、valid_time、model_version。

### P4. Workload Is Derived

Workload 由 CoverageNeed、SalesActivity、ServiceTime、Travel 等派生；区分 Intrinsic Workload 与 Network Workload。

### P5. Resource Is Not Person

使用 SalesResource 抽象，并区分 ResourceArchetype、ResourceRequirement、ResourceDeployment、DeploymentAssignment、SalesResource、ResourcePool。

### P6. Responsibility Is Explicit

禁止把核心关系简化成 Account.owner_id。使用 ResponsibilityAssignment 表达 Resource、Subject、Role、Activity、ProductScope、ResponsibilityScope、EffectiveTime、Source。

### P7. Policy Is Not Constraint

Business Policy 经 Problem Compiler 转换为具体数学 Constraint。

### P8. Decision Problem Is Not Solver

Problem 是业务语义，MILP/CP-SAT/heuristic 等是求解方式。

### P9. Semantic Separation, Computational Coupling

业务问题边界不能由算法实现方式决定。允许 Sequential、Iterative、Joint、Bilevel 等计算耦合。

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

Structural Decision 必须与 Baseline 比较，并考虑 ChangeCost、Disruption、Uncertainty、TransitionCost、ImplementationRisk。

### P12. Do Nothing Is a Valid Decision

MaintainCurrentState 必须是合法 Candidate。

### P13. Diagnosis Before Optimization

Observed Symptom → Allocation Gap → Root Cause Diagnosis → Materiality → Decision Trigger → Problem Classification。

### P14. Evidence Before Automation

重要判断必须标注 ObservedFact、MasterDataFact、ExternalFact、ModelEstimate、HumanJudgment、PolicyDefinition、DerivedState、DecisionOutput、ScenarioAssumption 等 Semantic Status。

### P15. Human Override Must Become Evidence

人工调整要记录 Change、Reason、Evidence、ExpectedImpact、Approver、Timestamp，并进入后续学习。

### P16. Change Has Cost

ChangeCost 至少包括 CustomerRelationshipCost、SalespersonIncomeImpact、RelocationCost、LearningCost、TerritoryTransitionCost、ManagementChangeCost。

### P17. Stability Is a Business Objective

持续评价 AssignmentChurn、TerritoryChurn、RelationshipDisruption、TransitionFrequency，并支持 Persistence、Hysteresis、Cooldown、Minimum Improvement Threshold。

### P18. Different Horizons Require Different Decisions

```text
Strategic
Structural
Tactical
Operational
Execution
```

下层 Solver 不得静默改变上层决策。

### P19. Optimize Opportunity Allocation, Not Geometric Beauty

Territory compactness 只是 proxy。Travel evaluation 分 L1 Geometric、L2 Road Network、L3 Operational Routing Simulation。

### P20. Reuse Before Reinvent

SRAF 自身重点建设 Ontology、World Model、Decision Problem Contract、Allocation Intelligence、Problem Compiler、Evaluation、Decision Governance、Evidence、Orchestration。成熟 GIS、routing、solver、workflow 等优先复用。


### P21. Single Normative Owner

每一个核心业务概念必须有且只有一个正式规范拥有其 canonical schema。

允许其他规范引用该概念，但不得重复定义一套不同 schema。

v1.2 的正式归属为：

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

P21 在 v1.2 的具体化：`01 §9–10` 关于 Canonical ID 的**原则**继续有效，
但其 canonical schema 与判定/治理规则归 `08`；
`01` 改为引用，不得维护第二套字段定义。

---

## 7. 核心世界模型

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

核心 Gap 包括：

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

新增 Atomic Problem 必须证明无法由现有 Contract 合理表达。

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

Coupling Mode：

```text
Independent
Sequential
Iterative
Joint
```

---

## 11. Business Scenario 与 Decision Problem 分离

Business Scenario 是 Context；Decision Problem 是可改变变量的业务问题。Expansion 不是一个 Solver Problem，而是可能编排 Incremental Sizing、Location、Territory、Personnel Matching 等。

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

Solver Objective 提升不是 Decision 成功的最终标准。

---

## 13. Decision Validation

重要 Structural / Tactical Decision 在产生时同步定义 DecisionValidationPlan：

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

## 14. Agent 的角色

Agent 是 Sales Allocation Decision Agent：

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

其中 World Model = Environment；Ontology = Language；Allocation Intelligence = Diagnostic Substrate；Decision Engines = Tools；Evaluation = Evidence；Human = Governance。

---

## 15. 与现有 Visit Scheduling Optimizer 的关系

`visit-scheduling-optimizer` 在 SRAF 中注册为：

> **Reference Decision Engine — DP06 Visit Scheduling**

并可作为 Scheduling Feasibility Oracle。

原则上不负责决定 Headcount、Territory、Opportunity、Resource Location 等上游问题。

---

## 16. 项目成功标准

SRAF v1.x 至少证明：

- 语义一致性；
- 问题分类能力；
- Baseline vs Candidate 可比较；
- Solver 可替换；
- Evidence Traceability；
- 实施后的真实可验证性。

---

## 17. 非目标

v1.2 不以以下事项作为优先：

```text
完整 CRM
完整 SFA
完整地图平台
LLM Foundation Model
通用 MLOps
自研 Routing Engine
自研通用 MILP Solver
实时自动重划所有 Territory
完全无人化资源配置
```

---

## 18. 最终架构方向

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

## 19. Charter 级 Architecture Gates

出现以下情况原则上拒绝：

```text
Account.owner_id 被当作唯一责任模型
Territory 被直接建模成 Polygon
Potential 与历史销量等同
Workload 被写成固定门店字段
Policy 直接硬编码进 Solver
Decision Problem 与某 Solver 绑定
Solver Solution 直接写真实业务状态
没有 Baseline 就做结构调整
没有 ChangeCost 就评价 Territory
Coverage Need 与 Coverage Commitment 混为一谈
Scheduling 自动修正上游 Coverage Policy
Agent 可以无 Evidence 自主改变 Territory
```
