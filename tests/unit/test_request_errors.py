import pytest
from pydantic import BaseModel, ValidationError

from backend.api_common.request_errors import pydantic_errors_to_dict

pytestmark = pytest.mark.unit


class _SampleSchema(BaseModel):
    username: str
    age: int


def _validation_error_for(data: dict) -> ValidationError:
    with pytest.raises(ValidationError) as exc_info:
        _SampleSchema.model_validate(data)
    return exc_info.value


def test_missing_required_field_produces_field_key():
    """
    GIVEN a ValidationError for a single missing required field
    WHEN pydantic_errors_to_dict is called
    THEN the result contains that field name as the key with a non-empty error list
    """
    validation_error = _validation_error_for({"age": 1})
    result = pydantic_errors_to_dict(validation_error)

    assert "username" in result
    assert isinstance(result["username"], list)
    assert len(result["username"]) > 0


def test_multiple_errors_on_different_fields_produce_separate_keys():
    """
    GIVEN a ValidationError with errors on multiple different fields
    WHEN pydantic_errors_to_dict is called
    THEN each field has its own key in the result
    """
    validation_error = _validation_error_for({})
    result = pydantic_errors_to_dict(validation_error)

    assert "username" in result
    assert "age" in result


def test_multiple_errors_on_same_field_accumulate_under_one_key():
    """
    GIVEN a schema with a list field that has multiple invalid entries
    WHEN pydantic_errors_to_dict is called
    THEN all error messages for that field are accumulated under one key
    """

    class _ListSchema(BaseModel):
        items: list[int]

    with pytest.raises(ValidationError) as exc_info:
        _ListSchema.model_validate({"items": ["a", "b"]})
    validation_error = exc_info.value

    result = pydantic_errors_to_dict(validation_error)
    assert "items" in result
    assert len(result["items"]) >= 2
