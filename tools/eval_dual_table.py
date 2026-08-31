#!/usr/bin/env python3
"""Generate the Phase 5 ceiling / cross-module evaluation report.

The report deliberately reads the compiler's existing derived artifact and
replays only the independent Ledger resolution path.  It does not modify the
compiler, the Ledger, or any data-pack artifact.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from allocation_ledger import Ledger  # noqa: E402


DISCLAIMER = """⚠ 本报告不含真实客户合同语料。
表 A 为几何天花板（给定正确输入时机制的复现上限），非端到端能力。
表 B 的描述文本由系统自身生成（territory_compile.verbalize），
   非客户合同原文；其结果反映【生成描述→独立解析器】链路的损失，
   不得表述为「在真实客户合同上的端到端能力」。
J_selfcover 为自证指标（以答案造词再比答案），恒为 1.0，不得对外引用。
覆盖率：35/70 —— 另 35 条围栏因单元库仅覆盖广州而完全无法编译。"""

MODE_ORDER = (
    "界带表达（X至A—B界 / X至行政区界）",
    "“一带”表述触发模糊匹配",
    "沿路/地物词无法命中索引",
    "其他解析失败",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def data_dir() -> Path:
    configured = os.environ.get("SRAF_DATA_DIR")
    return Path(configured) if configured else ROOT / "data" / "gz"


def classify_failure(term: str) -> str:
    if "至" in term and term.endswith("界"):
        return MODE_ORDER[0]
    if term.endswith("一带"):
        return MODE_ORDER[1]
    if "沿" in term:
        return MODE_ORDER[2]
    return MODE_ORDER[3]


def failure_area(dealer: str) -> str:
    if "珠海" in dealer:
        return "珠海"
    if "中山" in dealer:
        return "中山"
    if "韶关" in dealer:
        return "韶关"
    if "始兴" in dealer:
        return "始兴"
    return "其他"


def fmt_term(term: str) -> str:
    return term.replace("|", "／").replace("\n", " ")


def failure_examples(failures: list[dict]) -> str:
    if not failures:
        return "—"
    counts = Counter(item["term"] for item in failures)
    parts = []
    for term, count in counts.items():
        suffix = f"（{count}次）" if count > 1 else ""
        parts.append(f"{fmt_term(term)}{suffix}")
    return "；".join(parts)


def measure_l1(rows: list[dict], ledger: Ledger) -> tuple[list[dict], Counter, dict[str, set[int]]]:
    results = []
    mode_counts = Counter()
    mode_rows: dict[str, set[int]] = defaultdict(set)

    for row_index, row in enumerate(rows):
        truth = {int(unit_id) for unit_id in row.get("T", [])}
        resolved = set()
        failures = []
        for term in row.get("human_terms", []) or []:
            term = str(term)
            failed_this_term = False
            try:
                units = {int(unit_id) for unit_id in ledger.resolve_units(term)}
            except Exception as exc:  # A failed term is evidence for this measurement.
                units = set()
                failures.append({"term": term, "error": type(exc).__name__})
                failed_this_term = True
            if not units:
                if not failed_this_term:
                    failures.append({"term": term, "error": "empty"})
            else:
                resolved.update(units)

        union = truth | resolved
        jaccard = len(truth & resolved) / len(union) if union else 0.0
        for failure in failures:
            mode = classify_failure(failure["term"])
            failure["mode"] = mode
            mode_counts[mode] += 1
            mode_rows[mode].add(row_index)
        results.append(
            {
                "row": row,
                "truth_count": len(truth),
                "resolved_count": len(resolved),
                "jaccard": jaccard,
                "failures": failures,
            }
        )

    return results, mode_counts, mode_rows


def bucket(value: float, thresholds: tuple[tuple[str, float, float | None], ...]) -> str:
    for label, lower, upper in thresholds:
        if value >= lower and (upper is None or value < upper):
            return label
    raise ValueError(f"value outside distribution buckets: {value}")


def distribution_rows(values: list[float], thresholds: tuple[tuple[str, float, float | None], ...]):
    counts = Counter(bucket(value, thresholds) for value in values)
    return [(label, counts[label]) for label, _, _ in thresholds]


def build_report(rows: list[dict], l1_results: list[dict], mode_counts: Counter,
                 mode_rows: dict[str, set[int]]) -> str:
    has_t = [bool(row.get("T")) for row in rows]
    has_s = [bool(row.get("S")) for row in rows]
    if len(rows) != 70:
        raise ValueError(f"编译产物应为70行，实际为{len(rows)}行")
    if has_t != has_s:
        raise ValueError("T/S 可编译口径不一致，拒绝生成双表")

    compiled = [row for row in rows if row.get("S")]
    failed = [row for row in rows if not row.get("S")]
    if len(compiled) != 35 or len(failed) != 35:
        raise ValueError(f"可编译/失效围栏应为35/35，实际为{len(compiled)}/{len(failed)}")
    selfcover = [float(row["engine_J"]) for row in compiled]
    if any(value != 1.0 for value in selfcover):
        raise ValueError("可编译样本的 engine_J 不全为1.0，拒绝按冻结事实生成报告")

    ious = [float(row["iou"]) for row in compiled]
    covers = [float(row["cover"]) for row in compiled]
    area_counts = Counter(failure_area(str(row["dealer"])) for row in failed)
    expected_areas = Counter({"珠海": 13, "中山": 7, "韶关": 3, "始兴": 1, "其他": 11})
    if area_counts != expected_areas:
        raise ValueError(f"失效归属地分布与契约实测不一致: {dict(area_counts)}")

    iou_buckets = (
        ("<0.80", 0.0, 0.80),
        ("0.80–<0.90", 0.80, 0.90),
        ("0.90–<0.95", 0.90, 0.95),
        ("0.95–<0.99", 0.95, 0.99),
        ("0.99–<1.00", 0.99, 1.00),
        ("=1.00", 1.00, None),
    )
    cover_buckets = (
        ("<80%", 0.0, 80.0),
        ("80–<90%", 80.0, 90.0),
        ("90–<95%", 90.0, 95.0),
        ("95–<99%", 95.0, 99.0),
        ("99–<100%", 99.0, 100.0),
        ("=100%", 100.0, None),
    )

    lines = [
        DISCLAIMER,
        "",
        "## 表 A —— 几何天花板（确定性，非端到端）",
        "",
        "样本口径：70 条编译产物记录中，35 条有 S 片、35 条完全无法编译。",
        "",
        "| 指标 | 中位数 | 最小值 | 最大值 |",
        "|---|---:|---:|---:|",
        f"| IoU | {statistics.median(ious):.4f} | {min(ious):.4f} | {max(ious):.4f} |",
        f"| cover (%) | {statistics.median(covers):.2f}% | {min(covers):.2f}% | {max(covers):.2f}% |",
        "",
        "分布（35 条可编译围栏）：",
        "",
        "| 指标 | 区间 | 条数 |",
        "|---|---|---:|",
    ]
    lines.extend(f"| IoU | {label} | {count} |" for label, count in distribution_rows(ious, iou_buckets))
    lines.extend(f"| cover (%) | {label} | {count} |" for label, count in distribution_rows(covers, cover_buckets))
    lines.extend(
        [
            "",
            f"`J_selfcover = engine_J = {selfcover[0]:.4f}`（35/35）。这是自证指标，`synth` 以 T 为输入生成表达式再比 T，恒为 1.0，不度量还原能力，不得对外引用。",
            "",
            "覆盖率：35/70（可编译35条，失效35条）。失效围栏归属地分布：",
            "",
            "| 归属地 | 失效围栏数 |",
            "|---|---:|",
        ]
    )
    for area in ("珠海", "中山", "韶关", "始兴", "其他"):
        lines.append(f"| {area} | {area_counts[area]} |")
    lines.extend(
        [
            "| 合计 | 35 |",
            "",
            "本表衡量「单元库能多好地逼近手绘围栏几何」，不是「文本能多好地还原围栏」。",
            "",
            "## 表 B —— 跨模块反解（L1，语料为自动生成）",
            "",
            "测量链路：`human_terms` → `Ledger.resolve_units` → 单元集，与几何计算得到的 T 求 Jaccard。生成方为 `territory_compile.verbalize()`，解析方为 `allocation_ledger.resolve_units()`；两条代码路径独立，T 不由解析器生成。",
            "",
            "限制：本表是 L1 跨模块反解，不是 L2 真实端到端；描述文本由系统自身生成，不是客户合同原文。结果只反映「生成描述→独立解析器」链路的损失，不得表述为真实客户合同上的能力。",
            "",
            "| 围栏 | 人话句数 | len(T) | 解出数 | Jaccard | 解析失败词数 | 失败示例 |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for result in l1_results:
        row = result["row"]
        label = f"{row['dealer']}（{row['area_id']}）[自动生成语料]"
        lines.append(
            f"| {fmt_term(label)} | {len(row.get('human_terms', []) or [])} | "
            f"{result['truth_count']} | {result['resolved_count']} | "
            f"{result['jaccard']:.4f} | {len(result['failures'])} | "
            f"{failure_examples(result['failures'])} |"
        )

    jaccards = [result["jaccard"] for result in l1_results]
    total_failures = sum(mode_counts.values())
    lines.extend(
        [
            "",
            "L1 汇总（仅表 B 样本）：",
            "",
            "| 指标 | 值 |",
            "|---|---:|",
            f"| J_recall Jaccard 中位数 | {statistics.median(jaccards):.4f} |",
            f"| J_recall Jaccard 均值 | {statistics.mean(jaccards):.4f} |",
            f"| J_recall Jaccard 最小值 | {min(jaccards):.4f} |",
            f"| J_recall Jaccard 最大值 | {max(jaccards):.4f} |",
            f"| 解析失败词总数 | {total_failures} |",
            "",
            "解析失败按模式归类：",
            "",
            "| 失败模式 | 失败词数 | 影响围栏数 | 示例 |",
            "|---|---:|---:|---|",
        ]
    )
    mode_examples: dict[str, list[str]] = defaultdict(list)
    for result in l1_results:
        for failure in result["failures"]:
            mode = failure["mode"]
            term = fmt_term(failure["term"])
            if term not in mode_examples[mode]:
                mode_examples[mode].append(term)
    for mode in MODE_ORDER:
        examples = "；".join(mode_examples.get(mode, [])[:3]) or "—"
        lines.append(f"| {mode} | {mode_counts[mode]} | {len(mode_rows.get(mode, set()))} | {examples} |")
    lines.append(f"| 合计 | {total_failures} | {len(l1_results)} | — |")
    return "\n".join(lines) + "\n"


def main() -> None:
    data = data_dir()
    compiled_path = data / "territory_compiled.json"
    if not compiled_path.exists():
        raise FileNotFoundError(f"缺少编译产物：{compiled_path}")
    rows = load_json(compiled_path)
    if not isinstance(rows, list):
        raise TypeError("territory_compiled.json 顶层必须是数组")

    ledger = Ledger(data)
    compiled_rows = [row for row in rows if row.get("S")]
    l1_results, mode_counts, mode_rows = measure_l1(compiled_rows, ledger)
    report = build_report(rows, l1_results, mode_counts, mode_rows)

    target = ROOT / "cc-fix" / "verify" / "P5_REPORT.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.read_text(encoding="utf-8") != report:
        target.write_text(report, encoding="utf-8")
    print(f"P5_REPORT.md: {target}")
    print(f"表A: 可编译 {len(compiled_rows)}/{len(rows)}；表B: {len(l1_results)} 条自动生成语料")


if __name__ == "__main__":
    main()
