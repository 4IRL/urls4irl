"""Route tests for the public ``GET /invite/<token>`` page."""

from __future__ import annotations

import ast
import re
from contextlib import contextmanager
from html import unescape
from pathlib import Path
from typing import Generator

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

import backend.invite_links.page_response as page_response_module
from backend import db
from backend.invite_links.page_response import build_invite_splash_urls
from backend.models.users import Users
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.invite_link_strs import INVITE_LINK_PAGE
from tests.integration.invite_links.invite_route_helpers import seed_dead
from tests.integration.short_links.short_link_helpers import (
    FIRST_UTUB_ID,
    NON_XHR_HEADERS,
    THIRD_USER_ID,
    anonymous_client,
    logged_in_as,
    normalized_body,
)
from tests.utils_for_test import (
    add_invite_link,
    lock_utub,
    trash_utub,
)

pytestmark = pytest.mark.invite_links

UNKNOWN_TOKEN = "Z" * 22
MALFORMED_TOKEN = "not-a-valid-token"
VIEWER_ID = THIRD_USER_ID
SCRIPT_UTUB_NAME = "<script>alert(1)</script>"


@contextmanager
def _logged_in(
    app: Flask, user_id: int
) -> Generator[tuple[FlaskClient, str], None, None]:
    """``logged_in_as`` with Flask-Login's per-``g`` user cache cleared first."""
    with app.test_request_context():
        g.pop("_login_user", None)
    with logged_in_as(app, user_id) as session:
        yield session


def _get(
    client: FlaskClient, token: str, headers: dict[str, str] | None = None
) -> Response:
    with client.application.test_request_context():
        # The fixture's open app context keeps ``g`` alive across requests, so
        # Flask-Login's cached user would leak from one viewer into the next.
        g.pop("_login_user", None)
        url = url_for(ROUTES.INVITE_LINKS.INVITE_PAGE, token=token)
    return client.get(url, headers={**NON_XHR_HEADERS, **(headers or {})})


def _token_of(app: Flask, invite_id: int) -> str:
    with app.app_context():
        return db.session.get(Utub_Invite_Links, invite_id).token


def _live_token(app: Flask) -> str:
    return _token_of(app, add_invite_link(app, FIRST_UTUB_ID, 1))


def _set_unvalidated(app: Flask, user_id: int = VIEWER_ID) -> None:
    with app.app_context():
        db.session.get(Users, user_id).email_validated = False
        db.session.commit()


def _add_member(app: Flask, user_id: int = VIEWER_ID) -> None:
    with app.app_context():
        membership = Utub_Members(member_role=Member_Role.MEMBER)
        membership.utub_id = FIRST_UTUB_ID
        membership.user_id = user_id
        db.session.add(membership)
        db.session.commit()


def _main_of(response: Response) -> str:
    match = re.search(r"<main.*?</main>", response.get_data(as_text=True), re.DOTALL)
    assert match is not None
    return match.group(0)


def _nav_of(response: Response) -> str:
    match = re.search(r"<nav.*?</nav>", response.get_data(as_text=True), re.DOTALL)
    assert match is not None
    return match.group(0)


def _title_of(response: Response) -> str:
    match = re.search(r"<title>(.*?)</title>", response.get_data(as_text=True))
    assert match is not None
    return match.group(1)


def _snapshot(app: Flask) -> tuple:
    with app.app_context():
        db.session.expire_all()
        return (
            sorted(
                (row.id, row.use_count, row.revoked_at)
                for row in Utub_Invite_Links.query.all()
            ),
            sorted((row.utub_id, row.user_id) for row in Utub_Members.query.all()),
            Utub_Invite_Acceptances.query.count(),
        )


# --- Dead matrix -------------------------------------------------------------------


def _dead_unknown(app: Flask) -> str:
    return UNKNOWN_TOKEN


def _dead_malformed(app: Flask) -> str:
    return MALFORMED_TOKEN


def _dead_expired(app: Flask) -> str:
    return _token_of(app, seed_dead(app, "expired"))


def _dead_revoked(app: Flask) -> str:
    return _token_of(app, add_invite_link(app, FIRST_UTUB_ID, 1, revoked=True))


def _dead_used_up(app: Flask) -> str:
    return _token_of(app, seed_dead(app, "used_up"))


def _dead_trashed(app: Flask) -> str:
    token = _live_token(app)
    trash_utub(app, FIRST_UTUB_ID, 1)
    return token


def _dead_locked(app: Flask) -> str:
    token = _live_token(app)
    lock_utub(app, FIRST_UTUB_ID)
    return token


def _dead_creator_demoted(app: Flask) -> str:
    return _token_of(app, seed_dead(app, "creator_demoted"))


