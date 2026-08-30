#!/usr/bin/env python3
"""生成亨啡源北围栏示意图SVG"""
import sys; sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import json
from shapely.geometry import Polygon
from shapely.strtree import STRtree
from shapely import wkt
from collections import defaultdict
from intelligence.coords import pack_from_disk

DATA = "data/gz"
ATTR = json.load(open(f"{DATA}/unit_attributes.json"))["units"]
OFF = json.load(open(f"{DATA}/basic_units_wgs.json"))["units"]
units = [wkt.loads(u["geom"]) for u in OFF]; ut = STRtree(units)
meta = json.load(open(f"{DATA}/meta.json"))
reg = json.load(open(f"{DATA}/region.json"))
pack_from_disk(reg, [], meta)
f = [x for x in reg["fences"] if x["area_id"] == "694420772"][0]
zg = Polygon(f["rings"][0])
if not zg.is_valid: zg = zg.buffer(0)
if zg.geom_type == "MultiPolygon": zg = max(zg.geoms, key=lambda g: g.area)
orig = {int(i) for i in ut.query(zg) if units[int(i)].centroid.within(zg)}

pts = [(units[u].centroid.x, units[u].centroid.y) for u in orig]
minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)
pad = 0.025; W, H = 1000, 700
def tx(x): return (x - minx + pad) / (maxx - minx + 2*pad) * W
def ty(y): return H - (y - miny + pad) / (maxy - miny + 2*pad) * H

street_colors = {"凤凰街道":"#e74c3c","龙洞街道":"#3498db","新塘街道":"#2ecc71","联和街道":"#f39c12"}
streets = defaultdict(list)
for u in orig:
    c = units[u].centroid
    streets[ATTR[u].get("street","?")].append((u, c.x, c.y, ATTR[u].get("district","?"), ATTR[u].get("roads",[])))

L = []
L.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W+280} {H+40}" style="font-family:sans-serif;font-size:11px;background:#f8f9fa">')
L.append(f'<rect width="{W+280}" height="{H+40}" fill="#f8f9fa"/>')
lx, ly = W+15, 20
L.append(f'<text x="{lx}" y="{ly}" font-weight="bold" font-size="14">广州亨啡源商贸有限公司(北)</text>')
ly += 24
L.append(f'<text x="{lx}" y="{ly}" font-size="11" fill="#666">{len(orig)}个基础单元 面积{f["area_km2"]}km² 天河区+黄埔区</text>')
ly += 5
for st, col in street_colors.items():
    ly += 20
    cnt = sum(1 for u in orig if ATTR[u].get("street") == st)
    d = next((ATTR[u].get("district","?") for u in orig if ATTR[u].get("street") == st), "?")
    L.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="{col}"/>')
    L.append(f'<text x="{lx+20}" y="{ly}" dy="12">{st}({d},{cnt}单元)</text>')
ly += 26
L.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="none" stroke="#333" stroke-width="1.5" stroke-dasharray="4,3"/>')
L.append(f'<text x="{lx+20}" y="{ly}" dy="12">围栏边界</text>')
for st, ul in streets.items():
    col = street_colors.get(st, "#666")
    for u, x, y, dist, rds in ul:
        cx, cy = tx(x), ty(y)
        L.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{col}" stroke="#fff" stroke-width="1.5"/>')
        L.append(f'<text x="{cx:.1f}" y="{cy:.1f}" dy="-9" text-anchor="middle" font-size="8" fill="#333">#{u}</text>')
        for i, rd in enumerate(rds[:2]):
            L.append(f'<text x="{cx+8:.1f}" y="{cy+10+i*9:.1f}" font-size="7" fill="#555">{rd[:14]}</text>')
fx = [tx(p[0]) for p in pts]; fy = [ty(p[1]) for p in pts]
L.append(f'<rect x="{min(fx)-10:.0f}" y="{min(fy)-10:.0f}" width="{max(fx)-min(fx)+20:.0f}" height="{max(fy)-min(fy)+20:.0f}" fill="none" stroke="#333" stroke-width="1.5" stroke-dasharray="5,4"/>')
L.append('</svg>')
with open("/Users/ghb/sales-resource-allocation-framework/data/gz/hengfeiyuan_north.svg","w") as f:
    f.write("\n".join(L))
print("saved hengfeiyuan_north.svg")