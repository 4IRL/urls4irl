from flask import Flask
from flask.testing import FlaskClient
import pytest

from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

pytestmark = pytest.mark.mobile_api

_UNMATCHED_API_V1_PATH = f"{API_AUTH.API_V1_URL_PREFIX}/this-route-does-not-exist"
_HTML_ACCEPT_HEADER = {"Accept": "text/html"}
_FORCE_RATE_LIMIT_HEADER = "X-Force-Rate-Limit"


def test_unmatched_api_v1_path_returns_json_404(app: Flask, api_client: FlaskClient):
    """
    GIVEN a request to an /api/v1 path that matches no route (so it never
        enters the api_v1 blueprint)
    WHEN the app-level 404 handler runs — without any X-Requested-With header
    THEN the JSON ErrorResponse envelope is returned, not the HTML error page
    """
    response = api_client.get(_UNMATCHED_API_V1_PATH)

    assert response.status_code == 404
    assert response.is_json
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND


def test_unmatched_api_v1_path_returns_json_404_even_for_html_accept(
    app: Flask, api_client: FlaskClient
):
    """JSON errors are returned regardless of the client's Accept header."""
    response = api_client.get(_UNMATCHED_API_V1_PATH, headers=_HTML_ACCEPT_HEADER)

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_rate_limited_api_v1_request_returns_json_429(
    app: Flask, api_client: FlaskClient, bearer_headers_first_user: dict[str, str]
):
    """
    GIVEN a rate-limited request (forced via the test-only 429 hook)
    WHEN it targets an /api/v1 path
    THEN the app-level 429 handler returns the JSON envelope, not HTML
    """
    response = api_client.get(
        f"{API_AUTH.API_V1_URL_PREFIX}/me",
        headers={**bearer_headers_first_user, _FORCE_RATE_LIMIT_HEADER: "1"},
    )

    assert response.status_code == 429
    assert response.is_json
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == STD_JSON.TOO_MANY_REQUESTS


def test_rate_limited_web_request_still_returns_html_429(
    app: Flask, api_client: FlaskClient
):
    """The web surface's HTML 429 page is untouched by the /api/v1 branch."""
    response = api_client.get("/", headers={_FORCE_RATE_LIMIT_HEADER: "1"})

    assert response.status_code == 429
    assert not response.is_json


def test_unmatched_web_path_still_returns_html_404(app: Flask, api_client: FlaskClient):
    """The web surface's HTML 404 page is untouched by the /api/v1 branch."""
    response = api_client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert not response.is_json
