from typing import Any, Tuple
from unittest.mock import patch

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.trash import UtubRestoredResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.trash_strs import TRASH_FAILURE, TRASH_SUCCESS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME
from backend.utubs.constants import UTubErrorCodes
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
)
from tests.integration.trash.trash_helpers import (
    AJAX_HEADERS,
    FIRST_USER_ID,
    FIRST_UTUB_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
    SECOND_UTUB_ID,
    THIRD_USER_ID,
    get_row_state,
    get_trash_url_ids,
    login_as_user,
)
from tests.utils_for_test import (
    get_utub_url_id,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.trash


def post_restore_utub(
    client: FlaskClient,
    csrf_token: str,
    utub_id: int,
) -> Response:
    return client.post(
        url_for(ROUTES.UTUBS.RESTORE_UTUB, utub_id=utub_id),
        json={},
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def assert_utub_not_in_trash_response(response: Response) -> None:
    assert response.status_code == 404
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_FAILURE.NOT_IN_TRASH
    assert response_json[STD_JSON_RESPONSE.ERROR_CODE] == UTubErrorCodes.NOT_IN_TRASH


def get_utub_state(app: Flask, utub_id: int) -> dict[str, Any]:
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        return {
            "deleted_at": utub.deleted_at,
            "deleted_by": utub.deleted_by,
            "last_updated": utub.last_updated,
            "is_locked": utub.is_locked,
            "utub_creator": utub.utub_creator,
        }


def get_listed_utub_ids(client: FlaskClient) -> list[int]:
    response = client.get(url_for(ROUTES.UTUBS.GET_UTUBS), headers=AJAX_HEADERS)
    assert response.status_code == 200
    return [item[MODELS.ID] for item in response.json[MODELS.UTUBS]]


def get_trashed_utub_ids(client: FlaskClient) -> list[int]:
    response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)
    assert response.status_code == 200
    return [item[UTUB_ID] for item in response.json[MODELS.UTUBS]]


def transfer_creator_by_erasure(app: Flask, utub_id: int, new_creator_id: int) -> None:
    """Hand a UTub's creator row to ``new_creator_id`` and demote the old creator.

    Mirrors the state left behind when the original creator's account is erased:
    ``utub_creator`` points at the new creator and exactly one member holds the
    CREATOR role. The old creator stays a plain member so the test can assert the
    previous creator is denied.
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        old_creator_member: Utub_Members = Utub_Members.query.get(
            (utub_id, utub.utub_creator)
        )
        old_creator_member.member_role = Member_Role.MEMBER
        db.session.commit()
        new_creator_member: Utub_Members = Utub_Members.query.get(
            (utub_id, new_creator_id)
        )
        new_creator_member.member_role = Member_Role.CREATOR
        utub.utub_creator = new_creator_id
        db.session.commit()


def test_creator_restores_trashed_utub(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1, holding three live URLs, is trashed by its creator
    WHEN the creator restores it
    THEN the response is 200 and validates against the restored-UTub schema, the trash
        fields are cleared, last_updated moves forward, the UTub is back in the deck
        and out of Trash, and nothing but the trash fields changed
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    before = get_utub_state(app, FIRST_UTUB_ID)
    assert FIRST_UTUB_ID not in get_listed_utub_ids(client)
    assert get_trashed_utub_ids(client) == [FIRST_UTUB_ID]

    response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.SUCCESS
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_SUCCESS.UTUB_RESTORED
    UtubRestoredResponseSchema.model_validate(response_json)
    with app.app_context():
        utub: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        assert response_json[UTUB_ID] == FIRST_UTUB_ID
        assert response_json[UTUB_NAME] == utub.name
        assert response_json[MODELS.UTUB_DESCRIPTION] == utub.utub_description
    assert response_json[MODELS.MEMBER_ROLE] == Member_Role.CREATOR.value
    assert response_json[MODELS.IS_LOCKED] is False
    assert response_json[MODELS.RESTORED_URL_COUNT] == 3

    after = get_utub_state(app, FIRST_UTUB_ID)
    assert before["deleted_at"] is not None
    assert after["deleted_at"] is None
    assert after["deleted_by"] is None
    assert after["last_updated"] > before["last_updated"]
    assert after["is_locked"] == before["is_locked"]
    assert after["utub_creator"] == before["utub_creator"]
    assert get_listed_utub_ids(client)[0] == FIRST_UTUB_ID
    assert get_trashed_utub_ids(client) == []


def test_restore_leaves_individually_trashed_url_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 2 was trashed on its own, then UTub 1 was trashed
    WHEN the creator restores the UTub
    THEN restoredUrlCount counts only the two live URLs and URL 2 stays in Trash with
        its own deletedAt untouched
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    before = get_row_state(app, row_id)

    response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert response.status_code == 200
    assert response.json[MODELS.RESTORED_URL_COUNT] == 2
    assert get_row_state(app, row_id) == before
    assert get_trash_url_ids(client) == [row_id]


@pytest.mark.parametrize("acting_user_id", [SECOND_USER_ID, THIRD_USER_ID])
def test_non_creator_gets_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    acting_user_id: int,
):
    """
    GIVEN UTub 1 is trashed by its creator, with user 2 a plain member and user 3
        promoted to CO_CREATOR
    WHEN that member or co-creator tries to restore it
    THEN the response is the masking 404 NOT_IN_TRASH and the UTub stays trashed
    """
    _, _, _, app = login_first_user_without_register
    set_member_role(app, FIRST_UTUB_ID, THIRD_USER_ID, Member_Role.CO_CREATOR)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    before = get_utub_state(app, FIRST_UTUB_ID)

    with login_as_user(app, acting_user_id) as (client, csrf_token):
        response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(response)
    assert get_utub_state(app, FIRST_UTUB_ID) == before


def test_live_utub_gets_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is live
    WHEN its creator tries to restore it
    THEN the response is 404 NOT_IN_TRASH and the UTub is unchanged
    """
    client, csrf_token, _, app = login_first_user_without_register
    before = get_utub_state(app, FIRST_UTUB_ID)

    response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(response)
    assert get_utub_state(app, FIRST_UTUB_ID) == before


def test_nonexistent_utub_gets_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN no UTub has the requested id
    WHEN user 1 tries to restore it
    THEN the response is the same 404 NOT_IN_TRASH as for a live UTub
    """
    client, csrf_token, _, _ = login_first_user_without_register

    response = post_restore_utub(client, csrf_token, NONEXISTENT_ID)

    assert_utub_not_in_trash_response(response)


def test_second_restore_gets_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 was trashed and restored once
    WHEN the creator restores it a second time
    THEN the second response is 404 NOT_IN_TRASH and last_updated is not bumped again
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    first_response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)
    assert first_response.status_code == 200
    after_first = get_utub_state(app, FIRST_UTUB_ID)

    second_response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(second_response)
    assert get_utub_state(app, FIRST_UTUB_ID) == after_first


def test_departed_creator_membership_gets_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and the creator's membership row is gone
    WHEN the creator tries to restore it
    THEN the response is 404 NOT_IN_TRASH and the UTub stays trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    remove_member(app, FIRST_UTUB_ID, FIRST_USER_ID)

    response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(response)
    assert get_utub_state(app, FIRST_UTUB_ID)["deleted_at"] is not None


def test_other_users_trashed_utub_gets_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 2 is created by user 2 and trashed, and user 1 is a plain member of it
    WHEN user 1 tries to restore UTub 2
    THEN the response is 404 NOT_IN_TRASH and UTub 2 stays trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, SECOND_UTUB_ID, SECOND_USER_ID)

    response = post_restore_utub(client, csrf_token, SECOND_UTUB_ID)

    assert_utub_not_in_trash_response(response)
    assert get_utub_state(app, SECOND_UTUB_ID)["deleted_at"] is not None


def test_locked_trashed_utub_is_forbidden_and_stays_trashed(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and locked
    WHEN its creator tries to restore it
    THEN the response is 403 UTUB_IS_LOCKED and the UTub is unchanged and still trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = get_utub_state(app, FIRST_UTUB_ID)

    response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert response.status_code == 403
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response_json[STD_JSON_RESPONSE.ERROR_CODE] == UTubErrorCodes.UTUB_IS_LOCKED
    assert get_utub_state(app, FIRST_UTUB_ID) == before
    assert before["deleted_at"] is not None


def test_locked_trashed_utub_does_not_leak_to_non_creator(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and locked
    WHEN a plain member tries to restore it
    THEN the response is the masking 404 NOT_IN_TRASH, not the creator-only 403
    """
    _, _, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)

    with login_as_user(app, SECOND_USER_ID) as (client, csrf_token):
        response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(response)


