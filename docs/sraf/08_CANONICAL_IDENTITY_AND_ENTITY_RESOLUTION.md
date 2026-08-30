# SRAF Canonical Identity & Entity Resolution Specification v1.2

**Project:** Sales Resource Allocation Framework
**Abbreviation:** SRAF
**Document:** `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`
**Status:** Implementation Baseline v1.2
**Superseding specification:**

```text
00_PROJECT_CHARTER.md
01_WORLD_MODEL_SPEC.md
```

**Downstream referrers:** 02 / 03 / 04 / 05 / 06 / 07

---

## 1. Document Objective

`01_WORLD_MODEL_SPEC.md` specifies how the World "is represented":

```text
Canonical ID
ExternalIdentifier
Identity Mapping
Merge / Split Trace
```

but these are only **interface requirements**, not **decision rules**.

This document answers the questions that truly determine the success or failure of the system:

> **Given multiple records from multiple systems, on what basis does SRAF determine whether they are the same real-world entity;
> what happens if the determination is wrong; how to revoke it; and who has the authority to determine.

It must elevate Identity from a "data cleaning step" to:

# **A first-class, auditable governance object with evidence and time validity**

See §3 for reasons.

---

## 1A. Normative Ownership

This document solely owns:

```text
CanonicalIdentity lifecycle
ExternalIdentifier canonical schema
SourceRecord / Crosswalk
IdentityAssertion(SAME_AS / DISTINCT_FROM)
MatchCandidate / MatchDecision
IdentityCluster
Merge / Unmerge
Split
Supersede / Succession
RelocationResolution
RenameResolution
HierarchyResolution(Account ↔ AccountGroup ↔ ServiceLocation)
SurvivorshipPolicy
IdentityConfidence semantics
HumanIdentityResolution workflow
Identity Temporal Semantics
Identity Benchmark cases & metrics
```

This document **does not own** (only references):

```text
Account / ServiceLocation / Person canonical business attribute schema → 01
Assertion / Evidence / Observation / WorldEvent generic structure → 01
Semantic Status enumeration definition → 01
DecisionCase / CandidateDecision / Approval → 02
Responsibility / Coverage / Opportunity business semantics → 01 / 04
GW01 WorldModelRepair workflow → 05
B0 generic semantic invariants and Benchmark framework → 06
CanonicalIdentityService engineering implementation → 07
```

The Identity requirements in `01` Section 9-10 remain valid, but their **canonical schema belongs to 08**.
`01` should be changed to reference this document, and no second set of field definitions should be maintained (Charter P21).

---

## 2. Four Indistinguishable Boundary Lines

This is the core semantic discipline of this specification. No implementation and no Agent reasoning may cross them.

### 2.1 Identity Resolution ≠ Deduplication

```text
Deduplication: 
Find "duplicate-entered records" and delete them.
The object is record.
The goal is that the table becomes clean.
The success criterion is that the duplication rate decreases.

Identity Resolution: 
Establish a "record <-> real-world entity" mapping, and retain every source record.
The object is claim about the world.
The goal is that the canonical entity is unique and traceable.
The success criterion is that downstream decisions are not wrong because of identity.
```

Key difference:

```text
Dedup loses data.
Identity Resolution never loses SourceRecord.
```

A pair of records that "look duplicate" may be:

```text
Two codes for the same store      -> should be merged
Two neighboring stores with the same name        -> should be kept distinct
Two different business-type entities of the same store -> should be split into two Accounts
```

Therefore SRAF prohibits the appearance of:

```text
delete from account where duplicate
```

This kind of operation. Only allowed:

```text
link
resolve
merge (governance action, reversible)
supersede
```

### 2.2 Entity Merge ≠ Source Record Merge

```text
Source Record Merge (physical layer):
Merge two CRM/ERP records into one.
What changes is the source system or the import layer.

Entity Merge (semantic layer):
Announce "these two canonical entities are actually the same real-world object",
and re-attach all of their history, responsibilities, opportunities, and coverage to a single survivor.
What changes is the business truth, and it cascades into Opportunity / Territory / Workload.
```

Entity Merge is a **decision**, not an ETL.

Therefore it must reuse the governance chain from `02`:

```text
IdentityMergeProposal
      ↓
Evidence + ImpactAnalysis
      ↓
Authority (graded by impact scope)
      ↓
Approved Identity Resolution Record
      ↓
WorldEvent + downstream recomputation
```

**Prohibited**: attribute-level survivorship automatically rewriting business identity.

"Which entity should survive" and "which value its address should display" are two different questions:

```text
Survivorship (attribute value rules)  →  determines the golden record's fields
Identity (whether entities are the same)    →  determines how many real-world objects exist
```

Fields can be auto-selected by source-trust / recency rules;
Entity identity **cannot** be auto-merged by similarity threshold (§11, §14).

### 2.3 Account ≠ ServiceLocation

`01 §21–22` has established: Account is the commercial responsibility object, ServiceLocation is the physical location.
This document specifies their **identity-level independence**:

```text
Account identity: 
determined by "commercial responsibility continuity"
(contracts, settlement entity, customer relationship, responsibility attribution)

ServiceLocation identity: 
determined by "physical operating premises continuity"
(coordinates, address, store operating entity)
```

Therefore the four scenarios must each be expressible:

| Scenario | Account | ServiceLocation |
|---|---|---|
| Same store with new contract entity | New Account | Same Location |
| Customer changes address and continues operations | Same Account | New Location (old Location closed) |
| One address with multiple customers (two shops in same building) | Two Accounts | Two Locations or shared Location |
| One customer with multiple addresses (chain sub-area) | One Account | Multiple Locations |

**Forbidden**: Using coordinate distance to determine Account identity.
Coordinate consistency only supports Location layer candidate association, not Account layer SAME_AS.

### 2.4 Identity Confidence ≠ Business Truth

```text
identity_confidence = 0.93
```

Its meaning **can only be**:

> Under the current match_rule_version, current evidence set, and current model,
> the strength with which this pair of records is supported by the identity claim is 0.93.

It **does not equal**:

```text
They are indeed the same store
→ Therefore Opportunity can be merged
→ Therefore workload is 1.0 instead of 2.0
→ Therefore there is no personnel shortage
```

Confidence cannot be "laundered" into fact through downstream propagation. Each Derived State must be able to answer:

> The identity judgment I used, what confidence at that time, who approved it, which rule set was used.

This line is directly carried forward by `01 §28 Semantic Status`:

```text
Resolved Identity's Semantic Status:
CONFIRMED_MATCH + human approval → DerivedState (usable for planning)
PROVISIONAL_MATCH → still carries ModelEstimate nature, must propagate confidence
CANDIDATE → must not enter Structural Decision
```

---

## 3. Why Identity Is a Prerequisite for Decision (rather than Data Hygiene)

### 3.1 Error Propagation Chain

