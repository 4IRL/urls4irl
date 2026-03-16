import pytest
from pydantic import ValidationError

from backend.schemas.tags import UtubTagOnAddDeleteSchema, UtubTagSchema
from backend.utils.strings.model_strs import MODELS as M

pytestmark = pytest.mark.unit


def test_utub_tag_schema_dump():
    schema = UtubTagSchema(id=1, tag_string="foo")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {M.ID: 1, M.TAG_STRING: "foo", M.TAG_APPLIED: 0}


def test_utub_tag_on_add_delete_schema_dump():
    schema = UtubTagOnAddDeleteSchema(utub_tag_id=5, tag_string="bar")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {M.UTUB_TAG_ID: 5, M.TAG_STRING: "bar"}


class _MockTag:
    id = 3
    tag_string = "hello"


def test_utub_tag_on_add_delete_schema_from_orm_tag():
    tag = _MockTag()
    schema = UtubTagOnAddDeleteSchema.from_orm_tag(tag)
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {M.UTUB_TAG_ID: 3, M.TAG_STRING: "hello"}


def test_utub_tag_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubTagSchema()


def test_utub_tag_on_add_delete_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubTagOnAddDeleteSchema()
