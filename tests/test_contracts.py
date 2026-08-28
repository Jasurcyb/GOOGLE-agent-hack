from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from contracts.models.assessment import RegressionAssessment, RiskAssessment, RiskFactor
from contracts.models.code import Symbol, SymbolChange, CodeEdge, ImpactNode, ImpactEdge
from contracts.models.evidence import EvidenceBundle
from contracts.models.enums import RiskLevel, ChangeType, EdgeType, NodeKind, BindingType, Resolution
from contracts.events import (
    CloudEvent,
    PRReceivedEvent,
    PRReceivedData,
    AssessmentScoredEvent,
    AssessmentScoredData,
)


class TestContracts:
    def test_regression_assessment_defaults(self):
        ra = RegressionAssessment(run_id="test-1")
        assert ra.risk_score == 0
        assert ra.affected_assets == []
        assert ra.requires_human_review is False

    def test_risk_assessment_with_factors(self):
        ra = RiskAssessment(
            run_id="test-1",
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            regression_probability=0.65,
            impact_severity=0.82,
            confidence=85,
        )
        assert ra.risk_score == 75
        assert ra.risk_level == RiskLevel.HIGH
        assert ra.model_version == "v1"

    def test_symbol_change_serialization(self):
        sc = SymbolChange(
            symbol_id="src.parser.parse_amount",
            language="python",
            change_type=ChangeType.MODIFIED,
            old_signature="def parse_amount(value: str) -> int",
            new_signature="def parse_amount(value: str) -> Decimal",
            file_path="src/parser.py",
            start_line=42,
            end_line=67,
            semantic_delta={"signature_change": True},
        )
        d = sc.model_dump()
        assert d["change_type"] == "modified"
        assert d["semantic_delta"]["signature_change"] is True

    def test_evidence_bundle_structure(self):
        eb = EvidenceBundle(
            run={"id": "test-1", "repo": "acme/payments", "head_sha": "abc123"},
        )
        assert eb.bundle_version == "1.0"
        assert eb.redaction_manifest.secret_count == 0

    def test_cloud_event_envelope(self):
        data = PRReceivedData(
            run_id="test-1",
            repository="acme/payments",
            pr_number=481,
            head_sha="abc123",
            base_sha="fedcba",
            author_login="dev-alice",
            action="opened",
        )
        envelope = PRReceivedEvent.envelope(data)
        assert envelope.specversion == "1.0"
        assert envelope.type == "com.regressionhunter.pr.received.v1"
        assert envelope.data.pr_number == 481

    def test_impact_node(self):
        node = ImpactNode(
            run_id="test-1",
            node_key="src.parser.parse_amount",
            node_kind=NodeKind.CODE_SYMBOL,
            distance=0,
        )
        assert node.node_kind == NodeKind.CODE_SYMBOL

    def test_enums(self):
        assert RiskLevel.CRITICAL == "critical"
        assert ChangeType.ADDED == "added"
        assert BindingType.AUTHORITATIVE == "authoritative"
        assert Resolution.EXACT == "exact"


class TestDomainModel:
    def test_policy_config_defaults(self):
        from domain.policy import PolicyConfig
        pc = PolicyConfig()
        assert pc.confidence_neutral_threshold == 70
        assert pc.max_tool_calls == 12
        assert pc.token_ceiling == 80000
        assert len(pc.policy_floors) >= 1
        assert pc.policy_floors[0].floor_score == 85

    def test_policy_floor_conditions(self):
        from domain.policy import PolicyConfig, PolicyFloor
        pc = PolicyConfig()
        floor = pc.policy_floors[0]
        assert "breaking_change" in floor.conditions
        assert "authoritative_payment_or_regulated_path" in floor.conditions

    def test_domain_errors(self):
        from domain.errors import AnalysisError, PolicyViolation, InsufficientEvidence
        assert issubclass(AnalysisError, Exception)
        assert issubclass(PolicyViolation, Exception)
        assert issubclass(InsufficientEvidence, Exception)
