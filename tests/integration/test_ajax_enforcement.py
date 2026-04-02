"""Tests that @api_route AJAX enforcement works for all routes.

Routes with ajax_required=True (the default) must return 302 when the
X-Requested-With header is missing or incorrect.  Routes with
ajax_required=False must NOT return 302 regardless of the header.
"""

from __future__ import annotations

from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES, SYSTEM_ROUTES
from backend.utils.strings.url_validation_strs import URL_VALIDATION

pytestmark = [
    pytest.mark.utubs,
    pytest.mark.urls,
    pytest.mark.members,
    pytest.mark.tags,
]

NON_AJAX_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: "not-ajax"}
AJAX_REDIRECT_STATUS = 302
CSRF_HEADER_KEY = "X-CSRFToken"


# ---------------------------------------------------------------------------
# AJAX-required routes (17 total) — must return 302 without AJAX header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "route_name, method, url_for_target, url_kwargs_keys, json_body",
    [
        pytest.param(
            "create_utub",
            "POST",
            ROUTES.UTUBS.CREATE_UTUB,
            {},
            {"utub_name": "test"},
            id="create_utub",
        ),
        pytest.param(
            "get_single_utub",
            "GET",
            ROUTES.UTUBS.GET_SINGLE_UTUB,
            {"utub_id": "utub_id"},
            None,
            id="get_single_utub",
        ),
        pytest.param(
            "get_utubs",
            "GET",
            ROUTES.UTUBS.GET_UTUBS,
            {},
            None,
            id="get_utubs",
        ),
        pytest.param(
            "update_utub_name",
            "PATCH",
            ROUTES.UTUBS.UPDATE_UTUB_NAME,
            {"utub_id": "utub_id"},
            {"utub_name": "new name"},
            id="update_utub_name",
        ),
        pytest.param(
            "update_utub_desc",
            "PATCH",
            ROUTES.UTUBS.UPDATE_UTUB_DESC,
            {"utub_id": "utub_id"},
            {"utub_description": "new desc"},
            id="update_utub_desc",
        ),
        pytest.param(
            "delete_utub",
            "DELETE",
            ROUTES.UTUBS.DELETE_UTUB,
            {"utub_id": "utub_id"},
            None,
            id="delete_utub",
        ),
        pytest.param(
            "create_url",
            "POST",
            ROUTES.URLS.CREATE_URL,
            {"utub_id": "utub_id"},
            {"url_string": "https://example.com", "url_title": "Example"},
            id="create_url",
        ),
        pytest.param(
            "get_url",
            "GET",
            ROUTES.URLS.GET_URL,
            {"utub_id": "utub_id", "utub_url_id": "utub_url_id"},
            None,
            id="get_url",
        ),
        pytest.param(
            "update_url",
            "PATCH",
            ROUTES.URLS.UPDATE_URL,
            {"utub_id": "utub_id", "utub_url_id": "utub_url_id"},
            {"url_string": "https://example.com"},
            id="update_url",
        ),
        pytest.param(
            "update_url_title",
            "PATCH",
            ROUTES.URLS.UPDATE_URL_TITLE,
            {"utub_id": "utub_id", "utub_url_id": "utub_url_id"},
            {"url_title": "New Title"},
            id="update_url_title",
        ),
        pytest.param(
            "delete_url",
            "DELETE",
            ROUTES.URLS.DELETE_URL,
            {"utub_id": "utub_id", "utub_url_id": "utub_url_id"},
            None,
            id="delete_url",
        ),
        pytest.param(
            "create_member",
            "POST",
            ROUTES.MEMBERS.CREATE_MEMBER,
            {"utub_id": "utub_id"},
            {"username": "testuser"},
            id="create_member",
        ),
        pytest.param(
            "remove_member",
            "DELETE",
            ROUTES.MEMBERS.REMOVE_MEMBER,
            {"utub_id": "utub_id", "user_id": "member_user_id"},
            None,
            id="remove_member",
        ),
        pytest.param(
            "create_utub_tag",
            "POST",
            ROUTES.UTUB_TAGS.CREATE_UTUB_TAG,
            {"utub_id": "utub_id"},
            {"tag_string": "newtag"},
            id="create_utub_tag",
        ),
        pytest.param(
            "delete_utub_tag",
            "DELETE",
            ROUTES.UTUB_TAGS.DELETE_UTUB_TAG,
            {"utub_id": "utub_id", "utub_tag_id": "utub_tag_id"},
            None,
            id="delete_utub_tag",
        ),
        pytest.param(
            "create_utub_url_tag",
            "POST",
            ROUTES.URL_TAGS.CREATE_URL_TAG,
            {"utub_id": "utub_id", "utub_url_id": "utub_url_id"},
            {"tag_string": "newtag"},
            id="create_utub_url_tag",
        ),
        pytest.param(
            "delete_utub_url_tag",
            "DELETE",
            ROUTES.URL_TAGS.DELETE_URL_TAG,
            {
                "utub_id": "utub_id",
                "utub_url_id": "utub_url_id",
                "utub_tag_id": "utub_tag_id",
            },
            None,
            id="delete_utub_url_tag",
        ),
    ],
)
def test_ajax_required_routes_reject_non_ajax(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    route_name: str,
    method: str,
    url_for_target: str,
    url_kwargs_keys: dict,
    json_body: dict | None,
):
    """Routes with ajax_required=True must return 302 when AJAX header is missing."""
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.first()
        utub_url: Utub_Urls = Utub_Urls.query.filter_by(utub_id=utub.id).first()
        utub_url_tag: Utub_Url_Tags = Utub_Url_Tags.query.filter_by(
            utub_id=utub.id
        ).first()
        member: Utub_Members = Utub_Members.query.filter_by(utub_id=utub.id).first()

        id_map = {
            "utub_id": utub.id,
            "utub_url_id": utub_url.id,
            "utub_tag_id": utub_url_tag.utub_tag_id,
            "member_user_id": member.user_id,
        }

        resolved_kwargs = {
            param_name: id_map[id_key] for param_name, id_key in url_kwargs_keys.items()
        }

        target_url = url_for(url_for_target, **resolved_kwargs)

    headers = dict(NON_AJAX_HEADERS)
    if method != "GET":
        headers[CSRF_HEADER_KEY] = csrf_token

    request_kwargs: dict = {
        "headers": headers,
    }
    if json_body is not None:
        request_kwargs["json"] = json_body

    response = getattr(client, method.lower())(target_url, **request_kwargs)

    assert response.status_code == AJAX_REDIRECT_STATUS, (
        f"Route {route_name} ({method} {target_url}) returned {response.status_code}, "
        f"expected {AJAX_REDIRECT_STATUS}"
    )


