"""Route tests for the public ``POST /invite/<token>/join`` plain-form join."""

from __future__ import annotations

import logging
import re
from html import unescape
from unittest.mock import patch

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.invite_links.constants import (
    INVITE_LINK_JOIN_RATE_LIMIT,
    InviteJoinOutcome,
)
from backend.invite_links.data_models import InviteJoinResult
from backend.invite_links.routes import _join_outcome_response
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.invite_link_strs import INVITE_LINK_PAGE
from tests.integration.invite_links.invite_route_helpers import (
    disable_limiter,
    enable_limiter,
)
from tests.integration.invite_links.test_invite_page_route import (
    DEAD_CASES,
    MALFORMED_TOKEN,
    UNKNOWN_TOKEN,
    VIEWER_ID,
    _add_member,
    _get,
    _live_token,
    _logged_in,
    _main_of,
    _set_unvalidated,
    _title_of,
    _token_of,
)
from tests.integration.mobile_api.mobile_helpers import (
    bearer,
    clear_request_identity,
    token_for_user,
)
from tests.integration.short_links.short_link_helpers import (
    FIRST_UTUB_ID,
    NON_XHR_HEADERS,
    anonymous_client,
    normalized_body,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import add_invite_link

pytestmark = pytest.mark.invite_links

_FORCE_429 = {"X-Force-Rate-Limit": "1"}


def _join_path(app: Flask, token: str) -> str:
    with app.test_request_context():
        g.pop("_login_user", None)
        return url_for(ROUTES.INVITE_LINKS.JOIN_INVITE_PAGE, token=token)


def _post(
    client: FlaskClient,
    token: str,
    csrf_token: str | None,
    headers: dict[str, str] | None = None,
) -> Response:
    """Submit the Join form like a browser: urlencoded body, no XHR header."""
    data = {} if csrf_token is None else {"csrf_token": csrf_token}
    return client.post(
        _join_path(client.application, token),
        data=data,
        headers={**NON_XHR_HEADERS, **(headers or {})},
    )


def _state(
    app: Flask,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], int]:
    with app.app_context():
        db.session.expire_all()
        return (
            sorted((row.id, row.use_count) for row in Utub_Invite_Links.query.all()),
            sorted((row.utub_id, row.user_id) for row in Utub_Members.query.all()),
            Utub_Invite_Acceptances.query.count(),
        )


def _use_count(app: Flask, token: str) -> int:
    with app.app_context():
        db.session.expire_all()
        return Utub_Invite_Links.query.filter_by(token=token).one().use_count


def _is_member(app: Flask, user_id: int = VIEWER_ID) -> bool:
    with app.app_context():
        db.session.expire_all()
        return Utub_Members.query.get((FIRST_UTUB_ID, user_id)) is not None


def _assert_privacy_headers(response: Response) -> None:
    assert (
        response.headers[CONFIG_ENVS.REFERRER_POLICY]
        == CONFIG_ENVS.NO_REFERRER_POLICY_VALUE
    )
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert response.headers["Cache-Control"] == "no-store"


def _back_links(response: Response) -> list[str]:
    """Hrefs of every ``Back to the invite`` link in the page."""
    return re.findall(
        r'<a[^>]*href="([^"]*)"[^>]*>\s*' + INVITE_LINK_PAGE.BACK_TO_INVITE,
        response.get_data(as_text=True),
    )


def _logout(client: FlaskClient) -> None:
    with client.application.test_request_context():
        g.pop("_login_user", None)
        url = url_for(ROUTES.USERS.LOGOUT)
    client.get(url)


# --- Success and member precedence -------------------------------------------------


