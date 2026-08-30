# -*- coding: utf-8 -*-
"""T-201/T-202 单元测试：P2 输入层 + 邻接图与 G2-a 自洽。

全部用临时目录 + 最小合成夹具：不访问真实业务数据、无网络。
被测模块文件名以数字开头，无法常规 import，故用 importlib 按路径加载。

覆盖：
- T-201：正向验收 / 反向错误路径 / MultiPolygon / key→uid 冻结映射；
- T-202：共享边界米数（精确 50m / 49.999m / 点接触 / 相离 / 面积重叠 /
  Polygon-MultiPolygon / GeometryCollection）、邻接图结构不变量、
  G2-a 重叠率、孤立单元、unit_graph.json 原子写出的确定性；
- CLI：--data 必须显式传入；T-202 语义下写 unit_graph.json；
  重叠率超限 / 孤立单元的退出码与中文 / ESCALATION 输出。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import shapely.wkt
from shapely.geometry import Point

# ---------------------------------------------------------------------------
# 按路径加载被测模块
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../sraf
MODULE_PATH = REPO_ROOT / "sraf-pilot" / "src" / "02_units.py"

_spec = importlib.util.spec_from_file_location("units_02", MODULE_PATH)
units_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(units_mod)

# ---------------------------------------------------------------------------
# 最小合成夹具
# ---------------------------------------------------------------------------

VALID_WKT = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.1, 113.0 23.0))"
# 双部件 MultiPolygon：若代码直接读 .exterior 会 AttributeError，测试即失败。
VALID_MULTIPOLYGON_WKT = (
    "MULTIPOLYGON (((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.1, 113.0 23.0)),"
    " ((113.2 23.0, 113.3 23.0, 113.3 23.1, 113.2 23.1, 113.2 23.0)))"
)


def _ring(x0: float, y0: float, x1: float, y1: float) -> str:
    """构造一个闭合矩形的 ``((ring))`` 片段（单个 polygon 的环）。"""
    return f"(({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"


def _poly(x0: float, y0: float, x1: float, y1: float) -> str:
    """构造矩形 Polygon WKT（米级长度：经度差 0.01° 在北纬 23° 约 1.02 km）。"""
    return "POLYGON " + _ring(x0, y0, x1, y1)


def _mpoly(*polys: str) -> str:
    """把若干 ``((ring))`` 片段拼成 MultiPolygon WKT（代码不得触碰 .exterior）。"""
    return "MULTIPOLYGON (" + ", ".join(polys) + ")"


def make_unit(uid: int = 0, key: str | None = None, geom: str = VALID_WKT) -> dict:
    """构造一行符合卡载 schema 的单元。"""
    return {
        "uid": uid,
        "key": key if key is not None else f"U-{uid:04d}",
        "district_code": "440105",
        "street": "某街道",
        "area_km2": 1.0,
        "centroid": [113.05, 23.05],
        "geom": geom,
    }


def write_json(path: Path, payload) -> None:
    """以 UTF-8 写 JSON（测试夹具专用）。"""
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


# T-202 夹具：竖直共享边 x=113.1，纬度 23° 附近 0.1° 纬向 ≈ 11058 m。
SQ_LEFT = _poly(113.0, 23.0, 113.1, 23.1)      # A：左方块
SQ_RIGHT = _poly(113.1, 23.0, 113.2, 23.1)    # B：右方块（与 A 共享整条边 ≈ 11058 m）
SQ_FAR = _poly(113.5, 23.5, 113.6, 23.6)      # C：远处的方块（与 A/B 相离）
SQ_UPPER = _poly(113.1, 23.1, 113.2, 23.2)    # D：右上（与 A 仅点接触，与 B 共享边）
# E：MultiPolygon 双部件，两部件各与 A 共享半条竖边 ≈ 5529 m > 50 m。
MPOLY_HALVES = _mpoly(_ring(113.1, 23.0, 113.2, 23.05), _ring(113.1, 23.05, 113.2, 23.1))
# F：GeometryCollection 夹具 —— 宽左块（0.2°）与之相交时边界交为
# LineString（顶边一段）+ Point（三角形右下顶点斜触），且无面积重叠，
# 证明递归收集只累加线性部分、Point 贡献为 0。
GC_SHARED_LINE = _mpoly(_ring(113.1, 23.1, 113.2, 23.2), "((113.05 23.1, 113.1 23.15, 113.0 23.15, 113.05 23.1))")


def make_fence(src_id: str = "PZ-0001", name: str = "测试围栏", geom: str = VALID_WKT) -> dict:
    """构造一行符合卡载 schema 的围栏（经销商 / 业代通用）。"""
    return {
        "name": name,
        "src_id": src_id,
        "area_km2": 1.0,
        "center": [113.05, 23.05],
        "overlap_ratio": 0.999,
        "geom": geom,
    }


def build_valid_dir(root: Path) -> Path:
    """生成一套三文件齐全的最小合法 P1 产物目录（每次调用全新生成）。

    T-202 起单元几何为三个并排不相重的方块（0-1 共享边、2 相离），
    使 G2-a 重叠率为 0、无孤立单元，CLI 主流程可走通。
    """
    d = root / "pilot"
    d.mkdir(parents=True, exist_ok=True)
    write_json(d / units_mod.UNITS_FILENAME, {
        "crs": "GCJ-02",
        "units": [
            make_unit(0, geom=SQ_LEFT),
            make_unit(1, geom=SQ_RIGHT),
            make_unit(2, geom=SQ_FAR),
        ],
    })
    write_json(d / units_mod.DEALER_FILENAME, {
        "fences": [make_fence("PZ-0001"), make_fence("PZ-0002", name="经销商乙")],
    })
    write_json(d / units_mod.YEIDAI_FILENAME, {
        "fences": [make_fence("YD-0001", name="测试业代")],
    })
    return d



def snapshot_dir(d: Path) -> dict[str, str]:
    """目录内容指纹：相对路径 -> 内容 sha256（用于只读断言）。"""
    out: dict[str, str] = {}
    for p in sorted(d.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(d))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# ---------------------------------------------------------------------------
# 正向：验收断言 + MultiPolygon + 纯函数 + 只读
# ---------------------------------------------------------------------------


class TestHappyPath(unittest.TestCase):
    """正向验收：任务卡逐条可执行断言。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_card_acceptance_assertions(self):
        """任务卡 T-201 的全部正向断言（逐条对应）。"""
        d = build_valid_dir(self.root)
        units_payload = json.loads((d / units_mod.UNITS_FILENAME).read_text("utf-8"))
        dealer_payload = json.loads((d / units_mod.DEALER_FILENAME).read_text("utf-8"))
        yeidai_payload = json.loads((d / units_mod.YEIDAI_FILENAME).read_text("utf-8"))
        units = units_payload["units"]
        dealer_fences = dealer_payload["fences"]
        yeidai_fences = yeidai_payload["fences"]
        key_to_uid = units_mod.build_key_uid_map(units)
        unit_geoms = [
            units_mod.parse_payload_wkt(u["geom"], d / units_mod.UNITS_FILENAME, f"[{u['uid']}]")
            for u in units
        ]

        self.assertEqual(units_payload["crs"], "GCJ-02")
        self.assertEqual([u["uid"] for u in units], list(range(len(units))))
        self.assertEqual(len({u["key"] for u in units}), len(units))
        self.assertEqual(key_to_uid, {u["key"]: u["uid"] for u in units})
        self.assertEqual(len(key_to_uid), len(units))
        self.assertTrue(all(g.geom_type in {"Polygon", "MultiPolygon"} for g in unit_geoms))
        self.assertTrue(all(not g.is_empty for g in unit_geoms))
        self.assertEqual(len({f["src_id"] for f in dealer_fences}), len(dealer_fences))
        self.assertEqual(len({f["src_id"] for f in yeidai_fences}), len(yeidai_fences))
        self.assertTrue(
            {f["src_id"] for f in dealer_fences}.isdisjoint(f["src_id"] for f in yeidai_fences)
        )

    def test_load_pilot_inputs_end_to_end(self):
        """汇总入口：一次加载全部输入，各产物与几何齐备，映射逐字正确。"""
        d = build_valid_dir(self.root)
        inputs = units_mod.load_pilot_inputs(d)
        self.assertEqual(len(inputs["units"]), 3)
        self.assertEqual(len(inputs["unit_geoms"]), 3)
        self.assertEqual(len(inputs["dealer_fences"]), 2)
        self.assertEqual(len(inputs["dealer_geoms"]), 2)
        self.assertEqual(len(inputs["yeidai_fences"]), 1)
        self.assertEqual(len(inputs["yeidai_geoms"]), 1)
        self.assertEqual(inputs["key_to_uid"], {"U-0000": 0, "U-0001": 1, "U-0002": 2})
        self.assertTrue(all(not g.is_empty for g in inputs["unit_geoms"]))
        self.assertTrue(all(not g.is_empty for g in inputs["dealer_geoms"]))
        self.assertTrue(all(not g.is_empty for g in inputs["yeidai_geoms"]))

    def test_multipolygon_accepted_without_exterior(self):
        """合成 MultiPolygon：单元与围栏均可加载；代码触碰 .exterior 即会崩溃。"""
        d = self.root / "pilot-m"
        d.mkdir()
        write_json(d / units_mod.UNITS_FILENAME, {
            "crs": "GCJ-02",
            "units": [make_unit(0, geom=VALID_MULTIPOLYGON_WKT)],
        })
        write_json(d / units_mod.DEALER_FILENAME, {
            "fences": [make_fence("PZ-0001", geom=VALID_MULTIPOLYGON_WKT)],
        })
        write_json(d / units_mod.YEIDAI_FILENAME, {
            "fences": [make_fence("YD-0001", name="业代甲", geom=VALID_MULTIPOLYGON_WKT)],
        })
        inputs = units_mod.load_pilot_inputs(d)
        self.assertEqual(inputs["unit_geoms"][0].geom_type, "MultiPolygon")
        self.assertEqual(inputs["dealer_geoms"][0].geom_type, "MultiPolygon")
        self.assertEqual(inputs["yeidai_geoms"][0].geom_type, "MultiPolygon")

    def test_build_key_uid_map_is_literal_comprehension(self):
        """映射定义逐字等于字典推导式；不对输入顺序做任何假设或重排。"""
        units = [make_unit(0, key="K-b"), make_unit(1, key="K-a"), make_unit(2, key="K-c")]
        self.assertEqual(
            units_mod.build_key_uid_map(units),
            {unit["key"]: unit["uid"] for unit in units},
        )
        self.assertEqual(units_mod.build_key_uid_map(units), {"K-b": 0, "K-a": 1, "K-c": 2})

    def test_load_is_readonly(self):
        """只读保证：加载前后目录内容指纹逐字节一致，不产生任何文件。"""
        d = build_valid_dir(self.root)
        before = snapshot_dir(d)
        units_mod.load_pilot_inputs(d)
        self.assertEqual(snapshot_dir(d), before)


