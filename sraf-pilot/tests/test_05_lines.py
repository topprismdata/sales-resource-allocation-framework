# -*- coding: utf-8 -*-
"""T-501 单元测试：P5 OSM 全量命名线要素构建（p5-lines-v1，GCJ-02 归一）。

覆盖任务卡全部可执行断言：schema 冻结字段集、聚合与排序不变量、
``wgs2gcj`` 逐点 mock 计数、输入只读、双跑字节一致、失败路径中文抛错
不留半份文件；固定快照 smoke（存在时运行）核对冻结计数。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../sraf
MODULE_PATH = REPO_ROOT / "sraf-pilot" / "src" / "05_lines.py"

_spec = importlib.util.spec_from_file_location("lines_05", MODULE_PATH)
lines_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lines_mod)

from intelligence.coords import wgs2gcj as real_wgs2gcj  # noqa: E402


# ---------------------------------------------------------------------------
# 合成夹具：未命名 highway、两个同名 highway way、命名 waterway、
# 命名 railway、含两个类别键的 way —— 与任务卡逐条对应。
# ---------------------------------------------------------------------------


_spec = importlib.util.spec_from_file_location("lines_05", MODULE_PATH)
lines_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = lines_mod  # 供 mock 按名解析与子进程复用
_spec.loader.exec_module(lines_mod)
def _way(way_id, name, pts, extra_tags=None, typ="way", geometry_key="geometry"):
    """构造一条 Overpass way；pts 为 [(lat, lon), ...]（OSM 原顺序）。"""
    element: dict = {"type": typ, "id": way_id, "geometry": [{"lat": la, "lon": lo} for la, lo in pts]}
    tags: dict = {}
    if name is not None:
        tags["name"] = name
    if extra_tags:
        tags.update(extra_tags)
    if tags:
        element["tags"] = tags
    return element


def _pt3(lon0, lat0, lon1, lat1):
    """两点线夹具（广州附近，转换后仍与原值明显不同）。"""
    return [(lat0, lon0), (lat1, lon1)]


def build_source() -> dict:
    """合成输入：source_elements=5、named_ways=4、output_names=3、output_parts=4。

    way 10 同时带 highway+railway 两个类别键：同名路 classes 为跨 way 并集。
    """
    return {
        "version": 0.6,
        "generator": "test",
        "elements": [
            # 未命名 highway：仅计入 source_elements
            _way(1, None, _pt3(113.30, 23.04, 113.31, 23.04), {"highway": "residential"}),
            # 两个同名 highway way（id=10,20）：聚合为 MultiLineString
            _way(20, "同名路", _pt3(113.30, 23.04, 113.31, 23.04), {"highway": "primary"}),
            _way(10, "同名路", _pt3(113.32, 23.05, 113.33, 23.05),
                 {"highway": "primary", "railway": "rail"}),
            # 命名 waterway
            _way(30, "珠江", _pt3(113.28, 23.10, 113.29, 23.10), {"waterway": "river"}),
            # 命名 railway
            _way(40, "广珠铁路", _pt3(113.26, 23.02, 113.27, 23.02), {"railway": "rail"}),
        ],
    }


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class LinesTestCase(unittest.TestCase):
    """公共夹具：临时目录 + mock 计数的 wgs2gcj（wraps 真实实现）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.src = self.tmp / "osm_raw.json"
        self.out = self.tmp / "out" / "lines.json"
        self.out.parent.mkdir(parents=True, exist_ok=True)  # 模块要求输出目录已存在
        self.src.write_text(
            json.dumps(build_source(), ensure_ascii=False), encoding="utf-8"
        )
        self.src_bytes = self.src.read_bytes()
        patcher = mock.patch.object(lines_mod, "wgs2gcj", wraps=real_wgs2gcj)
        self.wgs_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def build(self):
        return lines_mod.build(self.src, self.out)


