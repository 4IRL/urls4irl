from unittest.mock import patch

from flask_login import current_user
import pytest
from sqlalchemy import event
from werkzeug.exceptions import NotFound

from backend import db
from backend.metrics.events import EventName
from backend.models.utub_members import Utub_Members
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.urls.constants import BulkCopySkipReason, DestCopyStatus, URLErrorCodes
from backend.urls.services.copy_urls import (
    _copy_source_rows_into_dest,
    copy_urls_into_utubs,
)
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
DESTINATION_COUNT_BUCKET_DIM_KEY = "destination_count_bucket"


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


def _result_by_dest(body: dict) -> dict[int, dict]:
    """Index the per-destination result cluster by destination UTub id."""
    return {
        result[MODEL_STRS.DEST_UTUB_ID]: result
        for result in body[MODEL_STRS.SEARCH_RESULTS]
    }


def test_service_single_destination_list_happy(
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN a source UTub (id 1) holding URLs {1, 2, 3} and one destination UTub
        (id 2) holding only URL 2, the copier a member of both
    WHEN the two source URLs NOT already in the destination (URLs 1 and 3) are copied
        into the single-element destination list [2]
    THEN the consolidated endpoint subsumes the Phase 3 single-destination copy: the
        destination gains two rows, its one result is `status="ok"`, total_copied==2,
        total_skipped==0, and the source is unchanged.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_source_rows = [source_by_url_id[1], source_by_url_id[3]]
        target_ids = [row.id for row in target_source_rows]
        source_url_ids_by_source_id = {row.id: row.url_id for row in target_source_rows}
        title_by_source_id = {row.id: row.url_title for row in target_source_rows}

        source_count_before = _dest_url_row_count(SOURCE_UTUB_ID)
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID],
            utub_url_ids=target_ids,
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert body[STD_JSON.MESSAGE] == URL_SUCCESS.URLS_COPIED
        assert body[MODEL_STRS.TOTAL_COPIED] == 2
        assert body[MODEL_STRS.TOTAL_SKIPPED] == 0

        results = body[MODEL_STRS.SEARCH_RESULTS]
        assert len(results) == 1
        result = results[0]
        assert result[MODEL_STRS.DEST_UTUB_ID] == DEST_UTUB_ID
        assert result[MODEL_STRS.STATUS] == DestCopyStatus.OK.value
        assert result[MODEL_STRS.SKIPPED] == []

        copied = result[MODEL_STRS.COPIED]
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


def test_service_two_destinations_both_copy(
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN a source UTub holding URLs {1, 2, 3} and two destinations (2 and 3), the
        copier a member of all three
    WHEN source URL 1 (net-new to both destinations) is copied into [2, 3]
    THEN both destinations gain the row, both results are `status="ok"`,
        total_copied==2, and the source is unchanged.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id

        source_count_before = _dest_url_row_count(SOURCE_UTUB_ID)
        dest2_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_before = _dest_url_row_count(THIRD_UTUB_ID)

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=[target_id],
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.TOTAL_COPIED] == 2
        assert body[MODEL_STRS.TOTAL_SKIPPED] == 0

        results = _result_by_dest(body)
        assert set(results.keys()) == {DEST_UTUB_ID, THIRD_UTUB_ID}
        for dest_id in (DEST_UTUB_ID, THIRD_UTUB_ID):
            assert results[dest_id][MODEL_STRS.STATUS] == DestCopyStatus.OK.value
            assert len(results[dest_id][MODEL_STRS.COPIED]) == 1

        assert _dest_url_row_count(SOURCE_UTUB_ID) == source_count_before
        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before + 1
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before + 1


