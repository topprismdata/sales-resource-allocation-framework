#!/usr/bin/env python3
"""新城市 OSM 地标抓取 + 解析：为区域数据包生成 osm_parsed.json。

两步合一：
  python3 tools/fetch_region_osm.py --bbox <南,西,北,东> --out data/<region>
  python3 tools/fetch_region_osm.py --bbox <南,西,北,东> --out data/<region> --tiles 4x4
  （bbox 顺序与 Overpass 一致：south,west,north,east）

产出: <out>/osm_raw.json（原始） + <out>/osm_parsed.json（rivers/roads/districts，
供 demo_server 四至重建 lookup_geometry 消费）。大区域按 --tiles 分块请求，
成功块按 OSM 的 (type, id) 去重合并；有失败块时只写 partial 文件并返回非零，
避免把不完整的路网静默当成完整数据包。

依赖: 仅 stdlib（urllib 调 Overpass API，耗时取决于区域大小和服务负载）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://overpass-api.de/api/interpreter"
UA = "SRAF-region-pack/1.0"
DEFAULT_RETRIES = 3
MIN_TILE_INTERVAL = 2.0
MAX_RETRY_BACKOFF = 60.0

QUERY = """[out:json][timeout:{timeout}];
(
  way["waterway"~"^(river|canal|stream)$"]["name"]({bbox});
  way["highway"~"^(motorway|trunk|primary|secondary)$"]["name"]({bbox});
  way["highway"]["ref"~"^G[0-9]"]({bbox});
  relation["boundary"="administrative"]["admin_level"="8"]["name"]({bbox});
  way["boundary"="administrative"]["admin_level"="8"]["name"]({bbox});
);
out geom;"""


def _parse_bbox(value: str) -> tuple[float, float, float, float]:
    """解析并校验 south,west,north,east。"""
    try:
        parts = tuple(float(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise ValueError("bbox 必须是 south,west,north,east 四个数字") from exc
    if len(parts) != 4:
        raise ValueError("bbox 必须是 south,west,north,east 四个数字")
    south, west, north, east = parts
    if not south < north or not west < east:
        raise ValueError("bbox 必须满足 south<north 且 west<east")
    if not -90 <= south <= 90 or not -90 <= north <= 90:
        raise ValueError("bbox 纬度必须在 -90 到 90 之间")
    if not -180 <= west <= 180 or not -180 <= east <= 180:
        raise ValueError("bbox 经度必须在 -180 到 180 之间")
    return south, west, north, east


def parse_tiles(value: str) -> tuple[int, int]:
    """解析 RxC 分块规格，行列均必须为正整数。"""
    match = re.fullmatch(r"\s*([1-9]\d*)x([1-9]\d*)\s*", value or "")
    if not match:
        raise ValueError("--tiles 必须是 RxC 格式，例如 4x4，R/C 必须为正整数")
    return int(match.group(1)), int(match.group(2))


def split_bbox(bbox: str, rows: int, cols: int) -> list[tuple[int, int, str]]:
    """把 bbox 按行优先切成 rows×cols 个不重叠网格块。"""
    if rows < 1 or cols < 1:
        raise ValueError("网格行列必须为正整数")
    south, west, north, east = _parse_bbox(bbox)
    lat_step = (north - south) / rows
    lon_step = (east - west) / cols
    tiles = []
    for row in range(rows):
        tile_south = south + row * lat_step
        tile_north = north if row == rows - 1 else south + (row + 1) * lat_step
        for col in range(cols):
            tile_west = west + col * lon_step
            tile_east = east if col == cols - 1 else west + (col + 1) * lon_step
            tile = ",".join(str(value) for value in
                             (tile_south, tile_west, tile_north, tile_east))
            tiles.append((row + 1, col + 1, tile))
    return tiles


def fetch(bbox: str, timeout: int = 180) -> dict:
    """请求单个 bbox；HTTP/网络错误交给上层重试。"""
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
    print(f"请求 Overpass（bbox={bbox}，可能需要数分钟）…", flush=True)
    with urllib.request.urlopen(req, timeout=timeout + 30, context=ctx) as resp:
        raw = json.loads(resp.read())
    print(f"获得 elements: {len(raw.get('elements', []))}", flush=True)
    return raw


def _retry_delay(exc: Exception, attempt: int) -> float:
    """计算重试退避；429 的 Retry-After 若可读则至少尊重它。"""
    retry_after = getattr(getattr(exc, "headers", None), "get", lambda *_: None)(
        "Retry-After")
    try:
        server_delay = float(retry_after) if retry_after is not None else 0.0
    except (TypeError, ValueError):
        server_delay = 0.0
    exponential = min(MAX_RETRY_BACKOFF, 2.0 ** attempt)
    return max(MIN_TILE_INTERVAL, server_delay, exponential)


def _merge_elements(
    elements: list[dict], raw_elements: object,
) -> int:
    """向有序元素表加入一个响应，返回本块新增元素数。"""
    if not isinstance(raw_elements, list):
        raise ValueError("Overpass 响应缺少合法 elements 数组")
    known = {(item.get("type"), item.get("id")) for item in elements}
    before = len(elements)
    for element in raw_elements:
        if not isinstance(element, dict):
            raise ValueError("Overpass elements 含非对象项")
        key = (element.get("type"), element.get("id"))
        if key not in known:
            known.add(key)
            elements.append(element)
    return len(elements) - before


def merge_raw_responses(raw_responses: list[dict]) -> dict:
    """按首次出现顺序合并响应，并按 (type,id) 去重。"""
    if not raw_responses:
        return {"elements": []}
    merged = dict(raw_responses[0])
    elements: list[dict] = []
    for raw in raw_responses:
        if not isinstance(raw, dict):
            raise ValueError("Overpass 响应不是 JSON 对象")
        _merge_elements(elements, raw.get("elements"))
    merged["elements"] = elements
    return merged


def fetch_tiled(
    bbox: str,
    rows: int = 1,
    cols: int = 1,
    timeout: int = 180,
    retries: int = DEFAULT_RETRIES,
    *,
    fetch_fn=None,
    sleep_fn=None,
    clock_fn=None,
) -> tuple[dict, list[dict]]:
    """抓取网格并合并，返回 (raw, failures)。"""
    if retries < 0:
        raise ValueError("重试次数不能为负数")
    if fetch_fn is None:
        fetch_fn = fetch
    if sleep_fn is None:
        sleep_fn = time.sleep
    if clock_fn is None:
        clock_fn = time.monotonic
    tiles = [(1, 1, bbox.strip())] if rows == cols == 1 else split_bbox(
        bbox, rows, cols)
    elements: list[dict] = []
    first_response: dict | None = None
    failures: list[dict] = []
    last_request_started: float | None = None

    for index, (row, col, tile_bbox) in enumerate(tiles, start=1):
        label = f"块 {index}/{len(tiles)}（r{row}c{col}）"
        print(f"{label} 开始，bbox={tile_bbox}", flush=True)
        response = None
        last_error: Exception | None = None
        for attempt in range(1, retries + 2):
            if last_request_started is not None:
                elapsed = clock_fn() - last_request_started
                wait = max(0.0, MIN_TILE_INTERVAL - elapsed)
                if wait:
                    sleep_fn(wait)
            last_request_started = clock_fn()
            try:
                candidate = fetch_fn(tile_bbox, timeout)
                if not isinstance(candidate, dict):
                    raise ValueError("Overpass 响应不是 JSON 对象")
                response = candidate
                break
            except Exception as exc:  # 网络/HTTP/响应错误均有限次重试
                last_error = exc
                if attempt > retries:
                    break
                delay = _retry_delay(exc, attempt)
                print(f"{label} 第 {attempt} 次失败：{type(exc).__name__}: {exc}；"
                      f"{delay:.1f}s 后重试", flush=True)
                sleep_fn(delay)
        if response is None:
            assert last_error is not None
            failure = {"row": row, "col": col, "bbox": tile_bbox,
                       "error": f"{type(last_error).__name__}: {last_error}"}
            failures.append(failure)
            print(f"{label} 最终失败：{failure['error']}", file=sys.stderr,
                  flush=True)
        else:
            if first_response is None:
                first_response = response
            added = _merge_elements(elements, response.get("elements"))
            print(f"{label} 成功：本块 {len(response.get('elements', []))} 条，"
                  f"新增 {added} 条，合计 {len(elements)} 条", flush=True)
        if index < len(tiles) and failures and failures[-1]["row"] == row \
                and failures[-1]["col"] == col:
            delay = _retry_delay(last_error, retries + 1)
            print(f"{label} 失败后的块间退避：{delay:.1f}s", flush=True)
            sleep_fn(delay)

    raw = dict(first_response) if first_response is not None else {"elements": []}
    raw["elements"] = elements
    print(f"抓取结束：成功块 {len(tiles) - len(failures)}/{len(tiles)}，"
          f"合并后 {len(elements)} 条；失败块数: {len(failures)}", flush=True)
    return raw, failures


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
            for member in e["members"]:
                if member.get("type") == "way" and "geometry" in member:
                    seg = [(p["lon"], p["lat"])
                           for p in member["geometry"] if p]
                    if len(seg) >= 2:
                        districts[name]["polys"].append(seg)
    for district in districts.values():
        district["npts"] = sum(len(poly) for poly in district["polys"])
    return {"districts": districts, "rivers": rivers, "roads": roads, "refs": refs}


def main() -> int:
    ap = argparse.ArgumentParser(description="抓取并解析新城市 OSM 地标")
    ap.add_argument("--bbox", required=True,
                    help="south,west,north,east（Overpass 顺序）")
    ap.add_argument("--out", required=True, help="区域数据包目录（将写入 osm_*.json）")
    ap.add_argument("--tiles", default="1x1",
                    help="分块网格 RxC（默认 1x1，广州建议 4x4）")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--retries", type=int, default=DEFAULT_RETRIES,
                    help=f"每块失败后的重试次数（默认 {DEFAULT_RETRIES}）")
    args = ap.parse_args()

    try:
        rows, cols = parse_tiles(args.tiles)
        _parse_bbox(args.bbox.strip())
        if args.timeout <= 0:
            raise ValueError("--timeout 必须为正数")
        if args.retries < 0:
            raise ValueError("--retries 不能为负数")
    except ValueError as exc:
        ap.error(str(exc))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    raw, failures = fetch_tiled(
        args.bbox.strip(), rows, cols, args.timeout, args.retries)
    if failures:
        partial = out / "osm_raw.partial.json"
        partial_payload = dict(raw)
        partial_payload["sraf_partial"] = True
        partial_payload["failed_tiles"] = failures
        partial.write_text(json.dumps(partial_payload, ensure_ascii=False),
                           encoding="utf-8")
        print(f"未写入正式 osm_raw.json/osm_parsed.json；部分结果见 {partial}",
              file=sys.stderr)
        return 2

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