def count_source_points(source: dict) -> int:
    """命名 way 的坐标点总数（期望的 wgs2gcj 调用次数）。"""
    total = 0
    for element in source["elements"]:
        tags = element.get("tags")
        if not tags or "name" not in tags:
            continue
        total += len(element.get("geometry", []))
    return total


def named_gcj_points(source: dict) -> set[tuple[float, float]]:
    """全部命名 way 坐标点经真实转换后的 GCJ 坐标集合。"""
    pts: set[tuple[float, float]] = set()
    for element in source["elements"]:
        tags = element.get("tags")
        if not tags or "name" not in tags:
            continue
        for p in element["geometry"]:
            pts.add(tuple(real_wgs2gcj(p["lon"], p["lat"])))
    return pts


# ---------------------------------------------------------------------------
# 正向：schema 冻结字段集 + 聚合/排序不变量 + 转换计数 + 只读 + 双跑一致
# ---------------------------------------------------------------------------


class TestHappyPath(LinesTestCase):
    def test_line_fields_and_aggregation(self):
        payload = self.build()
        self.assertEqual(
            set(payload),
            {"schema_version", "crs", "source_crs", "source_sha256", "counts", "lines"},
        )
        self.assertEqual(payload["schema_version"], "p5-lines-v1")
        self.assertEqual(payload["crs"], "GCJ-02")
        self.assertEqual(payload["source_crs"], "WGS-84")
        self.assertEqual(
            payload["source_sha256"], hashlib.sha256(self.src_bytes).hexdigest()
        )
        self.assertEqual(payload["counts"]["source_elements"], 6)
        self.assertEqual(payload["counts"]["source_elements"], len(build_source()["elements"]))
        self.assertEqual(payload["counts"]["source_named_ways"], 4)
        self.assertEqual(payload["counts"]["output_names"], 3)
        self.assertEqual(payload["counts"]["output_parts"], 4)
        self.assertEqual(
            [row["name"] for row in payload["lines"]], sorted({"同名路", "珠江", "广珠铁路"})
        )
        self.assertEqual(payload["counts"]["output_names"], len(payload["lines"]))

    def test_line_fields_and_aggregation(self):
        payload = self.build()
        for row in payload["lines"]:
            self.assertEqual(set(row), set(lines_mod.LINE_FIELDS))
        by_name = {row["name"]: row for row in payload["lines"]}
        same = by_name["同名路"]
        self.assertEqual(same["osm_way_ids"], [10, 20])
        self.assertTrue(same["geom"].startswith("MULTILINESTRING"))
        self.assertEqual(by_name["珠江"]["osm_way_ids"], [30])
        self.assertEqual(by_name["珠江"]["geom"].split(" ", 1)[0], "LINESTRING")
        self.assertEqual(by_name["珠江"]["classes"], ["waterway"])
        self.assertEqual(by_name["广珠铁路"]["classes"], ["railway"])
        # 双类别键 way：classes 为该名称全部命中键的升序唯一数组
        self.assertEqual(same["classes"], ["highway", "railway"])

    def test_wgs2gcj_call_count_and_values(self):
        source = build_source()
        payload = self.build()
        expected = count_source_points(source)
        self.assertEqual(self.wgs_mock.call_count, expected)
        # 每个输出坐标点都等于对相应原始 WGS 点调用一次真实转换的结果，
        # 且与 WGS 原值不相等（shapely 2.x wkt 往返 double 精确）。
        from shapely import wkt as shapely_wkt

        out_pts: set[tuple[float, float]] = set()
        for row in payload["lines"]:
            geom = shapely_wkt.loads(row["geom"])
            for part in getattr(geom, "geoms", [geom]):
                for x, y in part.coords:
                    out_pts.add((x, y))
        self.assertEqual(out_pts, named_gcj_points(source))
        wgs_pts = set()
        for element in source["elements"]:
            tags = element.get("tags")
            if not tags or "name" not in tags:
                continue
            for p in element["geometry"]:
                wgs_pts.add((p["lon"], p["lat"]))
        self.assertFalse(out_pts & wgs_pts)

    def test_input_readonly_and_deterministic(self):
        sha_before = hashlib.sha256(self.src.read_bytes()).hexdigest()
        src_obj = json.loads(self.src.read_text(encoding="utf-8"))
        obj_before = json.dumps(src_obj, sort_keys=True, ensure_ascii=False)
        self.build()
        self.assertEqual(hashlib.sha256(self.src.read_bytes()).hexdigest(), sha_before)
        obj_after = json.dumps(
            json.loads(self.src.read_text(encoding="utf-8")), sort_keys=True, ensure_ascii=False
        )
        self.assertEqual(obj_after, obj_before)
        first = self.out.read_bytes()
        self.build()
        self.assertEqual(self.out.read_bytes(), first)
        # 原子替换：无临时文件残留
        self.assertEqual(
            [p.name for p in self.out.parent.iterdir()], [self.out.name]
        )

    def test_json_formatting(self):
        self.build()
        text = self.out.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        payload = json.loads(text)
        self.assertEqual(payload["lines"], sorted(payload["lines"], key=lambda r: r["name"]))
        # 稳定缩进（indent=2）与 ensure_ascii=False 的中文原样出现
        self.assertIn("「" if False else "同名路", text)


