#!/usr/bin/env python3
"""贪心描述生成：为每个围栏自动产出人类可读选择项（街道 / 街道沿路复合项），
使选中单元 ≈ 原始单元组合。纯集合运算，无几何切割、无中心点、无面积。

描述词汇（人真会说的）：
  "凤凰街道"          → 该街道全部单元
  "龙洞街道沿广汕二路" → 龙洞街道 ∩ 沿广汕二路的单元
  "人和镇沿XX路"       → 飞地小店靠路定位
评估：P=选中∩原始/选中，R=选中∩原始/原始，J=交/并。
"""
import json, sys, math
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree
from intelligence.coords import pack_from_disk

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"

meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
pack_from_disk(reg, [], meta)
_off = json.load(open(f"{DATA}/basic_units_wgs.json", encoding="utf-8"))["units"]
attrs = [{"id": i, "street": u.get("street"), "district": u.get("district"),
          "roads": []} for i, u in enumerate(_off)]
units = [shapely.from_wkt(u["geom"]) for u in _off]
utree = STRtree(units)

# 预计算集合
street_full = {}                       # (district, street) → set
street_road = {}                       # (district, street, road) → set
for a in attrs:
    sid = (a["district"], a["street"])
    street_full.setdefault(sid, set()).add(a["id"])
    for rd in a["roads"]:
        street_road.setdefault(sid + (rd,), set()).add(a["id"])


def gen_description(orig, max_terms=16, min_gain=1):
    """贪心：每轮选让 (新覆盖原始 − 误纳) 最大的项。"""
    covered = set()
    terms = []
    # 候选项
    cand = []
    streets_present = {k for k, v in street_full.items() if v & orig}
    for k in streets_present:
        cand.append((k[1], k, street_full[k]))
        road_union = set()
        for u in (street_full[k] & orig):
            road_union |= set(attrs[u]["roads"])
        for rd in road_union:
            s = street_road.get(k + (rd,))
            if s:
                cand.append((f"{k[1]}沿{rd}", k + (rd,), s))
    while len(terms) < max_terms:
        best = None
        for label, key, s in cand:
            new = s - covered
            gain = len(new & orig) - len(new - orig)
            if gain < min_gain:
                continue
            # 打分：净新增覆盖，平手时选精确率高的
            prec = (len(new & orig) / len(new)) if new else 0
            sc = (len(new & orig), prec)
            if best is None or sc > best[0]:
                best = (sc, label, s)
        if best is None:
            break
        covered |= best[2]
        terms.append((best[1], len(best[2])))
        cand = [(l, k, s) for (l, k, s) in cand if s != best[2]]
        if orig <= covered:
            break
    return terms, covered


def main():
    rows = []
    for f in reg["fences"]:
        if "佛山" in f["dealer"]:
            continue
        zg = Polygon(f["rings"][0])
        if not zg.is_valid:
            zg = zg.buffer(0)
        if zg.geom_type == "MultiPolygon":
            zg = max(zg.geoms, key=lambda g: g.area)
        orig = {int(i) for i in utree.query(zg) if units[int(i)].centroid.within(zg)}
        if not orig:
            continue
        terms, sel = gen_description(orig)
        j = len(sel & orig) / len(sel | orig) if sel | orig else 0
        p = len(sel & orig) / len(sel) if sel else 0
        r = len(sel & orig) / len(orig) if orig else 0
        rows.append({"dealer": f["dealer"], "area_id": f["area_id"],
                     "orig": len(orig),
                     "sel": len(sel), "P": round(p, 2), "R": round(r, 2),
                     "J": round(j, 2), "nterms": len(terms),
                     "desc": [t[0] for t in terms]})
    import statistics as st
    rows.sort(key=lambda x: -x["J"])
    for r in rows:
        print(f"J={r['J']:.2f} R={r['R']:.2f} P={r['P']:.2f} "
              f"{r['dealer'][:14]:<16} {r['orig']}→{r['sel']}单元 "
              f"{r['nterms']}项: {';'.join(r['desc'])}")
    print(f"\n中位 J={st.median(x['J'] for x in rows):.2f} "
          f"≥0.9: {sum(1 for x in rows if x['J']>=0.9)}/{len(rows)} "
          f"≥0.8: {sum(1 for x in rows if x['J']>=0.8)}/{len(rows)}")
    json.dump(rows, open(f"{DATA}/desc_cover_eval.json", "w"), ensure_ascii=False)
    print("saved desc_cover_eval.json")


if __name__ == "__main__":
    main()
