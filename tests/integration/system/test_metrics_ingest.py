from __future__ import annotations

import logging
from unittest import mock

import pytest
from flask import Flask
from flask.testing import FlaskClient
from redis import Redis

from backend import metrics_writer as app_metrics_writer
from backend.metrics.constants import MetricsErrorCodes
from backend.metrics.events import DeviceType, EventName
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.metrics_strs import METRICS_REDIS
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.cli

INGEST_URL = "/api/metrics"


def assert_warning_logged(caplog: pytest.LogCaptureFixture, text: str) -> None:
    """Assert at least one captured log record at WARNING level contains ``text``.

    Tighter than ``is_string_in_logs(...)`` (which is text-only) plus a separate
    ``any(record.levelno == WARNING ...)`` check (which can be satisfied by an
    unrelated WARNING record): both conditions must hold on the same record.
    """
    matching_warning_records = [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and text in record.getMessage()
    ]
    assert matching_warning_records, (
        f"Expected a WARNING-level log containing {text!r}; "
        f"got records: {[(record.levelname, record.getMessage()) for record in caplog.records]}"
    )


def test_ingest_happy_path_no_csrf(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an anonymous client with no CSRF header or body token
    WHEN POSTing a single-event payload
    THEN the response is 200 and the corresponding Redis counter is incremented.
    """
    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {
                        "result": "success",
                        "device_type": DeviceType.MOBILE,
                    },
                }
            ]
        },
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json["accepted"] == 1
    assert count_counter_keys(provide_metrics_redis, EventName.UI_URL_COPY) == 1


def test_ingest_records_tag_sheet_toggle_with_action_dimension(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an anonymous client
    WHEN POSTing UI_TAG_SHEET_TOGGLE events with action open and close
    THEN each is accepted and a distinct Redis counter carries the `action` dim.
    """
    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_TAG_SHEET_TOGGLE.value,
                    "dimensions": {
                        "action": "open",
                        "trigger": "tap",
                        "device_type": DeviceType.MOBILE,
                    },
                },
                {
                    "event_name": EventName.UI_TAG_SHEET_TOGGLE.value,
                    "dimensions": {
                        "action": "close",
                        "trigger": "tap",
                        "device_type": DeviceType.MOBILE,
                    },
                },
            ]
        },
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json["accepted"] == 2

    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.UI_TAG_SHEET_TOGGLE
    )
    assert len(counter_keys) == 2
    actions = {parse_dims(counter_key)["action"] for counter_key in counter_keys}
    assert actions == {"open", "close"}


def test_ingest_rejects_unknown_tag_sheet_toggle_action(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an anonymous client
    WHEN POSTing UI_TAG_SHEET_TOGGLE with an action outside the closed set
    THEN the event is rejected and no counter is written.
    """
    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_TAG_SHEET_TOGGLE.value,
                    "dimensions": {
                        "action": "peek",
                        "trigger": "tap",
                        "device_type": DeviceType.MOBILE,
                    },
                }
            ]
        },
    )

    assert response.status_code == 400
    assert count_counter_keys(provide_metrics_redis, EventName.UI_TAG_SHEET_TOGGLE) == 0


def test_ingest_accepts_transport_beacon_query_param(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an anonymous client posting to the ingest endpoint with ?transport=beacon
    WHEN POSTing a single-event payload
    THEN the response is 200 and the corresponding Redis counter is incremented.

    Regression guard: once `extra="forbid"` is enforced on TransportQuerySchema,
    a typo'd `?transports=...` would 400. This test confirms `?transport=beacon`
    is accepted as a valid Literal value.
    """
    response = client.post(
        INGEST_URL + "?transport=beacon",
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {
                        "result": "success",
                        "device_type": DeviceType.MOBILE,
                    },
                }
            ]
        },
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json["accepted"] == 1


def test_ingest_rejects_unknown_transport_value(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN an anonymous client posting with ?transport=quic (not the Literal "beacon")
    WHEN POSTing a valid single-event payload
    THEN the response is 400 with INVALID_QUERY_PARAM (Literal mismatch).
    """
    response = client.post(
        INGEST_URL + "?transport=quic",
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {
                        "result": "success",
                        "device_type": DeviceType.MOBILE,
                    },
                }
            ]
        },
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.ERROR_CODE] == MetricsErrorCodes.INVALID_QUERY_PARAM


def test_ingest_rejects_unknown_query_param(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN an anonymous client posting with a typo'd ?transports=beacon (extra key)
    WHEN POSTing a valid single-event payload
    THEN the response is 400 with INVALID_QUERY_PARAM (extra="forbid").
    """
    response = client.post(
        INGEST_URL + "?transports=beacon",
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {
                        "result": "success",
                        "device_type": DeviceType.MOBILE,
                    },
                }
            ]
        },
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.ERROR_CODE] == MetricsErrorCodes.INVALID_QUERY_PARAM


