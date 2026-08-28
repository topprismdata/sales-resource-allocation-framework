"""经销商区域分配工作台 — 数据模型。

设计借鉴（思路映射）：
- Salesforce Territory2Model -> DealerTerritoryModel：版本化，PLANNING/ACTIVE/ARCHIVED，
  同一时间仅一个 ACTIVE；改区域=建新版本规划、审批后激活切换。
- Salesforce Territory2 树   -> RegionNode：层级只用于检索（最低匹配节点胜出）与汇总，
  归属规则不继承。
- AssignmentRule / Association(cause=Manual) / IsExcludedFromRealign
  -> 规则归属 / 人工覆盖留痕 / excluded 例外名单。

中国语境：
- 区域底座 = 行政区划（省/市/区县/街道乡镇，dims 键：province/city/district/town）
  + 可选 channel（渠道）维度；"*" 表示该级不限。
- 主干道分界（"以枫林路为界，路东归A"）：以 RegionNode.note 记录边界表述；
  与行政区划对不齐的路段，走语义层 RoadSplit 建议并落到街道/门店清单。
- 经销商(dealer)承接区域；厂家直供门店走 excluded 名单。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Mapping


class ModelStatus(enum.Enum):
    PLANNING = "PLANNING"    # 规划中：可随意调整，不影响在线归属
    ACTIVE = "ACTIVE"        # 生效中：当前线上归属依据
    ARCHIVED = "ARCHIVED"    # 已被替代，只读可回溯


class Cause(enum.Enum):
    RULE = "RULE"        # 规则自动归属（IMPORT 导入视为规则的来源标记）
    MANUAL = "MANUAL"    # 人工覆盖（必须带 set_by / reason）


CHANNEL_ANY = "*"


@dataclass(frozen=True)
class RegionNode:
    """区域树节点：维度值组合定义一片合同区域，由某经销商承接。

    层级（parent_id）只用于展示与汇总；匹配不看层级，看维度兼容 + 具体度。
    """

    model_version: int
    node_id: str
    parent_id: str | None
    name: str
    dims: Mapping[str, str]          # 键: province/city/district/town(/channel)；"*"=不限
    dealer_id: str                   # 承接该片区域的经销商
    note: str = ""                   # 边界表述，如"以枫林路为界，含路东"（合同原文口径）

    def depth_specificity(self) -> int:
        """匹配优先级：非 ANY 的维度数越多越具体（最低匹配节点胜出）。"""
        return sum(1 for v in self.dims.values() if v and v != CHANNEL_ANY)


@dataclass(frozen=True)
class Store:
    """门店（网点）。dims 用于规则匹配；excluded = 不参与自动归属（KA 直供等）。"""

    store_id: str
    name: str
    dims: Mapping[str, str]
    tier: str = "B"                  # 客户分层（展示/统计用，MVP 不参与归属）
    excluded: bool = False


@dataclass(frozen=True)
class Assignment:
    """归属记录：某门店在某模型版本下归某节点/经销商。

    immutable：改归属 = 旧记录作废、新记录追加（append-only，与 08 同款纪律）。
    """

    model_version: int
    assignment_id: str
    store_id: str
    node_id: str
    dealer_id: str
    cause: Cause
    set_by: str = "system"
    reason: str = ""
    overwritten_rule_node_id: str | None = None   # MANUAL 覆盖时被顶掉的规则结果
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True)
class DealerTerritoryModel:
    """一个版本化的区域模型 = 区域树节点 + 归属记录（不可变集合）。"""

    version: int
    status: ModelStatus
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    nodes: tuple[RegionNode, ...] = ()
    assignments: tuple[Assignment, ...] = ()

    def with_(self, **kw) -> "DealerTerritoryModel":
        return replace(self, **kw)


def active_model(models: Mapping[int, "DealerTerritoryModel"]) -> "DealerTerritoryModel | None":
    for m in models.values():
        if m.status is ModelStatus.ACTIVE:
            return m
    return None
