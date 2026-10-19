"""Unit tests for LLM provider implementations and provider factory."""

import pytest
from dentacall_agent.providers.anthropic_provider import AnthropicProvider
from dentacall_agent.providers.base import (
    ChatMessage,
    ProviderAuthError,
    ToolCall,
)
from dentacall_agent.providers.factory import get_llm_provider
from dentacall_agent.providers.mock_provider import MockProvider
from dentacall_agent.providers.openai_provider import OpenAIProvider
from dentacall_core.settings import settings


@pytest.mark.asyncio
async def test_mock_provider_queue_and_history() -> None:
    """Test MockProvider returns queued responses and records conversation history."""
    provider = MockProvider()
    provider.enqueue(content="First response")
    provider.enqueue(
        content="Second response with tool",
        tool_calls=[ToolCall(id="tc-1", function_name="get_clinic_info", arguments={})],
    )

    messages = [ChatMessage(role="user", content="Hello clinic!")]
    resp1 = await provider.generate(messages)
    assert resp1.content == "First response"
    assert not resp1.has_tool_calls

    resp2 = await provider.generate(messages)
    assert resp2.content == "Second response with tool"
    assert resp2.has_tool_calls
    assert resp2.tool_calls[0].function_name == "get_clinic_info"

    # Queue exhausted, returns default greeting fallback
    resp3 = await provider.generate(messages)
    assert "Grand Canal Dental Clinic" in (resp3.content or "")
    assert len(provider.calls_history) == 3


def test_openai_provider_empty_key_raises_auth_error() -> None:
    """Empty OpenAI API key immediately raises ProviderAuthError."""
    with pytest.raises(ProviderAuthError, match="OpenAI API key must not be empty"):
        OpenAIProvider(api_key="")


def test_anthropic_provider_empty_key_raises_auth_error() -> None:
    """Empty Anthropic API key immediately raises ProviderAuthError."""
    with pytest.raises(ProviderAuthError, match="Anthropic API key must not be empty"):
        AnthropicProvider(api_key="")


def test_get_llm_provider_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider factory correctly instantiates configured providers."""
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-openai-key")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-key")

    openai_prov = get_llm_provider("openai")
    assert isinstance(openai_prov, OpenAIProvider)
    assert openai_prov.api_key == "sk-test-openai-key"

    anthropic_prov = get_llm_provider("anthropic")
    assert isinstance(anthropic_prov, AnthropicProvider)
    assert anthropic_prov.api_key == "sk-ant-test-key"

    with pytest.raises(ValueError, match="Unknown or unsupported LLM provider"):
        get_llm_provider("unsupported_provider")
