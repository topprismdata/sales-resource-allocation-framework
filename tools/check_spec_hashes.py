#!/usr/bin/env python3
"""SRAF 规范哈希门禁：校验 docs/sraf/SHA256SUMS.md 与规范文件实际内容一致。

仅用标准库。对 docs/sraf/ 下所有 *.md 检查三类漂移：
  MISSING        清单登记了文件，但 docs/sraf/ 下不存在（可能被移动/删除）
  HASH_MISMATCH  登记哈希与实际 sha256 不一致（规范被改动）
  UNLISTED       docs/sraf/ 下存在但未登记的 .md（新规范未入清单）
  DUPLICATE      清单中同一文件名出现多次

任一漂移 → exit 1 并列出差异；全部一致 → exit 0。
注意：SHA256SUMS.md 自身不登记（自引用不可能），工具跳过它。

用法：
    python tools/check_spec_hashes.py [--spec-dir docs/sraf]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

MANIFEST_NAME = "SHA256SUMS.md"
LINE_RE = re.compile(r"^`([0-9a-fA-F]{64})`\s+`([^`]+)`\s*$")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_manifest(manifest: Path) -> list[tuple[str, str]]:
    """解析清单行：`<sha256>`  `<文件名>` → [(hash, name), …]。"""
    entries = []
    for lineno, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith(("#", ">")):
            continue
        m = LINE_RE.match(line)
        if not m:
            raise ValueError(f"{manifest}:{lineno}: 无法解析清单行: {line!r}")
        entries.append((m.group(1).lower(), m.group(2)))
    return entries


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--spec-dir", type=Path, default=repo_root / "docs" / "sraf")
    args = parser.parse_args(argv)
    spec_dir: Path = args.spec_dir

    manifest = spec_dir / MANIFEST_NAME
    if not manifest.is_file():
        print(f"[SPEC-HASH-GATE] FAIL: 清单不存在: {manifest}")
        return 1
    try:
        entries = parse_manifest(manifest)
    except ValueError as exc:
        print(f"[SPEC-HASH-GATE] FAIL: {exc}")
        return 1
    if not entries:
        print(f"[SPEC-HASH-GATE] FAIL: 清单为空: {manifest}")
        return 1

    problems: list[str] = []
    listed: dict[str, str] = {}
    for expected, name in entries:
        if name in listed:
            problems.append(f"DUPLICATE     {name}（清单登记两次）")
            continue
        listed[name] = expected
        target = spec_dir / name
        if not target.is_file():
            problems.append(f"MISSING       {name}"
                            f"（清单哈希 {expected[:12]}…，文件不在 {spec_dir}）")
            continue
        actual = sha256_of(target)
        if actual != expected:
            problems.append(f"HASH_MISMATCH {name}\n"
                            f"    清单: {expected}\n"
                            f"    实际: {actual}")

    for md in sorted(spec_dir.glob("*.md")):
        if md.name == MANIFEST_NAME or md.name in listed:
            continue
        problems.append(f"UNLISTED      {md.name}"
                        f"（实际哈希 {sha256_of(md)[:12]}…，未入清单）")

    print(f"[SPEC-HASH-GATE] 清单 {manifest}：{len(entries)} 条登记，"
          f"目录内 {sum(1 for _ in spec_dir.glob('*.md')) - 1} 份 .md")
    if problems:
        print(f"[SPEC-HASH-GATE] FAIL: {len(problems)} 处漂移：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("[SPEC-HASH-GATE] OK: 全部规范文件哈希一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
