"""基于道路/河流的围栏切分（微调）— 集成 market_partition 几何引擎。

用法：
    barrier = fetch_barrier("陈村水道", bbox)          # 从 OSM 拉河道几何
    result = split_fence(fence_ring, [barrier])       # 沿河道切分
    for piece in result.pieces:                       # 每个子区域
        ...                                           # 人确认 → 归属变更
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from shapely.geometry import LineString, MultiLineString, Point, Polygon, MultiPolygon
from shapely.ops import unary_union, linemerge

from market_partition.geometry.split import Barrier, partition, SplitResult
from market_partition.geometry.classify import classify_points, tally_by_region, apply_counts_to_regions
from market_partition.geometry.orient import label_piece


# ---- Barrier 构造 ----

@dataclass
class GeoBarrier:
    """一条切割障碍（道路/河流/行政边界）的 SRAF 包装。"""
    name: str
    kind: str            # "linear" (道路) / "closed" (环形路)
    segments: list[list[tuple[float, float]]]   # WGS84 折线段

    def to_barrier(self) -> Barrier:
        """转为 market_partition 的 Barrier 对象。"""
        if len(self.segments) == 1:
            geom = LineString(self.segments[0])
        else:
            geom = MultiLineString([LineString(s) for s in self.segments])
        # 判断障碍主体走向：南北向线 → 东西分标签；反之亦然
        lons_all = [p[0] for seg in self.segments for p in seg]
        lats_all = [p[1] for seg in self.segments for p in seg]
        span_x = (max(lons_all) - min(lons_all)) * 102.2
        span_y = (max(lats_all) - min(lats_all)) * 110.574
        scheme = "ew" if span_y > span_x else "ns"
        return Barrier(name=self.name, geometry=geom, kind=self.kind,
                       orient_scheme=scheme)


# ---- 围栏切分 ----

def split_fence(
    fence_ring: list[tuple[float, float]],
    barriers: list[GeoBarrier],
    stores: list[dict],
    dealer: str = "原经销商",
    region_name: str = "围栏区域",
) -> dict:
    """沿障碍物切分围栏，归类门店。

    参数：
        fence_ring  : [(lon,lat), ...] 围栏多边形顶点
        barriers    : 切割障碍列表（道路/河流）
        stores      : [{"store_id", "lon", "lat", "upstream", ...}]

    返回：
        {
            "pieces": [{"label": "陈村水道-东", "store_count": N, "polygon": [...]}],
            "unassigned_stores": [...],
            "diagnostics": ...
        }
    """
    # shapely 围栏
    closed = list(fence_ring) + [fence_ring[0]]
    region_poly = Polygon(closed)
    if not region_poly.is_valid:
        region_poly = region_poly.buffer(0)

    # 构造 market_partition Barriers
    mp_barriers = [b.to_barrier() for b in barriers]

    # 切分
    result = partition(region_poly, mp_barriers)

    # 门店点 → Point
    store_pts = [Point(s["lon"], s["lat"]) for s in stores]
    store_props = [{"store_id": s.get("store_id", s.get("name", "")),
                    "upstream": s.get("upstream", "")} for s in stores]

    # 归类
    classified = classify_points(store_pts, result.pieces, store_props)
    counts = tally_by_region(classified)
    apply_counts_to_regions(result.pieces, counts)

    # 汇总
    pieces = []
    for piece in result.pieces:
        poly_coords = list(piece.polygon.exterior.coords)
        pieces.append({
            "label": piece.label,
            "store_count": piece.poi_count,
            "polygon": [[round(x, 6), round(y, 6)] for x, y in
                        piece.polygon.exterior.coords[:-1]],
            "area_km2": round(piece.polygon.area * 111.32 * 110.574 *
                              math.cos(math.radians(piece.polygon.centroid.y)), 2)
        })

    unassigned = [
        {"store_id": cp.props["store_id"] if cp.props else "",
         "lon": cp.point.x, "lat": cp.point.y,
         "upstream": cp.props.get("upstream", "") if cp.props else ""}
        for cp in classified if cp.region_id is None
    ]

    return {
        "pieces": pieces,
        "unassigned_stores": unassigned,
        "diagnostics": result.diagnostics,
        "barrier_names": [b.name for b in barriers],
    }


# ---- 从 OSM 获取障碍几何 ----

def fetch_barrier_from_overpass(
    name: str,
    bbox: tuple[float, float, float, float],
    barrier_type: str = "waterway",
    timeout: int = 60,
) -> GeoBarrier | None:
    """从 Overpass API 获取道路/河流的几何。

    barrier_type: "waterway" (河流/水道) | "highway" (道路)
    """
    import urllib.request
    import urllib.parse

    y0, x0, y1, x1 = bbox[1], bbox[0], bbox[3], bbox[2]
    if barrier_type == "waterway":
        query = f'[out:json][timeout:{timeout}];way["waterway"~"^(river|canal)$"]["name"~"{name}"]({y0},{x0},{y1},{x1});out geom;'
    else:
        query = f'[out:json][timeout:{timeout}];way["highway"~"^(trunk|primary)$"]["name"~"{name}"]({y0},{x0},{y1},{x1});out geom;'

    api = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(api, data=data, headers={"User-Agent": "SRAF/1.0"})
    import urllib.error
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read())
    except Exception as e:
        print(f"Overpass error: {e}")
        return None

    segments = []
    for e in d.get("elements", []):
        if e.get("type") != "way" or "geometry" not in e:
            continue
        seg = [(p["lon"], p["lat"]) for p in e["geometry"] if p]
        if len(seg) > 1:
            segments.append(seg)
    if not segments:
        return None

    kind = "linear" if barrier_type == "highway" else "linear"
    return GeoBarrier(name=name, kind=kind, segments=segments)
