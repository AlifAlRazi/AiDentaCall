"""PII redaction utilities for transcripts and call logs."""

import re
from typing import Any

# Regex for email addresses
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    re.IGNORECASE,
)

# Regex for international and Irish telephone numbers (e.g. +353 87 123 4567, 087-123-4567, (01) 234 5678)
PHONE_REGEX = re.compile(
    r"(?:(?:\+|00)353[\s.-]?\(?0?\)?[\s.-]?[1-9][0-9]{1,4}[\s.-]?[0-9]{3,4}[\s.-]?[0-9]{3,4}"
    r"|0[1-9][0-9]?[\s.-]?[0-9]{3,4}[\s.-]?[0-9]{3,4}"
    r"|\+?[1-9]\d{1,14}"
    r"|\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4})",
    re.VERBOSE,
)

# Common spoken digit patterns (e.g. 0-8-7-1-2-3-4-5-6-7 or spaces between single digits)
SPOKEN_DIGITS_REGEX = re.compile(r"\b(?:\d[\s-]){6,}\d\b")


def redact_phone_numbers(text: str) -> str:
    """Replace all detected phone numbers with [REDACTED_PHONE]."""
    if not text:
        return text
    # First redact spoken hyphenated/spaced digit sequences
    redacted = SPOKEN_DIGITS_REGEX.sub("[REDACTED_PHONE]", text)

    # Then standard formatted phone numbers (ensure length >= 7 digits)
    def _phone_sub(match: re.Match[str]) -> str:
        matched = match.group(0)
        digits_only = re.sub(r"\D", "", matched)
        # Avoid redacting small isolated numbers like "€65" or "10:30" or years like "2026"
        if len(digits_only) >= 7:
            return "[REDACTED_PHONE]"
        return matched

    return PHONE_REGEX.sub(_phone_sub, redacted)


def redact_emails(text: str) -> str:
    """Replace all detected email addresses with [REDACTED_EMAIL]."""
    if not text:
        return text
    return EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)


def redact_pii(text: str) -> str:
    """Redact both email addresses and telephone numbers from text."""
    if not text:
        return text
    # Order matters: redact emails first so domain digits aren't mangled by phone regex
    with_redacted_emails = redact_emails(text)
    return redact_phone_numbers(with_redacted_emails)


def redact_transcript(messages: list[dict[str, Any]] | str) -> str:
    """Convert a transcript (string or list of message objects) into a redacted text representation."""
    if isinstance(messages, str):
        return redact_pii(messages)

    lines: list[str] = []
    for msg in messages:
        sender = msg.get("speaker") or msg.get("role") or msg.get("sender", "Unknown")
        content = msg.get("content") or msg.get("text", "")
        redacted_content = redact_pii(str(content))
        lines.append(f"{sender}: {redacted_content}")

    return "\n".join(lines)
