# -*- coding: utf-8 -*-
"""02_units.py — T-201…T-204：P2 输入层 + 邻接图 + oracle 指标 + G2/P2b 门禁汇总。

职责边界（任务卡 T-201 + T-202）：
- 只读加载 P1 产物 ``units.json`` / ``fences_dealer.json`` / ``fences_yeidai.json``；
- 严格 schema 校验：字段集合、uid 冻结契约、key 全局唯一、围栏 src_id 唯一且跨文件不冲突；
- WKT 解析为 shapely 几何（仅接受非空 Polygon / MultiPolygon，不假设存在 ``.exterior``）；
- 构造冻结映射 ``build_key_uid_map``：``uid`` 必须等于 ``units`` 数组下标（uid 稳定性契约）；
- T-202：按冻结常数 ``LINK_MIN_M = 50`` 建立单元无向邻接图，写 ``unit_graph.json``，
  并执行 G2-a（两两重叠面积占比 < 0.1%，无孤立单元；孤立单元逐条上报 ESCALATION）。
- T-203：校验 T-202 产物 ``unit_graph.json``，按 CONTRACTS v1.4 §3.6 冻结公式生成
  oracle 单元集（``fence.covers(Point(centroid))``，含恰落围栏边界的质心），计算
  iou / recall / precision / straddle（闭区间 [0.2, 0.8]）与诱导子图 components，
  写 ``oracle_unitsets.json``。
- T-204：执行 G2-b 门禁（业代 ``median(iou) >= 0.95``，FAIL 退出码 6 且原始数字全部
  保留在 stdout 与产物中）；经销商逐条报告并判定 P2b（任一 ``iou < 0.90`` → P2b，
  触发 P2b 不是 G2-c 失败，不改写/删除任何输出）；CLI 汇总精确三段
  （G2-a/G2-b/G2-c），禁止输出经销商中位数等聚合。

输出 ``unit_graph.json``（schema 精确为 ``{"adjacency", "link_min_m"}``）与
``oracle_unitsets.json``（schema 精确为 ``{"method", "link_min_m", "boundary_centroids", "fences"}``）；
明令禁止：不重排/重编号/修补数据、不做坐标转换（全程 GCJ-02，不调用 gcj2wgs）、
不豁免真实飞地、不访问网络、不生成第三个数据产物。

CLI 形态（--data 必须显式传入，禁止默认路径）::

    python3 sraf-pilot/src/02_units.py --data data/pilot
"""
import argparse
import json
import math
import os
import sys
import statistics
import tempfile
from pathlib import Path
from typing import Any

import shapely
import shapely.wkt
from shapely.geometry import Point

try:
    from intelligence.world import haversine_km
except ModuleNotFoundError:
    # 以脚本直跑（python3 sraf-pilot/src/02_units.py）时仓库根不在 sys.path；
    # 仓库根 = 本文件向上三级（sraf-pilot/src -> sraf-pilot -> <repo root>）。
    _REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from intelligence.world import haversine_km


class PilotInputError(Exception):
    """P1 产物不符合契约时抛出；消息为中文，含文件路径与具体原因。"""


# ---------------------------------------------------------------------------
# 契约常量（与 CONTRACTS §3.3 / P1 产物 schema 逐字对齐，禁止放宽）
# ---------------------------------------------------------------------------

EXPECTED_CRS = "GCJ-02"

UNIT_FIELDS = ("uid", "key", "district_code", "street", "area_km2", "centroid", "geom")
FENCE_FIELDS = ("name", "src_id", "area_km2", "center", "overlap_ratio", "geom")

# 几何只接受这两种非空类型；MultiPolygon 没有 .exterior，代码路径禁止触碰该属性。
GEOM_TYPES = ("Polygon", "MultiPolygon")

UNITS_FILENAME = "units.json"
DEALER_FILENAME = "fences_dealer.json"
YEIDAI_FILENAME = "fences_yeidai.json"
UNIT_GRAPH_FILENAME = "unit_graph.json"

