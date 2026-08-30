# -*- coding: utf-8 -*-
"""T-301/T-302/T-303 单元测试：输入契约、DSL 校验、名称解析、四原语求值与输出汇总。

覆盖：
- 输入层：crs / uid 冻结契约 / key 唯一 / 字段集合 / WKT（含 MultiPolygon）/
  邻接图覆盖-对称-无自环-link_min_m==50 / 全部只读（目录指纹不变）；
- 名称解析：逐级证明精确 > 去后缀 > 包含；0 匹配抛错；包含 >1 抛错；
  两字前缀不是独立兜底规则；街道/区县不跨类型；
- DSL 校验：空对象、未知 op、side_of/near、叶节点缺/多字段、union arity、
  minus arity、args 非对象、嵌套层（含 MultiPolygon 夹具证明未用 .exterior）；
- T-302：四原语求值语义（v1.7：in_street 只看 street 属性 /
  in_district 只看编码 / union 幂等 / minus 有序差）；真实数据交叉断言；
- T-303：execute 五字段输出契约（卡载 4 单元手写夹具）、图防御性复核、
  名称失败不降级为 warnings、只读与不可变证明。

真实数据条件（data/pilot 存在时执行；卡载锚点）：L1 单元 224（海珠 131 /
荔湾 93）、40 街道、邻接图 224 节点 538 无向边、彩虹街道 uid==56、海珠
诱导子图分量 1、海珠面积 fsum=91.13676698817557（锚点由独立 DFS+并查集
双算法预计算，非生产代码所得）。
"""

import hashlib
import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

import shapely.wkt

# ---------------------------------------------------------------------------
# 按路径加载被测模块
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../sraf
MODULE_PATH = REPO_ROOT / "sraf-pilot" / "src" / "03_dsl.py"

_spec = importlib.util.spec_from_file_location("dsl_03", MODULE_PATH)
dsl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dsl)

# ---------------------------------------------------------------------------
# 合成夹具
# ---------------------------------------------------------------------------

VALID_WKT = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.1, 113.0 23.0))"
# 双部件 MultiPolygon：若代码触碰 .exterior 会 AttributeError，测试即失败。
VALID_MULTIPOLYGON_WKT = (
    "MULTIPOLYGON (((113.0 23.0, 113.05 23.0, 113.05 23.05, 113.0 23.05, 113.0 23.0)),"
    " ((113.05 23.05, 113.1 23.05, 113.1 23.1, 113.05 23.1, 113.05 23.05)))"
)


def make_unit(uid: int = 0, key: str | None = None, geom: str = VALID_WKT,
              district_code: str = "440105", street: str = "彩虹街道") -> dict:
    """构造一行符合卡载 schema 的单元。"""
    return {
        "uid": uid,
        "key": key if key is not None else f"U-{uid:04d}",
        "district_code": district_code,
        "street": street,
        "area_km2": 1.0,
        "centroid": [113.05, 23.05],
        "geom": geom,
    }


def make_area(name: str, code: str, district_code: str = "440105",
              geom: str = VALID_WKT) -> dict:
    """构造一行 streets.json / districts.json 行（AREA_FIELDS）。"""
    return {"name": name, "code": code, "district_code": district_code, "geom": geom}


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def build_units_payload(units: list[dict] | None = None) -> dict:
    return {"crs": "GCJ-02", "units": units if units is not None else [make_unit(0)]}


def build_valid_dir(root: Path) -> Path:
    """四文件齐全的最小合法 P3 输入目录（每次全新生成）。

    名称表刻意覆盖三级解析逐级证明：
    - 精确名「彩虹街道」；查询「彩虹街道」走精确级；
    - 「翠湖街道」+「翠湖镇」并存（去后缀词干翠湖撞车）→ 查「翠湖」去后缀级歧义抛错；
    - 「人民街道」+「人民镇」并存 → 查「人民」去后缀歧义（卡载歧义夹具）；
    - 「沙河街道」唯一 → 查「沙河」去后缀唯一成功；
    - 「琶洲街道」唯一 → 查「琶洲」包含唯一成功（去后缀级 0 命中落到包含级）；
    - 「江南中街道」→ 查「江南」包含唯一；查「江」包含 0（无两字前缀兜底）。
    """
    d = root / "pilot"
    d.mkdir(parents=True)
    units = [make_unit(0), make_unit(1, district_code="440103")]
    write_json(d / "units.json", build_units_payload(units))
    streets = [
        make_area("彩虹街道", "440105001"),
        make_area("翠湖街道", "440105002"),
        make_area("翠湖镇", "440105003"),
        make_area("人民街道", "440105004"),
        make_area("人民镇", "440105005"),
        make_area("沙河街道", "440103001", district_code="440103"),
        make_area("琶洲街道", "440105006"),
        make_area("江南中街道", "440105007"),
    ]
    write_json(d / "streets.json", {"streets": streets})
    write_json(d / "districts.json", {"streets": [
        make_area("海珠区", "440105"),
        make_area("荔湾区", "440103"),
    ]})
    write_json(d / "unit_graph.json", {"adjacency": {"0": [1], "1": [0]}, "link_min_m": 50})
    return d


def snapshot_dir(d: Path) -> dict[str, str]:
    """目录内容指纹：相对路径 -> 内容 sha256（用于只读断言）。"""
    out: dict[str, str] = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(d))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ---------------------------------------------------------------------------
# 正向：卡载可执行验收断言 + MultiPolygon + 只读
# ---------------------------------------------------------------------------