DEAD_CASES: list = [
    pytest.param(_dead_unknown, id="unknown"),
    pytest.param(_dead_malformed, id="malformed"),
    pytest.param(_dead_expired, id="expired"),
    pytest.param(_dead_revoked, id="revoked"),
    pytest.param(_dead_used_up, id="used_up"),
    pytest.param(_dead_trashed, id="trashed"),
    pytest.param(_dead_locked, id="locked"),
    pytest.param(_dead_creator_demoted, id="creator_demoted"),
]


@pytest.mark.parametrize("make_dead", DEAD_CASES)
def test_every_dead_reason_returns_the_identical_404_for_anonymous(
    app: Flask, every_user_makes_a_unique_utub, make_dead
) -> None:
    """
    GIVEN an unknown, malformed, expired, revoked, used-up, trashed, locked or
        creator-demoted token
    WHEN an anonymous visitor opens it
    THEN the response is a 404 whose normalized body equals the unknown-token page
    """
    token = make_dead(app)
    baseline = _get(anonymous_client(app), UNKNOWN_TOKEN)
    response = _get(anonymous_client(app), token)

    assert baseline.status_code == 404
    assert response.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)
    assert INVITE_LINK_PAGE.DEAD_HEADING in unescape(response.get_data(as_text=True))


@pytest.mark.parametrize("make_dead", DEAD_CASES)
def test_every_dead_reason_returns_the_identical_404_for_a_validated_viewer(
    app: Flask, every_user_makes_a_unique_utub, make_dead
) -> None:
    """
    GIVEN a dead token and an email-validated logged-in non-member
    WHEN they open it
    THEN the response is a 404 whose body equals the unknown-token page for them
    """
    token = make_dead(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        baseline = _get(client, UNKNOWN_TOKEN)
        response = _get(client, token)

    assert response.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)


@pytest.mark.parametrize("viewer_id", [None, VIEWER_ID])
def test_live_link_with_a_missing_creator_is_the_uniform_dead_page(
    app: Flask, every_user_makes_a_unique_utub, viewer_id: int | None
) -> None:
    """
    GIVEN a live link whose creator is gone (created_by NULL)
    WHEN an anonymous or validated viewer opens it
    THEN the uniform dead 404 page with no inviter or UTub details
    """
    token = _live_token(app)
    with app.app_context():
        utub_name = db.session.get(Utubs, FIRST_UTUB_ID).name
        inviter = db.session.get(Users, 1).username
        Utub_Invite_Links.query.filter_by(token=token).one().created_by = None
        db.session.commit()

    if viewer_id is None:
        client = anonymous_client(app)
        baseline = _get(client, UNKNOWN_TOKEN)
        response = _get(client, token)
    else:
        with _logged_in(app, viewer_id) as (client, _):
            baseline = _get(client, UNKNOWN_TOKEN)
            response = _get(client, token)

    assert response.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)
    assert utub_name not in _main_of(response)
    assert inviter not in _main_of(response)


# --- States, statuses and links ----------------------------------------------------


