"""End-to-end acceptance tests for Stage 7 Observability and Cost Tracking."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from dentacall_core.models import CallLog
from dentacall_core.redaction import redact_pii
from dentacall_core.telephony import TelephonyManager
from dentacall_core.tracing import (
    clear_collected_spans,
    get_collected_spans,
    trace_llm,
    trace_stt,
    trace_tool,
    trace_tts,
    trace_turn,
)


@pytest.mark.asyncio
async def test_acceptance_one_call_produces_full_trace_and_cost() -> None:
    """Stage 7 Acceptance Check 1: One call produces a full trace and an itemized cost number."""
    clear_collected_spans()

    call_id = "test-call-acceptance-001"
    telephony = TelephonyManager()
    telephony.start_call_session(
        call_id=call_id,
        call_sid="CAacceptance001",
        caller_phone="+353871234567",
    )

    # 1. Conversational Turn produces OpenTelemetry spans across STT, LLM, Tool, and TTS
    with trace_turn(
        call_id=call_id,
        turn_id="turn-1",
        turn_number=1,
        user_input="I need an emergency appointment for toothache.",
    ):
        with trace_stt(provider="deepgram", request_id="dg-req-acc", duration_ms=195.0):
            pass
        with trace_llm(
            model="gpt-4o-mini", prompt_tokens=620, completion_tokens=110, ttft_ms=290.0
        ):
            pass
        with trace_tool(tool_name="check_availability", arguments={"service_code": "EMERGENCY"}):
            pass
        with trace_tts(provider="elevenlabs", characters_sent=140, ttfb_ms=160.0):
            pass

    spans = get_collected_spans()
    span_names = {s.name for s in spans}

    assert "call_turn" in span_names
    assert "stt_transcription" in span_names
    assert "llm_generation" in span_names
    assert "tool_check_availability" in span_names
    assert "tts_synthesis" in span_names

    # 2. Call completes and produces itemized cost calculation
    raw_transcript = [
        {"role": "user", "content": "My phone is 087 123 4567 and email is john@example.com."},
        {"role": "assistant", "content": "I booked you for tomorrow at 10:00 AM."},
    ]

    mock_db = AsyncMock()
    mock_clinic = MagicMock()
    mock_clinic.scalar_one_or_none.return_value = "00000000-0000-0000-0000-000000000001"
    mock_db.execute.return_value = mock_clinic

    result = await telephony.handle_call_disconnect(
        call_id=call_id,
        db_session=mock_db,
        reason="COMPLETED",
        transcript=raw_transcript,
        tool_calls=[{"name": "book_appointment", "service": "EMERGENCY"}],
        latency_metrics={"mean_ttfa_ms": 680.0},
        prompt_tokens=620,
        completion_tokens=110,
        characters_synthesized=140,
        outcome="BOOKED",
    )

    # Verify itemized cost number
    assert "estimated_cost_usd" in result
    assert result["estimated_cost_usd"] > 0.0
    assert "cost_breakdown" in result
    breakdown = result["cost_breakdown"]
    assert breakdown["deepgram_cost_usd"] > 0.0
    assert breakdown["openai_cost_usd"] > 0.0
    assert breakdown["elevenlabs_cost_usd"] > 0.0
    assert breakdown["twilio_cost_usd"] > 0.0
    assert breakdown["livekit_cost_usd"] > 0.0

    # Verify CallLog added with redacted transcript and cost
    mock_db.add.assert_called_once()
    saved_log = mock_db.add.call_args[0][0]
    assert isinstance(saved_log, CallLog)
    assert saved_log.transcript_redacted is not None
    assert "[REDACTED_PHONE]" in saved_log.transcript_redacted
    assert "[REDACTED_EMAIL]" in saved_log.transcript_redacted
    assert "087 123 4567" not in saved_log.transcript_redacted
    assert "john@example.com" not in saved_log.transcript_redacted
    assert saved_log.outcome == "BOOKED"
    assert saved_log.estimated_cost_usd > Decimal("0")


def test_acceptance_pii_redaction() -> None:
    """Stage 7 Acceptance Check 2: Redaction test passes for sensitive patient PII."""
    raw = "Patient Sean Kelly called from +353 87 555 4321, email sean.kelly@tcd.ie for €65 checkup at 09:30."
    redacted = redact_pii(raw)

    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "+353 87 555 4321" not in redacted
    assert "sean.kelly@tcd.ie" not in redacted
    # Non-PII retained
    assert "€65" in redacted
    assert "09:30" in redacted
    assert "Sean Kelly" in redacted
