"""区域调整（区域优先：片区是决策对象，门店归属是附带效果）。

本体立场（世界模型）：
  可决策对象 = TerritoryDesign 围栏（F2 片区）
  派生效果   = 门店归属（F3 供货足迹）——CRM 里改门店是数据同步，
              业务调整的对象是【区域】，店随区域走。

指令形态（区域优先）：
  把 <src> 的 <片区> 划给 <dst>
  把 <src> 整体并入 <dst>
  <src> 不做了，区域都给 <dst>
片区选择器（对门店点集判断，不做围栏切割）：
  全部/整体/不做了/退出   → 整个区域
  东/南/西/北 半区        → 质心经/纬度切半
  <区/街道名>            → 该经销商在此区/街道的门店集合
  OOF/跨界/错位           → 供货错位门店集合
  <门店名>周边           → 该店附近 ~1.2km 门店群

几何：逻辑合并（D11）。门店归属=唯一事实；围栏=经销商门店凸包的
派生视图，应用后仅重算 src/dst 两块。km² 为统计视图不参与守恒。
层间纪律：只产生 Layer-D 提案；I-B/I-V 以 Signal 表达。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from shapely.geometry import Point, Polygon

from .impact import move_impact


def km2(g) -> float:
    """deg² → km²：按质心纬度换算（1°lat≈110.574，1°lon≈111.320·cos(lat)）。"""
    from math import cos, radians
    lat = g.centroid.y if not g.is_empty else 23.1
    return g.area * 110.574 * 111.320 * cos(radians(lat))
from .knowledge import KnowledgeBase
from .world import Fence, Store, World

HALF_BOX = 2.0   # 度，足够大的半平面框


class AdjustError(ValueError):
    pass


@dataclass
class Proposal:
    text: str
    src_dealer: str
    dst_dealer: str
    area_desc: str            # 片区描述（决策对象的语义名）
    sub_ring: list            # 被划转片区多边形 [[lon,lat]…]
    stores: list              # 随片区走的门店（效果）
    impact: dict = field(default_factory=dict)
    parser: str = "rules"


# ---------- 经销商匹配 ----------

def _match_dealer(world: World, name: str):
    name = str(name).strip().strip("「」\"'")
    for suf in ("的门店", "的店", "的围栏", "的店都", "门店", "所有店", "经销商", "区域"):
        if name.endswith(suf):
            name = name[: -len(suf)]
    name = name.strip()
    seen, hits = set(), []
    for f in world.fences:
        if name and name in f.dealer and f.dealer not in seen:
            seen.add(f.dealer)
            hits.append(f)
    if len(hits) == 1:
        return hits[0]
    if len(name) < 3:
        raise AdjustError(f"经销商名太短：「{name}」，请写至少 3 个字")
    if not hits:
        cands = sorted({f.dealer[:14] for f in world.fences})[:8]
        raise AdjustError(f"找不到经销商「{name}」。示例: {'、'.join(cands)} …")
    raise AdjustError(f"「{name}」匹配到 {len(hits)} 家，请写更全: "
                      + "、".join(h.dealer[:14] for h in hits[:5]))


def _fence_poly(f: Fence) -> Polygon:
    pts = list(f.ring)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    p = Polygon(pts)
    if not p.is_valid:
        p = p.buffer(0)
    return p


def _hull(stores) -> Polygon:
    """逻辑围栏 = 该经销商门店点集的凸包（派生视图，非物理切割）。"""
    pts = [(st.lon, st.lat) for st in stores]
    if len(pts) < 3:
        return Polygon()
    return Polygon(pts).convex_hull

def _ring_of(poly: Polygon):
    if poly.is_empty:
        return ()
    pts = list(poly.exterior.coords)
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return tuple((round(x, 7), round(y, 7)) for x, y in pts)


# ---------- 片区选择（几何） ----------

def select_area(world: World, src: Fence, selector: str
                ) -> tuple[Polygon, str]:
    """selector → (片区多边形, 语义名)。多边形保证落在 src 围栏内。"""
    fp = _fence_poly(src)
    sel = (selector or "全部").strip()
    stores = world.fence_stores(src)

    if sel in ("全部", "整体", "所有", "", "不做了", "退出", "整个区域", "整个"):
        return fp, "整个区域"

    # 半区
    HALF_WORDS = {"东": "east", "南": "south", "西": "west", "北": "north",
                  "东边": "east", "南边": "south", "西边": "west", "北边": "north",
                  "东部": "east", "南部": "south", "西部": "west", "北部": "north",
                  "东侧": "east", "南侧": "south", "西侧": "west", "北侧": "north",
                  "东半区": "east", "南半区": "south", "西半区": "west",
                  "北半区": "north"}
    half = HALF_WORDS.get(sel)
    if half and sel[:1] in "东南西北":
        c = fp.centroid
        L, lat0, lon0 = HALF_BOX, c.y, c.x
        if half == "east":
            box = Polygon([(lon0, lat0 - L), (lon0 + L, lat0 - L),
                           (lon0 + L, lat0 + L), (lon0, lat0 + L)])
        elif half == "west":
            box = Polygon([(lon0 - L, lat0 - L), (lon0, lat0 - L),
                           (lon0, lat0 + L), (lon0 - L, lat0 + L)])
        elif half == "north":
            box = Polygon([(lon0 - L, lat0), (lon0 + L, lat0),
                           (lon0 + L, lat0 + L), (lon0 - L, lat0 + L)])
        else:  # south
            box = Polygon([(lon0 - L, lat0 - L), (lon0 + L, lat0 - L),
                           (lon0 + L, lat0), (lon0 - L, lat0)])
        sub = fp.intersection(box)
        if sub.is_empty or sub.area < 1e-10:
            raise AdjustError(f"「{sel}」切分失败（区域过小或退化）")
        return sub, f"{sel[:1]}部半区"

    # OOF / 跨界片区
    if sel in ("OOF", "跨界", "跨界供货", "非围栏供货", "错位", "错位片区"):
        pts = [(s.lon, s.lat) for s in stores if s.kind == "OOF"]
        if len(pts) < 3:
            raise AdjustError("该区域内跨界供货（OOF）门店不足，无法成片区")
        hull = Polygon(pts).convex_hull
        sub = fp.intersection(hull)
        if sub.is_empty:
            raise AdjustError("OOF 片区与围栏无交集")
        return sub, "跨界供货片区"

    # 区/街道名（数据里 district 或地标）
    areas = sorted({s.district for s in stores if s.district})
    hit = [a for a in areas if a and (a in sel or sel in a)]
    if hit:
        a = hit[0]
        pts = [(s.lon, s.lat) for s in stores if s.district == a]
        if len(pts) < 3:
            raise AdjustError(f"{src.dealer[:10]} 在「{a}」的门店不足 3 家，无法成片区")
        hull = Polygon(pts).convex_hull
        sub = fp.intersection(hull)
        if sub.is_empty:
            raise AdjustError(f"「{a}」片区与围栏无交集")
        return sub, f"{a}片区"

    # 门店名周边（~1.2km 圆）
    near = [s for s in stores if sel in s.name]
    if near:
        x, y = near[0].lon, near[0].lat
        d = Point(x, y).buffer(1.2 / 111.0)
        sub = fp.intersection(d)
        if not sub.is_empty:
            return sub, f"「{sel[:8]}」周边片区"

    raise AdjustError(
        f"无法识别片区「{sel}」。可用：整个区域 / 东南西北半区 / "
        f"区或街道名（此区域有：{('、'.join(areas[:6]) or '无')}）/ OOF / 门店名周边")


# ---------- 指令解析 ----------

def build_proposal(world: World, kb: KnowledgeBase, text: str,
                   src: Fence, dst: Fence, selector: str,
                   parser: str = "rules") -> Proposal:
    sel = (selector or "全部").strip()
    for fill in ("片区", "区域", "部分", "范围"):
        cand = sel.replace(fill, "").strip()
        if cand:
            sel = cand
    sub, area_desc = select_area(world, src, sel)
    moved = [s for s in world.fence_stores(src)
             if sub.contains(Point(s.lon, s.lat))]
    if not moved:
        raise AdjustError(f"「{area_desc}」内没有 {src.dealer[:10]} 的门店")
    impact = move_impact(world, src, dst, moved, kb)
    sub_hull = _hull(moved)
    src_stores = world.fence_stores(src)
    dst_stores = world.fence_stores(dst)
    impact["area"] = {
        "area_desc": area_desc,
        "sub_km2": round(km2(sub_hull), 2),
        "src_km2": [round(km2(_hull(src_stores)), 2),
                    round(km2(_hull([x for x in src_stores if x not in moved])), 2)],
        "dst_km2": [round(km2(_hull(dst_stores)), 2),
                    round(km2(_hull(list(dst_stores) + moved)), 2)],
        "src_stores": [len(src_stores), len(src_stores) - len(moved)],
        "dst_stores": [len(dst_stores), len(dst_stores) + len(moved)],
    }
    impact["signals"].insert(0, {
        "signal": f"区域划转（决策对象=片区，逻辑合并）：{src.dealer[:14]} "
                  f"{area_desc}（{len(moved)} 店）→ {dst.dealer[:14]}；"
                  f"围栏=门店派生视图，归属随店走",
        "spec_ref": "世界模型 F2 可干预 · F3 派生；店随区域走，"
                    "非门店级 CRM 改动"})
    coords = list(sub_hull.exterior.coords) if not sub_hull.is_empty else []
    coords = list(sub.exterior.coords)
    return Proposal(text=text, src_dealer=src.dealer, dst_dealer=dst.dealer,
                    area_desc=area_desc,
                    sub_ring=[[round(x, 6), round(y, 6)] for x, y in coords],
                    stores=moved, impact=impact, parser=parser)


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
    if src.area_id == dst.area_id:
        raise AdjustError("source 与 target 是同一区域")
    return build_proposal(world, kb, t, src, dst, sel, "rules")


def apply_proposal(world: World, proposal: Proposal) -> World:
    """逻辑合并：门店归属 src→dst（唯一事实），
    两经销商围栏=各自门店凸包（派生视图）。无多边形手术、无碎片。"""
    moved_ids = {id(s) for s in proposal.stores}
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

    new_fences = [f for f in w2.fences
                  if f.dealer not in (proposal.src_dealer, proposal.dst_dealer)]
    for dealer in (proposal.src_dealer, proposal.dst_dealer):
        orig = next((f for f in world.fences if f.dealer == dealer), None)
        ds = [st for st in new_stores if dealer in st.dealers]
        hull = _hull(ds)
        if hull.is_empty or not ds:
            continue
        new_fences.append(Fence(orig.area_id if orig else dealer[:8],
                                dealer, round(km2(hull), 2), _ring_of(hull)))
    return w2.with_fences(new_fences)
