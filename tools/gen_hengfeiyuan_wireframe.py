#!/usr/bin/env python3
"""生成亨啡源北围栏线框图SVG——每个基础单元多边形轮廓，沿边标路名"""
import sys
import _paths
sys.path.insert(0, str(_paths.ROOT))
import json
from shapely.geometry import Polygon, MultiPolygon
from shapely.strtree import STRtree
from shapely import wkt, ops
from collections import defaultdict
from intelligence.coords import pack_from_disk

DATA = _paths.DATA
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

# 计算所有单元的外包框
all_pts = []
for u in orig:
    g = units[u]
    if g.geom_type == "Polygon":
        for x, y in g.exterior.coords: all_pts.append((x, y))
    elif g.geom_type == "MultiPolygon":
        for p in g.geoms:
            for x, y in p.exterior.coords: all_pts.append((x, y))
minx = min(p[0] for p in all_pts); maxx = max(p[0] for p in all_pts)
miny = min(p[1] for p in all_pts); maxy = max(p[1] for p in all_pts)
pad = 0.015; W, H = 1200, 800
def tx(x): return (x - minx + pad) / (maxx - minx + 2*pad) * W
def ty(y): return H - (y - miny + pad) / (maxy - miny + 2*pad) * H

street_colors = {"凤凰街道":"#e74c3c","龙洞街道":"#3498db","新塘街道":"#2ecc71","联和街道":"#f39c12"}
street_styles = {"凤凰街道":"stroke:#e74c3c;stroke-width:2;fill:#e74c3c;fill-opacity:0.08",
                 "龙洞街道":"stroke:#3498db;stroke-width:2;fill:#3498db;fill-opacity:0.08",
                 "新塘街道":"stroke:#2ecc71;stroke-width:2;fill:#2ecc71;fill-opacity:0.08",
                 "联和街道":"stroke:#f39c12;stroke-width:2;fill:#f39c12;fill-opacity:0.08"}

L = []
L.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W+300} {H+40}" style="font-family:sans-serif;font-size:10px;background:#f8f9fa">')
L.append(f'<rect width="{W+300}" height="{H+40}" fill="#f8f9fa"/>')

# 图例
lx, ly = W+15, 20
L.append(f'<text x="{lx}" y="{ly}" font-weight="bold" font-size="14">广州亨啡源商贸有限公司(北)</text>')
ly += 22
L.append(f'<text x="{lx}" y="{ly}" font-size="11" fill="#666">{len(orig)}个基础单元 面积{f["area_km2"]}km²</text>')
ly += 5
for st, col in street_colors.items():
    ly += 20
    cnt = sum(1 for u in orig if ATTR[u].get("street") == st)
    d = next((ATTR[u].get("district","?") for u in orig if ATTR[u].get("street") == st), "?")
    all_roads = sorted(set(rd for u in orig if ATTR[u].get("street")==st for rd in ATTR[u].get("roads",[])))
    L.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="{col}"/>')
    L.append(f'<text x="{lx+20}" y="{ly}" dy="12" font-weight="bold">{st}({d},{cnt}单元)</text>')
    ly += 14
    L.append(f'<text x="{lx+20}" y="{ly}" font-size="8" fill="#666">贴路: {",".join(all_roads[:6])}</text>')
ly += 26
L.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="none" stroke="#333" stroke-width="2" stroke-dasharray="5,4"/>')
L.append(f'<text x="{lx+20}" y="{ly}" dy="12">围栏边界</text>')

# 画每个单元的多边形
for u in orig:
    g = units[u]
    st = ATTR[u].get("street","?")
    style = street_styles.get(st, "stroke:#666;stroke-width:1.5;fill:none")
    rds = ATTR[u].get("roads",[])
    polygons = [g] if g.geom_type == "Polygon" else (list(g.geoms) if g.geom_type == "MultiPolygon" else [])
    for poly in polygons:
        pts_str = " ".join(f"{tx(x)},{ty(y)}" for x, y in poly.exterior.coords)
        L.append(f'<polygon points="{pts_str}" style="{style}"/>')
        # 在单元中心标ID和道路
        cx, cy = tx(poly.centroid.x), ty(poly.centroid.y)
        L.append(f'<text x="{cx:.0f}" y="{cy-3:.0f}" text-anchor="middle" font-size="8" font-weight="bold" fill="#333">#{u}</text>')
        if rds:
            L.append(f'<text x="{cx:.0f}" y="{cy+8:.0f}" text-anchor="middle" font-size="6" fill="#555">{rds[0][:12]}</text>')

# 围栏虚线框
fence_pts = " ".join(f"{tx(x)},{ty(y)}" for x, y in zg.exterior.coords)
L.append(f'<polygon points="{fence_pts}" style="fill:none;stroke:#333;stroke-width:2;stroke-dasharray:6,4"/>')

L.append('</svg>')
with open(_paths.data_dir() / "hengfeiyuan_north_wireframe.svg", "w") as f:
    f.write("\n".join(L))
print("saved hengfeiyuan_north_wireframe.svg")
print("28个单元的多边形轮廓，按街道着色，每个单元内标ID+贴路名")
