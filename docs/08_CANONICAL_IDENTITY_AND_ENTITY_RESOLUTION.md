# SRAF Canonical Identity & Entity Resolution Specification v1.2

**项目：** Sales Resource Allocation Framework  
**简称：** SRAF  
**文档：** `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`  
**状态：** Implementation Baseline v1.2  
**上位规范：**

```text
00_PROJECT_CHARTER.md
01_WORLD_MODEL_SPEC.md
```

**下游引用者：** 02 / 03 / 04 / 05 / 06 / 07

---

## 1. 文档目标

`01_WORLD_MODEL_SPEC.md` 规定了世界「如何被表示」：

```text
Canonical ID
ExternalIdentifier
Identity Mapping
Merge / Split Trace
```

但这些只是**接口要求**，不是**决策规则**。

本文件回答真正会决定系统成败的问题：

> **给定来自多个系统的多条记录，SRAF 凭什么认定它们是不是同一个现实实体；
> 认定错了会发生什么；如何撤销；以及谁有权认定。**

它必须把 Identity 从「数据清洗步骤」提升为：

# **一等的、可审计的、带证据和时效的治理对象**

原因见 §3。

---

## 1A. Normative Ownership

本文件唯一拥有：

```text
CanonicalIdentity lifecycle
ExternalIdentifier canonical schema
SourceRecord / Crosswalk
IdentityAssertion（SAME_AS / DISTINCT_FROM）
MatchCandidate / MatchDecision
IdentityCluster
Merge / Unmerge
Split
Supersede / Succession
RelocationResolution
RenameResolution
HierarchyResolution（Account ↔ AccountGroup ↔ ServiceLocation）
SurvivorshipPolicy
IdentityConfidence 语义
HumanIdentityResolution workflow
Identity Temporal Semantics
Identity Benchmark cases & metrics
```

本文件**不拥有**（只引用）：

```text
Account / ServiceLocation / Person 的 canonical 业务属性 schema → 01
Assertion / Evidence / Observation / WorldEvent 通用结构 → 01
Semantic Status 枚举定义 → 01
DecisionCase / CandidateDecision / Approval → 02
Responsibility / Coverage / Opportunity 业务语义 → 01 / 04
GW01 WorldModelRepair workflow → 05
B0 通用语义不变量与 Benchmark 框架 → 06
CanonicalIdentityService 工程实现 → 07
```

`01` 第 9–10 节的 Identity 要求继续有效，但其 **canonical schema 归 08**。
`01` 应改为引用本文件，不得维护第二套字段定义（Charter P21）。

---

## 2. 四条不可混淆的分界线

这是本规范最核心的语义纪律。任何实现、任何 Agent 推理都不得跨越。

### 2.1 Identity Resolution ≠ Deduplication

```text
Deduplication：
    找出「重复录入的记录」并删除。
    对象是 record。
    目标是表变干净。
    成功标准是重复率下降。

Identity Resolution：
    建立「记录 ↔ 现实实体」的映射，并保留每条来源记录。
    对象是 claim about the world。
    目标是 canonical entity 唯一且可追溯。
    成功标准是下游决策不因身份而错。
```

关键差别：

```text
Dedup 会丢数据。
Identity Resolution 永不丢 SourceRecord。
```

一个「看起来重复」的记录对，可能是：

```text
同一家店的两套编码      → 该合并
两家隔壁的同名店        → 该保持区分
同一家店的两个不同业态主体 → 该拆成两个 Account
```

因此 SRAF 禁止出现：

```text
delete from account where duplicate
```

这类操作。只允许：

```text
link
resolve
merge（治理动作，可逆）
supersede
```

### 2.2 Entity Merge ≠ Source Record Merge

```text
Source Record Merge（物理层）：
    把两条 CRM/ERP 记录并成一条。
    改变的是源系统或导入层。

Entity Merge（语义层）：
    宣布「这两个 canonical entity 其实是同一个现实对象」，
    并把它们的历史、责任、机会、覆盖全部重挂到一个 survivor。
    改变的是业务真值，且波及 Opportunity / Territory / Workload。
```

Entity Merge 是一次**决策**，不是一次 ETL。

因此它必须复用 `02` 的治理链路：

```text
IdentityMergeProposal
      ↓
Evidence + ImpactAnalysis
      ↓
Authority（按影响范围分级）
      ↓
Approved Identity Resolution Record
      ↓
WorldEvent + 下游重算
```

**禁止**：属性级 survivorship 自动改写业务身份。

一个实体「该由谁活下来」与「它的地址该显示哪个值」是两个问题：

```text
Survivorship（属性取值规则）  → 决定 golden record 的字段
Identity（实体是否同一个）    → 决定有几个现实对象
```

字段可以按 source-trust / recency 规则自动挑；
实体身份**不可以**按相似度阈值自动合并（§11、§14）。

### 2.3 Account ≠ ServiceLocation

`01 §21–22` 已确立：Account 是商业责任对象，ServiceLocation 是物理位置。
本文件规定它们**身份层面的独立性**：

```text
Account identity：
    由「商业责任连续性」决定
    （合同、结算主体、客户关系、责任归属）

ServiceLocation identity：
    由「物理经营场所连续性」决定
    （坐标、门址、门店经营体）
```

于是四种情形必须可分别表达：

| 情形 | Account | ServiceLocation |
|---|---|---|
| 同店换合同主体 | 新 Account | 同一 Location |
| 客户换址续营 | 同一 Account | 新 Location（旧 Location 关闭） |
| 一址多客户（同楼两家） | 两个 Account | 两个 Location 或共享 Location |
| 一客户多址（连锁片区） | 一个 Account | 多个 Location |

**禁止**：用坐标距离决定 Account 身份。
坐标一致只支持 Location 层的候选关联，不支持 Account 层 SAME_AS。

### 2.4 Identity Confidence ≠ Business Truth

```text
identity_confidence = 0.93
```

它的含义**只能是**：

> 在当前的 match_rule_version、当前证据集、当前模型下，
> 这对记录被同一性主张支持的强度是 0.93。

它**不等于**：

```text
它们确实是同一家店
→ 因此可以合并 Opportunity
→ 因此 workload 是 1.0 而不是 2.0
→ 因此不缺人
```

置信度不能通过下游传播被「洗白」成事实。每条 Derived State 必须能回答：

> 我用到的身份判断，当时置信度是多少、谁批准的、用的哪套规则。

这条直接由 `01 §28 Semantic Status` 承接：

```text
Resolved Identity 的 Semantic Status：
    CONFIRMED_MATCH + 人工批准 → DerivedState（可规划使用）
    PROVISIONAL_MATCH          → 仍带 ModelEstimate 性质，必须传递 confidence
    CANDIDATE                  → 不得进入 Structural Decision
```

---

## 3. 为什么 Identity 是 Decision 前提（而非数据卫生）

### 3.1 错误传播链

