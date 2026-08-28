"""道路语义 → 几何切分（market_partition 引擎 + 地理侧选块）。

设计（对齐 market-partition README 的 LLM/Agent × GIS 分层）：
  market_partition.geometry.split.partition 负责「切」：
    环形高速（G2504 绕城）重建→buffer 带→碎片过滤；线性道路延伸切分。
  本模块负责「选」：按合同方向的【地理侧】测试质心选块，
    ——不信任 partition 的标签（竖线会被投影法误标为"南"）。

方向语义：
  "G2504以南" → G2504 是北界 → 保留在界线以南的块（centroid 更靠南）
  "上塘高架以东" → 西界 → 保留东侧块
  环形路（closed）：以南/北/东/西 仍按地理侧测试（对绕城环同样成立）。
"""
from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union

from market_partition.geometry.split import Barrier, partition

# 环/高速类关键词 → kind=closed
RING_WORDS = ("绕城", "环城", "高速", "快速路", "G2504", "G2501", "G1501")
# 方向 → 保留侧；keep 表示"区域在界线的哪一侧"
DIR_KEEP = {"北": "south", "南": "north", "东": "west", "西": "east"}


def is_ring(name: str, geom: list) -> bool:
    """判断是否环形/高速类：关键词命中，或闭合检测（首尾点距离<对角5%）。"""
    if any(w in name for w in RING_WORDS):
        return True
    pts = [p for seg in geom for p in seg]
    if len(pts) < 8:
        return False
    x0, y0 = pts[0]
    x1, y1 = pts[-1]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    diag = max((max(xs) - min(xs)) ** 2 + (max(ys) - min(ys)) ** 2, 1e-12) ** 0.5
    return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 < diag * 0.05


def _lines_from_geom(geom: list) -> MultiLineString:
    return MultiLineString([LineString(seg) for seg in geom if len(seg) >= 2])


def _piece_on_side(pieces, keep: str):
    """按地理侧选块：keep=north/south 比 centroid.y，east/west 比 centroid.x。"""
    if not pieces:
        return None
    if len(pieces) == 1:
        return pieces[0]
    if keep in ("north", "south"):
        key = lambda p: p.polygon.centroid.y
        return max(pieces, key=key) if keep == "north" \
            else min(pieces, key=key)
    key = lambda p: p.polygon.centroid.x
    return max(pieces, key=key) if keep == "east" \
        else min(pieces, key=key)



def _region_on_side(poly: Polygon, line, keep: str) -> bool:
    """界线不穿过区域时：验证区域是否在合同要求的地理侧。

    判据：线上离区域质心最近的点 → 比较相应坐标。
    南北向线用 x 判东西，东西向线用 y 判南北。
    """
    pts = []
    if line.geom_type == "MultiLineString":
        for g in line.geoms:
            pts.extend(list(g.coords))
    else:
        pts = list(line.coords)
    if not pts:
        return True
    c = poly.centroid
    xs = [x for (x, _) in pts]
    ys = [y for (_, y) in pts]
    near = min(pts, key=lambda q: (q[0] - c.x) ** 2 + (q[1] - c.y) ** 2)
    if (max(xs) - min(xs)) >= (max(ys) - min(ys)):   # 近东西向线 → 用 y 判南北
        return c.y >= near[1] if keep == "north" else c.y <= near[1]
    return c.x >= near[0] if keep == "east" else c.x <= near[0]


@dataclass
class SemResult:
    polygon: Polygon
    applied: list          # 每条界线的处理记录
    diagnostics: dict      # 每次切分的 buffer/snap 参数


def clip_by_bounds(poly: Polygon, bounds: dict, geoms: dict,
                   snap_deg: float = 0.003) -> SemResult:
    """按四条方向界线依次切分多边形。

    poly:    初始区域（如街道并集）
    bounds:  {"北":"G2504", "西":"上塘高架路", ...}
    geoms:   {地标名: [[lon,lat]…段列表]} 各界线几何
    """
    def zh(keep: str) -> str:
        return {"south": "南", "north": "北", "east": "东", "west": "西"}[keep]

    applied = []
    diag = {}
    for d in ("北", "南", "东", "西"):
        nm = bounds.get(d)
        keep = DIR_KEEP[d]
        if not nm or nm not in geoms:
            continue
        geom = geoms[nm]
        if not geom or sum(len(s) for s in geom) < 2:
            applied.append(f"{d}:{nm}(无几何)")
            continue
        ml = _lines_from_geom(geom)
        if ml.is_empty:
            applied.append(f"{d}:{nm}(几何为空)")
            continue
        ring = is_ring(nm, geom)
        b = Barrier(name=nm, kind="closed" if ring else "linear",
                    geometry=ml,
                    orient_scheme="in_out" if ring else None)
        try:
            res = partition(poly, [b], snap_deg=snap_deg)
        except Exception as e:  # noqa: BLE001
            applied.append(f"{d}:{nm}(切分失败 {e})")
            continue
        if not res or len(res.pieces) < 2:
            # 未切开：界线不穿过区域 → 校验区域在哪一侧（错误侧=合同矛盾）
            ok = _region_on_side(poly, ml, keep)
            if ok:
                applied.append(
                    f"✓ {d}:{nm}(界线不穿过区域，区域整体在其{zh(keep)}侧，符合合同)")
            else:
                applied.append(
                    f"⚠ {d}:{nm}(界线不穿过区域，但区域整体不在其{zh(keep)}侧——与合同矛盾，需人工确认)")
            diag[f"{d}:{nm}"] = {"kind": b.kind,
                                 "pieces": len(res.pieces) if res else 0,
                                 "note": "未穿过区域", "side_ok": ok}
            continue
        chosen = _piece_on_side(res.pieces, keep)
        if chosen is None:
            applied.append(f"{d}:{nm}(选块失败)")
            continue
        cp = chosen.polygon
        poly = cp if isinstance(cp, Polygon) else max(
            cp.geoms, key=lambda g: g.area)
        applied.append(
            f"{d}:{nm}({'环形' if ring else '线性'}→保留{zh(keep)}侧, "
            f"剩{round(poly.area * 111 * 111, 1)}km²)")
        diag[f"{d}:{nm}"] = {
            "kind": b.kind, "pieces": len(res.pieces),
            "labels": [(q.label, round(q.area * 111 * 111, 1)) for q in res.pieces],
            "kept": chosen.label, "buffer_deg": res.buffer_deg,
        }
    return SemResult(polygon=poly, applied=applied, diagnostics=diag)