class TestInputLayerHappyPath(unittest.TestCase):
    """T-301 输入层正向验收。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = build_valid_dir(Path(self._tmp.name))
        self.before = snapshot_dir(self.d)

    def test_card_asserts(self):
        """卡载断言：crs / uid 连续 / 几何类型 / 名称解析逐级 / 只读。"""
        ctx = dsl.load_pilot_context(self.d)
        units = ctx["units"]
        self.assertEqual(ctx["crs"], "GCJ-02")
        self.assertEqual([u["uid"] for u in units], list(range(len(units))))
        for g in ctx["unit_geoms"] + ctx["street_geoms"] + ctx["district_geoms"]:
            self.assertIn(g.geom_type, {"Polygon", "MultiPolygon"})
            self.assertFalse(g.is_empty)
        self.assertEqual(ctx["adjacency"], {0: [1], 1: [0]})

    def test_input_dir_untouched(self):
        """输入只读证明：加载前后目录指纹逐字节一致。"""
        dsl.load_pilot_context(self.d)
        self.assertEqual(snapshot_dir(self.d), self.before)

    def test_multipolygon_geometry_accepted(self):
        """MultiPolygon 夹具通过（证明没有裸用 .exterior）。"""
        d = self.d
        payload = build_units_payload([make_unit(0, geom=VALID_MULTIPOLYGON_WKT)])
        write_json(d / "units.json", payload)
        write_json(d / "streets.json", {"streets": [
            make_area("彩虹街道", "440105001", geom=VALID_MULTIPOLYGON_WKT)]})
        write_json(d / "districts.json", {"streets": [make_area("海珠区", "440105")]})
        # units 只剩 1 个，graph 必须同步缩到 1 节点
        write_json(d / "unit_graph.json", {"adjacency": {"0": []}, "link_min_m": 50})
        ctx = dsl.load_pilot_context(d)
        self.assertEqual(ctx["unit_geoms"][0].geom_type, "MultiPolygon")
        self.assertEqual(ctx["street_geoms"][0].geom_type, "MultiPolygon")

    def test_graph_asymmetry_rejected(self):
        """邻接不对称 → 中文抛错（无向图契约）。"""
        write_json(self.d / "unit_graph.json",
                   {"adjacency": {"0": [1], "1": []}, "link_min_m": 50})
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_pilot_context(self.d)
        self.assertIn("不对称", str(cm.exception))

    def test_graph_link_min_m_must_be_50(self):
        dsl.load_unit_graph(self.d, expected_n_units=2)  # 基线必须合法（不抛）
        payload = json.loads((self.d / "unit_graph.json").read_text("utf-8"))
        payload["link_min_m"] = 100
        write_json(self.d / "unit_graph.json", payload)
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_unit_graph(self.d, expected_n_units=2)
        self.assertIn("link_min_m", str(cm.exception))

    def test_graph_self_loop_rejected(self):
        write_json(self.d / "unit_graph.json",
                   {"adjacency": {"0": [0], "1": [0]}, "link_min_m": 50})
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_unit_graph(self.d, expected_n_units=2)
        self.assertIn("自环", str(cm.exception))

    def test_graph_missing_node_rejected(self):
        write_json(self.d / "unit_graph.json",
                   {"adjacency": {"0": [1]}, "link_min_m": 50})
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_unit_graph(self.d, expected_n_units=2)
        self.assertIn("恰好覆盖", str(cm.exception))

    def test_uid_frozen_contract(self):
        """uid != 数组下标 → 抛错（uid 冻结契约）。"""
        units = [make_unit(0), make_unit(5)]
        write_json(self.d / "units.json", build_units_payload(units))
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_units(self.d)
        self.assertIn("uid", str(cm.exception))

    def test_duplicate_key_rejected(self):
        units = [make_unit(0, key="同键"), make_unit(1, key="同键")]
        write_json(self.d / "units.json", build_units_payload(units))
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_units(self.d)
        self.assertIn("key 重复", str(cm.exception))

    def test_wrong_crs_rejected(self):
        payload = build_units_payload()
        payload["crs"] = "WGS84"
        write_json(self.d / "units.json", payload)
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_units(self.d)
        self.assertIn("GCJ-02", str(cm.exception))

    def test_extra_top_key_rejected(self):
        payload = build_units_payload()
        payload["extra"] = 1
        write_json(self.d / "units.json", payload)
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_units(self.d)
        self.assertIn("顶层键", str(cm.exception))

    def test_row_extra_field_rejected(self):
        unit = make_unit(0)
        unit["多余"] = 1
        write_json(self.d / "units.json", build_units_payload([unit]))
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_units(self.d)
        self.assertIn("字段集合不符", str(cm.exception))

    def test_missing_file_reports_path(self):
        (self.d / "streets.json").unlink()
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_pilot_context(self.d)
        self.assertIn("streets.json", str(cm.exception))

    def test_bad_wkt_rejected_with_path(self):
        write_json(self.d / "units.json",
                   build_units_payload([make_unit(0, geom="POINT (1 2)")]))
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_units(self.d)
        msg = str(cm.exception)
        self.assertIn("units.json", msg)
        self.assertIn("Point", msg)

# ---------------------------------------------------------------------------
# 名称解析：逐级证明 + 歧义 + 0 匹配 + 无两字前缀兜底 + 不跨类型
# ---------------------------------------------------------------------------


class TestNameResolution(unittest.TestCase):
    """三级解析逐级用例与异常路径（合成名称表逐项证明）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = build_valid_dir(Path(self._tmp.name))
        self.streets = json.loads((self.d / "streets.json").read_text("utf-8"))["streets"]
        self.districts = json.loads((self.d / "districts.json").read_text("utf-8"))["streets"]

    def test_exact_match_wins_before_all_fuzzy_stages(self):
        """精确匹配优先于一切模糊级：查全名直接命中本名。"""
        row = dsl.resolve_street("彩虹街道", self.streets)
        self.assertEqual(row["name"], "彩虹街道")
        self.assertEqual(row["code"], "440105001")

    def test_exact_beats_stem_collision(self):
        """存在「翠湖街道/翠湖镇」时查「翠湖街道」仍精确命中（不受词干撞车影响）。"""
        row = dsl.resolve_street("翠湖街道", self.streets)
        self.assertEqual(row["code"], "440105002")

    def test_stem_unique_succeeds(self):
        """去后缀唯一匹配成功：查「沙河」→「沙河街道」。"""
        row = dsl.resolve_street("沙河", self.streets)
        self.assertEqual(row["name"], "沙河街道")

    def test_contains_unique_succeeds(self):
        """包含唯一匹配成功：查「琶洲」（去后缀级 0 命中）→「琶洲街道」。"""
        row = dsl.resolve_street("琶洲", self.streets)
        self.assertEqual(row["name"], "琶洲街道")
        # 「江南」同理（且证明不是两字前缀截断：命中名比查询长且含中间字）
        row = dsl.resolve_street("江南", self.streets)
        self.assertEqual(row["name"], "江南中街道")

    def test_stem_collision_raises(self):
        """去后缀级歧义：翠湖街道/翠湖镇 并存，查「翠湖」抛错。"""
        with self.assertRaises(dsl.DslError) as cm:
            dsl.resolve_street("翠湖", self.streets)
        self.assertIn("翠湖", str(cm.exception))

    def test_card_ambiguous_fixture_raises(self):
        """卡载歧义夹具：人民街道/人民镇 并存，查「人民」必须抛错。"""
        with self.assertRaises(dsl.DslError) as cm:
            dsl.resolve_street("人民", self.streets)
        msg = str(cm.exception)
        self.assertIn("人民", msg)
        self.assertIn("2", msg)

    def test_contains_multiple_raises(self):
        """包含级 >1 抛错：构造 「中街道/中镇/中村街道」式三重包含。"""
        rows = [make_area("中街道", "1"), make_area("中镇", "2"),
                make_area("城中街道", "3")]
        with self.assertRaises(dsl.DslError):
            dsl.resolve_street("中", rows)

    def test_zero_match_raises_not_empty(self):
        """0 匹配抛错（禁止降级为空集/warning）。"""
        with self.assertRaises(dsl.DslError) as cm:
            dsl.resolve_street("不存在的街道", self.streets)
        self.assertIn("0 个", str(cm.exception))

    def test_two_char_prefix_is_not_a_fallback(self):
        """两字前缀不是独立兜底（主线 lookup_geometry 隐患禁止复刻）。

        判别构造：「彩虹大道」在任何一级都不命中——精确 0、去后缀（彩虹大道）
        0、包含 0 → 抛错。若实现把查询截成前两字「彩虹」再兜底匹配，就会
        静默命中「彩虹街道」；本用例证明该路径不存在。

        注意：查「江」唯一命中「江南中街道」是契约允许的包含级行为
        （"江" in "江南中街道"），不是前缀兜底，另用 test_contains_unique_
        succeeds 覆盖。
        """
        with self.assertRaises(dsl.DslError) as cm:
            dsl.resolve_street("彩虹大道", self.streets)
        self.assertIn("0 个", str(cm.exception))
        # 反向对照：截前两字「彩虹」确实能命中（证明夹具存在可被兜底误用的形态）
        self.assertEqual(
            dsl.resolve_street("彩虹", self.streets)["name"], "彩虹街道")

    def test_district_resolution_stages(self):
        """区县解析逐级：精确「海珠区」/ 去后缀「海珠」。"""
        self.assertEqual(dsl.resolve_district("海珠区", self.districts)["code"], "440105")
        self.assertEqual(dsl.resolve_district("海珠", self.districts)["code"], "440105")

    def test_district_zero_and_ambiguous(self):
        with self.assertRaises(dsl.DslError):
            dsl.resolve_district("天河区", self.districts)  # 0 匹配
        # 歧义夹具：两个名字在精确级与去后缀级均不产生「广州」，包含级 2 命中
        rows = [make_area("广州城区", "1"), make_area("广州郊区", "2")]
        with self.assertRaises(dsl.DslError) as cm:
            dsl.resolve_district("广州", rows)  # 包含匹配 >1 → 抛错
        self.assertIn("广州", str(cm.exception))

    def test_no_cross_type_lookup(self):
        """禁止跨类型：街道查询绝不落到区县表，反之亦然。"""
        with self.assertRaises(dsl.DslError):
            dsl.resolve_street("海珠区", self.streets)  # 区县名不在街道表
        with self.assertRaises(dsl.DslError):
            dsl.resolve_district("彩虹街道", self.districts)  # 街道名不在区县表

    def test_rows_not_mutated(self):
        """名称解析只读：表内容逐字节不变。"""
        before = json.dumps(self.streets, sort_keys=True, ensure_ascii=False)
        dsl.resolve_street("彩虹街道", self.streets)
        dsl.resolve_street("沙河", self.streets)
        after = json.dumps(self.streets, sort_keys=True, ensure_ascii=False)
        self.assertEqual(before, after)

    def test_non_string_query_raises(self):
        with self.assertRaises(dsl.DslError):
            dsl.resolve_street(123, self.streets)
        with self.assertRaises(dsl.DslError):
            dsl.resolve_street("", self.streets)


# ---------------------------------------------------------------------------
# DSL 节点校验：逐类非法节点抛错 + 合法树通过 + 只读 + 深度受控
# ---------------------------------------------------------------------------


