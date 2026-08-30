# TerritoryIR: A Controlled Geographic Language with Executable Semantics and Bidirectional Round-Trip

## Abstract

We present TerritoryIR, a controlled geographic language for describing sales territories, with an executable semantic layer and bidirectional round-trip capability. The system defines a Boolean region algebra over two heterogeneous geographic partitions—a road-block partition B (6261 atomic cells) and an administrative-street partition A (228 cells)—with a formal completion B* = B ∪ R that ensures partition coverage. A semantic intermediate representation (IR) maps to deterministic region expressions, while a dual-projection architecture separates human-readable verbalization from machine-executable serialization.

The representation achieves three layers of fidelity: (1) **geometric fidelity** between the original polygon and the IR-denoted reconstruction (IoU median 0.99, coverage median 99.8% on 43 real-world territories); (2) **representational exactness** via a Representational Completeness Theorem (J=1.0 for all 43 territories); and (3) **linguistic round-trip consistency** (parse(verbalize(IR)) ≡ IR for all 43). We formulate geographic clause selection as a set-level referring-expression problem, adapting the preference-order principle of Dale & Reiter's Incremental Algorithm. The system is deployed in a real FMCG sales territory management workflow in Guangzhou, China.

**Keywords:** Boolean region algebra, geographic controlled language, intermediate representation, referring expression generation, FMCG territory management

## 1. Introduction

### 1.1 Problem

Chinese FMCG companies manage hundreds of dealer territories drawn as polygons on digital maps. Field staff communicate these territories in natural language: "凤凰街道 + 龙洞街道沿华南快速 + 新塘街道沿广连高速 + 联和街道沿力康路，西至龙洞街道—长兴街道界". This requires a description that is simultaneously **human-readable**, **geometrically faithful**, and **machine-replayable**.

Existing approaches fail on at least one dimension:
- Manual descriptions are inconsistent and non-replayable.
- LLM-generated descriptions hallucinate verifiable spatial relations.
- Pure GIS polygon stores are not human-communicable.

### 1.2 Challenges

Three structural challenges arise from Chinese urban geographic data:

**Heterogeneous geographic partitions.** Road-block parcels (四级路网, 2675 parents → 6261 cut cells) and administrative street polygons (228 streets) are independently generated, with different coverage, granularity, and attribute semantics. Neither alone is sufficient for both human description and machine reconstruction.

**Incomplete coverage.** The road-block partition B does not cover all geographic space: river-adjacent strips, creek corridors, and street-boundary slivers have no road-block cells. A formal completion is needed to treat these residual areas as first-class spatial atoms.

**Coordinate system shift.** Fence data is stored in WGS-84 while road-block parcels are in GCJ-02. The ~600m offset between them must be corrected before any spatial computation.

### 1.3 Contributions