# ---------------------------------------------------------------------------
# 反向：每条失败路径都抛含路径与中文原因的 PilotInputError
# ---------------------------------------------------------------------------


class TestErrorPaths(unittest.TestCase):
    """反向验收：逐条破坏夹具，断言异常含文件路径与中文原因。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def expect_fail(self, d: Path, needle_path: Path, needle_msg: str):
        """统一断言：抛 PilotInputError，消息含目标文件路径与中文原因。"""
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.load_pilot_inputs(d)
        msg = str(ctx.exception)
        self.assertIn(str(needle_path), msg, f"异常应含文件路径：{msg}")
        self.assertIn(needle_msg, msg, f"异常应含中文原因「{needle_msg}」：{msg}")

    def mutate_units(self, d: Path, mutator) -> Path:
        """重写 units.json（整体替换 payload 后按 mutator 变形）。"""
        path = d / units_mod.UNITS_FILENAME
        payload = json.loads(path.read_text("utf-8"))
        mutator(payload)
        write_json(path, payload)
        return path

    def mutate_fences(self, d: Path, filename: str, mutator) -> Path:
        path = d / filename
        payload = json.loads(path.read_text("utf-8"))
        mutator(payload)
        write_json(path, payload)
        return path

    # -- 文件缺失 -----------------------------------------------------------

    def test_missing_each_input_file(self):
        for filename in (
            units_mod.UNITS_FILENAME,
            units_mod.DEALER_FILENAME,
            units_mod.YEIDAI_FILENAME,
        ):
            with self.subTest(filename=filename):
                d = build_valid_dir(self.root)
                path = d / filename
                path.unlink()
                self.expect_fail(d, path, "输入文件缺失")

    def test_missing_data_dir(self):
        d = build_valid_dir(self.root)
        ghost = self.root / "no-such-dir"
        self.expect_fail(ghost, ghost, "数据目录不存在")

    # -- 顶层结构 -----------------------------------------------------------

    def test_units_json_top_level_not_object(self):
        d = build_valid_dir(self.root)
        path = d / units_mod.UNITS_FILENAME
        write_json(path, [{"crs": "GCJ-02", "units": []}])
        self.expect_fail(d, path, "顶层必须是对象")

    def test_units_json_top_key_missing(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p.pop("crs"))
        self.expect_fail(d, path, "顶层键集合不符")

    def test_units_json_top_key_extra(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p.update({"extra": 1}))
        self.expect_fail(d, path, "顶层键集合不符")

    def test_fences_json_top_key_missing(self):
        d = build_valid_dir(self.root)
        path = self.mutate_fences(d, units_mod.DEALER_FILENAME, lambda p: p.pop("fences"))
        self.expect_fail(d, path, "顶层键集合不符")

    # -- 行字段集合 ---------------------------------------------------------

    def test_unit_field_set_mismatch(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][0].pop("street"))
        self.expect_fail(d, path, "字段集合不符")

    def test_fence_field_set_mismatch(self):
        d = build_valid_dir(self.root)
        path = self.mutate_fences(
            d, units_mod.YEIDAI_FILENAME, lambda p: p["fences"][0].pop("center")
        )
        self.expect_fail(d, path, "字段集合不符")

    # -- uid 契约 -----------------------------------------------------------

    def test_uid_not_integer(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][0].update({"uid": "0"}))
        self.expect_fail(d, path, "uid 必须是整数")

    def test_uid_bool_rejected(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][0].update({"uid": True}))
        self.expect_fail(d, path, "uid 必须是整数")

    def test_uid_not_contiguous(self):
        """uid 0..N-1 出现断档（0, 2）→ 不等于下标，禁止静默补号。"""
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][1].update({"uid": 2}))
        self.expect_fail(d, path, "不等于数组下标")

    def test_uid_not_equal_to_index(self):
        """uid 集合连续但与下标错位（1, 2, 3）→ 同样违反冻结契约。"""
        d = build_valid_dir(self.root)
        path = self.mutate_units(
            d, lambda p: p["units"].__setitem__(0, {**p["units"][0], "uid": 1})
        )
        self.expect_fail(d, path, "不等于数组下标")

    # -- key 契约 -----------------------------------------------------------

    def test_key_empty_string(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][0].update({"key": ""}))
        self.expect_fail(d, path, "key 必须是非空字符串")

    def test_key_duplicate(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][1].update({"key": "U-0000"}))
        self.expect_fail(d, path, "key 重复")

    # -- WKT 与几何 ---------------------------------------------------------

    def test_wkt_malformed(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][0].update({"geom": "POLYGON(("}))
        self.expect_fail(d, path, "WKT 解析失败")

    def test_wkt_empty_string(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][0].update({"geom": "  "}))
        self.expect_fail(d, path, "必须是非空 WKT 字符串")

    def test_wkt_empty_geometry(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][0].update({"geom": "POLYGON EMPTY"}))
        self.expect_fail(d, path, "空几何")

    def test_geometry_type_point_rejected(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(d, lambda p: p["units"][0].update({"geom": "POINT (113.0 23.0)"}))
        self.expect_fail(d, path, "类型是 Point")

    def test_geometry_type_linestring_rejected(self):
        d = build_valid_dir(self.root)
        path = self.mutate_units(
            d, lambda p: p["units"][0].update({"geom": "LINESTRING (113.0 23.0, 113.1 23.1)"})
        )
        self.expect_fail(d, path, "类型是 LineString")

    # -- src_id 唯一性与跨文件冲突 -----------------------------------------

    def test_dealer_src_id_duplicate_within_file(self):
        d = build_valid_dir(self.root)
        path = self.mutate_fences(
            d, units_mod.DEALER_FILENAME, lambda p: p["fences"][1].update({"src_id": "PZ-0001"})
        )
        self.expect_fail(d, path, "src_id 重复")

    def test_yeidai_src_id_duplicate_within_file(self):
        d = build_valid_dir(self.root)
        path = self.mutate_fences(
            d, units_mod.YEIDAI_FILENAME,
            lambda p: p["fences"].append(make_fence("YD-0001", name="业代乙")),
        )
        self.expect_fail(d, path, "src_id 重复")

    def test_src_id_conflict_across_files(self):
        """经销商与业代 src_id 跨文件冲突：异常须含双方文件路径。"""
        d = build_valid_dir(self.root)
        dealer_path = d / units_mod.DEALER_FILENAME
        yeidai_path = d / units_mod.YEIDAI_FILENAME
        self.mutate_fences(
            d, units_mod.YEIDAI_FILENAME, lambda p: p["fences"][0].update({"src_id": "PZ-0001"})
        )
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.load_pilot_inputs(d)
        msg = str(ctx.exception)
        self.assertIn(str(yeidai_path), msg, f"异常应含业代围栏路径：{msg}")
        self.assertIn(str(dealer_path), msg, f"异常应含经销商围栏路径：{msg}")
        self.assertIn("跨文件 src_id 冲突", msg)




# ---------------------------------------------------------------------------
# T-202：共享边界米数（冻结算法）+ 邻接图不变量 + G2-a + 原子写出
# ---------------------------------------------------------------------------


def _wkt(geom_text: str):
    """测试内解析 WKT（不依赖被测模块的解析入口，独立校验纯函数）。"""
    import shapely.wkt

    return shapely.wkt.loads(geom_text)



class TestSharedBoundaryAndGraph(unittest.TestCase):
    """任务卡 T-202 可执行验收断言（夹具逐条对应）。"""

    def test_shared_boundary_exact_50m(self):
        """共享边界恰好 50 米：>= 50 成立（边界值属邻接）。"""
        # A 东边上端 50m 竖段与 B 西边重合：B 西边 x=113.1、
        # 纬度从 23.1-dlat 到 23.1，dlat 由 haversine 反推 50m。
        dlat = math.degrees(50.0 / 6_371_000.0)
        left = _wkt(SQ_LEFT)
        right = _wkt(_poly(113.1, 23.1 - dlat, 113.15, 23.1))
        length = units_mod.shared_boundary_m(left, right)
        self.assertGreaterEqual(length, 50.0)
        self.assertTrue(units_mod.are_adjacent(left, right))

    def test_shared_boundary_just_below_50m(self):
        """共享边界 49.999 米：< 50，不得邻接。"""
        dlat = math.degrees(49.999 / 6_371_000.0)
        left = _wkt(SQ_LEFT)
        right = _wkt(_poly(113.1, 23.1 - dlat, 113.15, 23.1))
        length = units_mod.shared_boundary_m(left, right)
        self.assertLess(length, 50.0)
        self.assertFalse(units_mod.are_adjacent(left, right))

    def test_point_touch_is_not_adjacent(self):
        """仅点接触（对角）：共享边界无线性部分，不得邻接。"""
        a = _wkt(SQ_LEFT)
        b = _wkt(SQ_UPPER)
        self.assertEqual(a.boundary.intersection(b.boundary).geom_type, "Point")
        self.assertEqual(units_mod.shared_boundary_m(a, b), 0.0)
        self.assertFalse(units_mod.are_adjacent(a, b))

    def test_disjoint_is_not_adjacent(self):
        """相离：无共享边界，不得邻接。"""
        a = _wkt(SQ_LEFT)
        c = _wkt(SQ_FAR)
        self.assertEqual(units_mod.shared_boundary_m(a, c), 0.0)
        self.assertFalse(units_mod.are_adjacent(a, c))

    def test_area_overlap_is_not_adjacency(self):
        """只有面积重叠（破损几何）：边界交再长也不是邻接。"""
        a = _wkt(SQ_LEFT)
        b = _wkt("POLYGON ((113.05 23.0, 113.2 23.0, 113.2 23.1, 113.05 23.1, 113.05 23.0))")
        self.assertGreater(a.intersection(b).area, 0.0)
        self.assertFalse(units_mod.are_adjacent(a, b))

    def test_polygon_multipolygon_shared_full_edge(self):
        """Polygon-MultiPolygon：两部件拼成的整条共享边 > 50m → 邻接。"""
        a = _wkt(SQ_LEFT)
        mp = _wkt(MPOLY_HALVES)
        self.assertEqual(mp.geom_type, "MultiPolygon")
        length = units_mod.shared_boundary_m(a, mp)
        self.assertGreater(length, 50.0)
        self.assertTrue(units_mod.are_adjacent(a, mp))

    def test_geometry_collection_linear_parts_only(self):
        """GeometryCollection：只累加线性部分，Point 贡献为 0。"""
        # 宽左块（0.2°）与 GC 共享顶边一段线 + 上下两个交点
        wide = _wkt(_poly(113.0, 23.0, 113.2, 23.1))
        gc = _wkt(GC_SHARED_LINE)
        crossing = wide.boundary.intersection(gc.boundary)
        self.assertEqual(crossing.geom_type, "GeometryCollection")
        parts = [g.geom_type for g in crossing.geoms]
        self.assertEqual(parts.count("LineString"), 1)
        self.assertEqual(parts.count("Point"), 1)
        length = units_mod.shared_boundary_m(wide, gc)
        # 共享线段是 0.1° 纬向 ≈ 10.2 km（数量级断言）；点不贡献长度
        self.assertGreater(length, 10_000.0)
        self.assertLess(length, 11_000.0)
        self.assertTrue(units_mod.are_adjacent(wide, gc))

    def test_adjacency_graph_invariants(self):
        """建图不变量：全 uid 键 / 无自环 / 对称 / 升序唯一 / 孤立含空数组。"""
        geoms = [_wkt(SQ_LEFT), _wkt(SQ_RIGHT), _wkt(SQ_FAR)]
        graph = units_mod.build_adjacency(geoms)
        parsed = {int(u): v for u, v in graph.items()}
        self.assertEqual(set(parsed), {0, 1, 2})
        self.assertTrue(all(u not in nbrs for u, nbrs in parsed.items()))
        self.assertTrue(all(nbrs == sorted(set(nbrs)) for nbrs in parsed.values()))
        self.assertTrue(all(u in parsed[v] for u, nbrs in parsed.items() for v in nbrs))
        self.assertEqual(parsed[0], [1])
        self.assertEqual(parsed[1], [0])
        self.assertEqual(parsed[2], [])

    def test_pair_overlap_ratio_zero_and_gate(self):
        """G2-a：不相重夹具重叠率为 0；全重夹具为 1（超限）。"""
        geoms = [_wkt(SQ_LEFT), _wkt(SQ_RIGHT), _wkt(SQ_FAR)]
        self.assertEqual(units_mod.pair_overlap_ratio(geoms), 0.0)
        same = [_wkt(SQ_LEFT)] * 3
        self.assertEqual(units_mod.pair_overlap_ratio(same), 1.0)

    def test_isolated_detection(self):
        """孤立单元检测：SQ_FAR 为孤立，其余非孤立。"""
        geoms = [_wkt(SQ_LEFT), _wkt(SQ_RIGHT), _wkt(SQ_FAR)]
        adjacency = units_mod.build_adjacency(geoms)
        isolated = [u for u, nbrs in adjacency.items() if not nbrs]
        self.assertEqual(isolated, ["2"])

    def test_write_unit_graph_atomic_and_deterministic(self):
        """写出：schema 精确 / 键按 uid 升序 / 双跑字节一致 / 无残留临时文件。"""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            geoms = [_wkt(SQ_LEFT), _wkt(SQ_RIGHT), _wkt(SQ_UPPER)]
            adjacency = units_mod.build_adjacency(geoms)
            units_mod.write_unit_graph(d, adjacency)
            first = (d / units_mod.UNIT_GRAPH_FILENAME).read_bytes()
            graph = json.loads(first.decode("utf-8"))
            self.assertEqual(graph["link_min_m"], 50)
            self.assertEqual(set(graph), {"adjacency", "link_min_m"})
            self.assertEqual(list(graph["adjacency"]), ["0", "1", "2"])
            self.assertEqual(graph["adjacency"]["0"], [1])
            self.assertEqual(graph["adjacency"]["1"], [0, 2])
            self.assertEqual(graph["adjacency"]["2"], [1])
            # 双跑字节一致
            units_mod.write_unit_graph(d, adjacency)
            self.assertEqual((d / units_mod.UNIT_GRAPH_FILENAME).read_bytes(), first)
            # 原子替换：目录内无临时文件残留
            self.assertEqual([p.name for p in d.iterdir()], [units_mod.UNIT_GRAPH_FILENAME])



# ---------------------------------------------------------------------------
# T-203：oracle 单元集与 v1.4 冻结指标（可手算几何 + 精确断言）
# ---------------------------------------------------------------------------
#
# 全部夹具使用 0..N 小坐标（double 精确表示，面积/比例可手算到浮点精确）：
#
#   四方块布局（单元 1×1，uid 如下）：
#
#     y=2  ┌────┬────┐
#          │ 2  │ 3  │
#     y=1  ├────┼────┤
#          │ 0  │ 1  │
#     y=0  └────┴────┘
#         x=0  x=1  x=2
#
#   质心 = 各方块中心 (0.5,0.5)/(1.5,0.5)/(0.5,1.5)/(1.5,1.5)。
#   骑跨专用单元 (0,0)-(10,1)：宽 10 高 1，比例 2/10=0.2、8/10=0.8 均 double 精确。


def build_oracle_dir(root: Path) -> Path:
    """T-203 主夹具：四方块单元 + 可手算围栏（每次全新生成，返回目录）。

    默认围栏：经销商 PZ-0001 = F(0,0,1.5,1.5)（手算见 test_hand_computed_metrics）、
    业代 YD-0001 = F(1,0,2,1)（下右整块，iou=recall=precision=1）。
    """
    d = root / "pilot-oracle"
    d.mkdir(parents=True, exist_ok=True)
    geoms = [
        _poly(0, 0, 1, 1),  # 0 下左
        _poly(1, 0, 2, 1),  # 1 下右
        _poly(0, 1, 1, 2),  # 2 上左
        _poly(1, 1, 2, 2),  # 3 上右
    ]
    centroids = [[0.5, 0.5], [1.5, 0.5], [0.5, 1.5], [1.5, 1.5]]
    units = []
    for uid in range(4):
        u = make_unit(uid, geom=geoms[uid])
        u["centroid"] = centroids[uid]
        units.append(u)
    write_json(d / units_mod.UNITS_FILENAME, {"crs": "GCJ-02", "units": units})
    write_json(d / units_mod.DEALER_FILENAME, {
        "fences": [make_fence("PZ-0001", geom=_poly(0, 0, 1.5, 1.5))],
    })
    write_json(d / units_mod.YEIDAI_FILENAME, {
        "fences": [make_fence("YD-0001", name="业代甲", geom=_poly(1, 0, 2, 1))],
    })
    return d


def write_unit_graph_fixture(d: Path, adjacency: dict[int, list[int]]) -> None:
    """按 T-202 产物 schema 写 unit_graph.json（测试夹具专用）。"""
    write_json(d / units_mod.UNIT_GRAPH_FILENAME, {
        "adjacency": {str(u): sorted(nbrs) for u, nbrs in adjacency.items()},
        "link_min_m": 50,
    })


FULL_ADJ = {0: [1, 2], 1: [0, 3], 2: [0, 3], 3: [1, 2]}  # 四方块全边邻接 → 连通


class TestOracleMetrics(unittest.TestCase):
    """冻结公式逐条验证：手算精确值 + 闭区间边界 + MultiPolygon + components。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def _oracle_inputs(self, d: Path):
        inputs = units_mod.load_pilot_inputs(d)
        graph = units_mod.load_unit_graph(d, 4)
        return inputs, graph

    def test_hand_computed_metrics_and_boundary_centroids(self):
        """主手算夹具：F=PZ-0001=(0,0)-(1.5,1.5)，全部指标精确断言。

        - 质心 (0.5,0.5)/(1.5,0.5)/(0.5,1.5)/(1.5,1.5) 全部 covers
          （uid1/uid2/uid3 质心恰在 F 的右/上边界 → 含入）→ U = {0,1,2,3}。
        - U = 完整 2×2 方块 area=4；F area=2.25；F ⊂ U → inter = 2.25。
        - iou = 2.25 / 4 = 0.5625（浮点精确）。
        - recall = 2.25 / 2.25 = 1.0；precision = 2.25 / 4 = 0.5625。
        - 骑跨：uid0=1.0✗ uid1=0.5✓ uid2=0.5✓ uid3=0.25✓ → straddle=3。
        - 边界质心：uid1/uid2/uid3 三个恰在 F.boundary 上 → 3。
        - components：{0,1,2,3} 在 FULL_ADJ 下连通 → 1。
        """
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)
        inputs, graph = self._oracle_inputs(d)
        fence = inputs["dealer_geoms"][0]
        result = units_mod.compute_fence_oracle(
            fence, inputs["units"], inputs["unit_geoms"], graph
        )
        self.assertEqual(result["unit_ids"], [0, 1, 2, 3])
        self.assertTrue(math.isclose(result["iou"], 0.5625))
        self.assertTrue(math.isclose(result["recall"], 1.0))
        self.assertTrue(math.isclose(result["precision"], 0.5625))
        self.assertEqual(result["straddle"], 3)
        self.assertEqual(result["components"], 1)
        self.assertEqual(result["boundary_centroids"], 3)
        # 同一围栏经 build_oracle_unitsets 后 boundary_centroids 汇总正确
        payload = units_mod.build_oracle_unitsets(d, inputs, graph)
        # PZ-0001 贡献 3；YD-0001=(1,0)-(2,1) 质心全在内 → 0
        self.assertEqual(payload["boundary_centroids"], 3)

    def test_inclusive_fence_yields_perfect_metrics(self):
        """YD-0001 = 下右整块：单质心选中，iou=recall=precision=1。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)
        inputs, graph = self._oracle_inputs(d)
        result = units_mod.compute_fence_oracle(
            inputs["yeidai_geoms"][0], inputs["units"], inputs["unit_geoms"], graph
        )
        self.assertEqual(result["unit_ids"], [1])
        self.assertTrue(math.isclose(result["iou"], 1.0))
        self.assertTrue(math.isclose(result["recall"], 1.0))
        self.assertTrue(math.isclose(result["precision"], 1.0))
        self.assertEqual(result["straddle"], 0)
        self.assertEqual(result["components"], 1)

    def test_multipolygon_fence_two_components(self):
        """MultiPolygon 对角围栏：U={0,3} 互不邻接 → components=2，指标全 1。"""
        d = build_oracle_dir(self.root)
        # 拆开 0-3（FULL_ADJ 中 0-3 本就不相邻；换 DISJOINT_ADJ 更直接）
        adj = {0: [1, 2], 1: [0, 3], 2: [0, 3], 3: [1, 2]}
        adj = {u: [v for v in nbrs] for u, nbrs in adj.items()}
        write_unit_graph_fixture(d, adj)
        inputs, graph = self._oracle_inputs(d)
        fence = _wkt(
            "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 1, 0 0)), ((1 1, 2 1, 2 2, 1 2, 1 1)))"
        )
        result = units_mod.compute_fence_oracle(
            fence, inputs["units"], inputs["unit_geoms"], graph
        )
        self.assertEqual(result["unit_ids"], [0, 3])
        self.assertTrue(math.isclose(result["iou"], 1.0))
        self.assertTrue(math.isclose(result["recall"], 1.0))
        self.assertTrue(math.isclose(result["precision"], 1.0))
        self.assertEqual(result["components"], 2)

    def test_components_two_via_sparse_adjacency(self):
        """同 U={0,1} 但邻接拆掉 0-1 边 → components=2（证明分量只由图决定）。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, {0: [2], 2: [0], 1: [], 3: []})
        inputs, graph = self._oracle_inputs(d)
        fence = _wkt(_poly(0, 0, 2, 1))  # 下半整条：质心 (0.5,0.5)/(1.5,0.5) covered
        result = units_mod.compute_fence_oracle(
            fence, inputs["units"], inputs["unit_geoms"], graph
        )
        self.assertEqual(result["unit_ids"], [0, 1])
        self.assertEqual(result["components"], 2)

    def test_straddle_closed_interval_exact_boundaries(self):
        """骑跨闭区间：恰为 0.2 / 0.8 计入；刚低 0.2 / 刚高 0.8 不计（全 double 精确）。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)
        inputs, graph = self._oracle_inputs(d)
        wide_unit = {
            **make_unit(4, geom=_poly(0, 0, 10, 1)),
            "centroid": [5.0, 0.5],
        }
        units = inputs["units"] + [wide_unit]
        wide_geoms = inputs["unit_geoms"] + [_wkt(_poly(0, 0, 10, 1))]

        def straddle_of(fence_wkt: str) -> int:
            return units_mod.compute_fence_oracle(
                _wkt(fence_wkt), units, wide_geoms, graph
            )["straddle"]

        self.assertEqual(straddle_of(_poly(4, 0, 6, 1)), 1)       # 2/10 = 0.2 恰好
        self.assertEqual(straddle_of(_poly(4.0001, 0, 6, 1)), 0)  # 0.19999 < 0.2
        self.assertEqual(straddle_of(_poly(1, 0, 9, 1)), 1)       # 8/10 = 0.8 恰好
        self.assertEqual(straddle_of(_poly(0.9999, 0, 9, 1)), 0)  # 0.80001 > 0.8

    def test_straddle_counts_multiple_units(self):
        """多骑跨单元：F=(4,0)-(6,2) 盖两块 10×1 条各 0.2 → straddle=2。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)
        inputs, graph = self._oracle_inputs(d)
        units = inputs["units"] + [
            {**make_unit(4, geom=_poly(0, 0, 10, 1)), "centroid": [5.0, 0.5]},
            {**make_unit(5, geom=_poly(0, 1, 10, 2)), "centroid": [5.0, 1.5]},
        ]
        geoms = inputs["unit_geoms"] + [_wkt(_poly(0, 0, 10, 1)), _wkt(_poly(0, 1, 10, 2))]
        result = units_mod.compute_fence_oracle(
            _wkt(_poly(4, 0, 6, 2)), units, geoms, graph
        )
        self.assertEqual(result["straddle"], 2)

    def test_empty_selection_raises_without_output(self):
        """围栏不覆盖任何质心：中文报错（含产物文件名），不产生半成品。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)
        inputs, graph = self._oracle_inputs(d)
        fence = _wkt(SQ_FAR)
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.compute_fence_oracle(
                fence, inputs["units"], inputs["unit_geoms"], graph
            )
        msg = str(ctx.exception)
        self.assertIn(units_mod.ORACLE_FILENAME, msg)
        self.assertIn("选中单元集为空", msg)
        self.assertFalse((d / units_mod.ORACLE_FILENAME).exists())

    def test_zero_area_fence_raises(self):
        """零面积围栏：冻结公式无法产生有限指标，中文报错。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)
        inputs, graph = self._oracle_inputs(d)
        degenerate = _wkt("POLYGON ((0 0, 1 1, 1 1, 0 0))")
        self.assertEqual(degenerate.area, 0.0)
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.compute_fence_oracle(
                degenerate, inputs["units"], inputs["unit_geoms"], graph
            )
        self.assertIn("围栏面积为零", str(ctx.exception))

    def test_zero_area_selected_unit_raises(self):
        """零面积选中单元：指标分母相关项失效，中文报错。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)
        inputs, graph = self._oracle_inputs(d)
        fence = _wkt(_poly(0, 0, 1.5, 1.5))
        geoms = list(inputs["unit_geoms"])
        geoms[0] = _wkt("POLYGON ((0 0, 1 1, 1 1, 0 0))")  # uid0 退化，质心仍在 F 内
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.compute_fence_oracle(fence, inputs["units"], geoms, graph)
        self.assertIn("零面积选中单元", str(ctx.exception))

    def test_boundary_centroid_point_covers_contract(self):
        """卡载断言：fence.covers(边界质心点) is True（contains 为 False）。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)
        inputs, graph = self._oracle_inputs(d)
        fence = inputs["dealer_geoms"][0]
        p = Point(1.5, 0.5)  # uid1 质心恰在 F 右边界
        assert fence.covers(p) is True
        assert not fence.contains(p)


