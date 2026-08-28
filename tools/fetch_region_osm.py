#!/usr/bin/env python3
"""新城市 OSM 地标抓取 + 解析：为区域数据包生成 osm_parsed.json。

两步合一：
  python3 tools/fetch_region_osm.py --bbox <南,西,北,东> --out data/<region>
  （bbox 顺序与 Overpass 一致：south,west,north,east）

产出: <out>/osm_raw.json（原始） + <out>/osm_parsed.json（rivers/roads/districts，
供 demo_server 四至重建 lookup_geometry 消费）。

依赖: 仅 stdlib（urllib 调 Overpass API，约 1-3 分钟，视区域大小）。
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://overpass-api.de/api/interpreter"
UA = "SRAF-region-pack/1.0"

QUERY = """[out:json][timeout:{timeout}];
(
  way["waterway"~"^(river|canal|stream)$"]["name"]({bbox});
  way["highway"~"^(motorway|trunk|primary|secondary)$"]["name"]({bbox});
  way["highway"]["ref"~"^G[0-9]"]({bbox});
  relation["boundary"="administrative"]["admin_level"="8"]["name"]({bbox});
  way["boundary"="administrative"]["admin_level"="8"]["name"]({bbox});
);
out geom;"""


def fetch(bbox: str, timeout: int = 180) -> dict:
    q = QUERY.format(bbox=bbox, timeout=timeout)
    data = urllib.parse.urlencode({"data": q}).encode()
    import ssl
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl._create_unverified_context()  # noqa: SLF001 — 无 certifi 时降级
        print("⚠ 无 certifi，使用跳过证书校验（建议 pip install certifi）")
    req = urllib.request.Request(API, data=data, headers={"User-Agent": UA})
    print(f"请求 Overpass（bbox={bbox}，可能需要 1-3 分钟）…")
    with urllib.request.urlopen(req, timeout=timeout + 30, context=ctx) as resp:
        raw = json.loads(resp.read())
    print(f"获得 elements: {len(raw.get('elements', []))}")
    return raw


def parse(raw: dict) -> dict:
    rivers: dict[str, list] = {}
    roads: dict[str, list] = {}
    refs: dict[str, list] = {}
    districts: dict[str, dict] = {}

    def nm(tags: dict) -> str | None:
        return tags.get("name")

    HW = ("motorway", "trunk", "primary", "secondary")
    for e in raw.get("elements", []):
        tags = e.get("tags", {})
        if e["type"] == "way" and "geometry" in e:
            seg = [(p["lon"], p["lat"]) for p in e["geometry"] if p]
            if len(seg) < 2:
                continue
            name = nm(tags)
            hw = tags.get("highway")
            ref = tags.get("ref", "")
            if tags.get("waterway") in ("river", "canal", "stream") and name:
                rivers.setdefault(name, []).append(seg)
            if hw in HW and name:
                roads.setdefault(name, []).append(seg)
            if hw in HW and ref.startswith("G"):
                refs.setdefault(ref, []).append(seg)
            if (tags.get("boundary") == "administrative"
                    and tags.get("admin_level") == "8" and name):
                districts.setdefault(name, {"level": 8, "polys": [], "npts": 0})
                districts[name]["polys"].append(seg)
        elif e["type"] == "relation" and "members" in e:
            name = nm(tags)
            if (not name or tags.get("boundary") != "administrative"
                    or tags.get("admin_level") != "8"):
                continue
            districts.setdefault(name, {"level": 8, "polys": [], "npts": 0})
            for m in e["members"]:
                if m.get("type") == "way" and "geometry" in m:
                    seg = [(p["lon"], p["lat"]) for p in m["geometry"] if p]
                    if len(seg) >= 2:
                        districts[name]["polys"].append(seg)
    for d in districts.values():
        d["npts"] = sum(len(p) for p in d["polys"])
    return {"districts": districts, "rivers": rivers, "roads": roads, "refs": refs}


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取并解析新城市 OSM 地标")
    ap.add_argument("--bbox", required=True,
                    help="south,west,north,east（Overpass 顺序）")
    ap.add_argument("--out", required=True, help="区域数据包目录（将写入 osm_*.json）")
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = fetch(a.bbox.strip(), a.timeout)
    (out / "osm_raw.json").write_text(json.dumps(raw, ensure_ascii=False),
                                      encoding="utf-8")
    parsed = parse(raw)
    (out / "osm_parsed.json").write_text(json.dumps(parsed, ensure_ascii=False),
                                         encoding="utf-8")
    print(f"✓ 写出 {out/'osm_raw.json'} 与 {out/'osm_parsed.json'}")
    print(f"  rivers: {len(parsed['rivers'])} 条 · roads: {len(parsed['roads'])} 条 · "
          f"districts: {len(parsed['districts'])} 个")
    if not parsed["districts"]:
        print("⚠ 无区县边界——检查 bbox 是否覆盖目标城市，或 admin_level 是否为 8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
