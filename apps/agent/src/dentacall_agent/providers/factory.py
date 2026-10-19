"""Factory for instantiating LLM providers based on application configuration."""

import logging
from typing import Literal

from dentacall_agent.providers.anthropic_provider import AnthropicProvider
from dentacall_agent.providers.base import LLMProvider, ProviderAuthError
from dentacall_agent.providers.openai_provider import OpenAIProvider
from dentacall_core.settings import settings

logger = logging.getLogger(__name__)

ProviderType = Literal["openai", "anthropic", "mock"]


def get_llm_provider(
    provider_name: str | None = None,
    model: str | None = None,
) -> LLMProvider:
    """Instantiate and return the configured LLM provider."""
    selected = (provider_name or settings.default_llm_provider).lower().strip()

    # Smart fallback if selected provider lacks an API key but the other has one
    if selected == "anthropic" and not settings.anthropic_api_key and settings.openai_api_key:
        logger.info("Anthropic API key not configured, falling back to OpenAI with OPENAI_API_KEY.")
        selected = "openai"
    elif selected == "openai" and not settings.openai_api_key and settings.anthropic_api_key:
        logger.info(
            "OpenAI API key not configured, falling back to Anthropic with ANTHROPIC_API_KEY."
        )
        selected = "anthropic"

    if selected == "openai":
        api_key = settings.openai_api_key
        if not api_key:
            raise ProviderAuthError(
                "OPENAI_API_KEY is missing. Please set it in your environment or .env file."
            )
        return OpenAIProvider(
            api_key=api_key,
            model=model or settings.openai_model,
        )

    if selected == "anthropic":
        api_key = settings.anthropic_api_key
        if not api_key:
            raise ProviderAuthError(
                "ANTHROPIC_API_KEY is missing. Please set it in your environment or .env file."
            )
        return AnthropicProvider(
            api_key=api_key,
            model=model or settings.anthropic_model,
        )

    raise ValueError(
        f"Unknown or unsupported LLM provider '{selected}'. Supported: 'openai', 'anthropic'."
    )
