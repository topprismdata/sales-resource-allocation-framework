"""ProblemRouter：诊断 → 决策问题路由（04 §28 的最小实现）。

规范出处：
- 04 §28 路由表：Diagnosis → Primary Route（DP01–DP07 编号与 03 文档
  DP01–DP07 合同一一对应）；
- 04 §28：Router 可输出 Composite Problem、Alternative Route、Monitor、
  RequestMoreEvidence、NoAction；
- 04 §36 架构门禁：不允许「Router 不给 NoAction」「一切问题都路由到
  Territory Solver」「Router 与 Solver Selector 合并」；
- 02 §21：DataQualityIssue 的四个 identity 子型 → World Model Repair。
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .gaps import IDENTITY_SUBTYPES
from .materiality import MaterialityLevel
from .trigger import TriggerDecision, TriggerResult

__all__ = [
    "DPCode", "NonDPRoute", "RouterOutput", "RouteResult", "ProblemRouter",
    "DIAGNOSIS_ROUTES",
]


class DPCode(str, Enum):
    """DP01–DP07（04 §28 路由表；编号定义见 03_DECISION_PROBLEM_CONTRACTS.md）。"""

    DP01 = "DP01 Resource Sizing"
    DP02 = "DP02 Resource Location"
    DP03 = "DP03 Territory Alignment"
    DP04 = "DP04 Personnel Matching"
    DP05 = "DP05 Coverage Allocation"
    DP06 = "DP06 Visit Scheduling"
    DP07 = "DP07 Daily Routing"


class NonDPRoute(str, Enum):
    """非 DP 出口（04 §28 后三行）。"""

    WORLD_MODEL_REPAIR = "World Model Repair"
    MODEL_GOVERNANCE = "Model Governance"
    POLICY_REVIEW = "Policy Review"


class RouterOutput(str, Enum):
    """Router 输出形态（04 §28：Composite/Alternative/Monitor/MoreEvidence/NoAction）。"""

    ROUTE = "Route"
    MONITOR = "Monitor"
    REQUEST_MORE_EVIDENCE = "RequestMoreEvidence"
    NO_ACTION = "NoAction"


#: 04 §28 路由表：根因名（02 §21）→ 主路由。
DIAGNOSIS_ROUTES: dict[str, str] = {
    "CapacityShortage": DPCode.DP01.value,          # Global Capacity Shortage
    "CapacitySurplus": DPCode.DP01.value,           # DP01 / Downsizing
    "ResourceLocationMismatch": DPCode.DP02.value,  # Base Location Mismatch
    "TerritoryImbalance": DPCode.DP03.value,        # Local Allocation Imbalance
    "CapabilityMismatch": DPCode.DP04.value,        # Personnel / Skill Fit
    "PersonnelConstraint": DPCode.DP04.value,
    "CoveragePolicyMismatch": DPCode.DP05.value,    # Coverage / Channel Mismatch
    "CoverageAllocationMismatch": DPCode.DP05.value,
    "SchedulingInfeasibility": DPCode.DP06.value,   # Temporal Feasibility
    "RoutingInefficiency": DPCode.DP07.value,       # Daily Route Inefficiency
    "DataQualityIssue": NonDPRoute.WORLD_MODEL_REPAIR.value,
    "ModelQualityIssue": NonDPRoute.MODEL_GOVERNANCE.value,
    "PolicyConflict": NonDPRoute.POLICY_REVIEW.value,
}

#: identity 子型名 → World Model Repair（02 §21 / 04 §28 DataQualityIssue 行）。
_IDENTITY_NAME_TO_SUBTYPE = {s.value: s for s in IDENTITY_SUBTYPES}


@dataclass(frozen=True)
class RouteResult:
    output: RouterOutput
    primary_route: str | None            # DPCode/NonDPRoute 的规范名
    reason: str = ""
    alternatives: tuple[str, ...] = ()   # Alternative Route（04 §28）


class ProblemRouter:
    """04 §28 ProblemRouter：只做路由，不选 Solver（04 §36 解耦门禁）。"""

    ROUTE_TABLE = dict(DIAGNOSIS_ROUTES)

    def route(self, diagnosis: str, *,
              identity_unresolved_ratio: float | None = None,
              threshold: float = 0.05,
              ) -> RouteResult:
        """诊断名 → RouteResult。

        - identity 四子型（02 §21）→ World Model Repair；
        - 已知根因 → 04 §28 路由表；identity_unresolved_ratio 超阈时
          追加 RequestMoreEvidence 替代路（04 §24：身份未决不进结构决策）；
        - "NoGap" → NO_ACTION（04 §36：Router 必须允许 NoAction）；
        - 未知诊断 → REQUEST_MORE_EVIDENCE（不得臆测路由）。
        """
        if diagnosis == "NoGap":
            return RouteResult(RouterOutput.NO_ACTION, None,
                               "无缺口，无需路由（04 §28 NoAction）")
        if diagnosis in _IDENTITY_NAME_TO_SUBTYPE:
            return RouteResult(RouterOutput.ROUTE,
                               NonDPRoute.WORLD_MODEL_REPAIR.value,
                               f"{diagnosis} 为 DataQualityIssue 身份子型"
                               "（02 §21 → 04 §28 World Model Repair）")
        route = self.ROUTE_TABLE.get(diagnosis)
        if route is None:
            return RouteResult(RouterOutput.REQUEST_MORE_EVIDENCE, None,
                               f"未知诊断「{diagnosis}」：需要更多证据，不得臆测路由")
        alternatives: list[str] = []
        reason = f"04 §28 路由表：{diagnosis} → {route}"
        if (identity_unresolved_ratio is not None
                and identity_unresolved_ratio > threshold):
            alternatives.append(NonDPRoute.WORLD_MODEL_REPAIR.value)
            reason += ("；IdentityUnresolved 超阈，先修身份（04 §24/§36）")
        return RouteResult(RouterOutput.ROUTE, route, reason,
                           tuple(alternatives))

    def route_from_trigger(self, result: TriggerResult) -> RouteResult:
        """触发裁决 → Router 输出（仅 MONITOR/MORE_EVIDENCE/NO_ACTION 透传）。

        CREATE_DECISION_CASE 不在此转换——路由器只接收已满足门槛后的
        诊断，具体映射由 `route(diagnosis)` 承担（04 §36 不与 Trigger 合并）。
        """
        mapping = {
            TriggerDecision.MONITOR: RouterOutput.MONITOR,
            TriggerDecision.REQUEST_MORE_EVIDENCE: RouterOutput.REQUEST_MORE_EVIDENCE,
            TriggerDecision.NO_ACTION: RouterOutput.NO_ACTION,
        }
        out = mapping.get(result.decision)
        if out is None:
            raise ValueError(
                "CREATE_DECISION_CASE 需先确定根因诊断再调用 route()（04 §36）")
        return RouteResult(out, None, result.reason)


def route_from_materiality(level: MaterialityLevel) -> RouterOutput:
    """materiality 等级 → Router 兜底输出形态（02 §28 语义）。"""
    if level is MaterialityLevel.REVIEW:
        return RouterOutput.REQUEST_MORE_EVIDENCE
    if level is MaterialityLevel.MONITOR:
        return RouterOutput.MONITOR
    return RouterOutput.NO_ACTION
