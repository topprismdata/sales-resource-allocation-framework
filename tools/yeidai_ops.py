#!/usr/bin/env python3
"""业代围栏自然语言操作（@引用）：合并/拆分/划拨。纯几何，无门店。"""
import json, re, math, statistics
import shapely
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"


class YeidaiState:
    """业代围栏工作副本（WGS84）。"""

    def __init__(self):
        d = json.load(open(f"{DATA}/haizhu_liwan_zones_original.json", encoding="utf-8"))
        self.zones = [{"id": z["id"], "name": z["name"],
                       "geom": str_shapely(z["ring"])}
                      for z in d["zones"]]

    def snapshot(self):
        return [{"id": z["id"], "name": z["name"],
                 "ring": [[round(x, 6), round(y, 6)] for x, y in z["geom"].exterior.coords],
                 "area": round(z["geom"].area * 11320 * 0.995, 1)}
                for z in self.zones]


def str_shapely(ring):
    import shapely
    p = Polygon(ring)
    return p if p.is_valid else p.buffer(0)


def resolve_zones(text, zones):
    """@短名 → 完整围栏名（子串唯一匹配，多个@可重复指向同一片）。"""
    refs = re.findall(r"@([^\s@，。；、,;]+)", text)
    out = []
    for ref in refs:
        hits = [z for z in zones if ref in z["name"]]
        if len(hits) != 1:
            raise ValueError(f"@{ref} 匹配到 {len(hits)} 个围栏，请用更长的名字")
        out.append(hits[0])
    return out


def parse_op(text, zones):
    """规则解析 → 结构化操作。"""
    refs = resolve_zones(text, zones)
    t = text
    if re.search(r"合并|融合|并成一个", t):
        if len(refs) < 2:
            raise ValueError("合并需要至少两个 @围栏")
        return {"op": "merge", "zones": refs}
    m = re.search(r"(@\S+)\s*(?:的)?(北|南|东|西)(?:部|边|侧)?(?:区域)?\s*(?:划给|给|归|并入)\s*(@\S+)", t)
    if m:
        return {"op": "transfer_direction", "src_zone": refs[0],
                "direction": m.group(2), "dst_zone": refs[-1]}
    m = re.search(r"拆分|切开|分成两|一分为二", t)
    if m and refs:
        mc = re.search(r"沿\s*([^\s@，。；,;]+)", t)
        return {"op": "split", "zone": refs[0],
                "cut": mc.group(1) if mc else None}
    m = re.search(r"(@\S+)\s*(?:取消|删除|撤销)", t)
    if m:
        return {"op": "delete", "zone": refs[0]}
    raise ValueError("无法识别的指令：支持 合并/@A @B、拆分 @A 沿 XX、@A 的北部划给 @B、取消 @A")


def apply_op(state, op):
    zones = state.zones
    if op["op"] == "merge":
        names = [z["name"] for z in op["zones"]]
        geom = unary_union([z["geom"] for z in op["zones"]])
        keep = op["zones"][0]
        keep["geom"] = geom
        state.zones = [z for z in zones if z not in op["zones"][1:]]
        return f"已合并 {names} → {keep['name']}（{geom.area*11320:.1f}km²）"

    if op["op"] == "delete":
        z = op["zone"]
        state.zones = [x for x in zones if x is not z]
        return f"已取消 {z['name']}"

    if op["op"] == "split":
        z = op["zone"]
        cutname = op.get("cut")
        cutline = None
        if cutname:
            d = json.load(open(f"{DATA}/gz_osm_full.json", encoding="utf-8"))
            cands = []
            for grp in ("roads", "rivers"):
                for r in d[grp]:
                    if cutname and cutname in r.get("name", ""):
                        try:
                            g = shapely.from_wkt(r["wkt"])
                        except Exception:
                            continue
                        parts = ([g] if g.geom_type == "LineString"
                                 else list(g.geoms) if g.geom_type == "MultiLineString" else [])
                        cands += parts
            if cands:
                cutline = unary_union(cands).intersection(
                    z["geom"].buffer(0.0005)).buffer(0.00015)
        if cutline is None or cutline.is_empty:
            # 无线名：过质心的水平线
            c = z["geom"].centroid
            cutline = LineString([(c.x - 1, c.y), (c.x + 1, c.y)]).buffer(0.00015)
        from shapely.ops import split as shp_split
        cut_opts = [cutline]
        if cutline.geom_type == "MultiLineString":
            cut_opts += list(cutline.geoms)
        pieces = []
        for cut_one in cut_opts:
          for bw in (0.0, 0.0004, 0.0012):
            cutuse = cut_one.buffer(bw) if bw > 0 else cut_one
            if bw == 0:
                if cutuse.geom_type not in ("LineString", "MultiLineString"):
                    continue
                try:
                    res = shp_split(z["geom"], cutuse)
                except Exception:
                    continue
                polys = [g for g in (res.geoms if hasattr(res, "geoms") else [res])
                         if g.geom_type == "Polygon"]
            else:
                diff = z["geom"].difference(cutuse)
                polys = list(diff.geoms) if diff.geom_type == "MultiPolygon" else (
                    [diff] if diff.geom_type == "Polygon" and not diff.is_empty else [])
            if len(polys) >= 2:
                pieces = [g for g in polys if g.area > 1e-7]
                if len(pieces) >= 2:
                    break
        if len(pieces) < 2:
            raise ValueError("切分失败：切割要素未把围栏一分为二")
        pieces.sort(key=lambda p: -p.area)
        z["geom"] = pieces[0]
        newzone = {"id": z["id"] + "-b", "name": z["name"] + "-B", "geom": pieces[1]}
        zones.insert(zones.index(z) + 1, newzone)
        return (f"已拆分 {z['name']} → {z['name']}"
                f"（{pieces[0].area*11320:.1f}km²）+ {newzone['name']}"
                f"（{pieces[1].area*11320:.1f}km²）"
                + (f"，切割线：{cutname}" if cutname else "，默认水平切"))

    if op["op"] == "transfer_direction":
        src, dst, dr = op["src_zone"], op["dst_zone"], op["direction"]
        if src is dst:
            raise ValueError("源和目标相同")
        dv = {"北": (0, 1), "南": (0, -1), "东": (1, 0), "西": (-1, 0)}[dr]
        c = src["geom"].centroid
        half = box(c.x - 1 + (0 if dv[0] >= 0 else 0), c.y, c.x + 1, c.y + 1) \
            if dr == "北" else None
        if dr == "北":
            half = box(c.x - 1, c.y, c.x + 1, c.y + 1)
        elif dr == "南":
            half = box(c.x - 1, c.y - 1, c.x + 1, c.y)
        elif dr == "东":
            half = box(c.x, c.y - 1, c.x + 1, c.y + 1)
        else:
            half = box(c.x - 1, c.y - 1, c.x, c.y + 1)
        piece = src["geom"].intersection(half)
        if piece.is_empty or piece.area < 1e-7:
            raise ValueError(f"{dr}部没有可划的区域")
        src["geom"] = src["geom"].difference(half)
        dst["geom"] = unary_union([dst["geom"], piece])
        return (f"已把 {src['name']} 的{dr}部"
                f"（{piece.area*11320:.1f}km²）划给 {dst['name']}")
    raise ValueError(f"未知操作 {op['op']}")