```text
Identity Error
      ↓
CommercialEntity 计数错误
      ↓
OpportunityEstimate 重复计入 / 漏计
      ↓
CoverageNeed / CoverageCommitment 目标对象错误
      ↓
WorkloadDemand 错误（IntrinsicWorkload 按 subject × activity 求和）
      ↓
CapacityUtilization 错误
      ↓
AllocationGap（假阳性或假阴性）
      ↓
DiagnosticHypothesis（H-DATA 未触发，H-CAP 被误选）
      ↓
ProblemRouter 路由错误
      ↓
DecisionCase（本该 WorldModelRepair，结果走了 DP01 Expansion）
      ↓
Transition（真实增员、真实换客户负责人、真实 ChangeCost）
```

一旦进入最后一步，错误就已经花掉了钱。

### 3.2 重复计入的定量后果（强制示例）

`01 §35` 冻结：

\[
IntrinsicWorkload
=
\sum_{activity}
CoverageCommitment_{activity}
\times
ExpectedServiceTime_{activity}
\]

若同一门店在 CRM 与 DMS 各有一条未解析记录，且都被判为高潜：

```text
CoverageCommitment: 2/month × 2 = 4/month
IntrinsicWorkload:              ×2
Territory workload:             +Δ（该店贡献翻倍）
CapacityUtilization:            虚高
```

于是：

```text
GlobalCapacityTest → 显示 overload
→ H-CAPACITY 支持证据成立
→ 建议加人
```

而真实原因是：

```text
H-DATA（Identity）
```

这正是 `04 §22` 要求 DataQualityIssue 必须是顶层 alternative hypothesis 的深层理由。
**SRAF 的 H-DATA 假设在 08 落地之前是不可检验的。**

### 3.3 反向风险：过度合并

```text
两家相邻但不同的店被误合并
→ Coverage 表面达标（一个 subject 被覆盖）
→ 实际漏覆盖一家
→ UncoveredOpportunity 被隐藏
→ 系统看起来更健康，业务更差
```

**漏合并（duplicate）与误合并（false match）的失败方向相反**，
但都污染决策。这是 §11 双阈值设计的根据。

### 3.4 对历史回测与验证的污染

```text
Bitemporal replay 要求 identity 也在 known_time 下可复原（§15）
```

若 identity 是「当前态」的单值字段，则：

```text
2026-Q1 的 Baseline 会用 2026-Q3 才发现的合并结果
→ Look-ahead Bias（01 §32 / 06 §10）
→ DecisionValidation 的比较对象被事后修改
→ 无法回答「当时为什么这么决定」
```

因此 identity resolution 结果本身必须是 **bitemporal、append-only、带版本**。

---

## 4. 概念分层

```text
L4  GOVERNANCE
    IdentityResolutionRecord（谁、何时、依据什么、批准了什么）

L3  SEMANTIC
    CanonicalEntity（account:8a2f…）—— 现实对象的唯一表示
    IdentityCluster          —— 被主张为同一对象的 entity 集合
    IdentityAssertion        —— SAME_AS / DISTINCT_FROM

L2  LINKAGE
    IdentityLink             —— SourceRecord ↔ CanonicalEntity 的挂接
    MatchCandidate           —— 待判定的记录对 / 簇
    MatchDecision            —— 三态判定结果

L1  EVIDENCE
    SourceRecord             —— 每个源系统的原始记录（不可变）
    ExternalIdentifier       —— 外部 ID 及其时效
    IdentityEvidence         —— 支撑判定的具体事实
```

不可跳层：L3 的同一性主张只能由 L2 挂接 + L1 证据支撑，
并且必须由 L4 记录其形成过程。

---

## 5. CanonicalIdentity

### 5.1 定义

> **在 SRAF 语义空间内，对一个现实业务对象的唯一、稳定、不复用的身份。**

### 5.2 硬性要求

```text
R-ID-1  永不复用：一个已退役的 entity_id 不得指向另一个现实对象
R-ID-2  永不因外部 ID 变化而变化
R-ID-3  永不因地址 / 名称 / 归属变化而重建
R-ID-4  每个 entity_id 必须声明 entity_type 与 identity_domain
R-ID-5  创建必须带 creation_reason（SOURCE_SYNC / MANUAL / MERGE_SURVIVOR /
        SPLIT_CHILD / PROSPECT_CONVERT）
```

### 5.3 identity_domain

身份判定规则按域不同，禁止一套全局相似度逻辑：

```text
commercial_account     商业客户主体
service_location       物理经营场所
person                 自然人
sales_resource         可分配能力单元
organization           法人 / 集团 / 经销商
distribution_channel   渠道主体
geo_unit               空间单元
```

每个 domain 有自己的：候选属性集、强/弱信号、阻断策略、默认阈值、
人工升级条件。

### 5.4 Entity type 与 domain 的正交

```text
CommercialEntity / Account / Prospect   → identity_domain = commercial_account
Person / SalesResource                  → 两个 domain，各自独立解析
```

**Person 与 SalesResource 必须分别解析身份**：

```text
同一 Person（工号变更 / 换主体签约）
    → 可能对应同一 SalesResource（能力延续）
    → 也可能对应新 SalesResource（新岗位契约）
```

二者混淆会直接污染 `01 §17A DeploymentAssignment` 的时间连续性。

---

## 6. ExternalIdentifier（canonical schema 归 08）

```text
ExternalIdentifier

external_identifier_id
entity_id                 → CanonicalEntity
source_system
identifier_type
external_id
scope                     （如 国家 / BU / 部署环境）
valid_from
valid_to
observed_first_at
observed_last_at
status                    ACTIVE / RETIRED / SUPERSEDED
confidence
resolution_record_id
```

### 6.1 关键约束

```text
EI-1  (source_system, identifier_type, external_id, scope) 在 valid 区间内
      至多指向一个 entity_id —— 除非显式建立 SPLIT / MERGE 后继链
EI-2  同一 external_id 在不同 scope 下允许指向不同 entity
      （SAP client 100 与 200 的 CUS_99821 是两个对象）
EI-3  external_id 退役时不得删除记录，只能置 RETIRED + valid_to
EI-4  一个现实对象的历史编号集合（门店ID 88291 → 223817）
      必须保留为多行，不得覆盖
```

### 6.2 编号变更 ≠ 身份变更

新系统重编码是最常见噪声：

```text
历史系统 门店ID 88291
新系统    门店ID 223817
```

只要迁移映射存在，二者是**同一 entity 的两个 ExternalIdentifier**。
SRAF 必须能在给定 mapping_version 下双向解析，
并保留「某段时间我们只知道 88291」的 knowledge time。

### 6.3 identifier_type 强度分级

```text
STRONG_GOVERNED   税号 / 统一社会信用代码 / 合同号 / 营业执照号
                  （低 u-probability，可单独支撑 PROVISIONAL_MATCH）
STRONG_SCOPED     源系统主键（在明确 scope 内唯一）
MEDIUM            品牌连锁内部门店编码、渠道会员码
WEAK              电话（可能共享）、联系人邮箱、店长姓名
VERY_WEAK         名称、地址文本、经纬度（仅用于 blocking / 特征，不得单独定身份）
```

```text
禁止：仅凭 VERY_WEAK 信号达到 HIGH 相似度即 CONFIRMED_MATCH
```

