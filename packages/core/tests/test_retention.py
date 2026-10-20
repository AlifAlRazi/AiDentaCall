"""Unit tests for CallLog data retention policy and purging."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from dentacall_core.retention import get_expired_call_logs_count, purge_expired_call_logs


@pytest.mark.asyncio
async def test_get_expired_call_logs_count() -> None:
    """Verify get_expired_call_logs_count executes count query with cutoff."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 8
    mock_session.execute.return_value = mock_result

    count = await get_expired_call_logs_count(mock_session, retention_days=90)
    assert count == 8
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_purge_expired_call_logs() -> None:
    """Verify purge_expired_call_logs deletes records older than retention threshold and commits."""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 12
    mock_session.execute.return_value = mock_result

    deleted = await purge_expired_call_logs(mock_session, retention_days=60)
    assert deleted == 12
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()