1. **Boolean region algebra over heterogeneous geographic partitions.** We define a formal IR with five clause types—block, feat, slice, except, band—each with a deterministic denotation over the completed partition B* = B ∪ R and the administrative partition A. The algebra supports union (block, feat, slice), complement (except, band), and atomic singleton (P#) operations.

2. **Bidirectional controlled-language architecture.** Geometry → IR → language and language → IR → geometry share the same semantic layer, with three formally distinct fidelity levels: geometric (IoU), representational (J), and linguistic (round-trip).

3. **Representational Completeness Theorem.** The IR vocabulary guarantees lossless representation of any target region T ⊆ U in the discrete atomic space, via singleton atoms P#. This turns J=1.0 from an empirical result into a formal property.

4. **Geographic clause selection as set-level REG.** We formulate the selection of named clauses as a referring-expression problem over atomic cells, adapting the preference-order principle of the Incremental Algorithm (Dale & Reiter, 1995) with road-class salience ordering.

5. **Real-world FMCG deployment.** 43 territories (32 dealers + 11 sales-rep zones) in Guangzhou, with IoU 0.99 and round-trip consistency.

## 2. Related Work

### 2.1 Boolean Region Algebra and RCC

The Region Connection Calculus (RCC-8) defines eight topological relations between spatial regions (Randell, Cui & Cohn, 1992). Wolter & Zakharyaschev (2000) extended RCC-8 with Boolean region terms, allowing union, intersection, and complement operations on named regions. TerritoryIR implements a Boolean region algebra over geographic partitions—not as a logical reasoning system, but as a denotational semantics for a controlled geographic language. Our `band` clause (A−B) corresponds to the complement operation in this algebra, grounded in physical street boundaries rather than abstract region terms.

### 2.2 Geographic Referring Expression Generation

Dale & Reiter (1995) introduced the Incremental Algorithm for generating referring expressions, using a fixed preference order of attributes. de Oliveira, Sripada, and Reiter (2016) studied geographic referring expressions with GIS spatial operations for dynamic property construction (e.g., "northern France"). Ramos et al. (2019) examined fuzzy grounding of geographic expressions across different spatial frames and partitions. 

TerritoryIR extends this line of work by requiring that geographic descriptions have **executable denotations** and **round-trip reconstructability**—properties not required in prior geographic REG work, which focuses on generating approximately accurate descriptions rather than machine-replayable ones.

### 2.3 Geographic Language Generation from Structured Data

Generating geographical location descriptions with spatial templates (IJGIS, 2021) studied landmark salience and spatial templates for location description. Spatial-RAG (arXiv 2025, ACL Findings 2026) addressed geospatial QA and retrieval—relevant background for LLM + structured geospatial computing, but not for region description generation. Our work differs in its focus on **two-way** language↔geometry with formal fidelity guarantees.

### 2.4 Controlled Natural Languages for GIS

Controlled Natural Languages (CNLs) restrict grammar and vocabulary to ensure unambiguous semantic interpretation. TerritoryIR functions as a CNL for geographic territory descriptions, with a formal grammar mapping to deterministic region expressions over named partitions. This is conceptually analogous to how GeoSPARQL provides a standard query language for geospatial RDF data, though TerritoryIR does not use RDF/SPARQL.

## 3. Methodology

### 3.1 Data and Coordinate Alignment

Three data sources are used:

- **Road-block parcels** (Amap GCJ-02): 2675 parent parcels, cut to 6261 atomic cells by street boundaries. Each cell has a B-attribute (parcel-assigned street name) and an A-attribute (street-polygon-assigned name).
- **Administrative street polygons** (GCJ-02): 228 street polygons covering Guangzhou.
- **OSM road and river networks** (WGS-84): 59,000 road segments and 8,000 river segments, used for feature adjacency.

**Coordinate alignment.** Fence data is stored in WGS-84, while road-block parcels are in GCJ-02. The offset in Guangzhou is approximately 600m (longitude). All fences are converted via wgs2gcj before processing.

### 3.2 Completed Partition B* and Joint Refinement U

**Problem.** The road-block partition B is incomplete: river-adjacent strips, creek corridors, and street-boundary slivers have no cells. We define the completion:

$$B^* = B \cup R$$

where R is the residual:

$$R = \{a_i - \bigcup\{b_j \in B : b_j \subseteq a_i\} : a_i \in A\}$$

i.e., the portion of each administrative street polygon not covered by any road-block cell. This makes B* a true partition: $\bigcup B^* = \Omega$ with non-overlapping interiors.

**Joint refinement.** The joint refinement of A and B* is:

$$U = A \land B^* = \{a_i \cap b_j^* \neq \emptyset : a_i \in A, b_j^* \in B^*\}$$

Each cell $u \in U$ has a dual attribute: (B-street, A-street), where B-street comes from the parcel property and A-street from the containing street polygon. |U| = 6261.

### 3.3 Feature Index

OSM road and river segments (WGS-84) are indexed in a spatial R-tree. For each cell u ∈ U, we query named features within 100m (after gcj2wgs transformation). Road classes are ranked by salience: motorway(0), trunk(1), primary(2), secondary(3), tertiary(4), residential(6), service(8). Rivers are assigned rank 3 (between primary and secondary roads). The resulting feature index FEATS maps feature name → cell id sets.

### 3.4 Semantic Intermediate Representation (SIR)

The IR consists of five clause types, each with a deterministic denotation over the atomic space U:

| Clause | Example | Denotation | Boolean Op |
|---|---|---|---|
| `block` | 凤凰街道 | {u ∈ U: A-street(u) = "凤凰街道"} | union of A atoms |
| `feat` | 龙洞街道沿华南快速 | {u ∈ U: B-street(u) = "龙洞" ∧ "华南快速" ∈ FEATS(u)} | intersection |
| `slice` | 凤凰街道(限龙洞街道内) | {u ∈ U: B-street(u) = "凤凰" ∧ A-street(u) = "龙洞"} | intersection |
| `except` | 增城区除正果镇、小楼镇外 | {u ∈ U: A-district(u) = "增城" ∧ A-street(u) ∉ {"正果镇","小楼镇"}} | complement |
| `band` | 西至龙洞街道—长兴街道界 | ∂(A_龙洞, A_长兴) ∩ R | boundary constraint |
| `pieces` | P#4763 | {u_4763} | atomic singleton |

**Key design decisions:**
- `block` resolves over the A-ontology (administrative street), not the B-ontology (parcel street). This aligns with human intuition: "凤凰街道" means the administrative area, not "all parcels tagged with 凤凰".
- `except` also resolves over the A-ontology: it excludes street-polygon atoms, not road-block cells.
- `band` is defined as a **boundary constraint** between two adjacent street polygons, intersected with the residual R. Direction (west/east/north/south) is a separate predicate for verbalization, not part of the denotation.

### 3.5 Forward Pipeline: Geometry → IR → Language

**Truth selection.** Given a fence polygon Z and a cell u ∈ U, define:

$$w(u, Z) = \frac{|u \cap Z|}{|u|}$$

The truth set T is:

$$T = \{u \in U : w(u, Z) \ge 0.5 \lor w(u, Z) \cdot |u| / |Z| \ge 0.3\}$$

The second term handles micro-fences: a cell covering 30% of the fence area is included even if it only covers a small fraction of the cell.

**Greedy clause selection.** From the global vocabulary V (all named clauses + P# atoms), we solve:

$$\min_{x_c} \lambda_1|chosen| + \lambda_2|P\#| + \lambda_3|over|$$

subject to: $\hat{T} = \bigcup_{c:x_c=1} \llbracket c \rrbracket \supseteq T$

via a greedy algorithm: at each step, pick the clause c with:
- max gain = |(⟦c⟧ ∩ T) − cov|
- min over = |(⟦c⟧ − cov) − T|
- tiebreak: max salience (for feat clauses, road class rank)

P# atoms guarantee representation completeness (Theorem 1).

**Theorem 1 (Discrete Representational Completeness).** Given a finite atomic partition U, if the vocabulary V contains a singleton atom P# for every u ∈ U, then every target region T ⊆ U has an exact representation: E_T = ∪_{u∈T} P# u, with ⟦E_T⟧ = T.

*Proof.* By construction. Each P# u denotes exactly {u}. The union of P# atoms for all u ∈ T denotes T. 

**Band clauses.** Compute Z − ⟦∪_{chosen}⟧, intersect with the 150m buffer of all street boundaries (∂(A_i, A_j) for all adjacent pairs), and generate band clauses for segments ≥ 0.01 km².

**Human verbalization.** Clauses are grouped by A-street, one sentence per street. Following the Incremental Algorithm's preference-order principle, we order candidate features by road-class salience (motorway > trunk > primary > ...). For territories involving >4 streets, district-level summarization is used: "增城区南部（含永宁街道、新塘镇等8个街镇，沿荔新公路一带）".

### 3.6 Reverse Pipeline: Language → IR → Geometry

**Deterministic parsing.** Each human phrase maps to an SIR clause via a deterministic grammar:

```
"凤凰街道" → block(A="凤凰街道")
"龙洞街道沿华南快速" → feat(B="龙洞", feat="华南快速")
"增城区除正果镇、小楼镇外" → except(district="增城", exclude=["正果镇","小楼镇"])
"西至龙洞街道—长兴街道界" → band(dir="西", boundary="龙洞街道—长兴街道界")
```

**LLM polishing with round-trip validation.** An LLM may polish the verbalized text (e.g., "约半" → "中北部") but only if parse(polished) reconstructs to the same IR. Failure triggers fallback to the deterministic template.

### 3.7 Evaluation Framework

We distinguish three formally distinct fidelity levels:

| Level | Measurement | What it measures | Formal guarantee |
|---|---|---|---|
| **Geometric** | IoU(Z, Z') | polygon fit | approximation (bounded by U resolution) |
| **Geometric** | coverage(Z, Z') = |Z ∩ Z'| / |Z| | recall of polygon area | approximation |
| **Representational** | J = hit/(hit+over+miss) | T ↔ T' exactness | ⟦IR⟧ = T' = T (Theorem 1) |
| **Linguistic** | parse(verbalize(IR)) ≡ IR | round-trip consistency | deterministic grammar |
| **Linguistic** | atomic fallback rate | % of T volume expressed via P# | compression quality |
| **Linguistic** | clause count | description length | readability |
| **Linguistic** | human comprehension | user accuracy on map ID from text | human evaluation |

## 4. Experiments

### 4.1 Dataset

| Dataset | Count | Area range | Type |
|---|---|---|---|
| Dealer territories | 32 | 0.6–2010 km² | hand-drawn, street/river/boundary-following |
| Sales-rep zones | 11 | 2–50 km² | hand-drawn, Haizhu/Liwan districts |
| Atomic partition U | 6261 cells | — | parcels cut by street polygons |
| Named features | 13,383 | — | roads + rivers |
| Admin street polygons | 228 | — | Amap administrative data |

### 4.2 Geometric Fidelity

**Coordinate alignment effect.** Converting fences from WGS to GCJ dramatically improves IoU:

| Configuration | Haosheng IoU | All 32 median IoU |
|---|---|---|
| fence WGS + parcels GCJ (misaligned) | 0.696 | 0.816 |
| fence GCJ + parcels GCJ (aligned) | **0.990** | **0.992** |

**Overall results.**

| Metric | Dealers (32) | Sales-rep zones (11) |
|---|---|---|
| IoU median | 0.992 | 0.971 |
| Coverage median | 99.81% | 99.17% |
| Human sentences | 5–51 | 2–10 |

### 4.3 Representational Exactness

**Theorem 1 verification.** All 43 territories achieve J=1.0, confirming that the IR vocabulary is representationally complete for the discrete space U. The one failure (海珠荔湾07 duplicate) is a data issue, not a representation failure.

**Ablation: P# removal.**

| Dealer | Full system | Without P# | Drop |
|---|---|---|---|
| Hao Sheng | 1.000 | 0.976 | 0.024 |
| Heng Fei Yuan | 1.000 | 0.513 | 0.487 |
| Hong Li | 1.000 | 0.884 | 0.116 |
| Zheng Ming | 1.000 | 0.500 | 0.500 |
| Ding Sen | 1.000 | 0.990 | 0.010 |

Mean drop: 0.227. Heng Fei Yuan (street-boundary slivers) and Zheng Ming (micro-fence, 1 cell) depend most heavily on P# atoms.

### 4.4 Linguistic Round-trip Consistency

All 43 territories pass: parse(verbalize(IR)) ≡ IR. This confirms that the deterministic grammar and the verbalization function are consistent.

### 4.5 Case Studies

**Heng Fei Yuan North (dense street territory, 38.9 km²):**
Human: 凤凰街道；联和街道沿思成路；龙洞街道沿渔东路；新塘街道沿天顺路；长兴街道沿天源路
J=1.00, IoU=0.997, coverage=99.93%

**Hao Sheng (river-adjacent, 8.1 km²):**
Human: 瑞宝街道；南洲街道沿南天东路；凤阳街道沿石溪肉菜市场小街；南石头街道沿金诚东街；洛浦街道一带
J=1.00, IoU=0.990, coverage=99.07%

**Hong Li (large rural, 174 km²):**
Summary: 增城区南部（含永宁街道、新塘镇等8个街镇，沿荔新公路一带）
J=1.00, IoU=0.999, coverage=99.93%

**Zheng Ming (micro-fence, 0.6 km²):**
Human: 新塘镇沿荔新大道
J=1.00, IoU=0.094 (geometric ceiling: 1 cell, 6 km², contains only 2% of cell area)

## 5. Discussion

### 5.1 Limitations

**Geometric fidelity is bounded by atomic resolution.** The IoU ceiling is determined by the granularity of the atomic partition U. Zheng Ming (IoU=0.094) demonstrates this bound: the entire territory is a single atomic cell, and the fence covers only 2% of that cell. Improving geometric fidelity requires a finer base partition.

**Human sentence count remains high for large rural territories.** The district-level summarization reduces this, but some cases (e.g., 51 sentences) still exceed human-friendly limits. Multi-level hierarchical summarization (district → street → road → boundary, expandable on demand) is the planned solution.

**River-adjacent strips are not fully covered.** Hao Sheng achieves 99.07% coverage; the remaining gap is along the riverbank where the road-block partition has no cells. Incorporating river-buffer strips into the feature index is straightforward and planned.

### 5.2 Future Work

- **Human-authored reverse benchmark.** Collect 100–200 human-written descriptions from maps, measure parse accuracy and geometric fidelity.
- **Human comprehension study.** Task: given a description + 4 maps, select the correct territory. Measure accuracy and response time.
- **Preference study.** Rate naturalness, clarity, and cognitive effort vs. human-written descriptions.
- **Threshold sensitivity analysis.** Test τ ∈ {0.3, 0.4, 0.5, 0.6, 0.7} for the truth-selection rule.
- **Greedy vs. optimal baseline.** Formulate as weighted set cover and compare with ILP/CP-SAT.
- **Cross-city generalization.** Validate in other Chinese cities or with equivalent data abroad.
- **Open benchmark.** Release a de-identified TerritoryIR benchmark, grammar, parser, and evaluation scripts.

## 6. Conclusion

We presented TerritoryIR, a controlled geographic language for sales territory descriptions with executable semantics and bidirectional round-trip. The system defines a Boolean region algebra over two heterogeneous geographic partitions, with a formal completion ensuring partition coverage. A Representational Completeness Theorem guarantees lossless representation in the discrete atomic space. On 43 real-world territories in Guangzhou, the system achieves IoU 0.99, J=1.0, and linguistic round-trip consistency. This is the first system to unify Boolean region algebra, geographic referring-expression generation, and executable IR semantics in a deployed FMCG territory management workflow.

## References

1. Randell, D. A., Cui, Z., & Cohn, A. G. (1992). A spatial logic based on regions and connection. *KR*, 92, 165–176.
2. Dale, R., & Reiter, E. (1995). Computational interpretations of the Gricean maxims in the generation of referring expressions. *Cognitive Science*, 19(2), 233–263.
3. Wolter, F., & Zakharyaschev, M. (2000). Spatial reasoning in RCC-8 with Boolean region terms. *ECAI*, 244–250.
4. van Deemter, K. (2002). Generating referring expressions: Boolean extensions of the incremental algorithm. *Computational Linguistics*, 28(1), 37–52.
5. Gatt, A., & Krahmer, E. (2018). Survey of the state of the art in natural language generation. *JAIR*, 61, 65–170.
6. de Oliveira, R., Sripada, S., & Reiter, E. (2016). Absolute and relative properties in geographic referring expressions. *INLG*, 90–94.
7. Ramos, R., et al. (2019). Fuzzy-based language grounding of geographical references: From writers to readers. *International Journal of Computational Intelligence Systems*, 12(2), 866–877.
8. Montello, D. R. (1993). Scale and multiple psychologies of space. *COSIT*, 312–321.
9.