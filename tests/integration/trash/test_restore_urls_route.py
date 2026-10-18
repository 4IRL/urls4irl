from datetime import datetime
from typing import Tuple
from unittest.mock import patch

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.schemas.trash import UrlsRestoredResponseSchema
from backend.urls.constants import BulkRestoreSkipReason, URLErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.constants import URL_CONSTANTS
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS, TAG_COUNTS_MODIFIED
from backend.utils.strings.trash_strs import TRASH_SUCCESS
from backend.utils.strings.utub_strs import UTUB_ID
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
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
    login_as_user,
    post_restore_urls,
)
from tests.utils_for_test import (
    count_tag_instances_in_utub,
    get_utub_url_id,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.trash


def skipped_by_id(response_json: dict) -> dict[int, str]:
    return {
        item[MODELS.UTUB_URL_ID]: item[MODELS.SKIP_REASON]
        for item in response_json[MODELS.SKIPPED]
    }


def first_utub_row_ids(app: Flask) -> tuple[int, int, int]:
    """Row ids of URL 1 (user 1), URL 2 (user 2) and URL 3 (user 3) in UTub 1."""
    return (
        get_utub_url_id(app, FIRST_UTUB_ID, 1),
        get_utub_url_id(app, FIRST_UTUB_ID, 2),
        get_utub_url_id(app, FIRST_UTUB_ID, 3),
    )


def test_restore_three_trashed_urls_in_place(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URLs 1, 2 and 3 of UTub 1 are trashed
    WHEN user 1 (creator) restores all three in one request
    THEN the response is 200 with three full cards keeping their adders, the rows are
        live again with every trash field cleared, nothing is skipped and
        tagCountsInUtub matches the association counts
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_ids = first_utub_row_ids(app)
    with app.app_context():
        shared_tag_id, solo_tag_id = Utub_Urls.query.get(row_ids[0]).associated_tag_ids
    before = {row_id: get_row_state(app, row_id) for row_id in row_ids}
    for row_id in row_ids:
        trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, list(row_ids))

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.SUCCESS
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_SUCCESS.URLS_RESTORED
    UrlsRestoredResponseSchema.model_validate(response_json)
    assert response_json[UTUB_ID] == FIRST_UTUB_ID
    assert response_json[MODELS.TOTAL_RESTORED] == 3
    assert response_json[MODELS.TOTAL_SKIPPED] == 0
    assert response_json[MODELS.SKIPPED] == []
    cards = {card[MODELS.UTUB_URL_ID]: card for card in response_json[MODELS.RESTORED]}
    assert set(cards) == set(row_ids)
    for row_id, adder_id in zip(
        row_ids, (FIRST_USER_ID, SECOND_USER_ID, THIRD_USER_ID)
    ):
        assert cards[row_id][MODELS.ADDED_BY] == adder_id
        assert cards[row_id][MODELS.CAN_DELETE] is True
        assert (
            datetime.fromisoformat(cards[row_id]["addedAt"])
            == before[row_id]["added_at"]
        )
        after = get_row_state(app, row_id)
        for cleared_field in (
            "deleted_at",
            "deleted_by",
            "trashed_tag_ids",
            "trashed_tag_names",
        ):
            assert after[cleared_field] is None
        assert after["user_id"] == adder_id
    assert response_json[MODELS.LOST_TAG_COUNT] == 0
    assert response_json[MODELS.LOST_TAG_NAMES] == []
    assert {tag[MODELS.ID] for tag in response_json[MODELS.APPLIED_TAGS]} == {
        shared_tag_id,
        solo_tag_id,
    }
    with app.app_context():
        assert response_json[TAG_COUNTS_MODIFIED] == {
            str(tag_id): count_tag_instances_in_utub(FIRST_UTUB_ID, tag_id)
            for tag_id in (shared_tag_id, solo_tag_id)
        }


def test_mixed_ids_restore_only_actionable_trashed_rows(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN trashed URLs 1 and 2 of UTub 1, a live URL 3, a nonexistent id and a trashed
        URL belonging to UTub 2
    WHEN user 1 sends all five ids to UTub 1's bulk restore
    THEN only URLs 1 and 2 are restored, every other id is skipped as not_in_trash, the
        response is 200 and the other UTub's row stays trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, second_row, live_row = first_utub_row_ids(app)
    with app.app_context():
        other_utub_row: int = (
            Utub_Urls.query.filter(Utub_Urls.utub_id == SECOND_UTUB_ID).first().id
        )
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, second_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, other_utub_row, deleted_by=FIRST_USER_ID)

    response = post_restore_urls(
        client,
        csrf_token,
        FIRST_UTUB_ID,
        [first_row, second_row, live_row, NONEXISTENT_ID, other_utub_row],
    )

    assert response.status_code == 200
    response_json = response.json
    assert {card[MODELS.UTUB_URL_ID] for card in response_json[MODELS.RESTORED]} == {
        first_row,
        second_row,
    }
    assert response_json[MODELS.TOTAL_RESTORED] == 2
    assert response_json[MODELS.TOTAL_SKIPPED] == 3
    assert skipped_by_id(response_json) == {
        live_row: BulkRestoreSkipReason.NOT_IN_TRASH,
        NONEXISTENT_ID: BulkRestoreSkipReason.NOT_IN_TRASH,
        other_utub_row: BulkRestoreSkipReason.NOT_IN_TRASH,
    }
    assert get_row_state(app, first_row)["deleted_at"] is None
    assert get_row_state(app, other_utub_row)["deleted_at"] is not None


def test_non_adder_plain_member_has_every_id_skipped(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN trashed URLs 1 and 2 of UTub 1, neither added by plain member user 3
    WHEN user 3 restores both
    THEN the response is 200 with both skipped as not_in_trash and the rows stay trashed
    """
    client, csrf_token, _, app = login_third_user_without_register
    first_row, second_row, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, second_row, deleted_by=SECOND_USER_ID)

    response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, second_row]
    )

    assert response.status_code == 200
    assert response.json[MODELS.RESTORED] == []
    assert response.json[MODELS.TOTAL_RESTORED] == 0
    assert response.json[MODELS.TOTAL_SKIPPED] == 2
    assert skipped_by_id(response.json) == {
        first_row: BulkRestoreSkipReason.NOT_IN_TRASH,
        second_row: BulkRestoreSkipReason.NOT_IN_TRASH,
    }
    assert get_row_state(app, first_row)["deleted_at"] is not None
    assert get_row_state(app, second_row)["deleted_at"] is not None


def test_removed_member_gets_200_with_everything_skipped(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 trashed their own URL 2 and was then removed from UTub 1
    WHEN user 2 restores it
    THEN the response is 200 with the id skipped as not_in_trash (membership is never
        revealed) and the row stays trashed
    """
    _, _, _, app = login_first_user_without_register
    _, second_row, _ = first_utub_row_ids(app)
    trash_utub_url(app, second_row, deleted_by=SECOND_USER_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    with login_as_user(app, SECOND_USER_ID) as (client, csrf_token):
        response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [second_row])

    assert response.status_code == 200
    assert response.json[MODELS.TOTAL_RESTORED] == 0
    assert response.json[MODELS.TOTAL_SKIPPED] == 1
    assert skipped_by_id(response.json) == {
        second_row: BulkRestoreSkipReason.NOT_IN_TRASH
    }
    assert get_row_state(app, second_row)["deleted_at"] is not None


def test_locked_utub_with_actionable_row_is_forbidden_and_restores_nothing(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN trashed URLs 1 and 2 of a UTub that is then locked
    WHEN the creator restores both
    THEN the response is 403 UTUB_IS_LOCKED and neither row is restored
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, second_row, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, second_row, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, second_row]
    )

    assert response.status_code == 403
    assert response.json[STD_JSON_RESPONSE.ERROR_CODE] == URLErrorCodes.UTUB_IS_LOCKED
    assert get_row_state(app, first_row)["deleted_at"] is not None
    assert get_row_state(app, second_row)["deleted_at"] is not None


def test_locked_utub_without_actionable_rows_never_leaks_the_lock(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 is trashed in a locked UTub and user 3 is not allowed to restore it
    WHEN user 3 restores it
    THEN the response is 200 with the id skipped, not a 403 that reveals the lock
    """
    client, csrf_token, _, app = login_third_user_without_register
    first_row, _, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [first_row])

    assert response.status_code == 200
    assert response.json[MODELS.TOTAL_RESTORED] == 0
    assert response.json[MODELS.TOTAL_SKIPPED] == 1
    assert skipped_by_id(response.json) == {
        first_row: BulkRestoreSkipReason.NOT_IN_TRASH
    }
    assert get_row_state(app, first_row)["deleted_at"] is not None


def test_restoring_the_same_ids_twice_skips_everything_the_second_time(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URLs 1 and 2 were trashed and then restored by one request
    WHEN the same request is sent again
    THEN the second response is 200 with both ids skipped as not_in_trash
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, second_row, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, second_row, deleted_by=FIRST_USER_ID)
    first_response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, second_row]
    )
    assert first_response.json[MODELS.TOTAL_RESTORED] == 2

    second_response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, second_row]
    )

    assert second_response.status_code == 200
    assert second_response.json[MODELS.TOTAL_RESTORED] == 0
    assert skipped_by_id(second_response.json) == {
        first_row: BulkRestoreSkipReason.NOT_IN_TRASH,
        second_row: BulkRestoreSkipReason.NOT_IN_TRASH,
    }


def test_lost_tags_are_summed_and_names_deduped_alphabetically(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN trashed URL 1 (shared + solo tags) and URL 3 (shared tag), and both UTub tags
        are then deleted from the UTub
    WHEN user 1 restores both
    THEN lostTagCount is 3 (2 + 1), lostTagNames is the alphabetical deduped union of
        the two tag strings, and there are no applied tags
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, _, third_row = first_utub_row_ids(app)
    with app.app_context():
        tag_ids: list[int] = Utub_Urls.query.get(first_row).associated_tag_ids
        tag_strings: list[str] = [
            Utub_Tags.query.get(tag_id).tag_string for tag_id in tag_ids
        ]
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, third_row, deleted_by=FIRST_USER_ID)
    with app.app_context():
        for tag_id in tag_ids:
            db.session.delete(Utub_Tags.query.get(tag_id))
        db.session.commit()

    response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, third_row]
    )

    assert response.status_code == 200
    assert response.json[MODELS.LOST_TAG_COUNT] == 3
    assert response.json[MODELS.LOST_TAG_NAMES] == sorted(set(tag_strings))
    assert response.json[MODELS.APPLIED_TAGS] == []
    assert response.json[TAG_COUNTS_MODIFIED] == {}


def test_surviving_tags_are_unioned_with_live_applied_counts(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN trashed URLs 1 (shared + solo tags) and 3 (shared tag), and only the solo tag
        is then deleted from the UTub
    WHEN user 1 restores both
    THEN lostTagCount is 1 naming the solo tag, appliedTags is just the shared tag
        counted across all three live URLs
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, _, third_row = first_utub_row_ids(app)
    with app.app_context():
        shared_tag_id, solo_tag_id = Utub_Urls.query.get(first_row).associated_tag_ids
        shared_tag_string: str = Utub_Tags.query.get(shared_tag_id).tag_string
        solo_tag_string: str = Utub_Tags.query.get(solo_tag_id).tag_string
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, third_row, deleted_by=FIRST_USER_ID)
    with app.app_context():
        db.session.delete(Utub_Tags.query.get(solo_tag_id))
        db.session.commit()

    response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, third_row]
    )

    assert response.status_code == 200
    assert response.json[MODELS.LOST_TAG_COUNT] == 1
    assert response.json[MODELS.LOST_TAG_NAMES] == [solo_tag_string]
    assert [
        (tag[MODELS.ID], tag[MODELS.TAG_STRING], tag[MODELS.TAG_APPLIED])
        for tag in response.json[MODELS.APPLIED_TAGS]
    ] == [(shared_tag_id, shared_tag_string, 3)]
    assert response.json[TAG_COUNTS_MODIFIED] == {str(shared_tag_id): 3}


def test_trashed_origin_utub_skips_rows_as_destination_required(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is itself in Trash
    WHEN its creator bulk-restores two of its rows in place plus a nonexistent id
    THEN the rows are skipped as destination_required (still in Trash, not gone), the
        nonexistent id as not_in_trash, and nothing is restored
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, second_row, _ = first_utub_row_ids(app)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, first_row)

    response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, second_row, NONEXISTENT_ID]
    )

    assert response.status_code == 200
    assert response.json[MODELS.RESTORED] == []
    assert response.json[MODELS.TOTAL_RESTORED] == 0
    assert response.json[MODELS.TOTAL_SKIPPED] == 3
    assert skipped_by_id(response.json) == {
        first_row: BulkRestoreSkipReason.DESTINATION_REQUIRED,
        second_row: BulkRestoreSkipReason.DESTINATION_REQUIRED,
        NONEXISTENT_ID: BulkRestoreSkipReason.NOT_IN_TRASH,
    }
    assert get_row_state(app, first_row) == before


def test_plain_member_in_trashed_utub_gets_every_id_masked_as_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is itself in Trash and user 3 is only a plain member of it
    WHEN user 3 bulk-restores two of its rows (neither added by them)
    THEN every id is skipped as not_in_trash and none as destination_required, so the
        trashed UTub is never revealed to a member who cannot act on it
    """
    client, csrf_token, _, app = login_third_user_without_register
    first_row, second_row, _ = first_utub_row_ids(app)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, first_row)

    response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, second_row]
    )

    assert response.status_code == 200
    assert response.json[MODELS.RESTORED] == []
    assert response.json[MODELS.TOTAL_SKIPPED] == 2
    assert skipped_by_id(response.json) == {
        first_row: BulkRestoreSkipReason.NOT_IN_TRASH,
        second_row: BulkRestoreSkipReason.NOT_IN_TRASH,
    }
    assert get_row_state(app, first_row) == before


