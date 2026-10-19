from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from pydantic import Field

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.models.utubs import Utubs
from backend.schemas import utub_settings
from backend.schemas.utub_settings import TagsSettings
from backend.schemas.utubs import UtubSettingsUpdatedResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_FAILURE, UTUB_ID
from backend.utubs.constants import UTubErrorCodes
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.utils import assert_response_conforms_to_schema
from tests.settings_stub import STUB_KEY, StubUtubSettings, patch_settings_model
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
STUB_COUNT_KEY = "stub_count"


class StubTagsSettings(TagsSettings):
    stub_count: int = 0


class TwoSectionStubUtubSettings(StubUtubSettings):
    """Stub with settings in two sections, to test cross-section merges."""

    tags: StubTagsSettings = Field(default_factory=StubTagsSettings)


def _patch_two_section_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        utub_settings, "get_settings_model", lambda: TwoSectionStubUtubSettings
    )


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
):
    with app.app_context():
        url = url_for(ROUTES.UTUBS.UPDATE_UTUB_SETTINGS, utub_id=utub_id)
    return client.patch(url, json=body, headers={"X-CSRFToken": csrf_token})


def _stored_settings(app: Flask) -> Any:
    with app.app_context():
        db.session.expire_all()
        return Utubs.query.get(UTUB_ID_VALUE).settings


def _set_stored_settings(app: Flask, value: Any) -> None:
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID_VALUE)
        utub.settings = value
        db.session.commit()


def _last_updated(app: Flask) -> Any:
    with app.app_context():
        db.session.expire_all()
        return Utubs.query.get(UTUB_ID_VALUE).last_updated


def _count_commits(action) -> int:
    real_commit = db.session.commit
    with mock.patch.object(db.session, "commit", wraps=real_commit) as commit_spy:
        action()
    return commit_spy.call_count


def _seed_roles(app: Flask) -> None:
    set_member_role(app, UTUB_ID_VALUE, CO_OWNER_ID, Member_Role.CO_CREATOR)


def _assert_400(response, expected_error_keys: set[str]) -> None:
    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_SETTINGS
    )
    assert response.json[STD_JSON.ERROR_CODE] == INVALID_FORM_INPUT
    assert set(response.json[STD_JSON.ERRORS]) == expected_error_keys


def _default_settings_dict() -> dict[str, dict[str, Any]]:
    return {"utubs": {}, "members": {}, "tags": {}, "urls": {}}


# --------------------------------------------------------------------------
# Success paths
# --------------------------------------------------------------------------


def test_creator_empty_section_patch_returns_default_settings(
    add_multiple_users_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a UTub with no stored settings
    WHEN the creator PATCHes an empty section
    THEN a 200 conforming to the response schema with default settings is
        returned and nothing is stored
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {}})

    assert response.status_code == 200
    # The envelope's status is added by APIResponse, not part of the schema.
    assert_response_conforms_to_schema(
        {key: value for key, value in response.json.items() if key != STD_JSON.STATUS},
        UtubSettingsUpdatedResponseSchema,
        {UTUB_ID, MODELS.SETTINGS},
    )
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response.json[UTUB_ID] == UTUB_ID_VALUE
    assert response.json[MODELS.SETTINGS] == _default_settings_dict()
    assert _stored_settings(app) is None


def test_co_owner_can_patch_settings(
    add_multiple_users_to_utub_without_logging_in, app, monkeypatch
):
    """
    GIVEN a UTub with a co-owner
    WHEN the co-owner PATCHes a stub setting
    THEN a 200 with the full resolved settings is returned and the sparse
        overrides are stored
    """
    patch_settings_model(monkeypatch)
    _seed_roles(app)

    with _client_for(app, CO_OWNER_ID) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})

    assert response.status_code == 200
    assert response.json[MODELS.SETTINGS]["urls"] == {STUB_KEY: True}
    assert _stored_settings(app) == {"urls": {STUB_KEY: True}}


def test_creator_patch_stores_sparse_overrides_and_returns_full_settings(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN the settings seam patched to a stub section
    WHEN the creator PATCHes one stub key
    THEN the response holds the full resolved settings and the DB holds only
        the sparse override
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})

    assert response.status_code == 200
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response.json[MODELS.SETTINGS] == {
        **_default_settings_dict(),
        "urls": {STUB_KEY: True},
    }
    assert _stored_settings(app) == {"urls": {STUB_KEY: True}}


