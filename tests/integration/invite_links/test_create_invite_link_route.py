"""Route tests for ``POST /utubs/<utub_id>/invite-link`` (manager create)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.invite_links.constants import (
    INVITE_LINK_MANAGE_RATE_LIMIT,
    INVITE_LINK_TOKEN_MAX_ATTEMPTS,
    InviteLinkErrorCodes,
    InviteLinkStatus,
)
from backend.invite_links.services import manage_invite_link as manage_module
from backend.metrics.events import EventName
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role
from backend.schemas.invite_links import InviteLinkResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.invite_link_strs import INVITE_LINK_SUCCESS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.invite_route_helpers import (
    disable_limiter,
    enable_limiter,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
    logged_in_as,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import (
    add_invite_link,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub,
)

pytestmark = pytest.mark.invite_links

SECOND_UTUB_ID: int = FIRST_UTUB_ID + 1
COLLIDING_TOKEN: str = "Z" * 22
EXPIRY_TOLERANCE: timedelta = timedelta(minutes=2)
DEAD_STATE_IDS: list[str] = ["expired", "used_up", "creator_demoted"]


def _create_url(utub_id: int = FIRST_UTUB_ID) -> str:
    return url_for(ROUTES.INVITE_LINKS.CREATE_INVITE_LINK, utub_id=utub_id)


def _post_create(
    client: FlaskClient,
    csrf_token: str,
    body: Any = None,
    utub_id: int = FIRST_UTUB_ID,
) -> Response:
    return client.post(
        _create_url(utub_id), json=body, headers={"X-CSRFToken": csrf_token}
    )


def _create_as(
    app: Flask, user_id: int, body: Any = None, utub_id: int = FIRST_UTUB_ID
) -> Response:
    with logged_in_as(app, user_id) as (client, csrf_token):
        return _post_create(client, csrf_token, {} if body is None else body, utub_id)


def _rows(app: Flask, utub_id: int = FIRST_UTUB_ID) -> list[Utub_Invite_Links]:
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


def _unrevoked(app: Flask, utub_id: int = FIRST_UTUB_ID) -> list[Utub_Invite_Links]:
    return [row for row in _rows(app, utub_id) if row.revoked_at is None]


def _assert_no_error_code(response: Response) -> None:
    body = response.get_json(silent=True) or {}
    assert STD_JSON.ERROR_CODE not in body


def _seed_dead(app: Flask, state: str) -> int:
    """Seed one dead-but-unrevoked row in the first UTub, returning its id."""
    if state == "expired":
        return add_invite_link(
            app, FIRST_UTUB_ID, CREATOR_ID, expires_at=utc_now() - timedelta(minutes=1)
        )
    if state == "used_up":
        return add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=1, use_count=1)
    return add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)


def _seed_for_case(app: Flask, case: str) -> int | None:
    return None if case == "no_row" else _seed_dead(app, "expired")


def _expires_at(response: Response) -> datetime:
    return datetime.fromisoformat(
        response.get_json()[MODELS.INVITE_LINK][MODELS.EXPIRES_AT]
    )


def _link(response: Response) -> dict[str, Any]:
    body = response.get_json()
    InviteLinkResponseSchema.model_validate(body)
    return body[MODELS.INVITE_LINK]


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("acting_user_id", [CREATOR_ID, SECOND_USER_ID])
def test_create_defaults_for_owner_and_co_owner(
    every_user_in_every_utub, app: Flask, acting_user_id: int
) -> None:
    """GIVEN an owner or co-owner and a UTub with no link
    WHEN they post ``{}``
    THEN 201 with a live 7-day unlimited link created by them, one row written."""
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)

    response = _create_as(app, acting_user_id, {})

    assert response.status_code == 201
    assert response.get_json()[STD_JSON.MESSAGE] == (
        INVITE_LINK_SUCCESS.INVITE_LINK_CREATED
    )
    link = _link(response)
    assert len(link[MODELS.TOKEN]) == 22
    assert link[MODELS.STATUS] == InviteLinkStatus.LIVE
    assert link[MODELS.MAX_USES] is None
    assert link[MODELS.USE_COUNT] == 0
    assert (
        abs(_expires_at(response) - (utc_now() + timedelta(days=7))) < EXPIRY_TOLERANCE
    )
    rows = _unrevoked(app)
    assert len(rows) == 1
    assert rows[0].created_by == acting_user_id
    assert rows[0].token == link[MODELS.TOKEN]


@pytest.mark.parametrize("days", [1, 7, 30])
@pytest.mark.parametrize("max_uses", [None, 1, 5, 10, 25])
def test_create_with_each_closed_set_value(
    every_user_in_every_utub, app: Flask, days: int, max_uses: int | None
) -> None:
    response = _create_as(
        app, CREATOR_ID, {"expires_in_days": days, "max_uses": max_uses}
    )

    assert response.status_code == 201
    link = _link(response)
    assert link[MODELS.MAX_USES] == max_uses
    assert (
        abs(_expires_at(response) - (utc_now() + timedelta(days=days)))
        < EXPIRY_TOLERANCE
    )
    assert _unrevoked(app)[0].max_uses == max_uses


def test_create_sets_no_store_cache_control(
    every_user_in_every_utub, app: Flask
) -> None:
    response = _create_as(app, CREATOR_ID, {})

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_create_missing_body_is_invalid_form_input(
    every_user_in_every_utub, app: Flask
) -> None:
    with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
        response = client.post(_create_url(), headers={"X-CSRFToken": csrf_token})

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == InviteLinkErrorCodes.INVALID_FORM_INPUT
    )
    assert _rows(app) == []


@pytest.mark.parametrize(
    "body",
    [
        {"expires_in_days": 2},
        {"expires_in_days": 0},
        {"expires_in_days": "7"},
        {"expires_in_days": True},
        {"expires_in_days": 7.0},
        {"expires_in_days": None},
        {"max_uses": 2},
        {"max_uses": "5"},
        {"max_uses": True},
        {"max_uses": 5.0},
        {"max_uses": 0},
    ],
)
def test_create_invalid_value_is_invalid_form_input(
    every_user_in_every_utub, app: Flask, body: dict[str, Any]
) -> None:
    response = _create_as(app, CREATOR_ID, body)

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == InviteLinkErrorCodes.INVALID_FORM_INPUT
    )
    assert _rows(app) == []


# ---------------------------------------------------------------------------
# Authorization and UTub state
# ---------------------------------------------------------------------------


def test_create_plain_member_forbidden(every_user_in_every_utub, app: Flask) -> None:
    response = _create_as(app, SECOND_USER_ID)

    assert response.status_code == 403
    _assert_no_error_code(response)
    assert _rows(app) == []


def test_create_non_member_not_found(every_user_in_every_utub, app: Flask) -> None:
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _create_as(app, SECOND_USER_ID)

    assert response.status_code == 404
    _assert_no_error_code(response)
    assert _rows(app) == []


def test_create_trashed_utub_not_found(every_user_in_every_utub, app: Flask) -> None:
    trash_utub(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _create_as(app, CREATOR_ID)

    assert response.status_code == 404
    _assert_no_error_code(response)
    assert _rows(app) == []


def test_create_missing_utub_not_found(every_user_in_every_utub, app: Flask) -> None:
    response = _create_as(app, CREATOR_ID, utub_id=NONEXISTENT_ID)

    assert response.status_code == 404
    _assert_no_error_code(response)


def test_create_locked_utub_rejected_with_code(
    every_user_in_every_utub, app: Flask
) -> None:
    lock_utub(app, FIRST_UTUB_ID)

    response = _create_as(app, CREATOR_ID)

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.ERROR_CODE] == InviteLinkErrorCodes.UTUB_IS_LOCKED
    assert _rows(app) == []


@pytest.mark.parametrize("is_member, expected_status", [(True, 403), (False, 404)])
def test_create_locked_utub_hides_lock_from_unauthorized(
    every_user_in_every_utub, app: Flask, is_member: bool, expected_status: int
) -> None:
    """GIVEN a locked UTub
    WHEN a plain member or a non-member posts
    THEN the member gets 403 and the non-member 404, never with an errorCode."""
    lock_utub(app, FIRST_UTUB_ID)
    if not is_member:
        remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _create_as(app, SECOND_USER_ID)

    assert response.status_code == expected_status
    _assert_no_error_code(response)


def test_create_without_csrf_token_returns_html_403(
    every_user_in_every_utub, app: Flask
) -> None:
    with logged_in_as(app, CREATOR_ID) as (client, _):
        response = client.post(_create_url(), json={})

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert _rows(app) == []


# ---------------------------------------------------------------------------
# Existing rows
# ---------------------------------------------------------------------------


def test_create_live_row_conflicts_and_is_untouched(
    every_user_in_every_utub, app: Flask
) -> None:
    invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)
    before = _rows(app)[0]

    response = _create_as(app, CREATOR_ID, {"expires_in_days": 30})

    assert response.status_code == 409
    body = response.get_json()
    assert body[STD_JSON.ERROR_CODE] == InviteLinkErrorCodes.LIVE_LINK_EXISTS
    rows = _rows(app)
    assert len(rows) == 1
    assert rows[0].id == invite_id
    assert rows[0].revoked_at is None
    assert (rows[0].token, rows[0].expires_at, rows[0].max_uses) == (
        before.token,
        before.expires_at,
        before.max_uses,
    )


@pytest.mark.parametrize("state", DEAD_STATE_IDS)
def test_create_over_dead_row_revokes_it_and_creates_new(
    every_user_in_every_utub, app: Flask, state: str
) -> None:
    old_id = _seed_dead(app, state)

    response = _create_as(app, CREATOR_ID, {"max_uses": 5})

    assert response.status_code == 201
    link = _link(response)
    assert link[MODELS.STATUS] == InviteLinkStatus.LIVE
    assert link[MODELS.USE_COUNT] == 0
    rows = _rows(app)
    assert len(rows) == 2
    old_row = next(row for row in rows if row.id == old_id)
    assert old_row.revoked_at is not None
    live = _unrevoked(app)
    assert len(live) == 1
    assert live[0].id != old_id
    assert live[0].token == link[MODELS.TOKEN]


def test_create_revoked_row_does_not_block(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, revoked=True)

    response = _create_as(app, CREATOR_ID)

    assert response.status_code == 201
    assert len(_rows(app)) == 2
    assert len(_unrevoked(app)) == 1


# ---------------------------------------------------------------------------
# Insert races
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["no_row", "dead_row"])
def test_create_token_collision_retries(
    every_user_in_every_utub, app: Flask, case: str
) -> None:
    add_invite_link(app, SECOND_UTUB_ID, CREATOR_ID)
    with app.app_context():
        other = Utub_Invite_Links.query.filter_by(utub_id=SECOND_UTUB_ID).one()
        other.token = COLLIDING_TOKEN
        db.session.commit()
    _seed_for_case(app, case)

    with mock.patch.object(
        manage_module,
        "generate_invite_token",
        side_effect=[COLLIDING_TOKEN, "F" * 22],
    ):
        response = _create_as(app, CREATOR_ID)

    assert response.status_code == 201
    assert _link(response)[MODELS.TOKEN] == "F" * 22
    assert len(_unrevoked(app)) == 1


@pytest.mark.parametrize("case", ["no_row", "dead_row"])
def test_create_exhausted_token_retries_return_500_and_write_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    case: str,
) -> None:
    add_invite_link(app, SECOND_UTUB_ID, CREATOR_ID)
    with app.app_context():
        other = Utub_Invite_Links.query.filter_by(utub_id=SECOND_UTUB_ID).one()
        other.token = COLLIDING_TOKEN
        db.session.commit()
    old_id = _seed_for_case(app, case)

    with mock.patch.object(
        manage_module, "generate_invite_token", return_value=COLLIDING_TOKEN
    ) as generator:
        response = _create_as(app, CREATOR_ID)

    assert generator.call_count == INVITE_LINK_TOKEN_MAX_ATTEMPTS
    assert response.status_code == 500
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE
    rows = _rows(app)
    assert len(rows) == (0 if old_id is None else 1)
    if old_id is not None:
        assert rows[0].revoked_at is None
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 0


@pytest.mark.parametrize("case", ["no_row", "dead_row"])
def test_create_one_active_violation_returns_409_and_writes_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    case: str,
) -> None:
    """GIVEN the insert trips an integrity error the dispatcher names the
    one-active-link index
    WHEN create runs
    THEN 409 LIVE_LINK_EXISTS, no new row, a dead row stays unrevoked and no
    revoke or create metric is emitted."""
    add_invite_link(app, SECOND_UTUB_ID, CREATOR_ID)
    with app.app_context():
        other = Utub_Invite_Links.query.filter_by(utub_id=SECOND_UTUB_ID).one()
        other.token = COLLIDING_TOKEN
        db.session.commit()
    old_id = _seed_for_case(app, case)

    with (
        mock.patch.object(
            manage_module, "generate_invite_token", return_value=COLLIDING_TOKEN
        ),
        mock.patch.object(
            manage_module,
            "violated_constraint",
            return_value=manage_module.ONE_ACTIVE_INVITE_LINK_PER_UTUB,
        ),
    ):
        response = _create_as(app, CREATOR_ID)

    assert response.status_code == 409
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == InviteLinkErrorCodes.LIVE_LINK_EXISTS
    )
    rows = _rows(app)
    assert len(rows) == (0 if old_id is None else 1)
    if old_id is not None:
        assert rows[0].revoked_at is None
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 0


def test_create_unrelated_integrity_error_propagates(
    every_user_in_every_utub, app: Flask
) -> None:
    """GIVEN an integrity error naming an unrelated constraint
    WHEN create runs
    THEN it propagates (fail closed) and no row is left."""
    add_invite_link(app, SECOND_UTUB_ID, CREATOR_ID)
    with app.app_context():
        other = Utub_Invite_Links.query.filter_by(utub_id=SECOND_UTUB_ID).one()
        other.token = COLLIDING_TOKEN
        db.session.commit()

    with (
        mock.patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        mock.patch.object(
            manage_module, "generate_invite_token", return_value=COLLIDING_TOKEN
        ),
        mock.patch.object(
            manage_module, "violated_constraint", return_value="some_other_constraint"
        ),
    ):
        response = _create_as(app, CREATOR_ID)

    assert response.status_code == 500
    assert _rows(app) == []


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------


def test_create_forced_rate_limit_returns_429_and_writes_nothing(
    every_user_in_every_utub, app: Flask
) -> None:
    with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
        response = client.post(
            _create_url(),
            json={},
            headers={"X-CSRFToken": csrf_token, "X-Force-Rate-Limit": "1"},
        )

    assert response.status_code == 429
    assert _rows(app) == []


def test_create_rate_limit_budgets_are_per_manager(
    every_user_in_every_utub, app: Flask
) -> None:
    """GIVEN the real limiter and two managers behind one address
    WHEN the owner exhausts the create budget
    THEN the owner gets the HTML 429 while the co-owner is still served."""
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    allowed = int(INVITE_LINK_MANAGE_RATE_LIMIT.split(" ")[0])

    enable_limiter(app)
    try:
        # One client at a time: nested test clients share the request context stack.
        with logged_in_as(app, CREATOR_ID) as (owner_client, owner_csrf):
            for _ in range(allowed):
                assert _post_create(owner_client, owner_csrf, {}).status_code != 429

            owner_limited = _post_create(owner_client, owner_csrf, {})
        with logged_in_as(app, SECOND_USER_ID) as (co_owner_client, co_owner_csrf):
            co_owner_response = _post_create(co_owner_client, co_owner_csrf, {})
    finally:
        disable_limiter()

    assert owner_limited.status_code == 429
    assert IDENTIFIERS.HTML_429 in owner_limited.get_data(as_text=True)
    assert co_owner_response.status_code != 429


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _dims_of(redis_client: Any, event: EventName) -> list[dict]:
    return [parse_dims(key) for key in find_counter_keys(redis_client, event)]


@pytest.mark.parametrize("max_uses, expected", [(None, "false"), (5, "true")])
def test_create_emits_created_metric_with_has_use_limit(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    max_uses: int | None,
    expected: str,
) -> None:
    response = _create_as(app, CREATOR_ID, {"max_uses": max_uses})

    assert response.status_code == 201
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 1
    dims = _dims_of(provide_metrics_redis, EventName.INVITE_LINK_CREATED)
    assert [dim["has_use_limit"] for dim in dims] == [expected]
    token = response.get_json()[MODELS.INVITE_LINK][MODELS.TOKEN]
    assert token not in str(dims)
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_create_over_dead_row_emits_dead_on_create_revoke(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    _seed_dead(app, "expired")

    response = _create_as(app, CREATOR_ID)

    assert response.status_code == 201
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 1
    dims = _dims_of(provide_metrics_redis, EventName.INVITE_LINK_REVOKED)
    assert [dim["reason"] for dim in dims] == ["dead_on_create"]
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1


@pytest.mark.parametrize(
    "setup",
    ["live_row", "locked", "invalid_body", "plain_member"],
)
def test_create_failure_emits_no_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    setup: str,
) -> None:
    acting = CREATOR_ID
    body: Any = {}
    if setup == "live_row":
        add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    elif setup == "locked":
        lock_utub(app, FIRST_UTUB_ID)
    elif setup == "invalid_body":
        body = {"expires_in_days": 2}
    else:
        acting = SECOND_USER_ID

    response = _create_as(app, acting, body)

    assert response.status_code >= 400
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0
