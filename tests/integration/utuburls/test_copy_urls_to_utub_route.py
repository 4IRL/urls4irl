from unittest.mock import patch

from flask import current_app, url_for
from flask_login import current_user
import pytest

from backend import db
from backend.metrics.events import EventName
from backend.models.utub_members import Utub_Members
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.urls.constants import BulkCopySkipReason, URLErrorCodes
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
UTUB_URL_IDS_FIELD = "utubUrlIds"
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


# Happy Path Tests :)
def test_route_copies_urls_happy_path(
    add_mixed_state_source_and_dest_for_copy,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a source UTub (id 1) holding URLs {1, 2, 3} and a destination UTub
        (id 2) holding only URL 2, with the copier a member of both
    WHEN they POST the two source URLs NOT already in the destination (1 and 3)
        to the copy endpoint
    THEN the server returns 200, the destination gains two Utub_Urls rows (each
        attributed to the copier, url_title carried, same url_id as the source),
        the source UTub row count is unchanged, `copied` carries the source→dest id
        pairs, and `skipped` is empty.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        target_source_rows = [source_by_url_id[1], source_by_url_id[3]]
        target_ids = [row.id for row in target_source_rows]
        title_by_source_id = {row.id: row.url_title for row in target_source_rows}
        url_id_by_source_id = {row.id: row.url_id for row in target_source_rows}
        source_count_before = _dest_url_row_count(SOURCE_UTUB_ID)
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID, UTUB_URL_IDS_FIELD: target_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == URL_SUCCESS.URLS_COPIED
    assert body[MODEL_STRS.SKIPPED] == []

    copied = body[MODEL_STRS.COPIED]
    assert len(copied) == 2
    assert {entry[MODEL_STRS.SOURCE_UTUB_URL_ID] for entry in copied} == set(target_ids)

    with app.app_context():
        assert _dest_url_row_count(SOURCE_UTUB_ID) == source_count_before
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before + 2
        for entry in copied:
            source_id = entry[MODEL_STRS.SOURCE_UTUB_URL_ID]
            new_dest_row: Utub_Urls = Utub_Urls.query.get(entry[MODEL_STRS.UTUB_URL_ID])
            assert new_dest_row is not None
            assert new_dest_row.utub_id == DEST_UTUB_ID
            assert new_dest_row.user_id == copier_id
            assert new_dest_row.url_id == url_id_by_source_id[source_id]
            assert new_dest_row.url_title == title_by_source_id[source_id]
            assert entry[MODEL_STRS.URL_TITLE] == title_by_source_id[source_id]

    assert is_string_in_logs("Copied bulk URLs into UTub", caplog.records)
    assert is_string_in_logs(f"DestUTub.id={DEST_UTUB_ID}", caplog.records)


def test_route_partial_success_skips_duplicate(
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
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        duplicate_source_id = source_by_url_id[2].id  # URL 2 already in destination
        all_source_ids = [
            source_by_url_id[1].id,
            source_by_url_id[2].id,
            source_by_url_id[3].id,
        ]
        dup_rows_in_dest_before = Utub_Urls.query.filter(
            Utub_Urls.utub_id == DEST_UTUB_ID, Utub_Urls.url_id == 2
        ).count()

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID, UTUB_URL_IDS_FIELD: all_source_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    copied_source_ids = {
        entry[MODEL_STRS.SOURCE_UTUB_URL_ID] for entry in body[MODEL_STRS.COPIED]
    }
    assert copied_source_ids == {source_by_url_id[1].id, source_by_url_id[3].id}

    skipped = body[MODEL_STRS.SKIPPED]
    assert len(skipped) == 1
    assert skipped[0][MODEL_STRS.UTUB_URL_ID] == duplicate_source_id
    assert skipped[0][MODEL_STRS.SKIP_REASON] == BulkCopySkipReason.DUPLICATE.value

    with app.app_context():
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == DEST_UTUB_ID, Utub_Urls.url_id == 2
            ).count()
            == dup_rows_in_dest_before
        )


def test_route_all_skipped_is_noop(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a source and destination UTub that already hold the same URLs
    WHEN every source URL is copied
    THEN `copied` is empty, every source URL is reported skipped, the destination
        gains no rows, its last_updated is NOT bumped, and the response is still 200.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == SOURCE_UTUB_ID).all()
        ]
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)
        last_updated_before = dest_utub.last_updated

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID, UTUB_URL_IDS_FIELD: source_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[MODEL_STRS.COPIED] == []
    assert {entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.SKIPPED]} == set(
        source_ids
    )

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before
        dest_after: Utubs = Utubs.query.get(DEST_UTUB_ID)
        assert dest_after.last_updated == last_updated_before


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
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
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
    GIVEN a member of both UTubs
    WHEN they POST an empty utubUrlIds list
    THEN the schema's min_length rejects the request 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID, UTUB_URL_IDS_FIELD: []},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in body


