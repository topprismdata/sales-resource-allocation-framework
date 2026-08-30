# -*- coding: utf-8 -*-
"""04_nl2rule.py — T-401：P4 确定性中文规则解析器（规则优先主路径，D12）。

职责边界：
- 把受支持的中文街道/区县表达确定性编译为 CONTRACTS v1.7 §四原语 DSL 树
  （in_street / in_district / union / minus），全过程不调用 LLM、不发起
  网络请求、不处理坐标、不做几何计算、不自行求值单元。
- 名称解析完全复用 ``03_dsl.py`` 的三级解析（resolve_street /
  resolve_district：精确 → 去末尾后缀 → 包含；唯一才成功），简称一律
  规范化回填正式名；绝不复制/改写/放宽 03 的解析器与校验器。
- 解析成功后必须通过 ``03_dsl.validate_rule`` 的最终结构校验才返回。

冻结语法（T-401 卡载，不得自行扩展）：
    ATOM
    ATOM (和|、|加上|以及) ATOM [...]
    BASE 不含 EXCLUSION_LIST
    BASE 除 EXCLUSION_LIST 外
    除 EXCLUSION_LIST 外，BASE
- ATOM：一个且仅一个街道名或区县名（正式全名或可唯一解析的简称）。
- BASE / EXCLUSION_LIST：ATOM 或只含并集连接词的 ATOM 列表。
- 全表达式外允许一次无业务含义包装：前缀 范围为/覆盖/包括/选择/负责，
  后缀 范围/区域/片区；去包装后仍须完整匹配冻结语法。
- 并集规范化为单个扁平 union；保持文本顺序；相同规范节点按首次出现
  去重；去重后只剩一个节点则直接返回该节点。
- A不含B / A除B外 / 除B外，A 都规范化为 minus(parse(A), parse(B))。
- 全角/半角逗号仅作为差集模板 ``除…外，BASE`` 中的模板标点，可有可无；
  其他位置的逗号/空格/括号等一律视为未知残余文字，整体失败。

失败纪律：空文本、非字符串、纯标点、未知名称、歧义简称（单表内或跨
街道/区县类型）、连接词两侧缺项、多个差集标记、差集嵌套、括号、坐标、
WKT、side_of/near 意图、任何未完整消费的残余文字，均抛
``RuleParseError``（中文，含原文与失败原因），绝不猜测、绝不忽略残余。

只读纪律：不修改传入的 ``text``、``ctx``、街道/区县行对象；不写任何
文件；不访问网络。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# 按相邻文件路径加载 03_dsl（文件名以数字开头，无法常规 import）。
# 卡载要求：不得写死绝对路径，必须基于本文件所在目录解析。
# ---------------------------------------------------------------------------

_DSL_PATH = Path(__file__).resolve().parent / "03_dsl.py"
_dsl_spec = importlib.util.spec_from_file_location("sraf_pilot_03_dsl", _DSL_PATH)
dsl = importlib.util.module_from_spec(_dsl_spec)
_dsl_spec.loader.exec_module(dsl)


# ---------------------------------------------------------------------------
# 异常（T-401 卡载冻结接口）
# ---------------------------------------------------------------------------


class Nl2RuleError(Exception):
    """中文 NL→规则层错误基类。"""


class RuleParseError(Nl2RuleError):
    """文本无法确定性地完整编译为四原语 DSL 时抛出；消息含原文与失败原因。"""


# ---------------------------------------------------------------------------
# 冻结词表（与 T-401 卡载语法逐字对齐，禁止放宽）
# ---------------------------------------------------------------------------

_UNION_CONNS = ("、", "和", "加上", "以及")
_WRAP_PREFIXES = ("范围为", "覆盖", "包括", "选择", "负责")
_WRAP_SUFFIXES = ("范围", "区域", "片区")
_NEGATION = "不含"
_EXCLUSIVE = "除"
_EXCLUSIVE_END = "外"
_COMMAS = ("，", ",")  # 全角/半角逗号：仅作差集模板标点

# 切分方案数防御上限：合法表达切分基本唯一，超限即视为歧义过大而失败，
# 绝不猜测取其一。
_MAX_SOLUTIONS = 64


# ---------------------------------------------------------------------------
# 入口（T-401 卡载冻结接口）
# ---------------------------------------------------------------------------


def parse_rule_deterministic(text: str, ctx: dict) -> dict:
    """把受支持的中文规则文本确定性编译为四原语 DSL 树。

    成功返回新的 DSL dict（并已通过 ``03_dsl.validate_rule`` 校验）；
    无法完整、唯一地解析时抛 ``RuleParseError``（中文，含原文与原因）。
    上下文结构不合法时抛 ``Nl2RuleError``。
    """
    if not isinstance(text, str):
        raise RuleParseError(
            f"规则文本必须是非空字符串，实际为 {type(text).__name__}：{text!r}"
        )
    stripped = text.strip()
    if not stripped:
        raise RuleParseError(f"规则文本去除首尾空白后为空，无法解析；原文：『{text}』")

    streets = ctx.get("streets") if isinstance(ctx, dict) else None
    districts = ctx.get("districts") if isinstance(ctx, dict) else None
    if not isinstance(streets, list) or not isinstance(districts, list):
        raise Nl2RuleError(
            "解析上下文不合法：ctx 必须提供 streets / districts 两个行表（list）"
        )

    # 枚举包装剥离方案：不剥 / 剥一次前缀 / 剥一次后缀 / 前后各剥一次。
    # 每种方案独立完整解析；结果唯一才接受，多种不同结果即歧义失败。
    results: dict[str, dict] = {}
    reasons: list[str] = []
    for variant in _unwrap_variants(stripped):
        try:
            rule = _parse_core(variant, streets, districts)
        except RuleParseError as exc:
            reasons.append(str(exc))
            continue
        key = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        results.setdefault(key, rule)

    if not results:
        detail = "；".join(dict.fromkeys(reasons))
        raise RuleParseError(f"无法解析规则：{detail}；原文：『{text}』")
    if len(results) > 1:
        raise RuleParseError(
            f"规则文本存在 {len(results)} 种不同解析结果，拒绝猜测；原文：『{text}』"
        )

    rule = next(iter(results.values()))
    try:
        dsl.validate_rule(rule)
    except dsl.DslError as exc:  # 防御：解析器构造的树必须总能通过 03 校验
        raise Nl2RuleError(f"内部错误：解析产物未通过 03_dsl 校验：{exc}") from exc
    return rule


# ---------------------------------------------------------------------------
# 包装剥离
# ---------------------------------------------------------------------------


def _unwrap_variants(s: str) -> list[str]:
    """枚举去包装变体：不剥 / 剥一次前缀 / 剥一次后缀 / 前后各剥一次。

    只剥词表内的固定词、各最多一次；其余一切文字留给核心解析器按残余
    文字处理。返回去重后的非空候选（已再去首尾空白）。
    """
    variants = {s}
    for prefix in _WRAP_PREFIXES:
        if s.startswith(prefix):
            variants.add(s[len(prefix):])
    expanded = set(variants)
    for v in variants:
        for suffix in _WRAP_SUFFIXES:
            if v.endswith(suffix) and len(v) > len(suffix):
                expanded.add(v[: -len(suffix)])
    return sorted({v.strip() for v in expanded if v.strip()})


# ---------------------------------------------------------------------------
# 核心解析：差集模板识别 + 并集表达式分词
# ---------------------------------------------------------------------------


def _parse_core(s: str, streets: list, districts: list) -> dict:
    """解析已去包装文本：识别至多一个差集标记，否则按并集表达式解析。"""
    count_neg = s.count(_NEGATION)
    count_exc = s.count(_EXCLUSIVE)
    if count_neg + count_exc > 1:
        raise RuleParseError(
            f"出现多个差集标记（不含/除…外），差集嵌套不受支持；文本：『{s}』"
        )

    if count_neg == 1:
        pos = s.index(_NEGATION)
        base_text = s[:pos]
        excl_text = s[pos + len(_NEGATION):]
        if not base_text:
            raise RuleParseError(f"『不含』之前缺少主体表达式；文本：『{s}』")
        if not excl_text:
            raise RuleParseError(f"『不含』之后缺少排除项；文本：『{s}』")
        base = _parse_side(base_text, "被减主体", streets, districts)
        excl = _parse_side(excl_text, "排除列表", streets, districts)
        return {"op": "minus", "args": [base, excl]}

    if count_exc == 1:
        i = s.index(_EXCLUSIVE)
        j = s.find(_EXCLUSIVE_END, i + 1)
        if j == -1:
            raise RuleParseError(f"『除』之后未找到配对的『外』；文本：『{s}』")
        excl_text = s[i + 1:j]
        if i == 0:
            # 前置型：除 EXCLUSION_LIST 外[，] BASE
            rest = s[j + 1:]
            if rest[:1] in _COMMAS:
                rest = rest[1:]
            base_text = rest
            if not base_text:
                raise RuleParseError(f"『除…外，』之后缺少主体表达式；文本：『{s}』")
        else:
            # 后置型：BASE 除 EXCLUSION_LIST 外（『外』必须是结尾）
            base_text = s[:i]
            if s[j + 1:]:
                raise RuleParseError(
                    f"『外』之后存在未知残余文字『{s[j + 1:]}』；文本：『{s}』"
                )
        if not excl_text:
            raise RuleParseError(f"『除』与『外』之间缺少排除项；文本：『{s}』")
        base = _parse_side(base_text, "被减主体", streets, districts)
        excl = _parse_side(excl_text, "排除列表", streets, districts)
        return {"op": "minus", "args": [base, excl]}

    return _parse_side(s, "表达式", streets, districts)


def _parse_side(s: str, role: str, streets: list, districts: list) -> dict:
    """解析一个 ATOM 或并集 ATOM 列表；去重后单节点直接返回，不包 union。"""
    seq = _parse_union_seq(s, role, streets, districts)
    nodes: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for node in seq:
        key = (node["op"], node["name"])
        if key in seen:
            continue
        seen.add(key)
        nodes.append(node)
    if len(nodes) == 1:
        return nodes[0]
    return {"op": "union", "args": nodes}


def _parse_union_seq(s: str, role: str, streets: list, districts: list) -> list[dict]:
    """把 ``ATOM (连接词 ATOM)*`` 文本切分为按文本顺序的规范节点序列。

    ATOM 与连接词之间无定界符，采用记忆化穷举切分：每个位置枚举可能的
    ATOM 结束点并用 03 三级名称解析验证；收集全部可行切分，恰有一种
    归一结果才接受。无解抛 RuleParseError（含名称失败原因），多种不同
    结果抛歧义错误，方案数超防御上限同样失败——绝不猜测。
    """
    if not s:
        raise RuleParseError(f"{role}为空")

    atom_cache: dict[str, tuple[tuple[str, str] | None, str | None]] = {}
    seq_cache: dict[tuple[int, bool], list[list[tuple[str, str]]]] = {}
    atom_reasons: list[str] = []

    def resolve_atom(query: str) -> tuple[tuple[str, str] | None, str | None]:
        """用 03 三级解析在街道表/区县表内分别解析；两类同时可解析即跨类型歧义。

        返回 ((op, 正式名) | None, 失败原因)。None 表示该 ATOM 候选不可用，
        只杀死当前切分路径，不中断其他切分的尝试。
        """
        if query in atom_cache:
            return atom_cache[query]
        street_hit = None
        street_err = None
        district_hit = None
        district_err = None
        try:
            street_hit = dsl.resolve_street(query, streets)["name"]
        except dsl.DslError as exc:
            street_err = str(exc)
        except KeyError:
            street_err = "街道表行缺少 name 字段，上下文不合法"
        try:
            district_hit = dsl.resolve_district(query, districts)["name"]
        except dsl.DslError as exc:
            district_err = str(exc)
        except KeyError:
            district_err = "区县表行缺少 name 字段，上下文不合法"

        if street_hit is not None and district_hit is not None:
            result = (
                None,
                f"名称『{query}』同时可解析为街道『{street_hit}』和区县"
                f"『{district_hit}』，跨类型歧义",
            )
        elif street_hit is not None:
            result = (("in_street", street_hit), None)
        elif district_hit is not None:
            result = (("in_district", district_hit), None)
        else:
            detail = street_err if street_err is not None else district_err
            if street_err is not None and district_err is not None:
                detail = f"{street_err}；{district_err}"
            result = (None, f"名称『{query}』无法解析：{detail}")
        atom_cache[query] = result
        return result

    def seq_from(pos: int, need_atom: bool) -> list[list[tuple[str, str]]]:
        """从 pos 开始的所有可行节点序列；need_atom 表示必须先出现 ATOM。"""
        key = (pos, need_atom)
        if key in seq_cache:
            return seq_cache[key]
        solutions: list[list[tuple[str, str]]] = []
        if not need_atom:
            if pos == len(s):
                solutions.append([])
            else:
                for conn in _UNION_CONNS:
                    if s.startswith(conn, pos):
                        for tail in seq_from(pos + len(conn), True):
                            solutions.append(list(tail))
        else:
            for end in range(pos + 1, len(s) + 1):
                atom_key, reason = resolve_atom(s[pos:end])
                if atom_key is None:
                    if reason is not None:
                        atom_reasons.append(reason)
                    continue
                for tail in seq_from(end, False):
                    if len(solutions) >= _MAX_SOLUTIONS:
                        raise RuleParseError(
                            f"文本切分方案超过防御上限 {_MAX_SOLUTIONS}，"
                            f"视为歧义过大而拒绝；文本：『{s}』"
                        )
                    solutions.append([atom_key] + tail)
        seq_cache[key] = solutions
        return solutions

    solutions = seq_from(0, True)
    if not solutions:
        detail = "；".join(dict.fromkeys(atom_reasons[:6])) or "无任何可行切分"
        raise RuleParseError(
            f"{role}『{s}』无法按冻结语法（ATOM 连接词 ATOM…）完整解析：{detail}"
        )

    distinct: dict[str, list[tuple[str, str]]] = {}
    for seq in solutions:
        distinct.setdefault(json.dumps(seq, ensure_ascii=False), seq)
    if len(distinct) > 1:
        raise RuleParseError(
            f"{role}『{s}』存在 {len(distinct)} 种不同切分结果，拒绝猜测"
        )

    # 规范化回填正式名：由 (op, 正式名) 元组新建 dict，绝不复用表行对象。
    return [
        {"op": op, "name": name}
        for op, name in next(iter(distinct.values()))
    ]


# ---------------------------------------------------------------------------
# T-402：可插拔 LLM 兜底（规则优先、LLM 兜底，D12）
# ---------------------------------------------------------------------------
#
# 纪律（任务卡冻结，违反即返工）：
# - 只有确定性路径抛 RuleParseError 才允许进入 LLM 兜底；输入数据/schema
#   错误、03 执行错误、代码异常一律原样抛出，绝不发给 LLM 掩盖。
# - 未配置 adapter/config 且规则路径失败：抛 LlmUnavailableError
#   （llm_unavailable=True），绝不静默跳过、绝不伪装成功。
# - LLM 只允许输出四原语 DSL JSON 对象；坐标/WKT/uid/面积/components/
#   side_of/near/解释文字一律经 03_dsl.validate_rule 拒绝，不清洗不修补。
# - prompt 只含：原文本、允许的正式街道/区县名、四原语 schema、只返 JSON
#   纪律；绝不含 units、uid、centroid、geom、WKT、oracle 答案或任何坐标。
# - HTTP 线协议固定为 anthropic-compatible：stdlib urllib，无第三方依赖，
#   不自动重试、不切换 endpoint、不回退模型。

import os
import urllib.error
import urllib.request
from typing import Callable


class LlmUnavailableError(Nl2RuleError):
    """规则路径失败且没有可用 LLM 兜底时抛出；llm_unavailable 恒为 True。"""

    llm_unavailable = True


class LlmOutputError(Nl2RuleError):
    """LLM 配置非法、HTTP 失败或输出不符合 DSL 纪律时抛出。"""


# 可插拔边界：签名 (prompt: str, request_body: dict) -> object。
# 返回 Python dict 或“仅含一个 JSON 对象”的 str；测试注入 fake，未来
# 其他 provider 注入同签名 callable，HTTP 逻辑绝不耦合进解析器。
LlmAdapter = Callable[[str, dict], object]

# LLM 配置 MVP schema（精确五字段，无内置默认值，禁止明文凭证字段）。
_LLM_CONFIG_FIELDS = ("provider", "endpoint", "model", "api_key_env", "timeout_seconds")
_LLM_SECRET_FIELD_HINTS = ("api_key", "token", "secret")
_LLM_PROVIDER = "anthropic-compatible"
_LLM_MAX_TIMEOUT_SECONDS = 120
_LLM_ANTHROPIC_VERSION = "2023-06-01"
_LLM_MAX_TOKENS = 1024

_LLM_SYSTEM_DISCIPLINE = (
    "你是规则编译器。只输出一个 JSON 对象，不得输出任何解释文字、代码围栏或坐标。"
    "只允许以下四种 DSL 节点："
    '{"op":"in_street","name":"<街道正式名>"}、'
    '{"op":"in_district","name":"<区县正式名>"}、'
    '{"op":"union","args":[<节点>,<节点>,…]}（args 至少 2 个）、'
    '{"op":"minus","args":[<节点>,<节点>]}（args 恰 2 个）。'
    "禁止输出坐标、WKT、uid、面积、components、side_of、near 或任何其他字段。"
)


def load_llm_config(path: Path) -> dict:
    """读取并校验 LLM 配置文件；路径/schema/密钥环境变量任一不符即抛
    LlmOutputError（中文），不打印配置原文、不打印密钥。"""
    path = Path(path)
    if not path.is_file():
        raise LlmOutputError(f"LLM 配置文件不存在：{path}")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise LlmOutputError(f"LLM 配置文件不是合法 UTF-8：{path}") from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmOutputError(f"LLM 配置文件 JSON 解析失败：{path}：{exc}") from exc
    if not isinstance(payload, dict):
        raise LlmOutputError(
            f"LLM 配置顶层必须是 JSON 对象，实际为 {type(payload).__name__}"
        )
    for field in payload:
        lowered = field.lower()
        if any(hint in lowered for hint in _LLM_SECRET_FIELD_HINTS) and field != "api_key_env":
            raise LlmOutputError(f"LLM 配置禁止明文凭证字段『{field}』；密钥只允许经 api_key_env 指定的环境变量提供")
    actual = tuple(payload.keys())
    if set(actual) != set(_LLM_CONFIG_FIELDS):
        raise LlmOutputError(
            f"LLM 配置字段集合必须恰为 {sorted(_LLM_CONFIG_FIELDS)}，"
            f"实际为 {sorted(actual)}（禁止缺字段或多字段）"
        )
    if payload["provider"] != _LLM_PROVIDER:
        raise LlmOutputError(
            f"LLM 配置 provider 只支持『{_LLM_PROVIDER}』，实际为 {payload['provider']!r}"
        )
    endpoint = payload["endpoint"]
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise LlmOutputError("LLM 配置 endpoint 必须是非空字符串")
    model = payload["model"]
    if not isinstance(model, str) or not model.strip():
        raise LlmOutputError("LLM 配置 model 必须是非空字符串")
    api_key_env = payload["api_key_env"]
    if not isinstance(api_key_env, str) or not api_key_env.strip():
        raise LlmOutputError("LLM 配置 api_key_env 必须是非空字符串（密钥环境变量名）")
    timeout = payload["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not (
        timeout > 0 and timeout <= _LLM_MAX_TIMEOUT_SECONDS
    ):
        raise LlmOutputError(
            f"LLM 配置 timeout_seconds 必须是 (0, {_LLM_MAX_TIMEOUT_SECONDS}] 内的有限数字，"
            f"实际为 {timeout!r}"
        )
    if api_key_env not in os.environ:
        raise LlmOutputError(
            f"密钥环境变量『{api_key_env}』未设置；请先在环境中提供 API 密钥"
        )
    # 防御：绝不让配置对象带出密钥（本函数只返回校验过的字段本身，
    # 字段值不含密钥；密钥只在 adapter 内读取环境变量时短暂存在）。
    return payload


def build_llm_prompt(text: str, ctx: dict) -> str:
    """构造只含纪律与允许名称的 prompt；绝不含 units/uid/坐标/WKT。"""
    streets = ctx.get("streets") if isinstance(ctx, dict) else None
    districts = ctx.get("districts") if isinstance(ctx, dict) else None
    if not isinstance(streets, list) or not isinstance(districts, list):
        raise Nl2RuleError(
            "prompt 上下文不合法：ctx 必须提供 streets / districts 两个行表（list）"
        )
    street_names: list[str] = []
    for row in streets:
        if isinstance(row, dict) and isinstance(row.get("name"), str) and row["name"].strip():
            street_names.append(row["name"])
    district_names: list[str] = []
    for row in districts:
        if isinstance(row, dict) and isinstance(row.get("name"), str) and row["name"].strip():
            district_names.append(row["name"])
    return (
        "任务：把用户文本编译为规则 DSL。\n"
        "允许的街道正式名：\n" + "\n".join(street_names) + "\n"
        "允许的区县正式名：\n" + "\n".join(district_names) + "\n"
        "四种 DSL 节点 schema：\n"
        '{"op":"in_street","name":"<街道正式名>"}\n'
        '{"op":"in_district","name":"<区县正式名>"}\n'
        '{"op":"union","args":[<节点>,<节点>,…]}\n'
        '{"op":"minus","args":[<节点>,<节点>]}\n'
        "纪律：只返回一个 JSON 对象，不要解释、不要代码围栏、不要坐标。\n"
        "用户文本：\n" + text
    )


def _default_llm_adapter(prompt: str, request_body: dict) -> dict:
    """anthropic-compatible 默认 adapter：stdlib urllib 单次 POST。

    request_body 必须已含 endpoint/api_key_env/timeout_seconds 传输参数
    （由 _compile_llm_path 注入，不属于发给模型的内容）。非 2xx、超时、
    响应 schema 不符均抛中文 LlmOutputError；绝不重试、绝不切换 endpoint。
    """
    endpoint = request_body.pop("_endpoint")
    api_key_env = request_body.pop("_api_key_env")
    timeout = request_body.pop("_timeout_seconds")
    api_key = os.environ.get(api_key_env, "")
    body = json.dumps(
        {
            "model": request_body["model"],
            "max_tokens": _LLM_MAX_TOKENS,
            "temperature": 0,
            "system": _LLM_SYSTEM_DISCIPLINE,
            "messages": [{"role": "user", "content": prompt}],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _LLM_ANTHROPIC_VERSION,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise LlmOutputError(f"LLM HTTP 请求失败：状态码 {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise LlmOutputError(f"LLM HTTP 请求失败：{exc.reason}") from exc
    except OSError as exc:
        raise LlmOutputError(f"LLM HTTP 请求失败：{exc}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LlmOutputError("LLM 响应不是合法 UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise LlmOutputError("LLM 响应顶层必须是 JSON 对象")
    content = payload.get("content")
    if (
        not isinstance(content, list)
        or len(content) != 1
        or not isinstance(content[0], dict)
        or content[0].get("type") != "text"
        or not isinstance(content[0].get("text"), str)
    ):
        raise LlmOutputError("LLM 响应 content 必须恰好包含一个 text block")
    return payload


def _extract_llm_dsl(adapter_result: object) -> dict:
    """从 adapter 返回值提取唯一 JSON 对象并走 03_dsl.validate_rule。

    接受 dict 或“仅含一个 JSON 对象”的 str；代码围栏、解释文字、多个
    JSON、数组、空响应、非法 JSON、坐标字段均拒绝，绝不清洗修补。
    """
    raw: str
    if isinstance(adapter_result, dict):
        # dict 返回值视作已解析的响应体：提取唯一 text block 或整体当 DSL。
        content = adapter_result.get("content")
        if isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict) \
                and content[0].get("type") == "text" and isinstance(content[0].get("text"), str):
            raw = content[0]["text"]
        elif "op" in adapter_result:
            candidate = adapter_result
            try:
                dsl.validate_rule(candidate)
            except dsl.DslError as exc:
                raise LlmOutputError(f"LLM 输出不符合 DSL 纪律：{exc}") from exc
            return candidate
        else:
            raise LlmOutputError("LLM adapter 返回 dict 既非响应体也非合法 DSL 对象")
    elif isinstance(adapter_result, str):
        raw = adapter_result
    else:
        raise LlmOutputError(
            f"LLM adapter 返回值必须是 dict 或 str，实际为 {type(adapter_result).__name__}"
        )
    stripped = raw.strip()
    if stripped.startswith("```"):
        raise LlmOutputError("LLM 输出包含代码围栏，拒绝")
    # 只允许恰好一个 JSON 对象：用 json.JSONDecoder.raw_decode 确认整体
    # 消费且无前后残余。
    decoder = json.JSONDecoder()
    try:
        obj, end = decoder.raw_decode(stripped)
    except json.JSONDecodeError as exc:
        raise LlmOutputError(f"LLM 输出不是合法 JSON：{exc}") from exc
    if stripped[end:].strip():
        raise LlmOutputError("LLM 输出在 JSON 对象之后存在额外内容，拒绝")
    if not isinstance(obj, dict):
        raise LlmOutputError("LLM 输出必须是 JSON 对象，实际为数组或标量")
    try:
        dsl.validate_rule(obj)
    except dsl.DslError as exc:
        raise LlmOutputError(f"LLM 输出不符合 DSL 纪律：{exc}") from exc
    return obj


def _rule_path(text: str, ctx: dict) -> dict:
    """确定性路径薄封装：RuleParseError 原样上抛（由调用方捕获兜底）。"""
    return parse_rule_deterministic(text, ctx)


def compile_description(text: str, ctx: dict, llm_adapter=None, llm_config=None) -> dict:
    """规则优先编译：成功返回 ``{"rule","path","llm_unavailable"}``。

    规则路径成功：adapter 调用数为 0，llm_unavailable 反映“本次是否没有
    可用 adapter”。规则路径 RuleParseError 才进入兜底：无 adapter/config
    抛 LlmUnavailableError；有 adapter 则调用一次，产物经 validate_rule。
    输入/schema/03 执行错误原样上抛，绝不发送给 LLM 掩盖。
    """
    if llm_adapter is None and llm_config is not None:
        # 卡载路由规则 4：有配置时默认 adapter 为 anthropic-compatible
        # stdlib urllib 实现；测试与未来 provider 经注入 LlmAdapter 扩展。
        llm_adapter = _default_llm_adapter
    try:
        rule = _rule_path(text, ctx)
    except RuleParseError:
        if llm_adapter is None:
            raise LlmUnavailableError(
                f"规则路径无法解析且未配置 LLM 兜底；原文：『{text}』"
            ) from None
        prompt = build_llm_prompt(text, ctx)
        request_body = {
            "model": llm_config["model"],
            "_endpoint": llm_config["endpoint"],
            "_api_key_env": llm_config["api_key_env"],
            "_timeout_seconds": llm_config["timeout_seconds"],
        }
        adapter_result = llm_adapter(prompt, request_body)
        rule = _extract_llm_dsl(adapter_result)
        return {"rule": rule, "path": "llm", "llm_unavailable": False}
    return {"rule": rule, "path": "rule", "llm_unavailable": llm_adapter is None}


def execute_description(text: str, ctx: dict, llm_adapter=None, llm_config=None) -> dict:
    """编译并执行：result 五字段直接来自 03_dsl.execute，绝不复制求值逻辑。"""
    compiled = compile_description(text, ctx, llm_adapter, llm_config)
    rule = compiled["rule"]
    result = dsl.execute(rule, ctx)
    return {
        "description": text,
        "path": compiled["path"],
        "llm_unavailable": compiled["llm_unavailable"],
        "rule": rule,
        "result": result,
    }


import sys


# ---------------------------------------------------------------------------
# T-402 CLI：translate 子命令（stdout 单行 JSON；密钥/坐标/配置原文不外泄）
# ---------------------------------------------------------------------------


def _cli_translate(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="04_nl2rule.py translate")
    parser.add_argument("--data", required=True, help="P3 数据目录")
    parser.add_argument("--text", required=True, help="中文规则文本")
    parser.add_argument("--llm-config", default=None, help="LLM 配置文件路径（可选）")
    args = parser.parse_args(argv)

    llm_adapter = None
    llm_config = None
    try:
        if args.llm_config is not None:
            llm_config = load_llm_config(Path(args.llm_config))
        ctx = dsl.load_pilot_context(Path(args.data))
        out = execute_description(args.text, ctx, llm_adapter, llm_config)
    except LlmUnavailableError:
        print(json.dumps(
            {"ok": False, "llm_unavailable": True,
             "error": "规则路径无法解析且未配置 LLM 兜底"},
            ensure_ascii=False,
        ))
        return 2
    except (LlmOutputError, dsl.PilotInputError) as exc:
        # 配置文件缺失/schema 错/密钥环境变量缺失/输入数据错误：显式失败，
        # 不退回空规则、不跳过 LLM；单行 JSON 到 stdout，中文且不含
        # 配置原文、请求头与密钥。
        payload = {"ok": False, "error": str(exc)}
        if isinstance(exc, LlmOutputError):
            payload["llm_unavailable"] = True
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    out["ok"] = True
    print(json.dumps(out, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# T-403：G4 合成语料构造（从 oracle 真值反推，强制 [合成语料] 标注）
# ---------------------------------------------------------------------------
#
# 纪律（任务卡冻结，违反即返工）：
# - 语料是"从答案反推输入"的有意合成基线，不是独立测试集：描述由 oracle
#   真值 uid 映射 unit.street 得到，评测存在循环性；每条 case 顶层必须
#   携带 SYNTHETIC_LABEL 精确标签，局限性声明见 SYNTHETIC_LIMITATION；
#   下游（T-404 的 case/CLI/报告）不得把合成语料包装成真实合同文本。
# - 只用 oracle 真值 uid、units.json 的 street 属性、streets.json 的正式
#   目录顺序；禁止调用 03_dsl.eval_rule/execute 或任何 NL 解析器反算；
#   不调用 LLM、不访问网络、不读取围栏几何（iou/recall/precision/straddle
#   仅做 schema 存在性与类型校验，绝不参与描述）。
# - 输入文件与对象只读；任一校验失败中文抛错（诊断一律带 [合成语料]
#   标签），不跳样本、不补样本、不返回半份结果。
# - 产物只暴露匿名 case_id（G4-001..G4-0NN），不输出客户围栏 src_id/name。

SYNTHETIC_LABEL = "[合成语料]"
SYNTHETIC_LIMITATION = "本表使用的描述系从真值反推，不代表在真实客户合同上的表现"
RULE_PATH_ONLY_NOTE = "本轮只测试规则路径；未配置、未调用 LLM 兜底"

_SYNTH_SOURCE = "oracle_unitsets_reverse_streets"
# 多街道并置连接词按 case 序号每 4 条循环：
# G4-001=、、G4-002=和、G4-003=加上、G4-004=以及，之后周而复始。
_SYNTH_CONNECTORS = ("、", "和", "加上", "以及")
_SYNTH_ORACLE_METHOD = "3.6-v1.4"

_SYNTH_ORACLE_KEYS = frozenset(("method", "link_min_m", "boundary_centroids", "fences"))
_SYNTH_FENCE_KEYS = frozenset((
    "name", "layer", "unit_ids", "iou", "recall", "precision", "straddle",
    "components",
))
_SYNTH_UNITS_KEYS = frozenset(("crs", "units"))
_SYNTH_UNIT_KEYS = frozenset((
    "uid", "key", "district_code", "street", "area_km2", "centroid", "geom",
))
_SYNTH_STREETS_KEYS = frozenset(("streets",))
_SYNTH_STREET_KEYS = frozenset(("name", "code", "district_code", "geom"))


class SyntheticCorpusError(Nl2RuleError):
    """合成语料输入非法（schema/门禁计数/uid/街道目录）时抛出；消息中文。"""


def _synth_fail(message: str) -> None:
    """统一中文抛错入口；诊断一律带 [合成语料] 标签（D-2）。"""
    raise SyntheticCorpusError(f"{SYNTHETIC_LABEL} {message}")


def _synth_is_int(value) -> bool:
    """严格整数判定；排除 bool（Python 中 bool 是 int 的子类）。"""
    return type(value) is int


def _synth_is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _synth_require_keys(obj, expected: frozenset, what: str) -> None:
    """严格 schema 校验：必需字段一个不能少，未知字段一个不能多。"""
    if not isinstance(obj, dict):
        _synth_fail(f"{what} 必须是 JSON 对象")
    missing = sorted(expected - obj.keys())
    if missing:
        _synth_fail(f"{what} 缺少必需字段：{'、'.join(missing)}")
    extra = sorted(obj.keys() - expected)
    if extra:
        _synth_fail(f"{what} 含有未知字段：{'、'.join(extra)}")


def _synth_load_json(path: Path, what: str):
    """只读加载 JSON；文件缺失、不可读或解析失败中文抛错。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        _synth_fail(f"读取{what}失败：{path}（{exc}）")
    except ValueError as exc:
        _synth_fail(f"{what} 不是合法 JSON：{path}（{exc}）")


