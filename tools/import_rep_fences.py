#!/usr/bin/env python3
"""Import rep (Layer-B) fence CSV into a region pack as reps.json.

Input : CSV with columns 片区id, 业代组织编码, 围栏名称, 中心点经度/纬度,
        围栏面积, fence (WKT POLYGON/MULTIPOLYGON, GCJ-02)
Output: data/<region>/reps.json  — {crs, generated, reps:[{pid, code, name,
        claimed_km2, center, rings:[[[lon,lat],…],…]}]}  (kept in GCJ-02 on
        disk, normalized to WGS-84 at load by demo_server, same contract
        as region.json).

Diagnostics printed: duplicate codes, zero-area/empty reps, claimed vs
recomputed area mismatch.
Usage: python3 tools/import_rep_fences.py <csv> --out data/gz
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path

from shapely import wkt as swkt


def rings_of(g) -> list[list[list[float]]]:
    """Polygon/MultiPolygon → list of exterior rings (GCJ coords as-is)."""
    polys = g.geoms if g.geom_type == "MultiPolygon" else [g]
    out = []
    for p in polys:
        pts = [list(c) for c in p.exterior.coords]
        if pts[0] != pts[-1]:
            pts.append(pts[0])
        out.append(pts)
    return out


def km2(g) -> float:
    p = g.representative_point()
    return g.area * 110.574 * 111.320 * math.cos(math.radians(p.y))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--out", default="data/gz")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.csv_path, encoding="utf-8-sig")))
    reps, warn = [], []
    for r in rows:
        g = swkt.loads(r["fence"])
        if not g.is_valid:
            g = g.buffer(0)
        if g.is_empty or g.area < 1e-12:
            warn.append(f"empty geometry: {r['围栏名称']} pid={r['片区id']}")
            continue
        claimed = float(r["围栏面积"])
        got = km2(g)
        if claimed > 0.05 and abs(got - claimed) / claimed > 0.3:
            warn.append(f"area mismatch {r['围栏名称']}: claimed {claimed} vs "
                        f"recomputed {got:.2f} km²")
        reps.append({
            "pid": r["片区id"],
            "code": r["业代组织编码"],
            "name": r["围栏名称"],
            "office": r.get("办事处名称", ""),
            "claimed_km2": claimed,
            "center": [float(r["中心点经度"]), float(r["中心点纬度"])],
            "rings": rings_of(g),
        })
    dup = [c for c in {x["code"] for x in reps}
           if sum(1 for x in reps if x["code"] == c) > 1]
    out = Path(a.out) / "reps.json"
    out.write_text(json.dumps({
        "crs": "GCJ-02",
        "source": Path(a.csv_path).name,
        "reps": reps,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"{out}: {len(reps)} fence rows "
          f"({len({x['code'] for x in reps})} reps)")
    if dup:
        print("duplicate rep codes (multiple beat fragments):", dup)
    for w in warn:
        print("WARN:", w)


if __name__ == "__main__":
    main()