def test_new_creator_after_ownership_transfer_restores(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and ownership was transferred to user 2 (the original
        creator, user 1, is now a plain member)
    WHEN user 1 and then user 2 try to restore it
    THEN user 1 gets 404 NOT_IN_TRASH and user 2 restores it as the CREATOR
    """
    _, _, _, app = login_first_user_without_register
    transfer_creator_by_erasure(app, FIRST_UTUB_ID, SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, SECOND_USER_ID)

    with login_as_user(app, FIRST_USER_ID) as (old_client, old_csrf_token):
        old_creator_response = post_restore_utub(
            old_client, old_csrf_token, FIRST_UTUB_ID
        )
    with login_as_user(app, SECOND_USER_ID) as (new_client, new_csrf_token):
        new_creator_response = post_restore_utub(
            new_client, new_csrf_token, FIRST_UTUB_ID
        )

    assert_utub_not_in_trash_response(old_creator_response)
    assert new_creator_response.status_code == 200
    assert new_creator_response.json[MODELS.MEMBER_ROLE] == Member_Role.CREATOR.value
    assert get_utub_state(app, FIRST_UTUB_ID)["deleted_at"] is None


def test_restore_without_csrf_token_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed
    WHEN its creator POSTs the restore without a CSRF token
    THEN the response is the 403 HTML page and the UTub is still trashed
    """
    client, _, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)

    response = client.post(
        url_for(ROUTES.UTUBS.RESTORE_UTUB, utub_id=FIRST_UTUB_ID),
        json={},
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert get_utub_state(app, FIRST_UTUB_ID)["deleted_at"] is not None


def test_restore_records_utub_restored_from_trash_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed UTub and metrics enabled
    WHEN its creator restores it
    THEN exactly one UTUB_RESTORED_FROM_TRASH counter key is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUB_RESTORED_FROM_TRASH)
        == 0
    )

    response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert response.status_code == 200
    assert (
        len(
            find_counter_keys(provide_metrics_redis, EventName.UTUB_RESTORED_FROM_TRASH)
        )
        == 1
    )