def test_co_creator_restores_rows_other_members_added(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 3 is promoted to CO_CREATOR and URLs 1 and 2 (added by users 1 and 2)
        are trashed in UTub 1
    WHEN user 3 bulk-restores both
    THEN both are restored with their original adders and each returned card has
        canDelete true (the manager branch), nothing is skipped
    """
    _, _, _, app = login_first_user_without_register
    first_row, second_row, _ = first_utub_row_ids(app)
    set_member_role(app, FIRST_UTUB_ID, THIRD_USER_ID, Member_Role.CO_CREATOR)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, second_row, deleted_by=SECOND_USER_ID)

    with login_as_user(app, THIRD_USER_ID) as (client, csrf_token):
        response = post_restore_urls(
            client, csrf_token, FIRST_UTUB_ID, [first_row, second_row]
        )

    assert response.status_code == 200
    assert response.json[MODELS.TOTAL_RESTORED] == 2
    assert response.json[MODELS.TOTAL_SKIPPED] == 0
    cards = {card[MODELS.UTUB_URL_ID]: card for card in response.json[MODELS.RESTORED]}
    assert set(cards) == {first_row, second_row}
    assert cards[first_row][MODELS.ADDED_BY] == FIRST_USER_ID
    assert cards[second_row][MODELS.ADDED_BY] == SECOND_USER_ID
    for card in cards.values():
        assert card[MODELS.CAN_DELETE] is True
    assert get_row_state(app, first_row)["deleted_at"] is None
    assert get_row_state(app, second_row)["deleted_at"] is None


def test_bulk_restore_unauthenticated_is_redirected_and_restores_nothing(
    add_mixed_delete_permission_urls_in_first_utub,
    load_login_page: Tuple[FlaskClient, str],
    app: Flask,
):
    """
    GIVEN a trashed URL and a client that is not logged in
    WHEN it posts the bulk restore (with a valid CSRF token)
    THEN it is redirected away and the row stays trashed
    """
    client, csrf_token = load_login_page
    first_row, _, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [first_row])

    assert response.status_code == 302
    assert get_row_state(app, first_row)["deleted_at"] is not None


def test_bulk_restore_with_unverified_email_is_redirected_and_restores_nothing(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged-in user whose session records an unvalidated email
    WHEN they post the bulk restore
    THEN the email-validation gate redirects them and the row stays trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, _, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    with client.session_transaction() as session:
        session[EMAILS.EMAIL_VALIDATED_SESS_KEY] = False

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [first_row])

    assert response.status_code == 302
    assert get_row_state(app, first_row)["deleted_at"] is not None


def test_bulk_restore_records_one_metric_per_restored_row(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN three trashed URLs and metrics enabled
    WHEN user 1 restores all three in one request
    THEN URL_RESTORED_FROM_TRASH is counted three times under one restore_target
        "origin" key
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_ids = first_utub_row_ids(app)
    for row_id in row_ids:
        trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, list(row_ids))

    assert response.status_code == 200
    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH
    )
    assert len(counter_keys) == 1
    assert parse_dims(counter_keys[0])["restore_target"] == "origin"
    assert (
        sum_counter_values(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 3
    )


def test_skipped_ids_record_no_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL user 3 may not restore
    WHEN user 3 sends it to the bulk restore
    THEN no URL_RESTORED_FROM_TRASH counter is written
    """
    client, csrf_token, _, app = login_third_user_without_register
    first_row, _, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [first_row])

    assert response.status_code == 200
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )


@pytest.mark.parametrize(
    "bad_ids",
    [
        [],
        list(range(1, URL_CONSTANTS.MAX_BULK_DELETE_URLS + 2)),
        [0],
        [-1, 1],
    ],
    ids=["empty", "over-cap", "zero", "negative"],
)
def test_invalid_id_lists_are_bad_requests(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    bad_ids: list[int],
):
    """
    GIVEN an empty, over-cap or non-positive id list
    WHEN user 1 posts it to the bulk restore
    THEN the response is a 400 failure body
    """
    client, csrf_token, _, _ = login_first_user_without_register

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, bad_ids)

    assert response.status_code == 400
    assert response.json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE


def test_bulk_restore_without_csrf_token_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged-in user
    WHEN the bulk restore is posted without a CSRF token
    THEN the response is 403 and nothing is restored
    """
    client, _, _, app = login_first_user_without_register
    first_row, _, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)

    response = client.post(
        url_for(ROUTES.URLS.RESTORE_URLS, utub_id=FIRST_UTUB_ID),
        json={"utubUrlIds": [first_row]},
        headers=AJAX_HEADERS,
    )

    assert response.status_code == 403
    assert get_row_state(app, first_row)["deleted_at"] is not None


def test_restore_urls_route_does_not_collide_with_single_url_routes(
    app: Flask,
):
    """
    GIVEN the bulk and single URL routes share the /utubs/<id>/urls/ prefix
    WHEN the url_map resolves POST /utubs/<id>/urls/restore
    THEN it matches the bulk restore endpoint, not an <int:utub_url_id> sibling route
    """
    adapter = app.url_map.bind("localhost")

    endpoint, view_args = adapter.match(
        f"/utubs/{FIRST_UTUB_ID}/urls/restore", method="POST"
    )

    assert endpoint == ROUTES.URLS.RESTORE_URLS
    assert view_args == {"utub_id": FIRST_UTUB_ID}


def test_duplicate_ids_in_request_restore_once(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN trashed URLs 1 and 2
    WHEN the request repeats URL 1's id
    THEN each row is restored once: two cards, nothing skipped and one metric per row
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, second_row, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, second_row, deleted_by=FIRST_USER_ID)

    response = post_restore_urls(
        client, csrf_token, FIRST_UTUB_ID, [first_row, first_row, second_row]
    )

    assert response.status_code == 200
    assert response.json[MODELS.TOTAL_RESTORED] == 2
    assert response.json[MODELS.TOTAL_SKIPPED] == 0
    assert response.json[MODELS.SKIPPED] == []
    restored_ids = [card[MODELS.UTUB_URL_ID] for card in response.json[MODELS.RESTORED]]
    assert sorted(restored_ids) == sorted([first_row, second_row])
    assert (
        sum_counter_values(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 2
    )


def test_bulk_restore_service_failure_rolls_back_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN two trashed URLs and the tag-count recompute raising after the rows were un-trashed
    WHEN user 1 restores both
    THEN the unhandled error is a 500, the failure is logged, no row is restored
        (state unchanged) and no URL_RESTORED_FROM_TRASH counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_row, second_row, _ = first_utub_row_ids(app)
    trash_utub_url(app, first_row, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, second_row, deleted_by=FIRST_USER_ID)
    before = {row_id: get_row_state(app, row_id) for row_id in (first_row, second_row)}

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch(
            "backend.urls.services.trash_urls.recompute_tag_counts_after_delete",
            side_effect=RuntimeError("boom"),
        ) as recompute_mock,
        patch("backend.urls.services.trash_urls.warning_log") as warning_log_mock,
    ):
        response = post_restore_urls(
            client, csrf_token, FIRST_UTUB_ID, [first_row, second_row]
        )

    recompute_mock.assert_called_once()
    warning_log_mock.assert_called_once()
    assert response.status_code == 500
    for row_id, row_before in before.items():
        assert get_row_state(app, row_id) == row_before
        assert get_row_state(app, row_id)["deleted_at"] is not None
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )
