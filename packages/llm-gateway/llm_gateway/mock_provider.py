from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from llm_gateway.provider import LLMProvider, LLMRequest, LLMResponse

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class MockLLMProvider:
    """Deterministic LLM provider that returns fixture-based responses."""

    name = "mock"

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._fixtures_dir = fixtures_dir or FIXTURES_DIR

    def _fixture_path(self, purpose: str) -> Path:
        return self._fixtures_dir / f"{purpose}.json"

    async def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()

        fixture_path = self._fixture_path(request.purpose)
        if fixture_path.exists():
            data = json.loads(fixture_path.read_text(encoding="utf-8"))
        else:
            data = self._generate_default(request)

        latency = int((time.monotonic() - start) * 1000)

        input_hash = hashlib.sha256(
            request.user_content.encode("utf-8")
        ).hexdigest()[:16]

        return LLMResponse(
            content=json.dumps(data, indent=2),
            parsed=data,
            token_usage=data.get("_token_usage", {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300,
            }),
            latency_ms=latency,
            provider="mock",
            model="mock-gpt",
            raw=data,
        )

    def _generate_default(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "risk_score": 0,
            "risk_level": "low",
            "regression_probability": 0.0,
            "impact_severity": 0.0,
            "confidence": 50,
            "requires_human_review": False,
            "affected_assets": [],
            "recommended_tests": [],
            "review_summary": "Mock response — no fixture found for this purpose.",
            "business_impact": "none",
            "root_cause": "none",
            "_token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 200,
                "total_tokens": 300,
            },
        }
