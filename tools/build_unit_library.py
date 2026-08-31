#!/usr/bin/env python3
"""Build the WGS-84 base-unit library and its ledger attributes.

The source tessellation is the module-level ``U`` produced by
``territory_compile``.  Its polygons are GCJ-02, while the ledger contract
stores WGS-84 WKT, so conversion happens exactly once at this boundary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build basic_units_wgs.json and unit_attributes.json"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="data pack directory (default: _paths.data_dir resolution)",
    )
    return parser.parse_args()


def _write_json(path: Path, payload: dict) -> None:
    """Write deterministic JSON through a same-directory temporary file."""
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    temporary.replace(path)


def build(data_dir: Path, tc) -> tuple[Path, Path]:
    """Build both ledger inputs from one immutable snapshot of ``tc.U``."""
    from shapely import ops

    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise FileNotFoundError(f"data directory does not exist: {data_dir}")

    units = []
    attributes = []
    total = len(tc.U)
    print(f"开始导出统一铺盖 U：{total} 片", flush=True)

    for k, (geom, street_builtin, street_face, parent_index) in enumerate(tc.U):
        # U is GCJ-02; basic_units_wgs.json is explicitly WGS-84.
        wgs_geom = ops.transform(
            lambda x, y: tc.gcj2wgs(x, y),
            geom,
        )
        units.append({"geom": wgs_geom.wkt})

        street = street_builtin or street_face or ""
        district = tc.pdistrict[parent_index]
        attributes.append({
            "id": k,
            "district": district,
            "street": street,
            "roads": sorted(tc.feats_of(k)),
        })

        completed = k + 1
        if completed == 1 or completed % 500 == 0 or completed == total:
            print(f"属性/几何进度：{completed}/{total}", flush=True)

    basic_path = data_dir / "basic_units_wgs.json"
    attributes_path = data_dir / "unit_attributes.json"
    _write_json(basic_path, {"units": units})
    _write_json(attributes_path, {"units": attributes})
    print(f"已写入：{basic_path}")
    print(f"已写入：{attributes_path}")
    return basic_path, attributes_path


def main() -> int:
    args = _parse_args()

    # territory_compile reads _paths.DATA/SOURCE at import time.  Set the
    # explicit CLI selection before importing it so --data-dir is honoured by
    # the complete source pipeline, while still resolving the final path via
    # _paths.data_dir().
    requested = str(args.data_dir) if args.data_dir is not None else None
    if requested is not None:
        os.environ["SRAF_DATA_DIR"] = requested

    import _paths

    data_dir = _paths.data_dir(requested)
    import territory_compile as tc

    build(data_dir, tc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
