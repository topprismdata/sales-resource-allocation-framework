"""区域调整 v2（RC2.0）：决策对象 = TerritoryIR 单元片集合（S 片）。

v0.4.x（旧）：门店归属=唯一事实，围栏=门店凸包派生视图。
             片区=门店集合 → 无门店经销商直接失败。
v2.0（本版）：单元片=唯一事实（6261 片统一铺盖 U × territory_compiled S），
             围栏=片并集几何视图；门店=派生效果层（只出统计信号，
             永不作为失败条件）。

指令语法（与 v1 兼容）：
  把 <src> 的 <片区> 划给 <dst>
  把 <src> 整体并入 <dst>
  <src> 不做了，区域都给 <dst>
片区选择：
  全部/整体/不做了/退出   → src 全部 S 片
  东/南/西/北 半区        → 片质心相对并集质心的方向
  <街道名>               → 街道标签或所在街道匹配的片
  <区名>                 → street→district 映射反查街道 → 该街道的片
  OOF/跨界               → 派生层概念，IR 模式不支持（明确报错）
应用：对 src/dst 围栏做几何手术（difference / union），门店归属随片内
包含关系同步（若存在），territory_compiled.json 的 S 集合同步增删。
"""
from __future__ import annotations

import json
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from math import cos, radians
from pathlib import Path

from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from .knowledge import KnowledgeBase
from .world import Fence, Store, World

_KM2_LAT = 110.574
_KM2_LON = 111.320


def km2(g) -> float:
    """deg² → km²：按质心纬度换算。"""
    lat = g.centroid.y if not g.is_empty else 23.1
    return g.area * _KM2_LAT * _KM2_LON * cos(radians(lat))


class AdjustError(ValueError):
    pass


@dataclass
class Proposal:
    text: str
    src_dealer: str
    dst_dealer: str
    area_desc: str            # 片区描述（决策对象的语义名）
    sub_rings: list           # 被划转片区多边形环列表 [[[lon,lat]…], …]
    stores: list              # 派生效果：随片区走的门店（可为空！）
    pieces: list = field(default_factory=list)   # 被划转的 S 片号
    impact: dict = field(default_factory=dict)
    parser: str = "rules"


# ---------- TerritoryIR 数据接入（惰性加载） ----------

_DATA_DIR: Path | None = None
_TC = None
_ROWS: list | None = None
_STREET_DISTRICT: dict | None = None
_LOCK = threading.Lock()


def set_data_dir(data_dir) -> None:
    """服务端 pack 加载后注入数据目录（region/compiled 同目录）。"""
    global _DATA_DIR, _ROWS
    _DATA_DIR = Path(data_dir)
    _ROWS = None


def _tc():
    """惰性导入 territory_compile：提供 U 统一铺盖与街道面。首次 ~8s。"""
    global _TC
    if _TC is None:
        import sys
        tools_dir = Path(__file__).resolve().parent.parent / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        with _LOCK:
            if _TC is None:
                _TC = __import__("territory_compile")
    return _TC


def _rows() -> list:
    global _ROWS
    if _ROWS is None:
        if _DATA_DIR is None:
            raise AdjustError("adjust 未初始化数据目录（set_data_dir）")
        path = _DATA_DIR / "territory_compiled.json"
        if not path.exists():
            raise AdjustError("缺少 territory_compiled.json（先跑 tools/territory_compile.py）")
        _ROWS = json.loads(path.read_text(encoding="utf-8"))
    return _ROWS


def _row_of(dealer: str) -> dict:
    hit = next((r for r in _rows() if r.get("dealer") == dealer), None)
    if hit is None or not hit.get("S"):
        raise AdjustError(
            f"{dealer[:14]} 没有TerritoryIR编译结果（S片为空）——"
            "该经销商无法参与区域调整")
    return hit


def _street_district_map() -> dict:
    """street → district（官方2675单元属性众数）。"""
    global _STREET_DISTRICT
    if _STREET_DISTRICT is None:
        path = (_DATA_DIR or Path("data/gz")) / "unit_attributes.json"
        m: dict[str, Counter] = {}
        if path.exists():
            attrs = json.loads(path.read_text(encoding="utf-8"))
            for a in attrs:
                if a.get("street") and a.get("district"):
                    m.setdefault(a["street"], Counter())[a["district"]] += 1
        _STREET_DISTRICT = {k: v.most_common(1)[0][0] for k, v in m.items()}
    return _STREET_DISTRICT


