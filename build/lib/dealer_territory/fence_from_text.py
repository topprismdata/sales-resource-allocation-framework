"""从四至文字描述【精确重建围栏】（文字 → 围栏）。

输入（合同级语言）：
    "西至陈村水道，北至珠江后航道，东至市桥水道，南至顺德水道。"
    + 中心点提示（如 区域质心/办事处位置）
输出：围栏多边形（边界贴附真实河道/道路/区界的弯曲）

方法：
1. parse_four_bounds_text  正则抽取四个方向的地标名
2. lookup_geometry         从 OSM 解析数据查地标几何（河流/道路=折线；区=多边形边界）
3. build_fence_from_bounds
     a. 每条界线：取距中心点最近点为锚，向两侧扩至半径 R，得截段
     b. 四角 = 相邻界线截段端点的最近点对
     c. 沿截段保留中间顶点（河道/道路的真实弯曲），按 西→北→东→南 组环闭合
4. evaluate_roundtrip      重建围栏 vs 原围栏：门店包含率 + 网格 IoU

纯 stdlib。R（区域半径）由调用方给：无提示时默认 5km，
有街道清单/门店点云时可用点云距中心最大距离。
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

_LON_KM, _LAT_KM = 102.2, 110.574
DIRS = ("西", "北", "东", "南")


# ---------- 文本解析 ----------

def parse_four_bounds_text(text: str) -> dict[str, str]:
    """'西至陈村水道，北至珠江后航道…' -> {"西": "陈村水道", ...}"""
    out = {}
    for m in re.finditer(r"([东西南北])至([^，。；、\n]+)", text):
        d, name = m.group(1), m.group(2).strip()
        if d in DIRS and name:
            out[d] = name
    return out


# ---------- 地标几何 ----------

def _seg_pts(segs: list[list[tuple[float, float]]]) -> list[tuple[float, float]]:
    pts = []
    for seg in segs:
        for p in seg:
            if p not in pts[-1:] if pts else True:
                pts.append(p)
    return pts


def _dist_km(a, b) -> float:
    return math.hypot((a[0] - b[0]) * _LON_KM, (a[1] - b[1]) * _LAT_KM)


def lookup_geometry(name: str, osm_parsed: dict, center=None) -> list[list[tuple[float, float]]]:
    """地标名 -> 折线段集合（容错：精确 -> 去"珠江"前缀 -> 包含匹配+就近消歧）。

    河流/主干道=折线；区县=多边形外环。
    """
    rivers = osm_parsed.get("rivers", {})
    roads = osm_parsed.get("roads", {})
    refs = osm_parsed.get("refs", {})
    dv = osm_parsed.get("districts", {}).get(name)
    if dv:
        return [poly + [poly[0]] for poly in dv["polys"]]
    if name in refs:
        return refs[name]
    for r, segs in refs.items():
        if name in r:
            return segs
    if name in rivers:
        return rivers[name]
    if name in roads:
        return roads[name]
    alt = name.replace("珠江", "")
    if alt in rivers:
        return rivers[alt]
    if alt in roads:
        return roads[alt]
    pool = list(roads.items()) + list(rivers.items())
    cands = [(nm, segs) for nm, segs in pool if name in nm or nm in name]
    if not cands and len(name) >= 2:
        pre = name[:2]
        cands = [(nm, segs) for nm, segs in pool if nm.startswith(pre) or name.startswith(nm[:2])]
    if cands:
        if center:
            def mind(segs):
                return min((p[0] - center[0]) ** 2 + (p[1] - center[1]) ** 2
                           for seg in segs for p in seg)
            cands.sort(key=lambda c: mind(c[1]))
        return cands[0][1]
    return []


# ---------- 界线截段 ----------

def _clip_line_to_radius(segs, center, radius_km):
    """取折线(可多段)上距 center<=radius 的连续部分；返回按沿线顺序的点列。

    锚点 = 全线距 center 最近的点所在段；从锚点向两端扩展。
    """
    best = (1e18, 0, 0)  # (d2, seg_idx, pt_idx)
    for si, seg in enumerate(segs):
        for pi, p in enumerate(seg):
            d2 = _dist_km(p, center) ** 2
            if d2 < best[0]:
                best = (d2, si, pi)
    if best[0] > (radius_km * 3) ** 2:
        return []
    si, pi = best[1], best[2]
    seg = segs[si]
    r2 = radius_km ** 2
    fwd = [seg[pi]]
    for p in seg[pi + 1:]:
        if _dist_km(p, center) > radius_km:
            break
        fwd.append(p)
    bwd = []
    for p in reversed(seg[:pi]):
        if _dist_km(p, center) > radius_km:
            break
        bwd.append(p)
    line = list(reversed(bwd)) + fwd
    # 相邻段的延续（同端点衔接）
    remain = [s for k, s in enumerate(segs) if k != si]
    end = line[-1]
    changed = True
    used = set()
    while changed:
        changed = False
        for k, seg2 in enumerate(remain):
            if k in used:
                continue
            if seg2 and seg2[0] == end and _dist_km(seg2[0], center) <= radius_km:
                for p in seg2[1:]:
                    if _dist_km(p, center) > radius_km:
                        changed = False
                        break
                    line.append(p); end = p
                used.add(k); changed = True
                break
            if seg2 and seg2[-1] == end and _dist_km(seg2[-1], center) <= radius_km:
                for p in reversed(seg2[:-1]):
                    if _dist_km(p, center) > radius_km:
                        changed = False
                        break
                    line.append(p); end = p
                used.add(k); changed = True
                break
    return line


def _sub_by_ratio(line, fr: float, to: float) -> list[tuple[float, float]]:
    """折线按累积长度归一化截取 [fr, to] 比例区间子段（保留真实弯曲）。"""
    if len(line) < 2:
        return line[:]
    cum = [0.0]
    for i in range(1, len(line)):
        cum.append(cum[-1] + _dist_km(line[i - 1], line[i]))
    total = cum[-1] or 1.0
    d0, d1 = min(fr, to) * total, max(fr, to) * total
    out = []
    for i, p in enumerate(line):
        if d0 <= cum[i] <= d1:
            out.append(p)
    if not out:
        out = [line[0], line[-1]]
    return out


def _endpoints(line):
    if not line:
        return None, None
    return line[0], line[-1]


def _closest_pair(line_a, line_b):
    best = (1e18, None, None)
    for pa in line_a:
        for pb in line_b:
            d = _dist_km(pa, pb)
            if d < best[0]:
                best = (d, pa, pb)
    mid = ((best[1][0] + best[2][0]) / 2, (best[1][1] + best[2][1]) / 2) if best[1] else None
    return best[0], mid


# ---------- 围栏构建 ----------

def _closest_pair(line_a, line_b):
    best = (1e18, None, None)
    for pa in line_a:
        for pb in line_b:
            d = _dist_km(pa, pb)
            if d < best[0]:
                best = (d, pa, pb)
    return best


@dataclass
class RebuiltFence:
    dealer: str
    ring: list[tuple[float, float]]
    lines_used: dict[str, int]
    area_km2: float = 0.0


def build_fence_from_bounds(
    bounds: dict[str, str],
    center: tuple[float, float],
    osm_parsed: dict,
    radius_km: float = 5.0,
    dealer: str = "重建围栏",
) -> RebuiltFence:
    """四至地标 + 中心点 → 围栏多边形。

    步骤：
    1. lookup_geometry 取四条界线（精确/归一/包含+就近消歧）
    2. 相邻界线（西-北 / 北-东 / 东-南 / 南-西）最近点对 = 四个角
    3. 每界取两角之间的子段（保留河道/道路真实弯曲）
    4. 按西->南->东->北 组环闭合
    """
    lines: dict[str, list[tuple[float, float]]] = {}
    for d in DIRS:
        nm = bounds.get(d)
        if not nm:
            continue
        segs = lookup_geometry(nm, osm_parsed, center)
        if len(segs) >= 1 and sum(len(s) for s in segs) >= 2:
            lines[d] = [p for seg in segs for p in seg]
    if len(lines) < 3:
        raise ValueError(f"可用界线不足（{list(lines)}），至少需要 3 条")

    # 相邻界对 -> 角（最近点对中点）
    def corner(d1, d2):
        d, pa, pb = _closest_pair(lines[d1], lines[d2])
        return ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2), d

    (nw, e1), (ne, e2), (se, e3), (sw, e4) = (
        corner("西", "北"), corner("北", "东"), corner("东", "南"), corner("南", "西"))

    def sub_between(line, pa, pb):
        ia = min(range(len(line)), key=lambda i: _dist_km(line[i], pa))
        ib = min(range(len(line)), key=lambda i: _dist_km(line[i], pb))
        if ia <= ib:
            return line[ia:ib + 1]
        return list(reversed(line[ib:ia + 1]))

    west = sub_between(lines["西"], nw, sw)
    south = sub_between(lines["南"], sw, se)
    east = sub_between(lines["东"], se, ne)
    north = sub_between(lines["北"], ne, nw)

    ring = west + south[1:] + east[1:] + north[1:]
    dedup = [ring[0]]
    for p in ring[1:]:
        if p != dedup[-1]:
            dedup.append(p)
    if dedup[0] != dedup[-1]:
        dedup.append(dedup[0])

    area = _shoelace_km2(dedup[:-1])
    return RebuiltFence(dealer=dealer, ring=dedup,
                        lines_used={d: len(v) for d, v in lines.items()},
                        area_km2=area)


def _shoelace_km2(ring) -> float:
    s = 0.0
    lat_ref = sum(p[1] for p in ring) / len(ring)
    px = [p[0] * _LON_KM * math.cos(math.radians(lat_ref)) for p in ring]
    py = [p[1] * _LAT_KM for p in ring]
    for i in range(len(ring)):
        j = (i + 1) % len(ring)          # 闭合边：末点→首点（缺失会虚增上万 km²）
        s += px[i] * py[j] - px[j] * py[i]
    return abs(s) / 2


# ---------- 重建评估 ----------

def _pip(pt, ring, bbox) -> bool:
    x, y = pt
    x0, y0, x1, y1 = bbox
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def evaluate_roundtrip(
    rebuilt_ring, original_ring, stores: list[tuple[float, float]] | None = None,
    grid_km: float = 0.5,
) -> dict:
    """重建 vs 原围栏：门店包含率 + 网格 IoU + 面积。"""
    rb = (min(p[0] for p in rebuilt_ring), min(p[1] for p in rebuilt_ring),
          max(p[0] for p in rebuilt_ring), max(p[1] for p in rebuilt_ring))
    ob = (min(p[0] for p in original_ring), min(p[1] for p in original_ring),
          max(p[0] for p in original_ring), max(p[1] for p in original_ring))

    res = {}
    if stores:
        in_orig = in_re = both = 0
        for pt in stores:
            io = _pip(pt, original_ring, ob)
            ir = _pip(pt, rebuilt_ring, rb)
            in_orig += io
            in_re += ir
            both += io and ir
        res["stores_in_original"] = in_orig
        res["stores_in_rebuilt"] = in_re
        res["store_containment_rate"] = round(both / in_orig, 4) if in_orig else None

    # 网格 IoU（在联合 bbox 内）
    gx0, gx1 = min(ob[0], rb[0]), max(ob[2], rb[2])
    gy0, gy1 = min(ob[1], rb[1]), max(ob[3], rb[3])
    lat_ref = (gy0 + gy1) / 2
    dlon = grid_km / (_LON_KM * math.cos(math.radians(lat_ref)))
    dlat = grid_km / _LAT_KM
    inter = uni = 0
    la = gy0
    while la <= gy1:
        lo = gx0
        while lo <= gx1:
            pt = (lo, la)
            a = _pip(pt, original_ring, ob)
            b = _pip(pt, rebuilt_ring, rb)
            if a or b:
                uni += 1
            if a and b:
                inter += 1
            lo += dlon
        la += dlat
    iou = inter / uni if uni else 0.0
    res["grid_iou"] = round(iou, 4)
    res["rebuilt_area_km2"] = round(_shoelace_km2(rebuilt_ring[:-1]), 2)
    res["original_area_km2"] = round(_shoelace_km2(original_ring[:-1]), 2)
    return res


# ---------- 按「地标+比例」构建（LLM/agentic 输出的落地形态） ----------

def build_from_landmark_ratios(
    dealer: str,
    spec: dict[str, tuple[str, float, float]],
    center: tuple[float, float],
    osm_parsed: dict,
) -> dict:
    """spec: {方向: (地标名, 沿线起点比例, 沿线终点比例)}。

    返回 {"ring": ..., "area_km2": ..., "iou_grid": ..., "containment": ...,
          "lines": {方向: 子段}, "missing": [方向]}。
    纯几何；spec 的比例由上层（LLM/agentic）给出，本函数负责确定性构建。
    """
    lines: dict[str, list] = {}
    missing = []
    for d, (nm, fr, to) in spec.items():
        segs = lookup_geometry(nm, osm_parsed, center)
        if not segs:
            missing.append((d, nm))
            continue
        allp = [p for seg in segs for p in seg]
        anchor = min(allp, key=lambda p: (p[0] - center[0]) ** 2 + (p[1] - center[1]) ** 2)
        line = []
        for seg in segs:
            if anchor in seg:
                line = seg
                break
        if not line:
            line = max(segs, key=len)
        sub = _sub_by_ratio(line, fr, to)
        if len(sub) >= 2:
            lines[d] = sub
    if len(lines) < 3:
        return {"error": f"可用界线不足 {list(lines)}", "missing": missing}
    for need in ("西", "北", "东", "南"):
        if need not in lines:
            return {"error": f"缺 {need} 界，环无法闭合（有 {list(lines)}）",
                    "missing": missing}

    def corner(d1, d2):
        best = (1e18, None, None)
        for pa in lines[d1]:
            for pb in lines[d2]:
                dd = _dist_km(pa, pb)
                if dd < best[0]:
                    best = (dd, pa, pb)
        return (best[1][0] + best[2][0]) / 2, (best[1][1] + best[2][1]) / 2

    nw, ne = corner("西", "北"), corner("北", "东")
    se, sw = corner("东", "南"), corner("南", "西")

    def sub_ab(line, pa, pb):
        ia = min(range(len(line)), key=lambda i: _dist_km(line[i], pa))
        ib = min(range(len(line)), key=lambda i: _dist_km(line[i], pb))
        if ia <= ib:
            return line[ia:ib + 1]
        return list(reversed(line[ib:ia + 1]))

    ring = (sub_ab(lines["西"], nw, sw) + sub_ab(lines["南"], sw, se)[1:]
            + sub_ab(lines["东"], se, ne)[1:] + sub_ab(lines["北"], ne, nw)[1:])
    dedup = [ring[0]]
    for p in ring[1:]:
        if p != dedup[-1]:
            dedup.append(p)
    if dedup[0] != dedup[-1]:
        dedup.append(dedup[0])

    if len(dedup) < 4:
        return {"error": f"重建退化（环点 {len(dedup)}），需人工解释",
                "missing": missing}
    area = _shoelace_km2(dedup[:-1])
    return {"ring": dedup, "area_km2": round(area, 2),
            "lines": {d: len(v) for d, v in lines.items()}, "missing": missing}
