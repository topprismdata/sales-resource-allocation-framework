# 04 分配智能层实施设计（Allocation Intelligence Implementation Design）

- 状态：草稿 v0.1
- 日期：2026-08-28
- 定位：04 规范的**实施设计**——复用其全部 schema（Health/Gap/Test/Router/Signal），补三件事：层定位（PROPOSAL v1.3）、知识驱动（KB v0.3）、建议生成（世界模型 v2.1 因果结构）
- 上游：世界模型 v2.1 · 知识库 v0.3 · PROPOSAL_v1.3_LAYER_BINDINGS · 04 规范 v1.2
- 铁律：产出**给人建议**，不自动执行（D9）；诊断**先定位层再归因**（D10）

---

## 1. 总体流水线

```text
                    ┌─────────────────────────────────────┐
 WorldSnapshot ────→│ Fast 层（每快照自动跑，规则+统计）      │
 (v2.1 三层 slice)  │  L0 层定位 → L1 Gap 检测 → L2 假设检验 │
                    └──────────────┬──────────────────────┘
                                   ↓ AllocationDecisionSignal
                    ┌─────────────────────────────────────┐
 人工触发/信号 ────→│ Slow 层（按需，深诊断）                │
                    │  L3 反事实模拟 → L4 建议组装 → L5 解释 │
                    └──────────────┬──────────────────────┘
                                   ↓ 建议（理由链+风险+路由）
                            人（层内决策主体审批）
```

对应 04 §33 Fast/Slow：Fast = 规则/统计测试；Slow = 模拟+LLM 解释。
**LLM 只做解释生成（§23），诊断结论一律来自规则与检验。**

---

## 2. L0 层定位（本设计新增，规范出处 PROPOSAL v1.3）

任何 Gap 进入假设检验前，先回答"这是哪一层的问题"：

```text
LayerLocator 输入: gap 的对象层级 + 接口状态
  ├─ 归属/围栏异常（OOF 集中、align(F1,F2) 低）      → suspect_layer=D
  ├─ 线路/负荷异常（beat 均衡差、达成率低）           → suspect_layer=B
  ├─ 排程/路线异常（频次不合规、旅行超 K-BENCH-004）  → suspect_layer=V
  └─ 数据/身份异常（MULTI、低置信、缺口可能是假的）    → suspect_layer=DATA（04 §22 H-DATA 优先）
输出: Signal.suspect_layer + 证据
```

规则：跨层症状只在**一层**开方子；下层发现上游问题→发 Signal 不自行修（层间纪律 5 条，PROPOSAL §3）。

---

## 3. L1 Gap 检测：直接消费 kind 六分类

门店级 kind（gz_data.json）= 世界模型 L4 现成派生状态：

```text
GAP  433   → 进入诊断（四分类）
OOF  4,300 → 跨界供货检测：比例在 K-BENCH-001 正常带（≈12%）内 → Monitor；
             超 20% → Gap 升级 Review
MULTI 7    → 矛盾登记簿（08 优先于一切结构诊断）
DIRECT/DIRECT_IN → 不进缺口候选（K-RULE-003）
OK 26,182  → 健康，不产生 Gap
```

围栏级聚合：每围栏输出 `align(F1,F2,F3)` + kind 构成 → Health Profile（04 §4 六维）。

---

## 4. L2 假设检验：DiagnosticTest × 知识库映射

04 §24 的 11 个 MVP 测试逐个接上知识依据（建议推理链的证据来源）：

| 测试（04 §24） | 知识依据（KB v0.3） | 判定要点 |
|---|---|---|
| GlobalCapacityTest | K-BENCH-003/004 | 负荷 vs 承载力（20-30 店/天分级；旅行<40%） |
| LocalImbalanceTest | K-RULE-012 负荷均衡 | Σ店数×频率 的线间离散度 |
| TravelBurdenBenchmarkTest | K-BENCH-004 | 旅行占比超 40% → 线路问题非人力问题 |
| CoveragePolicyStressTest | K-RULE-012 分级频率 | ABC 频率 vs 容量 schedule 可行性 |
| SchedulingFeasibilityTest | DP06 oracle（接口 I-B 后） | 名义可行 vs 排得下 |
| IdentityIntegrityTest | K-RULE-005 + 08 | MULTI/低置信 → materiality 封顶 Review（04 §24 已有） |
| AssignmentConflictTest | K-PRIN-005 防重叠防白区 | 双归属/零归属 |
| BaseLocationCounterfactualTest | 04 §18 ResourceEquivalent | 换驻点反事实 |
| StructuralGapTest（新增） | K-RULE-007/010 | 低密度+大半径 → StructuralGap，禁开"加人"方子 |
| DirectSupplyFilter（新增） | K-RULE-003 | 直供店剔除逻辑 |
| DataCompletenessTest | K-FACT-003 基准 | 缺字段/快照过期 |

