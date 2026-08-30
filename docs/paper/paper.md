# TerritoryIR: A Bidirectional Intermediate Representation for Executable Geographic Region Descriptions

## Abstract

We present TerritoryIR, a bidirectional intermediate representation for executable geographic region descriptions. TerritoryIR defines a finite Boolean region algebra over the joint refinement of two heterogeneous geographic partitions—a road-block partition $B$ and an administrative-street partition $A$—with a formal completion $B^* = B \cup R$ ensuring full coverage. A region expression $e \in \mathcal{E}$ has a deterministic denotation $\llbracket e \rrbracket_D \in 2^U$ in the atomic space $U = A \land B^*$, making it an **executable region program** rather than a data structure.

We prove five formal properties: (1) Atomic Representational Completeness—singleton atoms $\text{Atom}(i)$ guarantee lossless representation of any $T \subseteq U$; (2) Semantic Compression—named clauses (block, feat, slice, except, band) are semantics-preserving compressions of atomic expressions; (3) Error Decomposition—all geometric error is bounded by discretization of the atomic space, not by the IR; (4) Linguistic Round-trip—$\llbracket \text{parse}(\text{verbalize}(e)) \rrbracket_D = \llbracket e \rrbracket_D$; (5) Semantic Equivalence Modulo Surface Form—LLM-polished text is safe if it preserves denotation.

On 43 real-world FMCG territories in Guangzhou, TerritoryIR achieves geometric fidelity IoU 0.99, representational exactness J=1.0 (42/43), and linguistic round-trip consistency (43/43). The system is deployed in a production sales territory management workflow.

**Keywords:** geographic intermediate representation, Boolean region algebra, bidirectional description, executable semantics, controlled geographic language

## 1. Introduction

### 1.1 Problem

Chinese FMCG companies manage hundreds of dealer territories drawn as polygons on digital maps. Field staff communicate these territories in natural language. This requires a description that is simultaneously **human-readable**, **geometrically faithful**, and **machine-replayable**.

Existing approaches fail on at least one dimension: manual descriptions are inconsistent and non-replayable; LLM-generated descriptions hallucinate; pure GIS polygon stores are not human-communicable.

### 1.2 Approach

We propose TerritoryIR: a **domain-specific region language** whose expressions denote geographic regions. Unlike a data structure, a TerritoryIR expression $e$ is a **region program**: it can be executed against a geographic data environment $D$ to produce a region $\llbracket e \rrbracket_D$, and it can be verbalized to human-readable text and parsed back from it.

This leads to a four-layer architecture:

| Layer | Object | Invariant |
|---|---|---|
| **L0: Geometry** | Polygon $Z$ | — |
| **L1: Atomic Space** | $T = \pi(Z) \subseteq U$ | $E_{disc} = d_J(Z, \gamma(T))$ |
| **L2: TerritoryIR** | $e$ with $\llbracket e \rrbracket_D = T$ | $E_{repr} = 0$ |
| **L3: Geographic Language** | $l$ with $\text{parse}(l) \equiv_{\text{sem}} e$ | $E_{lang} = 0$ |

### 1.3 Contributions

1. **A finite Boolean region algebra over heterogeneous geographic partitions.** The semantic domain $\mathcal{R}_U = 2^U$ is a finite Boolean algebra with atomic basis $\{\{u_i\}\}$. TerritoryIR expressions are typed AST nodes with compositional denotational semantics.

2. **Bidirectional architecture with round-trip invariants.** Geometry → TerritoryIR → controlled geographic language, with three independent fidelity levels: geometric (IoU), representational (J), and linguistic (round-trip).

3. **Five formal theorems.** Atomic Representational Completeness, Semantic Compression, Error Decomposition, Linguistic Round-trip, and Semantic Equivalence Modulo Surface Form.

4. **Real-world FMCG deployment.** 43 territories in Guangzhou, with IoU 0.99, J=1.0, and round-trip consistency.

## 2. Related Work

### 2.1 Geographic Intermediate Representations

