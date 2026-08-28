from __future__ import annotations

import os
from typing import Any

from llm_gateway.gemini_provider import GeminiProvider
from llm_gateway.mock_provider import MockLLMProvider
from llm_gateway.provider import LLMProvider, LLMRequest, LLMResponse


class LLMGateway:
    """Provider routing with tracing, token budget enforcement, and Gemini 3.5 support."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        token_budget: int = 80000,
    ) -> None:
        if provider is not None:
            self._provider = provider
        elif os.environ.get("GEMINI_API_KEY"):
            self._provider = GeminiProvider()
        else:
            self._provider = MockLLMProvider()

        self._token_budget = token_budget
        self._tokens_used = 0

    @property
    def provider_name(self) -> str:
        return getattr(self._provider, "name", "unknown")

    @property
    def tokens_remaining(self) -> int:
        return self._token_budget - self._tokens_used

    async def complete(self, request: LLMRequest) -> LLMResponse:
        if self._tokens_used >= self._token_budget:
            raise RuntimeError("Token budget exhausted")

        response = await self._provider.complete(request)

        total = response.token_usage.get("total_tokens", 0)
        self._tokens_used += total

        return response

    async def complete_with_schema(
        self,
        request: LLMRequest,
    ) -> dict[str, Any]:
        response = await self.complete(request)
        if response.parsed is not None:
            return response.parsed
        import json
        return json.loads(response.content)
