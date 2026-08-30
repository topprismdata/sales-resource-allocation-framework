# SRAF World Model Specification v1.2

**Project:** Sales Resource Allocation Framework
**Abbreviation:** SRAF
**Document:** `01_WORLD_MODEL_SPEC.md`
**Status:** Implementation Baseline v1.2
**Parent Specification:** `00_PROJECT_CHARTER.md`

---

## 1. Document Objectives

Sales World Model is responsible for expressing:

> **At a certain point in time, what is the state of the sales market, customers, opportunities, service requirements, sales resources, responsibility relationships, and business policies.**

World Model is not responsible for answering:

> What should be done.

The latter belongs to the Decision Layer.


### 1.1 Normative Ownership Boundary

`01_WORLD_MODEL_SPEC.md` formally owns only:

```text
Canonical World Entities
Canonical World Relations
Semantic Status
Temporal Semantics
Evidence / Assertion
Observation / WorldEvent
Derived World State
WorldSnapshot
```

The following concepts can be referenced in this file to illustrate boundaries, but their canonical schema **is not owned by 01**:

```text
Baseline               → 02 Decision Ontology
Scenario               → 05 Decision Orchestration
HumanOverride          → 02 Decision Ontology
ProblemProjection      → 03 Decision Problem Contracts
CandidateDecision      → 02 Decision Ontology
ApprovedDecision       → 02 Decision Ontology
ExternalIdentifier     → 08 Canonical Identity & Entity Resolution
IdentityResolutionRecord → 08 Canonical Identity & Entity Resolution
```

Therefore, World Model should not replicate independent schemas of these objects.

Therefore, strict adherence must be maintained:

```text
WORLD
  ↓
STATE
  ↓
DECISION PROBLEM
  ↓
DECISION
```

rather than:

```text
Solver Model
   ↓
World
```

---

## 2. Formal Definition of World Model

In SRAF:

\[
WorldModel_t
=
Entities_t
+
Relations_t
+
Assertions_t
+
Policies_t
+
Observations_{\le t}
+
Events_{\le t}
+
DerivedStates_t
\]

At the same time, each important state must have:

```text
identity
time
source
semantic status
provenance
confidence (where applicable)
```

Therefore, SRAF World Model is essentially a:

# **Temporal, Evidence-aware Business World Model**

that is:

> Sales business world model with time, source, and evidence.

---

## 3. World Model Is Not Equal to Database

This is a point that engineering implementation must clarify.

Logically:

```text
Sales World Model
```

is Canonical Semantic Model.

Physically, it can consist of multiple storage:

```text
┌───────────────────────────────┐
│      SALES WORLD MODEL        │
├───────────────────────────────┤
│ Canonical State Store         │
│ Event / Observation Store     │
│ Evidence Store                │
│ Spatial Store                 │
│ Graph Projection              │
│ Analytical / Feature Store    │
└───────────────────────────────┘
```

Therefore, forming is prohibited:

> "World Model = Neo4j"

or:

> "World Model = PostgreSQL"。

Database is implementation.

World Model is semantics.

---

## 4. Physical Architecture Principles for v1.2

It is recommended that the first version adopt:

```text
                Source Systems
                      │
                      ↓
             Ingestion / Mapping
                      │
                      ↓
          ┌─────────────────────┐
          │ Canonical World API │
          └─────────┬───────────┘
                    │
       ┌────────────┼─────────────┐
       ↓            ↓             ↓
Relational      Event Store    Evidence
State Store                   / Artifact
       │
       ├────────────┐
       ↓            ↓
Spatial Index   Graph Projection
       │            │
       └──────┬─────┘
              ↓
       Problem Projection
              ↓
         Decision Engine
```

---

## 5. Why Canonical State Primarily Uses Relational Model

The most important objects in SRAF, for example:

```text
Account
SalesResource
ResourceDeployment
CoverageCommitment
ResponsibilityAssignment
Policy
WorldSnapshot
```

have obvious:

- stable schema; 
- temporal validity; 
- uniqueness; 
- referential integrity; 
- lifecycle; 
- transactional consistency。

for example:

```text
ResponsibilityAssignment
```

Graph query convenience cannot be used as justification to allow two mutually conflicting active relations for the same Primary Responsibility.

Relational models are more suitable for bearing such constraints.

Therefore:

> **Canonical State Store is Source of Truth.**

Graph is Projection.

Not the other way around.

---

## 6. Why "All Event Sourcing" Is Not Possible

Event Sourcing is very valuable for historical recovery.

But if requiring:

> All current world state can only be obtained through complete replay of events,

it is not necessary for SRAF.

A large amount of data actually comes from:

```text
ERP Master Data
HR
CRM
External POI
Market Model
Road Network
```

These are already the current state of external systems.

Therefore, SRAF uses:

# State + Event Hybrid

rather than Pure Event Sourcing.

---

## 7. Responsibilities of Event Store

Event Store is mainly used to record:

> **What important changes occurred in the world.**

For example:

