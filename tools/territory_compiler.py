#!/usr/bin/env python3
"""领地编译器 v1：人话描述 + 人工围栏 → 引擎精确表达式(统一铺盖U上的限定词组合)

双层架构（B为主A为辅）：
  人类层：父库上的街道名/街道沿路/界带词（≤8句，可读）
  引擎层：统一铺盖U上的限定词精确组合（零过选零漏选，机器用）
编译一次，重演时只用引擎层。
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
ROAD_BUF = 100 / 111000

# ---------- 数据（全GCJ） ----------
d = json.load(open('/Users/ghb/Downloads/边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson'))
parents = []; pstreet = []
for f in d["features"]:
    g = f["geometry"]
    if g["type"] != "Polygon": continue
    parents.append(Polygon(g["coordinates"][0], g["coordinates"][1:]))
    pstreet.append(f["properties"].get("街道[内置]", ""))
pt = STRtree(parents)

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
sbt = ops.unary_union([p.boundary for p in spoly])

reg = json.load(open(f"{DATA}/region.json"))

# ---------- 统一铺盖 U（带父id） ----------
U = []
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
        if u.geom_type == "Polygon": U.append((u, pstreet[pi], a, pi))
        continue
    for j, part in hits:
        if part.geom_type == "Polygon": U.append((part, pstreet[pi], sname[j], pi))
        elif part.geom_type == "MultiPolygon":
            for g2 in part.geoms: U.append((g2, pstreet[pi], sname[j], pi))
for k in range(len(U)):
    if not U[k][0].is_valid: U[k] = (U[k][0].buffer(0),) + U[k][1:]
Ut = STRtree([x[0] for x in U])

# 剩余带 R（每A街）
residual = {}
for j in range(len(spoly)):
    inside = [x[0] for x in U if x[2] == sname[j]]
    if not inside: continue
    r = spoly[j].difference(ops.unary_union(inside))
    if not r.is_empty and r.area * KM2 > 0.005:
        residual[sname[j]] = r

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
_rd = {}
_p_rd = {}
def unit_roads(k):
    if k not in _rd:
        gw = ops.transform(lambda x, y: gcj2wgs(x, y), U[k][0])
        _rd[k] = {named[j][0] for j in nrt.query(gw.buffer(ROAD_BUF))}
    return _rd[k]

# ---------- 人类层：父库上的描述词（v1规则） ----------
def human_terms_for(fence, psel, pby_road):
    zg = Polygon(fence["rings"][0])
    if not zg.is_valid: zg = zg.buffer(0)
    if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
    pstreet_all = defaultdict(set)
    for i, s in enumerate(pstreet):
        if s: pstreet_all[s].add(i)
    groups = defaultdict(list)
    for i in psel: groups[pstreet[i]].append(i)
    terms = []
    for stn, ids in sorted(groups.items(), key=lambda x: -len(x[1])):
        tot = len(pstreet_all.get(stn, ()))
        if len(ids) == tot:
            terms.append(stn); continue
        in_cnt = Counter(); all_cnt = Counter()
        for i in ids: in_cnt.update(pby_road[i])
        for i in pstreet_all.get(stn, ()): all_cnt.update(pby_road.get(i, set()))
        cand = sorted(in_cnt.items(), key=lambda kv: (all_cnt.get(kv[0], 0) - kv[1], -kv[1]))
        covered = set()
        for rd, c in cand:
            if c == 0: continue
            terms.append(f"{stn}沿{rd}")
            covered |= {i for i in ids if rd in pby_road[i]}
            if covered >= set(ids): break
        if set(ids) - covered:
            terms.append(stn)
    # 界带
    punion = ops.unary_union([parents[i] for i in psel])
    strip = zg.difference(punion).intersection(sbt.buffer(150/111000))
    if strip.area * KM2 > 0.01:
        pieces = strip.geoms if strip.geom_type == "MultiPolygon" else [strip]
        for pc in pieces:
            if pc.area * KM2 < 0.01: continue
            c = pc.centroid
            best = None
            for j in range(len(spoly)):
                dd = spoly[j].boundary.distance(c) * 111000
                if best is None or dd < best[1]: best = (j, dd)
            j = best[0]
            cands = sorted(((sname[j2], spoly[j2].boundary.distance(c)*111000) for j2 in range(len(spoly)) if j2 != j), key=lambda t: t[1])
            terms.append(f"{'西' if c.x < zg.centroid.x else '东' if c.x > zg.centroid.x else '南' if c.y < zg.centroid.y else '北'}至{sname[j]}—{cands[0][0] if cands else '?'}界")
    return terms

# ---------- 引擎层：U上的限定词精确覆盖（贪心，工程层） ----------
_WORDS = None
def global_words():
    """词表与围栏无关, 全局构建一次"""
    global _WORDS
    if _WORDS is not None: return _WORDS
    words = {}
    byba = defaultdict(list)
    for k in range(len(U)): byba[(U[k][1], U[k][2])].append(k)
    for (b, a), ks in byba.items():
        if a: words[f"{b}(限{a}内)"] = set(ks)
    byba_rd = defaultdict(set)
    for k in range(len(U)):
        for rd in unit_roads(k): byba_rd[(U[k][1], U[k][2], rd)].add(k)
    for (b, a, rd), ks in byba_rd.items():
        if a: words[f"{b}沿{rd}(限{a}内)"] = set(ks)
    for k in range(len(U)): words[f"P#{k}"] = {k}
    _WORDS = words
    return words

def engine_terms_for(zg, T):
    """T: 真值片集合。贪心选限定词，零过选零漏。"""
    words = global_words()
    chosen = []
    cov = set()
    T = set(T)
    while cov < T:
        best = None
        for w, s in words.items():
            gain = len((s & T) - cov)
            if gain == 0: continue
            o = len((s - cov) - T)
            key = (o, -gain)
            if best is None or key < best[0]: best = (key, w, s)
        if best is None: break
        _, w, s = best
        chosen.append(w)
        cov |= (s & T)
    miss = T - cov
    # 兜底: 残余片逐片用片词
    if miss:
        byba = defaultdict(list)
        for k in miss: byba[(U[k][1], U[k][2])].append(k)
        for (b, a), ks in byba.items():
            w = f"{b}(限{a}内)"
            if w not in chosen: chosen.append(w)
    return chosen

def engine_resolve(chosen):
    S = set()
    for w in chosen:
        if w.startswith("P#"):
            S |= {int(w[2:])}; continue
        if "(限" in w and "沿" in w:
            a, rest = w.split("沿", 1)
            rd, rest2 = rest.split("(限", 1)
            a_s = rest2.rstrip("内)")
            S |= {k for k in range(len(U)) if U[k][1] == a and U[k][2] == a_s and rd in unit_roads(k)}
        elif "(限" in w:
            b = w.split("(")[0]; a_s = w.split("限")[1].rstrip("内)")
            S |= {k for k in range(len(U)) if U[k][1] == b and U[k][2] == a_s}
    return S

def iou_v(a, b):
    i = a.intersection(b).area; s = a.area + b.area - i
    return i/s if s else 0

def compile_fence(fence):
    zg = Polygon(fence["rings"][0])
    if not zg.is_valid: zg = zg.buffer(0)
    if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
    # 真值(引擎层): 片≥50%
    T = {k for k in range(len(U)) if U[k][0].intersection(zg).area/max(U[k][0].area,1e-12) >= 0.5}
    # 真值(人类层): 父≥50%
    psel = {i for i in pt.query(zg) if parents[i].intersection(zg).area/max(parents[i].area,1e-12) >= 0.5}
    if not psel:
        psel = {i for i in pt.query(zg) if parents[i].intersection(zg).area > 1e-9}
    pby_road = {}
    for i in psel:
        if i not in _p_rd:
            gw = ops.transform(lambda x, y: gcj2wgs(x, y), parents[i])
            _p_rd[i] = {named[j][0] for j in nrt.query(gw.buffer(ROAD_BUF))}
        pby_road[i] = _p_rd[i]
    hterms = human_terms_for(fence, psel, pby_road)
    eterms = engine_terms_for(zg, T)
    S = engine_resolve(eterms)
    hit = len(S & T); over = len(S - T); miss = len(T - S)
    J = hit/(hit+over+miss) if hit+over+miss else 0
    full = ops.unary_union([U[k][0] for k in S]) if S else None
    cov = zg.intersection(full).area/zg.area*100 if full is not None else 0
    ii = iou_v(zg, full) if full is not None else 0
    return {"dealer": fence["dealer"], "area_id": fence["area_id"], "km2": fence["area_km2"],
            "human_terms": hterms, "engine_terms": eterms,
            "engine_J": round(J, 3), "engine_hit": hit, "engine_over": over, "engine_miss": miss,
            "truth_pieces": len(T), "iou": round(ii, 3), "cover": round(cov, 2)}

if __name__ == "__main__":
    rows = []
    fences = [f for f in reg["fences"] if "佛山" not in f["dealer"]]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for k, f in enumerate(fences):
        if only and only not in f["dealer"]: continue
        try:
            r = compile_fence(f)
        except Exception as e:
            r = {"dealer": f["dealer"], "area_id": f["area_id"], "human_terms": [f"ERROR {type(e).__name__}: {e}"],
                 "engine_terms": [], "engine_J": 0, "engine_hit": 0, "engine_over": 0, "engine_miss": 0,
                 "truth_pieces": 0, "iou": 0, "cover": 0, "km2": f["area_km2"]}
        rows.append(r)
        print(f"[{k+1}] {f['dealer'][:16]:<16} 人话{len(r['human_terms'])}句 引擎{len(r['engine_terms'])}词 "
              f"J={r['engine_J']:.2f} over={r['engine_over']} miss={r['engine_miss']} IoU={r['iou']:.3f} 覆盖={r['cover']}%")
    if not only:
        json.dump(rows, open(f"{DATA}/territory_compiled.json", "w"), ensure_ascii=False, indent=1)
        import statistics
        print(f"\n=== {len(rows)}条 ===")
        print(f"引擎J中位: {statistics.median(r['engine_J'] for r in rows):.3f}")
        print(f"IoU中位: {statistics.median(r['iou'] for r in rows):.3f}  覆盖中位: {statistics.median(r['cover'] for r in rows):.2f}%")
        print("saved territory_compiled.json")
