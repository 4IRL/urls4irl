"""Public ``GET /s/<code>`` confirmation page: resolve rules, privacy, headers, shell."""

from __future__ import annotations

from typing import Callable, Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from markupsafe import escape

from backend import db
from backend.metrics.events import EventName
from backend.models.short_links import Short_Links
from backend.models.user_preferences import Theme, User_Preferences
from backend.models.users import User_Role, Users
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.short_links.code_generator import generate_short_link_code
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.config_strs import CONFIG_ENVS
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    THIRD_USER_ID,
    anonymous_client,
    code_from_short_url,
    delete_revoke,
    get_share_page,
    logged_in_as,
    normalized_body,
    post_mint,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    sum_counter_values,
)
from tests.integration.trash.trash_helpers import post_restore
from tests.utils_for_test import (
    add_short_link,
    get_utub_url_id,
    lock_utub,
    remove_member,
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.short_links

LOGIN_FIXTURE = Tuple[FlaskClient, str, Users, Flask]
SECRET_UTUB_NAME = "Zq-secret-utub-name-7431"
SECRET_URL_TITLE = "Zq-secret-url-title-7431"
SECRET_TAG = "zqsecrettag7431"
UNKNOWN_CODE = "Zzzzzzzzzz"
DEAD_PAGE_HEADING = "This link has expired or doesn't exist"


def _seed_secrets(app: Flask) -> None:
    """Give UTub 1 / URL 1 distinctive values that must never reach the share page."""
    with app.app_context():
        utub: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        utub.name = SECRET_UTUB_NAME
        url_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == FIRST_UTUB_ID
        ).first()
        url_row.url_title = SECRET_URL_TITLE
        db.session.add(
            Utub_Tags(
                utub_id=FIRST_UTUB_ID, tag_string=SECRET_TAG, created_by=CREATOR_ID
            )
        )
        db.session.commit()


def _destination_of(app: Flask, utub_url_id: int) -> str:
    with app.app_context():
        return Utub_Urls.query.get(utub_url_id).standalone_url.url_string


def _seed_link(app: Flask, utub_url_id: int, **kwargs) -> str:
    """Seed a link row directly and return its code."""
    code = generate_short_link_code()
    add_short_link(app, utub_url_id, minted_by=CREATOR_ID, code=code, **kwargs)
    return code


def _usernames(app: Flask) -> list[str]:
    with app.app_context():
        return [user.username for user in Users.query.all()]


# --- Live link ---------------------------------------------------------------------


