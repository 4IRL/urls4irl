from __future__ import annotations
from pydantic import ValidationError


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
        errors.setdefault(field_name, []).append(msg)
    return errors
