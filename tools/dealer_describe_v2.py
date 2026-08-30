#!/usr/bin/env python3
"""经销商描述生成 v2 —— 本体：统一铺盖U(地块x街道面切割) + 剩余带R
四类词：块词 / 片词 / 路词 / 界带词，解析全部与围栏无关。
评估双口径：地块级J + 几何IoU。
"""
import sys; sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import json
from shapely.geometry import Polygon
from shapely import wkt, ops
from shapely.strtree import STRtree
from intelligence.coords import gcj2wgs
from collections import Counter, defaultdict

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
KM2 = 12364.0
ROAD_BUF = 100 / 111000   # 语言常量：路词缓冲100m，固化

# ---------- 数据 ----------
d = json.load(open('/Users/ghb/Downloads/边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson'))
parents = []; pstreet = []
for f in d["features"]:
    g = f["geometry"]
    if g["type"] != "Polygon": continue
    parents.append(Polygon(g["coordinates"][0], g["coordinates"][1:]))
    pstreet.append(f["properties"].get("街道[内置]", ""))

sd = json.load(open('/Users/ghb/Downloads/区划数据-街道-广东省-广州市.geojson'))
spoly = []; sname = []
for f in sd["features"]:
    g = f["geometry"]
    try:
        if g["type"] == "Polygon": p = Polygon(g["coordinates"][0], g["coordinates"][1:])
        elif g["type"] == "MultiPolygon": p = ops.unary_union([Polygon(c[0], c[1:]) for c in g["coordinates"]])
        else: continue
    except Exception: continue
    if p.is_empty: continue
    if not p.is_valid: p = p.buffer(0)
    spoly.append(p)
    pr = f["properties"]
    sname.append(pr.get("街道[内置]") or pr.get("街道") or pr.get("name") or "")
sst = STRtree(spoly)

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
print(f"数据: 父地块{len(parents)} 街道面{len(spoly)} 路{len(named)}")

# ---------- 统一铺盖 U：地块按街道面切割，片带(B街,A街,父id) ----------
U = []  # (geom, bstreet, astreet, parent_id)
split_cnt = 0
for pi, u in enumerate(parents):
    cand = [int(j) for j in sst.query(u)]
    hits = []
    for j in cand:
        if not spoly[j].intersects(u): continue
        inter = spoly[j].intersection(u)
        if inter.is_empty or inter.area < 1e-12: continue
        if not inter.is_valid: inter = inter.buffer(0)
        hits.append((j, inter))
    if len(hits) <= 1:
        a = sname[hits[0][0]] if hits else ""
        if hits and u.geom_type == "Polygon":
            U.append((u, pstreet[pi], a, pi))
        elif u.geom_type == "Polygon":
            U.append((u, pstreet[pi], "", pi))
        continue
    split_cnt += 1
    for j, part in hits:
        if part.geom_type == "Polygon":
            U.append((part, pstreet[pi], sname[j], pi))
        elif part.geom_type == "MultiPolygon":
            for g2 in part.geoms:
                U.append((g2, pstreet[pi], sname[j], pi))
for k, (g, b, a, p) in enumerate(U):
    if not g.is_valid: U[k] = (g.buffer(0), b, a, p)
Ut = STRtree([x[0] for x in U])
print(f"统一铺盖U: {len(U)}片 (切割{split_cnt}个跨界地块)")

# 校验A铺盖完整性(抽样): 街道面相互重叠量
ov = 0.0
for i in range(min(len(spoly), 30)):
    for j in range(i+1, min(len(spoly), 30)):
        if spoly[i].intersects(spoly[j]):
            ov += spoly[i].intersection(spoly[j]).area
print(f"A铺盖校验(前30面两两重叠): {ov*KM2:.1f}km²")

# ---------- 剩余带 R: 每个A街面 − 落在其内的所有U片 ----------
residual = {}  # astreet → geom
for j in range(len(spoly)):
    inside = [x[0] for x in U if x[2] == sname[j]]
    if not inside: continue
    r = spoly[j].difference(ops.unary_union(inside))
    if not r.is_empty and r.area * KM2 > 0.005:
        residual[sname[j]] = r
print(f"剩余带R: {len(residual)}个街道有剩余带")

# ---------- 路属性 ----------
_rd = {}
def unit_roads(g):
    key = id(g)
    if key not in _rd:
        gw = ops.transform(lambda x, y: gcj2wgs(x, y), g)
        _rd[key] = {named[j][0] for j in nrt.query(gw.buffer(ROAD_BUF))}
    return _rd[key]

# ---------- 解析器（与围栏无关） ----------
def resolve_block(stn):      # 块词
    return [k for k, x in enumerate(U) if x[1] == stn]
def resolve_slice(stn, ast): # 片词
    return [k for k, x in enumerate(U) if x[1] == stn and x[2] == ast]
def resolve_road(stn, rd):   # 路词
    return [k for k, x in enumerate(U) if x[1] == stn and rd in unit_roads(x[0])]
def resolve_band(ast):       # 界带词
    return residual.get(ast)

def parse_term(t):
    """返回 (类型, 解析的U片列表, 解析的额外几何)"""
    if "(" in t and "限" in t:
        stn = t.split("(")[0]; ast = t.split("限")[1].rstrip("内）)")
        return ("片", resolve_slice(stn, ast), None)
    if "沿" in t:
        a, b = t.split("沿", 1)
        return ("路", resolve_road(a, b), None)
    if "界带" in t:
        ast = t.replace("界带", "")
        return ("带", [], residual.get(ast))
    return ("块", resolve_block(t), None)

