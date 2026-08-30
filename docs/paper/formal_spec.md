# TerritoryIR Formal Specification v1.0

## 1. Semantic Domain

Let $U = \{u_1, u_2, \ldots, u_n\}$ be a finite set of atomic spatial cells (the joint refinement of the road-block partition $B$ and the administrative partition $A$). The semantic domain of TerritoryIR is the finite Boolean algebra:

$$(\mathcal{R}_U, \cup, \cap, \complement, \varnothing, U)$$

where $\mathcal{R}_U = 2^U$.

The atoms of this algebra are the singleton sets $\{u_i\}$. Every region $R \in \mathcal{R}_U$ can be uniquely expressed as a join of atoms:

$$R = \bigvee_{u_i \in R} \{u_i\}$$

## 2. Denotational Semantics

A TerritoryIR expression $e \in \mathcal{E}$ denotes a region $\llbracket e \rrbracket_D \in \mathcal{R}_U$ under a geographic data environment $D$.

### 2.1 Environment

The environment $D$ consists of:

- $D.A$: administrative street polygons (228 cells), indexed by name
- $D.B$: road-block cells (6261 cells), indexed by parcel-assigned street name
- $D.U$: joint refinement $U = A \land B^*$ (6261 cells)
- $D.F$: feature index (feature name → set of adjacent U cells)
- $D.R$: residual cells $R = A - B^*$ (uncovered portions of streets)
- $D.\partial$: boundary relation $\partial(A_i, A_j)$ for adjacent street pairs

### 2.2 Type System

```
RegionExpr ::= 
    NamedAdmin(name: string)                    → Region
  | NamedBlock(name: string)                    → Region  
  | AdjacentTo(feature: string, δ: float)       → Region
  | Intersect(e1: RegionExpr, e2: RegionExpr)   → Region
  | Union(e1: RegionExpr, e2: RegionExpr)       → Region
  | Difference(e1: RegionExpr, e2: RegionExpr)  → Region
  | Complement(e: RegionExpr)                   → Region
  | Buffer(b: BoundaryExpr, δ: float)           → Region
  | Atom(id: int)                               → Region

BoundaryExpr ::=
    StreetBoundary(a: string, b: string)        → Boundary

Direction ::= West | East | South | North
```

### 2.3 Denotation Functions

**Base expressions:**

$$\llbracket \text{NamedAdmin}(s) \rrbracket_D = \{ u \in D.U : u.A\text{-street} = s \}$$

$$\llbracket \text{NamedBlock}(s) \rrbracket_D = \{ u \in D.U : u.B\text{-street} = s \}$$

$$\llbracket \text{Atom}(i) \rrbracket_D = \{ u_i \}$$

**Feature expressions:**

$$\llbracket \text{AdjacentTo}(f, \delta) \rrbracket_D = \{ u \in D.U : f \in D.F(u) \}$$

**Combinators:**

$$\llbracket \text{Intersect}(e_1, e_2) \rrbracket_D = \llbracket e_1 \rrbracket_D \cap \llbracket e_2 \rrbracket_D$$

$$\llbracket \text{Union}(e_1, e_2) \rrbracket_D = \llbracket e_1 \rrbracket_D \cup \llbracket e_2 \rrbracket_D$$

$$\llbracket \text{Difference}(e_1, e_2) \rrbracket_D = \llbracket e_1 \rrbracket_D - \llbracket e_2 \rrbracket_D$$

$$\llbracket \text{Complement}(e) \rrbracket_D = U - \llbracket e \rrbracket_D$$

**Boundary expressions:**

$$\llbracket \text{StreetBoundary}(a, b) \rrbracket_D = \partial D.A(a) \cap \partial D.A(b)$$

$$\llbracket \text{Buffer}(b, \delta) \rrbracket_D = \{ u \in D.U : u \cap \text{buffer}(\llbracket b \rrbracket_D, \delta) \neq \varnothing \}$$

### 2.4 Surface Syntax Mapping

The five surface clause types map to typed expressions:

| Surface Clause | Typed Expression |
|---|---|
| `block` 凤凰街道 | `NamedAdmin("凤凰街道")` |
| `feat` 龙洞街道沿华南快速 | `Intersect(NamedBlock("龙洞街道"), AdjacentTo("华南快速", 100m))` |
| `slice` 凤凰街道(限龙洞街道内) | `Intersect(NamedBlock("凤凰街道"), NamedAdmin("龙洞街道"))` |
| `except` 增城区除正果镇、小楼镇外 | `Difference(NamedAdmin("增城区"), Union(NamedAdmin("正果镇"), NamedAdmin("小楼镇")))` |
| `band` 西至龙洞街道—长兴街道界 | `Buffer(StreetBoundary("龙洞街道", "长兴街道"), 150m)` |
| `pieces` P#4763 | `Atom(4763)` |

## 3. Theorems

### Theorem 1: Atomic Representational Completeness

Let $U = \{u_1, \ldots, u_n\}$ be a finite atomic space. If the TerritoryIR vocabulary contains $\text{Atom}(i)$ for every $u_i \in U$, then for every target region $T \subseteq U$, there exists a TerritoryIR expression $e_T$ such that:

$$\llbracket e_T \rrbracket_D = T$$

**Proof.** By construction:

$$e_T = \bigcup_{u_i \in T} \text{Atom}(i)$$

Then:

$$\llbracket e_T \rrbracket_D = \bigcup_{u_i \in T} \llbracket \text{Atom}(i) \rrbracket_D = \bigcup_{u_i \in T} \{u_i\} = T$$

