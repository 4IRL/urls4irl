"""Tests for the /api/v1 invite link manager twins.

The parity half runs each scenario on the web routes and on the bearer twins and
asserts the same status, the same ``errorCode`` (or none) and the same row state.
The rest covers what only the mobile surface has: bearer auth, the shared
rate-limit scope, JSON 429s, cache headers, token containment and metrics.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Callable

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.invite_links.constants import (
    INVITE_LINK_MANAGE_RATE_LIMIT,
    InviteLinkErrorCodes,
    InviteLinkStatus,
)
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.invite_route_helpers import (
    DEAD_STATE_IDS,
    disable_limiter,
    enable_limiter,
    error_code_of,
    invite_url,
    link_of,
    request_as,
    rows,
    seed_dead,
    unrevoked,
)
from tests.integration.mobile_api.mobile_helpers import (
    bearer,
    bearer_request_as,
    clear_request_identity,
    token_for_user,
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

pytestmark = pytest.mark.mobile_api

# op -> (web endpoint, mobile endpoint, method)
OPS: dict[str, tuple[str, str, str]] = {
    "get": (
        ROUTES.INVITE_LINKS.GET_INVITE_LINK,
        ROUTES.API_V1.GET_INVITE_LINK,
        "GET",
    ),
    "create": (
        ROUTES.INVITE_LINKS.CREATE_INVITE_LINK,
        ROUTES.API_V1.CREATE_INVITE_LINK,
        "POST",
    ),
    "update": (
        ROUTES.INVITE_LINKS.UPDATE_INVITE_LINK,
        ROUTES.API_V1.UPDATE_INVITE_LINK,
        "PATCH",
    ),
    "replace": (
        ROUTES.INVITE_LINKS.REPLACE_INVITE_LINK,
        ROUTES.API_V1.REPLACE_INVITE_LINK,
        "POST",
    ),
    "revoke": (
        ROUTES.INVITE_LINKS.REVOKE_INVITE_LINK,
        ROUTES.API_V1.REVOKE_INVITE_LINK,
        "DELETE",
    ),
}
WRITE_OPS: list[str] = ["create", "update", "replace", "revoke"]
TOKEN_OPS: list[str] = ["get", "create", "update", "replace"]
DEFAULT_BODIES: dict[str, Any] = {
    "get": None,
    "create": {},
    "update": {"max_uses": 5},
    "replace": {},
    "revoke": None,
}

Send = Callable[..., Response]


def _web_send(
    app: Flask,
    op: str,
    user_id: int = CREATOR_ID,
    body: Any = None,
    utub_id: int = FIRST_UTUB_ID,
) -> Response:
    web_route, _, method = OPS[op]
    clear_request_identity()
    return request_as(app, user_id, method, invite_url(web_route, utub_id), body)


def _mobile_send(
    app: Flask,
    op: str,
    user_id: int = CREATOR_ID,
    body: Any = None,
    utub_id: int = FIRST_UTUB_ID,
) -> Response:
    _, mobile_route, method = OPS[op]
    return bearer_request_as(
        app, user_id, method, invite_url(mobile_route, utub_id), body
    )


@pytest.fixture(params=["web", "mobile"])
def send(request: pytest.FixtureRequest, app: Flask) -> Send:
    """The same request sender for the web routes and for the bearer twins."""
    sender = _web_send if request.param == "web" else _mobile_send

    def _send(op: str, **kwargs: Any) -> Response:
        return sender(app, op, **kwargs)

    return _send


def _state(app: Flask) -> list[tuple[bool, int | None, int]]:
    """Row state that must match across surfaces (tokens and times differ)."""
    return [
        (row.revoked_at is not None, row.max_uses, row.use_count) for row in rows(app)
    ]


# ---------------------------------------------------------------------------
# Parity: GET
# ---------------------------------------------------------------------------


def test_parity_get_null_when_no_link(every_user_in_every_utub, app: Flask, send: Send):
    response = send("get")

    assert response.status_code == 200
    assert response.get_json()[MODELS.INVITE_LINK] is None


@pytest.mark.parametrize(
    "state, expected",
    [
        ("expired", InviteLinkStatus.EXPIRED),
        ("used_up", InviteLinkStatus.USED_UP),
        ("creator_demoted", InviteLinkStatus.CREATOR_DEMOTED),
    ],
)
def test_parity_get_each_dead_status(
    every_user_in_every_utub, app: Flask, send: Send, state: str, expected
):
    seed_dead(app, state)

    response = send("get")

    assert response.status_code == 200
    assert link_of(response)[MODELS.STATUS] == expected


def test_parity_get_live(every_user_in_every_utub, app: Flask, send: Send):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)

    response = send("get")

    assert response.status_code == 200
    assert link_of(response)[MODELS.STATUS] == InviteLinkStatus.LIVE


# ---------------------------------------------------------------------------
# Parity: create
# ---------------------------------------------------------------------------


def test_parity_create_defaults(every_user_in_every_utub, app: Flask, send: Send):
    response = send("create", body={})

    assert response.status_code == 201
    assert link_of(response)[MODELS.STATUS] == InviteLinkStatus.LIVE
    assert _state(app) == [(False, None, 0)]


@pytest.mark.parametrize("days", [1, 7, 30])
@pytest.mark.parametrize("max_uses", [None, 1, 5, 10, 25])
def test_parity_create_closed_set_values(
    every_user_in_every_utub,
    app: Flask,
    send: Send,
    days: int,
    max_uses: int | None,
):
    response = send("create", body={"expires_in_days": days, "max_uses": max_uses})

    assert response.status_code == 201
    assert link_of(response)[MODELS.MAX_USES] == max_uses
    assert _state(app) == [(False, max_uses, 0)]


def test_parity_create_on_live_row_is_409(
    every_user_in_every_utub, app: Flask, send: Send
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)
    before = _state(app)

    response = send("create", body={})

    assert response.status_code == 409
    assert error_code_of(response) == InviteLinkErrorCodes.LIVE_LINK_EXISTS
    assert _state(app) == before


@pytest.mark.parametrize("state", DEAD_STATE_IDS)
def test_parity_create_over_dead_row_revokes_it(
    every_user_in_every_utub, app: Flask, send: Send, state: str
):
    old_id = seed_dead(app, state)

    response = send("create", body={})

    assert response.status_code == 201
    live = unrevoked(app)
    assert len(live) == 1 and live[0].id != old_id
    old_row = next(row for row in rows(app) if row.id == old_id)
    assert old_row.revoked_at is not None


# ---------------------------------------------------------------------------
# Parity: update
# ---------------------------------------------------------------------------


def test_parity_update_live_row(every_user_in_every_utub, app: Flask, send: Send):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=25, use_count=5)

    response = send("update", body={"max_uses": 5})

    assert response.status_code == 200
    assert link_of(response)[MODELS.MAX_USES] == 5
    assert _state(app) == [(False, 5, 5)]


def test_parity_update_shortened_expiry(
    every_user_in_every_utub, app: Flask, send: Send
):
    add_invite_link(
        app, FIRST_UTUB_ID, CREATOR_ID, expires_at=utc_now() + timedelta(days=30)
    )

    response = send("update", body={"expires_in_days": 1})

    assert response.status_code == 200
    assert link_of(response)[MODELS.STATUS] == InviteLinkStatus.LIVE
    assert rows(app)[0].expires_at < utc_now() + timedelta(days=2)


@pytest.mark.parametrize("state", DEAD_STATE_IDS)
def test_parity_update_dead_row_is_409(
    every_user_in_every_utub, app: Flask, send: Send, state: str
):
    seed_dead(app, state)
    before = _state(app)

    response = send("update", body={"max_uses": 25, "expires_in_days": 30})

    assert response.status_code == 409
    assert error_code_of(response) == InviteLinkErrorCodes.DEAD_LINK_UPDATE
    assert _state(app) == before


def test_parity_update_below_joined_is_400(
    every_user_in_every_utub, app: Flask, send: Send
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=25, use_count=5)
    before = _state(app)

    response = send("update", body={"max_uses": 1})

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.USES_BELOW_JOINED
    assert _state(app) == before


# ---------------------------------------------------------------------------
# Parity: replace and revoke
# ---------------------------------------------------------------------------


def test_parity_replace_live_row(every_user_in_every_utub, app: Flask, send: Send):
    old_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)
    old_token = rows(app)[0].token

    response = send("replace", body={})

    assert response.status_code == 201
    assert link_of(response)[MODELS.TOKEN] != old_token
    old_row = next(row for row in rows(app) if row.id == old_id)
    assert old_row.revoked_at is not None
    assert len(unrevoked(app)) == 1


def test_parity_revoke_by_creator(every_user_in_every_utub, app: Flask, send: Send):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = send("revoke")

    assert response.status_code == 200
    assert unrevoked(app) == []
    assert len(rows(app)) == 1


@pytest.mark.parametrize("op", ["update", "replace", "revoke"])
def test_parity_no_row_is_404_with_code(
    every_user_in_every_utub, app: Flask, send: Send, op: str
):
    response = send(op, body=DEFAULT_BODIES[op])

    assert response.status_code == 404
    assert error_code_of(response) == InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND
    assert rows(app) == []


@pytest.mark.parametrize("op", ["replace", "revoke"])
def test_parity_co_owner_manages_owners_link(
    every_user_in_every_utub, app: Flask, send: Send, op: str
):
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = send(op, user_id=SECOND_USER_ID, body=DEFAULT_BODIES[op])

    assert response.status_code in (200, 201)
    live = unrevoked(app)
    if op == "replace":
        assert len(live) == 1 and live[0].created_by == SECOND_USER_ID
    else:
        assert live == []


# ---------------------------------------------------------------------------
# Parity: validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op", ["create", "update", "replace"])
@pytest.mark.parametrize("body", [None, {"expires_in_days": 2}, {"max_uses": 0}])
def test_parity_invalid_or_missing_body_is_400(
    every_user_in_every_utub, app: Flask, send: Send, op: str, body: Any
):
    if op != "create":
        add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)
    before = _state(app)

    response = send(op, body=body)

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.INVALID_FORM_INPUT
    assert _state(app) == before


def test_parity_empty_update_body_is_400(
    every_user_in_every_utub, app: Flask, send: Send
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)

    response = send("update", body={})

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.INVALID_FORM_INPUT


# ---------------------------------------------------------------------------
# Parity: authorization and UTub state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("op", list(OPS))
def test_parity_plain_member_is_403_without_code(
    every_user_in_every_utub, app: Flask, send: Send, op: str
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    before = _state(app)

    response = send(op, user_id=SECOND_USER_ID, body=DEFAULT_BODIES[op])

    assert response.status_code == 403
    assert error_code_of(response) is None
    assert _state(app) == before


@pytest.mark.parametrize("op", list(OPS))
@pytest.mark.parametrize("case", ["non_member", "trashed", "missing"])
def test_parity_unreachable_utub_is_404_without_code(
    every_user_in_every_utub, app: Flask, send: Send, op: str, case: str
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    before = _state(app)
    acting = CREATOR_ID
    utub_id = FIRST_UTUB_ID
    if case == "non_member":
        remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
        acting = SECOND_USER_ID
    elif case == "trashed":
        trash_utub(app, FIRST_UTUB_ID, CREATOR_ID)
    else:
        utub_id = NONEXISTENT_ID

    response = send(op, user_id=acting, utub_id=utub_id, body=DEFAULT_BODIES[op])

    assert response.status_code == 404
    assert error_code_of(response) is None
    assert _state(app) == before


@pytest.mark.parametrize("op", WRITE_OPS)
def test_parity_locked_utub_rejects_writes(
    every_user_in_every_utub, app: Flask, send: Send, op: str
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    lock_utub(app, FIRST_UTUB_ID)
    before = _state(app)

    response = send(op, body=DEFAULT_BODIES[op])

    assert response.status_code == 403
    assert error_code_of(response) == InviteLinkErrorCodes.UTUB_IS_LOCKED
    assert _state(app) == before


def test_parity_locked_utub_still_reads(
    every_user_in_every_utub, app: Flask, send: Send
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response = send("get")

    assert response.status_code == 200
    assert link_of(response)[MODELS.STATUS] == InviteLinkStatus.LIVE


# ---------------------------------------------------------------------------
# Mobile only: authentication
# ---------------------------------------------------------------------------


def _mobile_url(app: Flask, op: str, utub_id: int = FIRST_UTUB_ID) -> str:
    with app.test_request_context():
        return url_for(OPS[op][1], utub_id=utub_id)


@pytest.mark.parametrize("op", list(OPS))
def test_no_token_is_401_and_writes_nothing(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient, op: str
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    before = _state(app)

    response = api_client.open(
        _mobile_url(app, op), method=OPS[op][2], json=DEFAULT_BODIES[op]
    )

    assert response.status_code == 401
    assert response.get_json()[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.AUTHENTICATION_REQUIRED
    )
    assert _state(app) == before


@pytest.mark.parametrize("op", list(OPS))
def test_session_cookie_only_identity_is_401(
    every_user_in_every_utub, app: Flask, op: str
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    before = _state(app)

    with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
        response = client.open(
            url_for(OPS[op][1], utub_id=FIRST_UTUB_ID),
            method=OPS[op][2],
            json=DEFAULT_BODIES[op],
            headers={"X-CSRFToken": csrf_token},
        )

    assert response.status_code == 401
    assert _state(app) == before


@pytest.mark.parametrize("op", list(OPS))
def test_unvalidated_manager_is_403_and_writes_nothing(
    every_user_in_every_utub, app: Flask, op: str
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    before = _state(app)
    with app.app_context():
        creator: Users = Users.query.get(CREATOR_ID)
        creator.email_validated = False
        db.session.commit()

    response = _mobile_send(app, op, body=DEFAULT_BODIES[op])

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED
    )
    assert error_code_of(response) is None
    assert _state(app) == before


# ---------------------------------------------------------------------------
# Mobile only: Cache-Control and token containment
# ---------------------------------------------------------------------------


def _seed_for_op(app: Flask, op: str) -> None:
    if op in ("get", "update", "replace", "revoke"):
        add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)


@pytest.mark.parametrize("op", TOKEN_OPS)
def test_token_ops_send_no_store(every_user_in_every_utub, app: Flask, op: str):
    _seed_for_op(app, op)

    response = _mobile_send(app, op, body=DEFAULT_BODIES[op])

    assert response.status_code in (200, 201)
    assert response.headers["Cache-Control"] == "no-store"


def test_revoke_sends_no_cache_control(every_user_in_every_utub, app: Flask):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _mobile_send(app, "revoke")

    assert response.status_code == 200
    assert response.headers.get("Cache-Control") != "no-store"


@pytest.mark.parametrize("op", TOKEN_OPS)
def test_token_appears_only_in_invite_link_token(
    every_user_in_every_utub, app: Flask, op: str
):
    _seed_for_op(app, op)

    response = _mobile_send(app, op, body=DEFAULT_BODIES[op])

    body = response.get_json()
    token = body[MODELS.INVITE_LINK].pop(MODELS.TOKEN)
    assert token not in json.dumps(body)


@pytest.mark.parametrize(
    "op, user_id, body",
    [
        ("create", CREATOR_ID, {}),
        ("create", CREATOR_ID, {"expires_in_days": 2}),
        ("update", CREATOR_ID, {"expires_in_days": 2}),
        ("replace", SECOND_USER_ID, {}),
        ("revoke", SECOND_USER_ID, None),
    ],
)
def test_error_bodies_never_carry_the_token(
    every_user_in_every_utub, app: Flask, op: str, user_id: int, body: Any
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    token = rows(app)[0].token

    response = _mobile_send(app, op, user_id=user_id, body=body)

    assert response.status_code >= 400
    assert token not in response.get_data(as_text=True)


def test_revoke_message_never_carries_the_token(every_user_in_every_utub, app: Flask):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    token = rows(app)[0].token

    response = _mobile_send(app, "revoke")

    assert response.status_code == 200
    assert token not in response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------


def _assert_json_429(response: Response) -> None:
    assert response.status_code == 429
    assert response.is_json
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == STD_JSON.TOO_MANY_REQUESTS


@pytest.mark.parametrize("op", ["create", "replace"])
def test_forced_429_is_json_and_writes_nothing(
    every_user_in_every_utub, app: Flask, op: str
):
    if op == "replace":
        add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=10)
    before = _state(app)
    _, mobile_route, method = OPS[op]

    response = bearer_request_as(
        app,
        CREATOR_ID,
        method,
        invite_url(mobile_route),
        {},
        extra_headers={"X-Force-Rate-Limit": "1"},
    )

    _assert_json_429(response)
    assert _state(app) == before


def test_web_create_and_mobile_replace_share_one_budget(
    every_user_in_every_utub, app: Flask
):
    """GIVEN the real limiter and two managers
    WHEN the owner spends the manage budget across web create and mobile replace
    THEN the owner is 429 on both surfaces and the co-owner is not limited."""
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    allowed = int(INVITE_LINK_MANAGE_RATE_LIMIT.split(" ")[0])
    web_share = allowed // 2
    web_create_url = "web_create"

    enable_limiter(app)
    try:
        clear_request_identity()
        with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
            web_create_url = url_for(
                ROUTES.INVITE_LINKS.CREATE_INVITE_LINK, utub_id=FIRST_UTUB_ID
            )
            for _ in range(web_share):
                response = client.post(
                    web_create_url, json={}, headers={"X-CSRFToken": csrf_token}
                )
                assert response.status_code != 429
        for _ in range(allowed - web_share):
            assert _mobile_send(app, "replace", body={}).status_code != 429

        mobile_create = _mobile_send(app, "create", body={})
        mobile_replace = _mobile_send(app, "replace", body={})
        clear_request_identity()
        with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
            web_limited = client.post(
                web_create_url, json={}, headers={"X-CSRFToken": csrf_token}
            )
        co_owner = _mobile_send(app, "replace", user_id=SECOND_USER_ID, body={})
    finally:
        disable_limiter()

    _assert_json_429(mobile_create)
    _assert_json_429(mobile_replace)
    assert web_limited.status_code == 429
    assert co_owner.status_code != 429


def test_mobile_update_and_revoke_are_not_limited_by_manage_scope(
    every_user_in_every_utub, app: Flask
):
    allowed = int(INVITE_LINK_MANAGE_RATE_LIMIT.split(" ")[0])

    enable_limiter(app)
    try:
        for _ in range(allowed):
            assert _mobile_send(app, "create", body={}).status_code != 429
        assert _mobile_send(app, "create", body={}).status_code == 429
        update = _mobile_send(app, "update", body={"max_uses": 5})
        revoke = _mobile_send(app, "revoke")
    finally:
        disable_limiter()

    assert update.status_code == 200
    assert revoke.status_code == 200


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _dims(redis_client: Any, event: EventName) -> list[dict]:
    return [parse_dims(key) for key in find_counter_keys(redis_client, event)]


@pytest.mark.parametrize("max_uses, expected", [(None, "false"), (5, "true")])
def test_mobile_create_emits_created_with_has_use_limit(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    max_uses: int | None,
    expected: str,
):
    response = _mobile_send(app, "create", body={"max_uses": max_uses})

    assert response.status_code == 201
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 1
    dims = _dims(provide_metrics_redis, EventName.INVITE_LINK_CREATED)
    assert [dim["has_use_limit"] for dim in dims] == [expected]
    assert link_of(response)[MODELS.TOKEN] not in str(dims)
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_mobile_replace_emits_replaced_and_created(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    old_token = rows(app)[0].token

    response = _mobile_send(app, "replace", body={"max_uses": 5})

    assert response.status_code == 201
    revoked = _dims(provide_metrics_redis, EventName.INVITE_LINK_REVOKED)
    assert [dim["reason"] for dim in revoked] == ["replaced"]
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1
    created = _dims(provide_metrics_redis, EventName.INVITE_LINK_CREATED)
    assert [dim["has_use_limit"] for dim in created] == ["true"]
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 1
    leaked = str(revoked) + str(created)
    assert old_token not in leaked
    assert link_of(response)[MODELS.TOKEN] not in leaked


def test_mobile_revoke_emits_manual(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
):
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _mobile_send(app, "revoke")

    assert response.status_code == 200
    dims = _dims(provide_metrics_redis, EventName.INVITE_LINK_REVOKED)
    assert [dim["reason"] for dim in dims] == ["manual"]
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 0


def test_mobile_create_over_dead_row_emits_dead_on_create(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
):
    seed_dead(app, "expired")

    response = _mobile_send(app, "create", body={})

    assert response.status_code == 201
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 1
    dims = _dims(provide_metrics_redis, EventName.INVITE_LINK_REVOKED)
    assert [dim["reason"] for dim in dims] == ["dead_on_create"]


@pytest.mark.parametrize(
    "op, setup",
    [
        ("create", "live_row"),
        ("create", "locked"),
        ("create", "invalid_body"),
        ("create", "plain_member"),
        ("create", "no_token"),
        ("replace", "no_row"),
        ("replace", "locked"),
        ("replace", "plain_member"),
        ("revoke", "no_row"),
        ("revoke", "locked"),
        ("revoke", "plain_member"),
        ("update", "no_row"),
    ],
)
def test_mobile_failure_emits_no_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    api_client: FlaskClient,
    op: str,
    setup: str,
):
    acting = CREATOR_ID
    body: Any = DEFAULT_BODIES[op]
    if op != "create" and setup not in ("no_row",):
        add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    if setup == "live_row":
        add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    elif setup == "locked":
        lock_utub(app, FIRST_UTUB_ID)
    elif setup == "invalid_body":
        body = {"expires_in_days": 2}
    elif setup == "plain_member":
        acting = SECOND_USER_ID

    if setup == "no_token":
        response = api_client.open(_mobile_url(app, op), method=OPS[op][2], json=body)
    else:
        response = _mobile_send(app, op, user_id=acting, body=body)

    assert response.status_code >= 400
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_CREATED) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_token_for_user_and_bearer_helpers_round_trip(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """The shared helpers authenticate a plain client as the minted user."""
    response = api_client.get(
        _mobile_url(app, "get"), headers=bearer(token_for_user(app, CREATOR_ID))
    )

    assert response.status_code == 200
