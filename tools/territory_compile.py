#!/usr/bin/env python3
"""领地编译器 v3.1 —— IR居中架构
真值T → (词label, 子句)对贪心覆盖 → SIR → 双投影(人话/引擎词)
规范: data/gz/ONTOLOGY.md
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
FEAT_BUF = 100 / 111000
BAND_BUF = 150 / 111000

# ---------- 数据 ----------
d = json.load(open('/Users/ghb/Downloads/边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson'))
parents = []; pstreet = []; pdistrict = []
for f in d["features"]:
    g = f["geometry"]
    if g["type"] != "Polygon": continue
    pr = f["properties"]
    parents.append(Polygon(g["coordinates"][0], g["coordinates"][1:]))
    pstreet.append(pr.get("街道[内置]", ""))
    pdistrict.append(pr.get("区[内置]", ""))
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
spoly_by_name = dict(zip(sname, spoly))

reg = json.load(open(f"{DATA}/region.json"))
osm = json.load(open(f"{DATA}/gz_osm_full.json"))

CLASS_RANK = {"motorway":0,"motorway_link":1,"trunk":1,"trunk_link":2,"primary":2,
              "primary_link":3,"secondary":3,"secondary_link":4,"tertiary":4,
              "tertiary_link":5,"residential":6,"unclassified":7,"service":8}
RIVER_RANK = 3

feat_geoms = []; feat_names = []; feat_rank = {}
def _add_feat(nm, g, rk_default):
    parts = [g] if g.geom_type=="LineString" else (list(g.geoms) if g.geom_type=="MultiLineString" else [])
    for pp in parts:
        if pp.length > 1e-5:
            feat_geoms.append(pp); feat_names.append(nm)
    rk = feat_rank.get(nm, rk_default)
    if nm not in feat_rank or rk < feat_rank[nm]: feat_rank[nm] = rk
for r in osm["roads"]:
    nm = r.get("name")
    if not nm: continue
    try: g = wkt.loads(r["wkt"])
    except Exception: continue
    _add_feat(nm, g, CLASS_RANK.get(r.get("cls","unclassified"), 7))
for r in osm.get("rivers", []):
    nm = r.get("name","")
    if not nm: continue
    try: g = wkt.loads(r["wkt"])
    except Exception: continue
    _add_feat(nm, g, RIVER_RANK)
ftt = STRtree(feat_geoms)

adm6 = []
for rr in osm["adm6"]:
    try: adm6.append((rr.get("name",""), wkt.loads(rr["wkt"]).boundary))
    except Exception: pass
adm6bt = ops.unary_union([b for _, b in adm6])
print(f"数据: 地块{len(parents)} 街道面{len(spoly)} 地物{len(feat_geoms)}条/{len(feat_rank)}名")

# ---------- 统一铺盖 U ----------
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
print(f"统一铺盖U: {len(U)}片")

# ---------- 地物贴附（缓存） ----------
_feats = {}
def feats_of(k):
    if k not in _feats:
        gw = ops.transform(lambda x, y: gcj2wgs(x, y), U[k][0])
        s = set()
        for j in ftt.query(gw.buffer(FEAT_BUF)):
            if feat_geoms[j].distance(gw) <= FEAT_BUF: s.add(feat_names[j])
        _feats[k] = s
    return _feats[k]

FEATS = defaultdict(set)   # 地物名 → 片id集合
for _k in range(len(U)):
    for _nm in feats_of(_k): FEATS[_nm].add(_k)

# ---------- 词表与子句（全局一次；词label与其子句一一对应） ----------
VOCAB = None   # list of (label, clause, pieces)
def vocab():
    global VOCAB
    if VOCAB is not None: return VOCAB
    v = []
    byba = defaultdict(list)
    for k in range(len(U)): byba[(U[k][1], U[k][2])].append(k)
    for (b, a), ks in byba.items():
        v.append((f"{b}沿界(限{a}内)" if False else f"{b}(限{a}内)",
                  {"type": "slice", "street": b, "within": a}, set(ks)))
    byf = defaultdict(set)
    for k in range(len(U)):
        for f in feats_of(k): byf[(U[k][1], U[k][2], f)].add(k)
    for (b, a, f), ks in byf.items():
        kind = "river" if f in _river_name_set else "road"
        v.append((f"{b}沿{f}(限{a}内)",
                  {"type": "feat", "street": b, "feat": f, "kind": kind, "within": a}, set(ks)))
    v.append(("零星地块", {"type": "pieces", "ids": []}, set()))  # 占位: P#逐片词在下方
    for k in range(len(U)):
        v.append((f"P#{k}", {"type": "pieces", "ids": [k]}, {k}))
    VOCAB = v
    return v

# 河名集合（供 kind 判定）
_river_name_set = set()
for r in osm.get("rivers", []):
    nm = r.get("name","")
    if nm: _river_name_set.add(nm)

def clause_pieces(clause):
    t = clause["type"]
    if t == "band": return set()
    if t == "slice":
        return {k for k, x in enumerate(U) if x[1] == clause["street"] and x[2] == clause["within"]}
    if t == "feat":
        return {k for k in FEATS.get(clause["feat"], set()) if U[k][1] == clause["street"]
                and (not clause.get("within") or U[k][2] == clause["within"])}
    if t == "block":
        return {k for k, x in enumerate(U) if x[1] == clause["street"]}
    if t == "pieces":
        return set(clause["ids"])
    return set()



# ---------- eval SIR ----------
def eval_sir(ir):
    S = set(); bands = []
    for cl in ir["clauses"]:
        S |= clause_pieces(cl)
        if cl["type"] == "band":
            nm = cl["ref"].replace("河岸", "")
            g = spoly_by_name.get(nm.replace("至", "").split("—")[0] if "—" in nm else nm.replace("至", ""))
            # 界带几何: 街道剩余带(确定性)
            if g is not None:
                inside = [x[0] for x in U if x[2] == cl["ref"].replace("至", "").replace("河岸", "").split("—")[0]]
                if inside:
                    bands.append(g.difference(ops.unary_union(inside)))
    return S, bands

# ---------- 贪心合成: 真值T → 子句列表 ----------
def synth(zg, T):
    T = set(T)
    chosen = []; cov = set()
    V = vocab()
    while cov < T:
        best = None
        for label, clause, s in V:
            gain = len((s & T) - cov)
            if gain == 0: continue
            o = len((s - cov) - T)
            salience = 0
            if clause["type"] == "feat":
                salience = -feat_rank.get(clause["feat"], 7)
            key = (o, -gain, salience)
            if best is None or key < best[0]: best = (key, label, clause, s)
        if best is None: break
        _, label, clause, s = best
        chosen.append((label, clause))
        cov |= (s & T)
    return chosen

# ---------- 人话 verbalize ----------
def verbalize(chosen, zg_):
    by_street = defaultdict(list)
    bands = []
    for label, cl in chosen:
        if cl["type"] == "band":
            bands.append(cl); continue
        if cl["type"] == "pieces": continue
        if cl["type"] == "slice":
            by_street[cl["street"]].append(cl)
        elif cl["type"] == "feat":
            by_street[cl["street"]].append(cl)
        elif cl["type"] == "block":
            by_street[cl["street"]].append(cl)
    parts = []
    for stn, cls in sorted(by_street.items(), key=lambda kv: -len(kv[1])):
        whole = any(c["type"] == "slice" and c["street"] == c["within"] for c in cls)                 or (len(cls) == 1 and cls[0]["type"] == "block")
        feats = sorted({c["feat"] for c in cls if c["type"] == "feat"},
                       key=lambda f: -feat_rank.get(f, 7))
        if whole:
            parts.append(stn)
        elif feats:
            parts.append(f"{stn}沿{feats[0]}")
        else:
            parts.append(f"{stn}一带")
    for cl in bands:
        parts.append(f"{cl['side']}至{cl['ref']}")
    return parts
def band_clause(zg, pc):
    c = pc.centroid
    best6 = None
    for n6, b6 in adm6:
        dd6 = b6.distance(c) * 111000
        if best6 is None or dd6 < best6[1]: best6 = (n6, dd6)
    if best6 and best6[1] < 300:
        side = "西" if c.x < zg.centroid.x else "东" if c.x > zg.centroid.x else "南" if pc.centroid.y < zg.centroid.y else "北"
        return {"type": "band", "side": side, "ref": f"{best6[0]}界"}
    best = None
    for j in range(len(spoly)):
        dd = spoly[j].boundary.distance(c) * 111000
        if best is None or dd < best[1]: best = (j, dd)
    j = best[0]
    cands = sorted(((sname[j2], spoly[j2].boundary.distance(c)*111000) for j2 in range(len(spoly)) if j2 != j), key=lambda t: t[1])
    side = "西" if c.x < zg.centroid.x else "东" if c.x > zg.centroid.x else "南" if pc.centroid.y < zg.centroid.y else "北"
    return {"type": "band", "side": side, "ref": f"{sname[j]}—{cands[0][0] if cands else '?'}界"}

# ---------- 单围栏编译 ----------
def compile_fence(fence):
    zg = Polygon(fence["rings"][0])
    if not zg.is_valid: zg = zg.buffer(0)
    if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
    fa = zg.area
    T = {k for k in range(len(U))
         if U[k][0].intersection(zg).area/max(U[k][0].area,1e-12) >= 0.5
         or U[k][0].intersection(zg).area/fa >= 0.3}
    psel = {i for i in pt.query(zg)
            if parents[i].intersection(zg).area/max(parents[i].area,1e-12) >= 0.5
            or parents[i].intersection(zg).area/fa >= 0.3}
    if not psel:
        psel = {i for i in pt.query(zg) if parents[i].intersection(zg).area > 1e-9}
    chosen = synth(zg, T)
    # 界带: 围栏−片并集 沿行政界的剩余
    if chosen:
        S_syn = set()
        for _, c in chosen: S_syn |= clause_pieces(c)
        pu = ops.unary_union([U[k][0] for k in S_syn])
        strip = zg.difference(pu).intersection(ops.unary_union([sbt, adm6bt]).buffer(BAND_BUF))
        if strip.area * KM2 > 0.01:
            pieces = strip.geoms if strip.geom_type == "MultiPolygon" else [strip]
            for pc in pieces:
                if pc.area * KM2 < 0.01: continue
                chosen.append((f"{pc.centroid.x:.4f}界带", band_clause(zg, pc)))
    # IR
    clauses = [cl for _, cl in chosen]
    libhash = __import__("hashlib").sha256(open('/Users/ghb/Downloads/边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson','rb').read()).hexdigest()[:16]
    ir = {"area_id": fence["area_id"], "ir_version": 1, "tessellation": "U",
          "unit_library": f"{libhash}+cutv2", "clauses": clauses, "annotations": {}}
    # 验证: eval(ir) ⊇ T
    S = set(); bands_g = []
    for cl in clauses:
        s = clause_pieces(cl)
        S |= s
        if cl["type"] == "band":
            nm = cl["ref"].replace("界", "")
            a = nm.split("—")[0]
            g = spoly_by_name.get(a)
            if g is not None:
                inside = [x[0] for x in U if x[2] == a]
                if inside: bands_g.append(g.difference(ops.unary_union(inside)))
    full = ops.unary_union([U[k][0] for k in S] + bands_g) if (S or bands_g) else None
    hterms = verbalize(chosen, zg)
    hit = len(S & T); over = len(S - T); miss = len(T - S)
    J = hit/(hit+over+miss) if hit+over+miss else 0
    cov = zg.intersection(full).area/zg.area*100 if full is not None else 0
    ii = iou_v(zg, full) if full is not None else 0
    return {"dealer": fence["dealer"], "area_id": fence["area_id"], "km2": fence["area_km2"],
            "human_terms": hterms, "engine_terms": [l for l, _ in chosen],
            "ir": ir, "T": sorted(T), "S": sorted(S),
            "engine_J": round(J, 3), "engine_hit": hit, "engine_over": over, "engine_miss": miss,
            "truth_pieces": len(T), "iou": round(ii, 3), "cover": round(cov, 2)}

def iou_v(a, b):
    i = a.intersection(b).area; s = a.area + b.area - i
    return i/s if s else 0

_p_rd = {}

if __name__ == "__main__":
    rows = []
    fences = [f for f in reg["fences"] if "佛山" not in f["dealer"]]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for k, f in enumerate(fences):
        if only and only not in f["dealer"]: continue
        try:
            r = compile_fence(f)
        except Exception as e:
            import traceback; traceback.print_exc()
            r = {"dealer": f["dealer"], "area_id": f["area_id"], "human_terms": [f"ERROR {type(e).__name__}: {e}"],
                 "engine_terms": [], "engine_J": 0, "engine_hit": 0, "engine_over": 0,
                 "engine_miss": 0, "truth_pieces": 0, "iou": 0, "cover": 0, "km2": f["area_km2"], "T": [], "S": [], "ir": {}}
        rows.append(r)
        print(f"[{k+1}] {f['dealer'][:16]:<16} 人话{len(r['human_terms'])}句 引擎{len(r['engine_terms'])}词 "
              f"J={r['engine_J']:.2f} over={r['engine_over']} miss={r['engine_miss']} IoU={r['iou']:.3f} 覆盖={r['cover']}%")
    if not only:
        json.dump(rows, open(f"{DATA}/territory_compiled.json", "w"), ensure_ascii=False, indent=1)
        import statistics
        print(f"\n=== {len(rows)}条 ===")
        print(f"引擎J中位: {statistics.median(r['engine_J'] for r in rows):.3f}  "
              f"J=1.0: {sum(1 for r in rows if r['engine_J']==1.0)}/{len(rows)}")
        print(f"IoU中位: {statistics.median(r['iou'] for r in rows):.3f}  "
              f"覆盖中位: {statistics.median(r['cover'] for r in rows):.2f}%")
        print("saved territory_compiled.json")
    else:
        json.dump(rows, open("/tmp/compile_test.json", "w"), ensure_ascii=False, indent=1)
