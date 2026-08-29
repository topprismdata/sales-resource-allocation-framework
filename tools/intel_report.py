"""三问 CLI：tools 入口，输出人读报告（L5 模板解释，非 LLM）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intelligence.classify import classify_gap          # noqa: E402
from intelligence.health import run_q1                   # noqa: E402
from intelligence.impact import move_impact              # noqa: E402
from intelligence.knowledge import KnowledgeBase         # noqa: E402
from intelligence.world import World                     # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="SRAF 分配智能层 MVP 三问")
    ap.add_argument("--q1", action="store_true", help="围栏健康报告")
    ap.add_argument("--q2", action="store_true", help="缺口五分类")
    ap.add_argument("--q3", action="store_true", help="调整影响模拟")
    ap.add_argument("--fence", help="Q3: source 围栏经销商名（子串匹配）")
    ap.add_argument("--target", help="Q3: target 围栏经销商名（子串匹配）")
    ap.add_argument("--district", help="Q3: 按区选被移动门店")
    ap.add_argument("--out", help="结果 JSON 输出路径")
    args = ap.parse_args()

    kb = KnowledgeBase()
    world = World()
    result: dict = {"kb_version": kb.version}

    if args.q1:
        reports = run_q1(world, kb)
        result["q1"] = reports
        print(f"Q1 围栏健康: {len(reports)} 份")
        for r in reports[:8]:
            print(f"  [{r['verdict']}] {r['dealer'][:16]} 店={r['stores']} "
                  f"OK={r['ok_rate']:.0%} OOF={r['oof_rate']:.0%} "
                  f"top区={r['top_district']}")

    if args.q2:
        res = classify_gap(world, kb)
        result["q2"] = res
        s = res["summary"]
        print(f"Q2 缺口五分类: 共 {s['total_gaps']} 家")
        print(f"  按类: {s['by_class']}")
        print(f"  按层: {s['by_layer']}  结构性: {s['structural']}")

    if args.q3:
        if not (args.fence and args.target):
            ap.error("--q3 需要 --fence 与 --target")
        src = [f for f in world.fences if args.fence in f.dealer]
        tgt = [f for f in world.fences if args.target in f.dealer]
        # D14: 一个经销商可能有多块围栏，按去重后的经销商数判歧义
        sd, td = {f.dealer for f in src}, {f.dealer for f in tgt}
        if len(sd) != 1 or len(td) != 1:
            ap.error(f"匹配歧义: source={len(sd)} target={len(td)}，请用更长子串")
        if not src or not tgt:
            ap.error("未找到匹配的围栏")
        stores = world.fence_stores(src[0])
        if args.district:
            stores = [s for s in stores if s.district == args.district]
        rep = move_impact(world, src[0], tgt[0], stores, kb)
        result["q3"] = rep
        print(f"Q3 影响模拟: {rep['action']}")
        print(f"  source 调整后: {rep['source_after']['stores']} 店 {rep['source_after']['kinds']}")
        print(f"  target 调整后: {rep['target_after']['stores']} 店 {rep['target_after']['kinds']}")
        print(f"  moved kind 变化: {rep['moved_kind_delta']}")
        for s in rep["signals"]:
            print(f"  [signal] {s['signal']}")

    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"已写出 {args.out}")
    if not (args.q1 or args.q2 or args.q3):
        ap.error("至少指定 --q1/--q2/--q3 之一")


if __name__ == "__main__":
    main()
