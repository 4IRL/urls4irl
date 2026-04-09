from __future__ import annotations

import pytest
from pydantic import BaseModel

from backend.cli.openapi import (
    _humanize_class_name,
    _response_description,
    _schema_has_status_property,
    _schema_is_empty,
    _strip_auto_titles,
)

pytestmark = [pytest.mark.unit, pytest.mark.cli]


class DirectStatusSchema(BaseModel):
    status: str


class InheritedStatusSchema(DirectStatusSchema):
    pass


class NoStatusSchema(BaseModel):
    name: str


class EmptySchema(BaseModel):
    pass


class NonEmptySchema(BaseModel):
    name: str


class TestSchemaHasStatusProperty:
    """Tests for _schema_has_status_property helper."""

    def test_direct_status_returns_true(self) -> None:
        """
        GIVEN a schema with a direct 'status' field
        WHEN _schema_has_status_property is called
        THEN it returns True
        """
        assert _schema_has_status_property(DirectStatusSchema)

    def test_inherited_status_returns_true(self) -> None:
        """
        GIVEN a schema that inherits a 'status' field from a parent
        WHEN _schema_has_status_property is called
        THEN it returns True
        """
        assert _schema_has_status_property(InheritedStatusSchema)

    def test_no_status_returns_false(self) -> None:
        """
        GIVEN a schema without a 'status' field
        WHEN _schema_has_status_property is called
        THEN it returns False
        """
        assert not _schema_has_status_property(NoStatusSchema)


class TestSchemaIsEmpty:
    """Tests for _schema_is_empty helper."""

    def test_empty_schema_returns_true(self) -> None:
        """
        GIVEN a schema with no fields
        WHEN _schema_is_empty is called
        THEN it returns True
        """
        assert _schema_is_empty(EmptySchema)

    def test_non_empty_schema_returns_false(self) -> None:
        """
        GIVEN a schema with at least one field
        WHEN _schema_is_empty is called
        THEN it returns False
        """
        assert not _schema_is_empty(NonEmptySchema)


class SchemaWithDocstring(BaseModel):
    """Summary of this schema."""

    name: str


class SchemaWithoutDocstring(BaseModel):
    __doc__ = None
    name: str


class TestHumanizeClassName:
    """Tests for _humanize_class_name helper."""

    def test_strips_response_schema_suffix(self) -> None:
        """
        GIVEN a class name ending in 'ResponseSchema'
        WHEN _humanize_class_name is called
        THEN the suffix is stripped and the result is humanized
        """
        assert (
            _humanize_class_name("UtubSummaryListResponseSchema") == "UTub summary list"
        )

    def test_strips_schema_suffix(self) -> None:
        """
        GIVEN a class name ending in 'Schema' (but not 'ResponseSchema')
        WHEN _humanize_class_name is called
        THEN the 'Schema' suffix is stripped
        """
        assert _humanize_class_name("UtubSummarySchema") == "UTub summary"

    def test_strips_bare_response_suffix(self) -> None:
        """
        GIVEN a class name ending in bare 'Response'
        WHEN _humanize_class_name is called
        THEN the 'Response' suffix is stripped
        """
        assert _humanize_class_name("UtubSummaryResponse") == "UTub summary"

    def test_acronym_map_applied_mid_name(self) -> None:
        """
        GIVEN a class name containing tokens in the ACRONYM_MAP
        WHEN _humanize_class_name is called
        THEN acronyms are uppercased correctly
        """
        assert _humanize_class_name("UrlValidationSchema") == "URL validation"

    def test_api_acronym_applied(self) -> None:
        """
        GIVEN a class name containing 'Api'
        WHEN _humanize_class_name is called
        THEN 'Api' is replaced with 'API'
        """
        assert _humanize_class_name("ApiKeySchema") == "API key"

    def test_id_acronym_applied(self) -> None:
        """
        GIVEN a class name containing 'Id'
        WHEN _humanize_class_name is called
        THEN 'Id' is replaced with 'ID'
        """
        assert _humanize_class_name("UserIdSchema") == "User ID"

    def test_single_word_no_suffix(self) -> None:
        """
        GIVEN a single-word class name with no recognized suffix
        WHEN _humanize_class_name is called
        THEN the name is returned as-is
        """
        assert _humanize_class_name("Summary") == "Summary"

    def test_first_token_capitalized_rest_lowercased(self) -> None:
        """
        GIVEN a multi-token PascalCase name with no acronyms
        WHEN _humanize_class_name is called
        THEN the first token stays capitalized and later tokens are lowercased
        """
        assert _humanize_class_name("MemberListResponseSchema") == "Member list"