def build_synthetic_cases(
    oracle_path: Path,
    data_dir: Path,
    *,
    expected_n: int,
    expected_layer_counts: dict[str, int],
) -> list[dict]:
    """从 oracle 真值反推每条围栏涉及的正式街道，构造 G4 合成 case 列表。

    有意设计的合成基线，不是独立测试集：描述由真值 uid 反推，评测存在
    循环性，结果只反映这条受控管线，不能证明真实合同理解能力（见
    SYNTHETIC_LIMITATION）。每条 case 顶层携带 SYNTHETIC_LABEL；任何
    校验失败中文抛错，不跳样本、不补样本、不返回半份结果。只读输入
    文件；不调用 03_dsl.eval_rule/execute、不调用任何 NL 解析器、不
    调用 LLM、不访问网络、不读取围栏几何。

    参数：
        oracle_path: oracle_unitsets.json 路径（schema 严格校验：必需
            字段一个不能少，未知字段一个不能多）。
        data_dir: 含 units.json 与 streets.json 的数据目录。
        expected_n: 调用方门禁：围栏总数。生产 G4 固定传 21。
        expected_layer_counts: 调用方门禁：layer→数量。生产 G4 固定传
            {"dealer": 4, "yeidai": 17}；小型单测必须显式传自己的预期
            计数，禁止通过省略门禁绕过校验。

    返回：list[dict]。每条顶层键恰为 label / case_id / source / layer /
    description / oracle_unit_ids / expected_components；case_id 为稳定
    匿名序号（src_id 字符串升序映射 G4-001..）；oracle_unit_ids 为升序
    唯一的新列表（深拷贝语义），case 之间不共享可变对象。
    """
    if not _synth_is_int(expected_n) or expected_n < 1:
        _synth_fail(f"expected_n 必须为正整数，收到 {expected_n!r}")
    if not isinstance(expected_layer_counts, dict) or not all(
        isinstance(layer, str) and layer and _synth_is_int(count) and count >= 0
        for layer, count in expected_layer_counts.items()
    ):
        _synth_fail("expected_layer_counts 必须是 {layer 名: 非负整数} 字典")
    sum_expected_layers = sum(expected_layer_counts.values())
    if sum_expected_layers != expected_n:
        _synth_fail(
            f"expected_layer_counts 各层之和 {sum_expected_layers} 与 "
            f"expected_n {expected_n} 不一致"
        )

    oracle_path = Path(oracle_path)
    data_dir = Path(data_dir)
    oracle = _synth_load_json(oracle_path, "oracle_unitsets")
    units_doc = _synth_load_json(data_dir / "units.json", "units")
    streets_doc = _synth_load_json(data_dir / "streets.json", "streets")

    # ---- oracle schema 与冻结方法 ----------------------------------------
    _synth_require_keys(oracle, _SYNTH_ORACLE_KEYS, "oracle_unitsets")
    if oracle["method"] != _SYNTH_ORACLE_METHOD:
        _synth_fail(
            f"oracle method={oracle['method']!r} 与冻结方法 "
            f"{_SYNTH_ORACLE_METHOD!r} 不符"
        )
    if not _synth_is_number(oracle["link_min_m"]) or not _synth_is_number(
        oracle["boundary_centroids"]
    ):
        _synth_fail("oracle link_min_m 与 boundary_centroids 必须是数字")
    fences = oracle["fences"]
    if not isinstance(fences, dict) or not fences:
        _synth_fail("oracle fences 必须是非空 JSON 对象")
    if len(fences) != expected_n:
        _synth_fail(
            f"oracle 围栏共 {len(fences)} 条，与 expected_n {expected_n} 不一致"
        )

    # ---- 正式街道目录（目录顺序即描述排序依据）---------------------------
    _synth_require_keys(streets_doc, _SYNTH_STREETS_KEYS, "streets")
    streets_list = streets_doc["streets"]
    if not isinstance(streets_list, list) or not streets_list:
        _synth_fail("streets.streets 必须是非空数组")
    catalog_order: dict[str, int] = {}
    for idx, row in enumerate(streets_list):
        _synth_require_keys(row, _SYNTH_STREET_KEYS, f"streets[{idx}]")
        name = row["name"]
        if not isinstance(name, str) or not name:
            _synth_fail(f"streets[{idx}].name 必须是非空字符串")
        if name in catalog_order:
            _synth_fail(f"正式街道目录中 {name!r} 重复出现")
        catalog_order[name] = idx

    # ---- L1 单元：uid → street 映射 --------------------------------------
    _synth_require_keys(units_doc, _SYNTH_UNITS_KEYS, "units")
    units_list = units_doc["units"]
    if not isinstance(units_list, list) or not units_list:
        _synth_fail("units.units 必须是非空数组")
    uid_street: dict[int, str] = {}
    for idx, row in enumerate(units_list):
        _synth_require_keys(row, _SYNTH_UNIT_KEYS, f"units[{idx}]")
        uid = row["uid"]
        if not _synth_is_int(uid):
            _synth_fail(f"units[{idx}].uid 必须是整数，收到 {uid!r}")
        if uid in uid_street:
            _synth_fail(f"units 中 uid {uid} 重复出现")
        street = row["street"]
        if not isinstance(street, str) or not street:
            _synth_fail(f"units[{idx}]（uid {uid}）的 street 必须是非空字符串")
        uid_street[uid] = street

    # ---- 逐围栏校验；case 顺序 = src_id 字符串升序（与 JSON 插入顺序无关）
    ordered_fences: list[tuple] = []
    for src_id, fence in sorted(fences.items()):
        _synth_require_keys(fence, _SYNTH_FENCE_KEYS, f"围栏 {src_id!r}")
        layer = fence["layer"]
        if not isinstance(layer, str) or not layer:
            _synth_fail(f"围栏 {src_id!r} 的 layer 必须是非空字符串")
        if layer not in expected_layer_counts:
            _synth_fail(
                f"围栏 {src_id!r} 的 layer {layer!r} 不在调用方给定的"
                f"分层计数 {sorted(expected_layer_counts)} 中"
            )
        if not isinstance(fence["name"], str) or not fence["name"]:
            _synth_fail(f"围栏 {src_id!r} 的 name 必须是非空字符串")
        for metric in ("iou", "recall", "precision", "straddle"):
            if not _synth_is_number(fence[metric]):
                _synth_fail(f"围栏 {src_id!r} 的 {metric} 必须是数字")
        components = fence["components"]
        if not _synth_is_int(components) or components < 1:
            _synth_fail(
                f"围栏 {src_id!r} 的 components 必须是正整数，收到 {components!r}"
            )
        unit_ids = fence["unit_ids"]
        if not isinstance(unit_ids, list) or not unit_ids:
            _synth_fail(f"围栏 {src_id!r} 的 unit_ids 必须是非空数组")
        for uid in unit_ids:
            if not _synth_is_int(uid):
                _synth_fail(f"围栏 {src_id!r} 的 unit_ids 含非整数 uid：{uid!r}")
            if uid not in uid_street:
                _synth_fail(
                    f"围栏 {src_id!r} 的 uid {uid} 越界：units.json 中不存在该 uid"
                )
        if len(set(unit_ids)) != len(unit_ids):
            _synth_fail(f"围栏 {src_id!r} 的 unit_ids 含重复 uid")
        ordered_fences.append((src_id, fence))

    # ---- 分层计数门禁 -----------------------------------------------------
    actual_layers: dict[str, int] = {}
    for _, fence in ordered_fences:
        actual_layers[fence["layer"]] = actual_layers.get(fence["layer"], 0) + 1
    for layer, expected_count in expected_layer_counts.items():
        actual_count = actual_layers.get(layer, 0)
        if actual_count != expected_count:
            _synth_fail(
                f"layer {layer!r} 实际 {actual_count} 条，"
                f"与调用方预期 {expected_count} 条不符"
            )

    # ---- 反推描述并构造 case（此处绝不触碰执行器/解析器/LLM）-------------
    cases: list[dict] = []
    for seq, (src_id, fence) in enumerate(ordered_fences, start=1):
        street_names = {uid_street[uid] for uid in fence["unit_ids"]}
        unknown = sorted(name for name in street_names if name not in catalog_order)
        if unknown:
            _synth_fail(
                f"围栏 {src_id!r}（case G4-{seq:03d}）的街道 {unknown} "
                f"不在正式街道目录中"
            )
        ordered_names = sorted(street_names, key=lambda n: catalog_order[n])
        if len(ordered_names) == 1:
            description = ordered_names[0]
        else:
            connector = _SYNTH_CONNECTORS[(seq - 1) % len(_SYNTH_CONNECTORS)]
            description = connector.join(ordered_names)
        cases.append({
            "label": SYNTHETIC_LABEL,
            "case_id": f"G4-{seq:03d}",
            "source": _SYNTH_SOURCE,
            "layer": fence["layer"],
            "description": description,
            # 新列表：升序唯一，深拷贝语义；元素为不可变 int。
            "oracle_unit_ids": sorted(fence["unit_ids"]),
            "expected_components": fence["components"],
        })
    return cases


# ---------------------------------------------------------------------------
# T-404：G4 规则路径集成评测、D-1 双表报告与 g4 CLI
# ---------------------------------------------------------------------------
#
# 纪律（任务卡冻结，违反即返工）：
# - 只走规则路径：逐条 case 直接 parse_rule_deterministic → 03_dsl.execute；
#   绝不调用 LLM adapter / HTTP / compile_description 兜底分支 / --llm-config；
#   本机无 LLM 端点，llm_evaluated 恒为 False，LLM 调用数恒为 0。
# - D-1 双表铁律：表 A（G3 几何天花板）与表 B（G4 [合成语料] 端到端）物理
#   分离（中间局限性段落 + --- 分隔），永不合并成单一数字；禁止第三张总分
#   表、G3+G4 合并分数、G4 PASS/FAIL。
# - D-2 标签铁律：每条 case 行、汇总行、失败明细行一律以 SYNTHETIC_LABEL
#   开头；报告内置两条固定局限性文案；[合成语料] 分数不代表真实合同能力。
# - G4 无预设通过线：has_preset_pass_line 恒为 False；指标原值报告，低分是
#   信息而非失败；解析失败计入 n 条分母，绝不删样本、绝不只算成功样本。
# - 隐私：stdout 与报告绝不输出客户围栏 name/src_id、WKT、坐标、完整 uid
#   列表或任何凭证；只允许匿名 case_id、layer、Jaccard、components、解析状态。
# - 报告 UTF-8 原子写入；任一 schema/执行错误非零退出，绝不写半份报告。

