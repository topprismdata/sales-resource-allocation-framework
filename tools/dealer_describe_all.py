#!/usr/bin/env python3
"""全部经销商描述生成（METHOD.md v1.0 管线）"""
import sys
import _paths
sys.path.insert(0, str(_paths.ROOT))
import json
from shapely.geometry import Polygon
from shapely import wkt, ops
from shapely.strtree import STRtree
from intelligence.coords import gcj2wgs
from collections import Counter, defaultdict

DATA = _paths.DATA
KM2 = 12364.0

d = json.load(open(_paths.SOURCE / "边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson"))
parents = []; pstreet = []; pdistrict = []
for f in d["features"]:
    g = f["geometry"]
    if g["type"] != "Polygon": continue
    parents.append(Polygon(g["coordinates"][0], g["coordinates"][1:]))
    pr = f["properties"]
    pstreet.append(pr.get("街道[内置]", ""))
    pdistrict.append(pr.get("区[内置]") or pr.get("区县编码", ""))
pt = STRtree(parents)

sd = json.load(open(_paths.SOURCE / "区划数据-街道-广东省-广州市.geojson"))
spoly = []; sname = []
for f in sd["features"]:
    g = f["geometry"]
    try:
        if g["type"] == "Polygon": p = Polygon(g["coordinates"][0], g["coordinates"][1:])
        elif g["type"] == "MultiPolygon": p = ops.unary_union([Polygon(c[0], c[1:]) for c in g["coordinates"]])
        else: continue
    except Exception:
        continue
    if p.is_empty: continue
    if not p.is_valid: p = p.buffer(0)
    spoly.append(p)
    pr = f["properties"]
    sname.append(pr.get("街道[内置]") or pr.get("街道") or pr.get("name") or "")
sbt = ops.unary_union([p.boundary for p in spoly])

reg = json.load(open(f"{DATA}/region.json"))
osm = json.load(open(f"{DATA}/gz_osm_full.json"))
named = []
for r in osm["roads"]:
    if not r.get("name") or r["cls"] in ("footway","steps","path","cycleway","construction","proposed"): continue
    try: g = wkt.loads(r["wkt"])
    except Exception: continue
    parts = [g] if g.geom_type == "LineString" else (list(g.geoms) if g.geom_type == "MultiLineString" else [])
    for p in parts:
        if p.length > 1e-5: named.append((r["name"], p))
nrt = STRtree([p for _, p in named])
adm6 = []
for rr in osm["adm6"]:
    try: adm6.append((rr.get("name",""), wkt.loads(rr["wkt"]).boundary))
    except Exception: pass
adm6bt = ops.unary_union([b for _, b in adm6])

print(f"数据: 地块{len(parents)} 街道面{len(spoly)} 路{len(named)}")

def roads_of(u):
    gw = ops.transform(lambda x, y: gcj2wgs(x, y), u)
    r = {named[j][0] for j in nrt.query(gw.buffer(60/111000))}
    if not r:
        r = {named[j][0] for j in nrt.query(gw.buffer(200/111000))}
    return r

def iou_v(a, b):
    i = a.intersection(b).area; s = a.area + b.area - i
    return i/s if s else 0

def direction(geom, fence):
    dx = geom.centroid.x - fence.centroid.x
    dy = geom.centroid.y - fence.centroid.y
    if abs(dx) > abs(dy): return "西" if dx < 0 else "东"
    return "南" if dy < 0 else "北"

def boundary_name(strip):
    c = strip.centroid
    best6 = None
    for n, b in adm6:
        dd = b.distance(c) * 111000
        if best6 is None or dd < best6[1]: best6 = (n, dd)
    if best6 and best6[1] < 300:
        return f"{best6[0]}界"
    best = None
    for j in range(len(spoly)):
        dd = spoly[j].boundary.distance(c) * 111000
        if best is None or dd < best[1]: best = (j, dd)
    j = best[0]
    cands = sorted(((sname[j2], spoly[j2].boundary.distance(c)*111000) for j2 in range(len(spoly)) if j2 != j), key=lambda t: t[1])
    return f"{sname[j]}—{cands[0][0] if cands else '?'}界"