def test_route_over_max_bulk_copy_ids_rejected(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a member of both UTubs
    WHEN they POST utubUrlIds with MAX_BULK_COPY_URLS + 1 distinct ids
    THEN the schema's max_length rejects the request 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    over_cap_ids = list(range(1, URL_CONSTANTS.MAX_BULK_COPY_URLS + 2))
    assert len(over_cap_ids) == URL_CONSTANTS.MAX_BULK_COPY_URLS + 1

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID, UTUB_URL_IDS_FIELD: over_cap_ids},
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
    GIVEN the source and destination UTub are the same
    WHEN a copy is attempted
    THEN the service rejects 400 with CANNOT_COPY_TO_SAME_UTUB + INVALID_FORM_INPUT
        and writes no rows.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        dest_count_before = _dest_url_row_count(SOURCE_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=SOURCE_UTUB_ID),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            UTUB_URL_IDS_FIELD: [source_row.id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.MESSAGE] == URL_FAILURE.CANNOT_COPY_TO_SAME_UTUB
    assert int(body[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_FORM_INPUT

    with app.app_context():
        assert _dest_url_row_count(SOURCE_UTUB_ID) == dest_count_before


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

    Uses add_one_url_to_each_utub_no_tags (which does NOT add every user to every
    UTub), so the copier is a member of a UTub they created while being a genuine
    non-member of another UTub used as the source.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        dest_utub: Utubs = Utubs.query.filter(Utubs.utub_creator == copier_id).first()
        source_utub: Utubs = Utubs.query.filter(Utubs.utub_creator != copier_id).first()
        # Confirm the copier is genuinely a member of dest but NOT of source.
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
        url_for(ROUTES.URLS.COPY_URLS, utub_id=dest_utub_id),
        json={
            SOURCE_UTUB_ID_FIELD: source_utub_id,
            UTUB_URL_IDS_FIELD: [source_url_id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404

    with app.app_context():
        assert _dest_url_row_count(dest_utub_id) == dest_count_before


def test_route_non_member_of_dest_returns_404(
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN the copier is NOT a member of the destination UTub
    WHEN a copy INTO that destination UTub is attempted
    THEN the @utub_membership_required decorator returns 404 before the service
        runs, and no rows are written.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        copier_id = current_user.id
        own_utub: Utubs = Utubs.query.filter(Utubs.utub_creator == copier_id).first()
        foreign_dest: Utubs = Utubs.query.filter(
            Utubs.utub_creator != copier_id
        ).first()
        assert Utub_Members.query.get((foreign_dest.id, copier_id)) is None
        source_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == own_utub.id
        ).first()
        foreign_dest_id = foreign_dest.id
        own_utub_id = own_utub.id
        source_url_id = source_url.id
        dest_count_before = _dest_url_row_count(foreign_dest_id)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=foreign_dest_id),
        json={SOURCE_UTUB_ID_FIELD: own_utub_id, UTUB_URL_IDS_FIELD: [source_url_id]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404

    with app.app_context():
        assert _dest_url_row_count(foreign_dest_id) == dest_count_before


def test_route_locked_destination_returns_403(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a locked destination UTub (the copier IS a member of the source)
    WHEN a copy into it is attempted
    THEN the write-guard rejects it 403 (UTUB_IS_LOCKED) and writes no rows.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        dest_utub: Utubs = Utubs.query.get(DEST_UTUB_ID)
        dest_utub.is_locked = True
        db.session.commit()
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            UTUB_URL_IDS_FIELD: [source_row.id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(body[STD_JSON.ERROR_CODE]) == URLErrorCodes.UTUB_IS_LOCKED

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before


def test_route_invalid_csrf_returns_403(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a member of both UTubs
    WHEN they POST without a valid CSRF token
    THEN the server returns 403 and no rows are written to the destination.
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        source_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SOURCE_UTUB_ID
        ).first()
        dest_count_before = _dest_url_row_count(DEST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            UTUB_URL_IDS_FIELD: [source_row.id],
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
    GIVEN a source URL that carries tags and a destination that does not hold it
    WHEN the URL is copied
    THEN the new destination Utub_Urls row has zero tag associations — tags are
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
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={
            SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
            UTUB_URL_IDS_FIELD: [source_row_id],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    copied = response.json[MODEL_STRS.COPIED]
    assert len(copied) == 1
    new_dest_url_id = copied[0][MODEL_STRS.UTUB_URL_ID]

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == new_dest_url_id
            ).count()
            == 0
        )


# Atomicity Tests
def test_route_mid_loop_exception_leaves_zero_rows(
    add_mixed_state_source_and_dest_for_copy,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a copy of two net-new source URLs where the duplicate check raises on its
        second call
    WHEN the endpoint processes the batch
    THEN the exception propagates (PROPAGATE_EXCEPTIONS is on in testing), the
        already-flushed first destination row is rolled back (single final commit
        never reached), and the rollback breadcrumb is logged.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        # URLs 1 and 3 are net-new to the destination, so both reach the insert path.
        target_ids = [source_by_url_id[1].id, source_by_url_id[3].id]
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
            client.post(
                url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
                json={
                    SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID,
                    UTUB_URL_IDS_FIELD: target_ids,
                },
                headers={"X-CSRFToken": csrf_token},
            )

    with app.app_context():
        assert _dest_url_row_count(DEST_UTUB_ID) == dest_count_before

    assert is_string_in_logs("Bulk URL copy failed", caplog.records)
    assert is_string_in_logs(f"DestUTub.id={DEST_UTUB_ID}", caplog.records)
    assert is_string_in_logs("error_type=RuntimeError", caplog.records)


# Metrics Tests
def test_route_records_one_urls_copied_to_utub_event(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_state_source_and_dest_for_copy,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a mixed copy (two copied, one duplicate skipped)
    WHEN the batch is copied through the endpoint
    THEN exactly one URLS_COPIED_TO_UTUB counter is written carrying
        url_count_bucket="2-5" (2 copied) and skipped_count_bucket="1" (1 skipped).
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_by_url_id = _source_rows_by_url_id(SOURCE_UTUB_ID)
        all_source_ids = [
            source_by_url_id[1].id,
            source_by_url_id[2].id,
            source_by_url_id[3].id,
        ]

    assert count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB) == 0

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID, UTUB_URL_IDS_FIELD: all_source_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB) == 1

    keys = find_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB)
    dims = parse_dims(keys[0])
    assert dims[URL_COUNT_BUCKET_DIM_KEY] == "2-5"
    assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "1"


def test_route_no_metric_when_all_skipped(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and a copy where every source URL is already in the
        destination
    WHEN the batch is copied through the endpoint
    THEN no URLS_COPIED_TO_UTUB counter is written (nothing was actually copied).
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        source_ids = [
            row.id
            for row in Utub_Urls.query.filter(Utub_Urls.utub_id == SOURCE_UTUB_ID).all()
        ]

    response = client.post(
        url_for(ROUTES.URLS.COPY_URLS, utub_id=DEST_UTUB_ID),
        json={SOURCE_UTUB_ID_FIELD: SOURCE_UTUB_ID, UTUB_URL_IDS_FIELD: source_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.URLS_COPIED_TO_UTUB) == 0


# Route Disambiguation Smoke Test
def test_copy_route_resolves_distinctly_from_add_and_tag_batch(app):
    """
    GIVEN the copy path `/utubs/<utub_id>/urls/copy` shares a prefix with the add
        path `/utubs/<utub_id>/urls` and the multi-URL tag-batch path
        `/utubs/<utub_id>/urls/tags/batch`
    WHEN Flask's URL map matches each POST path
    THEN the static `copy` segment resolves to copy_urls_to_utub, distinctly from
        the create-URL and apply-tags-to-URLs view functions, and it does NOT
        collide with the `/urls/<int:utub_url_id>` GET route.

    Pure URL-map smoke test: needs only the app (no logged-in user or seed data),
    since it exercises route registration/matching, not the handler bodies.
    """
    with app.app_context():
        url_adapter = current_app.url_map.bind("localhost")

        copy_endpoint, _ = url_adapter.match("/utubs/1/urls/copy", method="POST")
        add_endpoint, _ = url_adapter.match("/utubs/1/urls", method="POST")
        tag_batch_endpoint, _ = url_adapter.match(
            "/utubs/1/urls/tags/batch", method="POST"
        )
        get_endpoint, get_args = url_adapter.match("/utubs/1/urls/2", method="GET")

    assert copy_endpoint == ROUTES.URLS.COPY_URLS
    assert add_endpoint == ROUTES.URLS.CREATE_URL
    assert tag_batch_endpoint == ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS
    assert copy_endpoint != add_endpoint
    assert copy_endpoint != tag_batch_endpoint
    assert get_endpoint == ROUTES.URLS.GET_URL
    assert get_args["utub_url_id"] == 2
