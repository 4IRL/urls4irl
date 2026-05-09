from __future__ import annotations

import logging
from typing import Generator
from unittest import mock

import pytest
from flask import Flask
from flask.testing import FlaskClient
from redis import Redis

from backend import metrics_writer as app_metrics_writer
from backend.metrics.constants import MetricsErrorCodes
from backend.metrics.events import EventName
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.metrics_strs import METRICS_REDIS
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.cli

INGEST_URL = "/api/metrics"


@pytest.fixture
def metrics_enabled_app(
    app: Flask, provide_metrics_redis: Redis
) -> Generator[Flask, None, None]:
    """Re-init the app's `metrics_writer` extension with `METRICS_ENABLED=True`
    so the ingest route's CSRF + nonce + dispatch path actually exercises Redis.

    Mutates the module-level singleton (the same instance the
    `app.extensions["metrics_writer"]` slot points at) rather than swapping in
    a fresh one — keeps the writer that `record_event(...)` resolves through
    `current_app.extensions` and the writer that the route's
    `from backend import metrics_writer` import binds to identical, so
    `mock.patch.object(app_metrics_writer, ...)` in tests is honored by both
    the route code and the proxy.
    """
    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    app_metrics_writer.init_app(app)

    yield app

    app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
    app_metrics_writer._redis = original_redis
    app_metrics_writer._enabled = original_enabled


def _load_csrf(client: FlaskClient) -> str:
    splash_response = client.get("/")
    return get_csrf_token(splash_response.get_data(), meta_tag=True)


def _count_counter_keys(metrics_redis: Redis, event: EventName) -> int:
    pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{event.value}:*"
    return len(list(metrics_redis.scan_iter(match=pattern)))


def test_ingest_happy_path_with_csrf_header(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an anonymous client with a CSRF token in the X-CSRFToken header
    WHEN POSTing a single-event payload
    THEN the response is 200 and the corresponding Redis counter is incremented.
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {"result": "success"},
                }
            ]
        },
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json["accepted"] == 1
    assert _count_counter_keys(provide_metrics_redis, EventName.UI_URL_COPY) == 1


def test_ingest_happy_path_with_csrf_body_token(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a sendBeacon-style payload with the CSRF token in the body
    WHEN POSTing without an X-CSRFToken header
    THEN the response is 200 and the counter is incremented.
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {"result": "failure"},
                }
            ],
            "csrf_token": csrf,
        },
    )

    assert response.status_code == 200
    assert _count_counter_keys(provide_metrics_redis, EventName.UI_URL_COPY) == 1


def test_ingest_rejects_missing_csrf(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN no CSRF header and no body token
    WHEN POSTing a payload
    THEN the response is 400 with MISSING_CSRF and no counter is incremented.
    """
    client.get("/")  # warm session

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {"result": "success"},
                }
            ]
        },
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.ERROR_CODE] == MetricsErrorCodes.INVALID_FORM_INPUT
    assert _count_counter_keys(provide_metrics_redis, EventName.UI_URL_COPY) == 0


def test_ingest_rejects_invalid_csrf(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a non-empty but invalid X-CSRFToken header
    WHEN POSTing a payload
    THEN the response is 403 (the global CSRFError handler returns an HTML page).
    """
    client.get("/")  # warm session

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {"result": "success"},
                }
            ]
        },
        headers={"X-CSRFToken": "invalid-garbage-token"},
    )

    assert response.status_code == 403
    assert _count_counter_keys(provide_metrics_redis, EventName.UI_URL_COPY) == 0


