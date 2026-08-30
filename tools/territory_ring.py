#!/usr/bin/env python3
"""环闭合式围栏重建（V3）：
四至锚定弧（路/河/行政界）+ 路网最短连接线 → 闭环 → 中心所在面 = 围栏。
理论：边界=路网上围绕中心的闭合回路（min-cycle 的贪心近似，锚定弧强制在场）。
"""
import json, sys, math
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import networkx as nx
import shapely
from shapely.geometry import LineString, Polygon, Point, box
from shapely.strtree import STRtree
from shapely.ops import unary_union, transform as sh_transform, polygonize
from intelligence.coords import pack_from_disk, convert

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
GRID = 0.00025  # ~25m 节点吸附
ORDER = ["北", "东", "南", "西"]


def build_road_graph(streets):
    G = nx.Graph()
    grid = {}
    def nid(p):
        k = (round(p[0] / GRID), round(p[1] / GRID))
        if k not in grid:
            grid[k] = (k[0] * GRID, k[1] * GRID)
        return grid[k]
    for seg in streets:
        c = list(seg.coords)
        for i in range(len(c) - 1):
            u, v = nid(c[i]), nid(c[i + 1])
            if u == v:
                continue
            w = math.dist(c[i], c[i + 1])
            if not G.has_edge(u, v) or w < G[u][v]["len"]:
                G.add_edge(u, v, len=w)
    return G


def arc_nodes(G, arc):
    """锚定弧附近的图节点。"""
    return [nid for nid, pos in G.nodes(data="pos") if False] or \
        [k for k, pos in ((n, G.nodes[n].get("pos")) for n in G.nodes)
         if pos and arc.distance(Point(pos)) < 30 / 111000]


def nearest_pair_nodes(G, nodes_a, nodes_b):
    best = (1e18, None, None)
    posb = {n: G.nodes[n].get("pos") for n in nodes_b}
    for na in nodes_a:
        pa = G.nodes[na].get("pos")
        nb_best = min(posb.items(), key=lambda kv: math.dist(pa, kv[1]))
        dd = math.dist(pa, nb_best[1])
        if dd < best[0]:
            best = (dd, na, nb_best[0])
    return best[1], best[2]


