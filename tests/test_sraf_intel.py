"""WP13 sraf_intel 规范一致性测试（对照 docs/sraf/02、03、04 的结构定义）。

每个断言锚定规范章节：枚举成员集合、schema 字段、路由表映射、
materiality 封顶与触发门控语义。全部纯内存，hermetic。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sraf_intel
from sraf_intel import (
    ALLOCATIONGAP_SCHEMA_FIELDS, CONFIDENCE_FLOOR, DECISIONTRIGGER_SCHEMA_FIELDS,
    DIAGNOSIS_ROUTES, DPCode, GapSubtype, GapType, IDENTITY_SUBTYPES,
    MATERIALITY_ORDER, MaterialityAssessment, MaterialityLevel,
    NonDPRoute, ProblemRouter, RouterOutput, AllocationGap,
    assess_materiality, build_trigger, cap_materiality, evaluate_trigger,
    route_from_materiality, schema_field_names, TriggerDecision,
)


def gap(**kw):
    base = dict(gap_id="G-001", gap_type=GapType.CAPACITY, scope="华南大区",
                period="2026-Q3", observed_value=140.0, reference_value=100.0,
                severity=0.6, persistence=4, confidence=0.9)
    base.update(kw)
    return AllocationGap(**base)


class TestSpecConsistency(unittest.TestCase):
    """规范结构断言（字段/枚举/路由表须与 docs/sraf 定义逐字对齐）。"""

    def test_package_import_and_docstrings_cite_specs(self):
        self.assertTrue(sraf_intel.__doc__ and "04" in sraf_intel.__doc__)
        for mod in ("gaps", "materiality", "trigger", "router"):
            import importlib
            m = importlib.import_module(f"sraf_intel.{mod}")
            self.assertIsNotNone(m.__doc__)
            self.assertRegex(m.__doc__, r"0[234]")

    def test_gap_type_is_exactly_seven_first_level_categories(self):
        # 02 §10：v1.2 固定七个一级 Gap 类别
        self.assertEqual({t.value for t in GapType}, {
            "CoverageGap", "CapacityGap", "OpportunityGap", "SpatialTravelGap",
            "CapabilityGap", "LocalAllocationGap", "StabilityGap"})

    def test_identity_subtypes_exact_four_from_02_s21(self):
        # 02 §21：DataQualityIssue 的四个 identity 子型，名字逐字对齐
        self.assertEqual({s.value for s in IDENTITY_SUBTYPES}, {
            "IdentityDuplicate", "IdentityFalseMatch",
            "IdentityUnresolved", "HierarchyMisattribution"})

    def test_coverage_funnel_subtypes_from_04_s11A(self):
        # 04 §11A：CoverageGap 沿漏斗三分为 v1.2 子类型
        self.assertEqual({s.value for s in GapSubtype} & {
            "CoverageAllocationGap", "SchedulingCoverageGap",
            "ExecutionCoverageGap"}, {
            "CoverageAllocationGap", "SchedulingCoverageGap",
            "ExecutionCoverageGap"})

    def test_materiality_levels_exact_five_in_spec_order(self):
        # 02 §28 / 04 §26：Informational→Monitor→Review→Actionable→Critical
        self.assertEqual([m.value for m in MaterialityLevel], [
            "Informational", "Monitor", "Review", "Actionable", "Critical"])
        self.assertEqual(sorted(MATERIALITY_ORDER.values()), [0, 1, 2, 3, 4])

    def test_allocationgap_schema_fields_cover_02_s9(self):
        # 02 §9 统一结构的 15 个字段必须全部存在
        self.assertEqual(set(ALLOCATIONGAP_SCHEMA_FIELDS)
                         - set(schema_field_names()), set())
        self.assertEqual(len(ALLOCATIONGAP_SCHEMA_FIELDS), 15)

    def test_decisiontrigger_schema_fields_cover_02_s29(self):
        self.assertEqual(set(DECISIONTRIGGER_SCHEMA_FIELDS)
                         - set(
                             f.name for f in
                             __import__("dataclasses").fields(
                                 __import__("sraf_intel.trigger",
                                            fromlist=["DecisionTrigger"]
                                         ).DecisionTrigger)), set())

    def test_dp_codes_match_04_s28_table(self):
        self.assertEqual([d.value for d in DPCode], [
            "DP01 Resource Sizing", "DP02 Resource Location",
            "DP03 Territory Alignment", "DP04 Personnel Matching",
            "DP05 Coverage Allocation", "DP06 Visit Scheduling",
            "DP07 Daily Routing"])

    def test_route_table_matches_04_s28_mapping(self):
        expect = {
            "CapacityShortage": DPCode.DP01.value,
            "ResourceLocationMismatch": DPCode.DP02.value,
            "TerritoryImbalance": DPCode.DP03.value,
            "CapabilityMismatch": DPCode.DP04.value,
            "CoveragePolicyMismatch": DPCode.DP05.value,
            "SchedulingInfeasibility": DPCode.DP06.value,
            "RoutingInefficiency": DPCode.DP07.value,
            "DataQualityIssue": NonDPRoute.WORLD_MODEL_REPAIR.value,
            "ModelQualityIssue": NonDPRoute.MODEL_GOVERNANCE.value,
            "PolicyConflict": NonDPRoute.POLICY_REVIEW.value,
        }
        for diagnosis, route in expect.items():
            self.assertEqual(DIAGNOSIS_ROUTES[diagnosis], route,
                             f"04 §28 路由漂移: {diagnosis}")


class TestAllocationGap(unittest.TestCase):
    def test_gap_value_defaults_to_observed_minus_reference(self):
        g = gap()
        self.assertEqual(g.gap_value, 40.0)
        self.assertAlmostEqual(g.relative_magnitude(), 0.4)

    def test_subtype_parent_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            gap(subtype=GapSubtype.COVERAGE_ALLOCATION)  # 父类是 CoverageGap

    def test_identity_subtype_allowed_on_any_gap_type(self):
        # identity 子型归属根因轴（02 §21），不校验 Gap 类别
        g = gap(subtype=GapSubtype.IDENTITY_UNRESOLVED)
        self.assertIn(g.subtype, IDENTITY_SUBTYPES)

    def test_confidence_and_severity_range_validation(self):
        with self.assertRaises(ValueError):
            gap(confidence=1.5)
        with self.assertRaises(ValueError):
            gap(severity=-0.1)
        with self.assertRaises(ValueError):
            gap(gap_id="")


class TestMateriality(unittest.TestCase):
    def test_strong_persistent_gap_is_actionable(self):
        a = assess_materiality(gap())  # mag 0.4, sev 0.6, persist 4/4, conf 0.9
        self.assertEqual(a.materiality_level, MaterialityLevel.ACTIONABLE)

    def test_low_confidence_caps_at_review(self):
        a = assess_materiality(gap(confidence=CONFIDENCE_FLOOR - 0.01))
        self.assertEqual(a.materiality_level, MaterialityLevel.REVIEW)
        self.assertIn("confidence_floor", a.caps_applied)

    def test_nonpositive_edv_caps_at_review(self):
        a = assess_materiality(gap(), expected_decision_value=-1.0)
        self.assertEqual(a.materiality_level, MaterialityLevel.REVIEW)
        self.assertIn("edv_nonpositive", a.caps_applied)

    def test_trivial_gap_is_informational(self):
        a = assess_materiality(gap(observed_value=100.5, reference_value=100.0,
                                   severity=0.0, persistence=1))
        self.assertEqual(a.materiality_level, MaterialityLevel.INFORMATIONAL)

    def test_identity_unresolved_ratio_caps_actionable(self):
        # 04 §24：占比超阈 → 不得高于 Review
        self.assertEqual(
            cap_materiality(MaterialityLevel.CRITICAL,
                            identity_unresolved_ratio=0.10),
            MaterialityLevel.REVIEW)
        self.assertEqual(
            cap_materiality(MaterialityLevel.REVIEW,
                            identity_unresolved_ratio=0.10),
            MaterialityLevel.REVIEW)
        # 未超阈 → 原级返回
        self.assertEqual(
            cap_materiality(MaterialityLevel.CRITICAL,
                            identity_unresolved_ratio=0.01),
            MaterialityLevel.CRITICAL)


class TestTrigger(unittest.TestCase):
    def setUp(self):
        self.g = gap()
        self.t = build_trigger(self.g, "CapacityShortage",
                               entry_threshold=0.30, persistence=3,
                               cooldown_periods=5)

    def test_trigger_schema_and_hysteresis_default(self):
        self.assertEqual(self.t.trigger_id, "T-G-001")
        self.assertEqual(self.t.scope, "华南大区")
        self.assertEqual(self.t.materiality_gate, MaterialityLevel.ACTIONABLE)
        self.assertEqual(self.t.exit_threshold, 0.15)  # entry 的一半防抖

    def test_exit_threshold_must_not_exceed_entry(self):
        with self.assertRaises(ValueError):
            build_trigger(self.g, "CapacityShortage",
                          entry_threshold=0.2, exit_threshold=0.3)

    def test_full_chain_creates_decision_case(self):
        r = evaluate_trigger(self.t, self.g, MaterialityLevel.ACTIONABLE,
                             persistence_periods=3, confidence=0.9)
        self.assertEqual(r.decision, TriggerDecision.CREATE_DECISION_CASE)

    def test_cooldown_blocks_but_critical_passes(self):
        blocked = evaluate_trigger(self.t, self.g, MaterialityLevel.ACTIONABLE,
                                   persistence_periods=3, confidence=0.9,
                                   cooldown_remaining_periods=2)
        self.assertEqual(blocked.decision, TriggerDecision.NO_ACTION)
        critical = evaluate_trigger(self.t, self.g, MaterialityLevel.CRITICAL,
                                    persistence_periods=3, confidence=0.9,
                                    cooldown_remaining_periods=2)
        self.assertEqual(critical.decision, TriggerDecision.CREATE_DECISION_CASE)

    def test_below_materiality_gate_and_low_confidence_routes(self):
        r = evaluate_trigger(self.t, self.g, MaterialityLevel.REVIEW,
                             persistence_periods=3, confidence=0.9)
        self.assertEqual(r.decision, TriggerDecision.REQUEST_MORE_EVIDENCE)
        r2 = evaluate_trigger(self.t, self.g, MaterialityLevel.MONITOR,
                              persistence_periods=3, confidence=0.9)
        self.assertEqual(r2.decision, TriggerDecision.MONITOR)
        r3 = evaluate_trigger(self.t, self.g, MaterialityLevel.ACTIONABLE,
                              persistence_periods=3, confidence=0.4)
        self.assertEqual(r3.decision, TriggerDecision.REQUEST_MORE_EVIDENCE)

    def test_hysteresis_band_monitors(self):
        weak = gap(observed_value=118.0, persistence=1)
        r = evaluate_trigger(self.t, weak, MaterialityLevel.ACTIONABLE,
                             persistence_periods=1, confidence=0.9)
        self.assertEqual(r.decision, TriggerDecision.MONITOR)  # 持续不足+滞回带
        tiny = gap(observed_value=110.0, persistence=1)
        r2 = evaluate_trigger(self.t, tiny, MaterialityLevel.ACTIONABLE,
                              persistence_periods=5, confidence=0.9)
        self.assertEqual(r2.decision, TriggerDecision.NO_ACTION)  # ≤ exit


class TestProblemRouter(unittest.TestCase):
    def setUp(self):
        self.router = ProblemRouter()

    def test_root_causes_route_to_dp_codes(self):
        cases = {
            "CapacityShortage": DPCode.DP01.value,
            "ResourceLocationMismatch": DPCode.DP02.value,
            "TerritoryImbalance": DPCode.DP03.value,
            "PersonnelConstraint": DPCode.DP04.value,
            "CoverageAllocationMismatch": DPCode.DP05.value,
            "SchedulingInfeasibility": DPCode.DP06.value,
            "RoutingInefficiency": DPCode.DP07.value,
        }
        for diagnosis, dp in cases.items():
            r = self.router.route(diagnosis)
            self.assertEqual((r.output, r.primary_route),
                             (RouterOutput.ROUTE, dp), diagnosis)

    def test_identity_subtypes_route_to_world_model_repair(self):
        for s in IDENTITY_SUBTYPES:
            r = self.router.route(s.value)
            self.assertEqual(r.primary_route,
                             NonDPRoute.WORLD_MODEL_REPAIR.value, s)

    def test_data_quality_routes_to_world_model_repair(self):
        r = self.router.route("DataQualityIssue")
        self.assertEqual(r.primary_route, NonDPRoute.WORLD_MODEL_REPAIR.value)

    def test_unknown_diagnosis_requests_more_evidence(self):
        r = self.router.route("完全未知的诊断")
        self.assertEqual(r.output, RouterOutput.REQUEST_MORE_EVIDENCE)
        self.assertIsNone(r.primary_route)

    def test_no_action_is_legal_output(self):
        # 04 §36：Router 不给 NoAction 属于原则性违规
        r = self.router.route("NoGap")
        self.assertEqual(r.output, RouterOutput.NO_ACTION)

    def test_identity_ratio_above_threshold_appends_repair_alternative(self):
        r = self.router.route("CapacityShortage", identity_unresolved_ratio=0.2)
        self.assertIn(NonDPRoute.WORLD_MODEL_REPAIR.value, r.alternatives)

    def test_route_from_trigger_passthrough(self):
        from sraf_intel import TriggerResult
        r = self.router.route_from_trigger(
            TriggerResult(TriggerDecision.MONITOR, "x", "T-1",
                          MaterialityLevel.MONITOR))
        self.assertEqual(r.output, RouterOutput.MONITOR)
        with self.assertRaises(ValueError):
            self.router.route_from_trigger(
                TriggerResult(TriggerDecision.CREATE_DECISION_CASE, "x",
                              "T-1", MaterialityLevel.ACTIONABLE))

    def test_materiality_fallback_outputs(self):
        self.assertEqual(route_from_materiality(MaterialityLevel.REVIEW),
                         RouterOutput.REQUEST_MORE_EVIDENCE)
        self.assertEqual(route_from_materiality(MaterialityLevel.MONITOR),
                         RouterOutput.MONITOR)
        self.assertEqual(route_from_materiality(MaterialityLevel.INFORMATIONAL),
                         RouterOutput.NO_ACTION)

    def test_end_to_end_gap_to_route(self):
        # Gap → Materiality → Trigger → Router 全链（04 §1 核心链）
        g = gap(gap_id="G-E2E", gap_type=GapType.LOCAL_ALLOCATION,
                subtype=None, observed_value=130.0, reference_value=100.0)
        a = assess_materiality(g)
        t = build_trigger(g, "TerritoryImbalance", entry_threshold=0.25)
        tr = evaluate_trigger(t, g, a.materiality_level,
                              persistence_periods=2, confidence=0.9)
        self.assertEqual(tr.decision, TriggerDecision.CREATE_DECISION_CASE)
        r = self.router.route("TerritoryImbalance")
        self.assertEqual(r.primary_route, DPCode.DP03.value)
        self.assertIsInstance(a, MaterialityAssessment)


if __name__ == "__main__":
    unittest.main()
