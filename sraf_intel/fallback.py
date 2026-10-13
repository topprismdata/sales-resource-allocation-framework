"""sraf_intel.fallback — nearby-containers 兜底（WP16）。

语义（计划 §WP16 原文口径）：未分配门店 → 最近可用片区**候选** + 人工确认。
- 输出永远是候选清单（带距离、余量、理由），requires_human_confirmation 恒 True；
- **不自动合并、不自动分配**（同 WP05 纪律：兜底是建议不是授权）；
- 排序确定性：(距离升序, territory_id 升序) 平局全序，可回归测试锁定。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TerritoryContainer:
    territory_id: str
    centroid_km: tuple[float, float]  # 片区质心（平面 km，同 coords-core 口径）
    headroom_stores: int               # 剩余可容门店数（编制余量，>0 才可用）


@dataclass(frozen=True)
class NearbyCandidate:
    territory_id: str
    distance_km: float
    headroom_stores: int
    requires_human_confirmation: bool = field(default=True, init=False)


def nearby_candidates(
    store_km: tuple[float, float],
    containers: list[TerritoryContainer] | tuple[TerritoryContainer, ...],
    k: int = 3,
    max_radius_km: float = 25.0,
) -> list[NearbyCandidate]:
    """未分配门店的最近可用片区候选（欧氏 km；与 osrm 车程口径差异见 docstring）。

    欧氏近似仅用于兜底排序提示；正式分配以道路行驶距离评估（territory-ir
    roadsem 链）为准——候选≠结论，人工确认环节负责补精确口径。
    """
    out: list[NearbyCandidate] = []
    for c in containers:
        if c.headroom_stores <= 0:
            continue  # 无余量片区不进候选（可用=硬条件）
        d = math.dist(store_km, c.centroid_km)
        if d <= max_radius_km:
            out.append(NearbyCandidate(c.territory_id, round(d, 4), c.headroom_stores))
    out.sort(key=lambda x: (x.distance_km, x.territory_id))
    return out[:k]
