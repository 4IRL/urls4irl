"""Route tests for the preview fields on the manager invite-link routes (web)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend.invite_links.constants import InviteLinkErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.invite_route_helpers import (
    EXPIRY_TOLERANCE,
    error_code_of,
    invite_url,
    link_of,
    request_as,
    rows,
    seed_dead,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    NON_XHR_HEADERS,
    anonymous_client,
    logged_in_as,
)
from tests.utils_for_test import add_invite_link, lock_utub, unlock_utub

pytestmark = pytest.mark.invite_links


def _patch(app: Flask, body: Any) -> Response:
    return request_as(
        app,
        CREATOR_ID,
        "PATCH",
        invite_url(ROUTES.INVITE_LINKS.UPDATE_INVITE_LINK),
        body,
    )


def _patch_in(client: FlaskClient, csrf_token: str, body: Any) -> Response:
    """PATCH within one logged-in session (a fresh session per write fails CSRF)."""
    url = url_for(ROUTES.INVITE_LINKS.UPDATE_INVITE_LINK, utub_id=FIRST_UTUB_ID)
    return client.patch(url, json=body, headers={"X-CSRFToken": csrf_token})


def _get(app: Flask) -> Response:
    return request_as(
        app, CREATOR_ID, "GET", invite_url(ROUTES.INVITE_LINKS.GET_INVITE_LINK)
    )


def _post(app: Flask, route: str, body: Any) -> Response:
    return request_as(app, CREATOR_ID, "POST", invite_url(route), body)


def _anonymous_invite_page(app: Flask, token: str) -> Response:
    def drop_request_caches() -> None:
        # The fixture's open app context keeps the last viewer's user and CSRF token
        # on ``g``; clear them so they neither leak in nor out of this request.
        with app.test_request_context():
            g.pop("_login_user", None)
            g.pop("csrf_token", None)

    drop_request_caches()
    with app.test_request_context():
        url = url_for(ROUTES.INVITE_LINKS.INVITE_PAGE, token=token)
    response = anonymous_client(app).get(url, headers=NON_XHR_HEADERS)
    drop_request_caches()
    return response


def _when(link: dict[str, Any], key: str) -> datetime:
    return datetime.fromisoformat(link[key])


def _stored(app: Flask) -> tuple[bool, int, datetime | None]:
    row = rows(app)[0]
    return row.preview_enabled, row.preview_window_days, row.preview_ends_at


def _assert_preview_off_defaults(link: dict[str, Any]) -> None:
    assert link[MODELS.PREVIEW_ENABLED] is False
    assert link[MODELS.PREVIEW_WINDOW_DAYS] == 3
    assert link[MODELS.PREVIEW_ENDS_AT] is None
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is False
    assert link[MODELS.PREVIEW_EFFECTIVE_ENDS_AT] is None


def test_get_fresh_link_reports_preview_off(every_user_in_every_utub, app: Flask):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _get(app)

    assert response.status_code == 200
    _assert_preview_off_defaults(link_of(response))


def test_create_returns_preview_off(every_user_in_every_utub, app: Flask):
    response = _post(
        app, ROUTES.INVITE_LINKS.CREATE_INVITE_LINK, {"expires_in_days": 7}
    )

    assert response.status_code == 201
    _assert_preview_off_defaults(link_of(response))


def test_replace_returns_preview_off_even_if_old_link_was_on(
    every_user_in_every_utub, app: Flask
):
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        preview_enabled=True,
        preview_window_days=7,
        preview_ends_at=utc_now() + timedelta(days=7),
    )

    response = _post(app, ROUTES.INVITE_LINKS.REPLACE_INVITE_LINK, {})

    assert response.status_code == 201
    _assert_preview_off_defaults(link_of(response))


@pytest.mark.parametrize(
    "route",
    [ROUTES.INVITE_LINKS.CREATE_INVITE_LINK, ROUTES.INVITE_LINKS.REPLACE_INVITE_LINK],
)
def test_create_and_replace_ignore_preview_keys(
    every_user_in_every_utub, app: Flask, route: str
):
    if route == ROUTES.INVITE_LINKS.REPLACE_INVITE_LINK:
        add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _post(app, route, {"preview_enabled": True, "preview_window_days": 7})

    assert response.status_code == 201
    _assert_preview_off_defaults(link_of(response))
    assert rows(app)[-1].preview_enabled is False


def test_patch_enable_with_window_anchors_end(every_user_in_every_utub, app: Flask):
    add_invite_link(
        app, FIRST_UTUB_ID, CREATOR_ID, expires_at=utc_now() + timedelta(days=30)
    )

    response = _patch(app, {"preview_enabled": True, "preview_window_days": 7})

    assert response.status_code == 200
    link = link_of(response)
    expected_end = utc_now() + timedelta(days=7)
    assert link[MODELS.PREVIEW_ENABLED] is True
    assert link[MODELS.PREVIEW_WINDOW_DAYS] == 7
    assert abs(_when(link, MODELS.PREVIEW_ENDS_AT) - expected_end) < EXPIRY_TOLERANCE
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is True
    assert _when(link, MODELS.PREVIEW_EFFECTIVE_ENDS_AT) == min(
        _when(link, MODELS.PREVIEW_ENDS_AT), _when(link, MODELS.EXPIRES_AT)
    )
    enabled, days, ends_at = _stored(app)
    assert (enabled, days) == (True, 7)
    assert ends_at is not None and abs(ends_at - expected_end) < EXPIRY_TOLERANCE


@pytest.mark.parametrize("bad", [2, 0, True, 3.0, "3", None, 30])
def test_patch_invalid_window_rejected(every_user_in_every_utub, app: Flask, bad):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _patch(app, {"preview_window_days": bad})

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.INVALID_FORM_INPUT
    assert _stored(app) == (False, 3, None)


@pytest.mark.parametrize("bad", [None, 1, "true"])
def test_patch_invalid_enabled_rejected(every_user_in_every_utub, app: Flask, bad):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _patch(app, {"preview_enabled": bad})

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.INVALID_FORM_INPUT
    assert _stored(app) == (False, 3, None)


def test_locked_utub_patch_rejected_with_code(every_user_in_every_utub, app: Flask):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response = _patch(app, {"preview_enabled": True})

    assert response.status_code == 403
    assert error_code_of(response) == InviteLinkErrorCodes.UTUB_IS_LOCKED
    assert _stored(app) == (False, 3, None)


def test_no_link_patch_not_found_with_code(every_user_in_every_utub, app: Flask):
    response = _patch(app, {"preview_enabled": True})

    assert response.status_code == 404
    assert error_code_of(response) == InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND


@pytest.mark.parametrize(
    "state", ["expired", "used_up", "creator_demoted", "creator_not_allowed"]
)
def test_dead_link_patch_conflict_with_code(
    every_user_in_every_utub, app: Flask, state: str
):
    seed_dead(app, state)

    response = _patch(app, {"preview_enabled": True})

    assert response.status_code == 409
    assert error_code_of(response) == InviteLinkErrorCodes.DEAD_LINK_UPDATE
    assert _stored(app) == (False, 3, None)


def test_window_capped_by_expiry(every_user_in_every_utub, app: Flask):
    expires_at = utc_now() + timedelta(days=1)
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, expires_at=expires_at)

    response = _patch(app, {"preview_enabled": True, "preview_window_days": 7})

    link = link_of(response)
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is True
    assert _when(link, MODELS.PREVIEW_EFFECTIVE_ENDS_AT) == _when(
        link, MODELS.EXPIRES_AT
    )


def test_shorten_then_lengthen_expiry_keeps_stored_window(
    every_user_in_every_utub, app: Flask
):
    add_invite_link(
        app, FIRST_UTUB_ID, CREATOR_ID, expires_at=utc_now() + timedelta(days=7)
    )
    with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
        enabled = _patch_in(
            client, csrf_token, {"preview_enabled": True, "preview_window_days": 7}
        )
        stored_end = _when(link_of(enabled), MODELS.PREVIEW_ENDS_AT)
        shortened = link_of(_patch_in(client, csrf_token, {"expires_in_days": 1}))
        lengthened = link_of(_patch_in(client, csrf_token, {"expires_in_days": 30}))

    assert shortened[MODELS.PREVIEW_WINDOW_DAYS] == 7
    assert _when(shortened, MODELS.PREVIEW_ENDS_AT) == stored_end
    assert _when(shortened, MODELS.PREVIEW_EFFECTIVE_ENDS_AT) == _when(
        shortened, MODELS.EXPIRES_AT
    )
    assert (
        abs(_when(shortened, MODELS.EXPIRES_AT) - (utc_now() + timedelta(days=1)))
        < EXPIRY_TOLERANCE
    )

    assert lengthened[MODELS.PREVIEW_WINDOW_DAYS] == 7
    assert _when(lengthened, MODELS.PREVIEW_ENDS_AT) == stored_end
    assert _when(lengthened, MODELS.PREVIEW_EFFECTIVE_ENDS_AT) == stored_end


def test_turning_off_nulls_end_and_keeps_days(every_user_in_every_utub, app: Flask):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
        _patch_in(
            client, csrf_token, {"preview_enabled": True, "preview_window_days": 7}
        )
        link = link_of(_patch_in(client, csrf_token, {"preview_enabled": False}))

    assert link[MODELS.PREVIEW_ENABLED] is False
    assert link[MODELS.PREVIEW_WINDOW_DAYS] == 7
    assert link[MODELS.PREVIEW_ENDS_AT] is None
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is False
    assert link[MODELS.PREVIEW_EFFECTIVE_ENDS_AT] is None
    assert _stored(app) == (False, 7, None)


def test_past_window_end_reports_effective_off(every_user_in_every_utub, app: Flask):
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        preview_enabled=True,
        preview_window_days=1,
        preview_ends_at=utc_now() - timedelta(hours=1),
    )

    link = link_of(_get(app))

    assert link[MODELS.PREVIEW_ENABLED] is True
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is False


def test_reenable_after_lapse_reanchors(every_user_in_every_utub, app: Flask):
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        preview_enabled=True,
        preview_window_days=7,
        preview_ends_at=utc_now() - timedelta(hours=1),
    )

    link = link_of(_patch(app, {"preview_enabled": True}))

    expected_end = utc_now() + timedelta(days=7)
    assert abs(_when(link, MODELS.PREVIEW_ENDS_AT) - expected_end) < EXPIRY_TOLERANCE
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is True


def test_resent_window_on_on_row_restarts_window(every_user_in_every_utub, app: Flask):
    soon = utc_now() + timedelta(hours=2)
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        preview_enabled=True,
        preview_window_days=3,
        preview_ends_at=soon,
    )

    link = link_of(_patch(app, {"preview_window_days": 3}))

    expected_end = utc_now() + timedelta(days=3)
    assert abs(_when(link, MODELS.PREVIEW_ENDS_AT) - expected_end) < EXPIRY_TOLERANCE


def test_enable_on_row_within_end_is_noop(every_user_in_every_utub, app: Flask):
    end = utc_now() + timedelta(hours=2)
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        preview_enabled=True,
        preview_window_days=3,
        preview_ends_at=end,
    )

    link = link_of(_patch(app, {"preview_enabled": True}))

    assert _when(link, MODELS.PREVIEW_ENDS_AT) == end
    assert _stored(app)[2] == end


def test_locked_utub_get_keeps_live_status_but_effective_off(
    every_user_in_every_utub, app: Flask
):
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        preview_enabled=True,
        preview_window_days=3,
        preview_ends_at=utc_now() + timedelta(days=1),
    )
    lock_utub(app, FIRST_UTUB_ID)

    link = link_of(_get(app))

    assert link[MODELS.STATUS] == "live"
    assert link[MODELS.PREVIEW_ENABLED] is True
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is False


def test_unlock_resumes_stored_on_preview(every_user_in_every_utub, app: Flask):
    end = utc_now() + timedelta(days=1)
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        preview_enabled=True,
        preview_window_days=3,
        preview_ends_at=end,
    )
    lock_utub(app, FIRST_UTUB_ID)
    assert link_of(_get(app))[MODELS.PREVIEW_EFFECTIVE_ENABLED] is False
    token = rows(app)[0].token
    assert _anonymous_invite_page(app, token).status_code == 404

    unlock_utub(app, FIRST_UTUB_ID)

    link = link_of(_get(app))
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is True
    assert _stored(app) == (True, 3, end)
    page = _anonymous_invite_page(app, token)
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'id="invitePreviewEmpty"' in body
    assert 'id="invitePreviewBar"' in body


def test_window_only_patch_on_off_row_stores_days_only(
    every_user_in_every_utub, app: Flask
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    link = link_of(_patch(app, {"preview_window_days": 7}))

    assert link[MODELS.PREVIEW_WINDOW_DAYS] == 7
    assert link[MODELS.PREVIEW_ENABLED] is False
    assert link[MODELS.PREVIEW_ENDS_AT] is None
    assert link[MODELS.PREVIEW_EFFECTIVE_ENABLED] is False
    assert _stored(app) == (False, 7, None)
