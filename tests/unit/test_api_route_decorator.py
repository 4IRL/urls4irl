import logging
from typing import Type

import pytest
from flask import Blueprint, Flask
from pydantic import BaseModel

from backend import limiter
from backend.api_common.parse_request import _schema_name_to_kwarg, api_route
from backend.contact.routes import contact
from backend.members.routes import members
from backend.schemas.base import BaseSchema
from backend.schemas.contact import ContactResponseSchema
from backend.schemas.requests.contact import ContactRequest
from backend.schemas.requests.members import AddMemberRequest
from backend.schemas.requests.splash import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from backend.schemas.system import HealthResponseSchema
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
    EmailValidationResponseSchema,
    ForgotPasswordResponseSchema,
    LoginRedirectResponseSchema,
    MemberModifiedResponseSchema,
    RegisterResponseSchema,
    ResetPasswordResponseSchema,
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
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utubs.routes import utubs

AJAX_HEADER = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}

pytestmark = pytest.mark.unit


@pytest.fixture()
def minimal_app():
    """Minimal Flask app with test routes decorated by @api_route."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True

    # Register a stub utubs blueprint so url_for("utubs.home") resolves
    utubs_bp = Blueprint("utubs", __name__)

    @utubs_bp.route("/home")
    def home():
        return "home", 200

    flask_app.register_blueprint(utubs_bp)

    @flask_app.route("/test-with-body", methods=["POST"])
    @api_route(
        request_schema=LoginRequest,
        error_message="Invalid input",
        error_code=1,
    )
    def test_with_body(login_request: LoginRequest):
        return {"username": login_request.username}, 200

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
    def test_with_response(login_request: LoginRequest):
        return {"username": login_request.username}, 200

    @flask_app.route("/test-no-ajax-required", methods=["GET"])
    @api_route(ajax_required=False)
    def test_no_ajax_required():
        return {"status": "ok"}, 200

    return flask_app


def test_api_route_missing_json_body_returns_400(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route that requires a request body
    WHEN the request has no JSON body
    THEN a 400 response is returned with the configured error message
    """
    with minimal_app.test_client() as client:
        response = client.post("/test-with-body", headers=AJAX_HEADER)

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["message"] == "Invalid input"
    assert payload["errorCode"] == 1


def test_api_route_valid_body_injects_validated_request(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route that requires a request body
    WHEN the request has a valid JSON body
    THEN the schema-derived kwarg (login_request) is injected and the route returns 200
    """
    with minimal_app.test_client() as client:
        response = client.post(
            "/test-with-body",
            json={"username": "testuser", "password": "validpassword1"},
            headers=AJAX_HEADER,
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
            headers=AJAX_HEADER,
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
        response = client.get("/test-no-body", headers=AJAX_HEADER)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"


def test_api_route_no_schema_ignores_request_body(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route() with no request_schema
    WHEN the request includes a JSON body
    THEN the body is silently ignored and the route returns 200
    """
    with minimal_app.test_client() as client:
        response = client.get(
            "/test-no-body",
            json={"unexpected": "data", "should_be": "ignored"},
            headers=AJAX_HEADER,
        )

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
    ("splash.register_user", RegisterRequest, RegisterResponseSchema),
    ("splash.login", LoginRequest, LoginRedirectResponseSchema),
    ("splash.send_validation_email", None, EmailValidationResponseSchema),
    ("splash.forgot_password", ForgotPasswordRequest, ForgotPasswordResponseSchema),
    ("splash.reset_password", ResetPasswordRequest, ResetPasswordResponseSchema),
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
    ("contact.submit_contact_us", ContactRequest, ContactResponseSchema),
    # System routes
    ("system.health", None, HealthResponseSchema),
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


def test_api_route_raises_when_route_missing_derived_kwarg():
    """
    GIVEN @api_route with request_schema=LoginRequest
    WHEN the decorated function does not declare a 'login_request' parameter
    THEN a ValueError is raised indicating the required parameter name
    """
    with pytest.raises(ValueError, match="must declare a 'login_request' parameter"):

        @api_route(
            request_schema=LoginRequest,
            error_message="Invalid input",
            error_code=1,
        )
        def bad_route():
            pass


def test_api_route_succeeds_with_mixed_positional_and_injected_params():
    """
    GIVEN @api_route with request_schema=LoginRequest
    WHEN the decorated function has URL path params before the schema kwarg
    THEN decoration succeeds without ValueError
    """

    @api_route(
        request_schema=LoginRequest,
        error_message="Invalid input",
        error_code=1,
    )
    def route_with_path_params(utub_id: int, login_request: LoginRequest):
        pass

    assert hasattr(route_with_path_params, "_api_route_request_schema")
    assert route_with_path_params._api_route_request_schema is LoginRequest


def test_api_route_rejects_non_ajax_request(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route that requires a request body
    WHEN a POST is made with valid JSON but WITHOUT the AJAX header
    THEN a 302 redirect response is returned
    """
    with minimal_app.test_client() as client:
        response = client.post(
            "/test-with-body",
            json={"username": "testuser", "password": "validpassword1"},
        )

    assert response.status_code == 302


def test_api_route_rejects_non_ajax_get_request(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route with no request_schema
    WHEN a GET request is made WITHOUT the AJAX header
    THEN a 302 redirect response is returned
    """
    with minimal_app.test_client() as client:
        response = client.get("/test-no-body")

    assert response.status_code == 302


def test_api_route_ajax_required_false_allows_non_ajax(minimal_app: Flask):
    """
    GIVEN a route decorated with @api_route(ajax_required=False)
    WHEN a GET request is made WITHOUT the AJAX header
    THEN the route returns 200 normally
    """
    with minimal_app.test_client() as client:
        response = client.get("/test-no-ajax-required")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"


def test_api_route_stashes_ajax_required(minimal_app: Flask):
    """
    GIVEN routes decorated with @api_route with different ajax_required values
    WHEN accessing the view functions
    THEN _api_route_ajax_required reflects the configured value
    """
    ajax_true_fn = minimal_app.view_functions["test_with_body"]
    assert ajax_true_fn._api_route_ajax_required is True

    ajax_false_fn = minimal_app.view_functions["test_no_ajax_required"]
    assert ajax_false_fn._api_route_ajax_required is False


def test_api_route_non_ajax_logs_warning(minimal_app: Flask, caplog):
    """
    GIVEN a route decorated with @api_route (ajax_required=True by default)
    WHEN a POST is made WITHOUT the AJAX header
    THEN the caplog contains a warning about the non-AJAX request
    """
    with caplog.at_level(logging.WARNING):
        with minimal_app.test_client() as client:
            client.post(
                "/test-with-body",
                json={"username": "testuser", "password": "validpassword1"},
            )

    assert any(
        "User=unknown did not make an AJAX request" in record.message
        for record in caplog.records
    )


def test_schema_name_to_kwarg_conversions():
    """
    GIVEN various schema classes with CamelCase names
    WHEN _schema_name_to_kwarg is called
    THEN the names are correctly converted to snake_case
    """
    assert _schema_name_to_kwarg(LoginRequest) == "login_request"
    assert _schema_name_to_kwarg(CreateURLRequest) == "create_url_request"
    assert _schema_name_to_kwarg(UpdateURLStringRequest) == "update_url_string_request"
    assert _schema_name_to_kwarg(AddMemberRequest) == "add_member_request"
    assert _schema_name_to_kwarg(CreateUTubRequest) == "create_utub_request"
    assert _schema_name_to_kwarg(UpdateUTubNameRequest) == "update_utub_name_request"
    assert (
        _schema_name_to_kwarg(UpdateUTubDescriptionRequest)
        == "update_utub_description_request"
    )
    assert _schema_name_to_kwarg(ContactRequest) == "contact_request"
