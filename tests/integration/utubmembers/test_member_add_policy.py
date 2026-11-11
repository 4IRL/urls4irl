"""Web tests for the plain-member add policy (members_can_add), suggestions and daily cap.

Fixture shape: ``every_user_in_every_utub`` puts users 1, 2 and 3 in UTub 1, where
user 1 is the owner and users 2 and 3 are plain members. User 3 is removed to act
as the person being added, and user 2 is the plain member doing the adding.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest
from flask import Flask, g, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response
from redis import Redis

from backend.members.constants import (
    MEMBER_ADD_DAILY_CAP,
    MEMBER_ADD_DAILY_CAP_MEMBER,
    MEMBER_ADD_RATE_LIMIT,
    MemberAddSource,
    UTubMembersErrorCodes,
)
from backend.members.services.create_members import create_utub_member
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.form_strs import ADD_USER_FORM
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from tests.integration.invite_links.invite_route_helpers import (
    disable_limiter,
    enable_limiter,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    logged_in_as,
)
from tests.models_for_test import valid_users
from tests.utils_for_test import (
    lock_utub,
    remove_member,
    set_member_role,
    set_members_settings,
    statements_while,
)

pytestmark = pytest.mark.members

TARGET_USER_ID = 3
TARGET_USERNAME = valid_users[2]["username"]
ADD_ALLOWED = {"members_can_add": True}
ADD_NOT_ALLOWED = {"members_can_add": False}
NOT_ALLOWED_CODE = UTubMembersErrorCodes.MEMBER_ADD_NOT_ALLOWED


def _add_url() -> str:
    return url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=FIRST_UTUB_ID)


def _candidates_url() -> str:
    return url_for(ROUTES.MEMBERS.CO_MEMBER_CANDIDATES, utub_id=FIRST_UTUB_ID)


def _add_with(client: FlaskClient, csrf_token: str, body: Any = None) -> Response:
    payload = {ADD_USER_FORM.USERNAME: TARGET_USERNAME} if body is None else body
    return client.post(_add_url(), json=payload, headers={"X-CSRFToken": csrf_token})


def _add_as(app: Flask, user_id: int, body: Any = None) -> Response:
    with logged_in_as(app, user_id) as (client, csrf_token):
        return _add_with(client, csrf_token, body)


def _candidates_as(app: Flask, user_id: int) -> Response:
    with logged_in_as(app, user_id) as (client, _):
        return client.get(_candidates_url())


def _is_member(app: Flask, user_id: int) -> bool:
    with app.app_context():
        return Utub_Members.query.get((FIRST_UTUB_ID, user_id)) is not None


def _has_row_lock(statements: list[str]) -> bool:
    return any(
        'FROM "Utubs"' in " ".join(statement.split())
        and "FOR NO KEY UPDATE" in statement
        for statement in statements
    )


def _enforcement_redis(app: Flask) -> Redis:
    redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == "memory://":
        pytest.skip("Enforcement Redis unavailable (memory:// stub) - cap not enforced")
    return Redis.from_url(redis_uri)


def _seed_counter(app: Flask, user_id: int, count: int) -> None:
    redis_client = _enforcement_redis(app)
    redis_client.set(f"member-add-lookup:{user_id}", count)
    redis_client.close()


def _drop_counter(app: Flask, user_id: int) -> None:
    redis_client = _enforcement_redis(app)
    redis_client.delete(f"member-add-lookup:{user_id}")
    redis_client.close()


def _error_code(response: Response) -> int | None:
    return (response.get_json(silent=True) or {}).get(STD_JSON.ERROR_CODE)


# ---------------------------------------------------------------------------
# Add: policy
# ---------------------------------------------------------------------------


def test_plain_member_add_refused_when_setting_off(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN members_can_add off (the default) and a plain member
    WHEN they add a user
    THEN 403 errorCode 7 and nothing changes
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)

    response = _add_as(app, SECOND_USER_ID)

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
    assert body[STD_JSON.ERROR_CODE] == NOT_ALLOWED_CODE
    assert not _is_member(app, TARGET_USER_ID)


@pytest.mark.parametrize("corrupt_value", ["garbage", 2, None, [True]])
def test_plain_member_add_refused_with_corrupt_stored_override(
    every_user_in_every_utub, app: Flask, corrupt_value
):
    """
    GIVEN a stored members_can_add override that is not exactly True
    WHEN a plain member adds a user
    THEN the add fails closed with 403 and nothing changes
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, {"members_can_add": corrupt_value})

    response = _add_as(app, SECOND_USER_ID)

    assert response.status_code == 403
    assert not _is_member(app, TARGET_USER_ID)


