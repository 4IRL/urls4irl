from flask import current_app, url_for
from flask_login import current_user
import pytest
from werkzeug.exceptions import MethodNotAllowed

from backend import db
from backend.metrics.events import EventName
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.urls.constants import BulkDeleteSkipReason, URLErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.constants import URL_CONSTANTS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as MODEL_STRS, TAG_COUNTS_MODIFIED
from backend.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE
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
UTUB_URL_IDS_FIELD = "utubUrlIds"
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


def _tag_counts_from_body(body: dict) -> dict[int, int]:
    """Normalize the JSON tag-count map's string keys back to int ids."""
    return {int(tag_id): count for tag_id, count in body[TAG_COUNTS_MODIFIED].items()}


# Happy Path Tests :)
def test_route_creator_bulk_deletes_own_urls_happy_path(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN the literal creator (user 1) of a UTub holding three URLs
    WHEN two of those URLs are bulk-deleted via the endpoint
    THEN the server returns 200 with the full report shape (deleted/skipped/
        tagCountsInUtub/totalDeleted/totalSkipped), both rows are removed, nothing is
        skipped, and the success breadcrumb is logged.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id, rows_by_url_id[2].id]
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: target_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == URL_SUCCESS.URLS_DELETED
    assert body[MODEL_STRS.TOTAL_DELETED] == 2
    assert body[MODEL_STRS.TOTAL_SKIPPED] == 0
    assert body[MODEL_STRS.SKIPPED] == []
    assert {entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.DELETED]} == set(
        target_ids
    )
    assert TAG_COUNTS_MODIFIED in body

    with app.app_context():
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before - 2
        for deleted_id in target_ids:
            assert Utub_Urls.query.get(deleted_id) is None

    assert is_string_in_logs(
        "Bulk-deleted UTubURLs and associated UTubURLTags", caplog.records
    )
    assert is_string_in_logs(f"UTub.id={FIRST_UTUB_ID}", caplog.records)
    assert is_string_in_logs("URLsDeleted=2", caplog.records)


def test_route_partial_permission_skip_body_shape(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register,
):
    """
    GIVEN a plain member (user 2) who added only URL 2 in a UTub they do not own
    WHEN they bulk-delete all three URLs (theirs + two added by others)
    THEN only their own URL is deleted; the other two come back FORBIDDEN-skipped with
        the correct DELETED/SKIPPED/SKIP_REASON/TOTAL_DELETED/TOTAL_SKIPPED shape and a
        tagCountsInUtub map, and only one row is removed.
    """
    client, csrf_token, _, app = login_second_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        own_id = rows_by_url_id[2].id
        creators_id = rows_by_url_id[1].id
        third_members_id = rows_by_url_id[3].id
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: [creators_id, own_id, third_members_id]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[MODEL_STRS.TOTAL_DELETED] == 1
    assert body[MODEL_STRS.TOTAL_SKIPPED] == 2
    assert [entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.DELETED]] == [
        own_id
    ]

    skipped_by_id = {
        entry[MODEL_STRS.UTUB_URL_ID]: entry[MODEL_STRS.SKIP_REASON]
        for entry in body[MODEL_STRS.SKIPPED]
    }
    assert skipped_by_id == {
        creators_id: BulkDeleteSkipReason.FORBIDDEN.value,
        third_members_id: BulkDeleteSkipReason.FORBIDDEN.value,
    }
    assert TAG_COUNTS_MODIFIED in body

    with app.app_context():
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before - 1
        assert Utub_Urls.query.get(own_id) is None
        assert Utub_Urls.query.get(creators_id) is not None
        assert Utub_Urls.query.get(third_members_id) is not None


def test_route_tag_cascade_and_tag_counts_modified(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a UTub where a `shared` tag is on URLs 1, 2, 3 and a `solo` tag is on URL 1
    WHEN the creator bulk-deletes URLs 1 and 2
    THEN each deleted URL's Utub_Url_Tags rows are removed, the shared tag's returned
        count is the aggregate remaining (1, still on URL 3), and the solo tag whose
        last URL was deleted is present in tagCountsInUtub with count 0 (not omitted).
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        url_one = rows_by_url_id[1]
        url_two = rows_by_url_id[2]
        target_ids = [url_one.id, url_two.id]
        # Tag ids: shared is the first UTub-1 tag, solo the second.
        shared_tag_id = sorted(url_two.associated_tag_ids)[0]
        solo_tag_id = next(
            tag_id for tag_id in url_one.associated_tag_ids if tag_id != shared_tag_id
        )

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: target_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    tag_counts = _tag_counts_from_body(response.json)
    assert tag_counts[shared_tag_id] == 1
    assert solo_tag_id in tag_counts
    assert tag_counts[solo_tag_id] == 0

    with app.app_context():
        for deleted_id in target_ids:
            assert (
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_url_id == deleted_id
                ).count()
                == 0
            )


