from flask import Flask
import pytest

from backend.schemas.system import HealthResponseSchema
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from tests.integration.utils import assert_response_conforms_to_schema

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

    assert_response_conforms_to_schema(
        response_json, HealthResponseSchema, {STD_JSON.STATUS}
    )
