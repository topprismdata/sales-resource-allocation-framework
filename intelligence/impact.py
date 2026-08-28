"""Q3 围栏调整影响（L3 反事实，仅 Layer-D 内；跨层只发 Signal 不越权）。"""
from __future__ import annotations

from collections import Counter

from .knowledge import KnowledgeBase
from .world import Fence, Store, World


def _kind_comp(stores: list[Store]) -> dict:
    return dict(Counter(s.kind for s in stores).most_common())


def move_impact(world: World, source: Fence, target: Fence,
                stores: list[Store], kb: KnowledgeBase) -> dict:
    """把 stores 从 source 围栏划给 target：重算双方 kind 构成与负荷。"""
    moved = [s for s in stores if source.dealer in s.dealers and target.dealer not in s.dealers]
    if not moved:
        raise ValueError("给定门店不在 source 围栏内（或已在 target 中），无调整可做")

    before_s = world.fence_stores(source)
    before_t = world.fence_stores(target)
    moved_set = set(id(m) for m in moved)
    after_s = [s for s in before_s if id(s) not in moved_set]
    after_t = before_t + moved

    def dealer_view(stores_after: list[Store], fence: Fence) -> dict:
        return {"stores": len(stores_after),
                "kinds": _kind_comp(stores_after),
                "density_per_km2": round(len(stores_after) / fence.area_km2, 1)}

    # 被移动门店的 kind 变化（新归属下：dealers 去掉 source 加上 target）
    moved_detail = []
    for s in moved:
        new_dealers = tuple(d for d in s.dealers if d != source.dealer) + (target.dealer,)
        new_kind = world.reclassify(s, new_dealers)
        moved_detail.append({"store": s.name, "district": s.district,
                             "upstream": s.upstream,
                             "kind": f"{s.kind} → {new_kind}"})

    signals = [
        {"signal": "I-D 契约版本 +1（E6 围栏变更事件，走 GW 审批）",
         "spec_ref": "PROPOSAL_v1.3 §3"},
        {"signal": "I-B 需重估：涉事门店的 beat 归属与频率（Layer-B 责任，本工具不发号施令）",
         "spec_ref": "PROPOSAL_v1.3 §3 层间纪律"},
        {"signal": "V 层增量重排在 I-B v+1 之后（本次不评估）", "spec_ref": "D10"},
    ]
    risk_chain = [
        kb.cite("K-PRIN-002"),   # carryover：短期波动不构成失败证据
        kb.cite("K-PRIN-003"),   # disruption 打击中等体量门店
        kb.cite("K-RULE-006"),   # 客情依赖：过渡方案
    ]
    gaps_kb = kb.gaps
    if gaps_kb:
        risk_chain.append({"kb_id": "KNOWLEDGE-GAP", "type": "gap",
                           "statement": f"业务口径待确认 {len(gaps_kb)} 项（客情量化等），"
                                        "影响置信度标注", "source": "knowledge_base"})
    evidence = [
        {"data_ref": f"moved={len(moved)} source {source.dealer} "
                     f"{len(before_s)}→{len(after_s)}; target {target.dealer} "
                     f"{len(before_t)}→{len(after_t)}"},
        {"data_ref": f"moved kind 变化: "
                     f"{dict(Counter(d['kind'].split(' → ')[1] for d in moved_detail))}"},
        kb.cite("K-CONST-002"),
    ]
    KnowledgeBase.validate_chain(evidence + risk_chain)
    return {
        "action": f"将 {len(moved)} 家门店从「{source.dealer}」划入「{target.dealer}」",
        "source_after": dealer_view(after_s, source),
        "target_after": dealer_view(after_t, target),
        "moved_sample": moved_detail[:10],
        "moved_kind_delta": dict(Counter(d["kind"] for d in moved_detail)),
        "signals": signals,
        "risks": risk_chain,
        "evidence": evidence,
        "materiality": "Review",
    }
