"""
Integration tests for the `utub_size_bucket` dim on TAG_APPLIED.

All six emission sites (single tag, batch, multi-URL, create-with-tags,
revive-on-create, revive-on-edit) route through `record_tag_applied_events`.
Each scenario below takes an index `variant` (0 or 1) so a failing-COUNT run
and a passing control can run against equivalent but distinct targets inside
one test.
"""

import json
from collections.abc import Callable
from typing import Any
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from sqlalchemy import text
from werkzeug.test import TestResponse

from backend import db
from backend.api_v1.services.tokens import create_access_token
from backend.metrics.events import DEVICE_TYPE_DIM_KEY, DeviceType, EventName
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH
from backend.utils.strings.form_strs import TAG_FORM, URL_FORM
from backend.utils.strings.model_strs import MODELS
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import trash_utub_url

pytestmark = pytest.mark.tags

UTUB_ID = 1
TAG_STRINGS_FIELD = "tagStrings"
UTUB_URL_IDS_FIELD = "utubUrlIds"
COUNT_PATH = "backend.tags.services.create_url_tag._count_live_urls_in_utub"
BUCKET_PATH = "backend.tags.services.create_url_tag.bucket_utub_size"
LOG_MESSAGE = "metrics: tag_applied bucket computation failed"

Fire = Callable[[FlaskClient, str, Flask, int], TestResponse]


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _row_id(app: Flask, url_id: int) -> int:
    """utub_url id of the given URL's row in UTub 1."""
    with app.app_context():
        return (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == UTUB_ID, Utub_Urls.url_id == url_id
            )
            .one()
            .id
        )


def _add_extra_url(app: Flask, label: str, *, trashed: bool) -> tuple[int, str]:
    """Insert an extra URL row in UTub 1 (added by user 1); returns (row id, string)."""
    url_string = f"https://www.{label}.example.com/"
    with app.app_context():
        url = Urls(normalized_url=url_string, current_user_id=1)
        db.session.add(url)
        db.session.flush()
        row = Utub_Urls()
        row.standalone_url = url
        row.url_id = url.id
        row.utub_id = UTUB_ID
        row.user_id = 1
        row.url_title = f"Title {label}"
        db.session.add(row)
        db.session.commit()
        row_id = row.id
    if trashed:
        trash_utub_url(app, row_id, deleted_by=1)
    return row_id, url_string


def _url_tag_count(app: Flask) -> int:
    with app.app_context():
        db.session.expire_all()
        return Utub_Url_Tags.query.count()


# ---------------------------------------------------------------------------
# Scenarios: one per emission site. (fire, expected event count for variant 0)
# ---------------------------------------------------------------------------


def _fire_single(
    client: FlaskClient, csrf: str, app: Flask, variant: int
) -> TestResponse:
    return client.post(
        url_for(
            ROUTES.URL_TAGS.CREATE_URL_TAG,
            utub_id=UTUB_ID,
            utub_url_id=_row_id(app, 2 + variant),
        ),
        json={TAG_FORM.TAG_STRING: f"singletag{variant}"},
        headers={"X-CSRFToken": csrf},
    )


def _fire_batch(
    client: FlaskClient, csrf: str, app: Flask, variant: int
) -> TestResponse:
    return client.post(
        url_for(
            ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS,
            utub_id=UTUB_ID,
            utub_url_id=_row_id(app, 2 + variant),
        ),
        json={TAG_STRINGS_FIELD: [f"batchtaga{variant}", f"batchtagb{variant}"]},
        headers={"X-CSRFToken": csrf},
    )


def _fire_multi(
    client: FlaskClient, csrf: str, app: Flask, variant: int
) -> TestResponse:
    return client.post(
        url_for(ROUTES.URL_TAGS.APPLY_TAGS_TO_URLS, utub_id=UTUB_ID),
        json={
            UTUB_URL_IDS_FIELD: [_row_id(app, url_id) for url_id in (1, 2, 3)],
            TAG_STRINGS_FIELD: [f"multitag{variant}"],
        },
        headers={"X-CSRFToken": csrf},
    )


def _fire_create(
    client: FlaskClient, csrf: str, app: Flask, variant: int
) -> TestResponse:
    return client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=UTUB_ID),
        json={
            URL_FORM.URL_STRING: f"https://www.createsite{variant}.example.com/",
            URL_FORM.URL_TITLE: f"Created {variant}",
            TAG_STRINGS_FIELD: [f"createtag{variant}"],
        },
        headers={"X-CSRFToken": csrf},
    )


