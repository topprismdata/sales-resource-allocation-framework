"""四至描述生成（人类可读的区域闭合表述）——基于 OSM 公共地理数据。

「四至」= 中国地籍/合同描述区域的天然语言：东至X、南至Y、西至Z、北至W。
参照优先级（真实合同「以界限划分」条款同款）：
    1. 界河：珠江前/后/西航道等命名河流（点落在河道带内，或吸附最近河流）
    2. 主干道：围栏边界极值点吸附最近 OSM 命名主干道（trunk/primary/secondary）
    3. 邻区界：极值点落入相邻区县行政边界内 → "X区界"

不依赖门店数据。地标索引由 build_index(osm_parsed) 从 OSM 数据构建
（一次构建，多围栏复用）。

⚠️ 术语纪律：非围栏供货是中性洞察；四至中的邻区地标只是边界参照。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

GZ_DISTRICTS = ("越秀区", "海珠区", "荔湾区", "天河区", "白云区", "黄埔区",
                "番禺区", "南沙区", "花都区", "增城区", "从化区")

# 珠江中心城区段航道带（经纬度近似框，边界点落入即判界河）
PEARL_BRANCHES = (
    ("珠江前航道", 23.096, 23.140, 113.230, 113.490),
    ("珠江后航道", 23.048, 23.102, 113.195, 113.450),
    ("珠江西航道", 23.090, 23.175, 113.150, 113.330),
)

_LON_KM, _LAT_KM = 102.2, 110.574


def _km2(a, b) -> float:
    return ((a[0] - b[0]) * _LON_KM) ** 2 + ((a[1] - b[1]) * _LAT_KM) ** 2


# ---------- 地标索引 ----------

@dataclass
class LandmarkIndex:
    roads: dict[str, list[list[tuple[float, float]]]]       # 路名 -> 段列表
    rivers: dict[str, list[list[tuple[float, float]]]]      # 河名 -> 段列表
    districts: dict[str, list[list[tuple[float, float]]]]   # 区县 -> 环列表
    road_pts: list[tuple[tuple[float, float], str]]         # (点, 路名) 展平
    river_pts: list[tuple[tuple[float, float], str]]        # (点, 河名) 展平


def build_index(osm_parsed: dict) -> LandmarkIndex:
    roads = osm_parsed.get("roads", {})
    rivers = osm_parsed.get("rivers", {})
    districts = {}
    for name, v in osm_parsed.get("districts", {}).items():
        polys = v["polys"] if isinstance(v, dict) else v
        if polys:
            districts[name] = polys
    road_pts = [(pt, name) for name, segs in roads.items() for seg in segs for pt in seg]
    river_pts = [(pt, name) for name, segs in rivers.items() for seg in segs for pt in seg]
    return LandmarkIndex(roads, rivers, districts, road_pts, river_pts)


# ---------- 参照判定 ----------

def river_at(pt, idx: LandmarkIndex, snap_km: float = 1.0) -> str | None:
    lon, lat = pt
    for name, y0, y1, x0, x1 in PEARL_BRANCHES:
        if y0 <= lat <= y1 and x0 <= lon <= x1:
            return name
    r2 = snap_km ** 2
    best, best_d = None, r2
    for p, nm in idx.river_pts:
        d = _km2(pt, p)
        if d < best_d:
            best_d, best = d, nm
    return best


def nearest_road(pt, idx: LandmarkIndex, max_km: float = 1.2) -> str | None:
    r2 = max_km ** 2
    best, best_d = None, r2
    for p, nm in idx.road_pts:
        d = _km2(pt, p)
        if d < best_d:
            best_d, best = d, nm
    return best


def district_containing(pt, idx: LandmarkIndex) -> str | None:
    for dn, polys in idx.districts.items():
        for poly in polys:
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            if _pip(pt, poly, (min(xs), min(ys), max(xs), max(ys))):
                return dn
    return None


def main_district(ring, idx: LandmarkIndex) -> str | None:
    """围栏边界采样点的多数区县（OSM 区界判定）。"""
    sample = ring[:: max(1, len(ring) // 60)]
    cnt: Counter = Counter()
    for p in sample:
        dn = district_containing(p, idx)
        if dn:
            cnt[dn] += 1
    return cnt.most_common(1)[0][0] if cnt else None


def _pip(pt, ring, bbox) -> bool:
    x, y = pt
    x0, y0, x1, y1 = bbox
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


# ---------- 四至 ----------

def _dir_label(pt, idx: LandmarkIndex, main_district: str, road_km: float = 1.2,
               river_snap_km: float = 1.0) -> str:
    river = river_at(pt, idx, river_snap_km)
    if river:
        return river
    road = nearest_road(pt, idx, road_km)
    if road:
        return road
    adj = district_containing(pt, idx)
    if adj and adj != main_district:
        return f"{adj}区界"
    return f"{main_district}边缘"


def four_bounds(ring, idx: LandmarkIndex, main_district: str | None = None) -> dict:
    md = main_district or main_district(ring, idx) or "未知"
    extremes = {
        "北": max(ring, key=lambda p: p[1]),
        "南": min(ring, key=lambda p: p[1]),
        "东": max(ring, key=lambda p: p[0]),
        "西": min(ring, key=lambda p: p[0]),
    }
    return {d: _dir_label(pt, idx, md) for d, pt in extremes.items()}


def describe_fence(ring, idx: LandmarkIndex, main_district: str | None = None) -> str:
    b = four_bounds(ring, idx, main_district)
    return f"西至{b['西']}，北至{b['北']}，东至{b['东']}，南至{b['南']}。"
