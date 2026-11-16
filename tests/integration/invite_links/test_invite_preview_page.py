"""Route tests for state 3, the logged-out read-only preview on ``GET /invite/<token>``."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from html import escape, unescape

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.invite_links.constants import INVITE_LINK_PREVIEW_MAX_URLS
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.invite_link_strs import INVITE_LINK_PAGE
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    NON_XHR_HEADERS,
    SECOND_USER_ID,
    THIRD_USER_ID,
    anonymous_client,
    logged_in_as,
    normalized_body,
)
from tests.utils_for_test import (
    add_invite_link,
    add_short_link,
    lock_utub,
    trash_utub,
    trash_utub_url,
    unlock_utub,
)

pytestmark = pytest.mark.invite_links

UNKNOWN_TOKEN = "Z" * 22
UTUB_NAME = "Zorblax Preview Utub"
UTUB_DESCRIPTION = "Qwerty description for previewers"
ADDER_NAME = "adderuniqueuser"
TAGGER_NAME = "taggeruniqueuser"
SHORT_CODE = "SHRTCODE12"


def _preview_link(app: Flask, **kwargs) -> str:
    """Seed a live, preview-on link in the first UTub and return its token."""
    kwargs.setdefault("preview_enabled", True)
    kwargs.setdefault("preview_ends_at", utc_now() + timedelta(days=3))
    invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, **kwargs)
    return _token_of(app, invite_id)


def _token_of(app: Flask, invite_id: int) -> str:
    with app.app_context():
        return db.session.get(Utub_Invite_Links, invite_id).token


def _remove_member(app: Flask, user_id: int) -> None:
    with app.app_context():
        Utub_Members.query.filter_by(utub_id=FIRST_UTUB_ID, user_id=user_id).delete()
        db.session.commit()


def _seed_url(
    app: Flask,
    *,
    url: str,
    title: str | None,
    tags: tuple[str, ...] = (),
    adder_id: int = SECOND_USER_ID,
    tagger_id: int = THIRD_USER_ID,
    added_at: datetime | None = None,
) -> int:
    """Add one URL (and tags) to the first UTub directly; returns the UtubUrls id."""
    with app.app_context():
        standalone = Urls.query.filter_by(url_string=url).first()
        if standalone is None:
            standalone = Urls(normalized_url=url, current_user_id=adder_id)
            db.session.add(standalone)
            db.session.flush()
        utub_url = Utub_Urls(
            utub_id=FIRST_UTUB_ID,
            url_id=standalone.id,
            user_id=adder_id,
            url_title=title,
        )
        if added_at is not None:
            utub_url.added_at = added_at
        db.session.add(utub_url)
        db.session.flush()
        for tag_string in tags:
            tag = Utub_Tags.query.filter_by(
                utub_id=FIRST_UTUB_ID, tag_string=tag_string
            ).first()
            if tag is None:
                tag = Utub_Tags(
                    utub_id=FIRST_UTUB_ID, tag_string=tag_string, created_by=tagger_id
                )
                db.session.add(tag)
                db.session.flush()
            db.session.add(
                Utub_Url_Tags(
                    utub_id=FIRST_UTUB_ID,
                    utub_url_id=utub_url.id,
                    utub_tag_id=tag.id,
                    user_id=tagger_id,
                )
            )
        db.session.commit()
        return utub_url.id


def _rename_users_and_utub(app: Flask) -> None:
    with app.app_context():
        db.session.get(Users, SECOND_USER_ID).username = ADDER_NAME
        db.session.get(Users, THIRD_USER_ID).username = TAGGER_NAME
        utub = db.session.get(Utubs, FIRST_UTUB_ID)
        utub.name = UTUB_NAME
        utub.utub_description = UTUB_DESCRIPTION
        db.session.commit()


def _creator_username(app: Flask) -> str:
    with app.app_context():
        return db.session.get(Users, CREATOR_ID).username


def _get(client: FlaskClient, token: str) -> Response:
    with client.application.test_request_context():
        g.pop("_login_user", None)
        url = url_for(ROUTES.INVITE_LINKS.INVITE_PAGE, token=token)
    return client.get(url, headers=NON_XHR_HEADERS)


def _get_anon(app: Flask, token: str) -> Response:
    return _get(anonymous_client(app), token)


def _html(response: Response) -> str:
    return response.get_data(as_text=True)


def _list_of(response: Response) -> str:
    match = re.search(
        r'<ul id="invitePreviewList".*?</ul>\s*(?=<p id="invitePreviewMore"|</section>)',
        _html(response),
        re.DOTALL,
    )
    assert match is not None
    return match.group(0)


def _cards(response: Response) -> list[str]:
    return re.findall(r'<li class="invite-preview-card">', _html(response), re.DOTALL)


def _body_tag(response: Response) -> str:
    match = re.search(r"<body[^>]*>", _html(response))
    assert match is not None
    return match.group(0)


def _post_join(client: FlaskClient, token: str, csrf_token: str) -> Response:
    with client.application.test_request_context():
        g.pop("_login_user", None)
        url = url_for(ROUTES.INVITE_LINKS.JOIN_INVITE_PAGE, token=token)
    return client.post(url, data={"csrf_token": csrf_token}, headers=NON_XHR_HEADERS)


def _assert_no_preview(response: Response) -> None:
    html = _html(response)
    assert "invitePreviewList" not in html
    assert "invitePreviewBar" not in html
    assert "invitePreviewSkip" not in html
    assert "invitePreviewBadge" not in html
    assert "invite-preview" not in _body_tag(response)


# --- Allowlist ---------------------------------------------------------------------


def test_preview_renders_allowlisted_fields_only(
    app: Flask, every_user_in_every_utub
) -> None:
    """
    GIVEN a preview-on link whose URLs were added/tagged by other members
    WHEN an anonymous visitor opens it
    THEN the name, description, titles, URLs and tags show, and nothing else leaks
    """
    _rename_users_and_utub(app)
    first = _seed_url(
        app,
        url="https://example.com/one?a=1&b=2",
        title="Alpha <b>title</b>",
        tags=("tagzeta", "Tagalpha"),
    )
    _seed_url(app, url="https://example.org/two", title=None)
    add_short_link(app, first, SECOND_USER_ID, code=SHORT_CODE)
    token = _preview_link(app)
    creator = _creator_username(app)

    response = _get_anon(app, token)
    html = _html(response)

    assert response.status_code == 200
    assert escape(UTUB_NAME) in html
    assert escape(UTUB_DESCRIPTION) in html
    assert escape("Alpha <b>title</b>") in html
    assert "<b>title</b>" not in html
    assert escape("https://example.com/one?a=1&b=2") in html
    assert "https://example.org/two" in html
    assert "tagzeta" in html and "Tagalpha" in html
    # Tags sorted case-insensitively.
    assert html.index("Tagalpha") < html.index("tagzeta")
    assert ADDER_NAME not in html
    assert TAGGER_NAME not in html
    assert SHORT_CODE not in html
    assert "/s/" not in html
    assert "member" not in _main_text(response).lower()
    assert f"{creator} invited you to join" in unescape(html)

    listing = _list_of(response)
    assert "data-" not in listing
    assert re.findall(r'\sid="([^"]*)"', listing) == ["invitePreviewList"]
    hrefs = re.findall(r'href="([^"]*)"', listing)
    assert sorted(unescape(href) for href in hrefs) == sorted(
        ["https://example.com/one?a=1&b=2", "https://example.org/two"]
    )


def _main_text(response: Response) -> str:
    match = re.search(r"<main.*?</main>", _html(response), re.DOTALL)
    assert match is not None
    return re.sub(r"<[^>]+>", " ", match.group(0))


# --- Off / lapsed / dead -----------------------------------------------------------


def test_off_by_default_renders_state_two(app: Flask, every_user_in_every_utub) -> None:
    _seed_url(app, url="https://example.com/x", title="X")
    token = _preview_link(app, preview_enabled=False, preview_ends_at=None)

    response = _get_anon(app, token)

    assert response.status_code == 200
    _assert_no_preview(response)
    assert "invite-page" in _body_tag(response)


def test_lapsed_window_renders_state_two_and_join_still_works(
    app: Flask, every_user_in_every_utub
) -> None:
    """
    GIVEN a stored-on link whose window has passed
    THEN anonymous gets state 2 and a logged-in non-member can still join
    """
    _remove_member(app, THIRD_USER_ID)
    _seed_url(app, url="https://example.com/x", title="X")
    token = _preview_link(app, preview_ends_at=utc_now() - timedelta(minutes=1))

    response = _get_anon(app, token)
    assert response.status_code == 200
    _assert_no_preview(response)

    with app.test_request_context():
        # Drop the per-``g`` caches the anonymous request left in the fixture's open
        # app context: Flask-Login's user and Flask-WTF's CSRF token (which would
        # otherwise be reused for the logged-in session and fail validation).
        g.pop("_login_user", None)
        g.pop("csrf_token", None)
    with logged_in_as(app, THIRD_USER_ID) as (client, csrf_token):
        join = _post_join(client, token, csrf_token)
    assert join.status_code == 302
    assert join.headers["Location"].endswith(f"/home?UTubID={FIRST_UTUB_ID}")


def test_expiry_before_window_end_caps_the_label(
    app: Flask, every_user_in_every_utub
) -> None:
    expires = utc_now() + timedelta(days=1)
    token = _preview_link(
        app, expires_at=expires, preview_ends_at=utc_now() + timedelta(days=7)
    )

    response = _get_anon(app, token)
    html = _html(response)

    expires_utc = expires.astimezone(timezone.utc)
    label = f"{expires_utc:%b} {expires_utc.day}, {expires_utc.year}"
    match = re.search(r'<time datetime="([^"]*)">([^<]*)</time>', html)
    assert match is not None
    assert match.group(2) == label
    assert datetime.fromisoformat(match.group(1)) == expires


def test_validated_non_member_sees_state_one_and_member_is_redirected(
    app: Flask, every_user_in_every_utub
) -> None:
    _remove_member(app, THIRD_USER_ID)
    _seed_url(app, url="https://example.com/x", title="X")
    token = _preview_link(app)

    with logged_in_as(app, THIRD_USER_ID) as (client, _):
        non_member = _get(client, token)
    with logged_in_as(app, SECOND_USER_ID) as (client, _):
        member = _get(client, token)

    assert non_member.status_code == 200
    _assert_no_preview(non_member)
    assert INVITE_LINK_PAGE.JOIN_LABEL in _html(non_member)
    assert member.status_code == 302
    assert "invitePreview" not in _html(member)


def _dead_preview_expired(app: Flask) -> str:
    return _preview_link(app, expires_at=utc_now() - timedelta(minutes=1))


def _dead_preview_revoked(app: Flask) -> str:
    return _preview_link(app, revoked=True)


def _dead_preview_used_up(app: Flask) -> str:
    return _preview_link(app, max_uses=1, use_count=1)


def _dead_preview_locked(app: Flask) -> str:
    token = _preview_link(app)
    lock_utub(app, FIRST_UTUB_ID)
    return token


def _dead_preview_trashed(app: Flask) -> str:
    token = _preview_link(app)
    trash_utub(app, FIRST_UTUB_ID, CREATOR_ID)
    return token


def _dead_preview_creator_demoted(app: Flask) -> str:
    # Created by a plain member, so the link is dead (creator not an owner/co-owner).
    invite_id = add_invite_link(
        app,
        FIRST_UTUB_ID,
        SECOND_USER_ID,
        preview_enabled=True,
        preview_ends_at=utc_now() + timedelta(days=3),
    )
    return _token_of(app, invite_id)


@pytest.mark.parametrize(
    "make_dead",
    [
        pytest.param(_dead_preview_expired, id="expired"),
        pytest.param(_dead_preview_revoked, id="revoked"),
        pytest.param(_dead_preview_used_up, id="used_up"),
        pytest.param(_dead_preview_locked, id="locked"),
        pytest.param(_dead_preview_trashed, id="trashed"),
        pytest.param(_dead_preview_creator_demoted, id="creator_demoted"),
    ],
)
def test_dead_preview_on_link_is_the_identical_dead_page(
    app: Flask, every_user_in_every_utub, make_dead
) -> None:
    _seed_url(app, url="https://example.com/x", title="X")
    token = make_dead(app)

    baseline = _get_anon(app, UNKNOWN_TOKEN)
    response = _get_anon(app, token)

    assert response.status_code == 404
    assert normalized_body(response) == normalized_body(baseline)
    _assert_no_preview(response)


def test_join_post_without_session_rerenders_state_two_with_login_message(
    app: Flask, every_user_in_every_utub
) -> None:
    _seed_url(app, url="https://example.com/x", title="X")
    token = _preview_link(app)

    with logged_in_as(app, THIRD_USER_ID) as (client, csrf_token):
        with client.application.test_request_context():
            g.pop("_login_user", None)
            logout_url = url_for(ROUTES.USERS.LOGOUT)
        client.get(logout_url)
        response = _post_join(client, token, csrf_token)

    assert response.status_code == 401
    assert INVITE_LINK_PAGE.LOGIN_MESSAGE in unescape(_html(response))
    _assert_no_preview(response)


def test_lock_then_unlock_restores_state_three(
    app: Flask, every_user_in_every_utub
) -> None:
    """
    GIVEN a preview-on link
    WHEN the UTub is locked and then unlocked
    THEN the anonymous page is the dead 404 while locked and state 3 again after
    """
    _seed_url(app, url="https://example.com/x", title="X")
    token = _preview_link(app)
    assert 'id="invitePreviewList"' in _html(_get_anon(app, token))

    lock_utub(app, FIRST_UTUB_ID)
    locked = _get_anon(app, token)
    assert locked.status_code == 404
    _assert_no_preview(locked)

    unlock_utub(app, FIRST_UTUB_ID)
    restored = _get_anon(app, token)
    assert restored.status_code == 200
    assert 'id="invitePreviewList"' in _html(restored)
    assert 'id="invitePreviewBar"' in _html(restored)


# --- Cap, count, ordering ----------------------------------------------------------


def test_cap_shows_25_of_26_with_one_more_line(
    app: Flask, every_user_in_every_utub
) -> None:
    base = utc_now() - timedelta(hours=1)
    for index in range(INVITE_LINK_PREVIEW_MAX_URLS + 1):
        _seed_url(
            app,
            url=f"https://example.com/cap/{index}",
            title=f"T{index}",
            added_at=base + timedelta(seconds=index),
        )
    token = _preview_link(app)

    response = _get_anon(app, token)
    html = _html(response)

    assert len(_cards(response)) == INVITE_LINK_PREVIEW_MAX_URLS
    assert INVITE_LINK_PAGE.PREVIEW_MORE_TEMPLATE.format(count=1) in html
    assert INVITE_LINK_PAGE.PREVIEW_URL_COUNT_TEMPLATE.format(count=26) in html
    # Newest first: the oldest (index 0) is the one hidden.
    assert "https://example.com/cap/25" in html
    assert 'https://example.com/cap/0"' not in html
    assert html.index("cap/25") < html.index("cap/24")


def test_exactly_25_has_no_more_line(app: Flask, every_user_in_every_utub) -> None:
    for index in range(INVITE_LINK_PREVIEW_MAX_URLS):
        _seed_url(app, url=f"https://example.com/n/{index}", title=f"T{index}")
    token = _preview_link(app)

    response = _get_anon(app, token)

    assert len(_cards(response)) == INVITE_LINK_PREVIEW_MAX_URLS
    assert "invitePreviewMore" not in _html(response)


def test_trashed_url_is_neither_listed_nor_counted(
    app: Flask, every_user_in_every_utub
) -> None:
    _seed_url(app, url="https://example.com/live", title="Live")
    trashed = _seed_url(app, url="https://example.com/trashed", title="Trashed")
    trash_utub_url(app, trashed, CREATOR_ID)
    token = _preview_link(app)

    response = _get_anon(app, token)
    html = _html(response)

    assert "example.com/trashed" not in html
    assert "Trashed" not in html
    assert INVITE_LINK_PAGE.PREVIEW_URL_COUNT_ONE in html


def test_empty_utub_shows_empty_message_and_zero_count(
    app: Flask, every_user_in_every_utub
) -> None:
    token = _preview_link(app)

    response = _get_anon(app, token)
    html = _html(response)

    assert response.status_code == 200
    assert 'id="invitePreviewEmpty"' in html
    assert "invitePreviewList" not in html
    assert INVITE_LINK_PAGE.PREVIEW_EMPTY in html
    assert INVITE_LINK_PAGE.PREVIEW_URL_COUNT_TEMPLATE.format(count=0) in html


def test_ordering_is_newest_first(app: Flask, every_user_in_every_utub) -> None:
    base = utc_now() - timedelta(hours=1)
    _seed_url(app, url="https://example.com/old", title="Old", added_at=base)
    _seed_url(
        app,
        url="https://example.com/new",
        title="New",
        added_at=base + timedelta(minutes=5),
    )
    token = _preview_link(app)

    html = _html(_get_anon(app, token))

    assert html.index("example.com/new") < html.index("example.com/old")


# --- Markup, body class, skip link -------------------------------------------------


def test_body_class_bar_and_skip_link_only_on_state_three(
    app: Flask, every_user_in_every_utub
) -> None:
    _seed_url(app, url="https://example.com/x", title="X")
    token = _preview_link(app)

    response = _get_anon(app, token)
    html = _html(response)

    body = _body_tag(response)
    assert "invite-preview" in body and "invite-page" in body
    assert 'id="invitePreviewBar"' in html
    assert 'tabindex="-1"' in re.search(
        r'<div id="invitePreviewBar"[^>]*>', html
    ).group(0)
    skip = re.search(r'<a id="invitePreviewSkip"[^>]*>([^<]*)</a>', html)
    assert skip is not None
    assert 'href="#invitePreviewBar"' in skip.group(0)
    assert skip.group(1) == INVITE_LINK_PAGE.PREVIEW_SKIP_LINK
    assert html.index("invitePreviewSkip") < html.index('id="invitePreviewList"')
    assert 'id="invitePreviewCreateAccount"' in html
    assert 'id="invitePreviewLogIn"' in html
    assert "<h2" not in html.split("invitePreviewBar", 1)[1]


def test_non_preview_states_have_no_preview_markup(
    app: Flask, every_user_in_every_utub
) -> None:
    token = _preview_link(app, preview_enabled=False, preview_ends_at=None)

    state_two = _get_anon(app, token)

    _assert_no_preview(state_two)
    assert "invite-page" in _body_tag(state_two)


def test_non_web_url_is_plain_text_and_web_anchors_are_hardened(
    app: Flask, every_user_in_every_utub
) -> None:
    _seed_url(app, url="https://example.com/web", title="Web")
    _seed_url(app, url="ftp://files.example.com/pub", title="Ftp")
    token = _preview_link(app)

    response = _get_anon(app, token)
    listing = _list_of(response)

    anchors = re.findall(r"<a [^>]*>", listing)
    assert len(anchors) == 1
    assert 'href="https://example.com/web"' in anchors[0]
    assert 'target="_blank"' in anchors[0]
    assert 'rel="noopener noreferrer nofollow"' in anchors[0]
    assert INVITE_LINK_PAGE.PREVIEW_NEW_TAB in listing
    assert (
        '<span class="invite-preview-url">ftp://files.example.com/pub</span>' in listing
    )


def test_structure_title_and_privacy_headers(
    app: Flask, every_user_in_every_utub
) -> None:
    _seed_url(app, url="https://example.com/x", title="X")
    token = _preview_link(app)

    response = _get_anon(app, token)
    html = _html(response)

    assert html.count("<h1") == 1
    assert html.count("<main") == 1
    assert (
        re.search(r"<title>(.*?)</title>", html).group(1) == INVITE_LINK_PAGE.TITLE_JOIN
    )
    assert "noindex" in html
    assert (
        response.headers[CONFIG_ENVS.REFERRER_POLICY]
        == CONFIG_ENVS.NO_REFERRER_POLICY_VALUE
    )
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert response.headers["Cache-Control"] == "no-store"


def test_get_changes_no_rows(app: Flask, every_user_in_every_utub) -> None:
    _seed_url(app, url="https://example.com/x", title="X")
    token = _preview_link(app)

    def snapshot() -> tuple:
        with app.app_context():
            db.session.expire_all()
            return (
                [
                    (row.id, row.use_count, row.preview_ends_at, row.revoked_at)
                    for row in Utub_Invite_Links.query.order_by(Utub_Invite_Links.id)
                ],
                Utub_Urls.query.count(),
                Utub_Url_Tags.query.count(),
            )

    before = snapshot()
    _get_anon(app, token)
    assert snapshot() == before
