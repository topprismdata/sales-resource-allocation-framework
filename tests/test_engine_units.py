"""WP13 引擎单元测试（hermetic：纯内存合成世界，参照 test_multicomponent 的 sq()/World 构造）。

覆盖 intelligence.health / classify / impact / adjust(纯函数与错误路径)。
不依赖 data/ 真实数据包；adjust 中依赖 TerritoryIR 数据集的路径不予覆盖。
"""
import sys
import unittest
from pathlib import Path

from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intelligence.world import Fence, World
from intelligence.adjust import (
    AdjustError, Proposal, _fence_poly, _fence_union, _match_dealer,
    _ring_of, _row_of, _rows, km2, parse_and_propose)
from intelligence.classify import STRUCTURAL_KM, classify_gap
from intelligence.health import KIND_ZH, fence_health, run_q1
from intelligence.impact import move_impact


def sq(cx, cy, h=0.01):
    """a small square ring around (cx,cy)."""
    return [[cx - h, cy - h], [cx + h, cy - h],
            [cx + h, cy + h], [cx - h, cy + h], [cx - h, cy - h]]


def store(name, dealer, lon, lat, kind="OK", district="X区", upstream=None,
          direct=False):
    u = upstream if upstream is not None else dealer
    dealers = (dealer,) if dealer else ()
    return {"n": name, "c": "食杂店/批发", "d": district, "u": u,
            "lon": lon, "lat": lat, "direct": direct,
            "dealers": list(dealers), "kind": kind}


class FakeKB:
    version = "test"
    gaps = []

    def cite(self, kid):
        return {"kb_id": kid, "statement": "s", "source": "t", "confidence": "HIGH"}

    @staticmethod
    def validate_chain(chain):
        return True


def make_health_world():
    """4 经销商：甲=健康(2块10店全OK)、乙=调查(30% OOF)、丙=观察(ok率0.7)、丁=空围栏。"""
    fences = [
        {"area_id": "A1", "dealer": "甲", "area_km2": 10.0, "rings": [sq(113.20, 23.00)]},
        {"area_id": "A2", "dealer": "甲", "area_km2": 12.0, "rings": [sq(113.80, 23.30)]},
        {"area_id": "B1", "dealer": "乙", "area_km2": 8.0, "rings": [sq(113.25, 22.80)]},
        {"area_id": "C1", "dealer": "丙", "area_km2": 6.0, "rings": [sq(113.30, 23.10)]},
        {"area_id": "D1", "dealer": "丁", "area_km2": 4.0, "rings": [sq(113.40, 23.20)]},
    ]
    stores = ([store(f"甲西{i}", "甲", 113.20 + 0.001 * i, 23.00, district="A区")
               for i in range(5)]
              + [store(f"甲东{i}", "甲", 113.80 + 0.001 * i, 23.30, district="B区")
                 for i in range(5)]
              + [store(f"乙O{i}", "乙", 113.25 + 0.001 * i, 22.80, district="C区")
                 for i in range(7)]
              + [store(f"乙F{i}", "乙", 113.254 + 0.001 * i, 22.802,
                       kind="OOF", upstream="外卖商", district="C区")
                 for i in range(3)]
              + [store(f"丙O{i}", "丙", 113.30 + 0.001 * i, 23.10)
                 for i in range(7)]
              + [store(f"丙F{i}", "丙", 113.303 + 0.001 * i, 23.102,
                       kind="OOF", upstream="外卖商")
                 for i in range(2)]
              + [dict(store("丙M0", "丙", 113.305, 23.104),
                      dealers=["丙", "戊"], kind="MULTI")])
    return World({"fences": fences, "stores": stores,
                  "kinds": {"OK": 24, "OOF": 5, "MULTI": 1}})


