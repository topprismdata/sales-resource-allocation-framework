#!/usr/bin/env python3
"""分量式边界 map-matching v6（纯几何，无门店/无合同文本）。

1. 导引多边形自适应腐蚀扫描：取使分量数≥2 的最小腐蚀量 ε（天然脖颈），
   膨胀回交原 → 连通分量分解
2. 每分量独立匹配：走廊 r99（分量边界采样到最近候选线距离 99 分位）→
   候选段 → τ（候选段中点到分量边界距离中位）→ 边权=长度×(1+(d/τ)²) →
   直径端点最短路 → 环
3. 分量并集 vs 真值 IoU
"""
import json, sys, math, statistics
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import networkx as nx
import shapely
from shapely.geometry import LineString, Polygon, box
from shapely.strtree import STRtree
from shapely.ops import unary_union

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
DEALER = "亨啡源"

sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework/tools")
import boundary_matcher as bm

meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
from intelligence.coords import pack_from_disk
pack_from_disk(reg, [], meta)

vis = json.load(open(f"{DATA}/p1_visual.json"))
case = [c for c in vis["cases"] if DEALER in c["dealer"]][0]
guide = case["v1c"] + [case["v1c"][0]]
gpoly = Polygon(guide)
if not gpoly.is_valid:
    gpoly = gpoly.buffer(0)

# 1) 自适应腐蚀扫描找最小分裂点
peri = gpoly.exterior.length
print(f"导引: {gpoly.area*11320:.1f}km² 周长{peri*111:.0f}km", flush=True)
split_eps = None
for frac in (0.0005, 0.001, 0.0015, 0.002, 0.003, 0.004, 0.006, 0.008, 0.012):
    eps = peri * frac
    er = gpoly.buffer(-eps)
    if er.is_empty:
        break
    ncomp = len(er.geoms) if er.geom_type == "MultiPolygon" else 1
    print(f"  ε={eps*111000:.0f}m → {ncomp} 分量", flush=True)
    if ncomp >= 2:
        split_eps = eps
        break
if split_eps is None:
    comps = [gpoly]
    print("  无分裂点，单分量")
else:
    er = gpoly.buffer(-split_eps)
    parts = sorted(list(er.geoms), key=lambda g: -g.area)
    comps = [p.buffer(split_eps) for p in parts[:3]]
    comps = [c for c in comps if c.area > 2/11320]

# 2) 每分量匹配
segs, prior = bm.load_segments()
tree = STRtree(segs)
matched = []
for ci, comp in enumerate(comps):
    if comp.geom_type != "Polygon":
        comp = max(comp.geoms, key=lambda g: g.area)
    loop = comp.exterior
    M = max(30, int(loop.length / 0.002))
    spts = [loop.interpolate(i/M) for i in range(M)]
    d1 = [float(tree.query_nearest(p, return_distance=True)[1][0]) for p in spts]
    r99 = sorted(d1)[int(len(d1)*0.99)]
    idxs = tree.query(loop.buffer(r99))
    cand = [segs[i] for i in idxs]
    dmid = [c.interpolate(0.5).distance(loop) for c in cand]
    tau = statistics.median(dmid)
    print(f"分量{ci+1}: {comp.area*11320:.1f}km² r99={r99*111000:.0f}m "
          f"候选{len(cand)} τ={tau*111000:.0f}m", flush=True)
    G = nx.Graph(); grid = {}; id2k = {}
    def nid(p):
        k = (round(p.x/0.00025), round(p.y/0.00025))
        if k not in grid:
            grid[k] = len(grid); id2k[len(grid)-1] = k
        return grid[k]
    geo = {}
    for c in cand:
        u = nid(shapely.points(c.coords[0])); v = nid(shapely.points(c.coords[-1]))
        if u == v:
            continue
        dd = c.interpolate(0.5).distance(loop)
        w = c.length * (1 + (dd/tau)**2)
        if not G.has_edge(u, v) or w < G[u][v]["w"]:
            G.add_edge(u, v, w=w); geo[(u, v)] = c; geo[(v, u)] = c
    if G.number_of_edges() == 0:
        continue
    def nn(pt):
        return min(G.nodes, key=lambda nd: math.dist(id2k[nd], (pt.x, pt.y)))
    sub = spts[::max(1, M//40)]
    far, fp = 0, (sub[0], sub[1])
    for a_i in range(len(sub)):
        for b_i in range(a_i+1, len(sub)):
            dd = sub[a_i].distance(sub[b_i])
            if dd > far:
                far, fp = dd, (sub[a_i], sub[b_i])
    s_node, e_node = nn(fp[0]), nn(fp[1])
    try:
        path = nx.shortest_path(G, s_node, e_node, weight="w")
    except nx.NetworkXNoPath:
        print("  无路径"); continue
    lines = [geo[(a, b)] for a, b in zip(path[:-1], path[1:]) if (a, b) in geo]
    if not lines:
        continue
    merged = shapely.ops.linemerge(lines)
    if merged.geom_type == "LineString":
        ring = list(merged.coords)
    else:
        ring = list(max(merged.geoms, key=lambda l: l.length).coords)
    if len(ring) < 4:
        continue
    if ring[0] != ring[-1]:
        ring = ring + [ring[0]]
    p = Polygon(ring)
    if not p.is_valid:
        p = p.buffer(0)
    if p.geom_type == "MultiPolygon":
        p = max(p.geoms, key=lambda g: g.area)
    matched.append(p)
    print(f"  → {p.area*11320:.1f}km²", flush=True)

if matched:
    recon = unary_union(matched)
    full = unary_union([
        (lambda p: p if p.is_valid else p.buffer(0))(Polygon(f["rings"][0]))
        for f in reg["fences"] if DEALER in f["dealer"]])
    iou = full.intersection(recon).area / full.union(recon).area
    print(f"\n联合重建 {recon.area*11320:.1f}km² vs 真值 {full.area*11320:.1f}km²  IoU={iou:.3f}")
    def to_ring(g):
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda x: x.area)
        return [[round(x, 6), round(y, 6)] for x, y in g.exterior.coords]
    json.dump({"rings": [to_ring(m) for m in matched], "iou": round(iou, 3)},
              open(f"{DATA}/match_result.json", "w"), ensure_ascii=False)
    print("saved")
