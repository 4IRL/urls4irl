"""Policy tests for creating and deleting UTub tags (members_can_tag / members_can_delete_tags).

Fixture shape: ``every_user_in_every_utub`` puts users 1, 2 and 3 in UTub 1, where
user 1 is the owner, user 2 is promoted to co-owner per test and user 3 stays a plain
member. ``add_tags_to_utubs`` gives UTub 1 three tags. Every case runs on both the web
routes and their ``/api/v1`` bearer-token twins.
"""

from __future__ import annotations

from typing import Any, Callable
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.api_v1.services.tokens import create_access_token
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.models.utub_tags import Utub_Tags
from backend.tags.constants import UTubTagErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.tag_strs import (
    TAG_CREATE_NOT_ALLOWED,
    TAG_DELETE_NOT_ALLOWED,
    TAGS_FAILURE,
)
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.guards import lock_and_reauthorize as real_lock_and_reauthorize
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
    THIRD_USER_ID,
    logged_in_as,
)
from tests.utils_for_test import (
    lock_utub,
    remove_member,
    set_member_role,
    set_tags_settings,
    trash_utub,
)

pytestmark = pytest.mark.tags

NEW_TAG = "BrandNewPolicyTag"
CO_OWNER_ID = SECOND_USER_ID
MEMBER_ID = THIRD_USER_ID
TAGGING_OFF = {"members_can_tag": False}
DELETE_OFF = {"members_can_delete_tags": False}
BOTH_OFF = {"members_can_tag": False, "members_can_delete_tags": False}
CODE_TAGGING = UTubTagErrorCodes.TAGGING_NOT_ALLOWED
CODE_DELETE = UTubTagErrorCodes.TAG_DELETE_NOT_ALLOWED

Call = Callable[[Flask, int, str, int], Response]


def _first_tag(app: Flask) -> tuple[int, str]:
    with app.app_context():
        tag = (
            Utub_Tags.query.filter(Utub_Tags.utub_id == FIRST_UTUB_ID)
            .order_by(Utub_Tags.id)
            .first()
        )
        return tag.id, tag.tag_string


def _tag_count(app: Flask) -> int:
    with app.app_context():
        return Utub_Tags.query.filter(Utub_Tags.utub_id == FIRST_UTUB_ID).count()


def _web_create(app: Flask, user_id: int, tag: str, utub_id: int) -> Response:
    with logged_in_as(app, user_id) as (client, csrf_token):
        return client.post(
            url_for(ROUTES.UTUB_TAGS.CREATE_UTUB_TAG, utub_id=utub_id),
            json={MODELS.TAG_STRING: tag},
            headers={"X-CSRFToken": csrf_token},
        )


def _web_delete(app: Flask, user_id: int, tag: str, utub_id: int) -> Response:
    tag_id = _first_tag(app)[0] if tag == "" else int(tag)
    with logged_in_as(app, user_id) as (client, csrf_token):
        return client.delete(
            url_for(
                ROUTES.UTUB_TAGS.DELETE_UTUB_TAG, utub_id=utub_id, utub_tag_id=tag_id
            ),
            headers={"X-CSRFToken": csrf_token},
        )


def _api_client(app: Flask) -> FlaskClient:
    app.test_client_class = FlaskClient
    return app.test_client()


def _bearer(app: Flask, user_id: int) -> dict[str, str]:
    with app.app_context():
        token = create_access_token(user=Users.query.get(user_id))
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def _api_create(app: Flask, user_id: int, tag: str, utub_id: int) -> Response:
    with app.test_request_context():
        url = url_for(ROUTES.API_V1.CREATE_UTUB_TAG, utub_id=utub_id)
    return _api_client(app).post(
        url, json={MODELS.TAG_STRING: tag}, headers=_bearer(app, user_id)
    )


def _api_delete(app: Flask, user_id: int, tag: str, utub_id: int) -> Response:
    tag_id = _first_tag(app)[0] if tag == "" else int(tag)
    with app.test_request_context():
        url = url_for(
            ROUTES.API_V1.DELETE_UTUB_TAG, utub_id=utub_id, utub_tag_id=tag_id
        )
    return _api_client(app).delete(url, headers=_bearer(app, user_id))


CREATES = [pytest.param(_web_create, id="web"), pytest.param(_api_create, id="api")]
DELETES = [pytest.param(_web_delete, id="web"), pytest.param(_api_delete, id="api")]


@pytest.fixture
def tagged_utub(every_user_in_every_utub, add_tags_to_utubs, app: Flask) -> Flask:
    """UTub 1 with owner 1, co-owner 2, plain member 3 and three tags."""
    set_member_role(app, FIRST_UTUB_ID, CO_OWNER_ID, Member_Role.CO_CREATOR)
    return app