def process(fence):
    zg = Polygon(fence["rings"][0])
    if not zg.is_valid: zg = zg.buffer(0)
    if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
    sel = {i for i in pt.query(zg) if parents[i].intersection(zg).area/max(parents[i].area,1e-12) >= 0.5}
    fallback = False
    if not sel:
        sel = {i for i in pt.query(zg) if parents[i].intersection(zg).area > 1e-9}
        fallback = True
    if not sel: return None
    by_street_all = defaultdict(set)
    for i, s in enumerate(pstreet):
        if s: by_street_all[s].add(i)
    groups = defaultdict(list)
    for i in sel: groups[pstreet[i]].append(i)
    pby_road = {i: roads_of(parents[i]) for i in sel}
    terms = []
    for stn, ids in sorted(groups.items(), key=lambda x: -len(x[1])):
        tot = len(by_street_all.get(stn, ()))
        if len(ids) == tot:
            terms.append(stn); continue
        in_cnt = Counter()
        for i in ids: in_cnt.update(pby_road[i])
        all_cnt = Counter()
        for i in by_street_all.get(stn, ()): all_cnt.update(pby_road.get(i, set()))
        cand = sorted(in_cnt.items(), key=lambda kv: (all_cnt.get(kv[0], 0)-kv[1], -kv[1]))
        covered = set()
        for rd, c in cand:
            if c == 0: continue
            terms.append(f"{stn}沿{rd}")
            covered |= {i for i in ids if rd in pby_road[i]}
            if covered >= set(ids): break
        if set(ids) - covered:
            terms.append(stn)  # 郊区路不可达残地块: 用镇名(整镇语义)
    punion = ops.unary_union([parents[i] for i in sel])
    strip = zg.difference(punion).intersection(ops.unary_union([sbt, adm6bt]).buffer(150/111000))
    if strip.area * KM2 > 0.01:
        pieces = strip.geoms if strip.geom_type == "MultiPolygon" else [strip]
        for pc in pieces:
            if pc.area * KM2 < 0.01: continue
            terms.append(f"{direction(pc, zg)}至{boundary_name(pc)}")
    proj = set()
    for t in terms:
        if "沿" in t:
            a, b = t.split("沿", 1)
            proj |= {i for i in sel if pstreet[i] == a and b in pby_road[i]}
        elif "至" in t:
            continue
        else:
            proj |= by_street_all.get(t, set())
    hit = len(proj & sel); over = len(proj - sel); miss = len(sel - proj)
    J = hit/(hit+over+miss) if hit+over+miss else 0
    full = punion.union(strip)
    i2 = zg.intersection(full).area; s0 = zg.area + full.area - i2
    dist = Counter(pdistrict[i] for i in sel)
    return {"terms": terms, "J": round(J, 3), "units": f"{hit}/{len(sel)}",
            "over": over, "miss": miss, "iou": round(iou_v(zg, full), 3),
            "cover": round(zg.intersection(full).area/zg.area*100, 2),
            "fallback": fallback, "districts": dict(dist)}

rows = []
fences = [f for f in reg["fences"] if "佛山" not in f["dealer"]]
for k, f in enumerate(fences):
    try:
        r = process(f)
        if r is None: r = {"terms": [], "J": 0, "units": "0/0", "over": 0, "miss": 0, "iou": 0, "cover": 0}
    except Exception as e:
        r = {"terms": [f"ERROR {type(e).__name__}: {e}"], "J": 0, "units": "?", "over": -1, "miss": -1, "iou": 0, "cover": 0}
    r["dealer"] = f["dealer"]; r["area_id"] = f["area_id"]; r["km2"] = f["area_km2"]
    rows.append(r)
    print(f"[{k+1}/{len(fences)}] {f['dealer'][:16]:<16} {len(r['terms'])}词 J={r['J']:.2f} IoU={r['iou']:.3f} 覆盖={r['cover']}%")

json.dump(rows, open(f"{DATA}/all_dealer_descriptions.json", "w"), ensure_ascii=False, indent=1)
import statistics
js = [r["J"] for r in rows]; ious = [r["iou"] for r in rows]; covs = [r["cover"] for r in rows]
print(f"\n=== {len(rows)}条围栏 ===")
print(f"地块J: 中位{statistics.median(js):.3f}  J=1.0: {sum(1 for j in js if j==1.0)}/{len(rows)}")
print(f"围栏IoU: 中位{statistics.median(ious):.3f}  覆盖中位: {statistics.median(covs):.2f}%")
print("saved all_dealer_descriptions.json")
