from datetime import datetime
from typing import Tuple
from unittest.mock import patch

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask.wrappers import Response
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.trash import UrlRestoredResponseSchema
from backend.urls.constants import URLErrorCodes
from backend.urls.services.create_urls import check_url_already_in_utub
from backend.utils.strings.json_strs import FAILURE_GENERAL, STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS, TAG_COUNTS_MODIFIED
from backend.utils.strings.trash_strs import TRASH_FAILURE, TRASH_SUCCESS
from backend.utils.strings.url_strs import URL_FAILURE
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.integration.trash.trash_helpers import (
    FIRST_USER_ID,
    FIRST_UTUB_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
    SECOND_UTUB_ID,
    THIRD_USER_ID,
    assert_not_in_trash_response,
    get_row_state,
    get_trash_url_ids,
    post_restore,
)
from tests.utils_for_test import (
    get_utub_url_id,
    lock_utub,
    remove_member,
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.trash

THIRD_UTUB_ID = 3
DESTINATION_BODY = {"destUtubId": SECOND_UTUB_ID}


def count_url_tag_rows(app: Flask, utub_url_id: int) -> int:
    with app.app_context():
        return Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_url_id == utub_url_id
        ).count()


def get_utub_last_updated(app: Flask, utub_id: int) -> datetime:
    with app.app_context():
        return Utubs.query.get(utub_id).last_updated


def assert_destination_failure(
    response: Response, status_code: int, error_code: int, message: str
) -> None:
    assert response.status_code == status_code
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == message
    assert response_json[STD_JSON_RESPONSE.ERROR_CODE] == error_code


def test_restore_url_trashed_with_its_utub_into_destination(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed with URL 3 (added by user 3, carrying the shared tag) in it
        and UTub 2 does not hold that URL
    WHEN creator user 1 restores URL 3 into UTub 2
    THEN the response is 200 describing the move, the row now belongs to UTub 2 and
        is credited to user 1 with a fresh added-at, its tag associations are gone and
        reported as lostTagCount, the title is kept, the origin UTub stays trashed and
        the row leaves the Trash list
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 3)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)
    assert before["deleted_at"] is None
    assert before["user_id"] == THIRD_USER_ID
    assert count_url_tag_rows(app, row_id) == 1
    assert row_id in get_trash_url_ids(client)
    destination_last_updated_before = get_utub_last_updated(app, SECOND_UTUB_ID)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.SUCCESS
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_SUCCESS.URL_RESTORED
    UrlRestoredResponseSchema.model_validate(response_json)
    assert response_json[UTUB_ID] == SECOND_UTUB_ID
    with app.app_context():
        assert response_json[UTUB_NAME] == Utubs.query.get(SECOND_UTUB_ID).name
    assert response_json[MODELS.RESTORED_TO_DESTINATION] is True
    assert response_json[MODELS.APPLIED_TAGS] == []
    assert response_json[TAG_COUNTS_MODIFIED] == {}
    assert response_json[MODELS.LOST_TAG_COUNT] == 1
    card = response_json[MODELS.URL]
    assert card[MODELS.UTUB_URL_ID] == row_id
    assert card[MODELS.ADDED_BY] == FIRST_USER_ID
    assert card[MODELS.CAN_DELETE] is True
    assert card[MODELS.URL_TAG_IDS] == []
    assert card[MODELS.URL_TITLE] == before["url_title"]

    after = get_row_state(app, row_id)
    assert after["utub_id"] == SECOND_UTUB_ID
    assert after["user_id"] == FIRST_USER_ID
    assert after["added_at"] > before["added_at"]
    assert after["url_title"] == before["url_title"]
    assert after["last_accessed"] == before["last_accessed"]
    assert after["deleted_at"] is None
    assert after["deleted_by"] is None
    assert after["trashed_tag_ids"] is None
    assert count_url_tag_rows(app, row_id) == 0
    with app.app_context():
        assert Utubs.query.get(FIRST_UTUB_ID).deleted_at is not None
    assert get_utub_last_updated(app, SECOND_UTUB_ID) > destination_last_updated_before
    assert row_id not in get_trash_url_ids(client)


def test_adder_of_url_in_trashed_utub_cannot_restore_it_into_destination(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and user 2, a plain member, added URL 2 to it
    WHEN user 2 restores that URL into UTub 3, which does not hold it
    THEN the response is 404 NOT_IN_TRASH: only the trashed UTub's creator acts on its
        URLs, whoever added them, and nothing changes
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)

    response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": THIRD_UTUB_ID}
    )

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id) == before