def _code(response: Response) -> Any:
    return (response.get_json(silent=True) or {}).get(STD_JSON.ERROR_CODE)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("create", CREATES)
@pytest.mark.parametrize("user_id", [CREATOR_ID, CO_OWNER_ID])
@pytest.mark.parametrize("settings", [TAGGING_OFF, BOTH_OFF])
def test_manager_create_unaffected_by_policy(tagged_utub, create, user_id, settings):
    """
    GIVEN Tagging off
    WHEN the owner or a co-owner creates a UTub tag
    THEN 200 and the tag exists
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, settings)
    before = _tag_count(tagged_utub)

    response = create(tagged_utub, user_id, NEW_TAG, FIRST_UTUB_ID)

    assert response.status_code == 200
    assert _tag_count(tagged_utub) == before + 1


@pytest.mark.parametrize("create", CREATES)
@pytest.mark.parametrize("settings", [TAGGING_OFF, BOTH_OFF])
def test_plain_member_create_refused_when_tagging_off(tagged_utub, create, settings):
    """
    GIVEN Tagging off
    WHEN a plain member creates a UTub tag
    THEN 403 errorCode 4 with the create message and no row is written
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, settings)
    before = _tag_count(tagged_utub)

    response = create(tagged_utub, MEMBER_ID, NEW_TAG, FIRST_UTUB_ID)

    assert response.status_code == 403
    assert _code(response) == CODE_TAGGING
    assert response.get_json()[STD_JSON.MESSAGE] == TAG_CREATE_NOT_ALLOWED
    assert _tag_count(tagged_utub) == before


@pytest.mark.parametrize("create", CREATES)
@pytest.mark.parametrize("settings", [None, {}, DELETE_OFF, {"members_can_tag": True}])
def test_plain_member_create_allowed_when_tagging_on(tagged_utub, create, settings):
    """
    GIVEN Tagging on (stored or default), with Delete either way
    WHEN a plain member creates a UTub tag
    THEN 200
    """
    if settings is not None:
        set_tags_settings(tagged_utub, FIRST_UTUB_ID, settings)

    response = create(tagged_utub, MEMBER_ID, NEW_TAG, FIRST_UTUB_ID)

    assert response.status_code == 200


@pytest.mark.parametrize("create", CREATES)
@pytest.mark.parametrize("corrupt_value", ["garbage", 2, None, [True]])
def test_corrupt_key_resolves_to_defaults_and_allows_create(
    tagged_utub, create, corrupt_value
):
    """
    GIVEN a stored members_can_tag that is not a bool
    WHEN a plain member creates a UTub tag
    THEN the resolver defaults apply (Tagging on) and it is allowed
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, {"members_can_tag": corrupt_value})

    response = create(tagged_utub, MEMBER_ID, NEW_TAG, FIRST_UTUB_ID)

    assert response.status_code == 200


@pytest.mark.parametrize("create", CREATES)
def test_corrupt_tags_section_resolves_to_defaults(tagged_utub, create):
    """
    GIVEN a stored tags section that is not an object
    WHEN a plain member creates a UTub tag
    THEN it is allowed, the same as an unconfigured UTub
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, "garbage")

    response = create(tagged_utub, MEMBER_ID, NEW_TAG, FIRST_UTUB_ID)

    assert response.status_code == 200


