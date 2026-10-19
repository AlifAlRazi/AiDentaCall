"""OpenAI LLM provider implementation."""

import asyncio
import json
import logging
from typing import Any

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
from openai import APIError, APITimeoutError, AsyncOpenAI, AuthenticationError, RateLimitError

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI implementation using the AsyncOpenAI client."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        if not api_key:
            raise ProviderAuthError("OpenAI API key must not be empty.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

    async def generate(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Call OpenAI chat completions API with converted messages and tools."""
        formatted_messages: list[dict[str, Any]] = []
        for msg in messages:
            msg_dict: dict[str, Any] = {"role": msg.role}
            if msg.content is not None:
                msg_dict["content"] = msg.content
            if msg.role == "assistant" and msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function_name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if msg.role == "tool":
                msg_dict["tool_call_id"] = msg.tool_call_id
                if msg.name:
                    msg_dict["name"] = msg.name

            formatted_messages.append(msg_dict)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                message = choice.message

                tool_calls: list[ToolCall] = []
                if message.tool_calls:
                    for tc in message.tool_calls:
                        try:
                            args = (
                                json.loads(tc.function.arguments) if tc.function.arguments else {}
                            )
                        except json.JSONDecodeError:
                            args = {}
                        tool_calls.append(
                            ToolCall(
                                id=tc.id,
                                function_name=tc.function.name,
                                arguments=args,
                            )
                        )

                prompt_tokens = response.usage.prompt_tokens if response.usage else 0
                completion_tokens = response.usage.completion_tokens if response.usage else 0

                return LLMResponse(
                    content=message.content,
                    tool_calls=tool_calls,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    model=response.model or self.model,
                )

            except AuthenticationError as exc:
                raise ProviderAuthError(f"OpenAI Authentication failed: {exc}") from exc
            except RateLimitError as exc:
                if attempt == self.max_retries:
                    raise ProviderRateLimitError(f"OpenAI rate limit exceeded: {exc}") from exc
                wait_time = 1.5 * (2**attempt)
                logger.warning("OpenAI rate limit hit. Retrying in %.1fs...", wait_time)
                await asyncio.sleep(wait_time)
            except APITimeoutError as exc:
                if attempt == self.max_retries:
                    raise ProviderTimeoutError(f"OpenAI request timed out: {exc}") from exc
                wait_time = 1.0 * (2**attempt)
                logger.warning("OpenAI timeout. Retrying in %.1fs...", wait_time)
                await asyncio.sleep(wait_time)
            except APIError as exc:
                if attempt == self.max_retries:
                    raise ProviderError(f"OpenAI API error: {exc}") from exc
                wait_time = 1.0 * (2**attempt)
                logger.warning("OpenAI API error: %s. Retrying in %.1fs...", exc, wait_time)
                await asyncio.sleep(wait_time)

        raise ProviderError("Failed to get response from OpenAI after retries.")
