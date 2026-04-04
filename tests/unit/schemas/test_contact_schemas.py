import pytest
from pydantic import ValidationError

from backend.schemas.contact import ContactResponseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.unit


def test_contact_response_schema_dump():
    schema = ContactResponseSchema(status="Success", message="Message sent.")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {STD_JSON.STATUS: "Success", STD_JSON.MESSAGE: "Message sent."}


def test_contact_response_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        ContactResponseSchema()


def test_contact_response_schema_model_validate_round_trip():
    data = {STD_JSON.STATUS: "Success", STD_JSON.MESSAGE: "Message sent."}
    schema = ContactResponseSchema.model_validate(data)
    assert schema.status == "Success"
    assert schema.message == "Message sent."


def test_contact_response_schema_has_expected_fields():
    field_aliases = {
        field.alias or name
        for name, field in ContactResponseSchema.model_fields.items()
    }
    assert field_aliases == {STD_JSON.STATUS, STD_JSON.MESSAGE}
