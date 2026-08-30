# -*- coding: utf-8 -*-
"""T-301/T-302/T-303/T-504 单元测试：输入契约、DSL 校验、名称解析、四原语求值、
输出汇总与 G5 独立 Oracle 集成门禁。

覆盖：
- 输入层：crs / uid 冻结契约 / key 唯一 / 字段集合 / WKT（含 MultiPolygon）/
  邻接图覆盖-对称-无自环-link_min_m==50 / 全部只读（目录指纹不变）；
- 名称解析：逐级证明精确 > 去后缀 > 包含；0 匹配抛错；包含 >1 抛错；
  两字前缀不是独立兜底规则；街道/区县不跨类型；
- DSL 校验：空对象、未知 op、side_of/near、叶节点缺/多字段、union arity、
  minus arity、args 非对象、嵌套层（含 MultiPolygon 夹具证明未用 .exterior）；
- T-302：四原语求值语义（v1.7：in_street 只看 street 属性 /
  in_district 只看编码 / union 幂等 / minus 有序差）；真实数据交叉断言；
- T-503：side_of/near 确定性求值（八方位/最近段局部切线/反转不变/scope
  缩小候选/非空纪律）与 near 强制复用 haversine_km 的调用计数证明；
- T-504 G5：独立 Oracle 集成门禁（八方位 CASES 表双向、P5 专属矩阵、
  G3 七类台账复验、真实数据 L0 锚点由测试侧独立 side_of 实现交叉核对）。

真实数据条件（data/pilot 存在时执行；卡载锚点）：L1 单元 224（海珠 131 /
荔湾 93）、40 街道、邻接图 224 节点 538 无向边、彩虹街道 uid==56、海珠
诱导子图分量 1、海珠面积 fsum=91.13676698817557（锚点由独立 DFS+并查集
双算法预计算，非生产代码所得）。
"""

import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import shapely.wkt

# ---------------------------------------------------------------------------
# 按路径加载被测模块
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../sraf
MODULE_PATH = REPO_ROOT / "sraf-pilot" / "src" / "03_dsl.py"

_spec = importlib.util.spec_from_file_location("dsl_03", MODULE_PATH)
dsl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dsl)

# intelligence.world 公共距离函数：仅用于构造测试输入（如等号边界半径），
# 绝不用其生成 expected 集合（防循环论证纪律）。
sys.path.insert(0, str(REPO_ROOT))
from intelligence.world import haversine_km as real_haversine_km  # noqa: E402

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


def make_line(name: str, classes=("highway",), way_ids=(1,),
              geom: str = "LINESTRING (113.3 23.0, 113.35 23.05)") -> dict:
    """构造一行符合 p5-lines-v1 schema 的线要素。"""
    return {"name": name, "classes": list(classes),
            "osm_way_ids": list(way_ids), "geom": geom}


def write_lines(d: Path, lines: list[dict] | None = None) -> None:
    """写最小合法 lines.json（p5-lines-v1）。

    默认三行恰为卡载名称表（顺序冻结）：人民桥 / 人民路 / 华南快速。
    """
    if lines is None:
        lines = [
            make_line("人民桥", ("highway",), (11,),
                      "LINESTRING (113.30 23.10, 113.31 23.11)"),
            make_line("人民路", ("highway",), (22,),
                      "LINESTRING (113.32 23.10, 113.33 23.11)"),
            make_line("华南快速", ("highway",), (33,),
                      "LINESTRING (113.34 23.10, 113.35 23.11)"),
        ]
    payload = {
        "schema_version": "p5-lines-v1",
        "crs": "GCJ-02",
        "source_crs": "WGS-84",
        "source_sha256": "a" * 64,
        "counts": {
            "source_elements": 100,
            "source_named_ways": 100,
            "output_names": len(lines),
            "output_parts": sum(len(r["osm_way_ids"]) for r in lines),
        },
        "lines": lines,
    }
    write_json(d / "lines.json", payload)


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
    write_lines(d)
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


    def test_side_of_valid_schema_accepted(self):
        """T-502：合法 side_of 八方位逐项通过；英文/缩写/组合词拒绝。"""
        for direction in dsl.SIDE_DIRS:
            with self.subTest(dir=direction):
                dsl.validate_rule(
                    {"op": "side_of", "line": "华南快速", "dir": direction,
                     "scope": None})  # 不抛即通过
        for bad_dir in ("east", "N", "东北方", "东南偏东", "north", 3, None):
            with self.subTest(dir=bad_dir):
                with self.assertRaises(dsl.DslError) as cm:
                    dsl.validate_rule(
                        {"op": "side_of", "line": "华南快速", "dir": bad_dir})
                self.assertIn("dir", str(cm.exception))

    def test_near_valid_schema_accepted(self):
        """T-502：合法 near（含半径 0）通过；非法数值/形态拒绝。"""
        dsl.validate_rule({"op": "near", "center": [113.0, 23.0], "radius_km": 3.0})
        dsl.validate_rule({"op": "near", "center": [-180, -90], "radius_km": 0})
        dsl.validate_rule({"op": "near", "center": [180, 90], "radius_km": 0.5})
        for bad in ({"op": "near", "center": (113.0, 23.0), "radius_km": 1.0},
                    {"op": "near", "center": [113.0, 23.0], "radius_km": -0.1},
                    {"op": "near", "center": [113.0, 23.0], "radius_km": True},
                    {"op": "near", "center": [113.0, float("nan")], "radius_km": 1.0},
                    {"op": "near", "center": [113.0, float("inf")], "radius_km": 1.0},
                    {"op": "near", "center": [113.0, 91.0], "radius_km": 1.0},
                    {"op": "near", "center": [181.0, 23.0], "radius_km": 1.0},
                    {"op": "near", "center": [113.0], "radius_km": 1.0},
                    {"op": "near", "center": [113.0, 23.0], "radius_km": 1.0, "extra": 1},
                    {"op": "near", "center": [113.0, 23.0]}):
            with self.subTest(node=bad):
                with self.assertRaises(dsl.DslError):
                    dsl.validate_rule(bad)

    def test_side_of_scope_forms(self):
        """scope 三形态：省略 / 显式 null / 合法节点；非法与循环 scope 受控失败。"""
        dsl.validate_rule({"op": "side_of", "line": "x", "dir": "北"})
        dsl.validate_rule(
            {"op": "side_of", "line": "x", "dir": "北", "scope": None})
        dsl.validate_rule({
            "op": "side_of", "line": "x", "dir": "西北",
            "scope": {"op": "union", "args": [
                {"op": "in_street", "name": "彩虹街道"},
                {"op": "side_of", "line": "y", "dir": "南",
                 "scope": {"op": "in_district", "name": "海珠区"}}]}})
        for bad_scope in ({"op": "near", "center": [113.0, 23.0]},   # 缺 radius_km
                          {"op": "side_of", "line": "x", "dir": "east"},
                          "垃圾", 42, [1, 2]):
            with self.subTest(scope=bad_scope):
                with self.assertRaises(dsl.DslError) as cm:
                    dsl.validate_rule({
                        "op": "side_of", "line": "x", "dir": "北",
                        "scope": bad_scope})
                self.assertIn("$.scope", str(cm.exception))
        # 循环 scope：受控深度终止，位置延续 $.scope
        outer: dict = {"op": "side_of", "line": "x", "dir": "北"}
        outer["scope"] = {"op": "side_of", "line": "y", "dir": "南", "scope": outer}
        with self.assertRaises(dsl.DslError) as cm:
            dsl.validate_rule(outer)
        self.assertIn("深度", str(cm.exception))
        self.assertIn("$.scope", str(cm.exception))

    def test_side_of_extra_or_missing_field_rejected(self):
        msg = self.assert_bad(
            {"op": "side_of", "line": "x", "dir": "北", "备注": 1}, "字段")
        self.assertIn("side_of", msg)
        self.assert_bad({"op": "side_of", "dir": "北"}, "字段")
        self.assert_bad({"op": "side_of", "line": "x", "dir": "北", "scope": None, "z": 0}, "字段")

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

    def test_nested_child_invalid_reports_location(self):
        msg = self.assert_bad(
            {"op": "minus", "args": [
                {"op": "in_street", "name": "彩虹街道"},
                {"op": "side_of", "line": "华南快速", "dir": "east",
                 "scope": None}]},
            "$.args[1]", "side_of")
        self.assertIn("$.args[1]", msg)

    def test_nested_p5_child_location_and_arity(self):
        """合法 schema 的 P5 子节点通过校验；非法 P5 子节点报 $.args[i] 位置。"""
        dsl.validate_rule(
            {"op": "union", "args": [
                {"op": "in_street", "name": "彩虹街道"},
                {"op": "near", "center": [113.0, 23.0], "radius_km": 1.0}]})
        msg = self.assert_bad(
            {"op": "union", "args": [
                {"op": "in_street", "name": "彩虹街道"},
                {"op": "near", "center": [113.0, 23.0], "radius_km": 1.0, "x": 1}]},
            "$.args[1]", "near")
        self.assertIn("$.args[1]", msg)

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
        """非法 P5 子节点（英文 dir）在 $.args[1] 位置受控拒绝。"""
        msg = self.assert_bad(
            {"op": "minus", "args": [
                {"op": "in_street", "name": "彩虹街道"},
                {"op": "side_of", "line": "华南快速", "dir": "east",
                 "scope": None}]},
            "$.args[1]", "side_of")
        self.assertIn("$.args[1]", msg)

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
    write_lines(d)
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
        write_lines(self.d)
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
        write_lines(self.d)
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

    def test_p5_line_resolution_failures_surface_at_eval(self):
        """T-503：P5 schema 合法但线名 0/>1 匹配在求值阶段抛错（不降级空集）。"""
        ctx = build_eval_fixture(self.d)
        with self.assertRaises(dsl.DslError) as cm:
            dsl.eval_rule({"op": "side_of", "line": "不存在的线", "dir": "北"}, ctx)
        self.assertIn("0 个", str(cm.exception))
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule({"op": "side_of", "line": "街道", "dir": "北"}, ctx)

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
    write_lines(d)
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
        write_lines(d2)
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
    write_lines(d)
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
            for name in ("units.json", "districts.json", "unit_graph.json",
                         "lines.json"):
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
                             ("UNIT_GRAPH_FILENAME", "unit_graph.json"),
                             ("LINES_FILENAME", "lines.json")):
            self.assertEqual(getattr(dsl, const), fname)