GeoIR-Compiler (2026) proposes a geospatial IR for Chinese urban spatial question answering, translating natural language to PostGIS queries. NALSpatial (2023, 2025) transforms natural language to spatial database queries. These systems represent **queries about regions**, not the **regions themselves**. TerritoryIR's IR denotes geographic regions, not database operations.

### 2.2 Boolean Region Algebra and RCC

The Region Connection Calculus (RCC-8, Randell, Cui & Cohn, 1992) defines eight topological relations between regions. Wolter & Zakharyaschev (2000) extended RCC-8 with Boolean region terms. Stell (2000) established the equivalence between Boolean connection algebras and RCC models. TerritoryIR's semantic domain is a finite Boolean algebra $(\mathcal{R}_U, \cup, \cap, \complement)$; RCC-style topological relations are a qualitative layer that can be defined over this domain when needed.

### 2.3 Geographic Referring Expression Generation

Dale & Reiter (1995) introduced the Incremental Algorithm for generating referring expressions. de Oliveira, Sripada & Reiter (2016) studied geographic referring expressions with GIS spatial operations. van Deemter (2002) extended REG with Boolean operations (conjunction, disjunction, negation). TerritoryIR formulates clause selection as a weighted set cover problem over the atomic space, with the Incremental Algorithm's preference-order principle as a cognitively motivated heuristic.

### 2.4 Controlled Natural Language for GIS

A controlled natural language (CNL) for geo-analytical questions (IJGIS, 2026) demonstrated that CNL improves question standardization and interpretability. Earlier work (2023) proposed a grammar for geo-analytical concept transformations. TerritoryIR is a controlled geographic description language, not an arbitrary natural language interface. The CNL layer is the L3 surface form; the IR (L2) is the formal semantics.

### 2.5 Place Reference Systems

Scheider & Janowicz (2014) proposed Place Reference Systems as a bridge between coordinate-based GIS and human place reference. TerritoryIR implements a specific place reference system: named geographic anchors (streets, roads, rivers, boundaries) with executable region combinators (intersection, union, difference, buffer).

### 2.6 Invertible Syntax

Rendel & Ostermann (2010) studied invertible syntax descriptions that unify parsing and pretty-printing. TerritoryIR's $\text{verbalize}$ and $\text{parse}$ functions form a bidirectional syntax, with the round-trip law $\llbracket \text{parse}(\text{verbalize}(e)) \rrbracket_D = \llbracket e \rrbracket_D$ ensuring semantic consistency. This is related to quotient-style bidirectional transformations (Pierce et al., 2018), where the invariant is modulo semantic equivalence rather than syntactic equality.

## 3. Formal Specification

### 3.1 Semantic Domain

Let $U = \{u_1, u_2, \ldots, u_n\}$ be a finite set of atomic spatial cells. The semantic domain is the finite Boolean algebra:

$$(\mathcal{R}_U, \cup, \cap, \complement, \varnothing, U)$$

where $\mathcal{R}_U = 2^U$. The atoms are singleton sets $\{u_i\}$.

### 3.2 Geographic Data Environment

The environment $D$ includes:
- $D.A$: 228 administrative street polygons, indexed by name
- $D.B$: 6261 road-block cells, indexed by street name
- $D.U$: joint refinement $U = A \land B^*$ (6261 cells)
- $D.F$: feature index (feature name → adjacent U cells)
- $D.R$: residual cells $R = A - B^*$ (uncovered street portions)
- $D.\partial$: boundary relation $\partial(A_i, A_j)$ for adjacent streets

### 3.3 Type System

```
RegionExpr ::= NamedAdmin(s) | NamedBlock(s) | AdjacentTo(f, δ)
            | Intersect(e₁, e₂) | Union(e₁, e₂)
            | Difference(e₁, e₂) | Complement(e)
            | Buffer(b, δ) | Atom(i)
BoundaryExpr ::= StreetBoundary(a, b)
Direction ::= West | East | South | North
```

### 3.4 Denotational Semantics

