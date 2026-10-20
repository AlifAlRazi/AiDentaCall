"""Unit tests for TelephonyManager core domain logic, spend caps, and dropped-call hold tracking."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dentacall_core.settings import settings
from dentacall_core.telephony import TelephonyManager


@pytest.fixture
def manager() -> TelephonyManager:
    """Provide a fresh TelephonyManager."""
    mgr = TelephonyManager()
    mgr.clear()
    return mgr


def test_telephony_concurrency_limiting(manager: TelephonyManager) -> None:
    """Verify concurrency limiting detects when maximum calls are reached."""
    assert not manager.is_concurrency_limit_exceeded()

    for i in range(settings.max_concurrent_calls):
        manager.start_call_session(call_id=f"call-{i}")

    assert manager.is_concurrency_limit_exceeded()
    can_accept, reason = manager.can_accept_call()
    assert not can_accept
    assert "busy" in (reason or "").lower()


def test_telephony_daily_spend_cap(manager: TelephonyManager) -> None:
    """Verify daily spend cap prevents new calls once threshold is reached."""
    assert not manager.is_spend_cap_exceeded()

    # Add spend below cap
    manager.add_spend(10.0)
    assert not manager.is_spend_cap_exceeded()

    # Add spend above cap
    manager.add_spend(20.0)
    assert manager.is_spend_cap_exceeded()
    can_accept, reason = manager.can_accept_call()
    assert not can_accept
    assert "quota" in (reason or "").lower()


def test_hold_lifecycle_tracking(manager: TelephonyManager) -> None:
    """Verify slot holds can be registered and marked booked for a call session."""
    session = manager.start_call_session(call_id="call-123", caller_phone="+353871234567")
    hold_id = uuid.uuid4()

    manager.register_call_hold("call-123", hold_id)
    assert hold_id in session.active_holds

    # Convert to booking
    manager.mark_hold_booked("call-123", hold_id)
    assert hold_id not in session.active_holds


@pytest.mark.asyncio
async def test_dropped_call_invokes_release_hold(manager: TelephonyManager) -> None:
    """Verify dropped call automatically invokes release_hold for active unbooked holds."""
    _ = manager.start_call_session(call_id="call-drop-1", call_sid="CA_drop_1")
    hold_1 = uuid.uuid4()
    hold_2 = uuid.uuid4()

    manager.register_call_hold("call-drop-1", hold_1)
    manager.register_call_hold("call-drop-1", hold_2)
    # Mark hold_1 as booked, leave hold_2 unbooked (e.g. caller changed mind then hung up)
    manager.mark_hold_booked("call-drop-1", hold_1)

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    with patch("dentacall_core.telephony.release_hold", new_callable=AsyncMock) as mock_release:
        mock_release.return_value = True

        result = await manager.handle_call_disconnect(
            call_id="call-drop-1",
            db_session=mock_db,
            reason="DROPPED",
        )

        assert result["holds_released"] == 1
        assert str(hold_2) in result["released_hold_ids"]
        mock_release.assert_awaited_once_with(mock_db, hold_2)

    # Session should now be cleaned up from active list
    assert manager.get_session("call-drop-1") is None
