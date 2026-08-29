#!/usr/bin/env python3
"""Render a P1 visual comparison page: for each dealer draw truth (green),
V1c bbox-closure region (blue), oracle-arc region (orange), and the
noise-floor proxy simplify-1000m (red dashed). Lets a human SEE why
P1 == V1c and what the real ceiling is."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union
from shapely import contains_xy
from shapely.geometry import LineString

from dealer_territory.fence_from_text import lookup_geometry
from intelligence.coords import pack_from_disk
from tools.bench_p1 import barriers, lon_deg, BAND_KM, LAT

ROOT = Path(__file__).resolve().parent.parent
from bench_p1 import barriers, lon_deg, BAND_KM, LAT

def component_polys(bands, truth_fp, center, win):
    """re-derive region polygons via BFS but return as shapely geometry."""
    diag = float(np.hypot(win.bounds[2] - win.bounds[0], win.bounds[3] - win.bounds[1]))
    cell = max(0.20 / LAT, diag / 300)
    nx = min(int((win.bounds[2] - win.bounds[0]) / cell) + 1, 300)
    ny = min(int((win.bounds[3] - win.bounds[1]) / cell) + 1, 300)
    xs = np.linspace(win.bounds[0], win.bounds[2], nx)
    ys = np.linspace(win.bounds[1], win.bounds[3], ny)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    blocked = np.zeros((nx, ny), dtype=bool)
    if bands:
        blocked = contains_xy(unary_union(bands), gx.ravel(), gy.ravel()).reshape(nx, ny)
    from collections import deque
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
        return []
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
    if leak:
        bx = truth_fp.bounds
        a0, a1 = sorted((int(np.argmin(np.abs(xs - bx[0]))), int(np.argmin(np.abs(xs - bx[2])))))
        b0, b1 = sorted((int(np.argmin(np.abs(ys - bx[1]))), int(np.argmin(np.abs(ys - bx[3])))))
        mask = np.zeros_like(comp)
        mask[a0:a1 + 1, b0:b1 + 1] = True
        comp &= mask
    boxes = []
    dx = (xs[1] - xs[0]) if len(xs) > 1 else 1e-4
    dy = (ys[1] - ys[0]) if len(ys) > 1 else 1e-4
    for a in range(nx):                    # a indexes x (xs[a])
        col = comp[a]
        b = 0
        while b < ny:                      # b indexes y (ys[b])
            if col[b]:
                b0 = b
                while b < ny and col[b]:
                    b += 1
                boxes.append(box(xs[a] - dx / 2, ys[b0] - dy / 2,
                                 xs[a] + dx / 2, ys[b - 1] + dy / 2))
            else:
                b += 1
    if not boxes:
        return []
    u = unary_union(boxes)
    return [p for p in (u.geoms if u.geom_type == "MultiPolygon" else [u])]


def main():
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

    cases = []
    for c in cons:
        dealer = c["dealer_id"]
        center = tuple(c.get("center") or [])
        fb = c.get("four_bounds") or {}
        fp = truth.get(dealer)
        if fp is None or not center or len(fb) < 3:
            continue
        bx = fp.bounds
        pad = 3.0
        win = box(bx[0] - lon_deg(pad, center[1]), bx[1] - pad / LAT,
                  bx[2] + lon_deg(pad, center[1]), bx[3] + pad / LAT)
        v_polys = component_polys(barriers(osm, fb, center, fp, "auto"), fp, center, win)
        o_polys = component_polys(barriers(osm, fb, center, fp, "P1"), fp, center, win)
        bands_geo = barriers(osm, fb, center, fp, "auto")
        nf = fp.simplify(1000.0 / 110574.0, preserve_topology=True)
        nf_polys = list(nf.geoms) if nf.geom_type == "MultiPolygon" else [nf]
        cases.append(dict(dealer=dealer,
            truth=[[[round(x,5),round(y,5)] for x,y in p.exterior.coords] for p in (list(fp.geoms) if fp.geom_type=="MultiPolygon" else [fp])],
            v1c=[[round(x,5),round(y,5)] for p in v_polys for x,y in p.exterior.coords],
            oracle=[[round(x,5),round(y,5)] for p in o_polys for x,y in p.exterior.coords],
            nf=[[round(x,5),round(y,5)] for p in nf_polys for x,y in p.exterior.coords],
            bands=[[[round(x,5),round(y,5)] for x,y in bb.exterior.coords] for bb in bands_geo if bb.geom_type=="Polygon"][:12],
            landmarks={s: (nm or "") for s,nm in fb.items()}))
    out = Path("data/gz/p1_visual.json")
    out.write_text(json.dumps({"crs": "WGS84", "cases": cases}, ensure_ascii=False), encoding="utf-8")
    print(out, len(cases), "cases")


if __name__ == "__main__":
    main()
