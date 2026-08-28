#!/usr/bin/env python3
"""SRAF v1.2 cross-document consistency checker.

Every check below is executed against the actual files. The generated
CONSISTENCY_CHECK_REPORT.md is written from this script's real output,
never hand-authored.
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = [
    "00_PROJECT_CHARTER.md", "01_WORLD_MODEL_SPEC.md", "02_DECISION_ONTOLOGY.md",
    "03_DECISION_PROBLEM_CONTRACTS.md", "04_ALLOCATION_INTELLIGENCE.md",
    "05_DECISION_ORCHESTRATION.md", "06_EVALUATION_AND_BENCHMARK.md",
    "07_REFERENCE_ARCHITECTURE.md", "08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md",
]
# Layouts: docs live in ./docs when present, else flat at repo root.
DOCS = (ROOT / "docs") if (ROOT / "docs").is_dir() else ROOT
DOC_VER = "v1.2"
doc = {n: (DOCS / n).read_text(encoding="utf-8") for n in SPECS if (DOCS / n).exists()}

R = []  # (name, ok, detail)


def chk(name, ok, detail=""):
    R.append((name, bool(ok), detail))


def has(f, s):
    return s in doc.get(f, "")


def nhas(f, s):
    return s not in doc.get(f, "")


# --- 1. existence -----------------------------------------------------------
chk("All 00-08 exist", len(doc) == 9, str(sorted(doc)))

# --- 2. version hygiene -----------------------------------------------------
missing_hdr = []
for f in doc:
    head = doc[f][:400]
    if DOC_VER not in head:
        missing_hdr.append(f)
chk(f"All specs marked {DOC_VER}", not missing_hdr, str(missing_hdr))

# residual normative v1.0 in spec bodies (allowed only inside the benchmark
# case-version example in 06 108, which is documented as unrelated to doc ver.)
allowed = {"06_EVALUATION_AND_BENCHMARK.md": 1}
residual = {}
for f, body in doc.items():
    n = len(re.findall(r"v1\.0", body))
    if n > allowed.get(f, 0):
        residual[f] = n
chk("No normative v1.0 wording left", not residual, str(residual))

if "06_EVALUATION_AND_BENCHMARK.md" in doc:
    b = doc["06_EVALUATION_AND_BENCHMARK.md"]
    chk("06 case-version example preserved & annotated",
        "case v1.0" in b and "与规范文档版本无关" in b)

# --- 3. v1.2 hard fixes -----------------------------------------------------
chk("approved_approved_decision_id removed",
    all(nhas(f, "approved_approved_decision_id") for f in doc))
chk("02 has approved_decision_id", has("02_DECISION_ONTOLOGY.md", "approved_decision_id"))
chk("07 has Engineering Envelope 110A", has("07_REFERENCE_ARCHITECTURE.md", "110A"))
for tier in ("S — Interactive", "M — City/Regional Planning", "L — Structural Batch"):
    chk(f"Envelope tier: {tier}", has("07_REFERENCE_ARCHITECTURE.md", tier))
chk("Envelope binds Phase 0-3",
    all(f"Phase {i}" in doc.get("07_REFERENCE_ARCHITECTURE.md", "") for i in range(4)))
chk("06 Scale Benchmark references Envelope",
    "§110A" in doc.get("06_EVALUATION_AND_BENCHMARK.md", ""))

gov = doc.get("05_DECISION_ORCHESTRATION.md", "")
chk("05 owns GW01-GW03", all(x in gov for x in ("GW01", "GW02", "GW03", "14A")))
chk("05 forbids auto-execute for governance", "禁止 A2/A3" in gov)
chk("02 router covers ModelGovernance", has("02_DECISION_ONTOLOGY.md", "ModelGovernance"))
chk("02 §94 points to GW in 05", "§14A" in doc.get("02_DECISION_ONTOLOGY.md", ""))

# --- 4. spec 08 content -----------------------------------------------------
z = doc.get("08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md", "")
for d in ("Identity Resolution ≠ Deduplication", "Entity Merge ≠ Source Record Merge",
          "Account ≠ ServiceLocation", "Identity Confidence ≠ Business Truth"):
    chk(f"08 boundary: {d}", d in z)
for case in ("Same Entity", "Duplicate Entity", "Same Account + Different ServiceLocation",
             "Store Relocation", "Store Rename", "Store Split", "Store Merge", "False Match"):
    chk(f"08 case: {case}", case in z)
chk("08 three-way decision + error-rate thresholds",
    "UNCERTAIN" in z and "false_match_rate" in z and "false_non_match_rate" in z)
chk("08 anti-chaining rule", "single-linkage" in z)
chk("08 survivorship decoupled from identity", "SV-1" in z)
chk("08 temporal identity / snapshot binding", "TI-2" in z and "IdentityResolutionRecord" in z)
chk("08 invariants I20-I30", "I20" in z and "I30" in z)
chk("08 benchmark cases ID01-ID20", "ID01" in z and "ID20" in z)
chk("08 Identity Gate", "Identity Gate" in z)
chk("08 confidence confounding metric", "IdentityConfoundedGapRate" in z)
chk("08 literature anchoring", "Fellegi" in z and "Papadakis" in z and "Zoltners" in z)

# --- 5. ownership closure (P21): no duplicate schema -------------------------
chk("00 P21 lists 08", "08 Identity" in doc.get("00_PROJECT_CHARTER.md", ""))
chk("01 delegates ExternalIdentifier schema",
    "08" in doc.get("01_WORLD_MODEL_SPEC.md", "")
    and nhas("01_WORLD_MODEL_SPEC.md", "entity_id\nsource_system\nidentifier_type"))
chk("01 owns identity principles only", "Canonical Identity Model" in doc.get("01_WORLD_MODEL_SPEC.md", ""))
chk("02 owns identity subtypes",
    all(s in doc.get("02_DECISION_ONTOLOGY.md", "") for s in
        ("IdentityDuplicate", "IdentityFalseMatch", "IdentityUnresolved", "HierarchyMisattribution")))
chk("04 refers subtypes to 02/08",
    "由 `02 §21` 拥有" in doc.get("04_ALLOCATION_INTELLIGENCE.md", ""))
chk("04 has IdentityIntegrityTest", "IdentityIntegrityTest" in doc.get("04_ALLOCATION_INTELLIGENCE.md", ""))
chk("04 H6 carries IdentityConfidence",
    "IdentityConfidence" in doc.get("04_ALLOCATION_INTELLIGENCE.md", ""))
chk("03 contract carries identity snapshot",
    "identity_snapshot_id" in doc.get("03_DECISION_PROBLEM_CONTRACTS.md", ""))
chk("03 F1 identity cause, not F4", "F4 RESOURCE_INFEASIBLE" in doc.get("03_DECISION_PROBLEM_CONTRACTS.md", ""))
chk("01 §71 adds identity quality states",
    "IdentityStatus" in doc.get("01_WORLD_MODEL_SPEC.md", ""))
chk("01 §72 points identity conflict to 08",
    "TC-3" in doc.get("01_WORLD_MODEL_SPEC.md", ""))
chk("06 points I20-I30 to 08", "I20–I30" in doc.get("06_EVALUATION_AND_BENCHMARK.md", ""))
chk("07 places identity module", "src/domain/identity/" in doc.get("07_REFERENCE_ARCHITECTURE.md", ""))

# --- 6. v1.1 regression (must not have been broken) --------------------------
FORBIDDEN = {
    "Ambiguous old run term removed": "DecisionRun",
    "Old territory definition uses assignments": "Collection(ResponsibilityAssignment)",
    "Old local subtype heading": "AllocationGap（Local Allocation）",
    "Old G6 subtype": "G6 AllocationGap",
    "ResourceDeployment example hard-binds Rep17": "resource = Rep17",
}
for name, s in FORBIDDEN.items():
    hits = [f for f in doc if s in doc[f]]
    chk(f"[v1.1 regression] {name}", not hits, str(hits))

chk("[v1.1 regression] 01 has ResourceRequirement", has("01_WORLD_MODEL_SPEC.md", "ResourceRequirement"))
chk("[v1.1 regression] 01 has DeploymentAssignment", has("01_WORLD_MODEL_SPEC.md", "DeploymentAssignment"))
chk("[v1.1 regression] 01 has Capability", has("01_WORLD_MODEL_SPEC.md", "Capability"))
chk("[v1.1 regression] 01 has SalesActivity", has("01_WORLD_MODEL_SPEC.md", "SalesActivity"))
chk("[v1.1 regression] 01 has ServiceChannel", has("01_WORLD_MODEL_SPEC.md", "ServiceChannel"))
chk("[v1.1 regression] 02 has RequirementExceptionProposal", has("02_DECISION_ONTOLOGY.md", "RequirementExceptionProposal"))
chk("[v1.1 regression] 02 has ApprovedDecision", has("02_DECISION_ONTOLOGY.md", "ApprovedDecision"))
chk("[v1.1 regression] 04 owns LocalAllocationGap", has("04_ALLOCATION_INTELLIGENCE.md", "LocalAllocationGap"))
chk("[v1.1 regression] 03 uses DeploymentAssignment for DP04", has("03_DECISION_PROBLEM_CONTRACTS.md", "DeploymentAssignment"))
chk("[v1.1 regression] Territory semantics Responsibility-only",
    "Territory ↔ Responsibility" in doc.get("01_WORLD_MODEL_SPEC.md", "")
    or "TerritoryMembership" in doc.get("01_WORLD_MODEL_SPEC.md", ""))
chk("[v1.1 regression] ResourceEquivalent marked metric",
    re.search(r"ResourceEquivalent[^\n]*\n[^\n]*(metric|Metric)", doc.get("04_ALLOCATION_INTELLIGENCE.md", "")) is not None
    or "Derived Metric" in doc.get("04_ALLOCATION_INTELLIGENCE.md", ""))
for f, body in doc.items():
    opens = len(re.findall(r"^```", body, re.M))
    chk(f"Fenced blocks balanced: {f}", opens % 2 == 0, f"{opens} fences")
# every identity subtype named in 02 must also appear in 04 and 08
subtypes = ("IdentityDuplicate", "IdentityFalseMatch",
            "IdentityUnresolved", "HierarchyMisattribution")
chk("Identity subtypes consistent across 02/04/08",
    all(s in doc.get("02_DECISION_ONTOLOGY.md", "")
        and s in doc.get("04_ALLOCATION_INTELLIGENCE.md", "")
        and s in z for s in subtypes))

# every DP named anywhere must be declared in 03
dps = set(re.findall(r"\bDP0[1-7]\b", " ".join(doc.values())))
chk("All DP01-DP07 references have a contract in 03",
    all(d in doc.get("03_DECISION_PROBLEM_CONTRACTS.md", "") for d in sorted(dps)),
    str(sorted(dps)))

# seven gap types consistent between 02 and 04
gaps = ("CoverageGap", "CapacityGap", "OpportunityGap", "SpatialTravelGap",
        "CapabilityGap", "LocalAllocationGap", "StabilityGap")
chk("Seven Gap taxonomy consistent 02/04",
    all(g in doc.get("02_DECISION_ONTOLOGY.md", "")
        and g in doc.get("04_ALLOCATION_INTELLIGENCE.md", "") for g in gaps))

# 06 must bind I20-I30 to 08 without redefining them
chk("06 does not redefine identity invariants",
    "I20 " not in doc.get("06_EVALUATION_AND_BENCHMARK.md", ""))


refs = set(re.findall(r"`(0[0-8]_[A-Z_0-9]+\.md)`", " ".join(doc.values())))
chk("All referenced spec files exist", all(r in doc or (DOCS / r).exists() for r in refs), str(sorted(refs)))

# --- 8. evidence-level wording discipline -----------------------------------
chk("08 does not claim production validation",
    not re.search(r"已验证生产|已证明提升销售", z))

# v1.2.1 hotfix lock: ambiguous MissedOpportunity must not reappear as a term
chk("MissedOpportunity term eliminated (v1.2.1 hotfix)",
    all(nhas(f, "MissedOpportunity") for f in doc))
chk("UncoveredOpportunity/OpportunityAtRisk present in 02",
    has("02_DECISION_ONTOLOGY.md", "OpportunityAtRisk")
    and has("02_DECISION_ONTOLOGY.md", "UncoveredOpportunity"))

# --- report -----------------------------------------------------------------
passed = sum(1 for _, ok, _ in R if ok)
total = len(R)
lines = [
    "# SRAF v1.2 Consistency Check Report",
    "",
    f"**Result:** {passed}/{total} checks passed.",
    f"**Generated by:** `tools/consistency_check.py` (executed, not hand-written).",
    "",
    "This report is the fourth-pass cross-document consistency check after "
    "applying the v1.1 external-review corrections and adding "
    "`08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`. "
    "It re-runs all v1.1 regression rules to make sure the new baseline did not "
    "break previously frozen semantics.",
    "",
    "| Check | Result | Detail |",
    "|---|---|---|",
]
for name, ok, detail in R:
    d = (detail or "").replace("\n", " ").replace("|", "/")[:200]
    lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {d if d else ' '} |")
lines += [
    "",
    f"**Final status: {'PASS' if passed == total else 'FAIL'}.**",
    "",
]
(DOCS / "CONSISTENCY_CHECK_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
print(f"{passed}/{total} passed")
for name, ok, detail in R:
    if not ok:
        print("FAIL:", name, "|", detail[:200])
sys.exit(0 if passed == total else 1)
