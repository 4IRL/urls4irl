from __future__ import annotations

import pytest
from flask import Flask

from backend import create_app
from backend.config import ConfigTest
from backend.utils.all_routes import (
    ADMIN_JS_ROUTES,
    JS_ROUTES,
    UTUB_ROUTES,
    generate_admin_routes_js,
    generate_routes_js,
)

pytestmark = pytest.mark.unit

EXPECTED_JS_ROUTE_URLS: dict[str, str] = {
    # UTub routes
    "home": "/home",
    "createUTub": "/utubs",
    "getUTubs": "/utubs",
    "getUTub": "/utubs/-1",
    "deleteUTub": "/utubs/-1",
    "updateUTubName": "/utubs/-1/name",
    "updateUTubDescription": "/utubs/-1/description",
    # URL routes
    "getURL": "/utubs/-1/urls/-2",
    "createURL": "/utubs/-1/urls",
    "deleteURL": "/utubs/-1/urls/-2",
    "updateURL": "/utubs/-1/urls/-2",
    "updateURLTitle": "/utubs/-1/urls/-2/title",
    "copyURLsToUtubs": "/utubs/urls/copy",
    "bulkDeleteURLs": "/utubs/-1/urls/delete",
    # UTub URL Tag routes
    "createURLTag": "/utubs/-1/urls/-2/tags",
    "createURLTagsBatch": "/utubs/-1/urls/-2/tags/batch",
    "applyTagsToURLs": "/utubs/-1/urls/tags/batch",
    "deleteURLTag": "/utubs/-1/urls/-2/tags/-3",
    # UTub Tag routes
    "createUTubTag": "/utubs/-1/tags",
    "deleteUTubTag": "/utubs/-1/tags/-2",
    # Member routes
    "createMember": "/utubs/-1/members",
    "coMemberCandidates": "/utubs/-1/co-members",
    "removeMember": "/utubs/-1/members/-4",
    "modifyMemberRole": "/utubs/-1/members/-4",
    "transferUtubOwnership": "/utubs/-1/owner",
    # Splash routes
    "login": "/login",
    "register": "/register",
    "confirmEmailAfterRegister": "/confirm-email",
    "sendValidationEmail": "/send-validation-email",
    "resendRegistrationEmail": "/resend-registration-email",
    "forgotPassword": "/forgot-password",
    "oauthGoogleLogin": "/oauth/google/login",
    "oauthGithubLogin": "/oauth/github/login",
    # Util routes
    "errorPage": "/invalid",
    # Logout
    "logout": "/logout",
    # Contact
    "contactUs": "/contact",
    # Search
    "crossUtubSearch": "/search",
    # Metrics ingest
    "metricsIngest": "/api/metrics",
}

EXPECTED_ADMIN_JS_ROUTE_URLS: dict[str, str] = {
    "adminMetricsPage": "/admin/metrics",
    # Metrics query routes
    "metricsQueryTop": "/api/metrics/query/top",
    "metricsQueryTimeseries": "/api/metrics/query/timeseries",
    "metricsQuerySummary": "/api/metrics/query/summary",
    "metricsQueryGroupedTimeseries": "/api/metrics/query/grouped-timeseries",
    "metricsQueryFlow": "/api/metrics/query/flow",
    "metricsQueryGaugesTimeseries": "/api/metrics/query/gauges/timeseries",
    "metricsQueryLatency": "/api/metrics/query/latency",
    "metricsQueryLatencyTimeseries": "/api/metrics/query/latency/timeseries",
}


@pytest.fixture(scope="module")
def full_app() -> Flask:
    # Pass the class, not an instance, so Config.__init__ env validation is skipped.
    app = create_app(ConfigTest)
    assert app is not None
    return app


def test_delete_utub_key_points_at_delete_endpoint() -> None:
    """
    GIVEN the declarative JS_ROUTES table
    WHEN the deleteUTub key is looked up
    THEN it targets the DELETE_UTUB endpoint, not GET_SINGLE_UTUB
    """
    assert JS_ROUTES["deleteUTub"].endpoint == UTUB_ROUTES.DELETE_UTUB


def test_js_routes_table_keys_match_expected_order() -> None:
    """
    GIVEN the declarative JS_ROUTES table
    WHEN its keys are listed
    THEN they match the 38 frontend route keys in their established order
    """
    assert list(JS_ROUTES) == list(EXPECTED_JS_ROUTE_URLS)


def test_generate_routes_js_renders_expected_urls(full_app: Flask) -> None:
    """
    GIVEN the full app url_map
    WHEN generate_routes_js() is called inside a request context
    THEN it returns exactly the expected {key: url} dict for all 38 keys
    """
    with full_app.test_request_context():
        rendered_routes = generate_routes_js()

    assert rendered_routes == EXPECTED_JS_ROUTE_URLS


def test_generate_admin_routes_js_renders_expected_urls(full_app: Flask) -> None:
    """
    GIVEN the full app url_map
    WHEN generate_admin_routes_js() is called inside a request context
    THEN it returns the admin metrics page and the 8 metrics query URLs
    """
    with full_app.test_request_context():
        rendered_admin_routes = generate_admin_routes_js()

    assert rendered_admin_routes == EXPECTED_ADMIN_JS_ROUTE_URLS
    assert list(ADMIN_JS_ROUTES) == list(EXPECTED_ADMIN_JS_ROUTE_URLS)
