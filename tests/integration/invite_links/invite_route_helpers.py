"""Shared helpers for the invite link manage route tests (update, replace, revoke)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from flask import Flask, url_for
from flask.wrappers import Response

from backend import db, limiter
from backend.invite_links.validity import InviteState, evaluate_invite
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    logged_in_as,
)
from tests.utils_for_test import add_invite_link, set_members_settings

DEAD_STATE_IDS: list[str] = [
    "expired",
    "used_up",
    "creator_demoted",
    "creator_not_allowed",
]
EXPIRY_TOLERANCE: timedelta = timedelta(minutes=2)


def rows(app: Flask, utub_id: int = FIRST_UTUB_ID) -> list[Utub_Invite_Links]:
    """All invite rows of a UTub, oldest first, detached from the session."""
    with app.app_context():
        db.session.expire_all()
        found = (
            db.session.query(Utub_Invite_Links)
            .filter(Utub_Invite_Links.utub_id == utub_id)
            .order_by(Utub_Invite_Links.id)
            .all()
        )
        db.session.expunge_all()
        return found


def unrevoked(app: Flask, utub_id: int = FIRST_UTUB_ID) -> list[Utub_Invite_Links]:
    return [row for row in rows(app, utub_id) if row.revoked_at is None]


def state_of_current(app: Flask, utub_id: int = FIRST_UTUB_ID) -> InviteState:
    """The validity state of the UTub's single unrevoked row (raises if none)."""
    with app.app_context():
        db.session.expire_all()
        invite = (
            db.session.query(Utub_Invite_Links)
            .filter(
                Utub_Invite_Links.utub_id == utub_id,
                Utub_Invite_Links.revoked_at.is_(None),
            )
            .one()
        )
        return evaluate_invite(invite)


_EXPECTED_DEAD_STATE: dict[str, InviteState] = {
    "expired": InviteState.EXPIRED,
    "used_up": InviteState.USED_UP,
    "creator_demoted": InviteState.CREATOR_NOT_MANAGER,
    "creator_not_allowed": InviteState.CREATOR_NOT_ALLOWED,
}


def seed_dead(app: Flask, state: str, use_count_when_used_up: int = 1) -> int:
    """Seed one dead-but-unrevoked row in the first UTub, returning its id.

    Asserts the row really is in the requested state before returning.
    """
    invite_id = _seed_dead_row(app, state, use_count_when_used_up)
    assert state_of_current(app) is _EXPECTED_DEAD_STATE[state]
    return invite_id


def _make_co_owner(app: Flask, user_id: int) -> None:
    """Make the user a co-owner of the first UTub, adding the membership if absent."""
    with app.app_context():
        membership = db.session.get(Utub_Members, (FIRST_UTUB_ID, user_id))
        if membership is None:
            db.session.add(
                Utub_Members(
                    utub_id=FIRST_UTUB_ID,
                    user_id=user_id,
                    member_role=Member_Role.CO_CREATOR,
                )
            )
        else:
            membership.member_role = Member_Role.CO_CREATOR
        db.session.commit()


def _seed_dead_row(app: Flask, state: str, use_count_when_used_up: int) -> int:
    if state == "expired":
        return add_invite_link(
            app, FIRST_UTUB_ID, CREATOR_ID, expires_at=utc_now() - timedelta(minutes=1)
        )
    if state == "used_up":
        return add_invite_link(
            app,
            FIRST_UTUB_ID,
            CREATOR_ID,
            max_uses=use_count_when_used_up,
            use_count=use_count_when_used_up,
        )
    if state == "creator_not_allowed":
        # A co-owner's link, with owner_only stored directly (no revoke).
        _make_co_owner(app, SECOND_USER_ID)
        set_members_settings(app, FIRST_UTUB_ID, {"invite_link_creators": "owner_only"})
    return add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)


def request_as(
    app: Flask,
    user_id: int,
    method: str,
    url: InviteRoute,
    body: Any = None,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    """Send one CSRF-protected AJAX JSON request as a logged-in user.

    ``url`` comes from ``invite_url``; it is resolved inside the request context.
    """
    with logged_in_as(app, user_id) as (client, csrf_token):
        headers = {"X-CSRFToken": csrf_token, **(extra_headers or {})}
        return client.open(
            url_for(url.route, utub_id=url.utub_id),
            method=method,
            json=body,
            headers=headers,
        )


def enable_limiter(app: Flask) -> None:
    original_first_request = app._got_first_request
    app._got_first_request = False
    app.config["RATELIMIT_ENABLED"] = True
    limiter.enabled = True
    limiter.init_app(app)
    app._got_first_request = original_first_request


def disable_limiter() -> None:
    if limiter._storage is not None:
        limiter._storage.reset()
    limiter._storage = None
    limiter._limiter = None
    limiter.enabled = False
    limiter.initialized = False


@dataclass(frozen=True)
class InviteRoute:
    route: str
    utub_id: int


def invite_url(route: str, utub_id: int = FIRST_UTUB_ID) -> InviteRoute:
    return InviteRoute(route=route, utub_id=utub_id)


def error_code_of(response: Response) -> int | None:
    return (response.get_json(silent=True) or {}).get(STD_JSON.ERROR_CODE)


def link_of(response: Response) -> dict[str, Any]:
    return response.get_json()[MODELS.INVITE_LINK]
