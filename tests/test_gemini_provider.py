import pytest
from llm_gateway.gemini_provider import GeminiProvider
from llm_gateway.provider import LLMRequest
from llm_gateway.gateway import LLMGateway


def test_gemini_provider_init():
    provider = GeminiProvider(api_key="test-key", model="gemini-2.5-flash")
    assert provider.name == "gemini"
    assert provider._model == "gemini-2.5-flash"


def test_llm_gateway_auto_gemini_detection(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy_key")
    gateway = LLMGateway()
    assert gateway.provider_name == "gemini"


def test_llm_gateway_fallback_mock(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    gateway = LLMGateway()
    assert gateway.provider_name == "mock"