@pytest.mark.parametrize("create", CREATES)
def test_blocked_member_duplicate_create_gets_policy_error(tagged_utub, create):
    """
    GIVEN Tagging off
    WHEN a plain member creates a tag whose name already exists
    THEN 403 errorCode 4 (policy before the duplicate check), not the duplicate error
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, TAGGING_OFF)
    _, existing = _first_tag(tagged_utub)

    response = create(tagged_utub, MEMBER_ID, existing, FIRST_UTUB_ID)

    assert response.status_code == 403
    assert _code(response) == CODE_TAGGING
    assert response.get_json()[STD_JSON.MESSAGE] != TAGS_FAILURE.TAG_ALREADY_IN_UTUB


@pytest.mark.parametrize("create", CREATES)
def test_create_locked_utub_beats_policy(tagged_utub, create):
    """
    GIVEN a locked UTub with Tagging off
    WHEN a plain member creates a tag
    THEN UTUB_IS_LOCKED (code 3), not the policy refusal
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, TAGGING_OFF)
    lock_utub(tagged_utub, FIRST_UTUB_ID)

    response = create(tagged_utub, MEMBER_ID, NEW_TAG, FIRST_UTUB_ID)

    assert response.status_code == 403
    assert _code(response) == UTubTagErrorCodes.UTUB_IS_LOCKED
    assert response.get_json()[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED


@pytest.mark.parametrize("create", CREATES)
def test_create_post_lock_read_wins_over_route_guard_state(tagged_utub, create):
    """
    GIVEN Tagging on when the route guard runs and a manager turns it off before the lock
    WHEN a plain member creates a tag
    THEN the locked read refuses with errorCode 4 and nothing is written
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, {"members_can_tag": True})
    before = _tag_count(tagged_utub)

    def flip_then_lock(*args: Any, **kwargs: Any) -> Any:
        set_tags_settings(tagged_utub, FIRST_UTUB_ID, TAGGING_OFF)
        return real_lock_and_reauthorize(*args, **kwargs)

    with mock.patch(
        "backend.tags.services.create_utub_tag.lock_and_reauthorize",
        side_effect=flip_then_lock,
    ) as patched:
        response = create(tagged_utub, MEMBER_ID, NEW_TAG, FIRST_UTUB_ID)

    patched.assert_called_once()
    assert response.status_code == 403
    assert _code(response) == CODE_TAGGING
    assert _tag_count(tagged_utub) == before


@pytest.mark.parametrize("create", CREATES)
@pytest.mark.parametrize("scenario", ["revoked_member", "trashed_utub"])
def test_create_revoked_or_gone_utub_is_404(tagged_utub, create, scenario):
    """
    GIVEN a revoked member, or a trashed UTub
    WHEN they create a UTub tag
    THEN 404
    """
    if scenario == "revoked_member":
        remove_member(tagged_utub, FIRST_UTUB_ID, MEMBER_ID)
        actor = MEMBER_ID
    else:
        trash_utub(tagged_utub, FIRST_UTUB_ID, deleted_by=CREATOR_ID)
        actor = CREATOR_ID

    response = create(tagged_utub, actor, NEW_TAG, FIRST_UTUB_ID)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("delete", DELETES)
@pytest.mark.parametrize("user_id", [CREATOR_ID, CO_OWNER_ID])
def test_manager_delete_unaffected_by_policy(tagged_utub, delete, user_id):
    """
    GIVEN Tagging and Delete both off
    WHEN the owner or a co-owner deletes a UTub tag
    THEN 200 and the tag is gone
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, BOTH_OFF)
    before = _tag_count(tagged_utub)

    response = delete(tagged_utub, user_id, "", FIRST_UTUB_ID)

    assert response.status_code == 200
    assert _tag_count(tagged_utub) == before - 1


@pytest.mark.parametrize("delete", DELETES)
def test_plain_member_delete_refused_when_delete_off(tagged_utub, delete):
    """
    GIVEN Tagging on and Delete off
    WHEN a plain member deletes a UTub tag
    THEN 403 errorCode 5 with the delete message and the tag remains
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, DELETE_OFF)
    before = _tag_count(tagged_utub)

    response = delete(tagged_utub, MEMBER_ID, "", FIRST_UTUB_ID)

    assert response.status_code == 403
    assert _code(response) == CODE_DELETE
    assert response.get_json()[STD_JSON.MESSAGE] == TAG_DELETE_NOT_ALLOWED
    assert _tag_count(tagged_utub) == before


@pytest.mark.parametrize("create", CREATES)
def test_tagging_on_delete_off_member_can_create_not_delete(tagged_utub, create):
    """
    GIVEN Tagging on and Delete off
    WHEN a plain member creates a tag
    THEN 200 (only deletion is blocked)
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, DELETE_OFF)

    response = create(tagged_utub, MEMBER_ID, NEW_TAG, FIRST_UTUB_ID)

    assert response.status_code == 200


