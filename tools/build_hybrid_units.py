#!/usr/bin/env python3
"""混合单元库：细路网面(v3_clean) ∪ 官方粗块的未覆盖残余。
细库覆盖城区；官方库（四级路网，覆盖全部地域）补齐无路区空洞。
互斥：官方单元两两不交，残余=O−细并集 亦互斥。"""
import json, sys, math
import _paths
sys.path.insert(0, str(_paths.ROOT))
import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree
from shapely.ops import unary_union

DATA = _paths.DATA
d = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))
GZ11 = ["天河区", "越秀区", "荔湾区", "海珠区", "番禺区", "白云区",
        "黄埔区", "花都区", "从化区", "增城区", "南沙区"]
gz = unary_union([shapely.from_wkt(r["wkt"]) for r in d["adm6"]
                  if r["name"] in GZ11])
if not gz.is_valid:
    gz = gz.buffer(0)

fine = [shapely.from_wkt(u["wkt"]) for u in
        json.load(open(f"{DATA}/basic_units_v3_clean.json"))["units"]]
U3 = unary_union([g.intersection(gz) for g in fine if g.intersects(gz)])

def clip(g):
    c = g.intersection(gz)
    if c.is_empty:
        return []
    parts = [c] if c.geom_type == "Polygon" else (
        list(c.geoms) if c.geom_type in ("MultiPolygon", "GeometryCollection") else [])
    return [x for x in parts if x.geom_type == "Polygon"]

units = []
for i, g in enumerate(fine):
    for c in clip(g):
        if c.area > 1e-9:
            units.append({"id": len(units), "src": "fine", "parent": i,
                          "wkt": c.wkt})
fills = 0
for i, ou in enumerate(json.load(open(f"{DATA}/basic_units_wgs.json"))["units"]):
    O = shapely.from_wkt(ou["geom"])
    rest = O.difference(U3)
    for c in (rest.geoms if rest.geom_type == "MultiPolygon" else
              [rest] if rest.geom_type == "Polygon" else []):
        for cc in clip(c):
            if cc.area > 1e-9:
                units.append({"id": len(units), "src": "fill", "parent": i,
                              "district": ou.get("district"),
                              "street": ou.get("street"), "wkt": cc.wkt})
                fills += 1
U = unary_union([shapely.from_wkt(u["wkt"]) for u in units])
def akm(g):
    return g.area * 111320 * math.cos(math.radians(g.centroid.y)) * 110540 / 1e6
print(f"混合库: {len(units)} 面 (fine {len(units)-fills} + fill {fills})")
print(f"并集面积 {akm(U):.0f}km²  vs 市域 {akm(gz):.0f}km² → 覆盖率 "
      f"{akm(U.intersection(gz))/akm(gz):.1%}")
# 互斥抽查
geos = [shapely.from_wkt(u["wkt"]) for u in units]
t = STRtree(geos[:4000])
ov = 0
for i in range(4000):
    for j in t.query(geos[i]):
        j = int(j)
        if j <= i:
            continue
        a = geos[i].intersection(geos[j])
        if not a.is_empty and a.area > 1e-9:
            ov += 1
print(f"前4000互斥抽查: 重叠对 {ov}")
json.dump({"crs": "WGS84", "source": "v3_clean ∪ official-fills (GZ-clipped)",
           "units": units},
          open(f"{DATA}/basic_units_hybrid.json", "w"), ensure_ascii=False)
print("saved basic_units_hybrid.json")