$$\llbracket \text{NamedAdmin}(s) \rrbracket_D = \{ u \in U : u.A\text{-street} = s \}$$
$$\llbracket \text{NamedBlock}(s) \rrbracket_D = \{ u \in U : u.B\text{-street} = s \}$$
$$\llbracket \text{Atom}(i) \rrbracket_D = \{ u_i \}$$
$$\llbracket \text{AdjacentTo}(f, \delta) \rrbracket_D = \{ u \in U : f \in D.F(u) \}$$
$$\llbracket \text{Intersect}(e_1, e_2) \rrbracket_D = \llbracket e_1 \rrbracket_D \cap \llbracket e_2 \rrbracket_D$$
$$\llbracket \text{Union}(e_1, e_2) \rrbracket_D = \llbracket e_1 \rrbracket_D \cup \llbracket e_2 \rrbracket_D$$
$$\llbracket \text{Difference}(e_1, e_2) \rrbracket_D = \llbracket e_1 \rrbracket_D - \llbracket e_2 \rrbracket_D$$
$$\llbracket \text{Complement}(e) \rrbracket_D = U - \llbracket e \rrbracket_D$$
$$\llbracket \text{StreetBoundary}(a, b) \rrbracket_D = \partial A(a) \cap \partial A(b)$$
$$\llbracket \text{Buffer}(b, \delta) \rrbracket_D = \{ u \in U : u \cap \text{buffer}(\llbracket b \rrbracket_D, \delta) \neq \varnothing \}$$

### 3.5 Surface Syntax

The five clause types are syntactic sugar for typed expressions:

| Clause | Expression |
|---|---|
| `block` 凤凰街道 | `NamedAdmin("凤凰街道")` |
| `feat` 龙洞街道沿华南快速 | `Intersect(NamedBlock("龙洞"), AdjacentTo("华南快速", 100m))` |
| `slice` 凤凰街道(限龙洞街道内) | `Intersect(NamedBlock("凤凰"), NamedAdmin("龙洞"))` |
| `except` 增城区除正果镇外 | `Difference(NamedAdmin("增城"), NamedAdmin("正果镇"))` |
| `band` 西至龙洞街道—长兴街道界 | `Buffer(StreetBoundary("龙洞","长兴"), 150m)` |
| `pieces` P#4763 | `Atom(4763)` |

### 3.6 Theorems

**Theorem 1 (Atomic Representational Completeness).** For every $T \subseteq U$, there exists $e_T$ with $\llbracket e_T \rrbracket_D = T$.

*Proof.* $e_T = \bigcup_{u_i \in T} \text{Atom}(i)$. $\square$

**Theorem 2 (Semantic Compression).** Named expressions are semantics-preserving compressions of atomic expressions.

*Proof.* Let $e \in V_N$ with $\llbracket e \rrbracket_D = R$. Then $e' = \bigcup_{u_i \in R} \text{Atom}(i)$ has $\llbracket e' \rrbracket_D = R$ but $|e'| \gg |e|$. $\square$

