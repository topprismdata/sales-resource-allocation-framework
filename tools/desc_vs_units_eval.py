#!/usr/bin/env python3
"""描述↔原始单元组合 全量对比。

对每个真值围栏：
1. 原始组合 = 质心落入围栏的单元集合
2. 从原始组合反推描述（街道+占比；贴边路名）
3. 按描述重选单元集合
4. 单元重合度 P/R/J（按单元数）
"""
import json, sys, math
import _paths
sys.path.insert(0, str(_paths.ROOT))
import shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.strtree import STRtree
from shapely.ops import unary_union
from intelligence.coords import pack_from_disk

DATA = _paths.DATA

meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
pack_from_disk(reg, [], meta)
attrs = json.load(open(f"{DATA}/unit_attributes.json", encoding="utf-8"))["units"]
units = [shapely.from_wkt(u["wkt"]) for u in
         json.load(open(f"{DATA}/basic_units_v5_wgs.json", encoding="utf-8"))["units"]]
utree = STRtree(units)

# 索引：街道/路名 → 单元
by_street, by_road, by_district = {}, {}, {}
for a in attrs:
    if a["street"]:
        by_street.setdefault((a["district"], a["street"]), set()).add(a["id"])
        core = a["street"].replace("街道", "").replace("镇", "")
        by_street.setdefault(("*", core), set()).add(a["id"])
    for rd in a["roads"]:
        by_road.setdefault(rd, set()).add(a["id"])
    by_district.setdefault(a["district"], set()).add(a["id"])


def street_summary(unit_set):
    """按 (区,街道) 聚合并算覆盖率，反推描述。"""
    tot = {}
    for (k, us) in by_street.items():
        if k[0] == "*":
            continue
        ov = len(us & unit_set)
        if ov:
            tot[k] = (ov, len(us))
    terms = []
    for k, (ov, n) in sorted(tot.items(), key=lambda kv: -kv[1][0]):
        frac = ov / n
        if frac > 0.95:
            terms.append(("street_full", k))
        elif frac >= 0.15:
            terms.append(("street_part", k, frac))
    return terms


def rebuild_terms(unit_set, terms):
    sel = set()
    for t in terms:
        if t[0] == "street_full":
            sel |= by_street[(t[1][0], t[1][1])]
        else:
            us = by_street[(t[1][0], t[1][1])]
            # 部分覆盖：用围栏质心+方位近似（无真值）
            # 此处保守：取整个街道（模拟人只给街道名）
            sel |= us
    return sel


def eval_fences(sample=None):
    rows = []
    fences = [f for f in reg["fences"] if "佛山" not in f["dealer"]]
    for f in fences:
        zg = Polygon(f["rings"][0])
        if not zg.is_valid:
            zg = zg.buffer(0)
        if zg.geom_type == "MultiPolygon":
            zg = max(zg.geoms, key=lambda g: g.area)
        orig = set(int(i) for i in utree.query(zg)
                   if units[int(i)].centroid.within(zg))
        if not orig:
            continue
        terms = street_summary(orig)
        # 描述 A：全归并到街道（最粗）
        selA = rebuild_terms(orig, terms)
        pa = len(selA & orig) / len(selA) if selA else 0
        ra = len(selA & orig) / len(orig) if orig else 0
        ja = len(selA & orig) / len(selA | orig) if selA | orig else 0
        # 描述 B：街道全 + 部分街道取方向半区（更精）
        selB = set()
        for t in terms:
            us = by_street[(t[1][0], t[1][1])]
            if t[0] == "street_full":
                selB |= us
            else:
                frac = t[2]
                su = unary_union([units[u] for u in us])
                c = su.centroid
                ref = Point(list(zg.centroid.coords)[0])
                # 取该街道中朝向围栏质心一侧的单元，按数量截断到 frac
                cand = sorted(us, key=lambda u: units[u].centroid.distance(ref))
                selB |= set(cand[:max(1, int(round(frac * len(us))))])
        pb = len(selB & orig) / len(selB) if selB else 0
        rb = len(selB & orig) / len(orig) if orig else 0
        jb = len(selB & orig) / len(selB | orig) if selB | orig else 0
        rows.append({"dealer": f["dealer"], "area_id": f["area_id"],
                     "orig": len(orig),
                     "A": {"sel": len(selA), "P": round(pa, 2), "R": round(ra, 2), "J": round(ja, 2)},
                     "B": {"sel": len(selB), "P": round(pb, 2), "R": round(rb, 2), "J": round(jb, 2)},
                     "terms": len(terms)})
    return rows


if __name__ == "__main__":
    rows = eval_fences()
    print(f"{'经销商':<16} {'原始':>5} {'A街':>5} {'AP':>5} {'AR':>5} {'AJ':>5} {'B街':>5} {'BP':>5} {'BR':>5} {'BJ':>5}")
    for r in rows:
        print(f"{r['dealer'][:14]:<16} {r['orig']:>5} {r['A']['sel']:>5} "
              f"{r['A']['P']:>5} {r['A']['R']:>5} {r['A']['J']:>5} "
              f"{r['B']['sel']:>5} {r['B']['P']:>5} {r['B']['R']:>5} {r['B']['J']:>5}")
    import statistics as st
    print(f"\n中位 J：粗描述={st.median(r['A']['J'] for r in rows):.2f} "
          f"精描述={st.median(r['B']['J'] for r in rows):.2f}")
    json.dump(rows, open(f"{DATA}/desc_vs_units.json", "w"), ensure_ascii=False)
    print("saved desc_vs_units.json")