def test_route_success_bumps_last_updated(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN the creator of a UTub with deletable URLs
    WHEN at least one URL is bulk-deleted
    THEN the UTub's last_updated timestamp is bumped.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id]
        first_utub: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        last_updated_before = first_utub.last_updated

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: target_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    with app.app_context():
        first_utub_after: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        assert (first_utub_after.last_updated - last_updated_before).total_seconds() > 0


def test_route_all_skipped_is_noop_no_last_updated_bump(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register,
):
    """
    GIVEN a plain member (user 2) targeting ONLY URLs added by others
    WHEN they bulk-delete those two URLs
    THEN nothing is deleted, both are FORBIDDEN-skipped, last_updated is not bumped, and
        the response is still 200.
    """
    client, csrf_token, _, app = login_second_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id, rows_by_url_id[3].id]
        first_utub: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        count_before = _utub_url_row_count(FIRST_UTUB_ID)
        last_updated_before = first_utub.last_updated

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: target_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[MODEL_STRS.TOTAL_DELETED] == 0
    assert body[MODEL_STRS.TOTAL_SKIPPED] == 2
    assert body[MODEL_STRS.DELETED] == []
    assert body[TAG_COUNTS_MODIFIED] == {}

    with app.app_context():
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before
        first_utub_after: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        assert first_utub_after.last_updated == last_updated_before


# Rejection Tests (cross-UTub / validation)
def test_route_cross_utub_id_rejected_400(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that belongs to a UTub OTHER than the target
    WHEN it is included in a bulk-delete request against the target UTub
    THEN the whole request is rejected 400 with URLS_NOT_IN_UTUB + INVALID_FORM_INPUT
        and ZERO rows are deleted.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        foreign_row: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == SECOND_UTUB_ID
        ).first()
        assert foreign_row is not None
        foreign_row_id = foreign_row.id
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: [foreign_row_id]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == URL_FAILURE.URLS_NOT_IN_UTUB
    assert int(body[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_FORM_INPUT

    with app.app_context():
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before
        assert Utub_Urls.query.get(foreign_row_id) is not None


def test_route_unknown_id_rejected_400(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that does not exist at all (the sibling all-or-nothing branch
        to the cross-UTub case)
    WHEN it is included in a bulk-delete request alongside a valid id
    THEN the whole request is rejected 400 with URLS_NOT_IN_UTUB and ZERO rows are
        deleted.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        valid_id = rows_by_url_id[1].id
        unknown_id = (db.session.query(db.func.max(Utub_Urls.id)).scalar() or 0) + 1000
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: [valid_id, unknown_id]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == URL_FAILURE.URLS_NOT_IN_UTUB
    assert int(body[STD_JSON.ERROR_CODE]) == URLErrorCodes.INVALID_FORM_INPUT

    with app.app_context():
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before
        assert Utub_Urls.query.get(valid_id) is not None


def test_route_empty_utub_url_ids_rejected(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN the creator of a UTub
    WHEN they POST an empty utubUrlIds list
    THEN the schema's min_length rejects the request 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: []},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in body


def test_route_over_max_bulk_delete_urls_rejected(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN the creator of a UTub
    WHEN they POST utubUrlIds with MAX_BULK_DELETE_URLS + 1 distinct ids
    THEN the schema's max_length rejects the request 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    over_cap_ids = list(range(1, URL_CONSTANTS.MAX_BULK_DELETE_URLS + 2))
    assert len(over_cap_ids) == URL_CONSTANTS.MAX_BULK_DELETE_URLS + 1

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: over_cap_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in body


# Auth / Lock Tests
def test_route_non_member_returns_404(
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a logged-in user who is NOT a member of a UTub
    WHEN they POST a bulk-delete to that UTub
    THEN @utub_membership_required returns 404 and no rows are deleted.

    Uses add_one_url_to_each_utub_no_tags (which does NOT add every user to every
    UTub), so a UTub created by a different user has the first user as a non-member.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        other_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        other_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == other_utub.id
        ).first()
        other_utub_id = other_utub.id
        other_url_id = other_url.id
        count_before = _utub_url_row_count(other_utub_id)

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=other_utub_id),
        json={UTUB_URL_IDS_FIELD: [other_url_id]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404

    with app.app_context():
        assert _utub_url_row_count(other_utub_id) == count_before


def test_route_locked_utub_returns_403(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN the creator of a UTub with URLs, where the UTub is LOCKED
    WHEN they POST a bulk-delete
    THEN the write-guard rejects it 403 (UTUB_IS_LOCKED) and no rows are deleted.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        first_utub: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        first_utub.is_locked = True
        db.session.commit()
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id]
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: target_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert int(body[STD_JSON.ERROR_CODE]) == URLErrorCodes.UTUB_IS_LOCKED

    with app.app_context():
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before


def test_route_invalid_csrf_returns_403(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN the creator of a UTub with URLs
    WHEN they POST without a valid CSRF token
    THEN the server returns 403 and no rows are deleted.
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id]
        count_before = _utub_url_row_count(FIRST_UTUB_ID)

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: target_ids},
    )

    assert response.status_code == 403

    with app.app_context():
        assert _utub_url_row_count(FIRST_UTUB_ID) == count_before


# Metrics Tests
def test_route_records_one_urls_deleted_from_utub_event(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register,
):
    """
    GIVEN metrics enabled and a member bulk-delete that deletes one URL and skips two
    WHEN the batch is deleted through the endpoint
    THEN exactly one URLS_DELETED_FROM_UTUB counter is written carrying
        url_count_bucket="1" (1 deleted) and skipped_count_bucket="2-5" (2 skipped).
    """
    client, csrf_token, _, app = login_second_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [
            rows_by_url_id[1].id,
            rows_by_url_id[2].id,
            rows_by_url_id[3].id,
        ]

    assert (
        count_counter_keys(provide_metrics_redis, EventName.URLS_DELETED_FROM_UTUB) == 0
    )

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: target_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URLS_DELETED_FROM_UTUB) == 1
    )

    keys = find_counter_keys(provide_metrics_redis, EventName.URLS_DELETED_FROM_UTUB)
    dims = parse_dims(keys[0])
    assert dims[URL_COUNT_BUCKET_DIM_KEY] == "1"
    assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "2-5"


def test_route_no_metric_when_all_skipped(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register,
):
    """
    GIVEN metrics enabled and a bulk-delete where every targeted URL is FORBIDDEN
    WHEN the batch is deleted through the endpoint
    THEN no URLS_DELETED_FROM_UTUB counter is written (nothing was actually deleted).
    """
    client, csrf_token, _, app = login_second_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        target_ids = [rows_by_url_id[1].id, rows_by_url_id[3].id]

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: target_ids},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URLS_DELETED_FROM_UTUB) == 0
    )


