"""Unit tests for Stage 5 LiveKit voice pipeline and components."""

import pytest
from dentacall_agent.latency import LatencyTracker, TurnLatencyRecord
from dentacall_agent.livekit_tools import create_livekit_tools
from dentacall_agent.voice_prompt import build_voice_prompt
from dentacall_core.settings import settings


@pytest.mark.asyncio
async def test_livekit_tools_creation() -> None:
    """Verify all 9 receptionist tools are converted to LiveKit FunctionTools."""
    tools = create_livekit_tools()
    assert len(tools) == 9

    tool_names = {getattr(t, "__name__", None) for t in tools}
    expected_tools = {
        "find_patient",
        "check_availability",
        "hold_slot",
        "book_appointment",
        "reschedule_appointment",
        "cancel_appointment",
        "get_clinic_info",
        "take_message",
        "transfer_to_human",
    }
    assert tool_names == expected_tools

    # Check that tool descriptions exist
    for t in tools:
        assert hasattr(t, "description") or hasattr(t, "__doc__")


@pytest.mark.asyncio
async def test_voice_prompt_formatting() -> None:
    """Verify voice prompt enforces spoken voice guidelines, Dublin timezone, and guardrails."""
    prompt = build_voice_prompt()
    assert "Grand Canal Dental Clinic" in prompt
    assert "Dublin" in prompt
    # Voice guidelines
    assert "SPOKEN CONVERSATION ONLY" in prompt
    assert "CONVERSATIONAL FILLERS" in prompt
    assert "BARGE-IN AWARENESS" in prompt
    assert "sixty-five euro" in prompt
    # Emergency triage protocols
    assert "999" in prompt or "112" in prompt
    assert "milk" in prompt
    # Guardrails
    assert "REFUSE MEDICAL & MEDICATION ADVICE" in prompt


@pytest.mark.asyncio
async def test_latency_tracker_calculations() -> None:
    """Verify LatencyTracker aggregates turn latency, character counts, and target metrics."""
    tracker = LatencyTracker()

    t1 = TurnLatencyRecord(
        turn_id="turn-1",
        stt_duration_ms=180.0,
        llm_ttft_ms=250.0,
        tool_duration_ms=80.0,
        tts_ttfb_ms=210.0,
        total_ttfa_ms=720.0,  # <= 1200ms -> met
        characters_synthesized=120,
        deepgram_request_id="dg-req-001",
    )
    t2 = TurnLatencyRecord(
        turn_id="turn-2",
        stt_duration_ms=220.0,
        llm_ttft_ms=310.0,
        tool_duration_ms=0.0,
        tts_ttfb_ms=240.0,
        total_ttfa_ms=770.0,  # <= 1200ms -> met
        characters_synthesized=95,
        deepgram_request_id="dg-req-002",
    )

    tracker.record_turn(t1)
    tracker.record_turn(t2)

    stats = tracker.get_aggregate_stats()
    assert stats["turn_count"] == 2
    assert stats["avg_total_ttfa_ms"] == pytest.approx(745.0, 0.1)
    assert stats["target_success_rate"] == 100.0
    assert stats["total_characters_sent"] == 215
    assert stats["avg_stt_ms"] == pytest.approx(200.0, 0.1)


@pytest.mark.asyncio
async def test_voice_settings_configured() -> None:
    """Verify LiveKit, Deepgram, and ElevenLabs settings are loaded from .env."""
    assert settings.deepgram_api_key is not None
    assert settings.elevenlabs_api_key is not None
    assert settings.livekit_url is not None
    assert settings.livekit_api_key is not None
    assert settings.livekit_api_secret is not None
    assert settings.elevenlabs_model == "eleven_turbo_v2_5"