class TestUnitGraphValidation(unittest.TestCase):
    """T-202 产物校验：无效 uid / 非对称 / 缺覆盖 / 自环 / link_min_m 均中文报错。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.d = build_oracle_dir(self.root)

    def test_valid_graph_passes(self):
        write_unit_graph_fixture(self.d, FULL_ADJ)
        graph = units_mod.load_unit_graph(self.d, 4)
        self.assertEqual(graph, {0: [1, 2], 1: [0, 3], 2: [0, 3], 3: [1, 2]})

    def test_invalid_neighbor_uid(self):
        write_unit_graph_fixture(self.d, {0: [1], 1: [0], 2: [], 3: [9]})
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.load_unit_graph(self.d, 4)
        self.assertIn("无效 uid", str(ctx.exception))

    def test_asymmetric_adjacency(self):
        write_unit_graph_fixture(self.d, {0: [1, 2], 1: [0], 2: [], 3: []})
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.load_unit_graph(self.d, 4)
        self.assertIn("不对称", str(ctx.exception))

    def test_missing_uid_coverage(self):
        payload = {
            "adjacency": {str(u): nbrs for u, nbrs in FULL_ADJ.items()},
            "link_min_m": 50,
        }
        payload["adjacency"].pop("3")
        write_json(self.d / units_mod.UNIT_GRAPH_FILENAME, payload)
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.load_unit_graph(self.d, 4)
        self.assertIn("缺少 uid", str(ctx.exception))

    def test_self_loop(self):
        adj = {u: list(nbrs) for u, nbrs in FULL_ADJ.items()}
        adj[0].append(0)
        write_unit_graph_fixture(self.d, adj)
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.load_unit_graph(self.d, 4)
        self.assertIn("自环", str(ctx.exception))

    def test_wrong_link_min_m(self):
        write_unit_graph_fixture(self.d, FULL_ADJ)
        payload = json.loads((self.d / units_mod.UNIT_GRAPH_FILENAME).read_text("utf-8"))
        payload["link_min_m"] = 100
        write_json(self.d / units_mod.UNIT_GRAPH_FILENAME, payload)
        with self.assertRaises(units_mod.PilotInputError) as ctx:
            units_mod.load_unit_graph(self.d, 4)
        self.assertIn("link_min_m", str(ctx.exception))


class TestOracleCli(unittest.TestCase):
    """CLI 全链：夹具 → 双产物；oracle schema 精确；失败路径不留半成品。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_cli_end_to_end_schema_and_determinism(self):
        """完整链路写出两产物；oracle schema 精确、手算指标、双跑字节一致。"""
        d = build_oracle_dir(self.root)
        write_unit_graph_fixture(d, FULL_ADJ)  # 预置图会被 CLI 重建覆盖（同几何同图）
        result1 = run_cli(d)
        self.assertEqual(result1.returncode, 0, result1.stderr)
        out_path = d / units_mod.ORACLE_FILENAME
        first = out_path.read_bytes()
        oracle = json.loads(first.decode("utf-8"))
        units = json.loads((d / units_mod.UNITS_FILENAME).read_text("utf-8"))["units"]
        dealer_fences = json.loads((d / units_mod.DEALER_FILENAME).read_text("utf-8"))["fences"]
        yeidai_fences = json.loads((d / units_mod.YEIDAI_FILENAME).read_text("utf-8"))["fences"]
        assert oracle["method"] == "3.6-v1.4"
        assert oracle["link_min_m"] == 50
        assert set(oracle) == {"method", "link_min_m", "boundary_centroids", "fences"}
        assert isinstance(oracle["boundary_centroids"], int)
        assert oracle["boundary_centroids"] >= 0
        assert len(oracle["fences"]) == len(dealer_fences) + len(yeidai_fences)
        assert set(oracle["fences"]) == {f["src_id"] for f in dealer_fences + yeidai_fences}
        assert all(
            set(v) == {"name", "layer", "unit_ids", "iou", "recall", "precision",
                       "straddle", "components"}
            for v in oracle["fences"].values()
        )
        assert all(v["unit_ids"] == sorted(set(v["unit_ids"])) for v in oracle["fences"].values())
        assert all(0 <= uid < len(units) for v in oracle["fences"].values() for uid in v["unit_ids"])
        assert all(v["layer"] in {"dealer", "yeidai"} for v in oracle["fences"].values())
        assert sum(v["layer"] == "dealer" for v in oracle["fences"].values()) == 1
        assert sum(v["layer"] == "yeidai" for v in oracle["fences"].values()) == 1
        assert all(
            math.isfinite(v[field]) and 0.0 <= v[field] <= 1.0
            for v in oracle["fences"].values()
            for field in ("iou", "recall", "precision")
        )
        assert all(isinstance(v["straddle"], int) and v["straddle"] >= 0
                   for v in oracle["fences"].values())
        assert all(isinstance(v["components"], int) and v["components"] >= 1
                   for v in oracle["fences"].values())
        assert list(oracle["fences"]) == sorted(oracle["fences"])  # src_id 确定性排序
        # 手算：PZ-0001 见主手算夹具；YD-0001 = 下右整块
        self.assertTrue(math.isclose(oracle["fences"]["PZ-0001"]["iou"], 0.5625))
        self.assertTrue(math.isclose(oracle["fences"]["YD-0001"]["iou"], 1.0))
        self.assertEqual(oracle["boundary_centroids"], 3)
        # 同输入两跑字节一致
        result2 = run_cli(d)
        self.assertEqual(result2.returncode, 0, result2.stderr)
        self.assertEqual(out_path.read_bytes(), first)

    def test_cli_no_half_written_output_on_oracle_failure(self):
        """oracle 阶段失败：退出码 5，目录内无 oracle_unitsets.json 半成品。"""
        d = build_oracle_dir(self.root)
        write_json(d / units_mod.DEALER_FILENAME, {
            "fences": [make_fence("PZ-0001", geom=SQ_FAR)],
        })
        write_json(d / units_mod.YEIDAI_FILENAME, {"fences": []})
        result = run_cli(d)
        self.assertEqual(result.returncode, 5)
        self.assertIn("oracle 阶段失败", result.stderr)
        self.assertFalse((d / units_mod.ORACLE_FILENAME).exists())

    def test_cli_src_id_conflict_fails_clean(self):
        """跨类型 src_id 冲突：校验层直接报错（退出码 2），无 oracle 产物。"""
        d = build_oracle_dir(self.root)
        write_json(d / units_mod.YEIDAI_FILENAME, {
            "fences": [make_fence("PZ-0001", name="业代撞名")],
        })
        result = run_cli(d)
        self.assertEqual(result.returncode, 2)
        self.assertIn("跨文件 src_id 冲突", result.stderr)
        self.assertFalse((d / units_mod.ORACLE_FILENAME).exists())


