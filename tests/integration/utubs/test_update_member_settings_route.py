from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Generator
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.utubs import MemberSettingsUpdatedResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.utub_strs import UTUB_FAILURE, UTUB_ID
from backend.utubs.constants import UTubErrorCodes
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.utils import assert_response_conforms_to_schema
from tests.utils_for_test import (
    get_csrf_token,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub,
)

pytestmark = pytest.mark.utubs

UTUB_ID_VALUE = 1
CREATOR_ID = 1
CO_OWNER_ID = 2
PLAIN_MEMBER_ID = 3
INVALID_FORM_INPUT = UTubErrorCodes.INVALID_FORM_INPUT

URLS_DEFAULTS = {
    "hide_copy_button": False,
    "hide_short_link_button": False,
    "hide_date_added": False,
    "sort": None,
    "view_mode": None,
    "density": None,
    "disable_swipe_delete": False,
}
DEFAULT_MEMBER_SETTINGS = {"urls": URLS_DEFAULTS}


@contextmanager
def _client_for(
    app: Flask, user_id: int
) -> Generator[tuple[FlaskClient, str], None, None]:
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user = Users.query.get(user_id)
    with app.test_client(user=user) as client:
        csrf_token = get_csrf_token(client.get("/home").get_data(), meta_tag=True)
        yield client, csrf_token


def _patch(
    app: Flask,
    client: FlaskClient,
    csrf_token: str,
    body: Any,
    utub_id: int = UTUB_ID_VALUE,
) -> TestResponse:
    with app.app_context():
        url = url_for(ROUTES.UTUBS.UPDATE_MEMBER_SETTINGS, utub_id=utub_id)
    return client.patch(url, json=body, headers={"X-CSRFToken": csrf_token})


def _stored(app: Flask, user_id: int) -> Any:
    with app.app_context():
        db.session.expire_all()
        return Utub_Members.query.get((UTUB_ID_VALUE, user_id)).settings


def _set_stored(app: Flask, user_id: int, value: Any) -> None:
    with app.app_context():
        member: Utub_Members = Utub_Members.query.get((UTUB_ID_VALUE, user_id))
        member.settings = value
        db.session.commit()


def _utub_last_updated_and_settings(app: Flask) -> Any:
    with app.app_context():
        db.session.expire_all()
        utub: Utubs = Utubs.query.get(UTUB_ID_VALUE)
        return utub.last_updated, utub.settings


def _count_commits(action: Callable[[], object]) -> int:
    real_commit = db.session.commit
    with mock.patch.object(db.session, "commit", wraps=real_commit) as commit_spy:
        action()
    return commit_spy.call_count


def _assert_400(response: TestResponse, expected_error_keys: set[str]) -> None:
    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_SETTINGS
    )
    assert response.json[STD_JSON.ERROR_CODE] == INVALID_FORM_INPUT
    assert set(response.json[STD_JSON.ERRORS]) == expected_error_keys


# --------------------------------------------------------------------------
# Success paths
# --------------------------------------------------------------------------


def test_empty_patch_returns_default_member_settings(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member with no stored overrides
    WHEN they PATCH an empty urls section
    THEN a 200 conforming to the response schema with defaults is returned and
        nothing is stored
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {}})

    assert response.status_code == 200
    assert_response_conforms_to_schema(
        {key: value for key, value in response.json.items() if key != STD_JSON.STATUS},
        MemberSettingsUpdatedResponseSchema,
        {UTUB_ID, MODELS.MEMBER_SETTINGS},
    )
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response.json[UTUB_ID] == UTUB_ID_VALUE
    assert response.json[MODELS.MEMBER_SETTINGS] == DEFAULT_MEMBER_SETTINGS
    assert _stored(app, CREATOR_ID) is None


@pytest.mark.parametrize(
    "user_id",
    [CREATOR_ID, CO_OWNER_ID, PLAIN_MEMBER_ID],
    ids=["creator", "co", "plain"],
)
def test_each_role_changes_only_their_own_row(
    add_multiple_users_to_utub_without_logging_in, app, user_id
):
    """
    GIVEN a UTub with a creator, a co-owner and a plain member
    WHEN one of them PATCHes an override
    THEN 200 with the resolved slice, only their own row changes and the other
        members stay NULL
    """
    set_member_role(app, UTUB_ID_VALUE, CO_OWNER_ID, Member_Role.CO_CREATOR)

    with _client_for(app, user_id) as (client, csrf_token):
        response = _patch(
            app,
            client,
            csrf_token,
            {"urls": {"hide_copy_button": True, "sort": "title_az"}},
        )

    assert response.status_code == 200
    assert response.json[MODELS.MEMBER_SETTINGS]["urls"] == {
        **URLS_DEFAULTS,
        "hide_copy_button": True,
        "sort": "title_az",
    }
    for member_id in (CREATOR_ID, CO_OWNER_ID, PLAIN_MEMBER_ID):
        expected = (
            {"urls": {"hide_copy_button": True, "sort": "title_az"}}
            if member_id == user_id
            else None
        )
        assert _stored(app, member_id) == expected


