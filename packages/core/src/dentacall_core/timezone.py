"""Timezone utilities for canonical UTC storage and Europe/Dublin edge conversion."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

DUBLIN_TZ = ZoneInfo("Europe/Dublin")
UTC = UTC

__all__ = [
    "DUBLIN_TZ",
    "UTC",
    "combine_dublin",
    "format_dublin",
    "now_dublin",
    "now_utc",
    "to_dublin",
    "to_utc",
]


def now_utc() -> datetime:
    """Return the current time in UTC with timezone awareness."""
    return datetime.now(UTC)


def now_dublin() -> datetime:
    """Return the current time in Europe/Dublin with timezone awareness."""
    return datetime.now(DUBLIN_TZ)


def to_utc(dt: datetime) -> datetime:
    """Convert a datetime to UTC.

    If the datetime is naive, it is assumed to represent Europe/Dublin local time.
    If the datetime is aware, it is converted to UTC.
    """
    if dt.tzinfo is None:
        # Interpret naive as Europe/Dublin local time
        localized = dt.replace(tzinfo=DUBLIN_TZ)
        return localized.astimezone(UTC)
    return dt.astimezone(UTC)


def to_dublin(dt: datetime) -> datetime:
    """Convert a datetime to Europe/Dublin timezone."""
    if dt.tzinfo is None:
        # Interpret naive as UTC
        localized = dt.replace(tzinfo=UTC)
        return localized.astimezone(DUBLIN_TZ)
    return dt.astimezone(DUBLIN_TZ)


def combine_dublin(d: date, t: time) -> datetime:
    """Combine a calendar date and time in Dublin local time, returning UTC datetime."""
    local_dt = datetime.combine(d, t, tzinfo=DUBLIN_TZ)
    return local_dt.astimezone(UTC)


def format_dublin(dt: datetime, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
    """Format a UTC or local datetime for user presentation in Europe/Dublin."""
    dublin_dt = to_dublin(dt)
    return dublin_dt.strftime(fmt)
