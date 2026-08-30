#!/usr/bin/env python3
"""分配台账：基础单元 → 经销商 的所有权登记。文本指令 = 台账变更。

指令模式（全部是分配动作）：
  凤凰街道给亨啡源
  把龙洞街道和大源街道给A
  长兴街道的北部给B
  沿广汕二路以北给C
单元一旦划给某经销商，就归其所有，直到再次划转。
几何（围栏）= 该经销商名下单元的并集，仅作渲染。
"""
import json, re, math
import shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.strtree import STRtree
from shapely.ops import unary_union

DATA = "/Users/ghb/sales-resource-allocation-framework/data/gz"


class Ledger:
    def __init__(self):
        d = json.load(open(f"{DATA}/unit_attributes.json", encoding="utf-8"))
        self.attrs = d["units"]                       # id → district/street/roads
        self.geoms = [shapely.from_wkt(u["wkt"]) for u in
                      json.load(open(f"{DATA}/basic_units_v5_wgs.json",
                                     encoding="utf-8"))["units"]]
        self.owner = {}                               # unit_id → owner
        self.log = []
        # 索引
        self.by_street = {}
        self.by_road = {}
        self.by_district = {}
        for a in self.attrs:
            if a["street"]:
                self.by_street.setdefault(a["street"], set()).add(a["id"])
            core = a["street"].replace("街道", "").replace("镇", "") if a["street"] else ""
            if core:
                self.by_street.setdefault(core, set()).add(a["id"])
                if len(core) >= 2:
                    self.by_street.setdefault(core[:-1], set()).add(a["id"])
            for rd in a["roads"]:
                self.by_road.setdefault(rd, set()).add(a["id"])
            if a["district"]:
                self.by_district.setdefault(a["district"], set()).add(a["id"])

    def resolve_units(self, term):
        """街道名/区名/路名 → 单元 id 集合。"""
        if term in self.by_street:
            return set(self.by_street[term])
        if term in self.by_road:
            return set(self.by_road[term])
        if term in self.by_district:
            return set(self.by_district[term])
        # 模糊：街道名包含
        hits = set()
        for k, v in self.by_street.items():
            if term in k or k in term:
                hits |= v
        if hits:
            return hits
        for k, v in self.by_road.items():
            if term in k or k in term:
                hits |= v
        return hits

    def execute(self, text, owner_hint=None):
        """解析并执行一条分配指令。返回描述文本。"""
        t = text.replace("把", "").replace("的单元", "").replace("的", "的")
        # 目标经销商：最后出现的"给X"
        m = re.search(r"(?:划给|给|归|并入)\s*([^\s，。；,;]+?)(?:$|[，。；,;])", t)
        owner = m.group(1) if m else owner_hint
        if not owner:
            raise ValueError("缺少接收方（…给XX）")
        # 术语：抓取方位词前的地名
        m2 = re.search(r"([^\s，。；,;]+?)(?:的)?(北|南|东|西)(?:部|边|侧)?", t)
        direction = m2.group(2) if m2 else None
        term = m2.group(1) if m2 else None
        if term is None:
            m3 = re.search(r"^([^\s，。；,;]+?)给", t)
            term = m3.group(1) if m3 else None
        if not term:
            raise ValueError("未识别分配对象（街道/区/路名）")
        units = self.resolve_units(term)
        if not units:
            raise ValueError(f"找不到『{term}』对应的单元")
        # 方位过滤（相对该术语区域质心）
        if direction:
            dv = {"北": (0, 1), "南": (0, -1), "东": (1, 0), "西": (-1, 0)}[direction]
            g = unary_union([self.geoms[u] for u in units])
            c = g.centroid
            keep = set()
            for u in units:
                p = self.geoms[u].centroid
                if (p.x - c.x) * dv[0] + (p.y - c.y) * dv[1] > 0:
                    keep.add(u)
            units = keep
            if not units:
                raise ValueError(f"{direction}部无单元")
        # 执行划转
        for u in units:
            self.owner[u] = owner
        self.log.append(f"{text} → {owner} +{len(units)}单元")
        return owner, len(units)

    def fence_units(self, owner):
        return sorted(u for u, o in self.owner.items() if o == owner)

    def fence_geom(self, owner):
        ids = self.fence_units(owner)
        if not ids:
            return None
        return unary_union([self.geoms[u] for u in ids])

    def summary(self):
        owners = {}
        for u, o in self.owner.items():
            owners.setdefault(o, set()).add(u)
        return [{"owner": o, "units": len(us),
                 "area_km2": round(sum(self.geoms[u].area * 11320 * 1.0084
                                       for u in us), 1)}
                for o, us in sorted(owners.items(), key=lambda kv: -len(kv[1]))]


def ring_of(geom):
    if geom is None:
        return []
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    return [[round(x, 6), round(y, 6)] for x, y in geom.exterior.coords]


if __name__ == "__main__":
    L = Ledger()
    print("索引:", len(L.by_street), "街道名 |", len(L.by_road), "路名 |",
          len(L.by_district), "区名")
    owner, n = L.execute("凤凰街道的单元给广州亨啡源商贸有限公司")
    print(f"试运行: {owner} +{n}单元")
    owner, n = L.execute("龙洞街道也给广州亨啡源商贸有限公司")
    print(f"试运行: {owner} +{n}单元")
    print("亨啡源台账:", L.fence_units("广州亨啡源商贸有限公司"))
