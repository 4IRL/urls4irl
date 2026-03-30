import pytest
from flask import Flask

from backend import limiter
from backend.api_common.parse_request import api_route
from backend.schemas.requests.splash import LoginRequest
from backend.schemas.users import LoginRedirectResponseSchema
from backend.system.routes import system

pytestmark = pytest.mark.unit


@pytest.fixture()
def minimal_app():
    """Minimal Flask app with test routes decorated by @api_route."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    @flask_app.route("/test-with-body", methods=["POST"])
    @api_route(
        request_schema=LoginRequest,
        response_schema=None,
        error_message="Invalid input",
        error_code=1,
    )
    def test_with_body(validated_request: LoginRequest):
        return {"username": validated_request.username}, 200

    @flask_app.route("/test-no-body", methods=["GET"])
    @api_route(response_schema=None)
    def test_no_body():
        return {"status": "ok"}, 200

    @flask_app.route("/test-with-response", methods=["POST"])
    @api_route(
        request_schema=LoginRequest,
        response_schema=LoginRedirectResponseSchema,
        error_message="Invalid input",
        error_code=1,
    )
    def test_with_response(validated_request: LoginRequest):
        return {"username": validated_request.username}, 200

    return flask_app


def test_api_route_missing_json_body_returns_400(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route that requires a request body
    WHEN the request has no JSON body
    THEN a 400 response is returned with the configured error message
    """
    with minimal_app.test_client() as client:
        response = client.post("/test-with-body")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["message"] == "Invalid input"


def test_api_route_valid_body_injects_validated_request(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route that requires a request body
    WHEN the request has a valid JSON body
    THEN validated_request is injected and the route returns 200
    """
    with minimal_app.test_client() as client:
        response = client.post(
            "/test-with-body",
            json={"username": "testuser", "password": "validpassword1"},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["username"] == "testuser"


def test_api_route_invalid_body_returns_400_with_errors(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route that requires a request body
    WHEN the request has a JSON body that fails schema validation
    THEN a 400 response is returned with an errors dict
    """
    with minimal_app.test_client() as client:
        response = client.post(
            "/test-with-body",
            json={"username": "ab"},
        )

    assert response.status_code == 400
    payload = response.get_json()
    assert "errors" in payload
    assert isinstance(payload["errors"], dict)
    assert "username" in payload["errors"] or "password" in payload["errors"]


def test_api_route_get_without_body_succeeds(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route with no request_schema
    WHEN a GET request is made without a body
    THEN the route returns 200 with the expected payload
    """
    with minimal_app.test_client() as client:
        response = client.get("/test-no-body")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"


def test_api_route_stashes_request_schema(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route(request_schema=LoginRequest)
    WHEN accessing the view function
    THEN _api_route_request_schema is set to LoginRequest
    """
    view_fn = minimal_app.view_functions["test_with_body"]
    assert view_fn._api_route_request_schema is LoginRequest


def test_api_route_stashes_response_schema(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route(response_schema=LoginRedirectResponseSchema)
    WHEN accessing the view function
    THEN _api_route_response_schema is set to LoginRedirectResponseSchema
    """
    view_fn = minimal_app.view_functions["test_with_response"]
    assert view_fn._api_route_response_schema is LoginRedirectResponseSchema


def test_api_route_none_request_schema_stashed_for_get(minimal_app: Flask):
    """
    GIVEN a GET route decorated with @api_route(response_schema=None)
    WHEN accessing the view function
    THEN _api_route_request_schema is None
    """
    view_fn = minimal_app.view_functions["test_no_body"]
    assert view_fn._api_route_request_schema is None


def test_api_route_none_response_schema_stashed_when_none(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route(response_schema=None)
    WHEN accessing the view function
    THEN _api_route_response_schema is None
    """
    view_fn = minimal_app.view_functions["test_no_body"]
    assert view_fn._api_route_response_schema is None


def test_api_route_health_endpoint_stashes_none_response_schema():
    """
    GIVEN the system.health route decorated with @api_route(response_schema=None)
    WHEN accessing the view function from the real app
    THEN both _api_route_request_schema and _api_route_response_schema are None
    """
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    limiter.init_app(flask_app)
    flask_app.register_blueprint(system)

    view_fn = flask_app.view_functions["system.health"]
    assert view_fn._api_route_response_schema is None
    assert view_fn._api_route_request_schema is None
