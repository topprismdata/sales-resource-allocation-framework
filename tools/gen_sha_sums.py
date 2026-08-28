#!/usr/bin/env python3
"""Regenerate docs/SHA256SUMS.md for the current English file set."""
import hashlib
from pathlib import Path
DOCS = Path(__file__).resolve().parent.parent / "docs"
files = sorted(p for p in DOCS.glob("*.md") if p.name != "SHA256SUMS.md")
lines = ["# SHA256 Manifest", ""]
for p in files:
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    lines.append(f"`{h}`  `{p.name}`")
(DOCS / "SHA256SUMS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"SHA256SUMS.md regenerated for {len(files)} files")
