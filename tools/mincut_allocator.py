#!/usr/bin/env python3
"""Min-cut 单元分配器（V3）。

块邻接图上做 s-t 最小割：
- 源 = 中心所在的街区块
- 汇 = 可视性违例块（中心→块质心连线穿过任一锚定要素）+ 走廊边缘块
- 容量 = 共享边界长度 × (0.05 + (距最近锚定线/τ)²)
  → 切沿锚线走最便宜，别处切代价指数级高
源侧分区 = 分配给该经销商的单元集合。
"""
import json, sys, math, statistics
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import networkx as nx
import shapely
from shapely.geometry import LineString, Polygon, Point, box
from shapely.strtree import STRtree
from shapely.ops import unary_union

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"


def load_blocks(path=f"{DATA}/basic_units_v5_wgs.json"):
    d = json.load(open(path, encoding="utf-8"))
    return [shapely.from_wkt(u["wkt"]) for u in d["units"]]


def resolve_anchors(d_osm, bounds, center):
    """条款名 → 锚定要素几何（离中心最近的同名要素，需在中心 500m-15km 环内）。"""
    out = []
    c = Point(center)
    for dr, nm in (bounds or {}).items():
        if not nm:
            continue
        target = nm.split("（")[0].split("(")[0].strip().replace("边缘", "").replace("界", "")
        best = None
        for grp in ("roads", "rivers", "adm6", "adm8"):
            for r in d_osm[grp]:
                nm2 = r.get("name", "")
                if not nm2 or (target not in nm2 and nm2 not in target):
                    continue
                try: g = shapely.from_wkt(r["wkt"])
                except Exception: continue
                dd = g.distance(c)
                if best is None or dd < best[0]:
                    best = (dd, g)
        if best:
            out.append((dr, nm, best[1]))
    return out


def allocate_mincut(blocks, utree, bounds, center, d_osm, verbose=False):
    center = tuple(center)
    cp = Point(center)
    anchors = resolve_anchors(d_osm, bounds, center)
    if len(anchors) < 2:
        return None, {"error": f"锚不足 {len(anchors)}"}
    # 走廊半径：锚要素点到中心距离的 P90 + 1.5km
    adists = []
    for _, _, g in anchors:
        pts = []
        for geom in ([g] if g.geom_type in ("LineString", "Polygon") else list(g.geoms)):
            ring = geom.exterior.coords if geom.geom_type == "Polygon" else geom.coords
            pts += [(x, y) for x, y in list(ring)[::5]]
        adists += [math.dist(center, p) for p in pts]
    adists.sort()
    R = adists[int(len(adists) * 0.95)] + 1500 / 111000
    circle = cp.buffer(R)
    cand = sorted(set(int(j) for j in utree.query(circle)))
    idx = {j: k for k, j in enumerate(cand)}
    if verbose:
        print(f"锚 {[(dr, round(g.distance(cp)*111000)) for dr,_,g in anchors]} | "
              f"R={R*111000:.0f}m 候选块 {len(cand)}", flush=True)
    # 邻接 + 容量
    G = nx.Graph()
    s, t = "S", "T"
    G.add_node(s); G.add_node(t)
    # 可视性违例 → 直接连汇（∞）
    bgeoms = [g.buffer(20 / 111000) for _, _, g in anchors]
    visible = []
    for k, j in enumerate(cand):
        g = blocks[j]
        c = g.centroid
        conn = LineString([cp, c])
        viol = any(conn.intersects(bg) and not g.within(bg) for bg in bgeoms)
        if viol:
            G.add_edge(idx[j], t, cap=1e9)
        else:
            visible.append((k, j))
            G.add_edge(s, idx[j], cap=1e9)   # 可见块暂时挂源，后续被邻接边竞争
    # 块-块邻接容量
    ktree = STRtree([blocks[j] for k, j in visible])
    kidx = [k for k, j in visible]
    dmid_all = []
    epairs = []
    for a in range(len(visible)):
        ka, ja = visible[a]
        ga = blocks[ja]
        for b in range(a + 1, len(visible)):
            kb, jb = visible[b]
            gb = blocks[jb]
            inter = ga.intersection(gb)
            if inter.is_empty or inter.length < 50 / 111000:
                continue
            mid = inter.interpolate(0.5, normalized=True)
            dmid_all.append(min(g.distance(mid) for _, _, g in anchors))
            epairs.append((ka, kb, ja, jb, inter.length, mid))
    tau = statistics.median(dmid_all) if dmid_all else 1.0
    for ka, kb, ja, jb, slen, mid in epairs:
        da = min(g.distance(mid) for _, _, g in anchors)
        cap = slen * (0.05 + (da / tau) ** 2)
        G.add_edge(idx[ja], idx[jb], cap=max(cap, 0.01))
    # 走廊边缘块 → 汇（其外侧邻居不在候选集）
    for k, j in visible:
        g = blocks[j]
        for nb in utree.query(g.buffer(0.0006)):
            nb = int(nb)
            if nb not in idx:
                G.add_edge(idx[j], t, cap=1e6)
                break
    if verbose:
        print(f"图: {G.number_of_nodes()}/{G.number_of_edges()} τ={tau*111000:.0f}m", flush=True)
    cutv, (src_part, _) = nx.minimum_cut(G, s, t, capacity="cap")
    # 源侧单元（排除虚拟）
    keep = [cand[j] for j in src_part if isinstance(j, int)]
    if not keep:
        return None, {"error": "空割"}
    geom = unary_union([blocks[j] for j in keep])
    return geom, {"units": len(keep), "cut": cutv,
                  "anchors": [(dr, nm) for dr, nm, _ in anchors]}


if __name__ == "__main__":
    meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
    reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
    cons = json.load(open(f"{DATA}/contracts.json", encoding="utf-8"))
    from intelligence.coords import pack_from_disk
    pack_from_disk(reg, cons, meta)
    d_osm = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))
    blocks = load_blocks()
    utree = STRtree(blocks)
    targets = sys.argv[1:] or ["694420772", "694420772-2"]
    for aid in targets:
        c = next((x for x in cons if x.get("area_id") == aid), None)
        f = next((x for x in reg["fences"] if x["area_id"] == aid), None)
        if not c or not f:
            continue
        zg = Polygon(f["rings"][0])
        if not zg.is_valid: zg = zg.buffer(0)
        if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
        geom, info = allocate_mincut(blocks, utree, c["four_bounds"], c["center"],
                                     d_osm, verbose=True)
        if geom is None:
            print(f"{aid} 失败: {info}")
            continue
        iou = geom.intersection(zg).area / geom.union(zg).area
        print(f"{aid} {f['dealer'][:14]}: {geom.area*11320:.1f}km² vs 真值"
              f"{zg.area*11320:.1f}km² IoU={iou:.3f}", flush=True)
