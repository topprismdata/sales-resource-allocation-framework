# PROPOSAL v1.3 — 组织层级实例化绑定与跨层接口（Layer Bindings & Interfaces）

- 状态：草稿（提案，走 NORMATIVE_OWNERSHIP 流程；批准后进入 CHANGELOG v1.3）
- 日期：2026-08-28
- 提案人：zcode
- 影响规范：03（新增 §17A 层级绑定 + CP05）、07（接口 I-D/I-B 归 Adapter 边界）、05（跨层信号走 ProblemRouter）
- 依据：世界模型 v2.1 §2A 三级独立决策层；用户拍板 D10"每一层独立，不要干扰"

---

## 1. 问题陈述（为什么需要本提案）

规范 v1.2 的 DP03/DP05/DP06/DP07 是**层级无关的抽象**，但未声明它们在分销组织
层级（厂家→经销商→业代）上的**实例化绑定**。后果：

1. 实施者无法判断"业代线路设计"该复用 DP03 还是造新问题（本提案前 SRAF 实施曾因此跳过 Layer-B 直接对接 visit——错误已被纠正）
2. 跨层交接（经销商门店清单→线路设计→排程）没有正式接口契约，层间耦合风险不可控
3. 04 诊断路由无法"先定位层再归因"——缺层注册表

**本提案不新增 DP**（复用现有 schema，符合"不得重新拥有另一套 schema"规则），只新增：层级绑定声明、跨层接口契约、一个 Composite Problem。

---

## 2. 组织层级注册表（03 新增 §17A Layer Bindings）

```yaml
OrgLayer:
  Layer-D:
    name: 经销商区域层
    decision_owner: 厂家城市经理          # 分片包干制
    problems: [DP03@dealer, DP04@dealer]
    world_slice: [Contract, TerritoryDesign(F1/F2), MarketFeature,
                  ServiceLocation, SupplyEvent 派生状态]
    output_interface: I-D
  Layer-B:
    name: 业代线路层
    decision_owner: 经销商老板+主管        # 厂家督导协访纠偏（不改判）
    problems: [DP03@rep(Beat), DP05(频率), beat_sequencing(DP07-L1)]
    world_slice: [OrgUnit, SalesRepRole, Beat, CoveragePolicy,
                  I-D 输出（immutable）]
    output_interface: I-B
  Layer-V:
    name: 拜访排程层
    decision_owner: 业代 / 排程系统
    problems: [DP06, DP07]
    world_slice: [Calendar, Capacity, TravelMeasure,
                  I-B 输出（immutable）]
    output: VisitSchedule（回写世界模型为观察事实）
```

**实例化声明**：`Territory`/`Responsibility`/`Resource` 为层级泛型——

```text
DP03@dealer: Territory=DealerTerritory(围栏), Responsibility=分销责任, Resource=经销商
DP03@rep:    Territory=Beat(线路),       Responsibility=拜访责任,   Resource=业代(SalesRepRole)
```

schema 完全复用 03 §13，仅 binding 不同；`TerritoryMembership` 在两实例中
分别对应围栏成员关系与线路成员关系，互不混淆。

---

## 3. 接口契约（07 新增，Adapter 边界对象）

```yaml
InterfaceContract:
  I-D:  # Layer-D → Layer-B
    payload:
      store_dealer_assignment:      # store_id → dealer_id，含生效区间
      identity_snapshot_id:         # 08 §20 绑定
      direct_supply_flags:          # kind ∈ {DIRECT, DIRECT_IN} 标记（不进 B 层缺口）
    immutability: B 层不得修改归属；发现异常→发 Signal(layer=D) 给 04 路由
    versioning: world_snapshot_id 绑定；I-D 变更 = E6 事件，B 层全量重估

  I-B:  # Layer-B → Layer-V
    payload:
      beat_assignment:              # store_id → beat_id → rep_id
      coverage_policy:              # store_id → {min, preferred, max} 频率（DP05 schema）
      beat_calendar:                # beat_id → 拜访日模式
    immutability: V 层不得改成员/频率；排不下→Signal(layer=B)
    versioning: contract_version 绑定；I-B 变更 = E11 事件，V 层增量重排
```

**层间纪律（入 03 §1 核心原则）**：

```text
1. 上游接口输出 = 下层 immutable input（ProblemProjection 的 immutable_objects）
2. 下层不可行/发现异常 → Signal(怀疑层) → 04 ProblemRouter 定位层 → 该层内归因
3. 各层目标函数互不引用（D 层不优化排线效率；V 层不管线路划分）
4. 层内事件层内消化：E6→D 层，E10/E11→B 层；跨层影响仅经接口信号
5. 每层独立走 CandidateDecision → Approval → ApprovedDecision（02 流程）
```

---

## 4. CP05 — Beat Design（03 新增 §21A）

```text
CP05 Beat Design = DP03@rep + DP05 + beat_sequencing(DP07 能力 L1 档)
mode: sequential（定片→定人→定频→定线）
```

回答 03 §2 十问（Layer-B 主问题）：

```text
1 业务问题:  经销商内部，业代线路如何划分（定点→定片→定人→定频→定线）
2 世界状态:  I-D 归属（固定）+ 业代名册 + 门店分级 + 现有线路（baseline）
3 允许改变:  TerritoryMembership@rep、ResponsibilityAssignment@rep、
            CoverageCommitment（频率）、beat 顺序
4 不可改变:  I-D 归属、业代人数（E10 另行走人）、门店身份、直供店归属
5 必须满足:  每店恰属一条 beat（防重叠+防白区）；负荷 ≤ 容量（K-BENCH-003）；
            KA 特殊归属；频率可调度（DP06 oracle 前检，03 §8）
6 优化倾向:  片区紧凑、负荷均衡、disruption 最小（K-RULE-012 四原则）
7 可行:     全指派 + 容量可行 + 频率 schedule 可行
8 更好:     均衡度↑ 紧凑度↑ 变更↓（稳定性预算，K-CONST-002）
9 解释回业务: 线路清单 + 频率表 + 变更 delta + 每店归属理由
10 失败语义: F1 前置（I-D 缺失/身份低置信不进结构决策）、F4 容量不可行、
            F5 结构不可行、F7 超时——全部按 03 §10 分类，禁止静默空输出
```

---

## 5. 对现有文档的影响

| 文档 | 动作 |
|---|---|
| 03 | 新增 §17A 层级绑定、§21A CP05、§1 层间纪律三行 |
| 07 | 新增 I-D/I-B 接口对象定义（Adapter 边界） |
| 05 | ProblemRouter 增加层注册表路由（Signal 携带 suspect_layer） |
| DESIGN.md | P0-1 状态更新 |
| 04 设计 | 诊断引擎第一步 = 层定位（Signal.suspect_layer） |

## 6. 验收（提案批准标准）

1. DP03@rep 与 DP03@dealer 的 projection 字段可枚举且 schema 同源
2. I-D/I-B 可序列化、可版本化、可作为 immutable 投影进入下游测试
3. 一个跨层案例可走通：D 层变更 → Signal → B 层重估 → I-B v+1 → V 层增量重排
4. 04 诊断输出必含 `suspect_layer` 字段
