"""Bearer-token tests for the plain-member add policy (members_can_add).

Twins of tests/integration/utubmembers/test_member_add_policy.py for
POST /api/v1/utubs/<id>/members and GET /api/v1/utubs/<id>/co-members.
"""

from __future__ import annotations

from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from redis import Redis

from backend.members.constants import (
    MEMBER_ADD_DAILY_CAP,
    MEMBER_ADD_DAILY_CAP_MEMBER,
    MEMBER_ADD_RATE_LIMIT,
    UTubMembersErrorCodes,
)
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from tests.integration.invite_links.invite_route_helpers import (
    disable_limiter,
    enable_limiter,
)
from tests.integration.mobile_api.mobile_helpers import bearer, token_for_user
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
)
from tests.models_for_test import valid_users
from tests.utils_for_test import lock_utub, remove_member, set_members_settings

pytestmark = pytest.mark.mobile_api

TARGET_USER_ID = 3
TARGET_USERNAME = valid_users[2]["username"]
ADD_ALLOWED = {"members_can_add": True}
NOT_ALLOWED_CODE = UTubMembersErrorCodes.MEMBER_ADD_NOT_ALLOWED


def _add_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CREATE_MEMBER, utub_id=FIRST_UTUB_ID)


def _candidates_url(app: Flask) -> str:
    with app.test_request_context():
        return url_for(ROUTES.API_V1.CO_MEMBER_CANDIDATES, utub_id=FIRST_UTUB_ID)


def _add(app: Flask, client: FlaskClient, user_id: int, body: dict | None = None):
    return client.post(
        _add_url(app),
        json={"username": TARGET_USERNAME} if body is None else body,
        headers=bearer(token_for_user(app, user_id)),
    )


def _candidates(app: Flask, client: FlaskClient, user_id: int):
    return client.get(
        _candidates_url(app), headers=bearer(token_for_user(app, user_id))
    )


def _is_member(app: Flask, user_id: int) -> bool:
    with app.app_context():
        return Utub_Members.query.get((FIRST_UTUB_ID, user_id)) is not None


def test_plain_member_add_refused_when_setting_off(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add off
    WHEN a plain member adds a user over /api/v1
    THEN 403 errorCode 7 and nothing changes
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)

    response = _add(app, api_client, SECOND_USER_ID)

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.ERROR_CODE] == NOT_ALLOWED_CODE
    assert not _is_member(app, TARGET_USER_ID)