class TestResponseDescription:
    """Tests for _response_description helper."""

    def test_error_status_returns_http_phrase(self) -> None:
        """
        GIVEN a status code >= 400 that is in HTTP_STATUS_DESCRIPTIONS
        WHEN _response_description is called
        THEN the HTTP phrase is returned
        """
        result = _response_description(400, NonEmptySchema)
        assert result == "Bad request"

    def test_unmapped_error_status_returns_error(self) -> None:
        """
        GIVEN a status code >= 400 that is NOT in HTTP_STATUS_DESCRIPTIONS
        WHEN _response_description is called
        THEN 'Error' is returned as fallback
        """
        result = _response_description(418, NonEmptySchema)
        assert result == "Error"

    def test_success_with_docstring_returns_docstring(self) -> None:
        """
        GIVEN a success status code and a schema with a __doc__
        WHEN _response_description is called
        THEN the stripped docstring is returned
        """
        result = _response_description(200, SchemaWithDocstring)
        assert result == "Summary of this schema."

    def test_success_without_docstring_delegates_to_humanize(self) -> None:
        """
        GIVEN a success status code and a schema without a __doc__
        WHEN _response_description is called
        THEN it delegates to _humanize_class_name
        """
        result = _response_description(200, SchemaWithoutDocstring)
        assert result == "Schema without docstring"


class TestStripAutoTitles:
    """Tests for _strip_auto_titles helper."""

    def test_strip_auto_titles_removes_property_titles(self) -> None:
        """
        GIVEN a schema dict with title keys at root, property, nested $defs,
              allOf/anyOf/oneOf sub-schemas, and array items
        WHEN _strip_auto_titles is called
        THEN all title keys are removed
        """
        schema = {
            "title": "RootTitle",
            "type": "object",
            "properties": {
                "name": {"title": "Name", "type": "string"},
                "age": {"title": "Age", "type": "integer"},
            },
            "$defs": {
                "Nested": {
                    "title": "Nested",
                    "type": "object",
                    "properties": {
                        "value": {"title": "Value", "type": "string"},
                    },
                }
            },
            "allOf": [{"title": "AllOfEntry", "type": "object"}],
            "anyOf": [{"title": "AnyOfEntry", "type": "string"}],
            "oneOf": [{"title": "OneOfEntry", "type": "integer"}],
            "items": {"title": "ItemTitle", "type": "string"},
        }

        _strip_auto_titles(schema)

        # Root title removed
        assert "title" not in schema

        # Property titles removed
        for prop in schema["properties"].values():
            assert "title" not in prop

        # $defs titles removed (recursively)
        nested = schema["$defs"]["Nested"]
        assert "title" not in nested
        for prop in nested["properties"].values():
            assert "title" not in prop

        # allOf/anyOf/oneOf titles removed
        assert "title" not in schema["allOf"][0]
        assert "title" not in schema["anyOf"][0]
        assert "title" not in schema["oneOf"][0]

        # items title removed
        assert "title" not in schema["items"]

    def test_strip_auto_titles_preserves_non_title_keys(self) -> None:
        """
        GIVEN a schema dict with various non-title keys
        WHEN _strip_auto_titles is called
        THEN non-title keys are preserved unchanged
        """
        schema = {
            "title": "Root",
            "type": "object",
            "description": "A description",
            "properties": {
                "name": {"title": "Name", "type": "string", "minLength": 1},
            },
        }

        _strip_auto_titles(schema)

        assert schema["type"] == "object"
        assert schema["description"] == "A description"
        assert schema["properties"]["name"]["type"] == "string"
        assert schema["properties"]["name"]["minLength"] == 1

    def test_strip_auto_titles_handles_empty_schema(self) -> None:
        """
        GIVEN an empty schema dict
        WHEN _strip_auto_titles is called
        THEN it completes without error
        """
        schema: dict[str, object] = {}
        _strip_auto_titles(schema)
        assert schema == {}
