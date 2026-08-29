# SRAF Overall Design Document (Living Document)
- Status: v0.7 (overall design for implementation phase, updated as implementation progresses)
- Date: 2026-08-28
- Specification Baseline: 00-08 Specification Set (this directory) **v1.2.1 FROZEN** (this document does not modify specifications; it records implementation status and design decisions built upon the specifications)
- Implementation Baseline Update: docs/CHANGELOG_v1.2.2.md (regional priority semantics + logical fence merge, 2026-08-28)
- Governance: Specification changes follow CHANGELOG + NORMATIVE_OWNERSHIP; implementation decisions are recorded in §5 of this document

---

## 1. Project Positioning

**SRAF = Adding a brain to dealer territory management.**

Starting point is a user diagnosis: **"Current territory adjustments only have functionality, no business knowledge, meaning no intelligence."**

Existing tools (fence drawing, store classification, scheduling engine) are all "how-to" muscles; what's missing is the "why" brain:
Which store belongs to whom (identity), whether the gap is real or false (diagnosis), what happens if changed (prediction), how to change it (recommendation).

```text
Intelligence = World Model (skeleton) + Knowledge Base (flesh) + Reasoning (giving recommendations to people)
```

**Output Positioning: Recommendations are for people, not autonomous decisions.** Each recommendation comes with an evidence chain, and every "why"
traces back to a sourced knowledge entry (K-*), so people can keep questioning down to the root.

---

## 2. Overall Architecture: Three-Level Independent Decision Layers

**Layer mirroring organization; each layer makes decisions independently, transfers only via interfaces, cross-layer intervention prohibited** (D10):

```text
┌──────────────────────────────────────────────────────────────┐
│  People (City Manager D layer / Dealer Supervisor B layer / Field Sales Rep V layer)              │
│  ↑ Recommendations+evidence chain for each layer                ↑ Independent approval for each layer (GW process)      │
├──────────────────────────────────────────────────────────────┤
│  04 Allocation Intelligence layer (in design): Diagnosis first locates the layer, then attributes causes within that layer            │
├──────────────────────┬───────────────────────────────────────┤
│  World Model v2.1 (skeleton) │  Knowledge Base v0.4.0 (flesh, 32 entries)            │
│  L1-L4 UFO layering       │  Principles 6 · Rules 12 · Facts 3 · Cases 3 · Constraints 2 · Benchmarks 5    │
│  Event catalog E1-E11       │  Governance: No unverified source enters the database; MEDIUM only assists     │
│  Three-level structure §2A        │  Sources: books + papers + data + dialogues + industry search        │
├──────────────────────┴───────────────────────────────────────┤
│  Layer-D Dealer Territory layer (Decision authority: manufacturer city manager)                  │
│  dealer_territory/ fence splitting/assignment — Output I-D: store→dealer      │
├───────────────────────────────────────────────────────────────┤
│  Layer-B Field Sales Rep Beat Route layer (Decision authority: dealer owner + supervisor) 【To be built】          │
│  Site→sub-area→person→frequency→beat — Output I-B: store→beat→rep+frequency      │
├───────────────────────────────────────────────────────────────┤
│  Layer-V Visit Scheduling layer (Decision authority: field sales rep/system)                       │
│  visit-scheduling-optimizer (read-only dependency) — Output: visit plan          │
├───────────────────────────────────────────────────────────────┤
│  Data assets: gz_data.json (38 territories + 33,109 stores + kind six-classification)       │
│  Contract package · POS upstream · OSM road network rivers                               │
└───────────────────────────────────────────────────────────────┘

Interface contract: I-D (store assignment list) · I-B (beat + frequency policy)
Cross-layer discipline: upstream output = downstream fixed input; downstream finds issues → sends signal upstream, does not overstep to modify;
Each layer's optimization objectives do not interfere with each other; internal events are resolved within the layer (E6 only affects D layer, E10/E11 only affect B layer)
```

---

## 3. Component Status Summary

| Component | Location | Status | Description |
|---|---|---|---|
| Specification Set 00-08 | `docs/` | **v1.2.1 FROZEN** | Includes 08 identity specification; changes require governance process |
| World Model v2.1 | `analysis/WORLD_MODEL_dealer_management.md` + iCloud designs/ | **Finalized** | UFO alignment + three-level structure; remaining issue: POS availability |
| Knowledge Base | `knowledge_base/` | **v0.3.0** | 31 entries (+K-PRIN-006 regional priority); gaps reduced from 5→2 (customer relationship quantification algorithm, approval chain localization) |
| Layer-D code | `dealer_territory/` `tools/` | Available | 6 modules 13 tests (11 green+2 skipped); fence_split integrated with market_partition |
| Layer-B beat design | (To be built) | **Missing** | Requires decision problem contract + implementation; method: five-step beat design + four beat principles (K-RULE-011/012) |
| Layer-V visit adapter | (To be built) | **Design complete, pending implementation** | 32-item gap list in DP06_GAP_ANALYSIS_v2_full.md |

---

## 4. Data Asset Snapshot (2026-08, Guangzhou)