（Fellegi–Sunter 意义上的可分性要求，见 §16。）

---

## 7. SourceRecord 与 Crosswalk

```text
SourceRecord

source_record_id
source_system
source_table / source_endpoint
source_primary_key
extracted_at
payload_hash
schema_version
ingestion_run_id
```

```text
IdentityLink

link_id
source_record_id
entity_id
link_basis            DIRECT_MAPPING / MATCH_DECISION / MANUAL / MIGRATION
confidence
match_rule_version
created_at
retired_at
resolution_record_id
```

### 7.1 原则

```text
SR-1  SourceRecord 不可变、不删除（即使被判定为重复）
SR-2  删除只发生在 link 层：retire 一条 IdentityLink
SR-3  一条 SourceRecord 在给定 as_of 时刻至多有一个 ACTIVE link
      （多对一临时允许时，必须产生 AssertionConflict）
SR-4  一个 entity 可以有多条 ACTIVE link（多源汇聚，属正常态）
```

### 7.2 迁移与 legacy

```text
Legacy Import 的 IdentityLink 允许 resolution_record_id 为空，
但必须标 link_basis = MIGRATION 且 confidence 来源为
「批次映射表版本」而非模型分数。
```

---

## 8. IdentityAssertion

复用 `01 §27 Assertion Model` 的结构，只规定 identity 专用谓词：

```text
predicate ∈ {
  SAME_AS,                 主张同一（在指定 identity_domain 内）
  DISTINCT_FROM,           主张不同（负向主张，同样重要）
  PART_OF,                 层级归属（store ∈ chain）
  OPERATES_AT,             Account ↔ ServiceLocation 时间性关联
  HAS_SUCCESSOR,           继承关系（§13）
  IS_RELOCATION_OF         址变体不变（§12）
  IS_RENAME_OF             名变体不变（§12）
}
```

必填：

```text
subject / object
identity_domain
semantic_status
valid_time / observed_time
source / confidence / evidence[]
assertion_strength          CANDIDATE / PROVISIONAL / CONFIRMED
rule_or_actor               match_rule_version 或 human actor
```

### 8.1 负向主张必须存在

```text
DISTINCT_FROM 是防止「反复被同一个 matcher 提议」的机制。
```

没有负向记忆的系统会在每轮重跑中重复骚扰同一对候选，
并把已被人工否决的假设重新推上队列。

```text
AD-1  人工判定「不是同一个」必须写为 CONFIRMED DISTINCT_FROM
AD-2  该主张默认对后续 match_rule_version 生效（需显式撤销才能重开）
AD-3  撤销必须记录 reason（新证据 / 规则变更 / 误操作）
```

---

## 9. MatchCandidate 生成（Blocking / Indexing）

身份解析在真实规模下不可全量两两比较。

```text
accounts 200k → 2×10¹⁰ pairs
```

本规范要求：

```text
MB-1  必须存在 blocking 层，并把 recall-of-blocking 作为显式被测指标
MB-2  blocking key 不得使用单一弱属性（纯名称 / 纯坐标）
MB-3  必须支持「标准 blocking 漏掉」的补充召回通道：
      人工提名 / 地址近似检索 / 图邻居扩展 / 电话与结算号反查
MB-4  blocking 策略必须版本化：blocking_version
MB-5  L 档规模下（07 §110A）必须报告候选对数量级与内存预算
```

候选来源分类：

```text
BLOCKED_PAIR          blocking 命中
NEIGHBOR_EXPANSION    图 / 空间近邻扩展
HUMAN_REFERRAL        人工提名
MIGRATION_RESCAN      迁移批次重扫
IMPACT_RECHECK        下游异常回查（见 §14）
```

---

## 10. Matcher 与特征

允许并存的 matcher（可组合，不得只允许一种）：

```text
RULE          确定性规则（强 ID 精确一致、合同号一致）
FS_WEIGHTED   Fellegi–Sunter 式字段级权重累加
ML_MODEL      分类器（pairwise 匹配概率）
LLM_ASSISTED  语义辅助（仅可用于产生/解释候选，
              不得单独产出 CONFIRMED_MATCH）
EMBEDDING     向量近邻（用于候选生成与特征）
```

特征必须按 identity_domain 声明。commercial_account 至少包含：

```text
name_normalized / name_token_overlap
brand_or_chain_marker
address_text_similarity
coordinate_distance
geo_unit_relation（同 cell / 邻 cell）
phone / settlement_account agreement
legal_entity_id agreement
category / format agreement
manager or contact overlap
sales-series continuity（同一家店的历史销量序列不应断裂）
temporal co-occurrence（两条记录是否在同一时间窗内都活跃）
```

### 10.1 反 chaining 约束

```text
TC-1  禁止无约束 single-linkage 传递闭包
      （A≈B、B≈C 导致 A≈C 的链式误并是 MDM 的头号事故来源）
TC-2  簇内一致性必须检查：
      cluster 内任意两两的支撑证据不得存在冲突强信号
      （不同 legal_entity_id / 同坐标不同结算主体 / 同期双活）
TC-3  冲突强信号出现时，簇必须拆分回候选态并进入人工队列
TC-4  簇增长速率必须被监控：单簇在 short window 内吸收过多 entity
      → 自动降为 PROVISIONAL 并要求复核
```

---

## 11. MatchDecision 三态

```text
MatchDecision

decision_id
pair_or_cluster_ref
identity_domain
outcome ∈ { MATCH, NON_MATCH, UNCERTAIN }
score
thresholds_applied
rule_set_version / model_version / blocking_version
evidence[]
generated_by            RULE / MODEL / HUMAN
created_at
resolution_record_id
```

三态而非二态是强制的：

```text
MATCH       可自动建 link；是否可合并见 §12
NON_MATCH   写入 DISTINCT_FROM
UNCERTAIN   进入人工队列，不得被下游当作任何一种
```

### 11.1 阈值必须以错误率定义，不以分数定义

```text
禁止：score > 0.9 → 自动合并
```

必须声明**可容忍错误率**，再由校准后的分数反推阈值：

```text
max_false_match_rate      λ     （误并容忍度）
max_false_non_match_rate  π     （漏并容忍度）
review_band               [t_low, t_high] → UNCERTAIN
```

Fellegi–Sunter 的原始贡献正是这个：在给定两类错误率上界下，
最优决策规则就是把似然比分到三个区间，中间交给 clerical review。
本规范直接采纳该框架。

### 11.2 两类错误的非对称代价（强制）

代价必须按域与影响显式配置：

```text
False Match（误并）     → 覆盖被隐藏、责任归属被抹除、客户交接被误记
                         通常难以被业务发现，损害长期信任
False Non-Match（漏并） → workload 虚高、假 CapacityGap、误触发增员
                         通常可被诊断发现（同址同名双记录显眼）
```

SRAF 默认取**保守侧**：

```text
AM-1  自动 MATCH 的 λ 必须显著严于自动 NON_MATCH 的 π
AM-2  任何会触发 Structural Decision 的身份主张，必须 CONFIRMED
AM-3  UNRESOLVED 且影响 Materiality 的候选 → 阻断 Trigger（见 §14）
```

