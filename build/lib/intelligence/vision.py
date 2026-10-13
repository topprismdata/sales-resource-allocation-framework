"""视觉终审：把生成的围栏渲染成 PNG（纯 stdlib），交 GLM-5.3-Flash 视觉核验。

render_verify_png(ring, bound_lines, stores) -> png bytes
  ring:        [(lon,lat),…]         生成的围栏
  bound_lines: {"北":[(lon,lat)…], …} 合同界线（缺失方向不出现在图中）
  stores:      [(lon,lat,kind)]      围栏内门店
verify_fence(png_b64, contract_text, bounds_desc) -> dict
  {verdict: 通过|存疑|不通过, findings: […], note: str}
模型: GLM-5.3-Flash（zhipu coding-plan 凭证来自 ~/.omp/agent/agent.db）
"""
from __future__ import annotations

import base64
import json
import sqlite3
import re
import struct
import urllib.request
import zlib
from pathlib import Path

KIND_COLOR = {"OK": (46, 125, 50), "OOF": (239, 108, 0), "DIRECT_IN": (21, 101, 192),
              "DIRECT": (158, 158, 158), "GAP": (198, 40, 40), "MULTI": (106, 27, 154)}
BOUND_COLOR = {"北": (25, 118, 210), "南": (46, 125, 50),
               "东": (198, 40, 40), "西": (230, 126, 0)}
FENCE_FILL = (255, 138, 128)     # 弱粉
FENCE_LINE = (40, 40, 40)


def _png_bytes(px, w, h) -> bytes:
    raw = b"".join(b"\x00" + bytes(v for x in range(w) for v in px[y][x])
                   for y in range(h))
    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _lonlat_to_px(points, view, W, H, pad=40):
    """view=(lon0,lon1,lat0,lat1) → 像素坐标列表（y 翻转）。"""
    lon0, lon1, lat0, lat1 = view
    span_x = max(lon1 - lon0, 1e-9); span_y = max(lat1 - lat0, 1e-9)
    scale = min((W - 2 * pad) / span_x, (H - 2 * pad) / span_y)
    ox = (W - span_x * scale) / 2; oy = (H - span_y * scale) / 2
    out = []
    for lon, lat in points:
        x = int(ox + (lon - lon0) * scale)
        y = int(H - (oy + (lat - lat0) * scale))
        out.append((x, y))
    return out


def _draw_line(px, pts, color, thickness=2):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        steps = max(abs(x2 - x1), abs(y2 - y1)) * 2 + 1
        for i in range(steps + 1):
            x = int(x1 + (x2 - x1) * i / steps)
            y = int(y1 + (y2 - y1) * i / steps)
            for dy in range(-thickness // 2, thickness // 2 + 1):
                for dx in range(-thickness // 2, thickness // 2 + 1):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < len(px[0]) and 0 <= yy < len(px):
                        px[yy][xx] = color


def _draw_polygon_fill(px, pts, color, alpha):
    """扫描线偶奇填充 + 混合。"""
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    for y in range(max(0, min(ys)), min(len(px), max(ys) + 1)):
        xs = []
        n = len(pts)
        for i in range(n):
            x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(int(x1 + (x2 - x1) * (y - y1) / (y2 - y1)))
        xs.sort()
        for a, b in zip(xs[::2], xs[1::2]):
            for x in range(max(0, a), min(len(px[0]), b + 1)):
                c = px[y][x]
                px[y][x] = tuple(int(c[i] * (1 - alpha) + color[i] * alpha)
                                 for i in range(3))


def render_verify_png(ring, bound_lines, stores) -> bytes:
    """ring=[(lon,lat)…]; bound_lines={方向:[(lon,lat)…]}; stores=[(lon,lat,kind)]"""
    W, H = 1000, 760
    all_pts = list(ring) + [p for seg in bound_lines.values() for p in seg] \
        + [(lon, lat) for lon, lat, _ in stores]
    lons = [p[0] for p in all_pts]; lats = [p[1] for p in all_pts]
    pad_deg = 0.004
    view = (min(lons) - pad_deg, max(lons) + pad_deg,
            min(lats) - pad_deg, max(lats) + pad_deg)
    px = [[(255, 255, 255)] * W for _ in range(H)]
    # 界线（底层，粗）
    for d, seg in bound_lines.items():
        pts = _lonlat_to_px(seg, view, W, H)
        _draw_line(px, pts, BOUND_COLOR.get(d, (90, 90, 90)), thickness=4)
    # 围栏：填充 + 边界
    rp = _lonlat_to_px(ring, view, W, H)
    _draw_polygon_fill(px, rp, FENCE_FILL, 0.45)
    _draw_line(px, rp + [rp[0]], FENCE_LINE, thickness=3)
    # 门店点
    for lon, lat, kind in stores:
        x, y = _lonlat_to_px([(lon, lat)], view, W, H)[0]
        c = KIND_COLOR.get(kind, (90, 90, 90))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                xx, yy = x + dx, y + dy
                if 0 <= xx < W and 0 <= yy < H:
                    px[yy][xx] = c
    return _png_bytes(px, W, H)


def _zhipu_key() -> str:
    db = sqlite3.connect(str(Path.home() / ".omp" / "agent" / "agent.db"))
    row = db.execute("select data from auth_credentials "
                     "where provider='zhipu-coding-plan' limit 1").fetchone()
    return json.loads(row[0])["key"]



def _vision_conf() -> dict:
    import os
    path = Path(os.environ.get("SRAF_VISION_CONFIG",
                               str(Path.home() / ".sraf" / "vision.json")))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _call_vision_channel(endpoint, key, model, ua, png_b64, prompt, timeout=180):
    """OpenAI 兼容 /chat/completions + image_url 内容块。"""
    import ssl
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl._create_default_https_context
    body = {"model": model, "max_tokens": 4000, "messages": [{
        "role": "user", "content": [
            {"type": "image_url",
             "image_url": {"url": f"data:image/png;base64,{png_b64}"}},
            {"type": "text", "text": prompt}]}]}
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key, "User-Agent": ua})
    r = json.load(urllib.request.urlopen(req, timeout=timeout, context=ctx))
    return r.get("choices", [{}])[0].get("message", {}).get("content", "")


