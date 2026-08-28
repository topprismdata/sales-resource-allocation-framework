# SRAF World Model Specification v1.2

**项目：** Sales Resource Allocation Framework  
**简称：** SRAF  
**文档：** `01_WORLD_MODEL_SPEC.md`  
**状态：** Implementation Baseline v1.2  
**上位规范：** `00_PROJECT_CHARTER.md`

---

## 1. 文档目标

Sales World Model 负责表达：

> **在某一个时间点，销售市场、客户、机会、服务需求、销售资源、责任关系和业务政策究竟处于什么状态。**

World Model 不负责回答：

> 应该怎么办。

后者属于 Decision Layer。


### 1.1 Normative Ownership Boundary

`01_WORLD_MODEL_SPEC.md` 只正式拥有：

```text
Canonical World Entities
Canonical World Relations
Semantic Status
Temporal Semantics
Evidence / Assertion
Observation / WorldEvent
Derived World State
WorldSnapshot
```

下列概念可以在本文件中被引用以说明边界，但其 canonical schema **不由 01 拥有**：

```text
Baseline               → 02 Decision Ontology
Scenario               → 05 Decision Orchestration
HumanOverride          → 02 Decision Ontology
ProblemProjection      → 03 Decision Problem Contracts
CandidateDecision      → 02 Decision Ontology
ApprovedDecision       → 02 Decision Ontology
ExternalIdentifier     → 08 Canonical Identity & Entity Resolution
IdentityResolutionRecord → 08 Canonical Identity & Entity Resolution
```

因此 World Model 不应复制这些对象的独立 schema。

因此必须严格保持：

```text
WORLD
  ↓
STATE
  ↓
DECISION PROBLEM
  ↓
DECISION
```

而不是：

```text
Solver Model
   ↓
World
```

---

## 2. World Model 的正式定义

SRAF 中：

\[
WorldModel_t
=
Entities_t
+
Relations_t
+
Assertions_t
+
Policies_t
+
Observations_{\le t}
+
Events_{\le t}
+
DerivedStates_t
\]

同时每个重要状态必须具备：

```text
identity
time
source
semantic status
provenance
confidence（如适用）
```

所以 SRAF World Model 本质上是一个：

# **Temporal, Evidence-aware Business World Model**

即：

> 带时间、带来源、带证据的销售业务世界模型。

---

## 3. World Model 不等于数据库

这是工程实现必须明确的一点。

逻辑上：

```text
Sales World Model
```

是 Canonical Semantic Model。

物理上可以由多个存储组成：

```text
┌───────────────────────────────┐
│      SALES WORLD MODEL        │
├───────────────────────────────┤
│ Canonical State Store         │
│ Event / Observation Store     │
│ Evidence Store                │
│ Spatial Store                 │
│ Graph Projection              │
│ Analytical / Feature Store    │
└───────────────────────────────┘
```

因此禁止形成：

> “World Model = Neo4j”

或者：

> “World Model = PostgreSQL”。

数据库是实现。

World Model 是语义。

---

## 4. v1.2 的物理架构原则

建议第一版采用：

```text
                Source Systems
                      │
                      ↓
             Ingestion / Mapping
                      │
                      ↓
          ┌─────────────────────┐
          │ Canonical World API │
          └─────────┬───────────┘
                    │
       ┌────────────┼─────────────┐
       ↓            ↓             ↓
Relational      Event Store    Evidence
State Store                   / Artifact
       │
       ├────────────┐
       ↓            ↓
Spatial Index   Graph Projection
       │            │
       └──────┬─────┘
              ↓
       Problem Projection
              ↓
         Decision Engine
```

---

## 5. 为什么 Canonical State 以关系模型为主

SRAF 最重要的对象，例如：

```text
Account
SalesResource
ResourceDeployment
CoverageCommitment
ResponsibilityAssignment
Policy
WorldSnapshot
```

具有明显：

- stable schema；
- temporal validity；
- uniqueness；
- referential integrity；
- lifecycle；
- transactional consistency。

例如：

```text
ResponsibilityAssignment
```

不能因为图查询方便就允许同一个 Primary Responsibility 出现两个互相冲突的 active relation。

这类约束关系型模型更适合承担。

因此：

> **Canonical State Store 是 Source of Truth。**

Graph 是 Projection。

不是反过来。

---

## 6. 为什么不能“全部 Event Sourcing”

Event Sourcing 对历史恢复非常有价值。

但如果要求：

> 所有当前世界状态只能通过完整 replay event 得到，

对 SRAF 并没有必要。

大量数据其实来自：

```text
ERP Master Data
HR
CRM
External POI
Market Model
Road Network
```

这些本来就是外部系统当前状态。

因此 SRAF 使用：

# State + Event Hybrid

而不是 Pure Event Sourcing。

---

## 7. Event Store 的职责

Event Store 主要用于记录：

> **世界发生了什么重要变化。**

例如：

