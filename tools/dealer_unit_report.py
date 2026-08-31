#!/usr/bin/env python3
"""逐经销商：真实单元构成 vs 紧描述（文献+贪心混合）。

三输出：
  desc_compact = 贪心选的紧描述（净增益，高J，台账重演用）
  desc_full    = 结构化事实完整描述（含占比，正确答案）
  compose      = 结构化事实（全部街道+占比）
"""
import json, sys
from collections import Counter
import _paths
sys.path.insert(0, str(_paths.ROOT))
import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree
DATA = _paths.DATA
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
    """结构化事实"""
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


def greedy_compact(orig, max_terms=10):
    """贪心紧描述"""
    covered = set()
    terms = []
    cand = [(stn, by_street.get(stn, set())) for stn, _, _, _ in
            sorted(human_compose(orig), key=lambda x: -x[1]/x[2])]
    while len(terms) < max_terms:
        best = None
        for label, s in cand:
            new = s - covered
            gain = len(new & orig) - len(new - orig)
            if gain < 1:
                continue
            sc = (len(new & orig), len(new & orig) / len(new) if new else 0)
            if best is None or sc > best[0]:
                best = (sc, label, s)
        if best is None:
            break
        covered |= best[2]
        terms.append(best[1])
        if orig <= covered:
            break
    return terms


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
        compact = greedy_compact(orig)
        proj = set()
        for stn in compact:
            proj |= by_street.get(stn, set())
        j = len(proj & orig) / len(proj | orig) if proj | orig else 0
        full = " + ".join(f"{stn}({tag})" for stn, n, tot, tag in compose)
        out.append({"area_id": f["area_id"], "dealer": f["dealer"],
                    "orig_units": len(orig),
                    "compose": compose,
                    "desc_compact": compact,
                    "desc_full": full,
                    "J": round(j, 2)})
    for r in sorted(out, key=lambda x: -(x["J"] or 0)):
        comp = "；".join(f"{s}({tag})" for s, n, tot, tag in r["compose"][:6])
        print(f"【{r['dealer'][:18]}】{r['orig_units']}单元 J={r['J']}")
        print(f"    真实构成: {comp}")
        print(f"    紧描述({len(r['desc_compact'])}项): {';'.join(r['desc_compact'][:8])}")
    import statistics as st
    js = [r["J"] for r in out if r["J"] is not None]
    print(f"\n=== 共{len(out)}家 诊断J 中位={st.median(js):.2f} "
          f"≥0.9={sum(1 for x in js if x>=0.9)} ≥0.8={sum(1 for x in js if x>=0.8)} ===")
    json.dump(out, open(f"{DATA}/dealer_unit_descriptions.json", "w"), ensure_ascii=False, indent=1)
    print("saved dealer_unit_descriptions.json")


if __name__ == "__main__":
    main()
