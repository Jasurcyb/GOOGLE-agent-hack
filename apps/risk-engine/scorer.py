from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from contracts.models.assessment import RiskAssessment, RiskFactor
from contracts.models.enums import RiskLevel
from domain.policy import PolicyConfig


@dataclass
class RiskFeatures:
    change_hazard_score: float = 0.0
    change_hazard_details: list[str] = field(default_factory=list)

    blast_radius_score: float = 0.0
    weighted_downstream: float = 0.0

    business_criticality_score: float = 0.0
    has_tier0: bool = False
    has_payment: bool = False
    has_regulated: bool = False

    test_gap_score: float = 0.0
    changed_behavior_untested: bool = False
    coverage_decline: bool = False
    no_integration_test: bool = False

    operational_history_score: float = 0.0
    recurrent_incident: bool = False
    high_deploy_frequency: bool = False
    ownership_gap: bool = False

    mitigating_score: float = 0.0
    has_regression_test: bool = False
    has_data_contract: bool = False
    has_canary_guardrail: bool = False

    mapping_coverage: float = 0.0
    lineage_completeness: float = 0.0
    lineage_freshness_hours: float | None = None
    static_resolution_certainty: float = 1.0
    test_coverage_available: bool = False
    model_agreement: float = 1.0

    authoritative_bindings: int = 0
    is_breaking_change: bool = False
    has_authoritative_payment_path: bool = False

    @classmethod
    def from_bundle(cls, bundle: dict[str, Any]) -> RiskFeatures:
        features = cls()
        risk_features = bundle.get("risk_features", {})

        features.change_hazard_score = risk_features.get("change_hazard_score", 0.0)
        features.change_hazard_details = risk_features.get("change_hazard_details", [])
        features.blast_radius_score = risk_features.get("blast_radius_score", 0.0)
        features.weighted_downstream = risk_features.get("weighted_downstream", 0.0)
        features.business_criticality_score = risk_features.get("business_criticality_score", 0.0)
        features.has_tier0 = risk_features.get("has_tier0", False)
        features.has_payment = risk_features.get("has_payment", False)
        features.has_regulated = risk_features.get("has_regulated", False)
        features.test_gap_score = risk_features.get("test_gap_score", 0.0)
        features.changed_behavior_untested = risk_features.get("changed_behavior_untested", False)
        features.operational_history_score = risk_features.get("operational_history_score", 0.0)
        features.recurrent_incident = risk_features.get("recurrent_incident", False)
        features.mitigating_score = risk_features.get("mitigating_score", 0.0)
        features.has_regression_test = risk_features.get("has_regression_test", False)
        features.mapping_coverage = risk_features.get("mapping_coverage", 0.0)
        features.lineage_completeness = risk_features.get("lineage_completeness", 0.0)
        features.lineage_freshness_hours = risk_features.get("lineage_freshness_hours")
        features.static_resolution_certainty = risk_features.get("static_resolution_certainty", 1.0)
        features.test_coverage_available = risk_features.get("test_coverage_available", False)
        features.authoritative_bindings = risk_features.get("authoritative_bindings", 0)
        features.is_breaking_change = risk_features.get("is_breaking_change", False)
        features.has_authoritative_payment_path = risk_features.get("has_authoritative_payment_path", False)

        return features


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _compute_change_hazard(features: RiskFeatures) -> RiskFactor:
    points = features.change_hazard_score
    points = _clamp(points, 0, 25)
    return RiskFactor(
        factor_code="change_hazard",
        feature_value=features.change_hazard_score,
        points=points,
        evidence_refs=features.change_hazard_details,
    )


def _compute_blast_radius(features: RiskFeatures) -> RiskFactor:
    weighted = features.weighted_downstream
    points = min(20.0, 4.0 * math.log(1 + weighted)) if weighted > 0 else 0.0
    return RiskFactor(
        factor_code="blast_radius",
        feature_value=weighted,
        points=points,
        evidence_refs=[],
    )


def _compute_business_criticality(features: RiskFeatures) -> RiskFactor:
    points = features.business_criticality_score
    if features.has_tier0 or features.has_payment or features.has_regulated:
        points = max(points, 25)
    points = _clamp(points, 0, 25)
    return RiskFactor(
        factor_code="business_criticality",
        feature_value=features.business_criticality_score,
        points=points,
        evidence_refs=[],
    )


def _compute_test_gap(features: RiskFeatures) -> RiskFactor:
    points = 0.0
    if features.changed_behavior_untested:
        points += 10
    if features.coverage_decline:
        points += 3
    if features.no_integration_test:
        points += 2
    points = _clamp(points, 0, 15)
    return RiskFactor(
        factor_code="test_gap",
        feature_value=points,
        points=points,
        evidence_refs=[],
    )