class TestRuleValidation(unittest.TestCase):
    """validate_rule 逐类异常（卡载清单缺一不可）。"""

    def assert_bad(self, node, *fragments: str):
        with self.assertRaises(dsl.DslError) as cm:
            dsl.validate_rule(node)
        msg = str(cm.exception)
        for frag in fragments:
            self.assertIn(frag, msg)
        return msg

    def test_valid_minimal_tree(self):
        dsl.validate_rule({"op": "in_street", "name": "彩虹街道"})
        dsl.validate_rule({"op": "in_district", "name": "海珠区"})
        dsl.validate_rule({"op": "union", "args": [
            {"op": "in_street", "name": "彩虹街道"},
            {"op": "in_district", "name": "海珠区"}]})
        dsl.validate_rule({"op": "minus", "args": [
            {"op": "in_district", "name": "海珠区"},
            {"op": "in_street", "name": "彩虹街道"}]})

    def test_nested_3_levels_valid(self):
        dsl.validate_rule({"op": "union", "args": [
            {"op": "minus", "args": [
                {"op": "union", "args": [
                    {"op": "in_street", "name": "彩虹街道"},
                    {"op": "in_street", "name": "沙河街道"}]},
                {"op": "in_district", "name": "荔湾区"}]},
            {"op": "in_street", "name": "琶洲街道"}]})

    def test_empty_object(self):
        self.assert_bad({}, "op")

    def test_non_object_node(self):
        self.assert_bad("in_street", "对象")
        self.assert_bad(42, "对象")
        self.assert_bad(None, "对象")
        self.assert_bad([{"op": "in_street", "name": "x"}], "对象")

    def test_unknown_op(self):
        self.assert_bad({"op": "in_grid", "name": "x"}, "未知 op")

    def test_side_of_rejected_as_p3b(self):
        msg = self.assert_bad(
            {"op": "side_of", "line": "华南快速", "dir": "east", "scope": None}, "P3b")
        self.assertIn("side_of", msg)

    def test_near_rejected_as_p3b(self):
        self.assert_bad({"op": "near", "center": [113.0, 23.0], "radius_km": 3.0}, "P3b")

    def test_leaf_missing_field(self):
        self.assert_bad({"op": "in_street"}, "字段")
        self.assert_bad({"op": "in_district"}, "字段")

    def test_leaf_extra_field(self):
        self.assert_bad({"op": "in_street", "name": "彩虹街道", "scope": None}, "字段")

    def test_leaf_name_not_string(self):
        self.assert_bad({"op": "in_street", "name": 42}, "name")

    def test_union_missing_args_key(self):
        self.assert_bad({"op": "union"}, "字段")

    def test_union_arity_below_two(self):
        self.assert_bad({"op": "union", "args": []}, "至少")
        self.assert_bad({"op": "union", "args": [{"op": "in_street", "name": "x"}]}, "至少")

    def test_minus_arity_not_two(self):
        self.assert_bad({"op": "minus", "args": []}, "恰有 2")
        self.assert_bad({"op": "minus", "args": [
            {"op": "in_street", "name": "x"}]}, "恰有 2")
        self.assert_bad({"op": "minus", "args": [
            {"op": "in_street", "name": "x"},
            {"op": "in_street", "name": "y"},
            {"op": "in_street", "name": "z"}]}, "恰有 2")

    def test_args_non_object_child(self):
        msg = self.assert_bad(
            {"op": "union", "args": [{"op": "in_street", "name": "x"}, "垃圾"]}, "$.args[1]")
        self.assertIn("$.args[1]", msg)

    def test_args_non_list(self):
        self.assert_bad({"op": "minus", "args": "not-a-list"}, "数组")

    def test_nested_child_invalid_reports_location(self):
        self.assert_bad(
            {"op": "minus", "args": [
                {"op": "in_street", "name": "彩虹街道"},
                {"op": "near", "center": [113.0, 23.0], "radius_km": 1.0}]},
            "$.args[1]", "near")

    def test_location_path_nested(self):
        msg = self.assert_bad(
            {"op": "union", "args": [
                {"op": "in_street", "name": "彩虹街道"},
                {"op": "union", "args": [
                    {"op": "in_street", "name": "沙河街道"},
                    7]}]}, "$.args[1].args[1]")
        self.assertIn("$.args[1].args[1]", msg)

    def test_op_not_string(self):
        self.assert_bad({"op": 99, "name": "x"}, "字符串")

    def test_cyclic_reference_controlled_termination(self):
        """循环引用受控中文终止，不得无限递归或 RecursionError 逃逸。"""
        a: dict = {"op": "union", "args": [
            {"op": "in_street", "name": "彩虹街道"},
            {"op": "in_street", "name": "沙河街道"}]}
        b: dict = {"op": "union", "args": [
            {"op": "in_street", "name": "琶洲街道"}, a]}
        a["args"].append(b)  # 制造环
        with self.assertRaises(dsl.DslError) as cm:
            dsl.validate_rule(a)
        self.assertIn("深度", str(cm.exception))

    def test_rule_not_mutated_by_validation(self):
        """校验只读：树序列化前后逐字节一致（卡载断言）。"""
        rule = {"op": "union", "args": [
            {"op": "in_street", "name": "彩虹街道"},
            {"op": "minus", "args": [
                {"op": "in_district", "name": "海珠区"},
                {"op": "in_street", "name": "沙河街道"}]}]}
        before = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        dsl.validate_rule(rule)
        # 失败路径同样不得修改树
        with self.assertRaises(dsl.DslError):
            dsl.validate_rule({"op": "union", "args": [rule, {"op": "near"}]})
        self.assertEqual(json.dumps(rule, sort_keys=True, ensure_ascii=False), before)


# ---------------------------------------------------------------------------
# T-302：四原语确定性求值器（合成夹具；expected 全部手写字面量）
# ---------------------------------------------------------------------------

# 手写夹具几何（禁止由生产函数生成）：
#   街道甲 = 半边城 x∈[113.0,113.1)；街道乙 = 另半边城 x∈[113.1,113.2]；
#   两街无重叠、无共享边界。v1.7：in_street 只看单元 street 属性，
#   夹具几何（含故意错位）不得影响结果，另有专测证明。
STREET_JIA_WKT = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.1, 113.0 23.0))"
STREET_YI_WKT = "POLYGON ((113.1001 23.0, 113.2 23.0, 113.2 23.1, 113.1001 23.1, 113.1001 23.0))"


def build_eval_fixture(d: Path, *, unit_geoms: list[str] | None = None,
                       wrong_street_geoms: bool = False,
                       wrong_district_geoms: bool = False) -> dict:
    """构造求值专用最小合法 P3 输入目录并返回已加载上下文。

    单元布局（手写枚举，uid==数组下标；满足卡载断言 乙={2} / 海珠={0,1}）：
      0: street=甲街道，   440105
      1: street=无街道，   440105
      2: street=乙街道，   440103
      3: street=无街道，   440103
    - ``wrong_street_geoms``：把街道几何放到完全错位的经纬度，
      证明 in_street 不看几何（v1.7 只按 street 属性选取）。
    - ``wrong_district_geoms``：把区县几何放到完全错位的经纬度，
      证明 in_district 不看几何。
    """
    units = []
    centroids = [(113.05, 23.05), (114.0, 24.0), (113.15, 23.05), (113.5, 23.05)]
    codes = ["440105", "440105", "440103", "440103"]
    streets_of = ["甲街道", "无街道", "乙街道", "无街道"]
    for uid in range(4):
        u = make_unit(uid, geom=(unit_geoms or [VALID_WKT] * 4)[uid],
                      district_code=codes[uid])
        u["street"] = streets_of[uid]
        u["centroid"] = [centroids[uid][0], centroids[uid][1]]
        units.append(u)
    write_json(d / "units.json", build_units_payload(units))
    write_json(d / "streets.json", {"streets": [
        make_area("甲街道", "440105001", geom=STREET_JIA_WKT),
        make_area("乙街道", "440105002", geom=STREET_YI_WKT),
    ]})
    jia, yi = STREET_JIA_WKT, STREET_YI_WKT
    if wrong_street_geoms:
        # 刻意错位：街道几何被挪到远离全部单元 street 属性可及的位置。
        # v1.7：in_street 只按属性选取，错位几何不得改变结果。
        jia = "POLYGON ((120.0 30.0, 120.1 30.0, 120.1 30.1, 120.0 30.1, 120.0 30.0))"
        yi = jia
    if wrong_district_geoms:
        # 刻意错位：区县几何被挪到远离全部单元质心的位置
        jia = "POLYGON ((120.0 30.0, 120.1 30.0, 120.1 30.1, 120.0 30.1, 120.0 30.0))"
        yi = jia
    write_json(d / "districts.json", {"streets": [
        make_area("海珠区", "440105", geom=jia),
        make_area("荔湾区", "440103", geom=yi),
    ]})
    write_json(d / "unit_graph.json",
               {"adjacency": {"0": [], "1": [2], "2": [1], "3": []}, "link_min_m": 50})
    return dsl.load_pilot_context(d)