class TestRealDataOracle(unittest.TestCase):
    """真实数据验收（data/pilot 存在时执行；卡载 assert 逐条对应）。"""

    DATA_DIR = REPO_ROOT / "data" / "pilot"

    def setUp(self):
        if not self.DATA_DIR.is_dir():
            self.skipTest("data/pilot 不存在（业务数据不入 git）")

    def test_real_data_oracle_acceptance(self):
        oracle = json.loads(
            (self.DATA_DIR / units_mod.ORACLE_FILENAME).read_text("utf-8")
        )
        units = json.loads(
            (self.DATA_DIR / units_mod.UNITS_FILENAME).read_text("utf-8")
        )["units"]
        dealer_fences = json.loads(
            (self.DATA_DIR / units_mod.DEALER_FILENAME).read_text("utf-8")
        )["fences"]
        yeidai_fences = json.loads(
            (self.DATA_DIR / units_mod.YEIDAI_FILENAME).read_text("utf-8")
        )["fences"]
        assert oracle["method"] == "3.6-v1.4"
        assert oracle["link_min_m"] == 50
        assert set(oracle) == {"method", "link_min_m", "boundary_centroids", "fences"}
        assert isinstance(oracle["boundary_centroids"], int)
        assert oracle["boundary_centroids"] >= 0
        assert len(oracle["fences"]) == len(dealer_fences) + len(yeidai_fences)
        assert set(oracle["fences"]) == {f["src_id"] for f in dealer_fences + yeidai_fences}
        assert all(
            set(v) == {"name", "layer", "unit_ids", "iou", "recall", "precision",
                       "straddle", "components"}
            for v in oracle["fences"].values()
        )
        assert all(v["unit_ids"] == sorted(set(v["unit_ids"])) for v in oracle["fences"].values())
        assert all(0 <= uid < len(units) for v in oracle["fences"].values() for uid in v["unit_ids"])
        assert all(v["layer"] in {"dealer", "yeidai"} for v in oracle["fences"].values())
        assert sum(v["layer"] == "dealer" for v in oracle["fences"].values()) == 4
        assert sum(v["layer"] == "yeidai" for v in oracle["fences"].values()) == 17
        assert all(
            math.isfinite(v[field]) and 0.0 <= v[field] <= 1.0
            for v in oracle["fences"].values()
            for field in ("iou", "recall", "precision")
        )
        assert all(isinstance(v["straddle"], int) and v["straddle"] >= 0
                   for v in oracle["fences"].values())
        assert all(isinstance(v["components"], int) and v["components"] >= 1
                   for v in oracle["fences"].values())
        # G2-b 门禁只产数参照（门禁执行归 T-204）
        yeidai_values = [v["iou"] for v in oracle["fences"].values() if v["layer"] == "yeidai"]
        g2b_median = statistics.median(yeidai_values)
        self.assertGreaterEqual(g2b_median, 0.95)



