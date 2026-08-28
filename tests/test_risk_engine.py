from __future__ import annotations

import pytest

from risk_engine.scorer import RiskFeatures, score
from domain.policy import PolicyConfig


class TestRiskEngine:
    def test_low_risk_score(self):
        features = RiskFeatures(
            change_hazard_score=3,
            blast_radius_score=2,
            business_criticality_score=7,
            test_gap_score=0,
            operational_history_score=0,
            mitigating_score=-3,
            has_regression_test=True,
            mapping_coverage=0.8,
            lineage_completeness=0.9,
            static_resolution_certainty=0.95,
            test_coverage_available=True,
        )
        result = score("run-1", features, PolicyConfig())
        assert result.risk_score < 30
        assert result.risk_level.value == "low"
        assert result.confidence > 70

    def test_critical_risk_with_policy_floor(self):
        features = RiskFeatures(
            change_hazard_score=12,
            blast_radius_score=15,
            business_criticality_score=25,
            test_gap_score=10,
            operational_history_score=5,
            mitigating_score=0,
            has_tier0=True,
            has_payment=True,
            is_breaking_change=True,
            has_authoritative_payment_path=True,
            has_regression_test=False,
            authoritative_bindings=1,
            mapping_coverage=0.9,
            lineage_completeness=0.85,
            static_resolution_certainty=0.95,
        )
        result = score("run-2", features, PolicyConfig())
        assert result.risk_score >= 85
        assert result.risk_level.value == "critical"
        assert result.decision.get("policy_applied") is True

    def test_confidence_below_neutral_threshold(self):
        features = RiskFeatures(
            change_hazard_score=5,
            blast_radius_score=5,
            business_criticality_score=7,
            test_gap_score=5,
            mapping_coverage=0.3,
            lineage_completeness=0.4,
            static_resolution_certainty=0.5,
            test_coverage_available=False,
        )
        result = score("run-3", features, PolicyConfig())
        assert result.confidence < 70
        assert result.requires_review is True

    def test_regression_probability_range(self):
        features = RiskFeatures(
            change_hazard_score=10,
            blast_radius_score=10,
            business_criticality_score=15,
        )
        result = score("run-4", features, PolicyConfig())
        assert 0.0 <= result.regression_probability <= 1.0

    def test_impact_severity_range(self):
        features = RiskFeatures(
            blast_radius_score=20,
            business_criticality_score=25,
        )
        result = score("run-5", features, PolicyConfig())
        assert 0.0 <= result.impact_severity <= 1.0

    def test_mitigating_evidence_reduces_score(self):
        features_no_mitigation = RiskFeatures(
            change_hazard_score=10,
            business_criticality_score=15,
            test_gap_score=5,
        )
        features_with_mitigation = RiskFeatures(
            change_hazard_score=10,
            business_criticality_score=15,
            test_gap_score=5,
            has_regression_test=True,
            has_data_contract=True,
            has_canary_guardrail=True,
        )
        r1 = score("run-a", features_no_mitigation, PolicyConfig())
        r2 = score("run-b", features_with_mitigation, PolicyConfig())
        assert r2.risk_score <= r1.risk_score