```text
AccountCreated
AccountClosed

ResourceJoined
ResourceLeft

OpportunityUpdated

CoveragePolicyChanged

ResponsibilityAssigned
ResponsibilityTransferred

TerritoryActivated

ResourceDeploymentChanged

DecisionApproved

TransitionStarted

VisitCompleted
```

Event 主要支持：

```text
history
audit
baseline reconstruction
change detection
causal analysis
decision validation
```

---

## 8. Observation 与 Event 必须分开

这是一个重要语义边界。

### Observation

表示：

> 我们观察到了什么。

例如：

```text
ActualVisit
ActualTravelTime
ObservedServiceTime
POS Sales
StoreClosedSignal
GPS Visit Evidence
```

Observation 不一定意味着世界状态立即变化。

### Event

表示：

> 系统确认某个世界状态发生了变化。

例如：

```text
StoreClosedSignal
```

可能只是 Observation。

只有经过：

```text
verification
```

以后，才产生：

```text
AccountClosed
```

所以：

```text
Observation
     ↓
Interpretation / Validation
     ↓
Event
     ↓
State Transition
```

不能合并。

---

## 9. Canonical Identity Model

所有 Canonical Entity 必须有系统稳定 ID。

建议：

```text
entity_id
```

采用：

```text
<entity_type>:<UUID>
```

例如：

```text
account:4de8...
resource:82ff...
territory:a38c...
```

但 UUID 只是内部 identity。

不能使用：

```text
CRM customer code
employee number
POI ID
ERP ID
```

作为 Canonical ID。

因为同一个真实实体可能来自多个系统。
> **Schema 归属说明**：以上是不可违反的**原则**。
> Canonical ID 生命周期、identity_domain、永不复用/重建规则、
> 以及「多源记录凭什么算同一个对象」的判定与治理规则，
> 由 `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` 拥有，
> 本文件不重复定义其 schema（Charter P21）。

---

## 10. External Identifier

因此必须有统一的：

```text
ExternalIdentifier
```

它承载一个真实对象在各个外部系统中的编号，
并至少满足以下事实要求：

```text
必须能表达「哪个系统的哪种编号」
必须带有效期
编号变化不得覆盖历史
```

例如：

```text
entity:
account:123

source_system:
SAP

external_id:
CUS_99821
```

同一个 Account 可以同时存在：

```text
SAP ID
CRM ID
Tencent POI ID
Internal MDM ID
```

> 上例只说明「多编号可共存」这一事实要求。
> `ExternalIdentifier` 的 canonical schema、identifier_type 强度分级、
> 编号迁移（旧 ID → 新 ID）与退役规则，
> 见 `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §6。

---

## 11. Canonical Entity Categories

v1.2 不要求所有对象直接放进同一张 Entity 表。

但逻辑上必须属于以下六类：

```text
WORLD OBJECT
│
├── Actor
├── Business Object
├── Spatial Object
├── Resource Object
├── Responsibility Object
└── Decision Context Object
```

---

## 12. Actor

表示具有行为或责任能力的主体。

例如：

```text
Person
Organization
SalesResource
Distributor
Partner
```

注意：

```text
Person
```

与：

```text
SalesResource
```

不是同一个对象。

---

## 13. Person

Person 表示真实人员。

它可以具有：

```text
employee relationship
home location
organizational relation
skills
employment state
```

但：

> Person 不天然等于 Sales Resource。

例如一个销售经理可能：

```text
Person = active
```

但暂时没有：

```text
allocatable field capacity
```

---

## 14. SalesResource

SalesResource 表示：

> **可以被分配用于完成 Sales Responsibility 的能力单元。**

它可以由：

```text
Person
Team
Shared Pool
External Partner
Digital Agent
```

实现。

因此：

```text
Person
   ↓ realizes
SalesResource
```

而不是继承关系。

---


## 14A. Capability

`Capability` 是受控的销售能力语义，而不是任意字符串标签。

例如：

```text
GeneralSelling
KeyAccountNegotiation
Merchandising
ProductSpecialist
Audit
Training
```

结构至少包括：

```text
capability_id
capability_type
description
eligibility_semantics
version
```

`Capability` 可用于：

```text
ResourceArchetype
SalesResource
Responsibility
CoverageNeed
DecisionProblem
```

但不得从历史销售额自动推导成事实。

---

## 14B. SalesActivity

`SalesActivity` 表示销售责任中实际需要完成的活动类型。

例如：

```text
Sell
Merchandising
OrderTaking
Negotiation
Audit
Training
```

它是 `CoverageNeed`、`CoverageCommitment`、`WorkloadDemand` 与 `Responsibility` 的共同语义锚点。

---

## 14C. ServiceChannel

`ServiceChannel` 表示服务通过何种资源/接触方式完成。

第一版至少支持：

```text
Field
Phone
Digital
Distributor
Agent
Hybrid
```

`ServiceChannel` 与 `ResourceArchetype` 相关，但二者不是同义词。

---

## 15. ResourceArchetype

表示标准资源能力模板。

例如：

```text
FieldRep.TT
FieldRep.KA
Merchandiser
InsideSales
```

结构至少包括：

```text
resource_type
capability_set
default_capacity_model
mobility_mode
cost_model
service_channel
```

它主要用于：

```text
Greenfield
Sizing
Scenario
Resource Requirement
```

---


## 15A. ResourceRequirement

`ResourceRequirement` 表示在某一 Market / Scope / Period 下，经资源规划后形成的**计划能力需求**。

它不是员工，也不是已实际部署的 SalesResource。

结构至少包括：

```text
requirement_id
resource_archetype_id
scope
period

