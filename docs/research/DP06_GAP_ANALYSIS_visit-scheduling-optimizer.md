# DP06 Gap Analysis — visit-scheduling-optimizer vs SRAF Contract

**状态：** 分析报告（非规范性文档）  
**日期：** 2026-08-27  
**对照规范：** `03` §16 DP06 契约、§10 Infeasibility Taxonomy、§24 Optimality、§28 Provenance、§29 Shadow/DryRun、§31 Reference Engine；`07` §47–51、§72、§94–95  
**被测对象：** `/Users/ghb/Documents/Codex/2026-08-04/wo-xi/visit-scheduling-optimizer`  
（git HEAD `282ebd6` + 工作树未提交内容；含 `solver_adapter.py`/`planning.py`/`tests/` 的最完整工作副本。公开克隆 `2026-08-27/…` HEAD `23e99b8` 是其瘦身后代，不含 adapter/tests，无法单独评估。）  
**改动声明：** 本分析对 visit 仓库**只读**，未修改其任何文件。

---

## 0. 一句话结论

引擎核心（PVRP 列生成 + CP-SAT/ALNS）与 DP06 的**可变变量、间距约束、诚实最优性披露**高度吻合；差距集中在**契约外壳**——标准投影对象、失败语义分类、未满足承诺输出、run provenance 完整性、Oracle 模式。全部属于 `07 §72` 预设的 Adapter 层改造，**不需要重写求解器**。Vertical Slice v1 可以按 §5 清单直接开工。

---

## 1. 输入侧：07 §50 标准投影 10 项对照

| §50 要求 | 引擎现状 | 判定 | 证据 |
|---|---|---|---|
| resources | 每次求解单 `representative_id`，多资源=逐人调用 | **PARTIAL** | `solver_adapter.py:35` |
| responsibilities | 无此概念；客户以坐标索引进入 | **MISSING** | `solver_adapter.py:31-48` |
| coverage_commitments | `frequency_rules` 逐户必填、不可缺省，缺即抛错 | **MET（形态差异）** | `policy.py:57-62` |
| calendar | `_working_dates` 硬编码 Mon–Fri，无节假日表 | **PARTIAL** | `solver_adapter.py:15-23` |
| capacity | `max_work_minutes_per_day` + 分层工时上限；无 committed/available 之分 | **PARTIAL** | `policy.py:40-47` |
| service_time | 按层分钟数或统一 30 分钟；无按次差异 | **PARTIAL** | `solver_adapter.py:51-53` |
| spacing_policy | 隐式 `gap_i = days // (freq+1)` 线性间距约束 + 独立校验器 | **MET（非声明式）** | `solver.py:149-157, 404-415` |
| visit_windows | 输出有 `planned_arrival_window` 字段但从不赋值、不约束 | **MISSING** | `planning.py:77` |
| travel_estimate | `build_time_matrix` 校准 + time/distance 双模式 | **MET** | `calibration.py`, `solver_adapter.py:57-67` |
| fixed_day_policy | 无 | **MISSING** | — |

**输入侧结论**：引擎吃的是裸数组（`lats/lons/freq/svc/tiers/segments/counties`），不是 `VisitSchedulingProblemProjection` 对象。这正是 SRAF 需要写的 **ProjectionBuilder 映射层**（07 §36），属于新增代码而非引擎改造。

---

## 2. 输出侧：07 §51 标准输出 9 项对照

| §51 要求 | 引擎现状 | 判定 | 证据 |
|---|---|---|---|
| CandidateSchedule | `PlanVersion`（版本单调递增、draft→reviewed→published→superseded 生命周期）+ `PlannedVisit` | **MET** | `planning.py:16-86` |
| FeasibilityStatus | `DecisionEvidence.status` 直接透传 CP-SAT `StatusName` 原始串 | **PARTIAL** | `planning.py` Evidence、`solver.py:373-374` |
| UnfulfilledCommitments | **无此输出**。求解失败时适配器静默返回空计划 `a=[set()]*days`，哪些承诺没满足、为何、上游含义均不输出 | **MISSING** | `solver_adapter.py:68-69` |
| ConstraintConflictEvidence | 无；`warnings` 只装校准告警 | **MISSING** | `solver_adapter.py:108-109` |
| CapacityUtilization | 日容量被约束但不输出利用率 | **MISSING** | — |
| ScheduleStability | `n_changes/change_details` + `is_locked` 经理锁定 | **PARTIAL** | `planning.py:69,81` |
| TravelEstimate | **`estimated_travel_minutes` 从未赋值**（恒 0.0）；`plan_vs_actual` 拿 0 与实际比，travel_dev 指标失真 | **MISSING（字段在、值不在）** | grep 全库仅 planning.py:66 声明、plan_vs_actual.py:125 消费 |
| OptimalityStatus | `optimality_scope="restricted_column_pool"` + `lp_obj/ip_obj/mip_gap` 诚实披露 | **MET（需映射标准枚举）** | `solver_adapter.py:103` |
| RunProvenance | `solver_run_id`/`policy_version` 有；`input_version=f"n{n}"` 只记客户数；无 snapshot_id / contract_version / seed / network_version | **PARTIAL（弱）** | `solver_adapter.py:105` |

---

## 3. 失败语义（03 §10）：最大缺口