```text
Identity Error
      ↓
CommercialEntity count error
      ↓
OpportunityEstimate double counting / omission
      ↓
CoverageNeed / CoverageCommitment target object error
      ↓
WorkloadDemand error (IntrinsicWorkload summed by subject × activity)
      ↓
CapacityUtilization error
      ↓
AllocationGap (false positive or false negative)
      ↓
DiagnosticHypothesis (H-DATA not triggered, H-CAP mis‑selected)
      ↓
ProblemRouter routing error
      ↓
DecisionCase (should be WorldModelRepair, but went DP01 Expansion)
      ↓
Transition (real addition of personnel, real change of customer owner, real ChangeCost)
```

Once entering the final step,

### 3.2 Quantitative consequences of double counting (mandatory example)

`01 §35` freeze:

\[
IntrinsicWorkload
=
\sum_{activity}
CoverageCommitment_{activity}
\times
ExpectedServiceTime_{activity}
\]

If the same store has one unresolved record in CRM and one in DMS, and both are judged as high potential:

```text
CoverageCommitment: 2/month × 2 = 4/month
IntrinsicWorkload:              ×2
Territory workload:             +Δ (this store's contribution doubles)
CapacityUtilization:            inflated
```

Then:

```text
GlobalCapacityTest → shows overload
→ H-CAPACITY supporting evidence is established
→ suggests adding headcount
```

While the real reason is:

```text
H-DATA(Identity)
```

This is precisely the deep reason why `04 §22` requires DataQualityIssue to be a top-level alternative hypothesis.
**SRAF's H-DATA hypothesis is untestable before 08 lands.**

### 3.3 Reverse risk: over-merging

```text
Two adjacent but different stores being falsely merged
→ Coverage appears to meet target on the surface (one subject is covered)
→ Actually one is left uncovered
→ UncoveredOpportunity is hidden
→ The system looks healthier, but the business is worse
```

**Missed merge (duplicate) and false merge (false match) fail in opposite directions**,
but both pollute decisions. This is the basis for the dual-threshold design in §11.

### 3.4 Pollution of Historical Backtest and Validation

```text
Bitemporal replay requires that identity is also restorable under known_time (§15)
```

If identity is a "current state" single-value field, then:

```text
The 2026-Q1 Baseline will use the consolidation result only discovered in 2026-Q3
→ Look-ahead Bias(01 §32 / 06 §10)
→ The comparison object of DecisionValidation is modified after the fact
→ Unable to answer "why was this decided at that time"
```

Therefore the identity resolution result itself must be **bitemporal, append-only, versioned**.

---

## 4. Conceptual Layering

```text
L4  GOVERNANCE
IdentityResolutionRecord (who, when, based on what, approved what)

L3  SEMANTIC
CanonicalEntity (account:8a2f…) —— the unique representation of a real-world object
IdentityCluster          —— the entity set claimed to be the same object
    IdentityAssertion        —— SAME_AS / DISTINCT_FROM

L2  LINKAGE
IdentityLink             —— the attachment from SourceRecord ↔ CanonicalEntity
MatchCandidate           —— record pair / cluster pending judgment
MatchDecision            —— tri-state judgment result

L1  EVIDENCE
SourceRecord             —— the original record of each source system (immutable)
ExternalIdentifier       —— external ID and its time-effectiveness
IdentityEvidence         —— the specific facts supporting the judgment
```

Layers cannot be skipped: the identity claim of L3 can only be supported by L2 attachment + L1 evidence,
and its formation process must be recorded by L4.

---

## 5. CanonicalIdentity

### 5.1 Definition

> **Within the SRAF semantic space, a unique, stable, non-reused identity for a real-world business object.**

### 5.2 Hard Requirements

```text
R-ID-1  Never reuse: a retired entity_id must not point to another real-world object
R-ID-2  Never change due to changes in external IDs
R-ID-3  Never be rebuilt due to changes in address / name / attribution
R-ID-4  Each entity_id must declare entity_type and identity_domain
R-ID-5  Creation must carry creation_reason (SOURCE_SYNC / MANUAL / MERGE_SURVIVOR /
        SPLIT_CHILD / PROSPECT_CONVERT)
```

### 5.3 identity_domain

Identity determination rules vary by domain; one global similarity logic is forbidden:

```text
commercial_account     commercial customer entity
service_location       physical operating premises
person                 natural person
sales_resource         allocable capability unit
organization           legal entity / group / dealer
distribution_channel   channel entity
geo_unit               spatial unit
```

Each domain has its own: candidate attribute set, strong/weak signals, blocking strategy, default threshold,
manual escalation conditions.

### 5.4 Orthogonality between Entity type and domain

```text
CommercialEntity / Account / Prospect   → identity_domain = commercial_account
Person / SalesResource                  → two domains, each independently resolved
```

**Person and SalesResource must have identity resolved separately**:

```text
The same Person (employee ID change / contract subject change)
→ may correspond to the same SalesResource (capability continuation)
→ may also correspond to a new SalesResource (new position contract)
```

Confusing the two will directly pollute the temporal continuity of `01 §17A DeploymentAssignment`.

---

## 6. ExternalIdentifier (canonical schema deferred to 08)

```text
ExternalIdentifier

external_identifier_id
entity_id                 → CanonicalEntity
source_system
identifier_type
external_id
scope                     (e.g., country / BU / deployment environment)
valid_from
valid_to
observed_first_at
observed_last_at
status                    ACTIVE / RETIRED / SUPERSEDED
confidence
resolution_record_id
```

### 6.1 Key Constraints

```text
EI-1  (source_system, identifier_type, external_id, scope) within the valid interval
points to at most one entity_id -- unless an explicit SPLIT / MERGE successor chain is established
EI-2  The same external_id under different scopes is allowed to point to different entity
(SAP client 100 and 200's CUS_99821 are two objects)
EI-3  when external_id is retired, the record must not be deleted; only set RETIRED + valid_to
EI-4  a real-world object's historical ID set (store ID 88291 -> 223817)
must be preserved as multiple rows, not overwritten
```

### 6.2 ID change != identity change

recoding in the new system is the most common noise:

```text
legacy system store ID 88291
new system store ID 223817
```

as long as a migration mapping exists, the two are **two ExternalIdentifiers of the same entity**.
SRAF must be able to resolve bidirectionally given a mapping_version,
and preserve the knowledge time of "for some period we only knew 88291".

### 6.3 identifier_type strength tiers

```text
STRONG_GOVERNED   tax ID / unified social credit code / contract number / business license number
(low u-probability, can individually support PROVISIONAL_MATCH)
STRONG_SCOPED     source system primary key (unique within a defined scope)
MEDIUM            internal store codes within branded chains, channel membership codes
WEAK              phone (may be shared), contact email, store manager name
VERY_WEAK         name, address text, lat/long (only for blocking / features, must not determine identity alone)
```

```text
forbidden: achieving HIGH similarity and thus CONFIRMED_MATCH based on VERY_WEAK signals alone
```

(separability requirement in the Fellegi-Sunter sense, see §16.)

---

## 7. SourceRecord and Crosswalk

```text
SourceRecord

source_record_id
source_system
source_table / source_endpoint
source_primary_key
extracted_at
payload_hash
schema_version
ingestion_run_id
```