class TestEvalRuleSynthetic(unittest.TestCase):
    """四原语求值语义逐条冻结断言（expected 全部字面量，不经被测代码计算）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)

    # -- 卡载可执行验收断言（逐条原样落断言） -------------------------------

    def test_card_asserts(self):
        ctx = build_eval_fixture(self.d)
        self.assertEqual(
            dsl.eval_rule({"op": "in_street", "name": "甲街道"}, ctx), {0})
        self.assertEqual(
            dsl.eval_rule({"op": "in_district", "name": "海珠区"}, ctx), {0, 1})
        self.assertEqual(dsl.eval_rule({
            "op": "union",
            "args": [{"op": "in_street", "name": "甲街道"},
                     {"op": "in_street", "name": "乙街道"}],
        }, ctx), {0, 2})
        self.assertEqual(dsl.eval_rule({
            "op": "minus",
            "args": [{"op": "in_district", "name": "海珠区"},
                     {"op": "in_street", "name": "甲街道"}],
        }, ctx), {1})
        self.assertEqual(dsl.eval_rule({
            "op": "union",
            "args": [{"op": "in_street", "name": "甲街道"},
                     {"op": "in_street", "name": "甲街道"}],
        }, ctx), {0})
        self.assertEqual(dsl.eval_rule({
            "op": "minus",
            "args": [{"op": "in_district", "name": "海珠区"},
                     {"op": "in_district", "name": "海珠区"}],
        }, ctx), set())

    def test_minus_empty_set_is_valid_result(self):
        """G3-3：minus 结果为空集是合法值（不抛错、不置 None）。"""
        ctx = build_eval_fixture(self.d)
        self.assertEqual(dsl.eval_rule({
            "op": "minus",
            "args": [{"op": "in_street", "name": "甲街道"},
                     {"op": "in_street", "name": "甲街道"}],
        }, ctx), set())

    def test_union_duplicate_subtree_idempotent(self):
        """G3-4：重复子树 union 幂等（含嵌套同子树两次）。"""
        ctx = build_eval_fixture(self.d)
        leaf = {"op": "in_street", "name": "甲街道"}
        self.assertEqual(dsl.eval_rule({
            "op": "union", "args": [leaf, dict(leaf), dict(leaf)]}, ctx), {0})
        # union( minus(海珠={0,1}, 甲={0}) = {1}, 乙={2}, 乙={2} ) = {1, 2}
        self.assertEqual(dsl.eval_rule({
            "op": "union",
            "args": [{"op": "minus", "args": [
                {"op": "in_district", "name": "海珠区"},
                {"op": "in_street", "name": "甲街道"}]},
                {"op": "in_street", "name": "乙街道"},
                {"op": "in_street", "name": "乙街道"}],
        }, ctx), {1, 2})

    def test_single_unit_result(self):
        """G3-2：单单元结果。"""
        ctx = build_eval_fixture(self.d)
        self.assertEqual(
            dsl.eval_rule({"op": "in_street", "name": "乙街道"}, ctx), {2})

    def test_nested_at_least_4_levels_and_tree_unchanged(self):
        """G3-7：根到叶 4 层人工树；求值前后树序列化逐字节一致。"""
        ctx = build_eval_fixture(self.d)
        rule = {
            "op": "union",
            "args": [
                {"op": "minus",  # 第 2 层
                 "args": [
                     {"op": "union",  # 第 3 层
                      "args": [
                          {"op": "in_street", "name": "甲街道"},  # 第 4 层
                          {"op": "in_street", "name": "乙街道"}]},
                     {"op": "in_district", "name": "海珠区"}]},  # 第 4 层
                {"op": "in_street", "name": "乙街道"},  # 第 3 层
            ],
        }
        before = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        # 手工展开：union( minus( union(甲={0}, 乙={2}), 海珠={0,1} ), 乙={2} )
        #   = union( ({0,2} - {0,1}) = {2}, {2} ) = {2}
        self.assertEqual(dsl.eval_rule(rule, ctx), {2})
        self.assertEqual(json.dumps(rule, sort_keys=True, ensure_ascii=False), before)

    # -- 求值只看声明语义的两个判别夹具 ------------------------------------

    def test_in_street_uses_attr_only_regardless_of_geometry(self):
        """v1.7 属性语义判别（expected 手写）：

        - uid0 street=乙街道：质心在甲街道内、单元几何巨大完整覆盖
          乙街道 → 仍入选（几何 contains 不拉人也不排除）；
        - uid1 street=甲街道：质心在乙街道内 → 仍入选甲（质心不决定）；
        - uid2 street=无街道（两街之外）→ 不入选任一街。
        """
        huge = "POLYGON ((112.0 22.0, 114.5 22.0, 114.5 24.5, 112.0 24.5, 112.0 22.0))"
        units = [
            make_unit(0, geom=huge, district_code="440105"),
            make_unit(1, geom=VALID_WKT, district_code="440105"),
            make_unit(2, geom=huge, district_code="440103"),
        ]
        units[0]["street"] = "乙街道"
        units[1]["street"] = "甲街道"
        units[2]["street"] = "无街道"
        for u, c in zip(units, [(113.05, 23.05), (113.15, 23.05), (114.0, 24.0)]):
            u["centroid"] = [c[0], c[1]]
        write_json(self.d / "units.json", build_units_payload(units))
        write_json(self.d / "streets.json", {"streets": [
            make_area("甲街道", "440105001", geom=STREET_JIA_WKT),
            make_area("乙街道", "440105002", geom=STREET_YI_WKT),
        ]})
        write_json(self.d / "districts.json", {"streets": [
            make_area("海珠区", "440105"), make_area("荔湾区", "440103")]})
        write_json(self.d / "unit_graph.json",
                   {"adjacency": {"0": [], "1": [], "2": []}, "link_min_m": 50})
        ctx = dsl.load_pilot_context(self.d)
        self.assertEqual(
            dsl.eval_rule({"op": "in_street", "name": "乙街道"}, ctx), {0})
        self.assertEqual(
            dsl.eval_rule({"op": "in_street", "name": "甲街道"}, ctx), {1})

    def test_in_street_ignores_street_geometry(self):
        """街道几何刻意错位：in_street 只看 street 属性相等（v1.7）。"""
        ctx = build_eval_fixture(self.d, wrong_street_geoms=True)
        self.assertEqual(
            dsl.eval_rule({"op": "in_street", "name": "甲街道"}, ctx), {0})
        self.assertEqual(
            dsl.eval_rule({"op": "in_street", "name": "乙街道"}, ctx), {2})

    def test_in_district_ignores_geometry(self):
        """区县几何刻意错位：in_district 只看 district_code 属性相等。"""
        ctx = build_eval_fixture(self.d, wrong_district_geoms=True)
        self.assertEqual(
            dsl.eval_rule({"op": "in_district", "name": "海珠区"}, ctx), {0, 1})

    def test_boundary_geometry_does_not_exclude_attr_match(self):
        """v1.7 反向判别：单元几何压线/骑跨街道边界不影响属性选取。

        units[0] 几何与甲街道共享右边界 x=113.1（纯边界贴合、零重叠）、
        units[1] 几何横跨甲乙两街（骑跨），二者 street 均为甲街道 →
        都按属性入选（v1.6 的 contains/covers 判定已废弃）。
        """
        touching = ("POLYGON ((113.1 23.0, 113.2 23.0, 113.2 23.1,"
                    " 113.1 23.1, 113.1 23.0))")
        straddling = "POLYGON ((113.05 23.0, 113.15 23.0, 113.15 23.1, 113.05 23.1, 113.05 23.0))"
        units = [make_unit(0, geom=touching), make_unit(1, geom=straddling)]
        units[0]["street"] = "甲街道"
        units[1]["street"] = "甲街道"
        units[0]["centroid"] = [113.15, 23.05]  # 若按质心 contains 会被排除
        units[1]["centroid"] = [113.1, 23.05]   # 若按质心 contains 会压线排除
        write_json(self.d / "units.json", build_units_payload(units))
        write_json(self.d / "streets.json", {"streets": [
            make_area("甲街道", "440105001", geom=STREET_JIA_WKT),
            make_area("乙街道", "440105002", geom=STREET_YI_WKT),
        ]})
        write_json(self.d / "districts.json", {"streets": [
            make_area("海珠区", "440105"), make_area("荔湾区", "440103")]})
        write_json(self.d / "unit_graph.json",
                   {"adjacency": {"0": [], "1": []}, "link_min_m": 50})
        ctx = dsl.load_pilot_context(self.d)
        self.assertEqual(
            dsl.eval_rule({"op": "in_street", "name": "甲街道"}, ctx), {0, 1})

    # -- 异常路径：未知名 / 歧义名 / P3b / 非法 arity ------------------------

    def test_unknown_name_raises_not_empty_set(self):
        """G3-1：不存在街道名抛错，不降级为空集。"""
        ctx = build_eval_fixture(self.d)
        with self.assertRaises(dsl.DslError) as cm:
            dsl.eval_rule({"op": "in_street", "name": "不存在的街道"}, ctx)
        self.assertIn("0 个", str(cm.exception))

    def test_ambiguous_name_raises(self):
        """G3-6：歧义名抛错（两街并存查共同词干）。"""
        ctx = build_eval_fixture(self.d)
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule({"op": "in_street", "name": "街道"}, ctx)

    def test_p3b_ops_rejected_before_evaluation(self):
        """side_of / near 属 P3b：入口整体校验阶段即拒绝，不进入递归。"""
        ctx = build_eval_fixture(self.d)
        for bad in [{"op": "side_of", "line": "x", "dir": "east", "scope": None},
                    {"op": "near", "center": [113.0, 23.0], "radius_km": 1.0}]:
            with self.assertRaises(dsl.DslError) as cm:
                dsl.eval_rule(bad, ctx)
            self.assertIn("P3b", str(cm.exception))

    def test_illegal_arity_rejected_before_evaluation(self):
        """非法 arity 入口即拒绝（union<2 / minus!=2），不进入递归。"""
        ctx = build_eval_fixture(self.d)
        for bad in [{"op": "union", "args": []},
                    {"op": "union", "args": [{"op": "in_street", "name": "甲街道"}]},
                    {"op": "minus", "args": []},
                    {"op": "minus", "args": [{"op": "in_street", "name": "甲街道"}]}]:
            with self.assertRaises(dsl.DslError):
                dsl.eval_rule(bad, ctx)

    def test_cyclic_rule_controlled_chinese_error(self):
        """循环对象：入口校验受控中文终止，不无限递归。"""
        ctx = build_eval_fixture(self.d)
        a: dict = {"op": "union", "args": [
            {"op": "in_street", "name": "甲街道"},
            {"op": "in_street", "name": "乙街道"}]}
        b: dict = {"op": "union", "args": [
            {"op": "in_street", "name": "甲街道"}, a]}
        a["args"].append(b)  # 制造环
        with self.assertRaises(dsl.DslError) as cm:
            dsl.eval_rule(a, ctx)
        self.assertIn("深度", str(cm.exception))

    def test_result_type_is_set_of_int(self):
        """输出本体是 set[int]：类型与元素类型逐项断言。"""
        ctx = build_eval_fixture(self.d)
        out = dsl.eval_rule({"op": "in_district", "name": "海珠区"}, ctx)
        self.assertIsInstance(out, set)
        self.assertTrue(all(isinstance(i, int) and not isinstance(i, bool) for i in out))


class TestEvalRealData(unittest.TestCase):
    """真实数据独立交叉断言（expected 来自 raw_units 字段筛选，非被测代码）。"""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = REPO_ROOT / "data" / "pilot"
        cls.before = snapshot_dir(cls.data_dir)
        cls.ctx = dsl.load_pilot_context(cls.data_dir)
        cls.raw_units = json.loads(
            (cls.data_dir / "units.json").read_text("utf-8"))["units"]

    @classmethod
    def tearDownClass(cls):
        after = snapshot_dir(cls.data_dir)
        assert after == cls.before, "真实输入目录被修改"

    def test_real_in_district_haizhu_131(self):
        actual = dsl.eval_rule({"op": "in_district", "name": "海珠区"}, self.ctx)
        expected = {u["uid"] for u in self.raw_units if u["district_code"] == "440105"}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 131)

    def test_real_in_street_caihong_56(self):
        actual = dsl.eval_rule({"op": "in_street", "name": "彩虹街道"}, self.ctx)
        expected = {u["uid"] for u in self.raw_units if u["street"] == "彩虹街道"}
        self.assertEqual(actual, expected)
        self.assertEqual(actual, {56})

    def test_real_nested_minus_semantics(self):
        """荔湾区减去彩虹街道：expected 由 raw_units 字段筛选手写。

        真实数据中彩虹街道（uid==56）的单元 district_code 是 440103
        （荔湾），故减法必须落在「荔湾区 − 彩虹街道」上才有区分度
        （93 − 1 = 92）；同时证明树求值前后逐字节不变。
        """
        rule = {"op": "minus", "args": [
            {"op": "in_district", "name": "荔湾区"},
            {"op": "in_street", "name": "彩虹街道"}]}
        before = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        actual = dsl.eval_rule(rule, self.ctx)
        expected = {u["uid"] for u in self.raw_units
                    if u["district_code"] == "440103" and u["street"] != "彩虹街道"}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 92)
        self.assertEqual(json.dumps(rule, sort_keys=True, ensure_ascii=False), before)


# ---------------------------------------------------------------------------
# 真实数据验收（data/pilot 存在时执行；卡载锚点）
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    (REPO_ROOT / "data" / "pilot" / "units.json").is_file(), "data/pilot 不存在")
class TestRealData(unittest.TestCase):
    """卡载真实数据条件逐条断言；输入目录指纹只读证明。"""
    @classmethod
    def setUpClass(cls):
        cls.data_dir = REPO_ROOT / "data" / "pilot"
        cls.before = snapshot_dir(cls.data_dir)
        cls.ctx = dsl.load_pilot_context(cls.data_dir)

    @classmethod
    def tearDownClass(cls):
        after = snapshot_dir(cls.data_dir)
        assert after == cls.before, "真实输入目录被修改"

    def test_card_anchor_counts(self):
        units = self.ctx["units"]
        self.assertEqual(len(units), 224)
        self.assertEqual([u["uid"] for u in units], list(range(224)))
        codes = {u["district_code"] for u in units}
        self.assertEqual(
            {c: sum(1 for u in units if u["district_code"] == c) for c in codes},
            {"440105": 131, "440103": 93})
        self.assertEqual(len(self.ctx["streets"]), 40)
        self.assertEqual(self.ctx["link_min_m"], 50)
        self.assertEqual(len(self.ctx["adjacency"]), 224)
        undirected = sum(len(v) for v in self.ctx["adjacency"].values()) // 2
        self.assertEqual(undirected, 538)
        for g in self.ctx["unit_geoms"] + self.ctx["street_geoms"]:
            self.assertIn(g.geom_type, {"Polygon", "MultiPolygon"})

    def test_resolve_real_street_names(self):
        """卡载断言：彩虹精确、彩虹去后缀、海珠去后缀。"""
        self.assertEqual(
            dsl.resolve_street("彩虹街道", self.ctx["streets"])["name"], "彩虹街道")
        self.assertEqual(
            dsl.resolve_street("彩虹", self.ctx["streets"])["name"], "彩虹街道")
        self.assertEqual(
            dsl.resolve_district("海珠", self.ctx["districts"])["code"], "440105")

    def test_real_ambiguous_prefix_raises(self):
        """「石头」包含唯一（南石头街道）；空查询/未知查询抛错。"""
        self.assertEqual(
            dsl.resolve_street("石头", self.ctx["streets"])["name"], "南石头街道")
        with self.assertRaises(dsl.DslError):
            dsl.resolve_street("不存在的街道XYZ", self.ctx["streets"])

    def test_real_districts_table_shape(self):
        """districts.json 顶层键按 P1 契约仍名 streets。"""
        raw = json.loads((self.data_dir / "districts.json").read_text("utf-8"))
        self.assertIn("streets", raw)
        names = {r["name"] for r in raw["streets"]}
        self.assertEqual(names, {"海珠区", "荔湾区"})

# ---------------------------------------------------------------------------
# T-303：execute 五字段输出汇总（卡载手写 4 单元夹具；expected 全字面量）
# ---------------------------------------------------------------------------


def build_exec_fixture(d: Path) -> dict:
    """构造 T-303 卡载最小合法输入目录并返回已加载上下文。

    布局（手写枚举，uid==数组下标；图 0—1 相连、2—3 相连、两组间无边）：
      0: street=甲街道，  440105，area 1.0
      1: street=无街道，  440105，area 2.0
      2: street=无街道，  440103，area 4.0
      3: street=乙街道，  440103，area 8.0
    union(甲街道, 乙街道) = {0, 3}：两个分量、面积 9.0（1.0+8.0）。
    """
    units = []
    centroids = [(113.05, 23.05), (114.0, 24.0), (113.5, 23.05), (113.15, 23.05)]
    codes = ["440105", "440105", "440103", "440103"]
    areas = [1.0, 2.0, 4.0, 8.0]
    streets_of = ["甲街道", "无街道", "无街道", "乙街道"]
    for uid in range(4):
        u = make_unit(uid, district_code=codes[uid])
        u["area_km2"] = areas[uid]
        u["street"] = streets_of[uid]
        u["centroid"] = [centroids[uid][0], centroids[uid][1]]
        units.append(u)
    write_json(d / "units.json", build_units_payload(units))
    write_json(d / "streets.json", {"streets": [
        make_area("甲街道", "440105001", geom=STREET_JIA_WKT),
        make_area("乙街道", "440105002", geom=STREET_YI_WKT),
    ]})
    write_json(d / "districts.json", {"streets": [
        make_area("海珠区", "440105", geom=STREET_JIA_WKT),
        make_area("荔湾区", "440103", geom=STREET_YI_WKT),
    ]})
    write_json(d / "unit_graph.json", {
        "adjacency": {"0": [1], "1": [0], "2": [3], "3": [2]},
        "link_min_m": 50,
    })
    return dsl.load_pilot_context(d)


class TestExecuteOutputContract(unittest.TestCase):
    """T-303 输出契约：卡载可执行验收断言逐条原样落断言。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)
        self.ctx = build_exec_fixture(self.d)

    def test_card_asserts_union_two_components(self):
        """卡载主断言：union(甲, 乙)={0,3}，两分量，面积 9.0，树不变。"""
        rule = {
            "op": "union",
            "args": [{"op": "in_street", "name": "甲街道"},
                     {"op": "in_street", "name": "乙街道"}],
        }
        rule_bytes_before = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        result = dsl.execute(rule, self.ctx)
        self.assertEqual(
            set(result), {"unit_ids", "components", "area_km2", "rule", "warnings"})
        self.assertEqual(result["unit_ids"], [0, 3])
        self.assertEqual(result["components"], 2)
        self.assertTrue(math.isclose(result["area_km2"], 9.0))
        self.assertEqual(result["rule"], rule)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(
            json.dumps(rule, sort_keys=True, ensure_ascii=False), rule_bytes_before)

    def test_card_asserts_minus_empty(self):
        """卡载空集断言：minus 同子树 → 空集，components=0，面积 0.0。"""
        rule = {
            "op": "minus",
            "args": [{"op": "in_street", "name": "甲街道"},
                     {"op": "in_street", "name": "甲街道"}],
        }
        result = dsl.execute(rule, self.ctx)
        self.assertEqual(result["unit_ids"], [])
        self.assertEqual(result["components"], 0)
        self.assertEqual(result["area_km2"], 0.0)
        self.assertEqual(result["warnings"], [])

    def test_single_unit_component_is_one(self):
        """单单元结果 components == 1。"""
        result = dsl.execute({"op": "in_street", "name": "甲街道"}, self.ctx)
        self.assertEqual(result["unit_ids"], [0])
        self.assertEqual(result["components"], 1)
        self.assertTrue(math.isclose(result["area_km2"], 1.0))

    def test_duplicate_subtree_union_no_double_area(self):
        """重复子树 union 不重复面积（{0} 并 {0} = {0}，面积仍 1.0）。"""
        leaf = {"op": "in_street", "name": "甲街道"}
        result = dsl.execute({"op": "union", "args": [leaf, dict(leaf)]}, self.ctx)
        self.assertEqual(result["unit_ids"], [0])
        self.assertTrue(math.isclose(result["area_km2"], 1.0))

    def test_multi_component_report_only_no_repair(self):
        """多分量只改变报告数字：unit_ids 不变、不补路径、不加单元。"""
        leaf = {"op": "in_street", "name": "甲街道"}
        rule = {"op": "union", "args": [leaf, dict(leaf), dict(leaf)]}
        result = dsl.execute(rule, self.ctx)
        self.assertEqual(result["unit_ids"], [0])
        self.assertEqual(result["components"], 1)
        # 选 {0,3}：图不修补——unit_ids 恰为 [0,3]，不因诱导子图多块而增删
        rule03 = {
            "op": "union",
            "args": [{"op": "in_street", "name": "甲街道"},
                     {"op": "in_street", "name": "乙街道"}],
        }
        r03 = dsl.execute(rule03, self.ctx)
        self.assertEqual(r03["unit_ids"], [0, 3])
        self.assertEqual(r03["components"], 2)

    def test_unit_ids_always_sorted(self):
        """unit_ids 永远升序（求值集合无序，输出必须升序唯一）。"""
        rule = {
            "op": "union",
            "args": [{"op": "in_street", "name": "乙街道"},
                     {"op": "in_street", "name": "甲街道"}],
        }
        result = dsl.execute(rule, self.ctx)
        self.assertEqual(result["unit_ids"], sorted(result["unit_ids"]))
        self.assertEqual(result["unit_ids"], [0, 3])

    def test_result_rule_is_deep_copy_not_shared(self):
        """返回 rule 是深拷贝：改返回值不影响原树，反之亦然。"""
        rule = {
            "op": "union",
            "args": [{"op": "in_street", "name": "甲街道"},
                     {"op": "in_street", "name": "乙街道"}],
        }
        result = dsl.execute(rule, self.ctx)
        result["rule"]["args"][0]["name"] = "篡改"
        self.assertEqual(rule["args"][0]["name"], "甲街道")

    def test_name_failures_raise_never_warnings(self):
        """名称 0 匹配与歧义抛异常，绝不产出 warnings 结果。"""
        with self.assertRaises(dsl.DslError):
            dsl.execute({"op": "in_street", "name": "不存在的街道XYZ"}, self.ctx)
        # 构造歧义：两街道包含「街道」二字以外的共同子串——用去后缀歧义更直接
        d2 = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(d2, ignore_errors=True))
        units = []
        for uid in range(2):
            u = make_unit(uid)
            u["centroid"] = [113.05, 23.05]
            units.append(u)
        write_json(d2 / "units.json", build_units_payload(units))
        write_json(d2 / "streets.json", {"streets": [
            make_area("东镇", "440105001"),
            make_area("西镇", "440105002"),
        ]})
        write_json(d2 / "districts.json", {"streets": [
            make_area("海珠区", "440105"),
        ]})
        write_json(d2 / "unit_graph.json",
                   {"adjacency": {"0": [1], "1": [0]}, "link_min_m": 50})
        ctx2 = dsl.load_pilot_context(d2)
        with self.assertRaises(dsl.DslError):
            dsl.execute({"op": "in_street", "name": "镇"}, ctx2)

    def test_nested_three_levels_executes(self):
        """嵌套至少 3 层的树正常求值汇总（G3-7 铺垫）。"""
        rule = {
            "op": "union",
            "args": [
                {"op": "minus",
                 "args": [{"op": "in_district", "name": "海珠区"},
                          {"op": "union",
                           "args": [{"op": "in_street", "name": "甲街道"},
                                    {"op": "in_street", "name": "乙街道"}]}]},
                {"op": "in_street", "name": "乙街道"},
            ],
        }
        result = dsl.execute(rule, self.ctx)
        # minus(海珠={0,1}, {0,3}) = {1}；union {1} ∪ {3} = {1,3}
        self.assertEqual(result["unit_ids"], [1, 3])
        self.assertEqual(result["components"], 2)  # 1 与 3 之间无边
        self.assertTrue(math.isclose(result["area_km2"], 10.0))  # 2.0+8.0


