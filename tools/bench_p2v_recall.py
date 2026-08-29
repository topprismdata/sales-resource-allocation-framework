#!/usr/bin/env python3
"""P2-V: Candidate Boundary Choice Oracle — 候选线网对真值边界的召回率。

对每个真值围栏边界，量测 100m/300m 内存在候选线（区界/街道界/路/河）的比例。
判据（GPT 评审 2026-08-29）：
  Recall@100 > 0.9 → 问题=候选线排序+路径选择（map matching）
  Recall@300 < 0.6 → 需要更强的隐式边界机制（face assignment / fuzzy field）
"""
import json, sys, math
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
from intelligence.coords import pack_from_disk
from shapely.geometry import LineString, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
cons = []
pack_from_disk(reg, cons, meta)
osm = json.load(open(f"{DATA}/osm_parsed.json", encoding="utf-8"))
sub = json.load(open(f"{DATA}/osm_subdistricts.json", encoding="utf-8"))["subdistricts"]
extra = json.load(open(f"{DATA}/roads_extra.json", encoding="utf-8"))

# ---- 候选线网（WGS84），全部切成 ~250m 段 ----
def add_lines(store, lines):
    for line in lines:
        if not isinstance(line, list) or len(line) < 2:
            continue
        if not isinstance(line[0], (list, tuple)):
            continue
        try:
            ls = LineString(line)
        except Exception:
            continue
        if ls.is_empty or ls.length < 1e-6:
            continue
        n = max(1, int(ls.length / 0.0025))  # ~250m
        for i in range(n):
            store.append(ls.interpolate(i / n).coords[0] and
                         LineString([ls.interpolate(i / n),
                                     ls.interpolate(min(1.0, (i + 1) / n))]))

segs = []
add_lines(segs, [p for v in osm.get("districts", {}).values() for p in v.get("polys", [])])
add_lines(segs, [p for v in sub.values() for p in v])
for src in (osm.get("roads") or {}, osm.get("rivers") or {}, extra):
    if isinstance(src, dict):
        for v in src.values():
            add_lines(segs, v)
    elif isinstance(src, list):
        add_lines(segs, src)
print(f"候选段: {len(segs)}", file=sys.stderr)
tree = STRtree(segs)

def recall(ring, radius):
    ls = LineString(ring + [ring[0]])
    n = max(1, int(ls.length / 0.0005))  # 采样 ~55m
    hit_len = 0.0
    seg_len = ls.length / n
    for i in range(n):
        pt = ls.interpolate((i + 0.5) / n)
        near = tree.query(pt.buffer(radius))
        if len(near):
            hit_len += seg_len
    return hit_len / ls.length

rows = []
for f in reg["fences"]:
    r100 = recall(f["rings"][0], 100 / 111000)
    r300 = recall(f["rings"][0], 300 / 111000)
    rows.append({"dealer": f["dealer"], "area_id": f["area_id"],
                 "r100": round(r100, 3), "r300": round(r300, 3)})
rows.sort(key=lambda r: r["r100"])
med100 = sorted(r["r100"] for r in rows)[len(rows) // 2]
med300 = sorted(r["r300"] for r in rows)[len(rows) // 2]
print(json.dumps({"median_r100": med100, "median_r300": med300,
                  "n": len(rows), "rows": rows}, ensure_ascii=False, indent=1))
json.dump({"median_r100": med100, "median_r300": med300, "rows": rows},
          open(f"{DATA}/p2v_recall.json", "w"), ensure_ascii=False)
