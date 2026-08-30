#!/usr/bin/env python3
"""逐经销商：真实单元构成 vs 紧描述推演（文献接地版）。

真实构成 = 质心落入围栏的基础单元，按街道归并 + 占比标签。
紧描述 = 从构成推演的街道名（去重，按占比降序）。
J 诊断 = 紧描述投影能否复现单元集（整街高，飞地低）。
"""
import json, sys
from collections import Counter, OrderedDict
sys.path.insert(0, "/Users/ghb/sales-resource-allocation-framework")
import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree
DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
OFF = json.load(open(f"{DATA}/basic_units_wgs.json", encoding="utf-8"))["units"]
attrs = [{"id": i, "street": u.get("street"), "district": u.get("district")}
         for i, u in enumerate(OFF)]
units = [shapely.from_wkt(u["geom"]) for u in OFF]
utree = STRtree(units)

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
        items.append((stn, n, tot, tag))
    return items


def compact_desc(compose):
    """紧描述 = 街道名（去重，按占比降序）"""
    seen = set()
    return [stn for stn, _, _, _ in compose if not (stn in seen or seen.add(stn))]


def full_desc(compose):
    """完整描述 = 街道名+占比"""
    return " + ".join(f"{stn}({tag})" for stn, _, _, tag in compose)


def project(terms):
    """紧描述投影到单元集"""
    proj = set()
    for stn in terms:
        proj |= by_street.get(stn, set())
    return proj


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
        compose = human_compose(orig)
        terms = compact_desc(compose)
        proj = project(terms)
        j = len(proj & orig) / len(proj | orig) if proj | orig else 0
        out.append({"area_id": f["area_id"], "dealer": f["dealer"],
                    "orig_units": len(orig),
                    "compose": compose,
                    "desc_compact": terms,
                    "desc_full": full_desc(compose),
                    "J": round(j, 2)})
    # 打印
    for r in sorted(out, key=lambda x: -(x["J"] or 0)):
        comp = "；".join(f"{s}({tag})" for s, n, tot, tag in r["compose"][:6])
        print(f"【{r['dealer'][:18]}】{r['orig_units']}单元 J={r['J']}")
        print(f"    真实构成: {comp}")
        print(f"    紧描述: {';'.join(r['desc_compact'][:8])}")
        print(f"    完整描述: {r['desc_full']}")
    import statistics as st
    js = [r["J"] for r in out if r["J"] is not None]
    print(f"\n=== 共{len(out)}家 诊断J 中位={st.median(js):.2f} "
          f"≥0.9={sum(1 for x in js if x>=0.9)} ≥0.8={sum(1 for x in js if x>=0.8)} ===")
    json.dump(out, open(f"{DATA}/dealer_unit_descriptions.json", "w"),
              ensure_ascii=False, indent=1)
    print("saved dealer_unit_descriptions.json")


if __name__ == "__main__":
    main()