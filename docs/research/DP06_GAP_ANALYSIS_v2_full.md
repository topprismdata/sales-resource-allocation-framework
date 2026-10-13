# DP06 Gap Analysis — visit-scheduling-optimizer vs SRAF Contract

**日期：** 2026-08-28  
**分析框架：** "引擎 + SRAF 大脑 = 能否做出正确的区域决策？"（5 个核心问题）  
**被测对象：** visit-scheduling-optimizer 工作副本（HEAD `282ebd6` + 未提交内容）  
**对照规范：** 03 §16 DP06、§10 失败分类、§24 最优性、§28 Provenance、§31 Reference Engine  
**参照规范：** 07 §47–51、§72 五项改造、§94–95、§110A Envelope

---

## 一、设计理念理解（先回答"这个引擎在做什么"）

visit-scheduling-optimizer 不是"排班工具"，而是一个 **OR 学术研究与生产实践之间
的翻译层**。核心设计决策：

```text
1. 三层求解体系
   Tier 1: 求解后端（GLOP / CP-SAT / SCIP）— 可替换
   Tier 2: 通用算法内核（列生成 / ALNS / HGS）— 零业务感知
   Tier 3: 领域计划组装（拜访排班 CG Plan / 精确 Plan / HGS Plan）

2. 零业务感知引擎
   列生成引擎不知道什么是"门店""经销商""拜访"——
   它只管理抽象的 MasterProblem / Column / DualVector / PricingProvider

3. 证书化诚实
   每次求解输出 ColumnGenerationCertificate：
   明确声明 is_globally_optimal_proven / pricing_strategy / termination_reason
   启发式定价绝不签发全局最优凭证

4. 需求→数学血缘追踪
   每条业务需求（REQ-FREQ-001）可追溯到数学变量（y[customer, pattern]）
   对齐 W3C PROV-O 本体

5. 三级旅行校准
   L1 OSRM 路网 → L2 经验校准（319 段真实数据拟合）→ L3 球面直线兜底
   每级标注 source 和 confidence
```

**这个设计理念与 SRAF 的五条基本原则完全对齐：**

| SRAF 原则 | visit 实现 |
|---|---|
| P7 Policy Is Not Constraint | PlanningPolicy 独立于求解器约束 |
| P8 Decision Problem Is Not Solver | 列生成引擎零业务感知（Tier 2 不知门店） |
| P10 Solver State Never World Truth | DecisionEvidence 是只读元数据，不写回 World |
| Evidence Before Automation | 三级旅行校准每级标注 source + confidence |
| 证书化诚实 | ColumnGenerationCertificate 显式声明 optimality_scope |

**结论：设计理念无需修改，引擎架构是 SRAF Tier 2 的正确实现。差距不在架构，在契约层。**

---

## 二、DP06 契约对照（10 项投影 → 9 项输出 → 失败语义 → Provenance）

### 2.1 输入投影（07 §50 的 10 个实体）

| §50 要求 | visit 现状 | 判定 | 证据 |
|---|---|---|---|
| ResponsibilityAssignment | ❌ 客户以索引进入，无责任语义 | **MISSING** | `solve_to_plan(lats, lons, ...)` |
| CoverageCommitment | ⚠ `frequency_rules: {cust_id: freq}` 逐户必填 | **PARTIAL**（有频次，无 min/preferred/max 分层）| `policy.py:57-62` |
| SalesResource | ⚠ 单 `representative_id` 逐人求解 | **PARTIAL**（无多人联合优化）| `solver_adapter.py:35` |
| ResourceDeployment | ❌ 无驻点概念（depot 是坐标参数） | **MISSING** | — |
| Calendar | ⚠ `_working_dates` 硬编码 Mon–Fri | **PARTIAL** | `solver_adapter.py:15-23` |
| Capacity | ⚠ `max_work_minutes_per_day` + 分层工时 | **PARTIAL** | `policy.py:40-47` |
| SpacingPolicy | ⚠ 隐式 `gap_i = days // (freq+1)` | **PARTIAL**（非声明式）| `solver.py:149-157` |
| VisitWindows | ❌ 输出字段 `planned_arrival_window` 存在但从不赋值 | **MISSING** | `planning.py:77` |
| TravelEstimate | ✅ `build_time_matrix` + 校准 + time/distance 双模式 | **MET** | `calibration.py` |
| FixedDayPolicy | ❌ 无固定日约束 | **MISSING** | — |

### 2.2 输出契约（07 §51 的 9 个实体）

