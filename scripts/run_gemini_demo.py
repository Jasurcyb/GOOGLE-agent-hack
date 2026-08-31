#!/usr/bin/env python3
"""
Regression Hunter AI — Standalone Live Demo Script
Run complete end-to-end pipeline and print formatted Markdown report & JSON assessment.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env (GEMINI_API_KEY etc.) if present — keeps the key out of shell history
_ENV_FILE = Path(__file__).parent.parent / ".env"
if _ENV_FILE.exists():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# Add workspace apps & packages to path
ROOT_DIR = Path(__file__).parent.parent
for folder in ["packages", "apps"]:
    target_dir = ROOT_DIR / folder
    if target_dir.exists():
        for child in target_dir.iterdir():
            if child.is_dir() and str(child) not in sys.path:
                sys.path.insert(0, str(child))

from pr_listener.models import make_run_key
from repo_worker.worker import SourceSnapshot
from diff_analyzer.analyzer import parse_git_diff, classify_delta, FileChangeType
from code_intelligence.python_analyzer.analyzer import PythonAnalyzer, SourceFile
from context_orchestrator.builder import ContextBuilder
from datahub_adapter.stub_context import StubDataHubContextPort
from datahub_adapter.stub_graph import StubDataHubGraphPort
from risk_engine.scorer import RiskFeatures, score
from domain.policy import PolicyConfig
from reasoning_agent.agent import ReasoningAgent
from llm_gateway import LLMGateway, GeminiProvider, MockLLMProvider
from observability.memory_bank import CloudMemoryBank
from test_agent.planner import TestPlanner
from test_agent.sandbox import SandboxValidator
from publisher.datahub_publisher import DataHubPublisher


SAMPLE_GIT_DIFF = """diff --git a/payment/service.py b/payment/service.py
index 0000000..e69de29 100644
--- a/payment/service.py
+++ b/payment/service.py
@@ -1,12 +1,14 @@
 import os
 import json
 
+@datahub_urn("urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.payment_events,PROD)")
 def process_payment(account_id: str, amount: float) -> dict:
     \"\"\"Process customer payment transaction.\"\"\"
     if amount <= 0:
         raise ValueError("Invalid amount")
-    return {"status": "success", "tx_id": "tx_12345"}
+    return {"status": "success", "transaction_id": "tx_12345"}
 
 def refund_payment(tx_id: str) -> bool:
     \"\"\"Refund an existing transaction.\"\"\"
     return True
"""

CLEAN_PYTHON_SOURCE = """import os
import json

@datahub_urn("urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.payment_events,PROD)")
def process_payment(account_id: str, amount: float) -> dict:
    \"\"\"Process customer payment transaction.\"\"\"
    if amount <= 0:
        raise ValueError("Invalid amount")
    return {"status": "success", "transaction_id": "tx_12345"}

def refund_payment(tx_id: str) -> bool:
    \"\"\"Refund an existing transaction.\"\"\"
    return True
"""

TEST_CODE_SNIPPET = """def process_payment(account_id: str, amount: float) -> dict:
    if amount <= 0:
        raise ValueError("Invalid amount")
    return {"status": "success", "tx_id": "tx_12345"}

def test_process_payment():
    res = process_payment("acc_1", 100.0)
    assert res["status"] == "success"
