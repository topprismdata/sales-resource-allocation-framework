# -*- coding: utf-8 -*-
"""03_dsl.py — T-301：P3 只读输入契约、DSL 节点校验与三级名称解析。

职责边界（T-301 输入契约与三级名称解析；T-302 四原语确定性求值器；
T-303 ``execute`` 最终输出汇总；T-502 接入 P5 线要素输入、六原语 schema
与线名三级解析）：
- 只读加载并严格校验 P1/P2 产物 ``units.json`` / ``streets.json`` /
  ``districts.json`` / ``unit_graph.json`` 与 P5 产物 ``lines.json``；
  任一不符契约即抛 PilotInputError（中文，含文件路径与具体原因）。
- ``validate_rule``：接受 CONTRACTS §4.2 六原语
  （in_street / in_district / union / minus / side_of / near），逐节点校验
  字段集合与 arity；未知 op、额外字段、缺字段、非法数值、非对象节点均抛
  DslError（中文，含 ``$.args[i]`` / ``$.scope`` 形式的节点位置）。
  side_of / near 的 schema 边界与线名三级解析由 T-502 建立；T-503 在此之上
  实现两原语的无副作用确定性求值（见下）。
- ``resolve_street`` / ``resolve_district`` / ``resolve_line``：三级名称解析
  精确 → 去末尾后缀（街道/镇/区）→ 包含匹配；在某一级得到唯一匹配即返回；
  任一级匹配 >1 个、或三级用尽仍 0 个 → 抛 DslError。
  明令禁止：静默取第一个；复刻主线 ``lookup_geometry`` 的两字前缀兜底；
  跨类型查找（街道只在街道表内解析，区县只在区县表内解析，线名只在线表内
  解析）。
- T-302：四原语确定性求值器；T-303：``execute`` 输出汇总（components /
  area_km2 / rule / warnings 五字段）。
- T-502：``load_lines`` 严格校验 ``lines.json``（p5-lines-v1），交叉断言
  counts 与几何 part 数；``resolve_line`` 复用同一三级阶段机。

明令禁止（T-503 冻结，违反即返工）：
- ``side_of``：对每个候选单元仅使用落盘质心；在质心所在纬度建立局部东西/
  南北平面（经度差乘 ``cos(radians(lat))``），对命中线按 part/段顺序枚举
  相邻点段做钳制投影，取最近段的方向为**局部切线**（禁止整线首尾向量、
  全线 PCA 或 bbox），八方位向量与叉积同号判定选中；并列 ``1e-15`` 内取
  part/段 index 较小者保证确定性。反转线点序结果不变。
- ``near``：逐单元严格调用 ``intelligence.world.haversine_km``，距离
  ``<= radius_km`` 选中（等号包含）；禁止自写换算、投影距离或坐标转换。
- 非空纪律：side_of / near 自身结果为空、或任何含 P5 原语的表达式经
  union/minus 组装后为空，都必须显式抛 DslError（中文，含 op 与定位）；
  纯 P3 规则保持 v1.7 语义（``minus(X,X)`` 合法空集）。
- 不做任何坐标转换（全程 GCJ-02）；
- 单元/区县几何仅接受非空 Polygon/MultiPolygon，线几何仅接受非空
  LineString/MultiLineString；Multi* 一律走 ``.geoms`` 展开，不触碰
  ``.exterior``；
- 输入只读：不修改传入的 DSL 树、units / streets / districts / graph /
  lines 对象，不写任何文件、不访问网络。
- components 只在 L1 官方单元邻接图的诱导子图上计数并只报告（D-9）：
  不修补、不连通、不改变所选集合；禁止用几何 union 环数、单元 street
  分组或 L2 细面充当 components / area_km2。
"""

import copy
import json
import math
from pathlib import Path
from typing import Any

import shapely
import shapely.wkt

try:
    import sys

    from intelligence.world import haversine_km
except ModuleNotFoundError:
    # 与 01/02/05 模块同一模式：文件名以数字开头、由测试按路径加载时
    # 仓库根不在 sys.path，这里自行补一次（幂等）。
    _REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from intelligence.world import haversine_km


class PilotInputError(Exception):
    """P1/P2 产物不符合契约时抛出；消息为中文，含文件路径与具体原因。"""


class DslError(Exception):
    """DSL 节点非法或名称解析失败时抛出；消息为中文，含节点位置/查询名与原因。"""


# ---------------------------------------------------------------------------
# 契约常量（与 CONTRACTS §3.3 / §4 逐字对齐，禁止放宽）
# ---------------------------------------------------------------------------

EXPECTED_CRS = "GCJ-02"

EXPECTED_LINES_SCHEMA_VERSION = "p5-lines-v1"
EXPECTED_LINES_SOURCE_CRS = "WGS-84"
LINE_CLASSES = ("highway", "waterway", "railway")
SHA256_HEX_CHARS = frozenset("0123456789abcdef")

# 几何只接受这两种非空类型；MultiPolygon 没有 .exterior，代码路径禁止触碰该属性。
GEOM_TYPES = ("Polygon", "MultiPolygon")

# 线几何只接受这两种非空类型；MultiLineString 一律经 .geoms 展开。
LINE_GEOM_TYPES = ("LineString", "MultiLineString")

UNIT_FIELDS = ("uid", "key", "district_code", "street", "area_km2", "centroid", "geom")
AREA_FIELDS = ("name", "code", "district_code", "geom")  # streets.json / districts.json 行
LINE_FIELDS = ("name", "classes", "osm_way_ids", "geom")  # lines.json 行

UNITS_FILENAME = "units.json"
STREETS_FILENAME = "streets.json"
DISTRICTS_FILENAME = "districts.json"
UNIT_GRAPH_FILENAME = "unit_graph.json"
LINES_FILENAME = "lines.json"

LINK_MIN_M = 50  # 冻结常数（CONTRACTS §3.4 / T-202 产物），禁止放宽

# 六原语（T-502 扩展：side_of / near schema 本卡接受，求值归 T-503）。
LEAF_OPS = ("in_street", "in_district")
COMPOSITE_OPS = ("union", "minus")
P5_OPS = ("side_of", "near")
ALL_OPS = LEAF_OPS + COMPOSITE_OPS + P5_OPS
P5_SIDE_OF, P5_NEAR = P5_OPS

# side_of 八方位（T-502 冻结；快速实验四方位 0.6765 → 八方位 0.7931，
# 斜向贡献 0.12，不得退回四方位）。不接受英文、缩写、组合词或模糊匹配。
SIDE_DIRS = ("北", "南", "东", "西", "东北", "东南", "西北", "西南")

# 名称解析允许剥离的末尾后缀（CONTRACTS §4.3：去后缀（街道/镇/区））。
# 顺序无关紧要：三者互不为彼此后缀（“街道”结尾是“道”）。
NAME_SUFFIXES = ("街道", "镇", "区")