import statistics
import tempfile


class G4EvaluationError(Nl2RuleError):
    """G4 评测输入非法（case schema / 不变量 / state 证据）时抛出；消息中文。"""


def _g4_fail(message: str) -> None:
    """统一中文抛错入口；诊断一律带 [合成语料] 标签（D-2）。"""
    raise G4EvaluationError(f"{SYNTHETIC_LABEL} {message}")


def _g4_is_int(value) -> bool:
    """严格整数判定；排除 bool（Python 中 bool 是 int 的子类）。"""
    return type(value) is int



# 失败行 error 字段的精简上限：RuleParseError 含原文与逐词枚举，全量入报告
# 过长；截断为确定性前缀（双跑字节一致），前缀已含失败原因与原文开头。
_G4_ERROR_MAX_CHARS = 160


def _g4_condense_error(message: str) -> str:
    """把解析错误压缩为中文精简原因：压平空白并确定性截断。"""
    collapsed = " ".join(str(message).split())
    if len(collapsed) > _G4_ERROR_MAX_CHARS:
        collapsed = collapsed[: _G4_ERROR_MAX_CHARS - 1].rstrip() + "…"
    return collapsed


def _g4_require_str(case: dict, key: str, idx: int) -> None:
    value = case.get(key)
    if not isinstance(value, str) or not value:
        _g4_fail(f"cases[{idx}] 的 {key} 必须是非空字符串，实际为 {value!r}")


