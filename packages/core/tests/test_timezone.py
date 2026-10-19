"""Unit tests for UTC canonical storage and Europe/Dublin edge conversions, including daylight saving transitions."""

from datetime import date, datetime, time, timedelta

from dentacall_core.timezone import (
    DUBLIN_TZ,
    UTC,
    combine_dublin,
    format_dublin,
    to_dublin,
    to_utc,
)


def test_utc_conversion_idempotence() -> None:
    """Ensure that converting an already-UTC datetime produces an identical UTC datetime."""
    dt_utc = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
    assert to_utc(dt_utc) == dt_utc
    assert to_utc(dt_utc).tzinfo == UTC


def test_naive_datetime_interpreted_as_dublin() -> None:
    """Naive datetimes are assumed to represent Europe/Dublin local time when converted to UTC."""
    # In July 2026, Dublin is in IST (UTC+1)
    dt_summer_naive = datetime(2026, 7, 10, 10, 0)
    dt_utc = to_utc(dt_summer_naive)
    assert dt_utc.hour == 9
    assert dt_utc.tzinfo == UTC

    # In January 2026, Dublin is in GMT (UTC+0)
    dt_winter_naive = datetime(2026, 1, 15, 10, 0)
    dt_utc = to_utc(dt_winter_naive)
    assert dt_utc.hour == 10
    assert dt_utc.tzinfo == UTC


def test_spring_forward_daylight_saving_transition() -> None:
    """Verify Europe/Dublin spring daylight saving transition (GMT -> IST).

    In 2026, clocks spring forward on Sunday 29 March at 01:00 UTC (01:00 -> 02:00 IST).
    """
    # Saturday 28 March 2026: Winter GMT (UTC+0)
    sat_local = datetime(2026, 3, 28, 10, 0, tzinfo=DUBLIN_TZ)
    sat_utc = to_utc(sat_local)
    assert sat_utc.hour == 10
    assert sat_utc == datetime(2026, 3, 28, 10, 0, tzinfo=UTC)

    # Monday 30 March 2026: Summer IST (UTC+1)
    mon_local = datetime(2026, 3, 30, 10, 0, tzinfo=DUBLIN_TZ)
    mon_utc = to_utc(mon_local)
    assert mon_utc.hour == 9
    assert mon_utc == datetime(2026, 3, 30, 9, 0, tzinfo=UTC)

    # Difference in elapsed absolute UTC time across the 2 days is 47 hours (not 48)
    elapsed = mon_utc - sat_utc
    assert elapsed == timedelta(hours=47)


def test_fall_back_daylight_saving_transition() -> None:
    """Verify Europe/Dublin autumn daylight saving transition (IST -> GMT).

    In 2026, clocks fall back on Sunday 25 October at 02:00 IST (01:00 UTC) back to 01:00 GMT.
    """
    # Saturday 24 October 2026: Summer IST (UTC+1)
    sat_local = datetime(2026, 10, 24, 10, 0, tzinfo=DUBLIN_TZ)
    sat_utc = to_utc(sat_local)
    assert sat_utc.hour == 9

    # Monday 26 October 2026: Winter GMT (UTC+0)
    mon_local = datetime(2026, 10, 26, 10, 0, tzinfo=DUBLIN_TZ)
    mon_utc = to_utc(mon_local)
    assert mon_utc.hour == 10

    # Difference in elapsed absolute UTC time across the 2 days is 49 hours (not 48)
    elapsed = mon_utc - sat_utc
    assert elapsed == timedelta(hours=49)


def test_combine_dublin() -> None:
    """Verify combine_dublin creates exact UTC datetime from local date and time."""
    d = date(2026, 6, 1)
    t = time(14, 30)
    utc_dt = combine_dublin(d, t)
    assert utc_dt == datetime(2026, 6, 1, 13, 30, tzinfo=UTC)

    dublin_roundtrip = to_dublin(utc_dt)
    assert dublin_roundtrip.hour == 14
    assert dublin_roundtrip.minute == 30


def test_format_dublin() -> None:
    """Verify format_dublin formats time in Europe/Dublin local time."""
    # Summer timestamp in UTC: 13:00 UTC = 14:00 IST
    summer_utc = datetime(2026, 7, 1, 13, 0, tzinfo=UTC)
    formatted = format_dublin(summer_utc, fmt="%H:%M %Z")
    assert "14:00" in formatted
    assert "IST" in formatted
