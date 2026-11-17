"""Tagging policy (members_can_tag) on every path that re-attaches a trashed URL's preserved tags.

Fixture shape: UTub 1 holds owner 1, co-owner 2, plain member 3, three tags and three
URLs. The first URL carries the first tag, is added by the plain member and is trashed,
so the member may restore it. The second URL has no tags.
"""

from __future__ import annotations

import pytest
from flask import Flask, url_for

from backend import db
from backend.models.utub_members import Member_Role
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.urls.constants import URLErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import URL_FORM
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.tag_strs import TAG_URLS_NOT_ALLOWED
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.short_links.short_link_helpers import set_url_adder
from tests.integration.trash.trash_helpers import (
    FIRST_USER_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    THIRD_USER_ID,
    get_row_state,
    login_as_user,
    post_restore,
    post_restore_urls,
)
from tests.utils_for_test import set_member_role, set_tags_settings, trash_utub_url

pytestmark = [pytest.mark.trash, pytest.mark.tags, pytest.mark.urls]

MEMBER_ID = THIRD_USER_ID
CO_OWNER_ID = SECOND_USER_ID
TAGGING_OFF = {"members_can_tag": False}
CODE_TAGGING = URLErrorCodes.TAGGING_NOT_ALLOWED


@pytest.fixture
def trashed_tagged_url(
    add_all_urls_and_users_to_each_utub_no_tags, add_tags_to_utubs, app: Flask
) -> tuple[Flask, int, int]:
    """Return (app, trashed tagged row id, tag-less live row id)."""
    set_member_role(app, FIRST_UTUB_ID, CO_OWNER_ID, Member_Role.CO_CREATOR)
    with app.app_context():
        rows = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == FIRST_UTUB_ID)
            .order_by(Utub_Urls.id)
            .all()
        )
        first_tag = (
            Utub_Tags.query.filter(Utub_Tags.utub_id == FIRST_UTUB_ID)
            .order_by(Utub_Tags.id)
            .first()
        )
        tagged_id, plain_id = rows[0].id, rows[1].id
        db.session.add(
            Utub_Url_Tags(
                utub_id=FIRST_UTUB_ID, utub_url_id=tagged_id, utub_tag_id=first_tag.id
            )
        )
        db.session.commit()
    set_url_adder(app, tagged_id, MEMBER_ID)
    trash_utub_url(app, tagged_id, deleted_by=MEMBER_ID)
    return app, tagged_id, plain_id


def _is_trashed(app: Flask, utub_url_id: int) -> bool:
    return get_row_state(app, utub_url_id)["deleted_at"] is not None


def _assert_refused(response, app: Flask, utub_url_id: int) -> None:
    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.ERROR_CODE] == CODE_TAGGING
    assert body[STD_JSON.MESSAGE] == TAG_URLS_NOT_ALLOWED
    assert _is_trashed(app, utub_url_id)


# ---------------------------------------------------------------------------
# Single and bulk in-place restore
# ---------------------------------------------------------------------------


def test_member_restore_refused_when_tagging_off(trashed_tagged_url):
    """
    GIVEN Tagging off and a trashed URL with preserved tags the member added
    WHEN the plain member restores it in place
    THEN 403 errorCode 18 and the row stays trashed
    """
    app, tagged_id, _ = trashed_tagged_url
    set_tags_settings(app, FIRST_UTUB_ID, TAGGING_OFF)

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = post_restore(client, csrf_token, FIRST_UTUB_ID, tagged_id)

    _assert_refused(response, app, tagged_id)


def test_member_restore_allowed_when_tagging_on(trashed_tagged_url):
    """
    GIVEN Tagging on (the default)
    WHEN the plain member restores the tagged URL in place
    THEN 200 and the row is live again
    """
    app, tagged_id, _ = trashed_tagged_url

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = post_restore(client, csrf_token, FIRST_UTUB_ID, tagged_id)

    assert response.status_code == 200
    assert not _is_trashed(app, tagged_id)


@pytest.mark.parametrize("manager_id", [FIRST_USER_ID, CO_OWNER_ID])
def test_manager_restore_allowed_when_tagging_off(trashed_tagged_url, manager_id):
    """
    GIVEN Tagging off
    WHEN a manager restores the member's tagged URL in place
    THEN 200 and the row is live again
    """
    app, tagged_id, _ = trashed_tagged_url
    set_tags_settings(app, FIRST_UTUB_ID, TAGGING_OFF)

    with login_as_user(app, manager_id) as (client, csrf_token):
        response = post_restore(client, csrf_token, FIRST_UTUB_ID, tagged_id)

    assert response.status_code == 200
    assert not _is_trashed(app, tagged_id)


def test_member_restore_of_tagless_url_allowed_when_tagging_off(trashed_tagged_url):
    """
    GIVEN Tagging off and a trashed URL with no preserved tags
    WHEN the plain member restores it in place
    THEN 200 (no tag is re-attached, so nothing to gate)
    """
    app, _, plain_id = trashed_tagged_url
    set_url_adder(app, plain_id, MEMBER_ID)
    trash_utub_url(app, plain_id, deleted_by=MEMBER_ID)
    set_tags_settings(app, FIRST_UTUB_ID, TAGGING_OFF)

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = post_restore(client, csrf_token, FIRST_UTUB_ID, plain_id)

    assert response.status_code == 200
    assert not _is_trashed(app, plain_id)


