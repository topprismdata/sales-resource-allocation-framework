"""坐标系归一（GCJ-02 ⇄ WGS-84）。

数据约定（世界模型/数据包契约）：
  - 业务数据包（data/<region>）默认 crs=GCJ-02（高德/经纬地图系统一，
    围栏、门店、合同中心点同标准）
  - OSM 地标（roads/rivers/districts）与 OSM 瓦片 = WGS-84
  - 系统内部（intelligence/ + dealer_territory/ 全部几何判断）= WGS-84

混用两系 = 广州实测 ~623m 系统偏移（东-549/北+293），四至沿路判定、
合同→围栏生成、地图底图对齐全部失真。因此：
  _load_pack 入口 gcj→wgs；_persist_pack 出口 wgs→gcj；中间零混用。

WP03 收敛: 转换算法本体迁移至 coords-core v0.1.0 (组织唯一事实源)，
本模块保留数据包级帧流程 (crs_to_wgs/pack_from_disk/pack_for_disk)；
转换函数再导出自 coords_core，位级一致由金标测试锁定。
"""
from coords_core import (  # noqa: F401
    convert,
    gcj2wgs,
    out_of_china,
    wgs2gcj,
)


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