def _g4_validate_case(case: dict, idx: int) -> None:
    """单条 case 契约校验：D-2 标签强制 + oracle 非空（空 oracle 属契约错误）。"""
    if not isinstance(case, dict):
        _g4_fail(f"cases[{idx}] 必须是对象，实际为 {type(case).__name__}")
    label = case.get("label")
    if label != SYNTHETIC_LABEL:
        _g4_fail(
            f"cases[{idx}] 的 label 必须是 {SYNTHETIC_LABEL!r}（D-2），"
            f"实际为 {label!r}"
        )
    _g4_require_str(case, "case_id", idx)
    _g4_require_str(case, "layer", idx)
    _g4_require_str(case, "description", idx)
    oracle = case.get("oracle_unit_ids")
    if not isinstance(oracle, list) or not oracle:
        _g4_fail(
            f"cases[{idx}]（case_id={case.get('case_id')!r}）的 "
            f"oracle_unit_ids 必须是非空数组；空 oracle 属输入契约错误，"
            f"绝不自行定义空并空得分"
        )
    for uid in oracle:
        if not _g4_is_int(uid):
            _g4_fail(f"cases[{idx}] 的 oracle_unit_ids 含非整数 uid：{uid!r}")
    if len(set(oracle)) != len(oracle):
        _g4_fail(f"cases[{idx}] 的 oracle_unit_ids 含重复 uid")
    expected = case.get("expected_components")
    if not _g4_is_int(expected) or expected < 1:
        _g4_fail(
            f"cases[{idx}] 的 expected_components 必须是正整数，实际为 {expected!r}"
        )


