"""电子围栏的分配与【反向生成】（现状数据驱动）。

⚠️ 定位纪律（老板约束）：反向生成的结果必须【人类可理解】——
    面向人的主输出是"行政区划+地标"表述的区域清单（four_bounds.py），
    本文件的几何围栏仅是【系统用投影】（画图/校验/接口），
    不得把数学/地理斑块直接当业务交付。

问题（老板简化定义）：基于经销商情况 + 现有客户，做电子围栏的分配。

核心思路 = 【反向生成】：不从零优化划分，而是把"现状（哪些门店实际
由哪家经销商服务）+ 客户点云分布"反向翻译成区域归属与围栏。
围栏是分配结果的空间投影，而不是先验输入。

三层逻辑（现状优先）：
1. 分配 allocate   ：客户 → 经销商
     规则① 现状供货优先：上游客户是谁就归谁（市场的选择，最大真相）
     规则② 现有围栏兜底：无上游/上游不明 → 落在哪个现有围栏归谁
     规则③ 最近质心兜底：仍无 → 最近经销商（并标记为需人工确认）
     例外：excluded（KA 直供）不分配
2. 反向生成 generate：分配结果 → 电子围栏（系统用投影）
     栅格化 → 占用格边界追踪成环 → DP 简化；纯 stdlib
3. 对比 compare    ：生成围栏 vs 现行围栏 → 偏差即调整讨论证据
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EARTH_LAT_KM = 110.574


def _cell_size_deg(cell_size_km: float, lat_ref: float) -> float:
    return cell_size_km / (EARTH_LAT_KM * max(0.2, math.cos(math.radians(lat_ref))))


# ---------- 1. 分配 ----------

def allocate(
    store: dict,
    dealers: list[str],
    current_fences: list[dict] | None = None,
) -> tuple[str | None, str]:
    """返回 (dealer_id | None, rule)。store 需含 lon/lat/upstream/excluded。"""
    if store.get("excluded"):
        return None, "EXCLUDED"
    up = (store.get("upstream") or "").strip()
    if up and up in dealers:
        return up, "UPSTREAM"
    pt = (store["lon"], store["lat"])
    for f in current_fences or []:
        if _pip(pt, f["ring"], f["bbox"]):
            return f["dealer"], "CURRENT_FENCE"
    if dealers:
        best = min(
            dealers,
            key=lambda d: _dist(pt, _centroid_of(fences_of(d, current_fences or []))),
        )
        return best, "NEAREST_CENTROID"
    return None, "UNASSIGNED"


def fences_of(dealer: str, fences: list[dict]) -> list[dict]:
    return [f for f in fences if f["dealer"] == dealer]


def _centroid_of(fences: list[dict]) -> tuple[float, float]:
    pts = [p for f in fences for p in f["ring"]]
    if not pts:
        return (float("nan"), float("nan"))
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    if b != b or a != a:
        return float("inf")
    return math.hypot((a[0] - b[0]) * 102.2, (a[1] - b[1]) * 110.574)


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


# ---------- 2. 反向生成（系统用几何投影） ----------

@dataclass
class GeneratedFence:
    dealer: str
    rings: list[list[tuple[float, float]]]
    store_count: int
    cells: int


def generate_fence(
    dealer: str,
    points: list[tuple[float, float]],
    cell_size_km: float = 0.5,
    simplify_tolerance_km: float = 0.15,
    min_cells: int = 1,
) -> GeneratedFence | None:
    """客户点云 → 电子围栏（可能多个环=飞地）。

    栅格化(格宽 km) → 占用格集合 → 边界追踪成环 → DP 简化。
    """
    if not points:
        return None
    lat_ref = sum(p[1] for p in points) / len(points)
    dlon = _cell_size_deg(cell_size_km, lat_ref)
    dlat = cell_size_km / EARTH_LAT_KM

    occupied: set[tuple[int, int]] = set()
    for lon, lat in points:
        occupied.add((int(lon // dlon), int(lat // dlat)))
    if len(occupied) < min_cells:
        return None

    rings = _boundary_rings(occupied)
    origin_i = min(i for i, _ in occupied)
    origin_j = min(j for _, j in occupied)
    rings_ll = []
    for ring in rings:
        pts_ll = [((origin_i + i) * dlon, (origin_j + j) * dlat) for i, j in ring]
        rings_ll.append(_simplify(pts_ll, simplify_tolerance_km))
    return GeneratedFence(
        dealer=dealer,
        rings=[r for r in rings_ll if len(r) >= 4],
        store_count=len(points),
        cells=len(occupied),
    )


def _boundary_rings(occupied: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """占用格 → 边界环。边界边方向保持占用格在左侧；串成环。"""
    edges: dict[tuple[int, int], tuple[int, int]] = {}
    for (i, j) in occupied:
        if (i, j + 1) not in occupied:
            edges[(i, j + 1)] = (i + 1, j + 1)
        if (i, j - 1) not in occupied:
            edges[(i + 1, j)] = (i, j)
        if (i - 1, j) not in occupied:
            edges[(i, j)] = (i, j + 1)
        if (i + 1, j) not in occupied:
            edges[(i + 1, j + 1)] = (i + 1, j)

    rings = []
    while edges:
        start = next(iter(edges))
        ring = [start]
        cur = start
        while True:
            cur = edges.pop(cur, None)
            if cur is None:
                break
            ring.append(cur)
            if cur == start:
                break
        if len(ring) >= 4:
            rings.append(ring)
    rings.sort(key=len, reverse=True)
    return rings


def _simplify(points: list[tuple[float, float]], tol_km: float) -> list[tuple[float, float]]:
    if len(points) < 5:
        return points
    pts = points[:-1] if points[0] == points[-1] else points
    keep = _dp(pts, tol_km)
    keep.append(keep[0])
    return keep


def _dp(pts, tol):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    dmax, idx = -1.0, 0
    for i in range(1, len(pts) - 1):
        d = _point_line_km(pts[i], a, b)
        if d > dmax:
            dmax, idx = d, i
    if dmax > tol:
        left = _dp(pts[: idx + 1], tol)
        right = _dp(pts[idx:], tol)
        return left[:-1] + right
    return [a, b]


def _point_line_km(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return _dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return _dist(p, (ax + t * dx, ay + t * dy))


# ---------- 3. 对比 ----------

def compare(
    stores: list[dict],
    current_fences: list[dict],
    generated: list[GeneratedFence],
) -> dict:
    """反向生成围栏 vs 现行围栏：差异即调整讨论证据。"""
    gen_by_dealer = {g.dealer: g for g in generated}
    report: dict = {"per_dealer": {}, "moved": [], "summary": {}}
    changed = 0
    excluded = sum(1 for s in stores if s.get("excluded"))
    dealers = sorted({f["dealer"] for f in current_fences} | set(gen_by_dealer))
    for d in dealers:
        cur_f = fences_of(d, current_fences)
        gen = gen_by_dealer.get(d)
        now_c = gen_c = moved = 0
        for s in stores:
            if s.get("excluded"):
                continue
            in_cur = any(_pip((s["lon"], s["lat"]), f["ring"], f["bbox"]) for f in cur_f)
            in_gen = False
            if gen:
                for ring in gen.rings:
                    bbox = (min(p[0] for p in ring), min(p[1] for p in ring),
                            max(p[0] for p in ring), max(p[1] for p in ring))
                    if _pip((s["lon"], s["lat"]), ring, bbox):
                        in_gen = True
                        break
            now_c += in_cur
            gen_c += in_gen
            if in_cur != in_gen:
                moved += 1
                report["moved"].append(
                    {"store": s.get("n", s.get("store_id", "")),
                     "district": s.get("d", ""), "upstream": s.get("u", ""),
                     "in_current": in_cur, "in_generated": in_gen}
                )
        report["per_dealer"][d] = {"now_covered": now_c, "generated_covers": gen_c,
                                   "changed": moved}
        changed += moved
    report["summary"] = {
        "dealers": len(dealers),
        "total_changed": changed,
        "changed_rate": round(changed / max(1, len(stores) - excluded), 4),
    }
    return report
