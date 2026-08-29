#!/usr/bin/env python3
"""Benchmark: our four-bounds rebuild vs the customer's hand-drawn fences.

contracts.json four_bounds were reverse-extracted FROM the real fences,
so this is the fair pipeline test: text -> rebuild -> compare vs truth.

Two modes per dealer:
  blind   clip radius from store_count / density (what the system knows
          from the contract alone)
  oracle  clip radius from the TRUE fence extent (upper bound of what the
          landmark geometry can express if area were given perfectly)

Metrics (WGS-84, shapely):
  iou            intersection / union with the hand-drawn fence
  store_keep     % of that dealer's stores still inside the rebuilt fence
  edge_dev_m     median symmetric boundary-to-boundary vertex distance
  ok_rate        rebuilt with ring>=4 pts (else pipeline coverage gap)

Usage: python3 tools/bench_rebuild.py [--data-dir data/gz]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shapely.geometry import Point, Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from dealer_territory.fence_from_text import (  # noqa: E402
    build_from_landmark_ratios, lookup_geometry)
from intelligence.coords import pack_from_disk  # noqa: E402


def _dist_km(a, b):
    return math.hypot((a[0] - b[0]) * 111.32 * math.cos(math.radians(a[1])),
                      (a[1] - b[1]) * 110.574)


def km2(g):
    if g.is_empty:
        return 0.0
    p = g.representative_point()
    return g.area * 110.574 * 111.32 * math.cos(math.radians(p.y))
def boundary_dev_m(a, b, cap: int = 200) -> float:
    def coords(g):
        parts = (g.geoms if g.geom_type == "MultiPolygon" else [g])
        return [list(p.exterior.coords) for p in parts]
    def one_way(src, dst):
        out = []
        dst_b = unary_union([p.boundary for p in
                             (dst.geoms if dst.geom_type == "MultiPolygon" else [dst])])
        for pc in coords(src):
            pts = pc
            if len(pts) > cap:
                idx = [int(i * (len(pts) - 1) / (cap - 1)) for i in range(cap)]
                pts = [pts[i] for i in idx]
            out += [dst_b.distance(Point(p)) * 111000 for p in pts]
        return out
    s = one_way(a, b) + one_way(b, a)
    s.sort()
    return s[len(s) // 2] if s else float("nan")


def assemble_spec(fb, center, osm, r_clip):
    spec = {}
    for dd in ("西", "北", "东", "南"):
        nm = (fb.get(dd) or "").strip()
        if not nm:
            continue
        segs = lookup_geometry(nm, osm, center)
        if not segs:
            continue
        allp = [p for seg in segs for p in seg]
        anchor = min(allp, key=lambda p: (p[0] - center[0]) ** 2
                     + (p[1] - center[1]) ** 2)
        line = next((s for s in segs if anchor in s), max(segs, key=len))
        tot, cum = 0.0, [0.0]
        for i in range(1, len(line)):
            tot += _dist_km(line[i - 1], line[i])
            cum.append(tot)
        keep = [i for i, q in enumerate(line) if _dist_km(q, center) <= r_clip]
        if len(keep) < 2:
            continue
        fr = cum[min(keep)] / tot if tot > 0 else 0.0
        to = cum[max(keep)] / tot if tot > 0 else 1.0
        spec[dd] = (nm, fr, to)
    return spec


def try_build(dealer, spec, center, osm):
    if len(spec) < 3:
        return None, f"spec {len(spec)} bounds"
    built = build_from_landmark_ratios(dealer, spec, center, osm)
    if "ring" not in built:
        return None, str(built.get("error", "no ring"))[:60]
    rb = Polygon(built["ring"])
    rb = rb if rb.is_valid else rb.buffer(0)
    if rb.is_empty or rb.area < 1e-12:
        return None, "empty ring"
    return rb, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/gz")
    ap.add_argument("--out", default="/tmp/rebuild_bench.json")
    a = ap.parse_args()

    d = Path(a.data_dir)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8")) \
        if (d / "meta.json").exists() else {}
    reg = json.loads((d / "region.json").read_text(encoding="utf-8"))
    contracts = json.loads((d / "contracts.json").read_text(encoding="utf-8"))
    pack_from_disk(reg, contracts, meta)  # -> WGS-84
    osm = json.loads((d / "osm_parsed.json").read_text(encoding="utf-8"))

    fence_by_dealer: dict[str, list] = {}
    for f in reg["fences"]:
        rings = f["rings"]
        if isinstance(rings, str):
            rings = json.loads(rings)
        fence_by_dealer.setdefault(f["dealer"], []).append(rings[0])
    density = float(meta.get("density_assumption_stores_per_km2", 25))

    results = []
    for c in contracts:
        dealer = c["dealer_id"]
        center = tuple(c.get("center") or [])
        fb = c.get("four_bounds") or {}
        row = {"dealer": dealer}
        if dealer not in fence_by_dealer or not center or len(fb) < 3:
            results.append({**row, "error": "missing fence/center/bounds"})
            continue
        origs = [Polygon(r) for r in fence_by_dealer[dealer]]
        origs = [p if p.is_valid else p.buffer(0) for p in origs]
        o = unary_union(origs) if len(origs) > 1 else origs[0]
        mine = [s for s in reg["stores"] if dealer in s["dealers"]]

        for mode in ("blind", "oracle"):
            if mode == "blind":
                area_est = max(2.0, c.get("store_count", 500) / density)
                r_clip = math.sqrt(area_est / math.pi) * 1.6
            else:  # oracle: true extent radius + 25% margin
                parts = (o.geoms if o.geom_type == "MultiPolygon" else [o])
                r_clip = max(_dist_km(pt, center)
                             for pp in parts for pt in pp.exterior.coords) * 1.25
            spec = assemble_spec(fb, center, osm, r_clip)
            rb, err = try_build(dealer, spec, center, osm)
            m = "_blind" if mode == "blind" else "_oracle"
            if rb is None:
                row[f"built{m}"] = False
                row[f"err{m}"] = err
                continue
            inter = rb.intersection(o).area
            union = rb.union(o).area
            keep_n = sum(1 for s in mine if rb.contains(Point(s["lon"], s["lat"])))
            row[f"built{m}"] = True
            row[f"iou{m}"] = round(inter / union, 3) if union else 0.0
            row[f"store_keep{m}"] = round(keep_n / len(mine), 3) if mine else None
            row[f"edge_dev_m{m}"] = round(boundary_dev_m(o, rb))
            row[f"area_true{m}"] = round(km2(o), 1)
            row[f"area_rebuilt{m}"] = round(km2(rb), 1)
        results.append(row)

    nb = sum(1 for r in results if r.get("built_blind"))
    no = sum(1 for r in results if r.get("built_oracle"))
    def q(arr, p):
        arr = sorted(arr)
        return arr[int((len(arr) - 1) * p)] if arr else None
    bi = [r["iou_blind"] for r in results if r.get("built_blind")]
    bo = [r.get("iou_oracle") for r in results if r.get("built_oracle")]
    bk = [r["store_keep_blind"] for r in results
          if r.get("built_blind") and r.get("store_keep_blind") is not None]
    ok = [r.get("store_keep_oracle") for r in results
          if r.get("built_oracle") and r.get("store_keep_oracle") is not None]
    bd = [r["edge_dev_m_blind"] for r in results if r.get("built_blind")]
    od = [r.get("edge_dev_m_oracle") for r in results if r.get("built_oracle")]

    print(f"dealers: {len(results)}")
    print(f"pipeline coverage — blind(contract-only): {nb}/{len(results)}"
          f"  oracle(true radius): {no}/{len(results)}")
    if bi:
        print(f"blind  IoU median {q(bi,.5):.3f} p25 {q(bi,.25):.3f} | "
              f"store_keep median {q(bk,.5):.3f} | edge_dev median {q(bd,.5):.0f} m")
    if bo:
        print(f"oracle IoU median {q(bo,.5):.3f} p25 {q(bo,.25):.3f} | "
              f"store_keep median {q(ok,.5):.3f} | edge_dev median {q(od,.5):.0f} m")
    good = [r for r in results if r.get("built_oracle") and r.get("iou_oracle", 0) >= 0.6]
    print(f"oracle IoU>=0.6: {len(good)} dealers")
    Path(a.out).write_text(json.dumps(results, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(f"full results -> {a.out}")


if __name__ == "__main__":
    main()