def test_member_bulk_restore_refused_when_tagging_off(trashed_tagged_url):
    """
    GIVEN Tagging off and a trashed URL with preserved tags the member added
    WHEN the plain member bulk-restores it
    THEN the whole request is 403 errorCode 18 and the row stays trashed
    """
    app, tagged_id, _ = trashed_tagged_url
    set_tags_settings(app, FIRST_UTUB_ID, TAGGING_OFF)

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [tagged_id])

    _assert_refused(response, app, tagged_id)


def test_member_bulk_restore_allowed_when_tagging_on(trashed_tagged_url):
    """
    GIVEN Tagging on
    WHEN the plain member bulk-restores the tagged URL
    THEN 200 with it restored
    """
    app, tagged_id, _ = trashed_tagged_url

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [tagged_id])

    assert response.status_code == 200
    assert response.get_json()["totalRestored"] == 1
    assert not _is_trashed(app, tagged_id)


def test_manager_bulk_restore_allowed_when_tagging_off(trashed_tagged_url):
    """
    GIVEN Tagging off
    WHEN the owner bulk-restores the member's tagged URL
    THEN 200 with it restored
    """
    app, tagged_id, _ = trashed_tagged_url
    set_tags_settings(app, FIRST_UTUB_ID, TAGGING_OFF)

    with login_as_user(app, FIRST_USER_ID) as (client, csrf_token):
        response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [tagged_id])

    assert response.status_code == 200
    assert not _is_trashed(app, tagged_id)


# ---------------------------------------------------------------------------
# Revive by re-adding the same link
# ---------------------------------------------------------------------------


def _url_string(app: Flask, utub_url_id: int) -> str:
    with app.app_context():
        return Utub_Urls.query.get(utub_url_id).standalone_url.url_string


def test_member_readd_revive_refused_when_tagging_off(trashed_tagged_url):
    """
    GIVEN Tagging off and a trashed URL whose preserved tags the member could keep
    WHEN the plain member re-adds the same link (a revive)
    THEN 403 errorCode 18 and the row stays trashed
    """
    app, tagged_id, _ = trashed_tagged_url
    set_tags_settings(app, FIRST_UTUB_ID, TAGGING_OFF)

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = client.post(
            url_for(ROUTES.URLS.CREATE_URL, utub_id=FIRST_UTUB_ID),
            json={
                URL_FORM.URL_STRING: _url_string(app, tagged_id),
                URL_FORM.URL_TITLE: "Revive title",
            },
            headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
        )

    _assert_refused(response, app, tagged_id)


def test_member_readd_revive_allowed_when_tagging_on(trashed_tagged_url):
    """
    GIVEN Tagging on
    WHEN the plain member re-adds the trashed link
    THEN 200 and the row is live again
    """
    app, tagged_id, _ = trashed_tagged_url

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = client.post(
            url_for(ROUTES.URLS.CREATE_URL, utub_id=FIRST_UTUB_ID),
            json={
                URL_FORM.URL_STRING: _url_string(app, tagged_id),
                URL_FORM.URL_TITLE: "Revive title",
            },
            headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
        )

    assert response.status_code == 200
    assert not _is_trashed(app, tagged_id)


def test_manager_readd_revive_allowed_when_tagging_off(trashed_tagged_url):
    """
    GIVEN Tagging off
    WHEN the owner re-adds the trashed link
    THEN 200 and the row is live again
    """
    app, tagged_id, _ = trashed_tagged_url
    set_tags_settings(app, FIRST_UTUB_ID, TAGGING_OFF)

    with login_as_user(app, FIRST_USER_ID) as (client, csrf_token):
        response = client.post(
            url_for(ROUTES.URLS.CREATE_URL, utub_id=FIRST_UTUB_ID),
            json={
                URL_FORM.URL_STRING: _url_string(app, tagged_id),
                URL_FORM.URL_TITLE: "Revive title",
            },
            headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
        )

    assert response.status_code == 200
    assert not _is_trashed(app, tagged_id)


# ---------------------------------------------------------------------------
# Revive by editing a card's link to a trashed link
# ---------------------------------------------------------------------------


def _edit_link(client, csrf_token: str, utub_url_id: int, url_string: str):
    return client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=utub_url_id),
        json={URL_FORM.URL_STRING: url_string},
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def test_member_edit_revive_refused_when_tagging_off(trashed_tagged_url):
    """
    GIVEN Tagging off, a trashed tagged URL and a live URL the member added
    WHEN the member edits the live card's link to the trashed link (a revive)
    THEN 403 errorCode 18 and the trashed row stays trashed
    """
    app, tagged_id, plain_id = trashed_tagged_url
    set_url_adder(app, plain_id, MEMBER_ID)
    set_tags_settings(app, FIRST_UTUB_ID, TAGGING_OFF)

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = _edit_link(client, csrf_token, plain_id, _url_string(app, tagged_id))

    _assert_refused(response, app, tagged_id)
    assert not _is_trashed(app, plain_id)


def test_member_edit_revive_allowed_when_tagging_on(trashed_tagged_url):
    """
    GIVEN Tagging on
    WHEN the member edits their live card's link to the trashed link
    THEN 200 and the trashed row is live again
    """
    app, tagged_id, plain_id = trashed_tagged_url
    set_url_adder(app, plain_id, MEMBER_ID)

    with login_as_user(app, MEMBER_ID) as (client, csrf_token):
        response = _edit_link(client, csrf_token, plain_id, _url_string(app, tagged_id))

    assert response.status_code == 200
    assert not _is_trashed(app, tagged_id)
