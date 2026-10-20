"""Unit tests for PII redaction of phone numbers and emails in call transcripts."""

from dentacall_core.redaction import (
    redact_emails,
    redact_phone_numbers,
    redact_pii,
    redact_transcript,
)


def test_redact_irish_mobile_numbers() -> None:
    """Verify various formats of Irish mobile and landline numbers are redacted."""
    samples = [
        ("My number is +353871234567, thanks.", "My number is [REDACTED_PHONE], thanks."),
        ("Call me at +353 87 123 4567 please.", "Call me at [REDACTED_PHONE] please."),
        ("You can reach me on 0871234567.", "You can reach me on [REDACTED_PHONE]."),
        ("My office number is 01 234 5678.", "My office number is [REDACTED_PHONE]."),
        ("Phone is (01) 456 7890.", "Phone is [REDACTED_PHONE]."),
        ("Spoken slowly: 0 8 7 1 2 3 4 5 6 7.", "Spoken slowly: [REDACTED_PHONE]."),
        ("Hyphenated: 087-987-6543.", "Hyphenated: [REDACTED_PHONE]."),
    ]
    for raw, _expected in samples:
        result = redact_phone_numbers(raw)
        assert "[REDACTED_PHONE]" in result, f"Failed to redact phone in: {raw}"


def test_preserve_prices_times_and_dates() -> None:
    """Verify normal numbers like prices, times, and years are NOT redacted as phones."""
    non_phones = [
        "A routine dental exam is €65.",
        "Emergency extraction costs €130.",
        "Your appointment is at 10:30 AM tomorrow.",
        "Today's date is 2026-03-25.",
        "I need 2 fillings please.",
    ]
    for text in non_phones:
        result = redact_phone_numbers(text)
        assert "[REDACTED_PHONE]" not in result, f"False positive redaction on: {text}"
        assert result == text


def test_redact_emails() -> None:
    """Verify email addresses are redacted correctly."""
    samples = [
        (
            "Send the confirmation to patient@example.com please.",
            "Send the confirmation to [REDACTED_EMAIL] please.",
        ),
        ("My email is john.smith+dentist@dublin-dental.ie.", "My email is [REDACTED_EMAIL]."),
    ]
    for raw, _expected in samples:
        result = redact_emails(raw)
        assert "[REDACTED_EMAIL]" in result
        assert "@" not in result


def test_redact_pii_combined() -> None:
    """Verify combined redaction removes both phone and email from a statement."""
    text = (
        "Hello, my name is John Murphy. My phone is +353 87 999 8888 and my "
        "email is john.murphy@gmail.com. Can I book for 11:00 AM on €65 exam?"
    )
    redacted = redact_pii(text)
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "+353" not in redacted
    assert "john.murphy@gmail.com" not in redacted
    assert "€65" in redacted
    assert "11:00 AM" in redacted


def test_redact_transcript_messages() -> None:
    """Verify list of transcript turns is properly redacted and formatted."""
    turns = [
        {"role": "user", "content": "Hi, my phone is 0871112233."},
        {"role": "assistant", "content": "Thank you! I will send the code to user@test.ie."},
    ]
    output = redact_transcript(turns)
    assert "user: Hi, my phone is [REDACTED_PHONE]." in output
    assert "assistant: Thank you! I will send the code to [REDACTED_EMAIL]." in output
