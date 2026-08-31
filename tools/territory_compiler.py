#!/usr/bin/env python3
"""领地编译器 v3 —— 本体：块词 / 沿地物词(路+河统一) / 片词 + P#引擎原子

核心公理：一个基础单元，要么沿河，要么沿路（或都沿）。
人类层：每街道≤1句(可读优先)；>4街镇 → 区县补集/方位概要
引擎层：限定词精确组合 + P#片原子 (J=1.0)
"""
import sys
import _paths
sys.path.insert(0, str(_paths.ROOT))
import json
from shapely.geometry import Polygon
from shapely import wkt, ops
from shapely.strtree import STRtree
from intelligence.coords import gcj2wgs
from territory_ir import make_ir, library_hash
from collections import Counter, defaultdict

DATA = _paths.DATA
KM2 = 12364.0
FEAT_BUF = 100 / 111000   # 沿地物词贴附距离（语言常量）

# ---------- 数据（全GCJ；OSM为WGS，匹配时gcj2wgs） ----------
d = json.load(open(_paths.SOURCE / "边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson"))
parents = []; pstreet = []; pdistrict = []
for f in d["features"]:
    g = f["geometry"]
    if g["type"] != "Polygon": continue
    pr = f["properties"]
    parents.append(Polygon(g["coordinates"][0], g["coordinates"][1:]))
    pstreet.append(pr.get("街道[内置]", ""))
    pdistrict.append(pr.get("区[内置]", ""))
pt = STRtree(parents)

sd = json.load(open(_paths.SOURCE / "区划数据-街道-广东省-广州市.geojson"))
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
osm = json.load(open(f"{DATA}/gz_osm_full.json"))

# ---------- 线性地物（路+河统一）：名称数组与几何树对齐 ----------
CLASS_RANK = {"motorway":0,"motorway_link":1,"trunk":1,"trunk_link":2,"primary":2,
              "primary_link":3,"secondary":3,"secondary_link":4,"tertiary":4,
              "tertiary_link":5,"residential":6,"unclassified":7,"service":8}
RIVER_RANK = 3   # 河涌显著性：高于一般道路（人类以河涌为锚）

feat_geoms = []; feat_names = []; feat_rank = {}
for r in osm["roads"]:
    nm = r.get("name")
    if not nm: continue
    try: g = wkt.loads(r["wkt"])
    except Exception: continue
    parts = [g] if g.geom_type=="LineString" else (list(g.geoms) if g.geom_type=="MultiLineString" else [])
    rk = CLASS_RANK.get(r.get("cls","unclassified"), 7)
    for pp in parts:
        if pp.length > 1e-5:
            feat_geoms.append(pp); feat_names.append(nm)
            if nm not in feat_rank or rk < feat_rank[nm]: feat_rank[nm] = rk
for r in osm.get("rivers", []):
    nm = r.get("name","")
    if not nm: continue
    try: g = wkt.loads(r["wkt"])
    except Exception: continue
    parts = [g] if g.geom_type=="LineString" else (list(g.geoms) if g.geom_type=="MultiLineString" else [])
    for pp in parts:
        if pp.length > 1e-4:
            feat_geoms.append(pp); feat_names.append(nm)
            if nm not in feat_rank: feat_rank[nm] = RIVER_RANK
ftt = STRtree(feat_geoms)
print(f"线性地物: {len(feat_geoms)}条 (命名{len(feat_rank)}个)")

adm6 = []
for rr in osm["adm6"]:
    try: adm6.append((rr.get("name",""), wkt.loads(rr["wkt"]).boundary))
    except Exception: pass
adm6bt = ops.unary_union([b for _, b in adm6])

# ---------- 统一铺盖 U：地块按街道面切割，片带(地块属街B, 区划街A, 父id) ----------
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

# 地块贴附地物（缓存）
_feats = {}
def feats_of(k):
    if k not in _feats:
        gw = ops.transform(lambda x, y: gcj2wgs(x, y), U[k][0])
        s = set()
        for j in ftt.query(gw.buffer(FEAT_BUF)):
            if feat_geoms[j].distance(gw) <= FEAT_BUF: s.add(feat_names[j])
        _feats[k] = s
    return _feats[k]

