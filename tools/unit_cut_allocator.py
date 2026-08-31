#!/usr/bin/env python3
"""§12.2 对偶图标签匹配 min-cut 分配器（最终版）。

前景 = 种子单元（合同中心所在）；硬背景 = 可视性违例单元
（中心→质心连线穿过任一四至锚定要素）。
n-link 容量 = 共享边长 × 标签匹配因子：
  弧名与该方位四至条款名匹配 → 0.05（割在这里最便宜）
  部分匹配 → 0.5；不匹配 → 1.0
min cut 的源侧 = 分配给该经销商的基础单元集合。
"""
import json, sys, math
import _paths
sys.path.insert(0, str(_paths.ROOT))
import networkx as nx
import statistics
import shapely
from shapely.geometry import LineString, Polygon, Point, box
from shapely.strtree import STRtree
from shapely.ops import unary_union

DATA = _paths.DATA
DIRVEC = {"北": (0, 1), "南": (0, -1), "东": (1, 0), "西": (-1, 0)}
QUADS = {"北": 0, "东北": 45, "东": 90, "东南": 135, "南": 180,
         "西南": 225, "西": 270, "西北": 315}


def compass_deg(p, center):
    px = p.x if hasattr(p, "x") else p[0]
    py = p.y if hasattr(p, "y") else p[1]
    return (math.degrees(math.atan2(px - center[0], py - center[1])) + 360) % 360


def name_match(nm_edge, nm_clause):
    """0.05 精确含 ｜ 0.5 双向 2 字前缀含 ｜ 1.0 不匹配。"""
    if not nm_edge:
        return 1.0
    if not nm_clause:
        return 1.0
    if nm_clause in nm_edge or nm_edge in nm_clause:
        return 0.05
    if len(nm_edge) >= 2 and len(nm_clause) >= 2 and (
            nm_edge[:2] == nm_clause[:2]):
        return 0.5
    return 1.0


class UnitGraph:
    """基础单元 + 邻接弧（带线名标签）。"""

    def __init__(self, units_path=f"{DATA}/basic_units_v5_wgs.json",
                 osm_path=f"{DATA}/gz_osm_full.json"):
        d = json.load(open(units_path, encoding="utf-8"))
        self.units = [shapely.from_wkt(u["wkt"]) for u in d["units"]]
        self.utree = STRtree(self.units)
        o = json.load(open(osm_path, encoding="utf-8"))
        named = []
        for grp in ("roads", "rivers", "adm6", "adm8"):
            for r in o[grp]:
                if not r.get("name"):
                    continue
                try: g = shapely.from_wkt(r["wkt"])
                except Exception: continue
                parts = ([g] if g.geom_type in ("LineString", "Polygon")
                         else list(g.geoms) if g.geom_type == "MultiLineString"
                         else list(g.geoms) if g.geom_type == "MultiPolygon" else [])
                for p in parts:
                    if p.geom_type == "Polygon":
                        p = LineString(p.exterior.coords)
                    if p.length > 1e-5:
                        named.append((r["name"], p))
        self.ntree = STRtree([p for _, p in named])
        self.nname = [n for n, _ in named]

    def label_of(self, shared_mid, tol=15 / 111000):
        jr = self.ntree.query_nearest(shared_mid, return_distance=True)
        dd = float(jr[1][0])
        if dd > tol:
            return None
        j = int(jr[0][0])
        return self.nname[j]

    def candidates(self, center, R):
        return sorted(set(int(j) for j in self.utree.query(
            Point(center).buffer(R))))

    def anchor_geoms(self, d_osm, bounds, center):
        out = []
        for dr, nm in (bounds or {}).items():
            if not nm:
                continue
            target = nm.split("（")[0].split("(")[0].strip().replace(
                "边缘", "").replace("界", "")
            best = None
            for grp in ("roads", "rivers", "adm6", "adm8"):
                for r in d_osm[grp]:
                    nm2 = r.get("name", "")
                    if not nm2 or (target not in nm2 and nm2 not in target):
                        continue
                    try: g = shapely.from_wkt(r["wkt"])
                    except Exception: continue
                    parts = ([g] if g.geom_type in ("LineString", "Polygon")
                             else list(g.geoms) if g.geom_type in (
                                 "MultiLineString", "MultiPolygon") else [])
                    plines = []
                    for p in parts:
                        if p.geom_type == "Polygon":
                            plines.append(LineString(p.exterior.coords))
                        elif p.geom_type == "LineString":
                            plines.append(p)
                        else:
                            plines += [x for x in p.geoms
                                       if x.geom_type == "LineString"]
                    if not plines:
                        continue
                    lg = unary_union(plines)
                    dd = lg.distance(Point(center))
                    if best is None or dd < best[0]:
                        best = (dd, lg, dr, nm2)
            if best:
                out.append({"direction": dr, "geom": best[1], "name": best[3],
                            "dist": best[0]})
        return out


