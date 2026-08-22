from unittest.mock import patch

from flask import current_app, url_for
from flask_login import current_user
import pytest
from werkzeug.exceptions import NotFound

from backend.metrics.events import EventName
from backend.models.utub_members import Utub_Members
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.urls.constants import BulkCopySkipReason, DestCopyStatus, URLErrorCodes
from backend.urls.services.copy_urls import _copy_source_rows_into_dest
from backend.utils.all_routes import ROUTES
from backend.utils.constants import URL_CONSTANTS
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
SOURCE_UTUB_ID_FIELD = "sourceUtubId"
DEST_UTUB_IDS_FIELD = "destUtubIds"
UTUB_URL_IDS_FIELD = "utubUrlIds"
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


# Happy Path Tests :)
def test_route_copies_urls_into_two_destinations_happy_path(
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a source UTub (id 1) holding URLs {1, 2, 3} and two clean destination
        UTubs (2 and 3), the copier a member of all three
    WHEN source URL 1 (net-new to both destinations) is copied into [2, 3]
    THEN the server returns 200, both destinations each gain one Utub_Urls row
        (attributed to the copier, url_title carried, same url_id as the source),
        the source UTub row count is unchanged, each per-destination result is
        `status="ok"` with the source→dest id pair in `copied` and empty `skipped`,
        and totalCopied==2 / totalSkipped==0.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_row = source_by_url_id[1]
        target_id = target_row.id
        target_url_id = target_row.url_id
        target_title = target_row.url_title
        source_count_before = _dest_url_row_count(SOURCE_UTUB_ID)
        dest2_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_before = _dest_url_row_count(THIRD_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: [target_id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == URL_SUCCESS.URLS_COPIED
    assert body[MODEL_STRS.TOTAL_COPIED] == 2
    assert body[MODEL_STRS.TOTAL_SKIPPED] == 0

    results = _result_by_dest(body)
    assert set(results.keys()) == {DEST_UTUB_ID, THIRD_UTUB_ID}
    for dest_id in (DEST_UTUB_ID, THIRD_UTUB_ID):
        result = results[dest_id]
        assert result[MODEL_STRS.STATUS] == DestCopyStatus.OK.value
        assert result[MODEL_STRS.SKIPPED] == []
        copied = result[MODEL_STRS.COPIED]
        assert len(copied) == 1
        assert copied[0][MODEL_STRS.SOURCE_UTUB_URL_ID] == target_id

    with app.app_context():
        assert _dest_url_row_count(SOURCE_UTUB_ID) == source_count_before
        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before + 1
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before + 1
        for dest_id in (DEST_UTUB_ID, THIRD_UTUB_ID):
            new_dest_id = results[dest_id][MODEL_STRS.COPIED][0][MODEL_STRS.UTUB_URL_ID]
            new_dest_row: Utub_Urls = Utub_Urls.query.get(new_dest_id)
            assert new_dest_row is not None
            assert new_dest_row.utub_id == dest_id
            assert new_dest_row.user_id == copier_id
            assert new_dest_row.url_id == target_url_id
            assert new_dest_row.url_title == target_title

    assert is_string_in_logs("Copied bulk URLs into multiple UTubs", caplog.records)
    assert is_string_in_logs(f"SourceUTub.id={SOURCE_UTUB_ID}", caplog.records)


def test_route_partial_success_skips_per_destination_duplicate(
    add_multi_dest_with_one_dup,
    login_first_user_without_register,
):
    """
    GIVEN source URL 1 pre-seeded into destination UTub 3 only
    WHEN URL 1 is copied into [2, 3]
    THEN destination 2 copies it cleanly, destination 3 reports a DUPLICATE skip
        keyed on the SOURCE id with empty `copied`, totalCopied==1 / totalSkipped==1,
        and no duplicate row is written into UTub 3.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_row = source_by_url_id[1]
        target_id = target_row.id
        dest3_dup_rows_before = Utub_Urls.query.filter(
            Utub_Urls.utub_id == THIRD_UTUB_ID,
            Utub_Urls.url_id == target_row.url_id,
        ).count()

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: [target_id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
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
        dest3_skipped[0][MODEL_STRS.SKIP_REASON] == BulkCopySkipReason.DUPLICATE.value
    )

    with app.app_context():
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == THIRD_UTUB_ID,
                Utub_Urls.url_id == source_by_url_id[1].url_id,
            ).count()
            == dest3_dup_rows_before
        )


def test_route_all_skipped_is_noop(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a source and two destinations that already all hold URLs {1, 2, 3}
    WHEN every source URL is copied into [2, 3]
    THEN nothing is copied, every (destination, url) pair is a reported duplicate
        skip, neither destination's last_updated is bumped, and the response is 200.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
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

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: source_ids,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[MODEL_STRS.TOTAL_COPIED] == 0
    assert body[MODEL_STRS.TOTAL_SKIPPED] == len(source_ids) * 2

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_count_before
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_count_before
        dest2_after: Utubs = Utubs.query.get(DEST_UTUB_ID)
        dest3_after: Utubs = Utubs.query.get(THIRD_UTUB_ID)
        assert dest2_after.last_updated == dest2_last_updated_before
        assert dest3_after.last_updated == dest3_last_updated_before


def test_route_locked_destination_skip_and_report_200(
    add_multi_dest_with_one_locked,
    login_first_user_without_register,
):
    """
    GIVEN destination UTub 3 locked at write time (DD-3)
    WHEN source URL 1 is copied into [2, 3]
    THEN destination 2 copies it, destination 3's result is `status="locked"` with
        empty copied/skipped, the locked destination gains no rows and its
        last_updated is unchanged, and the response is still 200 (never 403).
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id
        dest3: Utubs = Utubs.query.get(THIRD_UTUB_ID)
        dest2_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_before = _dest_url_row_count(THIRD_UTUB_ID)
        dest3_last_updated_before = dest3.last_updated

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: [target_id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[MODEL_STRS.TOTAL_COPIED] == 1

    results = _result_by_dest(body)
    assert results[DEST_UTUB_ID][MODEL_STRS.STATUS] == DestCopyStatus.OK.value
    assert len(results[DEST_UTUB_ID][MODEL_STRS.COPIED]) == 1

    locked_result = results[THIRD_UTUB_ID]
    assert locked_result[MODEL_STRS.STATUS] == DestCopyStatus.LOCKED.value
    assert locked_result[MODEL_STRS.COPIED] == []
    assert locked_result[MODEL_STRS.SKIPPED] == []

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before + 1
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before
        dest3_after: Utubs = Utubs.query.get(THIRD_UTUB_ID)
        assert dest3_after.last_updated == dest3_last_updated_before


# Rejection Tests (cross-UTub / validation)
def test_route_cross_utub_id_rejected_400(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that belongs to a UTub OTHER than the claimed source
    WHEN it is included in a copy request
    THEN the whole request is rejected 400 with URL_NOT_IN_UTUB + INVALID_FORM_INPUT,
        and no rows are written to the destination.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        foreign_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == THIRD_UTUB_ID
        ).first()
        assert foreign_row is not None
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID],
            UTUB_URL_IDS_FIELD: [foreign_row.id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == URL_FAILURE.URL_NOT_IN_UTUB
    assert int(body[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_FORM_INPUT

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before


def test_route_empty_utub_url_ids_rejected(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a member of the source and destination UTubs
    WHEN they POST an empty utubUrlIds list
    THEN the schema's min_length rejects the request 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID],
            UTUB_URL_IDS_FIELD: [],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in body


def test_route_empty_dest_utub_ids_rejected(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a member of the source and destination UTubs
    WHEN they POST an empty destUtubIds list
    THEN the schema's min_length rejects the request 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [],
            UTUB_URL_IDS_FIELD: [source_row.id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in body


def test_route_over_max_bulk_copy_urls_rejected(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a member of the source and destination UTubs
    WHEN they POST utubUrlIds with MAX_BULK_COPY_URLS + 1 distinct ids
    THEN the schema's max_length rejects the request 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    over_cap_ids = list(range(1, URL_CONSTANTS.MAX_BULK_COPY_URLS + 2))
    assert len(over_cap_ids) == URL_CONSTANTS.MAX_BULK_COPY_URLS + 1

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID],
            UTUB_URL_IDS_FIELD: over_cap_ids,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in body


def test_route_over_max_bulk_copy_destinations_rejected(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a member of the source and destination UTubs
    WHEN they POST destUtubIds with MAX_BULK_COPY_DESTINATIONS + 1 distinct ids
    THEN the schema's max_length rejects the request 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()

    over_cap_dest_ids = list(range(2, URL_CONSTANTS.MAX_BULK_COPY_DESTINATIONS + 3))
    assert len(over_cap_dest_ids) == URL_CONSTANTS.MAX_BULK_COPY_DESTINATIONS + 1

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: over_cap_dest_ids,
            UTUB_URL_IDS_FIELD: [source_row.id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in body


def test_route_same_utub_copy_rejected_400(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN the source UTub id also appears in the destination list
    WHEN a copy is attempted
    THEN the service rejects 400 with CANNOT_COPY_TO_SAME_UTUB + INVALID_FORM_INPUT
        and writes no rows.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        source_count_before = _dest_url_row_count(SOURCE_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, SOURCE_UTUB_ID],
            UTUB_URL_IDS_FIELD: [source_row.id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.MESSAGE] == URL_FAILURE.CANNOT_COPY_TO_SAME_UTUB
    assert int(body[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_FORM_INPUT

    with app.app_context():
        assert _dest_url_row_count(SOURCE_UTUB_ID) == source_count_before


# Auth / Lock Tests
def test_route_non_member_of_source_returns_404(
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN the copier is a member of the destination UTub but NOT the source UTub
    WHEN a copy out of that source UTub is attempted
    THEN the service aborts 404 (masking the source UTub's existence) before any
        write, and the destination gains no rows.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        dest_utub: Utubs = Utubs.query.filter(Utubs.utub_creator == copier_id).first()
        source_utub: Utubs = Utubs.query.filter(Utubs.utub_creator != copier_id).first()
        assert Utub_Members.query.get((dest_utub.id, copier_id)) is not None
        assert Utub_Members.query.get((source_utub.id, copier_id)) is None
        source_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == source_utub.id
        ).first()
        dest_utub_id = dest_utub.id
        source_utub_id = source_utub.id
        source_url_id = source_url.id
        dest_count_before = _dest_url_row_count(dest_utub_id)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: source_utub_id,
            DEST_UTUB_IDS_FIELD: [dest_utub_id],
            UTUB_URL_IDS_FIELD: [source_url_id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404

    with app.app_context():
        assert _dest_url_row_count(dest_utub_id) == dest_count_before


def test_route_non_member_of_destination_returns_404(
    add_multi_dest_with_one_nonmember,
    login_first_user_without_register,
):
    """
    GIVEN a destination UTub the copier is NOT a member of (DD-4). Phase 3 got this
        masking "for free" via the path decorator; it is now validated service-side.
    WHEN a copy targeting that destination is attempted
    THEN the service masks it as 404 before any write, and no rows are written to
        any destination.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        assert Utub_Members.query.get((THIRD_UTUB_ID, copier_id)) is None
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id
        dest2_before = _dest_url_row_count(DEST_UTUB_ID)
        dest3_before = _dest_url_row_count(THIRD_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: [target_id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before


def test_route_invalid_csrf_returns_403(
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN a member of the source and destination UTubs
    WHEN they POST without a valid CSRF token
    THEN the server returns 403 and no rows are written to the destination.
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_id = source_by_url_id[1].id
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: [target_id],
        },
    )

    assert response.status_code == 403

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before


def test_route_does_not_carry_tags(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a source URL that carries tags and destinations that do not hold it
    WHEN the URL is copied into [2, 3]
    THEN every new destination Utub_Urls row has zero tag associations — tags are
        never carried across a copy.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == source_row.id
            ).count()
            > 0
        )
        source_row_id = source_row.id

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: [source_row_id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    results = _result_by_dest(response.json)

    with app.app_context():
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


# Atomicity Tests
def test_route_mid_loop_exception_leaves_zero_rows(
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a copy of one net-new source URL into two destinations where the per-
        destination core raises on the SECOND destination (DD-5)
    WHEN the endpoint processes the batch
    THEN the exception propagates (PROPAGATE_EXCEPTIONS is on in testing), the
        already-flushed FIRST destination row is rolled back too (single terminal
        commit never reached), neither destination keeps a row, and the rollback
        breadcrumb is logged.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
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
            client.post(
                url_for(ROUTES.URLS.COPY_URLS_MULTI),
                json={
                    SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
                    DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
                    UTUB_URL_IDS_FIELD: [target_id],
                },
                headers={"X-CSRFToken": csrf_token},
            )

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest2_before
        assert _dest_url_row_count(THIRD_UTUB_ID) == dest3_before

    assert is_string_in_logs("Bulk multi-UTub URL copy failed", caplog.records)
    assert is_string_in_logs(f"SourceUTub.id={SOURCE_UTUB_ID}", caplog.records)
    assert is_string_in_logs("error_type=RuntimeError", caplog.records)


# Metrics Tests
def test_route_records_one_urls_copied_to_utub_event(
    metrics_enabled_app,
    provide_metrics_redis,
    add_multi_dest_state_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a mixed multi-destination copy (URLs 1 and 3 into
        [2, 3], where URL 3 is already present in destination 3)
    WHEN the batch is copied through the endpoint
    THEN exactly one URLS_COPIED_TO_UTUB counter is written carrying
        url_count_bucket="2-5" (3 copied), skipped_count_bucket="1" (1 skipped), and
        destination_count_bucket="2-5" (both destinations received >=1 copy).
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_ids = [source_by_url_id[1].id, source_by_url_id[3].id]

    assert count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB) == 0

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: target_ids,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB) == 1

    keys = find_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
    dims = parse_dims(keys[0])
    assert dims[URL_COUNT_BUCKET_DIM_KEY] == "2-5"
    assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "1"
    assert dims[DESTINATION_COUNT_BUCKET_DIM_KEY] == "2-5"


def test_route_no_metric_when_all_skipped(
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
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == SOURCE_UTUB_ID).all()
        ]

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS_MULTI),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            DEST_UTUB_IDS_FIELD: [DEST_UTUB_ID, THIRD_UTUB_ID],
            UTUB_URL_IDS_FIELD: source_ids,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB) == 0


# Route Disambiguation Smoke Test
def test_copy_route_resolves_distinctly_from_add_and_tag_batch(app):
    """
    GIVEN the new no-path-param copy path `/utubs/urls/copy`
    WHEN Flask's URL map matches each POST path
    THEN `/utubs/urls/copy` resolves to copy_urls_to_utubs, distinctly from the
        create-URL and apply-tags-to-URLs view functions and the
        `/urls/<int:utub_url_id>` GET route, and the OLD single-destination path
        `/utubs/1/urls/copy` NO LONGER resolves.

    Pure URL-map smoke test: needs only the app (no logged-in user or seed data).
    """
    with app.app_context():
        url_adapter = current_app.url_map.bind("localhost")

        copy_endpoint, _ = url_adapter.match("/utubs/urls/copy", method="POST")
        add_endpoint, _ = url_adapter.match("/utubs/1/urls", method="POST")
        tag_batch_endpoint, _ = url_adapter.match(
            "/utubs/1/urls/tags/batch", method="POST"
        )
        get_endpoint, get_args = url_adapter.match("/utubs/1/urls/2", method="GET")

        # The retired single-destination path must no longer match.
        with pytest.raises(NotFound):
            url_adapter.match("/utubs/1/urls/copy", method="POST")

    assert copy_endpoint == ROUTES.URLS.COPY_URLS_MULTI
    assert add_endpoint == ROUTES.URLS.CREATE_URL
    assert tag_batch_endpoint == ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS
    assert copy_endpoint != add_endpoint
    assert copy_endpoint != tag_batch_endpoint
    assert get_endpoint == ROUTES.URLS.GET_URL
    assert get_args["utub_url_id"] == 2