def test_service_per_destination_duplicate_skip(
    add_multi_dest_with_one_dup,
    login_first_user_without_register,
):
    """
    GIVEN source URL 1 pre-seeded into destination UTub 3 only
    WHEN URL 1 is copied into [2, 3]
    THEN destination 2 copies it cleanly, destination 3 reports a DUPLICATE skip keyed
        on the source id, total_skipped counts the skip, and no duplicate row is
        written into UTub 3.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_row = source_by_url_id[1]
        target_id = target_row.id

        dest3_dup_rows_before = Utub_Urls.query.filter(
            Utub_Urls.utub_id == THIRD_UTUB_ID,
            Utub_Urls.url_id == target_row.url_id,
        ).count()

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=[target_id],
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.TOTAL_COPIED] == 1
        assert body[MODEL_STRS.TOTAL_SKIPPED] == 1

        results = _result_by_dest(body)
        assert results[DEST_UTUB_ID][MODEL_STRS.STATUS] == DestCopyStatus.OK.value
        assert len(results[DEST_UTUB_ID][MODEL_STRS.COPIED]) == 1
        assert results[DEST_UTUB_ID][MODEL_STRS.SKIPPED] == []

        dest3_skipped = results[THIRD_UTUB_ID][MODEL_STRS.SKIPPED]
        assert results[THIRD_UTUB_ID][MODEL_STRS.COPIED] == []
        assert len(dest3_skipped) == 1
        assert dest3_skipped[0][MODEL_STRS.UTUB_URL_ID] == target_id
        assert (
            dest3_skipped[0][MODEL_STRS.SKIP_REASON]
            == BulkCopySkipReason.DUPLICATE.value
        )

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == THIRD_UTUB_ID,
                Utub_Urls.url_id == target_row.url_id,
            ).count()
            == dest3_dup_rows_before
        )


def test_service_all_skipped_is_noop(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a source and two destinations that already all hold URLs {1, 2, 3}
    WHEN every source URL is copied into [2, 3]
    THEN nothing is copied, each (destination, url) pair is a reported duplicate skip,
        neither destination's last_updated is bumped, and the response is still 200.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == SOURCE_UTUB_ID).all()
        ]

        dest2: Utubs = Utubs.query.get(DEST_UTUB_ID)
        dest3: Utubs = Utubs.query.get(THIRD_UTUB_ID)
        dest2_count_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_count_before = _dest_url_row_count(THIRD_UTUB_ID)
        dest2_last_updated_before = dest2.last_updated
        dest3_last_updated_before = dest3.last_updated

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=source_ids,
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.TOTAL_COPIED] == 0
        assert body[MODEL_STRS.TOTAL_SKIPPED] == len(source_ids) * 2
        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_count_before
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_count_before
        assert dest2.last_updated == dest2_last_updated_before
        assert dest3.last_updated == dest3_last_updated_before


def test_service_locked_destination_skip_and_report(
    add_multi_dest_with_one_locked,
    login_first_user_without_register,
):
    """
    GIVEN destination UTub 3 locked at write time (DD-3)
    WHEN source URL 1 is copied into [2, 3]
    THEN destination 2 copies it, destination 3's result is `status="locked"` with
        empty copied/skipped, the locked destination gains no rows and its
        last_updated is unchanged, and the response is still 200.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id

        dest3: Utubs = Utubs.query.get(THIRD_UTUB_ID)
        dest2_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_before = _dest_url_row_count(THIRD_UTUB_ID)
        dest3_last_updated_before = dest3.last_updated

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=[target_id],
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.TOTAL_COPIED] == 1

        results = _result_by_dest(body)
        assert results[DEST_UTUB_ID][MODEL_STRS.STATUS] == DestCopyStatus.OK.value
        assert len(results[DEST_UTUB_ID][MODEL_STRS.COPIED]) == 1

        locked_result = results[THIRD_UTUB_ID]
        assert locked_result[MODEL_STRS.STATUS] == DestCopyStatus.LOCKED.value
        assert locked_result[MODEL_STRS.COPIED] == []
        assert locked_result[MODEL_STRS.SKIPPED] == []

        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before + 1
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before
        assert dest3.last_updated == dest3_last_updated_before


def test_service_every_destination_locked_is_noop(
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN every enabled destination locked at write time
    WHEN a copy into [2, 3] is attempted
    THEN both results are `status="locked"`, nothing is copied, no commit occurs, and
        the response is still 200.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id

        for dest_id in (DEST_UTUB_ID, THIRD_UTUB_ID):
            Utubs.query.get(dest_id).is_locked = True
        db.session.commit()

        dest2_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_before = _dest_url_row_count(THIRD_UTUB_ID)

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=[target_id],
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.TOTAL_COPIED] == 0
        results = _result_by_dest(body)
        for dest_id in (DEST_UTUB_ID, THIRD_UTUB_ID):
            assert results[dest_id][MODEL_STRS.STATUS] == DestCopyStatus.LOCKED.value
        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before


