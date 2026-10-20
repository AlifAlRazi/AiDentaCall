"""Data retention policy enforcement for call logs and transcripts."""

import logging
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dentacall_core.models import CallLog
from dentacall_core.settings import settings
from dentacall_core.timezone import now_utc

logger = logging.getLogger(__name__)


async def get_expired_call_logs_count(
    session: AsyncSession,
    retention_days: int | None = None,
) -> int:
    """Return count of call log records older than the data retention window."""
    days = retention_days if retention_days is not None else settings.data_retention_days
    cutoff = now_utc() - timedelta(days=days)

    stmt = select(func.count(CallLog.id)).where(CallLog.created_at_utc < cutoff)
    result = await session.execute(stmt)
    count: int = result.scalar() or 0
    return count


async def purge_expired_call_logs(
    session: AsyncSession,
    retention_days: int | None = None,
) -> int:
    """Permanently delete call log records older than the data retention threshold."""
    days = retention_days if retention_days is not None else settings.data_retention_days
    cutoff = now_utc() - timedelta(days=days)

    stmt = delete(CallLog).where(CallLog.created_at_utc < cutoff)
    result = await session.execute(stmt)
    deleted_count: int = result.rowcount or 0
    await session.commit()

    logger.info(
        "Data retention purge completed: deleted %d call logs older than %d days (cutoff: %s)",
        deleted_count,
        days,
        cutoff.isoformat(),
    )
    return deleted_count