def _piece_geom(k: int):
    return _tc().U[k][0]


def _pieces_union(pieces: set):
    """S 片并集（保留 MultiPolygon——不连续领地绝不能截成最大块）。"""
    geoms = [_piece_geom(k) for k in sorted(pieces)]
    return unary_union(geoms)


# ---------- 几何工具（沿用 v1） ----------

def _ring_of(poly: Polygon):
    if poly.is_empty:
        return ()
    pts = list(poly.exterior.coords)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return tuple((round(x, 7), round(y, 7)) for x, y in pts)


def _fence_poly(f: Fence) -> Polygon:
    if not f.ring:
        return Polygon()
    return Polygon(f.ring)


def _fence_union(world: World, dealer: str) -> Polygon:
    fs = world.fences_of(dealer)
    polys = [_fence_poly(f) for f in fs if _fence_poly(f).area > 0]
    return unary_union(polys) if len(polys) > 1 else (polys[0] if polys else Polygon())


def _rings_of_geom(g) -> list:
    out = []
    if g is None or g.is_empty:
        return out
    if g.geom_type == "GeometryCollection":
        for q in g.geoms:
            out.extend(_rings_of_geom(q))
    elif g.geom_type == "MultiPolygon":
        for q in g.geoms:
            out.extend(_rings_of_geom(q))
    elif g.geom_type == "Polygon":
        pts = list(g.exterior.coords)
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        out.append([[round(x, 6), round(y, 6)] for x, y in pts])
    return out


# ---------- 片区选择（单元片版） ----------

_HALF_WORDS = {"东": "east", "南": "south", "西": "west", "北": "north",
               "东边": "east", "南边": "south", "西边": "west", "北边": "north",
               "东部": "east", "南部": "south", "西部": "west", "北部": "north",
               "东侧": "east", "南侧": "south", "西侧": "west", "北侧": "north",
               "东半区": "east", "南半区": "south", "西半区": "west",
               "北半区": "north"}


def select_area_pieces(world: World, dealer: str, selector: str
                       ) -> tuple[set, str]:
    """selector → (被选中的 S 片集合, 语义名)。全部落在 src 的 S 片内。"""
    src = _row_of(dealer)
    allp = set(src["S"])
    sel = (selector or "全部").strip()

    if sel in ("全部", "整体", "所有", "", "不做了", "退出", "整个区域", "整个"):
        return allp, "整个区域"

    half = _HALF_WORDS.get(sel)
    if half and sel[:1] in "东南西北":
        fp = _pieces_union(allp)
        c = fp.centroid
        picked = set()
        for k in allp:
            pc = _piece_geom(k).centroid
            if half == "east" and pc.x >= c.x: picked.add(k)
            elif half == "west" and pc.x < c.x: picked.add(k)
            elif half == "north" and pc.y >= c.y: picked.add(k)
            elif half == "south" and pc.y < c.y: picked.add(k)
        if not picked:
            raise AdjustError(f"「{sel}」没有命中任何单元片")
        return picked, f"{sel[:1]}部半区"

    # 街道名（片的主街道标签 或 所在街道面）
    tc = _tc()
    hit_street = {k for k in allp if tc.U[k][1] == sel or tc.U[k][2] == sel}
    if hit_street:
        return hit_street, f"{sel}片区"

    # 区名 → street→district 反查
    sd = _street_district_map()
    streets = [st for st, d in sd.items() if d == sel or d == sel.replace("区", "")]
    if streets:
        ss = set(streets)
        hit = {k for k in allp if tc.U[k][1] in ss or tc.U[k][2] in ss}
        if hit:
            return hit, f"{sel}片区"

    # OOF 类是门店派生层概念，明确拒绝
    if sel in ("OOF", "跨界", "跨界供货", "非围栏供货", "错位", "错位片区"):
        raise AdjustError("OOF 片区属门店派生层，IR 调整模式不支持（请按街道/半区表达）")

    areas = sorted({sd.get(tc.U[k][1], "") for k in allp} -
                   {""} | {tc.U[k][1] for k in allp})
    raise AdjustError(
        f"无法识别片区「{sel}」。可用：整个区域 / 东南西北半区 / "
        f"街道名（此区域有：{'、'.join(sorted({tc.U[k][1] for k in allp})[:6])}）/"
        f"区名（{'、'.join(sorted(set(sd.get(tc.U[k][1], '') for k in allp) - {''})[:4])}）")


