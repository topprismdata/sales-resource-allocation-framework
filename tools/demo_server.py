#!/usr/bin/env python3
"""SRAF 分配智能 Demo 后端（纯 stdlib）。

三步流程：①合同→区域（fence_from_text + 冲突检测）②语义调整（规则优先，
LLM·M3 兜底自由句式，失败原因透传）③分析（Q1 健康 / Q2 缺口）。
区域数据包：--data-dir 指定初始包；GET /api/regions 列出全部；POST /api/switch
运行时热切换（带线程锁，无需重启）。包校验: tools/validate_region_pack.py
用法: python3 tools/demo_server.py [--data-dir <dir>] [port]   （默认 data/gz + 8765）
"""
from __future__ import annotations

import json
import math
import random
import sys
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dealer_territory.fence_from_text import (  # noqa: E402
    _dist_km, build_from_landmark_ratios, lookup_geometry,
    parse_four_bounds_text)
import re
import subprocess
import time
from intelligence.adjust import (  # noqa: E402
    AdjustError, apply_proposal, parse_and_propose)
from intelligence.llm import llm_four_bounds, llm_parse_command  # noqa: E402
from intelligence.health import fence_health, run_q1  # noqa: E402
from intelligence.classify import classify_gap  # noqa: E402
from intelligence.coords import pack_from_disk, pack_for_disk  # noqa: E402
from intelligence.knowledge import KnowledgeBase  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
from yeidai_ops import YeidaiState, llm_parse_op  # noqa: E402
from allocation_ledger import Ledger, ring_of  # noqa: E402
from intelligence.world import World, point_in_ring  # noqa: E402


def _parse_argv(argv: list[str]) -> tuple[int, str | None]:
    """[port] 与 --data-dir <dir> 任意顺序；返回 (port, data_dir)。"""
    port, data_dir, i = 8765, None, 0
    while i < len(argv):
        if argv[i] == "--data-dir" and i + 1 < len(argv):
            data_dir = argv[i + 1]; i += 2
        elif argv[i].isdigit():
            port = int(argv[i]); i += 1
        else:
            i += 1
    return port, data_dir


PORT, DATA_DIR_ARG = _parse_argv(sys.argv[1:])
DATA_ROOT = ROOT / "data"
TABLEAU20 = ["#4E79A7","#F28E2B","#E15759","#76B7B2","#59A14F","#EDC948",
             "#B07AA1","#FF9DA7","#9C755F","#BAB0AC","#A0CBE8","#FFBE7D",
             "#59A14F","#8CD17D","#B6992D","#F1CE63","#499894","#D4A6C8",
             "#D37295","#499894"]

KB = KnowledgeBase()


def _assign_dealer_colors(fences) -> tuple[dict, dict]:
    """邻接图贪心着色（四色定理实践）：bbox 粗筛 + 顶点邻近(~100m) = 邻接；
    随机选可用色分散到 Tableau20（种子固定可复现）。
    返回 (dealer→color, dealer→[相邻 dealer])。"""
    n = len(fences)
    bboxes = []
    for f in fences:
        xs = [p[0] for p in f.ring]; ys = [p[1] for p in f.ring]
        bboxes.append((min(xs), min(ys), max(xs), max(ys)))
    adj = [set() for _ in range(n)]
    th2 = 0.01
    for i in range(n):
        for j in range(i + 1, n):
            a, b = bboxes[i], bboxes[j]
            if a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]:
                continue
            ri = fences[i].ring[::2]
            rj = fences[j].ring[::2]
            near = False
            for p in ri:
                px, py = p
                for q in rj:
                    dx = (px - q[0]) * 97.0; dy = (py - q[1]) * 110.6
                    if dx * dx + dy * dy < th2:
                        near = True
                        break
                if near:
                    break
            if near:
                adj[i].add(j); adj[j].add(i)
    order = sorted(range(n), key=lambda i: -len(adj[i]))
    rng = random.Random(42)
    assign = [None] * n
    for i in order:
        used = {assign[j] for j in adj[i] if assign[j] is not None}
        free = [c for c in range(len(TABLEAU20)) if c not in used]
        assign[i] = rng.choice(free) if free else 0
    colors = {fences[i].dealer: TABLEAU20[assign[i]] for i in range(n)}
    neighbors = {fences[i].dealer: sorted(fences[j].dealer for j in adj[i])
                 for i in range(n)}
    return colors, neighbors


PAGE = ROOT / "tools" / "demo_page.html"

def _resolve_data_dir(data_dir_arg: str | None) -> Path:
    if data_dir_arg:
        return Path(data_dir_arg)
    if (ROOT / "data" / "gz").is_dir():
        return ROOT / "data" / "gz"
    return Path("/tmp")


def _load_pack(data_dir: Path) -> dict:
    """加载区域数据包 → 统一包状态（world/colors/neighbors/contracts/osm/meta）。

    坐标系契约：数据包默认 crs=GCJ-02（高德系），在此一次性转成
    WGS-84 供内部使用；OSM 本就是 WGS-84。meta.crs 可显式声明。"""
    meta_path = data_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    reg = json.loads((data_dir / "region.json").read_text(encoding="utf-8"))
    contracts_path = data_dir / "contracts.json"
    contracts = (json.loads(contracts_path.read_text(encoding="utf-8"))
                 if contracts_path.exists() else [])
    pack_from_disk(reg, contracts, meta)  # GCJ 声明 → 内存 WGS-84（幂等，WGS 包不动）
    w = World(reg)
    osm_path = data_dir / "osm_parsed.json"
    osm = json.loads(osm_path.read_text(encoding="utf-8")) if osm_path.exists() else None
    colors, neighbors = _assign_dealer_colors(w.fences)
    return {"data_dir": data_dir, "world": w, "contracts": contracts, "osm": osm,
            "meta": meta, "colors": colors, "neighbors": neighbors,
            "region_name": meta.get("region_name", data_dir.name),
            "map_center": tuple(meta.get("center", [113.35, 23.05])),
            "map_zoom": int(meta.get("zoom", 10))}


