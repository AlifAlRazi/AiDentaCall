"""Tests for OpenTelemetry turn tracing and itemized call cost calculation."""

from dentacall_core.cost_tracker import CallCostCalculator, CallCostEstimate
from dentacall_core.tracing import (
    clear_collected_spans,
    get_collected_spans,
    trace_llm,
    trace_stt,
    trace_tool,
    trace_tts,
    trace_turn,
)


def test_call_turn_produces_full_opentelemetry_trace() -> None:
    """Verify that a full conversational turn emits parent and child spans for STT, LLM, tool, and TTS."""
    clear_collected_spans()

    call_id = "call-test-trace-123"
    turn_id = "turn-001"

    # Simulate an entire end-to-end conversational turn
    with trace_turn(
        call_id=call_id, turn_id=turn_id, turn_number=1, user_input="Can I book a checkup tomorrow?"
    ):
        # 1. STT Span
        with trace_stt(provider="deepgram", request_id="dg-req-9988", duration_ms=210.5):
            pass

        # 2. LLM Span
        with trace_llm(model="gpt-4o-mini", prompt_tokens=450, completion_tokens=85, ttft_ms=310.2):
            pass

        # 3. Tool Execution Span
        with trace_tool(tool_name="check_availability", arguments={"service_code": "CHECKUP"}):
            pass

        # 4. TTS Span
        with trace_tts(provider="elevenlabs", characters_sent=95, ttfb_ms=180.0):
            pass

    spans = get_collected_spans()
    span_names = [s.name for s in spans]

    # Verify all expected spans were recorded
    assert "call_turn" in span_names
    assert "stt_transcription" in span_names
    assert "llm_generation" in span_names
    assert "tool_check_availability" in span_names
    assert "tts_synthesis" in span_names

    # Verify parent-child correlation and attributes
    turn_span = next(s for s in spans if s.name == "call_turn")
    assert turn_span.attributes is not None
    assert turn_span.attributes["dentacall.call_id"] == call_id
    assert turn_span.attributes["dentacall.turn_id"] == turn_id

    stt_span = next(s for s in spans if s.name == "stt_transcription")
    assert stt_span.attributes is not None
    assert stt_span.attributes["stt.provider"] == "deepgram"
    assert stt_span.attributes["deepgram.request_id"] == "dg-req-9988"

    llm_span = next(s for s in spans if s.name == "llm_generation")
    assert llm_span.attributes is not None
    assert llm_span.attributes["llm.model"] == "gpt-4o-mini"
    assert llm_span.attributes["llm.prompt_tokens"] == 450
    assert llm_span.attributes["llm.completion_tokens"] == 85

    tool_span = next(s for s in spans if s.name == "tool_check_availability")
    assert tool_span.attributes is not None
    assert tool_span.attributes["tool.name"] == "check_availability"

    tts_span = next(s for s in spans if s.name == "tts_synthesis")
    assert tts_span.attributes is not None
    assert tts_span.attributes["tts.provider"] == "elevenlabs"
    assert tts_span.attributes["tts.characters_sent"] == 95


def test_call_cost_calculation_itemized_and_total() -> None:
    """Verify itemized cost calculation across Twilio, Deepgram, OpenAI, ElevenLabs, and LiveKit."""
    cost: CallCostEstimate = CallCostCalculator.calculate(
        duration_seconds=180.0,  # 3 minutes
        prompt_tokens=1200,
        completion_tokens=300,
        characters_synthesized=850,
        is_telephony=True,
    )

    # Duration and counts
    assert cost.duration_seconds == 180.0
    assert cost.prompt_tokens == 1200
    assert cost.completion_tokens == 300
    assert cost.characters_synthesized == 850

    # Provider costs
    # Twilio: 3 min * 0.014 = $0.042
    assert cost.twilio_cost_usd == 0.042
    # Deepgram: 3 min * 0.0043 = $0.0129
    assert cost.deepgram_cost_usd == 0.0129
    # LiveKit: 3 min * 0.004 = $0.012
    assert cost.livekit_cost_usd == 0.012

    # OpenAI gpt-4o-mini: 1200 * $0.15/1M + 300 * $0.60/1M = 0.00018 + 0.00018 = 0.00036
    assert round(cost.openai_cost_usd, 5) == 0.00036

    # ElevenLabs: 850 * $25/1M = $0.02125
    assert cost.elevenlabs_cost_usd == 0.02125

    # Sum check
    expected_sum = (
        cost.twilio_cost_usd
        + cost.deepgram_cost_usd
        + cost.openai_cost_usd
        + cost.elevenlabs_cost_usd
        + cost.livekit_cost_usd
    )
    assert abs(cost.total_cost_usd - expected_sum) < 1e-5
    assert cost.total_cost_usd > 0.08  # Approx $0.08851

    # Dictionary conversion
    data = cost.to_dict()
    assert "total_cost_usd" in data
    assert "elevenlabs_cost_usd" in data