# DSL 树嵌套深度上限：防止循环引用导致无限递归（JSON 本身不可序列化循环对象，
# 但校验器直接面对内存对象，必须受控终止）。
MAX_RULE_DEPTH = 128


# ---------------------------------------------------------------------------
# 通用校验辅助（对齐 02_units.py 既有模式）
# ---------------------------------------------------------------------------


def _fail(path: Path, reason: str) -> PilotInputError:
    """统一中文异常格式：文件路径 + 原因。"""
    return PilotInputError(f"{path}：{reason}")


def load_json_object(path: Path) -> dict[str, Any]:
    """读取 UTF-8 JSON 且顶层必须是对象；缺失/编码错误/解析失败/非对象均抛中文异常。"""
    path = Path(path)
    if not path.is_file():
        raise _fail(path, "输入文件缺失")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise _fail(path, f"文件不是合法 UTF-8：{exc}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _fail(path, f"JSON 解析失败：{exc}") from exc
    if not isinstance(payload, dict):
        raise _fail(path, f"JSON 顶层必须是对象（dict），实际为 {type(payload).__name__}")
    return payload


def _require_top_keys(path: Path, payload: dict[str, Any], expected: tuple[str, ...]) -> None:
    """顶层键集合必须与契约完全一致（缺失或多余都算不符）。"""
    actual = tuple(payload.keys())
    if set(actual) != set(expected):
        raise _fail(
            path,
            f"顶层键集合不符：期望 {sorted(expected)}，实际为 {sorted(actual)}",
        )


def _require_row_fields(path: Path, row: Any, index: int, expected: tuple[str, ...]) -> dict[str, Any]:
    """行必须是对象且字段集合与契约完全一致。"""
    if not isinstance(row, dict):
        raise _fail(path, f"[{index}] 必须是对象，实际为 {type(row).__name__}")
    if set(row.keys()) != set(expected):
        raise _fail(
            path,
            f"[{index}] 字段集合不符：期望 {sorted(expected)}，实际为 {sorted(row.keys())}",
        )
    return row


def _require_nonempty_str(path: Path, label: str, value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(path, f"{label} 的 {field} 必须是非空字符串，实际为 {value!r}")
    return value


def _require_finite(path: Path, label: str, value: Any, field: str, *, positive: bool = False) -> float:
    """数字字段：接受 int/float（bool 除外），必须是有限值；positive 时还须 > 0。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(path, f"{label} 的 {field} 必须是数字，实际为 {value!r}")
    num = float(value)
    if not math.isfinite(num):
        raise _fail(path, f"{label} 的 {field} 必须是有限数字，实际为 {value!r}")
    if positive and num <= 0:
        raise _fail(path, f"{label} 的 {field} 必须是正数，实际为 {num}")
    return num


def _require_lonlat(path: Path, label: str, value: Any, field: str) -> list[float]:
    """坐标对字段：形如 ``[lon, lat]`` 的二元数组，元素均为有限数字。"""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise _fail(path, f"{label} 的 {field} 必须是 [lon, lat] 二元数组，实际为 {value!r}")
    lon = _require_finite(path, label, value[0], f"{field}[0]")
    lat = _require_finite(path, label, value[1], f"{field}[1]")
    return [lon, lat]


def parse_payload_wkt(wkt_text: Any, path: Path, label: str) -> Any:
    """解析 WKT 为 shapely 几何；非字符串/非法/空几何/类型不符均抛中文异常。"""
    if not isinstance(wkt_text, str) or not wkt_text.strip():
        raise _fail(path, f"{label} 的 geom 必须是非空 WKT 字符串，实际为 {wkt_text!r}")
    try:
        geom = shapely.wkt.loads(wkt_text)
    except Exception as exc:  # shapely 解析错误类型随版本变化，统一转契约异常
        raise _fail(path, f"{label} 的 geom WKT 解析失败：{exc}") from exc
    if geom.is_empty:
        raise _fail(path, f"{label} 的 geom 是空几何（仅接受非空 {'/'.join(GEOM_TYPES)}）")
    if geom.geom_type not in GEOM_TYPES:
        raise _fail(
            path,
            f"{label} 的 geom 类型是 {geom.geom_type}（仅接受 {'/'.join(GEOM_TYPES)}）",
        )
    return geom


def parse_line_wkt(wkt_text: Any, path: Path, label: str) -> Any:
    """解析线 WKT：仅接受非空 LineString/MultiLineString；
    每个 part 至少两个不同点（退化单点线一律拒绝）。
    """
    if not isinstance(wkt_text, str) or not wkt_text.strip():
        raise _fail(path, f"{label} 的 geom 必须是非空 WKT 字符串，实际为 {wkt_text!r}")
    try:
        geom = shapely.wkt.loads(wkt_text)
    except Exception as exc:
        raise _fail(path, f"{label} 的 geom WKT 解析失败：{exc}") from exc
    if geom.is_empty:
        raise _fail(
            path,
            f"{label} 的 geom 是空几何（仅接受非空 {'/'.join(LINE_GEOM_TYPES)}）",
        )
    if geom.geom_type not in LINE_GEOM_TYPES:
        raise _fail(
            path,
            f"{label} 的 geom 类型是 {geom.geom_type}"
            f"（仅接受 {'/'.join(LINE_GEOM_TYPES)}）",
        )
    parts = [geom] if geom.geom_type == "LineString" else list(geom.geoms)
    for j, part in enumerate(parts):
        if len(set(part.coords)) < 2:
            raise _fail(path, f"{label} 的 geom 第 {j} 个 part 退化（少于两个不同点）")
    return geom


# ---------------------------------------------------------------------------
# 输入加载与 schema 校验（只读；uid 冻结契约在此强制）
# ---------------------------------------------------------------------------


def load_units(data_dir: Path) -> tuple[list[dict[str, Any]], list[Any]]:
    """加载并校验 ``units.json``；返回（原样行列表, 已解析几何列表）。

    契约：顶层键恰为 ``{"crs","units"}``；``crs == "GCJ-02"``；
    ``uid`` 必须等于数组下标（uid 稳定性契约，CONTRACTS §3.3）；
    ``key`` 全局唯一；行字段集合恰为 UNIT_FIELDS。
    """
    path = Path(data_dir) / UNITS_FILENAME
    payload = load_json_object(path)
    _require_top_keys(path, payload, ("crs", "units"))
    if payload["crs"] != EXPECTED_CRS:
        raise _fail(path, f"crs 必须是 {EXPECTED_CRS!r}，实际为 {payload['crs']!r}")
    rows = payload["units"]
    if not isinstance(rows, list) or not rows:
        raise _fail(path, "units 必须是非空数组")
    geoms: list[Any] = []
    seen_keys: set[str] = set()
    for i, row in enumerate(rows):
        label = f"units[{i}]"
        _require_row_fields(path, row, i, UNIT_FIELDS)
        uid = row["uid"]
        if isinstance(uid, bool) or not isinstance(uid, int):
            raise _fail(path, f"{label} 的 uid 必须是整数，实际为 {uid!r}")
        if uid != i:
            raise _fail(path, f"{label} 的 uid 必须等于数组下标 {i}（uid 冻结契约），实际为 {uid}")
        key = _require_nonempty_str(path, label, row["key"], "key")
        if key in seen_keys:
            raise _fail(path, f"{label} 的 key 重复：{key!r}（key 必须全局唯一）")
        seen_keys.add(key)
        _require_nonempty_str(path, label, row["district_code"], "district_code")
        _require_nonempty_str(path, label, row["street"], "street")
        _require_finite(path, label, row["area_km2"], "area_km2", positive=True)
        _require_lonlat(path, label, row["centroid"], "centroid")
        geoms.append(parse_payload_wkt(row["geom"], path, label))
    return rows, geoms


def _load_area_table(filename: str, kind: str) -> Any:
    """streets.json / districts.json 共用加载器：字段与唯一 code 校验。

    districts.json 顶层键按既有 P1 契约仍名为 ``streets``（历史遗留，禁止改名）。
    name 不强制唯一：重名由三级名称解析在查询时按歧义抛错处理，不在此拦截。
    """
    table = {
        "street": (STREETS_FILENAME, "streets", "街道"),
        "district": (DISTRICTS_FILENAME, "streets", "区县"),
    }
    filename, top_key, zh = table[kind]

    def load(data_dir: Path) -> tuple[list[dict[str, Any]], list[Any]]:
        path = Path(data_dir) / filename
        payload = load_json_object(path)
        _require_top_keys(path, payload, (top_key,))
        rows = payload[top_key]
        if not isinstance(rows, list) or not rows:
            raise _fail(path, f"{top_key} 必须是非空数组")
        geoms: list[Any] = []
        seen_codes: set[str] = set()
        for i, row in enumerate(rows):
            label = f"{top_key}[{i}]"
            _require_row_fields(path, row, i, AREA_FIELDS)
            _require_nonempty_str(path, label, row["name"], "name")
            code = _require_nonempty_str(path, label, row["code"], "code")
            if code in seen_codes:
                raise _fail(path, f"{label} 的 code 重复：{code!r}（{zh}编码必须唯一）")
            seen_codes.add(code)
            _require_nonempty_str(path, label, row["district_code"], "district_code")
            geoms.append(parse_payload_wkt(row["geom"], path, label))
        return rows, geoms

    return load

load_streets = _load_area_table(STREETS_FILENAME, "street")
load_districts = _load_area_table(DISTRICTS_FILENAME, "district")


def load_lines(data_dir: Path) -> tuple[list[dict[str, Any]], list[Any]]:
    """加载并校验 ``lines.json``（T-502）；返回（原样行列表, 已解析几何列表）。

    契约（p5-lines-v1）：
    - 顶层键恰为 ``{"schema_version","crs","source_crs","source_sha256",
      "counts","lines"}``；``schema_version/crs/source_crs`` 分别严格等于
      ``p5-lines-v1/GCJ-02/WGS-84``；
    - ``source_sha256`` 为 64 位小写十六进制；``counts`` 四个键均为非负整数
      （bool 非法）；
    - 行字段恰为 ``{"name","classes","osm_way_ids","geom"}``；``name`` 非空
      且全表唯一；``classes`` 是 highway/waterway/railway 的非空升序唯一数组；
      ``osm_way_ids`` 为非空升序唯一正整数数组（bool 非法）；
    - ``geom`` 仅接受非空 LineString/MultiLineString，每个 part 至少两个
      不同点；
    - 交叉断言：``output_names == len(lines)``；
      ``output_parts == sum(len(osm_way_ids))``；每行几何 part 数等于该行
      ``osm_way_ids`` 数。任一失败中文报路径和行号。
    """
    path = Path(data_dir) / LINES_FILENAME
    payload = load_json_object(path)
    _require_top_keys(
        path,
        payload,
        ("schema_version", "crs", "source_crs", "source_sha256", "counts", "lines"),
    )
    if payload["schema_version"] != EXPECTED_LINES_SCHEMA_VERSION:
        raise _fail(
            path,
            f"schema_version 必须是 {EXPECTED_LINES_SCHEMA_VERSION!r}，"
            f"实际为 {payload['schema_version']!r}",
        )
    if payload["crs"] != EXPECTED_CRS:
        raise _fail(path, f"crs 必须是 {EXPECTED_CRS!r}，实际为 {payload['crs']!r}")
    if payload["source_crs"] != EXPECTED_LINES_SOURCE_CRS:
        raise _fail(
            path,
            f"source_crs 必须是 {EXPECTED_LINES_SOURCE_CRS!r}，"
            f"实际为 {payload['source_crs']!r}",
        )
    sha = payload["source_sha256"]
    if (
        not isinstance(sha, str)
        or len(sha) != 64
        or any(ch not in SHA256_HEX_CHARS for ch in sha)
    ):
        raise _fail(path, f"source_sha256 必须是 64 位小写十六进制，实际为 {sha!r}")
    counts = payload["counts"]
    if not isinstance(counts, dict) or set(counts.keys()) != {
        "source_elements", "source_named_ways", "output_names", "output_parts"
    }:
        raise _fail(
            path,
            "counts 字段必须恰为 ['output_names', 'output_parts', "
            "'source_elements', 'source_named_ways']，实际为 "
            f"{sorted(counts) if isinstance(counts, dict) else counts!r}",
        )
    for field, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise _fail(path, f"counts 的 {field} 必须是非负整数，实际为 {value!r}")
    rows = payload["lines"]
    if not isinstance(rows, list) or not rows:
        raise _fail(path, "lines 必须是非空数组")
    geoms: list[Any] = []
    seen_names: set[str] = set()
    for i, row in enumerate(rows):
        label = f"lines[{i}]"
        _require_row_fields(path, row, i, LINE_FIELDS)
        name = _require_nonempty_str(path, label, row["name"], "name")
        if name in seen_names:
            raise _fail(path, f"{label} 的 name 重复：{name!r}（线名必须全表唯一）")
        seen_names.add(name)
        classes = row["classes"]
        if not isinstance(classes, list) or not classes:
            raise _fail(path, f"{label} 的 classes 必须是非空数组，实际为 {classes!r}")
        if any(c not in LINE_CLASSES for c in classes):
            raise _fail(
                path,
                f"{label} 的 classes 含非法值（仅允许 {'/'.join(LINE_CLASSES)}），"
                f"实际为 {classes!r}",
            )
        if list(classes) != sorted(set(classes)):
            raise _fail(path, f"{label} 的 classes 必须升序且唯一，实际为 {classes!r}")
        way_ids = row["osm_way_ids"]
        if not isinstance(way_ids, list) or not way_ids:
            raise _fail(path, f"{label} 的 osm_way_ids 必须是非空数组，实际为 {way_ids!r}")
        for w in way_ids:
            if isinstance(w, bool) or not isinstance(w, int) or w <= 0:
                raise _fail(
                    path,
                    f"{label} 的 osm_way_ids 必须是正整数（bool 非法），实际为 {w!r}",
                )
        if list(way_ids) != sorted(set(way_ids)):
            raise _fail(path, f"{label} 的 osm_way_ids 必须升序且唯一，实际为 {way_ids!r}")
        geom = parse_line_wkt(row["geom"], path, label)
        n_parts = 1 if geom.geom_type == "LineString" else len(geom.geoms)
        if n_parts != len(way_ids):
            raise _fail(
                path,
                f"{label} 的几何 part 数（{n_parts}）必须等于 osm_way_ids 数"
                f"（{len(way_ids)}）",
            )
        geoms.append(geom)
    if counts["output_names"] != len(rows):
        raise _fail(
            path,
            f"counts.output_names（{counts['output_names']}）必须等于 lines 数"
            f"（{len(rows)}）",
        )
    if counts["output_parts"] != sum(len(r["osm_way_ids"]) for r in rows):
        raise _fail(
            path,
            f"counts.output_parts（{counts['output_parts']}）必须等于"
            f" osm_way_ids 总数（{sum(len(r['osm_way_ids']) for r in rows)}）",
        )
    return rows, geoms


def load_unit_graph(data_dir: Path, expected_n_units: int) -> dict[int, list[int]]:
    """加载并校验 ``unit_graph.json``，返回 ``uid -> 邻接 uid 升序列表``。

    契约：顶层键恰为 ``{"adjacency","link_min_m"}``；``link_min_m == 50``
    （冻结常数）；邻接键恰覆盖 ``0..expected_n_units-1``；邻居值域合法、
    升序唯一、无自环、且对称（无向图）。
    """
    path = Path(data_dir) / UNIT_GRAPH_FILENAME
    payload = load_json_object(path)
    _require_top_keys(path, payload, ("adjacency", "link_min_m"))
    link = payload["link_min_m"]
    if (
        isinstance(link, bool)
        or not isinstance(link, (int, float))
        or not math.isfinite(float(link))
        or float(link) != float(LINK_MIN_M)
    ):
        raise _fail(path, f"link_min_m 必须等于冻结常数 {LINK_MIN_M}，实际为 {link!r}")
    adjacency_raw = payload["adjacency"]
    if not isinstance(adjacency_raw, dict):
        raise _fail(path, f"adjacency 必须是对象，实际为 {type(adjacency_raw).__name__}")
    wanted_keys = {str(i) for i in range(expected_n_units)}
    actual_keys = set(adjacency_raw.keys())
    if actual_keys != wanted_keys:
        missing = sorted(wanted_keys - actual_keys, key=int)
        extra = sorted(actual_keys - wanted_keys, key=int)
        raise _fail(
            path,
            f"邻接键必须恰好覆盖 uid 0..{expected_n_units - 1}；"
            f"缺失 {missing[:8]}{'...' if len(missing) > 8 else ''}；"
            f"多余 {extra[:8]}{'...' if len(extra) > 8 else ''}",
        )
    parsed: dict[int, list[int]] = {}
    for key, neighbors in adjacency_raw.items():
        uid = int(key)
        if not isinstance(neighbors, list):
            raise _fail(path, f"adjacency[{key}] 必须是数组，实际为 {type(neighbors).__name__}")
        cleaned: list[int] = []
        for n in neighbors:
            if isinstance(n, bool) or not isinstance(n, int):
                raise _fail(path, f"adjacency[{key}] 的邻居必须是整数，实际为 {n!r}")
            if not 0 <= n < expected_n_units:
                raise _fail(path, f"adjacency[{key}] 的邻居 {n} 超出 uid 值域 0..{expected_n_units - 1}")
            if n == uid:
                raise _fail(path, f"adjacency[{key}] 含自环 {n}（无向图禁止自环）")
            cleaned.append(n)
        if cleaned != sorted(set(cleaned)):
            raise _fail(path, f"adjacency[{key}] 的邻居必须升序且唯一，实际为 {neighbors!r}")
        parsed[uid] = cleaned
    for uid, neighbors in parsed.items():
        for n in neighbors:
            if uid not in parsed[n]:
                raise _fail(
                    path,
                    f"邻接不对称：{uid} -> {n} 存在，但 {n} -> {uid} 缺失（无向图必须对称）",
                )
    return parsed


def load_pilot_context(data_dir: Path) -> dict[str, Any]:
    """一次加载 P3 四输入与 P5 ``lines.json`` 并校验；任一失败即抛异常。

    返回只读上下文 dict：crs / units / unit_geoms / streets / street_geoms /
    districts / district_geoms / adjacency / link_min_m / data_dir /
    lines / line_geoms。所有行对象均为本次 JSON 解析的新对象，与磁盘内容
    一致、未被修改。全程 GCJ-02，不做任何转换。
    """
    data_dir = Path(data_dir)
    units, unit_geoms = load_units(data_dir)
    streets, street_geoms = load_streets(data_dir)
    districts, district_geoms = load_districts(data_dir)
    adjacency = load_unit_graph(data_dir, expected_n_units=len(units))
    lines, line_geoms = load_lines(data_dir)
    return {
        "data_dir": data_dir,
        "crs": EXPECTED_CRS,
        "units": units,
        "unit_geoms": unit_geoms,
        "streets": streets,
        "street_geoms": street_geoms,
        "districts": districts,
        "district_geoms": district_geoms,
        "adjacency": adjacency,
        "link_min_m": LINK_MIN_M,
        "lines": lines,
        "line_geoms": line_geoms,
    }


# ---------------------------------------------------------------------------
# 三级名称解析（精确 → 去末尾后缀 → 包含；唯一才成功，否则中文抛错）
# ---------------------------------------------------------------------------


def _stem(name: str) -> str:
    """剥离一个末尾后缀（街道/镇/区）；剥离后不得为空串（退化名原样返回）。"""
    for suffix in NAME_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def _row_ident(row: dict[str, Any]) -> str:
    """歧义报错用的行标识：正式表行用 code，线表行（无 code 字段）回退 name。"""
    if "code" in row:
        return f"code={row['code']}"
    return f"name={row['name']}"


def _resolve_name(query: Any, rows: list[dict[str, Any]], zh: str) -> dict[str, Any]:
    """三级解析公共实现：任一级唯一即返回；>1 抛歧义错；三级用尽 0 个抛不存在错。

    只读 ``rows`` 的 ``name`` 字段，绝不修改任何行对象。
    街道/区县/线要素（resolve_line）共用同一阶段机与异常语义。
    """
    if not isinstance(query, str) or not query.strip():
        raise DslError(f"{zh}名称解析失败：查询名必须是非空字符串，实际为 {query!r}")
    exact = [row for row in rows if row["name"] == query]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        dup = "、".join(_row_ident(r) for r in exact)
        raise DslError(f"{zh}名称解析失败：『{query}』精确匹配到 {len(exact)} 个{zh}（{dup}）；请改用唯一编码")
    stem = _stem(query)
    stemmed = [row for row in rows if _stem(row["name"]) == stem]
    if len(stemmed) == 1:
        return stemmed[0]
    if len(stemmed) > 1:
        names = "、".join(r["name"] for r in stemmed)
        raise DslError(f"{zh}名称解析失败：『{query}』去后缀后匹配到 {len(stemmed)} 个{zh}（{names}）；请使用完整正式名称")
    contains = [row for row in rows if query in row["name"]]
    if len(contains) == 1:
        return contains[0]
    if len(contains) > 1:
        names = "、".join(r["name"] for r in contains[:8])
        more = f" 等 {len(contains)} 个" if len(contains) > 8 else ""
        raise DslError(f"{zh}名称解析失败：『{query}』包含匹配到 {len(contains)} 个{zh}（{names}{more}）；请使用完整正式名称")
    raise DslError(f"{zh}名称解析失败：『{query}』在{zh}表中匹配到 0 个（精确/去后缀/包含三级均未命中）")


def resolve_street(query: Any, street_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """在街道表内解析街道名（禁止跨类型到区县表）；返回命中的街道行（原对象）。"""
    return _resolve_name(query, street_rows, "街道")


def resolve_district(query: Any, district_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """在区县表内解析区县名（禁止跨类型到街道表）；返回命中的区县行（原对象）。"""
    return _resolve_name(query, district_rows, "区县")


def resolve_line(query: Any, line_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """在线要素表内解析线名（严格复用 §4.3 三级阶段机）。

    精确 → 去末尾后缀（沿用现有 街道/镇/区 规则）→ 包含匹配；某一级唯一
    才返回；匹配 0 个或大于 1 个一律抛 DslError。禁止两字前缀、拼音、
    ``ref``、别名或道路等级猜测；不得跨到街道/区县表。精确同名 way 已由
    T-501 聚合，不构成多匹配。
    """
    return _resolve_name(query, line_rows, "线要素")


# ---------------------------------------------------------------------------
# DSL 节点结构校验（只读递归；位置以 $ / $.args[i] 表示）
# ---------------------------------------------------------------------------


def validate_rule(node: Any, _depth: int = 0, _loc: str = "$") -> None:
    """递归校验 DSL 树结构与 arity；非法即抛 DslError（含节点位置与中文原因）。

    规则（CONTRACTS §4.2 六原语；T-502 冻结）：
    - 节点必须是对象；叶节点（in_street/in_district）字段恰为 ``{"op","name"}``，
      name 为非空字符串；
    - ``union``：字段恰为 ``{"op","args"}``，args 为数组且至少包含 2 个节点；
    - ``minus``：字段恰为 ``{"op","args"}``，args 恰有 2 个节点；
    - ``side_of``：字段为 ``op/line/dir`` 加可选 ``scope``（任一额外字段即错）；
      ``line`` 为非空字符串；``dir`` 恰为八方位 北/南/东/西/东北/东南/西北/西南
      之一（不接受英文、缩写、组合词或模糊匹配）；``scope`` 可省略或显式 null
      （= 全试点），非空时必须是递归合法的六原语节点，校验位置延续
      ``$.scope...``，深度与循环保护沿用 MAX_RULE_DEPTH；
    - ``near``：字段恰为 ``{"op","center","radius_km"}``；``center`` 为长度 2 的
      JSON 数组 ``[lon,lat]``（tuple 代替数组一律拒绝），元素为有限数字
      （bool 不算数字），范围 [-180,180] / [-90,90]；``radius_km`` 为有限非负
      数字（0 合法，bool 非法）；
    - 未知 op、额外字段、缺字段、tuple 代替数组、非法数值、非对象节点均抛错；
      不得修正、补默认值或改写传入规则（scope 省略的默认行为只在求值时解释，
      不回写树）；
    - 嵌套深度超过 MAX_RULE_DEPTH 受控终止（防循环引用无限递归）。

    只读：绝不修改树中任何对象。
    """
    if _depth > MAX_RULE_DEPTH:
        raise DslError(
            f"DSL 节点 {_loc}：嵌套深度超过上限 {MAX_RULE_DEPTH} 层，受控拒绝"
            f"（疑似循环引用或退化结构）"
        )
    if not isinstance(node, dict):
        raise DslError(f"DSL 节点 {_loc}：必须是对象（dict），实际为 {type(node).__name__}")
    if "op" not in node:
        raise DslError(f"DSL 节点 {_loc}：缺少必需字段 op")
    op = node["op"]
    if not isinstance(op, str):
        raise DslError(f"DSL 节点 {_loc}：op 必须是字符串，实际为 {op!r}")
    if op not in ALL_OPS:
        raise DslError(f"DSL 节点 {_loc}：未知 op『{op}』（仅允许 {'/'.join(ALL_OPS)}）")
    if op in LEAF_OPS:
        if set(node.keys()) != {"op", "name"}:
            raise DslError(
                f"DSL 节点 {_loc}（{op}）：叶节点字段必须恰为 ['name', 'op']，"
                f"实际为 {sorted(node.keys())}"
            )
        name = node["name"]
        if not isinstance(name, str) or not name.strip():
            raise DslError(f"DSL 节点 {_loc}（{op}）：name 必须是非空字符串，实际为 {name!r}")
        return
    if op in P5_OPS:
        _validate_p5_node(node, op, _loc, _depth)
        return
    # union / minus：字段恰为 {"op","args"}
    if set(node.keys()) != {"op", "args"}:
        raise DslError(
            f"DSL 节点 {_loc}（{op}）：字段必须恰为 ['args', 'op']，实际为 {sorted(node.keys())}"
        )
    args = node["args"]
    if not isinstance(args, list):
        raise DslError(f"DSL 节点 {_loc}（{op}）：args 必须是数组，实际为 {type(args).__name__}")
    if op == "union" and len(args) < 2:
        raise DslError(f"DSL 节点 {_loc}（union）：args 至少包含 2 个节点，实际为 {len(args)} 个")
    if op == "minus" and len(args) != 2:
        raise DslError(f"DSL 节点 {_loc}（minus）：args 必须恰有 2 个节点，实际为 {len(args)} 个")
    for i, child in enumerate(args):
        validate_rule(child, _depth + 1, f"{_loc}.args[{i}]")


def _validate_p5_node(node: dict[str, Any], op: str, _loc: str, _depth: int = 0) -> None:
    """P5 两原语（side_of / near）的严格 schema 校验（T-502 冻结）。

    - 字段集合与类型必须恰如 CONTRACTS §4.2；任一额外字段、缺字段、
      tuple 代替数组、非法数值均抛错；不得修正、补默认值或改写传入规则
      （scope 省略的默认行为只在求值时解释，不回写树）。
    - ``side_of.scope`` 非空时递归走 ``validate_rule``，位置延续
      ``$.scope...``，深度与循环保护沿用 MAX_RULE_DEPTH。
    """
    if op == P5_SIDE_OF:
        keys = set(node.keys())
        if not {"op", "line", "dir"} <= keys or not keys <= {"op", "line", "dir", "scope"}:
            raise DslError(
                f"DSL 节点 {_loc}（side_of）：字段必须为 op/line/dir 加可选 scope，"
                f"实际为 {sorted(keys)}"
            )
        line = node["line"]
        if not isinstance(line, str) or not line.strip():
            raise DslError(f"DSL 节点 {_loc}（side_of）：line 必须是非空字符串，实际为 {line!r}")
        direction = node["dir"]
        if not isinstance(direction, str) or direction not in SIDE_DIRS:
            raise DslError(
                f"DSL 节点 {_loc}（side_of）：dir 必须恰为 {'/'.join(SIDE_DIRS)} 之一"
                f"（不接受英文、缩写、组合词或模糊匹配），实际为 {direction!r}"
            )
        scope = node.get("scope")
        if scope is not None:
            validate_rule(scope, _depth + 1, f"{_loc}.scope")
        return
    # near
    if set(node.keys()) != {"op", "center", "radius_km"}:
        raise DslError(
            f"DSL 节点 {_loc}（near）：字段必须恰为 ['center', 'op', 'radius_km']，"
            f"实际为 {sorted(node.keys())}"
        )
    center = node["center"]
    if not isinstance(center, list) or len(center) != 2:
        raise DslError(
            f"DSL 节点 {_loc}（near）：center 必须是 [lon, lat] JSON 数组"
            f"（tuple 代替数组一律拒绝），实际为 {center!r}"
        )
    lon, lat = center
    for dim, val, lo, hi in (("lon", lon, -180.0, 180.0), ("lat", lat, -90.0, 90.0)):
        if isinstance(val, bool) or not isinstance(val, (int, float)) \
                or not math.isfinite(float(val)):
            raise DslError(
                f"DSL 节点 {_loc}（near）：center 的 {dim} 必须是有限数字"
                f"（bool 不算数字），实际为 {val!r}"
            )
        if not lo <= float(val) <= hi:
            raise DslError(
                f"DSL 节点 {_loc}（near）：center 的 {dim} 超出 [{lo:g}, {hi:g}]，"
                f"实际为 {val!r}"
            )
    radius = node["radius_km"]
    if isinstance(radius, bool) or not isinstance(radius, (int, float)) \
            or not math.isfinite(float(radius)):
        raise DslError(
            f"DSL 节点 {_loc}（near）：radius_km 必须是有限数字（bool 不算数字），"
            f"实际为 {radius!r}"
        )
    if float(radius) < 0:
        raise DslError(
            f"DSL 节点 {_loc}（near）：radius_km 必须非负（0 合法），实际为 {radius!r}"
        )


# ---------------------------------------------------------------------------
# 六原语确定性求值器（T-302 四原语；T-503 补齐 side_of / near 与非空纪律）
# ---------------------------------------------------------------------------


# side_of 八方位向量（T-503 冻结；在局部东西/南北平面内取值）。
SIDE_DIR_VECTORS: dict[str, tuple[float, float]] = {
    "北": (0.0, 1.0),
    "南": (0.0, -1.0),
    "东": (1.0, 0.0),
    "西": (-1.0, 0.0),
    "东北": (1.0, 1.0),
    "东南": (1.0, -1.0),
    "西北": (-1.0, 1.0),
    "西南": (-1.0, -1.0),
}

# 局部平面最近段并列（平方距离差 <= 该值）时取 part/段 index 较小者；
# 只保证浮点噪声级并列的确定性，不做业务级容差。
_SIDE_TIE_EPS = 1e-15
# 叉积退化阈值：|cross| <= 该值视为共线/零向量，该候选不入选、不猜测。
_SIDE_CROSS_EPS = 1e-12


def _contains_p5(node: Any) -> bool:
    """只读扫描 DSL 树是否包含任一 P5 原语（不修改树）。"""
    if not isinstance(node, dict):
        return False
    if node.get("op") in P5_OPS:
        return True
    return any(_contains_p5(child) for child in node.get("args", ()))


def eval_rule(node: Any, ctx: dict[str, Any]) -> set[int]:
    """对已校验的 DSL 树做确定性递归求值，返回单元 uid 集合 ``set[int]``。

    求值语义（CONTRACTS v1.7 冻结；v1.5/v1.6 的 in_street 几何判定已废弃）：
    - ``in_street``：先解析街道名为唯一正式街道名，再严格筛选
      ``unit["street"] == street.name``。街道归属是业务事实，以
      ``units.json`` 落盘的 ``street`` 属性为准；禁止任何几何判定
      （质心 contains / covers / 面积重叠 / 单元几何交集均废弃），
      街道多边形几何不参与单元选取。
    - ``in_district``：先解析区县名为唯一区编码，再严格筛选
      ``unit["district_code"] == district.code``；禁止任何几何判定。
    - ``union``：递归求值所有子节点取集合并（重复子树天然幂等）。
    - ``minus``：严格 ``eval(args[0]) - eval(args[1])``，不交换、不对称差。
    - ``side_of`` / ``near``：T-503 冻结求值（见 _eval_side_of /
      _eval_near）；scope 非空时先求值并严格缩小候选。

    纪律：无副作用——不缓存、不回写坐标/几何/解析名/unit ids 到规则树；
    入口处先整体 validate_rule（未知 op、非法 schema/arity、循环深度均在
    进入递归前拒绝）；串行、无网络、无坐标转换。输出仅 ``set[int]``；
    components / area_km2 由 T-303 在 L1 层另行汇总。

    非空纪律（T-503）：规则含任一 P5 原语且最终结果为空 → 显式抛
    DslError（中文，含规则与原因）；纯 P3 规则保持 v1.7 语义，
    ``minus(X,X)`` 合法空集不受影响。
    """
    validate_rule(node)
    result = _eval_node(node, ctx, "$")
    if not result and _contains_p5(node):
        raise DslError(
            f"规则求值结果为空：表达式 {json.dumps(node, ensure_ascii=False)} "
            f"包含 P5 原语（side_of/near），组装结果为空集；按 P5 非空纪律"
            f"显式失败，不静默返回空集（快速实验教训：全负分→全丢弃→空集→"
            f"Jaccard 归零，属于上游缺陷，不得作为合法结果输出）"
        )
    return result


def _eval_node(node: Any, ctx: dict[str, Any], _loc: str) -> set[int]:
    """递归求值单个节点（结构已在入口整体校验过，此处只做求值）。"""
    op = node["op"]
    if op == "in_street":
        street = resolve_street(node["name"], ctx["streets"])
        return {
            unit["uid"]
            for unit in ctx["units"]
            if unit["street"] == street["name"]
        }
    if op == "in_district":
        district = resolve_district(node["name"], ctx["districts"])
        code = district["code"]
        return {unit["uid"] for unit in ctx["units"] if unit["district_code"] == code}
    if op == "union":
        result: set[int] = set()
        for i, child in enumerate(node["args"]):
            result |= _eval_node(child, ctx, f"{_loc}.args[{i}]")
        return result
    if op in P5_OPS:
        return _P5_EVALUATORS[op](node, ctx, _loc)
    # minus：结构校验已保证 args 恰有 2 个节点
    return _eval_node(node["args"][0], ctx, f"{_loc}.args[0]") - _eval_node(
        node["args"][1], ctx, f"{_loc}.args[1]"
    )


def _eval_near(node: dict[str, Any], ctx: dict[str, Any], _loc: str) -> set[int]:
    """``near`` 冻结求值：全部 L1 单元逐个调用 haversine_km，<= radius 选中。

    - 候选固定为全部 L1 单元（side_of 才有 scope）；逐单元严格调用模块级
      导入的 ``intelligence.world.haversine_km``（测试可 mock 该名字），
      禁止自写换算、投影距离或坐标转换。
    - 距离 ``<= radius_km`` 选中，等号必须包含；``radius_km == 0`` 合法，
      center 恰等于某单元质心时该单元必须选中。
    - 结果为空时显式抛 DslError（P5 非空纪律；不返回空集占位）。
    """
    center = tuple(node["center"])
    radius = float(node["radius_km"])
    selected: set[int] = set()
    for unit in ctx["units"]:
        if haversine_km(tuple(unit["centroid"]), center) <= radius:
            selected.add(unit["uid"])
    if not selected:
        raise DslError(
            f"DSL 节点 {_loc}（near）：没有单元质心落在 center="
            f"{node['center']} 半径 {radius}km 内；按 P5 非空纪律显式失败，"
            f"不静默返回空集"
        )
    return selected


def _line_parts(geom: Any) -> list[Any]:
    """线几何展开为 part 列表：LineString 单 part；MultiLineString 经 .geoms。"""
    return [geom] if geom.geom_type == "LineString" else list(geom.geoms)


def _eval_side_of(node: dict[str, Any], ctx: dict[str, Any], _loc: str) -> set[int]:
    """``side_of`` 冻结求值（T-503 卡载算法逐步实现，不得近似）。

    1. ``resolve_line`` 唯一解析线名（0/>1 匹配已由三级解析抛错）。
    2. scope 省略/null → 候选为全部 L1 uid；非空 → 先递归求值 scope，
       候选严格等于 scope 集合；scope 为空 → 中文抛错（不进线侧判断）。
    3. 按 part/段顺序枚举相邻点段（LineString 视为一个 part；Multi 仅经
       .geoms 展开；零长度段拒绝输入或被其他有效段覆盖）。
    4. 对每个候选质心 P 在其纬度建局部平面（相对经度差乘
       ``cos(radians(P.lat))``），对每段做钳制投影，平方距离最小的段为
       最近段（``1e-15`` 内并列取 part/段 index 较小者）。
    5. 最近段方向 ``t = B - A`` 为局部切线；``r = P - Q``；八方位向量
       ``d``（SIDE_DIR_VECTORS 冻结）。
    6. ``cross(t,r)`` 与 ``cross(t,d)`` 绝对值均 > 1e-12 且同号才选中
       （反转线点序两项同反，结果不变）；质心在线上或方向与切线平行
       → 该候选不入选、不猜测。
    7. 无候选位于请求侧 → 显式抛 DslError（P5 非空纪律）。
    """
    line_row = resolve_line(node["line"], ctx["lines"])
    idx = ctx["lines"].index(line_row)
    line_geom = ctx["line_geoms"][idx]
    scope = node.get("scope")
    if scope is None:
        candidates = {unit["uid"] for unit in ctx["units"]}
    else:
        candidates = _eval_node(scope, ctx, f"{_loc}.scope")
        if not candidates:
            raise DslError(
                f"DSL 节点 {_loc}（side_of）：scope 求值结果为空集；"
                f"按 P5 非空纪律显式失败，不进入线侧判断"
            )
    parts = _line_parts(line_geom)
    selected: set[int] = set()
    for unit in ctx["units"]:
        uid = unit["uid"]
        if uid not in candidates:
            continue
        px = float(unit["centroid"][0])
        py = float(unit["centroid"][1])
        cos_lat = math.cos(math.radians(py))
        best_d2 = math.inf
        best_ax = best_ay = best_bx = best_by = 0.0
        best_t = 0.0
        for part_idx, part in enumerate(parts):
            coords = list(part.coords)
            for seg_idx in range(len(coords) - 1):
                ax, ay = (float(v) for v in coords[seg_idx])
                bx, by = (float(v) for v in coords[seg_idx + 1])
                if ax == bx and ay == by:
                    continue  # 零长度段跳过（重复点已被其他有效段覆盖）
                # 局部平面坐标：以 A 为原点、P 的纬度做东西压缩
                pex = (px - ax) * cos_lat
                pey = py - ay
                bex = (bx - ax) * cos_lat
                bey = by - ay
                seg_len2 = bex * bex + bey * bey
                if seg_len2 <= 0.0:
                    continue
                t_param = (pex * bex + pey * bey) / seg_len2
                if t_param < 0.0:
                    t_param = 0.0
                elif t_param > 1.0:
                    t_param = 1.0
                dx = pex - t_param * bex
                dy = pey - t_param * bey
                d2 = dx * dx + dy * dy
                if d2 < best_d2 - _SIDE_TIE_EPS:
                    best_d2 = d2
                    best_ax, best_ay, best_bx, best_by = ax, ay, bx, by
                    best_t = t_param
                # 并列（差 <= eps）：保留先到的 part/段 index（较小者）
        if math.isinf(best_d2):
            raise DslError(
                f"DSL 节点 {_loc}（side_of）：命中线『{line_row['name']}』"
                f"没有任何有效线段（全部为零长度段）；按纪律显式失败，不猜测"
            )
        # 最近段 AB 上钳制投影点 Q（原始经纬度差）。局部平面相对原始坐标
        # 只差公共正因子 cos(P.lat)，叉积符号不受影响，方向判定直接用
        # 原始坐标差（共同尺度不参与距离报告）。
        qx = best_ax + best_t * (best_bx - best_ax)
        qy = best_ay + best_t * (best_by - best_ay)
        tx = best_bx - best_ax
        ty = best_by - best_ay
        rx = px - qx
        ry = py - qy
        dir_x, dir_y = SIDE_DIR_VECTORS[node["dir"]]
        side_p = tx * ry - ty * rx
        side_d = tx * dir_y - ty * dir_x
        if abs(side_p) > _SIDE_CROSS_EPS and abs(side_d) > _SIDE_CROSS_EPS \
                and side_p * side_d > 0.0:
            selected.add(uid)
    if not selected:
        raise DslError(
            f"DSL 节点 {_loc}（side_of）：没有候选单元质心位于"
            f"『{line_row['name']}』最近点局部切线的{node['dir']}侧；"
            f"按 P5 非空纪律显式失败，不静默返回空集"
        )
    return selected


# 表驱动分发（T-502 静态纪律：求值器不以 P5 op 字面量做相等分发）
_P5_EVALUATORS: dict[str, Any] = {
    P5_SIDE_OF: _eval_side_of,
    P5_NEAR: _eval_near,
}


# ---------------------------------------------------------------------------
# T-303：最终执行入口与输出汇总（components / area_km2 / rule / warnings）
# ---------------------------------------------------------------------------


def _verify_graph(ctx: dict[str, Any]) -> None:
    """执行前对上下文里的 L1 邻接图做防御性复核（不通过即抛中文异常）。

    正常流程下 ``load_pilot_context`` 已在加载层做过同一套校验；此处独立
    复核是 T-303 卡冻结纪律：任何调用方绕过加载层手工拼 ctx 时，绝不允许
    带病图进入 components 统计。
    """
    data_dir = ctx.get("data_dir", ".")
    path = Path(data_dir) / UNIT_GRAPH_FILENAME
    link = ctx.get("link_min_m")
    if (
        isinstance(link, bool)
        or not isinstance(link, (int, float))
        or not math.isfinite(float(link))
        or float(link) != float(LINK_MIN_M)
    ):
        raise _fail(path, f"link_min_m 必须等于冻结常数 {LINK_MIN_M}，实际为 {link!r}")
    adjacency = ctx.get("adjacency")
    if not isinstance(adjacency, dict):
        raise _fail(path, f"adjacency 必须是对象，实际为 {type(adjacency).__name__}")
    n = len(ctx["units"])
    wanted = set(range(n))
    actual = set(adjacency.keys())
    if actual != wanted:
        missing = sorted(wanted - actual)[:8]
        extra = sorted(actual - wanted)[:8]
        raise _fail(
            path,
            f"邻接键必须恰好覆盖 uid 0..{n - 1}；"
            f"缺失 {missing}{'...' if len(wanted - actual) > 8 else ''}；"
            f"多余 {extra}{'...' if len(actual - wanted) > 8 else ''}",
        )
    for uid, neighbors in adjacency.items():
        if not isinstance(neighbors, list):
            raise _fail(path, f"adjacency[{uid}] 必须是数组，实际为 {type(neighbors).__name__}")
        for nv in neighbors:
            if isinstance(nv, bool) or not isinstance(nv, int):
                raise _fail(path, f"adjacency[{uid}] 的邻居必须是整数，实际为 {nv!r}")
            if not 0 <= nv < n:
                raise _fail(path, f"adjacency[{uid}] 的邻居 {nv} 超出 uid 值域 0..{n - 1}")
            if nv == uid:
                raise _fail(path, f"adjacency[{uid}] 含自环 {nv}（无向图禁止自环）")
        if sorted(set(neighbors)) != list(neighbors):
            raise _fail(path, f"adjacency[{uid}] 的邻居必须升序且唯一，实际为 {neighbors!r}")
    for uid, neighbors in adjacency.items():
        for nv in neighbors:
            if uid not in adjacency[nv]:
                raise _fail(
                    path,
                    f"邻接不对称：{uid} -> {nv} 存在，但 {nv} -> {uid} 缺失（无向图必须对称）",
                )


def _count_components(selected: set[int], adjacency: dict[int, list[int]]) -> int:
    """在 L1 诱导子图上数连通分量：只沿两端均在选择集内的边遍历。

    纯图遍历（迭代式 DFS，避免深图递归爆栈）；不读几何、不读 street 分组、
    不读 L2 细面；不修补、不添加单元（D-9：多块只报告）。
    """
    seen: set[int] = set()
    count = 0
    for start in sorted(selected):
        if start in seen:
            continue
        count += 1
        stack = [start]
        seen.add(start)
        while stack:
            cur = stack.pop()
            for nb in adjacency[cur]:
                if nb in selected and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
    return count


def execute(rule: Any, ctx: dict[str, Any]) -> dict[str, Any]:
    """T-303 最终执行入口：求值 DSL 树并汇总 CONTRACTS v1.5 §4.4 五字段对象。

    输出顶层键恰为 ``unit_ids / components / area_km2 / rule / warnings``：
    - ``unit_ids``：求值集合升序唯一整数数组（空集合为 ``[]``）；
    - ``components``：uid 在 L1 邻接图诱导子图中的连通分量数（空集 0），
      D-9：只报告，不修补、不连通、不改变所选集合；
    - ``area_km2``：所选单元 ``area_km2`` 的 ``math.fsum`` 确定性求和
      （空集 ``0.0``），不做几何 union/difference、不用 L2 细面重算；
    - ``rule``：调用方传入 DSL 树的深拷贝（``copy.deepcopy``），执行前后
      原树逐字节不变，返回值不与调用方对象共享可变结构；
    - ``warnings``：v1.5 P3-MVP 未定义非致命 warning，恒为 ``[]``；
      名称 0 匹配 / 歧义是异常直接抛出，绝不降级为 warning。

    纪律：只读输入、不写文件、不访问网络、串行执行；任何失败在中途抛
    中文异常，绝不返回半成品。
    """
    _verify_graph(ctx)
    selected = eval_rule(rule, ctx)
    area_by_uid = {u["uid"]: u["area_km2"] for u in ctx["units"]}
    return {
        "unit_ids": sorted(selected),
        "components": _count_components(selected, ctx["adjacency"]),
        "area_km2": math.fsum(area_by_uid[uid] for uid in selected),
        "rule": copy.deepcopy(rule),
        "warnings": [],
    }
