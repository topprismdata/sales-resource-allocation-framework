# SRAF Specification Changelog — v1.1

v1.1 is the first **Implementation Baseline** after the v1.0 consistency review.

## P0 changes applied

1. Clarified normative ownership of Baseline / Scenario / HumanOverride / ProblemProjection.
2. Reworked resource semantics:
   `ResourceArchetype → ResourceRequirement → ResourceDeployment → DeploymentAssignment → SalesResource`.
3. Added missing canonical concepts: `Capability`, `SalesActivity`, `ServiceChannel`, `ResourceRequirement`, `DeploymentAssignment`.
4. Froze Territory semantics: Territory membership is `Territory ↔ Responsibility`.
5. Renamed local mismatch subtype from `AllocationGap` to `LocalAllocationGap`.
6. Unified formal decision object as `ApprovedDecision`.

## P1 changes applied

1. Renamed technical `DecisionRun` to `ProblemRun`; defined run hierarchy under `OrchestrationRun`.
2. Added `RequirementExceptionProposal`.
3. Clarified `ChangeBudget` as requirements/guardrails, not a canonical entity.
4. Clarified `DecisionRisk` and `AutomationLevel` ownership under orchestration.
5. Normalized CoverageGap subtypes under 04.
6. Replaced ambiguous `MissedOpportunity` with `UncoveredOpportunity` / `OpportunityAtRisk`.
7. Upgraded intrinsic workload to activity-level aggregation.
8. Froze `ResourceEquivalent` as a derived metric.

## Implementation restraint

v1.1 also strengthens:

```text
Modular Monolith First
No dedicated graph DB in Phase 0–3
No generic BPMN requirement in Phase 0
No new solver platform before the vertical slice proves need
```
