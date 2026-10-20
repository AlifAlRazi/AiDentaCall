"""Tests for Stage 7 Metrics API (/api/metrics) and retention endpoints."""

import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from dentacall_api.main import create_app
from dentacall_core.db import get_async_session
from dentacall_core.models import CallLog
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_metrics_empty_database_defaults() -> None:
    """Verify /api/metrics returns clean zeroed defaults when no calls exist."""
    app = create_app()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    async def override_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_async_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/metrics?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["total_calls"] == 0
        assert data["calls_per_day"] == 0.0
        assert data["booking_rate"] == 0.0
        assert data["average_latency_ms"] == 0.0
        assert data["failure_rate"] == 0.0
        assert data["cost_per_call_usd"] == 0.0
        assert data["data_retention_days"] == 90
        assert data["calls_by_outcome"] == {}

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_metrics_with_calls_calculation() -> None:
    """Verify /api/metrics correctly calculates calls/day, booking rate, latency, failure rate, and costs."""
    app = create_app()

    now = datetime.now(UTC)
    mock_calls = [
        # Call 1: Booked, 750ms latency, $0.05 cost
        CallLog(
            id=uuid.uuid4(),
            clinic_id=uuid.uuid4(),
            status="COMPLETED",
            outcome="BOOKED",
            duration_seconds=120.0,
            latency_metrics=json.dumps({"mean_ttfa_ms": 750.0}),
            estimated_cost_usd=Decimal("0.0500"),
            created_at_utc=now,
        ),
        # Call 2: Booked, 650ms latency, $0.04 cost
        CallLog(
            id=uuid.uuid4(),
            clinic_id=uuid.uuid4(),
            status="COMPLETED",
            outcome="BOOKED",
            duration_seconds=90.0,
            latency_metrics=json.dumps({"mean_ttfa_ms": 650.0}),
            estimated_cost_usd=Decimal("0.0400"),
            created_at_utc=now,
        ),
        # Call 3: Dropped/Failed, 800ms latency, $0.03 cost
        CallLog(
            id=uuid.uuid4(),
            clinic_id=uuid.uuid4(),
            status="DROPPED",
            outcome="DROPPED",
            duration_seconds=60.0,
            latency_metrics=json.dumps({"mean_ttfa_ms": 800.0}),
            estimated_cost_usd=Decimal("0.0300"),
            created_at_utc=now,
        ),
        # Call 4: Completed inquiry, no latency metric, $0.02 cost
        CallLog(
            id=uuid.uuid4(),
            clinic_id=uuid.uuid4(),
            status="COMPLETED",
            outcome="INQUIRY",
            duration_seconds=45.0,
            latency_metrics=None,
            estimated_cost_usd=Decimal("0.0200"),
            created_at_utc=now,
        ),
    ]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_calls
    mock_session.execute.return_value = mock_result

    async def override_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_async_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/metrics?days=10")
        assert response.status_code == 200
        data = response.json()

        assert data["total_calls"] == 4
        # 4 calls over 10 days = 0.4 calls/day
        assert data["calls_per_day"] == 0.4
        # 2 booked out of 4 = 50% booking rate
        assert data["booking_rate"] == 0.5
        # 1 dropped out of 4 = 25% failure rate
        assert data["failure_rate"] == 0.25
        # (750 + 650 + 800) / 3 = 733.3ms
        assert round(data["average_latency_ms"], 1) == 733.3
        # Total cost: 0.05 + 0.04 + 0.03 + 0.02 = 0.14. Per call = 0.035
        assert round(data["cost_per_call_usd"], 3) == 0.035
        assert round(data["total_spend_usd"], 2) == 0.14
        assert data["calls_by_outcome"] == {
            "BOOKED": 2,
            "DROPPED": 1,
            "INQUIRY": 1,
        }

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_trigger_retention_purge_endpoint() -> None:
    """Verify /api/metrics/purge-retention calls retention purge logic and returns count."""
    app = create_app()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 15
    mock_session.execute.return_value = mock_result

    async def override_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    app.dependency_overrides[get_async_session] = override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/metrics/purge-retention?days=90")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted_count"] == 15
        assert data["data_retention_days"] == 90
        assert "cutoff_utc" in data

    app.dependency_overrides.clear()
