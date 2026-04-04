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


# --- Parametrized tests for status+message response schemas ---

STATUS_MESSAGE_SCHEMAS = pytest.mark.parametrize(
    "schema_class",
    [
        RegisterResponseSchema,
        ForgotPasswordResponseSchema,
        ResetPasswordResponseSchema,
        EmailValidationResponseSchema,
    ],
    ids=[
        "RegisterResponseSchema",
        "ForgotPasswordResponseSchema",
        "ResetPasswordResponseSchema",
        "EmailValidationResponseSchema",
    ],
)


@STATUS_MESSAGE_SCHEMAS
def test_status_message_schema_dump(schema_class):
    schema = schema_class(status="Success", message="Done.")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {STD_JSON.STATUS: "Success", STD_JSON.MESSAGE: "Done."}


@STATUS_MESSAGE_SCHEMAS
def test_status_message_schema_missing_required_fields(schema_class):
    with pytest.raises(ValidationError):
        schema_class()


@STATUS_MESSAGE_SCHEMAS
def test_status_message_schema_model_validate_round_trip(schema_class):
    data = {STD_JSON.STATUS: "Success", STD_JSON.MESSAGE: "Done."}
    schema = schema_class.model_validate(data)
    assert schema.status == "Success"
    assert schema.message == "Done."


@STATUS_MESSAGE_SCHEMAS
def test_status_message_schema_has_expected_fields(schema_class):
    field_aliases = {
        field.alias or name for name, field in schema_class.model_fields.items()
    }
    assert field_aliases == {STD_JSON.STATUS, STD_JSON.MESSAGE}