def evaluate_g4_rule_path(cases: list, ctx: dict) -> dict:
    """G4 规则路径逐条评测：确定性解析 → 03_dsl.execute → 单元集指标。

    只走规则路径：``parse_rule_deterministic`` 失败（``RuleParseError``）
    记为失败行并计入分母，绝不调用 LLM 兜底；03 执行/契约错误原样上抛，
    绝不吞错。Jaccard 只比较 uid 集合（``|P∩O| / |P∪O|``；oracle 非空已
    校验，无除零），绝不用 P2 oracle 的几何 iou/recall/precision 替代；
    predicted components 取 03 五字段输出，绝不重算。中位数覆盖全部
    n 行（失败行以 0.0 参与），符合冻结指标定义。输入只读。
    """
    if not isinstance(cases, list) or not cases:
        _g4_fail("cases 必须是非空数组")
    if not isinstance(ctx, dict):
        _g4_fail("ctx 必须是 dict")
    for idx, case in enumerate(cases):
        _g4_validate_case(case, idx)

    rows: list[dict] = []
    for case in cases:
        row: dict = {
            "label": case["label"],
            "case_id": case["case_id"],
            "layer": case["layer"],
            "description": case["description"],
        }
        try:
            rule = parse_rule_deterministic(case["description"], ctx)
        except RuleParseError as exc:
            row.update({
                "parse_success": False,
                "path": None,
                "llm_unavailable": True,
                "rule": None,
                "predicted_unit_ids": [],
                "jaccard": 0.0,
                "predicted_components": None,
                "expected_components": case["expected_components"],
                "components_correct": False,
                "error": _g4_condense_error(str(exc)),
            })
            rows.append(row)
            continue
        # 规则路径成功：03 执行错误在此原样上抛（契约错误，不进失败行）。
        result = dsl.execute(rule, ctx)
        oracle = set(case["oracle_unit_ids"])
        predicted = set(result["unit_ids"])
        jaccard = len(predicted & oracle) / len(predicted | oracle)
        row.update({
            "parse_success": True,
            "path": "rule",
            "llm_unavailable": True,
            "rule": rule,
            "predicted_unit_ids": result["unit_ids"],
            "jaccard": jaccard,
            "predicted_components": result["components"],
            "expected_components": case["expected_components"],
            "components_correct": (
                result["components"] == case["expected_components"]
            ),
            "error": None,
        })
        rows.append(row)

    n = len(rows)
    success_rows = [r for r in rows if r["parse_success"]]
    fail_rows = [r for r in rows if not r["parse_success"]]
    components_correct = sum(1 for r in success_rows if r["components_correct"])
    return {
        "label": SYNTHETIC_LABEL,
        "n": n,
        "rows": rows,
        "median_jaccard": statistics.median(r["jaccard"] for r in rows),
        "components_correct": components_correct,
        "components_accuracy": components_correct / n,
        "rule_parse_success": len(success_rows),
        "rule_parse_rate": len(success_rows) / n,
        "parse_failures": fail_rows,
        "rule_path_only": True,
        "llm_evaluated": False,
        "has_preset_pass_line": False,
    }


