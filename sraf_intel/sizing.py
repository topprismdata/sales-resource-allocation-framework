"""sraf_intel.sizing — 编制测算与负载平衡（WP16）。

公式谱系（书卡引用，双源核对口径）：
- Zoltners & Sinha 1983, "Sales Territory Alignment: A Review and Model"
  (Management Science 29(11)) §2/§3：辖区=工作量与潜力双目标平衡单元；
  sizing 采用覆盖法（coverage method）：N = 总工作量分钟 ÷ 单代表可用分钟。
  书卡: prism-ontology/docs/reviews/book-wiki/books/zoltners1983-territory-alignment.md
- Zoltners & Sinha, "Sales Territory Design: Thirty Years..." §7.3
  Salesforce Sizing and Segmentation。
  书卡: .../sales-territory-design-chapter.md
- 公平性指标 EQ = (Σx)²/(n·Σx²) ∈ [1/n, 1]，1=完全均衡（辖区均衡经典指数，
  HHI 归一化倒数；见 1983 综述双目标之工作量均衡）。

⚠️ 双源核对挂账（计划 §71 风险预案）：书内数值算例不在本地语料
（书卡为索引卡）。本模块单测用自洽可手核算例锁定算术，不冒充
"书内算例转录"；书内算例逐位核对待 PDF 页到位后补。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AccountWorkload:
    """账户级工作量（1983 模型粒度：账户而非区域，书卡评审结论）。"""

    account_id: str
    territory_id: str
    calls_per_year: float
    minutes_per_call: float
    minutes_drive_per_call: float = 0.0

    @property
    def minutes_per_year(self) -> float:
        """Zoltners 覆盖法基本项：calls × (duration + drive)。"""
        return self.calls_per_year * (self.minutes_per_call + self.minutes_drive_per_call)


@dataclass(frozen=True)
class RepCapacity:
    """单代表年可用销售分钟 = 天数 × 小时/天 × 60 × 销售时间占比。"""

    working_days_per_year: float = 250.0
    hours_per_day: float = 8.0
    selling_time_fraction: float = 0.6

    @property
    def available_minutes_per_year(self) -> float:
        return self.working_days_per_year * self.hours_per_day * 60.0 * self.selling_time_fraction


def territory_loads(workloads: tuple[AccountWorkload, ...] | list[AccountWorkload]) -> dict[str, float]:
    total: dict[str, float] = {}
    for w in workloads:
        total[w.territory_id] = total.get(w.territory_id, 0.0) + w.minutes_per_year
    return total


def required_reps(total_minutes: float, capacity: RepCapacity) -> int:
    """覆盖法编制：向上取整（半个人不存在；欠配比超配危险——负载不均会传导）。"""
    if total_minutes <= 0:
        return 0
    return math.ceil(total_minutes / capacity.available_minutes_per_year)


def eq_index(loads: dict[str, float]) -> float:
    """均衡指数 EQ = (Σx)² / (n·Σx²) ∈ [1/n, 1]，1=完全均衡（HHI 归一化倒数）。

    零负载辖区计入 n（无主区=失衡证据，不豁免）。空/单区/全零返回 1.0。
    """
    n = len(loads)
    if n <= 1:
        return 1.0
    s = sum(loads.values())
    if s <= 0:
        return 1.0
    q = sum(x * x for x in loads.values())
    return (s * s) / (n * q)


@dataclass(frozen=True)
class BalanceReport:
    loads: dict[str, float]
    reps_needed: dict[str, int]
    total_reps: int
    eq: float
    max_min_ratio: float | None  # None = 存在零负载辖区（结构性缺口）


def balance_report(workloads, capacity: RepCapacity) -> BalanceReport:
    loads = territory_loads(workloads)
    reps = {t: required_reps(m, capacity) for t, m in loads.items()}
    pos = [m for m in loads.values() if m > 0]
    ratio = (max(pos) / min(pos)) if pos and len(pos) == len(loads) else None
    return BalanceReport(
        loads=loads,
        reps_needed=reps,
        total_reps=required_reps(sum(loads.values()), capacity),
        eq=eq_index(loads),
        max_min_ratio=ratio,
    )


@dataclass(frozen=True)
class MoveProposal:
    """迁转=决策建议：requires_approval 恒 True，永不自动执行（WP05 纪律）。"""

    account_id: str
    from_territory: str
    to_territory: str
    minutes_moved: float
    eq_before: float
    eq_after: float
    requires_approval: bool = field(default=True, init=False)


def rebalance_suggestions(
    workloads: tuple[AccountWorkload, ...] | list[AccountWorkload],
    capacity: RepCapacity,
    max_moves: int = 5,
) -> list[MoveProposal]:
    """贪心确定性迁转建议：过载区最大账户 → 最欠载区，逐步提升 EQ。

    平局裁决全序（确定性测试锁定）：
    - 选源区：(负载降序, territory_id 升序)；选账户：(分钟降序, account_id 升序)
    - 选目标区：(负载升序, territory_id 升序)
    只产出建议，不改动输入。
    """
    wl = sorted(workloads, key=lambda w: w.account_id)
    loads = territory_loads(wl)
    if len([m for m in loads.values() if m > 0]) < 2:
        return []
    by_terr: dict[str, list[AccountWorkload]] = {}
    for w in wl:
        by_terr.setdefault(w.territory_id, []).append(w)
    proposals: list[MoveProposal] = []
    eq0 = eq_before = eq_index(loads)
    for _ in range(max_moves):
        src = max(loads, key=lambda t: (loads[t], _neg_id(t)))
        dst = min(loads, key=lambda t: (loads[t], t))
        if src == dst or loads[src] <= 0:
            break
        cand = max(by_terr[src], key=lambda w: (w.minutes_per_year, _neg_id(w.account_id)))
        moved = cand.minutes_per_year
        trial = dict(loads)
        trial[src] -= moved
        trial[dst] += moved
        eq_after = eq_index(trial)
        if eq_after <= eq_before + 1e-12:
            break  # 无增益即停：不制造无意义迁转
        proposals.append(
            MoveProposal(
                account_id=cand.account_id,
                from_territory=src,
                to_territory=dst,
                minutes_moved=moved,
                eq_before=round(eq_before, 10),
                eq_after=round(eq_after, 10),
            )
        )
        by_terr[src].remove(cand)
        by_terr.setdefault(dst, []).append(cand)
        loads = trial
        eq_before = eq_after
    return proposals


def _neg_id(s: str) -> str:
    """max() 平局时取 id 升序：用 (值, id) 键里 id 的逆序技巧。"""
    return "".join(chr(0x10FFFF - ord(c)) for c in s)
