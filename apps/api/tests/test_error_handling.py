"""Acceptance test: bad input returns helpful errors and hints, never a stack trace."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_missing_required_fields_returns_clean_hint_no_stack_trace(
    client: AsyncClient,
) -> None:
    """Submitting empty JSON payload returns 422 with structured INVALID_ARGUMENTS and hint."""
    response = await client.post("/tools/book_appointment", json={})
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "INVALID_ARGUMENTS"
    assert "hint" in body
    assert body["hint"] is not None
    # Verify no raw Python tracebacks leaked
    assert "Traceback (most recent call last)" not in response.text
    assert "ValidationError" not in response.text


@pytest.mark.asyncio
async def test_malformed_date_format_returns_clean_error(client: AsyncClient) -> None:
    """Submitting unparseable dates returns helpful validation message without stack trace."""
    payload = {
        "start_date": "not-a-valid-date",
        "end_date": "2026-05-10",
        "service_code": "CHECKUP",
    }
    response = await client.post("/tools/check_availability", json=payload)
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "INVALID_ARGUMENTS"
    assert "start_date" in body["error_message"]
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_malformed_phone_returns_clean_error(client: AsyncClient) -> None:
    """Submitting unparseable telephone number returns helpful error hint without stack trace."""
    payload = {
        "caller_name": "John Doe",
        "caller_phone": "abc-not-a-phone",
        "message": "Please call me back",
    }
    response = await client.post("/tools/take_message", json=payload)
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "INVALID_ARGUMENTS"
    assert "caller_phone" in body["error_message"]
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_invalid_service_code_returns_helpful_hint(client: AsyncClient) -> None:
    """Querying an unknown service code returns clear hint listing available service codes."""
    payload = {
        "start_date": "2026-07-01",
        "end_date": "2026-07-05",
        "service_code": "COSMETIC_VENEERS_NONEXISTENT",
    }
    response = await client.post("/tools/check_availability", json=payload)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == "INVALID_SERVICE_CODE"
    assert "CHECKUP" in body["hint"]
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_missing_api_key_returns_unauthorized_no_stack_trace() -> None:
    """Omitting X-API-Key header returns 401 with clean error envelope."""
    from dentacall_api.main import create_app
    from httpx import ASGITransport

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as unauthed_client:
        response = await unauthed_client.post(
            "/tools/find_patient", json={"phone": "+353871234567"}
        )
        assert response.status_code == 401

        body = response.json()
        assert body["success"] is False
        assert body["error_code"] == "UNAUTHORIZED"
        assert "X-API-Key" in body["hint"]
        assert "Traceback" not in response.text
