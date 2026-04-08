from __future__ import annotations

import pytest
from pydantic import BaseModel

from backend.cli.openapi import _schema_has_status_property, _schema_is_empty

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
        assert _schema_has_status_property(DirectStatusSchema) is True

    def test_inherited_status_returns_true(self) -> None:
        """
        GIVEN a schema that inherits a 'status' field from a parent
        WHEN _schema_has_status_property is called
        THEN it returns True
        """
        assert _schema_has_status_property(InheritedStatusSchema) is True

    def test_no_status_returns_false(self) -> None:
        """
        GIVEN a schema without a 'status' field
        WHEN _schema_has_status_property is called
        THEN it returns False
        """
        assert _schema_has_status_property(NoStatusSchema) is False


class TestSchemaIsEmpty:
    """Tests for _schema_is_empty helper."""

    def test_empty_schema_returns_true(self) -> None:
        """
        GIVEN a schema with no fields
        WHEN _schema_is_empty is called
        THEN it returns True
        """
        assert _schema_is_empty(EmptySchema) is True

    def test_non_empty_schema_returns_false(self) -> None:
        """
        GIVEN a schema with at least one field
        WHEN _schema_is_empty is called
        THEN it returns False
        """
        assert _schema_is_empty(NonEmptySchema) is False
