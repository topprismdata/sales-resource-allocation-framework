#!/usr/bin/env python3
"""经销商围栏 → 合同级语言描述（纯几何，零门店依赖）。

输入：广州办围栏 CSV + OSM 解析数据（L6 区界 / L8 街道镇界 / 主干道 / 河流）
输出：每围栏的「区县 + 街道构成（全域/部分）+ 四至」合同级描述。

街道构成判定（纯几何）：
  街道界采样点落入围栏内的比例
    >= 0.85 -> 全域
    >= 0.15 -> 部分（围栏边界穿过该街道）
    否则    -> 无关
"""

import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
import _paths

sys.path.insert(0, ".")
from dealer_territory.four_bounds import (  # noqa: E402
    LandmarkIndex, build_index, four_bounds, main_district,
)

csv.field_size_limit(10**7)

csv_path = sys.argv[1] if len(sys.argv) > 1 else _paths.ROOT.parent / "客户数据" / "广州办事处经销商围栏数据-20260827.csv"
osm_parsed_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/osm_parsed.json"
towns_path = sys.argv[3] if len(sys.argv) > 3 else "/tmp/gz_l8.json"
out_path = sys.argv[4] if len(sys.argv) > 4 else "analysis/FENCE_TOWNSHIP_DESCRIPTIONS.md"

# ---- 街道界（L8）----
l8 = json.load(open(towns_path, encoding="utf-8"))
towns = {}
for e in l8.get("elements", []):
    if e["type"] != "relation":
        continue
    nm = e["tags"].get("name", "")
    polys, cur = [], []
    for m in e.get("members", []):
        if m.get("type") == "way" and m.get("role") in ("outer", "") and "geometry" in m:
            g = [(p["lon"], p["lat"]) for p in m["geometry"] if p]
            if cur and cur[-1] == g[0]:
                cur += g[1:]
            else:
                if len(cur) > 3:
                    polys.append(cur)
                cur = g[:]
    if len(cur) > 3:
        polys.append(cur)
    if polys:
        towns[nm] = polys
print("街道/镇 polygons:", len(towns))

# ---- 围栏 ----
fences = []
with open(csv_path, encoding="utf-8-sig") as f:
    frows = list(csv.DictReader(f))
for r in frows:
    ring = [(float(a), float(b)) for a, b in
            re.findall(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", r["fence"])]
    bbox = (min(p[0] for p in ring), min(p[1] for p in ring),
            max(p[0] for p in ring), max(p[1] for p in ring))
    if any(112.8 <= p[0] <= 114.6 and 22.4 <= p[1] <= 24.0 for p in ring):
        fences.append({"dealer": r["围栏名称"], "ring": ring, "bbox": bbox,
                       "area": float(r["围栏面积"])})
print("fences:", len(fences))

# ---- OSM 地标索引 ----
osm = json.load(open(osm_parsed_path, encoding="utf-8"))
idx = build_index(osm)


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


def in_district(pt, polys):
    for poly in polys:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        if pip(pt, poly, (min(xs), min(ys), max(xs), max(ys))):
            return True
    return False


# ---- 街道采样点 + 街道→区县 ----
GZ_D = [k for k in osm["districts"] if k.endswith("区") and k != "广州市"
        and any(x in k for x in ["越秀", "海珠", "荔湾", "天河", "白云", "黄埔",
                                 "番禺", "南沙", "花都", "增城", "从化"])]

town_samples = {}
town_district = {}
for tn, polys in towns.items():
    pts = []
    for poly in polys:
        pts += poly[:: max(1, len(poly) // 40)]
    if not pts:
        continue
    town_samples[tn] = pts
    cnt = Counter()
    for p in pts:
        for dn in GZ_D:
            if in_district(p, osm["districts"][dn]["polys"]):
                cnt[dn] += 1
                break
    if cnt:
        town_district[tn] = cnt.most_common(1)[0][0]


def fence_towns(f):
    res = []
    for tn, pts in town_samples.items():
        n_in = sum(1 for p in pts if pip(p, f["ring"], f["bbox"]))
        ratio = n_in / len(pts) if pts else 0
        if ratio >= 0.15:
            full = ratio >= 0.85
            dn = town_district.get(tn, "未知")
            res.append((tn, ratio, full, dn))
    return sorted(res, key=lambda x: (x[3], -x[1]))


# ---- 生成描述 ----
lines = [
    "# 广州办经销商围栏 · 街道级合同语言描述（纯几何 · OSM L8）\n",
    "**口径**：围栏与街道/镇界（OSM admin_level=8）的空间关系，纯几何判定，不涉及门店。\n"
    "全域 = 街道界采样点 ≥85% 落入围栏；部分 = 15%~85%（围栏边界穿过该街道）。\n"
    "四至参照 = OSM 主干道/珠江航道/邻区界（dealer_territory.four_bounds）。\n",
]

gz_in, out_of_town = [], []
for f in sorted(fences, key=lambda x: -x["area"]):
    towns_res = fence_towns(f)
    gz_hits = sum(1 for _, _, fl, dn in towns_res if dn != "未知")
    if gz_hits == 0:
        out_of_town.append(f["dealer"])
        continue
    gz_in.append((f, towns_res))
for f, towns_res in gz_in:
    md = Counter(dn for _, _, fl, dn in towns_res if fl).most_common(1)
    main_d = md[0][0] if md else (main_district(f["ring"], idx) or "未知")
    full = [(t, dn) for t, r, fl, dn in towns_res if fl]
    part = [(t, dn, r) for t, r, fl, dn in towns_res if not fl]

    by_d = defaultdict(list)
    for t, dn in full:
        by_d[dn].append(t)
    full_txt = "；".join(f"{dn}: {'、'.join(ts)}" for dn, ts in sorted(by_d.items())) or "—"

    part_groups = defaultdict(list)
    for t, d2, r in part:
        part_groups[d2].append((t, r))
    part_txt = "；".join(
        f"{dn}: {'、'.join(f'{t}({r:.0%})' for t, r in sorted(g, key=lambda x: -x[1]))}"
        for dn, g in sorted(part_groups.items())) or "—"

    fb = four_bounds(f["ring"], idx, main_d)
    lines.append(
        f"### {f['dealer']}（{f['area']:.0f} km²）\n"
        f"- **主体区县**：{main_d}\n"
        f"- **含街道/镇（全域）**：{full_txt}\n"
        f"- **部分覆盖**：{part_txt}\n"
        f"- **四至**：西至{fb['西']}，北至{fb['北']}，东至{fb['东']}，南至{fb['南']}。\n"
    )

if out_of_town:
    lines.append(f"\n## 广州办代管的外埠围栏（{len(out_of_town)}，不生成描述）\n")
    for d in out_of_town:
        lines.append(f"- {d}")

with open(out_path, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print(f"written {out_path} ({len(fences) - len(out_of_town)} gz fences, {len(out_of_town)} out-of-town listed)")
