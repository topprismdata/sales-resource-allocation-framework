"""DecisionTrigger 生成与评估（02 §29–§31、04 §27 的最小实现）。

规范要点：
- 02 §29：DecisionTrigger 不是简单报警——Gap/Diagnosis/Materiality/治理条件
  全部满足后才用于创建 DecisionCase；结构含 entry/exit 阈值、persistence、
  confidence_gate、materiality_gate、cooldown、allowed_problem_types。
- 02 §30 Hysteresis：entry/exit 双阈值防抖（Decision Flapping）。
- 02 §31 Cooldown：结构调整后冷却期内不再重启；唯 Critical 可穿透。
- 04 §27：Trigger 只创建 DecisionCase，绝不自动修改 Territory。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .gaps import AllocationGap
from .materiality import MATERIALITY_ORDER, MaterialityLevel

__all__ = [
    "TriggerDecision", "TriggerResult", "DecisionTrigger",
    "build_trigger", "evaluate_trigger", "DECISIONTRIGGER_SCHEMA_FIELDS",
]

#: 02 §29 DecisionTrigger 结构字段名（规范一致性断言用）。
DECISIONTRIGGER_SCHEMA_FIELDS: tuple[str, ...] = (
    "trigger_id", "trigger_type", "scope",
    "required_gap", "required_hypothesis",
    "entry_threshold", "exit_threshold",
    "persistence", "confidence_gate", "materiality_gate",
    "cooldown", "allowed_problem_types", "policy_reference",
)


class TriggerDecision(str, Enum):
    """触发裁决（对齐 04 §28 Router 输出词汇与 04 §27 触发语义）。"""

    CREATE_DECISION_CASE = "CreateDecisionCase"   # 04 §27：仅创建 DecisionCase
    MONITOR = "Monitor"                           # 滞回未满足/低于 entry
    REQUEST_MORE_EVIDENCE = "RequestMoreEvidence" # 置信/诊断未达门槛（02 §29 gate）
    NO_ACTION = "NoAction"                        # 冷却中/低于 exit 阈值


@dataclass(frozen=True)
class TriggerResult:
    decision: TriggerDecision
    reason: str
    trigger_id: str
    materiality_level: MaterialityLevel


@dataclass(frozen=True)
class DecisionTrigger:
    """DecisionTrigger（02 §29 结构的最小落地）。"""

    trigger_id: str
    trigger_type: str
    scope: str
    required_gap: str                 # gap_id 或 gap_type 名
    required_hypothesis: str          # 如 CapacityShortage（02 §21 根因名）
    entry_threshold: float            # 相对幅度进入阈值（02 §30）
    exit_threshold: float             # 相对幅度退出阈值，须 ≤ entry
    persistence: int = 2              # 需连续满足的观测期数
    confidence_gate: float = 0.6
    materiality_gate: MaterialityLevel = MaterialityLevel.ACTIONABLE
    cooldown: int = 0                 # 冷却期（期/天），02 §31
    allowed_problem_types: tuple[str, ...] = field(default_factory=tuple)
    policy_reference: str = "SRAF 02 §29-31 / 04 §27"

    def __post_init__(self) -> None:
        if self.exit_threshold > self.entry_threshold:
            raise ValueError("exit_threshold 不得高于 entry_threshold（02 §30 滞回）")
        if not 0.0 <= self.confidence_gate <= 1.0:
            raise ValueError("confidence_gate 必须在 [0,1]")


def build_trigger(gap: AllocationGap,
                  hypothesis: str,
                  *,
                  entry_threshold: float,
                  exit_threshold: float | None = None,
                  persistence: int = 2,
                  cooldown_periods: int = 0,
                  allowed_problem_types: tuple[str, ...] = (),
                  trigger_id: str | None = None,
                  trigger_type: str = "GapThreshold",
                  policy_reference: str = "SRAF 02 §29-31 / 04 §27",
                  ) -> DecisionTrigger:
    """gap + hypothesis → DecisionTrigger（02 §29 结构合成）。

    scope 取 gap.scope；exit 缺省 = entry 的一半（防抖，02 §30）；
    materiality_gate 固定 ACTIONABLE（02 §28：仅 Actionable 允许创建 DecisionCase）。
    """
    return DecisionTrigger(
        trigger_id=trigger_id or f"T-{gap.gap_id}",
        trigger_type=trigger_type,
        scope=gap.scope,
        required_gap=gap.gap_id,
        required_hypothesis=hypothesis,
        entry_threshold=entry_threshold,
        exit_threshold=(entry_threshold / 2 if exit_threshold is None
                        else exit_threshold),
        persistence=persistence,
        cooldown=cooldown_periods,
        allowed_problem_types=tuple(allowed_problem_types),
        policy_reference=policy_reference,
    )


def evaluate_trigger(trigger: DecisionTrigger,
                     gap: AllocationGap,
                     materiality_level: MaterialityLevel,
                     *,
                     persistence_periods: int,
                     confidence: float,
                     cooldown_remaining_periods: int = 0,
                     ) -> TriggerResult:
    """触发评估：滞回 → 冷却 → materiality 门 → 置信门 → persistence → entry。

    判定顺序（每步短路，返回理由可审计）：
    1. 幅度 ≤ exit_threshold           → NO_ACTION（02 §30 滞回退出）；
    2. 冷却未过且非 Critical           → NO_ACTION（02 §31，Critical 穿透）；
    3. materiality < materiality_gate  → 按等级降级：Review→REQUEST_MORE_EVIDENCE
      （02 §28：Review=进入诊断），Monitor→MONITOR，Informational→NO_ACTION；
    4. confidence < confidence_gate    → REQUEST_MORE_EVIDENCE（02 §29 置信门）；
    5. persistence 不足                → MONITOR（滞回等待）；
    6. 幅度 ≥ entry_threshold 且以上全过 → CREATE_DECISION_CASE（04 §27）；
       否则 MONITOR。
    """
    mag = gap.relative_magnitude()
    if mag <= trigger.exit_threshold:
        return TriggerResult(TriggerDecision.NO_ACTION,
                             f"幅度 {mag:.3f} ≤ exit {trigger.exit_threshold}（滞回退出，02 §30）",
                             trigger.trigger_id, materiality_level)
    if (cooldown_remaining_periods > 0
            and materiality_level is not MaterialityLevel.CRITICAL):
        return TriggerResult(TriggerDecision.NO_ACTION,
                             f"冷却期剩余 {cooldown_remaining_periods} 期（02 §31）",
                             trigger.trigger_id, materiality_level)
    if (MATERIALITY_ORDER[materiality_level]
            < MATERIALITY_ORDER[trigger.materiality_gate]):
        by_level = {
            MaterialityLevel.REVIEW: TriggerDecision.REQUEST_MORE_EVIDENCE,
            MaterialityLevel.MONITOR: TriggerDecision.MONITOR,
        }
        decision = by_level.get(materiality_level, TriggerDecision.NO_ACTION)
        return TriggerResult(decision,
                             f"materiality {materiality_level.value} 低于门槛 "
                             f"{trigger.materiality_gate.value}（02 §29 materiality_gate）",
                             trigger.trigger_id, materiality_level)
    if confidence < trigger.confidence_gate:
        return TriggerResult(TriggerDecision.REQUEST_MORE_EVIDENCE,
                             f"置信 {confidence:.2f} < gate {trigger.confidence_gate}（02 §29）",
                             trigger.trigger_id, materiality_level)
    if persistence_periods < trigger.persistence:
        return TriggerResult(TriggerDecision.MONITOR,
                             f"持续 {persistence_periods} 期 < 要求 {trigger.persistence} 期（02 §30）",
                             trigger.trigger_id, materiality_level)
    if mag >= trigger.entry_threshold:
        return TriggerResult(TriggerDecision.CREATE_DECISION_CASE,
                             f"幅度 {mag:.3f} ≥ entry {trigger.entry_threshold}，"
                             "仅创建 DecisionCase（04 §27）",
                             trigger.trigger_id, materiality_level)
    return TriggerResult(TriggerDecision.MONITOR,
                         f"幅度 {mag:.3f} 介于 exit/entry 之间（滞回带，02 §30）",
                         trigger.trigger_id, materiality_level)
