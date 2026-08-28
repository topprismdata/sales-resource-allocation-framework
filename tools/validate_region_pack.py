#!/usr/bin/env python3
"""区域数据包校验器：换数据前先跑这个，坏包快速失败并给出明确原因。

用法: python3 tools/validate_region_pack.py data/<region>
退出码: 0 = 合法; 1 = 有问题（逐条列出）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_STORE_FIELDS = ("n", "c", "d", "u", "lon", "lat", "direct", "dealers", "kind")
REQUIRED_FENCE_FIELDS = ("area_id", "dealer", "area_km2", "rings")
REQUIRED_CONTRACT_FIELDS = ("dealer_id", "district", "four_bounds", "center",
                            "reserved_channels", "store_count")
VALID_KINDS = {"OK", "OOF", "DIRECT_IN", "DIRECT", "GAP", "MULTI"}
REQUIRED_META_FIELDS = ("region_name", "center", "zoom")


def main(data_dir: str) -> int:
    p = Path(data_dir)
    errs: list[str] = []
    if not p.is_dir():
        print(f"✗ 目录不存在: {p}")
        return 1

    # region.json
    rp = p / "region.json"
    if not rp.exists():
        errs.append("缺 region.json（fences+stores+kinds）")
    else:
        d = json.loads(rp.read_text(encoding="utf-8"))
        fences, stores = d.get("fences", []), d.get("stores", [])
        if not fences:
            print("⚠ fences 为空：greenfield 区域（围栏将由合同生成）——允许")
        if not stores:
            errs.append("region.json.stores 为空")
        for i, f in enumerate(fences):
            miss = [k for k in REQUIRED_FENCE_FIELDS if k not in f]
            if miss:
                errs.append(f"fences[{i}] 缺字段 {miss}")
                break
        for i, s in enumerate(stores):
            miss = [k for k in REQUIRED_STORE_FIELDS if k not in s]
            if miss:
                errs.append(f"stores[{i}] ({s.get('n','?')}) 缺字段 {miss}")
                break
            if s.get("kind") not in VALID_KINDS:
                errs.append(f"stores[{i}] ({s.get('n','?')}) kind 非法: {s.get('kind')}（合法: {sorted(VALID_KINDS)}）")
                break
            try:
                float(s["lon"]); float(s["lat"])
            except (TypeError, ValueError):
                errs.append(f"stores[{i}] ({s.get('n','?')}) 经纬度非法")
                break
        kinds = d.get("kinds", {})
        kinds_sum = sum(kinds.values()) if isinstance(kinds, dict) else 0
        if isinstance(kinds, dict) and kinds_sum != len(stores):
            errs.append(f"kinds 计数({kinds_sum}) != stores 数({len(stores)})")

    # contracts.json
    cp = p / "contracts.json"
    if not cp.exists():
        errs.append("缺 contracts.json（合同包）")
    else:
        cs = json.loads(cp.read_text(encoding="utf-8"))
        if not isinstance(cs, list) or not cs:
            errs.append("contracts.json 应为非空数组")
        else:
            for i, c in enumerate(cs):
                miss = [k for k in REQUIRED_CONTRACT_FIELDS if k not in c]
                if miss:
                    errs.append(f"contracts[{i}] 缺字段 {miss}")
                    break
            # 合同 dealer 与 region 围栏对得上吗（软检查：有合同没围栏 → 提示）
            if rp.exists():
                dealer_set = {f.get("dealer") for f in fences}
                orphan = [c["dealer_id"] for c in cs if c["dealer_id"] not in dealer_set]
                if orphan:
                    print(f"⚠ {len(orphan)} 份合同无对应围栏（greenfield，生成走草案）: "
                          + "、".join(o[:14] for o in orphan[:5]))

    # osm_parsed.json（四至重建需要；无则生成功能降级）
    op = p / "osm_parsed.json"
    if not op.exists():
        print("⚠ 无 osm_parsed.json：四至重建不可用（可由 fetch_region_osm + parse_osm_raw 生成）")
    else:
        o = json.loads(op.read_text(encoding="utf-8"))
        for k in ("districts", "rivers", "roads"):
            if k not in o:
                errs.append(f"osm_parsed.json 缺 {k}")

    # meta.json
    mp = p / "meta.json"
    meta = {}
    if mp.exists():
        meta = json.loads(mp.read_text(encoding="utf-8"))
        miss = [k for k in REQUIRED_META_FIELDS if k not in meta]
        if miss:
            errs.append(f"meta.json 缺字段 {miss}")
    else:
        errs.append("缺 meta.json（region_name/center/zoom）")

    for e in errs:
        print("✗", e)
    if errs:
        return 1
    print(f"✓ 数据包合法: {meta.get('region_name', p.name)} · "
          f"{len(fences)} 围栏 / {len(stores)} 门店 / {len(cs)} 合同")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/gz"))
