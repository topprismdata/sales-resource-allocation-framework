"""经销商区域分配工作台（中国语境：行政区划+主干道+河流围栏，借鉴 Salesforce Territory Management）。"""

from .models import (
    Assignment,
    Cause,
    DealerTerritoryModel,
    ModelStatus,
    RegionNode,
    Store,
    active_model,
)
from .assignment import manual_assign, match_nodes, rebuild_assignments, rule_assign
from .four_bounds import describe_fence, four_bounds, main_district
from . import fence_allocator, fence_analysis

__all__ = [
    "Assignment", "Cause", "DealerTerritoryModel", "ModelStatus", "RegionNode",
    "Store", "active_model", "manual_assign", "match_nodes",
    "rebuild_assignments", "rule_assign", "describe_fence", "four_bounds",
    "main_district", "fence_allocator", "fence_analysis",
]