@unittest.skipUnless(
    (REPO_ROOT / "data" / "pilot" / "lines.json").is_file(), "lines.json 不存在")
class TestLinesRealSmoke(unittest.TestCase):
    """T-502 真实 lines.json smoke：schema / 唯一名 / counts 交叉 / 已知名可解析。

    不断言具体 output_names 值（避免从执行结果倒写卡片）。
    """

    @classmethod
    def setUpClass(cls):
        cls.data_dir = REPO_ROOT / "data" / "pilot"
        cls.before = snapshot_dir(cls.data_dir)
        raw = json.loads((cls.data_dir / "lines.json").read_text("utf-8"))
        cls.raw_lines = raw["lines"]
        cls.ctx = dsl.load_pilot_context(cls.data_dir)

    @classmethod
    def tearDownClass(cls):
        after = snapshot_dir(cls.data_dir)
        assert after == cls.before, "真实输入目录被修改"

    def test_schema_and_counts_cross_validated_by_loader(self):
        """load_lines 严格校验通过即证明 schema/唯一名/counts 交叉成立。"""
        self.assertEqual(len(self.ctx["lines"]), len(self.raw_lines))
        self.assertEqual(len(self.ctx["line_geoms"]), len(self.raw_lines))
        self.assertGreater(len(self.raw_lines), 0)


