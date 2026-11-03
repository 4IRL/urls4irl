"""Shared helpers for the invite link manage route tests (update, replace, revoke)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from flask import Flask, url_for
from flask.wrappers import Response

from backend import db
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    logged_in_as,
)
from tests.utils_for_test import add_invite_link

DEAD_STATE_IDS: list[str] = ["expired", "used_up", "creator_demoted"]
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


def seed_dead(app: Flask, state: str, use_count_when_used_up: int = 1) -> int:
    """Seed one dead-but-unrevoked row in the first UTub, returning its id."""
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