```text
AccountCreated
AccountClosed

ResourceJoined
ResourceLeft

OpportunityUpdated

CoveragePolicyChanged

ResponsibilityAssigned
ResponsibilityTransferred

TerritoryActivated

ResourceDeploymentChanged

DecisionApproved

TransitionStarted

VisitCompleted
```

Event mainly supports:

```text
history
audit
baseline reconstruction
change detection
causal analysis
decision validation
```

---

## 8. Observation and Event Must Be Separated

This is an important semantic boundary.

### Observation

Represents:

> What we observed.

For example:

```text
ActualVisit
ActualTravelTime
ObservedServiceTime
POS Sales
StoreClosedSignal
GPS Visit Evidence
```

Observation does not necessarily mean the world state changes immediately.

### Event

Represents:

> The system confirms that a certain world state has changed.

For example:

```text
StoreClosedSignal
```

It may only be an Observation.

Only after:

```text
verification
```

does it generate:

```text
AccountClosed
```

Therefore:

```text
Observation
     ↓
Interpretation / Validation
     ↓
Event
     ↓
State Transition
```

Cannot be merged.

---

## 9. Canonical Identity Model

All Canonical Entity must have a system-stable ID.

It is recommended:

```text
entity_id
```

Adopt:

```text
<entity_type>:<UUID>
```

For example:

```text
account:4de8...
resource:82ff...
territory:a38c...
```

But UUID is only internal identity.

Cannot use:

```text
CRM customer code
employee number
POI ID
ERP ID
```

as Canonical ID.

Because the same real entity may come from multiple systems.
> **Schema Ownership Description**: The above is an unbreakable **principle**.
> Canonical ID lifecycle, identity_domain, never reuse/rebuild rules,
> and the decision and governance rules for "how multi-source records are considered the same object",
> owned by `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md`,
> This file does not redefine its schema (Charter P21).

---

## 10. External Identifier

Therefore there must be a unified:

```text
ExternalIdentifier
```

It carries the number of a real object in each external system,
and satisfies at least the following factual requirements:

```text
It must be able to express "which system's which ID"
It must include a validity period
ID changes must not overwrite history
```

For example:

```text
entity:
account:123

source_system:
SAP

external_id:
CUS_99821
```

The same Account can simultaneously have:

```text
SAP ID
CRM ID
Tencent POI ID
Internal MDM ID
```

> The above example only illustrates the factual requirement that "multiple IDs can coexist".
> `ExternalIdentifier`'s canonical schema, identifier_type strength classification,
> ID migration (old ID -> new ID) and retirement rules,
> See `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §6.

---

## 11. Canonical Entity Categories

v1.2 does not require all objects to be placed directly in the same Entity table.

However, logically they must belong to the following six categories:

```text
WORLD OBJECT
│
├── Actor
├── Business Object
├── Spatial Object
├── Resource Object
├── Responsibility Object
└── Decision Context Object
```

---

## 12. Actor

Represents a subject that has behavior or responsibility capability.

For example:

```text
Person
Organization
SalesResource
Distributor
Partner
```

Note:

```text
Person
```

and:

```text
SalesResource
```

are not the same object.

---

## 13. Person

Person represents a real person.

It can have:

```text
employee relationship
home location
organizational relation
skills
employment state
```

but:

> Person is not naturally equal to Sales Resource.

For example, a sales manager may:

```text
Person = active
```

but currently does not have:

```text
allocatable field capacity
```

---

## 14. SalesResource

SalesResource represents:

> **a capability unit that can be allocated to fulfill a Sales Responsibility.**

It can be realized by:

```text
Person
Team
Shared Pool
External Partner
Digital Agent
```

implementation.

Therefore:

```text
Person
   ↓ realizes
SalesResource
```

rather than an inheritance relationship.

---


## 14A. Capability

`Capability` is a controlled sales capability semantics, not an arbitrary string tag.

For example:

```text
GeneralSelling
KeyAccountNegotiation
Merchandising
ProductSpecialist
Audit
Training
```

The structure includes at least:

```text
capability_id
capability_type
description
eligibility_semantics
version
```

`Capability` can be used for:

```text
ResourceArchetype
SalesResource
Responsibility
CoverageNeed
DecisionProblem
```

but must not be automatically inferred as a fact from historical sales amounts.

---

## 14B. SalesActivity

`SalesActivity` represents the type of activity that actually needs to be completed within a sales responsibility.

For example:

```text
Sell
Merchandising
OrderTaking
Negotiation
Audit
Training
```

It is the common semantic anchor of `CoverageNeed`, `CoverageCommitment`, `WorkloadDemand` and `Responsibility`.

---

## 14C. ServiceChannel

`ServiceChannel` represents the resource/contact method through which a service is delivered.

The first version supports at least:

```text
Field
Phone
Digital
Distributor
Agent
Hybrid
```

`ServiceChannel` is related to `ResourceArchetype`, but they are not synonyms.

---

## 15. ResourceArchetype

Represents a standard resource capability template.

For example:

```text
FieldRep.TT
FieldRep.KA
Merchandiser
InsideSales
```

The structure includes at least:

```text
resource_type
capability_set
default_capacity_model
mobility_mode
cost_model
service_channel
```

It is primarily used for:

```text
Greenfield
Sizing
Scenario
Resource Requirement
```

---


## 15A. ResourceRequirement

`ResourceRequirement` represents the **planned capability demand** formed after resource planning for a given Market / Scope / Period.

It is not an employee, nor is it a SalesResource that has been actually deployed.

The structure includes at least:

```text
requirement_id
resource_archetype_id
scope
period