```text
IdentityLink

link_id
source_record_id
entity_id
link_basis            DIRECT_MAPPING / MATCH_DECISION / MANUAL / MIGRATION
confidence
match_rule_version
created_at
retired_at
resolution_record_id
```

### 7.1 Principles

```text
SR-1  SourceRecord is immutable and not deleted (even if judged as duplicate)
SR-2  deletion only happens at the link layer: retire an IdentityLink
SR-3  a SourceRecord has at most one ACTIVE link at a given as_of moment
(When many-to-one temporary allowance is enabled, an AssertionConflict must be produced)
SR-4  An entity can have multiple ACTIVE links (multi-source convergence, which is a normal state)
```

### 7.2 Migration and legacy

```text
The IdentityLink of a Legacy Import allows resolution_record_id to be empty,
but link_basis must be marked as MIGRATION and the confidence source must be
"batch mapping table version" rather than the model score.
```

---

## 8. IdentityAssertion

Reuse the structure of `01 §27 Assertion Model`, and only specify identity-dedicated predicates:

```text
predicate ∈ {
SAME_AS,                 asserts sameness (within the specified identity_domain)
DISTINCT_FROM,           asserts distinctness (negative assertion, equally important)
PART_OF,                 hierarchical belonging (store ∈ chain)
OPERATES_AT,             temporal association between Account and ServiceLocation
HAS_SUCCESSOR,           inheritance relationship (§13)
IS_RELOCATION_OF         address variant unchanged (§12)
IS_RENAME_OF             name variant unchanged (§12)
}
```

Required:

```text
subject / object
identity_domain
semantic_status
valid_time / observed_time
source / confidence / evidence[]
assertion_strength          CANDIDATE / PROVISIONAL / CONFIRMED
rule_or_actor               match_rule_version or human actor
```

### 8.1 Negative assertions must exist

```text
DISTINCT_FROM is the mechanism that prevents "repeated proposals by the same matcher".
```

A system without negative memory will repeatedly harass the same pair of candidates in every rerun round,
and re-queue hypotheses that have already been manually rejected.

```text
AD-1  A human judgment of "not the same one" must be written as CONFIRMED DISTINCT_FROM
AD-2  This assertion takes effect for subsequent match_rule_version by default (explicit revocation is required to reopen)
AD-3  Revocation must record the reason (new evidence / rule change / misoperation)
```

---

## 9. MatchCandidate generation (Blocking / Indexing)

Identity Resolution cannot perform full pairwise comparison at real scale.

```text
accounts 200k → 2×10¹⁰ pairs
```

This specification requires:

```text
MB-1 A blocking layer must exist, and recall-of-blocking must be an explicitly measured metric
MB-2 Blocking key must not use a single weak attribute (pure name / pure coordinate)
MB-3 A supplementary recall channel for "missed by standard blocking" must be supported:
manual nomination / address approximate search / graph neighbor expansion / phone and settlement number reverse lookup
MB-4 Blocking strategy must be versioned: blocking_version
MB-5 At L-tier scale (07 §110A), candidate pair order of magnitude and memory budget must be reported
```

Candidate source classification:

```text
BLOCKED_PAIR          blocking hit
NEIGHBOR_EXPANSION    graph / spatial neighbor expansion
HUMAN_REFERRAL        manual nomination
MIGRATION_RESCAN      migration batch rescan
IMPACT_RECHECK        downstream anomaly recheck (see §14)
```

---

## 10. Matcher and Features

Coexisting matchers allowed (combinable; not allowed to only permit one):

```text
RULE          deterministic rule (strong ID exact match, contract number match)
FS_WEIGHTED   Fellegi-Sunter style field-level weight accumulation
ML_MODEL      classifier (pairwise match probability)
LLM_ASSISTED  semantic assistance (may only be used to generate/explain candidates,
must not independently produce CONFIRMED_MATCH)
EMBEDDING     vector neighbor (used for candidate generation and features)
```

Features must be declared by identity_domain. commercial_account must at least include:

```text
name_normalized / name_token_overlap
brand_or_chain_marker
address_text_similarity
coordinate_distance
geo_unit_relation (same cell / adjacent cell)
phone / settlement_account agreement
legal_entity_id agreement
category / format agreement
manager or contact overlap
sales-series continuity (historical sales volume series of the same store should not be broken)
temporal co-occurrence (whether two records are both active within the same time window)
```

### 10.1 Anti-chaining constraints

```text
TC-1  Prohibit unconstrained single-linkage transitive closure
(A~=B, B~=C leading to A~=C chain mis-merge is the #1 source of MDM incidents)
TC-2  Intra-cluster consistency must be checked:
any pairwise supporting evidence within a cluster must not have conflicting strong signals
(different legal_entity_id / same coordinates different settlement entities / dual-active in same period)
TC-3  When conflicting strong signals appear, the cluster must be split back to candidate state and enter the manual queue
TC-4  Cluster growth rate must be monitored: if a single cluster absorbs too many entities within a short window
-> automatically downgrade to PROVISIONAL and require review
```

---

## 11. MatchDecision Three-state

```text
MatchDecision

decision_id
pair_or_cluster_ref
identity_domain
outcome ∈ { MATCH, NON_MATCH, UNCERTAIN }
score
thresholds_applied
rule_set_version / model_version / blocking_version
evidence[]
generated_by            RULE / MODEL / HUMAN
created_at
resolution_record_id
```

Three-state rather than two-state is mandatory:

```text
MATCH       Can automatically create link; whether mergeable see §12
NON_MATCH   Write to DISTINCT_FROM
UNCERTAIN   Enter manual queue, must not be treated as either by downstream
```

### 11.1 Thresholds must be defined by error rate, not by score

```text
Prohibited: score > 0.9 -> automatic merge
```

Must declare **tolerable error rate**, then derive threshold from calibrated score:

```text
max_false_match_rate      lambda     (false match tolerance)
max_false_non_match_rate  pi     (false non-match tolerance)
review_band               [t_low, t_high] → UNCERTAIN
```

Fellegi-Sunter's original contribution is exactly this: under given upper bounds of two types of error rates,
the optimal decision rule is to partition the likelihood ratio into three intervals, with the middle handed to clerical review.
This specification directly adopts that framework.

### 11.2 Asymmetric cost of two error types (mandatory)

Costs must be explicitly configured per domain and impact:

```text
False Match -> coverage hidden, responsibility attribution erased, customer handover mis-recorded
usually hard for the business to detect, damaging long-term trust
False Non-Match (missed merge) -> workload inflated, false CapacityGap, mistakenly triggering headcount increase
usually diagnosable (dual records with same name at same address are conspicuous)
```

SRAF defaults to the **conservative side**:

```text
AM-1  the lambda for automatic MATCH must be significantly stricter than the pi for automatic NON_MATCH
AM-2  any identity assertion that triggers a Structural Decision must be CONFIRMED
AM-3  UNRESOLVED candidates affecting Materiality -> block the Trigger (see §14)
```

### 11.3 Calibration

