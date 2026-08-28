"""坐标系归一（GCJ-02 ⇄ WGS-84）。

数据约定（世界模型/数据包契约）：
  - 业务数据包（data/<region>）默认 crs=GCJ-02（高德/经纬地图系统一，
    围栏、门店、合同中心点同标准）
  - OSM 地标（roads/rivers/districts）与 OSM 瓦片 = WGS-84
  - 系统内部（intelligence/ + dealer_territory/ 全部几何判断）= WGS-84

混用两系 = 广州实测 ~623m 系统偏移（东-549/北+293），四至沿路判定、
合同→围栏生成、地图底图对齐全部失真。因此：
  _load_pack 入口 gcj→wgs；_persist_pack 出口 wgs→gcj；中间零混用。

算法：标准 GCJ-02 偏移模型（国测局惯例），迭代反解 6 轮（亚毫米级）。
"""
from __future__ import annotations

import math

A = 6378245.0
EE = 0.00669342162296594323
PI = math.pi


def _tl(x: float, y: float) -> float:
    r = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    r += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    r += (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    r += (160.0 * math.sin(y / 12.0 * PI) + 320.0 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return r


def _to(x: float, y: float) -> float:
    r = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    r += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    r += (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    r += (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x * PI / 30.0)) * 2.0 / 3.0
    return r


def wgs2gcj(lon: float, lat: float) -> tuple[float, float]:
    rl = lat / 180.0 * PI
    magic = 1.0 - EE * math.sin(rl) ** 2
    sm = math.sqrt(magic)
    dlat = _tl(lon - 105.0, lat - 35.0)
    dlat = (dlat * 180.0) / ((A * (1.0 - EE)) / (magic * sm) * PI)
    dlon = _to(lon - 105.0, lat - 35.0)
    dlon = (dlon * 180.0) / (A / sm * math.cos(rl) * PI)
    return lon + dlon, lat + dlat


def gcj2wgs(lon: float, lat: float) -> tuple[float, float]:
    w = (lon, lat)
    for _ in range(6):
        g = wgs2gcj(*w)
        w = (lon + w[0] - g[0], lat + w[1] - g[1])
    return w


def out_of_china(lon: float, lat: float) -> bool:
    return not (72.0 <= lon <= 137.8 and 0.8 <= lat <= 55.8)


def convert(pt, to_wgs: bool) -> tuple[float, float]:
    """单点自动方向；境外点原样返回。"""
    lon, lat = pt[0], pt[1]
    if out_of_china(lon, lat):
        return (lon, lat)
    return gcj2wgs(lon, lat) if to_wgs else wgs2gcj(lon, lat)


def crs_to_wgs(meta: dict) -> bool:
    """数据包是否需要在加载时 GCJ→WGS。缺省声明 GCJ-02。"""
    crs = (meta.get("crs") or "GCJ-02").upper().replace("-", "").replace("_", "")
    return crs in ("GCJ02", "BD09LL")


def _pt(p, to_wgs):
    """to_wgs=True: GCJ→WGS；False: 恒等（幂等保证，绝不反方向乱转）。"""
    return tuple(round(v, 7) for v in convert(p[:2], True)) if to_wgs else tuple(p[:2])


def _rings(rings, to_wgs):
    import json as _json
    if isinstance(rings, str):
        rings = _json.loads(rings)
    return [[_pt(p, to_wgs) for p in r] for r in rings]


def pack_from_disk(reg: dict, contracts: list, meta: dict) -> None:
    """加载边界：GCJ 数据包 → 内存 WGS-84（就地）。crs=WGS84 的包不动。"""
    tw = crs_to_wgs(meta)
    for f in reg.get("fences", []):
        f["rings"] = _rings(f["rings"], tw)
    for st in reg.get("stores", []):
        st["lon"], st["lat"] = _pt((st["lon"], st["lat"]), tw)
    for ct in contracts:
        if ct.get("center"):
            ct["center"] = list(_pt(ct["center"], tw))
    if meta.get("center"):
        meta["center"] = list(_pt(meta["center"], tw))


def pack_for_disk(fences, stores, contracts, meta: dict) -> dict:
    """持久化边界：内存 WGS-84 → 磁盘声明坐标系。
    磁盘=GCJ（缺省）→ WGS→GCJ 逆转换；磁盘已声明 WGS84 → 原样（仅舍入）。"""
    to_gcj = crs_to_wgs(meta)

    def _pt2(p):
        v = convert(p[:2], False) if to_gcj else tuple(p[:2])
        return (round(v[0], 6), round(v[1], 6))

    def _rings(rings):
        import json as _json
        if isinstance(rings, str):
            rings = _json.loads(rings)
        return [[_pt2(p) for p in r] for r in rings]

    out_f = [{"area_id": f["area_id"], "dealer": f["dealer"],
              "area_km2": f.get("area_km2"),
              "rings": _rings(f["rings"])} for f in fences]
    lon_of = lambda st: _pt2((st["lon"], st["lat"]))[0]
    lat_of = lambda st: _pt2((st["lon"], st["lat"]))[1]
    out_s = [dict(st, lon=lon_of(st), lat=lat_of(st)) for st in stores]
    out_c = [dict(ct, center=list(_pt2(ct["center"])))
             if ct.get("center") else dict(ct) for ct in contracts]
    return {"fences": out_f, "stores": out_s, "contracts": out_c}