required_capacity
capacity_unit
recommended_range

opportunity_context
coverage_context
confidence

originating_decision_id
```

Typical sources:

```text
DP01 Resource Sizing
Greenfield Workflow
Expansion Workflow
```

---

## 16. ResourcePool

Represents a sharable resource collection.

For example:

```text
East China KA Team
Changsha Merchandising Pool
National Inside Sales Pool
```

ResourcePool can have:

```text
capacity
scope
capability
sharing_policy
```

Thus some responsibilities need not be immediately bound to a specific Person.

---

## 17. ResourceDeployment

This object is the core of the SRAF World Model.

Definition:

> **A sales capability deployment position (resource position) that is planned or activated within a certain space, organization, or market scope.**

`ResourceDeployment` can be in:

```text
planned
vacant
filled
inactive
```

Therefore it can exist before a specific person in Greenfield / Expansion scenarios.

The structure includes at least:

```text
deployment_id
resource_archetype_id

base_location
market_scope

required_capacity
capacity_unit

deployment_status

effective_from
effective_to

originating_decision_id
```

Note:

```text
Person.home_location
```

is personnel fact.

```text
ResourceDeployment.base_location
```

is a business deployment location.

The two must be separated.

Must also be distinguished:

```text
ResourceDeployment
!=
SalesResource
```

"Where is the deployment position, what capabilities are needed" and "which actual resource currently fills it" are two different facts.

---

## 17A. DeploymentAssignment

`DeploymentAssignment` indicates that a specific actual `SalesResource` fills a specific `ResourceDeployment` over a period of time.

Structure at least includes:

```text
deployment_assignment_id
deployment_id
sales_resource_id

effective_from
effective_to
status

source_approved_decision_id
```

Therefore:

```text
DP02 Resource Location
```

Main change `ResourceDeployment`;

And:

```text
DP04 Personnel Matching
```

Main change `DeploymentAssignment`.

---

## 18. Capacity Model

Capacity must be a time-related object, not a number on SalesResource.

Definition:

```text
CapacitySupply
```

Example:

```text
resource
period
nominal_capacity
available_capacity
committed_capacity
allocatable_capacity
capacity_unit
source
```

Allow:

```text
hour
FTE
visit-equivalent
activity-unit
```

But the same Decision Problem must declare a unit system.

---

## 19. Market

Market represents:

> A market defined in a certain sales decision context.

Example:

```text
Changsha beverage and food service channel
China modern channel
East China hospital market
```

It is not a simple administrative region.

Market can be defined by:

```text
geography
channel
product
customer segment
business context
```

Jointly defined.

---

## 20. GeoUnit

GeoUnit is the basic spatial computation unit.

Example:

```text
H3 Cell
Grid
Administrative Unit
Trade Area
Postal Zone
```

GeoUnit is used for:

```text
aggregation
demand surface
spatial index
territory projection
```

But:

\[
GeoUnit \neq Territory
\]

---

## 21. ServiceLocation

Indicates the physical location where actual sales activity occurs.

Example:

```text
Store
Restaurant
Hospital
Warehouse
Office
```

Structure at least includes:

```text
geometry
address
access information
opening status
valid time
```

Account and ServiceLocation have a many-to-many possible relationship.

---

## 22. Account

Account is:

> **Commercial responsibility object.**

Example:

```text
Single-store customer
Chain headquarters
Dealer
Hospital
Enterprise customer
```

Therefore:

```text
Account
```

with:

```text
ServiceLocation
```

Cannot be mixed into one object.

---

## 23. Prospect

Prospect can share a parent class with Account:

```text
CommercialEntity
```

But in v1.2, I suggest keeping status distinction:

```text
Prospect
Account
```

instead of:

```text
is_customer = false
```

Because Prospect often has different business rules on Coverage and Ownership.

---

## 24. MarketSignal

MarketSignal represents:

> Observation or indicator used to understand market status.

Example:

```text
POI density
O2O activity
population
commercial density
historical sales
footfall
```

MarketSignal is not Opportunity.

It is just Evidence.

---

## 25. OpportunityEstimate

This is one of the most critical objects in the World Model.

Opportunity is not allowed as:

```text
account.potential_score
```

This bare field cannot exist.

It must have independent Estimate semantics:

```text
OpportunityEstimate

subject_id
opportunity_type
metric
value
unit

valid_from
valid_to

estimate_time

source_type
source_id

confidence