### 11.3 校准

```text
CAL-1  分数必须校准到可解释概率（同置信度区间内的真实匹配率一致）
CAL-2  必须报告 calibration curve / ECE，按特征分片报告
CAL-3  禁止「所有结论 0.9 以上」（06 §39 同一纪律适用于 identity）
CAL-4  校准集不得与被评估集共享人工标注来源，避免自证
```

---

## 12. 八种情形的判定规则

用户提出的真实疑难场景，本规范要求每种都有**可执行的判别流程**。

判定按顺序问：

```text
Q1 是否同一现实对象？（SAME_AS）
Q2 若是，是否同一责任主体？（Account 层）
Q3 若是，是否同一物理场所？（Location 层）
Q4 变化性质是什么？（名 / 址 / 主体 / 拆分 / 合并 / 继承）
```

### 情形 1：Same Entity（正常多源汇聚）

```text
例：上海永辉XX店（CRM） + 永辉超市上海XX店（DMS） + 永辉生活XX（POI）
支持：brand marker 一致 + 坐标 < d_loc + 地址文本高相似 + 结算/合同号一致
判定：MATCH（可 CONFIRMED 若含 STRONG_GOVERNED 一致）
动作：三条 SourceRecord link 到同一 account entity
禁止：改写任何源系统记录
```

### 情形 2：Duplicate Entity（同系统内重复录入）

```text
例：CRM 内部两条同店记录
判定：MATCH + 同 source_system
动作：仍不删源记录；两 SourceRecord 可 link 同一 entity，
      其中一条标 status = DUPLICATE_WITHIN_SOURCE 供导入层降噪
必须：产生 IdentityEvidence 说明为何不是两家相邻门店
```

### 情形 3：Same Account + Different ServiceLocation

```text
例：客户（KA 集团）在北京、上海各有门店
判定：NOT SAME_AS（account 层），各自 OPERATES_AT 不同 location
禁止：因「同品牌」把两家店并成一个 account entity
正确建模：
    AccountGroup(永辉华东) → PART_OF → 各 store Account
    store Account → OPERATES_AT → ServiceLocation
```

### 情形 4：Store Relocation（换址）

```text
判别信号（按优先级）：
    合同/结算主体连续 且 客户责任连续     → 支持 relocation
    同负责人 + 同员工 + 同货架/许可      → 支持 relocation
    坐标变化 > d_relocate + 旧址出现关闭信号 → 支持 relocation
    新址与旧址同城不同商圈且同期双活       → 反对 relocation（是两家）
判定：IS_RELOCATION_OF（Account 同一，Location 不同）
动作：
    ServiceLocation_old.valid_to = 关闭日（valid_time）
    ServiceLocation_new 新建，valid_from = 开业日
    Account entity_id 不变（01 §63）
    ResponsibilityAssignment 默认连续，除非业务显式要求重开关系
影响：
    Opportunity 序列连续性保留 → 但必须在 history 上插入「搬迁断点标记」，
    否则销量序列被误读为需求崩塌（→ ModelGovernance 误判）
```

### 情形 5：Store Rename / Rebranding

```text
判定：IS_RENAME_OF（Account 与 Location 均同一）
动作：属性时间版本（名称产生新的 temporal assertion），entity_id 不变
禁止：因名称变化产生新 entity
注意：品牌翻牌（永辉→其他连锁）不必然等于 Account 变化，
      必须同时看 legal entity / 合同主体 是否变化：
        合同主体未变 → 同一 Account，翻牌记为属性变更
        合同主体变化 → 触发情形 8（Succession）判定
```

### 情形 6：Store Split（一拆二）

```text
例：一家大店拆成两家小店，各自独立签约
判定：父 entity 关系由 MERGE 逆操作表达为 SPLIT
动作：
    parent Account → status = SPLIT_INTO, valid_to = 拆分生效日
    child A / child B：新 entity_id，各自 HAS_PARENT = parent
    历史归属规则（强制声明，不得默认）：
        history_attribution ∈ { PARENT_ONLY, PROPORTIONAL, PRIMARY_CHILD }
    默认 PARENT_ONLY + 显式 split_note（避免虚假增长被读成 organic growth）
禁止：让 child 直接继承 parent 的 entity_id（破坏 R-ID-1/R-ID-3 可追溯性）
下游：DemandSurface / 历史 replay 必须能重算三种 attribution 下的曲线
```

### 情形 7：Store Merge（二合一）

```text
例：两家店合并经营
判定：MERGE，产生 survivor
动作：
    loser Account → SUPERSEDED_BY survivor, valid_to = 合并生效日
    loser 的 Opportunity / Workload / Coverage 历史保留在 loser 时间轴上，
      不得静默搬到 survivor 名下（会造成 survivor 历史销量虚假增长）
    需要「合并后经营体」与「原两家」的映射表用于回测
    ResponsibilityAssignment：loser 的 active assignment 必须显式迁移或终止
    TerritoryMembership：随 Responsibility 存续关系更新（01 §45）
Impact：合并前后的销量断层必须在 Derived State 上打「discontinuity」标记
```

### 情形 8：False Match（误并的识别与恢复）

```text
发现渠道：
    人工投诉 / IMPACT_RECHECK（§14）/ 双活检测 / 同期两个 GPS 轨迹
动作：Unmerge
    创建新的 IdentityResolutionRecord（不覆盖旧记录）
    被吸收的 SourceRecord 重新 link 回原 entity
    受影响的历史 Derived State 重算并记录 recalculation_run_id
    若已发生真实 Decision（增员/换负责人），必须产生 LearningSignal：
        IdentityErrorCausedDecision
必须：False Match 可发现性设计为强制项 —— 任何 merge 都必须可解
```

### 判定表汇总

| # | SAME_AS | Account | Location | canonical 动作 |
|---|---|---|---|---|
| 1 | 是 | 同一 | 同一 | link |
| 2 | 是 | 同一 | 同一 | link + DUPLICATE_WITHIN_SOURCE |
| 3 | 否 | 不同 | 不同 | OPERATES_AT + PART_OF |
| 4 | 部分 | 同一 | 不同 | IS_RELOCATION_OF |
| 5 | 是 | 同一 | 同一 | IS_RENAME_OF |
| 6 | 父→子 | 派生 | 派生 | SPLIT |
| 7 | 多→一 | 存活一个 | 可能换 | MERGE |
| 8 | 撤销 | — | — | UNMERGE |

---

## 13. Supersede / Succession

```text
Supersede 回答的是：
    「这个对象不在了，后继者是谁？」
```

与 MERGE 的区别：

```text
MERGE   ：两个其实一直是一个（身份判断错误纠正）
Supersede：时间上确实先后存在的两个对象（继承关系）
```

典型场景：

```text
门店关停后原址新开        → 新 entity，HAS_SUCCESSOR 关系（若业务上视为延续）
经销商被替换              → 新 organization，继承服务责任
连锁并购（被收购方主体注销）→ 收购方 entity 继承合同责任
Prospect → Account 转化   → 同一 entity，状态变更（不得新建 ID）
```

### 13.1 规则