def _fire_revive_create(
    client: FlaskClient, csrf: str, app: Flask, variant: int
) -> TestResponse:
    _, url_string = _add_extra_url(app, f"revivecreate{variant}", trashed=True)
    return client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=UTUB_ID),
        json={
            URL_FORM.URL_STRING: url_string,
            URL_FORM.URL_TITLE: f"Revived {variant}",
            TAG_STRINGS_FIELD: [f"revivetag{variant}"],
        },
        headers={"X-CSRFToken": csrf},
    )


def _fire_revive_edit(
    client: FlaskClient, csrf: str, app: Flask, variant: int
) -> TestResponse:
    _, url_string = _add_extra_url(app, f"reviveedit{variant}", trashed=True)
    return client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=UTUB_ID,
            utub_url_id=_row_id(app, 2 + variant),
        ),
        json={URL_FORM.URL_STRING: url_string},
        headers={"X-CSRFToken": csrf},
    )


# name -> (fire, events recorded by variant 0, events recorded by variant 1)
SCENARIOS: dict[str, tuple[Fire, int, int]] = {
    "single": (_fire_single, 1, 1),
    "batch": (_fire_batch, 2, 2),
    "multi": (_fire_multi, 3, 3),
    "create": (_fire_create, 1, 1),
    "revive_create": (_fire_revive_create, 1, 1),
    # URLs 2 and 3 each carry one tag; the revive target starts tag-less.
    "revive_edit": (_fire_revive_edit, 1, 1),
}
SITE_IDS = list(SCENARIOS)


# Per-site text the failing (variant 0) response must carry, read from ORM objects.
SITE_MARKERS = {
    "single": "singletag0",
    "batch": "batchtaga0",
    "multi": "multitag0",
    "create": "Created 0",
    "revive_create": "Revived 0",
    "revive_edit": "https://www.reviveedit0.example.com/",
}

# JSON keys whose values legitimately differ between variant 0 and variant 1.
PLACEHOLDER = "<volatile>"


def _is_volatile_key(key: str) -> bool:
    lowered = key.lower().replace("_", "")
    return (
        lowered.endswith(("id", "ids", "string", "strings", "url", "title"))
        or "date" in lowered
        or lowered.endswith("at")
    )


def _normalize(value: Any, key: str = "") -> Any:
    """JSON body with only volatile leaves (ids, tag/url strings, titles,
    timestamps) masked. Lists keep their length and order; id-keyed maps keep
    their size and are compared as sorted value lists."""
    if isinstance(value, dict):
        if value and all(inner_key.isdigit() for inner_key in value):
            return sorted(
                (_normalize(inner) for inner in value.values()),
                key=lambda item: repr(item),
            )
        return {
            inner_key: _normalize(inner, inner_key)
            for inner_key, inner in value.items()
        }
    if isinstance(value, list):
        if _is_volatile_key(key):
            # Id lists (e.g. every tag already on a URL) grow with prior requests
            # on the shared fixture URLs, so only their volatility is compared.
            return PLACEHOLDER
        return [_normalize(item, key) for item in value]
    if value is not None and _is_volatile_key(key) and not isinstance(value, bool):
        return PLACEHOLDER
    return value


def _live_url_count(app: Flask) -> int:
    with app.app_context():
        return Utub_Urls.query.filter(
            Utub_Urls.utub_id == UTUB_ID, Utub_Urls.deleted_at.is_(None)
        ).count()


def _recorded_dims(redis_client) -> list[dict]:
    return [
        parse_dims(key)
        for key in find_counter_keys(redis_client, EventName.TAG_APPLIED)
    ]


def _expected_dims(bucket: str) -> dict:
    return {"utub_size_bucket": bucket, DEVICE_TYPE_DIM_KEY: int(DeviceType.DESKTOP)}


