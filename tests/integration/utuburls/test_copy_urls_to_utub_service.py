from unittest.mock import patch

from flask_login import current_user
import pytest
from werkzeug.exceptions import NotFound

from backend import db
from backend.metrics.events import EventName
from backend.models.utub_members import Utub_Members
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.urls.constants import BulkCopySkipReason, URLErrorCodes
from backend.urls.services.copy_urls import copy_urls_into_utub
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as MODEL_STRS
from backend.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.urls

SOURCE_UTUB_ID = 1
DEST_UTUB_ID = 2
THIRD_UTUB_ID = 3
URL_COUNT_BUCKET_DIM_KEY = "url_count_bucket"
SKIPPED_COUNT_BUCKET_DIM_KEY = "skipped_count_bucket"


def _source_rows_by_url_id(utub_id: int) -> dict[int, Utub_Urls]:
    """Return {url_id: Utub_Urls} for every URL row in a UTub.

    Must be called within an active app context.
    """
    return {
        row.url_id: row
        for row in Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).all()
    }


def _dest_url_row_count(utub_id: int) -> int:
    return Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).count()


def test_service_copies_urls_into_dest_happy_path(
    add_mixed_state_source_and_dest_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN a source UTub (id 1) holding URLs {1, 2, 3} and a destination UTub
        (id 2) holding only URL 2, with the copier a member of both
    WHEN the two source URLs NOT already in the destination (URLs 1 and 3) are copied
    THEN the service returns 200, the destination gains two Utub_Urls rows (each
        attributed to the copier, url_title carried, same url_id as the source),
        the source UTub row count is unchanged, `copied` carries the source→dest id
        pairs, and `skipped` is empty.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        # URLs 1 and 3 are not in the destination (which holds only URL 2).
        target_source_rows = [source_by_url_id[1], source_by_url_id[3]]
        target_ids = [row.id for row in target_source_rows]
        source_url_ids_by_source_id = {row.id: row.url_id for row in target_source_rows}
        title_by_source_id = {row.id: row.url_title for row in target_source_rows}
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)

        source_count_before = _dest_url_row_count(SOURCE_UTUB_ID)
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

        response, status_code = copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=target_ids,
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert body[STD_JSON.MESSAGE] == URL_SUCCESS.URLS_COPIED
        assert body[MODEL_STRS.SKIPPED] == []

        copied = body[MODEL_STRS.COPIED]
        assert len(copied) == 2
        assert {entry[MODEL_STRS.SOURCE_UTUB_URL_ID] for entry in copied} == set(
            target_ids
        )

        assert _dest_url_row_count(SOURCE_UTUB_ID) == source_count_before
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before + 2

        for entry in copied:
            source_id = entry[MODEL_STRS.SOURCE_UTUB_URL_ID]
            new_dest_row: Utub_Urls = Utub_Urls.query.get(entry[MODEL_STRS.UTUB_URL_ID])
            assert new_dest_row is not None
            assert new_dest_row.utub_id == DEST_UTUB_ID
            assert new_dest_row.user_id == copier_id
            assert new_dest_row.url_id == source_url_ids_by_source_id[source_id]
            assert new_dest_row.url_title == title_by_source_id[source_id]
            assert entry[MODEL_STRS.URL_TITLE] == title_by_source_id[source_id]