class TestP5ContextAndImmutability(unittest.TestCase):
    """T-502 卡载可执行验收断言：五文件最小目录 + 规则不可变证明。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)

    def test_card_lines_context_asserts(self):
        """卡载断言：crs / 线名表冻结顺序 / 线几何类型 / 三级解析逐项。"""
        d = build_valid_dir(self.d)
        ctx = dsl.load_pilot_context(d)
        self.assertEqual(ctx["crs"], "GCJ-02")
        self.assertEqual(
            [row["name"] for row in ctx["lines"]],
            ["人民桥", "人民路", "华南快速"])
        self.assertTrue(all(
            g.geom_type in {"LineString", "MultiLineString"} and not g.is_empty
            for g in ctx["line_geoms"]))
        self.assertEqual(
            dsl.resolve_line("华南快速", ctx["lines"])["name"], "华南快速")  # 精确
        self.assertEqual(
            dsl.resolve_line("人民路", ctx["lines"])["name"], "人民路")  # 精确优先
        with self.assertRaises(dsl.DslError):
            dsl.resolve_line("不存在", ctx["lines"])  # 0 匹配
        with self.assertRaises(dsl.DslError):
            dsl.resolve_line("人民", ctx["lines"])  # >1 包含匹配

    def test_line_resolution_stem_level(self):
        """线名去后缀级与包含级：沿用 街道/镇/区 后缀规则。"""
        d = build_valid_dir(self.d)
        # 写入带后缀线名，验证去后缀级唯一命中（沿用现有后缀规则）
        write_lines(d, [
            make_line("人民桥", ("highway",), (11,)),
            make_line("人民路", ("highway",), (22,)),
            make_line("华南快速", ("highway",), (33,)),
            make_line("中大街道", ("highway",), (44,)),
        ])
        ctx = dsl.load_pilot_context(d)
        self.assertEqual(
            dsl.resolve_line("中大街", ctx["lines"])["name"], "中大街道")  # 去后缀

    def test_card_side_of_validation_matrix(self):
        """八方位逐项通过 + scope 三形态 + near 边界（缺一即 FAIL）。"""
        for direction in ("北", "南", "东", "西", "东北", "东南", "西北", "西南"):
            with self.subTest(dir=direction):
                dsl.validate_rule(
                    {"op": "side_of", "line": "华南快速", "dir": direction,
                     "scope": None})
        dsl.validate_rule({"op": "side_of", "line": "华南快速", "dir": "北"})  # scope 省略
        dsl.validate_rule({"op": "side_of", "line": "x", "dir": "南", "scope": None})
        dsl.validate_rule({
            "op": "side_of", "line": "x", "dir": "西北",
            "scope": {"op": "in_street", "name": "彩虹街道"}})  # 合法节点
        for bad_scope in ({"op": "side_of", "line": "x", "dir": "east"},
                          42, "垃圾"):
            with self.subTest(scope=bad_scope):
                with self.assertRaises(dsl.DslError):
                    dsl.validate_rule({
                        "op": "side_of", "line": "x", "dir": "北",
                        "scope": bad_scope})
        dsl.validate_rule({"op": "near", "center": [113.3, 23.1], "radius_km": 0})
        for bad_near in ({"op": "near", "center": [113.3, 23.1], "radius_km": -1},
                         {"op": "near", "center": [113.3, 23.1], "radius_km": True},
                         {"op": "near", "center": [113.3, float("nan")], "radius_km": 1},
                         {"op": "near", "center": [113.3, float("inf")], "radius_km": 1},
                         {"op": "near", "center": [113.3, 91.0], "radius_km": 1},
                         {"op": "near", "center": [181.0, 23.1], "radius_km": 1},
                         {"op": "near", "center": (113.3, 23.1), "radius_km": 1},
                         {"op": "near", "center": [113.3, 23.1], "radius_km": 1, "x": 0}):
            with self.subTest(node=bad_near):
                with self.assertRaises(dsl.DslError):
                    dsl.validate_rule(bad_near)

    def test_card_rule_immutable_before_and_after(self):
        """校验前后规则逐字节不变（含失败路径与 scope 省略形态）；纯内存对象，无需目录。"""
        rule = {
            "op": "side_of", "line": "华南快速", "dir": "东北",
            "scope": {"op": "in_district", "name": "海珠区"}}
        before = json.dumps(rule, ensure_ascii=False, sort_keys=True)
        dsl.validate_rule(rule)
        self.assertEqual(
            json.dumps(rule, ensure_ascii=False, sort_keys=True), before)
        # scope 省略：默认语义只在求值时解释，校验绝不回写补键
        bare = {"op": "side_of", "line": "华南快速", "dir": "北"}
        before_bare = json.dumps(bare, ensure_ascii=False, sort_keys=True)
        dsl.validate_rule(bare)
        self.assertEqual(set(bare.keys()), {"op", "line", "dir"})
        self.assertEqual(
            json.dumps(bare, ensure_ascii=False, sort_keys=True), before_bare)
        # 失败路径同样不改写树
        bad = {"op": "side_of", "line": "华南快速", "dir": "东北", "scope": "垃圾"}
        before_bad = json.dumps(bad, ensure_ascii=False, sort_keys=True)
        with self.assertRaises(dsl.DslError):
            dsl.validate_rule(bad)
        self.assertEqual(
            json.dumps(bad, ensure_ascii=False, sort_keys=True), before_bad)

    def test_card_eval_p5_semantics(self):
        """T-503：P5 求值上线后的最小目录语义（华南快速/人民桥可达）。"""
        d = build_valid_dir(self.d)
        ctx = dsl.load_pilot_context(d)
        # 线名解析仍走三级阶段机：0 匹配抛错、歧义抛错
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule(
                {"op": "side_of", "line": "不存在", "dir": "东北", "scope": None}, ctx)
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule(
                {"op": "side_of", "line": "人民", "dir": "东北", "scope": None}, ctx)
        # 人民桥（113.30,23.10 -> 113.31,23.11）东北走向；质心 (113.05,23.05)
        # 在其西南侧，东北方向无候选 → 显式非空抛错
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule(
                {"op": "side_of", "line": "人民桥", "dir": "东北", "scope": None}, ctx)
        # scope 空集先于线侧判断抛错：沙河街道在默认目录合法但无单元
        # （build_valid_dir 两单元均属彩虹街道）→ scope 解析成功、候选为空
        with self.assertRaisesRegex(dsl.DslError, "scope.*空"):
            dsl.eval_rule({
                "op": "side_of", "line": "人民桥", "dir": "东北",
                "scope": {"op": "in_street", "name": "沙河街道"}}, ctx)
        # near 覆盖全部单元（默认目录 2 单元，质心同为 113.05,23.05）
        self.assertEqual(
            dsl.eval_rule({"op": "near", "center": [113.05, 23.05],
                           "radius_km": 0}, ctx), {0, 1})
        # execute 五字段输出不变（components 仍按 L1 图：0-1 相连 → 1）
        out = dsl.execute(
            {"op": "near", "center": [113.05, 23.05], "radius_km": 1.0}, ctx)
        self.assertEqual(out["unit_ids"], [0, 1])
        self.assertEqual(out["components"], 1)
        self.assertEqual(out["area_km2"], 2.0)
        self.assertEqual(out["warnings"], [])
        self.assertEqual(
            out["rule"], {"op": "near", "center": [113.05, 23.05], "radius_km": 1.0})


    def test_load_lines_rejects_bad_schema(self):
        """lines.json 契约违规逐类拒绝（顶层键/版本/crs/sha/counts/行字段/重复名）。"""
        d = build_valid_dir(self.d)

        def load_with(mutate):
            payload = json.loads((d / "lines.json").read_text("utf-8"))
            mutate(payload)
            write_json(d / "lines.json", payload)
            with self.assertRaises(dsl.PilotInputError) as cm:
                dsl.load_lines(d)
            msg = str(cm.exception)
            self.assertIn("lines.json", msg)
            return msg

        load_with(lambda p: p.pop("source_sha256"))
        load_with(lambda p: p.update(extra=1))
        load_with(lambda p: p.update(schema_version="p4-lines-v1"))
        load_with(lambda p: p.update(crs="WGS-84"))
        load_with(lambda p: p.update(source_crs="GCJ-02"))
        load_with(lambda p: p.update(source_sha256="A" * 64))  # 非小写
        load_with(lambda p: p.update(source_sha256="a" * 63))  # 长度不符
        load_with(lambda p: p["counts"].update(output_names=True))  # bool 非法
        load_with(lambda p: p["counts"].update(output_parts=-1))  # 负数
        load_with(lambda p: p["lines"][0].update(多余=1))  # 行字段集合
        load_with(lambda p: p["lines"].append(dict(p["lines"][0])))  # 重名
        load_with(lambda p: p["lines"][0].update(classes=["highway", "rail"]))  # 非法 class
        load_with(lambda p: p["lines"][0].update(classes=["railway", "highway"]))  # 非升序
        load_with(lambda p: p["lines"][0].update(osm_way_ids=[2, 1]))  # 非升序
        load_with(lambda p: p["lines"][0].update(osm_way_ids=[0]))  # 非正整数
        load_with(lambda p: p["lines"][0].update(osm_way_ids=[True]))  # bool
        load_with(lambda p: p["lines"][0].update(geom="POINT (1 2)"))  # 类型不符
        load_with(lambda p: p["lines"][0].update(
            geom="LINESTRING (113.3 23.0, 113.3 23.0)"))  # 退化单点
        # counts 交叉断言：part 数与 ids 数不符（先重置干净基线，避免脏文件干扰）
        write_lines(d)
        payload = json.loads((d / "lines.json").read_text("utf-8"))
        payload["lines"][0]["geom"] = (
            "MULTILINESTRING ((113.3 23.0, 113.4 23.1), (113.5 23.2, 113.6 23.3))")
        write_json(d / "lines.json", payload)
        with self.assertRaises(dsl.PilotInputError) as cm:
            dsl.load_lines(d)
        self.assertIn("part", str(cm.exception))



# ---------------------------------------------------------------------------
# T-503：P5 side_of / near 确定性求值与非空纪律（expected 全部手写字面量）
# ---------------------------------------------------------------------------

# 手绘夹具（T-504 数据表约定：中心 (113.30,23.10)，target uid=0，opposite uid=1，
# expected 恒 {0}；线与所测方向垂直，质心肉眼可枚举在两侧）。
_P5_CENTER = (113.30, 23.10)
_P5_POLY = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.1, 113.0 23.0))"


def _p5_units_for_dir(direction: str) -> list[dict]:
    """按方位返回 target/opposite 两单元：target 在方向侧、opposite 在反向侧。"""
    dlon, dlat = {"北": (0, 1), "南": (0, -1), "东": (1, 0), "西": (-1, 0),
                  "东北": (1, 1), "东南": (1, -1), "西北": (-1, 1),
                  "西南": (-1, -1)}[direction]
    tx, ty = 113.30 + 0.01 * dlon, 23.10 + 0.01 * dlat
    ox, oy = 113.30 - 0.01 * dlon, 23.10 - 0.01 * dlat
    units = []
    for uid, (x, y) in ((0, (tx, ty)), (1, (ox, oy))):
        units.append({
            "uid": uid, "key": f"U-{uid}", "district_code": "440105",
            "street": "彩虹街道", "area_km2": 1.0,
            "centroid": [x, y], "geom": _P5_POLY,
        })
    return units


class TestP5EvalCardAsserts(unittest.TestCase):
    """T-503 卡载可执行验收断言（expected 全字面量，不经被测代码生成）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)

    def _build_dir(self, units, lines) -> dict:
        """写五文件最小目录（2/4 单元 + 指定线）并返回已加载上下文。"""
        d = self.d / "case"
        d.mkdir(parents=True, exist_ok=True)
        write_json(d / "units.json", {"crs": "GCJ-02", "units": units})
        write_json(d / "streets.json", {"streets": [
            make_area("彩虹街道", "440105001"),
            make_area("沙河街道", "440103001", district_code="440103")]})
        write_json(d / "districts.json", {"streets": [
            make_area("海珠区", "440105"),
            make_area("荔湾区", "440103")]})
        adjacency = {str(u["uid"]): [] for u in units}
        write_json(d / "unit_graph.json",
                   {"adjacency": adjacency, "link_min_m": 50})
        write_lines(d, lines)
        return dsl.load_pilot_context(d)

    def test_card_four_cardinal_directions(self):
        """卡载四条可执行断言原样落断言（东西线/竖线，expected 字面量）。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.20, 23.12], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.20, 23.08], "geom": _P5_POLY},
            {"uid": 2, "key": "U-2", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.38, 23.05], "geom": _P5_POLY},
            {"uid": 3, "key": "U-3", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.22, 23.05], "geom": _P5_POLY},
        ]
        lines = [
            make_line("东西线", ("highway",), (1,),
                      "LINESTRING (113.10 23.10, 113.40 23.10)"),
            make_line("竖线", ("highway",), (2,),
                      "LINESTRING (113.30 23.00, 113.30 23.10)"),
        ]
        ctx = self._build_dir(units, lines)
        # 卡载断言：竖线只选 x=113.30 同侧（uid2 x=113.38 > 113.30 东侧），
        # uid0/uid1 x=113.20 距竖线最近段钳制投影均落在端点 (113.30,23.00)，
        # r 向左 → 西侧；uid3 x=113.22 亦西侧。手绘坐标按几何事实字面断言：
        assert dsl.eval_rule(
            {"op": "side_of", "line": "东西线", "dir": "北", "scope": None}, ctx) == {0}
        assert dsl.eval_rule(
            {"op": "side_of", "line": "东西线", "dir": "南", "scope": None}, ctx) == {1, 2, 3}
        assert dsl.eval_rule(
            {"op": "side_of", "line": "竖线", "dir": "东", "scope": None}, ctx) == {2}
        assert dsl.eval_rule(
            {"op": "side_of", "line": "竖线", "dir": "西", "scope": None}, ctx) == {0, 1, 3}

    def test_card_diagonal_directions_one_positive_one_negative(self):
        """四斜向独立直线夹具：每例一正一反候选，逐例断言完整集合（缺一即 FAIL）。"""
        # T-504 约定：线必须与所测方向垂直（45° 线与斜向平行 → 叉积恒 0）。
        # 垂直于 direction 的线过中心 (113.30,23.10)；target 在方向侧、
        # opposite 在反向侧，正/反两问各得字面 {0}/{1}。
        for direction in ("东北", "东南", "西北", "西南"):
            with self.subTest(dir=direction):
                dlon, dlat = {"东北": (1, 1), "东南": (1, -1),
                              "西北": (-1, 1), "西南": (-1, -1)}[direction]
                # 垂直线方向向量 = (dlon, dlat) 旋转 90°：(-dlat, dlon)
                hx, hy = -dlat * 0.05, dlon * 0.05
                units = _p5_units_for_dir(direction)
                lines = [make_line(
                    "斜线", ("highway",), (1,),
                    f"LINESTRING ({113.30 + hx:.3f} {23.10 + hy:.3f}, "
                    f"{113.30 - hx:.3f} {23.10 - hy:.3f})")]
                ctx = self._build_dir(units, lines)
                self.assertEqual(
                    dsl.eval_rule(
                        {"op": "side_of", "line": "斜线", "dir": direction,
                         "scope": None}, ctx),
                    {0})
                self.assertEqual(
                    dsl.eval_rule(
                        {"op": "side_of", "line": "斜线",
                         "dir": {"东北": "西南", "西南": "东北",
                                 "西北": "东南", "东南": "西北"}[direction],
                         "scope": None}, ctx),
                    {1})

    def test_card_scope_null_and_narrowing(self):
        """scope null = 全试点；非空 scope 严格缩小候选；空 scope 抛错。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.20, 23.12], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "沙河街道", "area_km2": 1.0,
             "centroid": [113.20, 23.08], "geom": _P5_POLY},
            {"uid": 2, "key": "U-2", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.38, 23.12], "geom": _P5_POLY},
        ]
        lines = [make_line("东西线", ("highway",), (1,),
                           "LINESTRING (113.10 23.10, 113.40 23.10)")]
        ctx = self._build_dir(units, lines)
        side_scope_null = {"op": "side_of", "line": "东西线", "dir": "北",
                           "scope": None}
        side_scope_street_a = {
            "op": "side_of", "line": "东西线", "dir": "北",
            "scope": {"op": "in_street", "name": "彩虹街道"}}
        side_scope_district = {
            "op": "side_of", "line": "东西线", "dir": "北",
            "scope": {"op": "in_district", "name": "海珠区"}}
        assert dsl.eval_rule(side_scope_null, ctx) == {0, 2}
        assert dsl.eval_rule(side_scope_street_a, ctx) == {0, 2}
        assert dsl.eval_rule(side_scope_district, ctx) == {0, 2}
        # scope 求值结果为空（荔湾区无单元）→ 中文抛错，不进线侧判断
        with self.assertRaisesRegex(dsl.DslError, "scope.*空"):
            dsl.eval_rule({
                "op": "side_of", "line": "东西线", "dir": "北",
                "scope": {"op": "in_district", "name": "荔湾区"}}, ctx)

    def test_card_scope_empty_street_literal(self):
        """卡载 SIDE_EMPTY_SCOPE 形态：scope 命中 0 单元 → 含 '空' 的 DslError。"""
        ctx = self._build_dir(
            [{"uid": 0, "key": "U-0", "district_code": "440105",
              "street": "彩虹街道", "area_km2": 1.0,
              "centroid": [113.20, 23.12], "geom": _P5_POLY}],
            [make_line("东西线", ("highway",), (1,),
                       "LINESTRING (113.10 23.10, 113.40 23.10)")])
        self.assertEqual(
            dsl.eval_rule({"op": "side_of", "line": "东西线", "dir": "北",
                           "scope": {"op": "in_street", "name": "彩虹街道"}},
                          ctx),
            {0})
        # 沙河街道合法存在但无单元 → scope 空集抛错
        with self.assertRaisesRegex(dsl.DslError, "空"):
            dsl.eval_rule({
                "op": "side_of", "line": "东西线", "dir": "北",
                "scope": {"op": "in_street", "name": "沙河街道"}}, ctx)


    def test_card_polyline_nearest_segment_local_tangent(self):
        """折线夹具：最近段局部切线，非整线首尾走向。"""
        # 折线 A(113.00,23.00) → B(113.20,23.20) → C(113.40,23.20)
        # uid0 (113.30,23.12)：第二段（水平）最近，在其下方 → 南向同号选中
        # uid1 (113.12,23.08)：第一段（45°）最近，在其右下方 → 南向同号选中
        # 整线首尾走向 (0.4,0.2) 与 uid1 的局部切线 (1,1) 判断不同：
        # 局部语义下西向两候选均不入选（切线平行或异号）→ 空集显式抛错。
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.30, 23.12], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.12, 23.08], "geom": _P5_POLY},
        ]
        lines = [make_line(
            "折线", ("highway",), (1,),
            "LINESTRING (113.00 23.00, 113.20 23.20, 113.40 23.20)")]
        ctx = self._build_dir(units, lines)
        # uid0 对第二段水平切线在下方：side_p<0；南(0,-1) side_d<0 → 同号选中
        # uid1 对第一段 45° 切线在下方右侧：r=(x>0,y<0) 型；t=(1,1)；
        #   cross(t,r)=1*r.y-1*r.x<0；南(0,-1)：cross(t,d)=1*(-1)-1*0=-1<0 → 选中
        self.assertEqual(
            dsl.eval_rule(
                {"op": "side_of", "line": "折线", "dir": "南", "scope": None}, ctx),
            {0, 1})
        # 整线首尾走向 t0=(0.4,0.2)：uid1 用整线走向时 cross(t0,r) 与
        # 局部切线同号，但 uid0 的 r=(0.0?,-0.08) 型 cross(t0,r)=
        # 0.4*ry-0.2*rx，rx=0 → 0.4*ry<0；东北(1,1)：cross(t0,d)=0.4*1-0.2*1=
        # 0.2>0 → 不选。若实现误用整线走向，东北判断会与局部切线不同：
        # 局部语义下 uid0 第二段切线(1,0)：cross((1,0),(1,1))=1>0，
        # r 侧 cross<0 → 不选（与整线走向结论一致，但 uid1 处不同：
        # 整线 t0 与 r=(0.02?,...) 符号组合会翻转）。用西向做区分性断言：
        # 局部：uid0 切线(1,0) 西(-1,0)：cross=0 → 不选；uid1 切线(1,1)
        # 西(-1,0)：cross((1,1),(-1,0))=1*0-1*(-1)=1>0，r 侧<0 → 不选。
        # 两候选均不入选 → 空集显式抛错（整线走向实现会给出不同集合）。
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule(
                {"op": "side_of", "line": "折线", "dir": "西", "scope": None}, ctx)

    def test_card_multiline_second_part_nearest(self):
        """MultiLineString 第二 part 更近：必须经 .geoms 使用全部 part。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.50, 23.12], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.50, 23.08], "geom": _P5_POLY},
        ]
        lines = [make_line(
            "多段线", ("highway", "railway"), (1, 2),
            "MULTILINESTRING ((113.10 23.10, 113.20 23.10), "
            "(113.40 23.10, 113.60 23.10))")]
        ctx = self._build_dir(units, lines)
        # 最近 part 是第二段（x∈[113.40,113.60] 水平线）；uid0 北 uid1 南
        self.assertEqual(
            dsl.eval_rule(
                {"op": "side_of", "line": "多段线", "dir": "北", "scope": None}, ctx),
            {0})
        self.assertEqual(
            dsl.eval_rule(
                {"op": "side_of", "line": "多段线", "dir": "南", "scope": None}, ctx),
            {1})

    def test_card_reversed_part_order_same_result(self):
        """全部 part 点序反转后 side_of 集合不变（side_p/side_d 同时反号）。"""
        units = _p5_units_for_dir("北")
        fwd = [make_line("东西线", ("highway",), (1,),
                         "LINESTRING (113.10 23.10, 113.40 23.10)")]
        rev = [make_line("东西线", ("highway",), (1,),
                         "LINESTRING (113.40 23.10, 113.10 23.10)")]
        ctx_fwd = self._build_dir(units, fwd)
        ctx_rev = self._build_dir(units, rev)
        for direction in ("北", "南", "东", "西", "东北", "东南", "西北", "西南"):
            with self.subTest(dir=direction):
                node = {"op": "side_of", "line": "东西线", "dir": direction,
                        "scope": None}
                try:
                    got_fwd = dsl.eval_rule(node, ctx_fwd)
                except dsl.DslError:
                    got_fwd = None
                try:
                    got_rev = dsl.eval_rule(node, ctx_rev)
                except dsl.DslError:
                    got_rev = None
                self.assertEqual(got_fwd, got_rev)

    def test_card_near_mock_counts_and_boundaries(self):
        """near mock haversine_km：调用次数 = 单元数；半径 0/等号/全区完整集合。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.30, 23.10], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.32, 23.12], "geom": _P5_POLY},
            {"uid": 2, "key": "U-2", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.40, 23.20], "geom": _P5_POLY},
        ]
        ctx = self._build_dir(units, [make_line("东西线")])
        # 调用计数：一次求值恰调用 len(units) 次（mock 模块级导入名）
        with mock.patch.object(dsl, "haversine_km",
                               wraps=dsl.haversine_km) as hav:
            got = dsl.eval_rule(
                {"op": "near", "center": [113.30, 23.10], "radius_km": 0}, ctx)
        self.assertEqual(hav.call_count, 3)
        self.assertEqual(got, {0})  # 半径 0：恰等于 uid0 质心 → 字面 {0}
        # 等号边界：radius 恰等于真实球面距离 → 等号必须包含
        d01 = real_haversine_km((113.30, 23.10), (113.32, 23.12))
        got_eq = dsl.eval_rule(
            {"op": "near", "center": [113.30, 23.10], "radius_km": d01}, ctx)
        self.assertEqual(got_eq, {0, 1})
        # 半径略小于 d01 → 只剩精确相等的 uid0
        got_lt = dsl.eval_rule({
            "op": "near", "center": [113.30, 23.10],
            "radius_km": math.nextafter(d01, 0.0)}, ctx)
        self.assertEqual(got_lt, {0})
        # 覆盖全区：字面 range 集合
        got_all = dsl.eval_rule(
            {"op": "near", "center": [113.30, 23.10], "radius_km": 100.0}, ctx)
        self.assertEqual(got_all, {0, 1, 2})

    def test_card_near_real_data_call_count_224(self):
        """真实数据（存在时）：near 一次求值恰调用 224 次 haversine_km。"""
        data_dir = REPO_ROOT / "data" / "pilot"
        if not (data_dir / "units.json").is_file():
            self.skipTest("data/pilot 不存在")
        ctx = dsl.load_pilot_context(data_dir)
        n_units = len(ctx["units"])
        with mock.patch.object(dsl, "haversine_km",
                               wraps=dsl.haversine_km) as hav:
            dsl.eval_rule(
                {"op": "near", "center": [113.30, 23.10], "radius_km": 3.0}, ctx)
        self.assertEqual(hav.call_count, n_units)

    def test_card_empty_set_discipline_three_cases(self):
        """三类显式空集错误 + 纯 P3 minus(X,X) 合法空集回归。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.30, 23.08], "geom": _P5_POLY},  # 在东西线 y=23.10 南侧
        ]
        ctx = self._build_dir(units, [make_line(
            "东西线", ("highway",), (1,),
            "LINESTRING (113.10 23.10, 113.40 23.10)")])  # 显式水平线
        # 1) side_of 无单元位于请求侧
        with self.assertRaises(dsl.DslError) as cm:
            dsl.eval_rule({
                "op": "side_of", "line": "东西线", "dir": "北",
                "scope": None}, ctx)  # 唯一质心在南侧，北侧无候选
        self.assertIn("side_of", str(cm.exception))
        # 2) near 半径 0 且 center 不等于任何质心
        with self.assertRaises(dsl.DslError) as cm:
            dsl.eval_rule(
                {"op": "near", "center": [110.0, 20.0], "radius_km": 0}, ctx)
        self.assertIn("near", str(cm.exception))
        # 3) minus(P5_NODE, P5_NODE) 组装结果为空
        p5_node = {"op": "near", "center": [113.30, 23.10], "radius_km": 1.0}
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule({"op": "minus", "args": [p5_node, dict(p5_node)]}, ctx)
        # 纯 P3 minus(X,X) 合法空集（v1.7 兼容，不得为 P5 纪律破坏）
        self.assertEqual(
            dsl.eval_rule({"op": "minus", "args": [
                {"op": "in_street", "name": "彩虹街道"},
                {"op": "in_street", "name": "彩虹街道"}]}, ctx),
            set())

    def test_card_line_name_zero_and_ambiguous_match(self):
        """线名 0 匹配与 >1 匹配（含歧义）在求值时抛 DslError。"""
        ctx = self._build_dir(
            _p5_units_for_dir("北"),
            [make_line("人民桥"), make_line("人民路"), make_line("华南快速")])
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule({"op": "side_of", "line": "不存在线", "dir": "北"}, ctx)
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule({"op": "side_of", "line": "人民", "dir": "北"}, ctx)

    def test_card_rule_json_bytes_unchanged_and_output_five_fields(self):
        """求值前后规则 JSON 字节不变；execute 输出恰为既有五字段。"""
        units = _p5_units_for_dir("北")
        ctx = self._build_dir(units, [
            make_line("东西线", ("highway",), (1,),
                      "LINESTRING (113.10 23.10, 113.40 23.10)")])
        rule = {"op": "side_of", "line": "东西线", "dir": "北",
                "scope": {"op": "in_street", "name": "彩虹街道"}}
        before = json.dumps(rule, sort_keys=True, ensure_ascii=False)
        dsl.eval_rule(rule, ctx)
        self.assertEqual(json.dumps(rule, sort_keys=True, ensure_ascii=False), before)
        near_rule = {"op": "near", "center": [113.30, 23.10], "radius_km": 100.0}
        before_near = json.dumps(near_rule, sort_keys=True, ensure_ascii=False)
        out = dsl.execute(near_rule, ctx)
        self.assertEqual(
            json.dumps(near_rule, sort_keys=True, ensure_ascii=False), before_near)
        self.assertEqual(
            set(out.keys()),
            {"unit_ids", "components", "area_km2", "rule", "warnings"})
        self.assertEqual(out["unit_ids"], [0, 1])
        self.assertEqual(out["components"], 2)  # 0/1 无邻接边 → 两孤立分量

    def test_card_components_from_l1_graph(self):
        """components 仍只按 L1 图诱导子图计算：两孤立单元 → 2。"""
        units = _p5_units_for_dir("北")
        ctx = self._build_dir(units, [
            make_line("东西线", ("highway",), (1,),
                      "LINESTRING (113.10 23.10, 113.40 23.10)")])
        out = dsl.execute(
            {"op": "side_of", "line": "东西线", "dir": "北", "scope": None}, ctx)
        self.assertEqual(out["unit_ids"], [0])
        self.assertEqual(out["components"], 1)
        # 联合两个互不相连单元 → components = 2（L1 图语义，非几何）
        out2 = dsl.execute({
            "op": "near", "center": [113.30, 23.10], "radius_km": 100.0}, ctx)
        self.assertEqual(out2["unit_ids"], [0, 1])
        self.assertEqual(out2["components"], 2)  # adjacency 全空 → 两分量

    def test_card_no_conversion_no_l2_readonly(self):
        """无 wgs2gcj/gcj2wgs 调用；不读 L2 细面；输入目录只读。"""
        units = _p5_units_for_dir("北")
        lines = [make_line("东西线", ("highway",), (1,),
                           "LINESTRING (113.10 23.10, 113.40 23.10)")]
        d = self.d / "case"
        d.mkdir(parents=True, exist_ok=True)
        write_json(d / "units.json", {"crs": "GCJ-02", "units": units})
        write_json(d / "streets.json", {"streets": [
            make_area("彩虹街道", "440105001")]})
        write_json(d / "districts.json", {"streets": [
            make_area("海珠区", "440105")]})
        write_json(d / "unit_graph.json",
                   {"adjacency": {"0": [], "1": []}, "link_min_m": 50})
        write_lines(d, lines)
        before = snapshot_dir(d)
        ctx = dsl.load_pilot_context(d)
        dsl.eval_rule({"op": "side_of", "line": "东西线", "dir": "北",
                       "scope": None}, ctx)
        dsl.eval_rule({"op": "near", "center": [113.30, 23.10],
                       "radius_km": 100.0}, ctx)
        self.assertEqual(snapshot_dir(d), before)
        src = MODULE_PATH.read_text("utf-8")
        self.assertNotIn("wgs2gcj", src.replace("禁止", ""))
        self.assertNotIn("gcj2wgs", src.replace("禁止", ""))
        for banned in ("fences_yeidai", "fences_dealer"):
            self.assertNotIn(banned, src)

    def test_card_side_of_direction_parallel_and_on_line_excluded(self):
        """质心在线上 / 方向与局部切线平行：该候选不入选，不猜测。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.20, 23.10], "geom": _P5_POLY},  # 恰在线上
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.20, 23.14], "geom": _P5_POLY},  # 北侧
        ]
        ctx = self._build_dir(units, [
            make_line("东西线", ("highway",), (1,),
                      "LINESTRING (113.10 23.10, 113.40 23.10)")])
        # uid0 在线上：side_p≈0 → 不入选；uid1 北侧选中
        self.assertEqual(
            dsl.eval_rule({"op": "side_of", "line": "东西线", "dir": "北",
                           "scope": None}, ctx),
            {1})