LINK_MIN_M = 50  # 冻结常数（T-202）：共享边界 >= 50 米才建邻接边，禁止放宽

# T-203 冻结常数（CONTRACTS v1.4 §3.6，禁止放宽或修改）
ORACLE_FILENAME = "oracle_unitsets.json"
ORACLE_METHOD = "3.6-v1.4"
STRADDLE_LOW = 0.2   # 骑跨判定闭区间下界（恰为 0.2 计入）
STRADDLE_HIGH = 0.8  # 骑跨判定闭区间上界（恰为 0.8 计入）


def _fail(path: Path, reason: str) -> PilotInputError:
    """统一中文异常格式：文件路径 + 原因。"""
    return PilotInputError(f"{path}：{reason}")


def _row_label(index: int, ident: str) -> str:
    """行级错误定位标签，如 ``units[3]（key=U-0003）``。"""
    return f"[{index}]（{ident}）"


# ---------------------------------------------------------------------------
# 字段级校验辅助（全部含路径与中文字段名）
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# JSON 加载与顶层结构
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# WKT 解析（Polygon / MultiPolygon，禁止假设 .exterior 存在）
# ---------------------------------------------------------------------------


def parse_payload_wkt(wkt_text: Any, path: Path, label: str) -> Any:
    """解析 WKT 为 shapely 几何；非字符串/非法/空几何/类型不符均抛中文异常。"""
    if not isinstance(wkt_text, str) or not wkt_text.strip():
        raise _fail(path, f"{label} 的 geom 必须是非空 WKT 字符串，实际为 {wkt_text!r}")
    try:
        geom = shapely.wkt.loads(wkt_text)
    except Exception as exc:  # shapely 的解析错误类型随版本变化，统一转中文契约异常
        raise _fail(path, f"{label} 的 geom WKT 解析失败：{exc}") from exc
    if geom.is_empty:
        raise _fail(path, f"{label} 的 geom 是空几何（仅接受非空 {'/'.join(GEOM_TYPES)}）")
    if geom.geom_type not in GEOM_TYPES:
        raise _fail(
            path,
            f"{label} 的 geom 类型是 {geom.geom_type}（仅接受 {'/'.join(GEOM_TYPES)}）",
        )
    return geom


# ---------------------------------------------------------------------------
# units.json 校验（uid 冻结契约 + key 全局唯一）
# ---------------------------------------------------------------------------


def validate_units_payload(payload: dict[str, Any], path: Path) -> tuple[list[dict[str, Any]], list[Any]]:
    """严格校验 units.json；返回（原样行列表, 已解析几何列表）。

    uid 稳定性契约：uid 必须是整数、等于数组下标（即 0..N-1 连续），
    禁止按 key / 面积 / 街道重排或重编号；key 必须非空且全局唯一，重复即报错。
    centroid / area_km2 只作输入校验，不重新计算、不覆写。
    """
    _require_top_keys(path, payload, ("crs", "units"))
    if payload["crs"] != EXPECTED_CRS:
        raise _fail(
            path,
            f"crs 必须为 {EXPECTED_CRS!r}（全体同一坐标系，禁止转换），实际为 {payload['crs']!r}",
        )
    rows = payload["units"]
    if not isinstance(rows, list) or not rows:
        raise _fail(path, "units 必须是非空数组（单元库为空即契约失效）")
    seen_keys: dict[str, int] = {}
    units: list[dict[str, Any]] = []
    geoms: list[Any] = []
    for i, row in enumerate(rows):
        row = _require_row_fields(path, row, i, UNIT_FIELDS)
        uid = row["uid"]
        if isinstance(uid, bool) or not isinstance(uid, int):
            raise _fail(path, f"[{i}] 的 uid 必须是整数，实际为 {uid!r}")
        if uid != i:
            raise _fail(
                path,
                f"[{i}] 的 uid={uid} 不等于数组下标 {i}"
                "（uid 必须为 0..N-1 连续且与下标一致，禁止重排/重编号）",
            )
        key = _require_nonempty_str(path, f"[{i}]", row["key"], "key")
        if key in seen_keys:
            raise _fail(
                path,
                f"key 重复：{key}（units[{seen_keys[key]}] 与 units[{i}]），禁止覆盖",
            )
        seen_keys[key] = i
        _require_nonempty_str(path, f"[{i}]（key={key}）", row["district_code"], "district_code")
        _require_nonempty_str(path, f"[{i}]（key={key}）", row["street"], "street")
        _require_finite(path, f"[{i}]（key={key}）", row["area_km2"], "area_km2", positive=True)
        _require_lonlat(path, f"[{i}]（key={key}）", row["centroid"], "centroid")
        geom = parse_payload_wkt(row["geom"], path, f"[{i}]（key={key}）")
        units.append(row)
        geoms.append(geom)
    return units, geoms


