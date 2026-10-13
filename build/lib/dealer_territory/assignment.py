"""归属逻辑：规则匹配（最低匹配节点胜出）+ 手动覆盖留痕。"""

from __future__ import annotations

from typing import Iterable, Mapping

from .models import Assignment, Cause, DealerTerritoryModel, RegionNode, Store

POOL_NODE_ID = "POOL"     # 兜底节点：未覆盖门店可见化（Oracle "Any" / holding queue 同思路）
POOL_DEALER = "UNASSIGNED"


def match_nodes(store: Store, nodes: Iterable[RegionNode]) -> list[RegionNode]:
    """维度兼容的节点：节点声明的每个维度值须为 ANY(*) 或与门店一致。"""
    out = []
    for n in nodes:
        if all(v in ("*", "", None) or store.dims.get(d) == v for d, v in n.dims.items()):
            out.append(n)
    return out


def rule_assign(store: Store, model: DealerTerritoryModel, set_by: str = "system") -> Assignment | None:
    """规则归属：兼容节点中取维度最具体者；同分按 node_id 字典序（确定性）。

    excluded 门店不归属（KA 直供等例外名单单独管理）；
    无兼容节点 → POOL 兜底（覆盖缺口可见，而不是消失）。
    """
    if store.excluded:
        return None
    matched = match_nodes(store, model.nodes)
    if not matched:
        return Assignment(
            model_version=model.version,
            assignment_id=f"ASG_{model.version}_{store.store_id}",
            store_id=store.store_id,
            node_id=POOL_NODE_ID,
            dealer_id=POOL_DEALER,
            cause=Cause.RULE,
            set_by=set_by,
            reason="no_matching_region",
        )
    best = max(matched, key=lambda n: (n.depth_specificity(), n.node_id))
    return Assignment(
        model_version=model.version,
        assignment_id=f"ASG_{model.version}_{store.store_id}",
        store_id=store.store_id,
        node_id=best.node_id,
        dealer_id=best.dealer_id,
        cause=Cause.RULE,
        set_by=set_by,
        reason="rule_match",
    )


def manual_assign(
    model: DealerTerritoryModel,
    store: Store,
    target: RegionNode,
    set_by: str,
    reason: str,
    current: Assignment | None,
) -> Assignment:
    """人工覆盖：必须留操作人与原因；记录被顶掉的规则结果（可审计可回滚）。"""
    if not (set_by or "").strip():
        raise ValueError("manual_assign 必须记录操作人 set_by")
    if not (reason or "").strip():
        raise ValueError("manual_assign 必须记录原因 reason")
    overwritten = current.node_id if current is not None and current.cause is Cause.RULE else None
    return Assignment(
        model_version=model.version,
        assignment_id=f"ASG_{model.version}_{store.store_id}",
        store_id=store.store_id,
        node_id=target.node_id,
        dealer_id=target.dealer_id,
        cause=Cause.MANUAL,
        set_by=set_by,
        reason=reason,
        overwritten_rule_node_id=overwritten,
    )


def rebuild_assignments(
    model: DealerTerritoryModel,
    stores: Iterable[Store],
    manual_overrides: Mapping[str, tuple[str, str, str]] | None = None,
) -> DealerTerritoryModel:
    """整批重算：先规则，再套人工覆盖。manual_overrides: store_id -> (node_id, set_by, reason)"""
    overrides = manual_overrides or {}
    index = {n.node_id: n for n in model.nodes}
    out: list[Assignment] = []
    for s in stores:
        cur = rule_assign(s, model)
        if cur is None:
            continue  # excluded：直供名单单独管理
        ov = overrides.get(s.store_id)
        if ov:
            node_id, set_by, reason = ov
            cur = manual_assign(model, s, index[node_id], set_by, reason, cur)
        out.append(cur)
    return model.with_(assignments=tuple(out))