model_id
model_version
evidence_set_id
```

---

## 26. OpportunityType

At least allow:

```text
CurrentValue
Potential
IncrementalPotential
GrowthPotential
WhitespaceOpportunity
RiskAdjustedOpportunity
```

The framework must not assume:

```text
potential
```

Only one unified meaning.

Specific projects must declare Opportunity Metric Contract.

---

## 27. Assertion Model

This is the basic abstraction of the Evidence-aware World Model.

Unified structure:

```text
Assertion

subject
predicate
object / value

semantic_status

valid_time
observed_time

source
confidence

evidence
```

Example:

```text
Account A
HAS_CHANNEL
Restaurant
```

Can come from:

```text
HumanJudgment
```

And:

```text
Account A
BELONGS_TO_DISTRIBUTOR
Distributor X
```

May come from:

```text
MasterDataFact
```

---

## 28. Semantic Status

v1.2 fixes:

```text
ObservedFact
MasterDataFact
ExternalFact
ModelEstimate
HumanJudgment
PolicyDefinition
DerivedState
DecisionOutput
ScenarioAssumption
```

Any non-simple master data object should in principle be able to track its Semantic Status.

---

## 29. Evidence

Evidence is not a string note.

Should be expressed independently:

```text
Evidence

evidence_id
type
source
reference
timestamp
quality
```

Example:

```text
ERP Record
POS Record
POI Record
Model Output
Photo
GPS Trace
Human Review
External Dataset
```

One Assertion can be associated with multiple Evidence.

---

## 30. Provenance

All important Estimate / Derived State must at least know:

```text
created_by
method
input_version
model_version
calculation_version
timestamp
```

So for example:

```text
Potential = 82
```

can only be answered:

> How is 82 derived?

---

## 31. Temporal Model

SRAF must at least support:

# Bitemporal Semantics

i.e., differentiate between:

```text
Valid Time
```

and:

```text
System / Knowledge Time
```

Example:

```text
The store actually closed on August 1
```

but the system:

```text
did not know until August 12
```

should be expressed as:

```text
valid_from = Aug 1
known_from = Aug 12
```

Otherwise the historical Baseline will be polluted by future information.

---

## 32. Why Bitemporal is important

Suppose we want to backtest:

> Whether the Territory Decision made by SRAF on July 31 was reasonable.

can only use:

```text
known_at <= July 31
```

the data.

cannot use:

> Facts that were only known later in August.

Otherwise the Benchmark will show:

# Look-ahead Bias

---

## 33. CoverageNeed

CoverageNeed represents:

> **Sales service demand generated based on customer status, opportunities, business objectives, and policies.**

Example:

```text
subject
activity
purpose

eligible_resource_archetypes
service_channel

minimum_frequency
preferred_frequency
maximum_frequency

expected_service_time

service_window
priority

valid_period

policy_source
```

Note:

\[
CoverageNeed \neq Commitment
\]

---

## 34. CoverageCommitment

represents:

> **Coverage that the organization formally decides to actually bear after resource allocation decisions.**

Example:

```text
Account A
SalesVisit
3 / month
```

CoverageCommitment must be able to reference:

```text
originating_decision_id
```

This makes it possible to know:

> Why originally 2 visits now become 3 visits.

---

## 35. WorkloadDemand

WorkloadDemand must be a Derived State.

At least differentiate:

```text
IntrinsicWorkload
NetworkWorkload
TotalWorkload
```

among which:

\[
IntrinsicWorkload
=
\sum_{activity}
CoverageCommitment_{activity}
\times
ExpectedServiceTime_{activity}
\]

Therefore the smallest reasonable granularity of Workload is:

```text
subject × activity × period
```

rather than writing a fixed `workload_hours` on Account.

NetworkWorkload cannot be simply fixed on Account.

It depends on:

```text
ResourceDeployment
Territory
Schedule
TravelNetwork
```

---

## 36. DemandSurface

DemandSurface is a spatially aggregated Derived State.

It cannot replace the original Account / Coverage data.

Example:

```text
DemandSurfaceCell

geo_unit_id
period

opportunity
coverage_need
intrinsic_workload
prospect_count
account_count

source_snapshot
calculation_version
```

It is mainly used by:

```text
Sizing
Location
Macro Territory
Scenario
```

Use.

---

## 37. Responsibility

v1.2 recommends distinguishing:

```text
Responsibility
```

and:

```text
ResponsibilityAssignment
```

distinguish.

Responsibility represents:

> What sales responsibility needs to be undertaken.

Example:

```text
Account A
Product Beverage
Activity Sell
Role Primary
```

This is a responsibility awaiting assignment.

---

## 38. ResponsibilityScope

Used to define the scope of responsibility.

At least allow:

```text
Account
AccountGroup
Geography
Product
Channel
Activity
CustomerSegment
```

Example:

```text
scope:
AccountGroup = Walmart China
```

or:

```text
scope:
Geo = Territory T17
Activity = Merchandising
```

---

## 39. ResponsibilityAssignment

represents:

> Who bears which responsibility at what time.

Core structure:

```text
assignment_id

responsibility_id

resource_id / resource_pool_id

assignment_role