```text
CAL-1  scores must be calibrated to interpretable probabilities (consistent true match rates within the same confidence interval)
CAL-2  must report calibration curve / ECE, reported sliced by feature
CAL-3  "all conclusions above 0.9" is prohibited (06 §39 same discipline applies to identity)
CAL-4  the calibration set must not share human annotation sources with the evaluated set, to avoid self-verification
```

---

## 12. Decision Rules for the Eight Scenarios

the user's real difficult scenarios, this spec requires each to have an **executable discrimination flow**.

judgment asks in order:

```text
Q1 is it the same real-world object? (SAME_AS)
Q2 if so, is it the same accountable entity? (Account layer)
Q3 if so, is it the same physical location? (Location layer)
Q4 what is the nature of the change? (name / address / entity / split / merger / inheritance)
```

### Scenario 1: Same Entity (normal multi-source convergence)

```text
example: Shanghai Yonghui XX store (CRM) + Yonghui Supermarket Shanghai XX store (DMS) + Yonghui Life XX (POI)
support: brand marker consistent + coordinates < d_loc + high address text similarity + settlement/contract number consistent
judgment: MATCH (CONFIRMED if it includes STRONG_GOVERNED consistency)
action: three SourceRecords link to the same account entity
prohibited: rewriting any source system record
```

### Scenario 2: Duplicate Entity (duplicate entries within the same system)

```text
Example: two records of the same store within CRM
Judgment: MATCH + same source_system
Action: still do not delete the source records; both SourceRecord may link the same entity,
with one flagged status = DUPLICATE_WITHIN_SOURCE for import-layer denoising
Required: produce IdentityEvidence explaining why these are not two adjacent stores
```

### Scenario 3: Same Account + Different ServiceLocation

```text
Example: a customer (KA group) has stores in Beijing and Shanghai respectively
Judgment: NOT SAME_AS (at account layer), each OPERATES_AT a different location
Prohibited: merging two stores into one account entity on the basis of "same brand"
Correct modeling:
AccountGroup(Yonghui East China) → PART_OF → each store Account
    store Account → OPERATES_AT → ServiceLocation
```

### Scenario 4: Store Relocation

```text
Discriminating signals (in order of priority):
continuous contracting/settlement entity AND continuous customer responsibility     → supports relocation
same person in charge + same employees + same shelf/permit      → supports relocation
coordinate change > d_relocate + closure signal at old address → supports relocation
new address and old address in same city but different trade areas with concurrent dual activity in the same period → opposes relocation (they are two stores)
Judgment: IS_RELOCATION_OF (same Account, different Location)
Action:
ServiceLocation_old.valid_to = closing date (valid_time)
ServiceLocation_new newly created, valid_from = opening date
Account entity_id unchanged (01 §63)
ResponsibilityAssignment default continuous, unless business explicitly requires reopening the relationship
Impact:
Opportunity sequence continuity is preserved -> but a "relocation breakpoint marker" must be inserted on history,
otherwise the sales volume sequence will be misread as demand collapse (-> ModelGovernance misjudgment)
```

### Case 5: Store Rename / Rebranding

```text
Determination: IS_RENAME_OF (both Account and Location are the same)
Action: attribute temporal version (name generates a new temporal assertion), entity_id unchanged
Prohibited: creating a new entity due to a name change
Note: a brand re-sign (Yonghui -> other chain) does not necessarily equal an Account change,
must simultaneously check whether legal entity / contract subject has changed:
contract subject unchanged -> same Account, re-sign recorded as attribute change
contract subject changed -> triggers Case 8 (Succession) determination
```

### Case 6: Store Split (one into two)

```text
Example: one large store splits into two small stores, each signing independently
Determination: parent entity relationship is expressed as SPLIT by the inverse operation of MERGE
Action:
parent Account -> status = SPLIT_INTO, valid_to = split effective date
child A / child B: new entity_id, each HAS_PARENT = parent
Historical attribution rule (mandatory declaration, no defaulting):
        history_attribution ∈ { PARENT_ONLY, PROPORTIONAL, PRIMARY_CHILD }
default PARENT_ONLY + explicit split_note (to prevent false growth from being read as organic growth)
Prohibited: letting child directly inherit parent's entity_id (breaks R-ID-1/R-ID-3 traceability)
Downstream: DemandSurface / historical replay must be able to recompute curves under three attributions
```

### Case 7: Store Merge (two into one)

```text
Example: two stores merge operationally
Determination: MERGE, generates a survivor
Action:
loser Account -> SUPERSEDED_BY survivor, valid_to = merge effective date
The loser's Opportunity / Workload / Coverage history is retained on the loser's timeline,
and must not be silently moved under the survivor (which would cause false growth in the survivor's historical sales)
A mapping table between the "post-merger operating entity" and the "original two entities" is required for backtesting
ResponsibilityAssignment: the loser's active assignment must be explicitly migrated or terminated
TerritoryMembership: updated along with the Responsibility persistence relationship (01 §45)
Impact: sales discontinuities before and after the merger must be tagged with a "discontinuity" marker on the Derived State
```

### Scenario 8: False Match (identification and recovery of erroneous merging)

```text
Discovery channels:
Manual complaints / IMPACT_RECHECK (§14) / dual-active detection / two GPS tracks in the same period
Action: Unmerge
Create a new IdentityResolutionRecord (do not overwrite the old record)
The absorbed SourceRecord is re-linked back to the original entity
Affected historical Derived State is recalculated and the recalculation_run_id is recorded
If a real Decision has already occurred (add staff / change responsible person), a LearningSignal must be generated:
        IdentityErrorCausedDecision
Required: False Match discoverability is designed as a mandatory item — any merge must be reversible
```

### Decision Table Summary

| # | SAME_AS | Account | Location | canonical action |
|---|---|---|---|---|
| 1 | yes | same | same | link |
| 2 | yes | same | same | link + DUPLICATE_WITHIN_SOURCE |
| 3 | no | different | different | OPERATES_AT + PART_OF |
| 4 | partial | same | different | IS_RELOCATION_OF |
| 5 | yes | same | same | IS_RENAME_OF |
| 6 | parent→child | derived | derived | SPLIT |
| 7 | many→one | one survives | may change | MERGE |
| 8 | revoke | — | — | UNMERGE |

---

## 13. Supersede / Succession

```text
Supersede answers the question:
"This entity no longer exists; who is the successor?"
```

Difference from MERGE:

```text
MERGE   : two entities were actually one all along (correction of an identity judgment error)
Supersede: two entities that genuinely existed one after the other in time (successor relationship)
```

Typical scenarios:

```text
A new store opens at the original site after the previous store closes        -> new entity, HAS_SUCCESSOR relationship (if treated as continuation by the business)
Dealer is replaced              -> new organization, inheriting service responsibility
Chain acquisition (the acquired party's legal entity is deregistered) -> acquiring entity inherits contract responsibility
Prospect -> Account conversion   -> same entity, status change (a new ID must not be created)
```

### 13.1 Rules

