# SRAF Specification Changelog — v1.2

v1.2 是 v1.1 Implementation Baseline 经过外部评审后的**第二版实施基线**。

本版不扩充功能，而是补地基与修硬错误。

---

## P0 changes applied

### 1. 新增 `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`

World Model 的「身份真值」地基。核心内容：

```text
四条不可混淆分界
    Identity Resolution  != Deduplication
    Entity Merge         != Source Record Merge
    Account              != ServiceLocation
    Identity Confidence  != Business Truth

概念分层 L1 Evidence / L2 Linkage / L3 Semantic / L4 Governance

八种真实情形的判定规则
    Same Entity / Duplicate / Same Account+Different Location
    Relocation / Rename / Split / Merge / False Match(Unmerge)

Supersede vs Merge 分离
层级与集团身份（连锁：Group / store / location 三层 + PART_OF 时效）

MatchDecision 三态 + 以错误率(λ/π)而非裸分数定义阈值
Survivorship 与身份解耦（字段可自动，身份不可自动）
反 chaining 约束（禁止无约束传递闭包建簇）
Temporal Identity（resolution append-only + snapshot 固化身份决策集）
IdentityConfidence 组成化 + 禁止 confidence 在派生链上丢失

Identity Invariants I20–I30（并入 B0，违反即 Benchmark 失败）
Identity Benchmark ID01–ID20 + Identity Gate
```

关键设计后果：**`04` 的 H-DATA 假设从不可检验变为可检验**。
在此之前，`DataQualityIssue` 是垃圾桶标签；
现在有 subtype、有测试、有阈值、有阻断规则。

### 2. 修正 schema 级笔误

```text
02 §80  approved_approved_decision_id
     -> approved_decision_id
```

### 3. 版本措辞统一

消除正文中 `v1.0` / `v1.1` 混杂（00/01/02/04/05/06/07 共 46 处），
规范性表述统一为当前基线版本。

保留的 `v1.0` 字样只有两类，均为正确用法：

```text
CHANGELOG / README / CONSISTENCY REPORT 中的历史性指代
06 §108 的 Benchmark Case 自身版本示例（case v1.0 -> case v1.1），
    并加注说明它与规范文档版本无关
```

---

## P1 changes applied

### 4. 补 `v1 Engineering Envelope`（07 §110A）

不是系统上限，而是给 DecompositionPlanner / SolverRegistry /
Projection Cache / Benchmark 的工程契约：

```text
S  Interactive            <=5k Resp Units / <=50 Res      seconds
M  City/Regional Planning 5k-50k / 50-300                 minutes
L  Structural Batch       50k-200k / 300-1,000             tens of min - hours
```

并绑定 Phase 0–3 的最低承诺档位、各档计算策略切换、
以及「超出 L 档触发 Aggregation/Sampling 评审而非静默降精度」。

`06 §55 Scale Benchmark` 增加约束：
reported scale 必须覆盖对应 Phase 档位上界。

### 5. 补 3 个 Governance Workflow 最低语义（05 §14A）

```text
GW01 WorldModelRepair
GW02 ModelGovernance
GW03 PolicyReview
```

统一纪律：默认 A0/A1、禁止 A2/A3、不得直接改 Canonical World、
产出「修正提案 + 治理决定」而非资源配置 Candidate、
必须触发下游 Artifact STALE。

明确 `GW03` 与 `RequirementExceptionProposal` 的分界：
Proposal 是单 Case 内例外，GW03 是跨 Case 的 Policy 语义修订入口。

`02 §93/§94` 路由表同步补 `ModelGovernance` 并指向 §14A。

### 6. 交叉引用闭环