def test_failed_restores_do_not_record_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a live UTub, then a trashed-and-locked UTub
    WHEN the creator attempts to restore each
    THEN neither the 404 nor the 403 emits UTUB_RESTORED_FROM_TRASH
    """
    client, csrf_token, _, app = login_first_user_without_register

    not_in_trash_response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    locked_response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    assert not_in_trash_response.status_code == 404
    assert locked_response.status_code == 403
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUB_RESTORED_FROM_TRASH)
        == 0
    )


def test_restore_service_failure_rolls_back_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed UTub and set_last_updated raising after the trash fields were cleared
    WHEN its creator restores it
    THEN the unhandled error is a 500, the failure is logged, the un-trash is rolled
        back (UTub still trashed with the same deleted_at) and no
        UTUB_RESTORED_FROM_TRASH counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    before = get_utub_state(app, FIRST_UTUB_ID)

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch.object(
            Utubs, "set_last_updated", side_effect=RuntimeError("boom")
        ) as set_last_updated_mock,
        patch("backend.utubs.services.trash_utubs.warning_log") as warning_log_mock,
    ):
        response = post_restore_utub(client, csrf_token, FIRST_UTUB_ID)

    set_last_updated_mock.assert_called_once()
    warning_log_mock.assert_called_once()
    assert response.status_code == 500
    assert get_utub_state(app, FIRST_UTUB_ID) == before
    assert before["deleted_at"] is not None
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUB_RESTORED_FROM_TRASH)
        == 0
    )
