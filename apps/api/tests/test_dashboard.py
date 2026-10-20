"""Tests for Stage 8 Dashboard API endpoints: login, calls list, call detail, calendar, and overview."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from dentacall_api.main import create_app
from dentacall_core.db import get_async_session
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_dashboard_login() -> None:
    """Verify administrator login with credentials."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid password
        fail_res = await client.post(
            "/api/dashboard/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
        )
        assert fail_res.status_code == 200
        assert fail_res.json()["success"] is False
        assert fail_res.json()["token"] is None

        # Valid credentials
        success_res = await client.post(
            "/api/dashboard/auth/login",
            json={"username": "admin", "password": "dentacall2026"},
        )
        assert success_res.status_code == 200
        data = success_res.json()
        assert data["success"] is True
        assert data["role"] == "admin"
        assert "dentacall_admin_token_" in data["token"]


@pytest.mark.asyncio
async def test_dashboard_overview_endpoint() -> None:
    """Verify dashboard overview KPIs return rich seeded data when database empty."""
    app = create_app()

    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB offline")

    async def override_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_async_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/dashboard/overview")
        assert res.status_code == 200
        data = res.json()
        assert data["total_calls"] > 0
        assert data["booking_rate"] > 0.0
        assert data["average_latency_ms"] > 0.0
        assert len(data["recent_calls"]) > 0

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_calls_list_and_filters() -> None:
    """Verify listing calls with status and outcome filters."""
    app = create_app()

    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB offline")

    async def override_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_async_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # List all
        all_res = await client.get("/api/dashboard/calls")
        assert all_res.status_code == 200
        calls = all_res.json()
        assert len(calls) >= 5

        # Filter by outcome
        booked_res = await client.get("/api/dashboard/calls?outcome=BOOKED")
        assert booked_res.status_code == 200
        booked_calls = booked_res.json()
        assert all(c["outcome"] == "BOOKED" for c in booked_calls)

        # Filter by status
        dropped_res = await client.get("/api/dashboard/calls?status=DROPPED")
        assert dropped_res.status_code == 200
        dropped_calls = dropped_res.json()
        assert all(c["status"] == "DROPPED" for c in dropped_calls)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_call_detail_with_tools_and_transcript() -> None:
    """Stage 8 Acceptance Check: Call detail shows redacted transcript, each tool call, and timeline."""
    app = create_app()

    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB offline")

    async def override_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_async_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/dashboard/calls/call-001-emer")
        assert res.status_code == 200
        detail = res.json()

        # Transcript verified with redaction
        assert detail["transcript_redacted"] is not None
        assert "Grand Canal Dental Clinic" in detail["transcript_redacted"]
        assert "[REDACTED_PHONE]" in detail["transcript_redacted"]

        # Tool calls verified
        tool_calls = detail["tool_calls"]
        assert len(tool_calls) >= 3
        tool_names = [t["tool"] for t in tool_calls]
        assert "find_patient" in tool_names
        assert "check_availability" in tool_names
        assert "hold_slot" in tool_names
        assert "book_appointment" in tool_names

        # Cost and timeline verified
        assert detail["estimated_cost_usd"] > 0.0
        assert "twilio_cost_usd" in detail["cost_breakdown"]
        assert len(detail["timeline"]) >= 4

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_appointments_calendar() -> None:
    """Stage 8 Acceptance Check: Appointments calendar works with seeded data."""
    app = create_app()

    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("DB offline")

    async def override_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_async_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/dashboard/appointments")
        assert res.status_code == 200
        apts = res.json()
        assert len(apts) >= 3
        first_apt = apts[0]
        assert "patient_name" in first_apt
        assert "dentist_name" in first_apt
        assert "service_name" in first_apt
        assert "start_time_utc" in first_apt

    app.dependency_overrides.clear()
