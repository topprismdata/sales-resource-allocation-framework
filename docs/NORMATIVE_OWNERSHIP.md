# SRAF v1.2 Normative Ownership Matrix

| Spec | Canonical ownership |
|---|---|
| 00 Project Charter | 项目方向、原则、Non-goals、最高 Architecture Gates |
| 01 World Model | Canonical World、Identity 原则、Bitemporal、Evidence、Observation/Event、WorldSnapshot |
| 02 Decision Ontology | AllocationGap base、DecisionCase、Objective、Requirement、Candidate、ApprovedDecision、Transition、Validation、Root Cause Taxonomy（含 4 个身份 subtype） |
| 03 Decision Problem Contracts | DP01–DP07、Composite Problem、ProblemProjection、Oracle Contract、Failure Semantics、ProblemRun |
| 04 Allocation Intelligence | Health、Gap subtype taxonomy、Diagnostic Tests、Materiality、DecisionTrigger、ProblemRouter |
| 05 Decision Orchestration | Scenario workflow、Coupling execution、Artifact dependency、DecisionRisk、AutomationLevel、OrchestrationRun、GovernanceWorkflow GW01–GW03 |
| 06 Evaluation & Benchmark | B0–B4、Evidence Levels、Benchmark cases、Regression gates |
| 07 Reference Architecture | Module boundaries、Adapters、Storage/runtime reference、Engineering Envelope、implementation topology |
| 08 Canonical Identity | CanonicalIdentity lifecycle、ExternalIdentifier schema、Match/三态判定、Merge/Unmerge/Split/Supersede/Relocation/Rename、Hierarchy、Survivorship、IdentityConfidence、Human Resolution、Temporal Identity、I20–I30、ID01–ID20 |

## Cross-spec rule

上游规范可以引用下游概念，但不得重新拥有另一套 schema。

## v1.2 ownership resolution

`01 §9` 继续拥有 **Canonical ID 的原则**
（不用外部业务编号、UUID 形式、Account 与源 ID 解耦）。

`08 §5–7` 拥有 **CanonicalIdentity / ExternalIdentifier / SourceRecord
的 canonical schema 与判定治理规则**。

`01 §10` 已改为原则 + 指向 08，不再重复字段定义。

`04 §22` 只拥有 **H-DATA 身份子假设的检验方法**；
subtype 名称归 02，阈值与权限归 08。

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
