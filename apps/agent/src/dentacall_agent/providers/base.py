"""Base definitions and abstract interface for LLM providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ProviderError(Exception):
    """Base exception for LLM provider errors."""

    pass


class ProviderAuthError(ProviderError):
    """Raised when an API key is missing or invalid."""

    pass


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limits are exceeded."""

    pass


class ProviderTimeoutError(ProviderError):
    """Raised when provider request times out."""

    pass


@dataclass
class ToolCall:
    """Standardized tool invocation emitted by an LLM."""

    id: str
    function_name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """Standardized chat message structure for conversational history."""

    role: str  # "system", "user", "assistant", or "tool"
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class LLMResponse:
    """Standardized response output from any LLM provider."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """Abstract interface for LLM model providers (OpenAI, Anthropic, Mock)."""

    @abstractmethod
    async def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate a response from the underlying language model."""
        pass