# ---------------------------------------------------------------------------
# T-204：P2 集成验收与 G2-a/b/c 证据（CONTRACTS v1.4）
# ---------------------------------------------------------------------------

G2A_LINE_RE = re.compile(
    r"^G2-a overlap_ratio=([0-9.eE+-]+) isolated=(\d+) edges=(\d+)$"
)
G2B_LINE_RE = re.compile(
    r"^G2-b yeidai_n=(\d+) median_iou=([0-9.eE+-]+) result=(PASS|FAIL)$"
)
G2C_LINE_RE = re.compile(
    r"^G2-c dealer src_id=(\S+) iou=([0-9.eE+-]+) recall=([0-9.eE+-]+)"
    r" precision=([0-9.eE+-]+) straddle=(\d+) components=(\d+) p2b=(YES|NO)$"
)


def parse_gate_summary(stdout: str) -> dict:
    """解析 CLI 三段汇总；行序与格式不符即断言失败（而非静默漏检）。"""
    lines = [ln for ln in stdout.splitlines() if ln.startswith("G2-")]
    assert lines, "stdout 中没有任何 G2-* 汇总行"
    m = G2A_LINE_RE.match(lines[0])
    assert m, f"G2-a 行格式不符：{lines[0]!r}"
    g2a = {"overlap_ratio": float(m.group(1)), "isolated": int(m.group(2)),
           "edges": int(m.group(3))}
    m = G2B_LINE_RE.match(lines[1])
    assert m, f"G2-b 行格式不符：{lines[1]!r}"
    g2b = {"yeidai_n": int(m.group(1)), "median_iou": float(m.group(2)),
           "result": m.group(3)}
    g2c_rows = []
    i = 2
    while i < len(lines) and not lines[i].startswith("G2-c p2b_triggered="):
        m = G2C_LINE_RE.match(lines[i])
        assert m, f"G2-c 逐项行格式不符：{lines[i]!r}"
        g2c_rows.append({
            "src_id": m.group(1), "iou": float(m.group(2)),
            "recall": float(m.group(3)), "precision": float(m.group(4)),
            "straddle": int(m.group(5)), "components": int(m.group(6)),
            "p2b": m.group(7),
        })
        i += 1
    assert i < len(lines), "缺少 G2-c p2b_triggered 收尾行"
    m = re.match(r"^G2-c p2b_triggered=(YES|NO)$", lines[i])
    assert m, f"p2b_triggered 行格式不符：{lines[i]!r}"
    return {"g2a": g2a, "g2b": g2b, "g2c_rows": g2c_rows,
            "p2b_triggered": m.group(1)}


