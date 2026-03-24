import pytest
from pydantic import BaseModel, Field, ValidationError

from backend.api_common.request_errors import (
    INVALID_EMAIL_STR,
    _humanize_error_message,
    max_length_message,
    min_length_message,
    pydantic_errors_to_dict,
)
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR

pytestmark = pytest.mark.unit


class TestHumanizeFieldRequired:
    def test_field_required_maps_to_human_message(self):
        assert _humanize_error_message("Field required") == FIELD_REQUIRED_STR

    def test_min_length_1_maps_to_required(self):
        assert (
            _humanize_error_message("String should have at least 1 character")
            == FIELD_REQUIRED_STR
        )

    def test_min_length_1_plural_maps_to_required(self):
        assert (
            _humanize_error_message("String should have at least 1 characters")
            == FIELD_REQUIRED_STR
        )


class TestHumanizeMinLength:
    def test_min_length_n_maps_to_human_message(self):
        result = _humanize_error_message("String should have at least 12 characters")
        assert result == min_length_message(12)

    def test_min_length_3_maps_to_human_message(self):
        result = _humanize_error_message("String should have at least 3 characters")
        assert result == min_length_message(3)


class TestHumanizeMaxLength:
    def test_max_length_maps_to_human_message(self):
        result = _humanize_error_message("String should have at most 20 characters")
        assert result == max_length_message(20)

    def test_max_length_singular_maps_to_human_message(self):
        result = _humanize_error_message("String should have at most 1 character")
        assert result == max_length_message(1)


class TestHumanizeEmailError:
    def test_email_error_maps_to_human_message(self):
        raw = (
            "value is not a valid email address: An email address must have an @-sign."
        )
        assert _humanize_error_message(raw) == INVALID_EMAIL_STR

    def test_email_error_different_suffix_maps_to_human_message(self):
        raw = "value is not a valid email address: The part after the @-sign is not valid."
        assert _humanize_error_message(raw) == INVALID_EMAIL_STR


class TestHumanizePassthrough:
    def test_custom_messages_pass_through(self):
        custom_messages = [
            "Emails do not match.",
            "Passwords are not identical.",
            "Invalid input, please try again.",
            "Some completely unknown message",
        ]
        for msg in custom_messages:
            assert _humanize_error_message(msg) == msg


class TestPydanticErrorsToDictAppliesHumanization:
    def test_pydantic_errors_to_dict_applies_humanization(self):
        class _MinLengthSchema(BaseModel):
            name: str = Field(min_length=1)

        with pytest.raises(ValidationError) as exc_info:
            _MinLengthSchema.model_validate({"name": ""})

        result = pydantic_errors_to_dict(exc_info.value)
        assert "name" in result
        assert FIELD_REQUIRED_STR in result["name"]

    def test_pydantic_errors_to_dict_humanizes_field_required(self):
        class _RequiredSchema(BaseModel):
            email: str

        with pytest.raises(ValidationError) as exc_info:
            _RequiredSchema.model_validate({})

        result = pydantic_errors_to_dict(exc_info.value)
        assert "email" in result
        assert FIELD_REQUIRED_STR in result["email"]
