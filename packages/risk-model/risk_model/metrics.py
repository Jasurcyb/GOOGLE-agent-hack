from __future__ import annotations

import math
from typing import Any

import numpy as np


def compute_brier_score(y_true: list[int], y_prob: list[float]) -> float:
    """Brier score: mean squared difference between predictions and outcomes."""
    y_t = np.array(y_true, dtype=float)
    y_p = np.array(y_prob, dtype=float)
    return float(np.mean((y_p - y_t) ** 2))


def compute_ece(y_true: list[int], y_prob: list[float], n_bins: int = 10) -> float:
    """Expected Calibration Error."""
    y_t = np.array(y_true)
    y_p = np.array(y_prob)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)

    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (y_p >= lo) & (y_p < hi if i < n_bins - 1 else y_p <= hi)
        if mask.sum() == 0:
            continue
        bin_avg_conf = y_p[mask].mean()
        bin_avg_acc = y_t[mask].mean()
        ece += (mask.sum() / n) * abs(bin_avg_conf - bin_avg_acc)

    return float(ece)


def compute_precision_recall(
    y_true: list[int], y_pred: list[int]
) -> tuple[float, float]:
    """PR-level precision and recall for binary classification."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def compute_critical_recall(
    y_true: list[int],
    y_pred: list[int],
    severity: list[str | None],
) -> float:
    """Recall specifically for critical-severity incidents."""
    critical_indices = [
        i for i, s in enumerate(severity)
        if s in ("SEV1", "SEV2", "critical", "high")
    ]
    if not critical_indices:
        return 1.0

    detected = sum(
        1 for i in critical_indices
        if y_pred[i] == 1
    )
    return detected / len(critical_indices)


def compute_false_block_rate(
    y_true: list[int],
    y_pred: list[int],
    block_threshold: int = 80,
    scores: list[int] | None = None,
) -> float:
    """Rate of PRs that were blocked but had no incident."""
    if scores is None:
        scores = y_pred

    blocked_no_incident = sum(
        1 for i in range(len(y_true))
        if scores[i] >= block_threshold and y_true[i] == 0
    )
    total_blocked = sum(1 for s in scores if s >= block_threshold)

    return blocked_no_incident / total_blocked if total_blocked > 0 else 0.0


def compute_mtte(
    run_durations: list[float],
) -> float:
    """Mean Time To Explanation in seconds."""
    if not run_durations:
        return 0.0
    return sum(run_durations) / len(run_durations)
