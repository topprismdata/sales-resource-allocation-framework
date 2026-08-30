#!/usr/bin/env python3
"""区域构成描述生成（文献接地版）。

管线：围栏多边形 → 质心入选 → 按街道归并 → 结构化事实 → 紧描述推演 → J诊断。

J 是诊断指标：紧描述（街道名）能否复现单元集。对整街型 J≈1.0，飞地型 J≈0.0。
完整描述（含占比）才是正确答案。
"""
import json, sys, math
from collections import Counter
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree
from intelligence.coords import pack_from_disk

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
pack_from_disk(reg, [], meta)
OFF = json.load(open(f"{DATA}/basic_units_wgs.json", encoding="utf-8"))["units"]
attrs = [{"id": i, "street": u.get("street"), "district": u.get("district")}
         for i, u in enumerate(OFF)]
units = [shapely.from_wkt(u["geom"]) for u in OFF]
utree = STRtree(units)

# 预计算：街道 → 全部单元集
by_street = {}
for a in attrs:
    if a["street"]:
        by_street.setdefault(a["street"], set()).add(a["id"])


def human_compose(orig):
    """真实单元组合 → 结构化事实：[(街道名, 单元数, 街道总数, 占比标签)]"""
    cnt = Counter(attrs[u]["street"] for u in orig if attrs[u]["street"])
    items = []
    for stn, n in cnt.most_common():
        tot = len(by_street.get(stn, set()))
        frac = n / tot if tot else 1
        if frac > 0.95:
            tag = "全部"
        elif frac >= 0.6:
            tag = "大部"
        elif frac >= 0.3:
            tag = "约半"
        elif frac == 0.0:
            tag = "0%"
        else:
            tag = f"约{int(frac*100)}%"
        items.append((stn, n, tot, tag, frac))
    return items


def make_description(compose, orig):
    """从结构化事实推演紧描述和完整描述。"""
    # 紧描述 = 街道名（按占比降序, 去重），用于台账重演
    seen = set()
    compact = []
    for stn, n, tot, tag, frac in compose:
        if stn not in seen:
            compact.append(stn)
            seen.add(stn)
    # 完整描述 = 街道名+占比（人类可读）
    full_parts = [f"{stn}({tag})" for stn, n, tot, tag, frac in compose]
    full = " + ".join(full_parts)
    # 紧描述投影到单元集
    proj = set()
    for stn in compact:
        proj |= by_street.get(stn, set())
    return compact, full, proj


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
        compose = human_compose(orig)
        compact, full, proj = make_description(compose, orig)
        j = len(proj & orig) / len(proj | orig) if proj | orig else 0
        p = len(proj & orig) / len(proj) if proj else 0
        r = len(proj & orig) / len(orig) if orig else 0
        rows.append({"dealer": f["dealer"], "area_id": f["area_id"],
                     "orig": len(orig), "sel": len(proj),
                     "P": round(p, 2), "R": round(r, 2),
                     "J": round(j, 2),
                     "desc_compact": compact,
                     "desc_full": full,
                     "compose": [[stn, n, tot, tag] for stn, n, tot, tag, _ in compose]})
    import statistics as st
    rows.sort(key=lambda x: -x["J"])
    for r in rows:
        info = f"J={r['J']:.2f} P={r['P']:.2f} R={r['R']:.2f}  {r['dealer'][:14]:<16} {r['orig']}→{r['sel']}单元"
        print(f"{info}  {r['desc_full'][:60]}")
    print(f"\n中位 J={st.median(x['J'] for x in rows):.2f} "
          f"≥0.9: {sum(1 for x in rows if x['J']>=0.9)}/{len(rows)} "
          f"≥0.8: {sum(1 for x in rows if x['J']>=0.8)}/{len(rows)}")
    json.dump(rows, open(f"{DATA}/desc_cover_eval.json", "w"), ensure_ascii=False)
    print("saved desc_cover_eval.json")


if __name__ == "__main__":
    main()