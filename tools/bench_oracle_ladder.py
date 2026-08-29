#!/usr/bin/env python3
"""Oracle-ladder benchmark: separate implementation bugs from four-bounds
information ceiling (per analysis/research_brief_four_bounds.md).

Variants (pure geometry — stores NOT used):
  V1 typed-name   : barriers = contract-named entities via TYPED lookup
                    (roads/rivers/refs + ADMIN district fragments for
                    "…边缘/…区界" clauses that V0-of-old missed entirely)
  V2 oracle-arc   : barriers = ANY OSM line hugging the true fence's
                    extreme arc on that side (cheating arc selection)
  V3 oracle+close : V2 + oracle closure (clip leak to true bbox)

Barrier semantics: 200m band, ~150m grid, 4-conn BFS from center.
Metric: IoU vs hand-drawn truth; leak flag.

Usage: python3 tools/bench_oracle_ladder.py [--only V1|V2|V3]
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
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely import contains_xy

from dealer_territory.fence_from_text import lookup_geometry
from intelligence.coords import pack_from_disk

ROOT = Path(__file__).resolve().parent.parent
BAND_KM = 0.20
GRID_M = 150.0
LAT = 110.574


def lon_deg(km, lat):
    return km / (111.320 * math.cos(math.radians(lat)))


def load():
    d = ROOT / "data/gz"
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    reg = json.loads((d / "region.json").read_text(encoding="utf-8"))
    cons = json.loads((d / "contracts.json").read_text(encoding="utf-8"))
    pack_from_disk(reg, cons, meta)          # → WGS-84
    osm = json.loads((d / "osm_parsed.json").read_text(encoding="utf-8"))
    fences = {}
    for f in reg["fences"]:
        r = f["rings"]
        if isinstance(r, str):
            r = json.loads(r)
        p = Polygon([tuple(p) for p in r[0]])
        fences.setdefault(f["dealer"], []).append(p if p.is_valid else p.buffer(0))
    truth = {k: (unary_union(v) if len(v) > 1 else v[0]) for k, v in fences.items()}
    return osm, truth, cons


def all_osm_lines(osm):
    lines = []
    for cat in ("roads", "rivers"):
        for groups in osm.get(cat, {}).values():
            for pl in groups:
                if len(pl) >= 2:
                    lines.append(LineString(pl))
    return lines


def admin_lines(osm, name):
    """OSM admin fragments matching a clause mentioning that district."""
    out = []
    for dn, v in osm.get("districts", {}).items():
        core = dn.replace("区", "").replace("市", "")
        if core and (core in name or dn in name or name in dn):
            for pl in v.get("polys", []):
                if len(pl) >= 2:
                    out.append(LineString(pl))
    return out


def side_band(fp, center, side):
    """真值多边形被该侧半平面切出的部分（含其外部弧带 400m）。"""
    bb = fp.bounds
    W = (bb[2] - bb[0]) * 3
    H = (bb[3] - bb[1]) * 3
    cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    if side == "北":   hb = box(cx - W, cy, cx + W, cy + H)
    elif side == "南": hb = box(cx - W, cy - H, cx + W, cy)
    elif side == "东": hb = box(cx, cy - H, cx + W, cy + H)
    else:              hb = box(cx - W, cy - H, cx, cy + H)
    part = fp.intersection(hb)
    if part.is_empty:
        return None
    return part.exterior.buffer(400.0 / LAT) if part.geom_type == "Polygon" \
        else unary_union([q.exterior for q in part.geoms]).buffer(400.0 / LAT)


def barriers_for(dealer, fb, center, fp, osm, tree, idx, mode):
    bands = []
    for side, nm in fb.items():
        nm = (nm or "").strip()
        cand = []
        if mode in ("V1", "V1c") and nm:
            if any(t in nm for t in ("边缘", "区界", "市界", "界")):
                cand = admin_lines(osm, nm)
            if not cand:
                for s in lookup_geometry(nm, osm, center) or []:
                    if len(s) >= 2:
                        cand.append(LineString(s))
        elif mode in ("V2", "V3"):
            band = side_band(fp, center, side)
            if band is not None:
                q = tree.query(band)
                cand = [all_lines[int(i)] for i in list(q)[:400]]
        if not cand:
            continue
        bands.append(unary_union(cand).buffer(BAND_KM / LAT))
    return bands


def flood(barriers, win, center, nx, ny):
    xs = np.linspace(win.bounds[0], win.bounds[2], nx)
    ys = np.linspace(win.bounds[1], win.bounds[3], ny)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    blocked = np.zeros((nx, ny), dtype=bool)
    if barriers:
        B = unary_union(barriers)
        blocked = contains_xy(B, gx.ravel(), gy.ravel()).reshape(nx, ny)
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
        return None, xs, ys, False
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
    return comp, xs, ys, leak


all_lines = []
def run(mode):
    global all_lines
    osm, truth, cons = load()
    all_lines = all_osm_lines(osm)
    from shapely.strtree import STRtree
    tree = STRtree(all_lines); idx = None
    rows = []
    for c in cons:
        d = c["dealer_id"]
        fp = truth.get(d)
        center = tuple(c.get("center") or [])
        fb = c.get("four_bounds") or {}
        if fp is None or not center or len(fb) < 3:
            continue
        bb = fp.bounds
        pad = 3.0
        win = box(bb[0] - lon_deg(pad, center[1]), bb[1] - pad / LAT,
                  bb[2] + lon_deg(pad, center[1]), bb[3] + pad / LAT)
        diag = math.hypot(win.bounds[2] - win.bounds[0],
                          win.bounds[3] - win.bounds[1])
        cell = max(0.20 / LAT, diag / 300)
        nx = min(int((win.bounds[2] - win.bounds[0]) / cell) + 1, 300)
        ny = min(int((win.bounds[3] - win.bounds[1]) / cell) + 1, 300)
        barriers = barriers_for(d, fb, center, fp, osm, tree, idx, mode)
        comp, xs, ys, leak = flood(barriers, win, center, nx, ny)
        if comp is None:
            rows.append(dict(dealer=d, iou=None, leak=None, err="no-start"))
            continue
        gx, gy = np.meshgrid(xs, ys, indexing="ij")
        tmask = contains_xy(fp, gx.ravel(), gy.ravel()).reshape(nx, ny)
        if mode in ("V3", "V1c") and leak:
            a0, a1 = sorted((int(np.argmin(np.abs(xs - bb[0]))),
                             int(np.argmin(np.abs(xs - bb[2])))))
            b0, b1 = sorted((int(np.argmin(np.abs(ys - bb[1]))),
                             int(np.argmin(np.abs(ys - bb[3])))))
            mask = np.zeros_like(comp)
            mask[a0:a1 + 1, b0:b1 + 1] = True
            comp = comp & mask
        inter = int((comp & tmask).sum())
        union = int((comp | tmask).sum())
        rows.append(dict(dealer=d, iou=round(inter / union, 3) if union else 0.0,
                         leak=leak, nb=len(barriers)))
        Path("/tmp/ladder_partial.jsonl").open("a", encoding="utf-8").write(
            json.dumps(dict(mode=mode, **rows[-1])) + "\n")
    return rows


def report(tag, rows):
    ok = [r for r in rows if r["iou"] is not None]
    ious = sorted(r["iou"] for r in ok)
    if not ious:
        print(f"{tag}: 0 usable")
        return rows

    def q(p):
        return ious[int((len(ious) - 1) * p)]
    leaks = sum(1 for r in ok if r.get("leak"))
    print(f"{tag:16s} n={len(ok):2d}  IoU median {q(.5):.3f} "
          f"p25 {q(.25):.3f} p75 {q(.75):.3f}  "
          f"≥0.5:{sum(1 for x in ious if x >= .5):2d}  "
          f"≥0.7:{sum(1 for x in ious if x >= .7):2d}  "
          f"≥0.8:{sum(1 for x in ious if x >= .8):2d}  "
          f"leak {leaks:2d}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    modes = [a.only] if a.only else ["V1", "V1c", "V2", "V3"]
    out = {m: report(m, run(m)) for m in modes}
    Path("/tmp/oracle_ladder.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("→ /tmp/oracle_ladder.json")
