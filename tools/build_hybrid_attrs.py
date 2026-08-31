#!/usr/bin/env python3
"""混合库属性索引：街道/区/贴边路名。无 adm6 依赖（区界不可信），
district 由官方单元的 street→district 映射推导。"""
import json, sys
import _paths
sys.path.insert(0, str(_paths.ROOT))
import shapely
from shapely.geometry import LineString
from shapely.strtree import STRtree
from shapely.ops import unary_union

DATA = _paths.DATA
d = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))

# 街道面（adm8，不裁剪）
streets = []
for r in d["adm8"]:
    try:
        g = shapely.from_wkt(r["wkt"])
    except Exception:
        continue
    parts = [g] if g.geom_type == "Polygon" else (
        list(g.geoms) if g.geom_type == "MultiPolygon" else [])
    for p in parts:
        if p.area > 1e-7:
            streets.append((r["name"], p))
# street→district 映射（官方单元属性 + fill 单元）
sd = {}
for u in json.load(open(f"{DATA}/basic_units_wgs.json"))["units"]:
    if u.get("street") and u.get("district"):
        sd.setdefault(u["street"], u["district"])
stree = STRtree([s[1] for s in streets])

named = []
for r in d["roads"]:
    if not r.get("name") or r["cls"] in (
            "footway", "steps", "path", "cycleway", "construction",
            "proposed"):
        continue
    try:
        g = shapely.from_wkt(r["wkt"])
    except Exception:
        continue
    parts = [g] if g.geom_type == "LineString" else (
        list(g.geoms) if g.geom_type == "MultiLineString" else [])
    for p in parts:
        if p.length > 1e-5:
            named.append((r["name"], p))
ntree = STRtree([p for _, p in named])

H = json.load(open(f"{DATA}/basic_units_hybrid.json", encoding="utf-8"))["units"]
out = []
for ui, u in enumerate(H):
    g = shapely.from_wkt(u["wkt"])
    c = g.centroid
    street = u.get("street")
    if street is None:
        for j in stree.query(c):
            nm, sp = streets[j]
            if sp.contains(c):
                street = nm
                break
    district = u.get("district") or sd.get(street)
    bros = set()
    for j in ntree.query(g.buffer(30 / 111000)):
        bros.add(named[j][0])
    out.append({"id": ui, "district": district, "street": street,
                "roads": sorted(bros)})
json.dump({"units": out}, open(f"{DATA}/unit_attributes.json", "w"),
          ensure_ascii=False)
nost = sum(1 for a in out if not a["street"])
nod = sum(1 for a in out if not a["district"])
print(f"混合库属性: {len(out)}单元 无街道{nost} 无区{nod}")