# ---------- 影响评估（片为主，门店为派生信号） ----------

def _dealer_piece_view(world: World, dealer: str, pieces: set) -> dict:
    fp = _fence_union(world, dealer)
    stores = [s for s in world.fence_stores(
        world.fence_by_dealer.get(dealer)) ] if dealer in world.fence_by_dealer else []
    area = km2(_pieces_union(pieces)) if pieces else 0.0
    return {"pieces": len(pieces),
            "km2": round(area, 2),
            "stores": len(stores),
            "kinds": dict(Counter(s.kind for s in stores).most_common()),
            "density_per_km2": round(len(stores) / area, 1) if area else 0}


def _piece_impact(world: World, src: Fence, dst: Fence,
                  moved_pieces: set, moved_stores: list,
                  kb: KnowledgeBase) -> dict:
    src_row = _row_of(src.dealer)
    dst_row = next((r for r in _rows() if r.get("dealer") == dst.dealer), {"S": []})
    after_src = set(src_row["S"]) - moved_pieces
    after_dst = set(dst_row.get("S") or []) | moved_pieces

    moved_detail = []
    for k in sorted(moved_pieces)[:10]:
        g = _piece_geom(k)
        moved_detail.append({"piece": k,
                             "street": _tc().U[k][1],
                             "km2": round(km2(g), 3)})
    for s in moved_stores[:6]:
        moved_detail.append({"store": s.name, "district": s.district,
                             "upstream": s.upstream, "kind": s.kind})

    signals = [
        {"signal": f"IR 区域划转（决策对象=单元片）：{src.dealer[:14]} "
                   f"{len(moved_pieces)} 片（{round(km2(_pieces_union(moved_pieces)), 2)} km²）"
                   f"→ {dst.dealer[:14]}；围栏=片并集视图，店随区域走（派生层）",
         "spec_ref": "世界模型 F2 可干预 · F3 派生"},
        {"signal": "I-D 契约版本 +1（E6 围栏变更事件，走 GW 审批）",
         "spec_ref": "PROPOSAL_v1.3 §3"},
        {"signal": "I-B 需重估：涉事片区的 beat 归属与频率（Layer-B 责任）",
         "spec_ref": "PROPOSAL_v1.3 §3 层间纪律"},
    ]
    if not moved_stores:
        signals.append({"signal": "本片区无门店数据：纯几何划转，"
                                  "供货影响待门店层补全后重估",
                        "spec_ref": "F3 派生（信息性）"})
    risks = [
        kb.cite("K-PRIN-002"),
        kb.cite("K-PRIN-003"),
        kb.cite("K-RULE-006"),
    ]
    gaps_kb = kb.gaps
    if gaps_kb:
        risks.append({"kb_id": "KNOWLEDGE-GAP", "type": "gap",
                      "statement": f"业务口径待确认 {len(gaps_kb)} 项（客情量化等），"
                                   "影响置信度标注", "source": "knowledge_base"})
    evidence = [
        {"data_ref": f"moved_pieces={len(moved_pieces)} "
                     f"source {len(src_row['S'])}→{len(after_src)}片; "
                     f"target {len(dst_row.get('S') or [])}→{len(after_dst)}片"},
        {"data_ref": f"moved stores（派生）: {len(moved_stores)}"},
        kb.cite("K-CONST-002"),
    ]
    KnowledgeBase.validate_chain(evidence + risks)
    moved_kind_delta = {}
    if moved_stores:
        for s in moved_stores:
            new_dealers = tuple(d for d in s.dealers if d != src.dealer) + (dst.dealer,)
            new_kind = world.reclassify(s, new_dealers)
            moved_kind_delta[f"{s.kind} → {new_kind}"] = \
                moved_kind_delta.get(f"{s.kind} → {new_kind}", 0) + 1
    return {
        "action": f"将 {len(moved_pieces)} 个单元片（"
                  f"{round(km2(_pieces_union(moved_pieces)), 2)} km²）"
                  f"从「{src.dealer}」划入「{dst.dealer}」",
        "source_after": _dealer_piece_view(world, src.dealer, after_src),
        "target_after": _dealer_piece_view(world, dst.dealer, after_dst),
        "moved_sample": moved_detail,
        "moved_kind_delta": moved_kind_delta,
        "signals": signals,
        "risks": risks,
        "evidence": evidence,
        "materiality": "Review",
        "_after_sets": {"src": sorted(after_src), "dst": sorted(after_dst)},
    }


