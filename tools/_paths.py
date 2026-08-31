#!/usr/bin/env python3
"""统一路径解析——消灭硬编码用户目录。

优先级：显式参数 > 环境变量 SRAF_DATA_DIR > <仓库根>/data/gz
仓库根由 __file__ 推导，不依赖任何用户名。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # tools/ 的上一级 = 仓库根


def data_dir(arg: str | None = None) -> Path:
    if arg:
        return Path(arg)
    env = os.environ.get("SRAF_DATA_DIR")
    if env:
        return Path(env)
    return ROOT / "data" / "gz"


DATA = str(data_dir())                                  # 兼容既有 f"{DATA}/x.json" 写法
SOURCE = data_dir() / "source"                          # 原 ~/Downloads 的 geojson 落点