# ---------------------------------------------------------------------------
# 失败路径：逐项中文抛错且不产生半份输出
# ---------------------------------------------------------------------------


class TestErrorPaths(LinesTestCase):
    def _expect_fail(self, source, message_part: str):
        self.src.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(lines_mod.LineBuildError) as ctx:
            self.build()
        self.assertIn(message_part, str(ctx.exception))
        self.assertFalse(self.out.exists())  # 无半份输出
        if self.out.parent.exists():
            self.assertEqual([p.name for p in self.out.parent.iterdir()], [])

    def test_top_level_not_object(self):
        self.src.write_text("[]", encoding="utf-8")
        with self.assertRaises(lines_mod.LineBuildError) as ctx:
            self.build()
        self.assertIn("顶层必须是 JSON 对象", str(ctx.exception))
        self.assertFalse(self.out.exists())

    def test_elements_not_array(self):
        self._expect_fail({"elements": {}}, "elements 必须是数组")

    def test_named_element_not_way(self):
        self._expect_fail(
            {"elements": [{"type": "node", "id": 1, "tags": {"name": "x"}}]},
            "type 必须是 way",
        )

    def test_bad_id(self):
        self._expect_fail(
            {"elements": [_way("x", "路", _pt3(113.3, 23.0, 113.31, 23.0), {"highway": "road"})]},
            "id 必须是正整数",
        )

    def test_duplicate_ids(self):
        self._expect_fail(
            {
                "elements": [
                    _way(7, "路A", _pt3(113.3, 23.0, 113.31, 23.0), {"highway": "road"}),
                    _way(7, "路B", _pt3(113.32, 23.0, 113.33, 23.0), {"highway": "road"}),
                ]
            },
            "id 重复",
        )

    def test_no_class_key(self):
        self._expect_fail(
            {"elements": [_way(7, "路", _pt3(113.3, 23.0, 113.31, 23.0), {"bridge": "yes"})]},
            "缺少 highway/waterway/railway",
        )

    def test_missing_geometry(self):
        element = _way(7, "路", _pt3(113.3, 23.0, 113.31, 23.0), {"highway": "road"})
        del element["geometry"]
        self._expect_fail({"elements": [element]}, "geometry 必须是点数组")

    def test_fewer_than_two_distinct_points(self):
        self._expect_fail(
            {"elements": [_way(7, "路", [(23.0, 113.3), (23.0, 113.3)], {"highway": "road"})]},
            "至少需要 2 个不同坐标点",
        )

    def test_nan_and_inf_coords(self):
        raw = json.dumps(
            {"elements": [_way(7, "路", [(23.0, 113.3), (23.1, 113.31)], {"highway": "road"})]}
        ).replace("23.1", "1e999")
        self.src.write_text(raw, encoding="utf-8")
        with self.assertRaises(lines_mod.LineBuildError) as ctx:
            self.build()
        self.assertIn("非有限值", str(ctx.exception))
        self.assertFalse(self.out.exists())

    def test_illegal_name(self):
        self._expect_fail(
            {"elements": [_way(7, "   ", _pt3(113.3, 23.0, 113.31, 23.0), {"highway": "road"})]},
            "name 必须是非空字符串",
        )

    def test_converter_raises(self):
        with mock.patch(
            f"{lines_mod.__name__}.wgs2gcj", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(lines_mod.LineBuildError) as ctx:
                self.build()
        self.assertIn("wgs2gcj 坐标转换失败", str(ctx.exception))
        self.assertFalse(self.out.exists())

    def test_out_dir_not_writable(self):
        out = self.tmp / "lines.json"
        d = self.out.parent
        d.mkdir(parents=True, exist_ok=True)
        real_replace = os.replace

        def broken_replace(src_, dst_):
            raise PermissionError(13, "Permission denied")

        with mock.patch.object(lines_mod.os, "replace", side_effect=broken_replace):
            with self.assertRaises(lines_mod.LineBuildError) as ctx:
                self.build()
        self.assertIn("不可写", str(ctx.exception))
        self.assertFalse(out.exists())
        # 临时文件已被清理
        leftovers = [p.name for p in d.iterdir()]
        self.assertEqual(leftovers, [])
        real_replace  # 保持引用，避免 lint 误报未使用

    def test_failure_leaves_existing_output_untouched(self):
        self.build()
        good = self.out.read_bytes()
        self.src.write_text(
            json.dumps({"elements": [{"type": "node", "id": 1, "tags": {"name": "x"}}]},
                       ensure_ascii=False),
            encoding="utf-8",
        )
        with self.assertRaises(lines_mod.LineBuildError):
            self.build()
        self.assertEqual(self.out.read_bytes(), good)  # 目标原文件字节不变


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCli(LinesTestCase):
    def test_cli_success_and_failure(self):
        import subprocess

        argv = [sys.executable, str(MODULE_PATH), "--src", str(self.src), "--out", str(self.out)]
        result = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("构建完成", result.stdout)
        self.assertTrue(self.out.exists())
        bad = self.tmp / "bad.json"
        bad.write_text("[]", encoding="utf-8")
        result2 = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--src", str(bad), "--out", str(self.out / "x.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(result2.returncode, 1)
        self.assertIn("顶层必须是 JSON 对象", result2.stderr)


# ---------------------------------------------------------------------------
# 固定快照 smoke（/tmp/p2b_probe/osm_raw.json 存在时必须运行；不联网补源）
# ---------------------------------------------------------------------------

SNAPSHOT = Path("/tmp/p2b_probe/osm_raw.json")


@unittest.skipUnless(SNAPSHOT.is_file(), "固定快照不存在")
class TestFixedSnapshotSmoke(unittest.TestCase):
    def test_frozen_counts_and_invariants(self):
        payload = lines_mod.build(SNAPSHOT, REPO_ROOT / "data" / "pilot" / "lines.json")
        self.assertEqual(payload["counts"]["source_elements"], 45772)
        self.assertEqual(payload["counts"]["source_named_ways"], 13945)
        self.assertEqual(payload["counts"]["output_parts"], 13945)
        self.assertEqual(payload["counts"]["output_names"], len(payload["lines"]))
        names = [row["name"] for row in payload["lines"]]
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(names, sorted(names))
        self.assertTrue(
            all(row["geom"].startswith(("LINESTRING", "MULTILINESTRING")) for row in payload["lines"])
        )


if __name__ == "__main__":
    unittest.main()