def test_explicit_default_value_is_pinned(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN a stub setting whose default is False
    WHEN the creator PATCHes it explicitly to False
    THEN the explicit value is stored (pinned), not treated as absent
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {STUB_KEY: False}})

    assert response.status_code == 200
    assert _stored_settings(app) == {"urls": {STUB_KEY: False}}


def test_patch_response_equals_following_detail_get(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN the stub seam and a committed settings PATCH
    WHEN the UTub detail is fetched
    THEN its settings equal the PATCH response settings
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register

    patch_response = _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})
    with app.app_context():
        detail_url = url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=UTUB_ID_VALUE)
    detail_response = client.get(detail_url)

    assert detail_response.status_code == 200
    assert detail_response.json[MODELS.SETTINGS] == patch_response.json[MODELS.SETTINGS]


def test_patch_response_serializes_all_seam_model_keys(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN the seam patched to a stub subclass with a non-base key
    WHEN the creator PATCHes an empty section
    THEN the response carries the stub key's default, not only base-class keys
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {}})

    assert response.status_code == 200
    assert response.json[MODELS.SETTINGS]["urls"] == {STUB_KEY: False}


def test_second_section_patch_does_not_clobber_first(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN overrides stored in the urls section
    WHEN the creator PATCHes the tags section
    THEN both sections' overrides are persisted
    """
    _patch_two_section_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register

    first = _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})
    second = _patch(app, client, csrf_token, {"tags": {STUB_COUNT_KEY: 5}})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json[MODELS.SETTINGS]["urls"] == {STUB_KEY: True}
    assert second.json[MODELS.SETTINGS]["tags"] == {STUB_COUNT_KEY: 5}
    assert _stored_settings(app) == {
        "urls": {STUB_KEY: True},
        "tags": {STUB_COUNT_KEY: 5},
    }


# --------------------------------------------------------------------------
# last_updated and commit behavior
# --------------------------------------------------------------------------


def test_committing_write_does_not_bump_last_updated(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN a UTub with a known last_updated
    WHEN a settings PATCH commits
    THEN Utubs.last_updated is unchanged
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register
    before = _last_updated(app)

    response = _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})

    assert response.status_code == 200
    assert _stored_settings(app) == {"urls": {STUB_KEY: True}}
    assert _last_updated(app) == before


def test_identical_overrides_patch_does_not_commit(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN stored overrides
    WHEN the creator PATCHes identical overrides, or an empty body
    THEN 200 is returned and no commit is issued, but the first write did commit
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register
    responses: list[Any] = []

    first_commits = _count_commits(
        lambda: responses.append(
            _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})
        )
    )
    same_commits = _count_commits(
        lambda: responses.append(
            _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})
        )
    )
    empty_commits = _count_commits(
        lambda: responses.append(_patch(app, client, csrf_token, {}))
    )

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert first_commits >= 1
    assert same_commits == 0
    assert empty_commits == 0
    assert responses[2].json[MODELS.SETTINGS]["urls"] == {STUB_KEY: True}


def test_empty_section_patch_cleans_invalid_stored_section(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN a UTub whose stored urls section is invalid
    WHEN the creator PATCHes {"urls": {}}
    THEN 200 with defaults is returned, the bad section is removed and a commit
        is issued; the same patch on a clean UTub does not commit, and {} on an
        invalid-section UTub does not commit either
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register
    responses: list[Any] = []

    # {} patches no section: invalid stored section stays verbatim, no commit
    _set_stored_settings(app, {"urls": "garbage"})
    empty_body_commits = _count_commits(
        lambda: responses.append(_patch(app, client, csrf_token, {}))
    )
    assert empty_body_commits == 0
    assert _stored_settings(app) == {"urls": "garbage"}

    # Patching the invalid section cleans it
    clean_commits = _count_commits(
        lambda: responses.append(_patch(app, client, csrf_token, {"urls": {}}))
    )
    assert clean_commits >= 1
    assert _stored_settings(app) is None
    assert responses[1].json[MODELS.SETTINGS]["urls"] == {STUB_KEY: False}

    # Same patch on a clean UTub: no commit
    clean_utub_commits = _count_commits(
        lambda: responses.append(_patch(app, client, csrf_token, {"urls": {}}))
    )
    assert clean_utub_commits == 0

    assert [response.status_code for response in responses] == [200, 200, 200]


def test_patch_strips_legacy_key_on_write(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN a stored urls section with a legacy unknown key
    WHEN the creator PATCHes a valid key into that section
    THEN 200 is returned and the legacy key is stripped on write
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register
    _set_stored_settings(app, {"urls": {"legacy_key": 1}})

    response = _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})

    assert response.status_code == 200
    assert _stored_settings(app) == {"urls": {STUB_KEY: True}}


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def test_unknown_key_in_shipped_section_returns_400(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
):
    """
    GIVEN the shipped (empty) sections
    WHEN the creator PATCHes any key into one
    THEN 400 with a dotted error key and errorCode 2 is returned, DB unchanged
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {"anything": 1}})

    _assert_400(response, {"urls.anything"})
    assert _stored_settings(app) is None