def test_ingest_rejects_invalid_csrf_body_token(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a non-empty but invalid `csrf_token` body field and no X-CSRFToken header
    WHEN POSTing a payload
    THEN the response is 403 (the global CSRFError handler returns an HTML page).
    """
    client.get("/")  # warm session

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {"result": "success"},
                }
            ],
            "csrf_token": "invalid-garbage-token",
        },
    )

    assert response.status_code == 403
    assert _count_counter_keys(provide_metrics_redis, EventName.UI_URL_COPY) == 0


def test_ingest_rejects_domain_category_event_name(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN a payload using a domain-category EventName value (utub_created)
    WHEN POSTing with a valid CSRF token
    THEN the response is 400 (top-level event_name Literal restricts to UI events).
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={"events": [{"event_name": "utub_created"}]},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.ERROR_CODE] == MetricsErrorCodes.INVALID_FORM_INPUT


def test_ingest_rejects_completely_unknown_event_name(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN an event_name that is not a valid EventName at all
    WHEN POSTing with a valid CSRF token
    THEN the response is 400.
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={"events": [{"event_name": "made_up_event"}]},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_ingest_rejects_unknown_dimension_key(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an event with an unknown dimension key (extra="forbid" on the per-event model)
    WHEN POSTing with a valid CSRF token
    THEN the response is 400 and no counter is incremented.
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_FORM_SUBMIT.value,
                    "dimensions": {
                        "trigger": "enter_key",
                        "form": "url_create",
                        "plan": "free",
                    },
                }
            ]
        },
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.ERROR_CODE] == MetricsErrorCodes.INVALID_FORM_INPUT
    assert _count_counter_keys(provide_metrics_redis, EventName.UI_FORM_SUBMIT) == 0


def test_ingest_rejects_unknown_dimension_value(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN a Literal-mismatched dimension value
    WHEN POSTing with a valid CSRF token
    THEN the response is 400.
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_UTUB_NAME_EDIT_OPEN.value,
                    "dimensions": {"trigger": "pencil"},
                }
            ]
        },
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 400


def test_ingest_rejects_non_empty_dimensions_for_none_model(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN an event whose dimension model is None (no dims allowed)
    WHEN posting non-empty dimensions
    THEN the response is 400 (route-level validate_dimensions raises).
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_UTUB_CREATE_OPEN.value,
                    "dimensions": {"x": 1},
                }
            ]
        },
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_ingest_accepts_empty_dimensions_for_none_model(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an event whose dimension model is None and an omitted/empty dims field
    WHEN posting with a valid CSRF token
    THEN the response is 200.
    """
    csrf = _load_csrf(client)

    response_omitted = client.post(
        INGEST_URL,
        json={"events": [{"event_name": EventName.UI_UTUB_CREATE_OPEN.value}]},
        headers={"X-CSRFToken": csrf},
    )
    response_empty = client.post(
        INGEST_URL,
        json={
            "events": [
                {"event_name": EventName.UI_UTUB_CREATE_OPEN.value, "dimensions": {}}
            ]
        },
        headers={"X-CSRFToken": csrf},
    )

    assert response_omitted.status_code == 200
    assert response_empty.status_code == 200


def test_ingest_rejects_top_level_extra_key(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN a payload with an unknown top-level key
    WHEN POSTing with a valid CSRF token
    THEN the response is 400 (extra="forbid" on MetricsIngestRequest).
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={
            "events": [{"event_name": EventName.UI_UTUB_CREATE_OPEN.value}],
            "unknown": 1,
        },
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 400


def test_ingest_rejects_zero_events(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN an empty events list
    WHEN POSTing with a valid CSRF token
    THEN the response is 400 (min_length=1 enforced).
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={"events": []},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 400


def test_ingest_rejects_too_many_events(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN a 101-element events list
    WHEN POSTing with a valid CSRF token
    THEN the response is 400 (max_length=100 enforced).
    """
    csrf = _load_csrf(client)

    too_many_events = [
        {"event_name": EventName.UI_UTUB_CREATE_OPEN.value} for _ in range(101)
    ]
    response = client.post(
        INGEST_URL,
        json={"events": too_many_events},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 400


def test_ingest_batch_nonce_idempotent(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN two POSTs with the same payload and same batch_id
    WHEN both succeed at the HTTP layer
    THEN the Redis counter is incremented exactly once.
    """
    csrf = _load_csrf(client)
    payload = {
        "events": [
            {
                "event_name": EventName.UI_URL_COPY.value,
                "dimensions": {"result": "success"},
            }
        ],
        "batch_id": "idempotent-batch-1",
    }

    first_response = client.post(
        INGEST_URL, json=payload, headers={"X-CSRFToken": csrf}
    )
    second_response = client.post(
        INGEST_URL, json=payload, headers={"X-CSRFToken": csrf}
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    keys = list(
        provide_metrics_redis.scan_iter(
            match=f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{EventName.UI_URL_COPY.value}:*"
        )
    )
    assert len(keys) == 1
    assert provide_metrics_redis.get(keys[0]) == b"1"


def test_ingest_batch_nonce_distinct_ids_double_count(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN two POSTs of the same payload with two different batch_ids
    WHEN both succeed
    THEN the counter equals 2.
    """
    csrf = _load_csrf(client)
    base_payload = {
        "events": [
            {
                "event_name": EventName.UI_URL_COPY.value,
                "dimensions": {"result": "success"},
            }
        ]
    }

    response_a = client.post(
        INGEST_URL,
        json={**base_payload, "batch_id": "batch-a"},
        headers={"X-CSRFToken": csrf},
    )
    response_b = client.post(
        INGEST_URL,
        json={**base_payload, "batch_id": "batch-b"},
        headers={"X-CSRFToken": csrf},
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    keys = list(
        provide_metrics_redis.scan_iter(
            match=f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{EventName.UI_URL_COPY.value}:*"
        )
    )
    assert len(keys) == 1
    assert provide_metrics_redis.get(keys[0]) == b"2"


def test_ingest_batch_nonce_ttl_set(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a successful POST with a batch_id
    WHEN inspecting the metrics Redis DB
    THEN the batch nonce key exists and has a TTL <= METRICS_BATCH_NONCE_TTL_SECONDS.
    """
    csrf = _load_csrf(client)
    batch_id = "ttl-test-batch"
    response = client.post(
        INGEST_URL,
        json={
            "events": [{"event_name": EventName.UI_UTUB_CREATE_OPEN.value}],
            "batch_id": batch_id,
        },
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 200
    nonce_key = f"{METRICS_REDIS.BATCH_KEY_PREFIX}{batch_id}"
    assert provide_metrics_redis.exists(nonce_key) == 1
    ttl = provide_metrics_redis.ttl(nonce_key)
    expected_max = metrics_enabled_app.config[
        CONFIG_ENVS.METRICS_BATCH_NONCE_TTL_SECONDS
    ]
    assert 0 < ttl <= expected_max


def test_ingest_writer_log_and_drop_does_not_500(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN the writer's `_redis.pipeline` raises during INCR
    WHEN POSTing with a valid CSRF token
    THEN the response is still 200 (writer log-and-drop) and a metrics log entry is emitted.
    """
    csrf = _load_csrf(client)
    caplog.set_level(logging.WARNING)

    class _BrokenPipelineRedis:
        def pipeline(self):
            raise RuntimeError("simulated redis pipeline failure")

        def set(self, *_args, **_kwargs):
            return True

    with mock.patch.object(app_metrics_writer, "_redis", _BrokenPipelineRedis()):
        response = client.post(
            INGEST_URL,
            json={"events": [{"event_name": EventName.UI_UTUB_CREATE_OPEN.value}]},
            headers={"X-CSRFToken": csrf},
        )

    assert response.status_code == 200
    assert any("metrics" in record.message.lower() for record in caplog.records)


def test_ingest_anonymous_user_accepted(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an anonymous (logged-out) client
    WHEN POSTing a payload with a valid CSRF token
    THEN the response is 200 (no @login_required gate).
    """
    csrf = _load_csrf(client)

    response = client.post(
        INGEST_URL,
        json={"events": [{"event_name": EventName.UI_UTUB_CREATE_OPEN.value}]},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status_code == 200


def test_ingest_authenticated_user_accepted(
    provide_metrics_redis: Redis,
    login_first_user_with_register,
):
    """
    GIVEN a logged-in client
    WHEN POSTing a payload with a valid CSRF token
    THEN the response is 200.
    """
    logged_in_client, csrf, _user, app = login_first_user_with_register
    original_metrics_enabled = app.config.get(CONFIG_ENVS.METRICS_ENABLED, False)
    original_redis = app_metrics_writer._redis
    original_enabled = app_metrics_writer._enabled

    app.config[CONFIG_ENVS.METRICS_ENABLED] = True
    app_metrics_writer.init_app(app)

    try:
        response = logged_in_client.post(
            INGEST_URL,
            json={"events": [{"event_name": EventName.UI_UTUB_CREATE_OPEN.value}]},
            headers={"X-CSRFToken": csrf},
        )

        assert response.status_code == 200
    finally:
        app.config[CONFIG_ENVS.METRICS_ENABLED] = original_metrics_enabled
        app_metrics_writer._redis = original_redis
        app_metrics_writer._enabled = original_enabled