```text
38 territories · 33,109 stores (/tmp/gz_data.json, fields n/c/d/u/lon/lat/direct/dealers/kind)

kind six-classification = ready-made implementation of World Model L4:
OK        26,182 (79%)  Three-layer alignment normal
OOF        4,300 (12%)  Out-of-fence supply (diagnosis signal)
DIRECT_IN  2,111  (6%)  Chain direct supply (Meiyijia system accounts for 97% of direct supply)
GAP          433  (1%)  Coverage gap (input for four-classification diagnosis)
DIRECT        76        Direct supply stores
MULTI 7 Conflict Ledger Real Instance

Channel Structure: Grocery/Wholesale 51% · Special Channels 33% · CVS 11% (Typical Wholesale Distribution Market)
Fence Drawing Empirical Evidence: 72% district/county contracting system; boundaries follow main roads/rivers; old urban areas segmented into 3-6 blocks
```

---

## 5. Key Design Decision Records (ADR)

| # | Decision | Rationale | Date |
|---|---|---|---|
| D1 | **Identity First**: Must pass 08 Identity Resolution before allocation/diagnosis | Gaps without resolved identity may be false (double-counting) | When v1.2 was frozen |
| D2 | **visit Read-Only Dependency**: Code maintained by others, SRAF calls its public API via adapter, locked version + compatibility sentinel | 32 DP06 gaps all resolved in adapter layer; solver core zero modifications; upstream upgrades automatically benefit | 2026-08-28 |
| D3 | **Certificated Honesty**: Follows visit's ColumnGenerationCertificate pattern; heuristic results never certify global optimality | Align with 06 anti-cherry-pick | 2026-08-28 |
| D4 | **World Model UFO Alignment**: L1 objects/L2 role commitments/L3 events/L4 derived four layers; OntoClean verification (dealer=role not kind) | Literature review conclusion (UFO/gUFO+OntoClean) | 2026-08-28 |
| D5 | **Supply Relationship=Event Stream**: EPCIS ObjectEvent pattern; static edges deprecated; F3 footprint=materialized view | GS1 EPCIS standard; static edges lose time/item traceability | 2026-08-28 |
| D6 | **Three-Layer Fence Ontology**: F1 normative object (UFO-C)/F2 artifact/F3 derived observation; health=align(F1,F2,F3) | Three-layer alignment is measurement between three ontology levels | 2026-08-28 |
| D7 | **Three Iron Laws of Knowledge Governance**: No source, no entry; MEDIUM only for auxiliary reasoning; data classes refresh with snapshots, principle classes require business confirmation | Prevent "hallucinated knowledge" | 2026-08-28 |
| D8 | **Lightweight Storage Start**: dataclass+JSON/SQLite, interfaces designed per graph model, bitemporal implemented at application layer (XTDB close-and-open semantics) | 38 fences + 33k stores don't need Neo4j; smooth migration path exists | 2026-08-28 |
| D9 | **Intelligent Layer Output=Human Advice**: Observation→rule matching→reasoning chain assembly (advice+justification chain+risk+routing), no auto-execution | User positioning: "give humans advice"; high-risk adjustments require human approval (GW process) | 2026-08-28 |
| D14 | **Multi-component territory**: a dealer's territory may comprise multiple disconnected spatial components. `World.fences_of(dealer)` returns all blocks; transfer re-clusters remaining stores into N hulls (2 km proximity); density uses summed territory area. Continuity is a business preference, not an ontological constraint. | Oracle-ladder audit: 9/37 dealers multi-block; 国之林 3 blocks IoU 0.81 (multi ≠ hard); single `fence_by_dealer` index silently dropped blocks | 2026-08-29 |
| D13 | **Coordinate System Boundary Normalization**: Data packages declare meta.crs (default GCJ-02=Gaode system); one-time GCJ→WGS on load (`pack_from_disk`), reverse conversion on write (`pack_for_disk`), internal geometry=pure WGS-84 (same standard as OSM landmarks/tiles) | Discrimination experiment: fence vertices→OSM roads GCJ direct comparison median 338m vs after WGS conversion 123m → business fences confirmed drawn in Gaode (GCJ-02); Guangzhou mixed two systems=623m systematic offset (E-549/N+293), sufficient to distort four-direction verification/route-following judgment/base map alignment. Store↔fence kind classification on both sides uses same system so unaffected | 2026-08-28 |
| D11 | **Territory Priority + Logical Fence Merge**: Transfers only reassign store assignment (unique fact, quantity conservation trivially holds), fences=derived view of dealer-store point set convex hull; deprecated union/difference polygon surgery, fragmentation/conservation checks | Business corrected "decision object is territory, stores are side effects" (K-PRIN-006); hand-written GIS surgery is bug breeding ground (GeometryCollection crashes, km² caliber deviation 9%, fragmentation governance pseudo-problem), entire class of problems disappears with logical merge | 2026-08-28 |
| D12 | **Parsing Rules Priority, LLM Fallback**: Sub-area selector+regex pattern (<1s) as main path, LLM·M3 only for free-form sentences; @ mention engine ensures LLM always sees full names | LLM on critical path causes 8-20s latency and timeout jitter; colloquial abbreviation mismatches cured by @ expansion (frontend deterministic replacement) | 2026-08-28 |
| D10 | **Three-Tier Independent Decision Layers**: D/B/V layers independent, only interfaces (I-D/I-B) exchange data, cross-layer intervention prohibited; diagnosis first locates layer then attributes | User decision "each layer independent, don't interfere" + layer-mirrored organizational principle (industry consensus); prevents cross-layer coupling like fence layer optimizing route efficiency | 2026-08-28 |

