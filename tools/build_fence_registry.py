#!/usr/bin/env python3
"""围栏指纹注册表：每围栏的区/街道归属、贴边路名、邻接围栏、中心、面积。"""
import json, sys, math
import _paths
sys.path.insert(0, str(_paths.ROOT))
import shapely
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
from shapely.ops import unary_union
from intelligence.coords import pack_from_disk

DATA = _paths.DATA
meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
pack_from_disk(reg, [], meta)
d = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))

# 行政区/街道多边形
GZ11 = ["天河区", "越秀区", "荔湾区", "海珠区", "番禺区", "白云区",
        "黄埔区", "花都区", "从化区", "增城区", "南沙区"]
dist_polys = {}
street_polys = {}
for r in d["adm6"]:
    if r["name"] in GZ11:
        g = shapely.from_wkt(r["wkt"])
        parts = [g] if g.geom_type == "Polygon" else list(g.geoms)
        dist_polys[r["name"]] = unary_union(parts)
for r in d["adm8"]:
    if r["name"] not in GZ11 and not any(s.startswith(r["name"][:2]) for s in
            [x for x in GZ11]):
        pass
    try: g = shapely.from_wkt(r["wkt"])
    except Exception: continue
    parts = [g] if g.geom_type == "Polygon" else list(g.geoms)
    for p in parts:
        for dn, dp in dist_polys.items():
            if p.intersects(dp) and p.intersection(dp).area > 0.3 * p.area:
                street_polys.setdefault((dn, r["name"]), unary_union(
                    [street_polys.get((dn, r["name"]), Polygon()), p]))
                break

stree = STRtree(list(street_polys.values()))
skeys = list(street_polys.keys())
dtree = STRtree(list(dist_polys.values()))
dkeys = list(dist_polys.keys())

corpus = {c["area_id"]: c["four_bounds_v2"]
          for c in json.load(open(f"{DATA}/contracts_v2_corpus.json",
                                  encoding="utf-8"))}

# 邻接围栏（共享边界>200m）
fences = [(f["area_id"], f["dealer"],
           (lambda p: p if p.is_valid else p.buffer(0))(Polygon(f["rings"][0])))
          for f in reg["fences"] if "佛山" not in f["dealer"]]
ftree = STRtree([f[2] for f in fences])

registry = []
for aid, dealer, zg in fences:
    dists = {}
    streets_hit = set()
    c = zg.centroid
    for i, (dn, dp) in enumerate(zip(dkeys, list(dist_polys.values()))):
        if dp.intersects(zg):
            inter = dp.intersection(zg).area
            if inter > 0.02 * dp.area or inter > 0.5 * zg.area:
                dists[dn] = inter
    # 街道：与围栏相交显著的街道面
    for (dn, sn), sp in street_polys.items():
        if sp.intersects(zg):
            inter = sp.intersection(zg).area
            if inter > 0.1 * sp.area:
                streets_hit.add(f"{dn}·{sn}")
    # 邻接围栏
    nbrs = sorted(set(o[1] for o in fences
                      if o[0] != aid and o[2].intersection(zg).length > 200/111000))
    fb = corpus.get(aid, {})
    registry.append({
        "area_id": aid, "dealer": dealer,
        "districts": sorted(dists, key=lambda x: -dists[x]),
        "streets": sorted(streets_hit),
        "boundary_roads": [v for v in fb.values()],
        "bounds": fb,
        "area_km2": round(zg.area * 11320 * 1.0084, 1),
        "center": [round(c.x, 5), round(c.y, 5)],
        "neighbors": nbrs[:6],
        "profile": (f"{'/'.join(sorted(dists))} "
                    f"{'、'.join(sorted(streets_hit))} "
                    f"边界:{'/'.join(fb.values())} "
                    f"邻:{'/'.join(nbrs[:4])} "
                    f"面积{zg.area*11320:.0f}km²")})

json.dump({"crs": "WGS84", "registry": registry},
          open(f"{DATA}/fence_registry.json", "w"), ensure_ascii=False)
print(f"注册表: {len(registry)} 条")
for r in registry[:3]:
    print(" ", r["area_id"], r["districts"], r["streets"], r["profile"][:80])
