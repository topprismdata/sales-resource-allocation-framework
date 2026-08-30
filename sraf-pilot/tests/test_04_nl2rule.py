# -*- coding: utf-8 -*-
"""T-401 单元测试：确定性中文规则解析器（规则优先主路径，D12）。

覆盖：
- 卡载可执行验收断言：单 ATOM / 简称 / 四连接词并集 / 三差集模板 /
  包装前缀后缀 / 去重坍缩为单节点；
- 冻结语法边界：全角/半角逗号模板标点、并集顺序保持、去重；
- 失败类（全部 RuleParseError）：空/非字符串、纯标点、未知名称、
  歧义简称（单表内去后缀歧义 + 包含歧义 + 跨街道/区县类型歧义）、
  未知残余文字、连接词两侧缺项、多个差集标记、差集嵌套、括号、
  坐标文本、WKT、side_of/near 意图；
- D12 硬纪律：无网络调用（socket 计数 = 0）、输入不变证明
  （ctx 与街道/区县行对象 json 指纹逐字节一致）、输出 op 集合受限、
  无坐标/单元 id 泄漏、产物通过 03_dsl.validate_rule。

手写最小 ctx（不读 data/pilot，不访问磁盘数据文件；03_dsl 模块加载
本身只发生在 import 期且只读相邻源文件）。
"""

import importlib.util
import json
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# 按相邻路径加载被测模块与 03_dsl（只读源码文件；与生产加载方式一致）
# ---------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parents[1] / "src"

_spec = importlib.util.spec_from_file_location("nl2rule_04", _SRC / "04_nl2rule.py")
nl2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nl2)

_spec3 = importlib.util.spec_from_file_location("dsl_03_for_t401", _SRC / "03_dsl.py")
dsl = importlib.util.module_from_spec(_spec3)
_spec3.loader.exec_module(dsl)


# ---------------------------------------------------------------------------
# 手写最小 ctx（覆盖三级名称解析逐级与歧义场景）
# ---------------------------------------------------------------------------

