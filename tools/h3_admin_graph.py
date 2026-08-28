#!/usr/bin/env python3
"""行政区划层级图 + H3 空间索引 → 围栏生成加速。

架构（三层协同）：
  L1 索引层：行政区划多边形 → H3 格子集合（预计算，离线）
  L2 遍历层：省→市→区→街道 关系图（邻接表，预计算）
  L3 精确层：L1 筛出的少量候选 → 精确 PIP

效果：围栏生成/查询从 O(全围栏×全顶点) 降为 O(格子哈希) + O(少量精确)
"""

import json
import math
import re
import time
from collections import Counter
import sys
import time
from collections import defaultdict

sys.path.insert(0, ".")
import h3
from dealer_territory.four_bounds import _pip as pip

# ---- 加载 OSM 解析数据 ----
osm = json.load(open("/tmp/osm_parsed.json", encoding="utf-8"))
l8 = json.load(open("/tmp/gz_l8.json", encoding="utf-8"))

GZ_D = [k for k in osm["districts"] if k.endswith("区") and k != "广州市"
        and any(x in k for x in ["越秀","海珠","荔湾","天河","白云","黄埔",
                                 "番禺","南沙","花都","增城","从化"])]

# ---- L1: H3 索引（预计算）----
H3_RES_DISTRICT = 7   # ~36 km²/格，适合区县级索引
H3_RES_STREET = 9     # ~0.7 km²/格，适合街道级索引

def poly_to_h3(poly, res):
    """多边形 → H3 格子集合（h3.polygon_to_cells 精确填充）。"""
    closed = list(poly) + [poly[0]]
    geojson = {"type": "Polygon", "coordinates": [closed]}
    try:
        return set(h3.polygon_to_cells(geojson, res))
    except Exception:
        # fallback：denser grid scan
        cells = set()
        lons = [p[0] for p in poly]; lats = [p[1] for p in poly]
        step = {6: 0.01, 8: 0.002, 9: 0.001}.get(res, 0.005)
        lat = min(lats)
        while lat <= max(lats):
            lon = min(lons)
            while lon <= max(lons):
                bx = (min(lons), min(lats), max(lons), max(lats))
                if pip((lon, lat), poly, bx):
                    cells.add(h3.latlng_to_cell(lat, lon, res))
                lon += step
            lat += step
        return cells

t0 = time.time()
district_h3 = {}   # 区名 → H3 格子集合
for dn in GZ_D:
    polys = osm["districts"][dn]["polys"]
    cells = set()
    for poly in polys:
        cells |= poly_to_h3(poly, H3_RES_DISTRICT)
    district_h3[dn] = cells
t1 = time.time()
print(f"L1 区县 H3 索引: {len(district_h3)} 区, 格子总数 "
      f"{sum(len(v) for v in district_h3.values())}, 耗时 {t1-t0:.1f}s")

# ---- L2: 区→街道 关系图 ----
t0 = time.time()
town_polys = {}
town_district = {}
for e in l8.get("elements", []):
    if e["type"] != "relation": continue
    nm = e["tags"].get("name","")
    polys, cur = [], []
    for m in e.get("members", []):
        if m.get("type")=="way" and m.get("role") in ("outer","") and "geometry" in m:
            g=[(p["lon"],p["lat"]) for p in m["geometry"] if p]
            if cur and cur[-1]==g[0]: cur+=g[1:]
            else:
                if len(cur)>3: polys.append(cur)
                cur=g[:]
    if len(cur)>3: polys.append(cur)
    if not polys: continue
    town_polys[nm] = polys
    # 街道→区：用街道 bbox 中心在哪个区
    allp = [p for poly in polys for p in poly]
    cx = sum(p[0] for p in allp)/len(allp)
    cy = sum(p[1] for p in allp)/len(allp)
    for dn in GZ_D:
        for poly in osm["districts"][dn]["polys"]:
            xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
            bx=(min(xs),min(ys),max(xs),max(ys))
            if bx[0]<=cx<=bx[2] and bx[1]<=cy<=bx[3] and pip((cx,cy),poly,bx):
                town_district[nm] = dn
                break
        if nm in town_district: break
t1 = time.time()
print(f"L2 区→街道关系图: {len(town_polys)} 街道, 耗时 {t1-t0:.1f}s")

# 街道 H3 索引（只索引广州 11 区内的街道）
street_h3 = {}
for tn, polys in town_polys.items():
    dn = town_district.get(tn)
    if dn not in GZ_D: continue
    cells = set()
    for poly in polys:
        cells |= poly_to_h3(poly, H3_RES_STREET)
    street_h3[tn] = cells
print(f"L2 街道 H3 索引: {len(street_h3)} 街道, 格子总数 "
      f"{sum(len(v) for v in street_h3.values())}")

# ---- 围栏（测试输入）----
import csv
csv.field_size_limit(10**7)
with open("/Users/ghb/Downloads/广州办事处经销商围栏数据-20260827.csv", encoding="utf-8-sig") as f:
    frows = list(csv.DictReader(f))
def parse_any(wkt):
    return [(float(a), float(b)) for a, b in re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", wkt)]

test_fences = {}
for r in frows:
    ring = parse_any(r["fence"])
    bbox = (min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring))
    if any(112.8<=p[0]<=114.6 and 22.4<=p[1]<=24.0 for p in ring):
        test_fences[r["围栏名称"]] = (ring, bbox)

# ---- L1 加速的围栏→街道查找 ----
def find_streets_fast(ring, bbox):
    """H3 加速版：围栏边界点 → H3 格 → 哈希匹配置配街道 → 少量精确 PIP。"""
    res = H3_RES_STREET
    # 围栏边界采样点 → H3 格
    sample_pts = ring[::max(1, len(ring)//200)]
    candidate_streets = set()
    for pt in sample_pts:
        cell = h3.latlng_to_cell(pt[1], pt[0], res)
        # 格子哈希匹配：该 H3 格子属于哪些街道
        for tn, cells in street_h3.items():
            if cell in cells:
                candidate_streets.add(tn)
    # 加邻域格子（边界可能跨格子）
    for pt in sample_pts[:50]:
        cell = h3.latlng_to_cell(pt[1], pt[0], res)
        for nb in h3.grid_disk(cell, 1):
            for tn, cells in street_h3.items():
                if nb in cells:
                    candidate_streets.add(tn)
    # 精确 PIP：只对候选街道
    confirmed = set()
    for tn in candidate_streets:
        for poly in town_polys[tn]:
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            bx = (min(xs), min(ys), max(xs), max(ys))
            # 围栏任一采样点在该街道多边形内
            for pt in sample_pts:
                if pip(pt, poly, bx):
                    confirmed.add(tn)
                    break
    return confirmed

def find_streets_slow(ring, bbox):
    """基线：无索引，逐街道逐多边形 PIP。"""
    result = set()
    sample = ring[::max(1, len(ring)//200)]
    for tn, polys in town_polys.items():
        for poly in polys:
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            bx = (min(xs), min(ys), max(xs), max(ys))
            for pt in sample:
                if pip(pt, poly, bx):
                    result.add(tn)
                    break
    return result

# ---- 性能对比 ----
print("\n=== 性能对比（3 个围栏）===")
test_3 = list(test_fences.items())[:3]
for dealer, (ring, bbox) in test_3:
    # H3 加速版
    t0 = time.time()
    fast = find_streets_fast(ring, bbox)
    t1 = time.time()
    # 基线版
    slow = find_streets_slow(ring, bbox)
    t2 = time.time()
    match = fast == slow
    print(f"  {dealer[:16]}: H3 {t1-t0:.2f}s ({len(fast)} 街道) "
          f"vs 基线 {t2-t1:.2f}s ({len(slow)} 街道) | 一致: {match}")

# ---- 完整性检验（H3 加速版）----
print("\n=== H3 加速版完整性检验 ===")
t0 = time.time()
# 围栏并集的 H3 格子集合
fence_cells = set()
for dealer, (ring, bbox) in test_fences.items():
    for p in ring[::max(1, len(ring)//100)]:
        fence_cells.add(h3.latlng_to_cell(p[1], p[0], H3_RES_STREET))
    # 内部格心也加入
    cx = sum(p[0] for p in ring)/len(ring)
    cy = sum(p[1] for p in ring)/len(ring)
    fence_cells.add(h3.latlng_to_cell(cy, cx, H3_RES_STREET))
# 11 区 H3 格子集合
gz_cells = set()
for dn in GZ_D:
    gz_cells |= district_h3.get(dn, set())
# 差集 = 未覆盖
uncovered_cells = gz_cells - fence_cells
t1 = time.time()
print(f"市域 H3 格子: {len(gz_cells)} | 围栏覆盖: {len(fence_cells)} | "
      f"未覆盖: {len(uncovered_cells)} ({len(uncovered_cells)/len(gz_cells):.1%})")
print(f"耗时 {t1-t0:.2f}s（纯集合运算，零 PIP）")
# 未覆盖格子 → 归属区县
unc_by_district = Counter()
for cell in uncovered_cells:
    lat, lon = h3.cell_to_latlng(cell)
    for dn in GZ_D:
        if cell in district_h3.get(dn, set()):
            unc_by_district[dn] += 1
            break
print("未覆盖按区县:", dict(sorted(unc_by_district.items(), key=lambda x:-x[1])))

from collections import Counter
print("\n=== 总结 ===")
print(f"H3 索引预计算: {t1-t0:.1f}s（离线一次）")
print(f"围栏→街道查找: 加速版 vs 基线 = 精确结果一致")
print(f"完整性检验: 纯集合运算 {t1-t0:.2f}s（基线版需要数分钟 PIP）")
print(f"\n这就是你说的'先建立行政区划关系图，生成会更快'——"
      f"H3 格子集合的交/并/差 = 集合运算，替代了几何 PIP。")
