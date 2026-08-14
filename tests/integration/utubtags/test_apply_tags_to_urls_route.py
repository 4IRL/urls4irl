from unittest.mock import patch

from flask import current_app, url_for
from flask_login import current_user
import pytest

from backend import db
from backend.metrics.events import EventName
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.tags.constants import BulkTagSkipReason, URLTagErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.constants import TAG_CONSTANTS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as MODEL_STRS
from backend.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.tags

UTUB_URL_IDS_FIELD = "utubUrlIds"
TAG_STRINGS_FIELD = "tagStrings"
URL_COUNT_BUCKET_DIM_KEY = "url_count_bucket"
SKIPPED_COUNT_BUCKET_DIM_KEY = "skipped_count_bucket"
FRESH_TAG_ALPHA = "bulkalpha"
FRESH_TAG_BETA = "bulkbeta"


def _get_creator_utub_and_url_ids() -> tuple[int, list[int]]:
    """Return (utub_id, [utub_url_id, ...]) for a UTub the current user created.

    Must be called within an active app context. The UTub has multiple URLs
    (seeded by add_all_urls_and_users_to_each_utub_no_tags / the mixed-state
    fixture), which the multi-URL endpoint needs to exercise per-URL partial
    success.
    """
    utub_user_is_creator_of: Utubs = Utubs.query.filter(
        Utubs.utub_creator == current_user.id
    ).first()
    url_ids = [
        utub_url.id
        for utub_url in Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_is_creator_of.id
        )
        .order_by(Utub_Urls.id)
        .all()
    ]
    return utub_user_is_creator_of.id, url_ids


def _fill_url_to_tag_limit(utub_id: int, utub_url_id: int) -> None:
    """Seed MAX_URL_TAGS distinct tags onto a URL so it is at the per-URL limit.

    Must be called within an active app context.
    """
    for index in range(TAG_CONSTANTS.MAX_URL_TAGS):
        seed_tag = Utub_Tags(
            utub_id=utub_id,
            tag_string=f"limit_seed_{utub_url_id}_{index}",
            created_by=current_user.id,
        )
        db.session.add(seed_tag)
        db.session.flush()
        db.session.add(
            Utub_Url_Tags(
                utub_id=utub_id,
                utub_url_id=utub_url_id,
                utub_tag_id=seed_tag.id,
            )
        )
    db.session.commit()


# Happy Path Tests :)
def test_apply_two_fresh_tags_to_two_urls_succeeds(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a creator of a UTub with multiple tag-less URLs
    WHEN they POST two fresh tag strings for the first two URLs to the multi-URL
        batch endpoint
    THEN the server returns 200, both URLs appear in `applied` with the correct
        utubUrlTagIDs / appliedTags, `skipped` is empty, two new vocabulary rows
        and four new associations exist, every new association records the acting
        user's id, and the success breadcrumb is logged.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        target_url_ids = url_ids[:2]
        acting_user_id = current_user.id
        initial_vocab_count = Utub_Tags.query.count()
        initial_assoc_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id.in_(target_url_ids),
        ).count()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: target_url_ids,
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAGS_ADDED_TO_URLS
    assert response_json[MODEL_STRS.SKIPPED] == []

    applied = response_json[MODEL_STRS.APPLIED]
    assert len(applied) == 2
    assert {entry[MODEL_STRS.UTUB_URL_ID] for entry in applied} == set(target_url_ids)

    with app.app_context():
        for entry in applied:
            assert len(entry[MODEL_STRS.APPLIED_TAGS]) == 2
            url_after: Utub_Urls = Utub_Urls.query.get(entry[MODEL_STRS.UTUB_URL_ID])
            assert sorted(entry[MODEL_STRS.URL_TAG_IDS]) == sorted(
                url_after.associated_tag_ids
            )

        assert Utub_Tags.query.count() == initial_vocab_count + 2
        new_associations: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id.in_(target_url_ids),
        ).all()
        assert len(new_associations) == initial_assoc_count + 4
        assert all(
            association.user_id == acting_user_id for association in new_associations
        )

    assert is_string_in_logs("Applied bulk multi-URL tags", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_id}", caplog.records)
    assert is_string_in_logs("URLsModified=2", caplog.records)