def _glm_vision_fallback(png_b64, prompt):
    key = _zhipu_key()
    import ssl
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl._create_unverified_context()  # noqa: SLF001
    body = {"model": "glm-5.3-flash", "max_tokens": 4000, "messages": [{
        "role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{png_b64}"}},
            {"type": "text", "text": prompt}]}]}
    req = urllib.request.Request(
        "https://open.bigmodel.cn/api/coding/paas/v4/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    r = json.load(urllib.request.urlopen(req, timeout=180, context=ctx))
    msg = r.get("choices", [{}])[0].get("message", {})
    return (msg.get("content") or msg.get("reasoning_content") or "").strip()


def verify_fence(png: bytes, contract_text: str, bounds_desc: dict) -> dict:
    """GLM-5.3-Flash 视觉核验。bounds_desc: {"北":"地标名",…}"""
    from pathlib import Path
    key = _zhipu_key()
    b64 = base64.b64encode(png).decode()
    bd = "；".join(f"{d}界={nm}" for d, nm in bounds_desc.items())
    prompt = (
        "你是经销商合同围栏的视觉审核员。图为系统根据合同四至描述自动生成的围栏示意图：\n"
        "- 粉色半透明区域 = 生成的围栏\n"
        "- 彩色粗线 = 解析出的四条合同界线（蓝=北界 绿=南界 红=东界 橙=西界）\n"
        "- 彩色小点 = 围栏内门店\n\n"
        f"合同描述：{contract_text or '（结构化四至）'}\n"
        f"解析出的边界：{bd or '（无）'}\n\n"
        "请核验：1) 围栏形状与四条界线的位置关系是否合理（如北界应在围栏北侧）；\n"
        "2) 围栏是否明显偏离任何一条界线；3) 是否存在围栏越过某条界线的情况。\n"
        '只输出 JSON：{"verdict": "通过|存疑|不通过", '
        '"findings": ["逐条判断…"], "note": "一句话总结"}')
    import time as _t
    png_b64 = base64.b64encode(png).decode()
    cfg = _vision_conf()
    txt = ""
    err = None
    # 通道 1：GMI M3 视觉（独立配额，不与本 agent 抢）
    if cfg.get("api_key"):
        for attempt in range(3):
            try:
                txt = _call_vision_channel(
                    cfg["endpoint"], cfg["api_key"], cfg.get("model", "MiniMaxAI/MiniMax-M3"),
                    cfg.get("user_agent", "curl/8.6.0"), png_b64, prompt)
                break
            except Exception as e:  # noqa: BLE001
                err = e
                if getattr(e, "code", None) in (429, 500, 502, 503):
                    _t.sleep(15 * (attempt + 1))
                    continue
                break
    # 通道 2：GLM coding-plan（降级，可能与本 agent 抢配额）
    if not txt:
        try:
            txt = _glm_vision_fallback(png_b64, prompt)
        except Exception as e:  # noqa: BLE001
            err = err or e
    txt = (txt or "").replace("```json", "").replace("```", "").strip()
    m = re.search(r"\{.*\}", txt, re.S) if (txt := txt) else None
    if not m:
        return {"verdict": "存疑", "findings": [f"视觉未返回结构化结果: {err or txt[:120]}"],
                "note": "已存图待人工或重试", "debug": {"raw": txt[:300]}}
    return json.loads(m.group(0))
