from unittest.mock import patch

import pytest
from flask import url_for
from flask_login import current_user

from backend import db
from backend.metrics.events import EventName
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.tags.constants import URLTagErrorCodes
from backend.tags.services.create_url_tag import add_batch_tags_to_existing_url
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

TAG_STRINGS_FIELD = "tagStrings"
BATCH_SIZE_BUCKET_DIM_KEY = "batch_size_bucket"
FRESH_TAG_ALPHA = "batchalpha"
FRESH_TAG_BETA = "batchbeta"
FRESH_TAG_GAMMA = "batchgamma"


def _get_creator_utub_and_url() -> tuple[int, int]:
    """Return (utub_id, utub_url_id) for a UTub the current user created.

    Must be called within an active app context; queries use the ambient
    Flask-SQLAlchemy session.
    """
    utub_user_is_creator_of: Utubs = Utubs.query.filter(
        Utubs.utub_creator == current_user.id
    ).first()
    url_in_utub: Utub_Urls = Utub_Urls.query.filter(
        Utub_Urls.utub_id == utub_user_is_creator_of.id,
        Utub_Urls.user_id == current_user.id,
    ).first()
    return utub_user_is_creator_of.id, url_in_utub.id


# Happy Path Tests :)
def test_batch_add_two_fresh_tags_succeeds(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register, caplog
):
    """
    GIVEN a creator of a UTub with a URL that has no tags
    WHEN they POST two fresh tag strings to the batch endpoint
    THEN the server returns 200, the response reflects both newly-applied tags,
        two new Utub_Tags vocabulary rows are created, two new Utub_Url_Tags
        associations exist, and the success breadcrumb is logged with the
        UTub/URL/applied-count context.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()
        initial_vocab_count = Utub_Tags.query.count()
        initial_assoc_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).count()

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAGS_ADDED_TO_URL
    assert len(response_json[MODEL_STRS.APPLIED_TAGS]) == 2

    with app.app_context():
        url_after: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        assert sorted(response_json[MODEL_STRS.URL_TAG_IDS]) == sorted(
            url_after.associated_tag_ids
        )
        assert Utub_Tags.query.count() == initial_vocab_count + 2
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
            ).count()
            == initial_assoc_count + 2
        )

    assert is_string_in_logs("Applied batch of UTubURLTags", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_id}", caplog.records)
    assert is_string_in_logs(f"UTubURL.id={utub_url_id}", caplog.records)
    assert is_string_in_logs("AppliedCount=2", caplog.records)


def test_create_and_add_tag_to_url_in_locked_utub_is_rejected(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub with a URL that has no tags, where the UTub is LOCKED
    WHEN they POST a fresh (not-yet-existing) tag string to the batch endpoint, which would
        otherwise create the vocabulary row and apply it to the URL
        - By POST to "/utubs/<int:utub_id>/urls/<int:utub_url_id>/tags/batch"
    THEN the write-guard (add_batch_tags_to_existing_url) rejects the add: the server responds
        403 with the locked-UTub JSON error (error code URLTagErrorCodes.UTUB_IS_LOCKED, message
        UTUB_FAILURE.UTUB_IS_LOCKED), and neither a new Utub_Tags vocabulary row nor a new
        Utub_Url_Tags association is created.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()

        # Lock the UTub
        utub_to_lock: Utubs = Utubs.query.get(utub_id)
        utub_to_lock.is_locked = True
        db.session.commit()

        # Assert-before-state: no vocabulary rows and no associations exist yet
        initial_vocab_count = Utub_Tags.query.count()
        assert (
            Utub_Tags.query.filter(Utub_Tags.tag_string == FRESH_TAG_ALPHA).count() == 0
        )
        initial_assoc_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).count()
        assert initial_assoc_count == 0
        initial_total_assoc_count = Utub_Url_Tags.query.count()

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert int(response_json[STD_JSON.ERROR_CODE]) == URLTagErrorCodes.UTUB_IS_LOCKED

    with app.app_context():
        # No new vocabulary row created, and no new association created
        assert Utub_Tags.query.count() == initial_vocab_count
        assert (
            Utub_Tags.query.filter(Utub_Tags.tag_string == FRESH_TAG_ALPHA).count() == 0
        )
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
            ).count()
            == initial_assoc_count
        )
        assert Utub_Url_Tags.query.count() == initial_total_assoc_count


def test_batch_add_mix_new_and_existing_vocab_only_creates_new(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub with a URL, and an existing vocabulary tag in the UTub
    WHEN they POST one new tag string and the already-existing vocabulary string
    THEN both are applied to the URL but only the new vocabulary row is created.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()
        existing_vocab_tag = Utub_Tags(
            utub_id=utub_id, tag_string=FRESH_TAG_ALPHA, created_by=current_user.id
        )
        db.session.add(existing_vocab_tag)
        db.session.commit()
        initial_vocab_count = Utub_Tags.query.count()

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert len(response.json[MODEL_STRS.APPLIED_TAGS]) == 2

    with app.app_context():
        assert Utub_Tags.query.count() == initial_vocab_count + 1


def test_batch_add_idempotent_skips_already_applied_tag(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub with a URL that already has one tag applied
    WHEN they POST that same tag string plus a fresh one
    THEN only the fresh tag is applied; the already-present tag is skipped and
        its association count is unchanged.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()
        existing_tag = Utub_Tags(
            utub_id=utub_id, tag_string=FRESH_TAG_ALPHA, created_by=current_user.id
        )
        db.session.add(existing_tag)
        db.session.commit()
        already_applied = Utub_Url_Tags(
            utub_id=utub_id, utub_url_id=utub_url_id, utub_tag_id=existing_tag.id
        )
        db.session.add(already_applied)
        db.session.commit()
        existing_tag_id = existing_tag.id
        initial_assoc_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == utub_url_id,
            Utub_Url_Tags.utub_tag_id == existing_tag_id,
        ).count()

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    applied_tag_strings = {
        tag[MODEL_STRS.TAG_STRING] for tag in response.json[MODEL_STRS.APPLIED_TAGS]
    }
    assert FRESH_TAG_ALPHA not in applied_tag_strings
    assert FRESH_TAG_BETA in applied_tag_strings

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
                Utub_Url_Tags.utub_tag_id == existing_tag_id,
            ).count()
            == initial_assoc_count
        )


def test_batch_add_dedupes_within_payload(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub with a URL (service called directly)
    WHEN the service receives ["x", "x"] (exact-string duplicates)
    THEN the tag is applied only once.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()
        utub: Utubs = Utubs.query.get(utub_id)
        utub_url: Utub_Urls = Utub_Urls.query.get(utub_url_id)

        add_batch_tags_to_existing_url(
            tag_strings=[FRESH_TAG_ALPHA, FRESH_TAG_ALPHA],
            utub=utub,
            utub_url=utub_url,
        )

        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
            ).count()
            == 1
        )


def test_batch_add_at_limit_rejects_whole_batch_zero_rows(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a URL already at MAX_URL_TAGS - 1 tags
    WHEN three new tags are submitted (which would exceed the limit)
    THEN the whole batch is rejected with 400 and zero vocabulary AND zero
        association rows are written (two-pass atomicity).
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()
        for index in range(TAG_CONSTANTS.MAX_URL_TAGS - 1):
            seed_tag = Utub_Tags(
                utub_id=utub_id,
                tag_string=f"seedtag{index}",
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
        initial_vocab_count = Utub_Tags.query.count()
        initial_assoc_count = Utub_Url_Tags.query.count()

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA, FRESH_TAG_GAMMA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response.json[STD_JSON.MESSAGE] == TAGS_FAILURE.MAX_URL_TAGS_REACHED.format(
        max_tags=TAG_CONSTANTS.MAX_URL_TAGS
    )

    with app.app_context():
        assert Utub_Tags.query.count() == initial_vocab_count
        assert Utub_Url_Tags.query.count() == initial_assoc_count


def test_batch_add_all_already_applied_is_noop_without_batch_emit(
    metrics_enabled_app,
    provide_metrics_redis,
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a URL that already has a tag applied, and metrics enabled
    WHEN the payload contains only that already-applied tag string
    THEN the server returns 200 with an empty appliedTags list, the association
        count is unchanged, and NO TAGS_APPLIED_BATCH counter is written.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()
        existing_tag = Utub_Tags(
            utub_id=utub_id, tag_string=FRESH_TAG_ALPHA, created_by=current_user.id
        )
        db.session.add(existing_tag)
        db.session.commit()
        db.session.add(
            Utub_Url_Tags(
                utub_id=utub_id, utub_url_id=utub_url_id, utub_tag_id=existing_tag.id
            )
        )
        db.session.commit()
        initial_assoc_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).count()

    assert count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_BATCH) == 0

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json[MODEL_STRS.APPLIED_TAGS] == []
    assert count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_BATCH) == 0

    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
            ).count()
            == initial_assoc_count
        )


# Validation Tests
def test_batch_add_empty_list_rejected(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN they POST an empty tagStrings list
    THEN the server returns 400 with an errors payload.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: []},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        int(response.json[STD_JSON.ERROR_CODE]) == URLTagErrorCodes.INVALID_FORM_INPUT
    )
    assert STD_JSON.ERRORS in response.json


def test_batch_add_whitespace_only_element_rejected(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN they POST a tagStrings list with a whitespace-only element
    THEN the server returns 400.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, "   "]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_batch_add_over_length_element_rejected(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN they POST a tagStrings list with an element exceeding MAX_TAG_LENGTH
    THEN the server returns 400.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()

    over_length = "a" * (TAG_CONSTANTS.MAX_TAG_LENGTH + 1)
    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [over_length]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE


# Auth Tests
def test_batch_add_non_member_returns_404(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is NOT a member of a UTub
    WHEN they POST a batch to a URL in that UTub
    THEN the membership decorator returns 404.
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

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS,
            utub_id=other_utub_id,
            utub_url_id=other_url_id,
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 404


def test_batch_add_as_utub_member_succeeds(
    add_all_urls_and_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is a MEMBER (not the creator) of a UTub that has a URL
    WHEN they POST two fresh tag strings to the batch endpoint for that URL
    THEN the server returns 200, the response reflects both newly-applied tags,
        and two new Utub_Url_Tags associations exist where none did before.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id = utub_user_is_member_of.id
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).first()
        utub_url_id = url_in_utub.id
        initial_assoc_count = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id, Utub_Url_Tags.utub_url_id == utub_url_id
        ).count()
        assert initial_assoc_count == 0

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAGS_ADDED_TO_URL
    assert len(response_json[MODEL_STRS.APPLIED_TAGS]) == 2

    with app.app_context():
        url_after: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        assert sorted(response_json[MODEL_STRS.URL_TAG_IDS]) == sorted(
            url_after.associated_tag_ids
        )
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id,
                Utub_Url_Tags.utub_url_id == utub_url_id,
            ).count()
            == initial_assoc_count + 2
        )


def test_batch_add_invalid_csrf_returns_403(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN they POST without a valid CSRF token
    THEN the server returns 403.
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA]},
    )

    assert response.status_code == 403


# Metrics Tests
def test_batch_add_records_tag_applied_per_tag_and_one_batch_event(
    metrics_enabled_app,
    provide_metrics_redis,
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with a URL (no tags) and metrics enabled
    WHEN they POST two fresh tags to the batch endpoint
    THEN TAG_APPLIED is incremented by 2 (the two emits share dimensions and
        collapse into one INCR'd counter key with value 2), TAGS_APPLIED_BATCH
        fires once, and the batch counter carries batch_size_bucket="2-5".
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()

    assert sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == 0
    assert count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_BATCH) == 0

    response = client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS, utub_id=utub_id, utub_url_id=utub_url_id
        ),
        json={TAG_STRINGS_FIELD: [FRESH_TAG_ALPHA, FRESH_TAG_BETA]},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == 2
    assert count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_BATCH) == 1

    batch_keys = find_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_BATCH)
    assert parse_dims(batch_keys[0])[BATCH_SIZE_BUCKET_DIM_KEY] == "2-5"


# Atomicity Tests
def test_batch_add_mid_batch_exception_leaves_zero_rows(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register, caplog
):
    """
    GIVEN a creator of a UTub with a URL
    WHEN _add_url_tag raises on its 2nd call mid-batch
    THEN zero new vocabulary rows AND zero new association rows remain (single
        final commit guarantees all-or-nothing atomicity), and the rollback
        breadcrumb is logged with the UTub/URL/requested-count and the
        propagated exception type.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, utub_url_id = _get_creator_utub_and_url()
        initial_vocab_count = Utub_Tags.query.count()
        initial_assoc_count = Utub_Url_Tags.query.count()

    call_count = {"value": 0}

    def failing_add_url_tag(utub_url, utub_tag):
        call_count["value"] += 1
        if call_count["value"] == 2:
            raise RuntimeError("simulated mid-batch failure")
        new_association = Utub_Url_Tags(
            utub_id=utub_url.utub_id,
            utub_url_id=utub_url.id,
            utub_tag_id=utub_tag.id,
        )
        db.session.add(new_association)
        return new_association

    # The simulated failure propagates out of the WSGI test client because the
    # testing config enables PROPAGATE_EXCEPTIONS. The point under test is the
    # post-rollback DB state: the single final commit is never reached, so the
    # flushed vocabulary rows and any association writes are all rolled back.
    with patch(
        "backend.tags.services.create_url_tag._add_url_tag",
        side_effect=failing_add_url_tag,
    ):
        with pytest.raises(RuntimeError, match="simulated mid-batch failure"):
            client.post(
                url_for(
                    ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS,
                    utub_id=utub_id,
                    utub_url_id=utub_url_id,
                ),
                json={
                    TAG_STRINGS_FIELD: [
                        FRESH_TAG_ALPHA,
                        FRESH_TAG_BETA,
                        FRESH_TAG_GAMMA,
                    ]
                },
                headers={"X-CSRFToken": csrf_token},
            )

    with app.app_context():
        assert Utub_Tags.query.count() == initial_vocab_count
        assert Utub_Url_Tags.query.count() == initial_assoc_count

    assert is_string_in_logs("Batch tag-apply failed", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_id}", caplog.records)
    assert is_string_in_logs(f"UTubURL.id={utub_url_id}", caplog.records)
    assert is_string_in_logs("RequestedCount=3", caplog.records)
    assert is_string_in_logs("error_type=RuntimeError", caplog.records)
