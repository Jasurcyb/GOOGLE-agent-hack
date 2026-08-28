from __future__ import annotations

import asyncio
import json
import pytest
from typing import Any

from pr_listener.models import make_run_key
from repo_worker.worker import RepoWorker, SourceSnapshot
from diff_analyzer.analyzer import parse_git_diff, classify_delta, FileChangeType
from code_intelligence.python_analyzer.analyzer import PythonAnalyzer, SourceFile
from context_orchestrator.builder import ContextBuilder
from datahub_adapter.stub_context import StubDataHubContextPort
from datahub_adapter.stub_graph import StubDataHubGraphPort
from risk_engine.scorer import RiskFeatures, score
from domain.policy import PolicyConfig
from reasoning_agent.agent import ReasoningAgent
from test_agent.planner import TestPlanner
from test_agent.sandbox import SandboxValidator
from publisher.datahub_publisher import DataHubPublisher


SAMPLE_GIT_DIFF = """diff --git a/payment/service.py b/payment/service.py
new file mode 100644
index 0000000..e69de29
--- /dev/null
+++ b/payment/service.py
@@ -0,0 +1,15 @@
+import os
+import json
+
+def process_payment(account_id: str, amount: float) -> dict:
+    \"\"\"Process customer payment transaction.\"\"\"
+    if amount <= 0:
+        raise ValueError("Invalid amount")
+    return {"status": "success", "tx_id": "tx_12345"}
+
+def refund_payment(tx_id: str) -> bool:
+    \"\"\"Refund an existing transaction.\"\"\"
+    return True
+"""

SAMPLE_PYTHON_CODE = """def process_payment(account_id: str, amount: float) -> dict:
    if amount <= 0:
        raise ValueError("Invalid amount")
    return {"status": "success", "tx_id": "tx_12345"}

def test_process_payment():
    res = process_payment("acc_1", 100.0)
    assert res["status"] == "success"
"""



CLEAN_PYTHON_SOURCE = """import os
import json

def process_payment(account_id: str, amount: float) -> dict:
    \"\"\"Process customer payment transaction.\"\"\"
    if amount <= 0:
        raise ValueError("Invalid amount")
    return {"status": "success", "tx_id": "tx_12345"}

def refund_payment(tx_id: str) -> bool:
    \"\"\"Refund an existing transaction.\"\"\"
    return True
"""