| §51 要求 | visit 现状 | 判定 | 证据 |
|---|---|---|---|
| CandidateSchedule | `PlanVersion`（版本化、生命周期、is_locked）+ `PlannedVisit` | **MET** | `planning.py:16-86` |
| FeasibilityStatus | `DecisionEvidence.status` 透传 CP-SAT StatusName | **PARTIAL** | solver status ≠ business status |
| UnfulfilledCommitments | **无此输出**。求解失败时适配器静默返回空计划 | **MISSING** | `solver_adapter.py:68-69` |
| ConstraintConflictEvidence | 无；warnings 只装校准告警 | **MISSING** | — |
| CapacityUtilization | 日容量被约束但不输出利用率 | **MISSING** | — |
| ScheduleStability | `n_changes/change_details` + `is_locked` | **PARTIAL** | `planning.py:69,81` |
| TravelEstimate | **`estimated_travel_minutes` 从未赋值**（恒 0.0）| **BUG** | grep 全库仅声明无赋值 |
| OptimalityStatus | `optimality_scope + lp_obj/ip_obj/mip_gap` + Certificate | **MET** | 证书化诚实设计 |
| RunProvenance | `solver_run_id/policy_version` 有；`input_version="n{n}"` 太弱 | **PARTIAL** | `solver_adapter.py:105` |

### 2.3 失败语义（03 §10 的 F1–F7 分类）

| F 类型 | visit 现状 | 判定 |
|---|---|---|
| F1 DATA_INFEASIBLE | ❌ 不区分 | **MISSING** |
| F4 RESOURCE_INFEASIBLE | ⚠ 隐含在 INFEASIBLE 状态中 | **PARTIAL** |
| F5 STRUCTURAL_INFEASIBLE | ❌ 无 `TEMPORAL_STRUCTURAL_INFEASIBILITY` 概念 | **MISSING** |
| F7 SOLVER_FAILURE | ⚠ TIME_LIMIT 可识别 | **PARTIAL** |
| **核心问题** | 求解失败时 adapter **静默返回空计划**，调用方不知道是"真排不下"还是"超时" | **CRITICAL** |

### 2.4 Provenance（03 §28）

| 要求 | 现状 | 判定 |
|---|---|---|
| solver_run_id | ✅ | MET |
| world_snapshot_id | ❌ | MISSING |
| contract_version | ❌ | MISSING |
| seed | ❌ | MISSING |
| model_version / calibration_version | ⚠ warnings 元组中可能包含 | PARTIAL |

---

## 三、"引擎 + SRAF 大脑"五问五答

### Q1 引擎收到 DP06 投影时，知不知道身份已经被 08 解析过了？

**不知道。** `solve_to_plan` 接受裸数组（坐标+频次），没有 identity_snapshot_id。
SRAF 需要一个 **ProjectionBuilder**（07 §36）将 WorldSnapshot → `VisitSchedulingProblemProjection`，
在投影中附加 identity 信息（08 §20）。

**Gap: 投影层缺失** — 这是 07 §72"五项改造"的第一项。

### Q2 引擎排完之后，04 能不能诊断"这个结果是否合理"？

**不能直接诊断。** 引擎输出 `DecisionEvidence`（solver metrics），但不输出：
- 频次达成率（freq compliance = 实际排到的次数 / 要求频次）
- 产能利用率（实际工时 / 可用工时）
- 未满足承诺清单（哪些客户的频次没排够）

这些需要在 adapter 层从 `assigns` 结果中**后计算**并传给 04。
04 的 H-DATA 检验（IdentityDuplicateTest 等）也需要围栏+门店数据作为输入。

**Gap: 后计算指标缺失** — 需要 `ScheduleQualityEvaluator`。

### Q3 如果不合理，路由器能不能区分"缺人"还是"缺身份"？

**不能。** 当前引擎 INFEASIBLE 时静默返回空计划，不区分：
- 客户数 > 日容量×天数（真缺人 → F4 RESOURCE_INFEASIBLE）
- 频次约束互相矛盾（数学无解 → F5 STRUCTURAL_INFEASIBLE）  
- CP-SAT 超时（求解失败 → F7 SOLVER_FAILURE）
- 身份重复导致工作量虚高（→ H-DATA，非 DP06 问题）

**Gap: 失败语义分类器缺失** — 这是 07 §72 第三项"Failure Semantics"。

### Q4 人调整边界时，系统能不能说"这里有条河，建议沿河画"？

**引擎本身不管边界。** 但 SRAF 的 `fence_split.py`（已集成 market_partition）
可以做到：给定围栏+河流障碍 → 切分+门店归类。这个能力是**新增的**，
visit 引擎不需要改。

**已有** ✅ `dealer_territory/fence_split.py`（集成 market_partition）

### Q5 调整后，ValidationPlan 能不能追踪效果？

**部分。** `PlanVsActualMetrics`（plan_vs_actual.py）有：
- 拜访完成率、旅行偏差、服务时长偏差
- 但 `estimated_travel_minutes` 恒 0.0 → 旅行偏差指标失真（BUG）
- 无 carryover 建模（CHANGELOG G1 已挂账）
- 无 A/B 对照机制（06 §86 Matched Control 需手动设计）

