from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.schemas.users import (
    EmailValidationResponseSchema,
    ForgotPasswordResponseSchema,
    LoginRedirectResponseSchema,
    OwnershipTransferredResponseSchema,
    RegisterResponseSchema,
    ResetPasswordResponseSchema,
    UserSchema,
    UtubListPreferencesSchema,
    UtubMemberSchema,
    UtubSummaryItemSchema,
    UtubSummaryListSchema,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.user_strs import REDIRECT_URL
from backend.utils.strings.utub_strs import UTUB_ID

pytestmark = pytest.mark.unit


def test_user_schema_dump():
    schema = UserSchema(id=1, username="alice")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {MODELS.ID: 1, MODELS.USERNAME: "alice"}


def test_user_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UserSchema()


_CREATED = datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=timezone.utc)
_UPDATED = datetime(2026, 2, 3, 4, 5, 6, 789012, tzinfo=timezone.utc)
_OPENED = datetime(2026, 3, 4, 5, 6, 7, 890123, tzinfo=timezone.utc)
_PREFERENCES_DUMP = {
    MODELS.UTUB_SORT: "recent_activity",
    MODELS.SHOW_ROW_COUNTS: False,
    MODELS.SHOW_LIST_TOTALS: True,
}


def _item(item_id: int, name: str, role: str, opened: datetime | None):
    return UtubSummaryItemSchema(
        id=item_id,
        name=name,
        member_role=role,
        is_locked=False,
        url_count=3,
        member_count=2,
        created_at=_CREATED,
        last_updated=_UPDATED,
        last_opened_at=opened,
    )


def _item_dump(item_id: int, name: str, role: str, opened: str | None):
    return {
        MODELS.ID: item_id,
        MODELS.NAME: name,
        MODELS.MEMBER_ROLE: role,
        MODELS.IS_LOCKED: False,
        MODELS.URL_COUNT: 3,
        MODELS.MEMBER_COUNT: 2,
        MODELS.CREATED_AT: "2026-01-02T03:04:05.678+00:00",
        MODELS.LAST_UPDATED: "2026-02-03T04:05:06.789+00:00",
        MODELS.LAST_OPENED_AT: opened,
    }


def test_utub_summary_item_schema_dump():
    dumped = _item(2, "My UTub", "creator", _OPENED).model_dump(by_alias=True)
    assert dumped == _item_dump(
        2, "My UTub", "creator", "2026-03-04T05:06:07.890+00:00"
    )


def test_utub_summary_item_schema_null_last_opened_key_always_present():
    dumped = _item(2, "My UTub", "creator", None).model_dump(by_alias=True)
    assert MODELS.LAST_OPENED_AT in dumped
    assert dumped[MODELS.LAST_OPENED_AT] is None


def test_utub_summary_item_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubSummaryItemSchema()
    with pytest.raises(ValidationError):
        UtubSummaryItemSchema(
            id=2, name="My UTub", member_role="creator", is_locked=False
        )


def test_utub_summary_list_schema_dump():
    schema = UtubSummaryListSchema(
        utubs=[
            _item(1, "UTub A", "creator", None),
            _item(2, "UTub B", "editor", None),
        ],
        preferences=UtubListPreferencesSchema(
            utub_sort="recent_activity", show_row_counts=False, show_list_totals=True
        ),
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {
        MODELS.UTUBS: [
            _item_dump(1, "UTub A", "creator", None),
            _item_dump(2, "UTub B", "editor", None),
        ],
        MODELS.TRASH_COUNT: 0,
        MODELS.PREFERENCES: _PREFERENCES_DUMP,
    }


def test_utub_summary_list_schema_validate_from_dict():
    data = {
        MODELS.UTUBS: [_item_dump(1, "UTub A", "creator", None)],
        MODELS.PREFERENCES: _PREFERENCES_DUMP,
    }
    schema = UtubSummaryListSchema.model_validate(data)
    assert schema.utubs[0].id == 1
    assert schema.utubs[0].name == "UTub A"
    assert schema.utubs[0].member_role == "creator"
    assert schema.utubs[0].url_count == 3
    assert schema.preferences.utub_sort == "recent_activity"


def test_utub_summary_list_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubSummaryListSchema()
    with pytest.raises(ValidationError):
        UtubSummaryListSchema(utubs=[])


def test_utub_list_preferences_schema_rejects_unknown_sort():
    with pytest.raises(ValidationError):
        UtubListPreferencesSchema(
            utub_sort="bogus", show_row_counts=False, show_list_totals=True
        )


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


def test_ownership_transferred_response_schema_dump():
    schema = OwnershipTransferredResponseSchema(
        utub_id=7,
        new_owner=UtubMemberSchema(id=2, username="alice", member_role="creator"),
        previous_owner=UtubMemberSchema(id=1, username="bob", member_role="cocreator"),
    )
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {
        UTUB_ID: 7,
        MODELS.NEW_OWNER: {
            MODELS.ID: 2,
            MODELS.USERNAME: "alice",
            MODELS.MEMBER_ROLE: "creator",
        },
        MODELS.PREVIOUS_OWNER: {
            MODELS.ID: 1,
            MODELS.USERNAME: "bob",
            MODELS.MEMBER_ROLE: "cocreator",
        },
    }


def test_ownership_transferred_response_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        OwnershipTransferredResponseSchema()


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
