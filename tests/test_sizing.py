"""WP16 sizing/fallback：自洽算例锁算术 + 确定性 + 只建议不执行。

注：书内数值算例不在本地语料（书卡为索引卡），本文件不冒充书例转录；
算术按 Zoltners 覆盖法定义逐项手算可验证（docstring 给出算式）。
"""

import pytest

from sraf_intel.fallback import NearbyCandidate, TerritoryContainer, nearby_candidates
from sraf_intel.sizing import (
    AccountWorkload,
    RepCapacity,
    balance_report,
    eq_index,
    rebalance_suggestions,
    required_reps,
    territory_loads,
)

CAP = RepCapacity()  # 250天 × 8h × 60 × 0.6 = 72,000 分钟/年


def _acct(aid, terr, calls, dur, drive=0.0):
    return AccountWorkload(aid, terr, calls, dur, drive)


# ---- 覆盖法算术 ----

def test_rep_capacity_minutes():
    assert CAP.available_minutes_per_year == 250 * 8 * 60 * 0.6 == 72000.0


def test_account_minutes_calls_times_duration_plus_drive():
    # 50 次/年 × (30 分钟拜访 + 10 分钟在途) = 2,000 分钟/年
    w = _acct("A1", "T1", 50, 30, 10)
    assert w.minutes_per_year == 2000.0


def test_required_reps_ceiling():
    # 200,000 ÷ 72,000 = 2.78 → 3 人（向上取整）
    assert required_reps(200_000, CAP) == 3
    assert required_reps(0, CAP) == 0
    assert required_reps(72_000, CAP) == 1
    assert required_reps(72_001, CAP) == 2


def test_balance_report_per_territory_and_total():
    wl = [_acct("a", "T1", 100, 30), _acct("b", "T1", 100, 30),   # T1=6000
          _acct("c", "T2", 300, 30)]                              # T2=9000
    r = balance_report(wl, CAP)
    assert r.loads == {"T1": 6000.0, "T2": 9000.0}
    assert r.reps_needed == {"T1": 1, "T2": 1}
    assert r.total_reps == 1  # 合并编制 15000/72000 → 1：总量口径≠分辖区口径
    assert r.max_min_ratio == 1.5


# ---- EQ 均衡指数 ----

def test_eq_bounds_and_direction():
    assert eq_index({"A": 100, "B": 100}) == 1.0        # 完全均衡
    assert eq_index({"A": 100, "B": 0}) == 0.5          # 单区独占 n=2 → 1/n
    assert eq_index({"A": 3, "B": 1, "C": 1, "D": 1}) == pytest.approx(36 / 48)
    assert eq_index({}) == 1.0 and eq_index({"A": 5}) == 1.0
    # 方向锁死：更均衡 → EQ 更大（防 HHI 变体回潮）
    assert eq_index({"A": 55, "B": 45}) > eq_index({"A": 90, "B": 10})


# ---- 迁转建议：确定性 + 只建议 ----

def _imbalanced():
    return [
        _acct("a1", "T1", 100, 30),  # T1 3000
        _acct("a2", "T1", 100, 30),
        _acct("a3", "T1", 100, 30),
        _acct("b1", "T2", 10, 30),   # T2 300
    ]


def test_rebalance_deterministic_and_monotone():
    p1 = rebalance_suggestions(_imbalanced(), CAP)
    p2 = rebalance_suggestions(_imbalanced(), CAP)
    assert [(x.account_id, x.from_territory, x.to_territory) for x in p1] == \
           [(x.account_id, x.from_territory, x.to_territory) for x in p2]
    assert p1, "失衡输入必须产出建议"
    assert p1[0].account_id == "a1"  # 过载区最大账户（平局取 id 升序）
    assert all(x.eq_after > x.eq_before for x in p1)  # 每步严格增益才保留
    # 链式单调：后一步的 before = 前一步的 after
    for prev, nxt in zip(p1, p1[1:]):
        assert nxt.eq_before == prev.eq_after


def test_rebalance_never_mutates_input_and_always_asks_approval():
    wl = _imbalanced()
    snapshot = [(w.account_id, w.territory_id) for w in wl]
    for p in rebalance_suggestions(wl, CAP):
        assert p.requires_approval is True  # 恒 True：兜底≠授权（WP05 纪律）
    assert [(w.account_id, w.territory_id) for w in wl] == snapshot


def test_rebalance_stops_when_balanced():
    wl = [_acct("x", "T1", 100, 30), _acct("y", "T2", 100, 30)]
    assert rebalance_suggestions(wl, CAP) == []


# ---- nearby-containers 兜底 ----

def _containers():
    return [
        TerritoryContainer("T2", (2.0, 0.0), 5),
        TerritoryContainer("T1", (1.0, 0.0), 3),
        TerritoryContainer("T3", (0.5, 0.0), 0),   # 无余量 → 不进候选
        TerritoryContainer("T9", (1.0, 0.0), 2),   # 与 T1 同距 → id 平局裁决
    ]


def test_nearby_ordering_tiebreak_and_filters():
    got = nearby_candidates((0.0, 0.0), _containers(), k=3, max_radius_km=25)
    ids = [c.territory_id for c in got]
    assert ids == ["T1", "T9", "T2"]  # 距离升序；同距 id 升序；T3 无余量剔除
    assert [c.distance_km for c in got] == [1.0, 1.0, 2.0]
    assert all(c.requires_human_confirmation for c in got)


def test_nearby_radius_and_k_limits():
    assert nearby_candidates((0.0, 0.0), _containers(), k=1) [0].territory_id == "T1"
    assert nearby_candidates((100.0, 100.0), _containers()) == []  # 半径外无候选


def test_nearby_candidate_flag_not_silenceable():
    c = NearbyCandidate("T1", 1.0, 3)
    with pytest.raises(Exception):
        c.requires_human_confirmation = False  # frozen dataclass：不可翻