def test_service_partial_success_skips_duplicate(
    add_mixed_state_source_and_dest_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN a source UTub holding URLs {1, 2, 3} and a destination already holding URL 2
    WHEN all three source URLs are copied in one request
    THEN URLs 1 and 3 are copied, URL 2 is reported in `skipped` with reason
        DUPLICATE keyed on its SOURCE id, and no second row for URL 2 is inserted
        into the destination.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        duplicate_source_id = source_by_url_id[2].id  # URL 2 already in destination
        all_source_ids = [
            source_by_url_id[1].id,
            source_by_url_id[2].id,
            source_by_url_id[3].id,
        ]
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)

        dup_rows_in_dest_before = Utub_Urls.query.filter(
            Utub_Urls.utub_id == DEST_UTUB_ID, Utub_Urls.url_id == 2
        ).count()

        response, status_code = copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=all_source_ids,
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        copied_source_ids = {
            entry[MODEL_STRS.SOURCE_UTUB_URL_ID] for entry in body[MODEL_STRS.COPIED]
        }
        assert copied_source_ids == {source_by_url_id[1].id, source_by_url_id[3].id}

        skipped = body[MODEL_STRS.SKIPPED]
        assert len(skipped) == 1
        assert skipped[0][MODEL_STRS.UTUB_URL_ID] == duplicate_source_id
        assert skipped[0][MODEL_STRS.SKIP_REASON] == BulkCopySkipReason.DUPLICATE.value

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == DEST_UTUB_ID, Utub_Urls.url_id == 2
            ).count()
            == dup_rows_in_dest_before
        )


def test_service_all_skipped_is_noop(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a source and destination UTub that already hold the same URLs
    WHEN every source URL is copied
    THEN `copied` is empty, every source URL is reported skipped, the destination
        gains no rows, its last_updated is NOT bumped, and the response is still 200.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == SOURCE_UTUB_ID).all()
        ]
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)
        last_updated_before = dest_utub.last_updated

        response, status_code = copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=source_ids,
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.COPIED] == []
        assert {
            entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.SKIPPED]
        } == (set(source_ids))
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before
        assert dest_utub.last_updated == last_updated_before


def test_service_non_member_of_source_aborts_404(
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN the copier is a member of the destination UTub but NOT the source UTub
    WHEN a copy is attempted out of that source UTub
    THEN the service aborts 404 (masking the source UTub's existence) before any
        write, and the destination gains no rows.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        # The copier (user 1) created / is a member of UTub 1 only, so UTub 2 is a
        # genuine non-membership source. Destination is the copier's own UTub 1.
        assert Utub_Members.query.get((DEST_UTUB_ID, copier_id)) is None
        source_url_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == DEST_UTUB_ID).all()
        ]
        dest_utub: Utubs = Utubs.query.get(SOURCE_UTUB_ID)
        dest_count_before = _dest_url_row_count(SOURCE_UTUB_ID)

        with pytest.raises(NotFound):
            copy_urls_into_utub(
                source_utub_id=DEST_UTUB_ID,
                utub_url_ids=source_url_ids,
                dest_utub=dest_utub,
                current_user_id=copier_id,
            )

        assert _dest_url_row_count(SOURCE_UTUB_ID) == dest_count_before


def test_service_rejects_cross_utub_id_spoofing(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that belongs to a UTub OTHER than the claimed source
    WHEN it is included in a copy request
    THEN the whole request is rejected 400 with URL_NOT_IN_UTUB + INVALID_FORM_INPUT,
        and no rows are written to the destination.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        foreign_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == THIRD_UTUB_ID
        ).first()
        assert foreign_row is not None
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

        response, status_code = copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=[foreign_row.id],
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 400
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert body[STD_JSON.MESSAGE] == URL_FAILURE.URL_NOT_IN_UTUB
        assert body[STD_JSON.ERROR_CODE] == URLErrorCodes.INVALID_FORM_INPUT
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before


def test_service_rejects_same_utub_copy(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN the source and destination UTub are the same
    WHEN a copy is attempted
    THEN the service rejects 400 with CANNOT_COPY_TO_SAME_UTUB + INVALID_FORM_INPUT
        and writes no rows.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        dest_utub: Utubs = Utubs.query.get(SOURCE_UTUB_ID)
        dest_count_before = _dest_url_row_count(SOURCE_UTUB_ID)

        response, status_code = copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=[source_row.id],
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 400
        assert body[STD_JSON.MESSAGE] == URL_FAILURE.CANNOT_COPY_TO_SAME_UTUB
        assert body[STD_JSON.ERROR_CODE] == URLErrorCodes.INVALID_FORM_INPUT
        assert _dest_url_row_count(SOURCE_UTUB_ID) == dest_count_before


def test_service_rejects_locked_destination(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a locked destination UTub (the copier IS a member of the source)
    WHEN a copy into it is attempted
    THEN the service rejects 403 with UTUB_IS_LOCKED and writes no rows.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)
        dest_utub.is_locked = True
        db.session.commit()
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

        response, status_code = copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=[source_row.id],
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )

        assert status_code == 403
        body = response.get_json()
        assert body[STD_JSON.ERROR_CODE] == URLErrorCodes.UTUB_IS_LOCKED
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before


