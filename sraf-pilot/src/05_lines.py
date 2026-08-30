# -*- coding: utf-8 -*-
"""05_lines.py — T-501：P5 OSM 全量命名线要素构建与 GCJ-02 边界归一。

职责（任务卡 T-501，schema 卡载冻结 ``p5-lines-v1``）：

1. 读取 L0 准备的 OSM Overpass JSON 快照（只读、WGS-84、禁止联网）。
   必须覆盖全等级 ``highway/waterway/railway``：主线 ``tools/fetch_region_osm.py``
   只取 motorway~secondary 且强制 ``name``，在试点区仅覆盖约 12.8% 路网，
   是已知错误数据边界，本模块严禁复用或改写该查询。
2. 每个坐标入库前调用且仅调用一次 ``intelligence.coords.wgs2gcj``
   （试点业务数据为 GCJ-02；禁止复制/改写/近似转换公式，禁止二次转换）。
3. 同一精确 ``name`` 的 way 聚合为唯一一行；几何只做 LineString /
   MultiLineString 组装，禁止 polygonize/buffer/union/difference，
   禁止访问 ``.exterior``。
4. 先在内存完成全部校验与构建，再以同目录临时文件原子替换目标；
   任一命名 way 非法均中文抛错，不产生半份输出，输入快照字节不变。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from intelligence.coords import wgs2gcj
except ModuleNotFoundError:
    # 脚本直跑（python3 sraf-pilot/src/05_lines.py）时仓库根不在 sys.path；
    # 仓库根 = 本文件向上三级（sraf-pilot/src -> sraf-pilot -> <repo root>）。
    _REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from intelligence.coords import wgs2gcj


class LineBuildError(Exception):
    """OSM 快照或输出目标不满足契约时抛出；消息为中文，含具体定位与原因。"""


# ---------------------------------------------------------------------------
# 契约常量（任务卡 T-501 卡载冻结，禁止放宽或增删字段）
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "p5-lines-v1"
CRS = "GCJ-02"
SOURCE_CRS = "WGS-84"
CLASS_KEYS = ("highway", "waterway", "railway")
TOP_FIELDS = ("schema_version", "crs", "source_crs", "source_sha256", "counts", "lines")
LINE_FIELDS = ("name", "classes", "osm_way_ids", "geom")
COUNT_FIELDS = ("source_elements", "source_named_ways", "output_names", "output_parts")


# ---------------------------------------------------------------------------
# 输入读取：原始字节 + sha256 + JSON 解析（只读）
# ---------------------------------------------------------------------------


def load_source(path: Path) -> tuple[dict[str, Any], bytes, str]:
    """读取 OSM 快照：返回（解析对象, 原始字节, 原始字节 sha256 小写十六进制）。

    文件缺失 / 非法 UTF-8 JSON / 顶层非对象 / ``elements`` 非数组均中文抛错。
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise LineBuildError(f"源文件不存在：{path}")
    except IsADirectoryError:
        raise LineBuildError(f"源路径是目录而非文件：{path}")
    except OSError as exc:
        raise LineBuildError(f"源文件不可读：{path}：{exc}")
    sha = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LineBuildError(f"源文件 {path}：不是合法 UTF-8 JSON：{exc}")
    if not isinstance(payload, dict):
        raise LineBuildError(
            f"源文件 {path}：顶层必须是 JSON 对象，实际为 {type(payload).__name__}"
        )
    if not isinstance(payload.get("elements"), list):
        raise LineBuildError(
            f"源文件 {path}：elements 必须是数组，实际为 {type(payload.get('elements')).__name__}"
        )
    return payload, raw, sha


# ---------------------------------------------------------------------------
# 命名 way 校验（任一非法即中文抛错，禁止静默跳过脏命名 way）
# ---------------------------------------------------------------------------


def _way_label(index: int, way_id: Any, name: Any) -> str:
    """错误定位标签，如 ``elements[3]（way id=123，name='xx'）``。"""
    return f"elements[{index}]（way id={way_id}，name={name!r}）"


def _check_named_value(index: int, name: Any) -> str:
    """``tags.name`` 必须是去首尾空白后非空的字符串；返回原值。"""
    if not isinstance(name, str) or not name.strip():
        raise LineBuildError(
            f"elements[{index}]：命名 way 的 name 必须是非空字符串，实际为 {name!r}"
        )
    return name


