"""Route tests for ``DELETE /utubs/<utub_id>/invite-link`` (manager revoke)."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask, url_for
from flask.wrappers import Response

from backend.invite_links.constants import InviteLinkErrorCodes
from backend.metrics.events import EventName
from backend.models.utub_members import Member_Role
from backend.utils.all_routes import ROUTES
from backend.utils.strings.invite_link_strs import INVITE_LINK_SUCCESS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.invite_route_helpers import (
    DEAD_STATE_IDS,
    error_code_of,
    invite_url,
    request_as,
    rows,
    seed_dead,
    unrevoked,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    logged_in_as,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import add_invite_link, set_member_role

pytestmark = pytest.mark.invite_links


def _revoke(app: Flask, user_id: int = CREATOR_ID) -> Response:
    return request_as(
        app, user_id, "DELETE", invite_url(ROUTES.INVITE_LINKS.REVOKE_INVITE_LINK)
    )


def test_revoke_live_row_retains_it_with_revoked_at(
    every_user_in_every_utub, app: Flask
) -> None:
    invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _revoke(app)

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.MESSAGE] == (
        INVITE_LINK_SUCCESS.INVITE_LINK_REVOKED
    )
    all_rows = rows(app)
    assert [row.id for row in all_rows] == [invite_id]
    assert all_rows[0].revoked_at is not None


@pytest.mark.parametrize("state", DEAD_STATE_IDS)
def test_revoke_each_dead_state(
    every_user_in_every_utub, app: Flask, state: str
) -> None:
    seed_dead(app, state)

    response = _revoke(app)

    assert response.status_code == 200
    assert unrevoked(app) == []
    assert len(rows(app)) == 1


def test_revoke_without_link_is_404_with_code(
    every_user_in_every_utub, app: Flask
) -> None:
    response = _revoke(app)

    assert response.status_code == 404
    assert error_code_of(response) == InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND


def test_second_revoke_is_404_with_code(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
        url = url_for(ROUTES.INVITE_LINKS.REVOKE_INVITE_LINK, utub_id=FIRST_UTUB_ID)
        headers = {"X-CSRFToken": csrf_token}
        assert client.delete(url, headers=headers).status_code == 200
        response = client.delete(url, headers=headers)

    assert response.status_code == 404
    assert error_code_of(response) == InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND


def test_co_owner_can_revoke_owners_link(every_user_in_every_utub, app: Flask) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _revoke(app, SECOND_USER_ID)

    assert response.status_code == 200
    assert unrevoked(app) == []


def test_get_after_revoke_returns_null(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    assert _revoke(app).status_code == 200

    response = request_as(
        app,
        CREATOR_ID,
        "GET",
        invite_url(ROUTES.INVITE_LINKS.GET_INVITE_LINK),
    )

    assert response.status_code == 200
    assert response.get_json()[MODELS.INVITE_LINK] is None


def test_revoke_emits_manual_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _revoke(app)

    assert response.status_code == 200
    dims: list[dict[str, Any]] = [
        parse_dims(key)
        for key in find_counter_keys(
            provide_metrics_redis, EventName.INVITE_LINK_REVOKED
        )
    ]
    assert [dim["reason"] for dim in dims] == ["manual"]
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1


def test_revoke_failure_emits_no_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    response = _revoke(app)

    assert response.status_code == 404
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0