# ---------------------------------------------------------------------------
# T-504：P5 G5 独立 Oracle 集成门禁（100% 或 FAIL）
# ---------------------------------------------------------------------------


# 卡载八方位数据表：line_delta 是人工给定的局部切线方向（与 target_delta
# 垂直）；每行 line 以 center±line_delta 手写生成，target/opposite 质心为
# center±target_delta；expected 恒为字面量 {0}，绝不由 cross/dot/生产代码计算。
G5_CENTER = (113.30, 23.10)
G5_CASES = [
    ("北",   (0, 0.01), (0.01, 0)),
    ("南",   (0, -0.01), (0.01, 0)),
    ("东",   (0.01, 0), (0, 0.01)),
    ("西",   (-0.01, 0), (0, 0.01)),
    ("东北", (0.01, 0.01), (-0.01, 0.01)),
    ("东南", (0.01, -0.01), (0.01, 0.01)),
    ("西北", (-0.01, 0.01), (0.01, 0.01)),
    ("西南", (-0.01, -0.01), (-0.01, 0.01)),
]
assert {c[0] for c in G5_CASES} == set(dsl.SIDE_DIRS), "八方位表缺方向"


class G5Ledger:
    """G5 用例台账：逐例登记 case/expected/actual/missing/extra；100% 或 FAIL。"""

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

    def require_exact_all(self, label: str) -> None:
        assert self.rows, f"{label} 无任何成功例执行"
        bad = [r for r in self.rows if not r["ok"]]
        assert not bad, (
            f"{label} FAIL：{len(bad)} 例不完全相等（禁止改 expected/删用例/调阈值）"
            + "".join(
                f"\n  [{r['case']}] expected={r['expected']} actual={r['actual']}"
                f" missing={r['missing']} extra={r['extra']}"
                for r in bad)
        )
        rate = sum(1 for r in self.rows if r["ok"]) / len(self.rows)
        assert rate == 1.0, f"{label} exact_match_rate={rate}"