required_capacity
capacity_unit
recommended_range

opportunity_context
coverage_context
confidence

originating_decision_id
```

典型来源：

```text
DP01 Resource Sizing
Greenfield Workflow
Expansion Workflow
```

---

## 16. ResourcePool

表示可共享资源集合。

例如：

```text
East China KA Team
Changsha Merchandising Pool
National Inside Sales Pool
```

ResourcePool 可以有：

```text
capacity
scope
capability
sharing_policy
```

这样一些责任无需立即绑定具体 Person。

---

## 17. ResourceDeployment

这一对象是 SRAF World Model 中的核心。

定义：

> **在某个空间、组织或市场范围内，被计划或激活的一项销售能力部署位（resource position）。**

`ResourceDeployment` 可以处于：

```text
planned
vacant
filled
inactive
```

因此它在 Greenfield / Expansion 场景中可以先于具体人员存在。

结构至少包括：

```text
deployment_id
resource_archetype_id

base_location
market_scope

required_capacity
capacity_unit

deployment_status

effective_from
effective_to

originating_decision_id
```

注意：

```text
Person.home_location
```

是人员事实。

```text
ResourceDeployment.base_location
```

是业务部署位置。

二者必须分开。

也必须区分：

```text
ResourceDeployment
!=
SalesResource
```

“部署位在哪里、需要什么能力”与“当前由哪个实际资源填充”是两个不同事实。

---

## 17A. DeploymentAssignment

`DeploymentAssignment` 表示某个实际 `SalesResource` 在某段时间填充某个 `ResourceDeployment`。

结构至少包括：

```text
deployment_assignment_id
deployment_id
sales_resource_id

effective_from
effective_to
status

source_approved_decision_id
```

因此：

```text
DP02 Resource Location
```

主要改变 `ResourceDeployment`；

而：

```text
DP04 Personnel Matching
```

主要改变 `DeploymentAssignment`。

---

## 18. Capacity Model

Capacity 必须是时间相关对象，而不是 SalesResource 的一个数字。

定义：

```text
CapacitySupply
```

例如：

```text
resource
period
nominal_capacity
available_capacity
committed_capacity
allocatable_capacity
capacity_unit
source
```

允许：

```text
hour
FTE
visit-equivalent
activity-unit
```

但同一 Decision Problem 必须声明单位体系。

---

## 19. Market

Market 表示：

> 某一销售决策语境下定义的市场。

例如：

```text
长沙饮料餐饮渠道
中国现代渠道
华东医院市场
```

它不是简单行政区。

Market 可以由：

```text
geography
channel
product
customer segment
business context
```

共同定义。

---

## 20. GeoUnit

GeoUnit 是基础空间计算单位。

例如：

```text
H3 Cell
Grid
Administrative Unit
Trade Area
Postal Zone
```

GeoUnit 用于：

```text
aggregation
demand surface
spatial index
territory projection
```

但：

\[
GeoUnit \neq Territory
\]

---

## 21. ServiceLocation

表示实际发生销售活动的物理位置。

例如：

```text
Store
Restaurant
Hospital
Warehouse
Office
```

结构至少包括：

```text
geometry
address
access information
opening status
valid time
```

Account 和 ServiceLocation 是多对多可能关系。

---

## 22. Account

Account 是：

> **商业责任对象。**

例如：

```text
单店客户
连锁总部
经销商
医院
企业客户
```

因此：

```text
Account
```

与：

```text
ServiceLocation
```

不能混为一个对象。

---

## 23. Prospect

Prospect 可以与 Account 共用上位类：

```text
CommercialEntity
```

但在 v1.2 中，我建议保持状态区别：

```text
Prospect
Account
```

而不是：

```text
is_customer = false
```

因为 Prospect 在 Coverage 和 Ownership 上经常有不同业务规则。

---

## 24. MarketSignal

MarketSignal 表示：

> 用于理解市场状态的观测或指标。

例如：

```text
POI density
O2O activity
population
commercial density
historical sales
footfall
```

MarketSignal 不是 Opportunity。

它只是 Evidence。

---

## 25. OpportunityEstimate

这是 World Model 最关键对象之一。

Opportunity 不允许作为：

```text
account.potential_score
```

这种裸字段存在。

必须有独立 Estimate 语义：

```text
OpportunityEstimate

subject_id
opportunity_type
metric
value
unit

valid_from
valid_to

estimate_time

source_type
source_id

confidence

