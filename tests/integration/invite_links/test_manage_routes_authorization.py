"""Cross-route authorization table for update, replace and revoke."""

from __future__ import annotations

import pytest
from flask import Flask

from backend.invite_links.constants import InviteLinkErrorCodes
from backend.utils.all_routes import ROUTES
from tests.integration.invite_links.invite_route_helpers import (
    error_code_of,
    invite_url,
    request_as,
    rows,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
)
from tests.utils_for_test import add_invite_link, lock_utub, remove_member, trash_utub

pytestmark = pytest.mark.invite_links

ROUTE_CASES = [
    pytest.param(
        ROUTES.INVITE_LINKS.UPDATE_INVITE_LINK, "PATCH", {"max_uses": 5}, id="update"
    ),
    pytest.param(ROUTES.INVITE_LINKS.REPLACE_INVITE_LINK, "POST", {}, id="replace"),
    pytest.param(ROUTES.INVITE_LINKS.REVOKE_INVITE_LINK, "DELETE", None, id="revoke"),
]


def _assert_row_unchanged(app: Flask, before: tuple) -> None:
    all_rows = rows(app)
    assert len(all_rows) == 1
    row = all_rows[0]
    assert (row.token, row.expires_at, row.max_uses, row.revoked_at) == before


def _seed(app: Flask) -> tuple:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    row = rows(app)[0]
    return (row.token, row.expires_at, row.max_uses, row.revoked_at)


@pytest.mark.parametrize("route, method, body", ROUTE_CASES)
def test_plain_member_forbidden_without_code(
    every_user_in_every_utub, app: Flask, route: str, method: str, body
) -> None:
    before = _seed(app)

    response = request_as(app, SECOND_USER_ID, method, invite_url(route), body)

    assert response.status_code == 403
    assert error_code_of(response) is None
    _assert_row_unchanged(app, before)


@pytest.mark.parametrize("route, method, body", ROUTE_CASES)
def test_non_member_not_found_without_code(
    every_user_in_every_utub, app: Flask, route: str, method: str, body
) -> None:
    before = _seed(app)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = request_as(app, SECOND_USER_ID, method, invite_url(route), body)

    assert response.status_code == 404
    assert error_code_of(response) is None
    _assert_row_unchanged(app, before)


@pytest.mark.parametrize("route, method, body", ROUTE_CASES)
def test_trashed_utub_not_found_without_code(
    every_user_in_every_utub, app: Flask, route: str, method: str, body
) -> None:
    before = _seed(app)
    trash_utub(app, FIRST_UTUB_ID, CREATOR_ID)

    response = request_as(app, CREATOR_ID, method, invite_url(route), body)

    assert response.status_code == 404
    assert error_code_of(response) is None
    _assert_row_unchanged(app, before)


@pytest.mark.parametrize("route, method, body", ROUTE_CASES)
def test_missing_utub_not_found_without_code(
    every_user_in_every_utub, app: Flask, route: str, method: str, body
) -> None:
    response = request_as(
        app, CREATOR_ID, method, invite_url(route, NONEXISTENT_ID), body
    )

    assert response.status_code == 404
    assert error_code_of(response) is None


@pytest.mark.parametrize("route, method, body", ROUTE_CASES)
def test_locked_utub_rejected_with_code(
    every_user_in_every_utub, app: Flask, route: str, method: str, body
) -> None:
    before = _seed(app)
    lock_utub(app, FIRST_UTUB_ID)

    response = request_as(app, CREATOR_ID, method, invite_url(route), body)

    assert response.status_code == 403
    assert error_code_of(response) == InviteLinkErrorCodes.UTUB_IS_LOCKED
    _assert_row_unchanged(app, before)


@pytest.mark.parametrize("route, method, body", ROUTE_CASES)
def test_locked_utub_plain_member_gets_no_code(
    every_user_in_every_utub, app: Flask, route: str, method: str, body
) -> None:
    before = _seed(app)
    lock_utub(app, FIRST_UTUB_ID)

    response = request_as(app, SECOND_USER_ID, method, invite_url(route), body)

    assert response.status_code == 403
    assert error_code_of(response) is None
    _assert_row_unchanged(app, before)


@pytest.mark.parametrize("route, method, body", ROUTE_CASES)
def test_locked_utub_non_member_gets_no_code(
    every_user_in_every_utub, app: Flask, route: str, method: str, body
) -> None:
    before = _seed(app)
    lock_utub(app, FIRST_UTUB_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = request_as(app, SECOND_USER_ID, method, invite_url(route), body)

    assert response.status_code == 404
    assert error_code_of(response) is None
    _assert_row_unchanged(app, before)