def build_gate_pass_dir(root: Path) -> Path:
    """G2-b PASS 夹具：业代围栏 = 下右整块（iou=1.0）→ median ≥ 0.95；
    经销商 PZ-0001 手算 iou=0.5625（<0.90 → p2b=YES）、PZ-0002 远处空选——
    经空选即退出码 5，故改用半个下右块（iou<0.90 → p2b=YES）。
    """
    d = build_oracle_dir(root)
    write_json(d / units_mod.DEALER_FILENAME, {
        "fences": [
            make_fence("PZ-0001", geom=_poly(0, 0, 1.5, 1.5)),
            make_fence("PZ-0002", name="经销商乙", geom=_poly(1.0, 0.0, 1.5, 1.0)),
        ],
    })
    return d


def build_gate_fail_dir(root: Path) -> Path:
    """G2-b FAIL 夹具：业代围栏只盖小半块下右 → median < 0.95。

    YD-0001=(1.4,0)-(2,1)：质心 (1.5,0.5) covered；U=单元1(1×1)，inter=0.6，
    iou=0.6/(1+0.6-0.6)=0.6 <0.95 → 退出码 6。
    """
    d = build_oracle_dir(root)
    write_json(d / units_mod.YEIDAI_FILENAME, {
        "fences": [make_fence("YD-0001", name="业代甲", geom=_poly(1.4, 0.0, 2.0, 1.0))],
    })
    return d


