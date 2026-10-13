"""sraf_intel — SRAF 04 规范「Allocation Intelligence」最小实现（WP13）。

覆盖 04 §1A 中承诺由实现承接的四个核心抽象：
- AllocationGap（02 §9 结构 + 02 §10 七类 + 02 §21 identity 四子型 + 04 §11A/§12 细分）
- Materiality（02 §25–§28 / 04 §24/§26）
- DecisionTrigger（02 §29–§31 / 04 §27）
- ProblemRouter（04 §28，DP01–DP07 编号见 03）

铁律（04 §27/§36）：Trigger 只创建 DecisionCase，绝不自动修改 Territory；
Router 不与 Solver Selector 合并；NoAction 必须是合法输出。
"""
from .gaps import (
    ALLOCATIONGAP_SCHEMA_FIELDS,
    AllocationGap,
    GAP_SUBTYPE_PARENT,
    GapSubtype,
    GapType,
    IDENTITY_SUBTYPES,
    schema_field_names,
)
from .materiality import (
    CONFIDENCE_FLOOR,
    IDENTITY_UNRESOLVED_RATIO_THRESHOLD,
    MATERIALITY_ORDER,
    MaterialityAssessment,
    MaterialityLevel,
    assess_materiality,
    cap_materiality,
)
from .router import (
    DIAGNOSIS_ROUTES,
    DPCode,
    NonDPRoute,
    ProblemRouter,
    RouteResult,
    RouterOutput,
    route_from_materiality,
)
from .trigger import (
    DECISIONTRIGGER_SCHEMA_FIELDS,
    DecisionTrigger,
    TriggerDecision,
    TriggerResult,
    build_trigger,
    evaluate_trigger,
)

__version__ = "0.1.0"

from .sizing import (
    AccountWorkload,
    MoveProposal,
    RepCapacity,
    balance_report,
    eq_index,
    rebalance_suggestions,
    required_reps,
    territory_loads,
)
from .fallback import NearbyCandidate, TerritoryContainer, nearby_candidates

__all__ = [
    # gaps（02 §9/§10/§21、04 §11A/§12）
    "AllocationGap", "GapType", "GapSubtype", "IDENTITY_SUBTYPES",
    "GAP_SUBTYPE_PARENT", "ALLOCATIONGAP_SCHEMA_FIELDS", "schema_field_names",
    # materiality（02 §25–§28、04 §24/§26）
    "MaterialityLevel", "MATERIALITY_ORDER", "MaterialityAssessment",
    "assess_materiality", "cap_materiality",
    "IDENTITY_UNRESOLVED_RATIO_THRESHOLD", "CONFIDENCE_FLOOR",
    # trigger（02 §29–§31、04 §27）
    "DecisionTrigger", "TriggerDecision", "TriggerResult",
    "build_trigger", "evaluate_trigger", "DECISIONTRIGGER_SCHEMA_FIELDS",
    # router（04 §28/§36）
    "ProblemRouter", "DPCode", "NonDPRoute", "RouterOutput", "RouteResult",
    "DIAGNOSIS_ROUTES", "route_from_materiality",
    # sizing（WP16：Zoltners 覆盖法 + EQ 均衡 + 迁转建议）
    "AccountWorkload", "RepCapacity", "MoveProposal",
    "territory_loads", "required_reps", "eq_index", "balance_report",
    "rebalance_suggestions",
    # fallback（WP16：nearby-containers 兜底，只建议不执行）
    "NearbyCandidate", "TerritoryContainer", "nearby_candidates",
]
