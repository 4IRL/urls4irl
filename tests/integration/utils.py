from __future__ import annotations

from typing import Any, Type

from backend.schemas.base import BaseSchema


def assert_response_conforms_to_schema(
    response_json: dict[str, Any],
    schema_class: Type[BaseSchema],
    expected_keys: set[str],
) -> None:
    """Validate that a JSON response conforms to a Pydantic response schema.

    Performs three checks:
    1. ``model_validate`` succeeds (raises ``ValidationError`` on failure).
    2. Response keys exactly match the schema's aliased field names.
    3. All ``expected_keys`` are present in the response.

    Args:
        response_json: The parsed JSON body from the Flask test response.
        schema_class: The Pydantic schema class to validate against.
        expected_keys: Keys that must appear in the response (typically
            constants like ``STD_JSON.STATUS`` and ``STD_JSON.MESSAGE``).
    """
    # Validate response conforms to declared schema
    schema_class.model_validate(response_json)

    # Verify response keys match schema's aliased field names
    aliased_keys = {
        field_info.alias or field_name
        for field_name, field_info in schema_class.model_fields.items()
    }
    assert set(response_json.keys()) == aliased_keys

    # Verify expected keys are present
    for key in expected_keys:
        assert key in response_json
