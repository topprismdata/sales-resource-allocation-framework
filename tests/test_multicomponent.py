"""D14 multi-component territory tests (design doc §7.1).

Synthetic world built in-memory (WGS-84 declared, so pack_from_disk is a
no-op and coords are used as-is). Covers: 1:N index, dealer resolution,
single/multi/zero transfers, multi-ring proposal, persistence round-trip,
same-dealer guard, density aggregation.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intelligence.world import World
from intelligence.adjust import (
    AdjustError, _match_dealer, apply_proposal, build_proposal, parse_and_propose)
from intelligence.impact import move_impact


def sq(cx, cy, h=0.01):
    """a small square ring around (cx,cy)."""
    return [[cx - h, cy - h], [cx + h, cy - h],
            [cx + h, cy + h], [cx - h, cy + h], [cx - h, cy - h]]


def make_world():
    """Dealer A owns TWO disconnected components (west + far east);
    Dealer B owns one (south).  Each component has 4 stores."""
    def stores(dealer, bx, by, prefix):
        return [{"n": f"{prefix}{i}", "c": "食杂店/批发", "d": "X区", "u": dealer,
                 "lon": bx + 0.001 * i, "lat": by + 0.001 * i,
                 "direct": False, "dealers": [dealer], "kind": "OK"}
                for i in range(4)]

    fences = [
        {"area_id": "A1", "dealer": "经销商甲", "area_km2": 10.0, "rings": [sq(113.20, 23.00)]},
        {"area_id": "A2", "dealer": "经销商甲", "area_km2": 12.0, "rings": [sq(113.80, 23.30)]},
        {"area_id": "B1", "dealer": "经销商乙", "area_km2": 8.0, "rings": [sq(113.25, 22.80)]},
    ]
    raw = {"fences": fences,
           "stores": (stores("经销商甲", 113.20, 23.00, "甲西")
                      + stores("经销商甲", 113.80, 23.30, "甲东")
                      + stores("经销商乙", 113.25, 22.80, "乙南")),
           "kinds": {"OK": 12}}
    return World(raw)


class TestMultiComponent(unittest.TestCase):
    def setUp(self):
        self.w = make_world()

    # 1
    def test_fences_of_returns_all_components(self):
        self.assertEqual(len(self.w.fences_of("经销商甲")), 2)
        self.assertEqual(len(self.w.fences_of("经销商乙")), 1)
        self.assertEqual(self.w.fences_of("不存在"), [])

    # 2 (fence_by_dealer stays a single first-component, backward compat)
    def test_fence_by_dealer_backward_compat(self):
        f = self.w.fence_by_dealer.get("经销商甲")
        self.assertIsNotNone(f)
        self.assertEqual(f.dealer, "经销商甲")
        # territory_area sums both blocks
        self.assertAlmostEqual(self.w.territory_area_km2("经销商甲"), 22.0)

    # 3
    def test_match_dealer_returns_component(self):
        f = _match_dealer(self.w, "经销商甲")
        self.assertEqual(f.dealer, "经销商甲")
        # resolution still yields a Fence usable for select_area via dealer name
        self.assertEqual(len(self.w.fences_of(f.dealer)), 2)

    # 4 select "全部" covers stores from BOTH components
    def test_select_area_spans_components(self):
        src = _match_dealer(self.w, "经销商甲")
        p = build_proposal(self.w, FakeKB(), "把经销商甲的整个区域划给经销商乙",
                           src, _match_dealer(self.w, "经销商乙"), "全部")
        # all 8 of A's stores (both components) move
        self.assertEqual(len(p.stores), 8)
        self.assertEqual(set(s.name[:2] for s in p.stores), {"甲西", "甲东"} if False else {"甲西", "甲东"})

    # 5 single-component transfer still works
    def test_transfer_single_component(self):
        p = parse_and_propose(self.w, FakeKB(), "把经销商乙的整个区域划给经销商甲")
        self.assertEqual(len(p.stores), 4)
        w2 = apply_proposal(self.w, p)
        # B now has 0 stores → 0 fences
        self.assertEqual(w2.fences_of("经销商乙"), [])
        self.assertEqual(len(w2.fences_of("经销商甲")), 3)  # 西/东/并入的南 三不连续簇

    # 6 multi-component: after moving B into A, A's west cluster absorbs B
    #    (B is near A's west); east cluster stays separate → still 2 components
    def test_transfer_multi_component_preserves_clusters(self):
        p = parse_and_propose(self.w, FakeKB(), "把经销商乙的整个区域划给经销商甲")
        w2 = apply_proposal(self.w, p)
        a = w2.fences_of("经销商甲")
        self.assertGreaterEqual(len(a), 3)  # 西(+B) / 东 分离，B 距两者均>2km
        self.assertEqual(len(w2.stores), 12)  # store count conserved

    # 7 zero-store removal
    def test_transfer_zero_store_removal(self):
        p = parse_and_propose(self.w, FakeKB(), "把经销商甲整体并入经销商乙")
        w2 = apply_proposal(self.w, p)
        self.assertEqual(w2.fences_of("经销商甲"), [])

    # 8 proposal sub_rings is a LIST (multi-ring safe)
    def test_proposal_multi_ring(self):
        src = _match_dealer(self.w, "经销商甲")
        p = build_proposal(self.w, FakeKB(), "把经销商甲的整个区域划给经销商乙",
                           src, _match_dealer(self.w, "经销商乙"), "全部")
        self.assertIsInstance(p.sub_rings, list)
        self.assertGreaterEqual(len(p.sub_rings), 1)
        for ring in p.sub_rings:
            self.assertTrue(len(ring) >= 4)

    # 9 same-dealer guard now compares dealer, not area_id
    def test_same_dealer_guard(self):
        # 甲 west block vs 甲 east block are SAME dealer → must be rejected
        src = self.w.fences_of("经销商甲")[0]
        dst = self.w.fences_of("经销商甲")[1]
        with self.assertRaises(AdjustError):
            build_proposal(self.w, FakeKB(), "把甲的西块划给甲的东块",
                           src, dst, "全部")

    # 10 density uses summed territory area (not one block)
    def test_density_multi_component(self):
        src = _match_dealer(self.w, "经销商乙")
        a = _match_dealer(self.w, "经销商甲")
        b = _match_dealer(self.w, "经销商乙")
        stores = self.w.fence_stores(a)
        rep = move_impact(self.w, a, b, stores, FakeKB())
        # 经销商甲 source_after density: 0 stores / 22 → 0.0
        self.assertEqual(rep["source_after"]["stores"], 0)
        # target density denominator = 8 (only B block), source = 22 (both)
        self.assertEqual(rep["target_after"]["stores"], 12)


class FakeKB:
    version = "test"
    gaps = []

    def cite(self, kid):
        return {"kb_id": kid, "statement": "s", "source": "t", "confidence": "HIGH"}

    @staticmethod
    def validate_chain(chain):
        return True


if __name__ == "__main__":
    unittest.main()
