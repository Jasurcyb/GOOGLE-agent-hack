from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from risk_model.corpus import CorpusEntry
from risk_model.metrics import (
    compute_brier_score,
    compute_critical_recall,
    compute_ece,
    compute_false_block_rate,
    compute_mtte,
    compute_precision_recall,
)


@dataclass
class CalibrationResult:
    model_version: str
    precision: float = 0.0
    recall: float = 0.0
    critical_recall: float = 0.0
    brier_score: float = 0.0
    ece: float = 0.0
    false_block_rate: float = 0.0
    mtte_seconds: float = 0.0
    trained_on: int = 0
    tested_on: int = 0
    coefficients: dict[str, float] = field(default_factory=dict)
    fallback: bool = False


def _extract_feature_vector(entry: CorpusEntry, feature_names: list[str]) -> np.ndarray:
    return np.array([entry.features.get(f, 0.0) for f in feature_names])


def _extract_labels(entries: list[CorpusEntry]) -> list[int]:
    return [1 if e.actual_outcome == "incident" or e.rollback else 0 for e in entries]


def calibrate_logistic(
    train: list[CorpusEntry],
    test: list[CorpusEntry],
    feature_names: list[str] | None = None,
) -> CalibrationResult:
    """Logistic regression calibration on V1 features."""
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return CalibrationResult(
            model_version="v1_fallback",
            fallback=True,
            trained_on=len(train),
            tested_on=len(test),
        )

    if feature_names is None:
        feature_names = [
            "change_hazard_score", "blast_radius_score", "business_criticality_score",
            "test_gap_score", "operational_history_score", "mitigating_score",
            "authoritative_bindings", "is_breaking_change",
        ]

    if len(train) < 10:
        return CalibrationResult(
            model_version="v1_fallback",
            fallback=True,
            trained_on=len(train),
            tested_on=len(test),
        )

    X_train = np.array([_extract_feature_vector(e, feature_names) for e in train])
    y_train = np.array(_extract_labels(train))
    X_test = np.array([_extract_feature_vector(e, feature_names) for e in test])
    y_test = np.array(_extract_labels(test))

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_train_s, y_train)

    y_prob = model.predict_proba(X_test_s)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    precision, recall = compute_precision_recall(y_test.tolist(), y_pred.tolist())
    severities = [e.incident_severity for e in test]
    critical_recall = compute_critical_recall(y_test.tolist(), y_pred.tolist(), severities)
    brier = compute_brier_score(y_test.tolist(), y_prob.tolist())
    ece = compute_ece(y_test.tolist(), y_prob.tolist())

    scores = [min(100, int(p * 100)) for p in y_prob]
    fbr = compute_false_block_rate(y_test.tolist(), y_pred.tolist(), scores=scores)

    coefficients = {
        name: float(coef)
        for name, coef in zip(feature_names, model.coef_[0])
    }

    return CalibrationResult(
        model_version="v2_logistic",
        precision=precision,
        recall=recall,
        critical_recall=critical_recall,
        brier_score=brier,
        ece=ece,
        false_block_rate=fbr,
        trained_on=len(train),
        tested_on=len(test),
        coefficients=coefficients,
    )


def train_gradient_boosted(
    train: list[CorpusEntry],
    test: list[CorpusEntry],
    feature_names: list[str] | None = None,
) -> CalibrationResult:
    """Gradient-boosted model calibration (v3). Falls back to logistic if insufficient data."""
    if len(train) < 50:
        return calibrate_logistic(train, test, feature_names)

    try:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return calibrate_logistic(train, test, feature_names)

    if feature_names is None:
        feature_names = [
            "change_hazard_score", "blast_radius_score", "business_criticality_score",
            "test_gap_score", "operational_history_score", "mitigating_score",
            "authoritative_bindings", "is_breaking_change",
            "downstream_assets", "lineage_paths",
        ]

    X_train = np.array([_extract_feature_vector(e, feature_names) for e in train])
    y_train = np.array(_extract_labels(train))
    X_test = np.array([_extract_feature_vector(e, feature_names) for e in test])
    y_test = np.array(_extract_labels(test))

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=3,
        random_state=42,
    )
    model.fit(X_train_s, y_train)

    y_prob = model.predict_proba(X_test_s)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    precision, recall = compute_precision_recall(y_test.tolist(), y_pred.tolist())
    severities = [e.incident_severity for e in test]
    critical_recall = compute_critical_recall(y_test.tolist(), y_pred.tolist(), severities)
    brier = compute_brier_score(y_test.tolist(), y_prob.tolist())
    ece = compute_ece(y_test.tolist(), y_prob.tolist())
    scores = [min(100, int(p * 100)) for p in y_prob]
    fbr = compute_false_block_rate(y_test.tolist(), y_pred.tolist(), scores=scores)

    return CalibrationResult(
        model_version="v3_gbdt",
        precision=precision,
        recall=recall,
        critical_recall=critical_recall,
        brier_score=brier,
        ece=ece,
        false_block_rate=fbr,
        trained_on=len(train),
        tested_on=len(test),
    )


def evaluate_predictions(
    y_true: list[int],
    y_prob: list[float],
    y_pred: list[int],
    severity: list[str | None] | None = None,
    run_durations: list[float] | None = None,
) -> dict[str, float]:
    """Full evaluation report."""
    p, r = compute_precision_recall(y_true, y_pred)
    cr = compute_critical_recall(y_true, y_pred, severity or [None] * len(y_true))
    brier = compute_brier_score(y_true, y_prob)
    ece = compute_ece(y_true, y_prob)
    scores = [min(100, int(p * 100)) for p in y_prob]
    fbr = compute_false_block_rate(y_true, y_pred, scores=scores)
    mtte = compute_mtte(run_durations or [])

    return {
        "precision": p,
        "recall": r,
        "critical_recall": cr,
        "brier_score": brier,
        "ece": ece,
        "false_block_rate": fbr,
        "mtte_seconds": mtte,
    }
