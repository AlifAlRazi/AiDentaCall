"""Tests for LiveKit token endpoint and browser testing call interface."""

import pytest
from dentacall_api.main import create_app
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_livekit_token_generation() -> None:
    """Verify POST /api/livekit/token returns a valid JWT and connection payload."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/livekit/token",
            json={
                "room_name": "test-dental-room",
                "participant_name": "Jane Doe",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert len(data["token"]) > 50
        assert data["room_name"] == "test-dental-room"
        assert "server_url" in data
        assert "participant_identity" in data


@pytest.mark.asyncio
async def test_browser_call_page_served() -> None:
    """Verify GET /call serves the WebRTC testing client HTML interface."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/call")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Grand Canal Dental Clinic" in response.text
        assert "livekit-client" in response.text
        assert "Start Voice Call" in response.text
        assert "simulateBargeIn" in response.text