model_id
model_version
evidence_set_id
```

---

## 26. OpportunityType

至少允许：

```text
CurrentValue
Potential
IncrementalPotential
GrowthPotential
WhitespaceOpportunity
RiskAdjustedOpportunity
```

框架不得假设：

```text
potential
```

只有一个统一含义。

具体项目必须声明 Opportunity Metric Contract。

---

## 27. Assertion Model

这是 Evidence-aware World Model 的基础抽象。

统一结构：

```text
Assertion

subject
predicate
object / value

semantic_status

valid_time
observed_time

source
confidence

evidence
```

例如：

```text
Account A
HAS_CHANNEL
Restaurant
```

可以来自：

```text
HumanJudgment
```

而：

```text
Account A
BELONGS_TO_DISTRIBUTOR
Distributor X
```

可能来自：

```text
MasterDataFact
```

---

## 28. Semantic Status

v1.2 固定：

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

任何非简单主数据对象原则上都应该能够追踪其 Semantic Status。

---

## 29. Evidence

Evidence 不是一个字符串备注。

应该独立表达：

```text
Evidence

evidence_id
type
source
reference
timestamp
quality
```

例如：

```text
ERP Record
POS Record
POI Record
Model Output
Photo
GPS Trace
Human Review
External Dataset
```

一个 Assertion 可以关联多个 Evidence。

---

## 30. Provenance

所有重要 Estimate / Derived State 至少需要知道：

```text
created_by
method
input_version
model_version
calculation_version
timestamp
```

这样例如：

```text
Potential = 82
```

才能回答：

> 82 是怎么来的？

---

## 31. Temporal Model

SRAF 必须至少支持：

# Bitemporal Semantics

即区分：

```text
Valid Time
```

与：

```text
System / Knowledge Time
```

例如：

```text
门店实际上 8月1日已经关闭
```

但是系统：

```text
8月12日才知道
```

应该表示：

```text
valid_from = Aug 1
known_from = Aug 12
```

否则历史 Baseline 会被未来信息污染。

---

## 32. 为什么 Bitemporal 很重要

假设我们要回测：

> 7 月 31 日 SRAF 当时做出的 Territory Decision 是否合理。

就只能使用：

```text
known_at <= July 31
```

的数据。

不能用：

> 8 月后来才知道的事实。

否则 Benchmark 会出现：

# Look-ahead Bias

---

## 33. CoverageNeed

CoverageNeed 表示：

> **基于客户状态、机会、业务目标与政策产生的销售服务需求。**

例如：

```text
subject
activity
purpose

eligible_resource_archetypes
service_channel

minimum_frequency
preferred_frequency
maximum_frequency

expected_service_time

service_window
priority

valid_period

policy_source
```

注意：

\[
CoverageNeed \neq Commitment
\]

---

## 34. CoverageCommitment

表示：

> **经过资源配置决策后，组织正式决定实际承担的 Coverage。**

例如：

```text
Account A
SalesVisit
3 / month
```

CoverageCommitment 必须能引用：

```text
originating_decision_id
```

这样可以知道：

> 为什么原来 2 访现在变成 3 访。

---

## 35. WorkloadDemand

WorkloadDemand 必须是 Derived State。

至少区分：

```text
IntrinsicWorkload
NetworkWorkload
TotalWorkload
```

其中：

\[
IntrinsicWorkload
=
\sum_{activity}
CoverageCommitment_{activity}
\times
ExpectedServiceTime_{activity}
\]

因此 Workload 的最小合理粒度是：

```text
subject × activity × period
```

而不是把一个固定 `workload_hours` 写在 Account 上。

NetworkWorkload 不能简单固定在 Account 上。

它依赖：

```text
ResourceDeployment
Territory
Schedule
TravelNetwork
```

---

## 36. DemandSurface

DemandSurface 是空间聚合 Derived State。

它不能替代原始 Account / Coverage 数据。

例如：

```text
DemandSurfaceCell

geo_unit_id
period

opportunity
coverage_need
intrinsic_workload
prospect_count
account_count

source_snapshot
calculation_version
```

它主要供：

```text
Sizing
Location
Macro Territory
Scenario
```

使用。

---

## 37. Responsibility

v1.2 中建议把：

```text
Responsibility
```

和：

```text
ResponsibilityAssignment
```

区分。

Responsibility 表示：

> 什么销售责任需要被承担。

例如：

```text
Account A
Product Beverage
Activity Sell
Role Primary
```

这是一种待分配责任。

---

## 38. ResponsibilityScope

用于定义责任范围。

至少允许：

```text
Account
AccountGroup
Geography
Product
Channel
Activity
CustomerSegment
```

例如：

```text
scope:
AccountGroup = Walmart China
```

或：

```text
scope:
Geo = Territory T17
Activity = Merchandising
```

---

## 39. ResponsibilityAssignment

表示：

> 谁在什么时间承担什么责任。

核心结构：

```text
assignment_id

responsibility_id

resource_id / resource_pool_id

assignment_role

effective_from
effective_to

assignment_status

source_approved_decision_id

