"""Verified-assumption tests behind the small-cell suppression floor.

The read-time floor is only sound if nothing identifying is ever buffered or
logged: counter keys carry only registry dims, and the flush never logs dims.
"""

from __future__ import annotations

import json
import logging
import re
from unittest.mock import MagicMock

import psycopg2.errors
import pytest
from flask import Flask, url_for
from redis import Redis

from backend.metrics.dimension_models import DIMENSION_MODELS
from backend.metrics.events import EventName
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import UTUB_FORM
from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import (
    FLUSH_FAILURE_FLAG_KEY,
    FLUSH_LOCK_KEY,
    run_flush,
    run_flush_job,
)
from tests.integration.system.metrics_helpers import (
    build_counter_key,
    build_pg_conn,
    truncate_metrics_tables,
)

pytestmark = pytest.mark.cli

_COUNTER_KEY_PATTERN = re.compile(r"^metrics:counter:\d+:[a-z_]+:\{.*\}$")
_BUCKET_START_EPOCH = 1735689600  # 2025-01-01 00:00:00 UTC, hour-aligned
_DISTINCTIVE_ENDPOINT = "/distinctive-flush-log-probe-9f3a"
_DISTINCTIVE_BAD_ENDPOINT = "/distinctive-flush-log-bad-7c1e"


