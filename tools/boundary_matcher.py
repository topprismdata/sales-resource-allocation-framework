#!/usr/bin/env python3
"""边界 map-matching（Newson-Krumm HMM 对偶）v2。

导引线采样点 → 候选线网吸附（发射：高斯距离+类型先验）→
相邻采样间图上最短路（转移：|路网距离−导引距离|指数）→ Viterbi → 闭环。
"""
import json, sys, math
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import networkx as nx
import shapely
from shapely.geometry import LineString, Polygon
from shapely.strtree import STRtree

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
SIGMA = 120.0 / 111000
BETA = 200.0 / 111000
STEP = 200.0 / 111000
MAX_SNAP = 400.0 / 111000
K = 5
CORRIDOR = 400.0 / 111000
GRID = 0.00025  # ~25m

CLASS_PENALTY = {
    "motorway": 0.0, "trunk": 0.0, "primary": 0.0, "secondary": 0.0,
    "tertiary": 0.0, "residential": 0.0, "unclassified": 0.0,
    "living_street": -0.5, "service": -1.0, "motorway_link": -0.5,
    "trunk_link": -0.5, "primary_link": -0.5, "secondary_link": -0.5,
    "tertiary_link": -0.5, "road": -1.0, "busway": -1.0,
    "footway": -2.5, "path": -2.5, "steps": -3.0, "pedestrian": -2.5,
    "track": -2.0, "cycleway": -2.5, "bridleway": -2.5,
    "construction": -8.0, "proposed": -8.0, "planned": -8.0,
}
SKIP = {"elevator", "corridor", "raceway", "bus_stop", "platform",
        "rest_area", "bus_guideway"}


def load_segments():
    d = json.load(open(f"{DATA}/gz_osm_full.json"))
    segs, prior = [], []
    def add(wkt, pen):
        g = shapely.from_wkt(wkt)
        parts = [g] if g.geom_type == "LineString" else (
            list(g.geoms) if g.geom_type == "MultiLineString" else [])
        for line in parts:
            if line.is_empty or line.length < 1e-6:
                continue
            n = max(1, int(line.length / 0.0025))
            for i in range(n):
                a = line.interpolate(i / n)
                b = line.interpolate(min(1.0, (i + 1) / n))
                segs.append(LineString([a, b]))
                prior.append(pen)
    for r in d["roads"]:
        pen = CLASS_PENALTY.get(r["cls"])
        if pen is None:
            if r["cls"] in SKIP or r["cls"] not in CLASS_PENALTY:
                continue
            pen = -1.0
        add(r["wkt"], pen)
    for r in d["rivers"]:
        add(r["wkt"], -0.5)
    for lvl, pen in (("adm8", 0.5), ("adm6", 0.3)):
        for r in d[lvl]:
            add(r["wkt"], pen)
    return segs, prior


def build_graph(segs, prior, tree, corridor):
    G = nx.Graph()
    kept = []
    grid = {}
    def nid(pt):
        key = (round(pt.x / GRID), round(pt.y / GRID))
        if key not in grid:
            grid[key] = len(grid)
        return grid[key], key
    for idx in tree.query(corridor):
        s = segs[idx]
        u_id, u_key = nid(s.coords[0] and shapely.points(s.coords[0]))
        v_id, v_key = nid(shapely.points(s.coords[-1]))
        if u_id == v_id:
            continue
        w = s.length * (1.0 - 0.05 * prior[idx])
        if G.has_edge(u_id, v_id):
            if w < G[u_id][v_id]["len"]:
                G[u_id][v_id].update(len=w, seg=s, pri=prior[idx])
        else:
            G.add_edge(u_id, v_id, len=w, seg=s, pri=prior[idx])
        kept.append(idx)
    keys = {v: k for k, v in grid.items()}
    return G, kept, keys


def endpoint_keys(seg):
    c0, c1 = seg.coords[0], seg.coords[-1]
    k = lambda p: (round(p[0] / GRID), round(p[1] / GRID))
    return k(c0), k(c1)