def test_plain_member_add_allowed_when_setting_on(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add on
    WHEN a plain member adds a user over /api/v1
    THEN 200 with the member role and a joinedAt
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    response = _add(app, api_client, SECOND_USER_ID)

    assert response.status_code == 200
    member = response.get_json()[MEMBER_SUCCESS.MEMBER]
    assert member[MODELS.ID] == TARGET_USER_ID
    assert member[MODELS.MEMBER_ROLE] == Member_Role.MEMBER.value
    assert member[MODELS.JOINED_AT] is not None


def test_non_member_add_is_404(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add on
    WHEN a non-member adds a user over /api/v1
    THEN 404
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    assert _add(app, api_client, SECOND_USER_ID).status_code == 404


def test_malformed_add_body_is_400_before_policy(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add off
    WHEN a plain member sends a malformed add body
    THEN 400 INVALID_FORM_INPUT, not 403
    """
    response = _add(app, api_client, SECOND_USER_ID, body={"unexpected": "field"})

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == UTubMembersErrorCodes.INVALID_FORM_INPUT
    )


def test_plain_member_cap_is_25(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN a plain member allowed to add whose counter is at the member cap
    WHEN they add
    THEN MEMBER_ADD_RATE_LIMITED
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)
    redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == "memory://":
        pytest.skip("Enforcement Redis unavailable (memory:// stub) - cap not enforced")
    redis_client = Redis.from_url(redis_uri)
    key = f"member-add-lookup:{SECOND_USER_ID}"
    redis_client.set(key, MEMBER_ADD_DAILY_CAP_MEMBER)

    try:
        response = _add(app, api_client, SECOND_USER_ID)
    finally:
        redis_client.delete(key)
        redis_client.close()

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_ADD_RATE_LIMITED
    )
    assert not _is_member(app, TARGET_USER_ID)


def _seed_counter(app: Flask, user_id: int, count: int) -> None:
    redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == "memory://":
        pytest.skip("Enforcement Redis unavailable (memory:// stub) - cap not enforced")
    redis_client = Redis.from_url(redis_uri)
    redis_client.set(f"member-add-lookup:{user_id}", count)
    redis_client.close()


def _drop_counter(app: Flask, user_id: int) -> None:
    redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == "memory://":
        return
    redis_client = Redis.from_url(redis_uri)
    redis_client.delete(f"member-add-lookup:{user_id}")
    redis_client.close()


def test_plain_member_at_24_adds_succeeds(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN a plain member allowed to add whose counter is one below the member cap
    WHEN they add
    THEN 200
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    try:
        _seed_counter(app, SECOND_USER_ID, MEMBER_ADD_DAILY_CAP_MEMBER - 1)
        response = _add(app, api_client, SECOND_USER_ID)
    finally:
        _drop_counter(app, SECOND_USER_ID)

    assert response.status_code == 200
    assert _is_member(app, TARGET_USER_ID)


def test_manager_cap_is_100_not_25(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN a manager whose counter is at the member cap (25)
    WHEN they add it succeeds, and at 100 the next add is refused
    THEN the manager cap is MEMBER_ADD_DAILY_CAP
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)

    try:
        _seed_counter(app, CREATOR_ID, MEMBER_ADD_DAILY_CAP_MEMBER)
        assert _add(app, api_client, CREATOR_ID).status_code == 200

        remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
        _seed_counter(app, CREATOR_ID, MEMBER_ADD_DAILY_CAP)
        refused = _add(app, api_client, CREATOR_ID)
    finally:
        _drop_counter(app, CREATOR_ID)

    assert refused.status_code == 400
    assert (
        refused.get_json()[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_ADD_RATE_LIMITED
    )


def test_manager_add_unaffected_by_setting(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add off
    WHEN the owner adds a user over /api/v1
    THEN 200
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)

    assert _add(app, api_client, CREATOR_ID).status_code == 200


def test_plain_member_add_locked_utub_ordering(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN a locked UTub
    WHEN a plain member adds with the setting off, then on
    THEN off gives errorCode 7 (the lock is not disclosed), on gives UTUB_IS_LOCKED
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)

    off_response = _add(app, api_client, SECOND_USER_ID)
    assert off_response.status_code == 403
    assert off_response.get_json()[STD_JSON.ERROR_CODE] == NOT_ALLOWED_CODE

    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    on_response = _add(app, api_client, SECOND_USER_ID)
    assert on_response.status_code == 403
    assert (
        on_response.get_json()[STD_JSON.ERROR_CODE]
        == UTubMembersErrorCodes.UTUB_IS_LOCKED
    )
    assert not _is_member(app, TARGET_USER_ID)


def test_post_lock_check_refuses_when_owner_turned_setting_off(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN the setting is on when the pre-lock check runs and the owner turns it
        off before the row is locked
    WHEN a plain member adds over /api/v1
    THEN the post-lock check refuses with errorCode 7 and nothing changes
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    def pre_lock_check_then_owner_flips(utub: Utubs, *, is_manager: bool) -> None:
        assert is_manager is False
        set_members_settings(app, FIRST_UTUB_ID, {"members_can_add": False})

    with mock.patch(
        "backend.members.services.create_members.member_add_refusal_response",
        side_effect=pre_lock_check_then_owner_flips,
    ) as pre_lock_check:
        response = _add(app, api_client, SECOND_USER_ID)

    pre_lock_check.assert_called_once()
    assert response.status_code == 403
    assert response.get_json()[STD_JSON.ERROR_CODE] == NOT_ALLOWED_CODE
    assert not _is_member(app, TARGET_USER_ID)


def test_suggestions_refused_for_plain_member_when_off(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add off
    WHEN a plain member loads suggestions over /api/v1
    THEN 403 errorCode 7
    """
    response = _candidates(app, api_client, SECOND_USER_ID)

    assert response.status_code == 403
    assert response.get_json()[STD_JSON.ERROR_CODE] == NOT_ALLOWED_CODE


def test_suggestions_for_plain_member_when_on(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add on
    WHEN a plain member loads suggestions
    THEN 200 with the same candidates the owner gets
    """
    remove_member(app, FIRST_UTUB_ID, TARGET_USER_ID)
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)

    member_response = _candidates(app, api_client, SECOND_USER_ID)

    assert member_response.status_code == 200
    assert [item[MODELS.ID] for item in member_response.get_json()[MODELS.MEMBERS]] == [
        TARGET_USER_ID
    ]


def test_suggestions_manager_unchanged_when_off(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add off
    WHEN the owner loads suggestions
    THEN 200
    """
    assert _candidates(app, api_client, CREATOR_ID).status_code == 200


def test_suggestions_non_member_is_404(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN a user who is not in the UTub
    WHEN they load its suggestions
    THEN 404
    """
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    assert _candidates(app, api_client, SECOND_USER_ID).status_code == 404


def test_suggestions_rate_limited_with_member_add_limit(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN the MEMBER_ADD_RATE_LIMIT limiter on the /api/v1 suggestions route
    WHEN the limit is exceeded
    THEN the next request is 429
    """
    allowed_per_window = int(MEMBER_ADD_RATE_LIMIT.split("/")[0])
    enable_limiter(app)
    try:
        for _attempt in range(allowed_per_window):
            assert _candidates(app, api_client, CREATOR_ID).status_code != 429
        assert _candidates(app, api_client, CREATOR_ID).status_code == 429
    finally:
        disable_limiter()


def test_plain_member_cannot_create_invite_link_with_add_on(
    every_user_in_every_utub, app: Flask, api_client: FlaskClient
):
    """
    GIVEN members_can_add on
    WHEN a plain member creates an invite link over /api/v1
    THEN 403 (invite links stay manager-only)
    """
    set_members_settings(app, FIRST_UTUB_ID, ADD_ALLOWED)
    with app.test_request_context():
        url = url_for(ROUTES.API_V1.CREATE_INVITE_LINK, utub_id=FIRST_UTUB_ID)

    response = api_client.post(
        url, json={}, headers=bearer(token_for_user(app, SECOND_USER_ID))
    )

    assert response.status_code == 403