def main():
    meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
    reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
    pack_from_disk(reg, [], meta)
    cons = json.load(open(f"{DATA}/contracts.json", encoding="utf-8"))
    corpus = {c["area_id"]: c["four_bounds_v2"]
              for c in json.load(open(f"{DATA}/contracts_v2_corpus.json",
                                      encoding="utf-8"))}
    d = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))
    KEEP = {"motorway", "trunk", "primary", "secondary", "tertiary",
            "residential", "unclassified", "living_street", "motorway_link",
            "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
    GZ11 = ["天河区", "越秀区", "荔湾区", "海珠区", "番禺区", "白云区",
            "黄埔区", "花都区", "从化区", "增城区", "南沙区"]
    gz_poly = unary_union([shapely.from_wkt(r["wkt"]) for r in d["adm6"]
                           if r["name"] in GZ11])

    streets = []
    def clip_lines(g):
        pc = g.intersection(gz_poly)
        if pc.is_empty or pc.length < 1e-5: return None
        return [pc] if pc.geom_type == "LineString" else (
            list(pc.geoms) if pc.geom_type == "MultiLineString" else [])
    for r in d["roads"]:
        if r["cls"] not in KEEP:
            continue
        try: g = shapely.from_wkt(r["wkt"])
        except Exception: continue
        parts = ([g] if g.geom_type == "LineString"
                 else list(g.geoms) if g.geom_type == "MultiLineString" else [])
        for p in parts:
            pc = p.intersection(gz_poly)
            if not pc.is_empty and pc.length > 1e-5:
                streets += ([pc] if pc.geom_type == "LineString"
                            else list(pc.geoms) if pc.geom_type == "MultiLineString"
                            else [])
    print(f"路网段 {len(streets)}", flush=True)
    G = build_road_graph(streets)
    for n in G.nodes:
        G.nodes[n]["pos"] = n            # 网格坐标即位置
    print(f"路网图 {G.number_of_nodes()}/{G.number_of_edges()}", flush=True)

    def resolve_geom(name, center, zbox):
        target = name.split("（")[0].split("(")[0].strip().replace("边缘", "").replace("界", "")
        pieces = []
        for grp in ("roads", "rivers", "adm6", "adm8"):
            for r in d[grp]:
                nm = r.get("name", "")
                if not nm or (target not in nm and nm not in target):
                    continue
                try: g = shapely.from_wkt(r["wkt"])
                except Exception: continue
                polys = [g] if g.geom_type == "Polygon" else (
                    list(g.geoms) if g.geom_type == "MultiPolygon" else [])
                if polys:
                    pieces += [LineString(p.exterior.coords) for p in polys]
                else:
                    parts = [g] if g.geom_type == "LineString" else (
                        list(g.geoms) if g.geom_type == "MultiLineString" else [])
                    pieces += parts
        if not pieces:
            return None
        u = unary_union(pieces).intersection(zbox)   # 裁剪到围栏邻域
        parts = [u] if u.geom_type == "LineString" else (
            list(u.geoms) if u.geom_type == "MultiLineString" else [])
        parts = [p for p in parts if p.length > 1e-5]
        return unary_union(parts) if parts else None

    def arc_graph_nodes(G, arc):
        out = []
        for n, pos in G.nodes(data="pos"):
            if arc.distance(Point(pos)) < 30 / 111000:
                out.append(n)
        return out

    results = []
    for c in cons:
        aid = c.get("area_id")
        fb = corpus.get(aid)
        if not fb:
            continue
        f = [x for x in reg["fences"] if x["area_id"] == aid][0]
        zg = Polygon(f["rings"][0])
        if not zg.is_valid: zg = zg.buffer(0)
        if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
        center = list(zg.centroid.coords)[0]
        # 锚定弧
        arcs = {}
        zbox = box(zg.bounds[0]-0.02, zg.bounds[1]-0.02,
                   zg.bounds[2]+0.02, zg.bounds[3]+0.02)
        for dr in ORDER:
            nm = fb.get(dr)
            if not nm:
                continue
            g = resolve_geom(nm, center, zbox)
            if g is not None:
                arcs[dr] = g
        if len(arcs) < 2:
            print(f"{aid} {f['dealer'][:14]}: 锚不足({len(arcs)}) 跳过", flush=True)
            continue
        # 环：锚弧全量 + 弧间路网最短连接
        drs = [dr for dr in ORDER if dr in arcs]
        ring_lines = list(arcs.values())
        okconn = True
        for i in range(len(drs)):
            A, B = arcs[drs[i]], arcs[drs[(i + 1) % len(drs)]]
            na = arc_graph_nodes(G, A)
            nb = arc_graph_nodes(G, B)
            if not na or not nb:
                okconn = False; break
            sa, sb = nearest_pair_nodes(G, na, nb)
            try:
                path = nx.shortest_path(G, sa, sb, weight="len")
            except nx.NetworkXNoPath:
                okconn = False; break
            pts = [G.nodes[n].get("pos") for n in path]
            if len(pts) >= 2:
                ring_lines.append(LineString(pts))
        if not okconn:
            print(f"{aid} 连接失败"); continue
        ring_u = unary_union(ring_lines)
        ring_faces = list(polygonize(ring_u))
        if not ring_faces:
            print(f"{aid} 无面"); continue
        terr = unary_union(ring_faces)
        # 中心所在分量优先（多面时）
        if terr.geom_type == "MultiPolygon":
            terr = max((g for g in terr.geoms if g.contains(Point(center))),
                       key=lambda g: g.area, default=max(terr.geoms, key=lambda g: g.area))
        iou = terr.intersection(zg).area / terr.union(zg).area
        results.append((iou, f["dealer"], aid, terr))
        print(f"{aid} {f['dealer'][:14]}: 环面积{terr.area*11320:.1f}km² "
              f"真值{zg.area*11320:.1f}km² IoU={iou:.3f}", flush=True)

    if results:
        ious = sorted(r[0] for r in results)
        print(f"\n中位 IoU={ious[len(ious)//2]:.3f} "
              f"≥0.9: {sum(1 for r in ious if r>=0.9)}/{len(ious)}")
        json.dump({"results": [(r[1], r[2], round(r[0],3)) for r in results]},
                  open("/tmp/v3_ring_results.json", "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
