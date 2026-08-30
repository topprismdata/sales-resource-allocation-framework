#!/usr/bin/env python3
"""Territory IR v1.1 — 语义权威表示
schema + eval + verbalize + lower (纯函数, 无全局状态)
规范见 data/gz/ONTOLOGY.md
"""
import hashlib, json
from collections import defaultdict, Counter

IR_VERSION = 1
CUT_VERSION = "cutv2"

# ---------- schema ----------
def make_ir(area_id, clauses, unit_library_hash, annotations=None):
    return {"area_id": area_id, "ir_version": IR_VERSION,
            "tessellation": "U",
            "unit_library": f"{unit_library_hash}+{CUT_VERSION}",
            "clauses": clauses,
            "annotations": annotations or {}}

def library_hash(units_geojson_path):
    h = hashlib.sha256()
    with open(units_geojson_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]

# ---------- eval: IR → (片集合, 带几何列表) ----------
def eval_ir(ir, ctx):
    """返回 (片id集合, 带几何列表)。与围栏无关的确定性解析。
    ctx: {U, FEATS, street_residual, river_bands, spoly_by_name, adm6}"""
    U = ctx["U"]; FEATS = ctx["FEATS"]
    street_residual = ctx["street_residual"]; river_bands = ctx["river_bands"]
    spoly_by_name = ctx["spoly_by_name"]
    S = set(); bands = []
    for cl in ir["clauses"]:
        t = cl["type"]
        if t == "block":
            S |= {k for k, x in enumerate(U) if x[1] == cl["street"]}
        elif t == "feat":
            ks = {k for k in FEATS.get(cl["feat"], set()) if U[k][1] == cl["street"]}
            if cl.get("within"): ks = {k for k in ks if U[k][2] == cl["within"]}
            S |= ks
        elif t == "slice":
            S |= {k for k, x in enumerate(U) if x[1] == cl["street"] and x[2] == cl["within"]}
        elif t == "except":
            base = {k for k, x in enumerate(U) if x[2] == cl["district"]}
            exc = set()
            for e in cl["exclude"]:
                exc |= {k for k, x in enumerate(U) if x[1] == e}
            S |= base - exc
        elif t == "band":
            ref = cl["ref"]
            if ref in street_residual:
                g = street_residual[ref]
            elif ref in river_bands:
                g = river_bands[ref]
            else:
                # "X—Y界": 两街道面边界邻接带(确定性: 边界缓冲−地块)
                a, b = ref.replace("界", "").split("—")
                ga = spoly_by_name.get(a); gb = spoly_by_name.get(b)
                if ga is None or gb is None: continue
                line = ga.intersection(gb).boundary if ga.intersects(gb) else None
                if line is None or line.is_empty: continue
                g = line.buffer(150/111000) - _union_all(U)
            bands.append(g)
        elif t == "pieces":
            S |= set(cl["ids"])
    return S, bands

def _union_all(U):
    from shapely import ops
    return ops.unary_union([x[0] for x in U])

def eval_union(ir, ctx):
    from shapely import ops
    S, bands = eval_ir(ir, ctx)
    geoms = [U[k][0] for k in S] + bands
    return ops.unary_union(geoms) if geoms else None

# ---------- verbalize: IR → 人话句 ----------
def _feat_label(kind):
    return {"road": "沿", "river": "沿"}.get(kind, "沿")

def verbalize(ir):
    """确定性模板。返回 (概要句, 明细句list)。"""
    by_street = defaultdict(list)
    details = []
    for cl in ir["clauses"]:
        t = cl["type"]
        if t == "block":
            by_street[cl["street"]].append(("block", cl))
        elif t == "feat":
            by_street[cl["street"]].append(("feat", cl))
        elif t == "slice":
            by_street[cl["street"]].append(("slice", cl))
        elif t == "pieces":
            details.append(f"零星地块{len(cl['ids'])}处")
        elif t == "except":
            parts = []
            for e in cl["exclude"]:
                parts.append(f"{e}一带")
            details.append(f"{cl['district']}除{ '、'.join(parts) }外的边缘地块")
        elif t == "band":
            details.append(f"{cl['side']}至{cl['ref']}")
    # 每街道合成一句
    for stn, cls in sorted(by_street.items(), key=lambda kv: -len(kv[1])):
        whole = any(t == "block" for t, _ in cls)
        if whole and len(cls) == 1:
            details.insert(0, stn); continue
        feats = [c["feat"] for t, c in cls if t == "feat"]
        slices = [c["within"] for t, c in cls if t == "slice"]
        if whole:
            details.insert(0, stn); continue
        if feats and not slices:
            details.insert(0, f"{stn}沿{feats[0]}")
        elif slices:
            details.insert(0, f"{stn}(限{slices[0]}内)")
        else:
            details.insert(0, f"{stn}一带")
    labels = ir.get("annotations", {}).get("labels", {})
    lead = []
    for stn, lab in labels.items():
        if lab == "全部": lead.append(stn)
    summary = "；".join(lead + [d for d in details if d not in lead]) or "（空）"
    return summary, details

# ---------- lower: IR → 引擎词序列（派生缓存） ----------
def lower(ir, ctx, words):
    """SIR → 引擎限定词序列(派生缓存)。words=宿主的全局词表。"""
    U = ctx["U"]; FEATS = ctx["FEATS"]
    words = {}
    byba = defaultdict(list)
    for k in range(len(U)): byba[(U[k][1], U[k][2])].append(k)
    for (b, a), ks in byba.items():
        if a: words[f"{b}(限{a}内)"] = set(ks)
    byf = defaultdict(set)
    for k in range(len(U)):
        for f in feats_of_u(U, k): byf[(U[k][1], U[k][2], f)].add(k)
    for (b, a, f), ks in byf.items():
        if a: words[f"{b}沿{f}(限{a}内)"] = set(ks)
    for k in range(len(U)): words[f"P#{k}"] = {k}
    chosen = []; cov = set()
    T = eval_pieces(ir, ctx)
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

def eval_pieces(ir, ctx):
    U = ctx["U"]; FEATS = ctx["FEATS"]
    S = set()
    for cl in ir["clauses"]:
        t = cl["type"]
        if t == "block":
            S |= {k for k, x in enumerate(U) if x[1] == cl["street"]}
        elif t == "feat":
            ks = {k for k in FEATS.get(cl["feat"], set()) if U[k][1] == cl["street"]}
            if cl.get("within"): ks = {k for k in ks if U[k][2] == cl["within"]}
            S |= ks
        elif t == "slice":
            S |= {k for k, x in enumerate(U) if x[1] == cl["street"] and x[2] == cl["within"]}
        elif t == "pieces":
            S |= set(cl["ids"])
        # except/band: 需要几何, 见 eval_ir
    return S

# ---------- parse: 人话短语 → IR 子句（用于 LLM 润色等价校验） ----------
def parse_clause(text):
    """识别人话短语为子句；无法识别返回 None。"""
    if "除" in text and "外" in text and "区" in text:
        d2 = text.split("除")[0]
        exc = text.split("除")[1].replace("外全域", "").replace("外", "")
        return {"type": "except", "district": d2, "exclude": [x for x in exc.split("、") if x]}
    if "界" in text and "至" in text:
        side = text.split("至")[0]
        ref = text.split("至")[1]
        return {"type": "band", "side": side, "ref": ref}
    if "沿" in text:
        a, feat = text.split("沿", 1)
        return {"type": "feat", "street": a, "feat": feat, "kind": "road"}
    if "一带" in text:
        return {"type": "block", "street": text.replace("一带", "")}
    return {"type": "block", "street": text}
