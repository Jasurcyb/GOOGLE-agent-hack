from __future__ import annotations

import pytest

from risk_model.corpus import EvaluationCorpus, CorpusEntry
from risk_model.metrics import (
    compute_brier_score,
    compute_ece,
    compute_precision_recall,
    compute_critical_recall,
)
from datetime import datetime, timezone


class TestMetrics:
    def test_brier_score_perfect(self):
        assert compute_brier_score([0, 1, 0, 1], [0.0, 1.0, 0.0, 1.0]) == 0.0

    def test_brier_score_worst(self):
        assert compute_brier_score([0, 1], [1.0, 0.0]) == 1.0

    def test_ece_perfect(self):
        assert compute_ece([0, 1, 0, 1], [0.0, 1.0, 0.0, 1.0]) == 0.0

    def test_precision_recall(self):
        p, r = compute_precision_recall([1, 1, 0, 0], [1, 0, 0, 0])
        assert p == 1.0
        assert r == 0.5

    def test_critical_recall(self):
        y_true = [1, 1, 0]
        y_pred = [1, 0, 0]
        severity = ["SEV1", "SEV2", None]
        cr = compute_critical_recall(y_true, y_pred, severity)
        assert cr == 0.5


class TestCorpus:
    def test_corpus_add_and_size(self):
        corpus = EvaluationCorpus()
        corpus.add(CorpusEntry(
            pr_id="pr-1",
            repository="acme/test",
            pr_number=1,
            head_sha="abc",
            merged_at=datetime.now(timezone.utc),
            features={},
            predicted_score=50,
            predicted_probability=0.5,
            actual_outcome="no_incident",
        ))
        assert corpus.size == 1

    def test_corpus_split_by_repo(self):
        corpus = EvaluationCorpus()
        now = datetime.now(timezone.utc)
        corpus.add(CorpusEntry(
            pr_id="1", repository="acme/a", pr_number=1, head_sha="x",
            merged_at=now, features={}, predicted_score=50,
            predicted_probability=0.5, actual_outcome="no_incident",
        ))
        corpus.add(CorpusEntry(
            pr_id="2", repository="acme/b", pr_number=2, head_sha="y",
            merged_at=now, features={}, predicted_score=80,
            predicted_probability=0.8, actual_outcome="incident",
        ))
        train, test = corpus.split_by_repo_and_time(test_repos=["acme/b"])
        assert len(train) == 1
        assert len(test) == 1
        assert test[0].repository == "acme/b"
