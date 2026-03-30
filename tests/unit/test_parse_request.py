import pytest
from flask import Flask

from backend.api_common.parse_request import api_route
from backend.schemas.requests.splash import LoginRequest

pytestmark = pytest.mark.unit


@pytest.fixture()
def minimal_app():
    """Minimal Flask app with a test route decorated by @api_route."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    @flask_app.route("/test", methods=["POST"])
    @api_route(
        request_schema=LoginRequest,
        response_schema=None,
        error_message="Invalid input",
        error_code=1,
    )
    def test_route(validated_request: LoginRequest):
        return {"username": validated_request.username}, 200

    return flask_app


def test_missing_json_body_returns_400(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route
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
    GIVEN a route decorated with @api_route
    WHEN the request has a valid JSON body
    THEN validated_request is injected and the route returns 200
    """
    with minimal_app.test_client() as client:
        response = client.post(
            "/test",
            json={"username": "testuser", "password": "validpassword1"},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["username"] == "testuser"


def test_invalid_body_returns_400_with_errors(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route
    WHEN the request has a JSON body that fails schema validation
    THEN a 400 response is returned with an errors dict
    """
    with minimal_app.test_client() as client:
        response = client.post(
            "/test",
            json={"username": "ab"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "errors" in payload
    assert isinstance(payload["errors"], dict)
    # "username" too short, "password" missing
    assert "username" in payload["errors"] or "password" in payload["errors"]