def test_plain_member_add_allowed_when_setting_on(every_user_in_every_utub, app: Flask):
    """
    GIVEN members_can_add on
    WHEN a plain member adds a user
    THEN 200, the new member has the member role and a joinedAt
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    response = _add_as(app, SECOND_USER_ID)

    assert response.status_code == 200
    member = response.get_json()[MEMBER_SUCCESS.MEMBER]
    assert member[MODELS.ID] == TARGET_USER_ID
    assert member[MODELS.MEMBER_ROLE] == Member_Role.MEMBER.value
    assert member[MODELS.JOINED_AT] is not None
    assert _is_member(app, TARGET_USER_ID)


def test_manager_add_unaffected_by_setting(every_user_in_every_utub, app: Flask):
    """
    GIVEN members_can_add off
    WHEN the owner adds a user
    THEN 200
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)

    response = _add_as(app, CREATOR_ID)

    assert response.status_code == 200


def test_non_member_add_is_404(every_user_in_every_utub, app: Flask):
    """
    GIVEN members_can_add on
    WHEN a non-member adds a user
    THEN 404
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    response = _add_as(app, SECOND_USER_ID)

    assert response.status_code == 404


def test_plain_member_add_to_existing_member_keeps_today_error(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN members_can_add on
    WHEN a plain member adds someone already in the UTub
    THEN 400 MEMBER_ALREADY_IN_UTUB
    """
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    response = _add_as(app, SECOND_USER_ID)

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB
    )


def test_plain_member_add_locked_utub_ordering(every_user_in_every_utub, app: Flask):
    """
    GIVEN a locked UTub
    WHEN a plain member adds with the setting off, then on
    THEN off gives errorCode 7 (the lock is not disclosed), on gives UTUB_IS_LOCKED
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)

    with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
        off_response = _add_with(client, csrf_token)
        assert off_response.status_code == 403
        assert _error_code(off_response) == NOT_ALLOWED_CODE

        set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

        on_response = _add_with(client, csrf_token)
    assert on_response.status_code == 403
    assert _error_code(on_response) == UTubMembersErrorCodes.UTUB_IS_LOCKED
    assert not _is_member(app, TARGET_USER_ID)


def test_post_lock_check_refuses_when_owner_turned_setting_off(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN the setting is on when the pre-lock check runs and the owner turns it
        off before the row is locked
    WHEN a plain member adds
    THEN the post-lock check refuses with errorCode 7 and nothing changes
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    def pre_lock_check_then_owner_flips(utub: Utubs, *, is_manager: bool) -> None:
        assert is_manager is False
        set_members_settings(app, FIRST_UTUB_ID, ADD_NOT_ALLOWED)

    with mock.patch(
        "backend.members.services.create_members.member_add_refusal_response",
        side_effect=pre_lock_check_then_owner_flips,
    ) as pre_lock_check:
        response = _add_as(app, SECOND_USER_ID)

    pre_lock_check.assert_called_once()
    assert response.status_code == 403
    assert _error_code(response) == NOT_ALLOWED_CODE
    assert not _is_member(app, TARGET_USER_ID)


def test_malformed_add_body_is_400_before_policy(every_user_in_every_utub, app: Flask):
    """
    GIVEN members_can_add off
    WHEN a plain member sends a malformed add body
    THEN 400 INVALID_FORM_INPUT, not 403 (schema validation runs first)
    """
    response = _add_as(app, SECOND_USER_ID, body={"unexpected": "field"})

    assert response.status_code == 400
    assert _error_code(response) == UTubMembersErrorCodes.INVALID_FORM_INPUT


# ---------------------------------------------------------------------------
# Add: row lock
# ---------------------------------------------------------------------------


def _create_member_in_request_context(app: Flask, user_id: int) -> Any:
    """Call create_utub_member directly as ``user_id`` inside a request context."""
    with app.test_request_context():
        utub = Utubs.query.get(FIRST_UTUB_ID)
        g.is_manager = False
        responses: list[Any] = []
        caller = mock.MagicMock(id=user_id)
        with (
            mock.patch("backend.members.services.create_members.current_user", caller),
            mock.patch("backend.utubs.guards.current_user", caller),
        ):
            statements = statements_while(
                lambda: responses.append(
                    create_utub_member(
                        TARGET_USERNAME, utub, MemberAddSource.EXACT_USERNAME
                    )
                )
            )
        return responses[0], statements


def test_refused_plain_member_add_takes_no_row_lock(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN members_can_add off
    WHEN create_utub_member runs for a plain member
    THEN it is refused with errorCode 7 and no FOR NO KEY UPDATE statement ran
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)

    with app.app_context():
        (_, status_code), statements = _create_member_in_request_context(
            app, SECOND_USER_ID
        )

    assert status_code == 403
    assert not _has_row_lock(statements)


def test_allowed_plain_member_add_takes_row_lock_positive_control(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN members_can_add on
    WHEN create_utub_member runs for a plain member
    THEN it succeeds and a FOR NO KEY UPDATE statement ran (the capture is live)
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    with app.app_context():
        (_, status_code), statements = _create_member_in_request_context(
            app, SECOND_USER_ID
        )

    assert status_code == 200
    assert _has_row_lock(statements)


# ---------------------------------------------------------------------------
# Add: daily cap (shared Redis counter, role-aware cap)
# ---------------------------------------------------------------------------


def test_plain_member_cap_is_25(every_user_in_every_utub, app: Flask):
    """
    GIVEN a plain member allowed to add
    WHEN their counter is at 24 the add succeeds, and at 25 the next is refused
    THEN the refusal is MEMBER_ADD_RATE_LIMITED
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)
    _enforcement_redis(app).close()

    try:
        _seed_counter(app, SECOND_USER_ID, MEMBER_ADD_DAILY_CAP_MEMBER - 1)
        with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
            assert _add_with(client, csrf_token).status_code == 200

            remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
            refused = _add_with(client, csrf_token)
        assert refused.status_code == 400
        assert (
            refused.get_json()[STD_JSON.MESSAGE]
            == MEMBER_FAILURE.MEMBER_ADD_RATE_LIMITED
        )
        assert not _is_member(app, TARGET_USER_ID)
    finally:
        _drop_counter(app, SECOND_USER_ID)