def _check_way_id(index: int, way_id: Any) -> int:
    """命名 way 的 id 必须是正整数（bool 除外）。"""
    if not isinstance(way_id, int) or isinstance(way_id, bool) or way_id <= 0:
        raise LineBuildError(f"elements[{index}]：命名 way 的 id 必须是正整数，实际为 {way_id!r}")
    return way_id


def _check_class_keys(index: int, way_id: Any, tags: dict[str, Any]) -> list[str]:
    """命名 way 必须至少具有 highway/waterway/railway 之一；返回升序命中键。"""
    keys = sorted(k for k in CLASS_KEYS if k in tags)
    if not keys:
        raise LineBuildError(
            _way_label(index, way_id, tags.get("name"))
            + f"：缺少 highway/waterway/railway 之一，实际 tags 键为 {sorted(tags)!r}"
        )
    return keys


def _check_points(index: int, way_id: Any, name: Any, geometry: Any) -> list[tuple[float, float]]:
    """校验 geometry：点数组、每点有限数值 lat/lon、至少 2 个不同坐标点。

    返回 WGS-84 坐标点列表 ``[(lon, lat), ...]``，保持 OSM 原始点序。
    """
    if not isinstance(geometry, list):
        raise LineBuildError(
            _way_label(index, way_id, name)
            + f"：geometry 必须是点数组，实际为 {type(geometry).__name__}"
        )
    pts: list[tuple[float, float]] = []
    for j, p in enumerate(geometry):
        if not isinstance(p, dict):
            raise LineBuildError(
                _way_label(index, way_id, name) + f"：第 {j} 个坐标点必须是对象，实际为 {type(p).__name__}"
            )
        lat, lon = p.get("lat"), p.get("lon")
        for key, val in (("lat", lat), ("lon", lon)):
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise LineBuildError(
                    _way_label(index, way_id, name)
                    + f"：第 {j} 个坐标点的 {key} 必须是数字，实际为 {val!r}"
                )
            if not math.isfinite(val):
                raise LineBuildError(
                    _way_label(index, way_id, name)
                    + f"：第 {j} 个坐标点的 {key} 非有限值（NaN/Inf），实际为 {val!r}"
                )
        pts.append((float(lon), float(lat)))
    if len(set(pts)) < 2:
        raise LineBuildError(
            _way_label(index, way_id, name)
            + f"：几何至少需要 2 个不同坐标点，实际只有 {len(set(pts))} 个"
        )
    return pts


# ---------------------------------------------------------------------------
# 纯构建：源对象 -> 输出 payload（全部内存中完成，不写盘、不改输入）
# ---------------------------------------------------------------------------