# ---------- 指令解析（文本层与 v1 完全一致） ----------

def _match_dealer(world: World, name: str):
    name = str(name).strip().strip("「」\"'")
    for suf in ("的门店", "的店", "的围栏", "的店都", "门店", "所有店", "经销商", "区域"):
        if name.endswith(suf):
            name = name[: -len(suf)]
    name = name.strip()
    hits = []
    for d in {f.dealer for f in world.fences}:
        if name and name in d:
            hits.append(d)
    if not hits:
        raise AdjustError(f"找不到经销商「{name[:14]}」")
    if len(hits) > 1:
        exact = [h for h in hits if h == name]
        if exact:
            hits = exact
        else:
            raise AdjustError(f"「{name[:10]}」匹配到 {len(hits)} 家经销商，请写全称")
    f = world.fence_by_dealer[hits[0]]
    return f


def build_proposal(world: World, kb: KnowledgeBase, text: str,
                   src: Fence, dst: Fence, selector: str,
                   parser: str = "rules") -> Proposal:
    if src.dealer == dst.dealer:
        raise AdjustError("source 与 target 是同一经销商")
    sel = (selector or "全部").strip()
    for fill in ("片区", "区域", "部分", "范围"):
        cand = sel.replace(fill, "").strip()
        if cand:
            sel = cand
    moved_pieces, area_desc = select_area_pieces(world, src.dealer, sel)
    moved_union = _pieces_union(moved_pieces)
    sub_rings = _rings_of_geom(moved_union)

    # 派生效果层：片区内 src 门店（可为空，绝不报错）
    moved = [s for s in world.fence_stores(src)
             if moved_union.contains(Point(s.lon, s.lat))
             or moved_union.touches(Point(s.lon, s.lat))]
    impact = _piece_impact(world, src, dst, moved_pieces, moved, kb)
    impact["area"] = {
        "area_desc": area_desc,
        "sub_km2": round(km2(moved_union), 2),
        "sub_pieces": len(moved_pieces),
        "src_pieces": [len(_row_of(src.dealer)["S"]),
                       len(impact["_after_sets"]["src"])],
        "dst_pieces": [len(next((r for r in _rows()
                                 if r.get("dealer") == dst.dealer), {"S": []})["S"]),
                       len(impact["_after_sets"]["dst"])],
        "src_stores": [len(world.fence_stores(src)),
                       len(world.fence_stores(src)) - len(moved)],
        "dst_stores": [len(world.fence_stores(dst)),
                       len(world.fence_stores(dst)) + len(moved)],
    }
    return Proposal(text=text, src_dealer=src.dealer, dst_dealer=dst.dealer,
                    area_desc=area_desc,
                    sub_rings=sub_rings,
                    stores=moved, pieces=sorted(moved_pieces),
                    impact=impact, parser=parser)


