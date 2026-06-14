from __future__ import annotations

import json
from typing import Any

import psycopg2
from flask import Flask
from redis import Redis

from backend.metrics.events import EventName
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


DOMAIN_EVENTS_TESTED_ELSEWHERE: frozenset[EventName] = frozenset(
    {
        EventName.URL_ACCESSED,
        EventName.URL_ADDED_TO_UTUB,
        EventName.URL_REMOVED_FROM_UTUB,
        EventName.URL_STRING_UPDATED,
        EventName.UTUB_TAG_CREATED,
        EventName.REGISTER_SUCCESS,
        EventName.REGISTER_REJECTED,
        EventName.LOGIN_SUCCESS,
        EventName.LOGIN_FAILURE,
        EventName.EMAIL_VERIFIED,
        EventName.PASSWORD_RESET_REQUESTED,
        EventName.PASSWORD_RESET_COMPLETED,
        EventName.URL_CREATE_REJECTED,
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
tests/integration/splash/ and tests/integration/utuburls/. Each excluded event
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


def count_counter_keys(metrics_redis: Redis, event: EventName) -> int:
    return len(find_counter_keys(metrics_redis, event))


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