```text
SUP-1  Supersede does not merge identities: both entity_ids are retained
SUP-2  succession_kind must be declared:
       RELOCATION / REBRAND / LEGAL_CONTINUATION / OPERATIONAL_TAKEOVER /
NONE (no successor relationship)
SUP-3  Only LEGAL_CONTINUATION allows the historical responsibility chain to be linked by default;
OPERATIONAL_TAKEOVER requires business approval
SUP-4  RelationshipState (01 §42) at the point of succession must be explicitly decided:
inherit / reset / discount (reset by default and requires manual confirmation,
because customer relationship is not a legal entity)
```

### 13.2 Prospect → Account

```text
Forbidden: creating a new entity_id during conversion (this causes the potential model to see "new customers appearing out of nowhere"
and be misread as organic growth)
Required: same entity, status time-versioned + conversion_event_id
```

---

## 14. Downstream Impact of Identity Changes and Invalidation Propagation

Identity change is the operation with the largest system-wide impact. Impact Analysis is mandatory.

### 14.1 Impact Checklist (must be computed before Merge / Split / Unmerge)

```text
OpportunityEstimate       subject recompute total amount and distribution after re-attachment
DemandSurfaceCell         recompute aggregate values
CoverageNeed/Commitment   whether subject, frequency are duplicated
IntrinsicWorkload         recompute by subject×activity
CapacityUtilization       depends on workload
ResponsibilityAssignment  conflict detection (whether a dual primary appears after merge → violates 02 §40 Invariant)
TerritoryMembership       01 §45 relationship persistence
Open Candidate / Scenario referencing the affected subject → STALE
Open DecisionCase         recompute affected Gap / Hypothesis / Materiality
baseline of Validation for completed Decisions  mark as identity-affected (may be invalid)
Benchmark ground truth    affected case version number is bumped (06 §108)
```

### 14.2 Trigger blocking

```text
IF  unresolved identity candidates
AND the expected workload / opportunity change of the affected scope > materiality_threshold
THEN
prohibit creating Structural DecisionCase (Expansion / Rebalancing)
must first queue H-DATA in the diagnostic candidates
```

reason: an unresolved duplicate record is a **fake CapacityGap**;
adding headcount before merging = spending real money on fake demand.

### 14.3 Reverse detection (Identity Confounded metric)

the spec mandates defining and continuously measuring:

```text
IdentityConfoundedGapRate
= the proportion of AllocationGap that disappears or shrinks significantly due to identity correction (after deduplication)
```

this is SRAF's **overall identity health metric**, entering the `06` Governance report.
empirically it should be very low; if high, the problem is not in the Solver but in Identity.

---

## 15. Temporal Identity

### 15.1 Identity must be bitemporal

```text
IdentityResolutionRecord

resolution_id
identity_domain
action        LINK / MATCH / CONFIRM / MERGE / UNMERGE / SPLIT / SUPERSEDE /
              RENAME / RELOCATE / DISTINCT_ASSERT
subjects[]    participating entity_id / external_id / source_record_id
survivor      (if applicable)
rule_set_version / model_version / blocking_version / calibration_version
evidence[]
impact_analysis_id
authority     actor / role / policy_reference
decided_at                = knowledge/transaction time
effective_from / effective_to = valid time
status        PROPOSED / APPROVED / APPLIED / REVERSED / CONTESTED
supersedes_resolution_id  (revocation and re-decision form a chain, do not overwrite history)
reversal_of   (UNMERGE points to the revoked resolution_id)
```

### 15.2 Key Semantics

```text
TI-1  "When we know" and "When it is true in reality" are separated
(A merge completed on 8/12 may have a business effective date of 8/1)
TI-2  WorldSnapshot must freeze the set of identity decisions applied at that time
i.e.: snapshot_id → { applied resolution_ids }
TI-3  Replay (06 §95) must use that snapshot, current identity is prohibited
TI-4  UNMERGE must not erase old resolution; only mark REVERSED and create a new record
TI-5  If the identity determination of a historical Baseline is later overturned,
a LearningSignal = IdentityCorrectionAffectingPriorDecision must be produced
and explicitly state: whether the validation of that historical Decision is voided
```

### 15.3 Relationship with Scenario

```text
Does Scenario allow temporarily changing the identity view (e.g., assuming two records are the same)?

Allowed, but:
Must be written as ScenarioAssumption (semantic_status = ScenarioAssumption)
Must not be written into Canonical identity state
The explanation of the Candidate must disclose the assumption sensitivity
    (01 §55–56 / 05 §20)
```

---

## 16. IdentityConfidence

### 16.1 Components

Identity confidence is not a single scalar; it must be reported in layers at least:

```text
pair_score            matcher raw score
calibrated_probability
evidence_strength     STRONG / MIXED / WEAK (downgraded to WEAK if conflicting strong signals exist)
rule_coverage         the identifier_type set actually used in this determination
blocking_recall_risk  whether the prior risk of missing candidates is caused by the blocking design
human_confirmed       whether it contains a CONFIRMED human assertion
temporal_risk involves the degree to which it spans a long historical period / crosses migration boundaries
cluster_risk indicates whether the cluster exhibits chaining / abnormal growth rate
```

Downstream can set different thresholds based on purpose:

```text
Purpose                Minimum requirement
Display / Retrieval   pair_score is available
Operational coverage determination   calibrated_prob ≥ t_ops
ProblemProjection   must attach identity_confidence field
Structural Decision must be CONFIRMED (AM-2)
```

### 16.2 Connection to the World Model

```text
01 §71 DataQuality status extension:
IdentityConfidence   LOW / MEDIUM / HIGH (or continuous value + explanation)
    IdentityStatus       RESOLVED / PROVISIONAL / CONTESTED / UNRESOLVED
```

`01 §72 AssertionConflict` is one specific form of identity conflict,
Its payload and resolution path are defined by this document.

### 16.3 Prohibited behaviors

```text
IC-1  Must not use 'manually confirmed' to disguise identity as an ObservedFact
(its Semantic Status is still DerivedState / DecisionOutput)
IC-2  Must not only show a percentage in the UI without disclosing its composition
IC-3  Must not reuse the same threshold set across identity_domains (location threshold ≠ account threshold)
IC-4  Must not allow confidence to be lost in the Derived State chain
(OpportunityEstimate / WorkloadDemand must be traceable back to the used identity and its score)
```

---

## 17. Survivorship (attribute survivorship rules)

Decoupled from identity, it only concerns field values of the golden record.

```text
SurvivorshipPolicy

policy_id
identity_domain
attribute_scope (per-field or field-group)
strategy ∈ {
SOURCE_TRUST,        according to source_system priority
RECENCY,             take the latest valid/observed
COMPLETENESS,        prefer non-empty
FORMAT_VALIDITY,     prefer those that pass validation
MAJORITY,            majority across sources
ROLE_VIEW,           give different views according to business role
HUMAN_PINNED,        human-pinned, highest priority
}
tie_breaker
version
```

### 17.1 Discipline

