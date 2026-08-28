# Sales Resource Allocation Framework

**An allocation-intelligence layer for distributor territory management:
world model + evidence-governed knowledge base + reasoning that proposes
to humans — and never auto-executes.**

`WORLD MODEL` · `DECISION INTELLIGENCE` · `REAL-DATA VALIDATED` ·
`NO OPERATIONAL DATA IN REPO` · `MIT`

> **Decision question:** Given dealer territories derived from contracts,
> observed supply footprints, and road/river landmarks — which coverage
> gaps are real, which organizational layer owns them, and what happens
> if a sub-area is transferred between dealers?
>
> Part of **TopPrism Decision Intelligence**. Existing tools (fence
> drawing, store classification, visit scheduling) are the muscle — the
> *how*. SRAF supplies the brain — the *why*: identity, gap diagnosis,
> impact prediction, and advice with a full evidence chain.

------------------------------------------------------------------------

## Why this exists

Territory adjustments in the field today carry "function without
business knowledge": a fence can be redrawn, but nothing can answer
*why* a gap exists, *who* should own the fix, or *what breaks* if the
boundary moves.

```text
Intelligence = World Model (skeleton)
             + Knowledge Base (flesh, 31 sourced entries)
             + Reasoning (advice for humans, every "why" lands on an entry)
```

The output is always a **proposal for a human to approve** — with
signals, risks, and provenance attached (governance workflow GW,
approval gate A2/A3 forbidden for auto-execute).

------------------------------------------------------------------------

## Architecture: three independent decision layers

Layers mirror the organization. Each layer decides independently and
hands off only through interfaces (D10):

```text
 Human   city manager (D) / dealer supervisor (B) / field rep (V)
          ↑ advice + evidence chain          ↑ per-layer approval (GW)
├────────────────────────────────────────────────────────────┤
│  04 Allocation Intelligence: locate the layer, then diagnose│
├─────────────────────────┬──────────────────────────────────┤
│  World Model (skeleton) │  Knowledge Base (flesh, 31)      │
│  F1/F2/F3 fence ontology│  principles·rules·facts·cases…   │
│  events E1–E11          │  no-provenance-no-entry governance│
├─────────────────────────┴──────────────────────────────────┤
│  Layer D  dealer territory  → I-D: store → dealer          │
│  Layer B  rep beat routes   → I-B: store → beat → rep+freq │
│  Layer V  visit scheduling  → visit plan (read-only dep.)  │
└────────────────────────────────────────────────────────────┘
```

## What v1.2.2 establishes

- **Area-first adjustment semantics (K-PRIN-006 / D11).** The decision
  object is a *sub-area* of a territory — whole region, half-region,
  district, out-of-fence pocket, or store-neighborhood. Stores follow
  the area as a derived effect; editing stores directly is a CRM job,
  not a decision.
- **Logical fence merge, no polygon surgery.** Applying a transfer
  reassigns store ownership (the only fact — conservation trivially
  holds); a dealer's fence is a derived convex hull of its current
  stores. ~150 lines of union/difference geometry surgery deleted with
  it.
- **CRS boundary normalization (D13).** Business packs are declared
  GCJ-02 (Amap); OSM is WGS-84. Mixed naively, that is a ~623 m
  systematic offset in Guangzhou (measured) — enough to make four-bound
  direction checks fiction. All geometry runs pure WGS-84 internally:
  one-shot `pack_from_disk` on load, exact inverse on write
  (round-trip residual 0.000 m, tested).
- **Rules-first parsing, LLM as fallback (D12).** An `@`-mention engine
  guarantees the LLM only ever sees full legal names; the deterministic
  rule path answers standard commands in &lt;1 s.

## Demo: the three-step loop

```bash
python3 tools/demo_server.py          # stdlib server, Leaflet single page
# ① contract text → four bounds → OSM landmark rebuild → fence draft + conflicts
# ② natural-language area transfer:  "move @A's east half to @B"
#    → proposal card (area, stores, contract signals, materiality) → apply / reject
# ③ analysis: per-fence health (Q1) + coverage-gap taxonomy (Q2)
```

Business data packs (`data/<region>/`) are **not** included; assemble
your own per [data/README.md](data/README.md) (schema + `crs`
contract).

------------------------------------------------------------------------

## Repository layout

| Path | Contents |
|---|---|
| `docs/` | Normative specs 00–08 (**v1.2.1 FROZEN**) + governance files; language normalization per `CHANGELOG_v1.2.3.md` |
| `DESIGN.md` | Living implementation design + ADR log (D1–D13) |
| `intelligence/` | World-model slice, area-first adjust engine, GCJ⇄WGS boundary, road semantics, vision verification, LLM parse |
| `dealer_territory/` | Layer-D fence split / allocation / four-bounds / analysis |
| `knowledge_base/` | 31 knowledge entries (JSON machine-readable + human index) |
| `tools/` | Demo server + frontend, OSM fetch, pack validation, consistency & reference checks |
| `tests/` | 13 unit tests (`python3 -m unittest discover tests`) |

## Evidence

- World-model semantics validated on an anonymizable 38-fence /
  33,109-store Guangzhou snapshot (six-way `kind` classification,
  79% three-layer alignment rate — aggregate figures only; raw data is
  out of scope for this repository).
- Fence-vertex → OSM-road distance test discriminated the CRS question
  (338 m under GCJ-02 direct comparison vs 123 m after conversion).
- Consistency and cross-reference gates run in CI-able scripts:
  `tools/consistency_check.py`, `tools/ref_check.py`.

## Where it fits at TopPrism

SRAF is the decision-intelligence layer above
[market-partition](https://github.com/topprismdata/market-partition)
(spatial partitioning),
[bge-entity-match](https://github.com/topprismdata/bge-entity-match)
(entity resolution), and
[visit-scheduling-optimizer](https://github.com/topprismdata/visit-scheduling-optimizer)
(execution layer, consumed read-only through an adapter — D2).

------------------------------------------------------------------------

## TopPrism metadata

```yaml
topprism:
  purpose: decision-intelligence
  capability: territory-allocation
  platform_layer: business-world-model
  maturity: applied-internal
  evidence:
    type: operational-data-validated
    source: anonymized business snapshot + public OSM
    validation: programmatic-plus-visual
  spec_baseline: docs v1.2.1 FROZEN
  product_context:
    - dealer-territory-design
    - coverage-gap-diagnosis
    - area-transfer-what-if
```

## License

MIT. No operational business data or credentials are distributed with
this repository; `data/*` and `analysis/*` are excluded by contract
(`.gitignore`).