def test_does_not_touch_utub_row(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a creator
    WHEN they PATCH an override
    THEN Utubs.last_updated and Utubs.settings are unchanged
    """
    client, csrf_token, _, app = login_first_user_without_register
    before = _utub_last_updated_and_settings(app)

    response = _patch(app, client, csrf_token, {"urls": {"hide_date_added": True}})

    assert response.status_code == 200
    assert _utub_last_updated_and_settings(app) == before


def test_plain_member_succeeds_in_locked_utub(
    add_multiple_users_to_utub_without_logging_in, app
):
    """
    GIVEN a locked UTub
    WHEN a plain (non-manager) member PATCHes their own override
    THEN 200 is returned and the override is stored (no lock or role 403)
    """
    lock_utub(app, UTUB_ID_VALUE)

    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        response = _patch(
            app, client, csrf_token, {"urls": {"disable_swipe_delete": True}}
        )

    assert response.status_code == 200
    assert _stored(app, PLAIN_MEMBER_ID) == {"urls": {"disable_swipe_delete": True}}


def test_patches_merge_with_stored_overrides(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN stored overrides
    WHEN a later PATCH sets a different key
    THEN both keys are stored and returned
    """
    client, csrf_token, _, app = login_first_user_without_register
    _set_stored(app, CREATOR_ID, {"urls": {"hide_copy_button": True}})

    response = _patch(app, client, csrf_token, {"urls": {"density": "compact"}})

    assert response.status_code == 200
    assert _stored(app, CREATOR_ID) == {
        "urls": {"hide_copy_button": True, "density": "compact"}
    }
    assert response.json[MODELS.MEMBER_SETTINGS]["urls"]["density"] == "compact"


def test_explicit_null_clears_override_and_storage_becomes_null(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a stored sort override
    WHEN the member PATCHes sort: null
    THEN the override is cleared and the row is NULL (sparse storage)
    """
    client, csrf_token, _, app = login_first_user_without_register
    _set_stored(app, CREATOR_ID, {"urls": {"sort": "oldest"}})

    response = _patch(app, client, csrf_token, {"urls": {"sort": None}})

    assert response.status_code == 200
    assert response.json[MODELS.MEMBER_SETTINGS] == DEFAULT_MEMBER_SETTINGS
    assert _stored(app, CREATOR_ID) is None


def test_default_valued_boolean_is_not_stored(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a stored boolean override
    WHEN the member PATCHes it back to false
    THEN the row returns to NULL
    """
    client, csrf_token, _, app = login_first_user_without_register
    _set_stored(app, CREATOR_ID, {"urls": {"hide_copy_button": True}})

    response = _patch(app, client, csrf_token, {"urls": {"hide_copy_button": False}})

    assert response.status_code == 200
    assert _stored(app, CREATOR_ID) is None


def test_no_op_makes_no_commit_and_returns_full_slice(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN stored overrides
    WHEN the member PATCHes the same value again
    THEN 200 with the full resolved slice is returned and nothing is committed
    """
    client, csrf_token, _, app = login_first_user_without_register
    _set_stored(app, CREATOR_ID, {"urls": {"view_mode": "list"}})

    responses: list[TestResponse] = []
    commits = _count_commits(
        lambda: responses.append(
            _patch(app, client, csrf_token, {"urls": {"view_mode": "list"}})
        )
    )

    assert responses[0].status_code == 200
    assert responses[0].json[MODELS.MEMBER_SETTINGS]["urls"] == {
        **URLS_DEFAULTS,
        "view_mode": "list",
    }
    assert commits == 0
    assert _stored(app, CREATOR_ID) == {"urls": {"view_mode": "list"}}


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key, value",
    [
        ("sort", "bogus"),
        ("view_mode", "bogus"),
        ("density", "bogus"),
        ("hide_copy_button", "yes"),
    ],
)
def test_invalid_value_returns_400_with_dotted_key(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    key,
    value,
):
    """
    GIVEN a member
    WHEN they PATCH an invalid value
    THEN 400 keyed by "urls.<key>" is returned and nothing is stored
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {key: value}})

    _assert_400(response, {f"urls.{key}"})
    assert _stored(app, CREATOR_ID) is None


def test_unknown_key_returns_400(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member
    WHEN they PATCH an unknown settings key
    THEN 400 keyed "urls.<key>" is returned
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {"nope": True}})

    _assert_400(response, {"urls.nope"})
    assert _stored(app, CREATOR_ID) is None