---

## 6. visit Integration Architecture (D2 Expansion)

```text
SRAF adapter (self-built, responsible)              visit engine (read-only, maintained by others)
├── Projection construction: World Model slice→array          solve_to_plan / build_time_matrix
├── Failure semantics: F1-F7 classifier              PlanVersion / DecisionEvidence
├── Commitment output: Unfulfilled/utilization calculation     ColumnGenerationCertificate
├── Travel backfill: SRAF calibrated data fills gaps        (PVRPTW/multi-person optimization on their roadmap)
└── Provenance: snapshot/seed/version      Locked version ==0.1.x + CI signature sentinel
```

Five-Question Verification Conclusions (see DP06_GAP_ANALYSIS_v2_full.md):
Projection layer missing / post-calculation metrics missing / failure semantics classifier missing / fence intelligence already exists (fence_split) / effect tracking needs TravelEstimate fix.
**Modification scope: 3-5 working days (Envelope S), all in adapter layer.**

---

## 7. Current Gaps and Next Steps

**P0 Status (all design/implementation completed this round)**
0. ✅ Coordinate System Contract (D13): GCJ-02 data package ↔ WGS-84 internal, boundary single normalization, lossless round-trip (round-trip residual 0.000m measured)
1. ✅ Layer-B Contract Proposal: `docs/PROPOSAL_v1.3_LAYER_BINDINGS.md` (pending approval for v1.3)
2. ✅ 04 Implementation Design: `analysis/DESIGN_04_allocation_intelligence.md`
Also code-generated into `intelligence/` package (MVP three questions verified on real data)
3. ✅ visit adapter (read-only integration): landed with Demo (/api/bootstrap projection +
generate/adjust/apply/analysis four endpoints + territory package hot-switch)

**Demo Current Capabilities** (`tools/demo_server.py` + `demo_page.html`):
Territory data package hot-switch (/api/regions + /api/switch, data/<territory> directory plug-and-play) ·
Contract→territory generation (interpreted adoption/draft dual paths + road semantics + visual final review + conflict detection) ·
**Territory Priority Semantic Adjustment**: @ mentions (select to insert full name) + sub-area selector (entire territory/half-territory/
territory name/OOF/store surroundings) + rule main path LLM fallback + proposal evidence chain + orange preview ring +
Logical merge apply/reject (/api/reject invalidates expired proposals) · Focused workflow (home store+neighbor
stores each color) · Post-apply fence geometry redraw in-place · Full gray base map · Existence semantics
(fence does not exist before generation) · Viewport automatically aligns to fence extent.
Data switching guide: `data/README.md`.

**P1 (This Week)**
1. VisitSchedulingProjection dataclass (with identity_snapshot_id)
2. ScheduleQualityEvaluator (frequency achievement/capacity utilization/stability)
3. Oracle independent entry (feasibility_only)

**Legacy Business Confirmation (Non-blocking)**
- POS transaction data monthly availability (supply side evidence ceiling immediate hanging MEDIUM)
- Customer relationship quantification algorithm (suggestion: service years + visit stability proxy)
- Approval chain localization (immediate hanging industry default five levels)

---

## 8. Document Map

```text
docs/ Specification set v1.2.1 FROZEN (00 Charter … 08 Identity) + governance documents
CHANGELOG_v1.2.2 = implementation baseline update record (no spec changes)
`DESIGN.md` (moved to `docs/DESIGN.md`) This file — overall design for the implementation phase (living document)
knowledge_base/ Knowledge Base v0.3.0 (31 entries; json machine-readable + md human-readable index)
analysis/ World Model v2.1 · 04 Implementation Design · DP06 Gap Analysis v2 · Contract Package
Fence characteristics · Industry gaps · Three-round review · CN market reality · intel_reports_v0
dealer_territory/ 6 modules (models/assignment/four_bounds/fence_from_text/
                         fence_allocator/fence_analysis/fence_split) 
tools/ demo_server + demo_page (Region Package Demo) · intel_report
validate_region_pack · fetch_region_osm · consistency/reference check
H3 index · map generation
data/ Region data package (data/gz Guangzhou default + data/fs Foshan greenfield test
+ data/demo2 switch sample) · Data Switch Guide README.md
tests/ 13 tests (11 green + 2 skipped)
iCloud designs/ World Model v2.1 review mirror (cross-agent collaboration)

Mirror Collaboration: iCloud `AI team/zcode/designs/Dealer Management World Model.md` (for review),
Repository `analysis/` is the implementation-side master.