# Co-creator distinguishing route case
def test_route_co_creator_skips_third_members_url(
    add_co_creator_and_mixed_delete_permission_urls,
    login_second_user_without_register,
):
    """
    GIVEN a co-creator (user 2, NOT the literal utub.utub_creator) of a UTub holding a
        URL added by a THIRD member
    WHEN the co-creator bulk-deletes their own URL plus the third member's URL via the
        endpoint
    THEN their own URL is deleted but the third member's URL is FORBIDDEN-skipped (not
        deleted) — a case that would incorrectly succeed under the broader
        g.is_creator-inclusive predicate.
    """
    client, csrf_token, _, app = login_second_user_without_register

    with app.app_context():
        rows_by_url_id = _utub_url_rows_by_url_id(FIRST_UTUB_ID)
        co_creators_own_id = rows_by_url_id[2].id
        third_members_id = rows_by_url_id[3].id

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=FIRST_UTUB_ID),
        json={UTUB_URL_IDS_FIELD: [co_creators_own_id, third_members_id]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[MODEL_STRS.TOTAL_DELETED] == 1
    assert body[MODEL_STRS.TOTAL_SKIPPED] == 1
    assert [entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.DELETED]] == [
        co_creators_own_id
    ]

    skipped = body[MODEL_STRS.SKIPPED]
    assert len(skipped) == 1
    assert skipped[0][MODEL_STRS.UTUB_URL_ID] == third_members_id
    assert skipped[0][MODEL_STRS.SKIP_REASON] == BulkDeleteSkipReason.FORBIDDEN.value

    with app.app_context():
        assert Utub_Urls.query.get(co_creators_own_id) is None
        assert Utub_Urls.query.get(third_members_id) is not None


# Route Disambiguation Smoke Test
def test_bulk_delete_route_resolves_distinctly(app):
    """
    GIVEN the new UTub-scoped bulk-delete path /utubs/<utub_id>/urls/delete
    WHEN Flask's URL map matches the POST path
    THEN it resolves to delete_urls_from_utub, distinctly from the single-URL DELETE
        route and the create-URL POST route, and a bogus per-url-id variant of the
        path does not shadow it.

    Pure URL-map smoke test: needs only the app (no logged-in user or seed data).
    """
    with app.app_context():
        url_adapter = current_app.url_map.bind("localhost")

        bulk_delete_endpoint, bulk_delete_args = url_adapter.match(
            "/utubs/1/urls/delete", method="POST"
        )
        create_endpoint, _ = url_adapter.match("/utubs/1/urls", method="POST")
        single_delete_endpoint, _ = url_adapter.match(
            "/utubs/1/urls/2", method="DELETE"
        )

        # The bulk path only accepts POST — matching it with DELETE is a
        # method mismatch (405), never a fall-through to the single-URL DELETE
        # route (`delete` is not an int, so it cannot shadow that path).
        with pytest.raises(MethodNotAllowed):
            url_adapter.match("/utubs/1/urls/delete", method="DELETE")

    assert bulk_delete_endpoint == ROUTES.URLS.DELETE_URLS_BULK
    assert bulk_delete_args["utub_id"] == 1
    assert bulk_delete_endpoint == "urls.delete_urls_from_utub"
    assert bulk_delete_endpoint != create_endpoint
    assert bulk_delete_endpoint != single_delete_endpoint
    assert single_delete_endpoint == ROUTES.URLS.DELETE_URL