def test_invalid_value_returns_dotted_error_and_leaves_db_unchanged(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN the stub seam
    WHEN the creator PATCHes a value of the wrong type
    THEN 400 with errors["urls.stub_flag"] is returned and nothing is stored
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {STUB_KEY: "not-a-bool"}})

    _assert_400(response, {f"urls.{STUB_KEY}"})
    assert _stored_settings(app) is None


def test_errors_aggregate_across_sections(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN two invalid sections in one request
    WHEN the creator PATCHes them
    THEN a single 400 carries both dotted keys and the DB is unchanged
    """
    _patch_two_section_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(
        app,
        client,
        csrf_token,
        {"urls": {STUB_KEY: "nope"}, "tags": {STUB_COUNT_KEY: "nope"}},
    )

    _assert_400(response, {f"urls.{STUB_KEY}", f"tags.{STUB_COUNT_KEY}"})
    assert _stored_settings(app) is None


@pytest.mark.parametrize(
    "body",
    [
        {"unknown_section": {}},
        {"urls": None},
        {"urls": "string"},
        {"urls": ["list"]},
        {"urls": 5},
    ],
    ids=["unknown_top_level", "null_section", "string", "list", "number"],
)
def test_request_schema_shape_errors_return_400(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    body,
):
    """
    GIVEN a malformed settings body (unknown top-level key, null or non-object
        section)
    WHEN the creator PATCHes it
    THEN 400 with errorCode 2 is returned from the request-schema layer and the
        DB is unchanged
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, body)

    assert response.status_code == 400
    assert (
        response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_SETTINGS
    )
    assert response.json[STD_JSON.ERROR_CODE] == INVALID_FORM_INPUT
    assert STD_JSON.ERRORS in response.json
    assert _stored_settings(app) is None


def test_non_json_body_returns_400(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
):
    """
    GIVEN a creator
    WHEN they PATCH a non-JSON body
    THEN 400 is returned
    """
    client, csrf_token, _, app = login_first_user_without_register
    with app.app_context():
        url = url_for(ROUTES.UTUBS.UPDATE_UTUB_SETTINGS, utub_id=UTUB_ID_VALUE)

    response = client.patch(
        url,
        data="not json",
        content_type="text/plain",
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400


# --------------------------------------------------------------------------
# Permission matrix
# --------------------------------------------------------------------------


def test_plain_member_gets_403_not_authorized_without_error_code(
    add_multiple_users_to_utub_without_logging_in, app
):
    """
    GIVEN a plain member
    WHEN they PATCH settings
    THEN 403 NOT_AUTHORIZED is returned with no errorCode and nothing stored
    """
    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"urls": {}})

    assert response.status_code == 403
    assert response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
    assert STD_JSON.ERROR_CODE not in response.json
    assert _stored_settings(app) is None


def test_non_member_gets_404(add_multiple_users_to_utub_without_logging_in, app):
    """
    GIVEN a user who was removed from the UTub (revoked member)
    WHEN they PATCH settings
    THEN 404 is returned
    """
    remove_member(app, UTUB_ID_VALUE, PLAIN_MEMBER_ID)

    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"urls": {}})

    assert response.status_code == 404
    assert _stored_settings(app) is None