_G4_EVALUATION_KEYS = (
    "label", "n", "rows", "median_jaccard", "components_correct",
    "components_accuracy", "rule_parse_success", "rule_parse_rate",
    "parse_failures", "rule_path_only", "llm_evaluated",
    "has_preset_pass_line",
)
_G4_ROW_REQUIRED_KEYS = frozenset((
    "label", "case_id", "layer", "description", "parse_success", "path",
    "llm_unavailable", "rule", "predicted_unit_ids", "jaccard",
    "predicted_components", "expected_components", "components_correct",
    "error",
))


def _g4_load_g3_evidence(state_path: Path) -> dict:
    """只读加载 state.json 并提取 G3 证据；缺失/非 pass/schema 错均中文抛错。"""
    state_path = Path(state_path)
    try:
        text = state_path.read_text(encoding="utf-8")
    except OSError as exc:
        _g4_fail(f"state 文件无法读取：{state_path}（{exc}）")
    except UnicodeDecodeError as exc:
        _g4_fail(f"state 文件不是合法 UTF-8：{state_path}（{exc}）")
    try:
        state = json.loads(text)
    except json.JSONDecodeError as exc:
        _g4_fail(f"state 文件不是合法 JSON：{state_path}（{exc}）")
    if not isinstance(state, dict):
        _g4_fail(f"state 顶层必须是 JSON 对象：{state_path}")
    gates = state.get("gates")
    if not isinstance(gates, dict) or not isinstance(gates.get("G3"), dict):
        _g4_fail(f"state 缺少 gates.G3 证据，无法渲染表 A：{state_path}")
    g3 = gates["G3"]
    if g3.get("result") != "pass":
        _g4_fail(
            f"state 的 G3 result={g3.get('result')!r} 不是 pass；"
            f"拒绝渲染表 A 的 100% PASS 判定"
        )
    tests = g3.get("tests")
    if not _g4_is_int(tests) or tests < 1:
        _g4_fail(f"state 的 G3 tests 必须是正整数，实际为 {tests!r}")
    l0 = g3.get("l0_crosscheck")
    if not isinstance(l0, str) or not l0:
        _g4_fail(f"state 的 G3 l0_crosscheck 必须是非空字符串，实际为 {l0!r}")
    return {"tests": tests, "l0_crosscheck": l0}