relationship_state
```

Assignment 必须是 temporal。

---

## 40. Assignment Cardinality

不能假设：

```text
Account → 1 salesperson
```

真正关系是：

\[
Responsibility
\rightarrow
Resource
\]

因此同一个 Account 可以同时有：

```text
Primary Selling
Merchandising
KA Negotiation
Product Support
```

多个 Assignment。

---

## 41. Assignment Conflict

Ontology 必须允许定义：

```text
exclusive responsibility
```

例如：

```text
Primary Territory Selling
```

可能禁止：

```text
2 active primary owners
```

但：

```text
Merchandising
```

可以与：

```text
Selling
```

同时存在。

这类规则属于：

```text
Responsibility Policy
```

而不是数据库字段语义。

---

## 42. RelationshipState

用于表达 Assignment 的关系连续性。

例如：

```text
relationship_age
relationship_strength_estimate
handover_complexity
change_sensitivity
```

其中 Estimate 类型必须带 Evidence 和 confidence。

不能把：

```text
relationship_strength = 0.9
```

当绝对事实。

---

## 43. Territory

v1.2 正式定义：

> **Territory 是在给定时间与业务语境下，为形成一致销售资源部署而组织的一组 Responsibility 的逻辑集合。**

`ResponsibilityAssignment` 表示这些 Responsibility 当前由哪个 Resource / Deployment 承担，但 Assignment 变化不应自动改变 Territory 的业务 identity。

因此：

```text
Territory
```

必须能够存在：

```text
zero polygon
multiple polygons
non-contiguous geography
nationwide account list
```

---

## 44. TerritoryType

第一版至少允许：

```text
GeographicFieldTerritory
AccountTerritory
KeyAccountTerritory
ChannelTerritory
ProductTerritory
SpecialistTerritory
HybridTerritory
```

不要为每一种建不同核心模型。

---

## 45. TerritoryMembership

Territory 与 Responsibility 之间使用：

```text
TerritoryMembership
```

作为 canonical membership relation。

最小结构：

```text
territory_membership_id
territory_id
responsibility_id

effective_from
effective_to
status
```

禁止把：

```text
ResponsibilityAssignment
```

作为 Territory 的 canonical membership。

原因是：

> Resource / Personnel 发生替换时，Territory 不应因此被错误地重建为一个新 Territory。

同样禁止把：

```text
territory_id
```

直接塞进 Account 作为唯一责任语义。

---

## 46. TerritoryProjection

Territory 的地图表达必须是独立派生对象：

```text
TerritoryProjection
```

例如：

```text
projection_type = polygon
method = alpha_shape_v3
source_assignments = ...
generated_at = ...
```

所以：

```text
Territory.geometry
```

原则上不是 canonical responsibility truth。

---

## 47. 为什么这么设计

假设：

```text
Walmart China KA Territory
```

覆盖：

```text
北京
上海
广州
成都
```

没有任何合理单一 Polygon。

但它仍然是合法 Territory。

这证明：

\[
Territory \neq Geometry
\]

---

## 48. Policy Model

Policy 必须是一等对象。

结构：

```text
Policy

policy_id
policy_type
scope

rule_definition

effective_from
effective_to

source
owner

priority
exception_policy
```

---

## 49. PolicyType

第一版至少：

```text
EligibilityPolicy
ServicePolicy
AllocationPolicy
BoundaryPolicy
ChangePolicy
DecisionPolicy
SchedulingPolicy
```

---

## 50. Policy 不直接存 Solver Expression

例如 Policy：

```text
A类门店原则上每月2访
```

Canonical Model 应表达：

```text
minimum = 2
preferred = 2
scope = segment A
```

而不是：

```text
x[i,d] >= 2
```

数学表达只属于：

```text
Problem Projection / Compiler
```

---

## 51. DerivedState

SRAF 必须明确：

> 派生状态不是原始事实。

例如：

```text
CapacityUtilization
OpportunityCoverage
UncoveredOpportunity
OpportunityAtRisk
LocalAllocationBalanceMetric
TravelBurden
```

都属于：

```text
DerivedState
```

必须带：

```text
calculation_version
input_snapshot
calculated_at
```

---

## 52. State Snapshot

为了 Decision 和 Benchmark，必须支持：

```text
WorldSnapshot
```

定义：

> 在一个明确 Knowledge Time 下，对所需 World State 的不可变引用。

例如：

```text
snapshot_id
as_of_valid_time
as_of_known_time
scope
schema_version
data_version
```

---

## 53. Baseline（Boundary Reference）

`Baseline` 的 canonical schema 由 `02_DECISION_ONTOLOGY.md` 拥有。

World Model 只提供：

```text
WorldSnapshot
```

DecisionCase 将其中一个 WorldSnapshot 选为 Baseline：

```text
Baseline
   → references
WorldSnapshot
```

本文件不再定义独立 Baseline schema。

---

## 54. Scenario（Boundary Reference）

`Scenario` 的 workflow / lifecycle schema 由 `05_DECISION_ORCHESTRATION.md` 拥有。

World Model 只定义以下语义约束：

> Scenario 必须建立在 Baseline / WorldSnapshot 之上，通过 `ScenarioAssumption` 形成虚拟 World View，并且不得修改 Observed World。

示例：

```text
+6 Field Rep
Potential +10%
New Product Launch
Coverage Policy Changed
```

---

## 55. Scenario 不允许修改真实 World State

必须：

```text
Observed World
       ↓
