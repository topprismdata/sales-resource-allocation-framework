"""LLM 语义解析（MiniMax-M3，经本地 Anthropic 兼容代理）。

角色边界（04 §23）：LLM 只做「自然语言 → 结构化意图」，执行/校验全部
由确定性代码完成——LLM 永远不直接改世界。
凭证来源：~/.claude/settings.json 的 env（ANTHROPIC_BASE_URL/AUTH_TOKEN），
可用环境变量 SRAF_LLM_MODEL 覆盖模型名（默认 MiniMax-M3）。
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

_CONF = Path.home() / ".claude" / "settings.json"
_MAX_TOKENS = 4000


def _conf() -> tuple[str, str, str]:
    env = json.load(open(_CONF, encoding="utf-8")).get("env", {})
    base = os.environ.get("ANTHROPIC_BASE_URL", env["ANTHROPIC_BASE_URL"]).rstrip("/")
    tok = os.environ.get("ANTHROPIC_AUTH_TOKEN", env["ANTHROPIC_AUTH_TOKEN"])
    model = os.environ.get("SRAF_LLM_MODEL", "MiniMax-M3")
    return base, tok, model


def chat(prompt: str, timeout: int = 60) -> str:
    base, tok, model = _conf()
    req = urllib.request.Request(
        base + "/v1/messages",
        data=json.dumps({"model": model, "max_tokens": _MAX_TOKENS,
                         "messages": [{"role": "user", "content": prompt}]}).encode(),
        headers={"Content-Type": "application/json", "x-api-key": tok,
                 "Authorization": "Bearer " + tok,
                 "anthropic-version": "2023-06-01"})
    r = json.load(urllib.request.urlopen(req, timeout=timeout))
    return "".join(b.get("text", "") for b in r.get("content", [])
                   if b.get("type") == "text").strip()


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"LLM 未返回 JSON: {text[:120]}")
    return json.loads(m.group(0))


def llm_parse_command(world, kb, text: str):
    """区域调整 NL 指令 → 结构化意图 → 确定性校验 → Proposal（对象=片区）。"""
    from .adjust import AdjustError, _match_dealer, build_proposal
    dealers = sorted({f.dealer for f in world.fences})
    districts = sorted({s.district for s in world.stores if s.district})
    prompt = (
        "你是经销商区域调整助手。把用户的中文指令解析为 JSON，只输出 JSON，不要解释。\n"
        '动作一（划转）格式: {"action": "move", "area": str, "src": str, "dst": str}\n'
        "- area: 被划转的片区描述——可选值：整个区域 / 东部片区 / 南部片区 / "
        "西部片区 / 北部片区 / 某个区名（如 增城区）；未指明则填\"整个区域\"\n"
        '动作二（沿路重新分配）格式: {"action": "split", "src": str, "road": str, '
        '"side": "east|west|south|north", "dst": str}\n'
        '- 触发词：沿着/沿 某路 分开/分割/一分为二。road=路名（如 花莞高速），'
        'side=用户要划出的那一侧（西半边→west）。\n'
        '- split 的 dst：承接方经销商全称；若用户说"给新的经销商/先空着/还没定/无承接方"，'
        'dst 填空字符串 ""（表示置为无主待分配）。注意：dst 未在清单中不是错误，'
        '只要用户表达了"新经销商/空着"的意图就填 ""。\n'
        "- src（及 move 的 dst）: 必须取下方经销商清单中能唯一定位的子串"
        "（至少 4 个字），禁止照抄口语简称\n"
        "注意：语义是区域为主，门店是附带效果（「甲商贸不做了」→ "
        'src=甲商贸全称, area=整个区域, dst=承接方）\n'
        '若无法确定 src，输出 {"action": "unknown", "reason": "一句话原因"}\n\n'
        "经销商清单:\n" + "\n".join(dealers) +
        f"\n\n区名清单: {districts}\n\n用户指令: {text}"
    )
    intent, last_err = None, None
    for _attempt in range(2):
        try:
            intent = _extract_json(chat(prompt))
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
    if intent is None:
        raise AdjustError(f"LLM 解析失败: {last_err}")
    if intent.get("action") not in ("move", "split"):
        raise AdjustError(f"无法理解该指令（LLM: {intent.get('reason', '不支持的动作')}）")

    def _clean(s: str) -> str:
        s = str(s).strip().strip("「」\"'")
        for suf in ("的门店", "的店", "的围栏", "门店", "经销商", "的区域", "区域"):
            if s.endswith(suf):
                s = s[: -len(suf)]
        return s

    src = _match_dealer(world, _clean(intent.get("src", "")))
    if intent.get("action") == "split":
        from .adjust import build_split_proposal
        road = str(intent.get("road", "")).strip()
        if not road:
            raise AdjustError("沿路重新分配缺少路名")
        side = str(intent.get("side", "west")).strip().lower()
        if side not in ("east", "west", "south", "north"):
            side = {"东": "east", "西": "west", "南": "south", "北": "north"}.get(side[:1], "west")
        dst_name = _clean(intent.get("dst", ""))
        dst = _match_dealer(world, dst_name) if dst_name else None
        return build_split_proposal(world, kb, text, src, road, side, dst, "llm")
    dst = _match_dealer(world, _clean(intent.get("dst", "")))
    if src.dealer == dst.dealer:
        raise AdjustError("source 与 target 是同一经销商")
    area = str(intent.get("area", "")).strip() or "整个区域"
    try:
        return build_proposal(world, kb, text, src, dst, area, "llm")
    except AdjustError:
        if area != "整个区域":
            return build_proposal(world, kb, text, src, dst, "全部", "llm")
        raise


def llm_contract_semantics(text: str, landmark_names: dict) -> dict:
    """合同自由描述 → 语义结构。处理三类难点：
    1 方向反转：「G2504以南」→ 区域在 G2504 南边 → G2504 是区域的【北界】
    2 区域条款：「康桥街道、半山街道」→ areas（围栏须覆盖这些行政单元）
    3 渠道条款：「五金大世界批发市场传统渠道」→ channels（非几何，业务备注）

    返回 {"bounds": {方向: 地标名}, "areas": [...], "channels": [...], "raw": {...}}
    landmark_names: {"rivers","roads","districts","refs"}"""
    def _in_text(k: str) -> bool:
        if len(k) >= 2 and k in text:
            return True
        # 后缀裁剪核心匹配：上塘高架路 → 上塘高架
        for cut in (1, 2, 3, 4):
            if len(k) - cut >= 2 and k[:-cut] in text:
                return True
        return False

    def _pick(cat, cap):
        hits = [k for k in landmark_names.get(cat, []) if _in_text(k)]
        return "、".join(hits[:cap])

    catalog = (
        f"编号道路(如G2504): {_pick('refs', 40)}\n"
        f"河流: {_pick('rivers', 60)}\n"
        f"道路: {_pick('roads', 60)}\n"
        f"街道/区县: {_pick('districts', 60)}")
    prompt = (
        "你是经销商合同地理语义解析助手。从合同描述抽取结构，只输出 JSON：\n"
        '{"bounds": {"北":地标,"南":地标,"东":地标,"西":地标}, '
        '"areas":[街道或区县名], "channels":[市场或渠道名]}\n\n'
        "关键规则——「A以X」表示【区域在A的X方向】，即A是区域相反侧的界：\n"
        '  "G2504以南" → 区域在G2504南边 → G2504 是区域的【北界】，bounds.北=G2504\n'
        '  "上塘高架以东" → 区域在其东 → 上塘高架=【西界】\n'
        '  "留石高架以北" → 区域在其北 → 留石高架=【南界】\n'
        "- bounds 的值必须逐字取自目录（编号用 G2504 这种；街道用目录原名）\n"
        "- 「康桥街道、半山街道」这类并列行政区 → 放入 areas\n"
        "- 「XX批发市场传统渠道」等非道路/行政的市场渠道 → 放入 channels\n"
        "- 未提到的键省略；无法解析返回 {\"bounds\":{}}\n\n"
        f"地标目录:\n{catalog}\n\n合同描述: {text}")
    try:
        out = _extract_json(chat(prompt))
    except Exception as e:  # noqa: BLE001 — 上层 add_contract 按通用 Exception 处理
        raise ValueError(f"LLM 语义解析失败: {e}") from e
    b = out.get("bounds", {}) if isinstance(out.get("bounds"), dict) else {}
    return {"bounds": {d: str(v).strip() for d, v in b.items()
                       if d in ("北", "南", "东", "西") and v},
            "areas": [str(x).strip() for x in out.get("areas", []) if x],
            "channels": [str(x).strip() for x in out.get("channels", []) if x],
            "raw": out}


def llm_four_bounds(text: str, landmark_names: dict) -> dict:
    """（兼容旧接口）自由描述 → {方向: 地标名}。"""
    return llm_contract_semantics(text, landmark_names)["bounds"]


