#!/usr/bin/env python3
"""业代区域IR编译 —— 复用编译器内部函数"""
import sys; sys.path.insert(0,"."); sys.path.insert(0,"tools")
import json
from shapely.geometry import Polygon
from shapely import wkt, ops
from collections import defaultdict
from intelligence.coords import wgs2gcj
from territory_compile import U, sbt, spoly_by_name, adm6bt, adm6, KM2, BAND_BUF, clause_pieces, verbalize, synth, band_clause, iou_v

DATA = "data/gz"

zones = json.load(open(f"{DATA}/haizhu_liwan_zones.json"))["zones"]
rows = []
for k, zone in enumerate(zones):
    zg = Polygon(zone["ring"])
    if not zg.is_valid: zg = zg.buffer(0)
    zg_gcj = ops.transform(lambda x, y: wgs2gcj(x, y), zg)
    fa = zg_gcj.area
    T = {k2 for k2 in range(len(U))
         if U[k2][0].intersection(zg_gcj).area/max(U[k2][0].area, 1e-12) >= 0.5
         or U[k2][0].intersection(zg_gcj).area/fa >= 0.3}
    chosen = synth(zg_gcj, T)
    if chosen:
        S = set()
        for _, c in chosen: S |= clause_pieces(c)
        pu = ops.unary_union([U[k2][0] for k2 in S])
        strip = zg_gcj.difference(pu).intersection(ops.unary_union([sbt, adm6bt]).buffer(BAND_BUF))
        if strip.area * KM2 > 0.01:
            pieces = strip.geoms if strip.geom_type == "MultiPolygon" else [strip]
            for pc in pieces:
                if pc.area * KM2 < 0.01: continue
                chosen.append((f"{pc.centroid.x:.4f}界带", band_clause(zg_gcj, pc)))
        S2 = set()
        for _, c in chosen: S2 |= clause_pieces(c)
        hit = len(S2 & T); over = len(S2 - T); miss = len(T - S2)
        J = hit/(hit+over+miss) if hit+over+miss else 0
        full = ops.unary_union([U[k2][0] for k2 in S2]) if S2 else None
        cov = zg_gcj.intersection(full).area/zg_gcj.area*100 if full is not None else 0
        ii = iou_v(zg_gcj, full) if full is not None else 0
        hterms = verbalize(chosen, zg_gcj)
    else:
        J, hit, over, miss, ii, cov, hterms, chosen = 0, 0, 0, 0, 0, 0, [], []
    rows.append({"name": zone["name"], "id": zone["id"], "J": round(J, 3),
                 "hit": hit, "over": over, "miss": miss, "truth": len(T),
                 "iou": round(ii, 3), "cover": round(cov, 2),
                 "human_terms": hterms, "engine_terms": len(chosen)})
    print(f"[{k+1}/{len(zones)}] {zone['name']:10s} J={J:.2f} over={over} miss={miss} IoU={ii:.3f} 覆盖={cov:.2f}% 人话{len(hterms)}句")

json.dump(rows, open(f"{DATA}/yeidai_compiled.json", "w"), ensure_ascii=False, indent=1)
import statistics
print(f"\n=== {len(rows)}条 业代区域 ===")
print(f"J中位: {statistics.median(r['J'] for r in rows):.3f}  J=1.0: {sum(1 for r in rows if r['J']==1.0)}/{len(rows)}")
print(f"IoU中位: {statistics.median(r['iou'] for r in rows):.3f}  覆盖中位: {statistics.median(r['cover'] for r in rows):.2f}%")
print("saved yeidai_compiled.json")