# 全局地物索引: 名称 → 片id集合
FEATS = defaultdict(set)
for k in range(len(U)):
    for nm in feats_of(k): FEATS[nm].add(k)

def feat_rank_of(nm): return feat_rank.get(nm, 7)

# ---------- 解析器（与围栏无关） ----------
def resolve_feat(stn, feat):
    """沿地物词: 该街道地块中贴附该地物的片"""
    return {k for k in FEATS.get(feat, set()) if U[k][1] == stn}
def resolve_block(stn):
    return {k for k, x in enumerate(U) if x[1] == stn}
def resolve_slice(stn, ast):
    return {k for k, x in enumerate(U) if x[1] == stn and x[2] == ast}
def parse_term(t):
    if t.startswith("P#"):
        return {int(t[2:])}
    if "沿" in t and "(限" in t:
        a, rest = t.split("沿", 1)
        feat, rest2 = rest.split("(限", 1)
        ast = rest2.rstrip("内)")
        return {k for k in resolve_feat(a, feat) if U[k][2] == ast}
    if "沿" in t:
        a, feat = t.split("沿", 1)
        return resolve_feat(a, feat)
    if "(限" in t:
        b = t.split("(")[0]; ast = t.split("限")[1].rstrip("内)")
        return resolve_slice(b, ast)
    return resolve_block(t)

# ---------- 人类层 ----------
def _per_street_terms(groups, pby_road, zg_):
    psel = set()
    for ids in groups.values(): psel |= set(ids)
    terms = []
    for stn, ids in sorted(groups.items(), key=lambda x: -len(x[1])):
        tot = len({i for i in range(len(parents)) if pstreet[i] == stn})
        frac = len(ids)/max(tot, 1)
        if frac >= 0.9:
            terms.append(stn); continue
        in_cnt = Counter()
        for i in ids: in_cnt.update(pby_road[i])
        if in_cnt:
            # REG偏好序: 地物显著等级优先, 同级覆盖多优先
            feat, c = max(in_cnt.items(), key=lambda kv: (-feat_rank_of(kv[0]), kv[1]))
            terms.append(f"{stn}沿{feat}")
        else:
            terms.append(f"{stn}一带")
    # 界带（区县界优先, 去重）: 围栏沿行政界走、无地块覆盖的段
    psel = set()
    for ids in groups.values(): psel |= set(ids)
    punion = ops.unary_union([parents[i] for i in psel])
    strip = zg_.difference(punion).intersection(ops.unary_union([sbt, adm6bt]).buffer(150/111000))
    if strip.area * KM2 > 0.01:
        pieces = strip.geoms if strip.geom_type == "MultiPolygon" else [strip]
        seen_b = set()
        for pc in pieces:
            if pc.area * KM2 < 0.01: continue
            c = pc.centroid
            best6 = None
            for n6, b6 in adm6:
                dd6 = b6.distance(c) * 111000
                if best6 is None or dd6 < best6[1]: best6 = (n6, dd6)
            if best6 and best6[1] < 300:
                w = f"{'西' if c.x < zg_.centroid.x else '东' if c.x > zg_.centroid.x else '南' if pc.centroid.y < zg_.centroid.y else '北'}至{best6[0]}界"
            else:
                best = None
                for j in range(len(spoly)):
                    dd = spoly[j].boundary.distance(c) * 111000
                    if best is None or dd < best[1]: best = (j, dd)
                j = best[0]
                cands = sorted(((sname[j2], spoly[j2].boundary.distance(c)*111000) for j2 in range(len(spoly)) if j2 != j), key=lambda t: t[1])
                w = f"{'西' if c.x < zg_.centroid.x else '东' if c.x > zg_.centroid.x else '南' if pc.centroid.y < zg_.centroid.y else '北'}至{sname[j]}—{cands[0][0] if cands else '?'}界"
            if w not in seen_b:
                seen_b.add(w); terms.append(w)
    return terms