def _list_regions() -> list[dict]:
    out = []
    if not DATA_ROOT.is_dir():
        return out
    for d in sorted(DATA_ROOT.iterdir()):
        if not d.is_dir():
            continue
        try:
            meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
            region = json.loads((d / "region.json").read_text(encoding="utf-8"))
            out.append({"id": d.name, "region_name": meta.get("region_name", d.name),
                        "fences": len(region.get("fences", [])),
                        "stores": len(region.get("stores", []))})
        except Exception:  # noqa: BLE001 — 坏目录跳过
            continue
    return out


STATE_LOCK = threading.Lock()
STATE = {"pack": _load_pack(_resolve_data_dir(DATA_DIR_ARG)),
         "world": None, "proposal": None,
         "yeidai": YeidaiState(), "yeidai_snapshot": YeidaiState().snapshot(),
         "ledger": Ledger()}
STATE["world"] = STATE["pack"]["world"]


def _current() -> dict:
    return STATE["pack"]


def _world_snapshot(w: World, pack: dict) -> dict:
    return {
        "fences": [{"area_id": f.area_id, "dealer": f.dealer,
                    "area_km2": f.area_km2,
                    "color": pack["colors"].get(f.dealer, "#4E79A7"),
                    "neighbors": pack["neighbors"].get(f.dealer, []),
                    "ring": [list(p) for p in f.ring]}
                   for f in w.fences],
        "stores": [{"n": s.name, "d": s.district, "u": s.upstream,
                    "lon": s.lon, "lat": s.lat, "direct": s.direct,
                    "dealers": list(s.dealers), "kind": s.kind}
                   for s in w.stores],
        "kinds": w.kind_counts,
        "meta": {"region_name": pack["region_name"],
                 "center": list(pack["map_center"]), "zoom": pack["map_zoom"]},
    }


def _conflicts(stores) -> dict:
    oof = [s for s in stores if s.kind == "OOF"]
    mul = [s for s in stores if s.kind == "MULTI"]
    gap = [s for s in stores if s.kind == "GAP"]
    return {"oof_n": len(oof), "oof_sample": [s.name for s in oof[:5]],
            "multi_n": len(mul), "multi_sample": [s.name for s in mul[:5]],
            "gap_n": len(gap), "gap_sample": [s.name for s in gap[:5]]}
def _slug(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "", name).lower()
    return s or f"region{int(time.time())}"


