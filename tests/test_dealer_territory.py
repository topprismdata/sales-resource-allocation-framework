"""dealer_territory 模块测试（合成 OSM 索引 + 合成围栏，确定性、无门店依赖）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dealer_territory.fence_allocator import (  # noqa: E402
    allocate, compare, generate_fence,
)
from dealer_territory.four_bounds import (  # noqa: E402
    LandmarkIndex, describe_fence, four_bounds,
)
from dealer_territory.fence_analysis import (  # noqa: E402
    Fence, StorePoint, analyze, make_fence,
)


def square_ring(lon0, lat0, dx, dy, n=20):
    top = [(lon0 + dx * i / n, lat0 + dy) for i in range(n)]
    right = [(lon0 + dx, lat0 + dy - dy * i / n) for i in range(1, n)]
    bottom = [(lon0 + dx - dx * i / n, lat0) for i in range(1, n)]
    left = [(lon0, lat0 + dy * i / n) for i in range(1, n - 1)]
    return top + right + bottom + left


def synthetic_index():
    """合成 OSM 索引（坐标移出真实珠江航道带，避免与真实航道判定冲突）。"""
    main_road = [[(113.21, 23.45), (113.25, 23.45)]]            # "广州大道" 南北向（贴北界极值点）
    river = [[(113.371, 23.352), (113.40, 23.352)]]              # "测试河" 东西向（贴南界极值点）
    dist_a = [[(113.15, 23.00), (113.35, 23.00), (113.35, 23.07), (113.15, 23.07)]]
    dist_b = [[(113.35, 23.00), (113.55, 23.00), (113.55, 23.07), (113.35, 23.07)]]
    return LandmarkIndex(
        roads={"广州大道": main_road},
        rivers={"测试河": river},
        districts={"白云区": dist_a, "黄埔区": dist_b},
        road_pts=[(pt, "广州大道") for seg in main_road for pt in seg],
        river_pts=[(pt, "测试河") for seg in river for pt in seg],
    )


class TestFourBounds(unittest.TestCase):
    def test_north_road_south_river(self):
        idx = synthetic_index()
        # 围栏 lat 23.35-23.45：南界贴"测试河"(lat 23.352)，北界吸"广州大道"(lon 113.21)
        ring = square_ring(113.20, 23.35, 0.18, 0.10)
        b = four_bounds(ring, idx, main_district="白云区")
        self.assertEqual(b["南"], "测试河")
        self.assertEqual(b["北"], "广州大道")

    def test_adjacent_district(self):
        idx = synthetic_index()
        # 围栏骑在 A/B 区界 (lon 113.35) 上：西边界落入 A 区(白云)
        ring = square_ring(113.30, 23.01, 0.10, 0.035)
        b = four_bounds(ring, idx, main_district="黄埔区")
        self.assertIn("白云", b["西"])
        self.assertIn("白云", b["北"])                   # 北界落在邻区白云一侧


class TestAllocate(unittest.TestCase):
    FENCES = [
        {"dealer": "甲", "ring": square_ring(113.20, 23.00, 0.10, 0.10),
         "bbox": (113.20, 23.00, 113.30, 23.10)},
        {"dealer": "乙", "ring": square_ring(113.30, 23.00, 0.10, 0.10),
         "bbox": (113.30, 23.00, 113.40, 23.10)},
    ]
    DEALERS = ["甲", "乙"]

    def test_upstream_first(self):
        s = {"lon": 113.21, "lat": 23.01, "upstream": "乙", "excluded": False}
        self.assertEqual(allocate(s, self.DEALERS, self.FENCES), ("乙", "UPSTREAM"))

    def test_current_fence_fallback(self):
        s = {"lon": 113.31, "lat": 23.01, "upstream": "", "excluded": False}
        self.assertEqual(allocate(s, self.DEALERS, self.FENCES), ("乙", "CURRENT_FENCE"))

    def test_nearest_centroid(self):
        s = {"lon": 113.35, "lat": 23.05, "upstream": "", "excluded": False}
        dealer, rule = allocate(s, ["甲", "乙"], None)
        self.assertEqual(rule, "NEAREST_CENTROID")

    def test_excluded(self):
        s = {"lon": 113.21, "lat": 23.01, "upstream": "甲", "excluded": True}
        self.assertEqual(allocate(s, self.DEALERS, self.FENCES), (None, "EXCLUDED"))


class TestGenerateFence(unittest.TestCase):
    def test_grid_generation_closed_ring(self):
        pts = [(113.20 + 0.004 * (i % 10), 23.00 + 0.004 * (i // 10)) for i in range(100)]
        gf = generate_fence("甲", pts, cell_size_km=0.5, simplify_tolerance_km=0.05)
        self.assertIsNotNone(gf)
        self.assertGreater(len(gf.rings), 0)
        for ring in gf.rings:
            self.assertGreaterEqual(len(ring), 4)
            self.assertEqual(ring[0], ring[-1])          # 环闭合

    def test_isolated_cells_no_hang(self):
        # 回归：四角不相邻点云曾致死循环（边界环追踪）
        pts = [(113.30, 23.05), (113.31, 23.05), (113.31, 23.06), (113.30, 23.06)]
        gf = generate_fence("甲", pts, cell_size_km=0.5, simplify_tolerance_km=0.01)
        self.assertIsNotNone(gf)
        self.assertEqual(gf.store_count, 4)

    def test_empty_points(self):
        self.assertIsNone(generate_fence("甲", []))


class TestCompare(unittest.TestCase):
    def test_changed_count(self):
        stores = [
            {"n": "s1", "lon": 113.21, "lat": 23.01, "d": "A区", "u": "甲", "excluded": False},
            {"n": "s2", "lon": 113.22, "lat": 23.02, "d": "A区", "u": "甲", "excluded": False},
        ]
        cur = [{"dealer": "甲", "ring": square_ring(113.20, 23.00, 0.10, 0.10),
                "bbox": (113.20, 23.00, 113.30, 23.10)}]
        gen = generate_fence("甲", [(113.30, 23.05), (113.31, 23.05), (113.31, 23.06),
                                    (113.30, 23.06)], cell_size_km=0.5,
                             simplify_tolerance_km=0.01)
        rep = compare(stores, cur, [gen])
        self.assertEqual(rep["summary"]["total_changed"], 2)


class TestFenceAnalysis(unittest.TestCase):
    def _fence(self, dealer):
        ring = square_ring(113.20, 23.00, 0.10, 0.10)
        return make_fence("A1", dealer, "ORG", 10.0,
                          "POLYGON((" + ", ".join(f"{lon} {lat}" for lon, lat in ring) + "))")

    def test_kinds(self):
        f = self._fence("甲")
        stores = [
            StorePoint("s1", "店1", "流通", "A区", "甲", 113.25, 23.05),
            StorePoint("s2", "店2", "流通", "A区", "乙", 113.24, 23.04),
            StorePoint("s3", "直供店", "KA", "A区", "美宜佳", 113.40, 23.20),
            StorePoint("s4", "缺口店", "流通", "A区", "批发部", 113.60, 23.40),
        ]
        rep = analyze(stores, [f])
        self.assertEqual(rep.ok, 1)
        self.assertEqual(rep.out_of_fence, 1)
        self.assertEqual(rep.normal_direct, 1)
        self.assertEqual(rep.real_gap, 1)


if __name__ == "__main__":
    unittest.main()


class TestFenceSplit(unittest.TestCase):
    def test_river_split(self):
        from dealer_territory.fence_split import GeoBarrier, split_fence
        fence = square_ring(113.20, 23.00, 0.20, 0.10)
        river = GeoBarrier(name="测试河", kind="linear",
                          segments=[[(113.30, 22.99), (113.30, 23.11)]])
        stores = [
            {"store_id": "W1", "lon": 113.25, "lat": 23.05, "upstream": "甲", "excluded": False},
            {"store_id": "E1", "lon": 113.35, "lat": 23.05, "upstream": "乙", "excluded": False},
            {"store_id": "E2", "lon": 113.38, "lat": 23.08, "upstream": "乙", "excluded": False},
        ]
        r = split_fence(fence, [river], stores)
        self.assertEqual(len(r["pieces"]), 2)
        self.assertGreater(r["pieces"][0]["store_count"] +
                           r["pieces"][1]["store_count"], 0)
        self.assertEqual(len(r["unassigned_stores"]), 0)
        # 标签应区分东西
        labels = [p["label"] for p in r["pieces"]]
        self.assertNotEqual(labels[0], labels[1])

    def test_no_barrier_no_split(self):
        from dealer_territory.fence_split import GeoBarrier, split_fence
        fence = square_ring(113.20, 23.00, 0.20, 0.10)
        stores = [{"store_id": "S1", "lon": 113.25, "lat": 23.05,
                   "upstream": "甲", "excluded": False}]
        with self.assertRaises(ValueError):
            split_fence(fence, [], stores)
