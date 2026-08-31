#!/usr/bin/env python3
"""领地编译器 v3.1 —— 薄适配层（核心已抽取至 territory-ir 独立项目）。

本文件只做两件事：
1. 引入 territory_ir 并把广州数据集安装进模块全局（兼容 tc.U / tc.compile_fence 等旧访问）；
2. 保留命令行批编译入口（行为与旧版一致）。

核心实现见 ~/territory-ir（territory_ir/Dataset）。
"""
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_TIR = Path(os.environ.get("TIR_HOME", Path.home() / "territory-ir"))
if str(_TIR) not in sys.path:
    sys.path.insert(0, str(_TIR))
sys.path.insert(0, str(_ROOT))

from territory_ir.dataset import Dataset  # noqa: E402

DATA = str(_ROOT / "data" / "gz")
ds = Dataset.guangzhou(data_dir=DATA)
ds.install(globals())

if __name__ == "__main__":
    rows = []
    fences = [f for f in reg["fences"] if "佛山" not in f["dealer"]]
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for k, f in enumerate(fences):
        if only and only not in f["dealer"]:
            continue
        try:
            r = compile_fence(f)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            r = {"dealer": f["dealer"], "area_id": f["area_id"],
                 "human_terms": [f"ERROR {type(e).__name__}: {e}"],
                 "engine_terms": [], "engine_J": 0, "engine_hit": 0,
                 "engine_over": 0, "engine_miss": 0, "truth_pieces": 0,
                 "iou": 0, "cover": 0, "km2": f.get("area_km2", 0),
                 "T": [], "S": [], "ir": {}}
        rows.append(r)
        print(f"[{k+1}] {f['dealer'][:16]:<16} 人话{len(r['human_terms'])}句 "
              f"引擎{len(r['engine_terms'])}词 J={r['engine_J']:.2f} "
              f"over={r['engine_over']} miss={r['engine_miss']} "
              f"IoU={r['iou']:.3f} 覆盖={r['cover']}%")
    if not only:
        json.dump(rows, open(f"{DATA}/territory_compiled.json", "w"),
                  ensure_ascii=False, indent=1)
        import statistics
        print(f"\n=== {len(rows)}条 ===")
        print(f"引擎J中位: {statistics.median(r['engine_J'] for r in rows):.3f}  "
              f"J=1.0: {sum(1 for r in rows if r['engine_J'] == 1.0)}/{len(rows)}")
        print("saved territory_compiled.json")
    else:
        json.dump(rows, open("/tmp/compile_test.json", "w"),
                  ensure_ascii=False, indent=1)
