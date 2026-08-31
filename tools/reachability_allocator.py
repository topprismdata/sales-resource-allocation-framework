#!/usr/bin/env python3
"""可达性围栏重建（V3）：四至路名 → 屏障 → 中心可达区域 = 围栏。

原理：围栏边界必然沿路。把四至提到的路/河设为屏障，
从中心所在街区洪泛扩散（不可穿越屏障），
可达的街区集合的并集 = 围栏。全自动，无人工。
"""
import json, sys, math
import _paths
sys.path.insert(0, str(_paths.ROOT))
import shapely
from shapely.geometry import Polygon, LineString, Point, box
from shapely.strtree import STRtree
from shapely.ops import unary_union
from intelligence.coords import pack_from_disk

DATA = _paths.DATA


def load_enclosures():
    d = json.load(open(f"{DATA}/basic_units_v5_wgs.json", encoding="utf-8"))
    return [shapely.from_wkt(u["wkt"]) for u in d["units"]]


def resolve_barriers(d_osm, bounds):
    """四至名 → 屏障几何列表（名称命中的路/河线）。"""
    out = []
    for dr, nm in (bounds or {}).items():
        if not nm:
            continue
        target = nm.split("（")[0].split("(")[0].strip().replace("边缘", "").replace("界", "")
        pieces = []
        for grp in ("roads", "rivers"):
            for r in d_osm[grp]:
                nm2 = r.get("name", "")
                if not nm2 or (target not in nm2 and nm2 not in target):
                    continue
                try: g = shapely.from_wkt(r["wkt"])
                except Exception: continue
                parts = ([g] if g.geom_type == "LineString"
                         else list(g.geoms) if g.geom_type == "MultiLineString" else [])
                pieces += [p for p in parts if p.geom_type == "LineString" and p.length > 1e-6]
        if pieces:
            out.append((dr, nm, unary_union(pieces)))
    return out


def reachability_fence(enclosures, utree, center, barriers, max_hops=400):
    """从中心所在街区洪泛；跨屏障的邻接被阻断。返回 (reachable_union, n, hop)。"""
    # 中心块
    j0 = int(utree.nearest(Point(center)))
    # 预计算邻接：共享边长>50m 的邻居
    adj = {i: set() for i in range(len(enclosures))}
    edge_barrier = {}
    for i in range(len(enclosures)):
        for j in utree.query(enclosures[i].buffer(0.0004)):
            j = int(j)
            if j <= i:
                continue
            inter = enclosures[i].intersection(enclosures[j])
            if inter.is_empty or inter.length < 50 / 111000:
                continue
            adj[i].add(j); adj[j].add(i)
            edge_barrier[frozenset((i, j))] = inter
    # 屏障线联合（含 15m 容差）
    barrier_union = unary_union([b for _, _, b in barriers]).buffer(
        15 / 111000) if barriers else None
    # BFS：共享边触屏障 → 该边不可通
    reached = {j0}
    frontier = [j0]
    hop = 0
    while frontier and hop < max_hops:
        nxt = []
        for cur in frontier:
            for nb in adj[cur]:
                if nb in reached:
                    continue
                ek = frozenset((cur, nb))
                shared = edge_barrier.get(ek)
                if shared is not None and barrier_union is not None:
                    if barrier_union.intersects(shared):
                        continue  # 这条边被屏障挡住
                reached.add(nb)
                nxt.append(nb)
        frontier = nxt
        hop += 1
        if not nxt:
            break
    geom = unary_union([enclosures[i] for i in reached])
    return geom, len(reached), hop


if __name__ == "__main__":
    meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
    reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
    cons = json.load(open(f"{DATA}/contracts.json", encoding="utf-8"))
    pack_from_disk(reg, cons, meta)
    d_osm = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))
    encs = load_enclosures()
    utree = STRtree(encs)
    for c in cons:
        aid = c.get("area_id")
        fb = c.get("four_bounds") or {}
        if len(fb) < 2:
            continue
        f = next((x for x in reg["fences"] if x["area_id"] == aid), None)
        if not f:
            continue
        zg = Polygon(f["rings"][0])
        if not zg.is_valid: zg = zg.buffer(0)
        if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
        barriers = resolve_barriers(d_osm, fb)
        geom, n, hop = reachability_fence(encs, utree, c["center"], barriers)
        iou = geom.intersection(zg).area / geom.union(zg).area
        print(f"{aid} {f['dealer'][:14]}: 可达{geom.area*11320:.1f}km² ({n}块) "
              f"vs 真值{zg.area*11320:.1f}km² IoU={iou:.3f} 屏障{[b[1] for b in barriers]}",
              flush=True)
