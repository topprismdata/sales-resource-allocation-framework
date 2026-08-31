#!/usr/bin/env python3
"""业代围栏操作（单元集合范式）：围栏=基础单元集合，合并/拆分/划拨=集合运算。
基础单元库不可变；围栏只持有单元 id 集合，几何为渲染缓存。
"""
import json, re, math
from pathlib import Path
import shapely
import networkx as nx
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
from shapely.ops import unary_union
from _paths import DATA

LINK_MIN_M = 50          # 单元邻接判定：共享边界最短长度


class YeidaiState:
    """工作副本：每片 = 单元 id 集合。几何按需计算。"""

    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir is not None else Path(DATA)
        d = json.load(open(self.data_dir / "basic_units_wgs.json", encoding="utf-8"))
        self.unit_geoms = [shapely.from_wkt(u["geom"]) for u in d["units"]]
        try: g = json.load(open(self.data_dir / "unit_graph_hzlw.json", encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError): g = {"nodes": [], "edges": [], "adjacency": {}, "unit_zone": {}, "zone_units": {}}
        self.adj = {int(k): set(v) for k, v in g["adjacency"].items()}
        self.unit_zone0 = {int(k): v for k, v in g["unit_zone"].items()}
        self.zone_units0 = g["zone_units"]
        zmeta = json.load(open(self.data_dir / "haizhu_liwan_zones_original.json",
                               encoding="utf-8"))["zones"]
        # 初始围栏：按原始分配的单元集；无单元的围栏 → 原始环注册为伪单元
        self.zones = []
        self.pseudo = {}   # pseudo_id → geom（异常片兜底）
        extra = len(self.unit_geoms)
        for z in zmeta:
            key = z["name"] + "|" + z["id"]
            uids = set(self.zone_units0.get(key, []))
            geom = None
            if uids:
                geom = unary_union([self.unit_geoms[u] for u in uids])
            else:
                p = Polygon(z["ring"])
                geom = p if p.is_valid else p.buffer(0)
                if geom.geom_type == "MultiPolygon":
                    geom = max(geom.geoms, key=lambda x: x.area)
                self.pseudo[extra] = geom
                uids = {extra}
                extra += 1
            self.zones.append({"id": z["id"], "name": z["name"],
                               "unit_ids": uids, "geom": geom})

    # ---------- 几何 ----------
    def geom_of(self, unit_ids):
        return unary_union([self.unit_geoms[u] if u < len(self.unit_geoms)
                            else self.pseudo[u] for u in sorted(unit_ids)])

    def snapshot(self):
        out = []
        for z in self.zones:
            g = self.geom_of(z["unit_ids"])
            rings = ([list(g.exterior.coords)] if g.geom_type == "Polygon"
                     else [list(p.exterior.coords) for p in g.geoms])
            out.append({"id": z["id"], "name": z["name"],
                        "rings": [[[round(x, 6), round(y, 6)] for x, y in r]
                                  for r in rings],
                        "area": round(g.area * 11320 * 1.0084, 1)})
        return out

    # ---------- 解析 ----------
    def resolve(self, text):
        refs = re.findall(r"@([^\s@，。；、,;]+)", text)
        out = []
        for ref in refs:
            hits = [z for z in self.zones if ref in z["name"]]
            if len(hits) != 1:
                raise ValueError(f"@{ref} 匹配到 {len(hits)} 个围栏，请用更长的名字")
            out.append(hits[0])
        return out

    def resolve_llm(self, op):
        if op.get("op") == "merge":
            zs = self.resolve(" ".join("@"+n for n in op["zones"]))
            return {"op": "merge", "zones": zs}
        if op.get("op") == "split":
            return {"op": "split", "zone": self.resolve("@"+op["zone"])[0],
                    "cut": op.get("cut")}
        if op.get("op") == "transfer_direction":
            return {"op": "transfer_direction",
                    "src": self.resolve("@"+op["src_zone"])[0],
                    "direction": op["direction"],
                    "dst": self.resolve("@"+op["dst_zone"])[0]}
        if op.get("op") == "delete":
            return {"op": "delete", "zone": self.resolve("@"+op["zone"])[0]}
        raise ValueError(f"LLM: 未知操作 {op.get('op')}")

    def parse_op(self, text):
        refs = self.resolve(text)
        if re.search(r"合并|融合|并成一个", text):
            if len(refs) < 2:
                raise ValueError("合并需要至少两个 @围栏")
            return {"op": "merge", "zones": refs}
        m = re.search(r"(@\S+)\s*(?:的)?(北|南|东|西)(?:部|边|侧)?(?:区域)?\s*"
                      r"(?:划给|给|归|并入)\s*(@\S+)", text)
        if m:
            return {"op": "transfer_direction", "src": refs[0],
                    "direction": m.group(2), "dst": refs[-1]}
        if re.search(r"拆分|切开|分成两|一分为二", text) and refs:
            mc = re.search(r"沿\s*([^\s@，。；、,;]+)", text)
            return {"op": "split", "zone": refs[0],
                    "cut": mc.group(1) if mc else None}
        if re.search(r"取消|删除|撤销", text) and refs:
            return {"op": "delete", "zone": refs[0]}
        raise ValueError("无法识别的指令：支持 合并/@A @B、拆分 @A 沿 XX、"
                         "@A 的北部划给 @B、取消 @A")

    # ---------- 操作（全部是单元集合运算） ----------
    def apply(self, op):
        if op["op"] == "merge":
            zs = op["zones"]
            keep = zs[0]
            names = [z["name"] for z in zs]
            for z in zs[1:]:
                keep["unit_ids"] |= z["unit_ids"]
            keep["geom"] = self.geom_of(keep["unit_ids"])
            self.zones = [z for z in self.zones if z not in zs[1:]]
            return f"已合并 {names} → {keep['name']}（{len(keep['unit_ids'])}单元）"

        if op["op"] == "delete":
            z = op["zone"]
            self.zones = [x for x in self.zones if x is not z]
            return f"已取消 {z['name']}"

        if op["op"] == "transfer_direction":
            src, dst, dr = op["src"], op["dst"], op["direction"]
            dv = {"北": (0, 1), "南": (0, -1), "东": (1, 0), "西": (-1, 0)}[dr]
            c = src["geom"].centroid
            moved = {u for u in src["unit_ids"]
                     if ((self.unit_geoms[u].centroid.x - c.x) * dv[0]
                         + (self.unit_geoms[u].centroid.y - c.y) * dv[1]) > 0}
            if not moved:
                raise ValueError(f"{dr}部没有可划的单元")
            src["unit_ids"] -= moved
            dst["unit_ids"] |= moved
            src["geom"] = self.geom_of(src["unit_ids"])
            dst["geom"] = self.geom_of(dst["unit_ids"])
            return (f"已把 {src['name']} 的{dr}部 {len(moved)} 个单元"
                    f"划给 {dst['name']}")

        if op["op"] == "split":
            z = op["zone"]
            cutname = op.get("cut")
            cutline = self._resolve_cut(cutname) if cutname else None
            # 邻接子图（片内）+ 删边 → 连通分量
            sub = nx.Graph()
            uids = sorted(z["unit_ids"])
            sub.add_nodes_from(uids)
            for u in uids:
                for v in self.adj.get(u, ()):
                    if v in z["unit_ids"] and u < v:
                        sub.add_edge(u, v)
            if cutline is not None:
                drop = []
                for u, v in list(sub.edges()):
                    shared = self.unit_geoms[u].intersection(self.unit_geoms[v])
                    if not shared.is_empty and cutline.distance(shared) < 1e-9:
                        drop.append((u, v))
                for e in drop:
                    sub.remove_edge(*e)
            comps = sorted(nx.connected_components(sub), key=len, reverse=True)
            if len(comps) < 2:
                msg = ("切割要素未把围栏一分为二（它可能本来就是这条围栏的边界）"
                       if cutname else "默认切分未能分开（单元邻接过密），"
                                       "请指定沿XX路/河")
                raise ValueError(msg)
            z["unit_ids"] = set(comps[0])
            names = [z["name"]]
            for k, comp in enumerate(comps[1:], 1):
                nm = f"{z['name']}-{k}"
                self.zones.append({"id": f"{z['id']}-{k}", "name": nm,
                                   "unit_ids": set(comp), "geom": None})
                names.append(nm)
            for z_ in self.zones:
                if z_["unit_ids"] is not None and z_["geom"] is None:
                    z_["geom"] = self.geom_of(z_["unit_ids"])
            return f"已拆分 {z['name']} → {names}（{len(comps)} 片）"

        raise ValueError(f"未知操作 {op['op']}")

    def _resolve_cut(self, name):
        """名称 → 线网中的要素几何（路/河/行政界）。"""
        d = json.load(open(self.data_dir / "gz_osm_full.json", encoding="utf-8"))
        pieces = []
        for grp in ("roads", "rivers"):
            for r in d[grp]:
                if name and name in r.get("name", ""):
                    try:
                        g = shapely.from_wkt(r["wkt"])
                    except Exception:
                        continue
                    parts = ([g] if g.geom_type == "LineString"
                             else list(g.geoms) if g.geom_type == "MultiLineString" else [])
                    pieces += parts
        if not pieces:
            raise ValueError(f"找不到线要素『{name}』")
        return unary_union(pieces)


def str_shapely(ring):
    p = Polygon(ring)
    return p if p.is_valid else p.buffer(0)


def llm_parse_op(text, zones, timeout=60):
    """规则失败时的 LLM 兜底：返回结构化 op（名称形式）。"""
    import requests
    cfg = json.load(open(f"{DATA}/llm_config.json", encoding="utf-8"))
    names = [z["name"] for z in zones]
    sys_p = (
        "你是围栏指令解析器。把用户的中文指令解析成纯JSON（不要markdown、不要解释）。\n"
        f"可用围栏名：{json.dumps(names, ensure_ascii=False)}\n"
        '操作schema：\n'
        '{"op":"merge","zones":["名1","名2"]}\n'
        '{"op":"split","zone":"名","cut":"道路或河名，无则null"}\n'
        '{"op":"transfer_direction","src_zone":"名","direction":"北|南|东|西","dst_zone":"名"}\n'
        '{"op":"delete","zone":"名"}\n'
        "围栏名必须原样使用上面列表中的完整名称。"
    )
    r = requests.post(cfg["url"], headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['key']}"},
        json={"model": cfg["model"],
              "messages": [{"role": "system", "content": sys_p},
                           {"role": "user", "content": text}],
              "max_tokens": 512}, timeout=timeout)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    import re
    content = re.sub(r"^```(json)?|```$", "", content, flags=re.M).strip()
    return json.loads(content)