@pytest.mark.parametrize("delete", DELETES)
@pytest.mark.parametrize("settings", [TAGGING_OFF, BOTH_OFF])
def test_delete_with_tagging_off_returns_code_4_whatever_delete_stores(
    tagged_utub, delete, settings
):
    """
    GIVEN Tagging off, with Delete stored on (default) or off
    WHEN a plain member deletes a UTub tag
    THEN 403 errorCode 4 and the tag remains
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, settings)
    before = _tag_count(tagged_utub)

    response = delete(tagged_utub, MEMBER_ID, "", FIRST_UTUB_ID)

    assert response.status_code == 403
    assert _code(response) == CODE_TAGGING
    assert response.get_json()[STD_JSON.MESSAGE] == TAG_DELETE_NOT_ALLOWED
    assert _tag_count(tagged_utub) == before


@pytest.mark.parametrize("delete", DELETES)
@pytest.mark.parametrize("settings", [None, {"members_can_delete_tags": True}])
def test_plain_member_delete_allowed_by_default_and_when_on(
    tagged_utub, delete, settings
):
    """
    GIVEN the defaults, or Delete stored on
    WHEN a plain member deletes a UTub tag
    THEN 200
    """
    if settings is not None:
        set_tags_settings(tagged_utub, FIRST_UTUB_ID, settings)

    response = delete(tagged_utub, MEMBER_ID, "", FIRST_UTUB_ID)

    assert response.status_code == 200


@pytest.mark.parametrize("delete", DELETES)
@pytest.mark.parametrize("corrupt_value", ["garbage", 2, None, [True]])
def test_corrupt_delete_key_resolves_to_defaults_and_allows(
    tagged_utub, delete, corrupt_value
):
    """
    GIVEN a stored members_can_delete_tags that is not a bool
    WHEN a plain member deletes a UTub tag
    THEN the resolver defaults apply and it is allowed
    """
    set_tags_settings(
        tagged_utub, FIRST_UTUB_ID, {"members_can_delete_tags": corrupt_value}
    )

    response = delete(tagged_utub, MEMBER_ID, "", FIRST_UTUB_ID)

    assert response.status_code == 200


@pytest.mark.parametrize("delete", DELETES)
def test_delete_locked_utub_beats_policy(tagged_utub, delete):
    """
    GIVEN a locked UTub with Delete off
    WHEN a plain member deletes a tag
    THEN UTUB_IS_LOCKED (code 3)
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, BOTH_OFF)
    lock_utub(tagged_utub, FIRST_UTUB_ID)
    before = _tag_count(tagged_utub)

    response = delete(tagged_utub, MEMBER_ID, "", FIRST_UTUB_ID)

    assert response.status_code == 403
    assert _code(response) == UTubTagErrorCodes.UTUB_IS_LOCKED
    assert _tag_count(tagged_utub) == before