effective_from
effective_to

assignment_status

source_approved_decision_id

relationship_state
```

Assignment must be temporal.

---

## 40. Assignment Cardinality

Cannot assume:

```text
Account → 1 salesperson
```

The true relationship is:

\[
Responsibility
\rightarrow
Resource
\]

Therefore the same Account can simultaneously have:

```text
Primary Selling
Merchandising
KA Negotiation
Product Support
```

multiple Assignments.

---

## 41. Assignment Conflict

Ontology must allow defining:

```text
exclusive responsibility
```

Example:

```text
Primary Territory Selling
```

may prohibit:

```text
2 active primary owners
```

but:

```text
Merchandising
```

can with:

```text
Selling
```

coexist.

Such rules belong to:

```text
Responsibility Policy
```

rather than database field semantics.

---

## 42. RelationshipState

Used to express the continuity of Assignment relationships.

Example:

```text
relationship_age
relationship_strength_estimate
handover_complexity
change_sensitivity
```

Where Estimate type must carry Evidence and confidence.

Cannot treat:

```text
relationship_strength = 0.9
```

as absolute fact.

---

## 43. Territory

v1.2 formally defines:

> **Territory is a logical collection of a set of Responsibilities organized to form a consistent sales resource deployment within a given time and business context.**

`ResponsibilityAssignment` indicates which Resource/Deployment currently bears these Responsibilities, but changes in Assignment should not automatically alter the business identity of the Territory.

Therefore:

```text
Territory
```

Must be able to exist:

```text
zero polygon
multiple polygons
non-contiguous geography
nationwide account list
```

---

## 44. TerritoryType

At least the first version allows:

```text
GeographicFieldTerritory
AccountTerritory
KeyAccountTerritory
ChannelTerritory
ProductTerritory
SpecialistTerritory
HybridTerritory
```

Do not build a different core model for each type.

---

## 45. TerritoryMembership

Territory and Responsibility use:

```text
TerritoryMembership
```

Used as canonical membership relation.

Minimum structure:

```text
territory_membership_id
territory_id
responsibility_id

effective_from
effective_to
status
```

Prohibit using:

```text
ResponsibilityAssignment
```

as Territory's canonical membership.

The reason is:

> When Resource/Personnel is replaced, Territory should not be mistakenly rebuilt as a new Territory.

Similarly, prohibit using:

```text
territory_id
```

directly stuffing into Account as the sole responsibility semantics.

---

## 46. TerritoryProjection

Territory's map representation must be an independently derived object:

```text
TerritoryProjection
```

For example:

```text
projection_type = polygon
method = alpha_shape_v3
source_assignments = ...
generated_at = ...
```

Therefore:

```text
Territory.geometry
```

In principle, not a canonical responsibility truth.

---

## 47. Why this design

Assume:

```text
Walmart China KA Territory
```

Coverage:

```text
Beijing
Shanghai
Guangzhou
Chengdu
```

There is no reasonable single Polygon.

But it is still a legitimate Territory.

This proves:

\[
Territory \neq Geometry
\]

---

## 48. Policy Model

Policy must be a first‑class object.

Structure:

```text
Policy

policy_id
policy_type
scope

rule_definition

effective_from
effective_to

source
owner

priority
exception_policy
```

---

## 49. PolicyType

At least in the first version:

```text
EligibilityPolicy
ServicePolicy
AllocationPolicy
BoundaryPolicy
ChangePolicy
DecisionPolicy
SchedulingPolicy
```

---

## 50. Policy does not directly store Solver Expression

For example, Policy:

```text
Class A stores in principle have 2 visits per month
```

Canonical Model should express:

```text
minimum = 2
preferred = 2
scope = segment A
```

rather than:

```text
x[i,d] >= 2
```

Mathematical expressions only belong to:

```text
Problem Projection / Compiler
```

---

## 51. DerivedState

SRAF must clarify:

> Derived state is not an original fact.

For example:

```text
CapacityUtilization
OpportunityCoverage
UncoveredOpportunity
OpportunityAtRisk
LocalAllocationBalanceMetric
TravelBurden
```

both belong to:

```text
DerivedState
```

must include:

```text
calculation_version
input_snapshot
calculated_at
```

---

## 52. State Snapshot

To support Decision and Benchmark, must support:

```text
WorldSnapshot
```

Definition:

> An immutable reference to the required World State under a clear Knowledge Time.

For example:

```text
snapshot_id
as_of_valid_time
as_of_known_time
scope
schema_version
data_version
```

---

## 53. Baseline(Boundary Reference)

`Baseline`'s canonical schema is owned by `02_DECISION_ONTOLOGY.md`.

World Model only provides:

```text
WorldSnapshot
```

DecisionCase selects one WorldSnapshot as Baseline:

```text
Baseline
   → references