def test_ingest_ignores_invalid_csrf_header(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an anonymous client sending a garbage X-CSRFToken header
    WHEN POSTing a valid single-event payload
    THEN the response is 200 (the endpoint is CSRF-exempt; the header is ignored)
    AND the corresponding Redis counter is incremented.
    """
    assert count_counter_keys(provide_metrics_redis, EventName.UI_URL_COPY) == 0

    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_URL_COPY.value,
                    "dimensions": {
                        "result": "success",
                        "device_type": DeviceType.MOBILE,
                    },
                }
            ]
        },
        headers={"X-CSRFToken": "garbage-token-not-real"},
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json["accepted"] == 1
    assert count_counter_keys(provide_metrics_redis, EventName.UI_URL_COPY) == 1


def test_ingest_rejects_domain_category_event_name(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN a payload using a domain-category EventName value (utub_created)
    WHEN POSTing
    THEN the response is 400 (top-level event_name Literal restricts to UI events)
    AND the app logger emits a WARNING containing the validation failure details.
    """
    with caplog.at_level(logging.WARNING, logger="backend"):
        response = client.post(
            INGEST_URL,
            json={"events": [{"event_name": "utub_created"}]},
        )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.ERROR_CODE] == MetricsErrorCodes.INVALID_FORM_INPUT
    assert_warning_logged(caplog, "Invalid JSON")


def test_ingest_rejects_completely_unknown_event_name(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN an event_name that is not a valid EventName at all
    WHEN POSTing
    THEN the response is 400
    AND the app logger emits a WARNING containing the validation failure details.
    """
    with caplog.at_level(logging.WARNING, logger="backend"):
        response = client.post(
            INGEST_URL,
            json={"events": [{"event_name": "made_up_event"}]},
        )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert_warning_logged(caplog, "Invalid JSON")


def test_ingest_rejects_unknown_dimension_key(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an event with an unknown dimension key (extra="forbid" on the per-event model)
    WHEN POSTing
    THEN the response is 400 and no counter is incremented.
    """
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
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.ERROR_CODE] == MetricsErrorCodes.INVALID_FORM_INPUT
    assert count_counter_keys(provide_metrics_redis, EventName.UI_FORM_SUBMIT) == 0


def test_ingest_rejects_unknown_dimension_value(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN a Literal-mismatched dimension value
    WHEN POSTing
    THEN the response is 400.
    """
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
    )

    assert response.status_code == 400


def test_ingest_rejects_non_empty_dimensions_for_none_model(
    metrics_enabled_app: Flask,
    client: FlaskClient,
):
    """
    GIVEN a formerly-None-mapped UI event (now `_DimDeviceOnly`)
    WHEN posting an unknown dimension key
    THEN the response is 400 — extra="forbid" still rejects unknown keys.
    """
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
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_ingest_accepts_device_type_dimension_for_formerly_none_model(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a formerly-None-mapped UI event (now `_DimDeviceOnly`)
    WHEN posting with `device_type` (200), with omitted dimensions (400), or with empty dimensions (400)
    THEN only the `device_type`-bearing payload succeeds; both missing-field cases are rejected.
    """
    response_with_device = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_UTUB_CREATE_OPEN.value,
                    "dimensions": {"device_type": DeviceType.MOBILE},
                }
            ]
        },
    )
    response_omitted = client.post(
        INGEST_URL,
        json={"events": [{"event_name": EventName.UI_UTUB_CREATE_OPEN.value}]},
    )
    response_empty = client.post(
        INGEST_URL,
        json={
            "events": [
                {"event_name": EventName.UI_UTUB_CREATE_OPEN.value, "dimensions": {}}
            ]
        },
    )

    assert response_with_device.status_code == 200
    assert response_omitted.status_code == 400
    assert response_empty.status_code == 400