def allocate(ug: UnitGraph, d_osm, bounds, center, verbose=False):
    center = tuple(center)
    cp = Point(center)
    anchors = ug.anchor_geoms(d_osm, bounds, center)
    if len(anchors) < 2:
        return None, {"error": f"锚不足 {len(anchors)}"}, []
    adists = []
    for a in anchors:
        g = a["geom"]
        parts = ([g] if g.geom_type in ("LineString", "Polygon")
                 else list(g.geoms) if g.geom_type in (
                     "MultiLineString", "MultiPolygon") else [])
        for p in parts:
            ring = p.exterior.coords if p.geom_type == "Polygon" else p.coords
            adists += [math.dist(center, q) for q in list(ring)[::7]]
    adists.sort()
    R = adists[int(len(adists) * 0.95)] + 1500 / 111000
    cand = ug.candidates(center, R)
    if verbose:
        print(f"锚: {[(a['direction'], a['name']) for a in anchors]} | "
              f"R={R*111000:.0f}m 候选块 {len(cand)}", flush=True)
    idx = {j: k for k, j in enumerate(cand)}

    # KAPPA：数据推导的前景奖励系数（邻接边中位容量/单元中位面积）
    samp = []
    for a_i in range(len(cand)):
        for b_i in range(a_i + 1, min(a_i + 30, len(cand))):
            ga, gb = ug.units[cand[a_i]], ug.units[cand[b_i]]
            inter = ga.intersection(gb)
            if not inter.is_empty and inter.length > 50 / 111000:
                samp.append(inter.length)
    med_edge = statistics.median(samp) if samp else 0.003
    med_area = statistics.median(ug.units[j].area for j in cand)
    KAPPA = med_edge / med_area
    if verbose:
        print(f"KAPPA={KAPPA:.1f}", flush=True)

    # 种子：中心所在块
    j0 = int(ug.utree.nearest(cp))
    seed = idx[j0]

    G = nx.Graph()
    G.add_node("S"); G.add_node("T")
    # 硬约束：背景 = 可视性违例块
    for j in cand:
        k = idx[j]
        g = ug.units[j]
        c = g.centroid
        conn = LineString([cp, c])
        viol = any(conn.intersects(a["geom"].buffer(20 / 111000))
                   for a in anchors)
        if k == seed:
            G.add_edge("S", k, cap=1e18)
        elif viol:
            G.add_edge(k, "T", cap=1e18)
        else:
            area2 = g.area
            G.add_edge("S", k, cap=max(area2 * KAPPA, 0.01))
    # n-link 容量
    for a_i in range(len(cand)):
        for b_i in range(a_i + 1, len(cand)):
            ja, jb = cand[a_i], cand[b_i]
            ga, gb = ug.units[ja], ug.units[jb]
            inter = ga.intersection(gb)
            if inter.is_empty or inter.length < 50 / 111000:
                continue
            mid = inter.interpolate(0.5, normalized=True)
            nm = ug.label_of(mid)
            quadrant = min(QUADS.items(),
                           key=lambda kv: abs(((compass_deg(mid, center)
                                                 - kv[1] + 180) % 360) - 180))[0]
            best_clause = min(
                (a for a in anchors), key=lambda a: abs(
                    ((QUADS.get(a["direction"], compass_deg(mid, center))
                      + 180) % 360) - 180)) if False else None
            # 匹配该方位的条款名
            mf = 1.0
            dr_q = quadrant[0] if quadrant in ("北", "南", "东", "西") else quadrant[:2]
            for a in anchors:
                if a["direction"] == dr_q or (
                        len(dr_q) == 1 and a["direction"][0] == dr_q):
                    mf = name_match(nm, a["name"])
                    break
            cap = inter.length * mf
            G.add_edge(idx[ja], idx[jb], cap=max(cap, 0.01))
    cutv, (src_part, _) = nx.minimum_cut(G, "S", "T", capacity="cap")
    keep = [cand[j] for j in src_part if isinstance(j, int)]
    if not keep:
        return None, {"error": "空割"}, []
    geom = unary_union([ug.units[j] for j in keep])
    info = {"units": len(keep), "cut": cutv,
            "anchors": [(a["direction"], a["name"]) for a in anchors]}
    return geom, info, keep


if __name__ == "__main__":
    meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
    reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
    from intelligence.coords import pack_from_disk
    pack_from_disk(reg, [], meta)
    d_osm = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))
    ug = UnitGraph()
    targets = sys.argv[1:] or ["694420772", "694420772-2"]
    cons = json.load(open(f"{DATA}/contracts.json", encoding="utf-8"))
    for aid in targets:
        c = next((x for x in cons if x.get("area_id") == aid), None)
        f = next((x for x in reg["fences"] if x["area_id"] == aid), None)
        if not c or not f:
            continue
        zg = Polygon(f["rings"][0])
        if not zg.is_valid: zg = zg.buffer(0)
        if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
        try:
            geom, info, keep = allocate(ug, d_osm, c["four_bounds"],
                                        c["center"], verbose=True)
        except Exception as e:
            print(f"{aid} ERR: {e}", flush=True)
            continue
        iou = geom.intersection(zg).area / geom.union(zg).area
        print(f"{aid} {f['dealer'][:14]}: {geom.area*11320:.1f}km² vs 真值"
              f"{zg.area*11320:.1f}km² IoU={iou:.3f}", flush=True)