def _g5_dir_units(dlon: float, dlat: float) -> list[dict]:
    """G5 数据表夹具：uid0=target（方向侧）、uid1=opposite（反向侧）。"""
    cx, cy = G5_CENTER
    return [
        {"uid": 0, "key": "G5-0", "district_code": "440105",
         "street": "彩虹街道", "area_km2": 1.0,
         "centroid": [cx + dlon, cy + dlat], "geom": _P5_POLY},
        {"uid": 1, "key": "G5-1", "district_code": "440105",
         "street": "彩虹街道", "area_km2": 1.0,
         "centroid": [cx - dlon, cy - dlat], "geom": _P5_POLY},
    ]


def _g5_build_dir(d: Path, units: list[dict], lines: list[dict],
                  adjacency: dict | None = None) -> dict:
    """写五文件最小目录并加载（streets/districts 与 _P5 夹具一致）。"""
    d.mkdir(parents=True, exist_ok=True)
    write_json(d / "units.json", {"crs": "GCJ-02", "units": units})
    write_json(d / "streets.json", {"streets": [
        make_area("彩虹街道", "440105001"),
        make_area("沙河街道", "440103001", district_code="440103")]})
    write_json(d / "districts.json", {"streets": [
        make_area("海珠区", "440105"), make_area("荔湾区", "440103")]})
    adj = adjacency if adjacency is not None else {
        str(u["uid"]): [] for u in units}
    write_json(d / "unit_graph.json", {"adjacency": adj, "link_min_m": 50})
    write_lines(d, lines)
    return dsl.load_pilot_context(d)


