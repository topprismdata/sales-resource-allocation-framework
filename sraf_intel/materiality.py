"""Materiality 重要性评估（02 §25–§28、04 §24/§26 的阈值化最小实现）。

规范要点：
- 02 §26：Materiality = f(Magnitude, Persistence, BusinessImpact, Confidence,
  StrategicImportance)，**不得**仅凭 metric>threshold 直接触发。
- 04 §26：还须考虑 ExpectedDecisionValue 与 ChangeCost——EDV ≤ 0 时不值得
  进入决策（防「见到缺口就优化」）。
- 04 §10 H6：低置信度不得触发大规模结构调整。
- 04 §24（08 §14.2）：IdentityUnresolved 占比超阈时，该范围内任何 Gap 的
  materiality 不得高于 Review、不得直接 Actionable。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .gaps import AllocationGap

__all__ = [
    "MaterialityLevel", "MATERIALITY_ORDER", "MaterialityAssessment",
    "assess_materiality", "cap_materiality",
    "IDENTITY_UNRESOLVED_RATIO_THRESHOLD", "CONFIDENCE_FLOOR",
]

#: 04 §24：范围内 IdentityUnresolved 占比阈值（判定规则细节归 08 §11/§14）。
IDENTITY_UNRESOLVED_RATIO_THRESHOLD = 0.05

#: 04 §10 H6：置信度地板——低于此值不得给出 Actionable/Critical。
CONFIDENCE_FLOOR = 0.5


class MaterialityLevel(str, Enum):
    """Materiality 五级（02 §28 / 04 §26，顺序即严重度）。"""

    INFORMATIONAL = "Informational"   # 记录即可，无需行动
    MONITOR = "Monitor"               # 持续监测
    REVIEW = "Review"                 # 进入人工/Agent 诊断
    ACTIONABLE = "Actionable"         # 允许创建 DecisionCase
    CRITICAL = "Critical"             # 可进入快速响应流程


#: 等级 → 严重度序（用于比较与封顶）。
MATERIALITY_ORDER: dict[MaterialityLevel, int] = {
    MaterialityLevel.INFORMATIONAL: 0,
    MaterialityLevel.MONITOR: 1,
    MaterialityLevel.REVIEW: 2,
    MaterialityLevel.ACTIONABLE: 3,
    MaterialityLevel.CRITICAL: 4,
}

_LEVEL_RECOMMENDATION = {
    MaterialityLevel.INFORMATIONAL: "记录，不采取行动（02 §28 Informational）",
    MaterialityLevel.MONITOR: "持续监测，暂不进入诊断（02 §28 Monitor）",
    MaterialityLevel.REVIEW: "进入人工/Agent 深度诊断（02 §28 Review）",
    MaterialityLevel.ACTIONABLE: "允许创建 DecisionCase（02 §28 Actionable）",
    MaterialityLevel.CRITICAL: "进入快速响应流程（02 §28 Critical）",
}


@dataclass(frozen=True)
class MaterialityAssessment:
    """MaterialityAssessment（02 §25 结构的最小落地）。"""

    subject_gap_set: tuple[str, ...]          # 涉事 gap_id 集合
    magnitude: float                          # 相对幅度 0..1
    persistence: int                          # 连续观测期数
    business_impact: float                    # 0..1
    strategic_relevance: bool                 # 战略相关性
    confidence: float                         # 0..1
    expected_decision_value: float | None     # 04 §26 EDV = 改善期望 − 变更成本
    materiality_level: MaterialityLevel
    recommendation: str
    caps_applied: tuple[str, ...] = field(default_factory=tuple)


def _score_to_level(score: float) -> MaterialityLevel:
    """确定性评分 → 等级（阈值显式列出，供门禁断言）。

    评分 = 0.40·Magnitude + 0.30·BusinessImpact + 0.20·Persistence'
          + 0.10·Strategic   （Persistence' = min(期数/4, 1)，4 期视为结构性）
    """
    if score < 0.15:
        return MaterialityLevel.INFORMATIONAL
    if score < 0.35:
        return MaterialityLevel.MONITOR
    if score < 0.50:
        return MaterialityLevel.REVIEW
    if score < 0.80:
        return MaterialityLevel.ACTIONABLE
    return MaterialityLevel.CRITICAL


def assess_materiality(gap: AllocationGap, *,
                       strategic_relevance: bool = False,
                       expected_decision_value: float | None = None,
                       ) -> MaterialityAssessment:
    """Gap → MaterialityAssessment（04 §26 因子合成 + 显式封顶）。

    封顶规则（任一命中则等级不高于 Review）：
    - confidence < CONFIDENCE_FLOOR（04 §10 H6：低置信不触发大规模结构调整）；
    - expected_decision_value ≤ 0（04 §26：EDV 防止「见到缺口就优化」）；
    - 范围内 IdentityUnresolved 超阈（04 §24，由 cap_materiality 单独提供）。
    """
    caps: list[str] = []
    magnitude = gap.relative_magnitude()
    persistence_score = min(gap.persistence / 4, 1.0)
    score = (0.40 * magnitude
             + 0.30 * gap.severity
             + 0.20 * persistence_score
             + 0.10 * (1.0 if strategic_relevance else 0.0))
    level = _score_to_level(score)

    if gap.confidence < CONFIDENCE_FLOOR:
        caps.append("confidence_floor")
    if expected_decision_value is not None and expected_decision_value <= 0:
        caps.append("edv_nonpositive")
    if caps and MATERIALITY_ORDER[level] > MATERIALITY_ORDER[MaterialityLevel.REVIEW]:
        level = MaterialityLevel.REVIEW

    return MaterialityAssessment(
        subject_gap_set=(gap.gap_id,),
        magnitude=round(magnitude, 4),
        persistence=gap.persistence,
        business_impact=gap.severity,
        strategic_relevance=strategic_relevance,
        confidence=gap.confidence,
        expected_decision_value=expected_decision_value,
        materiality_level=level,
        recommendation=_LEVEL_RECOMMENDATION[level],
        caps_applied=tuple(caps),
    )


def cap_materiality(level: MaterialityLevel, *,
                    identity_unresolved_ratio: float,
                    threshold: float = IDENTITY_UNRESOLVED_RATIO_THRESHOLD,
                    ) -> MaterialityLevel:
    """04 §24 / 08 §14.2 的 materiality 联动封顶。

    范围内 `IdentityUnresolved` 占比超过 `threshold` 时，任何 Gap 的
    materiality 不得高于 Review、不得直接进入 Actionable。
    identity 四子型（02 §21）本身不受此封顶影响（它们就是身份问题信号）。
    """
    if identity_unresolved_ratio > threshold:
        if MATERIALITY_ORDER[level] > MATERIALITY_ORDER[MaterialityLevel.REVIEW]:
            return MaterialityLevel.REVIEW
    return level