def test_success_joins_once_and_redirects_into_the_utub(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    """
    GIVEN a live link and a validated non-member
    WHEN they submit the Join form
    THEN a 302 into the UTub, one MEMBER row, use_count + 1, one acceptance and one
        MEMBER_ADDED(source=invite_link)
    """
    token = _live_token(app)
    acceptances_before = _state(app)[2]
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        response = _post(client, token, csrf_token)

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/home?UTubID={FIRST_UTUB_ID}")
    _assert_privacy_headers(response)
    assert _is_member(app)
    assert _use_count(app, token) == 1
    assert _state(app)[2] == acceptances_before + 1
    assert sum_counter_values(provide_metrics_redis, EventName.MEMBER_ADDED) == 1
    dims = [
        parse_dims(key)
        for key in find_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED)
    ]
    assert [dim["source"] for dim in dims] == ["invite_link"]


def test_join_form_posted_from_the_rendered_page_token_succeeds(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN the CSRF token taken from the rendered invite page's meta tag
    WHEN the form is posted with it
    THEN the join succeeds
    """
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        page = _get(client, token)
        match = re.search(
            r'name="csrf-token" content="([^"]+)"', page.get_data(as_text=True)
        )
        assert match is not None
        response = _post(client, token, match.group(1))

    assert response.status_code == 302
    assert _is_member(app)


def test_member_repeat_post_redirects_without_consuming_a_use_even_if_revoked(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a member and a revoked link
    WHEN they post the join form
    THEN a 302 into the UTub and no row changes
    """
    token = _token_of(app, add_invite_link(app, FIRST_UTUB_ID, 1, revoked=True))
    _add_member(app)
    before = _state(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        response = _post(client, token, csrf_token)

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/home?UTubID={FIRST_UTUB_ID}")
    assert _state(app) == before


# --- Dead matrix -------------------------------------------------------------------


@pytest.mark.parametrize("make_dead", DEAD_CASES)
def test_dead_matrix_is_the_identical_404_and_joins_no_one(
    app: Flask, every_user_makes_a_unique_utub, make_dead
) -> None:
    """
    GIVEN an unknown, malformed, expired, revoked, used-up, trashed, locked or
        creator-demoted token and a validated non-member
    WHEN they post the join form
    THEN a 404 whose normalized body equals the GET dead page and nothing changes
    """
    token = make_dead(app)
    before = _state(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        baseline = _get(client, UNKNOWN_TOKEN)
        response = _post(client, token, csrf_token)

    assert response.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)
    assert _state(app) == before
    _assert_privacy_headers(response)


# --- Unconfirmed viewer is anonymous -----------------------------------------------


def test_unconfirmed_viewer_post_is_treated_as_logged_out(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a logged-in user whose email is unconfirmed (so an anonymous viewer)
    WHEN they post to a live token and to a revoked, an unknown and a malformed one
    THEN the live token gets the 401 state 2 with the log-in message and splash hrefs,
        every other token gets the uniform dead 404, and nothing is joined
    """
    live = _live_token(app)
    dead = _token_of(app, add_invite_link(app, FIRST_UTUB_ID, 1, revoked=True))
    dead_tokens = [dead, UNKNOWN_TOKEN, MALFORMED_TOKEN]
    before = _state(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        _set_unvalidated(app)
        baseline = _get(client, UNKNOWN_TOKEN)
        live_response = _post(client, live, csrf_token)
        dead_responses = [_post(client, token, csrf_token) for token in dead_tokens]

    main = _main_of(live_response)
    assert live_response.status_code == 401
    assert INVITE_LINK_PAGE.LOGIN_MESSAGE in unescape(main)
    assert f'href="/?next=/invite/{live}"' in main
    assert f'href="/?next=/invite/{live}/register"' in main
    _assert_privacy_headers(live_response)
    for response in dead_responses:
        assert response.status_code == 404
        assert normalized_body(response) == normalized_body(baseline)
        _assert_privacy_headers(response)
    assert _state(app) == before


# --- Suspended actor ---------------------------------------------------------------


def test_patched_actor_suspended_is_the_dead_page(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN the join service reports ACTOR_SUSPENDED
    WHEN a validated viewer posts
    THEN the uniform 404 dead page
    """
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        baseline = _get(client, UNKNOWN_TOKEN)
        with patch(
            "backend.invite_links.routes.join_via_invite",
            return_value=InviteJoinResult(
                outcome=InviteJoinOutcome.ACTOR_SUSPENDED, utub_id=None
            ),
        ):
            response = _post(client, token, csrf_token)

    assert response.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)
    assert not _is_member(app)


# --- Anonymous (logged out meanwhile) ----------------------------------------------


def test_logged_out_post_on_live_link_rerenders_state_two_with_login_message(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a session that logged out after the form loaded (CSRF still valid)
    WHEN the form is posted
    THEN 401 state 2 with the log-in message as the panel's first child, no join
    """
    token = _live_token(app)
    before = _state(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        _logout(client)
        response = _post(client, token, csrf_token)

    main = _main_of(response)
    assert response.status_code == 401
    assert INVITE_LINK_PAGE.LOGIN_MESSAGE in unescape(main)
    panel = main.split('<section class="short-link-panel"', 1)[1]
    first_child = re.search(r"<(\w+)([^>]*)>", panel.split(">", 1)[1])
    assert first_child is not None
    assert first_child.group(1) == "p"
    assert 'role="status"' in first_child.group(2)
    assert f'href="/?next=/invite/{token}"' in main
    assert f'href="/?next=/invite/{token}/register"' in main
    assert _state(app) == before
    _assert_privacy_headers(response)


def test_logged_out_post_on_dead_link_is_the_dead_404(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a logged-out session posting to a dead token
    WHEN the form is posted
    THEN the identical dead 404 page as the GET
    """
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        _logout(client)
        response = _post(client, UNKNOWN_TOKEN, csrf_token)
        baseline = _get(client, UNKNOWN_TOKEN)

    assert response.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)


# --- Endpoint-scoped CSRF and 429 --------------------------------------------------


def test_missing_csrf_renders_the_invite_error_page(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN no CSRF token on the form POST
    WHEN a validated viewer posts
    THEN a 403 invite error page: role=alert, no invite details, one Back to the invite
        link to /invite/<token>, the fixed title and no join
    """
    token = _live_token(app)
    with app.app_context():
        utub_name = db.session.get(Utubs, FIRST_UTUB_ID).name
        inviter = db.session.get(Users, 1).username
    before = _state(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        response = _post(client, token, None)

    body = unescape(response.get_data(as_text=True))
    assert response.status_code == 403
    assert 'role="alert"' in _main_of(response)
    assert INVITE_LINK_PAGE.CSRF_HEADING in body
    assert IDENTIFIERS.HTML_403 not in body
    assert utub_name not in body
    assert inviter not in body
    assert _back_links(response) == [f"/invite/{token}"]
    assert _title_of(response) == INVITE_LINK_PAGE.TITLE_CSRF
    assert 'href="/"' in body
    assert _state(app) == before
    _assert_privacy_headers(response)


def test_forced_429_renders_the_invite_error_page(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a forced rate limit
    WHEN a validated viewer posts
    THEN a 429 invite error page, not the global one, and no join
    """
    token = _live_token(app)
    with app.app_context():
        utub_name = db.session.get(Utubs, FIRST_UTUB_ID).name
        inviter = db.session.get(Users, 1).username
    before = _state(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        response = _post(client, token, csrf_token, headers=_FORCE_429)

    body = unescape(response.get_data(as_text=True))
    assert response.status_code == 429
    assert utub_name not in _main_of(response)
    assert inviter not in _main_of(response)
    assert 'role="alert"' in _main_of(response)
    assert INVITE_LINK_PAGE.RATE_LIMIT_HEADING in body
    assert IDENTIFIERS.HTML_429 not in body
    assert _back_links(response) == [f"/invite/{token}"]
    assert _title_of(response) == INVITE_LINK_PAGE.TITLE_RATE_LIMIT
    assert _state(app) == before
    _assert_privacy_headers(response)


@pytest.mark.parametrize("scenario", ["csrf", "forced_429"])
def test_back_link_is_the_percent_encoded_invite_path_for_an_escaped_token(
    app: Flask, every_user_makes_a_unique_utub, scenario: str
) -> None:
    """
    GIVEN a token needing escaping (space and quote)
    WHEN the join POST fails CSRF or is rate limited
    THEN the Back to the invite href is the percent-encoded /invite/<token>
    """
    token = "a b'c"
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        response = _post(
            client,
            token,
            None if scenario == "csrf" else csrf_token,
            headers=_FORCE_429 if scenario == "forced_429" else None,
        )

    assert response.status_code == (403 if scenario == "csrf" else 429)
    assert _back_links(response) == ["/invite/a%20b%27c"]


@pytest.mark.parametrize(
    "outcome",
    [
        outcome
        for outcome in InviteJoinOutcome
        if outcome not in (InviteJoinOutcome.JOINED, InviteJoinOutcome.ALREADY_MEMBER)
    ],
)
def test_join_outcome_fallback_is_the_dead_page_for_every_non_success(
    app: Flask, outcome: InviteJoinOutcome
) -> None:
    """
    GIVEN any non-success join outcome (even carrying a utub_id)
    WHEN it is mapped to a response
    THEN it is the uniform 404 dead page, never a redirect
    """
    with app.test_request_context():
        response = _join_outcome_response(
            InviteJoinResult(outcome=outcome, utub_id=FIRST_UTUB_ID)
        )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "outcome", [InviteJoinOutcome.JOINED, InviteJoinOutcome.ALREADY_MEMBER]
)
def test_join_outcome_success_redirects_only_with_a_utub_id(
    app: Flask, outcome: InviteJoinOutcome
) -> None:
    """
    GIVEN a success outcome
    WHEN it carries a utub_id THEN it redirects into the UTub
    WHEN utub_id is None THEN it fails closed to the 404 dead page
    """
    with app.test_request_context():
        redirected = _join_outcome_response(
            InviteJoinResult(outcome=outcome, utub_id=FIRST_UTUB_ID)
        )
        missing = _join_outcome_response(
            InviteJoinResult(outcome=outcome, utub_id=None)
        )

    assert redirected.status_code == 302
    assert redirected.headers["Location"].endswith(f"/home?UTubID={FIRST_UTUB_ID}")
    assert missing.status_code == 404


def test_eleventh_post_is_429_inline(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN the real limiter
    WHEN one user posts the join form an 11th time within the window
    THEN the 11th is the invite 429 page
    """
    allowed = int(INVITE_LINK_JOIN_RATE_LIMIT.split(" ")[0])
    enable_limiter(app)
    try:
        with _logged_in(app, VIEWER_ID) as (client, csrf_token):
            for _ in range(allowed):
                assert _post(client, UNKNOWN_TOKEN, csrf_token).status_code == 404
            limited = _post(client, UNKNOWN_TOKEN, csrf_token)
    finally:
        disable_limiter()

    assert limited.status_code == 429
    assert _back_links(limited) == [f"/invite/{UNKNOWN_TOKEN}"]


def test_web_and_mobile_join_share_one_bucket(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN the real limiter and ten mobile join calls by one user
    WHEN that user posts the web join form
    THEN it is rate limited
    """
    allowed = int(INVITE_LINK_JOIN_RATE_LIMIT.split(" ")[0])
    with app.test_request_context():
        mobile_url = url_for(ROUTES.API_V1.JOIN_VIA_INVITE, token=UNKNOWN_TOKEN)
    mobile_headers = bearer(token_for_user(app, VIEWER_ID))
    enable_limiter(app)
    try:
        for _ in range(allowed):
            clear_request_identity()
            app.test_client_class = FlaskClient
            response = app.test_client().post(mobile_url, headers=mobile_headers)
            assert response.status_code == 404
        with _logged_in(app, VIEWER_ID) as (client, csrf_token):
            limited = _post(client, UNKNOWN_TOKEN, csrf_token)
    finally:
        disable_limiter()

    assert limited.status_code == 429


def test_unconfirmed_viewer_error_pages_match_the_anonymous_ones(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a logged-in user whose email is unconfirmed (so an anonymous viewer)
    WHEN their join POST is rate limited or fails CSRF
    THEN each page keeps the linked href="/" brand and one Back to the invite link,
        like the anonymous viewer's
    """
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        _set_unvalidated(app)
        limited = _post(client, token, csrf_token, headers=_FORCE_429)
        no_csrf = _post(client, token, None)
    anonymous = _post(anonymous_client(app), token, None)

    assert limited.status_code == 429
    assert no_csrf.status_code == 403
    for response in (limited, no_csrf, anonymous):
        assert 'href="/"' in response.get_data(as_text=True)
        assert _back_links(response) == [f"/invite/{token}"]


def test_other_endpoints_and_the_invite_get_keep_the_global_pages(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a CSRF failure on another endpoint and a 429 on the invite GET
    WHEN each is requested
    THEN the global 403 / 429 page is returned, with no invite recovery link
    """
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        with app.test_request_context():
            g.pop("_login_user", None)
            other = url_for(
                ROUTES.URLS.MINT_SHORT_LINK, utub_id=FIRST_UTUB_ID, utub_url_id=1
            )
        csrf_failure = client.post(other, headers=NON_XHR_HEADERS)
        limited_get = _get(client, token, headers=_FORCE_429)

    assert csrf_failure.status_code == 403
    assert IDENTIFIERS.HTML_403 in unescape(csrf_failure.get_data(as_text=True))
    assert limited_get.status_code == 429
    assert IDENTIFIERS.HTML_429 in unescape(limited_get.get_data(as_text=True))
    for response in (csrf_failure, limited_get):
        assert INVITE_LINK_PAGE.BACK_TO_INVITE not in response.get_data(as_text=True)


# --- Logging and metrics -----------------------------------------------------------


def _is_path_bearing(record: logging.LogRecord) -> bool:
    return (
        record.getMessage().startswith("Request:")
        or getattr(record, "log_type", None) == "http_transaction"
    )


@pytest.mark.parametrize("scenario", ["joined", "csrf", "forced_429"])
def test_handlers_add_no_token_logging(
    app: Flask,
    every_user_makes_a_unique_utub,
    caplog: pytest.LogCaptureFixture,
    scenario: str,
) -> None:
    """
    GIVEN the framework's path-bearing request records are excluded (they log
        request.path for every route, an accepted exposure)
    WHEN the join form is posted, fails CSRF or is rate limited
    THEN no other log record carries the token
    """
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        with caplog.at_level(logging.DEBUG):
            caplog.clear()
            _post(
                client,
                token,
                None if scenario == "csrf" else csrf_token,
                headers=_FORCE_429 if scenario == "forced_429" else None,
            )

    for record in caplog.records:
        if _is_path_bearing(record):
            continue
        assert token not in record.getMessage()
        assert token not in str(vars(record))


def test_no_link_viewed_event_on_any_form_post_outcome(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    """
    GIVEN metrics enabled
    WHEN the form is posted: success, dead, unconfirmed, anonymous, CSRF failure, 429
    THEN no INVITE_LINK_VIEWED event is recorded
    """
    live = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, csrf_token):
        assert _post(client, UNKNOWN_TOKEN, csrf_token).status_code == 404
        assert _post(client, live, None).status_code == 403
        assert _post(client, live, csrf_token, _FORCE_429).status_code == 429
        assert _post(client, live, csrf_token).status_code == 302
        _set_unvalidated(app)
        assert _post(client, live, csrf_token).status_code == 401
        _logout(client)
        assert _post(client, live, csrf_token).status_code == 401

    # Positive control: metrics are live (the one successful join was counted).
    assert sum_counter_values(provide_metrics_redis, EventName.MEMBER_ADDED) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_VIEWED) == 0
