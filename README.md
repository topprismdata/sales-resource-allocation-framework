# TerritoryIR: Bidirectional Compilation Between Human Geographic Descriptions and Executable Regions

**Bidirectional territory semantics** · **Finite Boolean region algebra** · **Executable IR** · **Round-trip verification**

> **Decision question:** A sales manager draws a territory polygon on a digital map. A field rep describes the same territory in natural language: "凤凰街道 + 龙洞街道沿华南快速，西至龙洞街道—长兴街道界". Are they talking about the same place? TerritoryIR bridges these two representations through bidirectional compilation.

Part of **TopPrism Decision Intelligence**.

---

## Why this exists

Chinese FMCG companies manage hundreds of dealer territories. These territories exist in two incompatible representations:

- **In the field:** staff describe territories linguistically (street names, road segments, boundaries)
- **In the system:** territories are stored as GIS polygons

Bridging these two representations is a real operational problem. Contracts must be written in natural language but executed as geometric boundaries. Territory changes must be communicated to field staff as text but applied to the system as polygons. Neither representation alone suffices.

**TerritoryIR solves this through bidirectional compilation:**

```
Human Description  ⟷  TerritoryIR  ⟷  Executable Region
```

The IR is the **canonical semantic contract** — neither the text nor the polygon is authoritative. Both are projections of the same IR.

---

## Core contributions

| # | Contribution | Description |
|---|---|---|
| 1 | **Bidirectional territory semantics** | Human geographic language ↔ executable region geometry through a shared semantic IR |
| 2 | **Executable region algebra** | Finite Boolean algebra over heterogeneous geographic partitions, with typed AST and denotational semantics |
| 3 | **Semantics-preserving compression** | Named expressions (street, road, boundary) are formal compressions of atomic expressions |
| 4 | **Bidirectional evaluation** | 4-direction evaluation on 43 real-world territories |

## Formal properties

Five theorems establish the system's formal guarantees:

- **Theorem 1:** Atomic Representational Completeness — every $T \subseteq U$ has an exact IR expression
- **Theorem 2:** Semantic Compression — named clauses are semantics-preserving compressions
- **Theorem 3:** Error Decomposition — all geometric error is bounded by atomic discretization
- **Theorem 4:** R→L→R Round-trip — Region → Language → Region preserves semantics
- **Theorem 5:** L→R→L Round-trip — Language → Region → Language preserves semantics

## Results

| Metric | Dealers (32) | Sales-rep zones (11) |
|---|---|---|
| J (representational exactness) | 1.0 (32/32) | 1.0 (10/11) |
| IoU (geometric fidelity) | 0.992 | 0.971 |
| Coverage | 99.81% | 99.17% |
| R→L→R round-trip | 32/32 | 11/11 |
| L→R→L round-trip | 32/32 | 11/11 |
| Human sentences | 5–51 | 2–10 |

---

## Repository layout

| Path | Contents |
|---|---|
| `docs/paper/` | Paper (paper.md), outline, formal specification, screenshot |
| `docs/territory/` | Method docs, ontology, design specs, validation checklists |
| `docs/sraf/` | SRAF normative specs 00–08 |
| `tools/` | `territory_compile.py` (compiler), `dealer_describe_all.py`, `yeidai_compile.py`, `territory_ir.py` |
| `intelligence/` | World-model slice, GCJ⇄WGS boundary, road semantics |
| `data/gz/` | Business data (excluded from git per `.gitignore`) |

## Key tools

| Tool | Purpose |
|---|---|
| `tools/territory_compile.py` | Main compiler: fence → IR → human terms + engine terms |
| `tools/territory_ir.py` | IR schema, eval, verbalize, lower (pure functions) |
| `tools/yeidai_compile.py` | 业代 (sales-rep) zone compiler |
| `tools/dealer_describe_all.py` | Batch description generator for all dealers |

## Demo

```bash
# ① 业务数据包（来自 客户数据/ 的 CSV + geojson）
python3 tools/build_region_pack.py

# ② OSM 路网水系（需联网；广州规模必须分块）
python3 tools/fetch_region_osm.py --bbox 22.45,112.90,24.00,114.15 --out data/gz --tiles 4x4

# ③ 由 OSM 原始数据装配编译器输入
python3 tools/build_osm_full.py

# ④ 基础单元库（台账功能的前提；耗时数分钟）
python3 tools/build_unit_library.py

# ⑤ TerritoryIR 编译（可选，仅在需要 S 片回放时）
python3 tools/territory_compile.py

# ⑥ 启动
python3 tools/demo_server.py --data-dir data/gz 8765
```

`data/` 按数据契约不入库，clone 后必须先完成 ①–④；第 ⑤ 步只在需要
TerritoryIR 的 S 片回放时执行。缺少某一步的派生产物时，服务仍可启动，
相关功能会返回带 `missing_files` 的 HTTP 503，提示需要补跑的步骤。

## Paper

A full paper is under development: `docs/paper/paper.md`. Target venues: IJGIS, ACM SIGSPATIAL, Transactions in GIS.

---

## TopPrism metadata

```yaml
topprism:
  purpose: decision-intelligence
  capability: territory-description
  platform_layer: business-world-model
  maturity: applied-internal
  evidence:
    type: operational-data-validated
    source: anonymized Guangzhou business snapshot + public OSM + Amap
    validation: programmatic-plus-visual
```

## License

MIT. No operational business data or credentials are distributed with this repository; `data/*` is excluded by `.gitignore`.
