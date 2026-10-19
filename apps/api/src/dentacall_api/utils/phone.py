"""Phone number parsing and E.164 normalization utilities with Irish number support."""

import re

import phonenumbers


class InvalidPhoneNumberError(ValueError):
    """Raised when a phone number string cannot be parsed as a valid E.164 number."""

    pass


def normalize_phone_number(raw_phone: str, default_region: str = "IE") -> str:
    """Normalize an incoming phone number into E.164 format.

    Supports:
    - Irish mobile numbers: '0871234567', '086 123 4567' -> '+353871234567'
    - Irish landlines: '01 234 5678', '(01) 2345678' -> '+35312345678'
    - International numbers: '+44 20 7946 0912', '+1 555 123 4567'
    """
    if not raw_phone or not isinstance(raw_phone, str):
        raise InvalidPhoneNumberError("Phone number must be a non-empty string.")

    cleaned = raw_phone.strip()

    # Pre-clean common separators
    cleaned = re.sub(r"[ \-\.\(\)]", "", cleaned)

    try:
        parsed = phonenumbers.parse(cleaned, default_region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneNumberError(f"Cannot parse phone number '{raw_phone}': {exc}") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumberError(
            f"Phone number '{raw_phone}' is not a valid telephone number for region {default_region}."
        )

    return str(phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164))
