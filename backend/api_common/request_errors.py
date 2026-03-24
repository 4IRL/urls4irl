from __future__ import annotations

import re

from pydantic import ValidationError

from backend.utils.strings.json_strs import FIELD_REQUIRED_STR

_MIN_LENGTH_RE = re.compile(r"^String should have at least (\d+) characters?$")
_MAX_LENGTH_RE = re.compile(r"^String should have at most (\d+) characters?$")

INVALID_EMAIL_STR = "Please enter a valid email address."


def min_length_message(length: int) -> str:
    """Return the humanized min-length error for a given character count."""
    return f"Must be at least {length} characters."


def max_length_message(length: int) -> str:
    """Return the humanized max-length error for a given character count."""
    return f"Must be at most {length} characters."


def _humanize_error_message(msg: str) -> str:
    """Map raw Pydantic validation messages to user-friendly equivalents."""
    if msg == "Field required":
        return FIELD_REQUIRED_STR

    min_match = _MIN_LENGTH_RE.match(msg)
    if min_match:
        length = int(min_match.group(1))
        if length <= 1:
            return FIELD_REQUIRED_STR
        return min_length_message(length)

    max_match = _MAX_LENGTH_RE.match(msg)
    if max_match:
        length = int(max_match.group(1))
        return max_length_message(length)

    if msg.startswith("value is not a valid email address"):
        return INVALID_EMAIL_STR

    return msg


def pydantic_errors_to_dict(validation_error: ValidationError) -> dict[str, list[str]]:
    """Convert a Pydantic ValidationError to {fieldName: [errorMsg]}.
    Request schemas use camelCase Python field names so loc[0] is directly
    usable as the frontend-facing key without an alias lookup."""
    errors: dict[str, list[str]] = {}
    for error in validation_error.errors(include_url=False):
        field_name = str(error["loc"][0]) if error["loc"] else "__root__"
        msg = error["msg"]
        # Pydantic prefixes BeforeValidator/field_validator messages with "Value error, " — strip it
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        msg = _humanize_error_message(msg)
        errors.setdefault(field_name, []).append(msg)
    return errors
