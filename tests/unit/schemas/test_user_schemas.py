import pytest
from pydantic import ValidationError

from backend.schemas.users import (
    EmailValidationResponseSchema,
    ForgotPasswordResponseSchema,
    LoginRedirectResponseSchema,
    RegisterResponseSchema,
    ResetPasswordResponseSchema,
    UserSchema,
    UtubSummaryItemSchema,
    UtubSummaryListSchema,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.user_strs import REDIRECT_URL

pytestmark = pytest.mark.unit


def test_user_schema_dump():
    schema = UserSchema(id=1, username="alice")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {M.ID: 1, M.USERNAME: "alice"}


def test_user_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UserSchema()


def test_utub_summary_item_schema_dump():
    schema = UtubSummaryItemSchema(id=2, name="My UTub", member_role="creator")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {M.ID: 2, M.NAME: "My UTub", M.MEMBER_ROLE: "creator"}


def test_utub_summary_item_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubSummaryItemSchema()


def test_utub_summary_list_schema_dump():
    schema = UtubSummaryListSchema(
        utubs=[
            UtubSummaryItemSchema(id=1, name="UTub A", member_role="creator"),
            UtubSummaryItemSchema(id=2, name="UTub B", member_role="editor"),
        ]
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {
        M.UTUBS: [
            {M.ID: 1, M.NAME: "UTub A", M.MEMBER_ROLE: "creator"},
            {M.ID: 2, M.NAME: "UTub B", M.MEMBER_ROLE: "editor"},
        ]
    }


def test_utub_summary_list_schema_validate_from_dict():
    data = {
        M.UTUBS: [
            {M.ID: 1, M.NAME: "UTub A", M.MEMBER_ROLE: "creator"},
        ]
    }
    schema = UtubSummaryListSchema.model_validate(data)
    assert schema.utubs[0].id == 1
    assert schema.utubs[0].name == "UTub A"
    assert schema.utubs[0].member_role == "creator"


def test_utub_summary_list_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubSummaryListSchema()


def test_login_redirect_response_schema_dump():
    schema = LoginRedirectResponseSchema(redirect_url="/home")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {REDIRECT_URL: "/home"}


def test_login_redirect_response_schema_missing_field():
    with pytest.raises(ValidationError):
        LoginRedirectResponseSchema()


def test_login_redirect_response_schema_model_validate_round_trip():
    data = {REDIRECT_URL: "/home"}
    schema = LoginRedirectResponseSchema.model_validate(data)
    assert schema.redirect_url == "/home"


# --- RegisterResponseSchema tests ---


def test_register_response_schema_dump():
    schema = RegisterResponseSchema(status="Success", message="User registered.")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {STD_JSON.STATUS: "Success", STD_JSON.MESSAGE: "User registered."}


def test_register_response_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        RegisterResponseSchema()


def test_register_response_schema_model_validate_round_trip():
    data = {STD_JSON.STATUS: "Success", STD_JSON.MESSAGE: "User registered."}
    schema = RegisterResponseSchema.model_validate(data)
    assert schema.status == "Success"
    assert schema.message == "User registered."


def test_register_response_schema_has_expected_fields():
    field_aliases = {
        field.alias or name
        for name, field in RegisterResponseSchema.model_fields.items()
    }
    assert field_aliases == {STD_JSON.STATUS, STD_JSON.MESSAGE}


# --- ForgotPasswordResponseSchema tests ---


def test_forgot_password_response_schema_dump():
    schema = ForgotPasswordResponseSchema(status="Success", message="Email sent.")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {STD_JSON.STATUS: "Success", STD_JSON.MESSAGE: "Email sent."}


def test_forgot_password_response_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        ForgotPasswordResponseSchema()


def test_forgot_password_response_schema_has_expected_fields():
    field_aliases = {
        field.alias or name
        for name, field in ForgotPasswordResponseSchema.model_fields.items()
    }
    assert field_aliases == {STD_JSON.STATUS, STD_JSON.MESSAGE}


# --- ResetPasswordResponseSchema tests ---


def test_reset_password_response_schema_dump():
    schema = ResetPasswordResponseSchema(status="Success", message="Password reset.")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {STD_JSON.STATUS: "Success", STD_JSON.MESSAGE: "Password reset."}


def test_reset_password_response_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        ResetPasswordResponseSchema()


def test_reset_password_response_schema_has_expected_fields():
    field_aliases = {
        field.alias or name
        for name, field in ResetPasswordResponseSchema.model_fields.items()
    }
    assert field_aliases == {STD_JSON.STATUS, STD_JSON.MESSAGE}


# --- EmailValidationResponseSchema tests ---


def test_email_validation_response_schema_dump():
    schema = EmailValidationResponseSchema(
        status="Success", message="Validation email sent."
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {
        STD_JSON.STATUS: "Success",
        STD_JSON.MESSAGE: "Validation email sent.",
    }


def test_email_validation_response_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        EmailValidationResponseSchema()


def test_email_validation_response_schema_has_expected_fields():
    field_aliases = {
        field.alias or name
        for name, field in EmailValidationResponseSchema.model_fields.items()
    }
    assert field_aliases == {STD_JSON.STATUS, STD_JSON.MESSAGE}
