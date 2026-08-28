from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMRequest:
    purpose: str
    system_prompt: str
    developer_prompt: str
    user_content: str
    output_schema: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass
class LLMResponse:
    content: str
    parsed: dict[str, Any] | None = None
    token_usage: dict[str, int] = field(default_factory=dict)
    latency_ms: int = 0
    provider: str = ""
    model: str = ""
    raw: Any = None


class LLMProvider(Protocol):
    """Provider-agnostic LLM interface."""

    name: str

    async def complete(self, request: LLMRequest) -> LLMResponse: ...
