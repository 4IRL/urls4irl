import pytest
from pydantic import ValidationError

from backend.utils.strings.model_strs import MODELS as M

pytestmark = pytest.mark.unit

_MEMBER = {M.ID: 1, M.USERNAME: "alice"}
_TAG = {M.ID: 10, M.TAG_STRING: "python", M.TAG_APPLIED: 3}
_URL = {
    M.UTUB_URL_ID: 5,
    M.URL_STRING: "https://example.com",
    M.URL_TAG_IDS: [10],
    M.URL_TITLE: "Example",
    M.CAN_DELETE: True,
}
_UTUB_DICT = {
    M.ID: 42,
    M.NAME: "My UTub",
    M.CREATED_BY: 1,
    M.CREATED_AT: "01/01/2025 00:00:00",
    M.DESCRIPTION: "A test UTub",
    M.MEMBERS: [_MEMBER],
    M.URLS: [_URL],
    M.TAGS: [_TAG],
    M.IS_CREATOR: True,
    M.CURRENT_USER: "1",
}


def test_utub_detail_schema_dump():
    from backend.schemas.utubs import UtubDetailSchema

    schema = UtubDetailSchema.model_validate(_UTUB_DICT)
    dumped = schema.model_dump(by_alias=True)
    assert dumped[M.ID] == 42
    assert dumped[M.NAME] == "My UTub"
    assert dumped[M.CREATED_BY] == 1
    assert dumped[M.CREATED_AT] == "01/01/2025 00:00:00"
    assert dumped[M.DESCRIPTION] == "A test UTub"
    assert dumped[M.IS_CREATOR] is True
    assert dumped[M.CURRENT_USER] == "1"


def test_utub_detail_schema_nested_members():
    from backend.schemas.utubs import UtubDetailSchema

    schema = UtubDetailSchema.model_validate(_UTUB_DICT)
    dumped = schema.model_dump(by_alias=True)
    assert len(dumped[M.MEMBERS]) == 1
    assert dumped[M.MEMBERS][0] == {M.ID: 1, M.USERNAME: "alice"}


def test_utub_detail_schema_nested_urls():
    from backend.schemas.utubs import UtubDetailSchema

    schema = UtubDetailSchema.model_validate(_UTUB_DICT)
    dumped = schema.model_dump(by_alias=True)
    assert len(dumped[M.URLS]) == 1
    url = dumped[M.URLS][0]
    assert url[M.UTUB_URL_ID] == 5
    assert url[M.URL_STRING] == "https://example.com"
    assert url[M.URL_TAG_IDS] == [10]
    assert url[M.CAN_DELETE] is True


def test_utub_detail_schema_nested_tags():
    from backend.schemas.utubs import UtubDetailSchema

    schema = UtubDetailSchema.model_validate(_UTUB_DICT)
    dumped = schema.model_dump(by_alias=True)
    assert len(dumped[M.TAGS]) == 1
    tag = dumped[M.TAGS][0]
    assert tag[M.ID] == 10
    assert tag[M.TAG_STRING] == "python"
    assert tag[M.TAG_APPLIED] == 3


def test_utub_detail_schema_missing_required_fields():
    from backend.schemas.utubs import UtubDetailSchema

    with pytest.raises(ValidationError):
        UtubDetailSchema.model_validate({})


def test_utub_detail_schema_empty_lists():
    from backend.schemas.utubs import UtubDetailSchema

    data = {**_UTUB_DICT, M.MEMBERS: [], M.URLS: [], M.TAGS: []}
    schema = UtubDetailSchema.model_validate(data)
    assert schema.members == []
    assert schema.urls == []
    assert schema.tags == []