WorldSnapshot
```

This document no longer defines an independent Baseline schema.

---

## 54. Scenario(Boundary Reference)

`Scenario`'s workflow/lifecycle schema is owned by `05_DECISION_ORCHESTRATION.md`.

World Model only defines the following semantic constraints:

> Scenario must be built on Baseline / WorldSnapshot, forming a virtual World View via `ScenarioAssumption`, and must not modify Observed World.

Example:

```text
+6 Field Rep
Potential +10%
New Product Launch
Coverage Policy Changed
```

---

## 55. Scenario is not allowed to modify the real World State

Must:

```text
Observed World
       ↓
Baseline
       ↓
Scenario Overlay
       ↓
Scenario World View
```

Discard directly after scenario failure.

Must not:

> Write to World Model first, then roll back.

---

## 56. ScenarioAssumption

All Scenario modifications must have:

```text
ScenarioAssumption
```

For example:

```text
ResourceCount = 48
```

and explicitly:

```text
semantic_status = ScenarioAssumption
```

so that the Agent never interprets:

> Assume +6 people

as misreading:

> There are already 48 people.

---

## 57. World Event

Unified Event schema at least:

```text
event_id
event_type

subject

occurred_at
recorded_at

payload

source
evidence

causation_id
correlation_id
```

among which:

```text
causation_id
```

Very important.

For example:

```text
DecisionApproved
      ↓ causes
ResponsibilityTransferred
```

In the future can track:

> Which Decision caused this change.

---

## 58. Observation

Unify:

```text
Observation

observation_id
subject
observation_type
value

observed_at
recorded_at

source
evidence
quality
```

Observation may not generate an Event.

---

## 59. Decision Origin Tracking

All structural changes caused by SRAF decisions must be traceable:

```text
Decision
   ↓
TransitionPlan
   ↓
Event
   ↓
WorldState
```

Therefore, for example:

```text
ResponsibilityAssignment.source_approved_decision_id
```

In principle cannot be empty, unless from Legacy Import or External System.

---

## 60. HumanOverride(Boundary Reference)

`HumanOverride`'s canonical schema is owned by `02_DECISION_ONTOLOGY.md`.

World Model only acknowledges it may serve as:

```text
Decision Evidence
World Event causation context
future learning evidence
```

is referenced.

HumanOverride cannot directly modify Canonical World; it must first form a new `CandidateDecision`, then go through Evaluation / Approval / Transition.

---

## 61. Graph Projection

Outside the Canonical State Store, can maintain:

```text
Knowledge Graph Projection
```

used for:

```text
Agent reasoning
relationship traversal
evidence navigation
responsibility exploration
causal exploration
```

For example:

```text
Rep17
 ─ASSIGNED_TO→ Responsibility A
 ─DEPLOYED_AT→ Changsha South

Responsibility A
 ─ABOUT→ Account882

Account882
 ─HAS_OPPORTUNITY→ Estimate910
```

---

## 62. Graph is not a source of truth

If Graph Projection is inconsistent with Canonical State:

> **Canonical State wins.**

Graph must be rebuildable.

Therefore:

```text
Graph Node ID
```

must reference:

```text
Canonical Entity ID
```

---

## 63. Spatial Store

Spatial data can adopt a dedicated Spatial Store / index.

But must follow the same principles:

```text
Geometry
≠
Entity Identity
```

For example, when the same Account changes address:

```text
Account ID
```

should not change.

just:

```text
ServiceLocation
```

produces a new temporal geometry.

---

## 64. Travel Network

TravelNetwork is not recommended to be stored as a huge edge graph ontology relationship in World Model.

Canonical Model only records:

```text
network_version
routing_profile
provider
valid_period
calibration_version
```

Real graph / matrix belongs to:

```text
Spatial / Routing Infrastructure
```

World Model references version.

---

## 65. Travel Estimate

If it generates:

```text
TravelTime(A,B)=27min
```

it belongs to:

```text
DerivedEstimate
```

rather than a permanent fact.

Must at least know:

```text
network_version
routing_profile
departure_time / temporal context
calculation_version
```

---

## 66. ProblemProjection

This is the most important boundary object between World Model and Decision Engine.

Definition:

> **A read‑only, purpose‑limited computational view of a certain Decision Problem on World State.**

For example:

```text
TerritoryAlignmentProjection
```

can have only:

```text
responsibility unit
opportunity
intrinsic workload
travel proxy
current assignment
boundary rules
capacity
```

---

## 67. Principles of ProblemProjection

All that the Solver needs:

```text
x[i,j]
candidate cluster
matrix
penalty
encoded constraint
```

are not allowed to write back to World Model.

Therefore:

```text
WORLD MODEL
     ↓
ProblemProjection
     ↓
MathematicalModel
```

This direction is one‑way.

---

## 68. Backflow of Solver Solution

Can only:

```text
Mathematical Solution
        ↓
Decision Interpreter
        ↓
CandidateDecision
```

Must not:

```text
Mathematical Solution
        ↓
