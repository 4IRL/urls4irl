from __future__ import annotations

import re

from pydantic import ValidationError

from backend.utils.strings.json_strs import FIELD_REQUIRED_STR

_MIN_LENGTH_RE = re.compile(r"^String should have at least (\d+) characters?$")
_MAX_LENGTH_RE = re.compile(r"^String should have at most (\d+) characters?$")


def _humanize_error_message(msg: str) -> str:
    """Map raw Pydantic validation messages to user-friendly equivalents."""
    if msg == "Field required":
        return FIELD_REQUIRED_STR

    min_match = _MIN_LENGTH_RE.match(msg)
    if min_match:
        length = int(min_match.group(1))
        if length <= 1:
            return FIELD_REQUIRED_STR
        return f"Must be at least {length} characters."

    max_match = _MAX_LENGTH_RE.match(msg)
    if max_match:
        length = int(max_match.group(1))
        return f"Must be at most {length} characters."

    if msg.startswith("value is not a valid email address"):
        return "Please enter a valid email address."

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