"""


async def main():
    print("=" * 70)
    print("=== ALL THINGS AGENTIC HACKATHON: REGRESSION HUNTER AI (Google Gemini 3.5 + Google Cloud) ===")
    print("=" * 70)

    # 1. PR Listener
    repo = "acme/payment-service"
    pr_number = 42
    head_sha = "a1b2c3d4e5f678901234567890abcdef12345678"
    run_key = make_run_key(repo, pr_number, head_sha)
    print(f"1. [PR Listener] Run Key: {run_key}")

    # 2. Repo Worker
    snapshot = SourceSnapshot(
        snapshot_uri="s3://regression-hunter/snapshots/run-123/a1b2c3d4.tar.gz",
        sha256="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
        file_count=1,
        size_bytes=1024,
        diff_text=SAMPLE_GIT_DIFF,
        changed_sources=[{"path": "payment/service.py", "content": CLEAN_PYTHON_SOURCE}],
    )
    print(f"2. [Repo Worker] Snapshot created. Size: {snapshot.size_bytes} bytes")

    # 3. Diff Analyzer
    deltas = parse_git_diff(SAMPLE_GIT_DIFF)
    classified = classify_delta(deltas[0])
    print(f"3. [Diff Analyzer] File: {classified['path']} | Language: {classified['language']} | +{deltas[0].added_lines}/-{deltas[0].deleted_lines} lines")

    # 4. Code Intelligence
    analyzer = PythonAnalyzer()
    parsed = list(analyzer.parse([SourceFile(path="payment/service.py", language="python", content=CLEAN_PYTHON_SOURCE)]))[0]
    fqns = [s.fully_qualified_name for s in parsed.symbols]
    print(f"4. [Code Intelligence] Discovered AST Symbols: {fqns}")

    # 5. Context Orchestrator & DataHub
    stub_datahub = StubDataHubContextPort()
    builder = ContextBuilder(datahub_port=stub_datahub)
    symbols_list = [{"id": s.id, "fqn": s.fully_qualified_name, "symbol_kind": s.symbol_kind, "file_path": s.file_path} for s in parsed.symbols]

    semantic_deltas = [{
        "kind": "output_field_renamed",
        "symbol": "payment.service.process_payment",
        "from": "tx_id",
        "to": "transaction_id",
        "breaking": True,
    }]

    evidence_bundle = await builder.build(
        run_id="run-demo-001",
        repo=repo,
        head_sha=head_sha,
        change_summary={
            "symbols": symbols_list,
            "file_deltas": [classified],
            "semantic_deltas": semantic_deltas,
            "entry_points": ["payment.service.process_payment"],
        },
        code_impact={"call_paths": [], "unknown_resolution_count": 0},
        symbols=symbols_list,
        imports=parsed.imports,
        source_content={"payment/service.py": CLEAN_PYTHON_SOURCE},
    )
    blast_assets = len(evidence_bundle.datahub_impact.assets)
    print(f"5. [Context Orchestrator] EvidenceBundle Built (Version: {evidence_bundle.bundle_version} | Downstream Blast Radius: {blast_assets} assets)")

    # 6. Risk Engine
    bundle_dict = evidence_bundle.model_dump(mode="json")
    features = RiskFeatures.from_bundle(bundle_dict)
    policy = PolicyConfig()
    risk_assessment = score("run-demo-001", features, policy)
    print(f"6. [Risk Engine] Risk Score: {risk_assessment.risk_score}/100 | Level: {risk_assessment.risk_level.upper()}")

    # 7. Reasoning Agent — live Google Gemini 3.5 when GEMINI_API_KEY is set, deterministic mock otherwise
    if os.environ.get("GEMINI_API_KEY"):
        gateway = LLMGateway(provider=GeminiProvider())
        provider_label = "Gemini 3.5 live (gemini-3.5-flash)"
    else:
        gateway = LLMGateway(provider=MockLLMProvider())
        provider_label = "Mock provider (offline demo)"
    reasoner = ReasoningAgent(gateway=gateway)
    reasoning_result = await reasoner.reason(bundle_dict)
    meta = reasoner.last_meta
    print(f"7. [Reasoning Agent | {provider_label}]")
    print(f"   LLM call: provider={reasoner.last_meta.get('provider', 'mock')} | "
          f"model={reasoner.last_meta.get('model', 'mock-gpt')} | "
          f"latency={reasoner.last_meta.get('latency_ms', 0)}ms | "
          f"tokens={reasoner.last_meta.get('tokens', 0)}")
    hypotheses = reasoning_result.get("hypotheses", [])
    print(f"   Generated Hypotheses: {len(hypotheses)}")
    for h in hypotheses[:3]:
        mechanism = h.get("mechanism", h.get("title", "unknown"))
        conf = h.get("confidence", 0)
        conf_part = f"conf={conf} | " if conf else ""
        print(f"   - [{h.get('verification_status', '?')}] {mechanism} "
              f"| evidence: {len(h.get('evidence_refs', []))} refs")

    # 8. Test Agent Sandbox
    sandbox = SandboxValidator()
    val_res = sandbox.validate(TEST_CODE_SNIPPET, framework="pytest", language="python")
    print(f"8. [Test Agent Sandbox] Sandbox Validation Result: Valid={val_res.valid} | Test Passed={val_res.test_passed}")

    # 9. Google Cloud Memory Bank (Firestore if configured, local fallback otherwise)
    memory_bank = CloudMemoryBank(storage_file="memory_bank_store.json")
    memory_uri = await memory_bank.save_session_memory(
        session_id="run-demo-001",
        agent_type="reasoning_agent",
        context={
            "repo": repo,
            "pr_number": pr_number,
            "risk_score": risk_assessment.risk_score,
            "risk_level": risk_assessment.risk_level,
            "hypotheses_count": len(hypotheses),
        },
        reasoning_trace=[{"step": "grounded_evidence", "bundle_version": evidence_bundle.bundle_version}],
    )
    print(f"9. [Google Cloud Memory Bank] Audit Telemetry Persisted -> {memory_uri}")

    # 10. Publisher Write-Back
    stub_graph = StubDataHubGraphPort()
    publisher = DataHubPublisher(graph_port=stub_graph)
    deliveries = await publisher.publish(
        run_id="run-demo-001",
        repo=repo,
        pr_number=pr_number,
        head_sha=head_sha,
        assessment=reasoning_result,
    )
    print("10. [Publisher] DataHub & GitHub Deliveries:")
    for d in deliveries:
        print(f"   - Target: {d['target']} | Status: {d['status']}")

    print("\n" + "=" * 70)
    print("=== DEMO EXECUTION COMPLETE -- ALL SYSTEMS OPERATIONAL ===")
    print("=" * 70)



if __name__ == "__main__":
    asyncio.run(main())