World State
```

This formally implements the Charter's:

# Solver State Never Becomes World Truth Directly

---

## 69. World Model Read Patterns

SRAF must support at least four types of reads:

### Current State Query

Answer:

> What is the current situation?

### Historical State Query

Answer:

> What was the situation in 2026‑Q1?

### Decision Baseline Query

Answer:

> On what state was this Decision based?

### Scenario Query

Answer:

> What would it look like if Resource +6?

These four Query types must be semantically clear.

---

## 69A. v1.2 Canonical World Core Set

v1.2 freezes the following World Core:

```text
Market
GeoUnit
CommercialEntity
Account
Prospect
ServiceLocation

MarketSignal
OpportunityEstimate

Capability
SalesActivity
ServiceChannel

ResourceArchetype
ResourceRequirement
ResourceDeployment
SalesResource
ResourcePool
DeploymentAssignment
CapacitySupply

CoverageNeed
CoverageCommitment
WorkloadDemand
DemandSurface

Responsibility
ResponsibilityScope
ResponsibilityAssignment

Territory
TerritoryMembership
TerritoryProjection

Policy

Assertion
Evidence
Observation
WorldEvent
WorldSnapshot
ExternalIdentifier
```

The following are not canonical class of 01:

```text
Baseline
Scenario
HumanOverride
ProblemProjection
CandidateDecision
ApprovedDecision
AllocationGap
ResourceEquivalent
```

They are owned by Decision / Orchestration / Problem Contract / Metric layers respectively.

---

## 70. World Model Write Patterns

In principle only four types of legal writes:

```text
External State Synchronization
Validated Observation
Confirmed Event / State Transition
Approved Decision Transition
```

Solver, Agent, Simulation do not directly write Canonical World State.

---

## 71. Data Quality status must enter World Model

Cannot assume all data is clean.

```text
EntityQuality
AssertionQuality
LocationQuality
OpportunityQuality
TravelQuality
CoverageQuality
IdentityConfidence      LOW / MEDIUM / HIGH or continuous value + composition
IdentityStatus          RESOLVED / PROVISIONAL / CONTESTED / UNRESOLVED
```

The latter two semantics are defined by `08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §16
definition; its values must be propagatable down with Derived State
(08 §16.3 IC-4)。

For example:

```text
Account A
location_confidence = LOW
```

Thus, when Allocation Intelligence finds anomalies it can determine:

> Whether it is a business problem or a data problem.

---

## 72. Conflict

When different sources conflict:

```text
CRM:
store is open

External:
store is closed
```

Cannot forcibly silently overwrite.

Should generate:

```text
AssertionConflict
```

and allow:

```text
resolved
unresolved
```

Decision Problem can declare:

> Whether unresolved critical conflict is allowed to enter solving.

`AssertionConflict` a specific form is **identity conflict**
(two different settlement entities under the same coordinates / dual active records in the same period / strong signal contradictions within a cluster),
its detection conditions, resolution path, and human authority are specified by
`08_CANONICAL_IDENTITY_AND_ENTITY_RESOLUTION.md` §10 TC-3, §19

---

## 73. World Model Consistency Levels

I suggest defining:

```text
Verified
Operational
Estimated
Experimental
```

For example:

### Verified

Key master data and facts have been verified.

### Operational

Sufficient to support production decisions.

### Estimated

Contains many model estimates.

### Experimental

Suitable for Scenario / Benchmark, not suitable for direct production decisions.

Such a Scenario can be clarified:

```text
WorldConfidence = Experimental
```

---

## 74. Canonical Main Chain Final Fixed

In the World Model layer, we can now formally freeze:

```text
Market
   ↓
Commercial Entity
   ↓
Opportunity Estimate
   ↓
Coverage Need
   ↓
Coverage Commitment
   ↓
Workload Demand

Resource Archetype
   ↓
Resource Requirement
   ↓
Sales Resource / Resource Pool
   ↓
Resource Deployment
   ↓
Capacity Supply

Workload Demand
        ↕
Capacity Supply

        ↓
Responsibility Assignment
        ↓
Territory
        ↓
Execution
        ↓
Observation
        ↓
World State Update
```

---

## 75. Canonical vs Derived vs Decision Object

This is the three layers that v1.2 must clarify.

| Type | Example | Whether it belongs to World Fact |
|---|---|---|
| Canonical State | Account, ResourceDeployment, Assignment | Yes |
| Estimate / Derived State | Opportunity, Workload, Gap | Computed state with source |
| Decision State | Candidate Territory, Scenario | No, unless approved for implementation |

This is especially important:

```text
Candidate Territory
```

Before Approved:

> Not a Territory World State.

---

## 76. Reference Implementation Recommendation

On the engineering side of v1.2, I recommend keeping it simple and not building a complex Knowledge Graph platform prematurely.

You can start with:

```text
PostgreSQL + PostGIS
```

Take on:

```text
Canonical State
Temporal State
Spatial Object
Assignment
Policy
Snapshot Metadata
```

Then use:

```text
append-only event / observation tables
```

Implement the first version of the Event Store.

Graph Projection in the first phase can even:

```text
PostgreSQL materialized graph view
```

or a lightweight graph engine.

Only after Agent / complex relation traversal clearly proves the need should a specialized graph database be introduced.

This is very much in line with:

