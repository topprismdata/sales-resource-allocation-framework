"""Q1 围栏健康报告（L1 聚合 + 04 §4 Health Profile 简化版）。"""
from __future__ import annotations

from collections import Counter

from .knowledge import KnowledgeBase
from .world import Fence, Store, World

KIND_ZH = {"OK": "围栏内一致", "OOF": "非围栏供货", "DIRECT_IN": "直供KA(内)",
           "DIRECT": "直供KA(外)", "GAP": "覆盖缺口", "MULTI": "多围栏"}


def fence_health(world: World, fence: Fence, kb: KnowledgeBase) -> dict:
    stores = world.fence_stores(fence)
    kinds = Counter(s.kind for s in stores)
    districts = Counter(s.district for s in stores)
    n = len(stores)
    ok_rate = kinds.get("OK", 0) / n if n else 0.0
    oof_rate = kinds.get("OOF", 0) / n if n else 0.0

    bench = kb.cite("K-BENCH-001")
    if oof_rate > 0.20:
        verdict, sev = "调查", "Review"
    elif ok_rate >= 0.79:
        verdict, sev = "健康", "Monitor"
    else:
        verdict, sev = "观察", "Monitor"

    if n:
        top_district, top_n = districts.most_common(1)[0]
        purity = top_n / n
    else:
        top_district, purity = "—", 0.0
    evidence = [
        {"data_ref": f"gz_data.json: fence {fence.area_id} n={n} kind={dict(kinds)}"},
        bench,
    ]
    return {
        "area_id": fence.area_id,
        "dealer": fence.dealer,
        "area_km2": world.territory_area_km2(fence.dealer) or fence.area_km2,
        "blocks": len(world.fences_of(fence.dealer)),
        "density_per_km2": (round(n / max(world.territory_area_km2(fence.dealer),
                                          fence.area_km2), 1)
                            if fence.area_km2 else None),
        "kinds": {KIND_ZH.get(k, k): v for k, v in kinds.most_common()},
        "ok_rate": round(ok_rate, 3),
        "oof_rate": round(oof_rate, 3),
        "top_district": f"{top_district} ({purity:.0%})",
        "verdict": verdict,
        "materiality": sev,
        "evidence": evidence,
    }


def run_q1(world: World, kb: KnowledgeBase) -> list[dict]:
    # D14: 一经销商一报告（多块领地合并为一条，密度按领地总面积）
    seen, reports = set(), []
    for f in world.fences:
        if f.dealer in seen:
            continue
        seen.add(f.dealer)
        reports.append(fence_health(world, f, kb))
    reports.sort(key=lambda r: (r["verdict"] != "调查", -r["oof_rate"]))
    return reports