# ---------------------------------------------------------------------------
# Non-AJAX routes (7 total) — must NOT return 302
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "route_name, method, url_for_target, url_kwargs, json_body",
    [
        pytest.param(
            "register",
            "POST",
            ROUTES.SPLASH.REGISTER,
            {},
            {
                "username": "newuser",
                "email": "new@test.com",
                "password": "ValidPass1!",
                "confirm_password": "ValidPass1!",
            },
            id="register",
        ),
        pytest.param(
            "login",
            "POST",
            ROUTES.SPLASH.LOGIN,
            {},
            {"username": "newuser", "password": "ValidPass1!"},
            id="login",
        ),
        pytest.param(
            "send_validation_email",
            "POST",
            ROUTES.SPLASH.SEND_VALIDATION_EMAIL,
            {},
            None,
            id="send_validation_email",
        ),
        pytest.param(
            "forgot_password",
            "POST",
            ROUTES.SPLASH.FORGOT_PASSWORD_PAGE,
            {},
            {"email": "test@test.com"},
            id="forgot_password",
        ),
        pytest.param(
            "reset_password",
            "POST",
            ROUTES.SPLASH.RESET_PASSWORD,
            {"token": "fake-token"},
            {"new_password": "ValidPass1!", "confirm_new_password": "ValidPass1!"},
            id="reset_password",
        ),
        pytest.param(
            "contact_us",
            "POST",
            ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT,
            {},
            {"message": "Hello"},
            id="contact_us",
        ),
        pytest.param(
            "health",
            "GET",
            SYSTEM_ROUTES.HEALTH,
            {},
            None,
            id="health",
        ),
    ],
)
def test_ajax_not_required_routes_allow_non_ajax(
    app: Flask,
    client: FlaskClient,
    route_name: str,
    method: str,
    url_for_target: str,
    url_kwargs: dict,
    json_body: dict | None,
):
    """Routes with ajax_required=False must not return 302 AJAX redirect.

    These routes may return various status codes (200, 400, 401, 403, 422)
    depending on request validity and CSRF state.  The only assertion is that
    they do NOT return a 302 redirect, which would indicate AJAX enforcement
    was incorrectly applied.
    """
    with app.test_request_context():
        target_url = url_for(url_for_target, **url_kwargs)

    request_kwargs: dict = {
        "headers": NON_AJAX_HEADERS,
    }
    if json_body is not None:
        request_kwargs["json"] = json_body

    response = getattr(client, method.lower())(target_url, **request_kwargs)

    assert response.status_code != AJAX_REDIRECT_STATUS, (
        f"Route {route_name} ({method} {target_url}) returned {AJAX_REDIRECT_STATUS}, "
        f"indicating AJAX enforcement was applied when it should not have been"
    )