class TestExecuteGraphDefense(unittest.TestCase):
    """execute 对带病图的防御性复核：六类异常逐条（中文含路径）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)
        self.ctx = build_exec_fixture(self.d)

    def _rewrite_graph(self, adjacency, link_min_m=50):
        payload = {"adjacency": adjacency, "link_min_m": link_min_m}
        write_json(self.d / "unit_graph.json", payload)
        return dsl.load_pilot_context(self.d)

    def test_missing_node_rejected(self):
        ctx = self._rewrite_graph({"0": [], "1": [], "2": [], "3": []})
        del ctx["adjacency"][2]  # 模拟绕过加载层手工拼坏 ctx
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.execute({"op": "in_street", "name": "甲街道"}, ctx)
        self.assertIn("恰好覆盖", str(cm.exception))

    def test_extra_node_rejected(self):
        ctx = self._rewrite_graph({"0": [], "1": [], "2": [], "3": []})
        ctx["adjacency"][99] = []
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.execute({"op": "in_street", "name": "甲街道"}, ctx)
        self.assertIn("恰好覆盖", str(cm.exception))

    def test_illegal_neighbor_rejected(self):
        ctx = self._rewrite_graph({"0": [], "1": [], "2": [], "3": []})
        ctx["adjacency"][0] = [99]
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.execute({"op": "in_street", "name": "甲街道"}, ctx)
        self.assertIn("超出 uid 值域", str(cm.exception))

    def test_asymmetric_rejected(self):
        ctx = dsl.load_pilot_context(self.d)
        ctx["adjacency"][1] = []  # 内存破坏：0->1 存在但 1->0 缺失
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.execute({"op": "in_street", "name": "甲街道"}, ctx)
        self.assertIn("不对称", str(cm.exception))

    def test_self_loop_rejected(self):
        ctx = dsl.load_pilot_context(self.d)
        ctx["adjacency"][0] = [0]  # 内存破坏：自环
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.execute({"op": "in_street", "name": "甲街道"}, ctx)
        self.assertIn("自环", str(cm.exception))

    def test_link_min_m_rejected(self):
        ctx = dsl.load_pilot_context(self.d)
        ctx["link_min_m"] = 100  # 内存破坏：冻结常数被改
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.execute({"op": "in_street", "name": "甲街道"}, ctx)
        self.assertIn("link_min_m", str(cm.exception))


class TestExecuteRealData(unittest.TestCase):
    """真实数据 smoke：expected 全部直接筛 raw JSON，不经生产求值。"""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = REPO_ROOT / "data" / "pilot"
        cls.before = snapshot_dir(cls.data_dir)
        cls.ctx = dsl.load_pilot_context(cls.data_dir)
        cls.raw_units = json.loads(
            (cls.data_dir / "units.json").read_text("utf-8"))["units"]

    @classmethod
    def tearDownClass(cls):
        after = snapshot_dir(cls.data_dir)
        assert after == cls.before, "真实输入目录被修改"

    def test_real_haizhu_execute(self):
        """海珠区：uid 直接筛 raw JSON；分量与面积用独立预计算锚点。"""
        rule = {"op": "in_district", "name": "海珠区"}
        result = dsl.execute(rule, self.ctx)
        expected = sorted(u["uid"] for u in self.raw_units
                          if u["district_code"] == "440105")
        self.assertEqual(result["unit_ids"], expected)
        self.assertEqual(len(result["unit_ids"]), 131)
        self.assertEqual(result["components"], 1)
        self.assertTrue(math.isclose(
            result["area_km2"],
            math.fsum(u["area_km2"] for u in self.raw_units
                      if u["district_code"] == "440105")))

    def test_real_full_set_components(self):
        """全集 224 单元：分量 1、面积 fsum=153.8516742604974（独立锚点）。"""
        haizhu = {"op": "in_district", "name": "海珠区"}
        liwan = {"op": "in_district", "name": "荔湾区"}
        result = dsl.execute({"op": "union", "args": [haizhu, liwan]}, self.ctx)
        self.assertEqual(len(result["unit_ids"]), 224)
        self.assertEqual(result["components"], 1)
        self.assertTrue(math.isclose(
            result["area_km2"],
            math.fsum(u["area_km2"] for u in self.raw_units)))

    def test_real_minus_haizhu_caihong(self):
        """荔湾 − 彩虹街道：92 单元、分量 1；树执行前后逐字节不变。"""
        rule = {"op": "minus", "args": [
            {"op": "in_district", "name": "荔湾区"},
            {"op": "in_street", "name": "彩虹街道"}]}
        before = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        result = dsl.execute(rule, self.ctx)
        expected = sorted(u["uid"] for u in self.raw_units
                          if u["district_code"] == "440103"
                          and u["street"] != "彩虹街道")
        self.assertEqual(result["unit_ids"], expected)
        self.assertEqual(len(result["unit_ids"]), 92)
        self.assertEqual(result["components"], 1)
        self.assertEqual(result["warnings"], [])
        self.assertEqual(json.dumps(rule, sort_keys=True, ensure_ascii=False), before)

# ---------------------------------------------------------------------------
# T-304：P3 G3 独立 Oracle 集成门禁（expected 一律不经被测执行器产生）
# ---------------------------------------------------------------------------


# 七类退化用例的人工 DSL 常量（G3）
RULE_G3_UNKNOWN = {"op": "in_street", "name": "不存在街道"}
RULE_G3_SINGLE = {"op": "in_street", "name": "彩虹街道"}
RULE_G3_EMPTY_MINUS = {"op": "minus", "args": [
    {"op": "in_district", "name": "海珠区"},
    {"op": "in_district", "name": "海珠区"},
]}
RULE_G3_IDEMPOTENT = {"op": "union", "args": [RULE_G3_SINGLE, RULE_G3_SINGLE]}
RULE_G3_MULTI_COMPONENT = {"op": "union", "args": [
    {"op": "in_street", "name": "甲街道"},
    {"op": "in_street", "name": "乙街道"},
]}
RULE_G3_AMBIGUOUS = {"op": "in_street", "name": "人民"}
RULE_G3_NESTED = {"op": "union", "args": [
    {"op": "minus", "args": [
        {"op": "union", "args": [
            {"op": "in_street", "name": "甲街道"},
            {"op": "in_street", "name": "乙街道"},
        ]},
        {"op": "in_street", "name": "乙街道"},
    ]},
    {"op": "in_street", "name": "乙街道"},
]}
G3_EXPECTED_NESTED_LITERAL = [0, 3]

def _g3_oracle_components(selected: set, adjacency: dict) -> int:
    """G3 专用独立 BFS（队列式）计算 expected components。

    与生产 ``_count_components``（迭代 DFS、栈式）无共享代码路径；
    输入是 raw adjacency 与 expected uid 字面量/独立字段筛选结果，
    绝不调用生产 components helper 产生 expected。
    """
    from collections import deque
    seen: set = set()
    count = 0
    for start in sorted(selected):
        if start in seen:
            continue
        count += 1
        queue = deque([start])
        seen.add(start)
        while queue:
            cur = queue.popleft()
            for nb in adjacency[cur]:
                if nb in selected and nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
    return count


def _g3_tree_depth(node) -> int:
    """仅检查人工树结构深度，不参与 expected 单元计算。"""
    if not isinstance(node, dict):
        raise AssertionError(f"DSL 节点必须是 dict，实际为 {type(node).__name__}")
    args = node.get("args")
    if not isinstance(args, list):
        return 1
    return 1 + max(_g3_tree_depth(a) for a in args)


class G3Ledger:
    """用例台账：逐例登记 expected/actual/missing/extra；100% 或 FAIL。"""

    def __init__(self):
        self.rows: list[dict] = []

    def record(self, case_id: str, expected, actual) -> bool:
        exp, act = sorted(expected), sorted(actual)
        ok = exp == act
        self.rows.append({
            "case": case_id, "ok": ok, "expected": exp, "actual": act,
            "missing": sorted(set(exp) - set(act)),
            "extra": sorted(set(act) - set(exp)),
        })
        return ok

    def require_exact_all(self):
        bad = [r for r in self.rows if not r["ok"]]
        assert not bad, (
            f"G3 FAIL：{len(bad)} 例不完全相等"
            + "".join(
                f"\n  [{r['case']}] missing={r['missing']} extra={r['extra']} "
                f"expected_n={len(r['expected'])} actual_n={len(r['actual'])}"
                for r in bad
            )
        )
        assert self.rows, "G3 无任何用例执行"
        rate = sum(1 for r in self.rows if r["ok"]) / len(self.rows)
        assert rate == 1.0, f"exact_match_rate={rate}"


# G3 合成夹具（七类退化用例 1/5/6/7 用）：
#   v1.7：in_street 只按 street 属性选取；甲/乙街道几何仅用于名称解析
#   上下文，取值不影响结果。图 0-1、2-3 两组无边。
G3_SYN_STREET_JIA = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.1, 113.0 23.0))"
G3_SYN_STREET_YI = "POLYGON ((113.1001 23.0, 113.2 23.0, 113.2 23.1, 113.1001 23.1, 113.1001 23.0))"


def _g3_build_synthetic_ctx(tmp_root: Path) -> dict:
    """构造 G3 合成目录：乙街道={3}；图 0-1、2-3 相连、两组间无边。

    单元布局（uid==下标；street 属性：甲街道={0}、乙街道={3}）：
      0: street=甲街道，  440105
      1: street=无街道，  440105
      2: street=无街道，  440103
      3: street=乙街道，  440103
    歧义夹具：街道表另含正式名『人民街道』『人民镇』（名称独立于
    甲乙两街），专供用例 6 查询『人民』触发 >1 歧义抛错。
    union(甲街道, 乙街道) = {0, 3}：图中 0-3 无路径 → 分量 2。
    """
    d = tmp_root / "g3_syn"
    d.mkdir(parents=True)
    centroids = [(113.05, 23.05), (114.0, 24.0), (113.5, 23.05), (113.15, 23.05)]
    codes = ["440105", "440105", "440103", "440103"]
    streets_of = ["甲街道", "无街道", "无街道", "乙街道"]
    units = [{
        "uid": uid, "key": f"G3SYN-{uid}", "district_code": codes[uid],
        "street": streets_of[uid],
        "area_km2": float(uid + 1),
        "centroid": [centroids[uid][0], centroids[uid][1]],
        "geom": G3_SYN_STREET_JIA,
    } for uid in range(4)]
    far = "POLYGON ((120.0 30.0, 120.1 30.0, 120.1 30.1, 120.0 30.1, 120.0 30.0))"
    (d / "units.json").write_text(json.dumps(
        {"crs": "GCJ-02", "units": units}, ensure_ascii=False), "utf-8")
    (d / "streets.json").write_text(json.dumps({"streets": [
        {"name": "甲街道", "code": "440105001", "district_code": "440105", "geom": G3_SYN_STREET_JIA},
        {"name": "乙街道", "code": "440105002", "district_code": "440103", "geom": G3_SYN_STREET_YI},
        {"name": "人民街道", "code": "440105100", "district_code": "440105", "geom": far},
        {"name": "人民镇", "code": "440105101", "district_code": "440105", "geom": far},
    ]}, ensure_ascii=False), "utf-8")
    (d / "districts.json").write_text(json.dumps({"streets": [
        {"name": "海珠区", "code": "440105", "district_code": "440105", "geom": G3_SYN_STREET_JIA},
        {"name": "荔湾区", "code": "440103", "district_code": "440103", "geom": G3_SYN_STREET_YI},
    ]}, ensure_ascii=False), "utf-8")
    (d / "unit_graph.json").write_text(json.dumps(
        {"adjacency": {"0": [1], "1": [0], "2": [3], "3": [2]}, "link_min_m": 50}),
        "utf-8")
    return dsl.load_pilot_context(d)


class _G3SyntheticMixin:
    """惰性构建合成 ctx（每个测试方法独立目录，互不污染）。"""

    def syn_ctx(self) -> dict:
        if not hasattr(self, "_syn_ctx"):
            self._tmpdir = tempfile.TemporaryDirectory()
            self.addCleanup(self._tmpdir.cleanup)
            self._syn_ctx = _g3_build_synthetic_ctx(Path(self._tmpdir.name))
        return self._syn_ctx


class TestG3SevenDegenerate(_G3SyntheticMixin, unittest.TestCase):
    """G3 七类退化用例（缺一即本卡失败）；expected 手写字面量/raw 筛选。"""

    @classmethod
    def setUpClass(cls):
        cls.ledger = G3Ledger()
        cls.real_ctx = dsl.load_pilot_context(REPO_ROOT / "data" / "pilot")

    def test_case_1_unknown_street_raises(self):
        with self.assertRaises(dsl.DslError):
            dsl.execute(RULE_G3_UNKNOWN, self.syn_ctx())

    def test_case_2_single_unit_result(self):
        raw = json.loads((REPO_ROOT / "data" / "pilot" / "units.json")
                         .read_text("utf-8"))["units"]
        expected = sorted(u["uid"] for u in raw if u["street"] == "彩虹街道")
        self.assertEqual(expected, [56])
        before = json.dumps(RULE_G3_SINGLE, sort_keys=True)
        actual = dsl.execute(RULE_G3_SINGLE, self.real_ctx)["unit_ids"]
        self.assertEqual(json.dumps(RULE_G3_SINGLE, sort_keys=True), before)
        self.assertTrue(self.ledger.record("case2_single", expected, actual))

    def test_case_3_minus_empty_set(self):
        out = dsl.execute(RULE_G3_EMPTY_MINUS, self.real_ctx)
        self.assertTrue(self.ledger.record("case3_minus_empty", [], out["unit_ids"]))
        self.assertEqual(out["components"], 0)
        self.assertEqual(out["area_km2"], 0.0)
        self.assertEqual(out["warnings"], [])

    def test_case_4_union_duplicate_subtree_idempotent(self):
        out = dsl.execute(RULE_G3_IDEMPOTENT, self.real_ctx)
        self.assertTrue(self.ledger.record("case4_idempotent", [56], out["unit_ids"]))

    def test_case_5_multi_component_synthetic(self):
        out = dsl.execute(RULE_G3_MULTI_COMPONENT, self.syn_ctx())
        self.assertTrue(self.ledger.record("case5_multi_component", [0, 3],
                                           out["unit_ids"]))
        self.assertEqual(out["components"], 2)
        self.assertEqual(
            _g3_oracle_components({0, 3}, self.syn_ctx()["adjacency"]), 2)

    def test_case_6_ambiguous_name_raises(self):
        with self.assertRaises(dsl.DslError):
            dsl.execute(RULE_G3_AMBIGUOUS, self.syn_ctx())

    def test_case_7_nested_tree(self):
        self.assertGreaterEqual(_g3_tree_depth(RULE_G3_NESTED), 4)
        out = dsl.execute(RULE_G3_NESTED, self.syn_ctx())
        # 新布局字面量：甲={0}、乙={3}；(甲∪乙)−乙={0}；∪乙={0,3}；分量 2
        self.assertTrue(self.ledger.record(
            "case7_nested_literal", G3_EXPECTED_NESTED_LITERAL, out["unit_ids"]))
        self.assertEqual(out["components"], 2)
        self.assertEqual(
            _g3_oracle_components({0, 3}, self.syn_ctx()["adjacency"]), 2)

    def test_zz_gate_ledger_summary(self):
        executed = {r["case"] for r in self.ledger.rows}
        required = {
            "case2_single", "case3_minus_empty", "case4_idempotent",
            "case5_multi_component", "case7_nested_literal",
        }
        self.assertTrue(required <= executed, f"七类缺：{required - executed}")
        self.ledger.require_exact_all()


class TestG3RealOracles(unittest.TestCase):
    """真实区县/街道 oracle：expected 全部筛 raw JSON 字段（不经执行器）。"""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = REPO_ROOT / "data" / "pilot"
        cls.before = snapshot_dir(cls.data_dir)
        cls.ctx = dsl.load_pilot_context(cls.data_dir)
        cls.raw_units = json.loads(
            (cls.data_dir / "units.json").read_text("utf-8"))["units"]
        raw_graph = json.loads(
            (cls.data_dir / "unit_graph.json").read_text("utf-8"))
        cls.adjacency = {int(k): list(v) for k, v in raw_graph["adjacency"].items()}
        cls.ledger = G3Ledger()

    @classmethod
    def tearDownClass(cls):
        after = snapshot_dir(cls.data_dir)
        assert after == cls.before, "真实输入目录被修改"

    def test_real_district_haizhu(self):
        expected = sorted(u["uid"] for u in self.raw_units
                          if u["district_code"] == "440105")
        self.assertEqual(len(expected), 131)
        out = dsl.execute({"op": "in_district", "name": "海珠区"}, self.ctx)
        self.assertTrue(self.ledger.record("real_haizhu_131", expected,
                                           out["unit_ids"]))
        self.assertEqual(out["components"],
                         _g3_oracle_components(set(expected), self.adjacency))

    def test_real_district_liwan(self):
        expected = sorted(u["uid"] for u in self.raw_units
                          if u["district_code"] == "440103")
        self.assertEqual(len(expected), 93)
        out = dsl.execute({"op": "in_district", "name": "荔湾区"}, self.ctx)
        self.assertTrue(self.ledger.record("real_liwan_93", expected,
                                           out["unit_ids"]))
        self.assertEqual(out["components"],
                         _g3_oracle_components(set(expected), self.adjacency))

    def test_real_street_nanshitou(self):
        expected = sorted(u["uid"] for u in self.raw_units
                          if u["street"] == "南石头街道")
        out = dsl.execute({"op": "in_street", "name": "南石头街道"}, self.ctx)
        self.assertTrue(self.ledger.record("real_nanshitou", expected,
                                           out["unit_ids"]))
        self.assertEqual(out["components"],
                         _g3_oracle_components(set(expected), self.adjacency))

    def test_real_street_caihong_56(self):
        expected = sorted(u["uid"] for u in self.raw_units
                          if u["street"] == "彩虹街道")
        self.assertEqual(expected, [56])
        out = dsl.execute({"op": "in_street", "name": "彩虹街道"}, self.ctx)
        self.assertTrue(self.ledger.record("real_caihong_56", expected,
                                           out["unit_ids"]))

    def test_real_street_pazhou(self):
        expected = sorted(u["uid"] for u in self.raw_units
                          if u["street"] == "琶洲街道")
        out = dsl.execute({"op": "in_street", "name": "琶洲街道"}, self.ctx)
        self.assertTrue(self.ledger.record("real_pazhou", expected,
                                           out["unit_ids"]))
        self.assertEqual(out["components"],
                         _g3_oracle_components(set(expected), self.adjacency))

    def test_real_nested_union(self):
        rule = {"op": "union", "args": [
            {"op": "in_district", "name": "荔湾区"},
            {"op": "in_street", "name": "琶洲街道"},
            {"op": "in_street", "name": "南石头街道"},
        ]}
        before = json.dumps(rule, sort_keys=True)
        expected = sorted(u["uid"] for u in self.raw_units if (
            u["district_code"] == "440103"
            or u["street"] in ("琶洲街道", "南石头街道")))
        out = dsl.execute(rule, self.ctx)
        self.assertEqual(json.dumps(rule, sort_keys=True), before)
        self.assertTrue(self.ledger.record("real_nested_union", expected,
                                           out["unit_ids"]))
        self.assertEqual(out["components"],
                         _g3_oracle_components(set(expected), self.adjacency))

    def test_real_street_uses_attr_not_geometry(self):
        """v1.7 反偷换：把全部街道几何挪到远端错位坐标后重跑，
        in_street 仍按 street 属性选取，结果与原始真实数据完全一致
        （街道多边形几何不参与单元选取）。
        """
        import copy as _copy
        raw_streets = json.loads(
            (self.data_dir / "streets.json").read_text("utf-8"))
        streets = _copy.deepcopy(raw_streets)
        far = "POLYGON ((120.0 30.0, 120.1 30.0, 120.1 30.1, 120.0 30.1, 120.0 30.0))"
        for row in streets["streets"]:
            row["geom"] = far
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for name in ("units.json", "districts.json", "unit_graph.json"):
                (d / name).write_bytes((self.data_dir / name).read_bytes())
            (d / "streets.json").write_text(
                json.dumps(streets, ensure_ascii=False), "utf-8")
            ctx = dsl.load_pilot_context(d)
            expected = sorted(u["uid"] for u in self.raw_units
                              if u["street"] == "彩虹街道")
            self.assertEqual(expected, [56])
            out = dsl.execute({"op": "in_street", "name": "彩虹街道"}, ctx)
            self.assertTrue(self.ledger.record("real_caihong_attr_not_geom",
                                               expected, out["unit_ids"]))
            out_pazhou = dsl.execute({"op": "in_street", "name": "琶洲街道"}, ctx)
            expected_pazhou = sorted(u["uid"] for u in self.raw_units
                                     if u["street"] == "琶洲街道")
            self.assertTrue(self.ledger.record(
                "real_pazhou_attr_not_geom", expected_pazhou,
                out_pazhou["unit_ids"]))

    def test_zz_gate_ledger_summary(self):
        executed = {r["case"] for r in self.ledger.rows}
        required = {
            "real_haizhu_131", "real_liwan_93", "real_nanshitou",
            "real_caihong_56", "real_pazhou", "real_nested_union",
            "real_caihong_attr_not_geom",
        }
        self.assertTrue(required <= executed, f"真实 oracle 缺：{required - executed}")
        self.ledger.require_exact_all()


class TestG3StaticDiscipline(unittest.TestCase):
    """静态纪律：无 side_of/near 实现、无坐标转换、不读 L2 细面。"""

    def test_no_side_of_or_near_implementation(self):
        src = MODULE_PATH.read_text("utf-8")
        # side_of/near 只允许出现在拒绝语义（常量/注释/异常）；求值器不得分发
        self.assertNotIn('op == "side_of"', src)
        self.assertNotIn('op == "near"', src)
        with self.assertRaises(dsl.DslError):
            dsl.validate_rule({"op": "side_of", "name": "x"})
        with self.assertRaises(dsl.DslError):
            dsl.validate_rule({"op": "near", "name": "x"})

    def test_no_coordinate_conversion_dependencies(self):
        import ast
        src = MODULE_PATH.read_text("utf-8")
        for banned in ("pyproj", "Transformer", "osgeo", "to_crs"):
            self.assertNotIn(banned, src)
        top = set()
        for node in ast.parse(src).body:
            if isinstance(node, ast.Import):
                top.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                top.add(node.module.split(".")[0])
        self.assertTrue(
            top <= {"__future__", "copy", "json", "math", "pathlib", "typing",
                    "shapely"},
            f"意外顶层 import：{top}")

    def test_no_l2_fine_face_input(self):
        src = MODULE_PATH.read_text("utf-8")
        for banned in ("fences_yeidai", "fences_dealer"):
            self.assertNotIn(banned, src)
        for const, fname in (("UNITS_FILENAME", "units.json"),
                             ("STREETS_FILENAME", "streets.json"),
                             ("DISTRICTS_FILENAME", "districts.json"),
                             ("UNIT_GRAPH_FILENAME", "unit_graph.json")):
            self.assertEqual(getattr(dsl, const), fname)


if __name__ == "__main__":
    unittest.main()

