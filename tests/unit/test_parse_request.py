import pytest
from flask import Flask
from pydantic import BaseModel, Field

from backend.api_common.parse_request import parse_json_body

pytestmark = pytest.mark.unit


class _SimpleSchema(BaseModel):
    name: str = Field(min_length=1)
    count: int


@pytest.fixture()
def minimal_app():
    """Minimal Flask app with a test route decorated by parse_json_body."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    @flask_app.route("/test", methods=["POST"])
    @parse_json_body(
        _SimpleSchema,
        message="Invalid input",
        error_code=1,
    )
    def test_route(validated_request: _SimpleSchema):
        return {"name": validated_request.name, "count": validated_request.count}, 200

    return flask_app


def test_missing_json_body_returns_400(minimal_app: Flask):
    """
    GIVEN a route decorated with @parse_json_body
    WHEN the request has no JSON body
    THEN a 400 response is returned
    """
    with minimal_app.test_client() as client:
        response = client.post("/test")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["message"] == "Invalid input"


def test_valid_body_injects_validated_request(minimal_app: Flask):
    """
    GIVEN a route decorated with @parse_json_body
    WHEN the request has a valid JSON body
    THEN validated_request is injected and the route returns 200
    """
    with minimal_app.test_client() as client:
        response = client.post(
            "/test",
            json={"name": "hello", "count": 3},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["name"] == "hello"
    assert payload["count"] == 3


def test_invalid_body_returns_400_with_errors(minimal_app: Flask):
    """
    GIVEN a route decorated with @parse_json_body
    WHEN the request has a JSON body that fails schema validation
    THEN a 400 response is returned with an errors dict
    """
    with minimal_app.test_client() as client:
        response = client.post(
            "/test",
            json={"count": "not-a-number"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "errors" in payload
    assert isinstance(payload["errors"], dict)
    # "name" is missing, "count" has wrong type
    assert "name" in payload["errors"] or "count" in payload["errors"]
