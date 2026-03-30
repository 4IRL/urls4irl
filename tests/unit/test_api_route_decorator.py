from typing import Type

import pytest
from flask import Flask
from pydantic import BaseModel

from backend import limiter
from backend.api_common.parse_request import api_route
from backend.contact.routes import contact
from backend.members.routes import members
from backend.schemas.base import BaseSchema
from backend.schemas.requests.contact import ContactRequest
from backend.schemas.requests.members import AddMemberRequest
from backend.schemas.requests.splash import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from backend.schemas.requests.tags import AddTagRequest
from backend.schemas.requests.urls import (
    CreateURLRequest,
    UpdateURLStringRequest,
    UpdateURLTitleRequest,
)
from backend.schemas.requests.utubs import (
    CreateUTubRequest,
    UpdateUTubDescriptionRequest,
    UpdateUTubNameRequest,
)
from backend.schemas.tags import (
    UrlTagModifiedResponseSchema,
    UtubTagAddedToUtubResponseSchema,
    UtubTagDeletedFromUtubResponseSchema,
)
from backend.schemas.urls import (
    UrlCreatedResponseSchema,
    UrlDeletedResponseSchema,
    UrlReadResponseSchema,
    UrlTitleUpdatedResponseSchema,
    UrlUpdatedResponseSchema,
)
from backend.schemas.users import (
    LoginRedirectResponseSchema,
    MemberModifiedResponseSchema,
    UtubSummaryListSchema,
)
from backend.schemas.utubs import (
    UtubCreatedResponseSchema,
    UtubDeletedResponseSchema,
    UtubDescUpdatedResponseSchema,
    UtubDetailSchema,
    UtubNameUpdatedResponseSchema,
)
from backend.splash.routes import splash
from backend.system.routes import system
from backend.tags.url_tag_routes import utub_url_tags
from backend.tags.utub_tag_routes import utub_tags
from backend.urls.routes import urls
from backend.utubs.routes import utubs

pytestmark = pytest.mark.unit


@pytest.fixture()
def minimal_app():
    """Minimal Flask app with test routes decorated by @api_route."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    @flask_app.route("/test-with-body", methods=["POST"])
    @api_route(
        request_schema=LoginRequest,
        error_message="Invalid input",
        error_code=1,
    )
    def test_with_body(validated_request: LoginRequest):
        return {"username": validated_request.username}, 200

    @flask_app.route("/test-no-body", methods=["GET"])
    @api_route()
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
    assert payload["errorCode"] == 1


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
    assert payload["errorCode"] == 1
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


def test_api_route_raises_when_request_schema_without_error_message():
    """
    GIVEN @api_route called with request_schema but no error_message
    WHEN the decorator is applied
    THEN a ValueError is raised indicating error_message is required
    """
    with pytest.raises(ValueError, match="error_message is required"):
        api_route(request_schema=LoginRequest, error_code=1)


def test_api_route_raises_when_request_schema_without_error_code():
    """
    GIVEN @api_route called with request_schema but no error_code
    WHEN the decorator is applied
    THEN a ValueError is raised indicating error_code is required
    """
    with pytest.raises(ValueError, match="error_code is required"):
        api_route(request_schema=LoginRequest, error_message="Some error")


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
    GIVEN a GET route decorated with @api_route()
    WHEN accessing the view function
    THEN _api_route_request_schema is None
    """
    view_fn = minimal_app.view_functions["test_no_body"]
    assert view_fn._api_route_request_schema is None