class TestFenceHealth(unittest.TestCase):
    def setUp(self):
        self.w = make_health_world()
        self.kb = FakeKB()

    def test_healthy_fence(self):
        rep = fence_health(self.w, self.w.fence_by_dealer["甲"], self.kb)
        self.assertEqual(rep["verdict"], "健康")
        self.assertEqual(rep["materiality"], "Monitor")
        self.assertEqual(rep["ok_rate"], 1.0)
        self.assertEqual(rep["oof_rate"], 0.0)
        # D14: 密度分母 = 领地全部块面积之和（10+12=22）
        self.assertEqual(rep["area_km2"], 22.0)
        self.assertEqual(rep["blocks"], 2)
        self.assertEqual(rep["density_per_km2"], round(10 / 22, 1))

    def test_oof_over_threshold_triggers_investigation(self):
        rep = fence_health(self.w, self.w.fence_by_dealer["乙"], self.kb)
        self.assertEqual(rep["verdict"], "调查")
        self.assertEqual(rep["materiality"], "Review")
        self.assertEqual(rep["oof_rate"], 0.3)

    def test_low_ok_rate_is_watch(self):
        rep = fence_health(self.w, self.w.fence_by_dealer["丙"], self.kb)
        self.assertEqual(rep["verdict"], "观察")
        self.assertEqual(rep["materiality"], "Monitor")
        self.assertEqual(rep["ok_rate"], 0.7)   # 7 OK / 10
        self.assertEqual(rep["oof_rate"], 0.2)  # 2 OOF / 10，未破 0.20 调查线

    def test_empty_fence_zero_rates(self):
        rep = fence_health(self.w, self.w.fence_by_dealer["丁"], self.kb)
        self.assertEqual(rep["ok_rate"], 0.0)
        self.assertEqual(rep["oof_rate"], 0.0)
        self.assertEqual(rep["verdict"], "观察")
        self.assertTrue(rep["top_district"].startswith("—"))
        self.assertEqual(rep["density_per_km2"], 0.0)

    def test_kinds_use_chinese_labels_and_evidence_has_refs(self):
        rep = fence_health(self.w, self.w.fence_by_dealer["乙"], self.kb)
        self.assertIn("非围栏供货", rep["kinds"])
        self.assertEqual(rep["kinds"]["非围栏供货"], 3)
        self.assertIn(KIND_ZH["OK"], rep["kinds"])
        self.assertTrue(all("data_ref" in e or "kb_id" in e for e in rep["evidence"]))
        self.assertTrue(any(e.get("kb_id") == "K-BENCH-001" for e in rep["evidence"]))

    def test_run_q1_one_report_per_dealer_sorted_investigation_first(self):
        reps = run_q1(self.w, self.kb)
        self.assertEqual(len(reps), 4)  # D14: 一经销商一报告
        self.assertEqual(reps[0]["verdict"], "调查")
        self.assertEqual({r["dealer"] for r in reps}, {"甲", "乙", "丙", "丁"})


def make_gap_world():
    """GAP 缺口五分类合成世界：3 类缺口 + 1 个远离围栏的结构性缺口。"""
    fences = [
        {"area_id": "A1", "dealer": "甲", "area_km2": 8.0, "rings": [sq(113.20, 23.00)]},
        {"area_id": "B1", "dealer": "乙", "area_km2": 8.0, "rings": [sq(113.25, 22.80)]},
    ]
    stores = [
        store("g1", None, 113.20, 23.00, kind="GAP", upstream=""),        # 缺身份
        store("g2", None, 113.201, 23.001, kind="GAP", upstream="甲"),     # 缺围栏覆盖
        store("g3", None, 113.202, 23.002, kind="GAP", upstream="荔湾二批"),  # 缺意愿候选
        store("g4", None, 113.50, 23.00, kind="GAP", upstream=""),         # 结构性(远)
        store("ok1", "甲", 113.205, 23.005),                               # 非 GAP, 应被忽略
    ]
    return World({"fences": fences, "stores": stores, "kinds": {"GAP": 4, "OK": 1}})


class TestClassifyGap(unittest.TestCase):
    def setUp(self):
        self.w = make_gap_world()
        self.out = classify_gap(self.w, FakeKB())

    def _item(self, name):
        return next(o for o in self.out["items"] if o["store"] == name)

    def test_missing_upstream_is_identity_data_layer(self):
        it = self._item("g1")
        self.assertEqual(it["class"], "缺身份")
        self.assertEqual(it["layer"], "DATA")
        self.assertTrue(any(e.get("kb_id") == "K-RULE-005" for e in it["evidence"]))

    def test_upstream_in_fence_dealers_is_coverage_gap(self):
        it = self._item("g2")
        self.assertEqual(it["class"], "缺围栏覆盖")
        self.assertEqual(it["layer"], "D")
        self.assertTrue(any(e.get("kb_id") == "K-FACT-001" for e in it["evidence"]))

    def test_unwilling_upstream_is_willingness_candidate(self):
        it = self._item("g3")
        self.assertEqual(it["class"], "缺意愿候选")
        self.assertEqual(it["layer"], "D")
        self.assertEqual(it["materiality"], "Review")

    def test_far_gap_marked_structural_with_rule007(self):
        it = self._item("g4")
        self.assertTrue(it["structural"])
        self.assertGreater(it["nearest_fence_km"], STRUCTURAL_KM)
        self.assertIn("服务模式", it["action"])
        self.assertTrue(any(e.get("kb_id") == "K-RULE-007" for e in it["evidence"]))

    def test_near_gaps_not_structural(self):
        for name in ("g1", "g2", "g3"):
            self.assertFalse(self._item(name)["structural"])

    def test_summary_counts(self):
        s = self.out["summary"]
        self.assertEqual(s["total_gaps"], 4)
        self.assertEqual(s["by_class"],
                         {"缺身份": 2, "缺围栏覆盖": 1, "缺意愿候选": 1})
        self.assertEqual(s["by_layer"], {"DATA": 2, "D": 2})
        self.assertEqual(s["structural"], 1)

    def test_no_gaps_empty_result(self):
        w = World({"fences": [], "stores": [store("ok1", "甲", 113.2, 23.0)],
                   "kinds": {"OK": 1}})
        out = classify_gap(w, FakeKB())
        self.assertEqual(out["summary"]["total_gaps"], 0)
        self.assertEqual(out["items"], [])


