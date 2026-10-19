"""Unit tests covering Republic of Ireland statutory public holidays."""

from datetime import date

from dentacall_core.holidays import (
    compute_easter_sunday,
    get_irish_public_holiday_name,
    get_irish_public_holidays,
    is_irish_public_holiday,
)


def test_easter_sunday_calculation() -> None:
    """Verify Western Easter Sunday computus algorithm."""
    assert compute_easter_sunday(2024) == date(2024, 3, 31)
    assert compute_easter_sunday(2025) == date(2025, 4, 20)
    assert compute_easter_sunday(2026) == date(2026, 4, 5)


def test_all_ten_irish_public_holidays_2026() -> None:
    """Verify that all 10 statutory Irish public holidays are correctly generated for 2026."""
    holidays_2026 = get_irish_public_holidays(2026)
    assert len(holidays_2026) == 10

    expected_holidays = {
        date(2026, 1, 1): "New Year's Day",
        date(2026, 2, 2): "St. Brigid's Day",  # First Monday in Feb 2026
        date(2026, 3, 17): "St. Patrick's Day",
        date(2026, 4, 6): "Easter Monday",
        date(2026, 5, 4): "May Bank Holiday",
        date(2026, 6, 1): "June Bank Holiday",
        date(2026, 8, 3): "August Bank Holiday",
        date(2026, 10, 26): "October Bank Holiday",
        date(2026, 12, 25): "Christmas Day",
        date(2026, 12, 28): "St. Stephen's Day (Observed)",  # 26 Dec is Sat -> Mon 28 Dec
    }

    for expected_date, expected_name in expected_holidays.items():
        assert expected_date in holidays_2026, f"Missing holiday on {expected_date}"
        assert holidays_2026[expected_date] == expected_name


def test_st_brigid_friday_rule() -> None:
    """Verify St. Brigid's Day rule when Feb 1 falls on a Friday (e.g. 2030)."""
    # In 2030, Feb 1 is a Friday -> holiday must be Friday 1 Feb
    feb1_2030 = date(2030, 2, 1)
    assert feb1_2030.weekday() == 4
    holidays_2030 = get_irish_public_holidays(2030)
    assert feb1_2030 in holidays_2030
    assert holidays_2030[feb1_2030] == "St. Brigid's Day"


def test_weekend_rollover_substitute_days() -> None:
    """Verify that holidays falling on a weekend roll over to Monday/Tuesday."""
    # In 2022, 1 Jan was Saturday -> observed Monday 3 Jan
    holidays_2022 = get_irish_public_holidays(2022)
    assert date(2022, 1, 3) in holidays_2022
    assert "Observed" in holidays_2022[date(2022, 1, 3)]


def test_is_irish_public_holiday_helper() -> None:
    """Verify is_irish_public_holiday and name resolution."""
    assert is_irish_public_holiday(date(2026, 3, 17)) is True
    assert get_irish_public_holiday_name(date(2026, 3, 17)) == "St. Patrick's Day"

    # Regular working day
    assert is_irish_public_holiday(date(2026, 3, 18)) is False
    assert get_irish_public_holiday_name(date(2026, 3, 18)) is None
