"""OpenTelemetry distributed tracing for voice call turns, STT, LLM, tools, and TTS."""

import json
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import Span, Tracer

from dentacall_core.settings import settings

# Global in-memory exporter for testing and observability introspection
in_memory_exporter = InMemorySpanExporter()

# Initialize provider
_resource = Resource.create({"service.name": settings.otel_service_name})
_provider = TracerProvider(resource=_resource)
_provider.add_span_processor(SimpleSpanProcessor(in_memory_exporter))
trace.set_tracer_provider(_provider)

tracer: Tracer = trace.get_tracer(settings.otel_service_name, "0.1.0")


def get_tracer() -> Tracer:
    """Return the configured OpenTelemetry tracer."""
    return tracer


def get_collected_spans() -> list[ReadableSpan]:
    """Return all spans collected in memory."""
    return list(in_memory_exporter.get_finished_spans())


def clear_collected_spans() -> None:
    """Clear in-memory span buffer for tests."""
    in_memory_exporter.clear()


@contextmanager
def trace_turn(
    call_id: str,
    turn_id: str,
    turn_number: int = 1,
    user_input: str = "",
) -> Generator[Span, None, None]:
    """Context manager tracing an entire conversational turn."""
    with tracer.start_as_current_span(
        name="call_turn",
        attributes={
            "dentacall.call_id": call_id,
            "dentacall.turn_id": turn_id,
            "dentacall.turn_number": turn_number,
            "dentacall.user_input": user_input[:200],  # truncated summary
        },
    ) as span:
        yield span


@contextmanager
def trace_stt(
    provider: str = "deepgram",
    request_id: str | None = None,
    duration_ms: float = 0.0,
) -> Generator[Span, None, None]:
    """Context manager or block tracing Speech-to-Text transcription."""
    with tracer.start_as_current_span(
        name="stt_transcription",
        attributes={
            "stt.provider": provider,
            "stt.duration_ms": duration_ms,
            "deepgram.request_id": request_id or "unknown",
        },
    ) as span:
        yield span


@contextmanager
def trace_llm(
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    ttft_ms: float = 0.0,
) -> Generator[Span, None, None]:
    """Context manager tracing LLM generation and TTFT."""
    with tracer.start_as_current_span(
        name="llm_generation",
        attributes={
            "llm.provider": "openai" if "gpt" in model.lower() else "anthropic",
            "llm.model": model,
            "llm.prompt_tokens": prompt_tokens,
            "llm.completion_tokens": completion_tokens,
            "llm.total_tokens": prompt_tokens + completion_tokens,
            "llm.ttft_ms": ttft_ms,
        },
    ) as span:
        yield span


@contextmanager
def trace_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """Context manager tracing a receptionist tool invocation."""
    args_json = json.dumps(arguments or {})[:300]
    with tracer.start_as_current_span(
        name=f"tool_{tool_name}",
        attributes={
            "tool.name": tool_name,
            "tool.arguments": args_json,
        },
    ) as span:
        yield span


@contextmanager
def trace_tts(
    provider: str = "elevenlabs",
    characters_sent: int = 0,
    ttfb_ms: float = 0.0,
) -> Generator[Span, None, None]:
    """Context manager tracing Text-to-Speech synthesis and TTFB."""
    with tracer.start_as_current_span(
        name="tts_synthesis",
        attributes={
            "tts.provider": provider,
            "tts.characters_sent": characters_sent,
            "tts.ttfb_ms": ttfb_ms,
        },
    ) as span:
        yield span