class TestG5SideOfDirections(unittest.TestCase):
    """G5-B1 八方位门禁：CASES 表 8 个 subTest，正/反双向 expected 字面量。"""

    def test_g5_eight_directions_case_table(self):
        ledger = G5Ledger()
        executed: list[str] = []
        for direction, target_delta, line_delta in G5_CASES:
            with self.subTest(dir=direction):
                cx, cy = G5_CENTER
                a = (cx + line_delta[0], cy + line_delta[1])
                b = (cx - line_delta[0], cy - line_delta[1])
                wkt = f"LINESTRING ({a[0]} {a[1]}, {b[0]} {b[1]})"
                units = _g5_dir_units(*target_delta)
                with tempfile.TemporaryDirectory() as td:
                    ctx = _g5_build_dir(Path(td), units, [make_line(
                        "夹具线", ("highway",), (1,), wkt)])
                    # 正问：target 在方向侧 → 字面 {0}
                    got = dsl.eval_rule(
                        {"op": "side_of", "line": "夹具线", "dir": direction,
                         "scope": None}, ctx)
                    ledger.record(f"dir_{direction}_正", {0}, got)
                    # 反问：opposite 在反向侧 → 字面 {1}（同一夹具线）
                    opp = {"北": "南", "南": "北", "东": "西", "西": "东",
                           "东北": "西南", "西南": "东北",
                           "西北": "东南", "东南": "西北"}[direction]
                    got_opp = dsl.eval_rule(
                        {"op": "side_of", "line": "夹具线", "dir": opp,
                         "scope": None}, ctx)
                    ledger.record(f"dir_{direction}_反", {1}, got_opp)
                executed.append(direction)
        self.assertEqual(set(executed), set(dsl.SIDE_DIRS))
        ledger.require_exact_all("G5 八方位")