def test_restore_url_trashed_on_its_own_before_its_utub_into_destination(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 (shared + solo tags) was trashed on its own, the solo tag was then
        deleted from UTub 1, and UTub 1 was trashed afterwards
    WHEN user 1 restores URL 1 into UTub 2
    THEN lostTagCount counts the snapshot's tags and the surviving ones once each (2),
        the row is un-trashed in UTub 2 with no tags, and the origin UTub stays trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    with app.app_context():
        _, solo_tag_id = Utub_Urls.query.get(row_id).associated_tag_ids
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    with app.app_context():
        db.session.delete(Utub_Tags.query.get(solo_tag_id))
        db.session.commit()
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    assert count_url_tag_rows(app, row_id) == 1

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY)

    assert response.status_code == 200
    assert response.json[MODELS.RESTORED_TO_DESTINATION] is True
    assert response.json[MODELS.LOST_TAG_COUNT] == 2
    after = get_row_state(app, row_id)
    assert after["utub_id"] == SECOND_UTUB_ID
    assert after["deleted_at"] is None
    assert after["deleted_by"] is None
    assert after["trashed_tag_ids"] is None
    assert count_url_tag_rows(app, row_id) == 0
    with app.app_context():
        assert Utubs.query.get(FIRST_UTUB_ID).deleted_at is not None


def test_restore_into_destination_without_destination_is_bad_request(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL in the trashed UTub 1
    WHEN user 1 restores it without a destUtubId
    THEN the response is 400 DESTINATION_REQUIRED and nothing changes
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_destination_failure(
        response,
        400,
        URLErrorCodes.DESTINATION_REQUIRED,
        TRASH_FAILURE.DESTINATION_REQUIRED,
    )
    assert get_row_state(app, row_id) == before
    assert count_url_tag_rows(app, row_id) == 2


def test_restore_into_the_trashed_origin_is_invalid_destination(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL in the trashed UTub 1
    WHEN user 1 names UTub 1 itself as the destination
    THEN the response is 400 INVALID_DESTINATION and nothing changes
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)

    response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": FIRST_UTUB_ID}
    )

    assert_destination_failure(
        response,
        400,
        URLErrorCodes.INVALID_DESTINATION,
        TRASH_FAILURE.INVALID_DESTINATION,
    )
    assert get_row_state(app, row_id) == before
    assert count_url_tag_rows(app, row_id) == 2


@pytest.mark.parametrize("destination_state", ["missing", "trashed", "not_a_member"])
def test_restore_into_unavailable_destination_is_masked_not_found(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    destination_state: str,
):
    """
    GIVEN a URL in the trashed UTub 1 and a destination that does not exist, is itself
        trashed, or is one user 1 does not belong to
    WHEN user 1 restores the URL into it
    THEN the response is the same masked 404 in every case and nothing changes
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    destination_utub_id: int = SECOND_UTUB_ID
    if destination_state == "missing":
        destination_utub_id = NONEXISTENT_ID
    elif destination_state == "trashed":
        trash_utub(app, SECOND_UTUB_ID, deleted_by=SECOND_USER_ID)
    else:
        remove_member(app, SECOND_UTUB_ID, FIRST_USER_ID)
    before = get_row_state(app, row_id)
    baseline = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": NONEXISTENT_ID}
    )

    response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": destination_utub_id}
    )

    assert response.status_code == 404
    assert response.is_json
    assert response.json[STD_JSON_RESPONSE.MESSAGE] == FAILURE_GENERAL.NOT_FOUND
    assert response.json[STD_JSON_RESPONSE.MESSAGE] != TRASH_FAILURE.NOT_IN_TRASH
    assert response.json == baseline.json
    assert get_row_state(app, row_id) == before
    assert count_url_tag_rows(app, row_id) == 2


def test_restore_into_locked_destination_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL in the trashed UTub 1 and a locked destination UTub 2
    WHEN user 1 restores the URL into UTub 2
    THEN the response is 403 UTUB_IS_LOCKED and nothing changes
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    lock_utub(app, SECOND_UTUB_ID)
    before = get_row_state(app, row_id)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY)

    assert response.status_code == 403
    assert response.json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response.json[STD_JSON_RESPONSE.ERROR_CODE] == URLErrorCodes.UTUB_IS_LOCKED
    assert get_row_state(app, row_id) == before
    assert count_url_tag_rows(app, row_id) == 2


def test_restore_out_of_locked_trashed_origin_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL in UTub 1, which is both trashed and locked
    WHEN creator user 1 restores it into the unlocked UTub 2
    THEN the response is 403 UTUB_IS_LOCKED and nothing changes
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = get_row_state(app, row_id)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY)

    assert response.status_code == 403
    assert response.json[STD_JSON_RESPONSE.ERROR_CODE] == URLErrorCodes.UTUB_IS_LOCKED
    assert get_row_state(app, row_id) == before
    assert count_url_tag_rows(app, row_id) == 2


def test_non_actionable_member_restoring_to_destination_gets_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL user 3 neither added nor manages, in the trashed and locked UTub 1
    WHEN user 3 restores it into the unlocked UTub 2
    THEN the response is 404 NOT_IN_TRASH, never revealing the lock, and nothing changes
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = get_row_state(app, row_id)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY)

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id) == before
    assert count_url_tag_rows(app, row_id) == 2


@pytest.mark.parametrize("occupant_is_trashed", [False, True])
def test_restore_url_already_in_destination_conflicts(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    occupant_is_trashed: bool,
):
    """
    GIVEN URL 2 sits in the trashed UTub 1 and UTub 2 already holds URL 2, live or
        trashed
    WHEN user 1 restores UTub 1's copy into UTub 2
    THEN the response is 409 URL_ALREADY_IN_DESTINATION naming the URL, and neither
        row changes
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    occupant_row_id = get_utub_url_id(app, SECOND_UTUB_ID, 2)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    if occupant_is_trashed:
        trash_utub_url(app, occupant_row_id, deleted_by=SECOND_USER_ID)
    before = get_row_state(app, row_id)
    occupant_before = get_row_state(app, occupant_row_id)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY)

    assert_destination_failure(
        response,
        409,
        URLErrorCodes.URL_ALREADY_IN_DESTINATION,
        TRASH_FAILURE.URL_ALREADY_IN_DESTINATION,
    )
    assert response.json[URL_FAILURE.URL_STRING]
    assert get_row_state(app, row_id) == before
    assert get_row_state(app, occupant_row_id) == occupant_before
    assert count_url_tag_rows(app, row_id) == 1


