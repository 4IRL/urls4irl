"""Tests for the /api/v1 invite join twin (``POST /api/v1/invite/<token>/join``).

Covers the outcome-to-response mapper, the uniform dead 404, actor gates, token
containment in logs and metrics, the use limit and the join rate limit.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.api_v1.invite_link_routes import map_join_result
from backend.invite_links.constants import (
    INVITE_LINK_JOIN_RATE_LIMIT,
    InviteJoinOutcome,
)
from backend.invite_links.data_models import InviteJoinResult
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE
from backend.utils.strings.invite_link_strs import INVITE_LINK_SUCCESS
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.utub_strs import UTUB_ID
from tests.integration.invite_links.invite_route_helpers import (
    disable_limiter,
    enable_limiter,
    error_code_of,
    seed_dead,
)
from tests.integration.mobile_api.mobile_helpers import (
    bearer,
    clear_request_identity,
    token_for_user,
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
from tests.utils_for_test import add_invite_link, lock_utub, remove_member, trash_utub

pytestmark = pytest.mark.mobile_api

JOINER_ID: int = 3
UNKNOWN_TOKEN: str = "A" * 22
ROUTE_MODULE: str = "backend.api_v1.invite_link_routes"


def _join_url(app: Flask, token: str) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.JOIN_VIA_INVITE, token=token)


def _join(
    app: Flask,
    user_id: int | None,
    token: str,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    """POST the join twin as ``user_id`` (no auth header when None)."""
    headers = dict(extra_headers or {})
    if user_id is not None:
        headers.update(bearer(token_for_user(app, user_id)))
    clear_request_identity()
    app.test_client_class = FlaskClient
    return app.test_client().post(_join_url(app, token), headers=headers)


def _unknown_route_response(app: Flask, user_id: int) -> Response:
    clear_request_identity()
    app.test_client_class = FlaskClient
    return app.test_client().post(
        "/api/v1/invite/no-such/route/here",
        headers=bearer(token_for_user(app, user_id)),
    )


def _token_of(app: Flask, invite_id: int) -> str:
    with app.app_context():
        return Utub_Invite_Links.query.get(invite_id).token


def _use_count(app: Flask, invite_id: int) -> int:
    with app.app_context():
        db.session.expire_all()
        return Utub_Invite_Links.query.get(invite_id).use_count


def _state(app: Flask) -> tuple[int, int]:
    """(membership rows, acceptance rows) across the whole database."""
    with app.app_context():
        db.session.expire_all()
        return Utub_Members.query.count(), Utub_Invite_Acceptances.query.count()


def _live_link(app: Flask, **kwargs: Any) -> tuple[int, str]:
    invite_id = add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, **kwargs)
    return invite_id, _token_of(app, invite_id)


def _assert_dead(app: Flask, response: Response, reference: Response) -> None:
    assert response.status_code == 404
    assert response.status_code == reference.status_code
    assert response.get_json() == reference.get_json()
    assert response.get_json()[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND
    assert error_code_of(response) is None


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome, utub_id, status, already",
    [
        (InviteJoinOutcome.JOINED, 7, 200, False),
        (InviteJoinOutcome.ALREADY_MEMBER, 7, 200, True),
        (InviteJoinOutcome.DEAD, None, 404, None),
        (InviteJoinOutcome.ACTOR_SUSPENDED, None, 404, None),
        (InviteJoinOutcome.ACTOR_UNVALIDATED, None, 403, None),
        ("some_future_outcome", None, 404, None),
        ("some_future_outcome", 7, 404, None),
        (InviteJoinOutcome.JOINED, None, 404, None),
    ],
)
def test_mapper_maps_every_outcome(
    app: Flask,
    outcome: Any,
    utub_id: int | None,
    status: int,
    already: bool | None,
):
    response, code = map_join_result(InviteJoinResult(outcome=outcome, utub_id=utub_id))

    body = response.get_json()
    assert code == status
    if status == 200:
        assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert body[UTUB_ID] == 7
        assert body[MODELS.ALREADY_MEMBER] is already
        assert body[STD_JSON.MESSAGE] == (
            INVITE_LINK_SUCCESS.ALREADY_MEMBER
            if already
            else INVITE_LINK_SUCCESS.JOINED
        )
    elif status == 403:
        assert body[STD_JSON.MESSAGE] == API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED
        assert STD_JSON.ERROR_CODE not in body
    else:
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert body[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND
        assert STD_JSON.ERROR_CODE not in body


# ---------------------------------------------------------------------------
# Happy path and membership
# ---------------------------------------------------------------------------


def test_non_member_joins(every_user_makes_a_unique_utub, app: Flask):
    invite_id, token = _live_link(app)
    members_before, acceptances_before = _state(app)

    response = _join(app, JOINER_ID, token)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == INVITE_LINK_SUCCESS.JOINED
    assert body[UTUB_ID] == FIRST_UTUB_ID
    assert body[MODELS.ALREADY_MEMBER] is False
    assert _state(app) == (members_before + 1, acceptances_before + 1)
    assert _use_count(app, invite_id) == 1
    with app.app_context():
        member = Utub_Members.query.get((FIRST_UTUB_ID, JOINER_ID))
        assert member.member_role == Member_Role.MEMBER


@pytest.mark.parametrize("setup", ["live", "revoked", "locked"])
def test_existing_member_is_already_member_and_consumes_nothing(
    every_user_in_every_utub, app: Flask, setup: str
):
    invite_id, token = _live_link(app, revoked=(setup == "revoked"))
    if setup == "locked":
        lock_utub(app, FIRST_UTUB_ID)
    before = _state(app)

    response = _join(app, SECOND_USER_ID, token)

    assert response.status_code == 200
    body = response.get_json()
    assert body[MODELS.ALREADY_MEMBER] is True
    assert body[STD_JSON.MESSAGE] == INVITE_LINK_SUCCESS.ALREADY_MEMBER
    assert body[UTUB_ID] == FIRST_UTUB_ID
    assert _use_count(app, invite_id) == 0
    assert _state(app) == before


# ---------------------------------------------------------------------------
# Dead matrix
# ---------------------------------------------------------------------------


def _dead_token(app: Flask, reason: str) -> str:
    if reason == "malformed":
        return "short"
    if reason == "unknown":
        return UNKNOWN_TOKEN
    if reason == "revoked":
        return _live_link(app, revoked=True)[1]
    if reason in ("expired", "used_up", "creator_demoted"):
        return _token_of(app, seed_dead(app, reason))
    if reason == "trashed":
        token = _live_link(app)[1]
        trash_utub(app, FIRST_UTUB_ID, CREATOR_ID)
        return token
    if reason == "locked":
        token = _live_link(app)[1]
        lock_utub(app, FIRST_UTUB_ID)
        return token
    raise AssertionError(reason)


@pytest.mark.parametrize(
    "reason",
    [
        "malformed",
        "unknown",
        "revoked",
        "expired",
        "used_up",
        "creator_demoted",
        "trashed",
        "locked",
    ],
)
def test_dead_reasons_are_the_uniform_404(
    every_user_makes_a_unique_utub, app: Flask, reason: str
):
    token = _dead_token(app, reason)
    reference = _unknown_route_response(app, JOINER_ID)
    before = _state(app)

    response = _join(app, JOINER_ID, token)

    _assert_dead(app, response, reference)
    assert _state(app) == before
    with app.app_context():
        assert Utub_Members.query.get((FIRST_UTUB_ID, JOINER_ID)) is None
        assert all(
            row.use_count == (1 if reason == "used_up" else 0)
            for row in Utub_Invite_Links.query.all()
        )


# ---------------------------------------------------------------------------
# Actor gates
# ---------------------------------------------------------------------------


def _set_user(app: Flask, user_id: int, **fields: Any) -> None:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        for name, value in fields.items():
            setattr(user, name, value)
        db.session.commit()


def test_unvalidated_non_member_is_decorator_403(
    every_user_makes_a_unique_utub, app: Flask
):
    _, token = _live_link(app)
    _set_user(app, JOINER_ID, email_validated=False)
    before = _state(app)

    response = _join(app, JOINER_ID, token)

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.MESSAGE] == (
        API_AUTH_FAILURE.EMAIL_VALIDATION_REQUIRED
    )
    assert error_code_of(response) is None
    assert MODELS.ALREADY_MEMBER not in response.get_json()
    assert _state(app) == before


def test_unvalidated_existing_member_is_403_not_already_member(
    every_user_in_every_utub, app: Flask
):
    invite_id, token = _live_link(app)
    _set_user(app, SECOND_USER_ID, email_validated=False)
    before = _state(app)

    response = _join(app, SECOND_USER_ID, token)

    assert response.status_code == 403
    assert MODELS.ALREADY_MEMBER not in response.get_json()
    assert _state(app) == before
    assert _use_count(app, invite_id) == 0


def test_suspended_bearer_is_401_and_writes_nothing(
    every_user_makes_a_unique_utub, app: Flask
):
    _, token = _live_link(app)
    access_token = token_for_user(app, JOINER_ID)
    _set_user(app, JOINER_ID, is_suspended=True)
    before = _state(app)
    clear_request_identity()
    app.test_client_class = FlaskClient

    response = app.test_client().post(
        _join_url(app, token), headers=bearer(access_token)
    )

    assert response.status_code == 401
    assert _state(app) == before


def test_patched_actor_suspended_is_the_dead_404(
    every_user_makes_a_unique_utub, app: Flask
):
    _, token = _live_link(app)
    reference = _unknown_route_response(app, JOINER_ID)
    before = _state(app)

    with patch(
        f"{ROUTE_MODULE}.join_via_invite",
        return_value=InviteJoinResult(
            outcome=InviteJoinOutcome.ACTOR_SUSPENDED, utub_id=None
        ),
    ):
        response = _join(app, JOINER_ID, token)

    _assert_dead(app, response, reference)
    assert _state(app) == before


def test_no_token_is_401(every_user_makes_a_unique_utub, app: Flask):
    _, token = _live_link(app)
    before = _state(app)

    response = _join(app, None, token)

    assert response.status_code == 401
    assert _state(app) == before


# ---------------------------------------------------------------------------
# Log containment
# ---------------------------------------------------------------------------


def _is_path_bearing(record: logging.LogRecord) -> bool:
    return (
        record.getMessage().startswith("Request:")
        or getattr(record, "log_type", None) == "http_transaction"
    )


@pytest.mark.parametrize("scenario", ["joined", "already_member", "dead"])
def test_token_absent_from_application_logs(
    every_user_in_every_utub,
    app: Flask,
    caplog: pytest.LogCaptureFixture,
    scenario: str,
):
    token = _live_link(app, revoked=(scenario == "dead"))[1]
    joiner = SECOND_USER_ID
    if scenario != "already_member":
        remove_member(app, FIRST_UTUB_ID, joiner)

    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        response = _join(app, joiner, token)

    assert response.status_code in (200, 404)
    checked = [record for record in caplog.records if not _is_path_bearing(record)]
    if scenario == "joined":
        # The service's own log lines prove capture works and still hold no token.
        assert checked
    for record in checked:
        assert token not in record.getMessage()
        assert token not in str(vars(record))


# ---------------------------------------------------------------------------
# Use limit
# ---------------------------------------------------------------------------


def test_use_limit_one_admits_exactly_one_joiner(
    every_user_makes_a_unique_utub, app: Flask
):
    invite_id, token = _live_link(app, max_uses=1)
    acceptances_before = _state(app)[1]
    reference = _unknown_route_response(app, SECOND_USER_ID)

    first = _join(app, JOINER_ID, token)
    second = _join(app, SECOND_USER_ID, token)

    assert first.status_code == 200
    _assert_dead(app, second, reference)
    assert _state(app)[1] == acceptances_before + 1
    assert _use_count(app, invite_id) == 1
    with app.app_context():
        assert Utub_Members.query.get((FIRST_UTUB_ID, SECOND_USER_ID)) is None


# ---------------------------------------------------------------------------
# Rate limits
# ---------------------------------------------------------------------------


def test_forced_429_is_json_and_joins_no_one(
    every_user_makes_a_unique_utub, app: Flask
):
    _, token = _live_link(app)
    before = _state(app)

    response = _join(app, JOINER_ID, token, extra_headers={"X-Force-Rate-Limit": "1"})

    assert response.status_code == 429
    assert response.is_json
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == STD_JSON.TOO_MANY_REQUESTS
    assert _state(app) == before


def test_eleventh_attempt_is_429_and_other_user_is_not_limited(
    every_user_makes_a_unique_utub, app: Flask
):
    allowed = int(INVITE_LINK_JOIN_RATE_LIMIT.split(" ")[0])
    assert allowed == 10
    _, token = _live_link(app)
    before = _state(app)

    enable_limiter(app)
    try:
        for _ in range(allowed):
            assert _join(app, JOINER_ID, UNKNOWN_TOKEN).status_code == 404
        limited = _join(app, JOINER_ID, token)
        other = _join(app, SECOND_USER_ID, UNKNOWN_TOKEN)
    finally:
        disable_limiter()

    assert limited.status_code == 429
    assert limited.is_json
    assert limited.get_json()[STD_JSON.MESSAGE] == STD_JSON.TOO_MANY_REQUESTS
    assert other.status_code == 404
    assert _state(app) == before


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_join_emits_member_added_once_with_invite_link_source(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
):
    _, token = _live_link(app)

    response = _join(app, JOINER_ID, token)

    assert response.status_code == 200
    assert sum_counter_values(provide_metrics_redis, EventName.MEMBER_ADDED) == 1
    dims = [
        parse_dims(key)
        for key in find_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED)
    ]
    assert [dim["source"] for dim in dims] == ["invite_link"]
    assert token not in str(dims)


@pytest.mark.parametrize("scenario", ["already_member", "dead", "unvalidated"])
def test_non_join_outcomes_emit_no_member_added(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    scenario: str,
):
    _, token = _live_link(app, revoked=(scenario == "dead"))
    joiner = SECOND_USER_ID
    if scenario == "unvalidated":
        _set_user(app, joiner, email_validated=False)
    if scenario == "dead":
        remove_member(app, FIRST_UTUB_ID, joiner)

    response = _join(app, joiner, token)

    assert (
        response.status_code
        == {"already_member": 200, "dead": 404, "unvalidated": 403}[scenario]
    )
    assert count_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED) == 0
