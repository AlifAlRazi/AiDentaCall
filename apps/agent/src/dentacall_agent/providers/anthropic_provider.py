"""Anthropic (Claude) LLM provider implementation."""

import asyncio
import logging
from typing import Any

from anthropic import (
    APIError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
    RateLimitError,
)
from dentacall_agent.providers.base import (
    ChatMessage,
    LLMProvider,
    LLMResponse,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ToolCall,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude implementation using AsyncAnthropic client."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ProviderAuthError("Anthropic API key must not be empty.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = AsyncAnthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)

    async def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Call Anthropic Messages API with translated system prompt, messages, and tools."""
        system_prompt: str | None = None
        formatted_messages: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            if msg.role == "user":
                formatted_messages.append({"role": "user", "content": msg.content or ""})
            elif msg.role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function_name,
                            "input": tc.arguments,
                        }
                    )
                formatted_messages.append({"role": "assistant", "content": content_blocks})
            elif msg.role == "tool":
                formatted_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id or "",
                                "content": msg.content or "",
                            }
                        ],
                    }
                )

        anthropic_tools: list[dict[str, Any]] = []
        if tools:
            for t in tools:
                if "function" in t:
                    fn = t["function"]
                    anthropic_tools.append(
                        {
                            "name": fn["name"],
                            "description": fn.get("description", ""),
                            "input_schema": fn.get("parameters", {}),
                        }
                    )
                else:
                    anthropic_tools.append(t)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.messages.create(**kwargs)

                text_content: list[str] = []
                tool_calls: list[ToolCall] = []

                for block in response.content:
                    if block.type == "text":
                        text_content.append(block.text)
                    elif block.type == "tool_use":
                        tool_calls.append(
                            ToolCall(
                                id=block.id,
                                function_name=block.name,
                                arguments=block.input if isinstance(block.input, dict) else {},
                            )
                        )

                prompt_tokens = response.usage.input_tokens if response.usage else 0
                completion_tokens = response.usage.output_tokens if response.usage else 0

                return LLMResponse(
                    content=" ".join(text_content).strip() if text_content else None,
                    tool_calls=tool_calls,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    model=response.model or self.model,
                )

            except AuthenticationError as exc:
                raise ProviderAuthError(f"Anthropic Authentication failed: {exc}") from exc
            except RateLimitError as exc:
                if attempt == self.max_retries:
                    raise ProviderRateLimitError(f"Anthropic rate limit exceeded: {exc}") from exc
                wait_time = 1.5 * (2**attempt)
                logger.warning("Anthropic rate limit hit. Retrying in %.1fs...", wait_time)
                await asyncio.sleep(wait_time)
            except APITimeoutError as exc:
                if attempt == self.max_retries:
                    raise ProviderTimeoutError(f"Anthropic request timed out: {exc}") from exc
                wait_time = 1.0 * (2**attempt)
                logger.warning("Anthropic timeout. Retrying in %.1fs...", wait_time)
                await asyncio.sleep(wait_time)
            except APIError as exc:
                if attempt == self.max_retries:
                    raise ProviderError(f"Anthropic API error: {exc}") from exc
                wait_time = 1.0 * (2**attempt)
                logger.warning("Anthropic API error: %s. Retrying in %.1fs...", exc, wait_time)
                await asyncio.sleep(wait_time)

        raise ProviderError("Failed to get response from Anthropic after retries.")