def test_apply_as_utub_member_succeeds(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a logged-in user who is a MEMBER (not the creator) of a UTub with URLs
    WHEN they POST two fresh tag strings to the multi-URL batch endpoint
    THEN the server returns 200 and both URLs are applied — membership, not
        creatorship, is sufficient (@utub_membership_required).
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id = utub_user_is_member_of.id
        url_ids = [
            utub_url.id
            for utub_url in Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id)
            .order_by(Utub_Urls.id)
            .all()
        ]
        target_url_ids = url_ids[:2]

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: target_url_ids,
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert {
        entry[MODEL_STRS.UTUB_URL_ID] for entry in response.json[MODEL_STRS.APPLIED]
    } == set(target_url_ids)


def test_apply_partial_success_over_limit_url_skipped(
    add_mixed_tag_state_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN URL A (no tags), URL B (1 tag), and URL C (at the per-URL tag limit)
        in a UTub the user created (mixed-state fixture)
    WHEN two fresh tags are applied to all three URLs
    THEN the server returns 200, URLs A and B are in `applied`, URL C is in
        `skipped` with reason OVER_LIMIT, and URL C gains zero new association rows.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        url_a, url_b, url_c = url_ids[0], url_ids[1], url_ids[2]
        assoc_count_c_before = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_url_id == url_c
        ).count()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_a, url_b, url_c],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    applied_ids = {
        entry[MODEL_STRS.UTUB_URL_ID] for entry in response.json[MODEL_STRS.APPLIED]
    }
    assert applied_ids == {url_a, url_b}

    skipped = response.json[MODEL_STRS.SKIPPED]
    assert len(skipped) == 1
    assert skipped[0][MODEL_STRS.UTUB_URL_ID] == url_c
    assert skipped[0][MODEL_STRS.SKIP_REASON] == BulkTagSkipReason.OVER_LIMIT.value

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == url_c).count()
            == assoc_count_c_before
        )


def test_apply_all_urls_over_limit_is_noop_without_multi_url_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN every target URL already at the per-URL tag limit, metrics enabled
    WHEN a fresh tag is applied to all of them
    THEN the server returns 200 with an empty `applied` list, `skipped` lists
        every URL, no new association rows are written, no TAGS_APPLIED_MULTI_URL
        counter fires, and the UTub last_updated timestamp is not bumped.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        for url_id in url_ids:
            _fill_url_to_tag_limit(utub_id, url_id)
        assoc_count_before = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id
        ).count()
        utub_before: Utubs = Utubs.query.get(utub_id)
        last_updated_before = utub_before.last_updated

    assert (
        count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL) == 0
    )

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: url_ids,
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json[MODEL_STRS.APPLIED] == []
    assert {
        entry[MODEL_STRS.UTUB_URL_ID] for entry in response.json[MODEL_STRS.SKIPPED]
    } == set(url_ids)
    assert (
        count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL) == 0
    )

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_id == utub_id).count()
            == assoc_count_before
        )
        utub_after: Utubs = Utubs.query.get(utub_id)
        assert utub_after.last_updated == last_updated_before


def test_apply_already_present_tag_silently_noop_url_still_applied(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a URL that already has one of the requested tags applied
    WHEN the batch (that already-present tag plus a fresh one) is applied to it
    THEN the already-present tag is NOT in that URL's appliedTags (only the fresh
        one is), yet the URL still appears in `applied` and its utubUrlTagIDs is
        the union of the pre-existing and newly-applied tag ids.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        url_a = url_ids[0]
        existing_tag = Utub_Tags(
            utub_id=utub_id, tag_string=FRESH_TAG_ALPHA, created_by=current_user.id
        )
        db.session.add(existing_tag)
        db.session.commit()
        db.session.add(
            Utub_Url_Tags(
                utub_id=utub_id, utub_url_id=url_a, utub_tag_id=existing_tag.id
            )
        )
        db.session.commit()
        existing_tag_id = existing_tag.id

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_a],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    applied = response.json[MODEL_STRS.APPLIED]
    assert len(applied) == 1
    entry = applied[0]
    assert entry[MODEL_STRS.UTUB_URL_ID] == url_a

    applied_tag_ids = {tag[MODEL_STRS.ID] for tag in entry[MODEL_STRS.APPLIED_TAGS]}
    assert existing_tag_id not in applied_tag_ids
    assert len(applied_tag_ids) == 1
    assert existing_tag_id in entry[MODEL_STRS.URL_TAG_IDS]


