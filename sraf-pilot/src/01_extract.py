# -*- coding: utf-8 -*-
"""01_extract.py — T-101/T-102/T-103/T-104：P1 输入适配、地理层抽取、围栏筛区与坐标验证。

T-101（输入层，只读）：
1. 按 ``--src`` 定位五个客户源文件（只读，绝不写回源目录）；
2. 校验必需字段与结构（GeoJSON FeatureCollection、CSV 表头、数字字段）；
3. 安全解析 GeoJSON / CSV(utf-8-sig、超长字段) / WKT(shapely)。

T-102（地理层抽取）：
从三份官方 GeoJSON 中确定性抽取海珠(440105)+荔湾(440103)的单元、
区县与街道，无损转写为 WKT，产出 units.json / districts.json / streets.json。

T-103（围栏筛区与脏点留档，本卡增量）：
对两份围栏 CSV 执行冻结筛区规则：``overlap_ratio >= 0.5`` 入选；任一样本
落在 0.2~0.8 灰区立即输出 ESCALATION 并停止。src_id 取片区id 原值且文件内
唯一；名称不是主键，禁止按名去重，同名记录仅作留档观察。产出
fences_dealer.json / fences_yeidai.json 与人可读的 data_issues.md。

本模块不决定灰区取舍、不据围栏名称推断地理位置、不用门店位置作真值；
任何缺文件、结构不符、缺字段、非法数字、空/非法几何、主键重复都会抛出
带文件名与字段名的中文异常。全部计算先于全部写盘：任何失败都不产出
半成品文件。

T-104（坐标验证，契约 v1.3）：对全部经销商围栏做 §3.5.4 数字验证——
A 共配准（median_A_m < 1 m）+ C 转换自检（500 ≤ median_C_disp_m ≤ 750），
B（转 WGS 后最近边界距离）仅记录不判定；结论写入 crs_evidence.json。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

import shapely.geometry
import shapely.wkt

# 客户 CSV 的 fence 字段是超长 WKT（可超 128 KiB），先解除 Python csv 模块
# 默认单字段 131072 字符的上限，否则读入时会直接报
# "field larger than field limit"，数据根本读不进来。
csv.field_size_limit(sys.maxsize)

# intelligence 包按仓库根导入：本模块文件名以数字开头、由测试按路径加载，
# 不能假设调用方已把仓库根放进 sys.path，这里自行补一次（幂等）。
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from intelligence.coords import gcj2wgs  # noqa: E402  §3.5.4 冻结复用，禁止另写转换公式
from intelligence.world import haversine_km  # noqa: E402  冻结复用，禁止自写经纬度换算


class SourceDataError(Exception):
    """客户源数据不符合契约时抛出；消息为中文，含文件名与字段名。"""


# ---------------------------------------------------------------------------
# 源文件登记表：逻辑名 -> （文件名, 必需字段）
# ---------------------------------------------------------------------------

UNITS_FIELDS = ("区县编码", "街道[内置]", "中心点", "面积", "主键")
STREETS_FIELDS = ("行政区名称", "区域编码", "父级id")
DISTRICTS_FIELDS = ("行政区名称", "区域编码")
DEALER_FIELDS = (
    "片区id",
    "围栏名称",
    "fence",
    "中心点经度",
    "中心点纬度",
    "围栏面积",
)
# 业代围栏 = 经销商字段全量 + 办事处名称
YEIDAI_FIELDS = DEALER_FIELDS + ("办事处名称",)

SOURCES: dict[str, tuple[str, tuple[str, ...]]] = {
    "UNITS_SRC": (
        "边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson",
        UNITS_FIELDS,
    ),
    "STREETS_SRC": ("区划数据-街道-广东省-广州市.geojson", STREETS_FIELDS),
    "DISTRICTS_SRC": ("区划数据-区县-广东省-广州市.geojson", DISTRICTS_FIELDS),
    "DEALER_SRC": ("广州办事处经销商围栏数据-20260827.csv", DEALER_FIELDS),
    "YEIDAI_SRC": ("广州清单内业代的围栏数据-20260824.csv", YEIDAI_FIELDS),
}

GEOJSON_LOGICAL = ("UNITS_SRC", "STREETS_SRC", "DISTRICTS_SRC")
CSV_LOGICAL = ("DEALER_SRC", "YEIDAI_SRC")

# CSV 数字字段：中心点经纬度、围栏面积必须可解析为有限数字。
NUMERIC_FIELDS = ("中心点经度", "中心点纬度", "围栏面积")


# ---------------------------------------------------------------------------
# 异常辅助
# ---------------------------------------------------------------------------


def _fail(logical: str, reason: str, field: str | None = None) -> SourceDataError:
    """构造统一格式的中文异常：中文原因 + 文件名 +（可选）字段名。"""
    filename = SOURCES[logical][0]
    if field is not None:
        msg = f"{reason}（文件: {filename}，字段: {field}）"
    else:
        msg = f"{reason}（文件: {filename}）"
    return SourceDataError(msg)


# ---------------------------------------------------------------------------
# GeoJSON 读取
# ---------------------------------------------------------------------------


def locate_source(src_dir: Path, logical: str) -> Path:
    """确认 ``<src_dir>/<文件名>`` 存在；缺失即抛中文异常。"""
    path = src_dir / SOURCES[logical][0]
    if not path.is_file():
        raise _fail(logical, f"源文件不存在：缺少 {path}")
    return path


def _load_json(path: Path, logical: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise _fail(logical, f"JSON 解析失败：{exc}") from exc


def read_geojson(path: Path, logical: str) -> list[dict[str, Any]]:
    """读取 GeoJSON 并校验结构；返回 features 列表（properties 原样保留）。"""
    data = _load_json(path, logical)
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise _fail(logical, "顶层结构不是 FeatureCollection")
    features = data.get("features")
    if not isinstance(features, list):
        raise _fail(logical, "缺少 features 数组", "features")
    fields = SOURCES[logical][1]
    for i, feat in enumerate(features):
        if not isinstance(feat, dict) or feat.get("type") != "Feature":
            raise _fail(logical, f"第 {i} 个元素不是 Feature")
        props = feat.get("properties")
        if not isinstance(props, dict):
            raise _fail(logical, f"第 {i} 个 feature 的 properties 不是对象")
        for name in fields:
            if name not in props:
                raise _fail(logical, f"第 {i} 个 feature 缺少必需字段", name)
    return features


# ---------------------------------------------------------------------------
# CSV 读取
# ---------------------------------------------------------------------------


def _parse_float(value: Any, logical: str, field: str) -> float:
    """解析数字字段；非数字 / NaN / inf 均视为非法。"""
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise _fail(logical, f"字段值不是数字：{value!r}", field) from None
    if not math.isfinite(num):
        raise _fail(logical, f"字段值不是有限数字：{value!r}", field)
    return num


def read_csv_rows(path: Path, logical: str) -> list[dict[str, str]]:
    """按 utf-8-sig 读 CSV，校验表头并返回原始字符串行。

    - ``片区id`` 不做类型转换，按原值保留为字符串，供后继卡作 ``src_id``；
    - 数字字段（中心点经度/纬度、围栏面积）逐行校验；
    - 任何坏行直接抛异常，禁止跳过。
    """
    fields = SOURCES[logical][1]
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        for name in fields:
            if name not in header:
                raise _fail(logical, "表头缺少必需字段", name)
        rows: list[dict[str, str]] = []
        for lineno, row in enumerate(reader, start=2):  # 第 1 行是表头
            for name in fields:
                if row.get(name) is None:
                    raise _fail(logical, f"第 {lineno} 行缺少字段", name)
            for name in NUMERIC_FIELDS:
                _parse_float(row[name], logical, name)
            parse_fence_wkt(row["fence"], logical)
            rows.append(row)
    if not rows:
        raise _fail(logical, "数据行为空（只有表头）")
    return rows


# ---------------------------------------------------------------------------
# WKT 解析
# ---------------------------------------------------------------------------


def parse_fence_wkt(wkt_text: str, logical: str) -> Any:
    """解析 WKT 为 shapely 几何；空串/非法/空几何均抛异常。"""
    field = "fence"
    if not isinstance(wkt_text, str) or wkt_text.strip() == "":
        raise _fail(logical, "fence 是空串", field)
    try:
        geom = shapely.wkt.loads(wkt_text)
    except Exception as exc:
        raise _fail(logical, f"WKT 解析失败：{exc}", field) from exc
    if geom.is_empty:
        raise _fail(logical, "WKT 解析结果为空几何", field)
    return geom


# ---------------------------------------------------------------------------
# T-102：官方地理层抽取（单元 / 区县 / 街道）
# ---------------------------------------------------------------------------

# 试点范围冻结（CONTRACTS §2）：海珠 + 荔湾。禁止扩大或写成参数。
PILOT_DISTRICT_CODES = ("440105", "440103")


def _feature_geometry(feat: dict[str, Any], logical: str, index: int) -> Any:
    """取 feature 的 geometry 并转 shapely；缺失/空几何/非法坐标均抛中文异常。

    只做解析与非空校验，不校验拓扑合法性：源数据含 3 个试点区外的
    自相交街道面（花山/新塘/良口），若全量强校验拓扑，40 街道冻结裁定
    在真实数据上不可达成。拓扑合法性校验只施加于进入输出的要素。
    """
    raw = feat.get("geometry")
    if not isinstance(raw, dict) or not raw:
        raise _fail(logical, f"第 {index} 个 feature 缺少 geometry")
    try:
        geom = shapely.geometry.shape(raw)
    except (ValueError, KeyError, TypeError) as exc:
        raise _fail(logical, f"第 {index} 个 feature 几何非法：{exc}") from exc
    if not isinstance(geom, shapely.geometry.base.BaseGeometry) or geom.is_empty:
        raise _fail(logical, f"第 {index} 个 feature 是空几何")
    return geom


def _parse_centroid(text: Any, logical: str, index: int) -> list[float]:
    """解析 ``"lon,lat"`` 形式的中心点为 ``[lon, lat]`` 浮点数组。"""
    parts = str(text).split(",")
    if len(parts) != 2:
        raise _fail(logical, f"第 {index} 个单元中心点不是\"经度,纬度\"格式", "中心点")
    try:
        lon, lat = float(parts[0]), float(parts[1])
    except ValueError:
        raise _fail(
            logical, f"第 {index} 个单元中心点不是有限数字：{text!r}", "中心点"
        ) from None
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise _fail(logical, f"第 {index} 个单元中心点不是有限数字：{text!r}", "中心点")
    return [lon, lat]


def _parse_area_km2(text: Any, logical: str, index: int) -> float:
    """解析单元面积（km²）；非正数视为非法。"""
    area = _parse_float(text, logical, "面积")
    if area <= 0:
        raise _fail(logical, f"第 {index} 个单元面积不是正数：{text!r}", "面积")
    return area


def _unit_sort_key(unit: dict[str, Any]) -> tuple[str, str]:
    """单元输出的确定性排序键：区县编码升序，再按主键字典序。"""
    return (unit["district_code"], unit["key"])


def _require_unique_keys(units: list[dict[str, Any]], logical: str) -> None:
    """源主键在试点单元集合内必须唯一；重复即抛错，禁止静默取舍。"""
    seen: set[str] = set()
    for unit in units:
        if unit["key"] in seen:
            raise _fail(logical, f"单元源主键重复：{unit['key']}", "主键")
        seen.add(unit["key"])


def select_units(features: list[dict[str, Any]], logical: str = "UNITS_SRC") -> list[dict[str, Any]]:
    """按 ``区县编码`` 精确筛选试点单元并产出 units.json 行。

    源几何无损转写为 WKT（shapely wkt 往返已验证逐坐标相等），不做任何
    union/difference/简化/坐标转换。排序确定：区县编码升序 + 主键字典序；
    ``uid`` 即输出数组下标。
    """
    codes = set(PILOT_DISTRICT_CODES)
    units: list[dict[str, Any]] = []
    for index, feat in enumerate(features):
        props = feat["properties"]
        code = props["区县编码"]
        if code not in codes:
            continue
        geom = _feature_geometry(feat, logical, index)
        key = str(props["主键"]).strip()
        if not key:
            raise _fail(logical, f"第 {index} 个单元源主键为空", "主键")
        units.append(
            {
                "key": key,
                "district_code": code,
                "street": str(props["街道[内置]"]),
                "area_km2": _parse_area_km2(props["面积"], logical, index),
                "centroid": _parse_centroid(props["中心点"], logical, index),
                "geom": geom.wkt,
            }
        )
    if not units:
        raise _fail(logical, "筛选后试点单元为空（缺少 440105/440103 数据）")
    units.sort(key=_unit_sort_key)
    _require_unique_keys(units, logical)
    return [{"uid": i, **u} for i, u in enumerate(units)]


def select_districts(
    features: list[dict[str, Any]], logical: str = "DISTRICTS_SRC"
) -> list[dict[str, Any]]:
    """按 ``区域编码`` 精确筛选试点区县；缺任一目标编码即抛错。"""
    wanted = list(PILOT_DISTRICT_CODES)
    by_code: dict[str, dict[str, Any]] = {}
    for index, feat in enumerate(features):
        props = feat["properties"]
        code = props["区域编码"]
        if code in by_code:
            raise _fail(logical, f"区县编码重复：{code}", "区域编码")
        if code not in PILOT_DISTRICT_CODES:
            continue
        geom = _feature_geometry(feat, logical, index)
        by_code[code] = {
            "name": str(props["行政区名称"]),
            "code": code,
            "district_code": code,
            "geom": geom.wkt,
        }
    missing = [c for c in wanted if c not in by_code]
    if missing:
        raise _fail(logical, f"区县源缺少试点区编码：{'、'.join(missing)}")
    return [by_code[c] for c in wanted]


def select_streets(
    street_features: list[dict[str, Any]],
    district_features: list[dict[str, Any]],
    street_logical: str = "STREETS_SRC",
    district_logical: str = "DISTRICTS_SRC",
) -> list[dict[str, Any]]:
    """先全量校验街道→区县精确等值连接，再筛选试点街道。

    冻结裁定：``街道.父级id == 区县.区域编码`` 必须精确等值匹配；任何
    街道 ``父级id`` 不在完整区县编码集合中必须抛错，禁止模糊/名称/空间
    匹配或静默跳过。街道无法唯一连接父区县同样抛错。
    """
    district_codes = set()
    for feat in district_features:
        district_codes.add(feat["properties"]["区域编码"])
    joined: list[tuple[dict[str, Any], str]] = []
    for index, feat in enumerate(street_features):
        props = feat["properties"]
        parent = props["父级id"]
        if parent not in district_codes:
            raise _fail(
                street_logical,
                f"第 {index} 个街道的父级id {parent} 不在任何区县编码中（连接断裂）",
                "父级id",
            )
        if parent not in PILOT_DISTRICT_CODES:
            continue
        geom = _feature_geometry(feat, street_logical, index)
        if not geom.is_valid:
            raise _fail(
                street_logical,
                f"第 {index} 个街道（{props['行政区名称']}）几何拓扑非法，禁止直接转写",
            )
        joined.append(
            (
                {
                    "name": str(props["行政区名称"]),
                    "code": str(props["区域编码"]),
                    "district_code": parent,
                    "geom": geom.wkt,
                },
                parent,
            )
        )
    if not joined:
        raise _fail(street_logical, "筛选后试点街道为空（缺少 440105/440103 街道）")
    # 确定性排序：区县编码升序 + 街道编码升序。
    joined.sort(key=lambda pair: (pair[1], pair[0]["code"]))
    return [row for row, _ in joined]


def _write_json_atomic(path: Path, payload: Any) -> None:
    """确定性序列化（固定键序 + 紧凑分隔符）并原子写出（先写临时文件再替换）。"""
    text = json.dumps(payload, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def compute_pilot_geography(src_dir: Path) -> tuple[dict[str, Any], dict[str, int]]:
    """T-102 计算段：读取 → 校验 → 筛选，纯计算不写盘。

    返回（三个产物 payload、计数）；写盘由调用方在全部校验通过后统一执行，
    保证任何失败都不生成半成品文件。
    """
    unit_feats = read_geojson(locate_source(src_dir, "UNITS_SRC"), "UNITS_SRC")
    street_feats = read_geojson(locate_source(src_dir, "STREETS_SRC"), "STREETS_SRC")
    district_feats = read_geojson(locate_source(src_dir, "DISTRICTS_SRC"), "DISTRICTS_SRC")

    units = select_units(unit_feats)
    districts = select_districts(district_feats)
    streets = select_streets(street_feats, district_feats)

    payloads: dict[str, Any] = {
        "units.json": {"crs": "GCJ-02", "units": units},
        "districts.json": {"streets": districts},
        "streets.json": {"streets": streets},
    }
    counts = {"units": len(units), "districts": len(districts), "streets": len(streets)}
    return payloads, counts


# ---------------------------------------------------------------------------
# T-103：围栏筛区、规范化与脏点留档
# ---------------------------------------------------------------------------

# 冻结阈值（CONTRACTS §3.5.2）：入选下限与灰区边界，禁止写成参数。
OVERLAP_MIN = 0.5
GRAY_LOW = 0.2
GRAY_HIGH = 0.8

# 卡载预期：筛选后的真实输出条数。合成夹具不适用，仅用于真实数据终检。
EXPECTED_DEALER = 4
EXPECTED_YEIDAI = 17


class EscalationError(Exception):
    """冻结规则禁止自行取舍时抛出；消息以 ESCALATION: 开头。"""


def _escalate(question: str) -> EscalationError:
    return EscalationError(f"ESCALATION:{question}")


def _read_rows_with_lineno(path: Path, logical: str) -> list[tuple[int, dict[str, str]]]:
    """读 CSV 原始行并附带行号（从 2 起，第 1 行是表头）。

    不重复读表头校验——结构校验已由 ``extract_all``/``read_csv_rows`` 在
    上游完成；此处读出的行再逐行过 ``parse_fence_wkt`` 与数字字段校验，
    行号供 data_issues.md 留档引用。
    """
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return [(lineno, dict(row)) for lineno, row in enumerate(reader, start=2)]


def compute_fences(
    dealer_path: Path,
    yeidai_path: Path,
    pilot_union: Any,
) -> dict[str, Any]:
    """T-103 核心计算：解析全部围栏 → 筛区 → 规范化，纯计算不写盘。

    冻结规则（任务卡 + CONTRACTS §3.5.2/§3.5.3）：
    1. ``overlap_ratio = area(fence ∩ pilot_union) / area(fence)``，
       ``>= 0.5`` 入选；任一样本落在 0.2~0.8 灰区 → ESCALATION 停止；
    2. ``src_id`` = 片区id 原值（字符串），同一文件内重复 → 真重复 → 抛错；
    3. 名称不是主键：禁止按名去重，同名组仅进入 data_issues.md 留档。

    返回 dict 含 dealer_fences / yeidai_fences / issues_rows / counts，
    全部确定性排序（logical + 源行号），供调用方一次性写盘。
    """
    results: dict[str, Any] = {}
    issues_rows: list[dict[str, Any]] = []
    for logical, path in (("DEALER_SRC", dealer_path), ("YEIDAI_SRC", yeidai_path)):
        tagged = _read_rows_with_lineno(path, logical)
        # 逐行过输入层校验（WKT + 数字字段），与 T-101 契约保持一致。
        for lineno, row in tagged:
            parse_fence_wkt(row["fence"], logical)
            for name in NUMERIC_FIELDS:
                _parse_float(row[name], logical, name)
        # 真重复：同一文件内 src_id 相同必须抛错（名称去重被明令禁止）。
        seen_ids: dict[str, int] = {}
        for lineno, row in tagged:
            src_id = row["片区id"]
            if src_id in seen_ids:
                raise _fail(
                    logical,
                    f"第 {lineno} 行片区id {src_id} 与第 {seen_ids[src_id]} 行重复"
                    "（真重复，禁止静默取舍）",
                    "片区id",
                )
            seen_ids[src_id] = lineno
        fences: list[dict[str, Any]] = []
        for lineno, row in tagged:
            geom = parse_fence_wkt(row["fence"], logical)
            fence_area = float(row["围栏面积"])
            raw_ratio = (geom.intersection(pilot_union).area / geom.area
                         if geom.area > 0 else 0.0)
            # 交集面积数学上不可能超过自身面积；浮点舍入可能产生 1+ε，
            # 归约回 [0,1]，不影响任何阈值判定。
            ratio = min(1.0, max(0.0, raw_ratio))
            if GRAY_LOW <= ratio <= GRAY_HIGH:
                raise _escalate(
                    f"{row['片区id']} overlap_ratio={ratio:.4f} 落在灰区"
                    f"[{GRAY_LOW},{GRAY_HIGH}]，冻结规则禁止自行取舍"
                )
            record = {
                "name": row["围栏名称"],
                "src_id": row["片区id"],
                "area_km2": fence_area,
                "center": [float(row["中心点经度"]), float(row["中心点纬度"])],
                "overlap_ratio": ratio,
                "geom": geom.wkt,
            }
            if ratio >= OVERLAP_MIN:
                fences.append(record)
            issues_rows.append({
                "logical": logical,
                "lineno": lineno,
                "name": record["name"],
                "src_id": record["src_id"],
                "area_km2": fence_area,
                "center": record["center"],
                "overlap_ratio": ratio,
                "selected": ratio >= OVERLAP_MIN,
            })
        results[f"dealer_fences" if logical == "DEALER_SRC" else "yeidai_fences"] = fences
    results["issues_rows"] = issues_rows
    results["counts"] = {
        "dealer": len(results["dealer_fences"]),
        "yeidai": len(results["yeidai_fences"]),
    }
    return results


def _fmt_center(center: list[float]) -> str:
    return f"({center[0]:.4f},{center[1]:.4f})"


def build_data_issues_md(
    issues_rows: list[dict[str, Any]],
    counts: dict[str, int],
) -> str:
    """由逐条留档行生成人可读 Markdown（全部带数字，禁止无依据表述）。"""
    groups: dict[str, list[dict[str, Any]]] = {"DEALER_SRC": [], "YEIDAI_SRC": []}
    for row in issues_rows:
        groups[row["logical"]].append(row)
    lines: list[str] = [
        "# data_issues.md — T-103 脏点与筛区留档",
        "",
        "生成规则：CONTRACTS §3.5.2/§3.5.3 冻结裁定；全部判定基于 overlap_ratio 数字，",
        "未使用围栏名称、未使用门店位置、未按名称去重。",
        "",
        "## 0. 源数据观察（非脏点，仅记录）",
        "",
        "- 源数据存在 3 个自相交街道面：花山/新塘/良口，均在试点区外",
        "  （T-102 已留档：拓扑合法性只强校验进入输出的要素）。",
        "",
    ]
    tag = {"DEALER_SRC": SOURCES["DEALER_SRC"][0], "YEIDAI_SRC": SOURCES["YEIDAI_SRC"][0]}
    for logical in ("DEALER_SRC", "YEIDAI_SRC"):
        kind = "经销商" if logical == "DEALER_SRC" else "业代"
        rows = groups[logical]
        selected = [r for r in rows if r["selected"]]
        lines += [
            f"## {kind}（{tag[logical]}）",
            "",
            f"- 源数据行数：{len(rows)}；入选：{len(selected)}；"
            f"未入选：{len(rows) - len(selected)}",
            "- 判定式：`overlap_ratio = area(fence ∩ (海珠 ∪ 荔湾)) / area(fence)`，"
            "入选条件 `>= 0.5`",
            "",
            "| 行号 | 围栏名称 | 片区id | 面积km² | 中心点 | overlap_ratio | 是否入选 |",
            "|---:|---|---|---:|---|---:|---|",
        ]
        for r in rows:
            lines.append(
                f"| {r['lineno']} | {r['name']} | {r['src_id']} | {r['area_km2']:.4f} "
                f"| {_fmt_center(r['center'])} | {r['overlap_ratio']:.4f} "
                f"| {'是' if r['selected'] else '否'} |"
            )
        lines.append("")
        # 同名组留档：只对出现 >= 2 次的名称逐组列出，不做任何取舍动作。
        name_rows: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            name_rows.setdefault(r["name"], []).append(r)
        dup_in_file = {n: rs for n, rs in name_rows.items() if len(rs) >= 2}
        if dup_in_file:
            lines += ["### 同名不同位置留档", ""]
            for name, rs in dup_in_file.items():
                lines.append(f"- **{name}**：出现 {len(rs)} 次，未按名称去重，逐条独立判定：")
                for r in rs:
                    lines.append(
                        f"  - 行 {r['lineno']} / src_id {r['src_id']}：面积 {r['area_km2']:.2f} km²，"
                        f"中心点 {_fmt_center(r['center'])}，overlap_ratio {r['overlap_ratio']:.4f}，"
                        f"{'入选' if r['selected'] else '未入选'}"
                    )
            lines.append("")
    caitao = next(
        (r for r in groups["DEALER_SRC"] if "财涛" in r["name"]), None
    )
    if caitao is not None:
        lines += [
            "## 被排除围栏：财涛食品",
            "",
            f"- `广州市财涛食品有限公司`（行 {caitao['lineno']} / src_id {caitao['src_id']}）："
            f"overlap_ratio = {caitao['overlap_ratio']:.4f}（约 {caitao['overlap_ratio'] * 100:.1f}%），"
            f"低于 0.5 阈值被排除。面积 {caitao['area_km2']:.4f} km²，"
            f"中心点 {_fmt_center(caitao['center'])}。",
            "",
        ]
    lines += [
        "## 结果计数",
        "",
        f"- 经销商入选：{counts['dealer']} 条（预期 {EXPECTED_DEALER}）",
        f"- 业代入选：{counts['yeidai']} 条（预期 {EXPECTED_YEIDAI}）",
        "",
    ]
    return "\n".join(lines)

def compute_pilot_fences(src_dir: Path, districts_payload: dict[str, Any]) -> dict[str, Any]:

    """T-103 计算段：区县逻辑合并 → 围栏筛区 → 留档文本，纯计算不写盘。

    海珠 ∪ 荔湾 用 shapely 并集（区县级一次性并集，非围栏多边形手术，
    不违反 D11）。全部校验（含灰区 ESCALATION 与真重复检查）都在本函数内
    完成，失败即抛出，不产生任何写盘副作用。
    """
    rows = districts_payload.get("streets") if isinstance(districts_payload, dict) else None
    if not isinstance(rows, list) or len(rows) == 0:
        raise _fail("DISTRICTS_SRC", "districts 产物缺少 streets 数组或为空")
    by_code = {r.get("code"): r for r in rows if isinstance(r, dict)}
    missing = [c for c in PILOT_DISTRICT_CODES if c not in by_code]
    if missing:
        raise _fail("DISTRICTS_SRC", f"区县产物缺少试点区编码：{'、'.join(missing)}")
    geoms = [shapely.wkt.loads(by_code[c]["geom"]) for c in PILOT_DISTRICT_CODES]
    pilot_union = shapely.union_all(geoms)

    computed = compute_fences(
        locate_source(src_dir, "DEALER_SRC"),
        locate_source(src_dir, "YEIDAI_SRC"),
        pilot_union,
    )
    payloads: dict[str, Any] = {
        "fences_dealer.json": {"fences": computed["dealer_fences"]},
        "fences_yeidai.json": {"fences": computed["yeidai_fences"]},
        "data_issues.md": build_data_issues_md(computed["issues_rows"], computed["counts"]),
    }
    return payloads


# ---------------------------------------------------------------------------
# T-104：坐标系数字验证（CONTRACTS §3.5.4，全部参数冻结，禁止自行调整）
# ---------------------------------------------------------------------------

import shapely.ops


class CrsNotMeasurableError(Exception):
    """单元几何全部退化（如 Point 夹具，无边界）时 §3.5.4 无法测量。"""

CRS_METHOD = "3.5.4-v1.3"  # 证据 schema 的 method 字段
VERTEX_CAP = 200           # 每条围栏顶点等距抽样上限
A_THRESHOLD_M = 1.0        # 判据①：median_A_m < 1 m（共配准，顶点级重合）
C_DISP_LOW_M = 500.0       # 判据②：median_C_disp_m >= 500 m（转换自检）
C_DISP_HIGH_M = 750.0      # 且 <= 750 m：位移量符合 D13 广州 ~623 m


def _sample_ring_vertices(geom: Any, cap: int = VERTEX_CAP) -> list[tuple[float, float]]:
    """围栏顶点的确定性等距抽样（§3.5.4）。

    围栏可能是 MultiPolygon：不能直接取 .boundary（MultiPolygon 无此属性，
    Polygon 直接取会漏掉内环），先展开 ``geoms``（Polygon 则视作单元素），
    按序取每个部分的全部环顶点（shapely get_coordinates 顺序，确定性）。
    闭合点与首点重复时去掉尾点；顶点数 <= cap 全取，否则按下标
    ``(i * n) // cap`` 等距取 cap 个（含首点、严格递增、纯整数运算，
    同输入必同输出）。
    """
    parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    pts: list[tuple[float, float]] = []
    for part in parts:
        coords = shapely.get_coordinates(part.boundary)
        ring = [(float(x), float(y)) for x, y in coords]
        if len(ring) > 1 and ring[0] == ring[-1]:
            ring = ring[:-1]  # 每个部分各自去掉闭合点，拼接后不产生中间重复
        pts.extend(ring)
    n = len(pts)
    if n <= cap:
        return pts
    return [pts[(i * n) // cap] for i in range(cap)]


def _min_boundary_distance_m(pt: tuple[float, float], tree: Any, boundaries: list[Any]) -> float:
    """样本点到全部单元边界的最近距离（米）。

    最近边界由 STRtree.nearest 按平面度数选出，再用 shapely 最近点对拿到
    边界上的最近点坐标；米制换算只允许 haversine_km（冻结复用）。
    单元几何全程保持原样，两组对照都不转换（D13 不变量）。
    """
    point = shapely.geometry.Point(pt)
    idx = int(tree.nearest(point))
    on_boundary = shapely.ops.nearest_points(boundaries[idx], point)[0]
    return haversine_km(pt, (float(on_boundary.x), float(on_boundary.y))) * 1000.0


def compute_crs_evidence(
    units_payload: dict[str, Any], fences: list[dict[str, Any]]
) -> dict[str, Any]:
    """T-104 核心（契约 v1.3）：A 共配准 + C 位移自检 → §3.5.4 判定。纯计算不写盘。

    对照 A：围栏顶点保持原坐标到最近单元边界的距离；对照 B：仅围栏顶点经
    gcj2wgs 后的同一距离（记录性指标，诊断网格密度，不参与判定）；C：每
    顶点自身位移前后的 haversine 距离（转换自检）。单元几何两组对照都保持
    原样；每顶点只调一次 gcj2wgs，转换点同时用于 B 路径与 C 位移。
    判定式冻结（v1.3）：
    ``median_A_m < 1 and 500 <= median_C_disp_m <= 750 → SAME_CRS_GCJ02``，
    否则 ``INCONCLUSIVE``（不得下坐标结论，由 CLI 门禁非零退出）。
    """
    boundaries = [shapely.wkt.loads(u["geom"]).boundary for u in units_payload["units"]]
    if not any(not b.is_empty for b in boundaries):
        # 单元无任何有效边界（合成夹具的 Point 单元）：§3.5.4 不可测量，
        # 不制造伪证据、不做坐标结论；真实数据为多边形单元，不受影响。
        raise CrsNotMeasurableError("全部单元几何无有效边界，§3.5.4 无法测量")
    boundaries = [b for b in boundaries if not b.is_empty]
    tree = shapely.STRtree(boundaries)
    all_a: list[float] = []
    all_b: list[float] = []
    all_c: list[float] = []
    per_fence: list[dict[str, Any]] = []
    for fence in fences:
        verts = _sample_ring_vertices(shapely.wkt.loads(fence["geom"]))
        dist_a: list[float] = []
        dist_b: list[float] = []
        dist_c: list[float] = []
        for v in verts:
            dist_a.append(_min_boundary_distance_m(v, tree, boundaries))
            q = gcj2wgs(*v)
            dist_b.append(_min_boundary_distance_m(q, tree, boundaries))
            dist_c.append(haversine_km(v, q) * 1000.0)
        all_a.extend(dist_a)
        all_b.extend(dist_b)
        all_c.extend(dist_c)
        per_fence.append(
            {
                "src_id": fence["src_id"],
                "name": fence["name"],
                "n_vertices": len(verts),
                "median_A_m": statistics.median(dist_a),
                "median_B_m": statistics.median(dist_b),
                "median_C_disp_m": statistics.median(dist_c),
            }
        )
    median_a = statistics.median(all_a)
    median_b = statistics.median(all_b)
    median_c = statistics.median(all_c)
    areas = [float(u["area_km2"]) for u in units_payload["units"]]
    unit_median_area = statistics.median(areas)
    half_cell_m = math.sqrt(unit_median_area) * 1000.0 / 2.0
    same = median_a < A_THRESHOLD_M and C_DISP_LOW_M <= median_c <= C_DISP_HIGH_M
    return {
        "method": CRS_METHOD,
        "n_fences": len(fences),
        "vertex_cap": VERTEX_CAP,
        "median_A_m": median_a,
        "median_B_m": median_b,
        "median_C_disp_m": median_c,
        "unit_median_area_km2": unit_median_area,
        "grid_half_cell_m": half_cell_m,
        "verdict": "SAME_CRS_GCJ02" if same else "INCONCLUSIVE",
        "per_fence": per_fence,
    }

def build_crs_issues_section(evidence: dict[str, Any]) -> str:
    """§3.5.4 结论与 A/C 数值的 data_issues.md 追加段（只写数字与判定）。"""
    lines = [
        "## 坐标系验证（CONTRACTS §3.5.4，T-104）",
        "",
        f"- 方法 `{evidence['method']}`：全部 {evidence['n_fences']} 条经销商围栏、"
        f"每条顶点等距抽样至多 {evidence['vertex_cap']} 点；距离仅用 "
        "`intelligence.world.haversine_km`；对照 B/C 仅围栏顶点经 "
        "`intelligence.coords.gcj2wgs`；单元几何全程保持原样。",
        f"- 总体：median_A_m = {evidence['median_A_m']:.4f}，"
        f"median_B_m = {evidence['median_B_m']:.1f}（记录性，不判定），"
        f"median_C_disp_m = {evidence['median_C_disp_m']:.1f}，"
        f"grid_half_cell_m = {evidence['grid_half_cell_m']:.1f}",
        f"- 判定式 `median_A_m < 1 and 500 <= median_C_disp_m <= 750` → "
        f"**{evidence['verdict']}**（同一结论已写入 `crs_evidence.json`）",
        "",
        "| src_id | 围栏名称 | 顶点数 | median_A_m | median_B_m | median_C_disp_m |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for f in evidence["per_fence"]:
        lines.append(
            f"| {f['src_id']} | {f['name']} | {f['n_vertices']} "
            f"| {f['median_A_m']:.4f} | {f['median_B_m']:.1f} "
            f"| {f['median_C_disp_m']:.1f} |"
        )
    lines += [
        "",
        "若判定为 `INCONCLUSIVE`：不下坐标结论，CLI 以 `[GATE-FAIL]` 非零退出。",
        "",
    ]
    return "\n".join(lines)


def write_pilot_outputs(
    src_dir: Path, out_dir: Path
) -> tuple[dict[str, int], dict[str, Any] | None]:
    """P1 主流程：全部计算 → 全部校验 → 一次性写出全部产物。

    任何失败（缺文件、结构不符、灰区 ESCALATION、真重复）都发生在任何
    写盘之前：不产生副作用、不生成半成品文件。返回（产物计数，
    §3.5.4 坐标证据；无经销商围栏样本时证据为 None，不做坐标结论）。
    """
    geo_payloads, geo_counts = compute_pilot_geography(src_dir)
    fence_payloads = compute_pilot_fences(src_dir, geo_payloads["districts.json"])
    dealer_fences = fence_payloads["fences_dealer.json"]["fences"]
    crs_evidence: dict[str, Any] | None = None
    if dealer_fences:
        # §3.5.4 坐标验证：仅在有经销商围栏样本时产出证据（无样本不制造
        # n_fences=0 的伪证据）；units/fence 几何一律原样，不做任何转换。
        try:
            crs_evidence = compute_crs_evidence(geo_payloads["units.json"], dealer_fences)
            fence_payloads["crs_evidence.json"] = crs_evidence
            fence_payloads["data_issues.md"] = (
                fence_payloads["data_issues.md"] + "\n"
                + build_crs_issues_section(crs_evidence)
            )
        except CrsNotMeasurableError:
            crs_evidence = None
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in {**geo_payloads, **fence_payloads}.items():
        if name.endswith(".json"):
            _write_json_atomic(out_dir / name, payload)
        else:
            (out_dir / name).write_text(payload, encoding="utf-8")
    counts = {
        "units": geo_counts["units"],
        "districts": geo_counts["districts"],
        "streets": geo_counts["streets"],
        "dealer_fences": len(fence_payloads["fences_dealer.json"]["fences"]),
        "yeidai_fences": len(fence_payloads["fences_yeidai.json"]["fences"]),
    }
    return counts, crs_evidence



# ---------------------------------------------------------------------------
# 抽取入口与 CLI
# ---------------------------------------------------------------------------




def extract_all(src_dir: Path) -> dict[str, int]:
    """T-101 校验入口：只读解析全部五个源文件；全部合法则返回条目计数。

    纯只读校验，不写任何文件；供 CLI 调用方与测试单独验证输入契约。
    """
    counts: dict[str, int] = {}
    for logical in GEOJSON_LOGICAL:
        counts[logical] = len(read_geojson(locate_source(src_dir, logical), logical))
    for logical in CSV_LOGICAL:
        counts[logical] = len(read_csv_rows(locate_source(src_dir, logical), logical))
    return counts


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="T-101/T-102/T-103：输入层校验 + 地理层抽取 + 围栏筛区。",
    )
    parser.add_argument(
        "--src",
        required=True,
        help="客户源数据目录（只读；必须显式传入，无默认值）",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="产物输出目录（由调用者指定）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    src_dir = Path(args.src)
    if not src_dir.is_dir():
        print(f"错误：--src 目录不存在：{src_dir}", file=sys.stderr)
        return 2

    # 先 T-101 全量输入校验，再做全部计算，最后一次性写盘：
    # 任何失败（含灰区 ESCALATION 与真重复）都不产生副作用、不生成半成品。
    counts = extract_all(src_dir)
    try:
        produced, crs = write_pilot_outputs(src_dir, Path(args.out))
    except EscalationError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(
        "校验通过："
        + "，".join(f"{k}={v}" for k, v in counts.items())
        + "；产物："
        + "，".join(f"{k}={v}" for k, v in produced.items())
        + f"；输出目录：{args.out}"
    )
    if crs is None:
        # 无经销商围栏样本或单元边界不可测：§3.5.4 未执行，不做任何坐标结论。
        print("坐标验证 §3.5.4：未执行（无经销商围栏样本或单元边界不可测）；不做坐标结论")
        return 0
    print(
        f"坐标验证 §3.5.4：median_A_m={crs['median_A_m']:.4f}，"
        f"median_B_m={crs['median_B_m']:.1f}，"
        f"median_C_disp_m={crs['median_C_disp_m']:.1f}，"
        f"grid_half_cell_m={crs['grid_half_cell_m']:.1f} → {crs['verdict']}"
    )
    if crs["verdict"] != "SAME_CRS_GCJ02":
        print(
            f"[GATE-FAIL] ESCALATION:A={crs['median_A_m']:.4f}m,"
            f"C={crs['median_C_disp_m']:.1f}m：未满足 median_A_m<1 且 "
            "500<=median_C_disp_m<=750，不得下坐标结论",
            file=sys.stderr,
        )
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
