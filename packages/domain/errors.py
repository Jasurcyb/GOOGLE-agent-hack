from __future__ import annotations


class AnalysisError(Exception):
    pass


class PolicyViolation(Exception):
    pass


class InsufficientEvidence(Exception):
    pass