```text
SV-1  Survivorship can only act on clusters with CONFIRMED identity
(§2.2: fields can be automatic, identity cannot be automatic)
SV-2  Each field value must record the reason for winning (which rule, which source record)
SV-3  HUMAN_PINNED must include actor + evidence, and can be released by higher-level authority
SV-4  ROLE_VIEW must not cause Planning and Operations to use two sets
of unlabeled business truths (must be consistent within the same ProblemProjection)
SV-5  After an identity UNMERGE, survivorship results must be recalculable
(source values remain in SourceRecord, not dependent on 'what was selected at that time')
```

---

## 18. Hierarchy and Group Identity (chain scenarios)

In reality, the most common cause of misjudgment is hierarchy confusion (Third Round Book Conclusion §1).

```text
OrganizationGroup (Yonghui Supermarket / China Region KA Headquarters)
      ↑ PART_OF
Account (East China Region customer entity)      [optional intermediate layer]
      ↑ PART_OF
Account (Shanghai XX store)  ──OPERATES_AT──▶  ServiceLocation (some address)
```

### 18.1 Rules

```text
HR-1  Hierarchy relationships are IdentityAssertion(PART_OF), not foreign key fields
HR-2  PART_OF must be bitemporal
(store transferred from dealer A to dealer B in 2026-03)
HR-3  Aggregation scope must be explicitly declared:
whether opportunity is measured at store level or group level,
within the same projection, layers must not be summed together (otherwise double counting)
HR-4  'The same physical store belonging to both KA team and field sales team' is
a legitimate multi-responsibility coverage (01 §40),
not an identity conflict, and must not be used as a reason to merge two Accounts
HR-5  Group-level customers must not be treated as duplicates of their sub-stores
HR-6  Roll-up must be drillable: group Coverage/Workload summary
must be able to be broken down back to store, otherwise DP05 cannot be attributed
```

### 18.2 Connection with ResponsibilityScope

```text
01 §38 ResponsibilityScope's AccountGroup=Walmart China
This is precisely the business consumer of hierarchical identity.
This specification provides its identity-side resolvable prerequisite (hierarchy + time point).
```

---

## 19. Human Resolution

### 19.1 Who has permissions

```text
Permissions are graded by impact, and must not be owned by engineers or agents by default:

LINK / PROVISIONAL      System or Steward
CONFIRMED SAME_AS       Data Steward (domain level)
MERGE (within single market)        Steward + Business Owner
MERGE (cross Territory / affecting Open Case)  + Sales Ops approval
SPLIT / UNMERGE         + impact acknowledgment (due to affecting historical sales metrics)
Supersede LEGAL_CONTINUATION  + Business/Legal basis
```

### 19.2 Queue and SLA

```text
IdentityResolutionQueue

Priority factors:
Impacted opportunity amount
Whether it blocks an Open DecisionCase
Whether it affects a Candidate approval in submission
Whether it is within the Structural Freeze Window (05 §25)
SLA requirements:
UNCERTAIN candidates that block Structural Decision → must be resolved before the decision window
Otherwise the DecisionCase is automatically downgraded to Monitor (must not be forced to proceed)
```

### 19.3 Forms of manual assertion

Reuse the discipline of `02 §76 HumanOverride`, do not replicate a second set:

```text
old_value / new_value / reason_code / evidence / expected_impact
```

Identity-specific reason_code:

```text
LOCAL_KNOWLEDGE        local knowledge (I know this store)
FIELD_VISIT_EVIDENCE   GPS/photo/visit record
LEGAL_ENTITY_CHECK     checked the license
CONTRACT_CONTINUITY    contract continuity
SISTER_STORE           confirmed as another store next door
MIGRATION_ERROR        migration mapping error
POLICY_OVERRIDE        knowingly uncertain but handled according to business rules
```

### 19.4 Relationship with GW01 WorldModelRepair

```text
Identity defects → belong to GW01 (05 §14A)
But GW01 must not bypass the permission matrix in §19.1 of this specification;
Identity-related fixes must be recorded in IdentityResolutionRecord (§15),
Its impact_analysis_id must be a required output of GW01.
```

### 19.5 Agent boundaries

```text
Agents can:
nominate candidates (AGENT_REFERRAL, not HUMAN_REFERRAL)
explain evidence, summarize conflicts, prepare proposals
Agents must not:
directly execute MERGE / SPLIT / UNMERGE
describe model scores as 'definitely the same store'
bypass §19.1 permissions due to user request
```

(Charter P14 Evidence Before Automation, Gate 'Agent cannot autonomously change the world without evidence'
specific to the identity side.)

---

## 20. Identity in ProblemProjection

### 20.1 Mandatory inclusion

Whenever a Projection involves a subject, the following must be provided simultaneously:

```text
entity_id
identity_status
identity_confidence (+ composition)
used_resolution_ids[]
duplicate_risk_flag     whether this subject has ever been proposed as a duplicate of some entity
```

Solver may choose to ignore, but **cannot be uninformed**.

### 20.2 Data minimization (extension of 07 §90–91)

```text
identity resolution requires name / address / phone / license number,
but the Territory Solver does not need these.
Projection only exposes entity_id + business volume + coordinate/reachability + confidence.
```

Identity evidence of Person/SalesResource (ID number, individual tax subject)
**Prohibited** from entering any Projection.

---

## 21. Identity Invariants(Critical)

Incorporated into B0 invariant numbering system of `06 §5` (new additions start at I20):

```text
I20  Canonical identity is never reused, never rebuilt due to external ID changes
I21  SourceRecord is not deleted; identity corrections only change IdentityLink
I22  Entity Merge must produce a revokable IdentityResolutionRecord
I23  Identity assertion must declare identity_domain and evidence
I24  Automatic MATCH must be defined by an upper bound on error rate (λ/π), not by raw scores
I25  Identity assertions affecting Structural Decision must be CONFIRMED
I26  Account identity must not be determined solely by coordinate distance; Location identity must not be determined solely by customer list
I27  WorldSnapshot must solidify its identity decision set; replay must not use the current identity
I28  After UNMERGE, historical Derived State must be recalculable and the recalculation process must be recorded
I29  PART_OF / OPERATES_AT must be bitemporal
I30  Agents must not autonomously execute identity changes
```

Violation of I20–I30: B0 fails directly, does not enter higher-level evaluation.

---

## 22. Identity Architecture Gates

The following designs, if present, should be considered architectural issues and rejected:

```text
Using CRM customer codes or employee numbers as Canonical ID
Using fuzzy match score thresholds to directly auto-merge customers
Physically deleting the loser record or its historical facts during merge
Treating survivorship rules as identity determination rules
Linking two records without preserving provenance / rule version
Building clusters by single-link transitive closure (without TC-2 consistency check)
Identity decisions only have current state, no valid/known time
During backtesting, joining to 'today's identity' rather than snapshot identity
Creating a new Account when a store changes address (or vice versa, using address change to mask new customer)
After Split/Merge, not declaring history_attribution scope
Unresolved identity candidates do not block Trigger, directly proceeding to Expansion
Projection does not carry identity_confidence
Marking identity as ObservedFact using 'manually confirmed'
Agent has merge execution permission
Treating Group-level customers and their store records as duplicate items to merge
```

