# Dealer Territory Knowledge Base (Knowledge Base) 

- Status: v0.4.2 (34 items: 21 crystallized + 9 supplemented by industry research + 2 new from business corrections; business gaps 5→2) 
- Date: 2026-08-28
- Positioning: **04 Allocation Intelligence layer's "IQ" source**——World Model provides skeleton, Knowledge Base provides flesh
- Machine-readable: `knowledge_items.json` (This file is human-readable index) 

## Why is it needed

The output of the Intelligence layer is **advice for people**. Advice for people ≠ solver output, but rather:
"Recommendation X, reasons ①②③, risks A/B, based on: rule K-RULE-003 + case K-CASE-002 + data K-FACT-003".

Every link in the reasoning chain must come from **knowledge items with sources**——this is exactly the opposite of "lacking IQ":
Not a missing feature, but **missing knowledge**.

## Six types of knowledge × 34 items

### Principles (Why it's designed this way) ——from Zoltners book + market analysis
| ID | Knowledge | Source |
|---|---|---|
| K-PRIN-001 | Territory exclusivity = a system that protects dealer investment, not an optimization solution | book + CN_MARKET |
| K-PRIN-002 | Carryover: last year's effort, this year's results, evaluation must state impact horizon | book + 06 Carryover Gate |
| K-PRIN-003 | Adjustment impact causes the most harm on medium-sized stores | book Table 8.3 |
| K-PRIN-004 | Three-step design: account-level→geographic integration→alignment adjustment | book |
| K-PRIN-005 | Hierarchical mirroring organization: decision-making level = organizational level, D/B/V three levels independent, handovers only via interfaces, cross-level intervention prohibited | industry research + user final decision |
| K-PRIN-006 | Territory adjustment decision object = 【territory/sub-area】, store assignment is a derived effect (stores follow territory, not CRM store-level changes) | business side 2026-08-28 correction |
| K-PRIN-007 | A territory may comprise multiple disconnected spatial components; continuity is a business preference, not an ontological constraint (D14) | business side 2026-08-29 correction + oracle-ladder audit |
| K-PRIN-008 | Hand-drawn fence vs nominal landmark low fidelity ≈ drawing-noise floor (human shortcutting); evaluate vs human re-draw ceiling, not exact IoU | business side 2026-08-29 + fidelity decomposition audit |

### Rules (When and how to do it) ——data validation + business dialogue
| ID | Knowledge | Source |
|---|---|---|
| K-RULE-001 | Boundaries follow main roads/rivers, visible to naked eye, no disputes | 38 fence geometry validation |
| K-RULE-002 | District zoning as base: outer suburbs whole-territory contracting, old city one area divided into 3~6 blocks | 72% purity validation |
| K-RULE-003 | Direct supply stores don't count as gaps | Meiyijia 2,127 stores hard evidence |
| K-RULE-004 | Upstream consistency rate 85% normal, 100% unattainable | kind distribution |
| K-RULE-005 | Identity first: gaps with unparsed identity may be false gaps | 08 standard |
| K-RULE-006 | Dealer change: first evaluate customer relationship dependency, transition plan = joint visit endorsement 1-3 months (industry consensus) | Dashi case+industry research (HIGH)  |
| K-RULE-007 | Low-density gaps are structural: wholesale/sub-distribution + beat route direct delivery, not adding people | Conghua case+industry research (HIGH)  |
| K-RULE-008 | Rebate structure determines dealer behavioral response (tiered→channel stuffing impulse; process→compliance) | industry rebate practice research |
| K-RULE-009 | Change SOP: five-level approval+transition toolkit+1-3 months joint visit, strictly prohibit cliff drops | industry handover SOP research |
| K-RULE-010 | Low-density selection: extremely low density use sub-distribution, townships use central warehouse direct delivery+online ordering supplement | industry rural coverage research |
| K-RULE-011 | Beat route design five-step method (Layer-B): locate points→define areas→assign people→set frequency→design routes | industry beat route design research |
| K-RULE-012 | Beat route four principles: sub-area based to prevent backtracking · ABC classified frequency · load balancing · stability over optimization | industry beat design research |

### Facts (What the market looks like) 
K-FACT-001 Contract fill-in-the-blank text · K-FACT-002 Outright sell-in + no-return terms · K-FACT-003 Guangzhou current snapshot
K-FACT-004 Contract-named boundary landmarks may cross the territory interior (river as boundary ≠ river as cut) — P1 oracle-arc audit |

### Cases (How it specifically happened) 
K-CASE-001 Conghua whole-territory contracting · K-CASE-002 Panyu riverside division · K-CASE-003 Dashi adjustment transition

### Constraints (System hard boundaries) 
K-CONST-001 Visit read-only dependency · K-CONST-002 Stability budget+approval chain

### Benchmarks (What counts as good) 
K-BENCH-001 Territory health benchmark (alignment 79% line) · K-BENCH-002 Technology selection (H3+graph partitioning) · K-BENCH-003 Capacity China standard (20-30 stores/day classification, A week/B two weeks/C month) · K-BENCH-004 International standard cross-reference (40-45 days/Strike Rate 60-75%/travel<40%) · K-BENCH-005 Layer-B/V process benchmark (visit achievement rate red line 90%, co-visit 50-70%, process/result evaluation weight)

## Knowledge governance (Lifecycle of each knowledge item) 

```text
Acquisition → Registration (statement+source+confidence+maps_to)  → Usage (entering recommendation reasoning chain) 
  ↑                                                      ↓
└────── Data refresh/business correction triggers version update ←── Feedback when recommendation is accepted/rejected
```

Rules:
1. Each knowledge item must have `source`——knowledge without source is not stored (to prevent "hallucinated knowledge")
2. Knowledge with `confidence: MEDIUM/LOW` can only appear in auxiliary reasons of recommendations, cannot independently support strong recommendations
3. Data-type knowledge (FACT/BENCH) updates with snapshots; principle-type knowledge requires business confirmation to revise

## Business knowledge gaps (5 → 2, the rest have been resolved by industry research) 

**Resolved** (see json `knowledge_resolved_from_research`): Capacity ✓ K-BENCH-003/004 · Rebate structure ✓ K-RULE-008 · Approval chain+transition SOP ✓ K-RULE-009 · Low-density service model ✓ K-RULE-010

| # | Gap | Current State |
|---|---|---|
| 1 | Customer relationship reliance quantification metric | Industry has no standard metric; it is suggested to use the combination of 'continuous service years of the same dealer + visit stability' as a proxy, and the algorithm needs business confirmation (impact on 40% reproducibility of K-CASE-003). |
| 2 | Approval chain localization | K-RULE-009 is the industry default five-level (regional manager → region → sales general manager → finance → legal), and needs to be verified against the company's actual structure. |

## Suggestion Generation Pattern (04 Design Preview)

```text
Observation (World Model L4) → Rule matching (R-type rules) → Reasoning chain assembly
→ Suggested actions + Reason chain (Knowledge ID + data evidence) + Risk (PRIN-002/003) + Routing (approval chain)
```

Each suggestion carries its own evidence chain → humans can ask "why" → each "why" lands on a knowledge entry.