```text
SUP-1  Supersede 不合并身份：两个 entity_id 都保留
SUP-2  必须声明 succession_kind：
       RELOCATION / REBRAND / LEGAL_CONTINUATION / OPERATIONAL_TAKEOVER /
       NONE（无关先后）
SUP-3  LEGAL_CONTINUATION 才允许把历史责任链默认连上；
       OPERATIONAL_TAKEOVER 需业务批准
SUP-4  RelationshipState（01 §42）在继承处必须显式决策：
       继承 / 归零 / 打折（默认归零并要求人工确认，
       因为客户关系不是法律主体）
```

### 13.2 Prospect → Account

```text
禁止：转化时新建 entity_id（会导致潜力模型看到「新客户凭空出现」，
      并被误读为 organic growth）
要求：同一 entity，状态时间版本 + conversion_event_id
```

---

## 14. Identity 变更的下游影响与失效传播

身份变更是全系统影响面最大的操作。强制 Impact Analysis。

### 14.1 影响清单（Merge / Split / Unmerge 前必须算）

```text
OpportunityEstimate       subject 重挂后总额与分布变化
DemandSurfaceCell         聚合值重算
CoverageNeed/Commitment   目标 subject、频次是否重复
IntrinsicWorkload         按 subject×activity 重算
CapacityUtilization       依赖 workload
ResponsibilityAssignment  冲突检测（合并后是否出现双 primary → 违反 02 §40 Invariant）
TerritoryMembership       01 §45 关系存续
Open Candidate / Scenario 引用了受影响 subject 的 → STALE
Open DecisionCase         受影响 Gap / Hypothesis / Materiality 重算
已完成 Decision 的 Validation 基线  标记为 identity-affected（可能失效）
Benchmark ground truth     受影响 case 版本号提升（06 §108）
```

### 14.2 Trigger 阻断

```text
IF  unresolved identity candidates
   AND 影响 scope 的 workload / opportunity 变化预期 > materiality_threshold
THEN
   禁止创建 Structural DecisionCase（Expansion / Rebalancing）
   必须先把 H-DATA 排在诊断候选里
```

理由：一个尚未解析的重复记录就是一次**假的 CapacityGap**；
先加人再合并 = 花真钱买假需求。

### 14.3 反向检测（Identity Confounded 指标）

规范强制定义并持续测量：

```text
IdentityConfoundedGapRate
  = 因身份修正（去重后）而消失或显著缩小的 AllocationGap 占比
```

这是 SRAF 的**身份健康度总指标**，进 `06` Governance 报告。
经验上它应当很低；若偏高，说明问题不在 Solver 而在 Identity。

---

## 15. Temporal Identity

### 15.1 Identity 必须 bitemporal

```text
IdentityResolutionRecord

resolution_id
identity_domain
action        LINK / MATCH / CONFIRM / MERGE / UNMERGE / SPLIT / SUPERSEDE /
              RENAME / RELOCATE / DISTINCT_ASSERT
subjects[]    参与的 entity_id / external_id / source_record_id
survivor      （若适用）
rule_set_version / model_version / blocking_version / calibration_version
evidence[]
impact_analysis_id
authority     actor / role / policy_reference
decided_at                = knowledge/transaction time
effective_from / effective_to = valid time
status        PROPOSED / APPROVED / APPLIED / REVERSED / CONTESTED
supersedes_resolution_id  （撤销与再决策构成链，不覆盖历史）
reversal_of   （UNMERGE 指向被撤销的 resolution_id）
```

### 15.2 关键语义

```text
TI-1  「我们何时知道」与「现实中何时成立」分开
      （8/12 才完成的合并，其业务生效日可为 8/1）
TI-2  WorldSnapshot 必须固化当时已应用的 identity 决策集
      即：snapshot_id → { applied resolution_ids }
TI-3  重放（06 §95）必须使用该快照，禁止使用当前身份
TI-4  UNMERGE 不得抹掉旧 resolution；只能标记 REVERSED 并新建记录
TI-5  若某历史 Baseline 的身份判定后来被推翻，
      必须产生 LearningSignal = IdentityCorrectionAffectingPriorDecision
      并显式声明：该历史 Decision 的 validation 是否作废
```

### 15.3 与 Scenario 的关系

```text
Scenario 允许临时改身份视图（例如假设两条记录是同一个）吗？

允许，但：
    必须写成 ScenarioAssumption（semantic_status = ScenarioAssumption）
    不得写入 Canonical identity 状态
    Candidate 的解释中必须披露该假设敏感性
    （01 §55–56 / 05 §20）
```

---

## 16. IdentityConfidence

### 16.1 组成

身份置信度不是单一标量，至少分层报告：

```text
pair_score            matcher 原始分数
calibrated_probability
evidence_strength     STRONG / MIXED / WEAK（含冲突强信号则降为 WEAK）
rule_coverage         本次判定实际用到的 identifier_type 集
blocking_recall_risk  是否因 blocking 设计导致漏候选的先验风险
human_confirmed       是否含 CONFIRMED 人工主张
temporal_risk         涉及历史长时段 / 跨迁移边界的程度
cluster_risk          所在簇是否存在 chaining / 增长速率异常
```

下游可按用途设不同门槛：

```text
用途                最低要求
展示 / 检索         pair_score 可用
运营覆盖判定        calibrated_prob ≥ t_ops
ProblemProjection   必须附 identity_confidence 字段
Structural Decision 必须 CONFIRMED（AM-2）
```

### 16.2 与 World Model 的衔接

```text
01 §71 DataQuality 状态扩展：
    IdentityConfidence   LOW / MEDIUM / HIGH（或连续值 + 解释）
    IdentityStatus       RESOLVED / PROVISIONAL / CONTESTED / UNRESOLVED
```

`01 §72 AssertionConflict` 的具体形态之一就是身份冲突，
由本文件规定其 payload 与解决路径。

### 16.3 禁止行为

```text
IC-1  不得用「人工点过确认」把 identity 伪装成 ObservedFact
      （其 Semantic Status 仍是 DerivedState / DecisionOutput）
IC-2  不得只在 UI 展示一个百分数而不披露组成
IC-3  不得跨 identity_domain 复用同一个阈值集（location 阈值 ≠ account 阈值）
IC-4  不得让 confidence 在 Derived State 链上丢失
      （OpportunityEstimate / WorkloadDemand 必须能回溯到所用身份及其分数）
```

---

## 17. Survivorship（属性存活规则）

与身份解耦，只管 golden record 的字段取值。

```text
SurvivorshipPolicy

policy_id
identity_domain
attribute_scope（per-field 或 field-group）
strategy ∈ {
  SOURCE_TRUST,        按 source_system 优先级
  RECENCY,             取 valid/observed 最新
  COMPLETENESS,        非空优先
  FORMAT_VALIDITY,     通过校验者优先
  MAJORITY,            跨源多数
  ROLE_VIEW,           按业务角色给不同视图
  HUMAN_PINNED,        人工钉住，最高优先
}
tie_breaker
version
```

### 17.1 纪律