class TestT204GateSummary(unittest.TestCase):
    """T-204 三段汇总 / G2-b 门禁执行 / P2b 判定 / 无泄漏 / 无经销商聚合。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_g2b_pass_and_p2b_yes_exits_zero(self):
        """G2-b PASS（median=1.0）+ 经销商 iou<0.90 → 退出码 0 且 P2b=YES。

        P2b 触发不是失败：不得改变退出码，4 条逐项行 + 收尾行照常输出。
        """
        d = build_gate_pass_dir(self.root)
        result = run_cli(d)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = parse_gate_summary(result.stdout)
        self.assertEqual(summary["g2b"]["result"], "PASS")
        self.assertEqual(summary["g2b"]["yeidai_n"], 1)
        self.assertTrue(math.isclose(summary["g2b"]["median_iou"], 1.0))
        rows = summary["g2c_rows"]
        self.assertEqual(len(rows), 2)  # 夹具恰 2 条经销商围栏 → 恰 2 条逐项行
        self.assertEqual([r["src_id"] for r in rows], ["PZ-0001", "PZ-0002"])
        self.assertTrue(math.isclose(rows[0]["iou"], 0.5625))
        self.assertEqual(rows[0]["p2b"], "YES")
        self.assertEqual(summary["p2b_triggered"], "YES")
        # 无经销商聚合：stdout 不得出现中位数行/字段
        self.assertNotIn("dealer_median", result.stdout)
        self.assertNotIn("经销商中位", result.stdout)

    def test_g2b_fail_exits_six_with_gate_fail_and_numbers_kept(self):
        """G2-b FAIL：退出码 6、stderr [GATE-FAIL]、G2-a/G2-c 数字仍在 stdout，
        oracle_unitsets.json 不删除（原始数字供 L1 追加 [GATE-FAIL] 记录）。
        """
        d = build_gate_fail_dir(self.root)
        result = run_cli(d)
        self.assertEqual(result.returncode, 6)
        self.assertIn("[GATE-FAIL] G2-b", result.stderr)
        summary = parse_gate_summary(result.stdout)
        self.assertEqual(summary["g2b"]["result"], "FAIL")
        self.assertLess(summary["g2b"]["median_iou"], 0.95)
        self.assertTrue(math.isclose(summary["g2b"]["median_iou"], 0.6))
        self.assertTrue((d / units_mod.ORACLE_FILENAME).exists())
        self.assertTrue((d / units_mod.UNIT_GRAPH_FILENAME).exists())
        # FAIL 判定不得涉及 recall / precision（判据只有 iou，格式级回归防线）
        self.assertNotIn("recall=", result.stderr)
        self.assertNotIn("precision=", result.stderr)

    def test_recall_precision_absent_from_gate_expressions(self):
        """门禁判定行中 recall/precision 只允许出现在 G2-c 逐项行的解释字段。"""
        d = build_gate_pass_dir(self.root)
        result = run_cli(d)
        self.assertEqual(result.returncode, 0, result.stderr)
        for ln in result.stdout.splitlines():
            if ln.startswith("G2-a ") or ln.startswith("G2-b ") or ln.startswith("G2-c p2b"):
                self.assertNotIn("recall", ln, ln)
                self.assertNotIn("precision", ln, ln)

    def test_boundary_centroids_warn_line_on_positive(self):
        """boundary_centroids>0：stderr 出现精简告警行并含原值；结果不变。

        PZ-0002=(1,0.5)-(1.5,1)：右边界 x=1.5 恰过单元 1 质心 (1.5,0.5)
        （单元 3 质心 y=1.5 在围栏外）→ 贡献 1；PZ-0001 仍贡献 3 → 总计 4。
        """
        d = build_gate_pass_dir(self.root)
        write_json(d / units_mod.DEALER_FILENAME, {
            "fences": [
                make_fence("PZ-0001", geom=_poly(0, 0, 1.5, 1.5)),
                make_fence("PZ-0002", name="经销商乙", geom=_poly(1.0, 0.5, 1.5, 1.0)),
            ],
        })
        result = run_cli(d)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[WARN] boundary_centroids=4 > 0", result.stderr)
        oracle = json.loads((d / units_mod.ORACLE_FILENAME).read_text("utf-8"))
        self.assertEqual(oracle["boundary_centroids"], 4)


class TestT204RealDataAcceptance(unittest.TestCase):
    """真实数据端到端验收：卡载 assert 逐条 + 双跑一致性 + 输入只读 + 无泄漏。"""

    DATA_DIR = REPO_ROOT / "data" / "pilot"

    def setUp(self):
        if not self.DATA_DIR.is_dir():
            self.skipTest("data/pilot 不存在（业务数据不入 git）")

    def test_real_data_full_acceptance(self):
        data_dir = self.DATA_DIR
        units_path = data_dir / units_mod.UNITS_FILENAME
        dealer_path = data_dir / units_mod.DEALER_FILENAME
        yeidai_path = data_dir / units_mod.YEIDAI_FILENAME
        before = {
            "units": units_path.read_bytes(),
            "dealer": dealer_path.read_bytes(),
            "yeidai": yeidai_path.read_bytes(),
        }
        result1 = run_cli(data_dir)
        self.assertEqual(result1.returncode, 0, result1.stderr)
        summary = parse_gate_summary(result1.stdout)
        graph_bytes_1 = (data_dir / units_mod.UNIT_GRAPH_FILENAME).read_bytes()
        oracle_bytes_1 = (data_dir / units_mod.ORACLE_FILENAME).read_bytes()

        graph = json.loads(graph_bytes_1.decode("utf-8"))
        assert set(graph) == {"adjacency", "link_min_m"}
        assert graph["link_min_m"] == 50
        assert len(graph["adjacency"]) == 224
        adj = {int(u): nbrs for u, nbrs in graph["adjacency"].items()}
        assert set(adj) == set(range(224))
        assert all(u in adj[v] for u, nbrs in adj.items() for v in nbrs)
        assert all(u not in adj[u] for u in adj)
        assert summary["g2a"]["overlap_ratio"] < 0.001
        assert summary["g2a"]["isolated"] == 0

        oracle = json.loads(oracle_bytes_1.decode("utf-8"))
        assert set(oracle) == {"method", "link_min_m", "boundary_centroids", "fences"}
        assert oracle["method"] == "3.6-v1.4"
        assert oracle["link_min_m"] == 50
        assert isinstance(oracle["boundary_centroids"], int)
        assert oracle["boundary_centroids"] >= 0
        assert len(oracle["fences"]) == 21
        assert all(
            set(v) == {"name", "layer", "unit_ids", "iou", "recall", "precision",
                       "straddle", "components"}
            for v in oracle["fences"].values()
        )
        assert all(v["unit_ids"] == sorted(set(v["unit_ids"]))
                   for v in oracle["fences"].values())
        assert all(0 <= uid < 224
                   for v in oracle["fences"].values() for uid in v["unit_ids"])
        assert all(
            math.isfinite(v[f]) and 0.0 <= v[f] <= 1.0
            for v in oracle["fences"].values() for f in ("iou", "recall", "precision")
        )
        assert all(isinstance(v["straddle"], int) and v["straddle"] >= 0
                   for v in oracle["fences"].values())
        assert all(isinstance(v["components"], int) and v["components"] >= 1
                   for v in oracle["fences"].values())

        yeidai_values = [v["iou"] for v in oracle["fences"].values() if v["layer"] == "yeidai"]
        dealer_rows = summary["g2c_rows"]
        assert len(yeidai_values) == 17
        assert statistics.median(yeidai_values) >= 0.95
        assert summary["g2b"]["result"] == "PASS"
        assert len(dealer_rows) == 4
        assert all(
            r["src_id"] and math.isfinite(r["iou"]) and 0.0 <= r["iou"] <= 1.0
            and math.isfinite(r["recall"]) and 0.0 <= r["recall"] <= 1.0
            and math.isfinite(r["precision"]) and 0.0 <= r["precision"] <= 1.0
            and isinstance(r["straddle"], int) and r["straddle"] >= 0
            and isinstance(r["components"], int) and r["components"] >= 1
            for r in dealer_rows
        )
        assert "dealer_median" not in result1.stdout
        assert "经销商中位" not in result1.stdout
        expected_p2b = any(r["iou"] < 0.90 for r in dealer_rows)
        assert (summary["p2b_triggered"] == "YES") == expected_p2b

        # 第二跑：字节一致；输入文件全程只读
        result2 = run_cli(data_dir)
        self.assertEqual(result2.returncode, 0, result2.stderr)
        assert (data_dir / units_mod.UNIT_GRAPH_FILENAME).read_bytes() == graph_bytes_1
        assert (data_dir / units_mod.ORACLE_FILENAME).read_bytes() == oracle_bytes_1
        after = {
            "units": units_path.read_bytes(),
            "dealer": dealer_path.read_bytes(),
            "yeidai": yeidai_path.read_bytes(),
        }
        assert before == after

        # CLI 无泄漏：不打印完整 WKT / 坐标 / key 之外的客户名称或凭证
        units_payload = json.loads(before["units"].decode("utf-8"))
        a_unit_geom = units_payload["units"][0]["geom"]
        self.assertNotIn(a_unit_geom, result1.stdout)
        self.assertNotIn("POLYGON ((", result1.stdout)
        self.assertNotIn("MULTIPOLYGON ((", result1.stdout)


# ---------------------------------------------------------------------------


def run_cli(data_dir: Path | None) -> subprocess.CompletedProcess:
    argv = [sys.executable, str(MODULE_PATH)]
    if data_dir is not None:
        argv += ["--data", str(data_dir)]
    return subprocess.run(argv, capture_output=True, text=True)


class TestCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_cli_requires_explicit_data(self):
        """不传 --data 必须失败（证明无内置默认路径）。"""
        result = run_cli(None)
        self.assertNotEqual(result.returncode, 0)

    def test_cli_writes_unit_graph_when_no_isolated(self):
        """无孤立单元：写出 unit_graph.json 且两跑字节一致；夹具业代 iou=1/3
        未达 0.95 → G2-b 门禁生效，退出码 6 且 stderr 含 [GATE-FAIL]，
        但 T-202 产物照常写出（门禁失败不删图）。
        """
        d = build_valid_dir(self.root)
        # 让 3 个单元两两共享边（第三个移到与 1 相邻的位置），消除孤立节点
        payload = json.loads((d / units_mod.UNITS_FILENAME).read_text("utf-8"))
        payload["units"][2]["geom"] = SQ_UPPER  # 1-2 共享边；0-1 共享边；2 与 0 仅点接触
        write_json(d / units_mod.UNITS_FILENAME, payload)

        result1 = run_cli(d)
        self.assertEqual(result1.returncode, 6, result1.stdout)
        self.assertIn("[GATE-FAIL] G2-b", result1.stderr)
        out_path = d / units_mod.UNIT_GRAPH_FILENAME
        self.assertTrue(out_path.exists(), "G2-b 失败也必须保留 unit_graph.json")
        first = out_path.read_bytes()
        graph = json.loads(first.decode("utf-8"))
        self.assertEqual(graph["link_min_m"], 50)
        self.assertEqual(set(graph), {"adjacency", "link_min_m"})
        self.assertEqual(graph["adjacency"], {"0": [1], "1": [0, 2], "2": [1]})
        # 双跑确定性
        result2 = run_cli(d)
        self.assertEqual(result2.returncode, 6, result2.stdout)
        self.assertEqual(out_path.read_bytes(), first, "同输入两跑必须字节一致")

    def test_cli_isolated_unit_exits_4_with_escalation(self):
        """存在孤立单元：退出码 4，输出 ESCALATION:uid/key/district_code/street。"""
        d = build_valid_dir(self.root)  # uid=2 为孤立（SQ_FAR）
        result = run_cli(d)
        self.assertEqual(result.returncode, 4)
        self.assertIn("ESCALATION:2/U-0002/440105/某街道", result.stdout)

    def test_cli_overlap_gate_fail_exits_3(self):
        """重叠率 >= 0.001：退出码 3，stderr 含 [GATE-FAIL] 与数字。"""
        d = build_valid_dir(self.root)
        # 三个单元全部使用同一几何 → 全对重叠，重叠率 = 1
        payload = json.loads((d / units_mod.UNITS_FILENAME).read_text("utf-8"))
        for u in payload["units"]:
            u["geom"] = SQ_LEFT
        write_json(d / units_mod.UNITS_FILENAME, payload)
        result = run_cli(d)
        self.assertEqual(result.returncode, 3)
        self.assertIn("[GATE-FAIL]", result.stderr)
        self.assertNotEqual(result.returncode, 0)

    def test_cli_missing_dir_fails_with_chinese(self):
        result = run_cli(self.root / "no-such-dir")
        self.assertEqual(result.returncode, 2)
        self.assertIn("数据目录不存在", result.stderr)


if __name__ == "__main__":
    unittest.main()