> **Reuse Before Reinvent + Minimum Necessary Infrastructure。**

---

## 77. Things Not Recommended at the Start of v1.2

In the first phase, do not:

```text
Full-scale RDF / OWL
Complex semantic reasoner
Full event sourcing database
Self-built time-series database
Self-built graph database
Self-built MDM
Self-built GIS Engine
```

None of these are core innovations of the current SRAF.

What SRAF truly should first prove:

```text
World semantics
→ Decision problem
→ Candidate decision
→ Evaluation
```

Is able to run through.

---

## 78. World Model Architecture Gate

In later development reviews, the following situations should be directly considered architecture issues:

```text
Directly using external business IDs as Canonical IDs

Equating Account with a physical store completely

Potential directly becoming an Account field without a source

Merging CoverageNeed and Commitment

Merging Salesperson and Resource

Merging home location and deployment location

Territory requiring Polygon mandatorily

Account can have only one owner

Assignment has no time validity period

Solver field entering Canonical Entity

Scenario directly modifying production World State

Future obtained data being used for a past Baseline

Model Estimate lacks model_version

Derived State lacks calculation_version

Graph is treated as the sole Source of Truth

Solver Solution directly updates Territory
```

This set can directly become the basis for the CI / Architecture Review Checklist.

---

## 79. A Specific Example

Assume the system now sees:

> In the Changsha Hexi market, 800 high-potential restaurant stores have been newly added.

The correct World update should be:

```text
External POI / O2O
        ↓
Observations
        ↓
Commercial Entity Resolution
        ↓
Prospect / ServiceLocation
        ↓
Market Signals
        ↓
Opportunity Estimates
        ↓
Demand Surface Recalculation
        ↓
Allocation Gap Recalculation
```

At this point:

> **Territory does not undergo any automatic changes.**

Allocation Intelligence discovers:

```text
Opportunity Gap ↑
Capacity Gap ↑
```

Only later:

```text
DecisionTrigger
       ↓
Expansion / Rebalancing Decision Case
```

This is the boundary between the World Model and the Decision Model.

---

## 80. Another Assignment Example

Current:

```text
Account A
Selling → Rep17
Merchandising → Merch05
KA → KAM02
```

The system should not represent it as:

```text
account.owner = Rep17
```

But as:

```text
Responsibility R1
Account A / Selling / Primary

Assignment A1
R1 → Rep17

Responsibility R2
Account A / Merchandising

Assignment A2
R2 → Merch05

Responsibility R3
Account A / KA Negotiation

Assignment A3
R3 → KAM02
```

Thus the so-called:

```text
Field Territory T17
```

only aggregates:

```text
Selling Primary
```

that class of Assignment.

At this point, Overlay Territory naturally holds.

---

## 81. World Model Minimum Viable Version

To prevent Agent from turning v1.2 into a large project from the start, I recommend **MVP World Model implements only 14 core objects**:

```text
Market
GeoUnit
Account / Prospect
ServiceLocation
OpportunityEstimate
CoverageNeed
CoverageCommitment
SalesResource
ResourceDeployment
CapacitySupply
Responsibility
ResponsibilityAssignment
Policy
WorldSnapshot
```

Additionally, four supporting models:

```text
Assertion
Evidence
Observation
Event
```

Territory can initially be as:

```text
Assignment Group + Projection
```

implemented.

Wait until the first Territory Decision Engine starts before expanding the full Territory lifecycle.

---

## 82. Definition of Done

The implementation of `01_WORLD_MODEL_SPEC` cannot use:

> "Table created"

as Done.

At least the following chain must be verified to be runnable:

```text
Source Data
   ↓
Canonical Account
   ↓
Opportunity Estimate
   ↓
Coverage Need
   ↓
Workload
   ↓
Resource Deployment
   ↓
Responsibility Assignment
```

Then be able to:

```text
Create World Snapshot
      ↓
Fork Scenario
      ↓
Generate Problem Projection
      ↓
Run Decision Engine
      ↓
Create Candidate Decision
```

and Candidate does not pollute the real world.

Only by doing this is the World Model v1 considered valid.

---

## 83. v1.2 Engineering Architecture Conclusion

Regarding:

> **Which does the World Model actually adopt—Event Sourcing, Knowledge Graph, or relational model?**

v1.2 officially adopts:

```text
                    SRAF WORLD MODEL

             Canonical Relational State
                       │
               Source of Truth
                       │
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
 Temporal/Event     Spatial       Evidence
     History        Projection     Provenance
        │              │              │
        └──────────────┼──────────────┘
                       ↓
                 Graph Projection
                       ↓
              Semantic / Agent View
                       ↓
               Problem Projection
                       ↓
                Decision Engine
```

**Relational Canonical State is responsible for "what it is"; Event/Observation is responsible for "what has happened"; Graph is responsible for "how relations are connected"; Spatial is responsible for "where it is"; Evidence is responsible for "why we believe"; Problem Projection is responsible for "what the optimizer needs to see this time".**

This boundary serves as the engineering baseline for SRAF v1.2 World Model.
