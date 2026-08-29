#!/usr/bin/env python3
"""Generate data/<region>/compare.json — per-dealer hand-drawn vs rebuilt(V1c)
comparison payload for the /compare page.

rebuilt semantics = V1c from the oracle-ladder experiment:
typed-name barriers (roads/rivers/refs + admin fragments for 区界/边缘 clauses)
→ band 200m → grid BFS from contract center → oracle bbox closure.

Per dealer output: truth_ring, rebuilt_ring, bands, per-clause found flags,
IoU, leak, fidelity (share of hand-drawn perimeter within 150m of a
named-landmark geometry @150m).

Usage: python3 tools/gen_compare_data.py [--data-dir data/gz]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from shapely import contains_xy

from dealer_territory.fence_from_text import lookup_geometry
from intelligence.coords import pack_from_disk

BAND_KM = 0.20
LAT = 110.574


def lon_deg(km: float, lat: float) -> float:
    return km / (111.320 * math.cos(math.radians(lat)))


def ring_coords(g, cap: int = 900) -> list[list[float]]:
    return rings_of(g, cap)[0] if rings_of(g, cap) else []


def rings_of(g, cap: int = 900) -> list[list[list[float]]]:
    parts = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    out = []
    for p in parts:
        pts = list(p.exterior.coords)
        step = max(1, len(pts) // cap)
        out.append([[round(x, 5), round(y, 5)] for x, y in pts[::step]])
    return out

def admin_frags(osm: dict, nm: str) -> list[LineString]:
    out: list[LineString] = []
    for dn, v in osm.get("districts", {}).items():
        core = dn.replace("区", "").replace("市", "")
        if core and (core in nm or dn in nm or nm in dn):
            out += [LineString(pl) for pl in v.get("polys", []) if len(pl) >= 2]
    return out


def clause_lines(osm: dict, fb: dict, center) -> dict:
    """side → (name, [LineString…]) with typed lookup (admin vs roads/rivers)."""
    res = {}
    for side, raw in fb.items():
        nm = (raw or "").strip()
        if not nm:
            res[side] = (nm, [])
            continue
        segs = admin_frags(osm, nm) if any(
            t in nm for t in ("边缘", "区界", "市界", "界")) else []
        if not segs:
            segs = [LineString(s) for s in (lookup_geometry(nm, osm, center) or [])
                    if len(s) >= 2]
        res[side] = (nm, segs)
    return res


def rebuild_poly(fp: Polygon, center, clauses: dict, win: box):
    """V1c semantics: grid BFS inside window, oracle bbox closure on leak."""
    nx = min(int((win.bounds[2] - win.bounds[0]) / max(0.20 / LAT, math.hypot(
        win.bounds[2] - win.bounds[0], win.bounds[3] - win.bounds[1]) / 300)) + 1, 300)
    ny = min(int((win.bounds[3] - win.bounds[1]) / max(0.20 / LAT, math.hypot(
        win.bounds[2] - win.bounds[0], win.bounds[3] - win.bounds[1]) / 300)) + 1, 300)
    xs = np.linspace(win.bounds[0], win.bounds[2], nx)
    ys = np.linspace(win.bounds[1], win.bounds[3], ny)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    bands = [unary_union(l).buffer(BAND_KM / LAT)
             for _, l in clauses.values() if l]
    blocked = np.zeros((nx, ny), dtype=bool)
    if bands:
        blocked = contains_xy(unary_union(bands),
                              gx.ravel(), gy.ravel()).reshape(nx, ny)
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
        return None, False, xs, ys
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
    leak = bool(comp[0].any() or comp[-1].any()
                or comp[:, 0].any() or comp[:, -1].any())
    if leak:  # oracle closure to truth bbox
        bx = fp.bounds
        a0, a1 = sorted((int(np.argmin(np.abs(xs - bx[0]))),
                         int(np.argmin(np.abs(xs - bx[2])))))
        b0, b1 = sorted((int(np.argmin(np.abs(ys - bx[1]))),
                         int(np.argmin(np.abs(ys - bx[3])))))
        mask = np.zeros_like(comp)
        mask[a0:a1 + 1, b0:b1 + 1] = True
        comp = comp & mask
    return comp, leak, xs, ys


def mask_to_poly(comp, xs, ys) -> Polygon | None:
    dx = (xs[1] - xs[0]) if len(xs) > 1 else 1e-4
    dy = (ys[1] - ys[0]) if len(ys) > 1 else 1e-4
    boxes = []
    for a in range(comp.shape[0]):
        col = comp[a]
        b = 0
        while b < comp.shape[1]:
            if col[b]:
                b0 = b
                while b < comp.shape[1] and col[b]:
                    b += 1
                boxes.append(box(xs[a] - dx / 2, ys[b0] - dy / 2,
                                 xs[a] + dx / 2, ys[b - 1] + dy / 2))
            else:
                b += 1
    if not boxes:
        return None
    return unary_union(boxes)


def fidelity(osm: dict, fb: dict, center, fp: Polygon) -> float | None:
    lines = [l for _, ls in clause_lines(osm, fb, center).values() for l in ls]
    if not lines:
        return None
    parts = list(fp.geoms) if fp.geom_type == "MultiPolygon" else [fp]
    pts = []
    for p in parts:
        pts += [p.exterior.interpolate(t / 200, normalized=True) for t in range(200)]
    hit = sum(1 for pt in pts
              if any(L.distance(pt) * 111000 <= 150 for L in lines))
    return round(hit / len(pts), 3) if pts else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/gz")
    a = ap.parse_args()
    d = Path(a.data_dir)
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    reg = json.loads((d / "region.json").read_text(encoding="utf-8"))
    cons = json.loads((d / "contracts.json").read_text(encoding="utf-8"))
    pack_from_disk(reg, cons, meta)          # → WGS-84
    osm = json.loads((d / "osm_parsed.json").read_text(encoding="utf-8"))
    fences: dict[str, list] = {}
    for f in reg["fences"]:
        r = f["rings"]
        if isinstance(r, str):
            r = json.loads(r)
        p = Polygon([tuple(q) for q in r[0]])
        fences.setdefault(f["dealer"], []).append(p if p.is_valid else p.buffer(0))
    truth = {k: (unary_union(v) if len(v) > 1 else v[0]) for k, v in fences.items()}

    out = []
    for i, c in enumerate(cons):
        dealer = c["dealer_id"]
        center = tuple(c.get("center") or [])
        fb = c.get("four_bounds") or {}
        fp = truth.get(dealer)
        if fp is None or not center:
            continue
        bx = fp.bounds
        pad = 3.0
        win = box(bx[0] - lon_deg(pad, center[1]), bx[1] - pad / LAT,
                  bx[2] + lon_deg(pad, center[1]), bx[3] + pad / LAT)
        clauses = clause_lines(osm, fb, center)
        comp, leak, xs, ys = rebuild_poly(fp, center, clauses, win)
        if comp is None:
            print(f"[{i}] {dealer[:14]} no-start", flush=True)
            continue
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        tmask = contains_xy(fp, gx.ravel(), gy.ravel()).reshape(comp.shape)
        inter = int((comp & tmask).sum()); union = int((comp | tmask).sum())
        iou = round(inter / union, 3) if union else 0.0
        rb = mask_to_poly(comp, xs, ys)
        if rb is None:
            continue
        rb_s = rb.simplify(0.0008, preserve_topology=True)
        big = (max(rb_s.geoms, key=lambda p: p.area)
               if rb_s.geom_type == "MultiPolygon" else rb_s)
        bands_geo = [unary_union(l).buffer(BAND_KM / LAT)
                     for _, l in clauses.values() if l]
        out.append({
            "dealer": dealer,
            "iou": iou, "leak": leak,
            "fidelity": fidelity(osm, fb, center, fp),
            "center": [round(center[0], 5), round(center[1], 5)],
            "truth_rings": rings_of(fp),
            "rebuilt_rings": rings_of(rb_s),
            "clauses": {s: {"name": nm, "found": bool(l)}
                        for s, (nm, l) in clauses.items()},
            "bands": [r for b in bands_geo
                      for r in rings_of(b, 120)],
        })
        print(f"[{i}] {dealer[:14]:14s} IoU {iou:.2f} leak={leak} "
              f"fid={out[-1]['fidelity']}", flush=True)

    dst = d / "compare.json"
    dst.write_text(json.dumps({"crs": "WGS84", "version": "V1c",
                               "generated": True, "items": out},
                              ensure_ascii=False), encoding="utf-8")
    print(f"{dst}: {len(out)} dealers")


if __name__ == "__main__":
    main()
