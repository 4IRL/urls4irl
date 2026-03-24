from __future__ import annotations
from typing import Annotated
from pydantic import BeforeValidator
from backend.api_common.input_sanitization import sanitize_user_input
from backend.utils.strings.json_strs import FAILURE_GENERAL

INVALID_INPUT = FAILURE_GENERAL.INVALID_INPUT  # "Invalid input, please try again."


def _sanitize_and_reject_if_modified(value: str | None) -> str | None:
    """For required sanitized string fields: reject if sanitization would change the value."""
    if not isinstance(value, str):
        return value
    if not value:  # empty string → let min_length produce humanized error
        return value
    sanitized = sanitize_user_input(value)
    if sanitized != value:
        raise ValueError(INVALID_INPUT)
    return value


def _sanitize_optional_description(value: str | None) -> str | None:
    """For optional description fields: accept empty/whitespace as None; reject non-empty if sanitized differs."""
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    # Empty or whitespace-only → clear description (None)
    if value.replace(" ", "") == "":
        return None
    # Non-empty: check if sanitization modifies it
    sanitized = sanitize_user_input(value)
    if sanitized is None:
        sanitized = ""
    if sanitized != value:
        raise ValueError(INVALID_INPUT)
    return value


SanitizedStr = Annotated[str, BeforeValidator(_sanitize_and_reject_if_modified)]
OptionalSanitizedStr = Annotated[
    str | None, BeforeValidator(_sanitize_optional_description)
]