def test_null_boolean_returns_400(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a member
    WHEN they PATCH null onto a boolean key
    THEN 400 is returned and nothing is stored
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {"hide_date_added": None}})

    _assert_400(response, {"urls.hide_date_added"})
    assert _stored(app, CREATOR_ID) is None


@pytest.mark.parametrize(
    "body",
    [{"unknown_section": {}}, {"urls": None}, {"urls": "x"}, {"utubs": {}}],
    ids=["unknown_section", "null_section", "non_object_section", "other_panel"],
)
def test_malformed_body_returns_400(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    body,
):
    """
    GIVEN a member
    WHEN they PATCH a malformed body
    THEN 400 is returned from the request-schema layer and nothing is stored
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, body)

    assert response.status_code == 400
    assert response.json[STD_JSON.ERROR_CODE] == INVALID_FORM_INPUT
    assert _stored(app, CREATOR_ID) is None


# --------------------------------------------------------------------------
# Not found / CSRF
# --------------------------------------------------------------------------


def test_removed_member_gets_404(add_multiple_users_to_utub_without_logging_in, app):
    """
    GIVEN a member removed from the UTub
    WHEN they PATCH their settings
    THEN 404 is returned (the same answer a non-member gets) and no remaining
        member's row is written
    """
    remove_member(app, UTUB_ID_VALUE, PLAIN_MEMBER_ID)

    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"urls": {"hide_copy_button": True}})

    assert response.status_code == 404
    assert _stored(app, CREATOR_ID) is None
    assert _stored(app, CO_OWNER_ID) is None


def test_never_member_gets_404(add_single_user_to_utub_without_logging_in, app):
    """
    GIVEN an existing user who was never added to the UTub
    WHEN they PATCH their settings
    THEN 404 is returned and no membership row is written for them
    """
    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"urls": {"hide_copy_button": True}})

    assert response.status_code == 404
    with app.app_context():
        assert Utub_Members.query.get((UTUB_ID_VALUE, PLAIN_MEMBER_ID)) is None
    assert _stored(app, CREATOR_ID) is None
    assert _stored(app, CO_OWNER_ID) is None


def test_anonymous_patch_is_rejected(
    add_multiple_users_to_utub_without_logging_in, client: FlaskClient, app
):
    """
    GIVEN a logged-out, tokenless client
    WHEN it PATCHes member settings
    THEN it is rejected at the CSRF layer (403, which runs before the
        login_required redirect for state-changing methods) and nothing is stored
    """
    with app.test_request_context():
        url = url_for(ROUTES.UTUBS.UPDATE_MEMBER_SETTINGS, utub_id=UTUB_ID_VALUE)

    response = client.patch(url, json={"urls": {"hide_copy_button": True}})

    assert response.status_code == 403
    for member_id in (CREATOR_ID, CO_OWNER_ID, PLAIN_MEMBER_ID):
        assert _stored(app, member_id) is None


def test_trashed_utub_returns_404(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a trashed UTub
    WHEN a member PATCHes their settings
    THEN 404 is returned
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, UTUB_ID_VALUE, deleted_by=CREATOR_ID)

    response = _patch(app, client, csrf_token, {"urls": {}})

    assert response.status_code == 404


def test_missing_utub_returns_404(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a UTub id that does not exist
    WHEN a member PATCHes settings
    THEN 404 is returned
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {}}, utub_id=9999)

    assert response.status_code == 404


def test_missing_csrf_token_returns_403(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged in member
    WHEN they PATCH without a CSRF token
    THEN 403 HTML is returned and nothing is stored
    """
    client, _, _, app = login_first_user_without_register
    with app.app_context():
        url = url_for(ROUTES.UTUBS.UPDATE_MEMBER_SETTINGS, utub_id=UTUB_ID_VALUE)

    response = client.patch(url, json={"urls": {"hide_copy_button": True}})

    assert response.status_code == 403
    assert response.content_type.startswith("text/html")
    assert _stored(app, CREATOR_ID) is None
