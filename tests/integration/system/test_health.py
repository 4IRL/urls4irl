from flask import Flask
import pytest

from backend.schemas.system import HealthResponseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.cli


def test_health_response_conforms_to_schema(app: Flask):
    """
    GIVEN the health endpoint at /health
    WHEN a GET request is made
    THEN ensure the 200 JSON response conforms to HealthResponseSchema
    """
    with app.test_client() as health_client:
        response = health_client.get("/health")

    assert response.status_code == 200
    response_json = response.json

    # Validate response conforms to declared schema
    validated = HealthResponseSchema.model_validate(response_json)
    assert validated is not None

    # Verify response keys match schema's aliased field names
    expected_keys = {
        field_info.alias or field_name
        for field_name, field_info in HealthResponseSchema.model_fields.items()
    }
    assert set(response_json.keys()) == expected_keys

    # Verify status key is present (health has only status, no message)
    assert STD_JSON.STATUS in response_json
