"""Mock LLM provider for unit tests and deterministic simulation."""

from collections.abc import Callable
from typing import Any

from dentacall_agent.providers.base import (
    ChatMessage,
    LLMProvider,
    LLMResponse,
    ToolCall,
)


class MockProvider(LLMProvider):
    """Mock provider allowing queued responses or callback-driven responses for tests."""

    def __init__(
        self,
        canned_responses: list[LLMResponse] | None = None,
        responder_fn: Callable[[list[ChatMessage], list[dict[str, Any]] | None], LLMResponse]
        | None = None,
    ) -> None:
        self.queue: list[LLMResponse] = list(canned_responses or [])
        self.responder_fn = responder_fn
        self.calls_history: list[list[ChatMessage]] = []

    def enqueue(
        self,
        content: str | None = None,
        tool_calls: list[ToolCall] | None = None,
        prompt_tokens: int = 10,
        completion_tokens: int = 10,
    ) -> None:
        """Helper to append an LLMResponse to the mock queue."""
        self.queue.append(
            LLMResponse(
                content=content,
                tool_calls=tool_calls or [],
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model="mock-model",
            )
        )

    async def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Return next canned response from queue or execute callback function."""
        self.calls_history.append(list(messages))

        if self.responder_fn:
            return self.responder_fn(messages, tools)

        if self.queue:
            return self.queue.pop(0)

        # Default fallback if queue is empty
        return LLMResponse(
            content="Hello! How can I assist you at Grand Canal Dental Clinic today?",
            tool_calls=[],
            prompt_tokens=10,
            completion_tokens=15,
            model="mock-model",
        )
