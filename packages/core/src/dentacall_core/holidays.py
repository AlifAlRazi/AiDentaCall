"""Irish statutory public holidays calculator according to Republic of Ireland legislation."""

from datetime import date, timedelta


def compute_easter_sunday(year: int) -> date:
    """Compute Western Easter Sunday using the standard Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l_val = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_val) // 451
    month = (h + l_val - 7 * m + 114) // 31
    day = ((h + l_val - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _first_monday_of_month(year: int, month: int) -> date:
    """Return the date of the first Monday of the given month and year."""
    d = date(year, month, 1)
    days_ahead = (0 - d.weekday()) % 7  # 0 is Monday
    return d + timedelta(days=days_ahead)


def _last_monday_of_month(year: int, month: int) -> date:
    """Return the date of the last Monday of the given month and year."""
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    d = next_month - timedelta(days=1)
    days_back = (d.weekday() - 0) % 7
    return d - timedelta(days=days_back)


def get_irish_public_holidays(year: int) -> dict[date, str]:
    """Return all 10 statutory public holidays for Ireland for the given year."""
    holidays: dict[date, str] = {}

    # 1. New Year's Day (1 Jan)
    nyd = date(year, 1, 1)
    if nyd.weekday() == 5:  # Saturday
        holidays[date(year, 1, 3)] = "New Year's Day (Observed)"
    elif nyd.weekday() == 6:  # Sunday
        holidays[date(year, 1, 2)] = "New Year's Day (Observed)"
    else:
        holidays[nyd] = "New Year's Day"

    # 2. St. Brigid's Day (First Monday in Feb, or Fri 1 Feb if Friday)
    feb1 = date(year, 2, 1)
    if feb1.weekday() == 4:  # Friday 1 February
        holidays[feb1] = "St. Brigid's Day"
    else:
        holidays[_first_monday_of_month(year, 2)] = "St. Brigid's Day"

    # 3. St. Patrick's Day (17 March)
    spd = date(year, 3, 17)
    if spd.weekday() == 5:  # Saturday
        holidays[date(year, 3, 19)] = "St. Patrick's Day (Observed)"
    elif spd.weekday() == 6:  # Sunday
        holidays[date(year, 3, 18)] = "St. Patrick's Day (Observed)"
    else:
        holidays[spd] = "St. Patrick's Day"

    # 4. Easter Monday
    easter_sunday = compute_easter_sunday(year)
    easter_monday = easter_sunday + timedelta(days=1)
    holidays[easter_monday] = "Easter Monday"

    # 5. May Day Bank Holiday (First Monday in May)
    holidays[_first_monday_of_month(year, 5)] = "May Bank Holiday"

    # 6. June Bank Holiday (First Monday in June)
    holidays[_first_monday_of_month(year, 6)] = "June Bank Holiday"

    # 7. August Bank Holiday (First Monday in August)
    holidays[_first_monday_of_month(year, 8)] = "August Bank Holiday"

    # 8. October Bank Holiday (Last Monday in October)
    holidays[_last_monday_of_month(year, 10)] = "October Bank Holiday"

    # 9 & 10. Christmas Day (25 Dec) & St. Stephen's Day (26 Dec)
    xmas = date(year, 12, 25)
    stephen = date(year, 12, 26)

    if xmas.weekday() == 4:  # Friday 25 Dec, Saturday 26 Dec
        holidays[xmas] = "Christmas Day"
        holidays[date(year, 12, 28)] = "St. Stephen's Day (Observed)"
    elif xmas.weekday() == 5:  # Saturday 25 Dec, Sunday 26 Dec
        holidays[date(year, 12, 27)] = "Christmas Day (Observed)"
        holidays[date(year, 12, 28)] = "St. Stephen's Day (Observed)"
    elif xmas.weekday() == 6:  # Sunday 25 Dec, Monday 26 Dec
        holidays[date(year, 12, 27)] = "Christmas Day (Observed)"
        holidays[stephen] = "St. Stephen's Day"
    else:  # Normal weekdays
        holidays[xmas] = "Christmas Day"
        holidays[stephen] = "St. Stephen's Day"

    return holidays


def is_irish_public_holiday(d: date) -> bool:
    """Return True if the given date is an Irish public holiday."""
    holidays = get_irish_public_holidays(d.year)
    return d in holidays


def get_irish_public_holiday_name(d: date) -> str | None:
    """Return the name of the Irish public holiday, or None if not a holiday."""
    holidays = get_irish_public_holidays(d.year)
    return holidays.get(d)
