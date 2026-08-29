from unittest.mock import patch

import pytest

from backend import db
from backend.metrics.events import EventName
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.urls.constants import BulkDeleteSkipReason, URLErrorCodes
from backend.urls.services.delete_urls import delete_urls_in_utub
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import TAG_COUNTS_MODIFIED
from backend.utils.strings.model_strs import MODELS as MODEL_STRS
from backend.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.urls

FIRST_UTUB_ID = 1
SECOND_UTUB_ID = 2
CREATOR_USER_ID = 1
MEMBER_USER_ID = 2
THIRD_MEMBER_USER_ID = 3
URL_COUNT_BUCKET_DIM_KEY = "url_count_bucket"
SKIPPED_COUNT_BUCKET_DIM_KEY = "skipped_count_bucket"


def _utub_url_rows_by_url_id(utub_id: int) -> dict[int, Utub_Urls]:
    """Return {url_id: Utub_Urls} for every URL row in a UTub.

    Must be called within an active app context.
    """
    return {
        row.url_id: row
        for row in Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).all()
    }


def _utub_url_row_count(utub_id: int) -> int:
    return Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).count()


def _first_utub_tag_ids(utub_id: int) -> list[int]:
    return [
        tag.id
        for tag in Utub_Tags.query.filter(Utub_Tags.utub_id == utub_id)
        .order_by(Utub_Tags.id)
        .all()
    ]


def _tag_counts_from_body(body: dict) -> dict[int, int]:
    """Normalize the JSON tag-count map's string keys back to int ids."""
    return {int(tag_id): count for tag_id, count in body[TAG_COUNTS_MODIFIED].items()}


def test_service_creator_deletes_own_urls_happy(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN the literal creator (user 1) of a UTub holding three URLs
    WHEN two of those URLs are bulk-deleted
    THEN both rows are removed, total_deleted==2, nothing is skipped, and the response
        is 200.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id, rows_by_url_id[2].id]
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

        response, status_code = delete_urls_in_utub(
            utub_url_ids=target_ids,
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=CREATOR_USER_ID,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert body[STD_JSON.MESSAGE] == URL_SUCCESS.URLS_DELETED
        assert body[MODEL_STRS.TOTAL_DELETED] == 2
        assert body[MODEL_STRS.TOTAL_SKIPPED] == 0
        assert body[MODEL_STRS.SKIPPED] == []
        assert {
            entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.DELETED]
        } == (set(target_ids))

        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before - 2
        for deleted_id in target_ids:
            assert Utub_Urls.query.get(deleted_id) is None


def test_service_member_partial_permission_skip(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a plain member (user 2) who added only URL 2 in a UTub they do not own
    WHEN they bulk-delete all three URLs (theirs + two added by others)
    THEN only their own URL is deleted; the other two come back FORBIDDEN-skipped with
        correct totals, and only one row is removed.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        own_id = rows_by_url_id[2].id
        creators_id = rows_by_url_id[1].id
        third_members_id = rows_by_url_id[3].id
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

        response, status_code = delete_urls_in_utub(
            utub_url_ids=[creators_id, own_id, third_members_id],
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=MEMBER_USER_ID,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.TOTAL_DELETED] == 1
        assert body[MODEL_STRS.TOTAL_SKIPPED] == 2
        assert [
            entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.DELETED]
        ] == ([own_id])

        skipped_by_id = {
            entry[MODEL_STRS.UTUB_URL_ID]: entry[MODEL_STRS.SKIP_REASON]
            for entry in body[MODEL_STRS.SKIPPED]
        }
        assert skipped_by_id == {
            creators_id: BulkDeleteSkipReason.FORBIDDEN.value,
            third_members_id: BulkDeleteSkipReason.FORBIDDEN.value,
        }

        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before - 1
        assert Utub_Urls.query.get(own_id) is None
        assert Utub_Urls.query.get(creators_id) is not None
        assert Utub_Urls.query.get(third_members_id) is not None


