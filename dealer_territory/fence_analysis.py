"""经销商围栏现状分析（确定性内核）。

输入：经销商地理围栏（WKT POLYGON/MULTIPOLYGON）+ 门店点（坐标+实际上游）。
输出：覆盖/缺口/重叠/供货流向 的分型发现——agentic 现状分析的数据底座。

⚠️ 术语与定性（重要）：
- 围栏是经销商的**责任服务区域**（业代服务/市场秩序责任），
  不是供货独占权。中国经销商体系做不到 100% 严格：
  门店就近拿货、多家拿货、连锁系统直供、挂靠、临时缺货跨区调货，
  都是正常业务形态。
- 因此围栏外供货（OUT_OF_FENCE_SUPPLY）不是"错误清单"，
  而是**真实供货格局的洞察信号**：用于理解格局、发现系统性流向、
  支撑围栏修订与渠道政策讨论。

分型规则（可配置 direct_markers）：
- 门店不被任何围栏覆盖：
    上游匹配直供关键词(连锁/KA)  -> NORMAL_DIRECT（直供体系，正常）
    否则                        -> REAL_GAP（围栏未覆盖，需关注）
- 门店恰落一个围栏且上游=围栏经销商 -> OK
- 门店落多个围栏                   -> MULTI（边界接触，需人工确认）
- 门店落围栏但上游≠围栏经销商       -> OUT_OF_FENCE_SUPPLY（非围栏供货，中性洞察）
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field


# ---------- 围栏 ----------

@dataclass(frozen=True)
class Fence:
    area_id: str
    dealer: str
    org: str
    area_km2: float
    ring: tuple[tuple[float, float], ...]
    bbox: tuple[float, float, float, float]

    def contains(self, lon: float, lat: float) -> bool:
        return point_in_polygon((lon, lat), self.ring, self.bbox)


_NUM_PAIR = re.compile(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")

def parse_wkt(wkt: str) -> tuple[tuple[float, float], ...]:
    """POLYGON / MULTIPOLYGON 通吃：抓全部 x y 数字对（忽略环/孔结构，PIP 近似）。"""
    pts = tuple((float(a), float(b)) for a, b in _NUM_PAIR.findall(wkt))
    if len(pts) < 3:
        raise ValueError(f"WKT 顶点不足: {len(pts)}")
    return pts


def point_in_polygon(pt: tuple[float, float], ring, bbox) -> bool:
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


def make_fence(area_id: str, dealer: str, org: str, area_km2: float, wkt: str) -> Fence:
    ring = parse_wkt(wkt)
    bbox = (min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring))
    return Fence(area_id, dealer, org, area_km2, ring, bbox)


# ---------- 门店与分型 ----------

@dataclass(frozen=True)
class StorePoint:
    store_id: str
    name: str
    channel: str
    district: str
    upstream: str
    lon: float
    lat: float


class StoreKind:
    OK = "OK"
    NORMAL_DIRECT = "NORMAL_DIRECT"       # 未覆盖但上游是直供/连锁 KA —— 正常
    REAL_GAP = "REAL_GAP"                 # 围栏未覆盖（无直供解释），需关注
    MULTI = "MULTI"                       # 落多围栏（边界接触），需人工确认
    OUT_OF_FENCE_SUPPLY = "OUT_OF_FENCE_SUPPLY"  # 非围栏供货：中性洞察，非错误


@dataclass(frozen=True)
class Finding:
    store: StorePoint
    kind: str
    fence_dealers: tuple[str, ...] = ()


@dataclass
class AnalysisReport:
    total_stores: int = 0
    total_fences: int = 0
    ok: int = 0
    normal_direct: int = 0
    real_gap: int = 0
    multi: int = 0
    out_of_fence: int = 0
    findings: list[Finding] = field(default_factory=list)
    out_of_fence_by_upstream: Counter = field(default_factory=Counter)  # 供货格局：谁在围栏外供
    gap_by_district: Counter = field(default_factory=Counter)
    coverage_rate: float = 0.0

    def summary(self) -> str:
        return (
            f"围栏 {self.total_fences} | 门店 {self.total_stores} | "
            f"覆盖 {self.coverage_rate:.1%} | 真缺口 {self.real_gap} | "
            f"多围栏 {self.multi} | 非围栏供货 {self.out_of_fence}"
        )


DEFAULT_DIRECT_MARKERS = ("沃尔玛", "华润万家", "大润发", "永辉", "山姆", "盒马",
                          "美宜佳", "Ole'", "7-11", "十足", "便利蜂")


def _is_direct(upstream: str, markers: tuple[str, ...]) -> bool:
    return any(m in upstream for m in markers)


def analyze(
    stores: list[StorePoint],
    fences: list[Fence],
    direct_markers: tuple[str, ...] = DEFAULT_DIRECT_MARKERS,
) -> AnalysisReport:
    rep = AnalysisReport(total_stores=len(stores), total_fences=len(fences))
    for s in stores:
        pt = (s.lon, s.lat)
        hits = [f for f in fences if f.contains(pt[0], pt[1])]
        dealers = tuple(f.dealer for f in hits)
        if not hits:
            if _is_direct(s.upstream, direct_markers):
                rep.normal_direct += 1
                rep.findings.append(Finding(s, StoreKind.NORMAL_DIRECT))
            else:
                rep.real_gap += 1
                rep.gap_by_district[s.district] += 1
                rep.findings.append(Finding(s, StoreKind.REAL_GAP))
        else:
            if len(hits) > 1:
                rep.multi += 1
                rep.findings.append(Finding(s, StoreKind.MULTI, dealers))
            if s.upstream and s.upstream not in dealers:
                rep.out_of_fence += 1
                rep.out_of_fence_by_upstream[s.upstream] += 1
                rep.findings.append(Finding(s, StoreKind.OUT_OF_FENCE_SUPPLY, dealers))
            else:
                rep.ok += 1
    covered = rep.ok + rep.multi + rep.out_of_fence
    rep.coverage_rate = covered / rep.total_stores if rep.total_stores else 0.0
    return rep