**新增测试同样走 04 §14 DiagnosticHypothesis 结构**（hypothesis/test/evidence/verdict），不新造 schema。

---

## 5. L3 反事实模拟（预测引擎，04 §32）

```text
InterventionSpec（可干预变量，世界模型 §7）:
  F2 运营围栏变更 / 业代增减 / 频率调整 / 驻点迁移
      ↓
WorldSimulator（世界模型三层 slice 上运行）:
  D 层干预 → I-D 重算 → B 层负荷/紧凑度重估 → V 层可行性前检
      ↓
响应分布: align(F1,F2,F3) 变化 / 负荷均衡 / 达成率预测
      ↓
行为修正项（本设计新增）: 经销商反应预测 ← K-RULE-008
  阶梯返利结构 → 压货/窜货风险系数；过程返利 → 执行配合度
      ↓
Carryover 标注 ← K-PRIN-002: 任何预测必须声明 impact_horizon，
  调整后短期下滑不构成失败证据
```

**层间纪律落地**：模拟永远按接口链传导（D→B→V），不跨层直改变量。

---

## 6. L4/L5 建议组装与解释（建议引擎）

**Signal 组装**严格按 04 §29 十一字段；Trigger（§27）满足才建 DecisionCase（02）。

**建议对象格式**（Management View §35 落地）：

```text
建议: <动作，层内>
理由链: [证据1, 证据2, ...]        # 每项 = KB id 或 数据证据，缺一拒绝输出
风险: [carryover 周期(K-PRIN-002),
       disruption 影响中等店(K-PRIN-003),
       经销商反应(K-RULE-008),
       客情过渡需求(K-RULE-006/009)]
路由: 层内决策主体（D=城市经理 / B=经销商主管 / V=业代）
过渡方案: 涉及换人必附（联合拜访 1-3 月，K-RULE-009）
materiality: Review/Actionable（08 联动，身份低置信封顶 Review）
```

**LLM 解释生成器**（04 §23 的 LLM 位置）：
- 输入：Signal JSON + 引用的 KB 条目全文
- 任务：把证据链转成人话，**禁止**引入 Signal 之外的结论
- 输出：建议文本 + 可折叠的"为什么"树（每个为什么 → KB id / 数据引用）

---

## 7. 知识库接口

```python
KnowledgeLookup(query) -> list[KnowledgeItem]
  # 按 type/scope/conditions 过滤；返回含 confidence 与 source
# 约束（D7 治理落地）:
#   MEDIUM 项只能出现在理由链的 supporting 位，不得单独支撑建议
#   建议组装器硬校验：理由链为空 → 拒绝生成（宁可不建议，不可无据建议）
```

---

## 8. 双时间线与抑制（04 §34 落地）

- 所有诊断查询用 as_of 时间点查询（世界模型 §6）：7 月诊断只见 7 月底前入库事实
- Suppression 规则直接映射 §34 六情形；StructuralGap 判定引用 K-RULE-007
- 防止两种经典误判：旺季峰值误判缺人（§34）；8 月数据回头改 7 月诊断（时光机倒错）

---

## 9. MVP Vertical Slice（三问，真实数据）

数据：gz_data.json（38 围栏 / 33,109 门店）+ 合同包 + KB v0.3

| # | 问题 | 流水线 | 验收 |
|---|---|---|---|
| Q1 | 这个围栏健康吗 | L1 聚合 align + kind 构成 → Health Profile | 38 份报告，每份含证据 |
| Q2 | 缺口属于哪类 | L0 定位 → L2 四分类（资源/身份/通路/意愿/结构性） | GAP 433 全覆盖，materiality 标注 |
| Q3 | 调整 X 影响谁 | L3 模拟（接口链传导）→ 影响清单+行为修正 | 任选围栏变更可复现 |

硬性验收：每条输出可溯源（KB id / 数据引用 / 规范条款）；无证据链的输出 = 缺陷。

---

## 10. 不做（Non-goals，04 §30/§36 对齐）

- 不做 LLM 端到端诊断；不做自动执行（建议止于人审）
- 不跨层开方子；不在诊断中重拥有 08 身份判定（只调用）
- v0 不做在线学习/反馈闭环（KB 版本手工治理已够）