# Rejection Tests (cross-UTub / unknown ids)
def test_apply_cross_utub_id_rejected_400(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that belongs to a DIFFERENT UTub
    WHEN it is included in the multi-URL apply request
    THEN the whole request is rejected 400 with URL_NOT_IN_UTUB and
        INVALID_FORM_INPUT, and zero rows are written anywhere.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        foreign_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_id
        ).first()
        foreign_url_id = foreign_url.id
        assoc_count_before = Utub_Url_Tags.query.count()
        vocab_count_before = Utub_Tags.query.count()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_ids[0], foreign_url_id],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response.json[STD_JSON.MESSAGE] == TAGS_FAILURE.URL_NOT_IN_UTUB
    assert (
        int(response.json[STD_JSON.ERROR_CODE]) == URLTagErrorCodes.INVALID_FORM_INPUT
    )

    with app.app_context():
        assert Utub_Url_Tags.query.count() == assoc_count_before
        assert Utub_Tags.query.count() == vocab_count_before


def test_apply_nonexistent_id_rejected_400(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that does not exist at all
    WHEN it is included in the multi-URL apply request
    THEN the whole request is rejected 400 with URL_NOT_IN_UTUB and zero rows are
        written.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        nonexistent_id = (
            db.session.query(db.func.max(Utub_Urls.id)).scalar() or 0
        ) + 1000
        assoc_count_before = Utub_Url_Tags.query.count()
        vocab_count_before = Utub_Tags.query.count()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_ids[0], nonexistent_id],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.MESSAGE] == TAGS_FAILURE.URL_NOT_IN_UTUB
    assert (
        int(response.json[STD_JSON.ERROR_CODE]) == URLTagErrorCodes.INVALID_FORM_INPUT
    )

    with app.app_context():
        assert Utub_Url_Tags.query.count() == assoc_count_before
        assert Utub_Tags.query.count() == vocab_count_before


# Validation Tests
def test_apply_empty_utub_url_ids_rejected(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub
    WHEN they POST an empty utubUrlIds list
    THEN the server returns 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, _ = _get_creator_utub_and_url_ids()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        int(response.json[STD_JSON.ERROR_CODE]) == URLTagErrorCodes.INVALID_FORM_INPUT
    )
    assert STD_JSON.ERRORS in response.json


def test_apply_empty_tag_strings_rejected(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN they POST an empty tagStrings list
    THEN the server returns 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_ids[0]],
            TAG_STRINGS_FIELD: [],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in response.json


def test_apply_whitespace_only_tag_rejected(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN they POST a tagStrings list with a whitespace-only element
    THEN the server returns 400.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_ids[0]],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, "   "],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_apply_over_length_tag_rejected(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN they POST a tagStrings list with an element exceeding MAX_TAG_LENGTH
    THEN the server returns 400.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()

    over_length = "a" * (TAG_CONSTANTS.MAX_TAG_LENGTH + 1)
    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_ids[0]],
            TAG_STRINGS_FIELD: [over_length],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_apply_duplicate_ids_deduped_applied_once(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with a tag-less URL
    WHEN the same utubUrlId is submitted twice in utubUrlIds
    THEN the id is deduped: the URL appears once in `applied` and gains exactly
        one association per requested tag (no duplicate rows).
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        url_a = url_ids[0]

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_a, url_a],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    applied = response.json[MODEL_STRS.APPLIED]
    assert len(applied) == 1
    assert applied[0][MODEL_STRS.UTUB_URL_ID] == url_a

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == url_a).count() == 1
        )