def test_manager_cap_is_100_not_25(every_user_in_every_utub, app: Flask):
    """
    GIVEN a manager whose counter is at 25
    WHEN they add the 26th it succeeds, and at 100 the next is refused
    THEN the manager cap is MEMBER_ADD_DAILY_CAP
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    _enforcement_redis(app).close()

    try:
        _seed_counter(app, CREATOR_ID, MEMBER_ADD_DAILY_CAP_MEMBER)
        with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
            assert _add_with(client, csrf_token).status_code == 200

            remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
            _seed_counter(app, CREATOR_ID, MEMBER_ADD_DAILY_CAP)
            refused = _add_with(client, csrf_token)
        assert refused.status_code == 400
        assert (
            refused.get_json()[STD_JSON.MESSAGE]
            == MEMBER_FAILURE.MEMBER_ADD_RATE_LIMITED
        )
    finally:
        _drop_counter(app, CREATOR_ID)


def test_demoted_manager_with_30_adds_is_refused_at_once(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN a co-owner who made 30 adds and is then demoted to plain member
    WHEN they add with the setting on
    THEN MEMBER_ADD_RATE_LIMITED at once (the cap follows the fresh role)
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    _enforcement_redis(app).close()

    try:
        _seed_counter(app, SECOND_USER_ID, 30)
        set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.MEMBER)

        response = _add_as(app, SECOND_USER_ID)

        assert response.status_code == 400
        assert (
            response.get_json()[STD_JSON.MESSAGE]
            == MEMBER_FAILURE.MEMBER_ADD_RATE_LIMITED
        )
        assert not _is_member(app, TARGET_USER_ID)
    finally:
        _drop_counter(app, SECOND_USER_ID)


# ---------------------------------------------------------------------------
# Add: hidden member list
# ---------------------------------------------------------------------------

HIDE_AND_ADD = {"members_can_add": True, "hide_member_list": True}
UNKNOWN_USERNAME_BODY = {ADD_USER_FORM.USERNAME: "nosuchuser_hidden"}


def _comparable(response: Response) -> tuple[int, Any]:
    return response.status_code, response.get_json()


def test_hidden_plain_member_unknown_and_existing_user_get_identical_400(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN a hidden member list and members_can_add on
    WHEN a plain member adds an unknown user, then someone already in the UTub
    THEN both responses have the same status and JSON body (the unified error)
    """
    set_members_settings(app, FIRST_UTUB_ID, HIDE_AND_ADD)

    with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
        unknown = _add_with(client, csrf_token, UNKNOWN_USERNAME_BODY)
        existing = _add_with(client, csrf_token)

    assert unknown.status_code == 400
    assert _comparable(unknown) == _comparable(existing)
    body = unknown.get_json()
    assert body[STD_JSON.MESSAGE] == MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER
    assert body[STD_JSON.ERRORS] == {
        ADD_USER_FORM.USERNAME: [MEMBER_FAILURE.MEMBER_CANNOT_BE_ADDED]
    }


@pytest.mark.parametrize(
    "body", [None, UNKNOWN_USERNAME_BODY], ids=["existing", "unknown"]
)
def test_caller_demoted_after_decorator_gets_unified_error(
    every_user_in_every_utub, app: Flask, body: Any
):
    """
    GIVEN a hidden member list, members_can_add on, and a co-owner caller whom the
        decorator saw as a manager
    WHEN the caller is demoted to plain member before the row lock is taken
    THEN the post-lock role (list_hidden from g.is_manager) gives the unified 400
        for both an existing and an unknown username
    """
    set_members_settings(app, FIRST_UTUB_ID, HIDE_AND_ADD)
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)

    def pre_lock_check_then_demotion(utub: Utubs, *, is_manager: bool) -> None:
        assert is_manager is True
        set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.MEMBER)

    with mock.patch(
        "backend.members.services.create_members.member_add_refusal_response",
        side_effect=pre_lock_check_then_demotion,
    ) as pre_lock_check:
        response = _add_as(app, SECOND_USER_ID, body)

    pre_lock_check.assert_called_once()
    assert response.status_code == 400
    payload = response.get_json()
    assert payload[STD_JSON.MESSAGE] == MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER
    assert payload[STD_JSON.ERRORS] == {
        ADD_USER_FORM.USERNAME: [MEMBER_FAILURE.MEMBER_CANNOT_BE_ADDED]
    }


