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
from pathlib import Path
import shapely
from shapely.geometry import Polygon, Point, LineString
from shapely.strtree import STRtree
from shapely.ops import unary_union
from _paths import DATA


class AmbiguousTermError(ValueError):
    """术语命中多个不同街道/区/路，拒绝静默合并。"""


class Ledger:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir) if data_dir is not None else Path(DATA)
        d = json.load(open(self.data_dir / "unit_attributes.json", encoding="utf-8"))
        self.attrs = d["units"]                       # id → district/street/roads
        self.geoms = [shapely.from_wkt(u["geom"]) for u in
                      json.load(open(self.data_dir / "basic_units_wgs.json",
                                     encoding="utf-8"))["units"]]
        self.owner = {}                               # unit_id → owner
        self.log = []
        # 索引
        self.by_street = {}
        self.by_road = {}
        self.by_district = {}
        self._street_sources = {}
        self._road_sources = {}
        self._district_sources = {}
        for a in self.attrs:
            if a["street"]:
                self.by_street.setdefault(a["street"], set()).add(a["id"])
                self._street_sources.setdefault(a["street"], set()).add(a["street"])
            core = a["street"].replace("街道", "").replace("镇", "") if a["street"] else ""
            if core:
                self.by_street.setdefault(core, set()).add(a["id"])
                self._street_sources.setdefault(core, set()).add(a["street"])
            for rd in a["roads"]:
                self.by_road.setdefault(rd, set()).add(a["id"])
                self._road_sources.setdefault(rd, set()).add(rd)
            if a["district"]:
                self.by_district.setdefault(a["district"], set()).add(a["id"])
                self._district_sources.setdefault(a["district"], set()).add(a["district"])

    def _one(self, term):
        if term in self.by_street:
            return set(self.by_street[term])
        if term in self.by_road:
            return set(self.by_road[term])
        if term in self.by_district:
            return set(self.by_district[term])
        return set()

    def resolve_units(self, term):
        """街道名/区名/路名/复合(街道沿路) → 单元 id 集合。"""
        if "沿" in term:
            a, b = term.split("沿", 1)
            sa, sb = self._one(a.strip()), self._one(b.strip())
            return (sa & sb) if (sa and sb) else (sa | sb)
        r = self._one(term)
        if r:
            return r
        # 模糊：收集所有索引键；多个不同实体不得静默合并。
        matches = []
        for kind, index, sources in (
            ("街道", self.by_street, self._street_sources),
            ("路", self.by_road, self._road_sources),
            ("区", self.by_district, self._district_sources),
        ):
            for k, v in index.items():
                if term in k or k in term:
                    matches.append((kind, k, v, sources.get(k, {k})))

        source_ids = {
            (kind, source)
            for kind, _key, _units, source_names in matches
            for source in source_names
        }
        if len(matches) > 1 and len(source_ids) > 1:
            candidates = []
            for kind, _key, _units, source_names in matches:
                for source in sorted(source_names):
                    label = f"{source}（{kind}）"
                    if label not in candidates:
                        candidates.append(label)
            preview = "、".join(candidates[:8])
            more = f" 等 {len(candidates)} 个" if len(candidates) > 8 else ""
            raise AmbiguousTermError(
                f"术语『{term}』模糊命中 {len(matches)} 个索引键，涉及多个街道/区/路"
                f"（{preview}{more}）；请使用完整名称"
            )

        hits = set()
        for _kind, _key, units, _source_names in matches:
            hits |= units
        return hits

    def execute(self, text, owner_hint=None):
        """解析并执行一条分配指令。返回描述文本。"""
        t = text.replace("把", "").replace("的单元", "").replace("的", "的")
        # 目标经销商：最后出现的"给X"
        m = re.search(r"(?:划给|给|归|并入)\s*([^\s，。；,;]+?)(?:$|[，。；,;])", t)
        owner = m.group(1) if m else owner_hint
        if not owner:
            raise ValueError("缺少接收方（…给XX）")
        # 术语 = "给X" 之前整段；方位仅当以 …的北部/…北部 结尾时识别
        m3 = re.search(r"(.+?)给", t)
        raw = m3.group(1).strip() if m3 else t.split("给")[0].strip()
        direction = None
        md = re.search(r"^(.+?)的?(北|南|东|西)(?:部|边|侧)$", raw)
        if md:
            term, direction = md.group(1).strip(), md.group(2)
        else:
            term = raw
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

    def assign(self, term, owner):
        """直接按术语指派（无 NL 解析，供自动重放）。"""
        md = re.search(r"^(.+?)的?(北|南|东|西)(?:部|边|侧)$", term)
        direction = None
        if md:
            term, direction = md.group(1), md.group(2)
        units = self.resolve_units(term)
        if not units:
            raise ValueError(f"找不到『{term}』")
        if direction:
            dv = {"北": (0, 1), "南": (0, -1), "东": (1, 0), "西": (-1, 0)}[direction]
            g = unary_union([self.geoms[u] for u in units])
            c = g.centroid
            units = {u for u in units if
                     (self.geoms[u].centroid.x - c.x) * dv[0]
                     + (self.geoms[u].centroid.y - c.y) * dv[1] > 0}
        for u in units:
            self.owner[u] = owner
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
