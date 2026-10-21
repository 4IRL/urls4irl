"""UTub load and refresh: short-link fields on each URL card, and the load's query count.

``shortLinkExpiresAt`` / ``canRevokeShortLink`` ride on every URL item. The load path also
eager-loads the per-URL relationships, so its SQL statement count must not grow with the
number of URLs.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable, Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from sqlalchemy import event

from backend import db
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.trash.trash_helpers import login_as_user
from tests.utils_for_test import add_short_link, get_utub_url_id, set_member_role

pytestmark = pytest.mark.utubs

AJAX_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}
UTUB_ID = 1
CREATOR_ID = 1
SECOND_USER_ID = 2
THIRD_USER_ID = 3
EXTRA_URL_COUNT = 4


def _load(client: FlaskClient, route: str) -> dict[str, Any]:
    response = client.get(url_for(route, utub_id=UTUB_ID), headers=AJAX_HEADERS)
    assert response.status_code == 200
    return response.json


def _link_fields_by_url_id(payload: dict[str, Any]) -> dict[int, tuple[Any, bool]]:
    return {
        item[MODELS.UTUB_URL_ID]: (
            item[MODELS.SHORT_LINK_EXPIRES_AT],
            item[MODELS.CAN_REVOKE_SHORT_LINK],
        )
        for item in payload[MODELS.URLS]
    }


@pytest.mark.parametrize(
    "route",
    [ROUTES.UTUBS.GET_SINGLE_UTUB, ROUTES.UTUBS.REFRESH_SINGLE_UTUB],
    ids=["load", "refresh"],
)
def test_utub_load_reports_short_link_state_per_viewer(
    add_mixed_delete_permission_urls_in_first_utub, app: Flask, route: str
) -> None:
    """
    GIVEN UTub 1 with URL 1 (adder user 1) holding an active link minted by user 2, URL 2
        (adder user 2) holding an expired link, and URL 3 (adder user 3) holding none
    WHEN users 1 (owner), 2 (minter), and 3 (plain member) load or refresh the UTub
    THEN every URL item carries both fields: the active link's ISO expiry with
        canRevoke true for the owner and minter and false for the plain member, and
        null/false for the expired link and the missing one
    """
    url_1 = get_utub_url_id(app, UTUB_ID, 1)
    url_2 = get_utub_url_id(app, UTUB_ID, 2)
    url_3 = get_utub_url_id(app, UTUB_ID, 3)
    active_expiry = utc_now() + timedelta(days=3)
    add_short_link(app, url_1, minted_by=SECOND_USER_ID, expires_at=active_expiry)
    add_short_link(
        app, url_2, minted_by=CREATOR_ID, expires_at=utc_now() - timedelta(seconds=5)
    )

    expected_revoke_by_viewer = {
        CREATOR_ID: True,
        SECOND_USER_ID: True,
        THIRD_USER_ID: False,
    }
    for viewer_id, can_revoke in expected_revoke_by_viewer.items():
        with login_as_user(app, viewer_id) as (client, _):
            fields = _link_fields_by_url_id(_load(client, route))

        assert fields[url_1] == (active_expiry.isoformat(), can_revoke), viewer_id
        assert fields[url_2] == (None, False), viewer_id
        assert fields[url_3] == (None, False), viewer_id


@pytest.mark.parametrize(
    "route",
    [ROUTES.UTUBS.GET_SINGLE_UTUB, ROUTES.UTUBS.REFRESH_SINGLE_UTUB],
    ids=["load", "refresh"],
)
def test_utub_load_can_revoke_for_co_creator_and_non_manager_adder(
    add_mixed_delete_permission_urls_in_first_utub, app: Flask, route: str
) -> None:
    """
    GIVEN UTub 1 where user 3 is promoted to co-creator, URL 1 (adder user 1) and URL 2
        (adder user 2, a plain member) both hold active links minted by the owner
    WHEN users 2 (plain member) and 3 (co-creator) load or refresh the UTub
    THEN the co-creator may revoke both links (manager), while the plain member may
        revoke only the link on the URL they added
    """
    url_1 = get_utub_url_id(app, UTUB_ID, 1)
    url_2 = get_utub_url_id(app, UTUB_ID, 2)
    set_member_role(app, UTUB_ID, THIRD_USER_ID, Member_Role.CO_CREATOR)
    add_short_link(app, url_1, minted_by=CREATOR_ID)
    add_short_link(app, url_2, minted_by=CREATOR_ID)

    expected_revoke_by_viewer = {
        THIRD_USER_ID: {url_1: True, url_2: True},
        SECOND_USER_ID: {url_1: False, url_2: True},
    }
    for viewer_id, expected in expected_revoke_by_viewer.items():
        with login_as_user(app, viewer_id) as (client, _):
            fields = _link_fields_by_url_id(_load(client, route))

        actual = {url_id: fields[url_id][1] for url_id in expected}
        assert actual == expected, viewer_id


def _add_url_with_tag_and_link(
    *, app: Flask, utub_tag_id: int, index: int, adder_id: int
) -> None:
    """Add one more live URL to UTub 1 carrying a tag and an active link."""
    with app.app_context():
        url = Urls(
            normalized_url=f"https://short-link-load-{index}.example.com",
            current_user_id=adder_id,
        )
        db.session.add(url)
        db.session.flush()
        utub_url = Utub_Urls()
        utub_url.url_id = url.id
        utub_url.utub_id = UTUB_ID
        utub_url.user_id = adder_id
        utub_url.url_title = f"Load title {index}"
        db.session.add(utub_url)
        db.session.flush()
        db.session.add(
            Utub_Url_Tags(
                utub_id=UTUB_ID,
                utub_url_id=utub_url.id,
                utub_tag_id=utub_tag_id,
                user_id=adder_id,
            )
        )
        db.session.commit()
        new_utub_url_id = utub_url.id
    add_short_link(app, new_utub_url_id, minted_by=adder_id)


def _statements_during(send_request: Callable[[], Any]) -> list[str]:
    """Run ``send_request`` and return every SQL statement it executed."""
    statements: list[str] = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.split()))

    # Listen on the session's live connection, not the Engine class: the harness
    # checks out a long-lived SAVEPOINT connection at fixture setup.
    connection = db.session.connection()
    event.listen(connection, "before_cursor_execute", record_statement)
    try:
        send_request()
    finally:
        event.remove(connection, "before_cursor_execute", record_statement)
    return statements


@pytest.mark.parametrize(
    "route",
    [ROUTES.UTUBS.GET_SINGLE_UTUB, ROUTES.UTUBS.REFRESH_SINGLE_UTUB],
    ids=["load", "refresh"],
)
def test_utub_load_statement_count_does_not_grow_with_url_count(
    add_tags_to_utubs,
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    route: str,
) -> None:
    """
    GIVEN UTub 1 whose every URL has a tag, a standalone URL and an active link
    WHEN it is loaded (or refreshed) with 1 URL and again with 5 URLs
    THEN the same number of SQL statements runs both times
    """
    client, _, _, app = login_first_user_without_register
    with app.app_context():
        tag_id: int = (
            Utub_Tags.query.filter(Utub_Tags.utub_id == UTUB_ID)
            .order_by(Utub_Tags.id)
            .first()
            .id
        )
    first_url_id = get_utub_url_id(app, UTUB_ID, 1)
    with app.app_context():
        db.session.add(
            Utub_Url_Tags(
                utub_id=UTUB_ID,
                utub_url_id=first_url_id,
                utub_tag_id=tag_id,
                user_id=CREATOR_ID,
            )
        )
        db.session.commit()
    add_short_link(app, first_url_id, minted_by=CREATOR_ID)

    one_url_statements = _statements_during(lambda: _load(client, route))
    assert one_url_statements, "listener recorded no statements"
    assert len(_load(client, route)[MODELS.URLS]) == 1

    for index in range(EXTRA_URL_COUNT):
        _add_url_with_tag_and_link(
            app=app, utub_tag_id=tag_id, index=index, adder_id=CREATOR_ID
        )

    five_url_statements = _statements_during(lambda: _load(client, route))
    payload = _load(client, route)
    assert len(payload[MODELS.URLS]) == EXTRA_URL_COUNT + 1
    assert all(
        expires_at is not None
        for expires_at, _ in _link_fields_by_url_id(payload).values()
    )

    assert len(five_url_statements) == len(one_url_statements), (
        one_url_statements,
        five_url_statements,
    )