```text
00 P21        归属表加入 08
01 §1.1       ExternalIdentifier / IdentityResolutionRecord -> 08
01 §9/§10     Canonical ID 原则保留，schema 去重并指向 08（消除 P21 违例）
01 §71        新增 IdentityConfidence / IdentityStatus 质量状态
01 §72        AssertionConflict 的身份冲突形态 -> 08
02 §21        拥有 4 个 DataQualityIssue 身份 subtype
03 §3         Contract 新增 identity_snapshot_id / min_identity_confidence
03 §10        F1 DATA_INFEASIBLE 的身份成因 + 禁止误判为 F4
04 §10        H6 新增 IdentityConfidence（且为其他置信度的前提）
04 §22        H-DATA 引用 02/08，不重复定义
04 §24        新增 IdentityIntegrityTest（4 项子检验）+ Materiality 联动
05 §1A        所有权加入 GovernanceWorkflow GW01–GW03
06 §5         新增 I20–I30 指针 + §6 判定细则归属说明
06 §55        引用 07 §110A
06 §86        补 Matched Control 工业实证出处（见 §7）
07 §15        指向 08 + 模块落位 + 存储约束 + 已有 MDM 时的退化规则
```

---

## 7. 文献锚定（新增，提升可辩护性）

`06 §86` 补入一条真实工业对照研究作为规范依据：

```text
Zoltners, Sinha & Lorimer,
Sales Force Design for Strategic Advantage (Palgrave Macmillan, 2004),
Table 8.3 + p.318-319
```

该研究以 realignment 后「更换负责人」的 test 账户组 vs
未更换的 control 账户组测量 disruption 冲击，
结果显示影响**仅集中于中等体量账户**（$50–100k），
小账户与超大账户均不显著。

由此产生两条规范含义：

```text
1. Matched Control（V1 证据设计）在销售区域决策中真实可行，
   不是纯理论要求。
2. ChangeCost.CustomerRelationshipCost 必须按 account size /
   relationship strength 分段估计，禁止单一全局 disruption 系数。
```

`08 §26` 另附本规范的外部依据清单：
Fellegi–Sunter 三态决策与错误率上界、Papadakis/Christen ER 综述、
Papadakis 2023 对「过易」ER 基准的批评（→ 强制难负例）、
MDM golden-record survivorship / unmerge lineage 惯例、
Snodgrass 双时态与 Kimball late-arriving dimension。

---

## 8. 已知缺口（v1.3 候选，本版仅登记不实施）

精读上述专著后发现两项 SRAF 目前缺件，与 Identity 无关，
故不并入本版，但必须显式挂账以免丢失：

> 更新（v1.2.1）：这两项已在 `CHANGELOG_v1.2.1.md` 重新分级——
> G1 升级为 DP01 前置 Gate，G2 推迟到 DP04 production。本节保留为历史记录。

```text
G1 Carryover / 响应滞后未建模
   专著 Ch7（Fig 7.3, Table 7.3/7.9）：
   本年销量 = 本年努力 + 往年结转；
   高结转环境下只看单年 impact 会系统性低估 size 变动的长期效应。
   风险：SalesResponseEstimate 若把「去年努力的产出」记到
        本年 Candidate 名下 -> DP01/DP05 增益虚高，
        B4 Validation 观察窗错配（把滞后效应当成无效）。
   建议：OpportunityEstimate / SalesResponseEstimate 增加
        impact_horizon 与 carryover_share 声明；
        DecisionValidationPlan 强制 minimum_lag_window。

G2 DP04 公平性与合规风险等级不足
   专著 p.329-330 明确：人员匹配必须使用
   「一致、客观、可辩护」的标准，并点名法律风险。
   SRAF 现把 fairness 归为 Preference（03 DP04 / 02 §43）。
   建议：把「禁止未经 territory 校正的 raw performance 作目标」
        从约定升为 DP04 Invariant 示例，
        并要求 protected-attribute 相关规则进入 Requirement 层
        而非散落在 heuristic。
```

---

## 9. 本轮未做（明确排除）

```text
未进入 visit-scheduling-optimizer 代码 Gap Analysis（Step 4）
未新增 DP08 或任何新 Atomic Decision Problem
未引入新存储组件（identity 仍落 PostgreSQL）
未修改 00 Charter 的原则集合（仅补归属表第 08 行）
```

---

## Implementation restraint（继承 v1.1 并强化）

```text
Modular Monolith First
No dedicated graph DB in Phase 0–3
No generic BPMN requirement in Phase 0
No new solver platform before the vertical slice proves need
No enterprise MDM rebuild: 已有 MDM 时 SRAF 为消费方，
    但 Identity Gate 仍必须对上游产出跑通（07 §15 / 08 §23.4）
```
