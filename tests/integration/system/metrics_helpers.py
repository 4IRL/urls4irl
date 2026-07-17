from __future__ import annotations

import json
from typing import Any

import psycopg2
from flask import Flask
from redis import Redis

from backend.extensions.metrics.dimensions import canonicalize_dimensions
from backend.metrics.events import DEVICE_TYPE_DIM_KEY, DeviceType, EventName
from backend.utils.strings.metrics_strs import METRICS_REDIS

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)
WINDOWS_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

REJECTION_REASON_DIM_KEY = "reason"
STRIPPED_DIM_KEY = "stripped"


DOMAIN_EVENTS_TESTED_ELSEWHERE: frozenset[EventName] = frozenset(
    {
        EventName.CROSS_UTUB_SEARCH_PERFORMED,
        EventName.URL_ACCESSED,
        EventName.URL_ADDED_TO_UTUB,
        EventName.URL_REMOVED_FROM_UTUB,
        EventName.URL_STRING_UPDATED,
        EventName.URL_TRACKING_PARAMS_STRIPPED,
        EventName.UTUB_TAG_CREATED,
        EventName.TAGS_APPLIED_BATCH,
        EventName.REGISTER_SUCCESS,
        EventName.REGISTER_REJECTED,
        EventName.LOGIN_SUCCESS,
        EventName.LOGIN_FAILURE,
        EventName.EMAIL_VERIFIED,
        EventName.PASSWORD_RESET_REQUESTED,
        EventName.PASSWORD_RESET_COMPLETED,
        EventName.URL_CREATE_REJECTED,
        EventName.OAUTH_IDENTITY_LINKED,
        EventName.OAUTH_IDENTITY_UNLINKED,
    }
)
"""DOMAIN events whose pipeline coverage lives in dedicated per-route emit tests.

URL_ACCESSED and the URL_*/UTUB_TAG_CREATED events fire from URL/tag service
flows that the shared system-level seed does not exercise; the auth lifecycle
events (REGISTER_SUCCESS, LOGIN_SUCCESS, LOGIN_FAILURE, EMAIL_VERIFIED,
PASSWORD_RESET_*) fire from unauthenticated splash routes that the
authenticated test fixture cannot reach. The rejection events
(REGISTER_REJECTED, URL_CREATE_REJECTED) fire only on the register / URL-create
failure branches, which the shared authenticated success-path seed never
drives — each has its own per-cause emit test under
tests/integration/splash/ and tests/integration/utuburls/.
CROSS_UTUB_SEARCH_PERFORMED fires only from the /search service flow, which the
shared seed does not exercise; its per-dimension emit test lives under
tests/integration/search/. URL_TRACKING_PARAMS_STRIPPED fires only from the URL
create/update service flows, not the shared seed; its per-dimension emit tests
live under tests/integration/utuburls/. TAGS_APPLIED_BATCH fires only from the batch
tag-apply service flow, which the shared seed does not exercise; its per-batch
emit test lives under tests/integration/utubtags/. OAUTH_IDENTITY_LINKED and
OAUTH_IDENTITY_UNLINKED fire only from the authenticated OAuth link/unlink
service flows (settings-initiated link requiring a password re-auth or an OAuth
provider round-trip, and the collision confirm-link path), which the shared
success-path seed cannot drive; their per-flow emit tests live under
tests/integration/account_and_settings/test_oauth_linking.py and
tests/integration/splash/test_oauth_confirm_link.py. Each excluded event
has its own per-route emit test under tests/integration/<feature>/ and flushes
through the same pipeline, so the end-to-end invariant is still covered.
"""


def find_counter_keys(metrics_redis: Redis, event: EventName) -> list[bytes]:
    pattern = f"{METRICS_REDIS.COUNTER_KEY_PREFIX}*:{event.value}:*"
    return list(metrics_redis.scan_iter(match=pattern))


def build_pg_conn(app: Flask) -> Any:
    return psycopg2.connect(app.config["SQLALCHEMY_DATABASE_URI"])


def truncate_metrics_tables(pg_conn: Any) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute('TRUNCATE TABLE "AnonymousMetrics" RESTART IDENTITY CASCADE')
    pg_conn.commit()


def truncate_gauges_tables(pg_conn: Any) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute('TRUNCATE TABLE "AnonymousGauges" RESTART IDENTITY CASCADE')
    pg_conn.commit()


def count_counter_keys(metrics_redis: Redis, event: EventName) -> int:
    return len(find_counter_keys(metrics_redis, event))


def sum_counter_values(metrics_redis: Redis, event: EventName) -> int:
    """Sum the integer values of every counter key for `event`.

    Counter keys are stored via Redis ``INCR``, so multiple emits that share
    identical dimensions collapse into a single key whose value carries the
    increment count. Use this (not ``count_counter_keys``) when asserting the
    total number of times an event fired regardless of dimension cardinality.
    """
    total = 0
    for counter_key in find_counter_keys(metrics_redis, event):
        raw_value = metrics_redis.get(counter_key)
        if raw_value is not None:
            total += int(raw_value)
    return total


def parse_dims(counter_key: bytes) -> dict:
    """Extract the trailing canonical-dims JSON segment from a counter key.

    Key shape: `metrics:counter:<bucket>:<event_name>:<canonical_dims_json>`
    The JSON segment is everything after the 4th colon — split with
    `maxsplit=4` so a `:` inside the JSON does not corrupt the parse.
    """
    decoded = counter_key.decode("utf-8")
    parts = decoded.split(":", 4)
    return json.loads(parts[4])


def build_counter_key(bucket_epoch: int, event_value: str, dims: dict) -> str:
    canonical = json.dumps(dims, sort_keys=True, separators=(",", ":"))
    return f"{METRICS_REDIS.COUNTER_KEY_PREFIX}{bucket_epoch}:{event_value}:{canonical}"


def truncate_latency_tables(pg_conn: Any) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'TRUNCATE TABLE "AnonymousLatencySamples" RESTART IDENTITY CASCADE'
        )
    pg_conn.commit()


def truncate_latency_rollup_tables(pg_conn: Any) -> None:
    with pg_conn.cursor() as cursor:
        cursor.execute(
            'TRUNCATE TABLE "AnonymousLatencyDailyRollups" RESTART IDENTITY CASCADE'
        )
    pg_conn.commit()


def find_latency_keys(metrics_redis: Redis, metric_value: str) -> list[bytes]:
    pattern = f"{METRICS_REDIS.LATENCY_KEY_PREFIX}*:{metric_value}:*"
    return list(metrics_redis.scan_iter(match=pattern))


def build_latency_key(
    bucket_epoch: int,
    metric_value: str,
    endpoint: str,
    method: str,
    device_type: DeviceType,
) -> str:
    """Build a 7-segment latency Redis key.

    Format: ``metrics:latency:<bucket_epoch>:<metric_value>:<endpoint>:<method>:<canonical_device_dims_json>``
    where ``canonical_device_dims_json`` holds only ``device_type`` (endpoint and
    method are separate key segments, not embedded in the JSON dims).
    """
    canonical_device_dims = canonicalize_dimensions({DEVICE_TYPE_DIM_KEY: device_type})
    return (
        f"{METRICS_REDIS.LATENCY_KEY_PREFIX}{bucket_epoch}:{metric_value}:"
        f"{endpoint}:{method}:{canonical_device_dims}"
    )