def _persist_pack(pack: dict) -> None:
    """把内存（WGS-84）写回数据包 → 逆转换回声明坐标系（默认 GCJ-02）。"""
    d = pack["data_dir"]
    w = pack["world"]
    out = pack_for_disk(
        [{"area_id": f.area_id, "dealer": f.dealer, "area_km2": f.area_km2,
          "rings": [list(f.ring)]} for f in w.fences],
        [{"n": s.name, "c": s.category, "d": s.district, "u": s.upstream,
          "lon": s.lon, "lat": s.lat, "direct": s.direct,
          "dealers": list(s.dealers), "kind": s.kind} for s in w.stores],
        pack["contracts"], pack.get("meta") or {})
    (d / "contracts.json").write_text(
        json.dumps(out["contracts"], ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "region.json").write_text(json.dumps(
        {"fences": out["fences"], "stores": out["stores"],
         "kinds": w.kind_counts}, ensure_ascii=False), encoding="utf-8")


def _create_region(name: str, bbox: list) -> Path:
    slug = _slug(name)
    d = DATA_ROOT / slug
    if d.exists():
        raise ValueError(f"区域包已存在: {slug}")
    d.mkdir(parents=True)
    (d / "status.json").write_text(
        json.dumps({"status": "creating"}, ensure_ascii=False), encoding="utf-8")
    (d / "region.json").write_text(
        json.dumps({"fences": [], "stores": [], "kinds": {}}, ensure_ascii=False),
        encoding="utf-8")
    (d / "contracts.json").write_text("[]", encoding="utf-8")
    center = [(bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2]  # lat, lon
    (d / "meta.json").write_text(json.dumps(
        {"region_name": name, "center": [center[1], center[0]], "zoom": 12,
         "crs": "WGS84",  # 前端在 OSM(WGS84) 瓦片上点选，born-WGS
         "density_assumption_stores_per_km2": 25,
         "notes": f"前端创建于 {time.strftime('%Y-%m-%d %H:%M')}"},
        ensure_ascii=False, indent=1), encoding="utf-8")

    def work():
        try:
            r = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "fetch_region_osm.py"),
                 "--bbox", ",".join(str(x) for x in bbox), "--out", str(d)],
                capture_output=True, text=True, timeout=420)
            ok = (d / "osm_parsed.json").exists()
            (d / "status.json").write_text(json.dumps(
                {"status": "ready" if ok else "failed",
                 "log": (r.stdout + r.stderr)[-500:]}, ensure_ascii=False),
                encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            (d / "status.json").write_text(json.dumps(
                {"status": "failed", "log": str(e)[:300]}, ensure_ascii=False),
                encoding="utf-8")
    threading.Thread(target=work, daemon=True).start()
    return d


def _gen_synth_stores(ring, dealer: str, count: int, district: str) -> list:
    lons = [p[0] for p in ring]; lats = [p[1] for p in ring]
    out = []
    tries = 0
    while len(out) < count and tries < count * 60:
        tries += 1
        lon = random.uniform(min(lons), max(lons))
        lat = random.uniform(min(lats), max(lats))
        if not point_in_ring((lon, lat), tuple(map(tuple, ring))):
            continue
        out.append({"n": f"{district[:3]}模拟店{len(out)+1:03d}", "c": "食杂店/批发",
                    "d": district, "u": dealer, "lon": round(lon, 6),
                    "lat": round(lat, 6), "direct": False,
                    "dealers": [dealer], "kind": "OK"})
    return out




class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 安静
        pass

    def _send(self, code: int, body: dict | str, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            data = body.encode("utf-8")
        elif isinstance(body, bytes):
            data = body
        else:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._send(200, PAGE.read_text(encoding="utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/pack_status":
            q = dict(kv.split("=", 1) for kv in
                     self.path.split("?")[1:2][0].split("&") if "=" in kv) \
                if "?" in self.path else {}
            rid = unquote(q.get("region", ""))
            sf = DATA_ROOT / rid / "status.json"
            if rid and "/" not in rid and ".." not in rid and sf.exists():
                try:
                    self._send(200, json.loads(sf.read_text(encoding="utf-8")))
                except Exception:  # noqa: BLE001
                    self._send(200, {"status": "creating"})
            else:
                self._send(200, {"status": "ready"})
            return
        if path == "/p1":
            cp = ROOT / "tools" / "p1_visual_page.html"
            self._send(200, cp.read_text(encoding="utf-8"),
                       "text/html; charset=utf-8")
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return
        if path == "/north_desc":
            cp = ROOT / "tools" / "north_desc_page.html"
            self._send(200, cp.read_text(encoding="utf-8"),
                       "text/html; charset=utf-8")
            return
        if path == "/compare":
            cp = ROOT / "tools" / "compare_page.html"
            self._send(200, cp.read_text(encoding="utf-8"),
                       "text/html; charset=utf-8")
            return
        if path == "/fences":
            cp = ROOT / "tools" / "fences_page.html"
            self._send(200, cp.read_text(encoding="utf-8"),
                       "text/html; charset=utf-8")
            return
        with STATE_LOCK:
            pack = _current()
            w = STATE["world"]
            if path == "/api/regions":
                self._send(200, {"regions": _list_regions(),
                                 "current": pack["data_dir"].name})
                return
            if path == "/api/north_desc":
                df = pack["data_dir"] / "north_desc_recon.json"
                self._send(200, json.loads(df.read_text(encoding="utf-8"))
                           if df.exists() else {"error": "run recon first"})
                return
            if path == "/api/bootstrap":
                snap = _world_snapshot(w, pack)
                snap["contracts"] = pack["contracts"]
                snap["kb_version"] = KB.version
                snap["kb_gaps"] = KB.gaps
                snap["meta"]["data_dir"] = pack["data_dir"].name
                self._send(200, snap)
                return
            if path == "/api/p1_visual":
                vf = pack["data_dir"] / "p1_visual.json"
                self._send(200, json.loads(vf.read_text(encoding="utf-8"))
                           if vf.exists() else {"cases": []})
                return
            if path == "/api/p1_metrics":
                mf = Path("/tmp/p1_results.json")
                self._send(200, json.loads(mf.read_text(encoding="utf-8"))
                           if mf.exists() else [])
                return
            if path == "/api/fences":
                cons = {c["dealer_id"]: c for c in pack["contracts"]}
                dealers = []
                for de, fences in sorted(w.fences_by_dealer.items()):
                    if de.startswith("佛山"):
                        continue
                    c = cons.get(de, {})
                    stores = [{"lon": s.lon, "lat": s.lat, "d": s.district}
                              for s in w.stores if de in s.dealers]
                    dealers.append({
                        "name": de,
                        "area_ids": sorted(set(f.area_id for f in fences)),
                        "area_km2": round(sum(f.area_km2 for f in fences), 1),
                        "store_count": len(stores),
                        "rings": [list(map(list, f.ring)) for f in fences],
                        "district": c.get("district", ""),
                        "four_bounds": c.get("four_bounds", {}),
                        "center": list(c.get("center") or ([stores[0]["lon"],
                                     stores[0]["lat"]] if stores else [])),
                        "stores": stores})
                osm = pack["osm"] or {}
                admin = {name: v.get("polys", [])
                         for name, v in (osm.get("districts") or {}).items()}
                sdf = pack["data_dir"] / "osm_subdistricts.json"
                subs = (json.loads(sdf.read_text(encoding="utf-8"))
                        .get("subdistricts", {})) if sdf.exists() else {}
                self._send(200, {"dealers": dealers, "admin": admin,
                                 "subdistricts": subs})
                return
            if path == "/api/dealer_desc":
                df = pack["data_dir"] / "desc_cover_eval.json"
                self._send(200, json.loads(df.read_text(encoding="utf-8"))
                           if df.exists() else [])
                return
            if path == "/api/ledger":
                led: Ledger = STATE["ledger"]
                summ = led.summary()
                for s in summ:
                    g = led.fence_geom(s["owner"])
                    s["rings"] = ([[[round(x, 6), round(y, 6)]
                                    for x, y in g.exterior.coords]]
                                  if g is not None and g.geom_type == "Polygon"
                                  else ([[list(map(list, pp.exterior.coords))]
                                        for pp in g.geoms]
                                        if g is not None else []))
                self._send(200, {"owners": summ,
                                 "total_units": len(led.owner)})
                return
            if path == "/api/yeidai":
                zf = pack["data_dir"] / "haizhu_liwan_zones.json"
                self._send(200, json.loads(zf.read_text(encoding="utf-8"))
                           if zf.exists() else {"zones": []})
                return
            if path == "/api/compare":
                cf = pack["data_dir"] / "compare.json"
                if not cf.exists():
                    self._send(200, {"crs": "WGS84", "version": "V1c",
                                     "missing": True, "items": [],
                                     "debug_cwd": str(Path.cwd()),
                                     "debug_path": str(cf),
                                     "debug_exists": str(cf.exists()),
                                     "hint": "run tools/gen_compare_data.py"})
                    return
                self._send(200, json.loads(cf.read_text(encoding="utf-8")))
                return
            if path == "/api/analysis":
                q = dict(pp.split("=", 1) for pp in
                         self.path.split("?")[1:2][0].split("&") if "=" in pp) \
                    if "?" in self.path else {}
                fence_dealer = unquote(q.get("fence", ""))
                out: dict = {"kinds": w.kind_counts,
                             "gap_summary": classify_gap(w, KB)["summary"]}
                if fence_dealer:
                    fs = w.fences_of(fence_dealer)
                    out["health"] = fence_health(w, fs[0], KB) if fs else None
                else:
                    out["health_rank"] = run_q1(w, KB)[:12]
                self._send(200, out)
                return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        body = self._body()
        if self.path == "/api/create_region":
            name = str(body.get("name", "")).strip()
            bbox = body.get("bbox")  # [south, west, north, east]
            if not name or not isinstance(bbox, list) or len(bbox) != 4:
                self._send(400, {"error": "需要 name 与 bbox=[南,西,北,东]"})
                return
            try:
                bbox = [float(x) for x in bbox]
                assert bbox[0] < bbox[2] and bbox[1] < bbox[3]
                assert -90 <= bbox[0] <= 90 and -180 <= bbox[1] <= 180
            except Exception:  # noqa: BLE001
                self._send(400, {"error": "bbox 非法（应为 南,西,北,东 且南<北西<东）"})
                return
            try:
                d = _create_region(name, bbox)
            except ValueError as e:
                self._send(400, {"error": str(e)})
                return
            self._send(200, {"ok": True, "id": d.name,
                             "note": "后台抓取 OSM 中（约 1-3 分钟），"
                                     "状态见区域列表；抓取完成前生成走降级路径"})
            return
        if self.path == "/api/add_contract":
            from intelligence import geom
            from intelligence.llm import llm_contract_semantics
            from intelligence.world import Fence, Store
            pack = _current()
            w = STATE["world"]
            dealer = str(body.get("dealer_id", "")).strip()
            text = str(body.get("text", "")).strip()
            count = int(body.get("store_count", 60))
            osm = pack["osm"] or {}
            if not dealer or len(dealer) < 4:
                self._send(400, {"error": "dealer_id 至少 4 个字"}); return
            # D14: 同经销商新增围栏块是合法的多块领地（component），不再拒绝
            if not text:
                self._send(400, {"error": "缺少合同描述 text"}); return
            # —— LLM 语义抽取（方向反转 / areas / channels）——
            names = {"rivers": sorted(osm.get("rivers", {}).keys()),
                     "roads": sorted(osm.get("roads", {}).keys()),
                     "districts": sorted(osm.get("districts", {}).keys()),
                     "refs": sorted(osm.get("refs", {}).keys())}
            try:
                sem = llm_contract_semantics(text, names)
            except Exception as e:  # noqa: BLE001
                self._send(400, {"error": f"LLM 语义解析失败: {e}"}); return
            # 校验地标几何存在
            bounds, areas = {}, []
            DIR_MAP = {"以南": "北", "以北": "南", "以东": "西", "以西": "东"}
            catalog_keys = (list(osm.get("roads", {}).keys())
                            + list(osm.get("rivers", {}).keys())
                            + list(osm.get("refs", {}).keys())
                            + list(osm.get("districts", {}).keys()))
            def _norm(nm_raw):
                for k in catalog_keys:
                    if nm_raw == k or nm_raw in k or (len(nm_raw) >= 3 and k in nm_raw):
                        return k
                return None
            for d, nm in sem["bounds"].items():
                if lookup_geometry(nm, osm):
                    bounds[d] = nm
            # 正则兜底：补 LLM 漏抽的「X以Y」条款（如无标点粘连时）
            for m in re.finditer(r"([A-Za-z0-9\u4e00-\u9fff（）()·\-]{2,16}?)(以[东南西北])",
                                 text):
                keep = DIR_MAP.get(m.group(2))
                if not keep or keep in bounds:
                    continue
                nm = _norm(m.group(1))
                if nm and lookup_geometry(nm, osm):
                    bounds[keep] = nm
            for a in sem["areas"]:
                if lookup_geometry(a, osm):
                    areas.append(a)
            # —— 中心点（body 或从 areas/bounds 推）——
            center = body.get("center")
            if not center:
                seed = []
                for a in areas:
                    seed += [p for seg in lookup_geometry(a, osm) for p in seg]
                for nm in bounds.values():
                    seed += [p for seg in lookup_geometry(nm, osm)[:1] for p in seg]
                center = list(geom.centroid(seed)) if seed else list(pack["map_center"])
            # —— 构面：areas 凸包 ∪ 否则用中心小框 ——
            seed_pts = []
            for a in areas:
                seed_pts += [p for seg in lookup_geometry(a, osm) for p in seg]
            if seed_pts:
                poly = geom.convex_hull(seed_pts)
                built_from = f"街道并集凸包（{len(areas)} 个行政单元）"
            else:
                r0 = (max(2.0, count / float(pack["meta"].get(
                    "density_assumption_stores_per_km2", 25))) / math.pi) ** 0.5
                lon0, lat0 = center
                dlon = r0 / 97.0; dlat = r0 / 110.6
                poly = [(lon0-dlon, lat0-dlat), (lon0+dlon, lat0-dlat),
                        (lon0+dlon, lat0+dlat), (lon0-dlon, lat0+dlat)]
                built_from = "中心估算框（无街道时）"
            # —— 道路语义切分：market_partition 引擎（环形/线性/侧向校验）——
            from intelligence import roadsem
            kept = dict(bounds)
            bg = {}
            geoms = {}
            for d, nm in bounds.items():
                segs = lookup_geometry(nm, osm)
                if segs:
                    geoms[nm] = [[list(pt) for pt in seg] for seg in segs]
                    bg[d] = [list(pt) for pt in
                             max(segs, key=lambda s: len(s))]
            from shapely.geometry import Polygon as ShpPolygon
            try:
                sr = roadsem.clip_by_bounds(
                    ShpPolygon(poly), bounds, geoms)
                if sr.polygon is not None and not sr.polygon.is_empty:
                    poly = [list(c) for c in sr.polygon.exterior.coords]
                clipped = [x for x in sr.applied if x.startswith(("北", "南", "东", "西"))]
                recorded = [x for x in sr.applied if x.startswith(("✓", "⚠"))]
                geom_diag = sr.diagnostics
            except Exception as e:  # noqa: BLE001
                clipped = []
                recorded = [f"⚠ 道路语义切分失败({e})，保留街道凸包"]
                geom_diag = {}
            ring = [tuple(pt) for pt in poly]
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            # —— 模拟门店落位（区域无门店时）——
            new_stores = []
            if len(w.stores) == 0 and count > 0:
                lons = [p[0] for p in ring]; lats = [p[1] for p in ring]
                tries = 0
                while len(new_stores) < count and tries < count * 80:
                    tries += 1
                    lon = random.uniform(min(lons), max(lons))
                    lat = random.uniform(min(lats), max(lats))
                    if not point_in_ring((lon, lat), tuple(ring)):
                        continue
                    new_stores.append({"n": f"{dealer[:4]}店{len(new_stores)+1:03d}",
                                       "c": "食杂店/批发", "d": areas[0] if areas else "—",
                                       "u": dealer, "lon": round(lon, 6),
                                       "lat": round(lat, 6), "direct": False,
                                       "dealers": [dealer], "kind": "OK"})
            area_id = f"A{abs(hash(dealer)) % 900000 + 100000}"
            real_area = round(geom.shoelace_area_km2(poly), 2)
            w2 = w.with_stores(
                w.stores + [Store(s["n"], s["c"], s["d"], s["u"], s["lon"],
                                  s["lat"], s["direct"], tuple(s["dealers"]),
                                  s["kind"]) for s in new_stores])
            w2 = w2.with_fences(w2.fences + [
                Fence(area_id, dealer, real_area, tuple(map(tuple, ring)))])
            cols, nbs = _assign_dealer_colors(w2.fences)
            pack["world"] = w2; pack["colors"] = cols; pack["neighbors"] = nbs
            STATE["world"] = w2; STATE["proposal"] = None
            pack["contracts"].append({
                "dealer_id": dealer, "district": (areas[0] if areas else "—"),
                "four_bounds": kept, "areas": areas, "channels": sem["channels"],
                "center": [round(center[0], 6), round(center[1], 6)],
                "reserved_channels": sem["channels"], "store_count": count,
                "raw_text": text})
            _persist_pack(pack)
            self._send(200, {
                "ok": True, "dealer": dealer, "area_km2": real_area,
                "ring": [list(p) for p in ring],
                "bounds": kept, "areas": areas, "channels": sem["channels"],
                "clipped": clipped, "recorded": recorded, "bounds_geometry": bg,
                "built_from": built_from, "semantics": sem["raw"],
                "note": "语义解析→街道凸包→半平面裁剪→草案持久化；渠道条款已记录"
                        "（不参与几何）"})
            return
        if self.path == "/api/switch":
            rid = body.get("region", "")
            target = DATA_ROOT / rid
            if not rid or not target.is_dir() or target.parent != DATA_ROOT:
                self._send(400, {"error": f"未知区域包: {rid}"})
                return
            try:
                with STATE_LOCK:
                    new_state = {"pack": _load_pack(target), "world": None,
                                 "proposal": None}
                    new_state["world"] = new_state["pack"]["world"]
                    STATE.clear()
                    STATE.update(new_state)
            except Exception as e:  # noqa: BLE001
                self._send(400, {"error": f"数据包加载失败: {e}；"
                                          f"先跑 tools/validate_region_pack.py {target}"})
                return
            self._send(200, {"ok": True,
                             "region": STATE["pack"]["region_name"],
                             "kinds": STATE["world"].kind_counts})
            return
        with STATE_LOCK:
            pack = _current()
            w = STATE["world"]
            if self.path == "/api/generate":
                area_id = body.get("area_id")
                dealer = body.get("dealer")
                bounds = {}
                center = None
                # 首选：台账重放（自动描述/手动话术 → 单元并集），零几何切割
                descrows = []
                dcf = pack["data_dir"] / "desc_cover_eval.json"
                if dcf.exists():
                    descrows = json.loads(dcf.read_text(encoding="utf-8"))
                terms = body.get("terms")
                if terms is None:
                    hit = None
                    if area_id:
                        hit = next((x for x in descrows if x.get("area_id") == area_id), None)
                    if hit is None and dealer:
                        hit = next((x for x in descrows if x["dealer"] == dealer), None)
                    if hit:
                        terms = hit["desc"]
                        area_id = area_id or hit.get("area_id")
                if terms:
                    led: Ledger = STATE["ledger"]
                    owner_key = f"{dealer or (area_id or '')}#{area_id or 'manual'}"
                    errt = []
                    for tm in terms:
                        try:
                            led.assign(tm, owner_key)
                        except ValueError:
                            errt.append(tm)
                    sel = set(led.fence_units(owner_key))
                    if sel:
                        u = led.fence_geom(owner_key)
                        rings = ([list(u.exterior.coords)] if u.geom_type == "Polygon"
                                 else [list(p.exterior.coords) for p in u.geoms])
                        self._send(200, {
                            "ring": [list(pp) for pp in rings[0]],
                            "rings": [[list(map(list, pp))] for pp in rings],
                            "area_km2": round(u.area * 11320 * 1.0084, 2),
                            "units": len(sel),
                            "interpretation": "ledger", "draft_quality": "ok",
                            "conflicts": _conflicts([]),
                            "lines_used": {"allocator": "ledger-replay",
                                           "terms": terms, "unresolved": errt},
                            "missing": [], "bounds_geometry": {},
                            "dealer": dealer or owner_key})
                        return
                ce = None
                if area_id:
                    ce = next((c for c in pack["contracts"]
                               if c.get("area_id") == area_id), None)
                if ce:
                    bounds = ce.get("four_bounds") or {}
                    center = ce.get("center")
                    dealer = ce.get("dealer_id", "合同重建围栏")
                if not bounds:
                    bounds = body.get("bounds") or {}
                if not center:
                    center = body.get("center")
                dealer = body.get("dealer") or dealer
                if pack["osm"] is None:
                    self._send(400, {"error": f"数据包缺 osm_parsed.json"
                                              f"（{pack['data_dir']}），四至重建不可用"})
                    return
                origs = w.fences_of(dealer)
                if origs:
                    area_est = w.territory_area_km2(dealer)
                else:
                    sc = next((c["store_count"] for c in pack["contracts"]
                               if c["dealer_id"] == dealer), 0)
                    density = float(pack["meta"].get(
                        "density_assumption_stores_per_km2", 25))
                    area_est = max(2.0, sc / density)
                # V2 单元分配优先：四至名 → 线网锚 → 单元集合（全量路网）
                try:
                    sys.path.insert(0, str(ROOT / "tools"))
                    from unit_allocator import UnitLibrary, allocate
                    lib = UnitLibrary()
                    sel, ugeom, umiss = allocate(lib, bounds or {}, tuple(center))
                    area_u = ugeom.area * 11320 * 1.0084 if ugeom else 0.0
                    if ugeom and 0.3 * area_est <= area_u <= 3 * area_est:
                        self._send(200, {
                            "ring": [list(p) for p in ugeom.exterior.coords],
                            "area_km2": round(area_u, 2),
                            "interpretation": "draft", "draft_quality": "ok",
                            "area_estimate_km2": round(area_est, 1),
                            "conflicts": _conflicts([]),
                            "lines_used": {"allocator": "unit-v2",
                                           "units": len(sel)},
                            "missing": umiss, "bounds_geometry": {},
                            "dealer": dealer})
                        return
                except Exception:
                    pass  # V2 失败 → V1c 兜底
                rr = (area_est / math.pi) ** 0.5
                spec, missing, detail, bounds_geo = {}, [], {}, {}
                r_clip = rr * 1.6
                osm = pack["osm"]
                for d in ("西", "北", "东", "南"):
                    nm = bounds.get(d)
                    if not nm:
                        continue
                    segs = lookup_geometry(nm, osm, center)
                    if not segs:
                        missing.append(f"{d}:{nm}")
                        continue
                    allp = [p for seg in segs for p in seg]
                    anchor = min(allp, key=lambda p: (p[0] - center[0]) ** 2
                                 + (p[1] - center[1]) ** 2)
                    line = next((seg for seg in segs if anchor in seg),
                                max(segs, key=len))
                    tot, cum = 0.0, [0.0]
                    for i in range(1, len(line)):
                        tot += _dist_km(line[i - 1], line[i])
                        cum.append(tot)
                    keep = [i for i, q in enumerate(line)
                            if _dist_km(q, center) <= r_clip]
                    if len(keep) < 2:
                        missing.append(f"{d}:{nm}")
                        continue
                    seg_pts = line[min(keep):max(keep) + 1]
                    fr = cum[min(keep)] / tot if tot > 0 else 0.0
                    to = cum[max(keep)] / tot if tot > 0 else 1.0
                    spec[d] = (nm, fr, to)
                    detail[d] = f"{nm} [{fr:.2f},{to:.2f}]"
                    bounds_geo[d] = [list(p) for p in seg_pts]
                if len(spec) < 3:
                    self._send(400, {"error": f"界线证据不足（{missing}），需人工解释围栏"})
                    return
                # V2 单元分配优先（basic_units_v3_clean 存在时）
                ring = None
                rb = None
                try:
                    sys.path.insert(0, str(ROOT / "tools"))
                    from unit_allocator import UnitLibrary, allocate
                    lib = UnitLibrary()
                    sel, ugeom, umiss = allocate(lib, bounds, tuple(center))
                    area_u = ugeom.area * 11320 * 1.0084 if ugeom else 0.0
                    if ugeom and 0.3 * area_est <= area_u <= 3 * area_est:
                        rb = {"ring": list(ugeom.exterior.coords),
                              "area_km2": ugeom.area * 11320 * 1.0084}
                        detail["allocator"] = "unit-v2"
                except Exception:
                    rb = None
                if rb is None:
                    try:
                        rb = build_from_landmark_ratios(dealer, spec, tuple(center), osm)
                    except Exception as e:  # noqa: BLE001
                        self._send(400, {"error": f"重建失败: {e}; missing={missing}"})
                        return
                    if "error" in rb:
                        self._send(400, {"error": f"重建失败: {rb['error']}; "
                                                  f"missing={missing}"})
                        return
                ring = rb["ring"]
                lons = [p[0] for p in ring]; lats = [p[1] for p in ring]
                cand = [s for s in w.stores
                        if min(lons) <= s.lon <= max(lons)
                        and min(lats) <= s.lat <= max(lats)]
                in_fence = [s for s in cand
                            if point_in_ring((s.lon, s.lat), tuple(map(tuple, ring)))]
                quality = ("ok" if 0.3 * area_est <= rb["area_km2"] <= 3 * area_est
                           else "low")
                self._send(200, {
                    "ring": [list(p) for p in ring],
                    "area_km2": round(rb["area_km2"], 2),
                    "interpretation": "draft", "draft_quality": quality,
                    "area_estimate_km2": round(area_est, 1),
                    "conflicts": _conflicts(in_fence),
                    "lines_used": detail, "missing": missing,
                    "bounds_geometry": bounds_geo, "dealer": dealer})
                return
            if self.path == "/api/ledger_cmd":
                q = str(body.get("text", ""))
                led: Ledger = STATE["ledger"]
                try:
                    owner, n = led.execute(q)
                except ValueError as e:
                    self._send(400, {"error": str(e)})
                    return
                self._send(200, {"message": f"{owner} 名下 {n} 单元",
                                 "summary": led.summary()})
                return
            if self.path == "/api/fence_search":
                q = str(body.get("text", ""))
                regd = json.load(open(str(ROOT / "data" / "gz" / "fence_registry.json"),
                                      encoding="utf-8"))["registry"]
                results = []
                for r in regd:
                    score = 0.0
                    matched = []
                    prof = r["profile"]
                    for road in r["boundary_roads"]:
                        if road and road in q:
                            score += 3; matched.append(road)
                    for st in r["streets"]:
                        core = st.split("·")[-1].replace("街道", "").replace("镇", "")
                        if core and core in q:
                            score += 3; matched.append(st)
                    for dn in r["districts"]:
                        if dn in q:
                            score += 1; matched.append(dn)
                    for nb in r["neighbors"]:
                        if nb in q:
                            score += 2; matched.append(nb)
                    import re as _re
                    m = _re.search(r"(\d+(?:\.\d+)?)\s*(?:平方公里|km²|km2|平方公里)", q)
                    if m:
                        v = float(m.group(1))
                        if 0.6 * v <= r["area_km2"] <= 1.6 * v:
                            score += 1; matched.append(f"~{v}km²")
                    if score > 0:
                        results.append({"area_id": r["area_id"],
                                        "name": r["dealer"], "score": round(score, 1),
                                        "area_km2": r["area_km2"],
                                        "matched": matched[:6]})
                results.sort(key=lambda x: -x["score"])
                self._send(200, {"results": results[:8]})
                return
            if self.path == "/api/yeidai_adjust":
                text = str(body.get("text", ""))
                st: YeidaiState = STATE["yeidai"]
                parser = "rules"
                op = None
                err1 = None
                try:
                    op = st.parse_op(text)
                except ValueError as e1:
                    err1 = str(e1)
                    try:
                        op = llm_parse_op(text, st.zones)
                        op = st.resolve_llm(op)
                        parser = "llm"
                    except Exception as e2:
                        self._send(400, {"error": f"规则: {err1} ｜ LLM: {e2}"})
                        return
                msg = st.apply(op)
                self._send(200, {"message": f"[{parser}] {msg}",
                                 "zones": st.snapshot()})
                return
            if self.path == "/api/yeidai_apply":
                st: YeidaiState = STATE["yeidai"]
                snap = st.snapshot()
                json.dump({"crs": "WGS84", "zones": snap},
                          open(str(ROOT / "data" / "gz" / "haizhu_liwan_zones.json"),
                               "w", encoding="utf-8"), ensure_ascii=False)
                self._send(200, {"message": "已落盘", "zones": snap})
                return
            if self.path == "/api/yeidai_reset":
                STATE["yeidai"] = YeidaiState()
                self._send(200, {"message": "已还原",
                                 "zones": STATE["yeidai"].snapshot()})
                return
            if self.path == "/api/adjust":
                text = body.get("text", "")
                p = None
                parser = "rules"
                llm_err = None
                try:
                    p = parse_and_propose(w, KB, text)
                except AdjustError as e1:  # noqa: BLE001 → LLM 兜底自由句式
                    llm_err = f"{type(e1).__name__}: {e1}"
                    try:
                        p = llm_parse_command(w, KB, text)
                        parser = "llm"
                    except Exception as e2:  # noqa: BLE001
                        msg = str(e1) + f" ｜ LLM 侧: {e2}"
                        self._send(400, {"error": msg})
                        return
                STATE["proposal"] = p
                imp = p.impact
                become_oof = sum(v for k, v in imp["moved_kind_delta"].items()
                                 if k.split(" → ")[0] in ("OK", "DIRECT_IN")
                                 and k.endswith("→ OOF"))
                conflicts = {"become_oof_n": become_oof,
                             "multi_in_moved": sum(1 for s in p.stores
                                                   if s.kind == "MULTI")}
                self._send(200, {
                    "parser": parser,
                    "proposal": {"src": p.src_dealer, "dst": p.dst_dealer,
                                 "area": p.area_desc, "moved": len(p.stores)},
                    "area": imp.get("area", {}),
                    "sub_rings": p.sub_rings,
                    "source_after": imp["source_after"],
                    "target_after": imp["target_after"],
                    "moved_kind_delta": imp["moved_kind_delta"],
                    "moved_sample": imp["moved_sample"][:6],
                    "signals": imp["signals"],
                    "risks": imp["risks"],
                    "evidence": imp["evidence"],
                    "materiality": imp["materiality"],
                    "conflicts": conflicts,
                })
                return
            if self.path == "/api/apply":
                if not STATE["proposal"]:
                    self._send(400, {"error": "没有待应用的提案"})
                    return
                w2 = apply_proposal(w, STATE["proposal"])
                cols, nbs = _assign_dealer_colors(w2.fences)
                pack["colors"] = cols
                pack["neighbors"] = nbs
                pack["fence_areas"] = {
                    d: round(sum(g.area_km2 for g in fs), 2)
                    for d, fs in w2.fences_by_dealer.items()}
                pack["fence_blocks"] = {
                    d: len(fs) for d, fs in w2.fences_by_dealer.items()}
                STATE["world"] = w2
                STATE["proposal"] = None
                self._send(200, {"ok": True, "kinds": w2.kind_counts,
                                 "areas": pack["fence_areas"]})
                return
            if self.path == "/api/reject":
                STATE["proposal"] = None
                self._send(200, {"ok": True})
                return
            if self.path == "/api/verify_vision":
                from intelligence import vision
                ring = [(float(p[0]), float(p[1]))
                        for p in body.get("ring", [])]
                bl = {k: [(float(q[0]), float(q[1])) for q in v]
                      for k, v in (body.get("bounds_geometry") or {}).items()}
                text = str(body.get("text", "") or "")
                inside = [s for s in w.stores
                          if s.dealers and point_in_ring((s.lon, s.lat), tuple(ring))]
                png = vision.render_verify_png(
                    ring, bl, [(s.lon, s.lat, s.kind) for s in inside])
                ts = time.strftime("%Y%m%d-%H%M%S")
                vdir = pack["data_dir"] / "verify"
                vdir.mkdir(exist_ok=True)
                safe = re.sub(r"[^\w\u4e00-\u9fff]+", "",
                              str(body.get("dealer", "围栏")))[:20] or "围栏"
                vpath = vdir / f"{ts}-{safe}.png"
                vpath.write_bytes(png)
                if not text:
                    text = "；".join(f"{d}界={nm}" for d, nm
                                     in (body.get("lines_used") or {}).items())
                try:
                    verdict = vision.verify_fence(
                        png, text, body.get("lines_used") or {})
                except Exception as e:  # noqa: BLE001 — 路由不崩
                    verdict = {"verdict": "存疑",
                               "findings": [f"视觉核验异常: {e}"],
                               "note": "已存图，待人工或稍后重试"}
                if verdict.get("verdict") == "存疑" and "API 失败" in str(
                        verdict.get("findings")):
                    pass  # 限流：图仍返回，前端显示"点此重试"
                import base64 as b64mod
                self._send(200, {**verdict,
                    "image": "data:image/png;base64,"
                             + b64mod.b64encode(png).decode(),
                    "stores_in": len(inside), "saved": vpath.name})
                return
            if self.path == "/api/reset":
                STATE["world"] = pack["world"]
                STATE["proposal"] = None
                self._send(200, {"ok": True})
                return
        self._send(404, {"error": "not found"})


if __name__ == "__main__":
    pk = _current()
    print(f"SRAF demo[{pk['region_name']}]: http://127.0.0.1:{PORT}  "
          f"(KB {KB.version}, {len(pk['world'].fences)} fences / "
          f"{len(pk['world'].stores)} stores / {len(pk['contracts'])} contracts, "
          f"data={pk['data_dir']})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