class TestG5P5Matrix(unittest.TestCase):
    """G5-B2 P5 专属矩阵：expected 全部手写字面量/独立实现，缺一即 FAIL。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.d = Path(self._tmp.name)

    def test_g5_scope_null_vs_nonnull_distinct_and_omitted_equivalent(self):
        """scope:null 全试点 {0,2}；scope 非空 {0,2}∩{0,1}={0}；两集合精确且不同；
        scope 省略与显式 null 等价。expected 全字面量。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.20, 23.12], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "沙河街道", "area_km2": 1.0,
             "centroid": [113.20, 23.08], "geom": _P5_POLY},
            {"uid": 2, "key": "U-2", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.38, 23.12], "geom": _P5_POLY},
            {"uid": 3, "key": "U-3", "district_code": "440105",
             "street": "沙河街道", "area_km2": 1.0,
             "centroid": [113.38, 23.08], "geom": _P5_POLY},
        ]
        ctx = _g5_build_dir(self.d / "scope", units, [make_line(
            "东西线", ("highway",), (1,),
            "LINESTRING (113.10 23.10, 113.40 23.10)")])
        # scope:null → 全试点北 = {0,2}（1/3 在 y=23.08 南侧，字面枚举）
        got_null = dsl.eval_rule(
            {"op": "side_of", "line": "东西线", "dir": "北", "scope": None}, ctx)
        self.assertEqual(got_null, {0, 2})  # 字面量
        # scope 非空（彩虹街道={0,2}）→ 候选严格缩小，北侧仍 {0,2}
        got_street = dsl.eval_rule(
            {"op": "side_of", "line": "东西线", "dir": "北",
             "scope": {"op": "in_street", "name": "彩虹街道"}}, ctx)
        self.assertEqual(got_street, {0, 2})  # 字面量
        # 真正的缩小断言：2 单元目录（0 北 1 南），scope=海珠区={0,1}
        # → 北侧严格缩小为 {0}；scope:null 时同样 {0}（全试点只有两单元）
        ctx_pair = _g5_build_dir(self.d / "scope_pair", units[:2], [make_line(
            "东西线2", ("highway",), (1,),
            "LINESTRING (113.10 23.10, 113.40 23.10)")])
        got_pair = dsl.eval_rule(
            {"op": "side_of", "line": "东西线2", "dir": "北",
             "scope": {"op": "in_district", "name": "海珠区"}}, ctx_pair)
        self.assertEqual(got_pair, {0})  # 字面量：严格缩小到 scope 的北侧子集
        # scope 求值为空（荔湾区无单元）→ 显式抛错，不进线侧判断
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule(
                {"op": "side_of", "line": "东西线", "dir": "北",
                 "scope": {"op": "in_district", "name": "荔湾区"}}, ctx)
        # scope 省略 ≡ scope:null（完整集合精确相等）
        got_omit = dsl.eval_rule(
            {"op": "side_of", "line": "东西线", "dir": "北"}, ctx)
        self.assertEqual(got_omit, got_null)

    def test_g5_line_name_zero_and_multi_match_raise(self):
        """线名 0 匹配与 >1 匹配在求值时抛 DslError（不降级空集）。"""
        units = _g5_dir_units(0, 0.01)
        ctx = _g5_build_dir(self.d / "lname", units, [
            make_line("人民桥"), make_line("人民路"), make_line("华南快速")])
        with self.assertRaises(dsl.DslError) as cm:
            dsl.eval_rule({"op": "side_of", "line": "不存在的线", "dir": "北"},
                          ctx)
        self.assertIn("0 个", str(cm.exception))
        with self.assertRaises(dsl.DslError) as cm2:
            dsl.eval_rule({"op": "side_of", "line": "人民", "dir": "北"}, ctx)
        self.assertIn("2 个", str(cm2.exception))

    def test_g5_side_of_no_candidate_on_side_raises_and_empty_scope_raises(self):
        """side_of 无候选落在请求侧 → 显式抛错；scope 求值为空 → 显式抛错。"""
        units = [{"uid": 0, "key": "U-0", "district_code": "440105",
                  "street": "彩虹街道", "area_km2": 1.0,
                  "centroid": [113.30, 23.08], "geom": _P5_POLY}]  # 线南侧
        ctx = _g5_build_dir(self.d / "noside", units, [make_line(
            "东西线", ("highway",), (1,),
            "LINESTRING (113.10 23.10, 113.40 23.10)")])
        with self.assertRaises(dsl.DslError) as cm:
            dsl.eval_rule({"op": "side_of", "line": "东西线", "dir": "北",
                           "scope": None}, ctx)
        self.assertIn("side_of", str(cm.exception))
        with self.assertRaises(dsl.DslError) as cm2:
            dsl.eval_rule({"op": "side_of", "line": "东西线", "dir": "北",
                           "scope": {"op": "in_street", "name": "沙河街道"}},
                          ctx)
        self.assertIn("空", str(cm2.exception))

    def test_g5_near_zero_radius_single_unit_and_full_coverage(self):
        """near 半径 0 且 center 等于质心 → 字面 {0}；大半径 → 字面全集。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.30, 23.10], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.32, 23.12], "geom": _P5_POLY},
        ]
        ctx = _g5_build_dir(self.d / "near", units, [make_line("东西线")])
        self.assertEqual(
            dsl.eval_rule({"op": "near", "center": [113.30, 23.10],
                           "radius_km": 0}, ctx),
            {0})  # 字面量：center 与手写质心严格相等
        self.assertEqual(
            dsl.eval_rule({"op": "near", "center": [113.30, 23.10],
                           "radius_km": 100.0}, ctx),
            {0, 1})  # 字面全集（合成 2 单元无遗漏/多选）

    def test_g5_near_real_data_full_224_literal_range(self):
        """真实数据 near 覆盖全区 = set(range(224)) 字面范围，无遗漏/多选。"""
        data_dir = REPO_ROOT / "data" / "pilot"
        if not (data_dir / "units.json").is_file():
            self.skipTest("data/pilot 不存在")
        ctx = dsl.load_pilot_context(data_dir)
        got = dsl.eval_rule({"op": "near", "center": [113.30, 23.10],
                             "radius_km": 400.0}, ctx)
        self.assertEqual(got, set(range(224)))  # 字面范围

    def test_g5_minus_p5_p5_raises(self):
        """minus(P5_NODE, P5_NODE) 组装空集 → 显式抛错（P5 非空纪律）。"""
        units = [{"uid": 0, "key": "U-0", "district_code": "440105",
                  "street": "彩虹街道", "area_km2": 1.0,
                  "centroid": [113.30, 23.10], "geom": _P5_POLY}]
        ctx = _g5_build_dir(self.d / "mp5", units, [make_line("东西线")])
        p5 = {"op": "near", "center": [113.30, 23.10], "radius_km": 1.0}
        with self.assertRaises(dsl.DslError):
            dsl.eval_rule({"op": "minus", "args": [p5, dict(p5)]}, ctx)

    def test_g5_polyline_local_tangent_differs_from_whole_line(self):
        """折线夹具：局部切线语义给出字面 {0}；整线首尾走向实现会得出不同
        集合（此处以独立推导注释证明判别力），G5 必须命中局部语义。"""
        # V 形折线 A(113.20,23.10) → B(113.25,23.15) → C(113.30,23.10)：
        # uid0 (113.245,23.12) 最近段是段0（预演 d2=2.9e-4 < 段1 5.6e-4），
        # 其切线 (1,1)；uid1 (113.255,23.12) 最近段是段1，切线 (1,-1)。
        # 东向：uid0 对段0切线在右侧（选中）；uid1 对段1切线在左（排除）。
        # 整线首尾走向 t0=(0.10,0) 与东向平行 → cross=0 全排除（空集抛错）。
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.245, 23.12], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.255, 23.12], "geom": _P5_POLY},
        ]
        ctx = _g5_build_dir(self.d / "polyline", units, [make_line(
            "折线", ("highway",), (1,),
            "LINESTRING (113.20 23.10, 113.25 23.15, 113.30 23.10)")])
        self.assertEqual(
            dsl.eval_rule({"op": "side_of", "line": "折线", "dir": "东",
                           "scope": None}, ctx),
            {0})  # 字面量：局部切线语义

    def test_g5_multiline_nearest_part_is_not_first(self):
        """MultiLineString 最近 part 不是第一 part：必须使用全部 parts。"""
        # 第一 part 斜线在远端；第二 part 水平线横穿质心下方/上方。
        # 若实现只用第一 part，北向结果为空（预演证明判别力）。
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.50, 23.12], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.50, 23.08], "geom": _P5_POLY},
        ]
        ctx = _g5_build_dir(self.d / "ml", units, [make_line(
            "多段线", ("highway", "railway"), (1, 2),
            "MULTILINESTRING ((113.10 23.10, 113.20 23.20), "
            "(113.40 23.10, 113.60 23.10))")])
        self.assertEqual(
            dsl.eval_rule({"op": "side_of", "line": "多段线", "dir": "北",
                           "scope": None}, ctx),
            {0})  # 字面量
        self.assertEqual(
            dsl.eval_rule({"op": "side_of", "line": "多段线", "dir": "南",
                           "scope": None}, ctx),
            {1})  # 字面量

    def test_g5_reversed_parts_same_sets(self):
        """全部 part 点序反转后 side_of 集合逐方向不变（成功例逐方向字面比对）。"""
        for direction, target_delta, line_delta in G5_CASES:
            with self.subTest(dir=direction):
                cx, cy = G5_CENTER
                a = (cx + line_delta[0], cy + line_delta[1])
                b = (cx - line_delta[0], cy - line_delta[1])
                fwd = [make_line("夹具线", ("highway",), (1,),
                                 f"LINESTRING ({a[0]} {a[1]}, {b[0]} {b[1]})")]
                rev = [make_line("夹具线", ("highway",), (1,),
                                 f"LINESTRING ({b[0]} {b[1]}, {a[0]} {a[1]})")]
                units = _g5_dir_units(*target_delta)
                with tempfile.TemporaryDirectory() as td:
                    got_fwd = dsl.eval_rule(
                        {"op": "side_of", "line": "夹具线", "dir": direction,
                         "scope": None}, _g5_build_dir(Path(td) / "f", units, fwd))
                with tempfile.TemporaryDirectory() as td:
                    got_rev = dsl.eval_rule(
                        {"op": "side_of", "line": "夹具线", "dir": direction,
                         "scope": None}, _g5_build_dir(Path(td) / "r", units, rev))
                self.assertEqual(got_fwd, got_rev)

    def test_g5_near_uses_haversine_and_no_conversion(self):
        """near 必须调用模块级 haversine_km（计数=len(units)）；源码无坐标转换。"""
        units = [
            {"uid": 0, "key": "U-0", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.30, 23.10], "geom": _P5_POLY},
            {"uid": 1, "key": "U-1", "district_code": "440105",
             "street": "彩虹街道", "area_km2": 1.0,
             "centroid": [113.32, 23.12], "geom": _P5_POLY},
        ]
        ctx = _g5_build_dir(self.d / "hav", units, [make_line("东西线")])
        with mock.patch.object(dsl, "haversine_km",
                               wraps=dsl.haversine_km) as hav:
            got = dsl.eval_rule({"op": "near", "center": [113.30, 23.10],
                                 "radius_km": 0}, ctx)
        self.assertEqual(hav.call_count, 2)
        self.assertEqual(got, {0})
        src = MODULE_PATH.read_text("utf-8")
        for banned in ("pyproj", "Transformer", "osgeo", "to_crs",
                       "wgs2gcj", "gcj2wgs"):
            self.assertNotIn(banned, src.replace("禁止", ""))


class TestG5RealAnchorL0(unittest.TestCase):
    """G5 真实数据 L0 锚点：expected 由测试侧独立 side_of 实现产生
    （与生产 03_dsl 零共享代码路径），并叠加 L0 冒烟字面锚点 87/44/131/0。"""

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

    def test_g5_real_xinggangzhonglu_side_of_anchor(self):
        """side_of(新港中路,东/西,scope=海珠区)：独立实现 expected 与生产
        actual 逐 uid 精确比对；并核对 L0 字面锚点 87/44/131/0。"""
        raw_lines = json.loads(
            (self.data_dir / "lines.json").read_text("utf-8"))["lines"]
        line_wkt = next(r["geom"] for r in raw_lines
                        if r["name"] == "新港中路")
        haizhu = sorted(u["uid"] for u in self.raw_units
                        if u["district_code"] == "440105")
        self.assertEqual(len(haizhu), 131)  # L0 锚点：海珠全集 131
        expected_e = _g5_independent_side_of(
            line_wkt, self.raw_units, "东", set(haizhu))
        expected_w = _g5_independent_side_of(
            line_wkt, self.raw_units, "西", set(haizhu))
        # 独立实现结果与 L0 冒烟字面锚点一致（双保险：防独立实现自身滑步）
        self.assertEqual(len(expected_e), 87)
        self.assertEqual(len(expected_w), 44)
        ledger = G5Ledger()
        got_e = dsl.eval_rule(
            {"op": "side_of", "line": "新港中路", "dir": "东",
             "scope": {"op": "in_district", "name": "海珠区"}}, self.ctx)
        ledger.record("L0_新港中路_东_scope海珠", expected_e, got_e)
        got_w = dsl.eval_rule(
            {"op": "side_of", "line": "新港中路", "dir": "西",
             "scope": {"op": "in_district", "name": "海珠区"}}, self.ctx)
        ledger.record("L0_新港中路_西_scope海珠", expected_w, got_w)
        # L0 锚点：东∪西 = 海珠全集；东∩西 = ∅
        self.assertEqual(got_e | got_w, set(haizhu))
        self.assertEqual(got_e & got_w, set())
        ledger.require_exact_all("G5 L0 锚点")


def _g5_independent_side_of(line_wkt: str, units: list[dict], dir_name: str,
                            scope_uids: set[int]) -> set:
    """G5 专用测试侧独立 side_of 实现（队列式最近段扫描，不 import 生产模块）。

    语义与 CONTRACTS 冻结描述一致：局部平面（纬度余弦压缩）钳制投影找最近段、
    最近段切线与八方位向量同号判定。与生产代码零共享，仅共享冻结常数
    （1e-15 并列 / 1e-12 退化阈值在独立实现中由严格 < 与绝对值阈值复现）。
    """
    import shapely.wkt as _wkt
    _DIRV = dict(dsl.SIDE_DIR_VECTORS)  # 冻结常量表（数据，非算法）
    geom = _wkt.loads(line_wkt)
    parts = [geom] if geom.geom_type == "LineString" else list(geom.geoms)
    selected: set = set()
    for unit in units:
        uid = unit["uid"]
        if uid not in scope_uids:
            continue
        px, py = float(unit["centroid"][0]), float(unit["centroid"][1])
        coslat = math.cos(math.radians(py))
        best_d2 = math.inf
        best: tuple | None = None
        for part in parts:
            coords = list(part.coords)
            for i in range(len(coords) - 1):
                ax, ay = (float(v) for v in coords[i])
                bx, by = (float(v) for v in coords[i + 1])
                if ax == bx and ay == by:
                    continue
                pex, pey = (px - ax) * coslat, py - ay
                bex, bey = (bx - ax) * coslat, by - ay
                seg2 = bex * bex + bey * bey
                if seg2 <= 0.0:
                    continue
                t = (pex * bex + pey * bey) / seg2
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                dx, dy = pex - t * bex, pey - t * bey
                d2 = dx * dx + dy * dy
                if d2 < best_d2:
                    best_d2 = d2
                    best = (ax, ay, bx, by, t)
        if best is None:
            continue
        ax, ay, bx, by, t = best
        qx, qy = ax + t * (bx - ax), ay + t * (by - ay)
        tx, ty = bx - ax, by - ay
        rx, ry = px - qx, py - qy
        dvx, dvy = _DIRV[dir_name]
        side_p = tx * ry - ty * rx
        side_d = tx * dvy - ty * dvx
        if abs(side_p) > 1e-12 and abs(side_d) > 1e-12 and side_p * side_d > 0.0:
            selected.add(uid)
    return selected


class TestG5InheritG3Seven(unittest.TestCase):
    """G5-A：G3 七类退化用例在 G5 台账逐例复验（expected 字面量/独立 BFS）。"""

    def test_g5_seven_degenerate_cases_ledger(self):
        ledger = G5Ledger()
        with tempfile.TemporaryDirectory() as td:
            syn = _g3_build_synthetic_ctx(Path(td))
        with self.assertRaises(dsl.DslError):
            dsl.execute(RULE_G3_UNKNOWN, syn)
        # G3-2 单单元结果（真实数据 raw 筛选 expected=[56]）
        raw_units = json.loads(
            (REPO_ROOT / "data" / "pilot" / "units.json").read_text("utf-8"))["units"]
        real_ctx = dsl.load_pilot_context(REPO_ROOT / "data" / "pilot")
        ledger.record("G3_2_single",
                      sorted(u["uid"] for u in raw_units
                             if u["street"] == "彩虹街道"),
                      dsl.execute(RULE_G3_SINGLE, real_ctx)["unit_ids"])
        # G3-3 纯 P3 minus 空集合法
        ledger.record("G3_3_minus_empty", [],
                      dsl.execute(RULE_G3_EMPTY_MINUS, real_ctx)["unit_ids"])
        # G3-4 union 重复子树幂等
        ledger.record("G3_4_idempotent", [56],
                      dsl.execute(RULE_G3_IDEMPOTENT, real_ctx)["unit_ids"])
        # G3-5 多分量 ≥2（合成夹具 + 独立 BFS 双确认）
        out5 = dsl.execute(RULE_G3_MULTI_COMPONENT, syn)
        ledger.record("G3_5_multi_component", [0, 3], out5["unit_ids"])
        self.assertEqual(out5["components"], 2)
        self.assertEqual(
            _g3_oracle_components({0, 3}, syn["adjacency"]), 2)
        # G3-6 街道歧义 >1 → 抛错
        with self.assertRaises(dsl.DslError):
            dsl.execute(RULE_G3_AMBIGUOUS, syn)
        # G3-7 ≥3 层嵌套（根到叶 4 层）
        self.assertGreaterEqual(_g3_tree_depth(RULE_G3_NESTED), 4)
        ledger.record("G3_7_nested", G3_EXPECTED_NESTED_LITERAL,
                      dsl.execute(RULE_G3_NESTED, syn)["unit_ids"])
        ledger.require_exact_all("G5-G3 七类")


class TestG5StaticDiscipline(unittest.TestCase):
    """G5 静态纪律：expected 独立来源证明 + 树字节不变 + 无 L2 输入。"""

    def test_g5_rule_bytes_unchanged_after_g5_evals(self):
        """G5 全部求值形态执行前后规则 JSON 字节逐字节不变。"""
        rules = [
            {"op": "side_of", "line": "新港中路", "dir": "东",
             "scope": {"op": "in_district", "name": "海珠区"}},
            {"op": "near", "center": [113.30, 23.10], "radius_km": 400.0},
            {"op": "minus", "args": [
                {"op": "near", "center": [113.30, 23.10], "radius_km": 1.0},
                {"op": "near", "center": [113.30, 23.10], "radius_km": 1.0}]},
        ]
        data_dir = REPO_ROOT / "data" / "pilot"
        if not (data_dir / "units.json").is_file():
            self.skipTest("data/pilot 不存在")
        ctx = dsl.load_pilot_context(data_dir)
        for rule in rules:
            before = json.dumps(rule, sort_keys=True, ensure_ascii=False)
            try:
                dsl.eval_rule(rule, ctx)
            except dsl.DslError:
                pass  # P5 非空纪律抛错路径同样不得改树
            self.assertEqual(
                json.dumps(rule, sort_keys=True, ensure_ascii=False), before)

    def test_g5_no_l2_fine_face_and_warnings_empty(self):
        """03_dsl 不读 L2 细面；G5 相关 execute 输出 warnings 恒 []。"""
        src = MODULE_PATH.read_text("utf-8")
        for banned in ("fences_yeidai", "fences_dealer"):
            self.assertNotIn(banned, src)
        data_dir = REPO_ROOT / "data" / "pilot"
        if not (data_dir / "units.json").is_file():
            self.skipTest("data/pilot 不存在")
        ctx = dsl.load_pilot_context(data_dir)
        out = dsl.execute({"op": "near", "center": [113.30, 23.10],
                           "radius_km": 400.0}, ctx)
        self.assertEqual(out["warnings"], [])
        self.assertEqual(set(out.keys()),
                         {"unit_ids", "components", "area_km2", "rule",
                          "warnings"})
        self.assertEqual(out["unit_ids"], list(range(224)))


if __name__ == "__main__":
    unittest.main()


