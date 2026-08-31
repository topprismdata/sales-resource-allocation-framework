#!/usr/bin/env python3
"""Build a Guangzhou region data pack from the supplied source exports.

The source fence coordinates are GCJ-02 and are intentionally copied without
coordinate conversion.  ``demo_server.py`` performs the one-time conversion
when it loads a pack whose ``meta.crs`` is ``GCJ-02``.

Usage::

    python3 tools/build_region_pack.py
    python3 tools/build_region_pack.py --src ../客户数据 --out data/gz

The command is repeatable: expected JSON files are regenerated and the three
source GeoJSON files are copied byte-for-byte into ``<out>/source``.  Other
files already present in the output directory are left untouched.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

from shapely import wkt


DEALER_CSV = "广州办事处经销商围栏数据-20260827.csv"
YEIDAI_CSVS = (
    "广州清单内业代的围栏数据-20260824.csv",
    "广州及华南MT办事处业代图层围栏数据-20260824.csv",
)
SOURCE_GEOJSONS = (
    "边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson",
    "区划数据-街道-广东省-广州市.geojson",
    "区划数据-区县-广东省-广州市.geojson",
)

COMMON_CSV_FIELDS = (
    "片区id",
    "area_code",
    "业代组织编码",
    "围栏名称",
    "layer",
    "中心点经度",
    "中心点纬度",
    "围栏面积",
    "area_level",
    "fence",
)
COMMON_CSV_FIELD_SET = set(COMMON_CSV_FIELDS)

KIND_COUNTS = {
    "OK": 0,
    "OOF": 0,
    "DIRECT_IN": 0,
    "DIRECT": 0,
    "GAP": 0,
    "MULTI": 0,
}


def _read_rows(path: Path, *, allow_extra_fields: bool) -> tuple[list[dict[str, str]], list[str]]:
    """Read one UTF-8 CSV, including fields longer than csv's default limit."""
    csv.field_size_limit(sys.maxsize)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        expected = COMMON_CSV_FIELD_SET
        actual = set(fieldnames)
        if allow_extra_fields:
            missing = sorted(expected - actual)
            if missing:
                raise ValueError(f"{path.name}: 缺少公共字段 {missing}")
        elif actual != expected or len(fieldnames) != len(COMMON_CSV_FIELDS):
            raise ValueError(
                f"{path.name}: 经销商 CSV 表头不匹配；实际={fieldnames}，"
                f"期望={list(COMMON_CSV_FIELDS)}"
            )
        rows = []
        for line_no, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"{path.name}:{line_no}: 存在无法映射的额外 CSV 列")
            rows.append({str(key): value for key, value in row.items()})
    return rows, fieldnames


def _ring_coords(sequence: Any, *, source: str) -> list[list[float]]:
    coords = []
    for point in sequence.coords:
        if len(point) != 2:
            raise ValueError(f"{source}: 仅支持二维经纬度坐标")
        lon, lat = float(point[0]), float(point[1])
        if not math.isfinite(lon) or not math.isfinite(lat):
            raise ValueError(f"{source}: 坐标包含非有限数值")
        coords.append([lon, lat])
    return coords


def _polygon_parts(geometry: Any, *, source: str) -> list[Any]:
    if geometry.geom_type == "Polygon":
        parts = [geometry]
    elif geometry.geom_type == "MultiPolygon":
        parts = list(geometry.geoms)
    else:
        raise ValueError(f"{source}: 不支持的几何类型 {geometry.geom_type}")
    if not parts or any(part.is_empty for part in parts):
        raise ValueError(f"{source}: 围栏包含空几何组件")
    if any(not math.isfinite(part.area) for part in parts):
        raise ValueError(f"{source}: 围栏面积包含非有限数值")
    return sorted(parts, key=lambda part: -part.area)


def _fences_from_rows(
    rows: Iterable[dict[str, str]],
    *,
    source_name: str,
    preserve_extra: bool,
) -> list[dict[str, Any]]:
    fences: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_no, row in enumerate(rows, start=2):
        src_area_id = row.get("片区id", "")
        dealer = row.get("围栏名称", "")
        if not src_area_id or not dealer:
            raise ValueError(f"{source_name}:{line_no}: 片区id/围栏名称不能为空")
        if src_area_id in seen_ids:
            raise ValueError(f"{source_name}:{line_no}: 片区id 重复: {src_area_id}")
        seen_ids.add(src_area_id)

        try:
            source_area_km2 = float(row["围栏面积"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{source_name}:{line_no}: 围栏面积不是数字") from exc
        if not math.isfinite(source_area_km2) or source_area_km2 < 0:
            raise ValueError(f"{source_name}:{line_no}: 围栏面积非法: {row.get('围栏面积')!r}")

        wkt_text = row.get("fence", "")
        if not wkt_text:
            raise ValueError(f"{source_name}:{line_no}: fence 为空")
        try:
            geometry = wkt.loads(wkt_text)
        except Exception as exc:  # shapely exceptions vary by version
            raise ValueError(f"{source_name}:{line_no}: fence WKT 无法解析") from exc
        parts = _polygon_parts(geometry, source=f"{source_name}:{line_no}")
        total_area = sum(part.area for part in parts)
        if total_area <= 0:
            raise ValueError(f"{source_name}:{line_no}: 围栏组件总面积必须大于 0")

        allocations = [source_area_km2 * part.area / total_area for part in parts]
        # Make the conservation rule explicit.  The final residual only
        # removes floating-point summation drift; it does not change the
        # component-area ratio beyond that rounding error.
        if len(allocations) > 1:
            allocations[-1] = source_area_km2 - sum(allocations[:-1])

        extra = {}
        if preserve_extra:
            extra = {
                key: value
                for key, value in row.items()
                if key not in COMMON_CSV_FIELD_SET
            }

        components_total = len(parts)
        for component, (part, area_km2) in enumerate(zip(parts, allocations), start=1):
            outer = _ring_coords(part.exterior, source=f"{source_name}:{line_no}")
            holes = [
                _ring_coords(interior, source=f"{source_name}:{line_no}")
                for interior in part.interiors
            ]
            area_id = src_area_id if components_total == 1 else f"{src_area_id}#{component}"
            record: dict[str, Any] = {
                "area_id": area_id,
                "src_area_id": src_area_id,
                "component": component,
                "components_total": components_total,
                "dealer": dealer,
                "area_km2": area_km2,
                "rings": [outer],
                "holes": holes,
            }
            if preserve_extra:
                record["extra"] = extra.copy()
            fences.append(record)
    return fences


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _copy_bytes(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
    os.close(fd)
    try:
        shutil.copyfile(source, tmp_name)
        os.replace(tmp_name, destination)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def build_pack(src: Path, out: Path) -> dict[str, int]:
    dealer_path = src / DEALER_CSV
    if not dealer_path.is_file():
        raise FileNotFoundError(f"缺少经销商围栏 CSV: {dealer_path}")
    for filename in (*YEIDAI_CSVS, *SOURCE_GEOJSONS):
        if not (src / filename).is_file():
            raise FileNotFoundError(f"缺少输入文件: {src / filename}")

    dealer_rows, _ = _read_rows(dealer_path, allow_extra_fields=False)
    region_fences = _fences_from_rows(
        dealer_rows,
        source_name=dealer_path.name,
        preserve_extra=False,
    )

    yeidai_fences: list[dict[str, Any]] = []
    yeidai_rows = 0
    for filename in YEIDAI_CSVS:
        path = src / filename
        rows, _ = _read_rows(path, allow_extra_fields=True)
        converted = _fences_from_rows(
            rows,
            source_name=path.name,
            preserve_extra=True,
        )
        yeidai_fences.extend(converted)
        yeidai_rows += len(rows)

    _write_json(
        out / "region.json",
        {"fences": region_fences, "stores": [], "kinds": KIND_COUNTS.copy()},
    )
    _write_json(
        out / "meta.json",
        {
            "region_name": "广州",
            "center": [113.35, 23.05],
            "zoom": 10,
            "crs": "GCJ-02",
            "direct_markers": [],
            "density_assumption_stores_per_km2": 40,
        },
    )
    _write_json(out / "contracts.json", [])
    _write_json(out / "yeidai_fences.json", {"fences": yeidai_fences})

    for filename in SOURCE_GEOJSONS:
        _copy_bytes(src / filename, out / "source" / filename)

    return {
        "dealer_rows": len(dealer_rows),
        "region_components": len(region_fences),
        "yeidai_rows": yeidai_rows,
        "yeidai_components": len(yeidai_fences),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=Path("../客户数据"), help="原始数据目录")
    parser.add_argument("--out", type=Path, default=Path("data/gz"), help="输出数据包目录")
    args = parser.parse_args(argv)

    try:
        summary = build_pack(args.src, args.out)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        "built region pack: "
        f"{summary['dealer_rows']} dealer rows -> {summary['region_components']} components; "
        f"{summary['yeidai_rows']} yeidai rows -> {summary['yeidai_components']} components; "
        f"out={args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
