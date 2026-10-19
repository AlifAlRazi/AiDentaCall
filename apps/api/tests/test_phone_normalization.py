"""Unit tests for phone number parsing and Irish E.164 normalization."""

import pytest
from dentacall_api.utils.phone import InvalidPhoneNumberError, normalize_phone_number


def test_irish_mobile_normalization() -> None:
    """Verify various Irish mobile number input styles are cleanly normalized to E.164."""
    # Standard 10-digit mobile starting with 087
    assert normalize_phone_number("0871234567") == "+353871234567"
    # Mobile with spaces
    assert normalize_phone_number("086 234 5678") == "+353862345678"
    # Mobile with hyphens
    assert normalize_phone_number("085-345-6789") == "+353853456789"
    # Mobile with brackets
    assert normalize_phone_number("(089) 4567890") == "+353894567890"
    # Mobile already with +353 country code
    assert normalize_phone_number("+353 87 111 2222") == "+353871112222"


def test_irish_landline_normalization() -> None:
    """Verify Dublin and Irish regional landline formats are normalized to E.164."""
    # Dublin area code (01)
    assert normalize_phone_number("01 234 5678") == "+35312345678"
    assert normalize_phone_number("(01) 2345678") == "+35312345678"
    # Cork area code (021)
    assert normalize_phone_number("021 456 7890") == "+353214567890"


def test_international_number_normalization() -> None:
    """Verify valid international formats are preserved and normalized to E.164."""
    # UK mobile
    assert normalize_phone_number("+44 7911 123456") == "+447911123456"
    # US number
    assert normalize_phone_number("+1 (202) 456-1111") == "+12024561111"


def test_invalid_phone_numbers_raise_error() -> None:
    """Verify invalid strings or truncated digits raise InvalidPhoneNumberError."""
    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone_number("1234")

    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone_number("not-a-phone-number")

    with pytest.raises(InvalidPhoneNumberError):
        normalize_phone_number("")