```text
SV-1  Survivorship 只能作用于 CONFIRMED 同一性的簇
      （§2.2：字段可自动，身份不可自动）
SV-2  每次字段取值必须记录胜出原因（哪条规则、哪条源记录）
SV-3  HUMAN_PINNED 必须带 actor + evidence，且可被更高级权限解除
SV-4  ROLE_VIEW 不得导致 Planning 与 Operations 使用两套
      未标注的业务真值（同一 ProblemProjection 内必须一致）
SV-5  身份被 UNMERGE 后，survivorship 结果必须可重算
      （源值仍在 SourceRecord，不依赖「当时选了什么」）
```

---

## 18. 层级与集团身份（连锁场景）

现实中最容易导致误判的，是层级混淆（第三轮书本结论 §1）。

```text
OrganizationGroup（永辉超市 / 中国区 KA 总部）
      ↑ PART_OF
Account(华东大区客户主体)      [可选中间层]
      ↑ PART_OF
Account(上海XX店)  ──OPERATES_AT──▶  ServiceLocation(某门址)
```

### 18.1 规则

```text
HR-1  层级关系是 IdentityAssertion(PART_OF)，不是外键字段
HR-2  PART_OF 必须 bitemporal
      （门店 2026-03 从 A 经销商划转到 B 经销商）
HR-3  聚合口径必须显式声明：
      opportunity 在 store 层还是 group 层计量，
      同一 projection 内不得混层求和（否则重复计入）
HR-4  「同一物理门店同时属于 KA 团队与地推团队」是
      合法的多责任覆盖（01 §40），
      不是身份冲突，不得因此合并两个 Account
HR-5  Group 层客户不得被当作其子门店的 duplicate
HR-6  roll-up 必须可下钻：group 的 Coverage/Workload 汇总
      必须能分解回 store，否则 DP05 无法归因
```

### 18.2 与 ResponsibilityScope 的衔接

```text
01 §38 ResponsibilityScope 的 AccountGroup=Walmart China
正是层级身份的业务消费方。
本规范提供其 identity 侧的可解析前提（层级 + 时点）。
```

---

## 19. Human Resolution

### 19.1 谁有权限

```text
权限按影响分级，不得由工程师或 Agent 默认拥有：

LINK / PROVISIONAL      系统 or Steward
CONFIRMED SAME_AS       Data Steward（domain 级）
MERGE（单市场内）        Steward + 业务 owner
MERGE（跨 Territory / 影响 Open Case）  + Sales Ops 审批
SPLIT / UNMERGE         + 影响承认（因牵动历史销量口径）
Supersede LEGAL_CONTINUATION  + 商务/法务依据
```

### 19.2 队列与 SLA

```text
IdentityResolutionQueue

优先级因子：
    影响的 opportunity 金额
    是否阻断 Open DecisionCase
    是否影响提交中的 Candidate 审批
    是否位于 Structural Freeze Window 内（05 §25）
SLA 要求：
    阻断 Structural Decision 的 UNCERTAIN 候选 → 必须在决策窗口前解决
    否则 DecisionCase 自动降级为 Monitor（不得强行推进）
```

### 19.3 人工主张的形态

复用 `02 §76 HumanOverride` 的纪律，不复制第二套：

```text
old_value / new_value / reason_code / evidence / expected_impact
```

Identity 专用 reason_code：

```text
LOCAL_KNOWLEDGE        本地知识（我认识这家店）
FIELD_VISIT_EVIDENCE   GPS/照片/拜访记录
LEGAL_ENTITY_CHECK     查了执照
CONTRACT_CONTINUITY    合同连续
SISTER_STORE           确认为隔壁另一家
MIGRATION_ERROR        迁移映射错误
POLICY_OVERRIDE        明知不确定但按业务口径处理
```

### 19.4 与 GW01 WorldModelRepair 的关系

```text
身份缺陷 → 属于 GW01（05 §14A）
但 GW01 不得绕过本规范 §19.1 的权限矩阵；
身份类修复必须落 IdentityResolutionRecord（§15），
其 impact_analysis_id 必须是 GW01 的必备产出物。
```

### 19.5 Agent 边界

```text
Agent 可以：
    提名候选（HUMAN_REFERRAL 之外的 AGENT_REFERRAL）
    解释证据、汇总冲突、准备 proposal
Agent 不得：
    直接执行 MERGE / SPLIT / UNMERGE
    把模型分数叙述为「确定是同一家店」
    因用户要求而绕过 §19.1 权限
```

（Charter P14 Evidence Before Automation、Gate「Agent 无 Evidence 自主改变世界」的
identity 侧具体化。）

---

## 20. ProblemProjection 中的身份

### 20.1 强制携带

任何 Projection 涉及 subject 时，必须同时提供：

```text
entity_id
identity_status
identity_confidence（+ 组成）
used_resolution_ids[]
duplicate_risk_flag     该 subject 是否曾被提议为某对象的重复项
```

Solver 可以选择忽略，但**不能不被告知**。

### 20.2 数据最小化（07 §90–91 延伸）

```text
identity resolution 需要名称 / 地址 / 电话 / 证照号，
但 Territory Solver 不需要这些。
Projection 只暴露 entity_id + 业务量 + 坐标/可达性 + 置信度。
```

Person/SalesResource 的身份证据（身份证号、个税主体）
**禁止**进入任何 Projection。

---

## 21. Identity Invariants（Critical）

并入 `06 §5` 的 B0 不变量编号体系（新增 I20 起）：

```text
I20  Canonical identity 永不复用、永不因外部 ID 变化而重建
I21  SourceRecord 不被删除；身份修正只改变 IdentityLink
I22  Entity Merge 必须产生可撤销的 IdentityResolutionRecord
I23  同一性主张必须声明 identity_domain 与 evidence
I24  自动 MATCH 必须由错误率上界（λ/π）定义，不由裸分数定义
I25  影响 Structural Decision 的身份主张必须 CONFIRMED
I26  Account 同一性不得由坐标距离单独决定；Location 同一性不得由客户名单独决定
I27  WorldSnapshot 必须固化其身份决策集；replay 不得使用当前身份
I28  UNMERGE 后历史 Derived State 必须可重算且重算过程被记录
I29  PART_OF / OPERATES_AT 必须 bitemporal
I30  Agent 不得自主执行身份变更
```

违反 I20–I30：B0 直接失败，不进入更高层评价。

---

## 22. Identity Architecture Gates

出现以下设计，应视为架构问题并拒绝：

```text
用 CRM 客户编码或员工号作为 Canonical ID
用 fuzzy match 分数阈值直接自动合并客户
合并时物理删除 loser 记录或其历史事实
把 survivorship 规则当成身份判定规则
把两条记录 link 后不留 provenance / rule version
单链接传递闭包建簇（无 TC-2 一致性校验）
身份决策只有当前态、无 valid/known time
回测时 join 到「今天的身份」而不是快照身份
门店换址时新建 Account（或反之，用换址掩盖新建客户）
Split/Merge 后不声明 history_attribution 口径
未解决身份候选不阻断 Trigger，直接推进 Expansion
Projection 不携带 identity_confidence
用「人工确认过」把身份标为 ObservedFact
Agent 拥有 merge 执行权限
把 Group 层客户与其门店记录当作重复项合并
```

