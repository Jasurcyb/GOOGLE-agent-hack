from __future__ import annotations

import pytest

from test_agent.planner import TestPlanner
from test_agent.sandbox import SandboxValidator


class TestTestPlanner:
    def test_plan_from_hypotheses(self):
        planner = TestPlanner()
        plans = planner.plan_tests(
            hypotheses=[
                {
                    "mechanism": "contract_mismatch",
                    "impacted_urns": ["urn:li:dataset:payments"],
                    "evidence_refs": ["symbol:src/parser.py:parse_amount"],
                    "verification_status": "VERIFIED",
                    "confidence": 0.9,
                    "recommended_test_ids": ["test_parse_amount"],
                }
            ],
            affected_assets=[
                {"urn": "urn:li:dataset:payments", "type": "DATASET", "tags": ["tier0"]},
            ],
        )
        assert len(plans) >= 1
        assert plans[0].kind == "unit_test"
        assert plans[0].traceability_id == "rec_001"

    def test_skip_unverified(self):
        planner = TestPlanner()
        plans = planner.plan_tests(
            hypotheses=[
                {
                    "mechanism": "contract_mismatch",
                    "verification_status": "UNVERIFIED",
                    "confidence": 0.2,
                }
            ],
            affected_assets=[],
        )
        assert len(plans) == 0

    def test_escalation_for_dashboard(self):
        planner = TestPlanner()
        plans = planner.plan_tests(
            hypotheses=[
                {
                    "mechanism": "ui_path",
                    "impacted_urns": ["urn:li:dashboard:revenue"],
                    "evidence_refs": ["lineage:path:abc"],
                    "verification_status": "VERIFIED",
                    "confidence": 0.85,
                }
            ],
            affected_assets=[
                {"urn": "urn:li:dashboard:revenue", "type": "DASHBOARD"},
            ],
        )
        kinds = [p.kind for p in plans]
        assert "playwright_smoke_test" in kinds


class TestSandboxValidator:
    def test_valid_python_code(self):
        validator = SandboxValidator()
        code = "def test_basic():\n    assert 1 + 1 == 2\n"
        result = validator.validate(code, framework="pytest")
        assert result.parse_passed is True
        assert result.lint_passed is True

    def test_invalid_syntax(self):
        validator = SandboxValidator()
        code = "def test_bad(:\n    pass\n"
        result = validator.validate(code)
        assert result.parse_passed is False
        assert result.valid is False
