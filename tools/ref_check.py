#!/usr/bin/env python3
"""Cross-reference checker for SRAF specs.

Every `§n` / `0X §n` / `` `0X_NAME.md` §n `` reference in docs/*.md must
resolve to an existing heading in the target file. Catches the failure mode
where a spec points at a section that does not exist (wrong doc prefix,
renumbered heading, or copy-paste drift).

Exit 0 = all references resolve. Prints one line per unresolved reference.
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
SPECS = sorted(DOCS.glob("0*.md"))
if len(SPECS) != 9:
    print(f"FAIL: expected 9 specs, found {len(SPECS)}: {[p.name for p in SPECS]}")
    sys.exit(2)

# doc number -> file
by_num = {p.name[:2]: p for p in SPECS}
SELF_DEFAULT = None  # filled during scan

HEAD_RE = re.compile(r"^#{1,6}\s+(\d{1,3}[A-Z]?)(?:\.(\d+))?[\.\、:：]?\s", re.M)


def headings(text):
    hs = set()
    for m in HEAD_RE.finditer(text):
        hs.add(m.group(1))
        if m.group(2):
            hs.add(f"{m.group(1)}.{m.group(2)}")
    return hs


HEADS = {p: headings(p.read_text(encoding="utf-8")) for p in SPECS}

# reference patterns, checked in order of specificity at each § position
#  A) `0X_....md` §n   or   0X §n   (explicit doc prefix)
#  B) §n               (same file)
DOC_PREFIX = re.compile(
    r"(?:`(0[0-8])_[A-Za-z0-9_]+\.md`|(0[0-8]))\s*§\s*"
    r"(\d{1,3}[A-Z]?(?:\.\d+)?)(?:([–-](\d{1,3}[A-Z]?(?:\.\d+)?)))?"
)
SAME_FILE = re.compile(r"§(\d{1,3}[A-Z]?)(?:\.(\d+))?(?:([–-](\d{1,3}[A-Z]?)(?:\.(\d+))?))?")

problems = []
total = 0

for p in SPECS:
    text = p.read_text(encoding="utf-8")
    # positions already consumed by an explicit-doc-prefix match
    consumed = set()
    for m in DOC_PREFIX.finditer(text):
        num = m.group(1) or m.group(2)
        consumed.update(range(m.start(), m.end()))
        target = by_num.get(num)
        for grp in (m.group(3), m.group(5) if m.group(4) else None):
            if not grp:
                continue
            total += 1
            if "." in grp:
                ok = grp in HEADS[target]
            else:
                base = re.match(r"(\d+[A-Z]?)", grp).group(1)
                ok = grp in HEADS[target] or base in HEADS[target]
            if not ok:
                line = text[:m.start()].count("\n") + 1
                problems.append(
                    f"{p.name}:{line}: `{m.group(0)}` -> §{grp} missing in {target.name}"
                )
    for m in SAME_FILE.finditer(text):
        if any(i in consumed for i in range(m.start(), min(m.end(), m.start() + 6))):
            continue
        if text[max(0, m.start() - 1):m.start()].isdigit():
            # part of an already-consumed `NN §x` token (e.g. '02 §21' where the
            # DOC_PREFIX consumed it)
            continue
        parts = [(m.group(1), m.group(2)), (m.group(4), m.group(5)) if m.group(3) else (None, None)]
        for num, sub in parts:
            if not num:
                continue
            ref = num + (f".{sub}" if sub else "")
            total += 1
            base = re.match(r"(\d+[A-Z]?)", num).group(1)
            if ref not in HEADS[p] and base not in HEADS[p]:
                line = text[:m.start()].count("\n") + 1
                problems.append(f"{p.name}:{line}: `§{ref}` missing in same file")

# bare "§" tokens not matched by either (malformed), sanity
print(f"{total} references checked")
if problems:
    print(f"{len(problems)} UNRESOLVED:")
    for x in problems:
        print("  " + x)
    sys.exit(1)
print("all references resolve")
