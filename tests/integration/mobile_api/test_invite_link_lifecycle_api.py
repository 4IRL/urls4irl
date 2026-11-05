"""/api/v1 parity for the eager invite link revoke (removal, demotion, transfer)."""

from __future__ import annotations

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.invite_links.validity import InviteState
from backend.models.utub_members import Member_Role
from backend.utils.all_routes import ROUTES
from tests.integration.invite_links.invite_route_helpers import (
    rows,
    state_of_current,
    unrevoked,
)
from tests.integration.mobile_api.mobile_helpers import token_for_user
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
)
from tests.utils_for_test import add_invite_link, set_member_role

pytestmark = pytest.mark.mobile_api


def test_api_v1_removal_revokes(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient, make_bearer_headers
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)
    with app.test_request_context():
        url = url_for(
            ROUTES.API_V1.REMOVE_MEMBER, utub_id=FIRST_UTUB_ID, user_id=SECOND_USER_ID
        )

    response = api_client.delete(
        url, headers=make_bearer_headers(token_for_user(app, user_id=CREATOR_ID))
    )

    assert response.status_code == 200
    assert [row.revoked_at is not None for row in rows(app)] == [True]


def test_api_v1_self_leave_revokes_creators_link(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient, make_bearer_headers
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)
    with app.test_request_context():
        url = url_for(
            ROUTES.API_V1.REMOVE_MEMBER, utub_id=FIRST_UTUB_ID, user_id=SECOND_USER_ID
        )

    response = api_client.delete(
        url, headers=make_bearer_headers(token_for_user(app, user_id=SECOND_USER_ID))
    )

    assert response.status_code == 200
    assert [row.revoked_at is not None for row in rows(app)] == [True]
    assert unrevoked(app) == []


def test_api_v1_demotion_revokes(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient, make_bearer_headers
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)
    with app.test_request_context():
        url = url_for(
            ROUTES.API_V1.MODIFY_MEMBER_ROLE,
            utub_id=FIRST_UTUB_ID,
            user_id=SECOND_USER_ID,
        )

    response = api_client.patch(
        url,
        json={"member_role": "member"},
        headers=make_bearer_headers(token_for_user(app, user_id=CREATOR_ID)),
    )

    assert response.status_code == 200
    assert [row.revoked_at is not None for row in rows(app)] == [True]


def test_api_v1_transfer_keeps_link_live(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient, make_bearer_headers
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    with app.test_request_context():
        url = url_for(ROUTES.API_V1.TRANSFER_UTUB_OWNERSHIP, utub_id=FIRST_UTUB_ID)

    response = api_client.patch(
        url,
        json={"new_owner_id": SECOND_USER_ID},
        headers=make_bearer_headers(token_for_user(app, user_id=CREATOR_ID)),
    )

    assert response.status_code == 200
    assert len(unrevoked(app)) == 1
    assert state_of_current(app) is InviteState.LIVE