def human_terms_for(fence, psel, pby_road):
    """返回 (概要句, 明细句)。街镇≤4: 概要=明细; >4: 区县补集/方位概要"""
    zg_ = Polygon(fence["rings"][0])
    if not zg_.is_valid: zg_ = zg_.buffer(0)
    if zg_.geom_type == "MultiPolygon": zg_ = max(zg_.geoms, key=lambda g: g.area)
    groups0 = defaultdict(list)
    for i in psel: groups0[pstreet[i]].append(i)
    if len(groups0) <= 4:
        d = _per_street_terms(groups0, pby_road, zg_)
        return list(d), list(d)
    # 区县补集 vs 正枚举, 按提及数取小（例外集小且显著时"除X外"最自然）
    dist_streets = defaultdict(set)
    for i in range(len(parents)):
        if pdistrict[i]: dist_streets[pdistrict[i]].add(pstreet[i])
    dist_tot = Counter(pdistrict)
    dist_in = {}
    for d2 in set(pdistrict[i] for i in psel):
        ids2 = [i for i in psel if pdistrict[i]==d2]
        in_st = set(pstreet[i] for i in ids2)
        dist_in[d2] = (in_st, len(ids2), ids2)
    parts = []
    for d2, (in_st, pc, ids2) in sorted(dist_in.items(), key=lambda kv: -kv[1][1]):
        tot_st = dist_streets.get(d2, set())
        miss_st = sorted(tot_st - in_st)
        cov = pc / max(dist_tot[d2], 1)
        if miss_st and len(miss_st) < len(in_st) and len(miss_st) <= 3 and cov >= 0.6:
            parts.append(f"{d2}除{'、'.join(miss_st)}外")
        elif not miss_st:
            parts.append(f"{d2}全域")
        else:
            inner = [parents[i].centroid for i in ids2]
            icx = sum(c.x for c in inner)/len(inner); icy = sum(c.y for c in inner)/len(inner)
            dx = icx-zg_.centroid.x; dy = icy-zg_.centroid.y
            pos = ("西" if dx<0 else "东") if abs(dx)>abs(dy) else ("南" if dy<0 else "北")
            spine = Counter()
            for i in ids2:
                for f in pby_road[i]:
                    if feat_rank_of(f) <= 3: spine[f]+=1
            spine_txt = "、".join([f for f,_ in spine.most_common(2)]) if spine else "主干道路"
            stn_txt = "、".join(sorted(in_st, key=lambda s: -len(groups0.get(s, [])))[:2])
            parts.append(f"{d2}{pos}部（含{stn_txt}等{len(in_st)}个街镇，沿{spine_txt}一带）")
    summary = ["；".join(parts)]
    detail = _per_street_terms(groups0, pby_road, zg_)
    return summary, detail

# ---------- 引擎层（贪心最小覆盖 + P#原子兜底；贪心=集合覆盖标准近似, 机器层） ----------
_WORDS = None
def global_words():
    global _WORDS
    if _WORDS is not None: return _WORDS
    words = {}
    byba = defaultdict(list)
    for k in range(len(U)): byba[(U[k][1], U[k][2])].append(k)
    for (b, a), ks in byba.items():
        if a: words[f"{b}(限{a}内)"] = set(ks)
    byf = defaultdict(set)
    for k in range(len(U)):
        for f in feats_of(k): byf[(U[k][1], U[k][2], f)].add(k)
    for (b, a, f), ks in byf.items():
        if a: words[f"{b}沿{f}(限{a}内)"] = set(ks)
    for k in range(len(U)): words[f"P#{k}"] = {k}
    _WORDS = words
    return words

def engine_terms_for(zg, T):
    words = global_words()
    T = set(T)
    chosen = []; cov = set()
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
        chosen.append(w); cov |= (s & T)
    return chosen

def engine_resolve(chosen):
    S = set()
    for w in chosen:
        S |= parse_term(w)
    return S

