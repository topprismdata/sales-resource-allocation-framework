"""Q2 缺口五分类（L0 层定位 + L2 假设检验）。

GAP 门店（无围栏覆盖、非直供）按可用证据分类：
  u 为空                        → 缺身份   layer=DATA   （先 08 身份核验）
  u ∈ 围栏经销商集合             → 缺围栏覆盖 layer=D     （现实供货在先、围栏在后）
  u 为其他（二批/无名头）         → 缺意愿候选 layer=D     materiality=Review
叠加结构性标记：距最近围栏 > 5km → structural（K-RULE-007：服务模式而非加人）。
"""
from __future__ import annotations

from collections import Counter

from .knowledge import KnowledgeBase
from .world import Store, World

STRUCTURAL_KM = 5.0


def classify_gap(world: World, kb: KnowledgeBase) -> dict:
    fence_dealers = {f.dealer for f in world.fences}
    gaps = [s for s in world.stores if s.kind == "GAP"]
    out = []
    for s in gaps:
        near = world.nearest_fence((s.lon, s.lat))
        dist = round(near[1], 2) if near else None
        if not s.upstream:
            cls, layer, action = "缺身份", "DATA", "08 身份核验后再诊断"
            evidence = [{"data_ref": f"upstream 为空: {s.name}"},
                        kb.cite("K-RULE-005")]
        elif s.upstream in fence_dealers:
            cls, layer, action = "缺围栏覆盖", "D", "评估围栏扩展（E6，走审批）"
            evidence = [{"data_ref": f"实际由围栏经销商供货: {s.upstream}，但无围栏命中"},
                        kb.cite("K-FACT-001")]
        else:
            cls, layer, action = "缺意愿候选", "D", "门店政策调研（暂不强判）"
            evidence = [{"data_ref": f"上游为非围栏主体: {s.upstream or '空'}"}]
        structural = dist is not None and dist > STRUCTURAL_KM
        if structural:
            evidence.append(kb.cite("K-RULE-007"))
            action = "结构性缺口：调整服务模式（批发/直配/线上），非加人"
        out.append({
            "store": s.name, "district": s.district, "upstream": s.upstream,
            "class": cls, "layer": layer, "structural": structural,
            "nearest_fence_km": dist, "action": action,
            "materiality": "Review",
            "evidence": evidence,
        })
    summary = {
        "total_gaps": len(gaps),
        "by_class": dict(Counter(o["class"] for o in out)),
        "by_layer": dict(Counter(o["layer"] for o in out)),
        "structural": sum(1 for o in out if o["structural"]),
        "by_district": dict(Counter(o["district"] for o in out).most_common()),
    }
    return {"summary": summary, "items": out}