@pytest.mark.asyncio
async def test_end_to_end_regression_hunter_pipeline():
    """Verify full end-to-end happy path: PR -> Diff -> Code Graph -> DataHub -> Risk -> Reasoning -> Test Sandbox -> Publisher."""
    
    # 1. PR Listener step: generate run key
    repo_name = "acme/payment-service"
    pr_number = 42
    head_sha = "a1b2c3d4e5f678901234567890abcdef12345678"
    base_sha = "0000000000000000000000000000000000000000"
    
    run_key = make_run_key(repo_name, pr_number, head_sha)
    assert run_key == f"{repo_name}:{pr_number}:{head_sha}:v1"

    # 2. Repo Worker step: snapshot & diff
    source_snapshot = SourceSnapshot(
        snapshot_uri="s3://regression-hunter/snapshots/run-123/a1b2c3d4.tar.gz",
        sha256="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        file_count=5,
        size_bytes=10240,
        diff_text=SAMPLE_GIT_DIFF,
        changed_sources=[{"path": "payment/service.py", "content": CLEAN_PYTHON_SOURCE}],
    )
    assert source_snapshot.file_count == 5

    # 3. Diff Analyzer step: parse git diff into file deltas
    deltas = parse_git_diff(SAMPLE_GIT_DIFF)
    assert len(deltas) == 1
    delta = deltas[0]
    assert delta.path == "payment/service.py"
    assert delta.change_type == FileChangeType.ADDED
    assert delta.added_lines == 13

    classified = classify_delta(delta)
    assert classified["path"] == "payment/service.py"
    assert classified["language"] == "python"

    # 4. Code Intelligence step: parse AST and extract symbols & entrypoints
    analyzer = PythonAnalyzer()
    parsed_files = list(analyzer.parse([SourceFile(path="payment/service.py", language="python", content=CLEAN_PYTHON_SOURCE)]))
    assert len(parsed_files) == 1
    parsed_file = parsed_files[0]
    fqns = [s.fully_qualified_name for s in parsed_file.symbols]
    assert "payment.service.process_payment" in fqns
    assert "payment.service.refund_payment" in fqns

    # 5. Context Orchestrator step: retrieve DataHub impact & build EvidenceBundle
    stub_datahub = StubDataHubContextPort()
    builder = ContextBuilder(datahub_port=stub_datahub)

    symbols_list = [{"id": s.id, "fqn": s.fully_qualified_name, "symbol_kind": s.symbol_kind, "file_path": s.file_path} for s in parsed_file.symbols]

    evidence_bundle = await builder.build(
        run_id="run-test-e2e",
        repo=repo_name,
        head_sha=head_sha,
        change_summary={"symbols": symbols_list, "file_deltas": [classified]},
        code_impact={"call_paths": [], "unknown_resolution_count": 0},
        symbols=symbols_list,
        imports=parsed_file.imports,
        source_content={"payment/service.py": CLEAN_PYTHON_SOURCE},
    )

    assert evidence_bundle.bundle_version == "1.0"
    assert evidence_bundle.run["repo"] == repo_name

    # 6. Risk Engine step: score features
    bundle_dict = evidence_bundle.model_dump(mode="json")
    features = RiskFeatures.from_bundle(bundle_dict)
    policy = PolicyConfig()
    assessment = score("run-test-e2e", features, policy)
    assert assessment.risk_score >= 0
    assert assessment.risk_level in ("low", "medium", "high", "critical")

    # 7. Reasoning Agent step: reason over evidence & verify hypotheses
    reasoner = ReasoningAgent()
    reasoning_result = await reasoner.reason(bundle_dict)
    assert "hypotheses" in reasoning_result

    # 8. Test Agent step: plan & validate tests in sandbox
    planner = TestPlanner()
    hypotheses = reasoning_result.get("hypotheses", [{"title": "Payment edge case", "evidence_refs": ["ev_001"]}])
    test_plans = planner.plan_tests(hypotheses, affected_assets=[])
    assert len(test_plans) > 0

    sandbox = SandboxValidator()
    val_res = sandbox.validate(SAMPLE_PYTHON_CODE, framework="pytest", language="python")
    assert val_res.valid is True
    assert val_res.parse_passed is True

    # 9. Publisher step: DataHub write-back
    stub_graph = StubDataHubGraphPort()
    publisher = DataHubPublisher(graph_port=stub_graph)

    assessment_payload = {
        "risk_score": assessment.risk_score,
        "risk_level": assessment.risk_level.value,
        "regression_probability": assessment.regression_probability,
        "confidence": assessment.confidence,
        "affected_assets": [{"urn": "urn:li:dataset:(urn:li:dataPlatform:postgres,payments,PROD)", "binding_trust": "AUTHORITATIVE"}],
        "recommended_tests": [{"kind": "unit_test", "title": "Test Payment Processing", "target_path": "payment/test_service.py"}],
        "review_summary": "E2E pipeline integration test summary",
    }

    deliveries = await publisher.publish(
        run_id="run-test-e2e",
        repo=repo_name,
        pr_number=pr_number,
        head_sha=head_sha,
        assessment=assessment_payload,
    )

    assert len(deliveries) >= 4
    targets = [d["target"] for d in deliveries]
    assert "datahub_report" in targets
    assert "datahub_assessment" in targets
    assert len(stub_graph.documents) > 0
    assert len(stub_graph.custom_entities) > 0