`03` 要求 Solver status 与业务可行性分层，F1–F7 分类，且 `TEMPORAL_STRUCTURAL_INFEASIBILITY` 不得被误读为全局缺容量。现状：

```text
solver 返回 None（INFEASIBLE / TIME_LIMIT）
      ↓
adapter: a = [set() for _ in range(days)]   # 静默空计划
      ↓
PlanVersion(draft) + DecisionEvidence(status=原始串)
      ↓
调用方拿到一个"合法的空计划"，不知道是
   F4 RESOURCE_INFEASIBLE（真排不下）
   F7 SOLVER_FAILURE（超时）
   还是 03 §16 的 TEMPORAL_STRUCTURAL_INFEASIBILITY
```

这正是 03 §32 Architecture Gate 明令禁止的：「Solver timeout 被解释为业务无解」「所有 infeasible 返回同一状态」。**这是 Vertical Slice v1 的第一优先改造项**，且完全在 adapter 层可解：把 `status + freq/capacity 比值` 映射为 F1–F7 + 逐户 `UnfulfilledCoverageCommitment(reason, severity, upstream_implication)`。

---

## 4. Oracle / 治理面（07 §47–48、03 §29）

| 要求 | 现状 | 判定 |
|---|---|---|
| SchedulingFeasibilityOracle 独立调用模式 | 不存在；唯一入口 `solve_to_plan` 总是全量求解 | **MISSING** |
| run_purpose / output_contract / runtime_budget 三分离 | 无 | **MISSING** |
| DryRun / Shadow | `adapt_solution`（不重算）+ `PlanVersion.status` 生命周期提供了雏形 | **PARTIAL** |

好消息：`travel.py` 本就是列生成的 cost oracle——Oracle 语义在引擎内部已存在，缺的只是把它作为**独立调用面**暴露。

## 5. 上游语义越界（07 §49）：合规

五项禁区（客户是否值得拜访 / Coverage 频次政策 / Territory 归属 / Headcount / 驻点）逐一核查：引擎一律要求上游给全（`frequency_rules` 缺户即 `ValueError`），无增员/划区逻辑。唯一注意点：未提交的 `dynamic_policy.py`/`customer_value.py` 属于"客户价值→频次"的上游实验，**必须留在 SRAF 的 DP05 侧**，不得迁入引擎——这是后续 code review 的 watch item，不是现行违例。

---

## 6. 07 §72 五项改造原则逐项判定

| §72 项 | 判定 | 说明 |
|---|---|---|
| Adapter | **有雏形** | `solver_adapter.py` 即此角色，但面向 Plan-vs-Actual，不面向 SRAF Projection |
| Input Contract | **缺** | 需 ProjectionBuilder：WorldSnapshot→`VisitSchedulingProblemProjection`（含 identity_snapshot_id，08 §20） |
| Output Contract | **缺** | §51 九项中 4 项 MISSING、3 项 PARTIAL |
| Failure Semantics | **缺** | §3 所述，第一优先 |
| Run Provenance | **弱** | `input_version="n{n}"` 不足以复现；需绑 snapshot + calibration_version + seed |
| Feasibility Mode | **缺** | Oracle 模式待加 |

---

## 7. Vertical Slice v1 最小改造清单（全部 adapter 层，solver 零改动）
> **归属声明**：本清单是给 `visit-scheduling-optimizer` 仓库的建议，
> 不是 SRAF 仓库的工作项。SRAF 是规范与治理框架，不实现拜访排程；
> 清单的落点在引擎仓库自身或其后续改造计划。


按 03 §33 第一条 Vertical Slice 的通过条件排序：

```text
P0  FailureSemanticsMapper   status+gap → {OPTIMAL/FEASIBLE/TIME_LIMIT/...}
                            × {F1..F7}；TEMPORAL_STRUCTURAL_INFEASIBILITY 判据=
                            monthly workload ≤ capacity 且 CP-SAT INFEASIBLE
P0  UnfulfilledCommitments   对每个 freq[i] 未满足户输出
                            {customer_id, reason, severity, upstream_implication}
P1  ProjectionBuilder        SRAF 投影 → solve_to_plan 参数（含 calendar 注入点
                            替换 _working_dates、visit_windows 透传）
P1  RunProvenance 补全       snapshot_id / contract_version / seed /
                            calibration_version / network_version
P2  estimated_travel_minutes 回填（从 T 矩阵取相邻序列差）
P2  Oracle 入口              feasibility_only=True：只判可行不解全问题，
                            runtime_budget 独立声明
```

P0 两项完成即可跑通 03 §33 的五类 Case 演示（Business Feasible / Resource Infeasible / Temporal Structural / Solver Failure / Policy Infeasible——最后一类需 Projection 注入互斥策略来构造）。

---

## 8. 遗留观察（不阻塞，记录备查）

```text
- 单代表逐人求解：跨代表均衡属 DP03 职责，SRAF 侧编排，引擎无需改
- spacing 与 freq 强耦合（gap=freq 推导）：声明式 SpacingPolicy 到位前可接受
- tests/ 已覆盖 constraints/adapter/calibration/ALNS validity——
  改造时先给 P0 两项补契约测试，再动代码
- visit 仓库工作树 39 处未提交改动：分析基于当前工作树快照，
  若后续 rebase/丢弃未提交内容，本矩阵的行号证据需复核
```