Baseline
       ↓
Scenario Overlay
       ↓
Scenario World View
```

场景失败以后直接丢弃。

不能：

> 先写 World Model，再回滚。

---

## 56. ScenarioAssumption

所有 Scenario 修改都必须具有：

```text
ScenarioAssumption
```

例如：

```text
ResourceCount = 48
```

并明确：

```text
semantic_status = ScenarioAssumption
```

从而 Agent 永远不会把：

> 假设增加 6 人

误读成：

> 现在已经有 48 人。

---

## 57. World Event

统一 Event schema 至少：

```text
event_id
event_type

subject

occurred_at
recorded_at

payload

source
evidence

causation_id
correlation_id
```

其中：

```text
causation_id
```

非常重要。

例如：

```text
DecisionApproved
      ↓ causes
ResponsibilityTransferred
```

未来可以追踪：

> 这个变化到底是哪一个 Decision 导致的。

---

## 58. Observation

统一：

```text
Observation

observation_id
subject
observation_type
value

observed_at
recorded_at

source
evidence
quality
```

Observation 可以不产生 Event。

---

## 59. Decision Origin Tracking

所有由 SRAF 决策产生的结构变化必须能够追踪：

```text
Decision
   ↓
TransitionPlan
   ↓
Event
   ↓
WorldState
```

因此例如：

```text
ResponsibilityAssignment.source_approved_decision_id
```

原则上不能为空，除非来自 Legacy Import 或 External System。

---

## 60. HumanOverride（Boundary Reference）

`HumanOverride` 的 canonical schema 由 `02_DECISION_ONTOLOGY.md` 拥有。

World Model 只承认它可能作为：

```text
Decision Evidence
World Event causation context
future learning evidence
```

被引用。

HumanOverride 不能直接修改 Canonical World；它只能先形成新的 `CandidateDecision`，再经过 Evaluation / Approval / Transition。

---

## 61. Graph Projection

Canonical State Store 之外，可以维护：

```text
Knowledge Graph Projection
```

用于：

```text
Agent reasoning
relationship traversal
evidence navigation
responsibility exploration
causal exploration
```

例如：

```text
Rep17
 ─ASSIGNED_TO→ Responsibility A
 ─DEPLOYED_AT→ Changsha South

Responsibility A
 ─ABOUT→ Account882

Account882
 ─HAS_OPPORTUNITY→ Estimate910
```

---

## 62. Graph 不是事实源

如果 Graph Projection 与 Canonical State 不一致：

> **Canonical State 胜出。**

Graph 必须可以重建。

因此：

```text
Graph Node ID
```

必须引用：

```text
Canonical Entity ID
```

---

## 63. Spatial Store

空间数据可以采用专门 Spatial Store / index。

但必须遵守同样原则：

```text
Geometry
≠
Entity Identity
```

例如同一个 Account 移址：

```text
Account ID
```

不应该变化。

只是：

```text
ServiceLocation
```

产生新的 temporal geometry。

---

## 64. Travel Network

TravelNetwork 不建议存成 World Model 里的巨大 edge graph 本体关系。

Canonical Model 只记录：

```text
network_version
routing_profile
provider
valid_period
calibration_version
```

真实 graph / matrix 属于：

```text
Spatial / Routing Infrastructure
```

World Model 引用版本。

---

## 65. Travel Estimate

如果产生：

```text
TravelTime(A,B)=27min
```

它属于：

```text
DerivedEstimate
```

而不是永久事实。

必须至少知道：

```text
network_version
routing_profile
departure_time / temporal context
calculation_version
```

---

## 66. ProblemProjection

这是 World Model 与 Decision Engine 之间最重要的边界对象。

定义：

> **某个 Decision Problem 对 World State 的只读、目的限定的计算视图。**

例如：

```text
TerritoryAlignmentProjection
```

可以只有：

```text
responsibility unit
opportunity
intrinsic workload
travel proxy
current assignment
boundary rules
capacity
```

---

## 67. ProblemProjection 的原则

Solver 需要的所有：

```text
x[i,j]
candidate cluster
matrix
penalty
encoded constraint
```

都不允许回写 World Model。

所以：

```text
WORLD MODEL
     ↓
ProblemProjection
     ↓
MathematicalModel
```

这个方向是单向的。

---

## 68. Solver Solution 的回流

只能：

```text
Mathematical Solution
        ↓
Decision Interpreter
        ↓
CandidateDecision
```

不能：

```text
Mathematical Solution
        ↓
