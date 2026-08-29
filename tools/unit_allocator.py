#!/usr/bin/env python3
"""单元分配生成器（V2）：四至 + 中心点 → 基础单元选择 → 单元并集围栏。

替代 V1c（build_from_landmark_ratios 的几何切割/比率法）。
语义映射：每个方位条款 → 该方向上的标量界线（锚点坐标）；
单元质心满足全部方向约束且与中心连通（BFS）→ 入选。
"""
import json, math
import shapely
from shapely.ops import unary_union
from shapely.geometry import LineString, Polygon, Point
from shapely.strtree import STRtree

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
AXIS = {"北": ("y", "max"), "南": ("y", "min"), "东": ("x", "max"), "西": ("x", "min")}


class UnitLibrary:
    """基础单元库（v3_clean：全路网面+伪影清理）。"""

    def __init__(self, path=f"{DATA}/basic_units_v3_clean.json"):
        d = json.load(open(path, encoding="utf-8"))
        self.geoms = [shapely.from_wkt(u["wkt"]) for u in d["units"]]
        self.tree = STRtree(self.geoms)

    def resolve_anchor(self, name, center, direction):
        """条款名 → 边界要素几何（WGS 线网），供可视性约束使用。"""
        d = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))
        target = name.split("（")[0].split("(")[0].strip().replace("边缘", "").replace("界", "")
        cbuf = shapely.geometry.Point(center).buffer(0.0045)
        best = None   # (score, geom)：离中心更近的要素优先
        for grp in ("roads", "rivers", "adm6", "adm8"):
            for r in d[grp]:
                nm = r.get("name", "")
                if not nm or target not in nm:
                    continue
                try: g = shapely.from_wkt(r["wkt"])
                except Exception: continue
                parts = ([g] if g.geom_type in ("LineString", "Polygon")
                         else list(g.geoms) if g.geom_type == "MultiLineString"
                         else list(g.geoms))
                plines = []
                for p in parts:
                    if p.geom_type == "Polygon":
                        plines.append(LineString(p.exterior.coords))
                    elif p.geom_type == "LineString":
                        plines.append(p)
                    else:
                        plines += list(p.geoms)
                if not plines:
                    continue
                lg = unary_union(plines)
                if not lg.intersects(cbuf):
                    continue  # 离中心 >500m，与条款无关
                sc = lg.distance(shapely.geometry.Point(center))
                if best is None or sc < best[0]:
                    best = (sc, lg)
        return None if best is None else best[1]


def allocate(lib, bounds, center, units_extra_wkt=None):
    """可视性约束分配：中心到单元质心的连线不得穿过任何边界要素。
    返回 (unit_indices, union_geom, missing)。"""
    center_pt = shapely.geometry.Point(center)
    bgeoms = []
    missing = []
    for dr, nm in (bounds or {}).items():
        if not nm:
            continue
        g = lib.resolve_anchor(nm, center, dr)
        if g is None:
            missing.append(f"{dr}:{nm}")
            continue
        bgeoms.append((dr, g.buffer(20 / 111000)))   # 20m 容差
    def ok(geom):
        c = geom.centroid
        conn = LineString([center_pt, c])
        for dr, bg in bgeoms:
            if conn.intersects(bg) and not c.within(bg) \
                    and not conn.covered_by(bg):
                return False
        return True
    # 种子：中心附近第一个合格的非碎片单元
    seed, seed_area = None, -1
    for j in lib.tree.query(center_pt.buffer(0.004)):
        j = int(j)
        g = lib.geoms[j]
        if g.area * 11320 < 0.003:
            continue
        if ok(g) and g.area * 11320 > seed_area:
            seed, seed_area = j, g.area * 11320
    if seed is None:
        return set(), None, missing
    # 邻接扩散（BFS）
    selected = set()
    frontier = [seed]
    seen = {seed}
    while frontier:
        cur = frontier.pop()
        g = lib.geoms[cur]
        if not ok(g) or g.area * 11320 < 0.003:
            continue
        selected.add(cur)
        for j in lib.tree.query(g.buffer(0.002)):
            j = int(j)
            if j in seen:
                continue
            seen.add(j)
            frontier.append(j)
    if not selected:
        return set(), None, missing
    geom = unary_union([lib.geoms[i] for i in selected])
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    return selected, geom, missing

    """返回 (unit_indices, union_geom, missing)。"""
    center_pt = Point(center)
    # 方向界线
    limits = {}
    missing = []
    for dr, nm in (bounds or {}).items():
        if not nm:
            continue
        v = lib.resolve_anchor(nm, center, dr)
        if v is None:
            missing.append(f"{dr}:{nm}")
            continue
        limits[dr] = v
    # 同轴矛盾检测：上下界冲突 → 丢弃该轴（锚点贴着中心的弱证据）
    def axis_bad(hi, lo, ci):
        # 轴带宽 <500m = 锚点贴着中心的矛盾/弱证据 → 丢弃该轴
        return hi in limits and lo in limits and \
            (limits[lo] - limits[hi]) < 500 / 111000
    if axis_bad("东", "西", 0):
        limits.pop("东", None); limits.pop("西", None)
    if axis_bad("北", "南", 1):
        limits.pop("北", None); limits.pop("南", None)
    def ok(geom):
        c = geom.centroid
        if "北" in limits and c.y > limits["北"]: return False
        if "南" in limits and c.y < limits["南"]: return False
        if "东" in limits and c.x > limits["东"]: return False
        if "西" in limits and c.x < limits["西"]: return False
        return True
    # 种子：中心附近第一个满足全部界线的单元
    seed, seed_area = None, -1
    for j in lib.tree.query(center_pt.buffer(0.004)):
        j = int(j)
        g = lib.geoms[j]
        if g.area * 11320 < 0.003:   # 碎片面跳过
            continue
        if ok(g) and g.area * 11320 > seed_area:
            seed, seed_area = j, g.area * 11320
    if seed is None:
        return set(), None, missing
    # 候选：中心所在+满足方向约束的单元（邻接扩散）
    selected = set()
    frontier = [seed]
    seen = {seed}
    while frontier:
        cur = frontier.pop()
        g = lib.geoms[cur]
        if not ok(g) or g.area * 11320 < 0.003:
            continue
        selected.add(cur)
        for j in lib.tree.query(g.buffer(0.002)):
            j = int(j)
            if j in seen:
                continue
            seen.add(j)
            frontier.append(j)
    if not selected:
        return set(), None, missing
    geom = unary_union([lib.geoms[i] for i in selected])
    if geom.geom_type == "MultiPolygon":   # 保留含中心的主块
        geom = max(geom.geoms, key=lambda g: g.area)
    return selected, geom, missing