---

## 23. Identity Benchmark（B0 的身份子域）

归入 `06` 框架，作为 B0 的强制子套件。

### 23.1 Ground truth 构造

```text
T1 构造真值（推荐主力）：
    从干净的 synthetic 客户全集出发，
    按可控比例注入噪声后交给系统还原：
        name variant（简写/繁简/别名/翻牌）
        address variant（口语化/缺门牌/POI 命名差异）
        coordinate jitter（≤ d_loc / > d_loc 两档）
        新增同址真实邻居店（negative control）
        迁移重编码
        合并 / 拆分 / 换址 / 关停重开
        同期双活
    注入即真值，可测 FMR/FNMR/cluster 指标。
T2 专家仲裁：真实历史疑难对，多评审独立判断，
    不一致记 CONTESTED（对齐 06 §19 的做法）。
T3 结果支持：后续 Field 证据（拜访照片/合同）回看当初判定。
```

注意（Papadakis 等对 ER 基准的批评）：

```text
公开 benchmark 常因样本过易而使 matcher 虚高。
SRAF 的身份基准必须包含：
    同品牌不同门店对（难负例）
    同址不同主体对（难负例）
    真重复且证据缺失对（难正例）
并禁止只在易分样本上报准确率。
```

### 23.2 强制指标

```text
Pairwise：
    FalseMatchRate（对 λ 的实测违约）
    FalseNonMatchRate（对 π）
    UncertainBandSize
    BlockingRecall（真值对在候选集中的召回）
Cluster：
    BCubed precision / recall / F
    ChainingIncidence（跨强冲突信号被并入同簇的比例）
    OversizedClusterRate
Lifecycle：
    UnmergeRate（误并的事后暴露率）★关键健康指标
    ContestRate
    MedianResolutionLatency
    BlockingMissDiscoveryLatency（漏并由下游发现的时间）
Decision 相关（SRAF 特有，最重要）：
    IdentityConfoundedGapRate（§14.3）
    StructuralTriggerBlockedByIdentity（因身份未决而被正确抑制的 Trigger 数）
    FalseExpansionAttributableToIdentity
    ReplayIdentityLeakageRate（replay 使用了错误时点身份的比例，应为 0）
    IdentityAffectedValidationCount
Governance：
    ResolutionProvenanceCompleteness（缺 rule_set_version/evidence 的比例，应为 0）
    UnauthorizedMergeCount（应为 0）
```

### 23.3 必须存在的 Case Family

```text
ID01  多源同实体（情形 1）
ID02  系统内重复（情形 2）
ID03  同品牌不同门店 → 必须 NOT MATCH（难负例，最重要）
ID04  同址多主体 → 必须 NOT MATCH
ID05  换址续营（情形 4）
ID06  翻牌但合同未变（情形 5）
ID07  翻牌且主体变更（→ Supersede，非 Rename）
ID08  一拆二 + 历史归属口径
ID09  二合一 + 历史销量不得虚假增长
ID10  已误并 → Unmerge + 下游重算一致性
ID11  迁移重编码（88291 → 223817）
ID12  同期双活 → 阻断自动合并
ID13  Chaining 诱导（A~B~C 传递但 A≠C）
ID14  Group 与其门店
ID15  证据不足 + 影响 Structural Decision → 必须阻断并升级人工
ID16  Replay 时点身份正确性（未来才做的合并不得出现在过去快照）
ID17  负向主张持久性（人工否决后重跑不得再提议）
ID18  Prospect → Account 转化不新建 ID
ID19  跨 identity_domain 规则泄漏（location 规则误用于 account）
ID20  Agent 试图直接 merge → 必须被权限层拒绝
```

### 23.4 Gate

```text
Identity Gate（并入 06 Part X）：
在 Phase 2 / Phase 3 进入 Structural Decision Benchmark 之前：

    ID03 / ID04（难负例）通过
    BlockingRecall ≥ 声明门槛
    FalseMatchRate ≤ λ
    ReplayIdentityLeakageRate = 0
    ResolutionProvenanceCompleteness = 100%
    IdentityConfoundedGapRate 已测并报告

未通过：只允许跑 DP06/DP07（不改变责任结构的问题），
不得跑 DP01/DP02/DP03 与任何 Expansion Benchmark。
```

---

## 24. MVP 范围

为避免过重（Charter P20），第一版只要求：

```text
必做
    CanonicalIdentity（R-ID-1..5）+ identity_domain 划分
    ExternalIdentifier（§6，EI-1..4）
    SourceRecord + IdentityLink（§7，SR-1..4）
    SAME_AS / DISTINCT_FROM 主张 + 三态 MatchDecision
    规则型 matcher（STRONG_GOVERNED 精确一致）+ 一个统计/ML matcher
    双阈值 λ/π + UNCERTAIN → 人工队列
    MERGE / UNMERGE / SUPERSEDE / RELOCATION（四个动作）
    Survivorship（SOURCE_TRUST + RECENCY + HUMAN_PINNED 三种策略）
    IdentityResolutionRecord append-only + 快照固化
    ImpactAnalysis（§14.1 清单的最小集）+ Trigger 阻断（§14.2）
    Benchmark ID01–ID04、ID10、ID11、ID15、ID16

暂缓
    学习型 blocking 模型
    LLM 辅助语义匹配（可先用，但只做候选提名）
    ROLE_VIEW survivorship 多视图
    自动 unmerge 触发
    跨市场全局身份服务（先满足 07 §15「不建完整 MDM」的口径）
    图嵌入 / 复杂 community detection
```

第一版明确不做「企业级 MDM」：
本规范的目标是**让决策不被身份错误误导**，
不是成为全公司的唯一身份权威源。若客户已有 MDM，
则 `CanonicalIdentityService` 退化为消费方 + 冲突上报方
（走 `05 GW01`），SRAF 不重建第二套主数据。

---

## 25. 与现有规范的具体衔接

### 25.1 01 World Model

```text
01 §9  Canonical Identity  →  schema 由 08 拥有，01 保留原则声明
01 §10 ExternalIdentifier  → 指向 08 §6
01 §15/§12 Person vs SalesResource → 08 §5.4 规定各自独立解析
01 §21–22 Account vs ServiceLocation → 08 §2.3 规定身份层独立性
01 §63 Spatial（改址不换 Account ID）→ 08 §12 情形 4 给出判定流程
01 §71 DataQuality → 新增 IdentityConfidence / IdentityStatus 两项
01 §72 AssertionConflict → 身份冲突作为其具体形态（08 §10 TC-3）
01 §79 例子中的「Commercial Entity Resolution」→ 08 展开
01 §81 MVP 14 对象 → Identity 是横切前提，不新增第 15 个业务对象，
     但 IdentityResolutionRecord 必须实现
```

### 25.2 02 Decision Ontology