def test_trashed_utub_returns_404(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
):
    """
    GIVEN a trashed UTub
    WHEN its creator PATCHes settings
    THEN 404 is returned
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, UTUB_ID_VALUE, deleted_by=CREATOR_ID)

    response = _patch(app, client, csrf_token, {"urls": {}})

    assert response.status_code == 404


def test_missing_utub_returns_404(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
):
    """
    GIVEN a UTub id that does not exist
    WHEN the creator PATCHes settings
    THEN 404 is returned
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = _patch(app, client, csrf_token, {"urls": {}}, utub_id=9999)

    assert response.status_code == 404


def test_manager_on_locked_utub_gets_utub_is_locked(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    monkeypatch,
):
    """
    GIVEN a locked UTub
    WHEN a manager PATCHes settings
    THEN 403 UTUB_IS_LOCKED with errorCode 3 is returned and nothing is stored
    """
    patch_settings_model(monkeypatch)
    client, csrf_token, _, app = login_first_user_without_register
    lock_utub(app, UTUB_ID_VALUE)

    response = _patch(app, client, csrf_token, {"urls": {STUB_KEY: True}})

    assert response.status_code == 403
    assert response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert response.json[STD_JSON.ERROR_CODE] == UTubErrorCodes.UTUB_IS_LOCKED
    assert response.json[STD_JSON.ERROR_CODE] == 3
    assert _stored_settings(app) is None


def test_non_manager_on_locked_utub_gets_not_authorized(
    add_multiple_users_to_utub_without_logging_in, app
):
    """
    GIVEN a locked UTub
    WHEN a plain member PATCHes settings
    THEN 403 NOT_AUTHORIZED is returned with no errorCode (authorization first)
    """
    lock_utub(app, UTUB_ID_VALUE)

    with _client_for(app, PLAIN_MEMBER_ID) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"urls": {}})

    assert response.status_code == 403
    assert response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
    assert STD_JSON.ERROR_CODE not in response.json


@pytest.mark.parametrize(
    "user_id, expected_status",
    [(PLAIN_MEMBER_ID, 403), (None, 404)],
    ids=["plain_member", "non_member"],
)
def test_non_manager_with_malformed_body_gets_role_response_not_400(
    add_multiple_users_to_utub_without_logging_in, app, user_id, expected_status
):
    """
    GIVEN a non-manager (plain member or non-member)
    WHEN they PATCH a malformed body (unknown top-level key)
    THEN the role decorator's 403 / 404 wins; never 400
    """
    acting_user_id = PLAIN_MEMBER_ID
    if user_id is None:
        remove_member(app, UTUB_ID_VALUE, PLAIN_MEMBER_ID)

    with _client_for(app, acting_user_id) as (client, csrf_token):
        response = _patch(app, client, csrf_token, {"unknown_section": {}})

    assert response.status_code == expected_status


def test_missing_csrf_token_returns_403(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
):
    """
    GIVEN a logged in creator
    WHEN they PATCH settings without a CSRF token
    THEN 403 is returned and nothing is stored
    """
    client, _, _, app = login_first_user_without_register
    with app.app_context():
        url = url_for(ROUTES.UTUBS.UPDATE_UTUB_SETTINGS, utub_id=UTUB_ID_VALUE)

    response = client.patch(url, json={"urls": {}})

    assert response.status_code == 403
    assert _stored_settings(app) is None


def test_non_ajax_manager_request_redirects(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
):
    """
    GIVEN a logged in creator
    WHEN they PATCH settings without the AJAX header
    THEN the ajax_required default redirects with a 302
    """
    client, csrf_token, _, app = login_first_user_without_register
    with app.app_context():
        url = url_for(ROUTES.UTUBS.UPDATE_UTUB_SETTINGS, utub_id=UTUB_ID_VALUE)

    response = client.patch(
        url,
        json={"urls": {}},
        headers={
            "X-CSRFToken": csrf_token,
            URL_VALIDATION.X_REQUESTED_WITH: "not-ajax",
        },
    )

    assert response.status_code == 302
