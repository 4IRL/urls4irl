import pytest
from pydantic import ValidationError

from backend.schemas.tags import UtubTagOnAddDeleteSchema, UtubTagSchema
from backend.utils.strings.model_strs import MODELS

pytestmark = pytest.mark.unit


def test_utub_tag_schema_dump():
    schema = UtubTagSchema(id=1, tag_string="foo")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {MODELS.ID: 1, MODELS.TAG_STRING: "foo", MODELS.TAG_APPLIED: 0}


def test_utub_tag_on_add_delete_schema_dump():
    schema = UtubTagOnAddDeleteSchema(utub_tag_id=5, tag_string="bar")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {MODELS.UTUB_TAG_ID: 5, MODELS.TAG_STRING: "bar"}


class _MockTag:
    id = 3
    tag_string = "hello"


def test_utub_tag_on_add_delete_schema_from_orm_tag():
    tag = _MockTag()
    schema = UtubTagOnAddDeleteSchema.from_orm_tag(tag)
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {MODELS.UTUB_TAG_ID: 3, MODELS.TAG_STRING: "hello"}


def test_utub_tag_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubTagSchema()


def test_utub_tag_on_add_delete_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        UtubTagOnAddDeleteSchema()
