#!/usr/bin/env python3
"""往返验证演示：四至文字（+LLM 比例）→ 反向重建围栏 → 与原围栏对比。

用法：python3 tools/demo_fence_from_text.py
前置：/tmp/osm_parsed.json（OSM 解析）、广州办两份数据文件（默认路径）。
"""
import csv
import json
import math
import re
import sys
import zipfile

sys.path.insert(0, ".")
csv.field_size_limit(10**7)

from dealer_territory.fence_from_text import build_from_landmark_ratios  # noqa: E402

DL = "/Users/ghb/Downloads"
osm = json.load(open("/tmp/osm_parsed.json", encoding="utf-8"))


def parse_any(wkt):
    return [(float(a), float(b)) for a, b in
            re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", wkt)]


def pip(pt, ring, bbox):
    x, y = pt
    x0, y0, x1, y1 = bbox
    if not (x0 <= x <= x1 and y0 <= y <= y1):
        return False
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


fences = {}
with open(f"{DL}/广州办事处经销商围栏数据-20260827.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        ring = parse_any(r["fence"])
        bbox = (min(p[0] for p in ring), min(p[1] for p in ring),
                max(p[0] for p in ring), max(p[1] for p in ring))
        if any(112.8 <= p[0] <= 114.6 and 22.4 <= p[1] <= 24.0 for p in ring):
            fences[r["围栏名称"]] = (ring, bbox)

z = zipfile.ZipFile(f"{DL}/广州.xlsx")
sst = [re.sub(r"<[^>]+>", "", s) for s in
       re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode(), re.S)]
rows_xml = re.findall(r"<row[^>]*>(.*?)</row>", z.read("xl/worksheets/sheet1.xml").decode(), re.S)


def pr(x):
    out = {}
    for m in re.finditer(r'<c r="([A-Z]+)\d+"(?:[^>]*t="(\w+)")?[^>]*>(?:<v>([^<]*)</v>)?</c>', x):
        c, t, v = m.groups()
        out[c] = "" if v is None else (sst[int(v)] if t == "s" else v)
    return out


header = pr(rows_xml[0])
n2c = {v: k for k, v in header.items()}
stores = []
for rx in rows_xml[1:]:
    d = pr(rx)
    if d.get(n2c["城市名称"], "") != "广州市":
        continue
    try:
        stores.append((float(d.get(n2c["经度"])), float(d.get(n2c["纬度"]))))
    except ValueError:
        pass

# 三案例：四至文字（人工从围栏读出的描述）→ 合理比例（LLM/agentic 应给出的答案）
CASES = [
    ("示例经销商甲（供应链）",
     {"西": ("陈村水道", 0.15, 0.75), "北": ("后航道", 0.15, 0.75),
      "东": ("市桥水道", 0.10, 0.90), "南": ("顺德水道", 0.10, 0.90)}),
    ("示例经销商乙（贸易）",
     {"西": ("龙溪大道", 0.20, 0.80), "北": ("珠江西航道", 0.30, 0.80),
      "东": ("后航道", 0.20, 0.80), "南": ("花地大道", 0.20, 0.80)}),
    ("广州市财涛食品有限公司",
     {"西": ("珠江西航道", 0.40, 0.90), "北": ("广园快速路", 0.30, 0.90),
      "东": ("开发大道", 0.10, 0.60), "南": ("珠江", 0.20, 0.80)}),
]

for dealer, spec in CASES:
    orig_ring, ob = fences[dealer]
    cx = sum(p[0] for p in orig_ring) / len(orig_ring)
    cy = sum(p[1] for p in orig_ring) / len(orig_ring)
    r = build_from_landmark_ratios(dealer, spec, (cx, cy), osm)
    if "error" in r:
        print(f"{dealer[:14]}: {r['error']}")
        continue
    ring = r["ring"]
    rb = (min(p[0] for p in ring), min(p[1] for p in ring),
          max(p[0] for p in ring), max(p[1] for p in ring))
    in_o = in_r = both = 0
    for pt in stores:
        a = pip(pt, orig_ring, ob)
        b = pip(pt, ring, rb)
        in_o += a
        in_r += b
        both += a and b
    xs = [p[0] * 102.2 for p in orig_ring]
    ys = [p[1] * 110.574 for p in orig_ring]
    orig_area = round(abs(sum(xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
                              for i in range(len(orig_ring) - 1))) / 2, 1)
    print(f"{dealer[:14]}: 门店包含率 {both/max(1,in_o):.1%} "
          f"(原 {in_o} / 重建 {in_r}) | 面积 重建 {r['area_km2']} vs 原 {orig_area} km²")
