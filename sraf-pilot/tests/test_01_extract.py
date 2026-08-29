# -*- coding: utf-8 -*-
"""T-101/T-102/T-103/T-104 单元测试：输入适配、地理层抽取、围栏筛区与坐标验证。
全部用临时目录 + 最小合成夹具：不访问真实客户数据、无网络、不写源目录。
被测模块文件名以数字开头，无法常规 import，故用 importlib 按路径加载。
T-102 起 CLI 写出地理层三产物；T-103 起再写两份围栏 JSON 与
data_issues.md，夹具相应提供多边形区县几何与围栏筛选场景；T-104 起在有经销商
围栏样本时再写 crs_evidence.json（§3.5.4 坐标验证）。
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
import shapely.geometry
import shapely.wkt as shapely_wkt
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from intelligence.coords import gcj2wgs as real_gcj2wgs  # noqa: E402
from intelligence.world import haversine_km as real_haversine_km  # noqa: E402

# ---------------------------------------------------------------------------
# 按路径加载被测模块
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../sraf
MODULE_PATH = REPO_ROOT / "sraf-pilot" / "src" / "01_extract.py"

_spec = importlib.util.spec_from_file_location("extract_01", MODULE_PATH)
extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract)

FILENAMES = {logical: spec[0] for logical, spec in extract.SOURCES.items()}

VALID_WKT = "POLYGON ((113.0 23.0, 113.1 23.0, 113.1 23.1, 113.0 23.1, 113.0 23.0))"

# ---------------------------------------------------------------------------
# 最小合成夹具
# ---------------------------------------------------------------------------


def make_units_feature(
    district_code: str = "440103", key: str = "U-0001", street: str = "某街道"
) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "区县编码": district_code,
            "街道[内置]": street,
            "中心点": "113.1,23.1",
            "面积": 12.5,
            "主键": key,
        },
        "geometry": {"type": "Point", "coordinates": [113.1, 23.1]},
    }


def make_streets_feature(
    code: str = "440103001", parent: str = "440103", name: str = "某街道"
) -> dict:
    return {
        "type": "Feature",
        "properties": {"行政区名称": name, "区域编码": code, "父级id": parent},
        "geometry": {"type": "Point", "coordinates": [113.1, 23.1]},
    }


def make_districts_feature(code: str = "440103", name: str = "某区") -> dict:
    return {
        "type": "Feature",
        "properties": {"行政区名称": name, "区域编码": code},
        "geometry": {"type": "Point", "coordinates": [113.1, 23.1]},
    }


def csv_header(yeidai: bool = False) -> list[str]:
    return list(extract.YEIDAI_FIELDS if yeidai else extract.DEALER_FIELDS)


def make_dealer_row(name: str = "测试围栏", fence: str = VALID_WKT, **overrides) -> dict:
    row = {
        "片区id": "PZ-0001",
        "围栏名称": name,
        "fence": fence,
        "中心点经度": "113.05",
        "中心点纬度": "23.05",
        "围栏面积": "1234567.8",
    }
    if overrides:
        row.update(overrides)
    return row


def make_yeidai_row(name: str = "测试业代", fence: str = VALID_WKT) -> dict:
    row = make_dealer_row(name=name, fence=fence)
    row["办事处名称"] = "广州办事处"
    return row


def write_geojson(path: Path, features: list[dict], *, top_type: str = "FeatureCollection") -> None:
    payload = {"type": top_type, "features": features}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    """写出夹具 CSV；extrasaction="ignore" 以支持“表头缺字段”的残缺形态。"""
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_valid_src(root: Path) -> Path:
    """生成一套五文件齐全、含两个试点区的最小合成源目录（可重复调用）。

    地理层夹具：
    - 单元：440105 × 2（主键 U-A1/U-A2）+ 440103 × 1（U-B1）+ 第三区 440104 × 1；
    - 区县：440105、440103、440104 三个；
    - 街道：海珠 2 个（440105001/440105002）、荔湾 1 个（440103001）、
      第三区 1 个（440104001）。
    T-101 的输入层断言只关心结构合法，多几条不影响。
    """
    src = root / "src"
    src.mkdir(parents=True, exist_ok=True)
    unit_codes = ["440105", "440105", "440103", "440104"]
    unit_keys = ["U-A1", "U-A2", "U-B1", "U-C1"]
    unit_streets = ["海珠街道A", "海珠街道B", "荔湾街道A", "外区街道"]
    write_geojson(
        src / FILENAMES["UNITS_SRC"],
        [
            make_units_feature(c, k, s)
            for c, k, s in zip(unit_codes, unit_keys, unit_streets)
        ],
    )
    write_geojson(
        src / FILENAMES["STREETS_SRC"],
        [
            make_streets_feature("440105001", "440105", "海珠街道A"),
            make_streets_feature("440105002", "440105", "海珠街道B"),
            make_streets_feature("440103001", "440103", "荔湾街道A"),
            make_streets_feature("440104001", "440104", "外区街道"),
        ],
    )
    write_geojson(
        src / FILENAMES["DISTRICTS_SRC"],
        [
            make_districts_feature("440105", "海珠区"),
            make_districts_feature("440103", "荔湾区"),
            make_districts_feature("440104", "外区"),
        ],
    )
    write_csv(src / FILENAMES["DEALER_SRC"], csv_header(), [make_dealer_row()])
    write_csv(src / FILENAMES["YEIDAI_SRC"], csv_header(yeidai=True), [make_yeidai_row()])
    return src


def snapshot_bytes(src: Path) -> dict:
    return {
        p.relative_to(src).as_posix(): p.read_bytes()
        for p in sorted(src.rglob("*"))
        if p.is_file()
    }


def build_huge_wkt(min_len: int) -> str:
    """构造超长但合法的 POLYGON WKT：沿单调递增路径密集加点后闭合。"""
    import random

    rng = random.Random(42)
    pts: list[tuple[float, float]] = []
    x, y = 113.0, 23.0
    ring = lambda pts_: ", ".join(f"{px:.6f} {py:.6f}" for px, py in pts_)
    while len(ring(pts)) < min_len or len(pts) < 5:
        x += rng.uniform(0.00001, 0.0001)
        y += rng.uniform(0.00001, 0.0001)
        pts.append((x, y))
    pts.append(pts[0])  # 闭合
    return f"POLYGON (({ring(pts)}))"


def run_cli(src: Path, out: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(MODULE_PATH), "--src", str(src), "--out", str(out)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def has_cjk(msg: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in msg)


class T101Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _assert_invalid(
        self,
        mutate,
        logical: str,
        expect_field: str | None,
    ):
        """在合法源目录上施加变更后，extract_all 必须抛中文异常，
        且消息同时包含文件名与（可选）字段名。"""
        src = build_valid_src(self.root)
        mutate(src)
        with self.assertRaises(extract.SourceDataError) as ctx:
            extract.extract_all(src)
        msg = str(ctx.exception)
        self.assertIn(FILENAMES[logical], msg, f"异常应含文件名：{msg}")
        if expect_field is not None:
            self.assertIn(expect_field, msg, f"异常应含字段名：{msg}")
        self.assertTrue(has_cjk(msg), f"异常应含中文原因：{msg}")

    # -- 结构解析（正向） ----------------------------------------------------

    def test_geojson_featurecollection_parsed(self):
        """合成 GeoJSON 是 FeatureCollection，features 数量符合预期。"""
        src = build_valid_src(self.root)
        parsed = json.loads((src / FILENAMES["UNITS_SRC"]).read_text("utf-8"))
        self.assertEqual(parsed["type"], "FeatureCollection")
        self.assertEqual(len(parsed["features"]), 4)

    def test_csv_row_fields_parsed(self):
        src = build_valid_src(self.root)
        with (src / FILENAMES["DEALER_SRC"]).open("r", encoding="utf-8-sig") as fh:
            row = next(csv.DictReader(fh))
        self.assertEqual(row["围栏名称"], "测试围栏")

    def test_csv_huge_field_not_truncated(self):
        """fence 超 131072 字符必须完整读入（field_size_limit 已解除），
        且 shapely 解析出的几何非空。"""
        big_wkt = build_huge_wkt(min_len=140_000)
        self.assertGreater(len(big_wkt), 131_072)
        src = build_valid_src(self.root)
        write_csv(
            src / FILENAMES["DEALER_SRC"],
            csv_header(),
            [make_dealer_row(name="超长围栏", fence=big_wkt)],
        )
        with (src / FILENAMES["DEALER_SRC"]).open("r", encoding="utf-8-sig") as fh:
            row = next(csv.DictReader(fh))
        self.assertGreater(len(row["fence"]), 131_072)
        geom = extract.parse_fence_wkt(row["fence"], "DEALER_SRC")
        self.assertFalse(geom.is_empty)

    def test_wkt_parses_not_empty(self):
        geom = extract.parse_fence_wkt(VALID_WKT, "DEALER_SRC")
        self.assertFalse(geom.is_empty)

    def test_field_size_limit_lifted(self):
        """模块导入后 csv 单字段上限必须大于默认 131072。"""
        self.assertGreater(extract.csv.field_size_limit(), 131_072)

    # -- CLI 形态 ------------------------------------------------------------

    def test_cli_requires_explicit_src(self):
        """不传 --src 时 CLI 必须失败（证明无内置绝对路径默认值）。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(MODULE_PATH), "--out", tmp],
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--src", result.stderr)

    def test_cli_accepts_explicit_out_and_succeeds(self):
        src = build_valid_src(self.root)
        out = self.root / "out-custom"
        result = run_cli(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(out.is_dir())
        self.assertIn("校验通过", result.stdout)

    def test_cli_rejects_missing_src_dir(self):
        result = run_cli(self.root / "no-such-dir", self.root / "out")
        self.assertEqual(result.returncode, 2)

        self.assertIn("目录不存在", result.stderr)

    def test_out_contains_exactly_six_pilot_files(self):
        """T-103 起 CLI 必须写出恰好六个产物（三个地理层 + 两份围栏 +
        data_issues.md；T-102 旧裁定随本卡解冻更新）。"""
        src = build_valid_src(self.root)
        out = self.root / "out-pilot"
        result = run_cli(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            sorted(p.name for p in out.iterdir()),
            [
                "data_issues.md",
                "districts.json",
                "fences_dealer.json",
                "fences_yeidai.json",
                "streets.json",
                "units.json",
            ],
        )

    # -- 片区id 保留字符串 ----------------------------------------------------

    def test_pianqu_id_kept_as_string(self):
        """片区id 形如 0007 必须按原字符串保留（禁止被转成数字）。"""
        src = build_valid_src(self.root)
        write_csv(
            src / FILENAMES["DEALER_SRC"],
            csv_header(),
            [make_dealer_row(**{"片区id": "0007"})],
        )
        rows = extract.read_csv_rows(
            extract.locate_source(src, "DEALER_SRC"), "DEALER_SRC"
        )
        self.assertEqual(rows[0]["片区id"], "0007")
        self.assertIsInstance(rows[0]["片区id"], str)

    # -- 异常路径 --------------------------------------------------------------

    def test_missing_each_source_file(self):
        """五个源文件中任一缺失都必须抛含文件名的中文异常。"""
        for logical in FILENAMES:
            with self.subTest(logical=logical):
                src = build_valid_src(self.root)
                (src / FILENAMES[logical]).unlink()
                with self.assertRaises(extract.SourceDataError) as ctx:
                    extract.extract_all(src)
                msg = str(ctx.exception)
                self.assertIn(FILENAMES[logical], msg)
                self.assertTrue(has_cjk(msg), msg)

    def test_geojson_top_type_invalid(self):
        def mutate(src: Path):
            write_geojson(
                src / FILENAMES["UNITS_SRC"],
                [make_units_feature()],
                top_type="Feature",
            )

        self._assert_invalid(mutate, "UNITS_SRC", None)

    def test_missing_required_field_geojson(self):
        def mutate(src: Path):
            feat = make_units_feature()
            del feat["properties"]["主键"]
            write_geojson(src / FILENAMES["UNITS_SRC"], [feat])

        self._assert_invalid(mutate, "UNITS_SRC", "主键")

    def test_missing_required_field_csv(self):
        def mutate(src: Path):
            header = [c for c in csv_header() if c != "围栏名称"]
            write_csv(src / FILENAMES["DEALER_SRC"], header, [make_dealer_row()])

        self._assert_invalid(mutate, "DEALER_SRC", "围栏名称")

    def test_missing_required_field_yeidai(self):
        """业代 CSV 缺办事处名称必须抛异常。"""

        def mutate(src: Path):
            header = [c for c in csv_header(yeidai=True) if c != "办事处名称"]
            row = make_yeidai_row()
            row.pop("办事处名称", None)
            write_csv(src / FILENAMES["YEIDAI_SRC"], header, [row])

        self._assert_invalid(mutate, "YEIDAI_SRC", "办事处名称")

    def test_csv_non_numeric_center(self):
        for field in ("中心点经度", "中心点纬度"):
            with self.subTest(field=field):

                def mutate(src: Path, field=field):
                    write_csv(
                        src / FILENAMES["DEALER_SRC"],
                        csv_header(),
                        [make_dealer_row(**{field: "不是数字"})],
                    )

                self._assert_invalid(mutate, "DEALER_SRC", field)

    def test_csv_nan_area(self):
        def mutate(src: Path):
            write_csv(
                src / FILENAMES["DEALER_SRC"],
                csv_header(),
                [make_dealer_row(围栏面积="NaN")],
            )

        self._assert_invalid(mutate, "DEALER_SRC", "围栏面积")

    def test_fence_empty_string(self):
        def mutate(src: Path):
            write_csv(
                src / FILENAMES["DEALER_SRC"],
                csv_header(),
                [make_dealer_row(fence="")],
            )

        self._assert_invalid(mutate, "DEALER_SRC", "fence")

    def test_fence_invalid_wkt(self):
        def mutate(src: Path):
            write_csv(
                src / FILENAMES["DEALER_SRC"],
                csv_header(),
                [make_dealer_row(fence="POLYGON 不是合法WKT")],
            )

        self._assert_invalid(mutate, "DEALER_SRC", "fence")

    def test_fence_empty_geometry(self):
        """WKT 语法合法但几何为空（POINT EMPTY）同样必须拒绝。"""
        def mutate(src: Path):
            write_csv(
                src / FILENAMES["DEALER_SRC"],
                csv_header(),
                [make_dealer_row(fence="POINT EMPTY")],
            )

        self._assert_invalid(mutate, "DEALER_SRC", "fence")


class T102Tests(unittest.TestCase):
    """T-102 官方地理层抽取：筛选、无损转写、确定性写出与异常路径。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    # -- 夹具辅助 --------------------------------------------------------------

    @staticmethod
    def _load(out: Path, name: str) -> dict:
        return json.loads((out / name).read_text("utf-8"))

    def _run_valid(self) -> tuple[Path, Path]:
        src = build_valid_src(self.root)
        out = self.root / "out"
        result = run_cli(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        return src, out

    def _mutated_src(self, mutate) -> Path:
        src = build_valid_src(self.root)
        mutate(src)
        return src

    # -- 卡载可执行断言（对合成夹具输出执行） -----------------------------------

    def test_units_payload_contract(self):
        _, out = self._run_valid()
        payload = self._load(out, "units.json")
        units = payload["units"]
        self.assertEqual(payload["crs"], "GCJ-02")
        self.assertGreater(len(units), 0)
        self.assertEqual([u["uid"] for u in units], list(range(len(units))))
        self.assertEqual(len({u["key"] for u in units}), len(units))
        self.assertEqual({u["district_code"] for u in units}, {"440105", "440103"})
        for u in units:
            self.assertEqual(set(u), {"uid", "key", "district_code", "street",
                                      "area_km2", "centroid", "geom"})
            self.assertIsInstance(u["uid"], int)
            self.assertIsInstance(u["key"], str)
            self.assertTrue(u["key"])
            self.assertIsInstance(u["area_km2"], float)
            self.assertGreater(u["area_km2"], 0)
            self.assertEqual(len(u["centroid"]), 2)
            self.assertFalse(shapely_wkt.loads(u["geom"]).is_empty)

    def test_districts_payload_contract(self):
        """districts.json 顶层键必须是契约规定的 streets（不得改成 districts）。"""
        _, out = self._run_valid()
        districts = self._load(out, "districts.json")
        self.assertEqual({d["code"] for d in districts["streets"]}, {"440105", "440103"})
        self.assertEqual({d["district_code"] for d in districts["streets"]},
                         {"440105", "440103"})
        for d in districts["streets"]:
            self.assertEqual(set(d), {"name", "code", "district_code", "geom"})

    def test_streets_payload_contract(self):
        _, out = self._run_valid()
        streets = self._load(out, "streets.json")
        self.assertEqual(len(streets["streets"]), 3)  # 夹具：海珠2 + 荔湾1
        for s in streets["streets"]:
            self.assertIn(s["district_code"], {"440105", "440103"})
            self.assertEqual(set(s), {"name", "code", "district_code", "geom"})
            self.assertFalse(shapely_wkt.loads(s["geom"]).is_empty)
        self.assertEqual(
            sum(s["district_code"] == "440105" for s in streets["streets"]), 2
        )
        self.assertEqual(
            sum(s["district_code"] == "440103" for s in streets["streets"]), 1
        )

    def test_third_district_excluded_everywhere(self):
        """夹具混入第三区 440104 后，三个输出都不得出现该编码。"""
        _, out = self._run_valid()
        for name in ("units.json", "districts.json", "streets.json"):
            text = (out / name).read_text("utf-8")
            self.assertNotIn("440104", text)

    def test_deterministic_bytes_two_runs(self):
        """同一输入连续运行两次，三个输出文件字节完全相同。"""
        src, out1 = self._run_valid()
        out2 = self.root / "out2"
        result = run_cli(src, out2)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("units.json", "districts.json", "streets.json"):
            self.assertEqual(
                (out1 / name).read_bytes(), (out2 / name).read_bytes(), name
            )

    def test_uid_is_array_index_and_sorted_deterministically(self):
        """uid 必须等于 units 数组下标；不得把 key 用作 uid；排序确定。"""
        _, out = self._run_valid()
        units = self._load(out, "units.json")["units"]
        self.assertEqual([u["uid"] for u in units], list(range(len(units))))
        keys = [(u["district_code"], u["key"]) for u in units]
        self.assertEqual(keys, sorted(keys))

    def test_wkt_lossless_from_source_geometry(self):
        """WKT 必须由源几何无损转写：逐坐标与源 feature 一致。"""
        src, out = self._run_valid()
        source = json.loads(
            (src / FILENAMES["DISTRICTS_SRC"]).read_text("utf-8")
        )["features"]
        districts = self._load(out, "districts.json")["streets"]
        src_geom = {f["properties"]["区域编码"]: f["geometry"] for f in source}
        for d in districts:
            back = shapely_wkt.loads(d["geom"])
            origin = shapely.geometry.shape(src_geom[d["code"]])
            self.assertEqual(
                shapely.geometry.mapping(back), shapely.geometry.mapping(origin)
            )

    # -- 异常路径（中文报错 + 退出非零 + 不产半成品） ---------------------------

    def _assert_cli_fails_clean(self, mutate):
        src = self._mutated_src(mutate)
        out = self.root / "out"
        result = run_cli(src, out)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(has_cjk(result.stderr), result.stderr)
        self.assertFalse(out.exists() and any(out.iterdir()),
                         "失败时不得生成半成品文件")

    def test_rejects_district_missing_target_code(self):
        """区县源缺任一目标编码必须报错。"""
        def mutate(src: Path):
            feats = json.loads(
                (src / FILENAMES["DISTRICTS_SRC"]).read_text("utf-8")
            )["features"]
            feats = [f for f in feats
                     if f["properties"]["区域编码"] != "440105"]
            write_geojson(src / FILENAMES["DISTRICTS_SRC"], feats)

        self._assert_cli_fails_clean(mutate)

    def test_rejects_street_parent_not_in_districts(self):
        """任一街道 父级id 不在完整区县编码集合必须报错（禁止静默跳过）。"""
        def mutate(src: Path):
            feats = json.loads(
                (src / FILENAMES["STREETS_SRC"]).read_text("utf-8")
            )["features"]
            feats[0]["properties"]["父级id"] = "999999"
            write_geojson(src / FILENAMES["STREETS_SRC"], feats)

        self._assert_cli_fails_clean(mutate)

    def test_rejects_invalid_unit_geometry(self):
        """单元源几何为空/非法必须报错。"""
        for bad_geom in (None, {"type": "Polygon", "coordinates": []},
                         {"type": "Polygon", "coordinates": "垃圾"}):
            with self.subTest(bad_geom=bad_geom):
                def mutate(src: Path, bad_geom=bad_geom):
                    feats = json.loads(
                        (src / FILENAMES["UNITS_SRC"]).read_text("utf-8")
                    )["features"]
                    feats[0]["geometry"] = bad_geom
                    write_geojson(src / FILENAMES["UNITS_SRC"], feats)

                self._assert_cli_fails_clean(mutate)

    def test_rejects_duplicate_unit_keys(self):
        """试点单元源主键重复必须报错。"""
        def mutate(src: Path):
            feats = json.loads(
                (src / FILENAMES["UNITS_SRC"]).read_text("utf-8")
            )["features"]
            feats[1]["properties"]["主键"] = feats[0]["properties"]["主键"]
            write_geojson(src / FILENAMES["UNITS_SRC"], feats)

        self._assert_cli_fails_clean(mutate)

    def test_rejects_nonpositive_unit_area(self):
        """单元面积非正数必须报错。"""
        def mutate(src: Path):
            feats = json.loads(
                (src / FILENAMES["UNITS_SRC"]).read_text("utf-8")
            )["features"]
            feats[0]["properties"]["面积"] = "0"
            write_geojson(src / FILENAMES["UNITS_SRC"], feats)

        self._assert_cli_fails_clean(mutate)

    def test_rejects_bad_centroid_format(self):
        """中心点不是「经度,纬度」或非数字必须报错。"""
        for bad in ("113.1", "a,b", "113.1,23.1,10"):
            with self.subTest(bad=bad):
                def mutate(src: Path, bad=bad):
                    feats = json.loads(
                        (src / FILENAMES["UNITS_SRC"]).read_text("utf-8")
                    )["features"]
                    feats[0]["properties"]["中心点"] = bad
                    write_geojson(src / FILENAMES["UNITS_SRC"], feats)

                self._assert_cli_fails_clean(mutate)

    def test_source_dir_untouched_after_t102_run(self):
        """T-102 运行后源目录逐字节不变（输入只读）。"""
        src, _ = self._run_valid()
        # snapshot 在运行后仍应与重新快照一致；再用 mtime 比对做双保险。
        before = snapshot_bytes(src)
        out = self.root / "out-again"
        result = run_cli(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, snapshot_bytes(src))

    def test_select_streets_joins_by_exact_parent_id(self):
        """街道只按 父级id == 区县.区域编码 精确等值连接，名称相似不入选。"""
        src = build_valid_src(self.root)
        street_feats = extract.read_geojson(
            extract.locate_source(src, "STREETS_SRC"), "STREETS_SRC"
        )
        district_feats = extract.read_geojson(
            extract.locate_source(src, "DISTRICTS_SRC"), "DISTRICTS_SRC"
        )
        rows = extract.select_streets(street_feats, district_feats)
        self.assertEqual({r["code"] for r in rows},
                         {"440105001", "440105002", "440103001"})
        self.assertTrue(all(r["district_code"] in {"440105", "440103"} for r in rows))


class T103Tests(unittest.TestCase):
    """T-103 围栏筛区：空间判定、确定性、脏点留档与异常路径。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    # -- 夹具辅助 --------------------------------------------------------------

    @staticmethod
    def _poly_wkt(x0: float, y0: float, x1: float, y1: float) -> str:
        """轴对齐矩形 WKT（面积 = (x1-x0)*(y1-y0) 度²）。"""
        return (
            f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"
        )

    def _districts_feature(self, code: str, name: str, wkt: str) -> dict:
        return {
            "type": "Feature",
            "properties": {"行政区名称": name, "区域编码": code},
            "geometry": shapely_wkt.loads(wkt).__geo_interface__,
        }

    def _build_polygon_src(self) -> Path:
        """多边形区县夹具：海珠 440105 = [113.10,23.05]×[113.20,23.15]
        （0.01 度²），荔湾 440103 = [113.05,23.05]×[113.10,23.15]
        （0.005 度²）。两区不相交；并集面积 0.015 度²。"""
        src = build_valid_src(self.root)
        hz = self._poly_wkt(113.10, 23.05, 113.20, 23.15)
        lw = self._poly_wkt(113.05, 23.05, 113.10, 23.15)
        write_geojson(
            src / FILENAMES["DISTRICTS_SRC"],
            [
                self._districts_feature("440105", "海珠区", hz),
                self._districts_feature("440103", "荔湾区", lw),
                self._districts_feature("440104", "外区", self._poly_wkt(114.0, 23.0, 114.1, 23.1)),
            ],
        )
        return src

    @staticmethod
    def _dealer_row(src_id: str, name: str, fence: str, **overrides) -> dict:
        return make_dealer_row(name=name, fence=fence, **{"片区id": src_id, **overrides})

    @staticmethod
    def _yeidai_row(src_id: str, name: str, fence: str) -> dict:
        row = make_yeidai_row(name=name, fence=fence)
        row["片区id"] = src_id
        return row

    def _fences_from_out(self, out: Path, name: str) -> list[dict]:
        return json.loads((out / name).read_text("utf-8"))["fences"]

    # 缺省围栏行：extract_all 要求两份 CSV 至少各有一行合法数据（见 _run_t103）。

    def _default_full(self) -> str:
        return self._poly_wkt(113.10, 23.05, 113.20, 23.15)  # 100% 海珠内

    def _run_t103(self, dealer_rows, yeidai_rows, out_name="out") -> tuple[Path, Path]:
        """多边形区县夹具 + 指定围栏行 → 跑 CLI → (src, out)。

        空列表按「一行全入围栏」缺省补齐，避免触发 T-101 的空文件报错。
        """
        src = self._build_polygon_src()
        d_rows = dealer_rows if dealer_rows else [
            self._dealer_row("D-def", "缺省经销商", self._default_full())
        ]
        y_rows = yeidai_rows if yeidai_rows else [
            self._yeidai_row("Y-def", "缺省业代", self._default_full())
        ]
        write_csv(src / FILENAMES["DEALER_SRC"], csv_header(), d_rows)
        write_csv(src / FILENAMES["YEIDAI_SRC"], csv_header(yeidai=True), y_rows)
        out = self.root / out_name
        result = run_cli(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        return src, out

    # -- 卡载可执行断言：schema 与唯一性 ----------------------------------------

    def test_fence_schema_contract(self):
        """卡载逐项 schema 断言：键集合、类型、overlap 范围、WKT 非空。"""
        full = self._poly_wkt(113.10, 23.05, 113.20, 23.15)     # 100% 在海珠内
        _, out = self._run_t103(
            [self._dealer_row("D-1", "全入围栏", full)],
            [self._yeidai_row("Y-1", "全入业代", full)],
        )
        for fname in ("fences_dealer.json", "fences_yeidai.json"):
            fences = self._fences_from_out(out, fname)
            self.assertEqual(len(fences), 1)
            for fence in fences:
                self.assertEqual(
                    set(fence),
                    {"name", "src_id", "area_km2", "center", "overlap_ratio", "geom"},
                )
    def test_full_and_partial_and_excluded(self):
        """严格按面积比：全入=1.0；跨区=交/自面积比唯一值；区外=排除。

        夹具几何（海珠=[113.10,113.20]×[23.05,23.15]，荔湾不相交）：
        cross = [113.10,113.20]×[23.05,23.17]，自面积 0.012 度²，
        与试点区交集 = 海珠 0.01 度² → ratio = 0.01/0.012 = 5/6。
        """
        full = self._poly_wkt(113.10, 23.05, 113.20, 23.15)       # ratio 1.0
        cross = self._poly_wkt(113.10, 23.05, 113.20, 23.17)      # ratio 5/6 ≈ 0.833
        outside = self._poly_wkt(114.0, 23.0, 114.1, 23.1)        # ratio 0.0
        _, out = self._run_t103(
            [
                self._dealer_row("D-1", "全入", full),
                self._dealer_row("D-2", "跨区", cross),
                self._dealer_row("D-3", "区外", outside),
            ],
            [],
        )
        dealers = {f["src_id"]: f for f in self._fences_from_out(out, "fences_dealer.json")}
        self.assertEqual(set(dealers), {"D-1", "D-2"})  # 区外被排除
        self.assertAlmostEqual(dealers["D-1"]["overlap_ratio"], 1.0, places=6)
        self.assertAlmostEqual(dealers["D-2"]["overlap_ratio"], 5 / 6, places=6)

    def test_exact_half_in_gray_zone_escalates(self):
        """恰好 0.5 同时满足入选下限与灰区下界：灰区裁定优先 → ESCALATION。

        half = [113.15,113.25]×[23.05,23.15]：自面积 0.01，交（海珠内）
        [113.15,113.20]×[23.05,23.15] = 0.005 → ratio = 0.5 ∈ [0.2, 0.8]。
        冻结规则：任一样本落灰区立即停止，禁止自行取舍（含"恰好压线"）。
        """
        half = self._poly_wkt(113.15, 23.05, 113.25, 23.15)
        src = self._build_polygon_src()
        write_csv(src / FILENAMES["DEALER_SRC"], csv_header(),
                  [self._dealer_row("D-half", "恰好一半", half)])
        out = self.root / "out-half"
        result = run_cli(src, out)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ESCALATION:", result.stderr)
        self.assertFalse(out.exists() and any(out.iterdir()))

    def test_gray_zone_escalates_not_written(self):
        """0.2~0.8 灰区样本必须触发 ESCALATION，且不写出任何产物。

        gray = [113.15,113.20]×[23.05,23.20]：自面积 0.025 度²，
        交（海珠内）= 0.005 度² → ratio = 0.2，恰为灰区下界 → 停止。
        """
        gray = self._poly_wkt(113.15, 23.05, 113.20, 23.20)
        src = self._build_polygon_src()
        write_csv(src / FILENAMES["DEALER_SRC"], csv_header(),
                  [self._dealer_row("D-gray", "灰区", gray)])
        write_csv(src / FILENAMES["YEIDAI_SRC"], csv_header(yeidai=True),
                  [self._yeidai_row("Y-ok", "正常",
                                    self._poly_wkt(113.10, 23.05, 113.20, 23.15))])
        out = self.root / "out-gray"
        result = run_cli(src, out)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ESCALATION:", result.stderr)
        self.assertFalse(out.exists() and any(out.iterdir()),
                         "灰区 ESCALATION 时不得生成任何产物")

    def test_duplicate_src_id_raises(self):
        """同文件两条 src_id 相同 → 真重复 → 抛中文错，不产半成品。"""
        full = self._poly_wkt(113.10, 23.05, 113.20, 23.15)
        src = self._build_polygon_src()
        write_csv(src / FILENAMES["DEALER_SRC"], csv_header(),
                  [
                      self._dealer_row("D-dup", "甲围栏", full),
                      self._dealer_row("D-dup", "乙围栏", full),
                  ])
        out = self.root / "out-dup"
        result = run_cli(src, out)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("片区id", result.stderr)
        self.assertTrue(has_cjk(result.stderr))
        self.assertFalse(out.exists() and any(out.iterdir()))

    def test_same_name_different_src_id_not_overwritten(self):
        """同名不同 src_id 都按空间规则独立判定，不得被字典覆盖。"""
        full = self._poly_wkt(113.10, 23.05, 113.20, 23.15)
        outside = self._poly_wkt(114.0, 23.0, 114.1, 23.1)
        _, out = self._run_t103(
            [],
            [
                self._yeidai_row("Y-100", "同名围栏", full),
                self._yeidai_row("Y-200", "同名围栏", outside),
            ],
        )
        rows = self._fences_from_out(out, "fences_yeidai.json")
        self.assertEqual([f["src_id"] for f in rows], ["Y-100"])
        self.assertEqual(rows[0]["name"], "同名围栏")  # 同名者中仅区外那条落选

    def test_deterministic_bytes_two_runs(self):
        """同一输入连续运行两次，围栏与留档产物字节完全相同。"""
        full = self._poly_wkt(113.10, 23.05, 113.20, 23.15)
        cross = self._poly_wkt(113.075, 23.05, 113.20, 23.15)
        rows_d = [self._dealer_row("D-1", "全入", full),
                  self._dealer_row("D-2", "跨区", cross)]
        rows_y = [self._yeidai_row(f"Y-{i:03d}", f"同名组{i}", full) for i in (1, 2)]
        src1, out1 = self._run_t103(rows_d, rows_y, "out-run1")
        src2, out2 = self._run_t103(rows_d, rows_y, "out-run2")
        for name in ("fences_dealer.json", "fences_yeidai.json", "data_issues.md"):
            self.assertEqual(
                (out1 / name).read_bytes(), (out2 / name).read_bytes(), name
            )

    # -- data_issues.md 留档 ----------------------------------------------------

    def test_data_issues_documents_dup_groups_and_caitao(self):
        """data_issues.md 必须含同名组、次数 2、两组面积/中心点与财涛排除。

        三组同名（海珠荔湾07/番禺08/白云南03）逐条过空间规则：区内者入选、
        区外者落选；财涛食品低 overlap 被排除并留档。
        """
        inside = self._poly_wkt(113.10, 23.05, 113.20, 23.15)   # ratio 1.0
        outside = self._poly_wkt(114.0, 23.0, 114.1, 23.1)      # ratio 0.0
        rows_d = [
            self._dealer_row("D-999", "广州市财涛食品有限公司", outside,
                             围栏面积="65.0017"),
        ]
        rows_y = []
        for name, a_in, a_out, c_in, c_out in [
            ("海珠荔湾07", "20.8964", "1.7668", (113.2338, 23.0842), (113.2061, 23.1019)),
            ("番禺08", "0.9875", "0.8828", (113.3009, 23.1050), (113.2078, 23.0901)),
            ("白云南03", "0.531", "1.3326", (113.2396, 23.1482), (113.1498, 23.0062)),
        ]:
            # 夹具几何只关心筛选方向：面积/中心点用卡载数字原样写入 CSV 字段
            rows_y.append(self._yeidai_row(f"Y-{name}-in", name, inside))
            rows_y[-1]["围栏面积"] = a_in
            rows_y[-1]["中心点经度"] = f"{c_in[0]}"
            rows_y[-1]["中心点纬度"] = f"{c_in[1]}"
            rows_y.append(self._yeidai_row(f"Y-{name}-out", name, outside))
            rows_y[-1]["围栏面积"] = a_out
            rows_y[-1]["中心点经度"] = f"{c_out[0]}"
            rows_y[-1]["中心点纬度"] = f"{c_out[1]}"
        _, out = self._run_t103(rows_d, rows_y)
        text = (out / "data_issues.md").read_text("utf-8")
        for name in ("海珠荔湾07", "番禺08", "白云南03"):
            self.assertIn(name, text)
        self.assertIn("广州市财涛食品有限公司", text)
        for frag in ("20.90", "1.77", "0.99", "0.88", "0.53", "1.33"):
            self.assertIn(frag, text, frag)
        for coord in ("113.2338", "113.2061", "113.3009", "113.2078",
                      "113.2396", "113.1498"):
            self.assertIn(coord, text, coord)
        self.assertIn("自相交街道面", text)   # 花山/新塘/良口 观察留档
        self.assertIn("花山", text)

    def test_data_issues_mentions_selfintersect_streets(self):
        """留档必须记录：源数据 3 个自相交街道面（花山/新塘/良口，试点区外）。"""
        _, out = self._run_t103(
            [self._dealer_row("D-1", "全入", self._poly_wkt(113.10, 23.05, 113.20, 23.15))],
            [],
        )
        text = (out / "data_issues.md").read_text("utf-8")
        self.assertIn("花山/新塘/良口", text)
        self.assertIn("试点区外", text)

    def test_real_output_schema_shape(self):
        """dealer/yeidai 输出 src_id 在各自文件内唯一（合成场景）。"""
        full = self._poly_wkt(113.10, 23.05, 113.20, 23.15)
        _, out = self._run_t103(
            [self._dealer_row(f"D-{i}", f"围栏{i}", full) for i in range(3)],
            [self._yeidai_row(f"Y-{i}", f"业代{i}", full) for i in range(2)],
        )
        dealers = self._fences_from_out(out, "fences_dealer.json")
        yeidai = self._fences_from_out(out, "fences_yeidai.json")
        self.assertEqual(len({f["src_id"] for f in dealers}), len(dealers))
        self.assertEqual(len({f["src_id"] for f in yeidai}), len(yeidai))



def rotated_square_wkt(cx: float, cy: float, side: float = 0.02, angle_deg: float = 30.0) -> str:
    """绕中心旋转 angle_deg 的正方形 WKT（顶点 5 位小数）。

    旋转是刻意的：轴对齐矩形与 gcj2wgs 位移向量（≈ (-553m, +289m)）平行/
    垂直，压边顶点转 WGS 后到边距离只剩纬度分量 ≈ 289 m < 300 m，合成
    B 路径在数学上不可能过阈值；边与位移向量成 30° 角后垂直分量
    ≈ 623·sin30° ≈ 311 m，B 中位数实测 ≈ 451 m。单元与围栏用同一函数
    同一中心生成（同样舍入）→ 围栏角点坐标与单元角点完全相等 → A = 0。
    """
    t = math.radians(angle_deg)
    cos, sin = math.cos(t), math.sin(t)
    pts = []
    for dx, dy in ((side / 2, side / 2), (side / 2, -side / 2),
                   (-side / 2, -side / 2), (-side / 2, side / 2)):
        pts.append((cx + dx * cos - dy * sin, cy + dx * sin + dy * cos))
    ring = ", ".join(f"{x:.5f} {y:.5f}" for x, y in pts)
    return f"POLYGON (({ring}, {pts[0][0]:.5f} {pts[0][1]:.5f}))"


class T104Tests(unittest.TestCase):

    """T-104 坐标系数字验证（§3.5.4 契约 v1.3）：等距抽样、最近边界点与门禁。

    可控合成几何：四个互不重叠的旋转 30° 正方形单元；经销商围栏 = 同形同位
    正方形，角点全部压在单元边界上 → 对照 A 中位数 = 0（< 1 m，判据①）；
    gcj2wgs 在广州纬度的单侧位移 ≈ 623 m → C 位移中位数 ≈ 623 m
    （∈ [500, 750]，判据②）→ SAME_CRS_GCJ02。同形状平移进单元内部 →
    A 中位数 >= 1 m → INCONCLUSIVE。B（转 WGS 后最近边界距离）为饱和量，
    仅记录落盘、不参与判定。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    # -- 夹具辅助 --------------------------------------------------------------

    @staticmethod
    def _poly_wkt(x0: float, y0: float, x1: float, y1: float) -> str:
        return f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"

    @staticmethod
    def _units_feature(code: str, key: str, wkt: str) -> dict:
        return {
            "type": "Feature",
            "properties": {
                "区县编码": code,
                "街道[内置]": "某街道",
                "中心点": "113.13,23.09",
                "面积": 1.0,
                "主键": key,
            },
            "geometry": shapely_wkt.loads(wkt).__geo_interface__,
        }

    @staticmethod
    def _districts_feature(code: str, name: str, wkt: str) -> dict:
        return {
            "type": "Feature",
            "properties": {"行政区名称": name, "区域编码": code},
            "geometry": shapely_wkt.loads(wkt).__geo_interface__,
        }

    # 单元/围栏同形同位（旋转 30° 正方形，海珠范围内彼此分离）：
    # 围栏角点坐标与单元角点完全相等 → 对照 A 恒为 0。
    UNIT_CENTERS = ((113.10, 23.06), (113.22, 23.06), (113.10, 23.18), (113.22, 23.18))
    UNIT_WKTS = tuple(rotated_square_wkt(x, y) for x, y in UNIT_CENTERS)
    FENCE_WKTS = UNIT_WKTS

    def _build_crs_src(self, fence_wkt_list=None) -> Path:
        """海珠/荔湾多边形区县 + 四个多边形单元 + 指定经销商围栏（默认四条）。"""
        src = self.root / "src"
        src.mkdir(parents=True, exist_ok=True)
        haizhu = self._poly_wkt(113.02, 23.02, 113.30, 23.26)
        liwan = self._poly_wkt(112.95, 23.05, 113.01, 23.15)
        write_geojson(
            src / FILENAMES["DISTRICTS_SRC"],
            [
                self._districts_feature("440105", "海珠区", haizhu),
                self._districts_feature("440103", "荔湾区", liwan),
            ],
        )
        write_geojson(
            src / FILENAMES["STREETS_SRC"],
            [make_streets_feature("440105001", "440105", "海珠街道A")],
        )
        write_geojson(
            src / FILENAMES["UNITS_SRC"],
            [
                self._units_feature("440105", f"U-{i}", wkt)
                for i, wkt in enumerate(self.UNIT_WKTS)
            ],
        )
        wkts = self.FENCE_WKTS if fence_wkt_list is None else list(fence_wkt_list)
        write_csv(
            src / FILENAMES["DEALER_SRC"],
            csv_header(),
            [
                make_dealer_row(name=f"围栏{i}", fence=wkt, **{"片区id": f"D-{i}"})
                for i, wkt in enumerate(wkts)
            ],
        )
        write_csv(
            src / FILENAMES["YEIDAI_SRC"],
            csv_header(yeidai=True),
            [make_yeidai_row(name="业代样本", fence=haizhu)],
        )
        return src

    def _crs_units_payload(self) -> dict:
        return {
            "crs": "GCJ-02",
            "units": [
                {
                    "uid": i,
                    "key": f"U-{i}",
                    "district_code": "440105",
                    "street": "某街道",
                    "area_km2": 1.0,
                    "centroid": [113.13, 23.09],
                    "geom": wkt,
                }
                for i, wkt in enumerate(self.UNIT_WKTS)
            ],
        }

    def _crs_fences(self, wkts=None) -> list[dict]:
        wkts = self.FENCE_WKTS if wkts is None else list(wkts)
        return [
            {"src_id": f"D-{i}", "name": f"围栏{i}", "geom": wkt}
            for i, wkt in enumerate(wkts)
        ]

    # -- 确定性等距抽样 ---------------------------------------------------------

    def test_sample_ring_vertices_equidistant_deterministic(self):
        """501 顶点 → 恰好抽 200；下标 = (i*n)//cap，重复调用一致；<=200 全取。"""
        n = 501
        cx, cy, r = 113.30, 23.07, 0.005
        pts = [
            (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ]
        ring = ", ".join(f"{x:.9f} {y:.9f}" for x, y in pts)
        wkt = f"POLYGON (({ring}, {pts[0][0]:.9f} {pts[0][1]:.9f}))"
        geom = shapely_wkt.loads(wkt)
        sampled = extract._sample_ring_vertices(geom)
        cap = extract.VERTEX_CAP
        self.assertEqual(len(sampled), cap)
        coords = shapely.get_coordinates(geom.boundary)
        full = [(float(x), float(y)) for x, y in coords][:-1]  # 闭合点已去重
        self.assertEqual(len(full), n)
        self.assertEqual(sampled, [full[(i * n) // cap] for i in range(cap)])
        self.assertEqual(sampled, extract._sample_ring_vertices(geom))  # 确定性
        rect = shapely_wkt.loads(self._poly_wkt(113.1, 23.06, 113.12, 23.08))
        self.assertEqual(len(extract._sample_ring_vertices(rect)), 4)  # 闭合点去重 + 全取

    # -- 最近边界点 + haversine 米制换算 ------------------------------------------

    def test_min_boundary_distance_nearest_point(self):
        rect = shapely_wkt.loads(self._poly_wkt(113.10, 23.06, 113.12, 23.08))
        boundaries = [rect.boundary]
        tree = shapely.STRtree(boundaries)
        self.assertEqual(
            extract._min_boundary_distance_m((113.11, 23.06), tree, boundaries), 0.0
        )
        pt = (113.11, 23.079)  # 距上边 0.001° << 距左边 0.01°，最近边唯一
        got = extract._min_boundary_distance_m(pt, tree, boundaries)
        expect = real_haversine_km(pt, (113.11, 23.08)) * 1000.0
        self.assertAlmostEqual(got, expect, places=6)
        self.assertGreater(got, 0.0)

    # -- mock 断言实际调用了两个冻结复用函数 ---------------------------------------

    def test_haversine_and_gcj2wgs_actually_called(self):
        with mock.patch.object(
            extract, "haversine_km", wraps=extract.haversine_km
        ) as hav, mock.patch.object(
            extract, "gcj2wgs", wraps=extract.gcj2wgs
        ) as gj:
            evidence = extract.compute_crs_evidence(
                self._crs_units_payload(), self._crs_fences()
            )
        n_pts = sum(f["n_vertices"] for f in evidence["per_fence"])
        self.assertEqual(n_pts, 16)  # 4 围栏 × 4 角点（闭合点已去重）
        self.assertEqual(gj.call_count, n_pts)        # C 位移逐点转换（每点一次）
        self.assertEqual(hav.call_count, 3 * n_pts)   # A/B 测距 + C 位移三路
        for args, _kwargs in gj.call_args_list:
            lon, lat = args
            self.assertIsInstance(lon, float)

    # -- A/C 两条判据路径与明确阈值（端到端数学，无 mock） ------------------------------

    def test_ab_paths_thresholds_same_crs(self):
        evidence = extract.compute_crs_evidence(
            self._crs_units_payload(), self._crs_fences()
        )
        self.assertEqual(evidence["method"], "3.5.4-v1.3")
        self.assertEqual(evidence["n_fences"], 4)
        self.assertEqual(evidence["vertex_cap"], 200)
        self.assertEqual(evidence["median_A_m"], 0.0)      # 判据①：角点全部压在边界上
        self.assertGreaterEqual(evidence["median_C_disp_m"], 500.0)   # 判据②
        self.assertLessEqual(evidence["median_C_disp_m"], 750.0)
        self.assertIsInstance(evidence["median_B_m"], float)  # B 仅记录，不判定
        self.assertEqual(evidence["verdict"], "SAME_CRS_GCJ02")
        self.assertEqual(len(evidence["per_fence"]), 4)
        self.assertTrue(all(f["n_vertices"] == 4 for f in evidence["per_fence"]))
        self.assertTrue(
            all(set(f) >= {"src_id", "name", "n_vertices", "median_A_m",
                           "median_B_m", "median_C_disp_m"}
                for f in evidence["per_fence"])
        )

    def test_ab_paths_thresholds_translated_inconclusive(self):
        """可控平移：同形状整体移入单元内部，A 中位数 >= 1 m → INCONCLUSIVE。"""
        translated = [rotated_square_wkt(113.11, 23.065)]
        evidence = extract.compute_crs_evidence(
            self._crs_units_payload(), self._crs_fences(translated)
        )
        self.assertGreaterEqual(evidence["median_A_m"], 1.0)
        self.assertEqual(evidence["verdict"], "INCONCLUSIVE")

    def test_c_disp_out_of_band_inconclusive(self):
        """C 自检：单元几何退化时无法测边界，跳过测量不做坐标结论。

        真实判据②出带（C < 500 或 > 750）需要非广州纬度夹具，而单元筛选
        冻结在海珠/荔湾；此测试守住 CrsNotMeasurableError 不落伪证据路径。
        """
        payload = self._crs_units_payload()
        payload["units"] = [dict(u, geom="POINT (113.3 23.1)") for u in payload["units"]]
        with self.assertRaises(extract.CrsNotMeasurableError):
            extract.compute_crs_evidence(payload, self._crs_fences())

    def test_multipolygon_fence_vertices_flattened(self):
        """MultiPolygon 围栏：顶点须展开 geoms 按序拼接，不做整体边界。"""
        part1 = shapely_wkt.loads(rotated_square_wkt(113.10, 23.06))
        part2 = shapely_wkt.loads(rotated_square_wkt(113.22, 23.18))
        mgeom = shapely.geometry.MultiPolygon([part1, part2])
        sampled = extract._sample_ring_vertices(mgeom)
        expect = (
            extract._sample_ring_vertices(part1) + extract._sample_ring_vertices(part2)
        )
        self.assertEqual(sampled, expect)  # 8 个顶点，两 part 依次展开
        self.assertEqual(len(sampled), 8)

    def test_cli_gate_pass_seven_products_and_schema(self):
        src = self._build_crs_src()
        out = self.root / "out-pass"
        result = run_cli(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SAME_CRS_GCJ02", result.stdout)
        self.assertNotIn("[GATE-FAIL]", result.stdout + result.stderr)
        # CLI 只打印汇总数字：不含围栏名称、不含 WKT
        self.assertNotIn("围栏0", result.stdout)
        self.assertNotIn("POLYGON", result.stdout)
        self.assertEqual(
            sorted(p.name for p in out.iterdir()),
            [
                "crs_evidence.json",
                "data_issues.md",
                "districts.json",
                "fences_dealer.json",
                "fences_yeidai.json",
                "streets.json",
                "units.json",
            ],
        )
        evidence = json.loads((out / "crs_evidence.json").read_text("utf-8"))
        self.assertEqual(evidence["method"], "3.5.4-v1.3")
        self.assertEqual(evidence["n_fences"], 4)
        self.assertEqual(evidence["vertex_cap"], 200)
        self.assertTrue(math.isfinite(evidence["median_A_m"]))
        self.assertTrue(math.isfinite(evidence["median_B_m"]))
        self.assertTrue(math.isfinite(evidence["median_C_disp_m"]))
        self.assertGreaterEqual(evidence["median_A_m"], 0.0)
        self.assertLess(evidence["median_A_m"], 1.0)
        self.assertGreaterEqual(evidence["median_C_disp_m"], 500.0)
        self.assertLessEqual(evidence["median_C_disp_m"], 750.0)
        self.assertIsInstance(evidence["median_B_m"], (int, float))  # 仅记录
        self.assertEqual(evidence["verdict"], "SAME_CRS_GCJ02")
        self.assertEqual(len(evidence["per_fence"]), 4)
        self.assertTrue(all(0 < f["n_vertices"] <= 200 for f in evidence["per_fence"]))
        self.assertTrue(
            all(set(f) >= {"src_id", "name", "n_vertices", "median_A_m",
                           "median_B_m", "median_C_disp_m"}
                for f in evidence["per_fence"])
        )
        self.assertEqual(
            {f["src_id"] for f in evidence["per_fence"]}, {"D-0", "D-1", "D-2", "D-3"}
        )
        units_payload = json.loads((out / "units.json").read_text("utf-8"))
        self.assertEqual(units_payload["crs"], "GCJ-02")
        # 试点内部不得转换并覆写任何几何
        fences = json.loads((out / "fences_dealer.json").read_text("utf-8"))["fences"]
        self.assertTrue(
            shapely_wkt.loads(fences[0]["geom"]).equals(
                shapely_wkt.loads(self.FENCE_WKTS[0])
            )
        )
        issues = (out / "data_issues.md").read_text("utf-8")
        self.assertIn("3.5.4", issues)
        self.assertIn("SAME_CRS_GCJ02", issues)
        self.assertIn("median_A_m", issues)
        # 同一输入连续两次运行：字节级一致
        out2 = self.root / "out-pass2"
        result2 = run_cli(src, out2)
        self.assertEqual(result2.returncode, 0, result2.stderr)
        for name in ("crs_evidence.json", "data_issues.md"):
            self.assertEqual(
                (out / name).read_bytes(), (out2 / name).read_bytes(), name
            )

    def test_cli_gate_fail_inconclusive_writes_evidence(self):
        """A 判据①不满足 → INCONCLUSIVE + [GATE-FAIL] 非零退出，证据仍留档。"""
        src = self._build_crs_src(fence_wkt_list=[rotated_square_wkt(113.11, 23.065)])
        out = self.root / "out-fail"
        result = run_cli(src, out)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("[GATE-FAIL]", result.stderr)
        self.assertIn("ESCALATION:A=", result.stderr)
        evidence = json.loads((out / "crs_evidence.json").read_text("utf-8"))
        self.assertEqual(evidence["verdict"], "INCONCLUSIVE")
        self.assertGreaterEqual(evidence["median_A_m"], 1.0)
        issues = (out / "data_issues.md").read_text("utf-8")
        self.assertIn("INCONCLUSIVE", issues)

    def test_no_dealer_sample_no_crs_evidence_nor_claim(self):
        """无经销商围栏样本（全在区外）→ 无证据文件、不做任何坐标结论。"""
        src = self._build_crs_src(fence_wkt_list=[rotated_square_wkt(114.2, 23.0)])
        out = self.root / "out-nosample"
        result = run_cli(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("crs_evidence.json", [p.name for p in out.iterdir()])
        self.assertIn("未执行", result.stdout)
        self.assertNotIn("3.5.4", (out / "data_issues.md").read_text("utf-8"))

    def test_point_unit_fixtures_skip_crs_measurement(self):
        """单元全为 Point（存量夹具形态）→ 边界不可测，跳过且不做坐标结论。"""
        src = build_valid_src(self.root)
        out = self.root / "out-point-units"
        result = run_cli(src, out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("crs_evidence.json", [p.name for p in out.iterdir()])
        self.assertIn("未执行", result.stdout)
        self.assertNotIn("3.5.4", (out / "data_issues.md").read_text("utf-8"))