World State
```

这正式落实 Charter 的：

# Solver State Never Becomes World Truth Directly

---

## 69. World Model Read Patterns

SRAF 至少要支持四类读取：

### Current State Query

回答：

> 现在是什么情况？

### Historical State Query

回答：

> 2026-Q1 当时是什么情况？

### Decision Baseline Query

回答：

> 这个 Decision 当时基于什么状态？

### Scenario Query

回答：

> 如果 Resource +6，会是什么样？

这四种 Query 必须语义明确。

---

## 69A. v1.2 Canonical World Core Set

v1.2 冻结以下 World Core：

```text
Market
GeoUnit
CommercialEntity
Account
Prospect
ServiceLocation

MarketSignal
OpportunityEstimate

Capability
SalesActivity
ServiceChannel

ResourceArchetype
ResourceRequirement
ResourceDeployment
SalesResource
ResourcePool
DeploymentAssignment
CapacitySupply

CoverageNeed
CoverageCommitment
WorkloadDemand
DemandSurface

Responsibility
ResponsibilityScope
ResponsibilityAssignment

Territory
TerritoryMembership
TerritoryProjection

Policy

Assertion
Evidence
Observation
WorldEvent
WorldSnapshot
ExternalIdentifier
```

以下不是 01 的 canonical class：

```text
Baseline
Scenario
HumanOverride
ProblemProjection
CandidateDecision
ApprovedDecision
AllocationGap
ResourceEquivalent
```

它们分别由 Decision / Orchestration / Problem Contract / Metric 层拥有。

---

## 70. World Model Write Patterns

原则上只有四类合法写入：

```text
External State Synchronization
Validated Observation
Confirmed Event / State Transition
Approved Decision Transition
```

Solver、Agent、Simulation 不直接写 Canonical World State。

---

## 71. Data Quality 状态必须进入 World Model

不能假设所有数据都是干净的。

```text
EntityQuality
AssertionQuality
LocationQuality
OpportunityQuality
TravelQuality
CoverageQuality
IdentityConfidence      LOW / MEDIUM / HIGH 或连续值+组成
IdentityStatus          RESOLVED / PROVISIONAL / CONTESTED / UNRESOLVED
```

后两项语义由 `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §16
定义；其值必须可随 Derived State 向下传播
（08 §16.3 IC-4）。

例如：

```text
Account A
location_confidence = LOW
```

这样 Allocation Intelligence 发现异常时可以判断：

> 是业务问题还是数据问题。

---

## 72. Conflict

当不同来源互相矛盾：

```text
CRM:
店铺营业

External:
店铺关闭
```

不能强行静默覆盖。

应该生成：

```text
AssertionConflict
```

并允许：

```text
resolved
unresolved
```

Decision Problem 可以声明：

> unresolved critical conflict 是否允许进入求解。

`AssertionConflict` 的一类具体形态是**身份冲突**
（同一坐标下两个不同结算主体 / 同期双活记录 / 簇内强信号矛盾），
其检测条件、解决路径与人工权限由
`08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §10 TC-3、§19 规定。

---

## 73. World Model Consistency Levels

我建议定义：

```text
Verified
Operational
Estimated
Experimental
```

例如：

### Verified

关键主数据和事实已验证。

### Operational

足够支持生产决策。

### Estimated

包含较多模型估计。

### Experimental

适合 Scenario / Benchmark，不适合直接生产决策。

这样一个 Scenario 可以明确：

```text
WorldConfidence = Experimental
```

---

## 74. Canonical 主链最终固定

在 World Model 层，我们现在可以正式冻结：

```text
Market
   ↓
Commercial Entity
   ↓
Opportunity Estimate
   ↓
Coverage Need
   ↓
Coverage Commitment
   ↓
Workload Demand

Resource Archetype
   ↓
Resource Requirement
   ↓
Sales Resource / Resource Pool
   ↓
Resource Deployment
   ↓
Capacity Supply

Workload Demand
        ↕
Capacity Supply

        ↓
Responsibility Assignment
        ↓
Territory
        ↓
Execution
        ↓
Observation
        ↓
World State Update
```

---

## 75. Canonical vs Derived vs Decision Object

这是 v1.2 必须明确的三层。

| 类型 | 例子 | 是否属于世界事实 |
|---|---|---|
| Canonical State | Account、ResourceDeployment、Assignment | 是 |
| Estimate / Derived State | Opportunity、Workload、Gap | 有来源的计算状态 |
| Decision State | Candidate Territory、Scenario | 否，除非批准实施 |

这里特别重要：

```text
Candidate Territory
```

在 Approved 之前：

> 不是 Territory World State。

---

## 76. Reference Implementation 建议

v1.2 工程上我建议保持简单，不要过早建设复杂的知识图谱平台。

可以先用：

```text
PostgreSQL + PostGIS
```

承担：

```text
Canonical State
Temporal State
Spatial Object
Assignment
Policy
Snapshot Metadata
```

再使用：

```text
append-only event / observation tables
```

实现第一版 Event Store。

Graph Projection 第一阶段甚至可以：

```text
PostgreSQL materialized graph view
```

或者轻量 graph engine。

只有 Agent / complex relation traversal 明确证明需要以后，再引入专门图数据库。

这个非常符合：

> **Reuse Before Reinvent + Minimum Necessary Infrastructure。**

---

## 77. 不建议 v1.2 一开始做的事情

第一阶段不要：

```text
全量 RDF / OWL
复杂 semantic reasoner
全事件溯源数据库
自建时间序列数据库
自建图数据库
自建 MDM
自建 GIS Engine
```

这些都不是当前 SRAF 的核心创新。

SRAF 真正应该先证明：

```text
World semantics
→ Decision problem
→ Candidate decision
→ Evaluation
```

能够跑通。

---

## 78. World Model Architecture Gate

以后开发评审中，出现下面情况应直接视为架构问题：

```text
直接用外部业务 ID 作为 Canonical ID