def render_g4_report(evaluation: dict, state_path: Path) -> str:
    """渲染 D-1 双表报告：表 A（G3 几何天花板）+ 局限性段落 + --- + 表 B。

    两张表物理分离且永不聚合：表 A 只含 G3 证据（不含 Jaccard /
    [合成语料]），表 B 只含 G4 [合成语料] 指标（不含 G3 聚合）；表 B 后
    只允许四条带标签汇总/明细行；全文禁止 G4 PASS/FAIL 与总分表。
    G3 证据只读自 state_path；G3 非 pass 时拒绝渲染 100% PASS 判定。
    """
    if not isinstance(evaluation, dict) or any(
        key not in evaluation for key in _G4_EVALUATION_KEYS
    ):
        _g4_fail("evaluation 缺少必需键，拒绝渲染报告")
    rows = evaluation["rows"]
    n = evaluation["n"]
    if not _g4_is_int(n) or n < 1 or not isinstance(rows, list) or len(rows) != n:
        _g4_fail("evaluation 的 n 与 rows 数量不一致，拒绝渲染报告")
    if (
        evaluation["llm_evaluated"] is not False
        or evaluation["rule_path_only"] is not True
        or evaluation["has_preset_pass_line"] is not False
    ):
        _g4_fail("evaluation 违反规则路径不变量"
                 "（llm_evaluated/rule_path_only/has_preset_pass_line）")
    if evaluation["label"] != SYNTHETIC_LABEL:
        _g4_fail(f"evaluation 的 label 必须是 {SYNTHETIC_LABEL!r}（D-2）")
    for pos, row in enumerate(rows):
        if not isinstance(row, dict) or row.get("label") != SYNTHETIC_LABEL:
            _g4_fail(f"rows[{pos}] 缺少 {SYNTHETIC_LABEL!r} 标签（D-2），拒绝渲染")
        if not _G4_ROW_REQUIRED_KEYS.issubset(row.keys()):
            missing = sorted(_G4_ROW_REQUIRED_KEYS - set(row.keys()))
            _g4_fail(f"rows[{pos}] 缺少键：{missing}，拒绝渲染")
    g3 = _g4_load_g3_evidence(Path(state_path))
    fail_rows = evaluation["parse_failures"]

    lines: list[str] = []
    lines.append("### 表 A：G3 几何天花板（oracle DSL 树 → 单元集）")
    lines.append("")
    lines.append("| 验证证据 | 精确结果 | 判定 |")
    lines.append("|---|---:|---|")
    lines.append(
        f"| P3 全仓库单测 | {g3['tests']}/{g3['tests']} | 100%，PASS |"
    )
    lines.append(
        f"| L0 独立 oracle DSL 交叉验证 | {g3['l0_crosscheck']} | 100%，PASS |"
    )
    lines.append("")
    lines.append("判定：G3 必须且已经达到 100%。本表不含任何 G4 指标。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("### 表 B：G4 端到端 [合成语料]")
    lines.append("")
    lines.append(f"⚠️ {SYNTHETIC_LIMITATION}。")
    lines.append(f"{RULE_PATH_ONLY_NOTE}。")
    lines.append("“端到端”仅是 G4 门禁名称，指本轮合成描述→DSL→执行器→单元集管线；")
    lines.append("不得据此宣称已具备真实客户合同的端到端能力。")
    lines.append("")
    lines.append("| 标签 | 围栏 | 层 | 文本 | Jaccard | components 实际/预期 | 规则解析 |")
    lines.append("|---|---|---|---|---:|---:|---|")
    for row in rows:
        if row["parse_success"]:
            lines.append(
                f"| {SYNTHETIC_LABEL} | {row['case_id']} | {row['layer']} | "
                f"{row['description']} | {row['jaccard']!r} | "
                f"{row['predicted_components']}/{row['expected_components']} "
                f"| 成功 |"
            )
        else:
            lines.append(
                f"| {SYNTHETIC_LABEL} | {row['case_id']} | {row['layer']} | "
                f"{row['description']} | 0.0 | -/{row['expected_components']} "
                f"| 失败 |"
            )
    lines.append("")
    lines.append(
        f"{SYNTHETIC_LABEL} 中位单元集 Jaccard："
        f"{evaluation['median_jaccard']!r}（无预设通过线，仅作信息报告）"
    )
    lines.append(
        f"{SYNTHETIC_LABEL} components 准确率（正确数/{n}）："
        f"{evaluation['components_correct']}/{n} = "
        f"{evaluation['components_accuracy']!r}（无预设通过线，仅作信息报告）"
    )
    lines.append(
        f"{SYNTHETIC_LABEL} 规则路径解析成功率（成功数/{n}）："
        f"{evaluation['rule_parse_success']}/{n} = "
        f"{evaluation['rule_parse_rate']!r}（无预设通过线，仅作信息报告）"
    )
    if fail_rows:
        detail = "；".join(
            f"{row['case_id']}（{row['error']}）" for row in fail_rows
        )
    else:
        detail = "无"
    lines.append(
        f"{SYNTHETIC_LABEL} 解析失败明细：{detail}"
        f"（无预设通过线，仅作信息报告）"
    )
    lines.append("")
    return "\n".join(lines)


def write_text_atomic(path: Path, text: str) -> None:
    """UTF-8 原子写入：同目录临时文件 + fsync + ``os.replace``。

    任一阶段失败都会清理临时文件并原样抛错，目标路径绝不出现半份内容。
    """
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=parent, prefix=".g4_report_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    dir_fd = os.open(parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


# g4 子命令的生产门禁（与 T-403 卡载一致）：21 条围栏，dealer 4 + yeidai 17。
_G4_EXPECTED_N = 21
_G4_LAYER_COUNTS = {"dealer": 4, "yeidai": 17}


def _cli_g4(argv: list) -> int:
    """g4 子命令：规则路径评测 + D-1 双表报告（不接受 --llm-config）。"""
    import argparse

    parser = argparse.ArgumentParser(prog="04_nl2rule.py g4")
    parser.add_argument("--data", required=True, help="P3 数据目录（只读）")
    parser.add_argument("--oracle", required=True,
                        help="oracle_unitsets.json（只读）")
    parser.add_argument("--state", required=True,
                        help="state.json（只读，仅取 G3 证据）")
    parser.add_argument("--report", required=True,
                        help="报告输出路径（UTF-8 原子写入）")
    args = parser.parse_args(argv)
    try:
        ctx = dsl.load_pilot_context(Path(args.data))
        cases = build_synthetic_cases(
            Path(args.oracle), Path(args.data),
            expected_n=_G4_EXPECTED_N,
            expected_layer_counts=dict(_G4_LAYER_COUNTS),
        )
        evaluation = evaluate_g4_rule_path(cases, ctx)
        report = render_g4_report(evaluation, Path(args.state))
        # 报告只在全部评测与渲染成功后原子写入：此前任何失败都不产生半份报告。
        write_text_atomic(Path(args.report), report)
    except (Nl2RuleError, dsl.PilotInputError, dsl.DslError, OSError) as exc:
        # schema/执行错误：非零退出，原始匿名 case_id 保留在中文诊断里。
        print(f"[GATE-FAIL] {exc}", file=sys.stderr)
        return 2
    for row in evaluation["rows"]:
        if row["parse_success"]:
            print(
                f"{SYNTHETIC_LABEL} case={row['case_id']} layer={row['layer']} "
                f"jaccard={row['jaccard']!r} "
                f"components={row['predicted_components']}/"
                f"{row['expected_components']} 解析=成功"
            )
        else:
            print(
                f"{SYNTHETIC_LABEL} case={row['case_id']} layer={row['layer']} "
                f"解析=失败 error={row['error']}"
            )
    summary = evaluation
    print(
        f"{SYNTHETIC_LABEL} 汇总 n={summary['n']} "
        f"median_jaccard={summary['median_jaccard']!r} "
        f"components_correct={summary['components_correct']}/{summary['n']} "
        f"components_accuracy={summary['components_accuracy']!r} "
        f"rule_parse_success={summary['rule_parse_success']}/{summary['n']} "
        f"rule_parse_rate={summary['rule_parse_rate']!r} "
        f"rule_path_only=true llm_evaluated=false 无预设通过线"
    )
    return 0


if __name__ == "__main__":
    _argv = sys.argv[1:]
    if not _argv or _argv[0] not in ("translate", "g4"):
        print(json.dumps(
            {"ok": False, "error": "本脚本只支持 translate / g4 子命令"},
            ensure_ascii=False,
        ), file=sys.stderr)
        raise SystemExit(2)
    if _argv[0] == "translate":
        raise SystemExit(_cli_translate(_argv[1:]))
    raise SystemExit(_cli_g4(_argv[1:]))