def test_service_all_skipped_is_noop(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a plain member (user 2) targeting ONLY URLs added by others
    WHEN they bulk-delete those two URLs
    THEN nothing is deleted, both are FORBIDDEN-skipped, last_updated is not bumped, and
        the response is still 200.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id, rows_by_url_id[3].id]
        first_utub: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        count_before = _utub_url_row_count(FIRST_UTUB_ID)
        last_updated_before = first_utub.last_updated

        response, status_code = delete_urls_in_utub(
            utub_url_ids=target_ids,
            utub=first_utub,
            current_user_id=MEMBER_USER_ID,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.TOTAL_DELETED] == 0
        assert body[MODEL_STRS.TOTAL_SKIPPED] == 2
        assert body[MODEL_STRS.DELETED] == []
        assert body[TAG_COUNTS_MODIFIED] == {}
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before
        assert first_utub.last_updated == last_updated_before


def test_service_rejects_cross_utub_id_spoofing(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that belongs to a UTub OTHER than the target
    WHEN it is included in a bulk-delete request
    THEN the whole request is rejected 400 with URLS_NOT_IN_UTUB + INVALID_FORM_INPUT
        and ZERO rows are deleted.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        foreign_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SECOND_UTUB_ID
        ).first()
        assert foreign_row is not None
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

        response, status_code = delete_urls_in_utub(
            utub_url_ids=[foreign_row.id],
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=CREATOR_USER_ID,
        )
        body = response.get_json()

        assert status_code == 400
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert body[STD_JSON.MESSAGE] == URL_FAILURE.URLS_NOT_IN_UTUB
        assert body[STD_JSON.ERROR_CODE] == URLErrorCodes.INVALID_FORM_INPUT
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before
        assert Utub_Urls.query.get(foreign_row.id) is not None


def test_service_rejects_unknown_id_spoofing(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that does not exist at all
    WHEN it is included in a bulk-delete request alongside a valid id
    THEN the whole request is rejected 400 and ZERO rows are deleted.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        valid_id = rows_by_url_id[1].id
        unknown_id = 999_999
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

        response, status_code = delete_urls_in_utub(
            utub_url_ids=[valid_id, unknown_id],
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=CREATOR_USER_ID,
        )
        body = response.get_json()

        assert status_code == 400
        assert body[STD_JSON.MESSAGE] == URL_FAILURE.URLS_NOT_IN_UTUB
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before


def test_service_locked_utub_is_403(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a locked UTub
    WHEN a bulk-delete is attempted
    THEN the whole request is rejected 403 (UTub is locked) and no rows are deleted.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        first_utub: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        first_utub.is_locked = True
        db.session.commit()

        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id]
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

        response, status_code = delete_urls_in_utub(
            utub_url_ids=target_ids,
            utub=first_utub,
            current_user_id=CREATOR_USER_ID,
        )
        body = response.get_json()

        assert status_code == 403
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert body[STD_JSON.ERROR_CODE] == URLErrorCodes.UTUB_IS_LOCKED
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before


def test_service_cascade_removes_url_tags(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a deleted URL carrying tag associations
    WHEN it is bulk-deleted
    THEN its Utub_Url_Tags rows are removed alongside the Utub_Urls row.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_row = rows_by_url_id[1]
        target_id = target_row.id
        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == target_id).count()
            > 0
        )

        delete_urls_in_utub(
            utub_url_ids=[target_id],
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=CREATOR_USER_ID,
        )

        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == target_id).count()
            == 0
        )


def test_service_shared_tag_recompute_and_zero_backfill(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a UTub where a `shared` tag is on URLs 1, 2, and 3 and a `solo` tag is on
        URL 1 only
    WHEN the creator bulk-deletes URLs 1 and 2
    THEN the shared tag's recomputed count is the AGGREGATE remaining count (1, still
        on URL 3), not a naive double-decrement, AND the solo tag whose last URL was
        deleted is PRESENT in the map with count 0 (not omitted).
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id, rows_by_url_id[2].id]
        tag_ids = _first_utub_tag_ids(FIRST_UTUB_ID)
        shared_tag_id = tag_ids[0]
        solo_tag_id = tag_ids[1]

        response, _ = delete_urls_in_utub(
            utub_url_ids=target_ids,
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=CREATOR_USER_ID,
        )
        body = response.get_json()

        tag_counts = _tag_counts_from_body(body)
        # Shared tag still applies to URL 3 -> aggregate 1 (not 3-1-1 arithmetic drift).
        assert tag_counts[shared_tag_id] == 1
        # Solo tag's only URL was deleted -> present with 0, NOT omitted.
        assert solo_tag_id in tag_counts
        assert tag_counts[solo_tag_id] == 0


def test_service_metric_emitted_on_delete(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a member bulk-delete that deletes one URL and skips two
    WHEN the delete runs
    THEN exactly one URLS_DELETED_FROM_UTUB counter is written carrying
        url_count_bucket="1" (1 deleted) and skipped_count_bucket="2-5" (2 skipped).
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [
            rows_by_url_id[1].id,
            rows_by_url_id[2].id,
            rows_by_url_id[3].id,
        ]

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_DELETED_FROM_UTUB)
            == 0
        )

        delete_urls_in_utub(
            utub_url_ids=target_ids,
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=MEMBER_USER_ID,
        )

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_DELETED_FROM_UTUB)
            == 1
        )
        keys = find_counter_keys(
            provide_metrics_redis, EventName.URLS_DELETED_FROM_UTUB
        )
        dims = parse_dims(keys[0])
        assert dims[URL_COUNT_BUCKET_DIM_KEY] == "1"
        assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "2-5"


def test_service_no_metric_when_all_skipped(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a bulk-delete where every targeted URL is FORBIDDEN
    WHEN the delete runs
    THEN no URLS_DELETED_FROM_UTUB counter is written (nothing was actually deleted).
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id, rows_by_url_id[3].id]

        delete_urls_in_utub(
            utub_url_ids=target_ids,
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=MEMBER_USER_ID,
        )

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_DELETED_FROM_UTUB)
            == 0
        )


def test_service_mid_loop_exception_rolls_back_all(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a bulk-delete of two URLs where the per-row delete raises on the SECOND row
    WHEN the service processes the batch
    THEN the exception propagates, the already-removed FIRST row is rolled back too
        (single terminal commit never reached), no rows are deleted, and the rollback
        breadcrumb is logged.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id, rows_by_url_id[2].id]
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

        real_delete = db.session.delete
        call_count = {"value": 0}

        def failing_delete(instance):
            call_count["value"] += 1
            if call_count["value"] == 2:
                raise RuntimeError("simulated mid-loop failure")
            return real_delete(instance)

        with patch.object(db.session, "delete", side_effect=failing_delete):
            with pytest.raises(RuntimeError, match="simulated mid-loop failure"):
                delete_urls_in_utub(
                    utub_url_ids=target_ids,
                    utub=Utubs.query.get(FIRST_UTUB_ID),
                    current_user_id=CREATOR_USER_ID,
                )

        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before
        for target_id in target_ids:
            assert Utub_Urls.query.get(target_id) is not None

    assert is_string_in_logs("Bulk URL delete failed", caplog.records)
    assert is_string_in_logs(f"UTub.id={FIRST_UTUB_ID}", caplog.records)
    assert is_string_in_logs("error_type=RuntimeError", caplog.records)


def test_service_co_creator_can_delete_third_members_url(
    add_co_creator_and_mixed_delete_permission_urls,
    login_first_user_without_register,
):
    """
    GIVEN a co-creator (user 2, NOT the literal utub.utub_creator) of a UTub holding a
        URL added by a THIRD member
    WHEN the co-creator bulk-deletes their own URL plus the third member's URL
    THEN BOTH URLs are deleted with nothing skipped — a co-owner (co-creator) is a
        manager and may delete any URL in the UTub (DD-1), so the third member's URL is
        no longer FORBIDDEN-skipped.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        co_creators_own_id = rows_by_url_id[2].id
        third_members_id = rows_by_url_id[3].id

        response, status_code = delete_urls_in_utub(
            utub_url_ids=[co_creators_own_id, third_members_id],
            utub=Utubs.query.get(FIRST_UTUB_ID),
            current_user_id=MEMBER_USER_ID,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.TOTAL_DELETED] == 2
        assert body[MODEL_STRS.TOTAL_SKIPPED] == 0
        assert body[MODEL_STRS.SKIPPED] == []
        assert {
            entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.DELETED]
        } == {co_creators_own_id, third_members_id}

        assert Utub_Urls.query.get(co_creators_own_id) is None
        assert Utub_Urls.query.get(third_members_id) is None