Account 与物理门店完全等同

Potential 直接成为 Account 字段且无来源

CoverageNeed 和 Commitment 合并

Salesperson 与 Resource 合并

home location 与 deployment location 合并

Territory 强制要求 Polygon

Account 只能有一个 owner

Assignment 没有时间有效期

Solver 字段进入 Canonical Entity

Scenario 直接修改生产 World State

未来获得的数据被用于过去 Baseline

模型 Estimate 没有 model_version

Derived State 没有 calculation_version

Graph 被当作唯一 Source of Truth

Solver Solution 直接更新 Territory
```

这组可以直接成为 CI / Architecture Review Checklist 的基础。

---

## 79. 一个具体例子

假设系统现在看到：

> 长沙河西市场新增 800 家高潜餐饮门店。

正确世界更新应该是：

```text
External POI / O2O
        ↓
Observations
        ↓
Commercial Entity Resolution
        ↓
Prospect / ServiceLocation
        ↓
Market Signals
        ↓
Opportunity Estimates
        ↓
Demand Surface Recalculation
        ↓
Allocation Gap Recalculation
```

此时：

> **Territory 不发生任何自动变化。**

Allocation Intelligence 发现：

```text
Opportunity Gap ↑
Capacity Gap ↑
```

以后才：

```text
DecisionTrigger
       ↓
Expansion / Rebalancing Decision Case
```

这就是 World Model 与 Decision Model 的边界。

---

## 80. 再举一个 Assignment 例子

当前：

```text
Account A
Selling → Rep17
Merchandising → Merch05
KA → KAM02
```

系统不应该表示成：

```text
account.owner = Rep17
```

而是：

```text
Responsibility R1
Account A / Selling / Primary

Assignment A1
R1 → Rep17

Responsibility R2
Account A / Merchandising

Assignment A2
R2 → Merch05

Responsibility R3
Account A / KA Negotiation

Assignment A3
R3 → KAM02
```

于是所谓：

```text
Field Territory T17
```

只聚合：

```text
Selling Primary
```

那一类 Assignment。

这时 Overlay Territory 天然成立。

---

## 81. World Model 最小可用版本

为了避免 Agent 一上来把 v1.2 做成大工程，我建议 **MVP World Model 只实现 14 个核心对象**：

```text
Market
GeoUnit
Account / Prospect
ServiceLocation
OpportunityEstimate
CoverageNeed
CoverageCommitment
SalesResource
ResourceDeployment
CapacitySupply
Responsibility
ResponsibilityAssignment
Policy
WorldSnapshot
```

另外四个 supporting model：

```text
Assertion
Evidence
Observation
Event
```

Territory 可以先作为：

```text
Assignment Group + Projection
```

实现。

等第一个 Territory Decision Engine 开始以后再扩展完整 Territory lifecycle。

---

## 82. Definition of Done

`01_WORLD_MODEL_SPEC` 的实现不能以：

> “表建好了”

作为 Done。

至少必须验证以下链路真的可运行：

```text
Source Data
   ↓
Canonical Account
   ↓
Opportunity Estimate
   ↓
Coverage Need
   ↓
Workload
   ↓
Resource Deployment
   ↓
Responsibility Assignment
```

然后能够：

```text
Create World Snapshot
      ↓
Fork Scenario
      ↓
Generate Problem Projection
      ↓
Run Decision Engine
      ↓
Create Candidate Decision
```

且 Candidate 不污染真实世界。

做到这一点，World Model v1 才算成立。

---

## 83. v1.2 工程架构结论

关于：

> **World Model 到底采用 Event Sourcing、Knowledge Graph 还是关系模型？**

v1.2 正式采用：

```text
                    SRAF WORLD MODEL

             Canonical Relational State
                       │
               Source of Truth
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
 Temporal/Event     Spatial       Evidence
     History        Projection     Provenance
        │              │              │
        └──────────────┼──────────────┘
                       ↓
                 Graph Projection
                       ↓
              Semantic / Agent View
                       ↓
               Problem Projection
                       ↓
                Decision Engine
```

**Relational Canonical State 负责“是什么”；Event/Observation 负责“发生过什么”；Graph 负责“关系如何连接”；Spatial 负责“在哪里”；Evidence 负责“为什么相信”；Problem Projection 负责“这一次优化器需要看到什么”。**

这一边界作为 SRAF v1.2 World Model 的工程基线。