# ---------------------------------------------------------------------------
# fences_*.json 校验（src_id 文件内唯一）
# ---------------------------------------------------------------------------


def validate_fences_payload(
    payload: dict[str, Any], path: Path
) -> tuple[list[dict[str, Any]], list[Any]]:
    """严格校验围栏 JSON；返回（原样行列表, 已解析几何列表）。

    文件内 src_id 必须唯一（真重复即报错，禁止静默取舍）；
    fences 允许为空数组——P1 在无样本时本就可能产出空围栏文件。
    """
    _require_top_keys(path, payload, ("fences",))
    rows = payload["fences"]
    if not isinstance(rows, list):
        raise _fail(path, "fences 必须是数组")
    seen_ids: dict[str, int] = {}
    fences: list[dict[str, Any]] = []
    geoms: list[Any] = []
    for i, row in enumerate(rows):
        row = _require_row_fields(path, row, i, FENCE_FIELDS)
        src_id = _require_nonempty_str(path, f"[{i}]", row["src_id"], "src_id")
        if src_id in seen_ids:
            raise _fail(
                path,
                f"src_id 重复：{src_id}（fences[{seen_ids[src_id]}] 与 fences[{i}]），"
                "真重复禁止静默取舍",
            )
        seen_ids[src_id] = i
        label = _row_label(i, f"src_id={src_id}")
        _require_nonempty_str(path, label, row["name"], "name")
        _require_finite(path, label, row["area_km2"], "area_km2", positive=True)
        _require_lonlat(path, label, row["center"], "center")
        ratio = _require_finite(path, label, row["overlap_ratio"], "overlap_ratio")
        if not 0.0 <= ratio <= 1.0:
            raise _fail(path, f"{label} 的 overlap_ratio 必须在 [0,1] 内，实际为 {ratio}")
        geom = parse_payload_wkt(row["geom"], path, label)
        fences.append(row)
        geoms.append(geom)
    return fences, geoms


def ensure_src_id_disjoint(
    dealer_fences: list[dict[str, Any]],
    yeidai_fences: list[dict[str, Any]],
    dealer_path: Path,
    yeidai_path: Path,
) -> None:
    """两类围栏写入同一 oracle_unitsets.json 前，src_id 必须跨文件无冲突。"""
    dealer_ids = {f["src_id"] for f in dealer_fences}
    yeidai_ids = {f["src_id"] for f in yeidai_fences}
    clash = sorted(dealer_ids & yeidai_ids)
    if clash:
        raise _fail(
            yeidai_path,
            f"与经销商围栏存在跨文件 src_id 冲突：{', '.join(clash)}"
            f"（写入同一 oracle_unitsets.json 前必须全局唯一；"
            f"冲突双方：{dealer_path} 与 {yeidai_path}）",
        )


