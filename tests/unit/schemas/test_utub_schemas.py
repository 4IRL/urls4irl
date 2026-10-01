from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.schemas.utubs import UtubDetailSchema
from backend.utils.strings.model_strs import MODELS

pytestmark = pytest.mark.unit

_MEMBER = {MODELS.ID: 1, MODELS.USERNAME: "alice", MODELS.MEMBER_ROLE: "creator"}
_TAG = {MODELS.ID: 10, MODELS.TAG_STRING: "python", MODELS.TAG_APPLIED: 3}
_URL = {
    MODELS.UTUB_URL_ID: 5,
    MODELS.URL_STRING: "https://example.com",
    MODELS.URL_TAG_IDS: [10],
    MODELS.URL_TITLE: "Example",
    MODELS.CAN_DELETE: True,
    "addedAt": "2024-03-09T12:00:00+00:00",
    MODELS.ADDED_BY: 1,
}
_UTUB_DICT = {
    MODELS.ID: 42,
    MODELS.NAME: "My UTub",
    MODELS.CREATED_BY: 1,
    MODELS.CREATED_AT: datetime(2025, 1, 1, 0, 0, 0),
    MODELS.DESCRIPTION: "A test UTub",
    MODELS.MEMBERS: [_MEMBER],
    MODELS.URLS: [_URL],
    MODELS.TAGS: [_TAG],
    MODELS.IS_CREATOR: True,
    MODELS.IS_CO_CREATOR: False,
    MODELS.IS_LOCKED: False,
    MODELS.CURRENT_USER: 1,
}


def test_utub_detail_schema_dump():
    schema = UtubDetailSchema.model_validate(_UTUB_DICT)
    dumped = schema.model_dump(by_alias=True)
    assert dumped[MODELS.ID] == 42
    assert dumped[MODELS.NAME] == "My UTub"
    assert dumped[MODELS.CREATED_BY] == 1
    assert dumped[MODELS.CREATED_AT] == "2025-01-01T00:00:00"
    assert dumped[MODELS.DESCRIPTION] == "A test UTub"
    assert dumped[MODELS.IS_CREATOR] is True
    assert dumped[MODELS.IS_CO_CREATOR] is False
    assert dumped[MODELS.CURRENT_USER] == 1


def test_utub_detail_schema_nested_members():
    schema = UtubDetailSchema.model_validate(_UTUB_DICT)
    dumped = schema.model_dump(by_alias=True)
    assert len(dumped[MODELS.MEMBERS]) == 1
    assert dumped[MODELS.MEMBERS][0] == {
        MODELS.ID: 1,
        MODELS.USERNAME: "alice",
        MODELS.MEMBER_ROLE: "creator",
    }


def test_utub_detail_schema_nested_urls():
    schema = UtubDetailSchema.model_validate(_UTUB_DICT)
    dumped = schema.model_dump(by_alias=True)
    assert len(dumped[MODELS.URLS]) == 1
    url = dumped[MODELS.URLS][0]
    assert url[MODELS.UTUB_URL_ID] == 5
    assert url[MODELS.URL_STRING] == "https://example.com"
    assert url[MODELS.URL_TAG_IDS] == [10]
    assert url[MODELS.CAN_DELETE] is True
    assert url[MODELS.ADDED_BY] == 1


def test_utub_detail_schema_nested_tags():
    schema = UtubDetailSchema.model_validate(_UTUB_DICT)
    dumped = schema.model_dump(by_alias=True)
    assert len(dumped[MODELS.TAGS]) == 1
    tag = dumped[MODELS.TAGS][0]
    assert tag[MODELS.ID] == 10
    assert tag[MODELS.TAG_STRING] == "python"
    assert tag[MODELS.TAG_APPLIED] == 3


def test_utub_detail_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubDetailSchema.model_validate({})


def test_utub_detail_schema_empty_lists():
    data = {**_UTUB_DICT, MODELS.MEMBERS: [], MODELS.URLS: [], MODELS.TAGS: []}
    schema = UtubDetailSchema.model_validate(data)
    assert schema.members == []
    assert schema.urls == []
    assert schema.tags == []