def test_api_route_none_response_schema_stashed_when_none(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route()
    WHEN accessing the view function
    THEN _api_route_response_schema is None
    """
    view_fn = minimal_app.view_functions["test_no_body"]
    assert view_fn._api_route_response_schema is None


def test_api_route_preserves_functools_wraps_attributes(minimal_app: Flask):
    """
    GIVEN routes decorated with @api_route
    WHEN accessing the view functions registered on the Flask app
    THEN __name__ matches the original function name and __wrapped__ points
        to the original function
    """
    body_view_fn = minimal_app.view_functions["test_with_body"]
    assert body_view_fn.__name__ == "test_with_body"
    assert hasattr(body_view_fn, "__wrapped__")
    assert callable(body_view_fn.__wrapped__)

    no_body_view_fn = minimal_app.view_functions["test_no_body"]
    assert no_body_view_fn.__name__ == "test_no_body"
    assert hasattr(no_body_view_fn, "__wrapped__")
    assert callable(no_body_view_fn.__wrapped__)


# All 24 migrated routes with their expected request and response schemas
ALL_API_ROUTES = [
    # Splash routes
    ("splash.register_user", RegisterRequest, None),
    ("splash.login", LoginRequest, LoginRedirectResponseSchema),
    ("splash.send_validation_email", None, None),
    ("splash.forgot_password", ForgotPasswordRequest, None),
    ("splash.reset_password", ResetPasswordRequest, None),
    # UTub routes
    ("utubs.create_utub", CreateUTubRequest, UtubCreatedResponseSchema),
    ("utubs.get_single_utub", None, UtubDetailSchema),
    ("utubs.get_utubs", None, UtubSummaryListSchema),
    ("utubs.update_utub_name", UpdateUTubNameRequest, UtubNameUpdatedResponseSchema),
    (
        "utubs.update_utub_desc",
        UpdateUTubDescriptionRequest,
        UtubDescUpdatedResponseSchema,
    ),
    ("utubs.delete_utub", None, UtubDeletedResponseSchema),
    # URL routes
    ("urls.create_url", CreateURLRequest, UrlCreatedResponseSchema),
    ("urls.get_url", None, UrlReadResponseSchema),
    ("urls.update_url", UpdateURLStringRequest, UrlUpdatedResponseSchema),
    ("urls.update_url_title", UpdateURLTitleRequest, UrlTitleUpdatedResponseSchema),
    ("urls.delete_url", None, UrlDeletedResponseSchema),
    # Member routes
    ("members.create_member", AddMemberRequest, MemberModifiedResponseSchema),
    ("members.remove_member", None, MemberModifiedResponseSchema),
    # UTub tag routes
    ("utub_tags.create_utub_tag", AddTagRequest, UtubTagAddedToUtubResponseSchema),
    ("utub_tags.delete_utub_tag", None, UtubTagDeletedFromUtubResponseSchema),
    # URL tag routes
    ("utub_url_tags.create_utub_url_tag", AddTagRequest, UrlTagModifiedResponseSchema),
    ("utub_url_tags.delete_utub_url_tag", None, UrlTagModifiedResponseSchema),
    # Contact routes
    ("contact.submit_contact_us", ContactRequest, None),
    # System routes
    ("system.health", None, None),
]


@pytest.fixture()
def real_app_with_all_blueprints():
    """Flask app with all blueprints registered for schema introspection tests."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    limiter.init_app(flask_app)
    flask_app.register_blueprint(splash)
    flask_app.register_blueprint(utubs)
    flask_app.register_blueprint(urls)
    flask_app.register_blueprint(members)
    flask_app.register_blueprint(utub_tags)
    flask_app.register_blueprint(utub_url_tags)
    flask_app.register_blueprint(contact)
    flask_app.register_blueprint(system)

    return flask_app


@pytest.mark.parametrize(
    "endpoint_name,expected_request_schema,expected_response_schema",
    ALL_API_ROUTES,
    ids=[route[0] for route in ALL_API_ROUTES],
)
def test_api_route_schema_stashed_on_all_migrated_routes(
    real_app_with_all_blueprints: Flask,
    endpoint_name: str,
    expected_request_schema: Type[BaseModel] | None,
    expected_response_schema: Type[BaseSchema] | None,
):
    """
    GIVEN a route that has been migrated to @api_route
    WHEN accessing the view function via app.view_functions
    THEN _api_route_request_schema and _api_route_response_schema match expectations
    """
    view_fn = real_app_with_all_blueprints.view_functions[endpoint_name]
    assert view_fn._api_route_request_schema is expected_request_schema
    assert view_fn._api_route_response_schema is expected_response_schema