def _compute_operational_history(features: RiskFeatures) -> RiskFactor:
    points = 0.0
    if features.recurrent_incident:
        points += 5
    if features.high_deploy_frequency:
        points += 3
    if features.ownership_gap:
        points += 2
    points = _clamp(points, 0, 10)
    return RiskFactor(
        factor_code="operational_history",
        feature_value=points,
        points=points,
        evidence_refs=[],
    )


def _compute_mitigating(features: RiskFeatures) -> RiskFactor:
    points = 0.0
    if features.has_regression_test:
        points -= 5
    if features.has_data_contract:
        points -= 3
    if features.has_canary_guardrail:
        points -= 2
    points = _clamp(points, -10, 0)
    return RiskFactor(
        factor_code="mitigating_evidence",
        feature_value=abs(points),
        points=points,
        evidence_refs=[],
    )


def _compute_confidence(features: RiskFeatures) -> int:
    mapping = _clamp(features.mapping_coverage * 100, 0, 100) * 0.30
    lineage = _clamp(features.lineage_completeness * 100, 0, 100) * 0.25
    resolution = features.static_resolution_certainty * 100 * 0.20
    test_avail = (100 if features.test_coverage_available else 0) * 0.15
    agreement = features.model_agreement * 100 * 0.10
    return int(_clamp(mapping + lineage + resolution + test_avail + agreement, 0, 100))


def _compute_regression_probability(features: RiskFeatures) -> float:
    import math as _math

    z = (
        features.change_hazard_score * 0.015
        + features.blast_radius_score * 0.020
        + features.business_criticality_score * 0.010
        + features.test_gap_score * 0.030
        + features.operational_history_score * 0.020
        + features.mitigating_score * 0.015
    )
    z += 0.1 if features.is_breaking_change else 0.0
    z -= 0.15 if features.has_regression_test else 0.0
    return _clamp(1.0 / (1.0 + _math.exp(-z)), 0.0, 1.0)


def _compute_impact_severity(features: RiskFeatures) -> float:
    base = features.blast_radius_score / 20.0
    criticality = features.business_criticality_score / 25.0
    return _clamp((base * 0.6 + criticality * 0.4), 0.0, 1.0)


def _level_from_score(score: int, policy: PolicyConfig) -> RiskLevel:
    thresholds = policy.risk_thresholds
    for level_name, (lo, hi) in thresholds.items():
        if lo <= score <= hi:
            return RiskLevel(level_name)
    if score >= 80:
        return RiskLevel.CRITICAL
    if score >= 60:
        return RiskLevel.HIGH
    if score >= 30:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _apply_policy_floors(score: int, features: RiskFeatures, policy: PolicyConfig) -> int:
    for floor in policy.policy_floors:
        conditions = floor.conditions
        met = True

        if "breaking_change" in conditions and not features.is_breaking_change:
            met = False
        if "authoritative_payment_or_regulated_path" in conditions:
            if not features.has_authoritative_payment_path and not features.has_regulated:
                met = False
        if "no_regression_test" in conditions and features.has_regression_test:
            met = False

        if met:
            score = max(score, floor.floor_score)

    return score


def score(
    run_id: str,
    features: RiskFeatures,
    policy: PolicyConfig | None = None,
) -> RiskAssessment:
    policy = policy or PolicyConfig()

    factors = [
        _compute_change_hazard(features),
        _compute_blast_radius(features),
        _compute_business_criticality(features),
        _compute_test_gap(features),
        _compute_operational_history(features),
        _compute_mitigating(features),
    ]

    raw_score = sum(f.points for f in factors)
    raw_score = int(_clamp(raw_score, 0, 100))

    final_score = _apply_policy_floors(raw_score, features, policy)
    risk_level = _level_from_score(final_score, policy)

    confidence = _compute_confidence(features)
    probability = _compute_regression_probability(features)
    severity = _compute_impact_severity(features)

    requires_review = confidence < policy.confidence_neutral_threshold or risk_level in (
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    )

    return RiskAssessment(
        run_id=run_id,
        risk_score=final_score,
        risk_level=risk_level,
        regression_probability=probability,
        impact_severity=severity,
        confidence=confidence,
        model_version="v1",
        decision={
            "raw_score": raw_score,
            "policy_applied": final_score != raw_score,
            "policy_version": policy.version,
            "factors": {f.factor_code: f.points for f in factors},
        },
        requires_review=requires_review,
        factors=factors,
    )
