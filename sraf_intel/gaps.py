"""AllocationGap 数据类与缺口分类（WP13 / 04 规范最小实现）。

规范出处：
- 02_DECISION_ONTOLOGY.md §9  AllocationGap 统一结构（15 字段）
- 02_DECISION_ONTOLOGY.md §10 七个一级 Gap 类别
- 02_DECISION_ONTOLOGY.md §21 DataQualityIssue 的 4 个 identity 子类型
- 04_ALLOCATION_INTELLIGENCE.md §11A CoverageGap 漏斗细分（v1.2 子类型权威）
- 04_ALLOCATION_INTELLIGENCE.md §12  七类 Gap 的具体细分
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum

__all__ = [
    "GapType", "GapSubtype", "IDENTITY_SUBTYPES", "GAP_SUBTYPE_PARENT",
    "AllocationGap", "ALLOCATIONGAP_SCHEMA_FIELDS",
]


class GapType(str, Enum):
    """一级 Gap 类别，v1.2 固定七类（02 §10 / 04 §12）。"""

    COVERAGE = "CoverageGap"
    CAPACITY = "CapacityGap"
    OPPORTUNITY = "OpportunityGap"
    SPATIAL_TRAVEL = "SpatialTravelGap"
    CAPABILITY = "CapabilityGap"
    LOCAL_ALLOCATION = "LocalAllocationGap"   # 02 §16：禁止缩写为 AllocationGap
    STABILITY = "StabilityGap"


class GapSubtype(str, Enum):
    """具体缺口子类型（04 §1A：细分分类由 04 规范持有；02 §21：identity 四子型）。

    成员名即规范名；`GAP_SUBTYPE_PARENT` 给出向上归属。
    """

    # --- 04 §11A Coverage 漏斗（CoverageNeed → Commitment → Scheduled → Actual）---
    COVERAGE_ALLOCATION = "CoverageAllocationGap"    # Need → Commitment
    SCHEDULING_COVERAGE = "SchedulingCoverageGap"    # Commitment → Scheduled
    EXECUTION_COVERAGE = "ExecutionCoverageGap"      # Scheduled → Actual

    # --- 04 §12 Capacity：Global / Local / ResourceType / Temporal ---
    CAPACITY_GLOBAL = "CapacityGlobalGap"
    CAPACITY_LOCAL = "CapacityLocalGap"
    CAPACITY_RESOURCE_TYPE = "CapacityResourceTypeGap"
    CAPACITY_TEMPORAL = "CapacityTemporalGap"

    # --- 04 §12 Opportunity：Unserved / UnderServed / Misallocated ---
    OPPORTUNITY_UNSERVED = "OpportunityUnserved"
    OPPORTUNITY_UNDERSERVED = "OpportunityUnderServed"
    OPPORTUNITY_MISALLOCATED = "OpportunityMisallocated"

    # --- 04 §12 SpatialTravel：BaseLocation / TerritoryShape / RoadNetwork /
    #     CrossBoundaryTravel / RouteStructure ---
    TRAVEL_BASE_LOCATION = "SpatialTravelBaseLocation"
    TRAVEL_TERRITORY_SHAPE = "SpatialTravelTerritoryShape"
    TRAVEL_ROAD_NETWORK = "SpatialTravelRoadNetwork"
    TRAVEL_CROSS_BOUNDARY = "SpatialTravelCrossBoundary"
    TRAVEL_ROUTE_STRUCTURE = "SpatialTravelRouteStructure"

    # --- 02 §21 identity 子类型（DataQualityIssue 的身份侧细分）---
    # 判定规则与阈值归 08 §10–§14；此处仅做类型承载与路由（04 §28）。
    IDENTITY_DUPLICATE = "IdentityDuplicate"
    IDENTITY_FALSE_MATCH = "IdentityFalseMatch"
    IDENTITY_UNRESOLVED = "IdentityUnresolved"
    HIERARCHY_MISATTRIBUTION = "HierarchyMisattribution"


#: 02 §21 的四个 identity 子类型（判断规则归 08；类型与路由归本包）。
IDENTITY_SUBTYPES = frozenset({
    GapSubtype.IDENTITY_DUPLICATE,
    GapSubtype.IDENTITY_FALSE_MATCH,
    GapSubtype.IDENTITY_UNRESOLVED,
    GapSubtype.HIERARCHY_MISATTRIBUTION,
})

#: 子类型 → 一级 Gap 类别（identity 子型的父概念是 DataQualityIssue 根因，
#: 不是 Gap 类别，故为 None——路由时走 04 §28 的 World Model Repair）。
GAP_SUBTYPE_PARENT: dict[GapSubtype, GapType | None] = {
    GapSubtype.COVERAGE_ALLOCATION: GapType.COVERAGE,
    GapSubtype.SCHEDULING_COVERAGE: GapType.COVERAGE,
    GapSubtype.EXECUTION_COVERAGE: GapType.COVERAGE,
    GapSubtype.CAPACITY_GLOBAL: GapType.CAPACITY,
    GapSubtype.CAPACITY_LOCAL: GapType.CAPACITY,
    GapSubtype.CAPACITY_RESOURCE_TYPE: GapType.CAPACITY,
    GapSubtype.CAPACITY_TEMPORAL: GapType.CAPACITY,
    GapSubtype.OPPORTUNITY_UNSERVED: GapType.OPPORTUNITY,
    GapSubtype.OPPORTUNITY_UNDERSERVED: GapType.OPPORTUNITY,
    GapSubtype.OPPORTUNITY_MISALLOCATED: GapType.OPPORTUNITY,
    GapSubtype.TRAVEL_BASE_LOCATION: GapType.SPATIAL_TRAVEL,
    GapSubtype.TRAVEL_TERRITORY_SHAPE: GapType.SPATIAL_TRAVEL,
    GapSubtype.TRAVEL_ROAD_NETWORK: GapType.SPATIAL_TRAVEL,
    GapSubtype.TRAVEL_CROSS_BOUNDARY: GapType.SPATIAL_TRAVEL,
    GapSubtype.TRAVEL_ROUTE_STRUCTURE: GapType.SPATIAL_TRAVEL,
    GapSubtype.IDENTITY_DUPLICATE: None,
    GapSubtype.IDENTITY_FALSE_MATCH: None,
    GapSubtype.IDENTITY_UNRESOLVED: None,
    GapSubtype.HIERARCHY_MISATTRIBUTION: None,
}

#: 02 §9 AllocationGap 统一结构的全部字段名（规范一致性断言用）。
ALLOCATIONGAP_SCHEMA_FIELDS: tuple[str, ...] = (
    "gap_id", "gap_type", "scope", "period",
    "observed_value", "reference_value", "gap_value", "unit",
    "severity", "persistence", "business_impact",
    "confidence", "evidence", "baseline_snapshot", "calculation_version",
)


@dataclass(frozen=True)
class AllocationGap:
    """AllocationGap（02 §9 统一结构的最小落地）。

    形式定义（02 §9）：当前销售资源配置相对某业务需求、机会状态或可接受
    目标状态的可解释差异。字段与 02 §9 结构一一对应；`gap_value` 缺省时
    取 `observed_value - reference_value`。

    约束：
    - confidence / severity ∈ [0, 1]；
    - subtype 必须归属 gap_type（identity 子型除外，它们归属根因轴）。
    """

    gap_id: str
    gap_type: GapType
    scope: str
    period: str
    observed_value: float
    reference_value: float
    gap_value: float | None = None
    unit: str = ""
    subtype: GapSubtype | None = None
    severity: float = 0.0           # 业务影响度 0..1（BusinessImpact 量化代理）
    persistence: int = 1            # 连续观测期数（02 §27 Persistence）
    business_impact: str = ""
    confidence: float = 0.8
    evidence: tuple[dict, ...] = field(default_factory=tuple)
    baseline_snapshot: str = ""
    calculation_version: str = "sraf-intel@0.1.0"

    def __post_init__(self) -> None:
        if not self.gap_id:
            raise ValueError("gap_id 不能为空（02 §9）")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence 必须在 [0,1]，得到 {self.confidence}")
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError(f"severity 必须在 [0,1]，得到 {self.severity}")
        if self.gap_value is None:
            object.__setattr__(self, "gap_value",
                               self.observed_value - self.reference_value)
        if self.subtype is not None:
            parent = GAP_SUBTYPE_PARENT.get(self.subtype, "__unknown__")
            if parent == "__unknown__":
                raise ValueError(f"未知子类型: {self.subtype}")
            if parent is not None and parent is not self.gap_type:
                raise ValueError(
                    f"子类型 {self.subtype.value} 归属 {parent.value}，"
                    f"与 gap_type={self.gap_type.value} 不一致（02 §10A 分类归属）")

    def relative_magnitude(self) -> float:
        """|gap_value| / max(|reference_value|, ε)，截断到 [0,1]。

        供 04 §26 Materiality 的 Magnitude 因子使用。
        """
        denom = max(abs(self.reference_value), 1e-12)
        return min(abs(self.gap_value) / denom, 1.0)


def schema_field_names() -> tuple[str, ...]:
    """返回 AllocationGap 数据类的字段名元组（规范一致性自检用）。"""
    return tuple(f.name for f in fields(AllocationGap))
