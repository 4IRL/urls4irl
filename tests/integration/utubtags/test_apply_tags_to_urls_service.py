from unittest.mock import patch

from flask_login import current_user
import pytest

from backend import db
from backend.metrics.events import EventName
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.tags.constants import BulkTagSkipReason
from backend.tags.services.create_url_tag import add_tags_to_urls_in_utub
from backend.utils.constants import TAG_CONSTANTS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as MODEL_STRS
from backend.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.tags

FRESH_TAG_ALPHA = "bulkalpha"
FRESH_TAG_BETA = "bulkbeta"
FRESH_TAG_GAMMA = "bulkgamma"
URL_COUNT_BUCKET_DIM_KEY = "url_count_bucket"
SKIPPED_COUNT_BUCKET_DIM_KEY = "skipped_count_bucket"


def _get_creator_utub_and_url_ids() -> tuple[int, list[int]]:
    """Return (utub_id, [utub_url_id, ...]) for a UTub the current user created.

    Must be called within an active app context; the UTub has multiple URLs
    (seeded by add_all_urls_and_users_to_each_utub_no_tags), which the multi-URL
    service needs to exercise per-URL partial success.
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


def test_service_applies_tags_to_multiple_urls_happy_path(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub with multiple tag-less URLs (service called directly)
    WHEN two fresh tags are applied to the first two URLs
    THEN the service returns 200, both URLs appear in `applied` with the correct
        utubUrlTagIDs / appliedTags, `skipped` is empty, and two new associations
        are created per URL with acting-user attribution.

    Note: the success breadcrumb emitted via `safe_add_many_logs` is only flushed
    to a log record by the `after_request` HTTP hook, so it is asserted at the
    route layer (Step 5), not in this direct-service call.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        acting_user_id = current_user.id
        target_url_ids = url_ids[:2]
        utub: Utubs = Utubs.query.get(utub_id)

        response, status_code = add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA, FRESH_TAG_BETA],
            utub_url_ids=target_url_ids,
            utub=utub,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert body[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAGS_ADDED_TO_URLS
        assert body[MODEL_STRS.SKIPPED] == []
        applied = body[MODEL_STRS.APPLIED]
        assert len(applied) == 2
        assert {entry[MODEL_STRS.UTUB_URL_ID] for entry in applied} == set(
            target_url_ids
        )

        for entry in applied:
            assert len(entry[MODEL_STRS.APPLIED_TAGS]) == 2
            url_after: Utub_Urls = Utub_Urls.query.get(entry[MODEL_STRS.UTUB_URL_ID])
            assert sorted(entry[MODEL_STRS.URL_TAG_IDS]) == sorted(
                url_after.associated_tag_ids
            )

        new_associations: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id.in_(target_url_ids),
        ).all()
        assert len(new_associations) == 4
        assert all(
            association.user_id == acting_user_id for association in new_associations
        )


def test_service_partial_success_over_limit_url_skipped(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN three tag-less URLs where the third is already at the per-URL tag limit
    WHEN two fresh tags are applied to all three
    THEN the first two are in `applied`, the third is in `skipped` with reason
        OVER_LIMIT, and the over-limit URL gains zero new association rows.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        url_a, url_b, url_c = url_ids[0], url_ids[1], url_ids[2]
        _fill_url_to_tag_limit(utub_id, url_c)
        assoc_count_c_before = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_url_id == url_c
        ).count()
        utub: Utubs = Utubs.query.get(utub_id)

        response, status_code = add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA, FRESH_TAG_BETA],
            utub_url_ids=[url_a, url_b, url_c],
            utub=utub,
        )
        body = response.get_json()

        assert status_code == 200
        applied_ids = {
            entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.APPLIED]
        }
        assert applied_ids == {url_a, url_b}

        skipped = body[MODEL_STRS.SKIPPED]
        assert len(skipped) == 1
        assert skipped[0][MODEL_STRS.UTUB_URL_ID] == url_c
        assert skipped[0][MODEL_STRS.SKIP_REASON] == BulkTagSkipReason.OVER_LIMIT.value

        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == url_c).count()
            == assoc_count_c_before
        )


def test_service_all_urls_over_limit_is_noop(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN every target URL already at the per-URL tag limit
    WHEN fresh tags are applied to all of them
    THEN `applied` is empty, `skipped` lists every URL, and no new association
        rows are written to any of them.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        for url_id in url_ids:
            _fill_url_to_tag_limit(utub_id, url_id)
        assoc_count_before = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id
        ).count()
        utub: Utubs = Utubs.query.get(utub_id)

        response, status_code = add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA],
            utub_url_ids=url_ids,
            utub=utub,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.APPLIED] == []
        assert {
            entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.SKIPPED]
        } == set(url_ids)
        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_id == utub_id).count()
            == assoc_count_before
        )


def test_service_already_present_tag_silently_noop_but_url_still_applied(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a URL that already has one of the requested tags
    WHEN the batch (containing that already-present tag plus a fresh one) is applied
    THEN the already-present tag is not listed in that URL's appliedTags (only the
        fresh one is), the URL still appears in `applied`, and its utubUrlTagIDs is
        the Python-computed union of the pre-existing and newly-applied tag ids.
    """
    _, _, _, app = login_first_user_without_register

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
        utub: Utubs = Utubs.query.get(utub_id)

        response, status_code = add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA, FRESH_TAG_BETA],
            utub_url_ids=[url_a],
            utub=utub,
        )
        body = response.get_json()

        assert status_code == 200
        applied = body[MODEL_STRS.APPLIED]
        assert len(applied) == 1
        entry = applied[0]
        assert entry[MODEL_STRS.UTUB_URL_ID] == url_a

        applied_tag_ids = {tag[MODEL_STRS.ID] for tag in entry[MODEL_STRS.APPLIED_TAGS]}
        # The already-present tag is silently no-op'd — only the fresh tag is new.
        assert existing_tag_id not in applied_tag_ids
        assert len(applied_tag_ids) == 1

        url_after: Utub_Urls = Utub_Urls.query.get(url_a)
        # utubUrlTagIDs is the union of pre-existing + newly applied, sorted.
        assert entry[MODEL_STRS.URL_TAG_IDS] == sorted(url_after.associated_tag_ids)
        assert existing_tag_id in entry[MODEL_STRS.URL_TAG_IDS]


