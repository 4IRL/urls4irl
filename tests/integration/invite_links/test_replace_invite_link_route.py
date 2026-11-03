"""Route tests for ``POST /utubs/<utub_id>/invite-link/replace``."""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from flask import Flask
from flask.wrappers import Response

from backend import db
from backend.invite_links.constants import (
    INVITE_LINK_TOKEN_MAX_ATTEMPTS,
    InviteLinkErrorCodes,
    InviteLinkStatus,
)
from backend.invite_links.services import manage_invite_link as manage_module
from backend.invite_links.validity import InviteState, evaluate_invite
from backend.metrics.events import EventName
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role
from backend.utils.all_routes import ROUTES
from backend.utils.strings.invite_link_strs import INVITE_LINK_SUCCESS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.invite_route_helpers import (
    DEAD_STATE_IDS,
    error_code_of,
    invite_url,
    link_of,
    request_as,
    rows,
    seed_dead,
    unrevoked,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import add_invite_link, set_member_role

pytestmark = pytest.mark.invite_links

COLLIDING_TOKEN: str = "Z" * 22


def _replace(
    app: Flask,
    body: Any = None,
    user_id: int = CREATOR_ID,
    headers: dict[str, str] | None = None,
) -> Response:
    return request_as(
        app,
        user_id,
        "POST",
        invite_url(ROUTES.INVITE_LINKS.REPLACE_INVITE_LINK),
        {} if body is None else body,
        headers,
    )


def _dims(redis_client: Any, event: EventName) -> list[dict]:
    return [parse_dims(key) for key in find_counter_keys(redis_client, event)]


def test_replace_live_row_issues_new_token_and_kills_old(
    every_user_in_every_utub, app: Flask
) -> None:
    old_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5, use_count=2)

    response = _replace(app, {"max_uses": 10})

    assert response.status_code == 201
    assert response.get_json()[STD_JSON.MESSAGE] == (
        INVITE_LINK_SUCCESS.INVITE_LINK_REPLACED
    )
    link = link_of(response)
    assert link[MODELS.USE_COUNT] == 0
    assert link[MODELS.MAX_USES] == 10
    assert link[MODELS.STATUS] == InviteLinkStatus.LIVE
    all_rows = rows(app)
    assert len(all_rows) == 2
    old_row = next(row for row in all_rows if row.id == old_id)
    assert old_row.revoked_at is not None
    live = unrevoked(app)
    assert len(live) == 1
    assert live[0].token == link[MODELS.TOKEN] != old_row.token
    with app.app_context():
        old = db.session.get(Utub_Invite_Links, old_id)
        assert evaluate_invite(old) is InviteState.REVOKED
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("state", DEAD_STATE_IDS)
def test_replace_works_on_each_dead_state(
    every_user_in_every_utub, app: Flask, state: str
) -> None:
    old_id = seed_dead(app, state)

    response = _replace(app)

    assert response.status_code == 201
    assert link_of(response)[MODELS.STATUS] == InviteLinkStatus.LIVE
    live = unrevoked(app)
    assert len(live) == 1 and live[0].id != old_id
    old_row = next(row for row in rows(app) if row.id == old_id)
    assert old_row.revoked_at is not None


def test_replace_without_link_is_404_with_code(
    every_user_in_every_utub, app: Flask
) -> None:
    response = _replace(app)

    assert response.status_code == 404
    assert error_code_of(response) == InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND
    assert rows(app) == []


def test_replace_by_co_owner_sets_created_by(
    every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _replace(app, user_id=SECOND_USER_ID)

    assert response.status_code == 201
    assert unrevoked(app)[0].created_by == SECOND_USER_ID


def test_replace_forced_rate_limit_is_429_and_writes_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    old_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _replace(app, headers={"X-Force-Rate-Limit": "1"})

    assert response.status_code == 429
    live = unrevoked(app)
    assert [row.id for row in live] == [old_id]
    assert len(rows(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 0


@pytest.mark.parametrize(
    "body", [{"expires_in_days": 2}, {"max_uses": "5"}, {"max_uses": 0}]
)
def test_replace_invalid_body_is_400_and_changes_nothing(
    every_user_in_every_utub, app: Flask, body: dict[str, Any]
) -> None:
    old_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _replace(app, body)

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.INVALID_FORM_INPUT
    assert [row.id for row in unrevoked(app)] == [old_id]


def test_replace_missing_body_is_400_and_changes_nothing(
    every_user_in_every_utub, app: Flask
) -> None:
    old_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = request_as(
        app,
        CREATOR_ID,
        "POST",
        invite_url(ROUTES.INVITE_LINKS.REPLACE_INVITE_LINK),
        None,
    )

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.INVALID_FORM_INPUT
    assert [row.id for row in unrevoked(app)] == [old_id]


def test_replace_exhausted_token_retries_roll_back_the_revoke(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    add_invite_link(app, 2, CREATOR_ID)
    with app.app_context():
        other = Utub_Invite_Links.query.filter_by(utub_id=2).one()
        other.token = COLLIDING_TOKEN
        db.session.commit()
    old_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    with mock.patch.object(
        manage_module, "generate_invite_token", return_value=COLLIDING_TOKEN
    ) as generator:
        response = _replace(app)

    assert generator.call_count == INVITE_LINK_TOKEN_MAX_ATTEMPTS
    assert response.status_code == 500
    first_utub_rows = rows(app)
    assert [row.id for row in first_utub_rows] == [old_id]
    assert first_utub_rows[0].revoked_at is None
    with app.app_context():
        assert evaluate_invite(db.session.get(Utub_Invite_Links, old_id)) is (
            InviteState.LIVE
        )
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 0


@pytest.mark.parametrize("max_uses, expected", [(None, "false"), (5, "true")])
def test_replace_emits_replaced_and_created_metrics(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    max_uses: int | None,
    expected: str,
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _replace(app, {"max_uses": max_uses})

    assert response.status_code == 201
    assert [
        dim["reason"]
        for dim in _dims(provide_metrics_redis, EventName.INVITE_LINK_REVOKED)
    ] == ["replaced"]
    assert [
        dim["has_use_limit"]
        for dim in _dims(provide_metrics_redis, EventName.INVITE_LINK_CREATED)
    ] == [expected]
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 1