def test_service_does_not_carry_tags(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a source URL that carries tags and a destination that does not hold it
    WHEN the URL is copied
    THEN the new destination Utub_Urls row has zero tag associations — tags are
        never carried across a copy.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        # Source UTub 1 holds URL 1 (with tags); destination UTub 2 holds URL 2, so
        # URL 1 is net-new to the destination and will actually be copied.
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == source_row.id
            ).count()
            > 0
        )
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)

        response, status_code = copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=[source_row.id],
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        copied = body[MODEL_STRS.COPIED]
        assert len(copied) == 1
        new_dest_url_id = copied[0][MODEL_STRS.UTUB_URL_ID]
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == new_dest_url_id
            ).count()
            == 0
        )


def test_service_mid_loop_exception_rolls_back_all(
    add_mixed_state_source_and_dest_for_copy,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a copy of two net-new source URLs where the duplicate check raises on its
        second call
    WHEN the service processes the batch
    THEN the exception propagates, the already-flushed first destination row is
        rolled back (single final commit never reached), and the rollback breadcrumb
        is logged.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        # URLs 1 and 3 are net-new to the destination, so both reach the insert path.
        target_ids = [source_by_url_id[1].id, source_by_url_id[3].id]
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

        call_count = {"value": 0}

        def failing_dup_check(utub_id, url_id):
            call_count["value"] += 1
            if call_count["value"] == 2:
                raise RuntimeError("simulated mid-loop failure")
            return False

        with patch(
            "backend.urls.services.copy_urls.check_url_already_in_utub",
            side_effect=failing_dup_check,
        ):
            with pytest.raises(RuntimeError, match="simulated mid-loop failure"):
                copy_urls_into_utub(
                    source_utub_id=SOURCE_UTUB_ID,
                    utub_url_ids=target_ids,
                    dest_utub=dest_utub,
                    current_user_id=copier_id,
                )

        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before

    assert is_string_in_logs("Bulk URL copy failed", caplog.records)
    assert is_string_in_logs(f"DestUTub.id={DEST_UTUB_ID}", caplog.records)
    assert is_string_in_logs("error_type=RuntimeError", caplog.records)


def test_service_records_metric_on_mixed_copy(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_state_source_and_dest_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a mixed copy (two copied, one duplicate skipped)
    WHEN the batch is copied
    THEN exactly one URLS_COPIED_TO_UTUB counter is written carrying
        url_count_bucket="2-5" (2 copied) and skipped_count_bucket="1" (1 skipped).
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        all_source_ids = [
            source_by_url_id[1].id,
            source_by_url_id[2].id,
            source_by_url_id[3].id,
        ]
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
            == 0
        )

        copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=all_source_ids,
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
            == 1
        )
        keys = find_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
        dims = parse_dims(keys[0])
        assert dims[URL_COUNT_BUCKET_DIM_KEY] == "2-5"
        assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "1"


def test_service_no_metric_when_all_skipped(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a copy where every source URL is already in the
        destination
    WHEN the batch is copied
    THEN no URLS_COPIED_TO_UTUB counter is written (nothing was actually copied).
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == SOURCE_UTUB_ID).all()
        ]
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)

        copy_urls_into_utub(
            source_utub_id=SOURCE_UTUB_ID,
            utub_url_ids=source_ids,
            dest_utub=dest_utub,
            current_user_id=copier_id,
        )

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
            == 0
        )