# ---------------------------------------------------------------------------
# Dim value at every site
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("site", SITE_IDS)
def test_tag_applied_dims_equal_bucket_at_every_site(
    site: str,
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 with three live URLs and metrics enabled
    WHEN a request applies tags through the given emission site
    THEN every TAG_APPLIED counter carries exactly the "1-5" size bucket and
        device_type, and the counters sum to the number of applied tags
    """
    client, csrf, _, app = login_first_user_without_register
    fire, expected_events, _ = SCENARIOS[site]

    response = fire(client, csrf, app, 0)

    assert response.status_code == 200
    assert _recorded_dims(provide_metrics_redis) == [_expected_dims("1-5")]
    assert (
        sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED)
        == expected_events
    )


@pytest.mark.parametrize("site", ["single", "create"])
def test_tag_applied_bucket_boundary_on_route(
    site: str,
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 holding five live URLs
    WHEN a tag is applied to an existing URL (count stays 5) or a URL is created
        with a tag (count becomes 6)
    THEN the bucket is "1-5" for the former and "6-20" for the latter
    """
    client, csrf, _, app = login_first_user_without_register
    _add_extra_url(app, "boundaryone", trashed=False)
    _add_extra_url(app, "boundarytwo", trashed=False)
    assert _live_url_count(app) == 5

    response = SCENARIOS[site][0](client, csrf, app, 0)

    assert response.status_code == 200
    expected_bucket = "6-20" if site == "create" else "1-5"
    assert _recorded_dims(provide_metrics_redis) == [_expected_dims(expected_bucket)]


def test_tag_applied_does_not_count_trashed_urls(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN UTub 1 with five live URLs and one trashed URL
    WHEN a tag is applied to an existing URL
    THEN the bucket is "1-5", since the trashed URL is not counted
    """
    client, csrf, _, app = login_first_user_without_register
    _add_extra_url(app, "liveone", trashed=False)
    _add_extra_url(app, "livetwo", trashed=False)
    _add_extra_url(app, "trashedone", trashed=True)

    response = _fire_single(client, csrf, app, 0)

    assert response.status_code == 200
    assert _recorded_dims(provide_metrics_redis) == [_expected_dims("1-5")]


# ---------------------------------------------------------------------------
# One COUNT per request, none when nothing applied or metrics are off
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("site", ["batch", "multi"])
def test_count_runs_once_for_n_events(
    site: str,
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a request that applies several tags
    WHEN it succeeds
    THEN N events are recorded and the live-URL COUNT ran exactly once
    """
    client, csrf, _, app = login_first_user_without_register
    fire, expected_events, _ = SCENARIOS[site]

    with mock.patch(COUNT_PATH, return_value=3) as count_mock:
        response = fire(client, csrf, app, 0)

    assert response.status_code == 200
    assert count_mock.call_count == 1
    assert (
        sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED)
        == expected_events
    )


def test_nothing_applied_runs_no_count_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a URL that already carries the tag being batch-applied
    WHEN the batch request is made
    THEN it succeeds with no COUNT and no TAG_APPLIED
    """
    client, csrf, _, app = login_first_user_without_register
    first_fire = _fire_batch(client, csrf, app, 0)
    assert first_fire.status_code == 200
    redis_before = sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED)

    with mock.patch(COUNT_PATH) as count_mock:
        response = client.post(
            url_for(
                ROUTES.URL_TAGS.BATCH_ADD_URL_TAGS,
                utub_id=UTUB_ID,
                utub_url_id=_row_id(app, 2),
            ),
            json={TAG_STRINGS_FIELD: ["batchtaga0"]},
            headers={"X-CSRFToken": csrf},
        )

    assert response.status_code == 200
    count_mock.assert_not_called()
    assert (
        sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == redis_before
    )


@pytest.mark.parametrize("site", SITE_IDS)
def test_metrics_disabled_runs_no_count_no_rollback_no_event(
    site: str,
    request: pytest.FixtureRequest,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN the default test config (metrics disabled)
    WHEN a tag-applying request is made
    THEN it succeeds with no COUNT, no rollback and no TAG_APPLIED, and its
        response matches an enabled-metrics control run of the same site
    """
    client, csrf, _, app = login_first_user_without_register
    fire, _, control_events = SCENARIOS[site]

    with (
        mock.patch(COUNT_PATH) as count_mock,
        mock.patch.object(db.session, "rollback") as rollback_mock,
    ):
        disabled = fire(client, csrf, app, 0)

    assert disabled.status_code == 200
    count_mock.assert_not_called()
    rollback_mock.assert_not_called()

    # Enable metrics mid-test (restored on teardown) for the control run.
    request.getfixturevalue("metrics_enabled_app")
    redis_client = request.getfixturevalue("provide_metrics_redis")
    assert count_counter_keys(redis_client, EventName.TAG_APPLIED) == 0

    control = fire(client, csrf, app, 1)

    assert control.status_code == 200
    assert _normalize(disabled.get_json()) == _normalize(control.get_json())
    assert sum_counter_values(redis_client, EventName.TAG_APPLIED) == control_events


# ---------------------------------------------------------------------------
# Failing COUNT
# ---------------------------------------------------------------------------


def _raise_runtime_error(_utub_id: int) -> int:
    raise RuntimeError("boom")


def _raise_db_error(_utub_id: int) -> int:
    db.session.execute(text("SELECT 1/0"))
    return 0


@pytest.mark.parametrize("failure", [_raise_runtime_error, _raise_db_error])
@pytest.mark.parametrize("site", SITE_IDS)
def test_failing_count_keeps_success_response_and_association(
    site: str,
    failure: Callable[[int], int],
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN a COUNT that raises (a plain error, or a real aborted-transaction DB error)
    WHEN the request applies tags
    THEN the normal success response is returned (same shape as a passing control),
        the association is still present on a fresh read, no TAG_APPLIED is
        recorded and the failure is logged; TAGS_APPLIED_BATCH / MULTI_URL still
        record; a passing control then records events (the zero is not vacuous)
    """
    client, csrf, _, app = login_first_user_without_register
    fire, _, control_events = SCENARIOS[site]
    associations_before = _url_tag_count(app)

    with mock.patch(COUNT_PATH, side_effect=failure):
        failing = fire(client, csrf, app, 0)

    assert failing.status_code == 200
    # ORM-derived fields are readable after the failed COUNT (no stale/expired state)
    assert SITE_MARKERS[site] in json.dumps(failing.get_json())
    assert _url_tag_count(app) > associations_before
    assert count_counter_keys(provide_metrics_redis, EventName.TAG_APPLIED) == 0
    assert LOG_MESSAGE in caplog.text
    if site == "batch":
        assert (
            count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_BATCH) == 1
        )
    if site == "multi":
        assert (
            count_counter_keys(provide_metrics_redis, EventName.TAGS_APPLIED_MULTI_URL)
            == 1
        )

    control = fire(client, csrf, app, 1)

    assert control.status_code == 200
    assert _normalize(failing.get_json()) == _normalize(control.get_json())
    assert (
        sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED)
        == control_events
    )


@pytest.mark.parametrize("site", SITE_IDS)
def test_failing_bucketing_keeps_success_response_and_association(
    site: str,
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN bucket_utub_size raises after a successful COUNT
    WHEN the request applies tags
    THEN the normal success response is returned, the association is present,
        no TAG_APPLIED is recorded and the failure is logged
    """
    client, csrf, _, app = login_first_user_without_register
    fire, _, _ = SCENARIOS[site]
    associations_before = _url_tag_count(app)

    with mock.patch(BUCKET_PATH, side_effect=RuntimeError("boom")):
        failing = fire(client, csrf, app, 0)

    assert failing.status_code == 200
    assert SITE_MARKERS[site] in json.dumps(failing.get_json())
    assert _url_tag_count(app) > associations_before
    assert count_counter_keys(provide_metrics_redis, EventName.TAG_APPLIED) == 0
    assert LOG_MESSAGE in caplog.text


# ---------------------------------------------------------------------------
# Mobile (api_v1) route
# ---------------------------------------------------------------------------


def test_api_v1_create_url_tag_records_size_bucket(
    app: Flask,
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
):
    """
    GIVEN a bearer-authenticated member of UTub 1 (three live URLs)
    WHEN they POST a tag through the api_v1 route
    THEN a single TAG_APPLIED counter carries utub_size_bucket "1-5"
    """
    utub_url_id = _row_id(app, 2)
    with app.test_request_context():
        token = create_access_token(user=Users.query.get(1))
        route = url_for(
            ROUTES.API_V1.CREATE_URL_TAG, utub_id=UTUB_ID, utub_url_id=utub_url_id
        )

    # Plain client: no session, CSRF or X-Requested-With, like a native mobile client.
    response = FlaskClient(app, app.response_class).post(
        route,
        json={MODELS.TAG_STRING: "mobilesizetag"},
        headers={API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"},
    )

    assert response.status_code == 200
    dims = _recorded_dims(provide_metrics_redis)
    assert len(dims) == 1
    assert dims[0]["utub_size_bucket"] == "1-5"
    assert sum_counter_values(provide_metrics_redis, EventName.TAG_APPLIED) == 1
