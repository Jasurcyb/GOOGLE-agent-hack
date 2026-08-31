#!/usr/bin/env python3
"""
Regression Hunter AI — Google Cloud Firestore Memory Bank demo.

Persists agent session memories and reasoning traces to Google Cloud Firestore
(Firebase Spark free tier — works WITHOUT a billing account), then demonstrates
cross-session recall of past regressions. Point your camera at the Firestore
console during the demo video to prove deployment on Google Cloud.

Setup (5 minutes, no credit card):
  1. Create a Firebase project at https://console.firebase.google.com
     (or reuse a Google Cloud project) — Spark plan is enough.
  2. Build → Firestore Database → Create database → Native mode → region.
  3. Auth without a key file (recommended):
       gcloud auth application-default login
     Or with a service account key:
       - Firebase console -> Project settings -> Service accounts -> Generate new private key
       - set GOOGLE_APPLICATION_CREDENTIALS to the downloaded JSON
  4. Set the project id:
       PowerShell:  $env:GOOGLE_CLOUD_PROJECT="your-firebase-project-id"
       Linux/macOS: export GOOGLE_CLOUD_PROJECT="your-firebase-project-id"
     (No key file is needed when GOOGLE_CLOUD_PROJECT + gcloud ADC are used.)
  5. python scripts/run_firestore_demo.py
"""

import asyncio
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
for folder in ["packages", "apps"]:
    target_dir = ROOT_DIR / folder
    if target_dir.exists():
        for child in target_dir.iterdir():
            if child.is_dir() and str(child) not in sys.path:
                sys.path.insert(0, str(child))

from observability.memory_bank import CloudMemoryBank


PAST_SESSIONS = [
    {
        "session_id": "run-2026-08-20-payment-api",
        "agent_type": "reasoning_agent",
        "context": {
            "repo": "acme/payment-service",
            "pr_number": 17,
            "risk_score": 85,
            "risk_level": "high",
            "root_cause": "renamed column charged_amount breaks revenue dashboard fact_payments",
            "assets": ["snowflake.finance.revenue_daily", "looker.exec_revenue_dashboard"],
        },
        "reasoning_trace": [
            {"step": "grounded_evidence", "evidence_refs": ["datahub:lineage:revenue_daily"]},
            {"step": "hypothesis_verified", "confidence": 0.92},
        ],
    },
    {
        "session_id": "run-2026-08-24-kafka-ingest",
        "agent_type": "test_agent",
        "context": {
            "repo": "acme/stream-ingest",
            "pr_number": 23,
            "risk_score": 72,
            "risk_level": "high",
            "root_cause": "enum change in event schema silently drops Kafka records",
            "assets": ["kafka.payments.events", "bigquery.payments_raw"],
        },
        "reasoning_trace": [
            {"step": "sandbox_test_generated", "framework": "pytest", "valid": True},
        ],
    },
]


async def main() -> None:
    print("=" * 70)
    print("=== REGRESSION HUNTER AI: GOOGLE CLOUD FIRESTORE MEMORY BANK DEMO ===")
    print("=== Free tier: Firebase Spark plan (no billing account required) ===")
    print("=" * 70)

    bank = CloudMemoryBank(storage_file="memory_bank_store.json")

    for past in PAST_SESSIONS:
        uri = await bank.save_session_memory(
            session_id=past["session_id"],
            agent_type=past["agent_type"],
            context=past["context"],
            reasoning_trace=past["reasoning_trace"],
        )
        print(f"[Memory Bank] Persisted session -> {uri}")

    print("\n[Memory Bank] Cross-session recall: 'which past regressions touched payments?'")
    matches = await bank.search_relevant_past_regressions(["payment", "revenue", "kafka"], limit=3)
    for m in matches:
        ctx = m.get("context", {})
        print(
            f"   - {m.get('session_id')} | risk={ctx.get('risk_score')}/100"
            f" | cause: {ctx.get('root_cause', 'n/a')}"
        )

    print("\nIf records show under firestore:// URIs above, open:")
    print("  Firebase Console -> Firestore Database -> collection 'agent_memory_bank'")
    print("  (or Google Cloud Console -> Firestore) and show them in your demo video.")
    print("=" * 70)
    print("=== MEMORY BANK DEMO COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