def test_apply_negative_or_zero_url_id_rejected(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN a non-positive (zero AND negative) utubUrlId is submitted in utubUrlIds
    THEN the utub_url_ids_valid field validator rejects it 400 with the
        INVALID_URL_ID message, and zero rows are written.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        assoc_count_before = Utub_Url_Tags.query.count()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_ids[0], 0, -1],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert STD_JSON.ERRORS in response.json
    assert TAGS_FAILURE.INVALID_URL_ID in str(response.json[STD_JSON.ERRORS])

    with app.app_context():
        assert Utub_Url_Tags.query.count() == assoc_count_before


# Auth / Lock Tests
def test_apply_non_member_returns_404(
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a logged-in user who is NOT a member of a UTub
    WHEN they POST a multi-URL batch to that UTub
    THEN the membership decorator returns 404 (note: the master brief said 403;
        @utub_membership_required returns 404).

    Uses add_one_url_to_each_utub_no_tags (which does NOT add every user to every
    UTub), so a UTub created by a different user has the first user as a
    non-member — unlike add_all_urls_and_users_to_each_utub_no_tags where the
    first user is a member of every UTub.
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
        assoc_count_before = Utub_Url_Tags.query.count()
        vocab_count_before = Utub_Tags.query.count()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=other_utub_id),
        json={
            UTUB_URL_IDS_FIELD: [other_url_id],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404

    with app.app_context():
        assert Utub_Url_Tags.query.count() == assoc_count_before
        assert Utub_Tags.query.count() == vocab_count_before


def test_apply_to_locked_utub_returns_403(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with URLs, where the UTub is LOCKED
    WHEN they POST a multi-URL batch of fresh tags
    THEN the write-guard rejects it 403 (UTUB_IS_LOCKED) and zero rows are written.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        utub_to_lock: Utubs = Utubs.query.get(utub_id)
        utub_to_lock.is_locked = True
        db.session.commit()
        assoc_count_before = Utub_Url_Tags.query.count()
        vocab_count_before = Utub_Tags.query.count()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: url_ids[:2],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response.json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert int(response.json[STD_JSON.ERROR_CODE]) == URLTagErrorCodes.UTUB_IS_LOCKED

    with app.app_context():
        assert Utub_Url_Tags.query.count() == assoc_count_before
        assert Utub_Tags.query.count() == vocab_count_before


def test_apply_invalid_csrf_returns_403(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN they POST without a valid CSRF token
    THEN the server returns 403 and no rows are written.
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        assoc_count_before = Utub_Url_Tags.query.count()
        vocab_count_before = Utub_Tags.query.count()

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_ids[0]],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
    )

    assert response.status_code == 403

    with app.app_context():
        assert Utub_Url_Tags.query.count() == assoc_count_before
        assert Utub_Tags.query.count() == vocab_count_before


# Metrics Tests
def test_apply_records_tag_applied_per_association_and_one_multi_url_event(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and three tag-less URLs, the third at the tag limit
    WHEN one fresh tag is applied to all three (two succeed, one over-limit skip)
    THEN TAG_APPLIED is incremented once per applied (url, tag) association (2),
        exactly one TAGS_APPLIED_MULTI_URL counter fires, and it carries
        url_count_bucket="2-5" and skipped_count_bucket="1".
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        url_a, url_b, url_c = url_ids[0], url_ids[1], url_ids[2]
        _fill_url_to_tag_limit(utub_id, url_c)

    assert sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == 0
    assert (
        count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL) == 0
    )

    response = client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
        json={
            UTUB_URL_IDS_FIELD: [url_a, url_b, url_c],
            TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA],
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == 2
    assert (
        count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL) == 1
    )

    multi_url_keys = find_counter_keys(
        provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL
    )
    dims = parse_dims(multi_url_keys[0])
    assert dims[URL_COUNT_BUCKET_DIM_KEY] == "2-5"
    assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "1"