# ---------- 生成 ----------
def gen_terms(zg, T):
    """T: 真值片集合(片id)。返回 (terms, chosen_geoms)"""
    terms = []
    geoms = []
    # 按B街分组
    byb = defaultdict(list)
    for c in T: byb[U[c][1]].append(c)
    used_slice = set()
    for stn in sorted(byb, key=lambda s: -len(byb[s])):
        ids = byb[stn]
        allp = resolve_block(stn)
        if set(ids) >= set(allp):
            terms.append(stn)
            geoms.extend(allp)
            used_slice.update(allp)
            continue
        # 部分: 按A街再分组
        bya = defaultdict(list)
        for c in ids: bya[U[c][2]].append(c)
        covered = set()
        for ast, ids2 in sorted(bya.items(), key=lambda x: -len(x[1])):
            allslice = resolve_slice(stn, ast)
            if set(ids2) >= set(allslice) and len(allslice) > 0:
                terms.append(f"{stn}(限{ast}内)")
                geoms.extend(allslice); covered.update(allslice); used_slice.update(allslice)
                continue
            # 路词
            in_cnt = Counter()
            for c in ids2: in_cnt.update(unit_roads(U[c][0]))
            cand = sorted(in_cnt.items(), key=lambda kv: -kv[1])
            cov2 = set()
            for rd, cnt in cand:
                rp = resolve_road(stn, rd)
                rp_in = [k for k in rp if k in set(ids2)]
                if not rp_in: continue
                out = [k for k in rp if k not in T]
                terms.append(f"{stn}沿{rd}")
                geoms.extend(rp); cov2.update(rp_in); covered.update(rp_in); used_slice.update(rp)
                if set(ids2) - cov2 <= set(): break
            # 残余片无路: 片词兜底
            for c in ids2:
                if c not in covered:
                    terms.append(f"{stn}(限{ast}内)")
                    geoms.extend(allslice); used_slice.update(allslice)
                    break
    # 界带: 围栏 − 片并集 的部分若落在R中
    punion = ops.unary_union([x[0] for x in U]) if U else None
    if punion is not None:
        gap = zg.difference(punion)
        if gap.area * KM2 > 0.005:
            pieces = gap.geoms if gap.geom_type == "MultiPolygon" else [gap]
            for g in pieces:
                c = g.centroid
                for ast, rg in residual.items():
                    if rg.contains(c) or rg.intersects(g) and rg.intersection(g).area > g.area * 0.5:
                        terms.append(f"{ast}界带")
                        geoms.append(rg)
                        break
    return terms, geoms

def iou_v(a, b):
    i = a.intersection(b).area; s = a.area + b.area - i
    return i/s if s else 0

def process(fence):
    zg = Polygon(fence["rings"][0])
    if not zg.is_valid: zg = zg.buffer(0)
    if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
    # 真值: 片≥50%在围栏内
    T = {k for k in range(len(U)) if U[k][0].intersection(zg).area/max(U[k][0].area,1e-12) >= 0.5}
    terms, geoms = gen_terms(zg, T)
    # 验证
    chosen_pieces = [k for k in geoms if isinstance(k, int)]
    chosen_extra = [g for g in geoms if not isinstance(g, int)]
    hit = len(set(chosen_pieces) & T); over = len(set(chosen_pieces) - T); miss = len(T - set(chosen_pieces))
    J = hit/(hit+over+miss) if hit+over+miss else 0
    full = ops.unary_union([U[k][0] for k in set(chosen_pieces)] + chosen_extra) if (chosen_pieces or chosen_extra) else None
    cov = zg.intersection(full).area/zg.area*100 if full is not None else 0
    ii = iou_v(zg, full) if full is not None else 0
    return {"terms": terms, "J": round(J, 3), "hit": hit, "over": over, "miss": miss,
            "truth": len(T), "iou": round(ii, 3), "cover": round(cov, 2),
            "dealer": fence["dealer"], "area_id": fence["area_id"], "km2": fence["area_km2"]}

if __name__ == "__main__":
    rows = []
    fences = [f for f in json.load(open(f"{DATA}/region.json"))["fences"] if "佛山" not in f["dealer"]]
    for k, f in enumerate(fences):
        try:
            r = process(f)
        except Exception as e:
            r = {"terms": [f"ERROR {type(e).__name__}: {e}"], "J": 0, "hit": 0, "over": 0, "miss": 0,
                 "truth": 0, "iou": 0, "cover": 0, "dealer": f["dealer"], "area_id": f["area_id"], "km2": f["area_km2"]}
        rows.append(r)
        print(f"[{k+1}/{len(fences)}] {f['dealer'][:16]:<16} {len(r['terms'])}词 J={r['J']:.2f} "
              f"片{r['hit']}/{r['truth']} over={r['over']} IoU={r['iou']:.3f} 覆盖={r['cover']}%")
    json.dump(rows, open(f"{DATA}/all_dealer_descriptions_v2.json", "w"), ensure_ascii=False, indent=1)
    import statistics
    js = [r["J"] for r in rows]; ious = [r["iou"] for r in rows]; covs = [r["cover"] for r in rows]
    ws = [len(r["terms"]) for r in rows]
    print(f"\n=== v2: {len(rows)}条围栏 ===")
    print(f"地块J: 中位{statistics.median(js):.3f}  J=1.0: {sum(1 for j in js if j==1.0)}/{len(rows)}")
    print(f"围栏IoU: 中位{statistics.median(ious):.3f}  覆盖中位: {statistics.median(covs):.2f}%")
    print(f"词数: 中位{statistics.median(ws)} 最大{max(ws)}")
    print("saved all_dealer_descriptions_v2.json")