def test_counter_keys_match_shape_and_carry_only_registry_dims(
    metrics_enabled_app,
    provide_metrics_redis: Redis,
    login_first_user_with_register,
):
    """
    GIVEN metrics are enabled and a logged-in user drives real requests
        through the middleware (a page load plus a UTub create)
    WHEN every `metrics:counter:*` key in Redis is inspected
    THEN ensure each key matches the canonical shape, its dims JSON keys are a
        subset of the event's registered dims, and no user id, UTub id, IP,
        username or email appears anywhere in the key
    """
    client, csrf_token, user, app = login_first_user_with_register

    create_response = client.post(
        url_for(ROUTES.UTUBS.CREATE_UTUB),
        json={
            UTUB_FORM.UTUB_NAME: "Identifier Probe UTub",
            UTUB_FORM.UTUB_DESCRIPTION: "",
        },
        headers={"X-CSRFToken": csrf_token},
    )
    assert create_response.status_code == 200
    utub_id = int(create_response.json["utubID"])
    utub_open_response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={"X-CSRFToken": csrf_token},
    )
    assert utub_open_response.status_code == 200

    forbidden_fragments = {
        "127.0.0.1",
        user.username,
        user.email,
        "user_id",
        "utub_id",
    }

    counter_keys = list(
        provide_metrics_redis.scan_iter(match=f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*")
    )
    assert counter_keys, "expected the requests to have written counter keys"

    id_strings = {str(user.id), str(utub_id)}
    seen_events: set[str] = set()
    for counter_key in counter_keys:
        decoded = counter_key.decode("utf-8")
        assert _COUNTER_KEY_PATTERN.match(decoded), decoded

        _, _, _, event_value, dims_json = decoded.split(":", 4)
        seen_events.add(event_value)
        event_name = EventName(event_value)
        dims = json.loads(dims_json)
        # Numeric dims (status_code, device_type) may equal an id by chance;
        # string-valued dims never should.
        for dim_value in dims.values():
            if isinstance(dim_value, str):
                assert dim_value not in id_strings, decoded
        dim_model = DIMENSION_MODELS[event_name]
        registered_dims = set(dim_model.model_fields) if dim_model else set()
        for dim_key in dims:
            assert dim_key in registered_dims, (
                f"{decoded}: dim '{dim_key}' is not registered for {event_value}"
            )
        for fragment in forbidden_fragments:
            assert fragment.lower() not in decoded.lower(), (
                f"{decoded}: contains identifying fragment {fragment!r}"
            )

    # Both the API_HIT middleware path and a DOMAIN event path were exercised.
    assert EventName.API_HIT.value in seen_events
    assert len(seen_events) > 1, seen_events


def test_flush_logs_carry_no_dims_or_counter_keys(
    app: Flask,
    provide_metrics_redis: Redis,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN counter keys seeded with a distinctive dims value, one with a valid
        count and one whose count is corrupt (exercising the drop path)
    WHEN run_flush drains them with all logging captured
    THEN ensure the flush upserted the valid row and neither distinctive value,
        the dims JSON, nor any counter key prefix appears in the captured logs
    """
    provide_metrics_redis.delete(FLUSH_LOCK_KEY)
    pg_conn = build_pg_conn(app)
    try:
        truncate_metrics_tables(pg_conn)
        with pg_conn.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "EventRegistry" ("name", "category", "description", "addedAt")'
                ' VALUES (%s, %s, %s, NOW()) ON CONFLICT ("name") DO NOTHING',
                (EventName.API_HIT.value, "api", "probe"),
            )
        pg_conn.commit()

        good_dims = {
            "endpoint": _DISTINCTIVE_ENDPOINT,
            "method": "POST",
            "status_code": 200,
        }
        bad_dims = {
            "endpoint": _DISTINCTIVE_BAD_ENDPOINT,
            "method": "GET",
            "status_code": 200,
        }
        provide_metrics_redis.set(
            build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, good_dims),
            5,
        )
        provide_metrics_redis.set(
            build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, bad_dims),
            "not-a-number",
        )

        with caplog.at_level(logging.DEBUG):
            upserted = run_flush(redis_client=provide_metrics_redis, pg_conn=pg_conn)

        # Proves the flush actually ran (not a lock-skip) so the log checks bite.
        assert upserted == 1
        logged = caplog.text
        assert _DISTINCTIVE_ENDPOINT not in logged
        assert _DISTINCTIVE_BAD_ENDPOINT not in logged
        assert METRICS_REDIS.COUNTER_KEY_PREFIX not in logged
        assert (
            json.dumps(good_dims, sort_keys=True, separators=(",", ":")) not in logged
        )
    finally:
        truncate_metrics_tables(pg_conn)
        with pg_conn.cursor() as cursor:
            cursor.execute('DELETE FROM "EventRegistry"')
        pg_conn.commit()
        pg_conn.close()
        provide_metrics_redis.delete(FLUSH_LOCK_KEY)


def test_flush_failure_alert_and_logs_carry_no_dims(
    app: Flask,
    provide_metrics_redis: Redis,
    caplog: pytest.LogCaptureFixture,
):
    """
    GIVEN a counter key with a distinctive dims value and no EventRegistry row,
        so the upsert fails on the foreign key
    WHEN run_flush_job fails and alerts through a spy notifier
    THEN ensure the failure alert text and captured logs contain neither the
        distinctive value nor the dims JSON
    """
    provide_metrics_redis.delete(FLUSH_LOCK_KEY)
    provide_metrics_redis.delete(FLUSH_FAILURE_FLAG_KEY)
    pg_conn = build_pg_conn(app)
    spy_notifier = MagicMock(return_value=0)
    try:
        truncate_metrics_tables(pg_conn)
        with pg_conn.cursor() as cursor:
            cursor.execute('DELETE FROM "EventRegistry"')
        pg_conn.commit()

        dims = {
            "endpoint": _DISTINCTIVE_ENDPOINT,
            "method": "POST",
            "status_code": 200,
        }
        provide_metrics_redis.set(
            build_counter_key(_BUCKET_START_EPOCH, EventName.API_HIT.value, dims), 5
        )

        with caplog.at_level(logging.DEBUG):
            with pytest.raises(psycopg2.errors.ForeignKeyViolation):
                run_flush_job(
                    redis_client=provide_metrics_redis,
                    pg_conn=pg_conn,
                    notifier=spy_notifier,
                )

        spy_notifier.assert_called_once()
        alert_text = str(spy_notifier.call_args)
        for text in (alert_text, caplog.text):
            assert _DISTINCTIVE_ENDPOINT not in text
            assert json.dumps(dims, sort_keys=True, separators=(",", ":")) not in text
    finally:
        pg_conn.rollback()
        truncate_metrics_tables(pg_conn)
        pg_conn.close()
        provide_metrics_redis.delete(FLUSH_LOCK_KEY)
        provide_metrics_redis.delete(FLUSH_FAILURE_FLAG_KEY)