def test_restore_losing_a_concurrent_add_race_conflicts_and_rolls_back(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 in the trashed UTub 1, which the pre-check sees as absent from UTub 2
    WHEN another request adds URL 1 to UTub 2 before the restore's flush
    THEN the unique_url_per_utub violation is answered with 409
        URL_ALREADY_IN_DESTINATION, the restore is rolled back (row, tag associations)
        and the concurrent add stands
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)
    with app.app_context():
        url_id: int = Utub_Urls.query.get(row_id).url_id

    def add_concurrently_after_real_pre_check(
        utub_id: int, checked_url_id: int
    ) -> Utub_Urls | None:
        # The harness shares one transaction across sessions, so the concurrent
        # add commits through the scoped session, as the sibling race test does.
        occupant = check_url_already_in_utub(utub_id, checked_url_id)
        assert occupant is None
        with app.app_context():
            db.session.add(
                Utub_Urls(
                    utub_id=SECOND_UTUB_ID,
                    url_id=checked_url_id,
                    user_id=SECOND_USER_ID,
                )
            )
            db.session.commit()
        return occupant

    with patch(
        "backend.urls.services.trash_urls.check_url_already_in_utub",
        side_effect=add_concurrently_after_real_pre_check,
    ) as pre_check_mock:
        response = post_restore(
            client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY
        )

    pre_check_mock.assert_called_once_with(SECOND_UTUB_ID, url_id)
    assert_destination_failure(
        response,
        409,
        URLErrorCodes.URL_ALREADY_IN_DESTINATION,
        TRASH_FAILURE.URL_ALREADY_IN_DESTINATION,
    )
    assert response.json[URL_FAILURE.URL_STRING]
    assert get_row_state(app, row_id) == before
    assert count_url_tag_rows(app, row_id) == 2
    with app.app_context():
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == SECOND_UTUB_ID, Utub_Urls.url_id == url_id
            ).count()
            == 1
        )


@pytest.mark.parametrize(
    "failure",
    [RuntimeError("boom"), IntegrityError("statement", {}, Exception("other"))],
    ids=["runtime_error", "other_integrity_error"],
)
def test_restore_into_destination_failure_rolls_back_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    failure: Exception,
):
    """
    GIVEN URL 1 in the trashed UTub 1 and the final last-updated stamp failing after
        the row was moved (a generic error, or an IntegrityError that is not the
        unique_url_per_utub violation)
    WHEN user 1 restores it into UTub 2
    THEN the error is a 500, it is logged, the move and the deleted tag associations
        are rolled back and no URL_RESTORED_FROM_TRASH counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch.object(Utubs, "set_last_updated", side_effect=failure),
        patch("backend.urls.services.trash_urls.warning_log") as warning_log_mock,
    ):
        response = post_restore(
            client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY
        )

    assert response.status_code == 500
    warning_log_mock.assert_called_once()
    assert get_row_state(app, row_id) == before
    assert count_url_tag_rows(app, row_id) == 2
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )


def test_restore_into_destination_records_destination_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL in the trashed UTub 1 and metrics enabled
    WHEN user 1 restores it into UTub 2
    THEN exactly one URL_RESTORED_FROM_TRASH counter key is written with
        restore_target "destination"
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY)

    assert response.status_code == 200
    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH
    )
    assert len(counter_keys) == 1
    assert parse_dims(counter_keys[0])["restore_target"] == "destination"


def test_failed_destination_restores_do_not_record_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 2 in the trashed UTub 1 (also live in UTub 2) and a destination that is
        then locked
    WHEN user 1 attempts a 409, a 400, a masked 404 and a 403 restore
    THEN none of them emits URL_RESTORED_FROM_TRASH
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)

    conflict = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id, DESTINATION_BODY)
    missing_destination = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)
    unknown_destination = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": NONEXISTENT_ID}
    )
    lock_utub(app, THIRD_UTUB_ID)
    locked = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": THIRD_UTUB_ID}
    )

    assert conflict.status_code == 409
    assert missing_destination.status_code == 400
    assert unknown_destination.status_code == 404
    assert locked.status_code == 403
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )
