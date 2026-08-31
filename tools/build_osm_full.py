#!/usr/bin/env python3
"""Build the WKT landmark pack consumed by ``territory_compile``.

The source datasets intentionally use different coordinate systems:
OSM geometry is WGS-84, while the district GeoJSON is GCJ-02.  This
builder only changes the representation (lat/lon JSON -> lon/lat WKT)
and never transforms coordinates.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shapely.geometry import LineString, shape

import _paths


DISTRICT_FILENAME = "区划数据-区县-广东省-广州市.geojson"
HIGHWAY_CLASSES = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "residential",
    "unclassified",
    "service",
}


def _line_wkt(geometry: list[dict]) -> str:
    """Convert Overpass ``[{lat, lon}, ...]`` geometry to WKT."""
    coordinates = [(point["lon"], point["lat"]) for point in geometry]
    return LineString(coordinates).wkt


def _load_osm(raw_path: Path) -> tuple[list[dict], list[dict]]:
    with raw_path.open(encoding="utf-8") as handle:
        raw = json.load(handle)

    roads: list[dict] = []
    rivers: list[dict] = []
    for element in raw.get("elements", []):
        if element.get("type") != "way":
            continue

        tags = element.get("tags") or {}
        name = tags.get("name")
        geometry = element.get("geometry") or []
        if not name or len(geometry) < 2:
            continue

        wkt = _line_wkt(geometry)
        highway = tags.get("highway")
        if highway:
            if highway not in HIGHWAY_CLASSES:
                raise ValueError(
                    f"unsupported highway class {highway!r} "
                    f"for way {element.get('id')}; refusing invalid cls"
                )
            roads.append({"name": name, "cls": highway, "wkt": wkt})

        # Keep this independent from the highway branch so a way carrying
        # both tags would be represented in both source collections.
        if tags.get("waterway"):
            rivers.append({"name": name, "wkt": wkt})

    return roads, rivers


def _load_adm6(source_path: Path) -> list[dict]:
    with source_path.open(encoding="utf-8") as handle:
        source = json.load(handle)

    adm6: list[dict] = []
    for index, feature in enumerate(source.get("features", [])):
        geometry = feature.get("geometry")
        if not geometry:
            raise ValueError(f"district feature {index} has no geometry")
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError(
                f"district feature {index} has unsupported geometry type "
                f"{geometry.get('type')!r}"
            )

        properties = feature.get("properties") or {}
        adm6.append(
            {
                "name": properties.get("行政区名称", ""),
                # shape().wkt preserves polygon holes and multipolygon parts.
                "wkt": shape(geometry).wkt,
            }
        )
    return adm6


def build(data_root: Path) -> Path:
    raw_path = data_root / "osm_raw.json"
    source_path = data_root / "source" / DISTRICT_FILENAME
    output_path = data_root / "gz_osm_full.json"

    roads, rivers = _load_osm(raw_path)
    adm6 = _load_adm6(source_path)
    payload = {"roads": roads, "rivers": rivers, "adm6": adm6}

    # Replace atomically so a rerun cannot leave a partially written pack.
    temporary_path = output_path.with_name(f".{output_path.name}.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)

    print(
        f"Wrote {output_path}: roads={len(roads)} "
        f"rivers={len(rivers)} adm6={len(adm6)}"
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Guangzhou OSM WKT pack")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="data pack directory (default: _paths.data_dir resolution)",
    )
    args = parser.parse_args()
    data_root = _paths.data_dir(str(args.data_dir) if args.data_dir else None)
    build(data_root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
