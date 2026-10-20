"""Tests for Stage 6 Telephony router, Twilio integration, dropped call recovery, and spend cap."""

import uuid

import pytest
from dentacall_api.main import create_app
from dentacall_core.settings import settings
from dentacall_core.telephony import telephony_manager
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def reset_telephony_state() -> None:
    """Reset telephony manager between tests."""
    telephony_manager.clear()


@pytest.mark.asyncio
async def test_twilio_incoming_call_twiml() -> None:
    """Verify incoming Twilio call returns TwiML with mandatory legal AI & recording disclosure."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        call_sid = "CA" + uuid.uuid4().hex[:30]
        response = await client.post(
            "/api/telephony/twilio/incoming",
            data={
                "CallSid": call_sid,
                "From": "+353871234567",
                "To": "+35312345678",
                "CallStatus": "ringing",
            },
        )
        assert response.status_code == 200
        assert "application/xml" in response.headers.get("content-type", "")
        text = response.text
        # Mandatory AI disclosure
        assert "AI receptionist" in text
        assert "may be recorded" in text
        assert "Grand Canal Dental Clinic" in text
        # Active session created
        session = telephony_manager.get_session(call_sid)
        assert session is not None
        assert session.caller_phone == "+353871234567"


@pytest.mark.asyncio
async def test_concurrency_limit_enforcement() -> None:
    """Verify that exceeding max_concurrent_calls rejects the incoming call politely."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Fill all concurrent slots
        for i in range(settings.max_concurrent_calls):
            telephony_manager.start_call_session(call_id=f"sim-call-{i}")

        assert telephony_manager.is_concurrency_limit_exceeded()

        # Next call should be rejected with busy notice
        response = await client.post(
            "/api/telephony/twilio/incoming",
            data={
                "CallSid": "CA_overflow",
                "From": "+353879999999",
            },
        )
        assert response.status_code == 200
        assert "busy" in response.text.lower() or "hold" in response.text.lower()
        assert "<Hangup" in response.text or "<Reject" in response.text


@pytest.mark.asyncio
async def test_daily_spend_cap_enforcement() -> None:
    """Verify that reaching the daily spend cap prevents new non-emergency calls."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Artificially exhaust spend cap
        telephony_manager.add_spend(settings.daily_spend_cap_usd + 1.0)
        assert telephony_manager.is_spend_cap_exceeded()

        response = await client.post(
            "/api/telephony/twilio/incoming",
            data={
                "CallSid": "CA_cap_exceeded",
                "From": "+353871112233",
            },
        )
        assert response.status_code == 200
        assert "quota" in response.text.lower() or "limit" in response.text.lower()
        assert "<Hangup" in response.text


@pytest.mark.asyncio
async def test_dropped_call_releases_held_slot() -> None:
    """Verify that when a call drops during a booking, held slots are immediately released with no stuck holds."""
    from unittest.mock import AsyncMock, MagicMock, patch

    call_sid = "CA_dropped_test_" + uuid.uuid4().hex[:16]
    telephony_manager.start_call_session(call_id=call_sid, call_sid=call_sid)
    hold_id = uuid.uuid4()
    telephony_manager.register_call_hold(call_sid, hold_id)

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    with patch("dentacall_core.telephony.release_hold", new_callable=AsyncMock) as mock_release:
        mock_release.return_value = True

        result = await telephony_manager.handle_call_disconnect(
            call_id=call_sid,
            db_session=mock_db,
            reason="DROPPED",
        )
        assert result["holds_released"] == 1
        assert str(hold_id) in result["released_hold_ids"]
        mock_release.assert_awaited_once_with(mock_db, hold_id)

    # Verify session is cleaned up and hold is cleared
    assert telephony_manager.get_session(call_sid) is None


@pytest.mark.asyncio
async def test_human_transfer_and_emergency_routing() -> None:
    """Verify call transfer routes to escalation line and emergency line accordingly."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Standard Transfer
        resp_std = await client.post(
            "/api/telephony/twilio/transfer",
            data={"reason": "COMPLEX_QUERY"},
        )
        assert resp_std.status_code == 200
        assert settings.clinic_escalation_number in resp_std.text
        assert "receptionist" in resp_std.text.lower()

        # 2. Emergency Transfer
        resp_emerg = await client.post(
            "/api/telephony/twilio/transfer",
            data={"reason": "EMERGENCY"},
        )
        assert resp_emerg.status_code == 200
        assert settings.emergency_transfer_number in resp_emerg.text
        assert "emergency" in resp_emerg.text.lower()


@pytest.mark.asyncio
async def test_transfer_voicemail_fallback() -> None:
    """Verify that if human staff do not answer (no-answer/busy), call falls back to voicemail recording."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dial status callback with no-answer
        resp = await client.post(
            "/api/telephony/twilio/dial-status",
            data={"DialCallStatus": "no-answer"},
        )
        assert resp.status_code == 200
        assert "<Record" in resp.text
        assert "/api/telephony/twilio/voicemail" in resp.text
        assert "message after the tone" in resp.text.lower()


@pytest.mark.asyncio
async def test_voicemail_recording_callback() -> None:
    """Verify voicemail recorded webhook saves recording and provides confirmation."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        call_sid = "CA_vm_test"
        telephony_manager.start_call_session(call_id=call_sid, call_sid=call_sid)

        resp = await client.post(
            "/api/telephony/twilio/voicemail",
            data={
                "CallSid": call_sid,
                "From": "+353871234567",
                "RecordingUrl": "https://api.twilio.com/2010-04-01/Accounts/AC123/Recordings/RE999",
                "RecordingDuration": "25",
            },
        )
        assert resp.status_code == 200
        assert "receptionist will call you back" in resp.text.lower()
        assert "<Hangup" in resp.text


@pytest.mark.asyncio
async def test_telephony_status_endpoint() -> None:
    """Verify /api/telephony/status returns real-time metrics and limits."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/telephony/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "active_calls_count" in data
        assert "max_concurrent_calls" in data
        assert "today_spend_usd" in data
        assert "daily_spend_cap_usd" in data
        assert data["max_concurrent_calls"] == settings.max_concurrent_calls
