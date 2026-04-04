import pytest
from pydantic import ValidationError

from backend.schemas.system import HealthResponseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.unit


def test_health_response_schema_dump():
    schema = HealthResponseSchema(status="Success")
    dumped = schema.model_dump(by_alias=True)
    assert dumped == {STD_JSON.STATUS: "Success"}


def test_health_response_schema_missing_required_fields():
    with pytest.raises(ValidationError):
        HealthResponseSchema()


def test_health_response_schema_model_validate_round_trip():
    data = {STD_JSON.STATUS: "Success"}
    schema = HealthResponseSchema.model_validate(data)
    assert schema.status == "Success"


def test_health_response_schema_has_expected_fields():
    field_aliases = {
        field.alias or name for name, field in HealthResponseSchema.model_fields.items()
    }
    assert field_aliases == {STD_JSON.STATUS}
