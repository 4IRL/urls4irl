"""Integration tests for the JSON 429 on the metric flow builder route set."""

from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from backend.models.users import Users
from backend.utils.all_routes import ADMIN_ROUTES, BUILDER_JSON_429_ENDPOINTS
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_validation_strs import URL_VALIDATION

pytestmark = pytest.mark.admin

AdminSession = Tuple[FlaskClient, str, Users, Flask]

_FLOWS_URL: str = "/admin/metrics/flows"
_FLOW_URL: str = "/admin/metrics/flows/custom_1"
_MODERATION_URL: str = "/admin/ops/metrics-flush"
_UNMATCHED_URL: str = "/admin/metrics/flows-nope"
_XHR: dict[str, str] = {
    URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST,
    "X-Force-Rate-Limit": "1",
}
_NO_XHR: dict[str, str] = {**_XHR, URL_VALIDATION.X_REQUESTED_WITH: ""}
_BUILDER_REQUESTS: list[tuple[str, str]] = [
    ("GET", _FLOWS_URL),
    ("POST", _FLOWS_URL),
    ("PUT", _FLOW_URL),
    ("DELETE", _FLOW_URL),
]


def _send(
    client: FlaskClient, csrf: str, *, method: str, url: str, headers: dict[str, str]
) -> TestResponse:
    return client.open(
        url, method=method, headers={**headers, "X-CSRFToken": csrf}, json={}
    )


def _assert_html_429(response: TestResponse) -> None:
    assert response.status_code == 429
    assert not response.is_json
    assert IDENTIFIERS.HTML_429 in response.get_data(as_text=True)


def test_builder_endpoint_set_is_the_metric_flow_endpoints() -> None:
    assert BUILDER_JSON_429_ENDPOINTS == {
        ADMIN_ROUTES.METRIC_FLOWS_LIST,
        ADMIN_ROUTES.METRIC_FLOW_CREATE,
        ADMIN_ROUTES.METRIC_FLOW_UPDATE,
        ADMIN_ROUTES.METRIC_FLOW_DELETE,
    }


@pytest.mark.parametrize("method,url", _BUILDER_REQUESTS)
def test_builder_xhr_rate_limit_returns_json_429(
    login_admin_user_with_register: AdminSession, method: str, url: str
) -> None:
    """
    GIVEN a logged-in admin
    WHEN an XHR to a builder endpoint trips the rate limit
    THEN 429 with the JSON message envelope
    """
    client, csrf, _, _ = login_admin_user_with_register
    response = _send(client, csrf, method=method, url=url, headers=_XHR)

    assert response.status_code == 429
    assert response.is_json
    assert response.get_json() == {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: STD_JSON.TOO_MANY_REQUESTS,
    }


@pytest.mark.parametrize("method,url", _BUILDER_REQUESTS)
def test_builder_non_xhr_rate_limit_returns_html_429(
    login_admin_user_with_register: AdminSession, method: str, url: str
) -> None:
    client, csrf, _, _ = login_admin_user_with_register
    _assert_html_429(_send(client, csrf, method=method, url=url, headers=_NO_XHR))


@pytest.mark.parametrize(
    "method,url",
    [("POST", _MODERATION_URL), ("POST", "/login"), ("GET", _UNMATCHED_URL)],
)
def test_xhr_rate_limit_outside_builder_set_returns_html_429(
    login_admin_user_with_register: AdminSession, method: str, url: str
) -> None:
    """
    GIVEN a logged-in admin
    WHEN an XHR to a non-builder route or an unmatched URL trips the rate limit
    THEN the HTML 429 page (an unmatched URL has no endpoint and fails closed)
    """
    client, csrf, _, _ = login_admin_user_with_register
    _assert_html_429(_send(client, csrf, method=method, url=url, headers=_XHR))