def make_impact_world():
    fences = [
        {"area_id": "A1", "dealer": "甲", "area_km2": 10.0, "rings": [sq(113.20, 23.00)]},
        {"area_id": "A2", "dealer": "甲", "area_km2": 12.0, "rings": [sq(113.80, 23.30)]},
        {"area_id": "B1", "dealer": "乙", "area_km2": 8.0, "rings": [sq(113.25, 22.80)]},
    ]
    stores = ([store(f"甲西{i}", "甲", 113.20 + 0.001 * i, 23.00) for i in range(4)]
              + [store(f"甲东{i}", "甲", 113.80 + 0.001 * i, 23.30) for i in range(4)]
              + [store(f"乙{i}", "乙", 113.25 + 0.001 * i, 22.80) for i in range(4)])
    return World({"fences": fences, "stores": stores, "kinds": {"OK": 12}})


class TestMoveImpact(unittest.TestCase):
    def setUp(self):
        self.w = make_impact_world()
        self.a = self.w.fence_by_dealer["甲"]
        self.b = self.w.fence_by_dealer["乙"]

    def _moved_stores(self):
        return [s for s in self.w.fence_stores(self.a) if s.name.startswith("甲西")][:2]

    def test_move_recomputes_kinds_and_loads(self):
        rep = move_impact(self.w, self.a, self.b, self._moved_stores(), FakeKB())
        self.assertEqual(rep["source_after"]["stores"], 6)
        self.assertEqual(rep["target_after"]["stores"], 6)
        # D14: 密度分母 = 领地总面积（甲 22，乙 8）
        self.assertEqual(rep["source_after"]["density_per_km2"], round(6 / 22, 1))
        self.assertEqual(rep["target_after"]["density_per_km2"], round(6 / 8, 1))
        # kind 构成按原 Store.kind 统计（重算结果只出现在 moved_detail）
        self.assertEqual(rep["source_after"]["kinds"], {"OK": 6})
        self.assertEqual(rep["target_after"]["kinds"], {"OK": 6})

    def test_moved_kind_delta_and_sample(self):
        rep = move_impact(self.w, self.a, self.b, self._moved_stores(), FakeKB())
        self.assertEqual(rep["moved_kind_delta"], {"OK → OOF": 2})
        self.assertEqual(len(rep["moved_sample"]), 2)
        self.assertTrue(all(d["kind"] == "OK → OOF" for d in rep["moved_sample"]))
        self.assertTrue(all(d["upstream"] == "甲" for d in rep["moved_sample"]))

    def test_signals_risks_evidence_chains(self):
        rep = move_impact(self.w, self.a, self.b, self._moved_stores(), FakeKB())
        self.assertEqual(len(rep["signals"]), 3)
        self.assertTrue(all("spec_ref" in s for s in rep["signals"]))
        self.assertEqual({r["kb_id"] for r in rep["risks"]},
                         {"K-PRIN-002", "K-PRIN-003", "K-RULE-006"})
        self.assertEqual(rep["materiality"], "Review")

    def test_move_nothing_raises(self):
        with self.assertRaises(ValueError):
            move_impact(self.w, self.a, self.b, self.w.fence_stores(self.b),
                        FakeKB())  # 乙的店不在甲围栏内

    def test_store_already_in_both_fences_not_movable(self):
        # 手工构造双挂门店（dealers 同时含甲乙）
        from intelligence.world import Store
        dual = Store("双挂", "食杂店/批发", "X区", "甲", 113.21, 23.01,
                     False, ("甲", "乙"), "MULTI")
        w = self.w.with_stores(list(self.w.stores) + [dual])
        with self.assertRaises(ValueError):
            move_impact(w, self.a, self.b, [dual], FakeKB())


