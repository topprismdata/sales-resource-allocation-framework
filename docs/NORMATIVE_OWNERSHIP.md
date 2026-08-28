# SRAF v1.2 Normative Ownership Matrix

| Spec | Canonical ownership |
|---|---|
| 00 Project Charter | Project Direction, Principles, Non-goals, Top Architecture Gates |
| 01 World Model | Canonical World, Identity Principles, Bitemporal, Evidence, Observation/Event, WorldSnapshot |
| 02 Decision Ontology | AllocationGap base, DecisionCase, Objective, Requirement, Candidate, ApprovedDecision, Transition, Validation, Root Cause Taxonomy (including 4 identity subtypes) |
| 03 Decision Problem Contracts | DP01–DP07, Composite Problem, ProblemProjection, Oracle Contract, Failure Semantics, ProblemRun |
| 04 Allocation Intelligence | Health, Gap subtype taxonomy, Diagnostic Tests, Materiality, DecisionTrigger, ProblemRouter |
| 05 Decision Orchestration | Scenario workflow, Coupling execution, Artifact dependency, DecisionRisk, AutomationLevel, OrchestrationRun, GovernanceWorkflow GW01–GW03 |
| 06 Evaluation & Benchmark | B0–B4, Evidence Levels, Benchmark cases, Regression gates |
| 07 Reference Architecture | Module boundaries, Adapters, Storage/runtime reference, Engineering Envelope, implementation topology |
| 08 Canonical Identity | CanonicalIdentity lifecycle, ExternalIdentifier schema, Match/Three-state determination, Merge/Unmerge/Split/Supersede/Relocation/Rename, Hierarchy, Survivorship, IdentityConfidence, Human Resolution, Temporal Identity, I20–I30, ID01–ID20 |

## Cross-spec rule

Upstream specifications can reference downstream concepts, but shall not re-own another set of schema.

## v1.2 ownership resolution

`01 §9` continues to own **Canonical ID principles**.
(Do not use external business IDs, UUID format, Account decoupled from source ID).

`08 §5–7` owns **CanonicalIdentity / ExternalIdentifier / SourceRecord
the canonical schema and decision governance rules**.

`01 §10` changed to principle + pointing to 08, no longer repeating field definitions.

`04 §22` only owns **H-DATA identity sub-hypothesis verification method**;
subtype names belong to 02, thresholds and permissions belong to 08.

## Frozen v1.1 semantic corrections

```text
Territory contains Responsibility
ResponsibilityAssignment assigns Responsibility to Resource
ResourceDeployment is a deployable position, not a person
DeploymentAssignment fills a deployment with a SalesResource
AllocationGap is base class; LocalAllocationGap is subtype
CandidateDecision + Approval → ApprovedDecision
ResourceEquivalent is a metric, not an entity
ProblemRun replaces ambiguous DecisionRun
```

## Frozen v1.2 semantic corrections

```text
Canonical decision object field = approved_decision_id
Engineering scale commitment = S/M/L Engineering Envelope, not a max-size claim
WorldModelRepair / ModelGovernance / PolicyReview = Governance Workflows (GW01-GW03), not Atomic DPs
Identity Resolution != Deduplication
Entity Merge != Source Record Merge
Account identity != ServiceLocation identity
Identity Confidence != Business Truth
Survivorship may decide field values, never entity identity
SourceRecord is never deleted; identity fixes only change IdentityLink
Identity merge/split decisions are bitemporal and snapshot-bound
```