STREETS = [
    {"name": "凤阳街道", "code": "440105014", "district_code": "440105",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
    {"name": "华洲街道", "code": "440105015", "district_code": "440105",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
    {"name": "南华西街道", "code": "440105016", "district_code": "440105",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
    {"name": "琶洲街道", "code": "440105017", "district_code": "440105",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
    {"name": "官洲街道", "code": "440105018", "district_code": "440105",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
    # 去后缀歧义夹具：词干「翠湖」撞车
    {"name": "翠湖街道", "code": "440105019", "district_code": "440105",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
    {"name": "翠湖镇", "code": "440105020", "district_code": "440105",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
]
DISTRICTS = [
    {"name": "海珠区", "code": "440105", "district_code": "440105",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
    {"name": "荔湾区", "code": "440103", "district_code": "440103",
     "geom": "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"},
]


def build_ctx() -> dict:
    """每次返回全新深拷贝 ctx，测试间互不污染（geom 字段本卡不读取）。"""
    return {
        "streets": [dict(row) for row in STREETS],
        "districts": [dict(row) for row in DISTRICTS],
    }


def walk_ops(rule: dict) -> list[str]:
    """先序遍历 DSL 树收集所有 op。"""
    ops = [rule["op"]]
    for child in rule.get("args", []):
        ops.extend(walk_ops(child))
    return ops


def contains_coordinate_or_unit_ids(rule: dict) -> bool:
    """输出树中不得出现坐标数字或单元 id。"""
    text = json.dumps(rule, ensure_ascii=False)
    for token in ("113.", "23.0", "23.1", '"uid"', '"key"', "centroid",
                  "geom", "WKT", "POLYGON", "MULTIPOLYGON",
                  "side_of", "near"):
        if token in text:
            return True
    for node in _iter_nodes(rule):
        if node["op"] in ("in_street", "in_district"):
            if not isinstance(node["name"], str):
                return True
    return False


def _iter_nodes(rule: dict):
    yield rule
    for child in rule.get("args", []):
        yield from _iter_nodes(child)


def ctx_fingerprint(ctx: dict) -> str:
    """ctx 内容指纹（含行对象），用于输入不变断言。"""
    return json.dumps(ctx, sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 无网络调用证明：整个测试模块期间统计 socket 创建次数
# ---------------------------------------------------------------------------

import socket  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402

_network_call_count = {"n": 0}
_orig_socket = socket.socket
_orig_create = socket.create_connection


def _counting_socket(*args, **kwargs):
    _network_call_count["n"] += 1
    return _orig_socket(*args, **kwargs)


def _counting_create(*args, **kwargs):
    _network_call_count["n"] += 1
    return _orig_create(*args, **kwargs)


socket.socket = _counting_socket
socket.create_connection = _counting_create


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


class T401TestCase(unittest.TestCase):
    """公共夹具：手写 ctx、输入指纹快照。"""

    def setUp(self):
        self.ctx = build_ctx()
        self.ctx_before = ctx_fingerprint(self.ctx)


class TestCardAcceptance(T401TestCase):
    """卡载可执行验收断言逐项落地。"""

    def test_card_single_street(self):
        self.assertEqual(
            nl2.parse_rule_deterministic("凤阳街道", self.ctx),
            {"op": "in_street", "name": "凤阳街道"},
        )

    def test_card_district_shorthand(self):
        self.assertEqual(
            nl2.parse_rule_deterministic("海珠", self.ctx),
            {"op": "in_district", "name": "海珠区"},
        )

    def test_card_union_dunehao(self):
        self.assertEqual(
            nl2.parse_rule_deterministic("凤阳街道、华洲街道", self.ctx),
            {"op": "union", "args": [
                {"op": "in_street", "name": "凤阳街道"},
                {"op": "in_street", "name": "华洲街道"},
            ]},
        )

    def test_card_union_he_yiji(self):
        rule = nl2.parse_rule_deterministic("凤阳和华洲以及南华西街道", self.ctx)
        self.assertEqual(rule["op"], "union")
        self.assertEqual(
            rule["args"],
            [
                {"op": "in_street", "name": "凤阳街道"},
                {"op": "in_street", "name": "华洲街道"},
                {"op": "in_street", "name": "南华西街道"},
            ],
        )

    def test_card_minus_buhan_union(self):
        self.assertEqual(
            nl2.parse_rule_deterministic("海珠区不含琶洲街道和官洲街道", self.ctx),
            {"op": "minus", "args": [
                {"op": "in_district", "name": "海珠区"},
                {"op": "union", "args": [
                    {"op": "in_street", "name": "琶洲街道"},
                    {"op": "in_street", "name": "官洲街道"},
                ]},
            ]},
        )

    def test_card_minus_chu_prefix(self):
        self.assertEqual(
            nl2.parse_rule_deterministic("除琶洲街道外，海珠区", self.ctx),
            {"op": "minus", "args": [
                {"op": "in_district", "name": "海珠区"},
                {"op": "in_street", "name": "琶洲街道"},
            ]},
        )

    def test_card_wrap_prefix_jiazhang(self):
        rule = nl2.parse_rule_deterministic("负责凤阳街道加上华洲街道片区", self.ctx)
        self.assertEqual(rule["op"], "union")
        self.assertEqual(
            rule["args"],
            [
                {"op": "in_street", "name": "凤阳街道"},
                {"op": "in_street", "name": "华洲街道"},
            ],
        )

    def test_card_dedup_collapses_to_single(self):
        self.assertEqual(
            nl2.parse_rule_deterministic("凤阳街道、凤阳", self.ctx),
            {"op": "in_street", "name": "凤阳街道"},
        )


class TestFrozenGrammar(T401TestCase):
    """冻结语法边界：连接词全覆盖、差集模板变体、包装词、去重。"""

    def test_union_conns_jia_shang(self):
        rule = nl2.parse_rule_deterministic("凤阳街道加上华洲街道", self.ctx)
        self.assertEqual(rule, {"op": "union", "args": [
            {"op": "in_street", "name": "凤阳街道"},
            {"op": "in_street", "name": "华洲街道"},
        ]})

    def test_union_conns_yiji(self):
        rule = nl2.parse_rule_deterministic("凤阳以及华洲", self.ctx)
        self.assertEqual(rule, {"op": "union", "args": [
            {"op": "in_street", "name": "凤阳街道"},
            {"op": "in_street", "name": "华洲街道"},
        ]})

    def test_minus_chu_no_comma(self):
        """『A除B外』无逗号后置模板（模板标点可有可无）。"""
        self.assertEqual(
            nl2.parse_rule_deterministic("海珠区除琶洲街道外", self.ctx),
            {"op": "minus", "args": [
                {"op": "in_district", "name": "海珠区"},
                {"op": "in_street", "name": "琶洲街道"},
            ]},
        )

    def test_minus_chu_prefix_no_comma(self):
        """『除B外A』前置模板无逗号变体。"""
        self.assertEqual(
            nl2.parse_rule_deterministic("除琶洲街道外海珠区", self.ctx),
            {"op": "minus", "args": [
                {"op": "in_district", "name": "海珠区"},
                {"op": "in_street", "name": "琶洲街道"},
            ]},
        )

    def test_minus_buhan_single_atom(self):
        self.assertEqual(
            nl2.parse_rule_deterministic("海珠区不含琶洲街道", self.ctx),
            {"op": "minus", "args": [
                {"op": "in_district", "name": "海珠区"},
                {"op": "in_street", "name": "琶洲街道"},
            ]},
        )

    def test_minus_base_can_be_union(self):
        """BASE 也可以是并集列表。"""
        self.assertEqual(
            nl2.parse_rule_deterministic("凤阳街道和华洲街道不含琶洲街道", self.ctx),
            {"op": "minus", "args": [
                {"op": "union", "args": [
                    {"op": "in_street", "name": "凤阳街道"},
                    {"op": "in_street", "name": "华洲街道"},
                ]},
                {"op": "in_street", "name": "琶洲街道"},
            ]},
        )

    def test_half_width_comma_in_chu_template(self):
        """半角逗号同样作为差集模板标点。"""
        self.assertEqual(
            nl2.parse_rule_deterministic("除琶洲街道外,海珠区", self.ctx),
            {"op": "minus", "args": [
                {"op": "in_district", "name": "海珠区"},
                {"op": "in_street", "name": "琶洲街道"},
            ]},
        )

    def test_wrap_prefixes_all(self):
        for prefix in ("范围为", "覆盖", "包括", "选择", "负责"):
            with self.subTest(prefix=prefix):
                rule = nl2.parse_rule_deterministic(f"{prefix}凤阳街道", build_ctx())
                self.assertEqual(rule, {"op": "in_street", "name": "凤阳街道"})

    def test_wrap_suffixes_all(self):
        for suffix in ("范围", "区域", "片区"):
            with self.subTest(suffix=suffix):
                rule = nl2.parse_rule_deterministic(f"凤阳街道{suffix}", build_ctx())
                self.assertEqual(rule, {"op": "in_street", "name": "凤阳街道"})

    def test_wrap_both_ends(self):
        rule = nl2.parse_rule_deterministic("覆盖凤阳街道片区", build_ctx())
        self.assertEqual(rule, {"op": "in_street", "name": "凤阳街道"})

    def test_union_order_preserved(self):
        rule = nl2.parse_rule_deterministic("华洲街道和凤阳街道", self.ctx)
        self.assertEqual(
            rule["args"],
            [
                {"op": "in_street", "name": "华洲街道"},
                {"op": "in_street", "name": "凤阳街道"},
            ],
        )

    def test_dedup_keeps_first_occurrence_order(self):
        rule = nl2.parse_rule_deterministic("凤阳、华洲街道和凤阳街道", self.ctx)
        self.assertEqual(rule, {"op": "union", "args": [
            {"op": "in_street", "name": "凤阳街道"},
            {"op": "in_street", "name": "华洲街道"},
        ]})

    def test_district_union(self):
        rule = nl2.parse_rule_deterministic("海珠区、荔湾区", self.ctx)
        self.assertEqual(rule, {"op": "union", "args": [
            {"op": "in_district", "name": "海珠区"},
            {"op": "in_district", "name": "荔湾区"},
        ]})

    def test_mixed_street_district_union(self):
        rule = nl2.parse_rule_deterministic("海珠区和凤阳街道", self.ctx)
        self.assertEqual(rule, {"op": "union", "args": [
            {"op": "in_district", "name": "海珠区"},
            {"op": "in_street", "name": "凤阳街道"},
        ]})


class TestThreeLevelNameResolution(T401TestCase):
    """简称规范化回填正式名，且完全依赖 03 三级解析。"""

    def test_street_stem_unique(self):
        """查『凤阳』：精确级 0 命中，去后缀级唯一 → 凤阳街道。"""
        self.assertEqual(
            nl2.parse_rule_deterministic("凤阳", self.ctx),
            {"op": "in_street", "name": "凤阳街道"},
        )

    def test_street_contains_unique(self):
        """查『琶洲』：精确/去后缀均 0，包含级唯一 → 琶洲街道。"""
        self.assertEqual(
            nl2.parse_rule_deterministic("琶洲", self.ctx),
            {"op": "in_street", "name": "琶洲街道"},
        )

    def test_district_exact(self):
        self.assertEqual(
            nl2.parse_rule_deterministic("海珠区", self.ctx),
            {"op": "in_district", "name": "海珠区"},
        )

    def test_stemmed_ambiguity_rejected(self):
        """『翠湖』去后缀后同时命中翠湖街道/翠湖镇 → 歧义拒绝。"""
        with self.assertRaises(nl2.RuleParseError):
            nl2.parse_rule_deterministic("翠湖", self.ctx)

    def test_cross_type_ambiguity_rejected(self):
        """同一简称同时可解析为街道和区县 → 跨类型歧义拒绝。"""
        ctx = build_ctx()
        ctx["districts"].append(dict(DISTRICTS[0], name="凤阳区", code="440106"))
        with self.assertRaises(nl2.RuleParseError):
            nl2.parse_rule_deterministic("凤阳街道", ctx)


class TestFailureClasses(T401TestCase):
    """全部失败类必须 RuleParseError（中文，含原文与原因）。"""

    def _assert_err(self, text):
        with self.assertRaises(nl2.RuleParseError) as cm:
            nl2.parse_rule_deterministic(text, self.ctx)
        msg = str(cm.exception)
        self.assertIn(text, msg)  # 原文必须出现在错误消息里

    def test_empty_string(self):
        self._assert_err("")

    def test_whitespace_only(self):
        with self.assertRaises(nl2.RuleParseError):
            nl2.parse_rule_deterministic("   ", self.ctx)

    def test_non_string(self):
        for bad in (None, 123, 4.5, ["凤阳街道"], {"a": 1}):
            with self.subTest(bad=bad):
                with self.assertRaises(nl2.RuleParseError):
                    nl2.parse_rule_deterministic(bad, self.ctx)

    def test_pure_punctuation(self):
        with self.assertRaises(nl2.RuleParseError):
            nl2.parse_rule_deterministic("、、和", self.ctx)

    def test_unknown_name(self):
        self._assert_err("未知街道")

    def test_zero_match_shorthand(self):
        with self.assertRaises(nl2.RuleParseError):
            nl2.parse_rule_deterministic("不存在片区", self.ctx)

    def test_contains_ambiguity(self):
        """构造包含级 >1 命中：『街道』是所有街道的公共子串…改用真实夹具：
        『华』包含于 华洲街道/南华西街道 两行 → 歧义。"""
        with self.assertRaises(nl2.RuleParseError):
            nl2.parse_rule_deterministic("华", self.ctx)

    def test_unknown_residual_text(self):
        self._assert_err("凤阳街道及周边区域")

    def test_trailing_connector(self):
        self._assert_err("凤阳街道和")

    def test_leading_connector(self):
        self._assert_err("和凤阳街道")

    def test_missing_exclusion_after_buhan(self):
        self._assert_err("不含琶洲街道")

    def test_missing_base_before_buhan(self):
        self._assert_err("凤阳街道不含")

    def test_double_minus_marks_buhan(self):
        self._assert_err("海珠区不含琶洲街道不含官洲街道")

    def test_double_minus_marks_chu(self):
        self._assert_err("海珠区除琶洲街道除官洲街道外")

    def test_mixed_minus_marks(self):
        self._assert_err("海珠区不含琶洲街道除官洲街道外")

    def test_chu_without_wai(self):
        self._assert_err("海珠区除琶洲街道")

    def test_nested_minus_via_parens(self):
        """括号本身是残余文字；嵌套差集意图必须失败。"""
        self._assert_err("海珠区不含（琶洲街道和官洲街道）")

    def test_parentheses_rejected(self):
        self._assert_err("（凤阳街道和华洲街道）")

    def test_coordinate_text(self):
        self._assert_err("113.5,23.1")

    def test_wkt_text(self):
        self._assert_err("POLYGON((113.0 23.0, 113.1 23.0))")

    def test_side_of_intent(self):
        self._assert_err("凤阳街道side_of快速路")

    def test_near_intent(self):
        self._assert_err("near凤阳街道")

    def test_residual_after_wai(self):
        self._assert_err("海珠区除琶洲街道外所有")

    def test_residual_after_suffix_wrap(self):
        self._assert_err("凤阳街道范围 plus")

    def test_only_wrap_prefix_no_content(self):
        with self.assertRaises(nl2.RuleParseError):
            nl2.parse_rule_deterministic("负责", self.ctx)

    def test_only_wrap_suffix_no_content(self):
        with self.assertRaises(nl2.RuleParseError):
            nl2.parse_rule_deterministic("片区", self.ctx)


class TestHardDisciplines(T401TestCase):
    """D12 与只读纪律的可执行证明。"""

    def test_network_call_count_is_zero(self):
        before = _network_call_count["n"]
        nl2.parse_rule_deterministic("海珠区不含琶洲街道和官洲街道", self.ctx)
        nl2.parse_rule_deterministic("凤阳、华洲街道", self.ctx)
        self.assertEqual(_network_call_count["n"] - before, 0)

    def test_ctx_unchanged(self):
        nl2.parse_rule_deterministic("海珠区不含琶洲街道和官洲街道", self.ctx)
        self.assertEqual(ctx_fingerprint(self.ctx), self.ctx_before)

    def test_row_objects_not_mutated_and_not_reused(self):
        ctx = build_ctx()
        rows_before = [json.dumps(r, sort_keys=True) for r in
                       ctx["streets"] + ctx["districts"]]
        rule = nl2.parse_rule_deterministic("凤阳街道、华洲街道", ctx)
        rows_after = [json.dumps(r, sort_keys=True) for r in
                      ctx["streets"] + ctx["districts"]]
        self.assertEqual(rows_before, rows_after)
        # 产物必须是新建 dict，绝不复用表行对象
        for node in _iter_nodes(rule):
            self.assertNotIn(node, ctx["streets"])
            self.assertNotIn(node, ctx["districts"])

    def test_ops_restricted_to_four_primitives(self):
        for text in ("凤阳街道", "海珠", "凤阳、华洲街道", "海珠区不含琶洲街道",
                     "除琶洲街道外，海珠区", "海珠区除琶洲街道外"):
            with self.subTest(text=text):
                rule = nl2.parse_rule_deterministic(text, build_ctx())
                self.assertTrue(set(walk_ops(rule))
                                <= {"in_street", "in_district", "union", "minus"})

    def test_no_coordinates_or_unit_ids(self):
        for text in ("凤阳街道", "海珠", "海珠区不含琶洲街道和官洲街道",
                     "负责凤阳街道加上华洲街道片区"):
            with self.subTest(text=text):
                rule = nl2.parse_rule_deterministic(text, build_ctx())
                self.assertFalse(contains_coordinate_or_unit_ids(rule))

    def test_output_passes_03_validate_rule(self):
        for text in ("凤阳街道", "海珠", "凤阳、华洲街道", "凤阳和华洲以及南华西街道",
                     "海珠区不含琶洲街道和官洲街道", "除琶洲街道外，海珠区",
                     "海珠区除琶洲街道外", "凤阳街道、凤阳"):
            with self.subTest(text=text):
                rule = nl2.parse_rule_deterministic(text, build_ctx())
                dsl.validate_rule(rule)  # 不抛即通过

    def test_normalization_backfills_formal_names(self):
        """简称产物 name 必须是表中正式名，不是查询原文。"""
        rule = nl2.parse_rule_deterministic("凤阳", self.ctx)
        self.assertEqual(rule["name"], "凤阳街道")

    def test_ctx_missing_tables_raises_nl2error(self):
        with self.assertRaises(nl2.Nl2RuleError):
            nl2.parse_rule_deterministic("凤阳街道", {})



# ===========================================================================
# T-402：可插拔 LLM 兜底、显式不可用状态与 translate CLI
# ===========================================================================

import os
import tempfile
import unittest.mock


def build_exec_ctx() -> dict:
    """最小完整 P3 ctx：03_dsl.execute 可直接使用（含 L1 图）。"""
    geom = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"
    units = [
        {"uid": 0, "key": "u0", "district_code": "440105", "street": "凤阳街道",
         "area_km2": 1.5, "centroid": [113.0, 23.0], "geom": geom},
        {"uid": 1, "key": "u1", "district_code": "440105", "street": "华洲街道",
         "area_km2": 2.5, "centroid": [113.05, 23.05], "geom": geom},
    ]
    return {
        "data_dir": ".",
        "crs": "GCJ-02",
        "units": units,
        "unit_geoms": [None, None],
        "streets": [dict(STREETS[0]), dict(STREETS[1])],
        "street_geoms": [None, None],
        "districts": [dict(DISTRICTS[0])],
        "district_geoms": [None],
        "adjacency": {0: [1], 1: [0]},
        "link_min_m": 50,
    }


class CountingFakeAdapter:
    """卡载验收用计数 fake：记录调用并返回手写 DSL dict 或字符串。"""

    def __init__(self, result):
        self.result = result
        self.calls = 0
        self.prompts = []
        self.bodies = []

    def __call__(self, prompt, body):
        self.calls += 1
        self.prompts.append(prompt)
        self.bodies.append(body)
        return self.result


def fake_llm_config():
    return {"provider": "anthropic-compatible", "endpoint": "http://127.0.0.1:1/v1",
            "model": "FAKE", "api_key_env": "SRAF_T402_FAKE_KEY",
            "timeout_seconds": 30}


_UNPARSABLE = "自由表达，规则语法无法完整识别"


class T402Base(unittest.TestCase):
    """公共夹具：完整 exec ctx、无 SRAF_T402_FAKE_KEY 环境。"""

    def setUp(self):
        self.ctx = build_exec_ctx()
        self.ctx_fp = ctx_fingerprint(self.ctx)
        self._env_cleanup = []
        if "SRAF_T402_FAKE_KEY" in os.environ:
            self._env_cleanup.append(("SRAF_T402_FAKE_KEY",
                                      os.environ.pop("SRAF_T402_FAKE_KEY")))

    def tearDown(self):
        for key, value in self._env_cleanup:
            os.environ[key] = value


class TestCardAcceptanceT402(T402Base):
    """卡载可执行验收断言逐项落地。"""

    def test_rule_path_zero_adapter_calls(self):
        fake = CountingFakeAdapter({"op": "in_street", "name": "凤阳街道"})
        compiled = nl2.compile_description(
            "凤阳街道和华洲街道", self.ctx, fake, fake_llm_config())
        self.assertEqual(compiled["path"], "rule")
        self.assertEqual(fake.calls, 0)
        # 提供了 fake adapter：本次调用有可用 adapter，llm_unavailable=False
        self.assertFalse(compiled["llm_unavailable"])

    def test_llm_fallback_exactly_one_call(self):
        fake = CountingFakeAdapter({"op": "in_street", "name": "凤阳街道"})
        compiled = nl2.compile_description(
            _UNPARSABLE, self.ctx, fake, fake_llm_config())
        self.assertEqual(compiled, {
            "rule": {"op": "in_street", "name": "凤阳街道"},
            "path": "llm",
            "llm_unavailable": False,
        })
        self.assertEqual(fake.calls, 1)

    def test_unconfigured_raises_llm_unavailable(self):
        with self.assertRaises(nl2.LlmUnavailableError) as cm:
            nl2.compile_description(_UNPARSABLE, self.ctx)
        self.assertIs(cm.exception.llm_unavailable, True)
        self.assertIsInstance(cm.exception, nl2.Nl2RuleError)

    def test_execute_description_shape(self):
        out = nl2.execute_description("凤阳街道", self.ctx)
        self.assertEqual(set(out), {"description", "path", "llm_unavailable",
                                    "rule", "result"})
        self.assertEqual(set(out["result"]),
                         {"unit_ids", "components", "area_km2", "rule", "warnings"})
        self.assertEqual(out["result"]["rule"], out["rule"])
        self.assertEqual(out["path"], "rule")
        self.assertTrue(out["llm_unavailable"])
        self.assertEqual(out["result"]["unit_ids"], [0])
        self.assertEqual(out["result"]["area_km2"], 1.5)

    def test_execute_via_llm_path(self):
        fake = CountingFakeAdapter({"op": "in_street", "name": "华洲街道"})
        out = nl2.execute_description(
            _UNPARSABLE, self.ctx, fake, fake_llm_config())
        self.assertEqual(out["path"], "llm")
        self.assertFalse(out["llm_unavailable"])
        self.assertEqual(out["result"]["unit_ids"], [1])


class TestLlmDiscipline(T402Base):
    """LLM 输出纪律：恶意/越界输出全部拒绝，合法输出过 03 校验器。"""

    def _assert_rejected(self, result):
        fake = CountingFakeAdapter(result)
        with self.assertRaises(nl2.LlmOutputError):
            nl2.compile_description(_UNPARSABLE, self.ctx, fake, fake_llm_config())

    def test_reject_coordinates(self):
        self._assert_rejected({"op": "in_street", "name": "凤阳街道",
                               "centroid": [113.0, 23.0]})

    def test_reject_near(self):
        self._assert_rejected({"op": "near", "name": "凤阳街道"})

    def test_reject_side_of(self):
        self._assert_rejected({"op": "side_of", "name": "凤阳街道"})

    def test_reject_uid_list(self):
        self._assert_rejected({"op": "in_street", "name": "凤阳街道", "uids": [0, 1]})

    def test_reject_code_fence(self):
        self._assert_rejected('```json\n{"op": "in_street", "name": "凤阳街道"}\n```')

    def test_reject_explanatory_text(self):
        self._assert_rejected('好的，规则是 {"op": "in_street", "name": "凤阳街道"}')

    def test_reject_multiple_json(self):
        self._assert_rejected('{"op": "in_street", "name": "凤阳街道"}'
                              '{"op": "in_street", "name": "华洲街道"}')

    def test_reject_array(self):
        self._assert_rejected('[{"op": "in_street", "name": "凤阳街道"}]')

    def test_reject_empty_response(self):
        self._assert_rejected("")

    def test_reject_illegal_json(self):
        self._assert_rejected("{not json}")
    def test_unknown_name_fails_at_execute_not_compile(self):
        """合法结构但名称不在表内：结构校验通过（validate_rule 只查结构），
        编译成功；名称解析失败发生在 03_dsl.execute 阶段。"""
        fake = CountingFakeAdapter({"op": "in_street", "name": "不存在的街道"})
        compiled = nl2.compile_description(
            _UNPARSABLE, self.ctx, fake, fake_llm_config())
        self.assertEqual(compiled["path"], "llm")
        dsl.validate_rule(compiled["rule"])  # 结构合法，不抛
        with self.assertRaises(dsl.DslError):
            dsl.execute(compiled["rule"], self.ctx)

    def test_llm_output_from_response_body_dict(self):
        """dict 形式的 anthropic 响应体（恰好一个 text block）可提取。"""
        body = {"content": [{"type": "text",
                             "text": '{"op": "in_street", "name": "凤阳街道"}'}]}
        fake = CountingFakeAdapter(body)
        compiled = nl2.compile_description(
            _UNPARSABLE, self.ctx, fake, fake_llm_config())
        self.assertEqual(compiled["rule"],
                         {"op": "in_street", "name": "凤阳街道"})
        dsl.validate_rule(compiled["rule"])  # 生产 validate_rule 实际被调用


class TestPromptAndInputs(T402Base):
    """prompt 卫生与输入不变证明。"""

    def test_prompt_contains_no_geometry_or_uids(self):
        fake = CountingFakeAdapter({"op": "in_street", "name": "凤阳街道"})
        nl2.compile_description(_UNPARSABLE, self.ctx, fake, fake_llm_config())
        prompt = fake.prompts[0]
        for unit in self.ctx["units"]:
            self.assertNotIn(str(unit["uid"]), prompt)
            self.assertNotIn(str(unit["centroid"][0]), prompt)
            self.assertNotIn(unit["geom"][:20], prompt)
        for token in ("centroid", "geom", "WKT", "POLYGON", "area_km2",
                      "components", "unit_geoms", "adjacency"):
            self.assertNotIn(token, prompt)
        # 必含：原文本与允许的正式名
        self.assertIn(_UNPARSABLE, prompt)
        self.assertIn("凤阳街道", prompt)
        self.assertIn("海珠区", prompt)

    def test_inputs_unchanged(self):
        fake = CountingFakeAdapter({"op": "in_street", "name": "凤阳街道"})
        text = _UNPARSABLE
        llm_dict = {"content": [{"type": "text", "text": '{"op": "in_street", "name": "凤阳街道"}'}]}
        llm_dict_fp = json.dumps(llm_dict, sort_keys=True)
        nl2.compile_description(text, self.ctx, fake, fake_llm_config())
        self.assertEqual(ctx_fingerprint(self.ctx), self.ctx_fp)
        self.assertEqual(json.dumps(llm_dict, sort_keys=True), llm_dict_fp)
        self.assertEqual(fake.bodies[0].get("model"), "FAKE")


class TestLlmConfig(T402Base):
    """load_llm_config：路径/schema/密钥逐项显式失败。"""

    def _write(self, payload_text):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload_text)
        self.addCleanup(os.unlink, path)
        return Path(path)

    def _valid_json(self, **overrides):
        cfg = fake_llm_config()
        cfg.update(overrides)
        return json.dumps(cfg, ensure_ascii=False)

    def test_missing_file(self):
        with self.assertRaises(nl2.LlmOutputError):
            nl2.load_llm_config(Path("/nonexistent/t402_config.json"))

    def test_missing_env_var(self):
        path = self._write(self._valid_json())
        with self.assertRaises(nl2.LlmOutputError) as cm:
            nl2.load_llm_config(path)
        self.assertIn("SRAF_T402_FAKE_KEY", str(cm.exception))

    def test_ok_with_env_var(self):
        os.environ["SRAF_T402_FAKE_KEY"] = "sk-test-xyz"
        self.addCleanup(os.environ.pop, "SRAF_T402_FAKE_KEY", None)
        path = self._write(self._valid_json())
        cfg = nl2.load_llm_config(path)
        self.assertEqual(cfg["provider"], "anthropic-compatible")

    def test_reject_plaintext_secret_field(self):
        path = self._write(self._valid_json(api_key="sk-plain"))
        with self.assertRaises(nl2.LlmOutputError):
            nl2.load_llm_config(path)

    def test_reject_unknown_provider(self):
        path = self._write(self._valid_json(provider="openai"))
        with self.assertRaises(nl2.LlmOutputError):
            nl2.load_llm_config(path)

    def test_reject_extra_and_missing_fields(self):
        for payload in (
            self._valid_json(extra_field=1),
            json.dumps({k: v for k, v in fake_llm_config().items() if k != "model"}),
        ):
            with self.subTest(payload=payload):
                path = self._write(payload)
                with self.assertRaises(nl2.LlmOutputError):
                    nl2.load_llm_config(path)

    def test_reject_bad_timeout(self):
        for bad in (0, -1, 121, "30", None, True):
            with self.subTest(bad=bad):
                path = self._write(self._valid_json(timeout_seconds=bad))
                with self.assertRaises(nl2.LlmOutputError):
                    nl2.load_llm_config(path)

    def test_error_message_contains_no_config_body_or_key(self):
        os.environ["SRAF_T402_FAKE_KEY"] = "sk-super-secret"
        self.addCleanup(os.environ.pop, "SRAF_T402_FAKE_KEY", None)
        # 配置非法（provider 错），密钥已在环境中：错误消息绝不含密钥值
        path = self._write(self._valid_json(provider="openai"))
        with self.assertRaises(nl2.LlmOutputError) as cm:
            nl2.load_llm_config(path)
        self.assertNotIn("sk-super-secret", str(cm.exception))
        self.assertNotIn("FAKE_MODEL", str(cm.exception))

class TestDefaultAdapterHttp(T402Base):
    """默认 adapter 线协议：全部 mock，真实网络调用数为 0。"""

    def test_http_success_one_text_block(self):
        os.environ["SRAF_T402_FAKE_KEY"] = "sk-http-test"
        self.addCleanup(os.environ.pop, "SRAF_T402_FAKE_KEY", None)
        resp_body = {"content": [{"type": "text",
                                  "text": '{"op": "in_street", "name": "凤阳街道"}'}]}
        mock_resp = unittest.mock.MagicMock()
        mock_resp.read.return_value = json.dumps(resp_body).encode("utf-8")
        mock_resp.__enter__ = unittest.mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
        with unittest.mock.patch.object(nl2.urllib.request, "urlopen",
                                        return_value=mock_resp) as mock_open:
            compiled = nl2.compile_description(
                _UNPARSABLE, self.ctx, None, fake_llm_config())
        self.assertEqual(mock_open.call_count, 1)
        self.assertEqual(compiled["path"], "llm")
        req = mock_open.call_args[0][0]
        self.assertEqual(req.get_header("Content-type"), "application/json")
        self.assertEqual(req.get_header("X-api-key"), "sk-http-test")
        self.assertEqual(req.get_header("Anthropic-version"), "2023-06-01")
        sent = json.loads(req.data.decode("utf-8"))
        self.assertEqual(sent["model"], "FAKE")
        self.assertEqual(sent["temperature"], 0)
        self.assertEqual(sent["max_tokens"], 1024)
        self.assertIn(_UNPARSABLE, sent["messages"][0]["content"])

    def test_http_non_2xx_chinese_error_no_retry(self):
        os.environ["SRAF_T402_FAKE_KEY"] = "sk-http-test"
        self.addCleanup(os.environ.pop, "SRAF_T402_FAKE_KEY", None)
        err = nl2.urllib.error.HTTPError(
            "http://127.0.0.1:1/v1", 500, "boom", {}, None)
        with unittest.mock.patch.object(nl2.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(nl2.LlmOutputError) as cm:
                nl2.compile_description(_UNPARSABLE, self.ctx, None, fake_llm_config())
        self.assertIn("500", str(cm.exception))

    def test_http_bad_response_schema(self):
        for body in ('{"content": []}', '{"content": [{"type": "tool"}]}',
                     '{"nope": 1}', "[]", "not json"):
            with self.subTest(body=body):
                mock_resp = unittest.mock.MagicMock()
                mock_resp.read.return_value = body.encode("utf-8")
                mock_resp.__enter__ = unittest.mock.MagicMock(return_value=mock_resp)
                mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
                with unittest.mock.patch.object(nl2.urllib.request, "urlopen",
                                                return_value=mock_resp):
                    with self.assertRaises(nl2.LlmOutputError):
                        nl2.compile_description(
                            _UNPARSABLE, self.ctx, None, fake_llm_config())

    def test_http_timeout_wrapped_as_llm_output_error(self):
        with unittest.mock.patch.object(
                nl2.urllib.request, "urlopen",
                side_effect=TimeoutError("timed out")):
            with self.assertRaises(nl2.LlmOutputError):
                nl2.compile_description(_UNPARSABLE, self.ctx, None, fake_llm_config())


class TestTranslateCli(T402Base):
    """translate CLI：subprocess 端到端（真实网络 0 次）。"""

    def _run(self, *extra, env_key=None):
        import subprocess
        import sys
        env = dict(os.environ)
        env.pop("SRAF_T402_FAKE_KEY", None)
        if env_key is not None:
            env["SRAF_T402_FAKE_KEY"] = env_key
        data_dir = self._data_dir
        cmd = [sys.executable, str(_SRC / "04_nl2rule.py"), "translate",
               "--data", str(data_dir), "--text", self._text, *extra]
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                              timeout=60)
        return proc

    def setUp(self):
        super().setUp()
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        geom = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"
        (Path(self._tmp.name) / "units.json").write_text(json.dumps({
            "crs": "GCJ-02", "units": [
                {"uid": 0, "key": "u0", "district_code": "440105",
                 "street": "凤阳街道", "area_km2": 1.5,
                 "centroid": [113.0, 23.0], "geom": geom},
                {"uid": 1, "key": "u1", "district_code": "440105",
                 "street": "华洲街道", "area_km2": 2.5,
                 "centroid": [113.05, 23.05], "geom": geom},
            ]}, ensure_ascii=False), encoding="utf-8")
        (Path(self._tmp.name) / "streets.json").write_text(json.dumps({
            "streets": [
                {"name": "凤阳街道", "code": "440105014",
                 "district_code": "440105", "geom": geom},
                {"name": "华洲街道", "code": "440105015",
                 "district_code": "440105", "geom": geom},
            ]}, ensure_ascii=False), encoding="utf-8")
        (Path(self._tmp.name) / "districts.json").write_text(json.dumps({
            "streets": [{"name": "海珠区", "code": "440105",
                         "district_code": "440105", "geom": geom}]},
            ensure_ascii=False), encoding="utf-8")
        (Path(self._tmp.name) / "unit_graph.json").write_text(json.dumps({
            "adjacency": {"0": [1], "1": [0]}, "link_min_m": 50}),
            encoding="utf-8")
        # 04 CLI 经 03_dsl.load_pilot_context 读全部五文件（T-502 起 lines.json 必备）
        (Path(self._tmp.name) / "lines.json").write_text(json.dumps({
            "schema_version": "p5-lines-v1", "crs": "GCJ-02",
            "source_crs": "WGS-84", "source_sha256": "a" * 64,
            "counts": {"source_elements": 1, "source_named_ways": 1,
                       "output_names": 1, "output_parts": 1},
            "lines": [{"name": "环岛路", "classes": ["highway"],
                       "osm_way_ids": [1],
                       "geom": "LINESTRING (113.0 23.0, 113.1 23.1)"}]},
            ensure_ascii=False), encoding="utf-8")
        self._data_dir = self._tmp.name
        self._text = "凤阳街道"

    def _write_config(self):
        path = Path(self._tmp.name) / "llm_config.json"
        path.write_text(json.dumps(
            dict(fake_llm_config(),
                 endpoint="http://127.0.0.1:9/v1/messages"), ensure_ascii=False),
            encoding="utf-8")
        return path

    def test_rule_success_without_config_exit_0(self):
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertTrue(out["ok"])
        self.assertEqual(out["path"], "rule")
        self.assertTrue(out["llm_unavailable"])

    def test_rule_failure_without_config_nonzero_and_flag(self):
        self._text = _UNPARSABLE
        proc = self._run()
        self.assertNotEqual(proc.returncode, 0)
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1)
        out = json.loads(lines[0])
        self.assertFalse(out["ok"])
        self.assertIs(out["llm_unavailable"], True)
        self.assertEqual(out["error"], "规则路径无法解析且未配置 LLM 兜底")

    def test_missing_config_file_explicit_failure(self):
        self._text = _UNPARSABLE
        proc = self._run("--llm-config", str(Path(self._tmp.name) / "nope.json"))
        self.assertNotEqual(proc.returncode, 0)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertFalse(out["ok"])
        self.assertTrue(out["llm_unavailable"])

    def test_missing_api_key_env_explicit_failure(self):
        self._text = _UNPARSABLE
        proc = self._run("--llm-config", str(self._write_config()))
        self.assertNotEqual(proc.returncode, 0)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertFalse(out["ok"])
        self.assertTrue(out["llm_unavailable"])

    def test_no_key_leak_in_stdout_stderr(self):
        self._text = _UNPARSABLE
        proc = self._run("--llm-config", str(self._write_config()),
                         env_key="sk-very-secret-cli-key")
        self.assertNotIn("sk-very-secret-cli-key", proc.stdout)
        self.assertNotIn("sk-very-secret-cli-key", proc.stderr)
        self.assertNotIn("api_key_env", proc.stdout)

    def test_bad_config_schema_explicit_failure(self):
        self._text = _UNPARSABLE
        bad = Path(self._tmp.name) / "bad.json"
        bad.write_text('{"provider": "openai"}', encoding="utf-8")
        proc = self._run("--llm-config", str(bad))
        self.assertNotEqual(proc.returncode, 0)
        out = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertFalse(out["ok"])


# ===========================================================================
# T-403：G4 合成语料构造（从 oracle 真值反推，强制 [合成语料] 标注）
# ===========================================================================

import hashlib  # noqa: E402
import re  # noqa: E402


def _write_synth_fixture(data_dir: Path, *, oracle: dict, units: dict, streets: dict) -> Path:
    """把三份夹具写进临时目录；返回 oracle 路径。"""
    oracle_path = data_dir / "oracle_unitsets.json"
    oracle_path.write_text(json.dumps(oracle, ensure_ascii=False), encoding="utf-8")
    (data_dir / "units.json").write_text(json.dumps(units, ensure_ascii=False), encoding="utf-8")
    (data_dir / "streets.json").write_text(json.dumps(streets, ensure_ascii=False), encoding="utf-8")
    return oracle_path


def _synth_oracle(**overrides) -> dict:
    """合法 oracle 夹具基线；overrides 覆盖 fences/method 等顶层字段。

    基线围栏 SRC-B 引用 uid [2, 3]（两单元同属目录序 2 的华洲街道），
    即单街道 case。
    """
    doc = {
        "method": "3.6-v1.4", "link_min_m": 50, "boundary_centroids": 0,
        "fences": {
            "SRC-B": {"name": "乙围栏", "layer": "yeidai", "unit_ids": [2, 3],
                      "iou": 0.9, "recall": 0.9, "precision": 0.9, "straddle": 0,
                      "components": 1},
        },
    }
    doc.update(overrides)
    return doc


def _synth_units() -> dict:
    """4 个手写单元（3 个正式街道名，uid 0..3）。"""
    def row(uid, street):
        return {"uid": uid, "key": f"k{uid}", "district_code": "D",
                "street": street, "area_km2": 1.0, "centroid": [113.0, 23.0],
                "geom": "WKT"}
    return {"crs": "GCJ-02", "units": [
        row(0, "凤阳街道"), row(1, "南华西街道"), row(2, "华洲街道"),
        row(3, "华洲街道"),
    ]}


def _synth_streets() -> dict:
    """正式街道目录顺序：凤阳(0)、南华西(1)、华洲(2)。"""
    def row(name, code):
        return {"name": name, "code": code, "district_code": "D", "geom": "WKT"}
    return {"streets": [
        row("凤阳街道", "c1"), row("南华西街道", "c3"), row("华洲街道", "c2"),
    ]}


def _synth_cases_call(
    oracle_path: Path,
    data_dir: Path,
    *,
    expected_n: int,
    expected_layer_counts: dict,
) -> list:
    """在执行器/解析器/LLM 全部被 mock 为"一调用即抛错"的守卫下调用
    build_synthetic_cases；构造语料必须成功且 mock 计数保持 0。
    """
    with unittest.mock.patch.object(
        nl2.dsl, "execute", side_effect=AssertionError("调用了 03_dsl.execute")
    ), unittest.mock.patch.object(
        nl2.dsl, "eval_rule", side_effect=AssertionError("调用了 03_dsl.eval_rule")
    ), unittest.mock.patch.object(
        nl2, "parse_rule_deterministic",
        side_effect=AssertionError("调用了 parse_rule_deterministic"),
    ), unittest.mock.patch.object(
        nl2, "compile_description",
        side_effect=AssertionError("调用了 compile_description"),
    ), unittest.mock.patch.object(
        nl2, "_default_llm_adapter",
        side_effect=AssertionError("调用了 LLM adapter"),
    ):
        cases = nl2.build_synthetic_cases(
            oracle_path, data_dir,
            expected_n=expected_n,
            expected_layer_counts=expected_layer_counts,
        )
    return cases


class T403Base(unittest.TestCase):
    """公共夹具：临时目录 + 三份 JSON + 输入哈希快照。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = Path(self._tmp.name)
        self.oracle_path = _write_synth_fixture(
            self.data_dir,
            oracle=_synth_oracle(),
            units=_synth_units(),
            streets=_synth_streets(),
        )
        self.snapshot_inputs()

    def snapshot_inputs(self) -> dict:
        """（重新）记录输入文件哈希快照；夹具重写后调用。"""
        self.before = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.data_dir.iterdir())
        }
        return self.before

    def input_unchanged(self):
        """输入文件 sha256 前后一致（只读证明）。"""
        after = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.data_dir.iterdir())
        }
        self.assertEqual(after, self.before, "输入文件被修改")

    def build(self, **kw) -> list:
        return _synth_cases_call(
            self.oracle_path, self.data_dir,
            expected_n=kw.pop("expected_n", 1),
            expected_layer_counts=kw.pop(
                "expected_layer_counts", {"yeidai": 1}),
            **kw,
        )


class TestSynthCardAcceptance(T403Base):
    """卡载可执行验收断言逐项落地（2 条手写围栏 + 4 单元 + 3 街道）。"""

    def _build_card_fixture(self):
        oracle = _synth_oracle()
        oracle["fences"]["SRC-A"] = {
            "name": "甲围栏", "layer": "dealer", "unit_ids": [0, 2],
            "iou": 0.9, "recall": 0.9, "precision": 0.9, "straddle": 0,
            "components": 2,
        }
        # 卡面：G4-002 描述为 南华西街道和华洲街道；输入故意乱序 [3, 1]，
        # 同时证明输出 oracle_unit_ids 升序化。
        oracle["fences"]["SRC-B"] = {
            "name": "乙围栏", "layer": "yeidai", "unit_ids": [3, 1],
            "iou": 0.9, "recall": 0.9, "precision": 0.9, "straddle": 0,
            "components": 1,
        }
        return _write_synth_fixture(
            self.data_dir, oracle=oracle,
            units=_synth_units(), streets=_synth_streets(),
        )

    def test_card_literal_assertions(self):
        oracle_path = self._build_card_fixture()
        # 夹具在 setUp 之后被重写，刷新哈希快照再断言输入不变。
        self.snapshot_inputs()
        cases = _synth_cases_call(
            oracle_path, self.data_dir,
            expected_n=2, expected_layer_counts={"dealer": 1, "yeidai": 1},
        )
        self.assertEqual(cases[0], {
            "label": "[合成语料]",
            "case_id": "G4-001",
            "source": "oracle_unitsets_reverse_streets",
            "layer": "dealer",
            "description": "凤阳街道、华洲街道",
            "oracle_unit_ids": [0, 2],
            "expected_components": 2,
        })
        self.assertEqual(cases[1], {
            "label": "[合成语料]",
            "case_id": "G4-002",
            "source": "oracle_unitsets_reverse_streets",
            "layer": "yeidai",
            "description": "南华西街道和华洲街道",
            "oracle_unit_ids": [1, 3],
            "expected_components": 1,
        })
        self.assertTrue(all(c["label"] == "[合成语料]" for c in cases))
        self.assertTrue(all(set(c) == {
            "label", "case_id", "source", "layer", "description",
            "oracle_unit_ids", "expected_components",
        } for c in cases))
        self.input_unchanged()

    def test_single_street_description_is_formal_name(self):
        cases = self.build()
        self.assertEqual(cases[0]["description"], "华洲街道")
        self.assertEqual(cases[0]["case_id"], "G4-001")
        self.assertEqual(cases[0]["source"], "oracle_unitsets_reverse_streets")

    def test_connector_rotation_by_case_seq(self):
        oracle = _synth_oracle()
        for i in range(1, 9):
            oracle["fences"][f"S{i:02d}"] = {
                "name": f"n{i}", "layer": "yeidai",
                "unit_ids": [0, 1],  # 目录顺序：凤阳、南华西
                "iou": 0.9, "recall": 0.9, "precision": 0.9, "straddle": 0,
                "components": 1,
            }
        oracle["fences"]["SRC-B"] = {
            "name": "乙", "layer": "yeidai", "unit_ids": [2, 3],
            "iou": 0.9, "recall": 0.9, "precision": 0.9, "straddle": 0,
            "components": 1,
        }
        _write_synth_fixture(
            self.data_dir, oracle=oracle,
            units=_synth_units(), streets=_synth_streets(),
        )
        cases = self.build(expected_n=9, expected_layer_counts={"yeidai": 9})
        # src_id 升序：S01..S08, SRC-B → 序号 1..9；连接词槽位 = (序号-1) % 4。
        # 期序：seq1=、 seq2=和 seq3=加上 seq4=以及 seq5=、 seq6=和
        #       seq7=加上 seq8=以及 seq9（单街道，无连接词）。
        got = [c["description"] for c in cases]
        self.assertEqual(
            got,
            ["凤阳街道、南华西街道",
             "凤阳街道和南华西街道",
             "凤阳街道加上南华西街道",
             "凤阳街道以及南华西街道",
             "凤阳街道、南华西街道",
             "凤阳街道和南华西街道",
             "凤阳街道加上南华西街道",
             "凤阳街道以及南华西街道",
             "华洲街道"],
        )

    def test_no_customer_identifiers_in_output(self):
        cases = self.build()
        blob = json.dumps(cases, ensure_ascii=False)
        self.assertNotIn("SRC-B", blob)
        self.assertNotIn("乙围栏", blob)

    def test_case_ids_are_stable_anonymous(self):
        cases = self.build()
        self.assertEqual(cases[0]["case_id"], "G4-001")

    def test_unit_ids_sorted_unique_copy(self):
        cases = self.build()
        self.assertEqual(cases[0]["oracle_unit_ids"], [2, 3])

    def test_expected_components_passthrough(self):
        cases = self.build()
        self.assertEqual(cases[0]["expected_components"], 1)


class TestSynthDisciplines(T403Base):
    """mock 纪律、输入不变、双跑确定性、对象隔离。"""

    def test_double_run_deep_equal_and_isolated(self):
        c1 = self.build()
        self.input_unchanged()
        c2 = self.build()
        self.assertEqual(c1, c2)
        # 返回对象之间不共享可变 list；修改返回值不影响第二次调用。
        c1[0]["oracle_unit_ids"].append(99)
        self.assertNotEqual(c1, c2)
        c3 = self.build()
        self.assertEqual(c3, c2)
        self.assertIsNot(c1[0]["oracle_unit_ids"], c2[0]["oracle_unit_ids"])

    def test_error_messages_carry_label(self):
        with self.assertRaises(nl2.SyntheticCorpusError) as cm:
            self.build(expected_n=2)
        self.assertIn("[合成语料]", str(cm.exception))

    def test_failure_classes_are_labeled_chinese(self):
        def broken(mutate):
            oracle = _synth_oracle()
            units = _synth_units()
            streets = _synth_streets()
            mutate(oracle, units, streets)
            return _write_synth_fixture(
                self.data_dir, oracle=oracle, units=units, streets=streets)

        def expect_fail(**kw):
            with self.assertRaises(nl2.SyntheticCorpusError) as cm:
                _synth_cases_call(kw.pop("path"), self.data_dir, **kw)
            msg = str(cm.exception)
            self.assertRegex(msg, re.compile(r"\[合成语料\]"))
            self.assertTrue(msg)

        expect_fail(
            path=broken(lambda o, u, s: o.__setitem__("method", "9.9")),
            expected_n=1, expected_layer_counts={"yeidai": 1})
        expect_fail(
            path=broken(lambda o, u, s: o["fences"]["SRC-B"]["unit_ids"].clear()),
            expected_n=1, expected_layer_counts={"yeidai": 1})
        expect_fail(
            path=broken(lambda o, u, s: o["fences"]["SRC-B"]["unit_ids"].append(3)),
            expected_n=1, expected_layer_counts={"yeidai": 1})
        expect_fail(
            path=broken(lambda o, u, s: o["fences"]["SRC-B"]["unit_ids"].append(999)),
            expected_n=1, expected_layer_counts={"yeidai": 1})
        expect_fail(
            path=broken(lambda o, u, s: o["fences"]["SRC-B"].__setitem__(
                "components", 0)),
            expected_n=1, expected_layer_counts={"yeidai": 1})

    def test_street_not_in_catalog_fails(self):
        units = _synth_units()
        # 围栏 SRC-B 引用 uid [2, 3]；改这两个单元的街道才必然触发。
        units["units"][2]["street"] = "不存在街道"
        units["units"][3]["street"] = "不存在街道"
        path = _write_synth_fixture(
            self.data_dir, oracle=_synth_oracle(), units=units,
            streets=_synth_streets())
        with self.assertRaises(nl2.SyntheticCorpusError) as cm:
            _synth_cases_call(
                path, self.data_dir,
                expected_n=1, expected_layer_counts={"yeidai": 1})
        self.assertIn("[合成语料]", str(cm.exception))

    def test_illegal_schema_extra_field_fails(self):
        oracle = _synth_oracle()
        oracle["fences"]["SRC-B"]["unexpected"] = 1
        path = _write_synth_fixture(
            self.data_dir, oracle=oracle, units=_synth_units(),
            streets=_synth_streets())
        with self.assertRaises(nl2.SyntheticCorpusError) as cm:
            _synth_cases_call(
                path, self.data_dir,
                expected_n=1, expected_layer_counts={"yeidai": 1})
        self.assertIn("[合成语料]", str(cm.exception))
        self.assertIn("未知字段", str(cm.exception))




class TestSynthRealData(unittest.TestCase):
    """真实数据 smoke（data/pilot 存在时执行；卡载锚点）。"""

    REAL = Path(__file__).resolve().parents[2] / "data" / "pilot"

    @classmethod
    def setUpClass(cls):
        if not (cls.REAL / "oracle_unitsets.json").is_file():
            raise unittest.SkipTest("data/pilot 不存在（业务数据不入 git）")
        cls.cases = _synth_cases_call(
            cls.REAL / "oracle_unitsets.json", cls.REAL,
            expected_n=21, expected_layer_counts={"dealer": 4, "yeidai": 17},
        )

    def test_layer_count_mismatch_fails(self):
        # 真实数据 4+17；故意传错分层计数必须失败，不得静默通过。
        with self.assertRaises(nl2.SyntheticCorpusError) as cm:
            _synth_cases_call(
                self.REAL / "oracle_unitsets.json", self.REAL,
                expected_n=21, expected_layer_counts={"dealer": 5, "yeidai": 16},
            )
        self.assertIn("[合成语料]", str(cm.exception))

    def test_card_smoke_anchor(self):
        cases = self.cases
        self.assertEqual(len(cases), 21)
        self.assertEqual(
            [c["case_id"] for c in cases],
            [f"G4-{i:03d}" for i in range(1, 22)])
        self.assertEqual(sum(c["layer"] == "dealer" for c in cases), 4)
        self.assertEqual(sum(c["layer"] == "yeidai" for c in cases), 17)
        self.assertTrue(all(c["oracle_unit_ids"] for c in cases))
        self.assertTrue(all(c["description"] for c in cases))
        self.assertTrue(all(c["label"] == "[合成语料]" for c in cases))

    def test_real_descriptions_never_leak_customer_identifiers(self):
        street_catalog = {
            s["name"] for s in json.loads(
                (self.REAL / "streets.json").read_text(encoding="utf-8")
            )["streets"]
        }
        oracle = json.loads(
            (self.REAL / "oracle_unitsets.json").read_text(encoding="utf-8"))
        blob = json.dumps(self.cases, ensure_ascii=False)
        for src, fence in oracle["fences"].items():
            self.assertNotIn(src, blob)
            self.assertNotIn(fence["name"], blob)
        for case in self.cases:
            parts = re.split(r"、|和|加上|以及", case["description"])
            self.assertTrue(parts)
            self.assertTrue(all(p in street_catalog for p in parts))

    def test_input_files_unchanged_after_build(self):
        before = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.REAL.iterdir())
        }
        _synth_cases_call(
            self.REAL / "oracle_unitsets.json", self.REAL,
            expected_n=21, expected_layer_counts={"dealer": 4, "yeidai": 17},
        )
        after = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.REAL.iterdir())
        }
        self.assertEqual(after, before)



# ===========================================================================
# T-404：G4 规则路径集成、指标与 D-1 双表报告
# ===========================================================================

import subprocess  # noqa: E402
import tempfile  # noqa: E402


class _CountingBoom:
    """一调用即抛 AssertionError 的守卫桩（LLM adapter / HTTP 替身）。"""

    def __init__(self, label: str):
        self.label = label

    def __call__(self, *args, **kwargs):
        raise AssertionError(f"调用了 {self.label}")


def _g4_full_ctx() -> dict:
    """最小完整执行 ctx： streets/districts 与 03 execute 所需全量字段。

    uid 0..3：凤阳(0)、南华西(1)、华洲(2,3)。邻接 0-1、2-3：凤阳+南华西
    并集 = 1 个连通分量；华洲街 = 2 个连通分量（components 断言用）。
    """
    geom = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"
    units = [
        {"uid": 0, "key": "k0", "district_code": "D", "street": "凤阳街道",
         "area_km2": 1.0, "centroid": [113.0, 23.0], "geom": geom},
        {"uid": 1, "key": "k1", "district_code": "D", "street": "南华西街道",
         "area_km2": 1.0, "centroid": [113.0, 23.0], "geom": geom},
        {"uid": 2, "key": "k2", "district_code": "D", "street": "华洲街道",
         "area_km2": 1.0, "centroid": [113.0, 23.0], "geom": geom},
        {"uid": 3, "key": "k3", "district_code": "D", "street": "华洲街道",
         "area_km2": 1.0, "centroid": [113.0, 23.0], "geom": geom},
    ]
    streets = [
        {"name": "凤阳街道", "code": "c1", "district_code": "D", "geom": geom},
        {"name": "南华西街道", "code": "c3", "district_code": "D", "geom": geom},
        {"name": "华洲街道", "code": "c2", "district_code": "D", "geom": geom},
    ]
    return {
        "data_dir": ".",
        "crs": "GCJ-02",
        "units": units,
        "unit_geoms": [None, None, None, None],
        "streets": streets,
        "street_geoms": [None, None, None],
        "districts": [{"name": "海珠区", "code": "D", "district_code": "D",
                       "geom": geom}],
        "district_geoms": [None],
        "adjacency": {0: [1], 1: [0], 2: [3], 3: [2]},
        "link_min_m": 50,
    }


def _g4_case(case_id, description, oracle, expected_components, layer="dealer"):
    """合法 case 构造器（label 强制 [合成语料]）。"""
    return {
        "label": nl2.SYNTHETIC_LABEL,
        "case_id": case_id,
        "source": "oracle_unitsets_reverse_streets",
        "layer": layer,
        "description": description,
        "oracle_unit_ids": oracle,
        "expected_components": expected_components,
    }


def _g4_state(tmp_dir: Path, *, result="pass", tests=231,
              l0="14/14 exact") -> Path:
    """写一份最小合法 state.json；返回路径。"""
    path = tmp_dir / "state.json"
    path.write_text(json.dumps(
        {"gates": {"G3": {"result": result, "tests": tests,
                          "l0_crosscheck": l0}}},
        ensure_ascii=False), encoding="utf-8")
    return path


def _g4_guarded_evaluate(cases, ctx):
    """在 LLM adapter / HTTP / compile_description 全部一调用即抛的守卫下评测。

    完整真实 G4 仍必须跑完且守卫计数保持 0 —— 规则路径纪律的可执行证明。
    """
    calls = {"adapter": 0, "socket": 0, "compile": 0}
    def adapter_boom(*a, **k):
        calls["adapter"] += 1
        raise AssertionError("调用了 LLM adapter")
    def compile_boom(*a, **k):
        calls["compile"] += 1
        raise AssertionError("调用了 compile_description")
    with unittest.mock.patch.object(
        nl2, "_default_llm_adapter", side_effect=adapter_boom,
    ), unittest.mock.patch.object(
        nl2, "compile_description", side_effect=compile_boom,
    ), unittest.mock.patch.object(
        socket, "socket", side_effect=AssertionError("发起了网络调用"),
    ), unittest.mock.patch.object(
        socket, "create_connection", side_effect=AssertionError("发起了网络调用"),
    ):
        evaluation = nl2.evaluate_g4_rule_path(cases, ctx)
    return evaluation, calls


class T404Base(unittest.TestCase):
    """公共夹具：临时目录 + state.json + 输入哈希快照。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_dir = Path(self._tmp.name)
        self.state_path = _g4_state(self.tmp_dir)

    def snapshot(self, paths):
        return {
            str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in paths
        }


class TestG4CardAcceptance(T404Base):
    """卡载可执行验收断言逐项落地：3 case（含 1 个解析失败）。"""

    def build_3_cases(self):
        # ok1：凤阳+南华西 → uid {0,1}，oracle 同 → J=1.0，components 1/1。
        # ok2：华洲+南华西 → predicted {1,2,3}，oracle {2,3} → J=2/3
        #     （|交|=2，|并|=3），predicted components=2 与预期一致。
        # fail：幽灵街道 → RuleParseError → J=0.0 失败行进分母。
        return [
            _g4_case("G4-001", "凤阳街道和南华西街道", [0, 1], 1),
            _g4_case("G4-002", "华洲街道、南华西街道", [2, 3], 2),
            _g4_case("G4-003", "幽灵街道", [0], 1),
        ]

    def test_card_metric_formulas(self):
        cases = self.build_3_cases()
        evaluation, calls = _g4_guarded_evaluate(cases, _g4_full_ctx())
        self.assertEqual(calls, {"adapter": 0, "socket": 0, "compile": 0})
        self.assertEqual(evaluation["n"], 3)
        rows = evaluation["rows"]
        self.assertEqual(len(rows), 3)
        row_ok1, row_ok2, row_fail = rows
        self.assertEqual(row_ok1["case_id"], "G4-001")
        self.assertEqual(row_ok2["case_id"], "G4-002")
        self.assertEqual(row_fail["case_id"], "G4-003")
        # 卡载断言公式（ok2 即卡载 row_ok：J=2/3 且 components_correct）。
        self.assertEqual(row_ok2["jaccard"], 2 / 3)
        self.assertIs(row_ok2["components_correct"], True)
        self.assertIs(row_ok1["components_correct"], True)
        self.assertIs(row_fail["parse_success"], False)
        self.assertEqual(row_fail["jaccard"], 0.0)
        self.assertIsNone(row_fail["predicted_components"])
        self.assertIsNone(row_fail["rule"])
        self.assertIsNone(row_fail["path"])
        self.assertEqual(row_fail["predicted_unit_ids"], [])
        self.assertIs(row_fail["llm_unavailable"], True)
        self.assertTrue(row_fail["error"])
        summary = evaluation
        self.assertEqual(summary["rule_parse_success"], 2)
        self.assertEqual(summary["rule_parse_rate"], 2 / 3)
        self.assertEqual(summary["components_accuracy"], 2 / 3)
        self.assertEqual(summary["components_correct"], 2)
        self.assertEqual(
            summary["median_jaccard"],
            statistics.median([1.0, 2 / 3, 0.0]))
        self.assertIs(summary["rule_path_only"], True)
        self.assertIs(summary["llm_evaluated"], False)
        self.assertIs(summary["has_preset_pass_line"], False)
        self.assertEqual(len(summary["parse_failures"]), 1)
        self.assertEqual(summary["parse_failures"][0]["case_id"], "G4-003")
        # 失败行与其余行同键集合（同一 schema）。
        self.assertEqual(set(row_fail.keys()), set(row_ok1.keys()))

    def test_card_row_schema_exact_keys(self):
        cases = self.build_3_cases()
        evaluation = nl2.evaluate_g4_rule_path(cases, _g4_full_ctx())
        expected_keys = {
            "label", "case_id", "layer", "description", "parse_success",
            "path", "llm_unavailable", "rule", "predicted_unit_ids",
            "jaccard", "predicted_components", "expected_components",
            "components_correct", "error",
        }
        for row in evaluation["rows"]:
            self.assertEqual(set(row.keys()), expected_keys)
        ok = evaluation["rows"][0]
        self.assertEqual(
            ok["rule"],
            {"op": "union", "args": [
                {"op": "in_street", "name": "凤阳街道"},
                {"op": "in_street", "name": "南华西街道"},
            ]})
        dsl.validate_rule(ok["rule"])

    def test_synthetic_label_everywhere(self):
        cases = self.build_3_cases()
        evaluation, _ = _g4_guarded_evaluate(cases, _g4_full_ctx())
        self.assertEqual(evaluation["label"], nl2.SYNTHETIC_LABEL)
        for row in evaluation["rows"]:
            self.assertEqual(row["label"], nl2.SYNTHETIC_LABEL)
        for row in evaluation["parse_failures"]:
            self.assertEqual(row["label"], nl2.SYNTHETIC_LABEL)


class TestG4InputContract(T404Base):
    """空 oracle / 非法 case / ctx 缺失的显式失败（绝不自定义空并空得分）。"""

    def test_empty_oracle_is_input_contract_error(self):
        cases = [_g4_case("G4-001", "凤阳街道", [], 1)]
        with self.assertRaises(nl2.G4EvaluationError) as cm:
            nl2.evaluate_g4_rule_path(cases, _g4_full_ctx())
        self.assertIn("[合成语料]", str(cm.exception))
        self.assertIn("空 oracle", str(cm.exception))

    def test_wrong_label_rejected(self):
        case = _g4_case("G4-001", "凤阳街道", [0], 1)
        case["label"] = "真实合同"
        with self.assertRaises(nl2.G4EvaluationError) as cm:
            nl2.evaluate_g4_rule_path([case], _g4_full_ctx())
        self.assertIn("label", str(cm.exception))

    def test_bad_expected_components_rejected(self):
        case = _g4_case("G4-001", "凤阳街道", [0], 0)
        with self.assertRaises(nl2.G4EvaluationError):
            nl2.evaluate_g4_rule_path([case], _g4_full_ctx())

    def test_missing_ctx_fails_explicitly(self):
        cases = [_g4_case("G4-001", "凤阳街道", [0], 1)]
        with self.assertRaises(nl2.Nl2RuleError):
            nl2.evaluate_g4_rule_path(cases, {})


class TestG4Report(T404Base):
    """D-1 双表报告：物理分离、固定文案、无聚合、无 PASS/FAIL、双跑一致。"""

    def make_evaluation(self):
        cases = [
            _g4_case("G4-001", "凤阳街道和南华西街道", [0, 1], 1),
            _g4_case("G4-002", "华洲街道", [2], 1),
            _g4_case("G4-003", "幽灵街道", [0], 1),
        ]
        return nl2.evaluate_g4_rule_path(cases, _g4_full_ctx())

    def test_two_tables_physically_separated(self):
        report = nl2.render_g4_report(self.make_evaluation(), self.state_path)
        self.assertEqual(report.count("### 表 A："), 1)
        self.assertEqual(report.count("### 表 B："), 1)
        self.assertLess(
            report.index("### 表 A："), report.index("### 表 B："))
        sep = report.index("\n---\n")
        self.assertLess(report.index("### 表 A："), sep)
        self.assertGreater(report.index("### 表 B："), sep)
        # 局限性段落按卡载样例位于表 B 标题之后（表头之前），不是表 A 与
        # --- 之间；分隔符本身仍在两表标题之间。
        between = report[report.index("### 表 A："):report.index("### 表 B：")]
        self.assertNotIn(nl2.SYNTHETIC_LIMITATION, between)
        table_b_head = report[report.index("### 表 B："):report.index("| 标签")]
        self.assertIn(nl2.SYNTHETIC_LIMITATION, table_b_head)

    def test_table_a_no_g4_metrics_and_table_b_no_g3_aggregate(self):
        report = nl2.render_g4_report(self.make_evaluation(), self.state_path)
        sep = report.index("\n---\n")
        table_a = report[:sep]
        table_b = report[sep:]
        self.assertNotIn("Jaccard", table_a)
        self.assertNotIn(nl2.SYNTHETIC_LABEL, table_a)
        self.assertNotIn("100%", table_b)
        # 表 A 不含任何 G4 数值行；表 B 不含 G3 单测数字聚合。
        self.assertNotIn("231", table_b)

    def test_fixed_limitation_wording_exact(self):
        report = nl2.render_g4_report(self.make_evaluation(), self.state_path)
        self.assertIn(f"⚠️ {nl2.SYNTHETIC_LIMITATION}。", report)
        self.assertIn(f"{nl2.RULE_PATH_ONLY_NOTE}。", report)
        self.assertIn("不得据此宣称已具备真实客户合同的端到端能力", report)

    def test_summary_lines_have_label_and_no_pass_line(self):
        report = nl2.render_g4_report(self.make_evaluation(), self.state_path)
        for prefix in (
            f"{nl2.SYNTHETIC_LABEL} 中位单元集 Jaccard",
            f"{nl2.SYNTHETIC_LABEL} components 准确率",
            f"{nl2.SYNTHETIC_LABEL} 规则路径解析成功率",
            f"{nl2.SYNTHETIC_LABEL} 解析失败明细",
        ):
            self.assertEqual(report.count(prefix), 1)
            line = [ln for ln in report.splitlines()
                    if ln.startswith(prefix)][0]
            self.assertIn("无预设通过线，仅作信息报告", line)
        self.assertNotIn("PASS", report[report.index("### 表 B："):])
        self.assertNotIn("FAIL", report[report.index("### 表 B："):])

    def test_every_table_b_row_has_label(self):
        report = nl2.render_g4_report(self.make_evaluation(), self.state_path)
        table_b = report[report.index("### 表 B："):]
        data_rows = [ln for ln in table_b.splitlines()
                     if ln.startswith("| [") or ln.startswith("| ")]
        data_rows = [ln for ln in data_rows
                     if not ln.startswith("| 标签")
                     and not ln.startswith("|---")]
        self.assertEqual(len(data_rows), 3)  # 3 条 case 行（汇总行非表格行）
        for ln in data_rows:
            self.assertIn(nl2.SYNTHETIC_LABEL, ln)

    def test_no_merged_score_or_ranking(self):
        report = nl2.render_g4_report(self.make_evaluation(), self.state_path)
        self.assertNotIn("总分", report)
        self.assertNotIn("G3+G4", report)
        self.assertNotIn("平均分", report)
        self.assertNotIn("排名", report)

    def test_g3_not_pass_renders_no_100_claim(self):
        bad_state = _g4_state(self.tmp_dir, result="fail", tests=10,
                              l0="0/14")
        with self.assertRaises(nl2.G4EvaluationError) as cm:
            nl2.render_g4_report(self.make_evaluation(), bad_state)
        self.assertIn("pass", str(cm.exception))

    def test_deterministic_bytes_two_runs(self):
        text1 = nl2.render_g4_report(self.make_evaluation(), self.state_path)
        text2 = nl2.render_g4_report(self.make_evaluation(), self.state_path)
        self.assertEqual(text1, text2)
        self.assertEqual(
            hashlib.sha256(text1.encode("utf-8")).hexdigest(),
            hashlib.sha256(text2.encode("utf-8")).hexdigest())


class TestG4AtomicWrite(T404Base):
    """write_text_atomic：原子替换、UTF-8、失败不留半份。"""

    def test_write_and_reread(self):
        path = self.tmp_dir / "sub" / "r.md"
        nl2.write_text_atomic(path, "中文内容\n第二行\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "中文内容\n第二行\n")
        # 同目录无残留临时文件。
        leftovers = [p for p in path.parent.iterdir() if p.name != "r.md"]
        self.assertEqual(leftovers, [])

    def test_overwrite_replaces_whole_file(self):
        path = self.tmp_dir / "r.md"
        nl2.write_text_atomic(path, "旧内容" * 100)
        nl2.write_text_atomic(path, "新")
        self.assertEqual(path.read_text(encoding="utf-8"), "新")


class TestG4Cli(T404Base):
    """g4 CLI：subprocess 端到端（真实网络 0 次；--llm-config 拒绝）。"""

    def setUp(self):
        super().setUp()
        self.data_dir = self.tmp_dir / "pilot"
        self.data_dir.mkdir()
        geom = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.0))"
        (self.data_dir / "units.json").write_text(json.dumps({
            "crs": "GCJ-02", "units": [
                {"uid": i, "key": f"k{i}", "district_code": "D",
                 "street": s, "area_km2": 1.0,
                 "centroid": [113.0, 23.0], "geom": geom}
                for i, s in enumerate(
                    ["凤阳街道", "南华西街道", "华洲街道", "华洲街道"])
            ]}, ensure_ascii=False), encoding="utf-8")
        (self.data_dir / "streets.json").write_text(json.dumps({
            "streets": [
                {"name": "凤阳街道", "code": "c1", "district_code": "D",
                 "geom": geom},
                {"name": "南华西街道", "code": "c3", "district_code": "D",
                 "geom": geom},
                {"name": "华洲街道", "code": "c2", "district_code": "D",
                 "geom": geom},
            ]}, ensure_ascii=False), encoding="utf-8")
        (self.data_dir / "districts.json").write_text(json.dumps({
            "streets": [{"name": "海珠区", "code": "D",
                         "district_code": "D", "geom": geom}]},
            ensure_ascii=False), encoding="utf-8")
        (self.data_dir / "unit_graph.json").write_text(json.dumps({
            "adjacency": {"0": [1], "1": [0], "2": [3], "3": [2]},
            "link_min_m": 50}), encoding="utf-8")
        (self.data_dir / "lines.json").write_text(json.dumps({
            "schema_version": "p5-lines-v1", "crs": "GCJ-02",
            "source_crs": "WGS-84", "source_sha256": "a" * 64,
            "counts": {"source_elements": 1, "source_named_ways": 1,
                       "output_names": 1, "output_parts": 1},
            "lines": [{"name": "环岛路", "classes": ["highway"],
                       "osm_way_ids": [1],
                       "geom": "LINESTRING (113.0 23.0, 113.1 23.1)"}]},
            ensure_ascii=False), encoding="utf-8")
        # g4 子命令生产门禁固定 21 条（dealer 4 + yeidai 17）：生成式夹具。
        # dealer 围栏引用凤阳+南华西 {0,1}；yeidai 围栏引用华洲 {2,3}。
        fences = {}
        for i in range(4):
            fences[f"SRC-D{i:02d}"] = {
                "name": f"d{i}", "layer": "dealer", "unit_ids": [0, 1],
                "iou": 0.9, "recall": 0.9, "precision": 0.9,
                "straddle": 0, "components": 1}
        for i in range(17):
            fences[f"SRC-Y{i:02d}"] = {
                "name": f"y{i}", "layer": "yeidai", "unit_ids": [2, 3],
                "iou": 0.9, "recall": 0.9, "precision": 0.9,
                "straddle": 0, "components": 1}
        self.oracle_path = self.data_dir / "oracle_unitsets.json"
        self.oracle_path.write_text(json.dumps({
            "method": "3.6-v1.4", "link_min_m": 50, "boundary_centroids": 0,
            "fences": fences,
        }, ensure_ascii=False), encoding="utf-8")
        self.report_path = self.tmp_dir / "G4_REPORT.md"

    def _run(self, *extra):
        cmd = [sys.executable, str(_SRC / "04_nl2rule.py"), "g4",
               "--data", str(self.data_dir),
               "--oracle", str(self.oracle_path),
               "--state", str(self.state_path),
               "--report", str(self.report_path), *extra]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    def test_mini_gate_end_to_end(self):
        proc = self._run()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(self.report_path.is_file())
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
        self.assertTrue(lines)
        for ln in lines:
            self.assertTrue(
                ln.startswith(nl2.SYNTHETIC_LABEL),
                f"stdout 行缺 [合成语料] 标签：{ln}")
        report = self.report_path.read_text(encoding="utf-8")
        self.assertIn("### 表 A：", report)
        self.assertIn("### 表 B：", report)
        self.assertEqual(len(lines), 22)  # 21 条 case 行 + 1 条汇总行
        self.assertIn("n=21", lines[-1])

    def test_llm_config_rejected(self):
        proc = self._run("--llm-config", str(self.state_path))
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.report_path.exists())

    def test_bad_oracle_nonzero_and_no_report(self):
        self.oracle_path.write_text('{"broken": true}', encoding="utf-8")
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(self.data_dir.iterdir())}
        proc = self._run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("[GATE-FAIL]", proc.stderr)
        self.assertFalse(self.report_path.exists())
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(self.data_dir.iterdir())}
        self.assertEqual(after, before)

    def test_stdout_no_customer_identifiers(self):
        proc = self._run()
        self.assertEqual(proc.returncode, 0)
        # 客户围栏 name/src_id 绝不进 stdout（case_id 是匿名 G4-001）。
        self.assertNotIn("SRC-A", proc.stdout)
        self.assertNotIn("甲", proc.stdout)
        self.assertNotIn("unit_ids", proc.stdout)


class TestG4RealData(T404Base):
    """真实数据全量 G4（data/pilot 存在时执行；卡载锚点）。"""

    REAL = Path(__file__).resolve().parents[2] / "data" / "pilot"

    @classmethod
    def setUpClass(cls):
        if not (cls.REAL / "oracle_unitsets.json").is_file():
            raise unittest.SkipTest("data/pilot 不存在（业务数据不入 git）")

    def test_full_21_cases_metrics_in_bounds(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(self.REAL.iterdir())}
        ctx = nl2.dsl.load_pilot_context(self.REAL)
        cases = nl2.build_synthetic_cases(
            self.REAL / "oracle_unitsets.json", self.REAL,
            expected_n=21,
            expected_layer_counts={"dealer": 4, "yeidai": 17},
        )
        evaluation, calls = _g4_guarded_evaluate(cases, ctx)
        self.assertEqual(calls["adapter"], 0)
        self.assertEqual(calls["compile"], 0)
        self.assertEqual(evaluation["n"], 21)
        self.assertEqual(len(evaluation["rows"]), 21)
        self.assertTrue(
            all(r["label"] == nl2.SYNTHETIC_LABEL
                for r in evaluation["rows"]))
        self.assertGreaterEqual(evaluation["median_jaccard"], 0.0)
        self.assertLessEqual(evaluation["median_jaccard"], 1.0)
        self.assertGreaterEqual(evaluation["components_accuracy"], 0.0)
        self.assertLessEqual(evaluation["components_accuracy"], 1.0)
        self.assertGreaterEqual(evaluation["rule_parse_rate"], 0.0)
        self.assertLessEqual(evaluation["rule_parse_rate"], 1.0)
        self.assertLessEqual(evaluation["components_correct"], 21)
        self.assertLessEqual(evaluation["rule_parse_success"], 21)
        self.assertIs(evaluation["llm_evaluated"], False)
        self.assertIs(evaluation["rule_path_only"], True)
        self.assertIs(evaluation["has_preset_pass_line"], False)
        report = nl2.render_g4_report(evaluation, _REAL_STATE)
        self.assertIn("### 表 A：", report)
        self.assertIn("### 表 B：", report)
        self.assertEqual(report.count("\n---\n"), 1)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(self.REAL.iterdir())}
        self.assertEqual(after, before, "data/pilot 输入被修改")


_REAL_STATE = Path(__file__).resolve().parents[2] / "sraf-pilot" / "state.json"


if __name__ == "__main__":
    unittest.main()
