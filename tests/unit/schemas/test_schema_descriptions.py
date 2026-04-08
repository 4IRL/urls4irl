from __future__ import annotations

import pytest
from pydantic import BaseModel

import backend.schemas as schema_module
import backend.schemas.requests as request_schema_module
from backend.schemas.errors import ErrorResponse

pytestmark = pytest.mark.unit

# Collect response schemas from __all__ (filter to BaseModel subclasses)
_response_schemas = [
    cls
    for name in schema_module.__all__
    if isinstance(cls := getattr(schema_module, name), type)
    and issubclass(cls, BaseModel)
]

# Collect request schemas from __all__ (filter to BaseModel subclasses)
_request_schemas = [
    cls
    for name in request_schema_module.__all__
    if isinstance(cls := getattr(request_schema_module, name), type)
    and issubclass(cls, BaseModel)
]

# ErrorResponse is not in __all__, add it explicitly
_all_raw_schemas = _response_schemas + _request_schemas + [ErrorResponse]

# Deduplicate by class identity to handle any future aliases
_seen: set[int] = set()
ALL_SCHEMAS = [
    cls for cls in _all_raw_schemas if not (id(cls) in _seen or _seen.add(id(cls)))
]


def _assert_all_properties_described(
    properties: dict[str, dict], schema_label: str
) -> None:
    """Assert every property in a JSON Schema properties dict has a description.

    Handles plain fields, bare ``$ref`` fields (missing description), and
    ``allOf``-wrapped ``$ref`` fields (Pydantic wraps in allOf when a
    description is present alongside a reference).
    """
    for field_name, field_schema in properties.items():
        # A bare $ref with no sibling keys means Pydantic had no description
        # to attach — this is a missing-description case.
        if "$ref" in field_schema and "description" not in field_schema:
            raise AssertionError(
                f"{schema_label}.{field_name} uses "
                "$ref but is missing a 'description' in JSON Schema"
            )
        # allOf with $ref entries: Pydantic uses this when a description IS
        # present alongside a schema reference.  Verify description exists.
        if "allOf" in field_schema and all(
            "$ref" in entry for entry in field_schema["allOf"]
        ):
            assert "description" in field_schema, (
                f"{schema_label}.{field_name} uses allOf/"
                "$ref but is missing a 'description' in JSON Schema"
            )
            continue
        # Standard scalar / list / etc. field
        assert (
            "description" in field_schema
        ), f"{schema_label}.{field_name} is missing a 'description' in JSON Schema"


@pytest.mark.parametrize(
    "schema_cls",
    ALL_SCHEMAS,
    ids=lambda cls: cls.__name__,
)
def test_all_schema_fields_have_description(schema_cls: type[BaseModel]) -> None:
    """Every field in every schema must have a 'description' key in the JSON Schema output."""
    json_schema = schema_cls.model_json_schema()

    # Check top-level properties
    properties = json_schema.get("properties", {})
    _assert_all_properties_described(properties, schema_cls.__name__)

    # Check nested schemas in $defs
    defs = json_schema.get("$defs", {})
    for def_name, def_schema in defs.items():
        nested_properties = def_schema.get("properties", {})
        _assert_all_properties_described(nested_properties, f"$defs[{def_name}]")
