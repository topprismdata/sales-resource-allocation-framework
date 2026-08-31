#!/usr/bin/env python3
"""区域构成描述（文献事实 + 贪心紧描述，含路级词）。

双输出：
  desc_compact = 贪心选的紧描述（街道 / 街道沿路，高J，台账重演用）
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
from intelligence.coords import pack_from_disk

DATA = _paths.DATA
meta = json.load(open(f"{DATA}/meta.json", encoding="utf-8"))
reg = json.load(open(f"{DATA}/region.json", encoding="utf-8"))
pack_from_disk(reg, [], meta)
OFF = json.load(open(f"{DATA}/basic_units_wgs.json", encoding="utf-8"))["units"]
ATTR = json.load(open(f"{DATA}/unit_attributes.json", encoding="utf-8"))["units"]
units = [shapely.from_wkt(u["geom"]) for u in OFF]
utree = STRtree(units)

by_street = {}
by_road = {}
for a in ATTR:
    if a["street"]:
        by_street.setdefault(a["street"], set()).add(a["id"])
    for rd in a["roads"]:
        by_road.setdefault(rd, set()).add(a["id"])


def human_compose(orig):
    """结构化事实：[(街道名, 单元数, 街道总数, 占比标签, 占比)]"""
    cnt = Counter(ATTR[u]["street"] for u in orig if ATTR[u]["street"])
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


def greedy_compact(orig, max_terms=12):
    """贪心紧描述（街道+路级词），净增益优先。"""
    covered = set()
    terms = []
    cand = []
    streets_present = {stn for stn, s in by_street.items() if s & orig}
    for stn in streets_present:
        cand.append((stn, by_street[stn]))
        # 沿路词：orig 单元所贴的路 ∩ 该街道
        road_union = set()
        for u in (by_street[stn] & orig):
            road_union |= set(ATTR[u]["roads"])
        for rd in road_union:
            s = by_street[stn] & by_road.get(rd, set())
            if s and s - covered:
                cand.append((f"{stn}沿{rd}", s))
    while len(terms) < max_terms:
        best = None
        for label, s in cand:
            new = s - covered
            hit = len(new & orig)
            if hit == 0:
                continue
            over = len(new - orig)
            gain = hit - over
            if gain < 1:
                continue
            sc = (gain, hit, hit / len(new) if new else 0)
            if best is None or sc > best[0]:
                best = (sc, label, s)
        if best is None:
            break
        covered |= best[2]
        terms.append(best[1])
        if orig <= covered:
            break
    return terms


def resolve(term):
    """描述项 → 单元集"""
    if "沿" in term:
        a, b = term.split("沿", 1)
        return by_street.get(a, set()) & by_road.get(b, set())
    return by_street.get(term, set())


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
        full_parts = [f"{stn}({tag})" for stn, n, tot, tag, _ in compose]
        compact = greedy_compact(orig)
        proj = set()
        for tm in compact:
            proj |= resolve(tm)
        j = len(proj & orig) / len(proj | orig) if proj | orig else 0
        p = len(proj & orig) / len(proj) if proj else 0
        r = len(proj & orig) / len(orig) if orig else 0
        rows.append({"dealer": f["dealer"], "area_id": f["area_id"],
                     "orig": len(orig), "sel": len(proj),
                     "P": round(p, 2), "R": round(r, 2), "J": round(j, 2),
                     "desc_compact": compact,
                     "desc_full": " + ".join(full_parts),
                     "compose": [[stn, n, tot, tag] for stn, n, tot, tag, _ in compose]})
    import statistics as st
    rows.sort(key=lambda x: -x["J"])
    for r in rows:
        print(f"J={r['J']:.2f} {r['dealer'][:14]:<16} {r['orig']}→{r['sel']}单元 "
              f"{len(r['desc_compact'])}项: {';'.join(r['desc_compact'][:5])}")
    print(f"\n中位 J={st.median(x['J'] for x in rows):.2f} "
          f"≥0.9: {sum(1 for x in rows if x['J']>=0.9)}/{len(rows)} "
          f"≥0.8: {sum(1 for x in rows if x['J']>=0.8)}/{len(rows)}")
    json.dump(rows, open(f"{DATA}/desc_cover_eval.json", "w"), ensure_ascii=False)
    print("saved desc_cover_eval.json")


if __name__ == "__main__":
    main()