def parse_and_propose(world: World, kb: KnowledgeBase, text: str) -> Proposal:
    t = text.strip()
    src_name = dst_name = sel = None
    for pat in (
        r"把(.+?)的(.+?)划给(.+)",
        r"把(.+?)的(.+?)调整给(.+)",
        r"把(.+?)的(.+?)移交(?:给)?(.+)",
        r"把(.+?)在(.+?)的门店划给(.+)",
        r"把(.+?)整体并入(.+)",
        r"把(.+?)划给(.+)",
        r"^(.+?)不(?:做|干)了[，,]?(?:区域|店|门店|全部|都)?(?:都给|都划给|并入|交给|给)(.+)",
    ):
        m = re.search(pat, t)
        if not m:
            continue
        g = m.groups()
        if len(g) == 3:
            src_name, sel, dst_name = g
        elif "不" in t[:20]:
            src_name, dst_name, sel = g[0], g[1], "全部"
        else:
            src_name, dst_name, sel = g[0], g[1], "全部"
        break
    if not src_name:
        raise AdjustError(
            "无法解析区域调整指令。试试：把@A 的东部片区划给 @B、"
            "@A 不做了区域都给 @B、把 @A 的增城区划给 @B")
    src = _match_dealer(world, src_name)
    dst = _match_dealer(world, dst_name)
    if src.dealer == dst.dealer:
        raise AdjustError("source 与 target 是同一经销商")
    return build_proposal(world, kb, t, src, dst, sel, "rules")


# ---------- 应用（几何手术 + 派生层同步） ----------

def _sync_compiled_sets(proposal: Proposal) -> None:
    """territory_compiled.json 的 S 集合同步增删（调整后描述需重编译）。"""
    if _DATA_DIR is None or not proposal.pieces:
        return
    path = _DATA_DIR / "territory_compiled.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    moved = set(proposal.pieces)
    for r in rows:
        if r.get("dealer") == proposal.src_dealer:
            r["S"] = sorted(set(r["S"]) - moved)
        elif r.get("dealer") == proposal.dst_dealer:
            r["S"] = sorted(set(r.get("S") or []) | moved)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                    encoding="utf-8")


def apply_proposal(world: World, proposal: Proposal) -> World:
    """单元片手术：src 围栏 − 划转片并集；dst 围栏 ∪ 划转片并集。
    门店归属随「新围栏包含关系」重算（派生层，可为空）。"""
    sub = unary_union([Polygon(r) for r in proposal.sub_rings if len(r) >= 3])

    # 派生层：旧 src 围栏内、且落在划转几何内的门店 → 归属改挂 dst
    moved_ids = set()
    for st in world.stores:
        if proposal.src_dealer in st.dealers and sub.contains(Point(st.lon, st.lat)):
            moved_ids.add(id(st))
    new_stores = []
    for st in world.stores:
        if id(st) in moved_ids:
            nd = tuple(d for d in st.dealers
                       if d != proposal.src_dealer) + (proposal.dst_dealer,)
            new_stores.append(Store(st.name, st.category, st.district,
                                    st.upstream, st.lon, st.lat, st.direct,
                                    nd, world.reclassify(st, nd)))
        else:
            new_stores.append(st)
    w2 = world.with_stores(new_stores)

    # 决策层：围栏几何手术（不再用门店凸包重建）
    #   src: 原手绘几何 ∩ 剩余S片并集（片清空 → 围栏清空，杜绝边缘残渣）
    #   dst: 原几何 ∪ 划转几何
    after_src = set(_row_of(proposal.src_dealer)["S"]) - set(proposal.pieces)
    new_fences = [f for f in w2.fences
                  if f.dealer not in (proposal.src_dealer, proposal.dst_dealer)]
    for dealer, op in ((proposal.src_dealer, "sub"),
                       (proposal.dst_dealer, "union")):
        origs = [f for f in world.fences if f.dealer == dealer]
        if not origs:
            continue
        geom = unary_union([_fence_poly(f) for f in origs])
        if op == "sub":
            geom = (geom.intersection(_pieces_union(after_src))
                    if after_src else None)
        else:
            geom = unary_union([geom, sub])
        if geom is None or geom.is_empty or geom.area <= 0:
            continue  # 该经销商围栏清空（区域全部划出）
        polys = (list(geom.geoms) if geom.geom_type == "MultiPolygon"
                 else [geom])
        polys.sort(key=lambda g: -g.area)
        base_id = origs[0].area_id
        for i, poly in enumerate(polys):
            tag = "" if i == 0 else f"-{i + 1}"
            new_fences.append(Fence(f"{base_id}{tag}", dealer,
                                    round(km2(poly), 2), _ring_of(poly)))
    w2 = w2.with_fences(new_fences)
    _sync_compiled_sets(proposal)
    return w2
