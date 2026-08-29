#!/usr/bin/env python3
"""P1 Oracle-Arc-Endpoint experiment (docs/FOUR_BOUNDS_RECONSTRUCTION_SPEC.md §10).

Question it answers: is the V1c≈0.49 ceiling caused by (a) arc-selection
failure — fixable by contract slots / better algorithm, or (b) the human
drawing-noise floor — already near ceiling, chase nothing further?

Variants per contract (same window/grid/BFS as V1c, pure geometry, no stores):
  V1c  auto barriers (typed lookup, whole feature clipped) + bbox closure  [reference]
  P1   oracle arcs: barrier = (landmark ∩ buffer(fence_boundary, 300 m)) —
       i.e. human tells the algorithm WHICH segment of the landmark is used + bbox closure
  NF-x noise-floor proxies: IoU(truth, simplify(truth, x m)) for x in
       {100, 300, 1000}; IoU(truth, convex_hull). These emulate a human
       re-drawing with shortcutting — the achievable ceiling vs truth.

Usage: python3 tools/bench_p1.py
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely import contains_xy

from dealer_territory.fence_from_text import lookup_geometry
from intelligence.coords import pack_from_disk

ROOT = Path(__file__).resolve().parent.parent
BAND_KM = 0.20
LAT = 110.574
USE_TOL_M = 300.0  # landmark segment counts as "used" if within this of truth boundary


def lon_deg(km, lat):
    return km / (111.320 * math.cos(math.radians(lat)))


def load():
    d = ROOT / "data/gz"
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    reg = json.loads((d / "region.json").read_text(encoding="utf-8"))
    cons = json.loads((d / "contracts.json").read_text(encoding="utf-8"))
    pack_from_disk(reg, cons, meta)
    osm = json.loads((d / "osm_parsed.json").read_text(encoding="utf-8"))
    fences = {}
    for f in reg["fences"]:
        r = f["rings"]
        if isinstance(r, str):
            r = json.loads(r)
        p = Polygon([tuple(q) for q in r[0]])
        fences.setdefault(f["dealer"], []).append(p if p.is_valid else p.buffer(0))
    truth = {k: (unary_union(v) if len(v) > 1 else v[0]) for k, v in fences.items()}
    return meta, reg, cons, osm, truth


def entity_lines(osm, nm, center):
    if any(t in nm for t in ("边缘", "区界", "市界", "界")):
        out = []
        for dn, v in osm.get("districts", {}).items():
            core = dn.replace("区", "").replace("市", "")
            if core and (core in nm or dn in nm):
                out += [LineString(pl) for pl in v.get("polys", []) if len(pl) >= 2]
        return out
    return [LineString(s) for s in (lookup_geometry(nm, osm, center) or [])
            if len(s) >= 2]


def barriers(osm, fb, center, truth_fp, mode):
    bands = []
    for side, raw in fb.items():
        nm = (raw or "").strip()
        if not nm:
            continue
        lines = entity_lines(osm, nm, center)
        if not lines:
            continue
        L = unary_union(lines)
        if mode == "P1":
            # oracle: keep only the portion of the landmark actually used
            tol = USE_TOL_M / 110574.0
            used = L.intersection(truth_fp.exterior.buffer(tol)
                                  if truth_fp.geom_type == "Polygon"
                                  else unary_union(
                                      [q.exterior for q in truth_fp.geoms]).buffer(tol))
            if used.is_empty:
                continue
            L = used
        bands.append(L.buffer(BAND_KM / LAT))
    return bands


def bfs_iou(bands, truth_fp, center, win):
    diag = math.hypot(win.bounds[2] - win.bounds[0], win.bounds[3] - win.bounds[1])
    cell = max(0.20 / LAT, diag / 300)
    nx = min(int((win.bounds[2] - win.bounds[0]) / cell) + 1, 300)
    ny = min(int((win.bounds[3] - win.bounds[1]) / cell) + 1, 300)
    xs = np.linspace(win.bounds[0], win.bounds[2], nx)
    ys = np.linspace(win.bounds[1], win.bounds[3], ny)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    blocked = np.zeros((nx, ny), dtype=bool)
    if bands:
        blocked = contains_xy(unary_union(bands), gx.ravel(), gy.ravel()).reshape(nx, ny)
    i0 = int(np.argmin(np.abs(xs - center[0])))
    j0 = int(np.argmin(np.abs(ys - center[1])))
    st = None
    for rad in range(12):
        for ii in range(max(0, i0 - rad), min(nx, i0 + rad + 1)):
            for jj in range(max(0, j0 - rad), min(ny, j0 + rad + 1)):
                if not blocked[ii, jj]:
                    st = (ii, jj)
                    break
            if st:
                break
        if st:
            break
    if not st:
        return None, True
    comp = np.zeros((nx, ny), dtype=bool)
    dq = deque([st])
    comp[st] = True
    while dq:
        a, b = dq.popleft()
        for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            aa, bb = a + da, b + db
            if 0 <= aa < nx and 0 <= bb < ny and not blocked[aa, bb] and not comp[aa, bb]:
                comp[aa, bb] = True
                dq.append((aa, bb))
    leak = bool(comp[0].any() or comp[-1].any() or comp[:, 0].any() or comp[:, -1].any())
    if leak:  # same bbox closure as V1c
        bx = truth_fp.bounds
        a0, a1 = sorted((int(np.argmin(np.abs(xs - bx[0]))), int(np.argmin(np.abs(xs - bx[2])))))
        b0, b1 = sorted((int(np.argmin(np.abs(ys - bx[1]))), int(np.argmin(np.abs(ys - bx[3])))))
        mask = np.zeros_like(comp)
        mask[a0:a1 + 1, b0:b1 + 1] = True
        comp &= mask
    tmask = contains_xy(truth_fp, gx.ravel(), gy.ravel()).reshape(nx, ny)
    inter = int((comp & tmask).sum())
    union = int((comp | tmask).sum())
    return (inter / union if union else 0.0), leak


def simp_iou(fp, meters):
    s = fp.simplify(meters / 110574.0, preserve_topology=True)
    if s.is_empty:
        return 0.0
    return s.intersection(fp).area / s.union(fp).area


def main():
    meta, reg, cons, osm, truth = load()
    rows = []
    for c in cons:
        d = c["dealer_id"]
        center = tuple(c.get("center") or [])
        fb = c.get("four_bounds") or {}
        fp = truth.get(d)
        if fp is None or not center or len(fb) < 3:
            continue
        bx = fp.bounds
        pad = 3.0
        win = box(bx[0] - lon_deg(pad, center[1]), bx[1] - pad / LAT,
                  bx[2] + lon_deg(pad, center[1]), bx[3] + pad / LAT)
        r = {"dealer": d}
        for mode in ("V1c", "P1"):
            b = barriers(osm, fb, center, fp, "auto" if mode == "V1c" else "P1")
            iou, leak = bfs_iou(b, fp, center, win) if b else (None, None)
            r[f"{mode.lower()}_iou"] = None if iou is None else round(iou, 3)
            r[f"{mode.lower()}_leak"] = leak
        r["nf100"] = round(simp_iou(fp, 100), 3)
        r["nf300"] = round(simp_iou(fp, 300), 3)
        r["nf1000"] = round(simp_iou(fp, 1000), 3)
        ch = fp.convex_hull
        r["cvx"] = round(fp.intersection(ch).area / fp.union(ch).area, 3)
        rows.append(r)

    def med(key):
        v = [r[key] for r in rows if r.get(key) is not None]
        return statistics.median(v) if v else float("nan")

    def q(key, p):
        v = sorted(r[key] for r in rows if r.get(key) is not None)
        return v[int((len(v) - 1) * p)] if v else float("nan")

    print(f"cases: {len(rows)}")
    print(f"V1c  auto-arc    median IoU {med('v1c_iou'):.3f}  p25 {q('v1c_iou',.25):.3f}  p75 {q('v1c_iou',.75):.3f}")
    print(f"P1   oracle-arc median IoU {med('p1_iou'):.3f}  p25 {q('p1_iou',.25):.3f}  p75 {q('p1_iou',.75):.3f}")
    print(f"Δ(P1−V1c) median {med('p1_iou') - med('v1c_iou'):+.3f}")
    print(f"noise-floor proxies: simplify 100m {med('nf100'):.2f} | 300m {med('nf300'):.2f} "
          f"| 1000m {med('nf1000'):.2f} | convex-hull {med('cvx'):.2f}")
    print()
    print("per-case (sorted by P1):")
    for r in sorted([x for x in rows if x.get("p1_iou") is not None],
                    key=lambda x: x["p1_iou"]):
        print(f"  P1 {r['p1_iou']:.2f}  V1c {r['v1c_iou'] if r['v1c_iou'] is not None else '—':>5}"
              f"  nf1k {r['nf1000']:.2f} cvx {r['cvx']:.2f}  {r['dealer'][:20]}")
    Path("/tmp/p1_results.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("→ /tmp/p1_results.json")


if __name__ == "__main__":
    main()