def build_lines_payload(source: dict[str, Any], source_sha256: str) -> dict[str, Any]:
    """从已解析的 Overpass 对象构建 ``lines.json`` payload（纯函数，不改输入）。

    - 只处理 ``type == "way"`` 且 ``tags.name`` 去空白后非空、且具有三类键之一的元素；
      带非法 name 的命名 way 直接抛错（禁止冒充与静默跳过）。
    - 同一精确 name 聚合为唯一一行；parts 按 osm_way_id 升序；
      lines 按name Unicode 升序。
    """
    elements = source["elements"]
    named_ways = 0
    seen_ids: set[int] = set()
    # name -> {"classes": set[str], "ways": [(way_id, [(lon,lat),...]), ...]}
    by_name: dict[str, dict[str, Any]] = {}

    for index, element in enumerate(elements):
        if not isinstance(element, dict):
            continue  # 非 dict 元素无 tags，视为未命名，仅计数
        tags = element.get("tags")
        if not isinstance(tags, dict) or "name" not in tags:
            continue  # 未命名元素：计入 source_elements，不进入 lines
        name = _check_named_value(index, tags["name"])
        if element.get("type") != "way":
            raise LineBuildError(
                f"elements[{index}]（name={name!r}）：命名元素的 type 必须是 way，"
                f"实际为 {element.get('type')!r}"
            )
        named_ways += 1
        way_id = _check_way_id(index, element.get("id"))
        if way_id in seen_ids:
            raise LineBuildError(
                _way_label(index, way_id, name) + f"：命名 way 的 id 重复（首次见于本快照更早位置）"
            )
        seen_ids.add(way_id)
        _check_class_keys(index, way_id, tags)
        pts_wgs = _check_points(index, way_id, name, element.get("geometry"))

        bucket = by_name.setdefault(name, {"classes": set(), "ways": []})
        bucket["classes"].update(k for k in CLASS_KEYS if k in tags)
        bucket["ways"].append((way_id, pts_wgs))

    lines: list[dict[str, Any]] = []
    for name in sorted(by_name):
        bucket = by_name[name]
        # 每个坐标恰好调用一次真实 wgs2gcj（WGS-84 -> GCJ-02），结果必须有限。
        parts: list[list[tuple[float, float]]] = []
        for way_id, pts_wgs in sorted(bucket["ways"], key=lambda w: w[0]):
            pts_gcj: list[tuple[float, float]] = []
            for lon, lat in pts_wgs:
                try:
                    x, y = wgs2gcj(lon, lat)
                except Exception as exc:
                    raise LineBuildError(
                        _way_label(-1, way_id, name) + f"：wgs2gcj 坐标转换失败：{exc}"
                    )
                if not (isinstance(x, (int, float)) and isinstance(y, (int, float))
                        and math.isfinite(x) and math.isfinite(y)):
                    raise LineBuildError(
                        _way_label(-1, way_id, name)
                        + f"：wgs2gcj 转换结果非有限值，输入 (lon={lon!r}, lat={lat!r})，输出 ({x!r}, {y!r})"
                    )
                pts_gcj.append((float(x), float(y)))
            parts.append(pts_gcj)

        if len(parts) == 1:
            from shapely.geometry import LineString

            geom = LineString(parts[0]).wkt
        else:
            from shapely.geometry import MultiLineString

            geom = MultiLineString(
                [[(x, y) for x, y in part] for part in parts]
            ).wkt

        lines.append(
            {
                "name": name,
                "classes": sorted(bucket["classes"]),
                "osm_way_ids": sorted(w for w, _ in bucket["ways"]),
                "geom": geom,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "crs": CRS,
        "source_crs": SOURCE_CRS,
        "source_sha256": source_sha256,
        "counts": {
            "source_elements": len(elements),
            "source_named_ways": named_ways,
            "output_names": len(lines),
            "output_parts": named_ways,
        },
        "lines": lines,
    }


# ---------------------------------------------------------------------------
# 序列化与原子写出：同目录临时文件 + os.replace；失败不触碰目标原字节
# ---------------------------------------------------------------------------


def serialize_payload(payload: dict[str, Any]) -> str:
    """稳定序列化：UTF-8、ensure_ascii=False、indent=2、以换行结尾。"""
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def write_lines_json(out_path: Path, payload: dict[str, Any]) -> Path:
    """原子写出：临时文件写全、fsync 后 ``os.replace``；异常清理临时文件。"""
    out_path = Path(out_path)
    parent = out_path.parent
    if not parent.is_dir():
        raise LineBuildError(f"输出目录不存在：{parent}")
    text = serialize_payload(payload)
    tmp_name: str | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(dir=parent, prefix=".lines.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, out_path)
        tmp_name = None
    except OSError as exc:
        raise LineBuildError(f"输出目标不可写：{out_path}：{exc}")
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
    return out_path


# ---------------------------------------------------------------------------
# 编排入口：读取 -> 校验构建 -> 原子写出（任一步失败不留半份输出）
# ---------------------------------------------------------------------------


def build(src: Path, out: Path) -> dict[str, Any]:
    """完整构建：返回 payload（供 CLI 汇总与测试复用）；目标原子替换。"""
    source, _raw, sha = load_source(Path(src))
    payload = build_lines_payload(source, sha)
    write_lines_json(Path(out), payload)
    return payload


def output_sha256(out: Path) -> str:
    """输出文件字节 sha256（小写十六进制），用于汇总与双跑一致性留痕。"""
    return hashlib.sha256(Path(out).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="T-501：从 OSM 快照构建 P5 命名线要素 lines.json（GCJ-02）"
    )
    parser.add_argument("--src", required=True, help="OSM Overpass JSON 快照路径（只读）")
    parser.add_argument("--out", required=True, help="输出路径，如 data/pilot/lines.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        payload = build(Path(args.src), Path(args.out))
    except LineBuildError as exc:
        print(f"构建失败：{exc}", file=sys.stderr)
        return 1
    counts = payload["counts"]
    print(
        "lines.json 构建完成："
        f"source_elements={counts['source_elements']}"
        f" source_named_ways={counts['source_named_ways']}"
        f" output_names={counts['output_names']}"
        f" output_parts={counts['output_parts']}"
    )
    print(f"输出 sha256={output_sha256(Path(args.out))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