def test_live_code_shows_confirmation_page_with_exact_continue_link(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN a minted link for a URL in a UTub
    WHEN an anonymous visitor opens /s/<code>
    THEN 200 with the host, the full URL and a Continue anchor with that exact href
        and rel, followed by the secondary link home
    """
    client, csrf_token, _, app = login_first_user_without_register
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    mint_response = post_mint(client, csrf_token, FIRST_UTUB_ID, url_1)
    code = code_from_short_url(mint_response.json["shortUrl"])
    destination = _destination_of(app, url_1)

    response = get_share_page(anonymous_client(app), code)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert str(escape(destination)) in html
    assert (
        f'<a class="splash-button" href="{escape(destination)}" '
        'rel="noopener noreferrer nofollow">Continue</a>'
    ) in html
    assert '<meta name="robots" content="noindex, nofollow">' in html
    assert html.index('class="splash-button" href="') < html.index("Go to URLS4IRL</a>")


def test_live_page_leaks_nothing_about_the_utub(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN a UTub with a distinctive name, URL title and tag, and a minted link
    WHEN the link is opened anonymously
    THEN the HTML contains none of those, and no member username
    """
    client, csrf_token, _, app = login_first_user_without_register
    _seed_secrets(app)
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = code_from_short_url(
        post_mint(client, csrf_token, FIRST_UTUB_ID, url_1).json["shortUrl"]
    )

    html = get_share_page(anonymous_client(app), code).get_data(as_text=True)

    for secret in (SECRET_UTUB_NAME, SECRET_URL_TITLE, SECRET_TAG, *_usernames(app)):
        assert secret not in html


def test_get_does_not_change_the_link_row(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN a live link
    WHEN it is opened
    THEN its row is unchanged (no refresh of the expiry, no new rows)
    """
    _, _, _, app = login_first_user_without_register
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = _seed_link(app, url_1)
    with app.app_context():
        before = [
            (row.code, row.expires_at, row.created_at)
            for row in db.session.query(Short_Links)
        ]

    assert get_share_page(anonymous_client(app), code).status_code == 200

    with app.app_context():
        after = [
            (row.code, row.expires_at, row.created_at)
            for row in db.session.query(Short_Links)
        ]
    assert before == after


# --- Dead links --------------------------------------------------------------------


def _expired(app: Flask, **_) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    return _seed_link(app, url_1, expires_at=utc_now().replace(year=2000))


def _url_trashed(app: Flask, **_) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = _seed_link(app, url_1)
    trash_utub_url(app, url_1, deleted_by=CREATOR_ID)
    return code


def _utub_trashed(app: Flask, **_) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = _seed_link(app, url_1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=CREATOR_ID)
    return code


def _utub_locked(app: Flask, **_) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = _seed_link(app, url_1)
    lock_utub(app, FIRST_UTUB_ID)
    return code


def _revoked(app: Flask, client: FlaskClient, csrf_token: str) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = code_from_short_url(
        post_mint(client, csrf_token, FIRST_UTUB_ID, url_1).json["shortUrl"]
    )
    assert delete_revoke(client, csrf_token, FIRST_UTUB_ID, url_1).status_code == 200
    return code


def _edited_away(app: Flask, client: FlaskClient, csrf_token: str) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = code_from_short_url(
        post_mint(client, csrf_token, FIRST_UTUB_ID, url_1).json["shortUrl"]
    )
    response = client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=url_1),
        json={"urlString": "https://yahoo.com"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200
    return code


def _non_http_destination(app: Flask, **_) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = _seed_link(app, url_1)
    with app.app_context():
        Utub_Urls.query.get(url_1).standalone_url.url_string = "javascript:alert(1)"
        db.session.commit()
    return code


def _no_host_destination(app: Flask, **_) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = _seed_link(app, url_1)
    with app.app_context():
        Utub_Urls.query.get(url_1).standalone_url.url_string = "https:///path-only"
        db.session.commit()
    return code


def _backslash_destination(app: Flask, **_) -> str:
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = _seed_link(app, url_1)
    with app.app_context():
        Utub_Urls.query.get(
            url_1
        ).standalone_url.url_string = "https://good.example\\@evil.example/"
        db.session.commit()
    return code


DEAD_SCENARIOS: dict[str, Callable[..., str]] = {
    "backslash_destination": _backslash_destination,
    "unknown": lambda app, **_: UNKNOWN_CODE,
    "too_short": lambda app, **_: "abc123",
    "too_long": lambda app, **_: "A" * 11,
    "bad_character": lambda app, **_: "abcde-ghij",
    "encoded_space": lambda app, **_: "abcdefghi%20",
    "trailing_newline": lambda app, **_: "abcdefghi%0A",
    "expired": _expired,
    "url_trashed": _url_trashed,
    "utub_trashed": _utub_trashed,
    "utub_locked": _utub_locked,
    "revoked": _revoked,
    "edited_away": _edited_away,
    "javascript_destination": _non_http_destination,
    "no_host_destination": _no_host_destination,
}


@pytest.mark.parametrize("scenario", list(DEAD_SCENARIOS))
def test_every_dead_case_returns_the_identical_404_page(
    scenario: str,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN a code that is unknown, malformed, expired, trashed, locked, revoked,
        edited away or points at a non-http(s) destination
    WHEN it is opened anonymously
    THEN 404 whose body (nonce and CSRF normalised) equals the unknown-code page, and
        the page names no destination
    """
    client, csrf_token, _, app = login_first_user_without_register
    code = DEAD_SCENARIOS[scenario](app=app, client=client, csrf_token=csrf_token)
    visitor = anonymous_client(app)

    response = get_share_page(visitor, code)
    baseline = get_share_page(visitor, UNKNOWN_CODE)

    assert response.status_code == 404
    assert baseline.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)
    assert DEAD_PAGE_HEADING in response.get_data(as_text=True)
    assert '<meta name="robots" content="noindex, nofollow">' in (
        response.get_data(as_text=True)
    )


@pytest.mark.parametrize("target", ["url", "utub"])
def test_trash_then_restore_leaves_the_old_code_dead(
    target: str,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN a minted link whose URL (or whole UTub) is trashed and then restored
    WHEN the old code is opened
    THEN it is the 404 page: trash deleted the link and restore never brings it back
    """
    client, csrf_token, _, app = login_first_user_without_register
    url_1 = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    code = code_from_short_url(
        post_mint(client, csrf_token, FIRST_UTUB_ID, url_1).json["shortUrl"]
    )
    assert get_share_page(anonymous_client(app), code).status_code == 200
    headers = {"X-CSRFToken": csrf_token}

    if target == "url":
        client.delete(
            url_for(ROUTES.URLS.DELETE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=url_1),
            headers=headers,
        )
        assert post_restore(client, csrf_token, FIRST_UTUB_ID, url_1).status_code == 200
    else:
        client.delete(
            url_for(ROUTES.UTUBS.DELETE_UTUB, utub_id=FIRST_UTUB_ID), headers=headers
        )
        restore = client.post(
            url_for(ROUTES.UTUBS.RESTORE_UTUB, utub_id=FIRST_UTUB_ID),
            json={},
            headers=headers,
        )
        assert restore.status_code == 200

    response = get_share_page(anonymous_client(app), code)
    assert response.status_code == 404
    assert DEAD_PAGE_HEADING in response.get_data(as_text=True)


# --- Headers -----------------------------------------------------------------------


@pytest.mark.parametrize("live", [True, False])
def test_share_page_privacy_headers_on_200_and_404(
    live: bool,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN a live code and an unknown code
    WHEN each is opened
    THEN both carry no-referrer, noindex and no-store while the CSP stays in force
    """
    _, _, _, app = login_first_user_without_register
    code = (
        _seed_link(app, get_utub_url_id(app, FIRST_UTUB_ID, 1))
        if live
        else UNKNOWN_CODE
    )

    response = get_share_page(anonymous_client(app), code)

    assert response.status_code == (200 if live else 404)
    assert response.headers[CONFIG_ENVS.REFERRER_POLICY] == "no-referrer"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert response.headers["Cache-Control"] == "no-store"
    assert CONFIG_ENVS.CONTENT_SECURITY_POLICY in response.headers
    assert response.headers[CONFIG_ENVS.X_FRAME_OPTIONS] == "DENY"


def test_other_pages_keep_the_global_referrer_policy(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN the share page overrides Referrer-Policy
    WHEN the privacy page and the home page are requested
    THEN each still carries the configured global value, and none gets the robots tag
    """
    client, _, _, app = login_first_user_without_register
    visitor = anonymous_client(app)

    responses = [
        visitor.get(url_for(ROUTES.USERS.PRIVACY), headers={"X-Requested-With": ""}),
        client.get("/home", headers={"X-Requested-With": ""}),
    ]

    for response in responses:
        assert response.status_code == 200, response.request.path
        assert (
            response.headers[CONFIG_ENVS.REFERRER_POLICY]
            == CONFIG_ENVS.DEFAULT_REFERRER_POLICY_VALUE
        )
        assert "X-Robots-Tag" not in response.headers
        assert 'name="robots"' not in response.get_data(as_text=True)


def test_forced_rate_limit_returns_the_429_html_page(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN a live code
    WHEN the request is rate limited (X-Force-Rate-Limit)
    THEN the response is the HTML 429 page
    """
    _, _, _, app = login_first_user_without_register
    code = _seed_link(app, get_utub_url_id(app, FIRST_UTUB_ID, 1))

    response = get_share_page(
        anonymous_client(app), code, headers={"X-Force-Rate-Limit": "1"}
    )

    assert response.status_code == 429
    assert "text/html" in response.content_type


# --- Same neutral shell for every viewer -------------------------------------------


def _prepare_viewers(app: Flask) -> None:
    """User 2 prefers the dark theme, user 3 is an admin and no longer a member."""
    with app.app_context():
        db.session.add(User_Preferences(user_id=SECOND_USER_ID, theme=Theme.DARK))
        Users.query.get(THIRD_USER_ID).role = User_Role.ADMIN
        db.session.commit()
    remove_member(app, FIRST_UTUB_ID, THIRD_USER_ID)


@pytest.mark.parametrize("live", [True, False])
def test_every_viewer_gets_the_anonymous_page_byte_for_byte(
    live: bool,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN a member, a dark-theme member, an admin non-member and an anonymous visitor
    WHEN each opens the same live (or dead) code
    THEN the normalised bodies are identical, with no refresh meta, no authenticated
        navbar and the default theme stamp
    """
    _, _, _, app = login_first_user_without_register
    _prepare_viewers(app)
    code = (
        _seed_link(app, get_utub_url_id(app, FIRST_UTUB_ID, 1))
        if live
        else UNKNOWN_CODE
    )
    expected_status = 200 if live else 404

    anonymous = get_share_page(anonymous_client(app), code)
    assert anonymous.status_code == expected_status
    anonymous_body = normalized_body(anonymous)
    assert 'http-equiv="refresh"' not in anonymous_body
    assert 'id="backToSplashBtn"' in anonymous_body
    assert "toCrossUtubSearch" not in anonymous_body
    assert 'id="loginModal"' not in anonymous_body
    assert 'id="registerModal"' not in anonymous_body
    assert 'data-theme="system"' in anonymous_body

    for user_id in (CREATOR_ID, SECOND_USER_ID, THIRD_USER_ID):
        with logged_in_as(app, user_id) as (viewer_client, _):
            response = get_share_page(viewer_client, code)
        assert response.status_code == expected_status
        assert normalized_body(response) == anonymous_body, f"user {user_id}"


# --- Metrics -----------------------------------------------------------------------


def test_live_resolve_emits_metric_and_dead_resolve_does_not(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: LOGIN_FIXTURE,
) -> None:
    """
    GIVEN metrics enabled
    WHEN a dead code, then a live code, then the live code again are opened
    THEN SHORT_LINK_RESOLVED stays 0 for the dead one and counts each live open
    """
    _, _, _, app = login_first_user_without_register
    code = _seed_link(app, get_utub_url_id(app, FIRST_UTUB_ID, 1))
    visitor = anonymous_client(app)
    assert count_counter_keys(provide_metrics_redis, EventName.SHORT_LINK_RESOLVED) == 0

    assert get_share_page(visitor, UNKNOWN_CODE).status_code == 404
    assert count_counter_keys(provide_metrics_redis, EventName.SHORT_LINK_RESOLVED) == 0

    assert get_share_page(visitor, code).status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.SHORT_LINK_RESOLVED) == 1
    assert get_share_page(visitor, code).status_code == 200
    assert sum_counter_values(provide_metrics_redis, EventName.SHORT_LINK_RESOLVED) == 2
