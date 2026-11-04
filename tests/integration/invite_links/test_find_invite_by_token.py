from __future__ import annotations

from datetime import timedelta

import pytest
from flask import Flask
from sqlalchemy import event

from backend import db
from backend.invite_links.constants import INVITE_LINK_TOKEN_LENGTH
from backend.invite_links.lookup import find_invite_by_token
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.utils.datetime_utils import utc_now
from tests.integration.invite_links.invite_route_helpers import seed_dead
from tests.utils_for_test import add_invite_link

pytestmark = pytest.mark.invite_links

FIRST_UTUB_ID: int = 1
CREATOR_ID: int = 1

MALFORMED_TOKENS: list[str] = [
    "a" * (INVITE_LINK_TOKEN_LENGTH - 1),
    "a" * (INVITE_LINK_TOKEN_LENGTH + 1),
    "a" * (INVITE_LINK_TOKEN_LENGTH - 1) + "/",
    "a" * (INVITE_LINK_TOKEN_LENGTH - 1) + " ",
    "",
    "a" * (INVITE_LINK_TOKEN_LENGTH - 1) + "é",
    "a" * INVITE_LINK_TOKEN_LENGTH + "\n",
]


def _token_of(app: Flask, invite_id: int) -> str:
    with app.app_context():
        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert invite is not None
        return invite.token


@pytest.mark.parametrize("token", MALFORMED_TOKENS)
def test_malformed_token_returns_none_without_a_query(
    every_user_in_every_utub, app: Flask, token: str
) -> None:
    """
    GIVEN a malformed token
    WHEN it is looked up
    THEN None is returned and no SQL statement is issued
    """
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", _record)
        try:
            assert find_invite_by_token(token) is None
        finally:
            event.remove(db.engine, "before_cursor_execute", _record)

    assert statements == []


def test_unknown_well_formed_token_returns_none(
    every_user_in_every_utub, app: Flask
) -> None:
    """
    GIVEN a well-formed token that matches no row
    WHEN it is looked up
    THEN None is returned
    """
    with app.app_context():
        assert find_invite_by_token("A" * INVITE_LINK_TOKEN_LENGTH) is None


@pytest.mark.parametrize("state", ["live", "revoked", "expired", "used_up"])
def test_row_is_returned_in_every_state(
    every_user_in_every_utub, app: Flask, state: str
) -> None:
    """
    GIVEN a live, revoked, expired or used-up row
    WHEN it is looked up by token
    THEN the row is returned (revoked rows are dead, not missing)
    """
    if state == "live":
        invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    elif state == "revoked":
        invite_id = add_invite_link(
            app,
            FIRST_UTUB_ID,
            CREATOR_ID,
            expires_at=utc_now() + timedelta(days=1),
            revoked=True,
        )
    else:
        invite_id = seed_dead(app, state)
    token = _token_of(app, invite_id)

    with app.app_context():
        found = find_invite_by_token(token)
        assert found is not None
        assert found.id == invite_id