---

## 23. Identity Benchmark (B0's identity sub-domain)

Included in the `06` framework as a mandatory sub-suite of B0.

### 23.1 Ground truth construction

```text
T1 Construct ground truth (recommended primary):
Start from a clean synthetic customer universe,
inject noise at a controllable ratio and then let the system restore:
name variant (abbreviation/simplified-traditional/alias/rebranding)
address variant (colloquial/missing house number/POI naming differences)
coordinate jitter (≤ d_loc / > d_loc two tiers)
newly added real neighboring store at the same address (negative control)
migration re-encoding
merge / split / relocation / closure and reopening
concurrent dual-active status
injection serves as ground truth, enabling measurable FMR/FNMR/cluster metrics.
T2 expert arbitration: difficult real historical pairs, with multiple reviewers making independent judgments,
and discrepancies recorded as CONTESTED (aligned with the approach in 06 §19).
T3 result support: subsequent field evidence (visit photos/contracts) reviewed against the original judgment.
```

Note (Papadakis et al.'s criticism of ER benchmarks):

```text
public benchmarks often inflate matcher performance due to overly easy samples.
SRAF's identity benchmark must include:
same-brand different-store pairs (hard negatives)
same-address different-entity pairs (hard negatives)
true duplicates with missing evidence (hard positives)
and must prohibit reporting accuracy only on easily separable samples.
```

### 23.2 Mandatory Metrics

```text
Pairwise: 
FalseMatchRate (actual measured violation of λ)
FalseNonMatchRate (against π)
    UncertainBandSize
BlockingRecall (recall of true pairs in candidate set)
Cluster: 
    BCubed precision / recall / F
ChainingIncidence (proportion of cross-strong-conflict signals merged into the same cluster)
    OversizedClusterRate
Lifecycle: 
UnmergeRate (post-hoc exposure rate of erroneous merges) ★key health metric
    ContestRate
    MedianResolutionLatency
BlockingMissDiscoveryLatency (time for missed merges to be discovered downstream)
Decision-related (SRAF-specific, most important):
    IdentityConfoundedGapRate(§14.3)
StructuralTriggerBlockedByIdentity (number of Triggers correctly suppressed due to pending identity)
    FalseExpansionAttributableToIdentity
ReplayIdentityLeakageRate (proportion of replays using wrong-point-in-time identity, should be 0)
    IdentityAffectedValidationCount
Governance: 
ResolutionProvenanceCompleteness (proportion missing rule_set_version/evidence, should be 0)
UnauthorizedMergeCount (should be 0)
```

### 23.3 Required Case Family

```text
ID01  Multi-source same entity (scenario 1)
ID02  In-system duplicate (scenario 2)
ID03  Same brand different stores -> must NOT MATCH (hard negative, most important)
ID04  Same address multiple entities -> must NOT MATCH
ID05  Address change with continued operation (scenario 4)
ID06  Rebrand but contract unchanged (scenario 5)
ID07  Rebrand with entity change (-> Supersede, not Rename)
ID08  One split into two + historical attribution convention
ID09  Two merged into one + historical sales must not show false growth
ID10  Already wrongly merged -> Unmerge + downstream recomputation consistency
ID11  Migration re-encoding (88291 -> 223817)
ID12  Concurrent dual activity -> block automatic merge
ID13  Chaining induction (A~B~C transitive but A!=C)
ID14  Group and its stores
ID15  Insufficient evidence + affects Structural Decision -> must block and escalate to manual
ID16  Replay point-in-time identity correctness (merges only done in the future must not appear in past snapshots)
ID17  Persistence of negative assertions (must not be re-proposed after manual rejection on rerun)
ID18  Prospect -> Account conversion does not create new ID
ID19  Cross identity_domain rule leakage (location rule incorrectly applied to account)
ID20 Agent attempts to merge directly -> must be rejected by the permission layer
```

### 23.4 Gate

```text
Identity Gate (merged into 06 Part X):
Before entering the Structural Decision Benchmark in Phase 2 / Phase 3:

ID03 / ID04 (hard negatives) pass
BlockingRecall >= declared threshold
    FalseMatchRate ≤ λ
    ReplayIdentityLeakageRate = 0
    ResolutionProvenanceCompleteness = 100%
IdentityConfoundedGapRate measured and reported

If not passed: only DP06/DP07 allowed (problems that do not change the responsibility structure),
DP01/DP02/DP03 and any Expansion Benchmark must not be run.
```

---

## 24. MVP Scope

To avoid over-engineering (Charter P20), the first version only requires:

```text
Must-do
CanonicalIdentity (R-ID-1..5) + identity_domain partition
    ExternalIdentifier(§6, EI-1..4)
    SourceRecord + IdentityLink(§7, SR-1..4)
SAME_AS / DISTINCT_FROM assertions + three-state MatchDecision
Rule-based matcher (STRONG_GOVERNED exact match) + one statistical/ML matcher
Dual thresholds lambda/pi + UNCERTAIN -> human queue
MERGE / UNMERGE / SUPERSEDE / RELOCATION (four actions)
Survivorship (SOURCE_TRUST + RECENCY + HUMAN_PINNED three strategies)
IdentityResolutionRecord append-only + snapshot freezing
ImpactAnalysis (minimal set from the §14.1 checklist) + Trigger blocking (§14.2)
    Benchmark ID01–ID04, ID10, ID11, ID15, ID16

Deferred
Learning-based blocking model
LLM-assisted semantic matching (may be used first, but only for candidate nomination)
ROLE_VIEW survivorship multi-view
Automatic unmerge trigger
Cross-market global identity service (first satisfy the "do not build full MDM" stance from 07 §15)
Graph embedding / complex community detection
```

The first version explicitly does not do "enterprise-grade MDM":
The goal of this specification is **to keep decisions from being misled by identity errors**,
not to become the sole identity authority for the entire company. If the customer already has MDM,
then `CanonicalIdentityService` degrades to consumer + conflict reporter
(via `05 GW01`), and SRAF does not rebuild a second set of master data.

---

## 25. Specific Linkage with Existing Specifications

### 25.1 01 World Model

```text
01 §9  Canonical Identity  →  schema is owned by 08, 01 retains the principle statement
01 §10 ExternalIdentifier  →  points to 08 §6
01 §15/§12 Person vs SalesResource → 08 §5.4 specifies that each is resolved independently
01 §21–22 Account vs ServiceLocation → 08 §2.3 specifies identity-layer independence
01 §63 Spatial (address change does not change Account ID) → 08 §12 case 4 gives the determination flow
01 §71 DataQuality → add two items: IdentityConfidence / IdentityStatus
01 §72 AssertionConflict → identity conflict as its concrete form (08 §10 TC-3)
01 §79 example "Commercial Entity Resolution" → expanded in 08
01 §81 MVP 14 objects → Identity is a cross-cutting prerequisite, no new 15th business object is added,
but IdentityResolutionRecord must be implemented
```

### 25.2 02 Decision Ontology

```text
Root Cause Taxonomy's DataQualityIssue (§21)
→ refine subtypes: IdentityDuplicate / IdentityFalseMatch /
      IdentityUnresolved / HierarchyMisattribution
→ so that 04's H-DATA has verifiable sub-hypotheses
DiagnosticHypothesis's evidence
→ identity evidence is legitimate Evidence, and its semantic_status follows 08 §16.3
ChangeCost's CustomerRelationshipCost
→ depends on correct relationship history → depends on §15 Temporal Identity
```

### 25.3 03 Problem Contracts

```text
One legitimate cause of F1 DATA_INFEASIBLE = identity not resolved
Projection must declare the minimum requirement for identity_confidence (§20.1)
Immutable objects implicitly contain an "identity view":
Problem Contract should explicitly declare identity_snapshot_id
(= the version of the resolution set used)
```

### 25.4 04 Allocation Intelligence

```text
H-DATA (§22) must include identity sub-checks:
DuplicateSuspectTest    detect high-similarity dual-active entities with same address/brand
HierarchyOverlapTest    check whether group and store are counted multiple times
IdentityCoverageTest    proportion of subjects in UNRESOLVED/CONTESTED
H6 Stability & Confidence adds the IdentityConfidence dimension
DiagnosticTest Library (§24) adds:
IdentityIntegrityTest (the 6th test beyond the 5 mandatory MVP tests)
Materiality (§26): identity unresolved -> confidence upper bound of that Gap is limited
```

### 25.5 05 Orchestration

```text
GW01 WorldModelRepair takes over identity repair execution; see permissions in 08 §19.1
Artifact failure propagation (§21 / 08 §14.1)
Structural Freeze Window period: allow identity resolution (read and record),
but the structural recomputation triggered by it is delayed
```

### 25.6 06 Evaluation

```text
B0 add I20–I30 (08 §21)
Test 6.1 Multi-source Identity / 6.2 Source ID Collision /
6.3 Location Change specification details and threshold semantics -> provided by 08, referenced by 06
Case Family ID01–ID20 are placed under the benchmark/identity/ directory
Add Identity Gate (08 §23.4) integrated into Part X Acceptance Gates
Evidence Level (06 §141) applies to identity conclusions themselves:
an identity module that only passes ID01–ID04 synthetic = E1,
must not claim "already supports production decisions".
```

### 25.7 07 Reference Architecture

```text
§15 CanonicalIdentityService design input = this document
Module placement (07 §70 structure):
src/domain/identity/        (new, belongs to the domain layer of the World Plane)
adapters/sources/           provide ExternalIdentifier and SourceRecord
    benchmark/identity/         case + injector + ground truth
Storage: identity_resolution is append-only;
consistent with the PostgreSQL choice in 07 §9–10, no new graph DB dependency
(Graph Projection still derived)
```

---

## 26. External Basis

This specification is not invented from scratch, anchored on two sets of mature practices.

### 26.1 Entity Resolution Literature

```text
Fellegi & Fellegi–Sunter (1969), JASA —
Probabilistic record linkage, m/u weights, three-state optimal decision under two-class error rate bounds.
-> 08 §11 λ/π + UNCERTAIN band directly derived from this.
Newcombe (1962) — likelihood ratio and value-based stratified matching weights.
Christen (2012), Data Matching (Springer) —
Field-level comparison, standardization, blocking, clustering textbook system.
Papadakis, Skoutas, Thanos, Palpanas (2020), ACM CSUR —
blocking / filtering technology overview. -> §9 blocking mandatory and test requirements.
Christophides, Papadakis et al. (2020), ACM CSUR —
End-to-end ER pipeline (including clustering and conflict resolution).
Papadakis, Kirielle, Christen, Palpanas (2023) —
Critical re-evaluation of (deep) learning ER benchmark datasets: most benchmarks "too easy".
-> §23.1 mandate difficult negative examples and prohibit reporting accuracy on easy samples.
Li et al. (2020), Ditto —
Pretrained models do pairwise matching; only act as one of the matchers, not holding decision authority (§10).
```

### 26.2 Enterprise MDM Engineering Practices

```text
Golden record + attribute-level survivorship
(according to source-trust / recency / completeness / majority / role view).
Merge and Unmerge are first-class governance operations, must retain lineage to support undo.
Steward permission tiers and audit.
-> §17 / §19 adopted, but additional SRAF-specific constraints imposed:
survivorship must not determine identity (§2.2).
```

### 26.3 Temporal and Data Warehouse

```text
Snodgrass and TSQL2 / SQL:2011 valid time + transaction time bitemporal model;
Kimball's experience regarding late-arriving dimension and SCD handling.
→ §15 elevate these from "data warehouse tricks" to "mandatory record format for identity decisions".
```

### 26.4 Sales force design literature (and a blank)

```text
Zoltners, Sinha & Lorimer,
Sales Force Design for Strategic Advantage (Palgrave Macmillan, 2004)
Ch3 Potential estimation as heuristic (intra-segment percentile / gap fill ratio, and adjusted with lifecycle)
→ supports 01 P3 and OpportunityEstimate provenance requirements
Ch7 carryover and workload→FTE chain
→ supports workload's extreme sensitivity to subject count (§3.2)
Ch8 central baseline + local adjustment, personnel matching objectivity requirements
→ Identity errors can masquerade as "local knowledge conflict", must be ruled out first
Key gap: the whole book lacks an Identity Resolution / data quality chapter,
"customer universe" appears only once as a solved premise.
→ This document fills exactly what the classic methodology has not covered,
but is implicitly relied upon by all its downstream calculations as the foundation.
```

---

## 27. Definition of Done

`08` implementation cannot be considered complete when the "identity table is built". Must actually execute:

```text
1  The same real store's records in ≥3 source systems are resolved to 1 entity,
and all 3 ExternalIdentifiers are queryable, each with its own validity
2  Construct a pair of "same brand different stores", the system refuses to merge (ID03 passes)
3  After a MERGE, Opportunity / IntrinsicWorkload / CapacityUtilization
undergo explainable changes, and impact_analysis_id is traceable
4  After an UNMERGE, the above derived states precisely return to pre-merge values (or explain the source of differences)
5  A real store relocation: Account entity_id unchanged,
old/new ServiceLocation each have valid time, responsibility chain continuity is explicitly decided
6  A SPLIT: historical attribution scope is declared, three attribution curves can all be replayed
7  Historical replay of 2026-Q1 does not use identity corrections that only occur in Q3 (leakage = 0)
8  When an UNRESOLVED identity candidate exists and affects workload,
the system refuses to create a Structural DecisionCase and puts H-DATA into the hypothesis
9  Agent attempts direct merge, is denied by the permission layer, and the event is audit logged
10 IdentityConfoundedGapRate can be computed and reported on real data
```

Achieving these ten points completes the "identity truth" foundation of SRAF's World Model.

---

## 28. One-sentence boundary

```text
01 answer: what exists in this world?
08 answer: how do you determine that "this" and "that" are the same "this"?
and—if you are wrong, how to discover before you spend money.
```