$\square$

### Theorem 2: Semantic Compression

Let $V_N \subset \mathcal{E}$ be the set of named expressions (block, feat, slice, except, band), and $V_P = \{\text{Atom}(i) : u_i \in U\}$ be the atomic expressions. For any expression $e \in V_N$, there exists an equivalent atomic expression $e' \in \mathcal{E}(V_P)$ such that:

$$\llbracket e \rrbracket_D = \llbracket e' \rrbracket_D$$

and typically $|e'| \gg |e|$ (the named expression is a compression of the atomic one).

**Proof.** By Theorem 1, every region is representable by atoms. The named expression $e$ denotes some region $R = \llbracket e \rrbracket_D$. Then $e' = \bigcup_{u_i \in R} \text{Atom}(i)$ has the same denotation. The size difference $|e'| - |e|$ is positive when $|R| > 1$ and $e$ uses non-atomic clauses.

$\square$

### Theorem 3: Error Decomposition

Let $Z$ be the original polygon, $T = \pi(Z) \subseteq U$ be the discretized target, $e$ be a TerritoryIR expression with $\llbracket e \rrbracket_D = T$, and $Z' = \gamma(T)$ be the geometric reconstruction. Then:

$$d_J(Z, Z') \leq d_J(Z, \gamma(T)) + d_J(\gamma(T), Z')$$

where $d_J$ is the Jaccard distance.

If the synthesis is exact ($\llbracket e \rrbracket_D = T$), then:

$$d_J(\gamma(T), Z') = 0$$

and therefore:

$$d_J(Z, Z') \leq d_J(Z, \gamma(T))$$

i.e., all geometric error is bounded by the discretization error of the atomic space $U$.

**Proof.** The Jaccard distance satisfies the triangle inequality (Kosub, 2019). When $\llbracket e \rrbracket_D = T$, we have $Z' = \gamma(\llbracket e \rrbracket_D) = \gamma(T)$, so $d_J(\gamma(T), Z') = 0$.

$\square$

### Theorem 4: Linguistic Round-trip

Let $\text{verbalize}: \mathcal{E} \to \mathcal{L}$ be the verbalization function and $\text{parse}: \mathcal{L} \to \mathcal{E}$ be the parsing function. For any expression $e \in \mathcal{E}$ generated by the deterministic grammar:

$$\llbracket \text{parse}(\text{verbalize}(e)) \rrbracket_D = \llbracket e \rrbracket_D$$

**Proof sketch.** The deterministic grammar defines a bijection between a subset of surface forms and the typed AST. The verbalize function maps each AST node to a unique surface form, and the parse function maps each surface form back to the original AST. Since the denotation function is compositional, the denotation is preserved.

$\square$

### Theorem 5: Semantic Equivalence Modulo Surface Form

Let $\equiv_{\text{sem}}$ be the semantic equivalence relation:

$$e_1 \equiv_{\text{sem}} e_2 \iff \llbracket e_1 \rrbracket_D = \llbracket e_2 \rrbracket_D$$

For any LLM-polished text $l$ such that $\text{parse}(l) \equiv_{\text{sem}} e$:

$$\llbracket \text{parse}(l) \rrbracket_D = \llbracket e \rrbracket_D$$

**Proof.** Immediate from the definition of $\equiv_{\text{sem}}$ and the compositionality of the denotation function.

$\square$

## 4. Optimization Problem

The clause selection problem is formalized as a weighted set cover:

Given vocabulary $V = \{c_1, \ldots, c_m\}$ with each clause $c_j$ denoting a set $S_j = \llbracket c_j \rrbracket_D \subseteq U$, and a target region $T \subseteq U$, find:

$$C^* = \arg\min_{C \subseteq V} \sum_{c_j \in C} w(c_j)$$

subject to:

$$\bigcup_{c_j \in C} S_j = T$$

where the weight function $w: V \to \mathbb{R}^+$ is:

$$w(c_j) = \lambda_1 + \lambda_2 \cdot \text{cognitive}(c_j) + \lambda_3 \cdot \text{atomic\_penalty}(c_j)$$

with $\text{atomic\_penalty}(c_j) = K$ if $c_j$ is an $\text{Atom}$ expression, and $0$ otherwise.

## 5. Error Budget

| Layer | Object | Invariant | Measurement |
|---|---|---|---|
| **L0: Geometry** | Polygon $Z$ | — | — |
| **L1: Atomic Space** | $T = \pi(Z) \subseteq U$ | $T$ is the ground truth region | $E_{disc} = d_J(Z, \gamma(T))$ |
| **L2: TerritoryIR** | $e$ with $\llbracket e \rrbracket_D = T$ | $T' = \llbracket e \rrbracket_D$ | $E_{repr} = d_J(\gamma(T), \gamma(T'))$ |
| **L3: Language** | $l$ with $\text{parse}(l) \equiv_{\text{sem}} e$ | $\llbracket \text{parse}(l) \rrbracket_D = \llbracket e \rrbracket_D$ | $E_{lang} = \begin{cases}0 & \text{if parse(l)} \equiv_{\text{sem}} e \\ 1 & \text{otherwise}\end{cases}$ |

Total error bound:

$$E_{total} \leq E_{disc} + E_{repr} + E_{lang}$$

With exact synthesis ($E_{repr} = 0$) and round-trip consistency ($E_{lang} = 0$):

$$E_{total} \leq E_{disc}$$