@pytest.mark.parametrize("delete", DELETES)
def test_delete_post_lock_read_wins_over_route_guard_state(tagged_utub, delete):
    """
    GIVEN Delete on when the route guard runs and a manager turns it off before the lock
    WHEN a plain member deletes a tag
    THEN the locked read refuses with errorCode 5 and the tag remains
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, {"members_can_delete_tags": True})
    before = _tag_count(tagged_utub)

    def flip_then_lock(*args: Any, **kwargs: Any) -> Any:
        set_tags_settings(tagged_utub, FIRST_UTUB_ID, DELETE_OFF)
        return real_lock_and_reauthorize(*args, **kwargs)

    with mock.patch(
        "backend.tags.services.delete_utub_tag.lock_and_reauthorize",
        side_effect=flip_then_lock,
    ) as patched:
        response = delete(tagged_utub, MEMBER_ID, "", FIRST_UTUB_ID)

    patched.assert_called_once()
    assert response.status_code == 403
    assert _code(response) == CODE_DELETE
    assert _tag_count(tagged_utub) == before


@pytest.mark.parametrize("delete", DELETES)
@pytest.mark.parametrize("scenario", ["revoked_member", "trashed_utub"])
def test_delete_revoked_or_gone_utub_is_404(tagged_utub, delete, scenario):
    """
    GIVEN a revoked member, or a trashed UTub
    WHEN they delete a UTub tag
    THEN 404
    """
    tag_id = str(_first_tag(tagged_utub)[0])
    if scenario == "revoked_member":
        remove_member(tagged_utub, FIRST_UTUB_ID, MEMBER_ID)
        actor = MEMBER_ID
    else:
        trash_utub(tagged_utub, FIRST_UTUB_ID, deleted_by=CREATOR_ID)
        actor = CREATOR_ID

    response = delete(tagged_utub, actor, tag_id, FIRST_UTUB_ID)

    assert response.status_code == 404


@pytest.mark.parametrize("delete", DELETES)
def test_blocked_member_delete_of_nonexistent_tag_is_404_before_policy(
    tagged_utub, delete
):
    """
    GIVEN Delete off
    WHEN a plain member deletes a tag that does not exist
    THEN 404 (the route decorator runs before the policy)
    """
    set_tags_settings(tagged_utub, FIRST_UTUB_ID, BOTH_OFF)

    response = delete(tagged_utub, MEMBER_ID, str(NONEXISTENT_ID), FIRST_UTUB_ID)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Lock transaction: rollback on every early return, revoke-then-lock race
# ---------------------------------------------------------------------------

LOCK_CREATE = "backend.tags.services.create_utub_tag.lock_and_reauthorize"
LOCK_DELETE = "backend.tags.services.delete_utub_tag.lock_and_reauthorize"

CREATE_ROLLBACK_CASES = [
    pytest.param(TAGGING_OFF, False, MEMBER_ID, False, 403, id="tagging-off"),
    pytest.param(None, True, MEMBER_ID, False, 403, id="locked-utub"),
    pytest.param(None, False, CREATOR_ID, True, 400, id="manager-duplicate"),
]
DELETE_ROLLBACK_CASES = [
    pytest.param(DELETE_OFF, False, MEMBER_ID, 403, id="delete-off"),
    pytest.param(TAGGING_OFF, False, MEMBER_ID, 403, id="tagging-off"),
    pytest.param(None, True, MEMBER_ID, 403, id="locked-utub"),
]


@pytest.mark.parametrize("create", CREATES)
@pytest.mark.parametrize(
    "settings,locked,actor,duplicate,expected_status", CREATE_ROLLBACK_CASES
)
def test_create_refusal_rolls_back_the_lock_transaction(
    tagged_utub, create, settings, locked, actor, duplicate, expected_status
):
    """
    GIVEN a create that is refused after the UTub row lock is taken (tagging off,
        locked UTub, or a manager creating a duplicate tag)
    WHEN the request is made
    THEN the session is rolled back so the row lock is released
    """
    if settings is not None:
        set_tags_settings(tagged_utub, FIRST_UTUB_ID, settings)
    if locked:
        lock_utub(tagged_utub, FIRST_UTUB_ID)
    tag = _first_tag(tagged_utub)[1] if duplicate else NEW_TAG

    with mock.patch.object(db.session, "rollback", wraps=db.session.rollback) as spy:
        response = create(tagged_utub, actor, tag, FIRST_UTUB_ID)

    assert response.status_code == expected_status
    spy.assert_called()


@pytest.mark.parametrize("delete", DELETES)
@pytest.mark.parametrize("settings,locked,actor,expected_status", DELETE_ROLLBACK_CASES)
def test_delete_refusal_rolls_back_the_lock_transaction(
    tagged_utub, delete, settings, locked, actor, expected_status
):
    """
    GIVEN a delete that is refused after the UTub row lock is taken (delete off,
        tagging off, or a locked UTub)
    WHEN the request is made
    THEN the session is rolled back so the row lock is released
    """
    if settings is not None:
        set_tags_settings(tagged_utub, FIRST_UTUB_ID, settings)
    if locked:
        lock_utub(tagged_utub, FIRST_UTUB_ID)

    with mock.patch.object(db.session, "rollback", wraps=db.session.rollback) as spy:
        response = delete(tagged_utub, actor, "", FIRST_UTUB_ID)

    assert response.status_code == expected_status
    spy.assert_called()


@pytest.mark.parametrize("create", CREATES)
def test_create_member_revoked_after_route_guard_is_404_from_the_lock(
    tagged_utub, create
):
    """
    GIVEN a member whose membership is revoked after the route guard but before the lock
    WHEN they create a UTub tag
    THEN lock_and_reauthorize re-checks membership and returns 404 with no tag written
    """
    before = _tag_count(tagged_utub)

    def revoke_then_lock(*args: Any, **kwargs: Any) -> Any:
        remove_member(tagged_utub, FIRST_UTUB_ID, MEMBER_ID)
        return real_lock_and_reauthorize(*args, **kwargs)

    with mock.patch(LOCK_CREATE, side_effect=revoke_then_lock) as patched:
        response = create(tagged_utub, MEMBER_ID, NEW_TAG, FIRST_UTUB_ID)

    patched.assert_called_once()
    assert response.status_code == 404
    assert _tag_count(tagged_utub) == before


@pytest.mark.parametrize("delete", DELETES)
def test_delete_member_revoked_after_route_guard_is_404_from_the_lock(
    tagged_utub, delete
):
    """
    GIVEN a member whose membership is revoked after the route guard but before the lock
    WHEN they delete a UTub tag
    THEN lock_and_reauthorize re-checks membership and returns 404 with the tag kept
    """
    before = _tag_count(tagged_utub)

    def revoke_then_lock(*args: Any, **kwargs: Any) -> Any:
        remove_member(tagged_utub, FIRST_UTUB_ID, MEMBER_ID)
        return real_lock_and_reauthorize(*args, **kwargs)

    with mock.patch(LOCK_DELETE, side_effect=revoke_then_lock) as patched:
        response = delete(tagged_utub, MEMBER_ID, "", FIRST_UTUB_ID)

    patched.assert_called_once()
    assert response.status_code == 404
    assert _tag_count(tagged_utub) == before