def test_state_one_renders_for_a_validated_non_member(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link and a validated non-member
    WHEN they open it
    THEN 200 with the inviter, UTub name, a Not now link to /home and the Join form
    """
    token = _live_token(app)
    with app.app_context():
        utub_name = db.session.get(Utubs, FIRST_UTUB_ID).name
        inviter = db.session.get(Users, 1).username
    with _logged_in(app, VIEWER_ID) as (client, _):
        response = _get(client, token)

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert INVITE_LINK_PAGE.EYEBROW_TEMPLATE.format(inviter=inviter) in body
    assert utub_name in body
    assert 'href="/home">Not now</a>' in _main_of(response)
    main = _main_of(response)
    assert (
        f'<form id="inviteJoinForm" method="post" action="/invite/{token}/join">'
        in main
    )
    assert 'name="csrf_token"' in main
    assert 'id="inviteJoinBtn"' in main
    assert 'id="inviteJoinStatus"' in main


def test_invite_page_is_always_stamped_dark(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link
    WHEN a validated viewer opens it
    THEN the page is stamped dark and carries the invite-page body class
    """
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        body = _get(client, token).get_data(as_text=True)

    assert '<html lang="en" data-theme="dark"' in body
    assert 'class="flex-column invite-page"' in body


def test_state_two_hrefs_follow_the_splash_contract(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link and an anonymous visitor
    WHEN they open it
    THEN 200 with exactly the two splash `next` hrefs
    """
    token = _live_token(app)
    response = _get(anonymous_client(app), token)
    main = _main_of(response)

    assert response.status_code == 200
    assert f'href="/?next=/invite/{token}"' in main
    assert f'href="/?next=/invite/{token}/register"' in main


def test_build_invite_splash_urls_exact_strings() -> None:
    """
    GIVEN a token
    WHEN the splash URLs are built
    THEN slashes stay unescaped in both
    """
    assert build_invite_splash_urls("abc") == (
        "/?next=/invite/abc",
        "/?next=/invite/abc/register",
    )


def test_member_is_redirected_into_the_utub_for_every_link_state(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a validated member and a revoked link
    WHEN they open it
    THEN a 302 to /home?UTubID=<id> with the privacy headers
    """
    token = _token_of(app, add_invite_link(app, FIRST_UTUB_ID, 1, revoked=True))
    _add_member(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        response = _get(client, token)

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/home?UTubID={FIRST_UTUB_ID}")


def test_privacy_headers_on_200_302_and_404_with_csp(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link, a member redirect and a dead token
    WHEN each is requested
    THEN each carries the three privacy headers and the CSP header
    """
    token = _live_token(app)
    anonymous_ok = _get(anonymous_client(app), token)
    anonymous_dead = _get(anonymous_client(app), UNKNOWN_TOKEN)
    _add_member(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        redirect = _get(client, token)

    assert [resp.status_code for resp in (anonymous_ok, redirect, anonymous_dead)] == [
        200,
        302,
        404,
    ]
    for response in (anonymous_ok, redirect, anonymous_dead):
        assert (
            response.headers[CONFIG_ENVS.REFERRER_POLICY]
            == CONFIG_ENVS.NO_REFERRER_POLICY_VALUE
        )
        assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
        assert response.headers["Cache-Control"] == "no-store"
        assert "Content-Security-Policy" in response.headers


def test_get_changes_no_row(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN a live link
    WHEN states 1, 2 and the member redirect are requested
    THEN no invite, member or acceptance row changes
    """
    token = _live_token(app)
    before = _snapshot(app)

    _get(anonymous_client(app), token)
    with _logged_in(app, VIEWER_ID) as (client, _):
        _get(client, token)
    assert _snapshot(app) == before
    assert [row[1] for row in before[0]] == [0]

    _add_member(app)
    before_member = _snapshot(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        _get(client, token)

    assert _snapshot(app) == before_member


# --- Unconfirmed viewer is anonymous -----------------------------------------------


def test_unconfirmed_viewer_gets_the_anonymous_live_page(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link and a logged-in user whose email is unconfirmed
    WHEN they open it
    THEN they are anonymous: state 2 with the two splash `next` hrefs, no Join form
        and no Not now link
    """
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        _set_unvalidated(app)
        response = _get(client, token)

    main = _main_of(response)
    assert response.status_code == 200
    assert f'href="/?next=/invite/{token}"' in main
    assert f'href="/?next=/invite/{token}/register"' in main
    assert 'id="inviteJoinForm"' not in main
    assert 'href="/home">Not now</a>' not in main
    assert _title_of(response) == INVITE_LINK_PAGE.TITLE_JOIN
    assert 'id="backToSplashBtn"' in response.get_data(as_text=True)


def test_unconfirmed_member_of_a_dead_link_gets_the_anonymous_dead_page(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an unconfirmed member and a revoked link
    WHEN they open it
    THEN they are anonymous: the uniform dead 404, not a member redirect
    """
    token = _token_of(app, add_invite_link(app, FIRST_UTUB_ID, 1, revoked=True))
    _add_member(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        _set_unvalidated(app)
        response = _get(client, token)
    baseline = _get(anonymous_client(app), UNKNOWN_TOKEN)

    assert response.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)
    assert INVITE_LINK_PAGE.DEAD_HEADING in unescape(response.get_data(as_text=True))


# --- Suspended session -------------------------------------------------------------


@pytest.mark.parametrize("live", [True, False])
def test_suspended_web_session_is_anonymous(
    app: Flask, every_user_makes_a_unique_utub, live: bool
) -> None:
    """
    GIVEN a logged-in user who is then suspended
    WHEN they open a live or dead link
    THEN they see state 2 (live) or the uniform 404 (dead)
    """
    token = _live_token(app) if live else UNKNOWN_TOKEN
    with _logged_in(app, VIEWER_ID) as (client, _):
        with app.app_context():
            db.session.get(Users, VIEWER_ID).is_suspended = True
            db.session.commit()
        response = _get(client, token)

    assert response.status_code == (200 if live else 404)
    if live:
        assert f'href="/?next=/invite/{token}"' in _main_of(response)
    else:
        assert INVITE_LINK_PAGE.DEAD_HEADING in unescape(
            response.get_data(as_text=True)
        )


# --- Structure, titles and navbar --------------------------------------------------


def test_structure_and_titles_for_every_state(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN states 1, 2 and 4
    WHEN each renders
    THEN each has one h1, one main, the fixed title and no UTub name in the title
    """
    token = _live_token(app)
    with app.app_context():
        utub_name = db.session.get(Utubs, FIRST_UTUB_ID).name

    pages: dict[str, Response] = {}
    pages["state2"] = _get(anonymous_client(app), token)
    pages["dead"] = _get(anonymous_client(app), UNKNOWN_TOKEN)
    with _logged_in(app, VIEWER_ID) as (client, _):
        pages["state1"] = _get(client, token)

    expected = {
        "state1": INVITE_LINK_PAGE.TITLE_JOIN,
        "state2": INVITE_LINK_PAGE.TITLE_JOIN,
        "dead": INVITE_LINK_PAGE.TITLE_DEAD,
    }
    for name, response in pages.items():
        body = response.get_data(as_text=True)
        assert body.count("<h1") == 1, name
        assert body.count("<main") == 1, name
        assert _title_of(response) == expected[name], name
        assert utub_name not in _title_of(response), name
        assert '<meta name="robots" content="noindex, nofollow">' in body, name
    other_dead = _get(anonymous_client(app), MALFORMED_TOKEN)
    assert _title_of(other_dead) == INVITE_LINK_PAGE.TITLE_DEAD


def test_navbar_items_by_viewer(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN an anonymous and a logged-in viewer
    WHEN each opens the page
    THEN backToSplashBtn is present only for anonymous; the toggler only for anonymous;
        a validated viewer has no refresh meta
    """
    token = _live_token(app)
    anonymous = _get(anonymous_client(app), token).get_data(as_text=True)
    with _logged_in(app, VIEWER_ID) as (client, _):
        logged_in = _get(client, token).get_data(as_text=True)

    assert 'id="backToSplashBtn"' in anonymous
    assert "navbar-toggler" in anonymous
    assert 'id="backToSplashBtn"' not in logged_in
    assert "navbar-toggler" not in logged_in
    assert "NavbarNavDropdown" not in logged_in
    assert 'http-equiv="refresh"' not in logged_in


def _assert_balanced_nav(nav: str, brand_close: str) -> None:
    for tag in ("div", "span", "a"):
        assert len(re.findall(rf"<{tag}[\s>]", nav)) == nav.count(f"</{tag}>"), tag
    brand_tag = "span" if brand_close == "</span>" else "a"
    assert f'<{brand_tag} class="navbar-brand navbar-start"' in nav
    assert "navbar-toggler" not in nav
    assert "NavbarNavDropdown" not in nav


def test_navbar_is_well_formed_for_logged_in_viewers(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN validated and anonymous viewers
    WHEN each opens the page
    THEN the nav's divs balance and the brand closes with the matching tag
    """
    token = _live_token(app)
    anonymous_nav = _nav_of(_get(anonymous_client(app), token))
    with _logged_in(app, VIEWER_ID) as (client, _):
        validated_nav = _nav_of(_get(client, token))

    _assert_balanced_nav(validated_nav, "</a>")
    assert anonymous_nav.count("<div") == anonymous_nav.count("</div>")
    assert "NavbarNavDropdown" in anonymous_nav


# --- Rate limit and escaping -------------------------------------------------------


def test_forced_rate_limit_returns_the_global_429_page(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link
    WHEN the GET is rate limited (X-Force-Rate-Limit)
    THEN the response is the global HTML 429 page
    """
    token = _live_token(app)
    response = _get(anonymous_client(app), token, headers={"X-Force-Rate-Limit": "1"})

    assert response.status_code == 429
    assert "text/html" in response.content_type
    body = unescape(response.get_data(as_text=True))
    assert INVITE_LINK_PAGE.TITLE_JOIN not in body
    assert INVITE_LINK_PAGE.DEAD_HEADING not in body
    assert "InviteMain" not in body


def test_utub_name_and_description_are_html_escaped(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a UTub whose name and description contain a script tag
    WHEN the page renders
    THEN the markup is escaped text, with the description in .invite-description
    """
    with app.app_context():
        utub = db.session.get(Utubs, FIRST_UTUB_ID)
        utub.name = SCRIPT_UTUB_NAME
        utub.utub_description = "<b>bold</b>"
        db.session.commit()
    token = _live_token(app)
    body = _get(anonymous_client(app), token).get_data(as_text=True)

    assert SCRIPT_UTUB_NAME not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert 'class="invite-description">&lt;b&gt;bold&lt;/b&gt;' in body


def test_page_response_module_is_a_leaf() -> None:
    """
    GIVEN the page-response module
    WHEN it is inspected
    THEN it does not import the invite services or models (no import cycle)
    """
    tree = ast.parse(Path(page_response_module.__file__).read_text())
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(
        name.startswith(
            ("backend.invite_links.services", "backend.models.utub_invite_links")
        )
        for name in imported
    )