def main():
    dealer_key = sys.argv[1] if len(sys.argv) > 1 else "亨啡源"
    truth_wkt = sys.argv[2] if len(sys.argv) > 2 else None
    segs, prior = load_segments()
    tree = STRtree(segs)
    print(f"候选段 {len(segs)}", flush=True)

    vis = json.load(open(f"{DATA}/p1_visual.json"))
    case = [c for c in vis["cases"] if dealer_key in c["dealer"]][0]
    guide = case["v1c"] + [case["v1c"][0]]
    gls = LineString(guide)
    M = max(20, int(gls.length / STEP))
    samples = [gls.interpolate((i + 0.5) / M) for i in range(M)]
    print(f"导引采样 {M}", flush=True)

    G, kept, keys = build_graph(segs, prior, tree, gls.buffer(CORRIDOR))
    print(f"图 {G.number_of_nodes()}节点/{G.number_of_edges()}边", flush=True)
    kseg = [segs[i] for i in kept]
    kpri = [prior[i] for i in kept]
    ktree = STRtree(kseg)

    def key_to_id(key):
        return None  # keys dict 由 build_graph 填充（闭包内延迟）

    states = []
    for pt in samples:
        cands = []
        for j in ktree.query(pt.buffer(MAX_SNAP)):
            seg = kseg[j]
            dd = seg.distance(pt)
            if dd <= MAX_SNAP:
                cands.append((dd, j))
        cands.sort()
        st = []
        for dd, j in cands[:K]:
            seg = kseg[j]
            proj = seg.interpolate(seg.project(pt))
            uk, vk = endpoint_keys(seg)
            st.append({"j": j, "d": dd, "proj": proj,
                       "u": uk, "v": vk,
                       "e": emission(dd, kpri[j])})
        if not st:
            st = [{"j": None, "d": MAX_SNAP, "proj": pt, "u": None, "v": None,
                   "e": emission(MAX_SNAP, -3.0)}]
        states.append(st)

    def trans_cost(a, b, guide_d):
        if a["j"] is None or b["j"] is None:
            straight = a["proj"].distance(b["proj"])
            return abs(straight - guide_d) / BETA + 8.0, None
        best = (1e18, None)
        for (u, v) in ((a["u"], b["u"]), (a["u"], b["v"]),
                       (a["v"], b["u"]), (a["v"], b["v"])):
            uid = keys.get(u); vid = keys.get(v)
            if uid is None or vid is None:
                continue
            if uid == vid:
                nd, path = 0.0, [uid]
            else:
                try:
                    path = nx.shortest_path(G, uid, vid, weight="len")
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    continue
                nd = sum(G[path[k]][path[k+1]]["len"]
                         for k in range(len(path)-1))
            cost = abs(nd - guide_d) / BETA
            if cost < best[0]:
                best = (cost, path)
        if best[1] is None:
            straight = a["proj"].distance(b["proj"])
            return abs(straight - guide_d) / BETA + 8.0, None
        return best[0], best[1]

    INF = 1e18
    V = [dict() for _ in range(M)]
    BK = [dict() for _ in range(M)]
    for si, st in enumerate(states[0]):
        V[0][si] = st["e"]
    for i in range(1, M):
        gd = samples[i].distance(samples[i-1])
        for bi, bs in enumerate(states[i]):
            bestc, bestp = INF, None
            for ai, asx in enumerate(states[i-1]):
                if V[i-1].get(ai, INF) >= INF:
                    continue
                c, _ = trans_cost(asx, bs, gd)
                tot = c + V[i-1][ai]
                if tot < bestc:
                    bestc, bestp = tot, ai
            V[i][bi] = bestc + bs["e"]
            BK[i][bi] = bestp
    last = max(V[M-1], key=lambda k: V[M-1][k])
    seq = [last]
    for i in range(M-1, 0, -1):
        seq.append(BK[i][seq[-1]])
    seq.reverse()
    pts = [states[i][seq[i]]["proj"] for i in range(M)]
    loop = LineString(pts + [pts[0]])
    poly = Polygon(loop.coords)
    if not poly.is_valid:
        poly = poly.buffer(0)
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)
    print(f"重建面积 {poly.area*11320:.1f} km²")

    out = {"ring": [[round(x, 6), round(y, 6)] for x, y in poly.exterior.coords]}
    if truth_wkt:
        tp = shapely.from_wkt(truth_wkt)
        iou = poly.intersection(tp).area / poly.union(tp).area
        print(f"IoU = {iou:.3f}")
        out["iou"] = round(iou, 3)
    json.dump(out, open(f"{DATA}/match_result.json", "w"), ensure_ascii=False)
    print("saved", f"{DATA}/match_result.json")


def emission(d, pen):
    return -(d / SIGMA) ** 2 / 2 + pen


if __name__ == "__main__":
    main()