def test_hidden_unified_failures_each_consume_one_cap_unit(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN a hidden member list and a plain member with a zeroed counter
    WHEN they hit the unknown-user and already-member branches
    THEN each attempt consumed one daily-cap unit
    """
    set_members_settings(app, FIRST_UTUB_ID, HIDE_AND_ADD)
    _drop_counter(app, SECOND_USER_ID)

    try:
        with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
            _add_with(client, csrf_token, UNKNOWN_USERNAME_BODY)
            _add_with(client, csrf_token)

        redis_client = _enforcement_redis(app)
        assert int(redis_client.get(f"member-add-lookup:{SECOND_USER_ID}")) == 2
        redis_client.close()
    finally:
        _drop_counter(app, SECOND_USER_ID)


def test_hidden_plain_member_rate_limit_and_403_unchanged(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN a hidden member list
    WHEN a plain member is at the daily cap, and when members_can_add is off
    THEN the rate-limit 400 and the errorCode-7 403 are unchanged
    """
    set_members_settings(app, FIRST_UTUB_ID, HIDE_AND_ADD)
    _enforcement_redis(app).close()

    try:
        _seed_counter(app, SECOND_USER_ID, MEMBER_ADD_DAILY_CAP_MEMBER)
        with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
            limited = _add_with(client, csrf_token, UNKNOWN_USERNAME_BODY)
            assert limited.status_code == 400
            assert (
                limited.get_json()[STD_JSON.MESSAGE]
                == MEMBER_FAILURE.MEMBER_ADD_RATE_LIMITED
            )

            set_members_settings(
                app, FIRST_UTUB_ID, {"members_can_add": False, "hide_member_list": True}
            )
            refused = _add_with(client, csrf_token)
            assert refused.status_code == 403
            assert _error_code(refused) == NOT_ALLOWED_CODE
    finally:
        _drop_counter(app, SECOND_USER_ID)


@pytest.mark.parametrize("setting", [{"members_can_add": True}, HIDE_AND_ADD])
def test_manager_keeps_distinct_add_errors(
    every_user_in_every_utub, app: Flask, setting: dict[str, bool]
):
    """
    GIVEN the setting off or on
    WHEN a manager adds an unknown user, then an existing member
    THEN the two responses stay distinct, as today
    """
    set_members_settings(app, FIRST_UTUB_ID, setting)

    with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
        unknown = _add_with(client, csrf_token, UNKNOWN_USERNAME_BODY)
        existing = _add_with(client, csrf_token)

    assert unknown.status_code == existing.status_code == 400
    assert _comparable(unknown) != _comparable(existing)
    assert (
        existing.get_json()[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB
    )
    assert unknown.get_json()[STD_JSON.ERRORS][ADD_USER_FORM.USERNAME] != [
        MEMBER_FAILURE.MEMBER_CANNOT_BE_ADDED
    ]


def test_hidden_plain_member_add_succeeds_but_detail_omits_added_person(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN a hidden member list and members_can_add on
    WHEN a plain member adds a user successfully, then fetches the UTub detail
    THEN the add is 200 and the detail members list does not include the new person
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, HIDE_AND_ADD)

    with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
        response = _add_with(client, csrf_token)
        assert response.status_code == 200
        assert _is_member(app, TARGET_USER_ID)

        detail = client.get(
            url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=FIRST_UTUB_ID)
        )
        member_ids = {item[MODELS.ID] for item in detail.get_json()[MODELS.MEMBERS]}
        assert TARGET_USER_ID not in member_ids
        assert member_ids == {CREATOR_ID, SECOND_USER_ID}

        # Retyping the just-added name is the unified 400 (accepted, no client state)
        again = _add_with(client, csrf_token)
    assert again.status_code == 400
    assert again.get_json()[STD_JSON.ERRORS] == {
        ADD_USER_FORM.USERNAME: [MEMBER_FAILURE.MEMBER_CANNOT_BE_ADDED]
    }


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


def test_hidden_suggestions_empty_for_plain_member(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN a hidden member list, members_can_add on, and a user outside the UTub
    WHEN a plain member loads suggestions
    THEN 200 with an empty list
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, HIDE_AND_ADD)

    response = _candidates_as(app, SECOND_USER_ID)

    assert response.status_code == 200
    assert response.get_json()[MODELS.MEMBERS] == []


def test_suggestions_for_manager_identical_with_setting_on_and_off(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN a user outside the UTub
    WHEN the owner loads suggestions with hide_member_list off, then on
    THEN the two bodies are identical and non-empty
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    with logged_in_as(app, CREATOR_ID) as (client, _):
        off_body = client.get(_candidates_url()).get_json()
        set_members_settings(app, FIRST_UTUB_ID, HIDE_AND_ADD)
        on_body = client.get(_candidates_url()).get_json()

    assert on_body == off_body
    assert on_body[MODELS.MEMBERS] != []


def test_suggestions_refused_for_plain_member_when_off(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN members_can_add off
    WHEN a plain member loads suggestions
    THEN 403 errorCode 7
    """
    response = _candidates_as(app, SECOND_USER_ID)

    assert response.status_code == 403
    assert _error_code(response) == NOT_ALLOWED_CODE


def test_suggestions_for_plain_member_match_manager_when_on(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN members_can_add on and a user who shares another UTub with the requester
    WHEN a plain member and the owner load suggestions
    THEN both get 200 and each gets the candidate list for their own shared UTubs
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    member_response = _candidates_as(app, SECOND_USER_ID)
    manager_response = _candidates_as(app, CREATOR_ID)

    assert member_response.status_code == 200
    assert manager_response.status_code == 200
    member_ids = [
        item[MODELS.ID] for item in member_response.get_json()[MODELS.MEMBERS]
    ]
    manager_ids = [
        item[MODELS.ID] for item in manager_response.get_json()[MODELS.MEMBERS]
    ]
    assert member_ids == [TARGET_USER_ID]
    assert manager_ids == [TARGET_USER_ID]


def test_suggestions_manager_unchanged_when_off(every_user_in_every_utub, app: Flask):
    """
    GIVEN members_can_add off
    WHEN the owner loads suggestions
    THEN 200
    """
    assert _candidates_as(app, CREATOR_ID).status_code == 200


def test_suggestions_non_member_is_404(every_user_in_every_utub, app: Flask):
    """
    GIVEN a user who is not in the UTub
    WHEN they load its suggestions
    THEN 404
    """
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    assert _candidates_as(app, SECOND_USER_ID).status_code == 404


def test_suggestions_take_no_row_lock(every_user_in_every_utub, app: Flask):
    """
    GIVEN a plain member allowed to add
    WHEN they load suggestions
    THEN no FOR NO KEY UPDATE statement runs, and the capture sees SQL (live)
    """
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    with logged_in_as(app, SECOND_USER_ID) as (client, _):
        responses: list[Response] = []
        statements = statements_while(
            lambda: responses.append(client.get(_candidates_url()))
        )

    assert responses[0].status_code == 200
    assert statements != []
    assert not _has_row_lock(statements)


def test_refused_suggestions_take_no_row_lock(every_user_in_every_utub, app: Flask):
    """
    GIVEN members_can_add off
    WHEN a plain member loads suggestions
    THEN 403 errorCode 7, no FOR NO KEY UPDATE ran, and the capture saw SQL (live)
    """
    with logged_in_as(app, SECOND_USER_ID) as (client, _):
        responses: list[Response] = []
        statements = statements_while(
            lambda: responses.append(client.get(_candidates_url()))
        )

    assert responses[0].status_code == 403
    assert _error_code(responses[0]) == NOT_ALLOWED_CODE
    assert statements != []
    assert not _has_row_lock(statements)


def test_suggestions_rate_limited_with_member_add_limit(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN the MEMBER_ADD_RATE_LIMIT limiter on the suggestions route
    WHEN the limit is exceeded
    THEN the next request is 429
    """
    allowed_per_window = int(MEMBER_ADD_RATE_LIMIT.split("/")[0])
    enable_limiter(app)
    try:
        with logged_in_as(app, CREATOR_ID) as (client, _):
            for _attempt in range(allowed_per_window):
                assert client.get(_candidates_url()).status_code != 429
            assert client.get(_candidates_url()).status_code == 429
    finally:
        disable_limiter()


# ---------------------------------------------------------------------------
# Invite links stay manager-only
# ---------------------------------------------------------------------------


def test_plain_member_cannot_create_invite_link_with_add_on(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN members_can_add on
    WHEN a plain member creates an invite link
    THEN 403 (invite links stay manager-only)
    """
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
        response = client.post(
            url_for(ROUTES.INVITE_LINKS.CREATE_INVITE_LINK, utub_id=FIRST_UTUB_ID),
            json={},
            headers={"X-CSRFToken": csrf_token},
        )

    assert response.status_code == 403
