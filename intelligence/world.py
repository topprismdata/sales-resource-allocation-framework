"""世界模型切片：gz_data.json → 围栏/门店对象 + PIP + kind 语义（与生成逻辑一致）。

kind 语义（已对照地图工具与 fence_analysis.analyze 核实）:
  MULTI        len(dealers) > 1
  DIRECT       len(dealers) == 0 and direct
  GAP          len(dealers) == 0 and not direct
  DIRECT_IN    len(dealers) == 1 and direct
  OK           len(dealers) == 1 and u == dealers[0]
  OOF          len(dealers) == 1 and u != dealers[0]
重算移动门店的 kind 时沿用同一规则（u/direct 不变，dealers 按新归属重算）。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Fence:
    area_id: str
    dealer: str
    area_km2: float
    ring: tuple[tuple[float, float], ...]

    @property
    def centroid(self) -> tuple[float, float]:
        xs = [p[0] for p in self.ring]
        ys = [p[1] for p in self.ring]
        return (sum(xs) / len(xs), sum(ys) / len(ys))


@dataclass(frozen=True)
class Store:
    name: str
    category: str
    district: str
    upstream: str          # u：实际上游
    lon: float
    lat: float
    direct: bool
    dealers: tuple[str, ...]  # 所在围栏的经销商（生成时 PIP 结果）
    kind: str


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def point_in_ring(pt: tuple[float, float], ring: tuple[tuple[float, float], ...]) -> bool:
    """射线法（与 fence_analysis.point_in_polygon 同算法）。"""
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


class World:
    """gz_data.json 快照的内存切片。"""

    def __init__(self, path: "str|dict" = "/tmp/gz_data.json") -> None:
        raw = path if isinstance(path, dict) else json.load(open(path, encoding="utf-8"))
        self.fences: list[Fence] = []
        for f in raw["fences"]:
            rings = f["rings"]
            if isinstance(rings, str):
                rings = json.loads(rings)
            self.fences.append(Fence(
                f["area_id"], f["dealer"], float(f["area_km2"]),
                tuple(tuple(map(float, p)) for p in rings[0])))
        self.stores: list[Store] = [
            Store(s["n"], s["c"], s["d"], s["u"], float(s["lon"]), float(s["lat"]),
                  str(s["direct"]) == "True", tuple(s["dealers"]), s["kind"])
            for s in raw["stores"]
        ]
        self.by_dealer: dict[str, list[Store]] = {}
        for s in self.stores:
            for d in s.dealers:
                self.by_dealer.setdefault(d, []).append(s)
        self.fence_by_dealer = {f.dealer: f for f in self.fences}
        self.kind_counts = raw["kinds"]

    def with_stores(self, stores: list[Store]) -> "World":
        """以新门店列表重建索引（fences/kind_counts 共享）——用于调整应用。"""
        w = World.__new__(World)
        w.fences = self.fences
        w.stores = stores
        w.by_dealer = {}
        for s in stores:
            for d in s.dealers:
                w.by_dealer.setdefault(d, []).append(s)
        w.fence_by_dealer = self.fence_by_dealer
        from collections import Counter
        w.kind_counts = dict(Counter(s.kind for s in stores))
        return w

    def with_fences(self, fences: list) -> "World":
        """以新围栏列表重建（stores 保留）——用于合同生成围栏。"""
        w = World.__new__(World)
        w.fences = fences
        w.stores = self.stores
        w.by_dealer = self.by_dealer
        w.fence_by_dealer = {f.dealer: f for f in fences}
        w.kind_counts = self.kind_counts
        return w

    # ---- 派生 ----

    def fence_stores(self, fence: Fence) -> list[Store]:
        return self.by_dealer.get(fence.dealer, [])

    def reclassify(self, store: Store, new_dealers: tuple[str, ...]) -> str:
        """移动门店后重算 kind（u/direct 不变）。"""
        if len(new_dealers) > 1:
            return "MULTI"
        if not new_dealers:
            return "DIRECT" if store.direct else "GAP"
        if store.direct:
            return "DIRECT_IN"
        return "OK" if store.upstream == new_dealers[0] else "OOF"

    def dealers_at(self, lon: float, lat: float) -> tuple[str, ...]:
        return tuple(f.dealer for f in self.fences if point_in_ring((lon, lat), f.ring))

    def nearest_fence(self, pt: tuple[float, float],
                      exclude: set[str] = frozenset()) -> tuple[Fence, float] | None:
        best: tuple[Fence, float] | None = None
        for f in self.fences:
            if f.area_id in exclude:
                continue
            d = haversine_km(pt, f.centroid)
            if best is None or d < best[1]:
                best = (f, d)
        return best
