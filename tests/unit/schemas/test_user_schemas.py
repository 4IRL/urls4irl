import pytest
from pydantic import ValidationError

from backend.schemas.users import (
    UserSchema,
    UtubSummaryItemSchema,
    UtubSummaryListSchema,
)
from backend.utils.strings.model_strs import MODELS as M

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