# Atomicity Tests
def test_apply_mid_loop_exception_leaves_zero_rows(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a creator of a UTub with multiple tag-less URLs
    WHEN _add_url_tag raises on the first tag of the SECOND URL (its 3rd call
        overall — after the first URL's two tags are fully staged)
    THEN the exception propagates, every flushed vocabulary and association write
        across ALL URLs — including the fully-staged first URL — is rolled back
        (the single final commit is never reached), and the rollback breadcrumb is
        logged with the UTub id, URL count, and the propagated exception type.

    Raising on the second URL's first association (not the first URL's second) is
    what actually proves the cross-URL "all-or-nothing" property: the first URL is
    fully processed and staged before the abort, so the zero-rows assertions below
    would fail under any hypothetical per-URL-commit implementation.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        target_url_ids = url_ids[:2]
        initial_vocab_count = Utub_Tags.query.count()
        initial_assoc_count = Utub_Url_Tags.query.count()

    call_count = {"value": 0}

    def failing_add_url_tag(utub_url: Utub_Urls, utub_tag: Utub_Tags) -> Utub_Url_Tags:
        # Two fresh tags per URL → calls 1-2 land on the first URL, call 3 is the
        # first tag of the second URL. Raising there leaves the first URL fully
        # staged, so the rollback must discard an earlier URL's writes too.
        call_count["value"] += 1
        if call_count["value"] == 3:
            raise RuntimeError("simulated mid-loop failure")
        new_association = Utub_Url_Tags(
            utub_id=utub_url.utub_id,
            utub_url_id=utub_url.id,
            utub_tag_id=utub_tag.id,
        )
        db.session.add(new_association)
        return new_association

    # PROPAGATE_EXCEPTIONS is enabled in the testing config, so the simulated
    # failure propagates out of the WSGI test client. The point under test is the
    # post-rollback DB state: the single final commit is never reached, so every
    # flushed vocabulary row and association write across all URLs is rolled back.
    with patch(
        "backend.tags.services.create_url_tag._add_url_tag",
        side_effect=failing_add_url_tag,
    ):
        with pytest.raises(RuntimeError, match="simulated mid-loop failure"):
            client.post(
                url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=utub_id),
                json={
                    UTUB_URL_IDS_FIELD: target_url_ids,
                    TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA],
                },
                headers={"X-CSRFToken": csrf_token},
            )

    with app.app_context():
        assert Utub_Tags.query.count() == initial_vocab_count
        assert Utub_Url_Tags.query.count() == initial_assoc_count

    assert is_string_in_logs("Bulk multi-URL tag-apply failed", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_id}", caplog.records)
    assert is_string_in_logs(f"URLCount={len(target_url_ids)}", caplog.records)
    assert is_string_in_logs("error_type=RuntimeError", caplog.records)


# Route Disambiguation Smoke Test
def test_multi_url_and_per_url_batch_routes_resolve_distinctly(app):
    """
    GIVEN the multi-URL batch path shares a prefix with the per-URL batch path
    WHEN Flask's URL map matches each POST path
    THEN /utubs/<utub_id>/urls/tags/batch resolves to the multi-URL view function
        and /utubs/<utub_id>/urls/<utub_url_id>/tags/batch resolves to the
        per-URL view function — the int-converter disambiguates the shared prefix.

    Pure URL-map smoke test: needs only the app (no logged-in user or seed data),
    since it exercises route registration/matching, not the handler bodies.
    """
    with app.app_context():
        # The utub_url_tags blueprint is registered with no url_prefix, so the
        # route-decorator paths are the live paths matched here.
        url_adapter = current_app.url_map.bind("localhost")

        multi_url_endpoint, _ = url_adapter.match(
            "/utubs/1/urls/tags/batch", method="POST"
        )
        per_url_endpoint, per_url_args = url_adapter.match(
            "/utubs/1/urls/2/tags/batch", method="POST"
        )

    assert multi_url_endpoint == ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS
    assert per_url_endpoint == ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS
    assert multi_url_endpoint != per_url_endpoint
    assert per_url_args["utub_url_id"] == 2