```text
Root Cause Taxonomy 的 DataQualityIssue（§21）
    → 细化 subtype：IdentityDuplicate / IdentityFalseMatch /
      IdentityUnresolved / HierarchyMisattribution
    → 使 04 的 H-DATA 具备可检验子假设
DiagnosticHypothesis 的 evidence
    → 身份证据是合法 Evidence，其 semantic_status 遵循 08 §16.3
ChangeCost 的 CustomerRelationshipCost
    → 依赖正确的 relationship 历史 → 依赖 §15 Temporal Identity
```

### 25.3 03 Problem Contracts

```text
F1 DATA_INFEASIBLE 的合法成因之一 = 身份未解析
Projection 必须声明 identity_confidence 最低要求（§20.1）
Immutable objects 中隐含「identity 视图」：
    Problem Contract 应显式声明 identity_snapshot_id
    （= 所用 resolution 集合的版本）
```

### 25.4 04 Allocation Intelligence

```text
H-DATA（§22）必须包含身份子检验：
    DuplicateSuspectTest    同址/同品牌高相似双活检测
    HierarchyOverlapTest    group 与 store 是否被重复计入
    IdentityCoverageTest    有多少 subject 处于 UNRESOLVED/CONTESTED
H6 Stability & Confidence 增加 IdentityConfidence 维度
DiagnosticTest Library（§24）新增：
    IdentityIntegrityTest（MVP 必含的 5 个测试之外第 6 个）
Materiality（§26）：身份未决 → 该 Gap 的 confidence 上限受限
```

### 25.5 05 Orchestration

```text
GW01 WorldModelRepair 承接身份修复执行，权限见 08 §19.1
Artifact 失效传播（§21 / 08 §14.1）
Structural Freeze Window 期间：允许解析身份（读与记录），
    但据此触发的结构重算延后执行
```

### 25.6 06 Evaluation

```text
B0 新增 I20–I30（08 §21）
Test 6.1 Multi-source Identity / 6.2 Source ID Collision /
6.3 Location Change 的规范细则与阈值语义 → 由 08 提供，06 引用
Case Family ID01–ID20 归入 benchmark/identity/ 目录
新增 Identity Gate（08 §23.4）接入 Part X Acceptance Gates
Evidence Level（06 §141）适用于身份结论本身：
    一个只做 ID01–ID04 synthetic 通过的身份模块 = E1，
    不得宣称「已支持生产决策」
```

### 25.7 07 Reference Architecture

```text
§15 CanonicalIdentityService 的设计输入 = 本文件
模块落位（07 §70 结构）：
    src/domain/identity/        （新增，隶属 World Plane 的 domain 层）
    adapters/sources/           提供 ExternalIdentifier 与 SourceRecord
    benchmark/identity/         case + injector + ground truth
存储：identity_resolution 为 append-only；
     与 07 §9–10 PostgreSQL 选择一致，不新增图数据库依赖
     （Graph Projection 仍为派生）
```

---

## 26. 外部依据

本规范不是从零发明，锚定在两组成熟实践上。

### 26.1 Entity Resolution 文献

```text
Fellegi & Fellegi–Sunter (1969), JASA —
    概率式记录链接、m/u 权重、在两类错误率上界下的三态最优决策。
    → 08 §11 的 λ/π + UNCERTAIN band 直接源自此。
Newcombe (1962) — 似然比与按值分层的匹配权重。
Christen (2012), Data Matching (Springer) —
    字段级比较、标准化、blocking、clustering 的教科书体系。
Papadakis, Skoutas, Thanos, Palpanas (2020), ACM CSUR —
    blocking / filtering 技术综述。→ §9 的 blocking 强制与被测要求。
Christophides, Papadakis et al. (2020), ACM CSUR —
    端到端 ER 流水线（含 clustering 与冲突消解）。
Papadakis, Kirielle, Christen, Palpanas (2023) —
    对 (deep) learning ER 基准数据集的批判性重估：多数基准「过易」。
    → §23.1 强制难负例与禁止在易样本报准确率。
Li et al. (2020), Ditto —
    预训练模型做 pairwise 匹配；仅作 matcher 之一，不拥有决策权（§10）。
```

### 26.2 企业 MDM 工程惯例

```text
Golden record + attribute-level survivorship
    （按 source-trust / recency / completeness / majority / role view）。
Merge 与 Unmerge 为一等治理操作，须保留 lineage 以支持撤销。
Steward 权限分级与审计。
→ §17 / §19 采纳，但额外施加 SRAF 特有约束：
   survivorship 不得决定身份（§2.2）。
```

### 26.3 时态与数据仓库

```text
Snodgrass 与 TSQL2 / SQL:2011 的 valid time + transaction time 双时态模型；
Kimball 关于 late-arriving dimension 与 SCD 的处理经验。
→ §15 把这些从「数仓技巧」上升为「身份决策的强制记录格式」。
```

### 26.4 销售队伍设计文献（以及一个空白）

```text
Zoltners, Sinha & Lorimer,
Sales Force Design for Strategic Advantage (Palgrave Macmillan, 2004)
    Ch3 潜力估算为启发式（段内百分位 / 补齐缺口比例，并随生命周期调整）
        → 支撑 01 P3 与 OpportunityEstimate 的 provenance 要求
    Ch7 carryover 与 workload→FTE 链条
        → 支撑 workload 对 subject 计数的极端敏感（§3.2）
    Ch8 中央基准 + 本地调整、人员匹配客观性要求
        → 身份错误会伪装成「本地知识冲突」，必须先排除
    关键空白：全书没有身份解析 / 数据质量章节，
        "customer universe" 仅作为已解决前提出现一次。
        → 本文件填补的正是经典方法论未覆盖、
           但被其所有下游计算隐含依赖的地基。
```

---

## 27. Definition of Done

`08` 的实现不能以「身份表建好了」为完成。必须实际跑通：

```text
1  同一现实门店在 ≥3 个源系统的记录，解析到 1 个 entity，
   且 3 条 ExternalIdentifier 全部可查、各自带时效
2  构造一对「同品牌不同门店」，系统拒绝合并（ID03 通过）
3  一次 MERGE 后，Opportunity / IntrinsicWorkload / CapacityUtilization
   发生可解释变化，且 impact_analysis_id 可追溯
4  一次 UNMERGE 后，上述派生状态精确回到合并前值（或解释差异来源）
5  一次真实门店换址：Account entity_id 不变，
   旧/新 ServiceLocation 各有 valid time，责任链连续性被显式决策
6  一次 SPLIT：历史归属口径被声明，三种 attribution 曲线均可重放
7  2026-Q1 的历史 replay 不使用 Q3 才发生的身份修正（leakage = 0）
8  存在 UNRESOLVED 身份候选且影响 workload 时，
   系统拒绝创建 Structural DecisionCase，并把 H-DATA 列入假设
9  Agent 尝试直接 merge 被权限层拒绝，且事件被审计记录
10 IdentityConfoundedGapRate 可在真实数据上计算并报告
```

做到这十条，SRAF 的 World Model 才算补上「身份真值」这块地基。

---

## 28. 一句话边界

```text
01 回答：这个世界里有什么？
08 回答：你怎么确定「这个」和「那个」是同一个「这个」？
        以及——如果你错了，如何在你花钱之前发现。
```
