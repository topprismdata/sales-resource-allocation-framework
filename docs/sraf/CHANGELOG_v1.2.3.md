# SRAF Specification Changelog — v1.2.3 (documentation language normalization)

v1.2.3 is a **documentation-only** change on top of the v1.2.1
Implementation Baseline. The specs' language is normalized to **English**
across the whole repository (normative specs, governance files, design
docs, data contract, knowledge index). **Zero semantic change**: the
baseline stays **frozen** and ready for the engineering phase.

Date: 2026-08-28

## Why a patch bump

The normatively-owned content (`§` numbers, heading anchors, tables,
identifiers, invariants, benchmark cases) is byte-aligned in structure
with v1.2.1. Only natural-language wording moved from Chinese to
English. Translation was performed line-indexed with structural gates:
heading-anchor equality, table pipe-count equality, and reference
resolution must all pass before a file is accepted.

## What changed

- `docs/00–08` spec set: all Chinese prose translated to English;
  every `§N` reference target and heading number preserved.
- Governance/audit files (`README.md`, `NORMATIVE_OWNERSHIP.md`,
  `CONSISTENCY_CHECK_REPORT.md`, `PROPOSAL_v1.3_LAYER_BINDINGS.md`,
  `CHANGELOG_v1.1/v1.2/v1.2.1/v1.2.2`): normalized to English.
- `DESIGN.md`, `data/README.md`, `knowledge_base/KNOWLEDGE_BASE.md`:
  English; ADR numbers D1–D13 unchanged.
- Root `README.md` rewritten in TopPrism house style; `LICENSE` (MIT)
  added, matching the org-wide pattern.
- Machine-readable knowledge entries (`knowledge_items.json`) and all
  code remain as-is (code comments may retain Chinese; they are not
  documentation surfaces).
- `tools/consistency_check.py`: the four Chinese-string assertions now
  accept the English spec wording (bilingual during the transition).
- `docs/SHA256SUMS.md`: regenerated for the English file set.

## Validation after this change

- `tools/ref_check.py`: 145 `§` references resolve (unchanged count).
- `tools/consistency_check.py`: 83/83 checks pass.
- Heading-anchor diff before/after translation: empty for every file.

## Normative ownership

Unchanged. See `NORMATIVE_OWNERSHIP.md`.