def test_service_non_member_destination_aborts_404(
    add_multi_dest_with_one_nonmember,
    login_first_user_without_register,
):
    """
    GIVEN a destination UTub the copier is NOT a member of (DD-4)
    WHEN a copy targeting it is attempted
    THEN the service aborts 404 (masking) before any write, and no rows are written
        to any destination.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        assert Utub_Members.query.get((THIRD_UTUB_ID, copier_id)) is None
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id

        dest2_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_before = _dest_url_row_count(THIRD_UTUB_ID)

        with pytest.raises(NotFound):
            copy_urls_into_utubs(
                source_utub_id=SOURCE_UTUB_ID,
                dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
                utub_url_ids=[target_id],
                current_user_id=copier_id,
            )

        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before


def test_service_non_member_of_source_aborts_404(
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN the copier is a member of the destination UTub but NOT the source UTub
    WHEN a copy out of that source UTub is attempted
    THEN the service aborts 404 (masking the source UTub's existence) before any
        write, and the destination gains no rows.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        # The copier (user 1) is a member of UTub 1 only, so UTub 2 is a genuine
        # non-membership source. Destination is the copier's own UTub 1.
        assert Utub_Members.query.get((DEST_UTUB_ID, copier_id)) is None
        source_url_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == DEST_UTUB_ID).all()
        ]
        dest_count_before = _dest_url_row_count(SOURCE_UTUB_ID)

        with pytest.raises(NotFound):
            copy_urls_into_utubs(
                source_utub_id=DEST_UTUB_ID,
                dest_utub_ids=[SOURCE_UTUB_ID],
                utub_url_ids=source_url_ids,
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
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID],
            utub_url_ids=[foreign_row.id],
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
    GIVEN the source UTub id also appears in the destination list
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
        dest_count_before = _dest_url_row_count(SOURCE_UTUB_ID)

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, SOURCE_UTUB_ID],
            utub_url_ids=[source_row.id],
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 400
        assert body[STD_JSON.MESSAGE] == URL_FAILURE.CANNOT_COPY_TO_SAME_UTUB
        assert body[STD_JSON.ERROR_CODE] == URLErrorCodes.INVALID_FORM_INPUT
        assert _dest_url_row_count(SOURCE_UTUB_ID) == dest_count_before


def test_service_does_not_carry_tags(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a source URL that carries tags and destinations that do not hold it
    WHEN the URL is copied into [2, 3]
    THEN every new destination Utub_Urls row has zero tag associations — tags are
        never carried across a copy.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        # Source UTub 1 holds URL 1 (with tags); destinations 2 and 3 hold URL 2 / 3,
        # so URL 1 is net-new to both and will actually be copied.
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == source_row.id
            ).count()
            > 0
        )

        response, status_code = copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=[source_row.id],
            current_user_id=copier_id,
        )
        body = response.get_json()

        assert status_code == 200
        results = _result_by_dest(body)
        for dest_id in (DEST_UTUB_ID, THIRD_UTUB_ID):
            copied = results[dest_id][MODEL_STRS.COPIED]
            assert len(copied) == 1
            new_dest_url_id = copied[0][MODEL_STRS.UTUB_URL_ID]
            assert (
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_url_id == new_dest_url_id
                ).count()
                == 0
            )


def test_service_mid_loop_exception_rolls_back_all(
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a copy of one net-new source URL into two destinations where the per-
        destination core raises on the SECOND destination (DD-5)
    WHEN the service processes the batch
    THEN the exception propagates, the already-flushed FIRST destination's row is
        rolled back too (single terminal commit never reached), neither destination
        keeps a row, and the rollback breadcrumb is logged.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id

        dest2_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_before = _dest_url_row_count(THIRD_UTUB_ID)

        call_count = {"value": 0}

        def failing_core(**kwargs):
            call_count["value"] += 1
            if call_count["value"] == 2:
                raise RuntimeError("simulated mid-loop failure")
            return _copy_source_rows_into_dest(**kwargs)

        with patch(
            "backend.urls.services.copy_urls._copy_source_rows_into_dest",
            side_effect=failing_core,
        ):
            with pytest.raises(RuntimeError, match="simulated mid-loop failure"):
                copy_urls_into_utubs(
                    source_utub_id=SOURCE_UTUB_ID,
                    dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
                    utub_url_ids=[target_id],
                    current_user_id=copier_id,
                )

        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before

    assert is_string_in_logs("Bulk multi-UTub URL copy failed", caplog.records)
    assert is_string_in_logs(f"SourceUTub.id={SOURCE_UTUB_ID}", caplog.records)
    assert is_string_in_logs("error_type=RuntimeError", caplog.records)


def test_service_records_metric_on_mixed_multi_dest_copy(
    metrics_enabled_app,
    provide_metrics_redis,
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a mixed multi-destination copy (three net-new copies
        across two destinations, one duplicate skip)
    WHEN URLs 1 and 3 are copied into [2, 3] (URL 3 already present in dest 3)
    THEN exactly one URLS_COPIED_TO_UTUB counter is written carrying
        url_count_bucket="2-5" (3 copied), skipped_count_bucket="1" (1 skipped), and
        destination_count_bucket="2-5" (both destinations received >=1 copy;
        bucket_bulk_tag_url_count(2) == "2-5").
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_ids = [source_by_url_id[1].id, source_by_url_id[3].id]

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
            == 0
        )

        copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=target_ids,
            current_user_id=copier_id,
        )

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
            == 1
        )
        keys = find_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
        dims = parse_dims(keys[0])
        # 3 copied -> "2-5"; 1 skipped -> "1"; 2 destinations received a copy ->
        # bucket_bulk_tag_url_count(2) == "2-5" (the shared bulk bucket helper).
        assert dims[URL_COUNT_BUCKET_DIM_KEY] == "2-5"
        assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "1"
        assert dims[DESTINATION_COUNT_BUCKET_DIM_KEY] == "2-5"


def test_service_metric_destination_bucket_counts_only_copied_into_dests(
    metrics_enabled_app,
    provide_metrics_redis,
    add_multi_dest_with_one_locked,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and two targeted destinations where ONE (dest 3) is locked
        and ONE (dest 2) receives the copy
    WHEN source URL 1 is copied into [2, 3]
    THEN the single URLS_COPIED_TO_UTUB counter's destination_count_bucket reflects the
        number of destinations actually copied INTO (1 → bucket_bulk_tag_url_count(1)
        == "1"), NOT the targeted destination count of 2 (which would bucket as "2-5").
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
            == 0
        )

        copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=[target_id],
            current_user_id=copier_id,
        )

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
            == 1
        )
        keys = find_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
        dims = parse_dims(keys[0])
        # 1 copied -> "1"; 0 skipped -> "0"; only 1 destination received a copy (the
        # other was locked) -> bucket_bulk_tag_url_count(1) == "1", NOT the targeted
        # count of 2 (which would bucket as "2-5").
        assert dims[URL_COUNT_BUCKET_DIM_KEY] == "1"
        assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "0"
        assert dims[DESTINATION_COUNT_BUCKET_DIM_KEY] == "1"


def test_service_no_metric_when_all_skipped(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a copy where every source URL is already in every
        destination
    WHEN every source URL is copied into [2, 3]
    THEN no URLS_COPIED_TO_UTUB counter is written (nothing was actually copied).
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == SOURCE_UTUB_ID).all()
        ]

        copy_urls_into_utubs(
            source_utub_id=SOURCE_UTUB_ID,
            dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
            utub_url_ids=source_ids,
            current_user_id=copier_id,
        )

        assert (
            count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
            == 0
        )


def test_service_existing_pairs_prefetch_is_single_query(
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN a copy of multiple URLs into multiple destinations
    WHEN the batch is copied
    THEN the already-present check issues exactly ONE existing-pairs prefetch query
        (filtering utub_urls on both utub_id IN (...) AND url_id IN (...)), NOT one
        query per (destination, url) pair — guarding against a regression back to a
        per-pair `check_url_already_in_utub` call.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        # 3 urls x 2 destinations: a per-pair check would issue up to 6 queries.
        target_ids = [
            source_by_url_id[1].id,
            source_by_url_id[2].id,
            source_by_url_id[3].id,
        ]

        # The existing-pairs prefetch is the ONLY SELECT that filters utub_urls on
        # url_id IN (...); the source-id validation query filters utub_urls.id IN
        # (...) and per-pair `check_url_already_in_utub` (the regression we guard
        # against) would filter one url_id at a time (equality, not IN a list).
        existing_pairs_query_count = {"value": 0}

        def count_existing_pairs_query(
            conn, cursor, statement, parameters, context, executemany
        ):
            # Strip identifier quotes so the matcher is dialect-agnostic; the real
            # table/column render as `"utuburls"."urlid"`. The existing-pairs
            # prefetch is the ONLY SELECT filtering utuburls on urlid IN (...) — the
            # source-id validation filters `utuburls.id IN (...)`, and a regression
            # back to a per-pair `check_url_already_in_utub` would filter one urlid
            # by equality, never `urlid IN (...)`.
            normalized = " ".join(statement.lower().replace('"', "").split())
            if "utuburls.urlid in (" in normalized:
                existing_pairs_query_count["value"] += 1

        # Listen on the session's live connection, not the Engine class: the test
        # harness checks out a long-lived SAVEPOINT connection at fixture setup, so a
        # listener registered on the Engine afterwards never dispatches (the
        # connection's `_has_events` is already cached False).
        connection = db.session.connection()
        event.listen(connection, "before_cursor_execute", count_existing_pairs_query)
        try:
            copy_urls_into_utubs(
                source_utub_id=SOURCE_UTUB_ID,
                dest_utub_ids=[DEST_UTUB_ID, THIRD_UTUB_ID],
                utub_url_ids=target_ids,
                current_user_id=copier_id,
            )
        finally:
            event.remove(
                connection, "before_cursor_execute", count_existing_pairs_query
            )

        assert existing_pairs_query_count["value"] == 1