def iou_v(a, b):
    i = a.intersection(b).area; s = a.area + b.area - i
    return i/s if s else 0

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
    pby_road = {}
    for i in psel:
        if i not in _p_rd: _p_rd[i] = feats_of.__wrapped__(i) if hasattr(feats_of,'__wrapped__') else None
        # 父地块贴附: 单独计算（父不在U中）
        gw = ops.transform(lambda x, y: gcj2wgs(x, y), parents[i])
        s = set()
        for j in ftt.query(gw.buffer(FEAT_BUF)):
            if feat_geoms[j].distance(gw) <= FEAT_BUF: s.add(feat_names[j])
        pby_road[i] = s
    eterms = engine_terms_for(zg, T)
    # 引擎词 → IR 子句（格式确定，直接映射）
    clauses = []
    pieces_acc = []
    for w in eterms:
        if w.startswith("P#"):
            pieces_acc.append(int(w[2:])); continue
        clauses.append({"type": "feat" if "沿" in w else "slice" if "(限" in w else "block",
                        "_w": w})
    # 用 parse 语义展开为规范子句
    norm = []
    for cl in clauses:
        w = cl["_w"]
        if "沿" in w and "(限" in w:
            a, rest = w.split("沿", 1)
            feat, rest2 = rest.split("(限", 1)
            within = rest2.rstrip(")").rstrip("内").rstrip("限")
            norm.append({"type": "feat", "street": a, "feat": feat, "kind": "road", "within": within})
        elif "(限" in w:
            b = w.split("(限")[0]
            within = w.split("(限")[1].rstrip(")").rstrip("内")
            norm.append({"type": "slice", "street": b, "within": within})
        elif "沿" in w:
            a, feat = w.split("沿", 1)
            norm.append({"type": "feat", "street": a, "feat": feat, "kind": "road"})
        else:
            norm.append({"type": "block", "street": w})
    clauses = norm
    ir = make_ir(f["area_id"], clauses, library_hash(_paths.SOURCE / "边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson"))
    # 回环校验: IR eval 必须等于贪心覆盖 T
    ctx = {"U": U, "FEATS": FEATS, "street_residual": {}, "river_bands": {},
           "spoly_by_name": dict(zip(sname, spoly)), "adm6": adm6}
    S_ir = set()
    for cl in ir["clauses"]:
        t2 = cl["type"]
        if t2 == "block":
            S_ir |= {k for k, x in enumerate(U) if x[1] == cl["street"]}
        elif t2 == "feat":
            ks = {k for k in FEATS.get(cl["feat"], set()) if U[k][1] == cl["street"]}
            if cl.get("within"): ks = {k for k in ks if U[k][2] == cl["within"]}
            S_ir |= ks
        elif t2 == "slice":
            S_ir |= {k for k, x in enumerate(U) if x[1] == cl["street"] and x[2] == cl["within"]}
        elif t2 == "pieces":
            S_ir |= set(cl["ids"])
    if S_ir != set(T):
        raise RuntimeError(f"IR回环失败: ir={len(S_ir)} T={len(T)} 差={len(S_ir^set(T))}")
    S = S_ir
    hit = len(S & T); over = len(S - T); miss = len(T - S)
    J = hit/(hit+over+miss) if hit+over+miss else 0
    full = ops.unary_union([U[k][0] for k in S]) if S else None
    cov = zg.intersection(full).area/zg.area*100 if full is not None else 0
    ii = iou_v(zg, full) if full is not None else 0
    return {"dealer": fence["dealer"], "area_id": fence["area_id"], "km2": fence["area_km2"],
            "human_terms": hterms, "human_detail": hdetail, "engine_terms": eterms,
            "ir": ir, "T": sorted(T), "S": sorted(S),
            "engine_J": round(J, 3), "engine_hit": hit, "engine_over": over, "engine_miss": miss,
            "truth_pieces": len(T), "iou": round(ii, 3), "cover": round(cov, 2)}

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
                 "human_detail": [], "engine_terms": [], "engine_J": 0, "engine_hit": 0, "engine_over": 0,
                 "engine_miss": 0, "truth_pieces": 0, "iou": 0, "cover": 0, "km2": f["area_km2"], "T": [], "S": []}
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