def test_service_url_with_all_tags_already_present_is_applied_noop(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a URL whose every requested tag is already present (nothing net-new)
    WHEN the batch (containing only that already-present tag) is applied
    THEN the URL still appears in `applied` with an empty appliedTags list, its
        utubUrlTagIDs equals the unchanged tag set, no new association rows are
        written, and (metrics enabled) no TAGS_APPLIED_MULTI_URL counter fires
        because no URL actually gained a tag.
    """
    _, _, _, app = login_first_user_without_register

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
        assoc_count_before = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_url_id == url_a
        ).count()
        utub: Utubs = Utubs.query.get(utub_id)

        response, status_code = add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA],
            utub_url_ids=[url_a],
            utub=utub,
        )
        body = response.get_json()

        assert status_code == 200
        assert body[MODEL_STRS.SKIPPED] == []
        applied = body[MODEL_STRS.APPLIED]
        assert len(applied) == 1
        entry = applied[0]
        assert entry[MODEL_STRS.UTUB_URL_ID] == url_a
        assert entry[MODEL_STRS.APPLIED_TAGS] == []
        assert entry[MODEL_STRS.URL_TAG_IDS] == [existing_tag_id]

        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == url_a).count()
            == assoc_count_before
        )
        assert (
            count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL)
            == 0
        )


def test_service_rejects_url_from_different_utub(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that belongs to a different UTub
    WHEN it is included in the multi-URL apply request
    THEN the whole request is rejected 400 with URL_NOT_IN_UTUB and zero rows are
        written anywhere.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        foreign_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_id
        ).first()
        assert foreign_url is not None
        assoc_count_before = Utub_Url_Tags.query.count()
        vocab_count_before = Utub_Tags.query.count()
        utub: Utubs = Utubs.query.get(utub_id)

        response, status_code = add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA],
            utub_url_ids=[url_ids[0], foreign_url.id],
            utub=utub,
        )
        body = response.get_json()

        assert status_code == 400
        assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert body[STD_JSON.MESSAGE] == TAGS_FAILURE.URL_NOT_IN_UTUB
        assert Utub_Url_Tags.query.count() == assoc_count_before
        assert Utub_Tags.query.count() == vocab_count_before


def test_service_rejects_nonexistent_url_id(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a utubUrlId that does not exist at all
    WHEN it is included in the multi-URL apply request
    THEN the whole request is rejected 400 with URL_NOT_IN_UTUB and zero rows are
        written.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        nonexistent_id = (
            db.session.query(db.func.max(Utub_Urls.id)).scalar() or 0
        ) + 1000
        assoc_count_before = Utub_Url_Tags.query.count()
        utub: Utubs = Utubs.query.get(utub_id)

        response, status_code = add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA],
            utub_url_ids=[url_ids[0], nonexistent_id],
            utub=utub,
        )
        body = response.get_json()

        assert status_code == 400
        assert body[STD_JSON.MESSAGE] == TAGS_FAILURE.URL_NOT_IN_UTUB
        assert Utub_Url_Tags.query.count() == assoc_count_before


def test_service_mid_loop_exception_rolls_back_all_urls(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a multi-URL apply where _add_url_tag raises on its 2nd call
    WHEN the service processes the batch
    THEN the exception propagates, every flushed vocabulary and association write
        across ALL URLs is rolled back (single final commit is never reached), and
        the rollback breadcrumb is logged.
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        target_url_ids = url_ids[:2]
        vocab_count_before = Utub_Tags.query.count()
        assoc_count_before = Utub_Url_Tags.query.count()
        utub: Utubs = Utubs.query.get(utub_id)

        call_count = {"value": 0}

        def failing_add_url_tag(utub_url, utub_tag):
            call_count["value"] += 1
            if call_count["value"] == 2:
                raise RuntimeError("simulated mid-loop failure")
            new_association = Utub_Url_Tags(
                utub_id=utub_url.utub_id,
                utub_url_id=utub_url.id,
                utub_tag_id=utub_tag.id,
            )
            db.session.add(new_association)
            return new_association

        with patch(
            "backend.tags.services.create_url_tag._add_url_tag",
            side_effect=failing_add_url_tag,
        ):
            with pytest.raises(RuntimeError, match="simulated mid-loop failure"):
                add_tags_to_urls_in_utub(
                    tag_strings=[FRESH_TAG_ALPHA, FRESH_TAG_BETA],
                    utub_url_ids=target_url_ids,
                    utub=utub,
                )

        assert Utub_Tags.query.count() == vocab_count_before
        assert Utub_Url_Tags.query.count() == assoc_count_before

    assert is_string_in_logs("Bulk multi-URL tag-apply failed", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_id}", caplog.records)
    assert is_string_in_logs("error_type=RuntimeError", caplog.records)


def test_service_records_tag_applied_and_multi_url_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and three tag-less URLs (the third at the tag limit)
    WHEN one fresh tag is applied to all three (two succeed, one over-limit skip)
    THEN TAG_APPLIED is incremented once per applied (url, tag) association (2),
        exactly one TAGS_APPLIED_MULTI_URL counter is written, and it carries
        url_count_bucket="2-5" and skipped_count_bucket="1".
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        url_a, url_b, url_c = url_ids[0], url_ids[1], url_ids[2]
        _fill_url_to_tag_limit(utub_id, url_c)
        utub: Utubs = Utubs.query.get(utub_id)

        assert sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == 0
        assert (
            count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL)
            == 0
        )

        add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA],
            utub_url_ids=[url_a, url_b, url_c],
            utub=utub,
        )

        assert sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == 2
        assert (
            count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL)
            == 1
        )
        multi_url_keys = find_counter_keys(
            provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL
        )
        dims = parse_dims(multi_url_keys[0])
        assert dims[URL_COUNT_BUCKET_DIM_KEY] == "2-5"
        assert dims[SKIPPED_COUNT_BUCKET_DIM_KEY] == "1"


def test_service_no_multi_url_metric_when_all_skipped(
    metrics_enabled_app,
    provide_metrics_redis,
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN metrics enabled and every target URL at the per-URL tag limit
    WHEN a fresh tag is applied to all of them
    THEN no TAGS_APPLIED_MULTI_URL counter is written (nothing was actually applied).
    """
    _, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_id, url_ids = _get_creator_utub_and_url_ids()
        for url_id in url_ids:
            _fill_url_to_tag_limit(utub_id, url_id)
        utub: Utubs = Utubs.query.get(utub_id)

        add_tags_to_urls_in_utub(
            tag_strings=[FRESH_TAG_ALPHA],
            utub_url_ids=url_ids,
            utub=utub,
        )

        assert (
            count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL)
            == 0
        )