class TestAdjustPure(unittest.TestCase):
    def setUp(self):
        self.w = make_impact_world()

    def test_km2_square_at_lat23(self):
        g = Polygon([(x, y) for x, y in sq(113.20, 23.00)])
        # 0.02°×0.02° ≈ 0.0004 deg² ≈ 4.53 km²（质心纬度换算）
        self.assertAlmostEqual(km2(g), 4.53, delta=0.05)

    def test_km2_empty_polygon_is_zero(self):
        self.assertEqual(km2(Polygon()), 0.0)

    def test_adjust_error_is_value_error(self):
        self.assertTrue(issubclass(AdjustError, ValueError))

    def test_rows_uninitialized_raises(self):
        import intelligence.adjust as adj
        saved = (adj._DATA_DIR, adj._ROWS)
        adj._DATA_DIR, adj._ROWS = None, None
        try:
            with self.assertRaises(AdjustError):
                _rows()
        finally:
            adj._DATA_DIR, adj._ROWS = saved

    def test_row_of_lookup_and_error(self):
        import intelligence.adjust as adj
        saved = (adj._DATA_DIR, adj._ROWS)
        adj._DATA_DIR, adj._ROWS = Path("/nonexistent"), [
            {"dealer": "甲", "S": [1, 2]}, {"dealer": "乙", "S": []}]
        try:
            self.assertEqual(_row_of("甲")["S"], [1, 2])
            with self.assertRaises(AdjustError):  # S 片为空
                _row_of("乙")
            with self.assertRaises(AdjustError):  # 无编译结果
                _row_of("丙")
        finally:
            adj._DATA_DIR, adj._ROWS = saved

    def test_match_dealer_exact_and_stripped(self):
        self.assertEqual(_match_dealer(self.w, "甲").dealer, "甲")
        self.assertEqual(_match_dealer(self.w, "「甲」").dealer, "甲")
        self.assertEqual(_match_dealer(self.w, "甲的门店").dealer, "甲")

    def test_match_dealer_not_found(self):
        with self.assertRaises(AdjustError):
            _match_dealer(self.w, "不存在的人")

    def test_match_dealer_ambiguous_requires_full_name(self):
        w = World({"fences": [
            {"area_id": "H1", "dealer": "华南经销商", "area_km2": 1.0,
             "rings": [sq(113.20, 23.00)]},
            {"area_id": "Z1", "dealer": "海南经销商", "area_km2": 1.0,
             "rings": [sq(113.80, 23.30)]}],
            "stores": [], "kinds": {}})
        with self.assertRaises(AdjustError):
            _match_dealer(w, "南经销商")

    def test_ring_of_rounds_and_closes(self):
        g = Polygon([(x, y) for x, y in sq(113.20, 23.00)])
        ring = _ring_of(g)
        self.assertEqual(ring[0], ring[-1])
        self.assertTrue(all(isinstance(p, tuple) for p in ring))

    def test_fence_poly_empty_ring_is_empty(self):
        f = Fence("X1", "甲", 1.0, ())
        self.assertTrue(_fence_poly(f).is_empty)

    def test_fence_union_multi_component(self):
        area = _fence_union(self.w, "甲").area
        self.assertAlmostEqual(area, 0.0008, places=6)  # 两块 0.02° 方形之和
        self.assertTrue(_fence_union(self.w, "无此人").is_empty)

    def test_proposal_defaults(self):
        p = Proposal(text="t", src_dealer="甲", dst_dealer="乙",
                     area_desc="整个区域", sub_rings=[], stores=[])
        self.assertEqual(p.pieces, [])
        self.assertEqual(p.impact, {})
        self.assertEqual(p.parser, "rules")

    def test_parse_and_propose_rejects_unparseable_text(self):
        with self.assertRaises(AdjustError):
            parse_and_propose(self.w, FakeKB(), "随便说点什么")

    def test_parse_and_propose_rejects_same_dealer(self):
        with self.assertRaises(AdjustError):
            parse_and_propose(self.w, FakeKB(), "把甲整体并入甲")

    def test_parse_and_propose_rejects_unknown_dealer(self):
        with self.assertRaises(AdjustError):
            parse_and_propose(self.w, FakeKB(), "把不存在的人整体并入乙")


if __name__ == "__main__":
    unittest.main()
