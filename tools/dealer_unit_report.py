#!/usr/bin/env python3
"""逐经销商：真实单元组合 vs 自然语言描述复现（纯几何，无门店）。

真实组合 = 质心落入该围栏的基础单元集合，按 (区,街道) 归并成人类可读构成。
描述 = 贪心集合覆盖生成的选择项（街道 / 街道沿路 / 方位半区）。
复现 = 按描述选单元，对真实组合算 P/R/J（单元数口径）。
"""
import json, sys, math
from collections import Counter
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree
from shapely.ops import unary_union
DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))   # 原帧(GCJ)，与官方单元同帧
OFF = json.load(open(f"{DATA}/basic_units_wgs.json", encoding="utf-8"))["units"]
attrs = [{"id": i, "street": u.get("street"), "district": u.get("district"),
          "roads": []} for i, u in enumerate(OFF)]
units = [shapely.from_wkt(u["geom"]) for u in OFF]
utree = STRtree(units)

by_street = {}
for a in attrs:
    if a["street"]:
        by_street.setdefault(a["street"], set()).add(a["id"])


def human_compose(orig, total_by_street=None):
    """真实单元组合 → 街道+占比构成（人类可读）。"""
    A = {x["id"]: x for x in attrs}
    cnt = Counter(A[u]["street"] for u in orig if u in A and A[u]["street"])
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
        else:
            tag = f"约{int(frac*100)}%"
        items.append((stn, n, tot, tag))
    unassigned = len(orig) - sum(n for _, n, _, _ in items)
    return items, unassigned


def main():
    out = []
    for f in reg["fences"]:
        if "佛山" in f["dealer"]:
            continue
        z = Polygon(f["rings"][0])
        if not z.is_valid:
            z = z.buffer(0)
        if z.geom_type == "MultiPolygon":
            z = max(z.geoms, key=lambda g: g.area)
        orig = {int(i) for i in utree.query(z) if units[int(i)].centroid.within(z)}
        if not orig:
            continue
        items, unassigned = human_compose(orig)
        # 描述（贪心，复用 desc_cover）
        dc = next((x for x in json.load(open(f"{DATA}/desc_cover_eval.json",
                                            encoding="utf-8"))
                   if x["area_id"] == f["area_id"]), None)
        terms = [t for t in (dc["desc"] if dc else []) if t]
        out.append({"area_id": f["area_id"], "dealer": f["dealer"],
                    "orig_units": len(orig), "unassigned": unassigned,
                    "compose": items, "terms": terms,
                    "J": dc["J"] if dc else None,
                    "nterms": len(terms)})
    # 打印
    for r in sorted(out, key=lambda x: -(x["J"] or 0)):
        comp = "；".join(f"{s}({tag})" for s, n, tot, tag in r["compose"][:6])
        print(f"【{r['dealer'][:18]}】{r['orig_units']}单元 复现J={r['J']}"
              f"{' 未落街道'+str(r['unassigned']) if r['unassigned'] else ''}")
        print(f"    真实构成: {comp}")
        print(f"    我的描述({r['nterms']}项): {';'.join(r['terms'][:8])}")
    import statistics as st
    js = [r["J"] for r in out if r["J"] is not None]
    print(f"\n=== 共{len(out)}家 复现J 中位={st.median(js):.2f} "
          f"≥0.9={sum(1 for x in js if x>=0.9)} ≥0.8={sum(1 for x in js if x>=0.8)} ===")
    json.dump(out, open(f"{DATA}/dealer_unit_descriptions.json", "w"),
              ensure_ascii=False, indent=1)
    print("saved dealer_unit_descriptions.json")


if __name__ == "__main__":
    main()