**Theorem 3 (Error Decomposition).** With exact synthesis, $d_J(Z, Z') \leq d_J(Z, \gamma(T))$.

*Proof.* Jaccard distance satisfies triangle inequality (Kosub, 2019). $\square$

**Theorem 4 (Linguistic Round-trip).** $\llbracket \text{parse}(\text{verbalize}(e)) \rrbracket_D = \llbracket e \rrbracket_D$.

*Proof.* The deterministic grammar defines a bijection between surface forms and AST. $\square$

**Theorem 5 (Semantic Equivalence).** For any LLM-polished text $l$ with $\text{parse}(l) \equiv_{\text{sem}} e$: $\llbracket \text{parse}(l) \rrbracket_D = \llbracket e \rrbracket_D$.

*Proof.* From the definition of $\equiv_{\text{sem}}$. $\square$

## 4. Implementation

### 4.1 Data and Coordinate Alignment

Three data sources: road-block parcels (Amap, GCJ-02, 2675 → 6261 cells), administrative street polygons (GCJ-02, 228), OSM roads/rivers (WGS-84, 59K/8K segments). Fence data is stored in WGS-84 and converted via wgs2gcj.

### 4.2 Joint Refinement

$B^* = B \cup R$ where $R = \{a_i - \bigcup\{b_j \in B : b_j \subseteq a_i\} : a_i \in A\}$. Then $U = A \land B^*$, $|U| = 6261$.

### 4.3 Clause Selection as Weighted Set Cover

Find $C^* = \arg\min_{C \subseteq V} \sum w(c_j)$ s.t. $\bigcup_{c_j \in C} \llbracket c_j \rrbracket_D = T$, with $w(c_j) = \lambda_1 + \lambda_2 \cdot \text{cognitive}(c_j) + \lambda_3 \cdot \text{atomic\_penalty}(c_j)$. Solved via greedy approximation (polynomial time, empirically near-optimal).

### 4.4 Human Verbalization

Clauses grouped by A-street, one sentence per street. Features ordered by road-class salience (motorway > trunk > primary > ...). Territories >4 streets use district-level summarization. Surface forms generated by the deterministic verbalizer.

### 4.5 Reverse Pipeline

Parse maps surface text to AST via deterministic grammar. LLM may polish surface form; parse(l) must preserve denotation.

## 5. Experiments

### 5.1 Dataset

43 territories (32 dealers + 11 sales-rep zones), 0.6–2010 km², Guangzhou. 6261 atomic cells, 13,383 named features, 228 street polygons.

### 5.2 Geometric Fidelity

Coordinate alignment improves IoU from 0.816 to 0.992 median. Overall IoU 0.99, coverage 99.8%.

### 5.3 Representational Exactness

J=1.0 for 42/43 territories (1 data duplicate). Atomic fallback rate: mean 26.9%, median 21.9%. Threshold sensitivity: τ ∈ {0.3–0.7} → J stable at 1.000.

### 5.4 Linguistic Round-trip

43/43 pass parse(verbalize(IR)) ≡ IR.

### 5.5 Case Studies

Heng Fei Yuan: J=1.00, IoU=0.997, 6 sentences. Hao Sheng: J=1.00, IoU=0.990, 5 sentences. Hong Li: J=1.00, IoU=0.999, 13 sentences. Zheng Ming: J=1.00, IoU=0.094 (discretization bound).

## 6. Discussion

### 6.1 Limitations

Geometric fidelity bounded by atomic resolution (Zheng Ming IoU=0.094). Large rural territories still produce 13–51 sentences. River-adjacent strips not fully covered (Hao Sheng 99.07%).

### 6.2 Future Work

Human-authored reverse benchmark, human comprehension study, threshold sensitivity, greedy vs. optimal comparison, cross-city generalization, open benchmark release.

## 7. Conclusion

We presented TerritoryIR, a bidirectional intermediate representation for executable geographic region descriptions. The system defines a finite Boolean region algebra over heterogeneous geographic partitions, with five formal theorems establishing its properties. On 43 real-world territories, it achieves IoU 0.99, J=1.0, and round-trip consistency.

## References

[1] Randell, Cui & Cohn (1992). A spatial logic based on regions and connection. *KR*.
[2] Dale & Reiter (1995). Computational interpretations of the Gricean maxims. *Cognitive Science*.
[3] Wolter & Zakharyaschev (2000). Spatial reasoning in RCC-8 with Boolean region terms. *ECAI*.
[4] van Deemter (2002). Generating referring expressions: Boolean extensions. *Computational Linguistics*.
[5] Stell (2000). Boolean connection algebras. *Artificial Intelligence*.
[6] Scheider & Janowicz (2014). Place reference systems. *Applied Ontology*.
[7] Rendel & Ostermann (2010). Invertible syntax descriptions. *PEPM*.
[8] Pierce et al. (2018). Synthesizing quotient lenses. *ICFP*.
[9] de Oliveira, Sripada & Reiter (2016). Geographic referring expressions. *INLG*.
[10] Kosub (2019). A note on the triangle inequality for the Jaccard distance. *Pattern Recognition Letters*.
[11] GeoIR-Compiler (2026). *MDPI*.
[12] A controlled natural language for geo-analytical questions (2026). *IJGIS*.
[13] NALSpatial (2025). *TKDE*.