def test_ingest_rejects_top_level_extra_key(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN a payload with an unknown top-level key
    WHEN POSTing
    THEN the response is 400 (extra="forbid" on MetricsIngestRequest)
    AND the app logger emits a WARNING containing the validation failure details.
    """
    with caplog.at_level(logging.WARNING, logger="backend"):
        response = client.post(
            INGEST_URL,
            json={
                "events": [{"event_name": EventName.UI_UTUB_CREATE_OPEN.value}],
                "unknown": 1,
            },
        )

    assert response.status_code == 400
    assert_warning_logged(caplog, "Invalid JSON")


def test_ingest_rejects_zero_events(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN an empty events list
    WHEN POSTing
    THEN the response is 400 (min_length=1 enforced)
    AND the app logger emits a WARNING containing the validation failure details.
    """
    with caplog.at_level(logging.WARNING, logger="backend"):
        response = client.post(
            INGEST_URL,
            json={"events": []},
        )

    assert response.status_code == 400
    assert_warning_logged(caplog, "Invalid JSON")


def test_ingest_rejects_too_many_events(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN a 101-element events list
    WHEN POSTing
    THEN the response is 400 (max_length=100 enforced)
    AND the app logger emits a WARNING containing the validation failure details.
    """
    too_many_events = [
        {"event_name": EventName.UI_UTUB_CREATE_OPEN.value} for _ in range(101)
    ]
    with caplog.at_level(logging.WARNING, logger="backend"):
        response = client.post(
            INGEST_URL,
            json={"events": too_many_events},
        )

    assert response.status_code == 400
    assert_warning_logged(caplog, "Invalid JSON")


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
    payload = {
        "events": [
            {
                "event_name": EventName.UI_URL_COPY.value,
                "dimensions": {"result": "success", "device_type": DeviceType.MOBILE},
            }
        ],
        "batch_id": "idempotent-batch-1",
    }

    first_response = client.post(INGEST_URL, json=payload)
    second_response = client.post(INGEST_URL, json=payload)

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
    base_payload = {
        "events": [
            {
                "event_name": EventName.UI_URL_COPY.value,
                "dimensions": {"result": "success", "device_type": DeviceType.MOBILE},
            }
        ]
    }

    response_a = client.post(
        INGEST_URL,
        json={**base_payload, "batch_id": "batch-a"},
    )
    response_b = client.post(
        INGEST_URL,
        json={**base_payload, "batch_id": "batch-b"},
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
    batch_id = "ttl-test-batch"
    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_UTUB_CREATE_OPEN.value,
                    "dimensions": {"device_type": DeviceType.MOBILE},
                }
            ],
            "batch_id": batch_id,
        },
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
    WHEN POSTing
    THEN the response is still 200 (writer log-and-drop) and the app logger emits
    an ERROR entry with the exact phrase "metrics: record_event failed".
    """

    class _BrokenPipelineRedis:
        def pipeline(self):
            raise RuntimeError("simulated redis pipeline failure")

        def set(self, *_args, **_kwargs):
            return True

    with caplog.at_level(logging.ERROR, logger="backend"):
        with mock.patch.object(app_metrics_writer, "_redis", _BrokenPipelineRedis()):
            response = client.post(
                INGEST_URL,
                json={
                    "events": [
                        {
                            "event_name": EventName.UI_UTUB_CREATE_OPEN.value,
                            "dimensions": {"device_type": DeviceType.MOBILE},
                        }
                    ]
                },
            )

    assert response.status_code == 200
    assert is_string_in_logs("metrics: record_event failed", caplog.records)
    assert any(record.levelno == logging.ERROR for record in caplog.records)


def test_ingest_anonymous_user_accepted(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN an anonymous (logged-out) client
    WHEN POSTing a payload
    THEN the response is 200 (no @login_required gate).
    """
    response = client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_UTUB_CREATE_OPEN.value,
                    "dimensions": {"device_type": DeviceType.MOBILE},
                }
            ]
        },
    )

    assert response.status_code == 200


def test_ingest_authenticated_user_accepted(
    metrics_enabled_app: Flask,
    login_first_user_with_register,
):
    """
    GIVEN a logged-in client
    WHEN POSTing a payload
    THEN the response is 200.
    """
    logged_in_client, _csrf, _user, _app = login_first_user_with_register

    response = logged_in_client.post(
        INGEST_URL,
        json={
            "events": [
                {
                    "event_name": EventName.UI_UTUB_CREATE_OPEN.value,
                    "dimensions": {"device_type": DeviceType.MOBILE},
                }
            ]
        },
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# API_METRICS_INGEST_BATCH — pipeline-health counter (Phase 13)
# ---------------------------------------------------------------------------


def _three_event_batch_payload() -> dict:
    """Build a 3-event UI_URL_COPY batch payload for batch-counter tests."""
    return {
        "events": [
            {
                "event_name": EventName.UI_URL_COPY.value,
                "dimensions": {
                    "result": "success",
                    "device_type": DeviceType.DESKTOP,
                },
            }
            for _ in range(3)
        ]
    }


def test_ingest_emits_api_metrics_ingest_batch_counter_fetch_transport(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a 3-event batch posted without `?transport=beacon`
    WHEN the request succeeds (200)
    THEN exactly one API_METRICS_INGEST_BATCH counter key exists
    AND its dimensions are batch_size_bucket="2-5", transport="fetch", device_type=int.
    """
    assert (
        count_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
        == 0
    )

    response = client.post(INGEST_URL, json=_three_event_batch_payload())

    assert response.status_code == 200
    assert (
        count_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
        == 1
    )
    keys = find_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
    dims = parse_dims(keys[0])
    assert dims["batch_size_bucket"] == "2-5"
    assert dims["transport"] == "fetch"
    assert dims["device_type"] in (int(DeviceType.MOBILE), int(DeviceType.DESKTOP))


def test_ingest_emits_api_metrics_ingest_batch_counter_beacon_transport(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a 3-event batch posted with `?transport=beacon`
    WHEN the request succeeds (200)
    THEN exactly one counter key exists with transport="beacon".
    """
    assert (
        count_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
        == 0
    )

    response = client.post(
        INGEST_URL + "?transport=beacon", json=_three_event_batch_payload()
    )

    assert response.status_code == 200
    assert (
        count_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
        == 1
    )
    keys = find_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
    dims = parse_dims(keys[0])
    assert dims["batch_size_bucket"] == "2-5"
    assert dims["transport"] == "beacon"


def test_ingest_emits_batch_counter_even_on_validation_failure(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a payload with an unknown dimension key (per-event validation fails 400)
    WHEN POSTing
    THEN the per-event ingest fails (400)
    BUT the API_METRICS_INGEST_BATCH counter still increments — the counter
    measures every ingest attempt regardless of validation outcome, surfacing
    bad-client volume as a spike.
    """
    assert (
        count_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
        == 0
    )

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
    )

    assert response.status_code == 400
    assert (
        count_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
        == 1
    )


@pytest.mark.parametrize(
    "event_count, expected_bucket",
    [
        (1, "1"),
        (4, "2-5"),
        (25, "6-25"),
        (100, "26-100"),
    ],
)
def test_ingest_batch_counter_uses_correct_batch_size_bucket(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
    event_count: int,
    expected_bucket: str,
):
    """
    GIVEN batches of varying sizes (1, 4, 25, 100)
    WHEN POSTing
    THEN the counter's batch_size_bucket dim matches the closed-set label.
    """
    assert (
        count_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
        == 0
    )

    payload = {
        "events": [
            {
                "event_name": EventName.UI_URL_COPY.value,
                "dimensions": {
                    "result": "success",
                    "device_type": DeviceType.DESKTOP,
                },
            }
            for _ in range(event_count)
        ]
    }

    response = client.post(INGEST_URL, json=payload)

    assert response.status_code == 200
    assert (
        count_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
        == 1
    )
    keys = find_counter_keys(provide_metrics_redis, EventName.API_METRICS_INGEST_BATCH)
    dims = parse_dims(keys[0])
    assert dims["batch_size_bucket"] == expected_bucket


def test_ingest_batch_counter_is_not_double_counted_via_api_hit(
    metrics_enabled_app: Flask,
    client: FlaskClient,
    provide_metrics_redis: Redis,
):
    """
    GIVEN a successful ingest
    WHEN inspecting the metrics blueprint's API_HIT counter
    THEN there is no API_HIT counter for `metrics.ingest` — the recursion
    guard in `should_skip(blueprint='metrics')` keeps the new batch counter
    from being double-counted via the middleware. Belt-and-braces guard if
    that skip rule is ever weakened.
    """
    assert count_counter_keys(provide_metrics_redis, EventName.API_HIT) == 0

    response = client.post(INGEST_URL, json=_three_event_batch_payload())

    assert response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.API_HIT) == 0