**Gap: 效果追踪需要 TravelEstimate 修复 + carryover 模型**

---

## 四、07 §72 五项改造原则逐项判定

| §72 项 | visit 现状 | 需要做的 | 改造层级 |
|---|---|---|---|
| **Adapter** | `solver_adapter.py` 有雏形（Plan↔Solver 转换） | 扩展为 SRAF DP06 投影的入口 | Adapter 层 |
| **Input Contract** | 裸数组 `lats/lons/freq/svc` | 新建 `VisitSchedulingProjection` dataclass（含 identity_snapshot_id） | 新增 |
| **Output Contract** | `DecisionEvidence` 有 solver 指标 | 加 07 §51 的 9 项标准输出（Unfulfilled、CapacityUtilization、TravelEstimate 等） | Adapter 层 |
| **Failure Semantics** | INFEASIBLE 静默空计划 | 加 F1–F7 分类器 + `UnfulfilledCommitment` 输出 | Adapter 层 |
| **Run Provenance** | solver_run_id + input_version="n{n}" | 加 snapshot_id / seed / contract_version | Adapter 层 |
| **Feasibility Mode** | ❌ 无独立 oracle 入口 | 加 `check_feasibility()` 方法（不解，只判可行） | Adapter 层 |

**全部 6 项改造在 Adapter 层，求解器核心（solver.py / cg）零改动。**

---

## 五、visit 做得好且 SRAF 必须保留的

```text
1. 证书化诚实（ColumnGenerationCertificate）
   → SRAF 06 §131 "不允许 Cherry-pick" 的实现基础

2. 三层旅行校准（L1 OSRM → L2 经验 → L3 Haversine）
   → 每级标注 source + confidence，与 01 Evidence 模型对齐

3. 卖断式销售 + 无理由不退换
   → 业务约束清晰，避免边界扯皮

4. 需求→数学血缘追踪（W3C PROV-O）
   → 06 §125 Reproducibility Package 的实现基础

5. PlanVersion 生命周期（draft → reviewed → published → superseded）
   → 与 02 CandidateDecision 生命周期对齐

6. is_locked（经理锁定不可移动）
   → 02 HumanOverride 的实现基础

7. 需求→数学变量映射表（REQ-FREQ-001 → y[customer, pattern]）
   → 06 §125 Provenance Completeness 的实现基础
```

---

## 六、visit 缺失且 SRAF 必须补的

```text
1. UnfulfilledCoverageCommitment 输出          ← 03 §16 强制
2. F1–F7 失败语义分类                          ← 03 §10 强制
3. CapacityUtilization / ScheduleStability 输出 ← 07 §51 要求
4. estimated_travel_minutes 赋值               ← 当前恒 0.0（BUG）
5. identity_snapshot_id 在投影中               ← 08 §20 要求
6. RunProvenance 完整性（seed/snapshot/version）← 03 §28 要求
7. Oracle 独立入口（feasibility_only 模式）     ← 07 §47 要求
8. 街道/镇边界作为 Calendar 输入               ← 01 §21 ServiceLocation 关联
```

---

## 七、实际差距矩阵（汇总）

| 维度 | MET | PARTIAL | MISSING | BUG |
|---|---|---|---|---|
| 输入投影 (10) | 1 | 4 | 4 | 1 |
| 输出契约 (9) | 2 | 3 | 3 | 1 |
| 失败语义 (7) | 0 | 2 | 3 | 2 |
| Provenance (5) | 1 | 2 | 2 | 0 |
| Oracle 模式 | 0 | 0 | 1 | 0 |
| **合计** | **4** | **11** | **13** | **4** |

**总差距：32 项，其中 MISSING 13、PARTIAL 11、BUG 4、MET 4。**

改造工作量评估：**全部在 Adapter 层（solver_adapter.py + 新增 evaluator），求解器核心零改动。**
按 07 §110A Envelope S 档，预计 3–5 个工作日。

---

## 八、行动建议

```text
立即做（P0，阻塞 Vertical Slice v1）:
  1. UnfulfilledCoverageCommitment 输出（含 reason + severity）
  2. F1–F7 失败语义分类器
  3. estimated_travel_minutes 回填
  4. RunProvenance 补全（snapshot_id / seed / contract_version）

随后做（P1，本周内）:
  5. VisitSchedulingProjection dataclass（含 identity_snapshot_id）
  6. ScheduleQualityEvaluator（频次达成率 / 产能利用率 / 稳定性指标）
  7. Oracle 独立入口（feasibility_only 模式）
  8. 补 assignment.py / models.py 测试覆盖

后续做（P2，v1.3）:
  9. Carryover / sales-response lag 模型
  10. DP04 fairness 从 Preference 升为 Invariant
  11. H3 索引从 prototype 升级为 production
```