# ---------------------------------------------------------------------------
# key → uid 冻结映射（后继卡唯一入口）
# ---------------------------------------------------------------------------


def build_key_uid_map(units: list[dict[str, Any]]) -> dict[str, int]:
    """按契约逐字构造 ``key -> uid`` 映射；不经任何重排或变换。"""
    return {unit["key"]: unit["uid"] for unit in units}


# ---------------------------------------------------------------------------
# 汇总入口：一次加载、全部校验、纯内存返回（不写盘）
# ---------------------------------------------------------------------------


def load_pilot_inputs(data_dir: Path) -> dict[str, Any]:
    """加载并校验 P2 全部输入；任一失败即抛 PilotInputError，不产生任何文件。

    返回 dict：units / unit_geoms / dealer_fences / dealer_geoms /
    yeidai_fences / yeidai_geoms / key_to_uid。
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise _fail(data_dir, "数据目录不存在")
    units_path = data_dir / UNITS_FILENAME
    dealer_path = data_dir / DEALER_FILENAME
    yeidai_path = data_dir / YEIDAI_FILENAME

    units, unit_geoms = validate_units_payload(load_json_object(units_path), units_path)
    dealer_fences, dealer_geoms = validate_fences_payload(
        load_json_object(dealer_path), dealer_path
    )
    yeidai_fences, yeidai_geoms = validate_fences_payload(
        load_json_object(yeidai_path), yeidai_path
    )
    ensure_src_id_disjoint(dealer_fences, yeidai_fences, dealer_path, yeidai_path)
    return {
        "units": units,
        "unit_geoms": unit_geoms,
        "dealer_fences": dealer_fences,
        "dealer_geoms": dealer_geoms,
        "yeidai_fences": yeidai_fences,
        "yeidai_geoms": yeidai_geoms,
        "key_to_uid": build_key_uid_map(units),
    }


# ---------------------------------------------------------------------------
# T-202：共享边界米数（冻结算法：boundary 交的线性部分逐段 haversine 求和）
# ---------------------------------------------------------------------------


def _collect_linear_parts(geom: Any, parts: list[Any]) -> None:
    """递归收集几何中的线性部件（LineString / LinearRing）。

    boundary 交可能返回 Point / MultiPoint / MultiLineString / GeometryCollection，
    只有线性部件贡献共享边界长度；Point/MultiPoint 贡献为 0（直接跳过）。
    """
    gtype = geom.geom_type
    if gtype in ("LineString", "LinearRing"):
        parts.append(geom)
    elif gtype in ("MultiLineString", "GeometryCollection"):
        for sub in getattr(geom, "geoms", ()):
            _collect_linear_parts(sub, parts)
    # Point / MultiPoint / 多边形等其余类型：贡献 0，不收集


def shared_boundary_m(geom_a: Any, geom_b: Any) -> float:
    """两单元共享边界长度（米）。

    冻结算法（任务卡 T-202 逐字）：
    ``a.boundary.intersection(b.boundary)``，递归收集线性部分，
    对每段相邻坐标调用 ``haversine_km(p, q) * 1000`` 求和；
    Point/MultiPoint 贡献为 0。禁止用经纬度 ``.length`` 冒充米。
    """
    crossing = geom_a.boundary.intersection(geom_b.boundary)
    parts: list[Any] = []
    _collect_linear_parts(crossing, parts)
    total_m = 0.0
    for part in parts:
        coords = list(part.coords)
        for p, q in zip(coords, coords[1:]):
            total_m += haversine_km((p[0], p[1]), (q[0], q[1])) * 1000.0
    return total_m


def are_adjacent(geom_a: Any, geom_b: Any, link_min_m: float = LINK_MIN_M) -> bool:
    """邻接判定：共享边界 >= link_min_m 才建边。

    仅点接触、共享长度不足、相离、或只有面积重叠（内部相交时边界交集
    不会形成共享线）均不得建边。
    """
    if geom_a.intersection(geom_b).area > 0.0:
        return False  # 面积重叠 = 破损几何，不是邻接
    return shared_boundary_m(geom_a, geom_b) >= link_min_m


def pair_overlap_ratio(unit_geoms: list[Any]) -> float:
    """G2-a 重叠率：全部无序单元对（i<j）的交集面积和 / 全部单元面积和。

    分子分母均用同一批 GCJ-02 几何的 Shapely 平面面积，无量纲。
    """
    total_area = sum(g.area for g in unit_geoms)
    if total_area <= 0.0:
        return 0.0
    overlap = 0.0
    for i in range(len(unit_geoms)):
        for j in range(i + 1, len(unit_geoms)):
            overlap += unit_geoms[i].intersection(unit_geoms[j]).area
    return overlap / total_area


def build_adjacency(unit_geoms: list[Any], link_min_m: float = LINK_MIN_M) -> dict[str, list[int]]:
    """建立无向邻接图：键为 uid 的字符串形式（升序），值为升序唯一 uid 数组。

    包含全部 uid（含可能的孤立节点）；无自环；严格对称。
    """
    n = len(unit_geoms)
    neighbors: dict[int, set[int]] = {u: set() for u in range(n)}
    for u in range(n):
        for v in range(u + 1, n):
            if are_adjacent(unit_geoms[u], unit_geoms[v], link_min_m):
                neighbors[u].add(v)
                neighbors[v].add(u)
    return {str(u): sorted(neighbors[u]) for u in range(n)}


def _atomic_write_text(data_dir: Path, filename: str, text: str) -> Path:
    """原子写出 UTF-8 文本：临时文件 + ``os.replace``，异常时清理临时文件。"""
    out_path = data_dir / filename
    fd, tmp_name = tempfile.mkstemp(dir=data_dir, prefix=f".{filename}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, out_path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return out_path


def write_unit_graph(data_dir: Path, adjacency: dict[str, list[int]], link_min_m: int = LINK_MIN_M) -> Path:
    """原子写出 ``unit_graph.json``：紧凑 UTF-8 JSON，键按 uid 整数升序。

    临时文件 + ``os.replace`` 保证原子替换；同输入产出字节级一致（确定性序列化）。
    """
    out_path = data_dir / UNIT_GRAPH_FILENAME
    ordered: dict[str, list[int]] = {}
    for uid in sorted(adjacency, key=int):
        ordered[uid] = adjacency[uid]
    payload = {"adjacency": ordered, "link_min_m": link_min_m}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return _atomic_write_text(data_dir, UNIT_GRAPH_FILENAME, text)


# ---------------------------------------------------------------------------
# T-203：oracle 单元集与表达能力指标（CONTRACTS v1.4 §3.6，公式与边界规则冻结）
# ---------------------------------------------------------------------------


def load_unit_graph(data_dir: Path, expected_n_units: int) -> dict[int, list[int]]:
    """加载并校验 T-202 产物 ``unit_graph.json``，返回 ``uid -> 邻接 uid 升序列表``。

    冻结契约：顶层键恰为 ``{"adjacency", "link_min_m"}``；``link_min_m == 50``；
    adjacency 必须覆盖 uid ``0..N-1``、无自环、严格对称、值内升序唯一。
    """
    path = data_dir / UNIT_GRAPH_FILENAME
    payload = load_json_object(path)
    _require_top_keys(path, payload, ("adjacency", "link_min_m"))
    link_min_m = _require_finite(path, "顶层", payload["link_min_m"], "link_min_m")
    if link_min_m != LINK_MIN_M:
        raise _fail(path, f"link_min_m 必须为 {LINK_MIN_M}（冻结常数），实际为 {payload['link_min_m']!r}")
    adjacency_raw = payload["adjacency"]
    if not isinstance(adjacency_raw, dict):
        raise _fail(path, f"adjacency 必须是对象，实际为 {type(adjacency_raw).__name__}")
    expected_uids = set(range(expected_n_units))
    parsed: dict[int, list[int]] = {}
    for k, nbrs_raw in adjacency_raw.items():
        if not isinstance(k, str) or not k.isdigit():
            raise _fail(path, f"adjacency 键 {k!r} 必须是 uid 的十进制字符串")
        uid = int(k)
        if uid not in expected_uids:
            raise _fail(path, f"adjacency 含无效 uid：{uid}（合法范围 0..{expected_n_units - 1}）")
        if not isinstance(nbrs_raw, list):
            raise _fail(path, f"uid {uid} 的邻接值必须是数组，实际为 {type(nbrs_raw).__name__}")
        for v in nbrs_raw:
            if isinstance(v, bool) or not isinstance(v, int):
                raise _fail(path, f"uid {uid} 的邻接值含非整数元素：{v!r}")
            if v == uid:
                raise _fail(path, f"adjacency 存在自环：uid {uid}")
            if v not in expected_uids:
                raise _fail(path, f"uid {uid} 的邻接含无效 uid：{v}（合法范围 0..{expected_n_units - 1}）")
        parsed[uid] = nbrs_raw
    missing = expected_uids - set(parsed)
    if missing:
        raise _fail(path, f"adjacency 缺少 uid（必须覆盖 0..{expected_n_units - 1}）：{sorted(missing)[:5]}")
    for uid, nbrs in parsed.items():
        if nbrs != sorted(set(nbrs)):
            raise _fail(path, f"uid {uid} 的邻接列表必须升序且唯一")
        for v in nbrs:
            if uid not in parsed[v]:
                raise _fail(path, f"adjacency 不对称：uid {uid} 列出 {v}，但 {v} 未列出 {uid}")
    return parsed


def _components_of_induced_subgraph(unit_ids: list[int], adjacency: dict[int, list[int]]) -> int:
    """诱导子图连通分量数：只沿两端均在 ``unit_ids`` 内的边遍历（迭代 DFS）。

    ``unit_ids`` 为空时由调用方先报错；非空结果必为正整数。
    """
    selected = set(unit_ids)
    seen: set[int] = set()
    count = 0
    for start in sorted(selected):
        if start in seen:
            continue
        count += 1
        seen.add(start)
        stack = [start]
        while stack:
            cur = stack.pop()
            for nxt in adjacency.get(cur, ()):
                if nxt in selected and nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
    return count


def compute_fence_oracle(
    fence_geom: Any,
    units: list[dict[str, Any]],
    unit_geoms: list[Any],
    adjacency: dict[int, list[int]],
) -> dict[str, Any]:
    """单条围栏的 oracle 单元集与 v1.4 冻结指标（CONTRACTS v1.4 §3.6 逐字）。

    U(F) = {u : fence_geom.covers(Point(u["centroid"]))}（含恰落边界的质心）；
    iou/recall/precision 分母零、选中集空、任一参与面积非正 → 中文报错停止。
    """
    if fence_geom.area <= 0.0:
        raise _fail(Path(ORACLE_FILENAME), "围栏面积为零，冻结公式无法产生有限指标")
    centroid_points = [Point(u["centroid"]) for u in units]
    selected = [i for i, p in enumerate(centroid_points) if fence_geom.covers(p)]
    if not selected:
        raise _fail(Path(ORACLE_FILENAME), "oracle 选中单元集为空，冻结公式无法产生有限指标")
    boundary_centroids = sum(1 for i in selected if centroid_points[i].intersects(fence_geom.boundary))
    union = shapely.union_all([unit_geoms[i] for i in selected])
    inter_area = union.intersection(fence_geom).area
    union_area = union.area
    fence_area = fence_geom.area
    if union_area <= 0.0:
        raise _fail(Path(ORACLE_FILENAME), "选中单元并集面积为零，冻结公式无法产生有限指标")
    if any(unit_geoms[i].area <= 0.0 for i in selected):
        raise _fail(Path(ORACLE_FILENAME), "存在零面积选中单元，冻结公式无法产生有限指标")
    iou = inter_area / (union_area + fence_area - inter_area)
    recall = inter_area / fence_area
    precision = inter_area / union_area
    straddle = sum(
        1
        for u in unit_geoms
        if STRADDLE_LOW <= (u.intersection(fence_geom).area / u.area) <= STRADDLE_HIGH
    )
    components = _components_of_induced_subgraph(selected, adjacency)
    return {
        "unit_ids": selected,
        "iou": iou,
        "recall": recall,
        "precision": precision,
        "straddle": int(straddle),
        "components": int(components),
        "boundary_centroids": int(boundary_centroids),
    }


def build_oracle_unitsets(
    data_dir: Path,
    inputs: dict[str, Any],
    adjacency: dict[int, list[int]],
) -> dict[str, Any]:
    """全部围栏 × oracle 指标 → oracle_unitsets.json 的内存 payload（不写盘）。

    fences 按 src_id 确定性排序；boundary_centroids 为全部围栏计数之和。
    """
    units = inputs["units"]
    unit_geoms = inputs["unit_geoms"]
    fences_out: dict[str, dict[str, Any]] = {}
    boundary_centroids = 0
    for layer, fences, geoms in (
        ("dealer", inputs["dealer_fences"], inputs["dealer_geoms"]),
        ("yeidai", inputs["yeidai_fences"], inputs["yeidai_geoms"]),
    ):
        for fence, fgeom in zip(fences, geoms):
            metrics = compute_fence_oracle(fgeom, units, unit_geoms, adjacency)
            boundary_centroids += metrics.pop("boundary_centroids")
            fences_out[fence["src_id"]] = {
                "name": fence["name"],
                "layer": layer,
                **metrics,
            }
    ordered = {sid: fences_out[sid] for sid in sorted(fences_out)}
    return {
        "method": ORACLE_METHOD,
        "link_min_m": LINK_MIN_M,
        "boundary_centroids": boundary_centroids,
        "fences": ordered,
    }


def write_oracle_unitsets(data_dir: Path, payload: dict[str, Any]) -> Path:
    """原子写出 ``oracle_unitsets.json``：紧凑 UTF-8 JSON（确定性序列化）。"""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return _atomic_write_text(data_dir, ORACLE_FILENAME, text)


# ---------------------------------------------------------------------------
# CLI（T-202 主入口：校验 → 建图 → G2-a → 原子写出）
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "T-201…T-204：P2 输入层校验 + 单元邻接图 + G2-a 自洽检查"
            "（写 unit_graph.json）+ oracle 单元集与 v1.4 指标"
            "（写 oracle_unitsets.json）+ G2-b 门禁与 G2-c/P2b 三段汇总。"
        ),
    )
    parser.add_argument(
        "--data",
        required=True,
        help="P1 产物目录（units.json 等只读；unit_graph.json 与 oracle_unitsets.json 写入该目录）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """T-201…T-204 主流程：校验 → 建图 → G2-a → 写图 → oracle 指标 → 写出 → 三段汇总。

    退出码：0 成功（P2b 触发不改变退出码——它是 P2b 的入口条件，不是 G2-c 失败）；
    2 输入校验失败；3 G2-a 重叠率超限（[GATE-FAIL]）；
    4 存在孤立单元（打印 ESCALATION 逐条清单，等 L0 判定，不豁免、不写文件）；
    5 oracle 阶段失败（T-203 冻结公式无法产生全部有限指标等）；
    6 G2-b 门禁失败：业代 median(iou) < 0.95（[GATE-FAIL]，G2-a/G2-c 原始数字保留在
    stdout，oracle_unitsets.json 不删除）。
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    data_dir = Path(args.data)
    try:
        inputs = load_pilot_inputs(data_dir)
    except PilotInputError as exc:
        print(f"校验失败：{exc}", file=sys.stderr)
        return 2
    units = inputs["units"]
    unit_geoms = inputs["unit_geoms"]

    ratio = pair_overlap_ratio(unit_geoms)
    adjacency = build_adjacency(unit_geoms)
    isolated_uids = [u for u, nbrs in adjacency.items() if not nbrs]

    if ratio >= 0.001:
        print(f"[GATE-FAIL] G2-a 重叠率 {ratio:.6g} >= 0.001，停止。", file=sys.stderr)
        return 3
    if isolated_uids:
        print("发现孤立单元（无任何邻接边），真实飞地不得由 L2 自行豁免，上报等 L0 确认：")
        for u in sorted(isolated_uids, key=int):
            unit = units[int(u)]
            print(
                f"ESCALATION:{unit['uid']}/{unit['key']}/"
                f"{unit['district_code']}/{unit['street']}"
            )
        return 4

    write_unit_graph(data_dir, adjacency)
    n_edges = sum(len(nbrs) for nbrs in adjacency.values()) // 2
    # T-203：消费刚落盘的 T-202 产物（从盘读取并校验，保证链式一致）
    try:
        graph = load_unit_graph(data_dir, expected_n_units=len(units))
        oracle_payload = build_oracle_unitsets(data_dir, inputs, graph)
        oracle_path = write_oracle_unitsets(data_dir, oracle_payload)
    except PilotInputError as exc:
        print(f"oracle 阶段失败：{exc}", file=sys.stderr)
        return 5

    # T-204 CLI 汇总：精确三段（G2-a / G2-b / G2-c），不产生第三个报告文件。
    # 门禁判据只用 iou：recall / precision 仅落盘用于解释漏选与溢出，
    # 禁止出现在任何 PASS/FAIL 或 P2b 判定表达式中；经销商不做中位数等聚合。
    fences_metrics = oracle_payload["fences"]
    yeidai_values = [v["iou"] for v in fences_metrics.values() if v["layer"] == "yeidai"]
    dealer_items = [(sid, v) for sid, v in fences_metrics.items() if v["layer"] == "dealer"]
    g2b_median = statistics.median(yeidai_values) if yeidai_values else float("nan")
    g2b_pass = bool(yeidai_values) and g2b_median >= 0.95
    p2b_triggered = any(v["iou"] < 0.90 for _, v in dealer_items)

    if oracle_payload["boundary_centroids"] > 0:
        print(
            f"[WARN] boundary_centroids={oracle_payload['boundary_centroids']} > 0"
            "（恰落围栏边界的质心，按原值报告，不改变 G2-b/G2-c 结果）",
            file=sys.stderr,
        )
    print(f"G2-a overlap_ratio={ratio:.6g} isolated={len(isolated_uids)} edges={n_edges}")
    print(
        f"G2-b yeidai_n={len(yeidai_values)} median_iou={g2b_median:.6f} "
        f"result={'PASS' if g2b_pass else 'FAIL'}"
    )
    for sid, v in dealer_items:
        print(
            f"G2-c dealer src_id={sid} iou={v['iou']:.6f} recall={v['recall']:.6f} "
            f"precision={v['precision']:.6f} straddle={v['straddle']} "
            f"components={v['components']} p2b={'YES' if v['iou'] < 0.90 else 'NO'}"
        )
    print(f"G2-c p2b_triggered={'YES' if p2b_triggered else 'NO'}")

    if not g2b_pass:
        print(
            f"[GATE-FAIL] G2-b 业代 median(iou)={g2b_median:.6f} < 0.95；"
            "原始数字保留于上列汇总与 oracle_unitsets.json，供 L1 追加门禁记录。",
            file=sys.stderr,
        )
        return 6
    return 0


if __name__ == "__main__":
    sys.exit(main())
