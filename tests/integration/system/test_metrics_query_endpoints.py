from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, NoReturn, Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.exc import IntegrityError
from werkzeug.test import TestResponse

from backend import db
from backend.metrics import flow_counting
from backend.metrics.constants import MetricsErrorCodes, MetricsFailureMessages
from backend.metrics.events import (
    DEVICE_TYPE_DIM_KEY,
    EVENT_DESCRIPTIONS,
    DeviceType,
    EventCategory,
    EventName,
)
from backend.metrics.flow_counting import FlowCountError, count_flow
from backend.metrics.flow_invalid import first_invalid_detail
from backend.metrics.flow_validation import (
    serialize_flow_steps,
    validate_flow_payload,
)
from backend.metrics.flows import (
    FLOWS,
    FlowDefinition,
    FlowId,
    FlowStep,
    format_custom_flow_id,
)
from backend.metrics.gauges import GAUGE_REGISTRY, GaugeName
from backend.metrics.latency import LatencyMetricName
from backend.metrics.suppression import MIN_CELL_COUNT
from backend.models.anonymous_gauges import Anonymous_Gauges
from backend.models.anonymous_latency_rollups import Anonymous_Latency_Daily_Rollups
from backend.models.anonymous_latency_samples import Anonymous_Latency_Samples
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.event_registry import Event_Registry
from backend.models.metric_flows import Metric_Flows
from backend.models.users import Users
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.metric_flow_strs import (
    UNEXPECTED_FIELD_STR,
    unknown_event_message,
)
from backend.utils.strings.url_validation_strs import URL_VALIDATION

pytestmark = pytest.mark.cli

# Pydantic v2 `model_dump(mode="json")` serializes UTC datetimes as
# `YYYY-MM-DDTHH:MM:SS[.ffffff]<tz>` where `<tz>` is `Z` or `+00:00`
# depending on Pydantic minor version. The HTTP-Date (RFC 822) format
# Flask jsonify emits by default ("Sat, 06 Jun 2026 17:00:00 GMT") is the
# regression this regex guards against — either ISO-8601 spelling is fine.
_ISO_8601_UTC_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$"
)


_TOP_URL = "/api/metrics/query/top"
_TIMESERIES_URL = "/api/metrics/query/timeseries"
_SUMMARY_URL = "/api/metrics/query/summary"
_AJAX_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}


def _bucket_inside_window() -> datetime:
    """Return a UTC-aware bucket_start guaranteed to fall inside a 1-day
    lookback from `utc_now()`. We use `now - 1h` so the row sits comfortably
    inside the `day` / `week` windows the tests exercise.
    """
    return datetime.now(timezone.utc) - timedelta(hours=1)


def _seed_event_with_count(
    event_name: EventName,
    category: EventCategory,
    bucket_start: datetime,
    count: int,
    dimensions: dict | None = None,
    endpoint: str | None = None,
    method: str | None = None,
    status_code: int | None = None,
) -> None:
    """Seed one EventRegistry + AnonymousMetrics row through SQLAlchemy.

    Why ORM (not raw psycopg2): `login_admin_user_with_register` depends on
    the SAVEPOINT-based `app` fixture; raw psycopg2 writes would land outside
    the savepoint and roll back independently.

    `endpoint`/`method`/`status_code` populate the flat promoted columns the
    API-category `grouped_counts` branch matches against — `API_HIT` rows store
    these as columns, NOT as `dimensions` entries.
    """
    if Event_Registry.query.filter_by(name=event_name.value).one_or_none() is None:
        db.session.add(
            Event_Registry(
                name=event_name.value,
                category=category,
                description=EVENT_DESCRIPTIONS[event_name],
            )
        )
        db.session.flush()
    db.session.add(
        Anonymous_Metrics(
            event_name=event_name.value,
            bucket_start=bucket_start,
            dimensions=dimensions if dimensions is not None else {},
            count=count,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
        )
    )
    db.session.commit()


# ---------------------------------------------------------------------------
# Anonymous → 401 JSON envelope (NOT a 302 redirect to splash)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _TOP_URL + "?window=day",
        _TIMESERIES_URL + "?window=day&event_name=" + EventName.UTUB_OPENED.value,
        _SUMMARY_URL + "?window=day",
    ],
)
def test_query_endpoint_anonymous_returns_401_json_envelope(
    app: Flask, client: FlaskClient, url: str
) -> None:
    """
    GIVEN an anonymous client (no session)
    WHEN GETing any of the three /api/metrics/query/* endpoints
    THEN the response is 401 with a JSON failure envelope (NOT a 302 redirect
        to splash) — the metrics-admin decorator short-circuits before AJAX
        gating so the dashboard's fetch loop never follows a redirect.
    """
    response = client.get(url)

    assert response.status_code == 401
    assert response.is_json
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


# ---------------------------------------------------------------------------
# Authenticated non-admin → 404 JSON envelope
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _TOP_URL + "?window=day",
        _TIMESERIES_URL + "?window=day&event_name=" + EventName.UTUB_OPENED.value,
        _SUMMARY_URL + "?window=day",
    ],
)
def test_query_endpoint_non_admin_returns_404_json_envelope(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask], url: str
) -> None:
    """
    GIVEN a logged-in user with the default User_Role.USER
    WHEN GETing any of the three /api/metrics/query/* endpoints
    THEN the response is 404 with a JSON failure envelope (the surface is not
        advertised to non-admins).
    """
    logged_in_client, _, _, _ = login_first_user_with_register

    response = logged_in_client.get(url)

    assert response.status_code == 404
    assert response.is_json
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


# ---------------------------------------------------------------------------
# `top` — admin happy path
# ---------------------------------------------------------------------------


def test_query_top_admin_happy_path_returns_seeded_rows(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and one seeded UTUB_CREATED row inside the window
    WHEN GETing /api/metrics/query/top?window=day
    THEN the response is 200, JSON contains `events`, `window`, `window_start`,
        `window_end`, `category` aliases, and the description round-trips
        through the EventRegistry JOIN.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=5,
        )

    response = logged_in_client.get(_TOP_URL + "?window=day", headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert "events" in body
    assert "window" in body
    assert "window_start" in body
    assert "window_end" in body
    assert "category" in body
    assert body["window"] == "day"
    assert len(body["events"]) == 1
    seeded_event = body["events"][0]
    assert seeded_event["event_name"] == EventName.UTUB_CREATED.value
    assert seeded_event["total_count"] == 5
    assert seeded_event["description"] == EVENT_DESCRIPTIONS[EventName.UTUB_CREATED]
    assert seeded_event["previous_count"] == 0


# ---------------------------------------------------------------------------
# `timeseries` — admin happy path
# ---------------------------------------------------------------------------


def test_query_timeseries_admin_happy_path_returns_seeded_buckets(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and one seeded UTUB_CREATED row inside the window
    WHEN GETing /api/metrics/query/timeseries?window=day&event_name=<valid>
        &resolution=hour
    THEN the response is 200, JSON contains the full timeseries envelope
        (`event_name`, `window`, `resolution`, `window_start`, `window_end`,
        `buckets`) and at least one bucket reflects the seeded row's count.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=3,
        )

    url = (
        _TIMESERIES_URL
        + "?window=day&event_name="
        + EventName.UTUB_CREATED.value
        + "&resolution=hour"
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert "event_name" in body
    assert "window" in body
    assert "resolution" in body
    assert "window_start" in body
    assert "window_end" in body
    assert "buckets" in body
    assert body["event_name"] == EventName.UTUB_CREATED.value
    assert body["window"] == "day"
    assert body["resolution"] == "hour"
    assert isinstance(body["buckets"], list)
    assert len(body["buckets"]) >= 1
    assert sum(bucket["count"] for bucket in body["buckets"]) == 3


@pytest.mark.parametrize("requested", ["hour", "day"])
def test_query_timeseries_daily_event_echoes_day_resolution(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    requested: str,
) -> None:
    """
    GIVEN an admin client and a daily-stored event (UTUB_OPENED)
    WHEN GETing timeseries over a week with resolution=<requested>
    THEN the response echoes resolution "day" with exactly seven zero-filled
        midnight-UTC buckets ending at yesterday.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    url = (
        f"{_TIMESERIES_URL}?window=week&event_name={EventName.UTUB_OPENED.value}"
        f"&resolution={requested}"
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["resolution"] == "day"
    assert len(body["buckets"]) == 7
    bucket_starts = [_parse_iso(bucket["bucket"]) for bucket in body["buckets"]]
    # Compare against the route's own window_end (floored) so a run straddling
    # 00:00 UTC cannot disagree with the server's notion of "now".
    last_complete_day = _parse_iso(body["window_end"]).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    assert bucket_starts[-1] == last_complete_day
    assert all(
        bucket_start.hour == 0 and bucket_start.minute == 0
        for bucket_start in bucket_starts
    )
    assert all(
        later - earlier == timedelta(days=1)
        for earlier, later in zip(bucket_starts, bucket_starts[1:])
    )


def test_query_timeseries_daily_event_day_window_returns_one_bucket(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and a daily-stored event
    WHEN GETing timeseries with window=day
    THEN exactly one (yesterday's) bucket is returned.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    url = f"{_TIMESERIES_URL}?window=day&event_name={EventName.UTUB_OPENED.value}"
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["resolution"] == "day"
    assert len(body["buckets"]) == 1


def test_query_timeseries_daily_event_counts_seeded_midnight_row(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and a midnight-UTC UTUB_OPENED row for yesterday
    WHEN GETing timeseries with window=day
    THEN the single day bucket is keyed at yesterday's UTC midnight and
        carries the seeded count.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    yesterday = utc_now().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_OPENED,
            category=EventCategory.DOMAIN,
            bucket_start=yesterday,
            count=4,
        )

    url = f"{_TIMESERIES_URL}?window=day&event_name={EventName.UTUB_OPENED.value}"
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["resolution"] == "day"
    assert [
        (_parse_iso(bucket["bucket"]), bucket["count"]) for bucket in body["buckets"]
    ] == [(yesterday, 4)]


def test_query_timeseries_hourly_event_echoes_hour_resolution(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and an hourly event (UTUB_CREATED)
    WHEN GETing timeseries with resolution=hour
    THEN the response echoes resolution "hour".
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    url = (
        f"{_TIMESERIES_URL}?window=day&event_name={EventName.UTUB_CREATED.value}"
        "&resolution=hour"
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    assert response.get_json()["resolution"] == "hour"


# ---------------------------------------------------------------------------
# Bad window 400 — shared envelope across all three query endpoints
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _TOP_URL + "?window=bogus",
        _TIMESERIES_URL + "?window=bogus&event_name=" + EventName.UTUB_OPENED.value,
        _SUMMARY_URL + "?window=bogus",
    ],
)
def test_query_endpoint_bad_window_returns_400_with_field_error(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url: str,
) -> None:
    """
    GIVEN an admin client
    WHEN GETing any of the three /api/metrics/query/* endpoints with
        window=bogus
    THEN the response is 400 with error_code=INVALID_QUERY_PARAM and the
        field errors map contains a "window" key — guards the shared
        `parse_query_args` + `parse_window(ValueError → 400)` code path
        across `top`, `timeseries`, and `summary`.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "window" in body[STD_JSON.ERRORS]


# ---------------------------------------------------------------------------
# `top` — 400 on extra query param (extra="forbid")
# ---------------------------------------------------------------------------


def test_query_top_extra_query_param_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/top with an unknown query param
    THEN the response is 400 (TopEventsQuerySchema.model_config has
        `extra="forbid"`).
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _TOP_URL + "?window=day&foo=bar", headers=_AJAX_HEADERS
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


# ---------------------------------------------------------------------------
# `timeseries` — 400 on missing event_name
# ---------------------------------------------------------------------------


def test_query_timeseries_missing_event_name_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/timeseries?window=day (missing event_name)
    THEN the response is 400 — TimeseriesQuerySchema requires event_name.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _TIMESERIES_URL + "?window=day", headers=_AJAX_HEADERS
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert "event_name" in body[STD_JSON.ERRORS]


# ---------------------------------------------------------------------------
# `summary` — admin happy path
# ---------------------------------------------------------------------------


def test_query_summary_admin_happy_path_returns_by_category_list(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and seeded rows in both the current and previous
        window for category=domain
    WHEN GETing /api/metrics/query/summary?window=day
    THEN the response is 200 and `by_category` is a list of
        {category, current, previous} objects with the domain row reflecting
        the seeded sums.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        current_bucket = _bucket_inside_window()
        previous_bucket = current_bucket - timedelta(days=1)
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=current_bucket,
            count=10,
        )
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=previous_bucket,
            count=4,
        )

    response = logged_in_client.get(_SUMMARY_URL + "?window=day", headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert "by_category" in body
    assert isinstance(body["by_category"], list)
    domain_row = next(
        (
            row
            for row in body["by_category"]
            if row["category"] == EventCategory.DOMAIN.value
        ),
        None,
    )
    assert domain_row is not None
    assert domain_row["current"] == 10
    assert domain_row["previous"] == 4
    assert "last_flush_at" in body
    last_flush_at_value = body["last_flush_at"]
    assert last_flush_at_value is None or _ISO_8601_UTC_REGEX.match(last_flush_at_value)
    assert "last_event_at" in body
    last_event_at_value = body["last_event_at"]
    assert last_event_at_value is None or _ISO_8601_UTC_REGEX.match(last_event_at_value)


# ---------------------------------------------------------------------------
# Admin missing X-Requested-With → 302 redirect to /home
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _TOP_URL + "?window=day",
        _TIMESERIES_URL + "?window=day&event_name=" + EventName.UTUB_CREATED.value,
        _SUMMARY_URL + "?window=day",
    ],
)
def test_query_endpoint_admin_missing_ajax_header_redirects_to_home(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url: str,
) -> None:
    """
    GIVEN an admin client
    WHEN GETing any /api/metrics/query/* endpoint WITHOUT X-Requested-With
    THEN the response is a 302 redirect to /home — the `ajax_required=True`
        gate fires AFTER `@admin_required` admits the admin user.

    Suppress the auto-injected AJAX header by passing the key with an empty
    value (`AjaxFlaskLoginClient.open` skips injection only when the key is
    already present, regardless of value).
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(url, headers={URL_VALIDATION.X_REQUESTED_WITH: ""})

    assert response.status_code == 302
    assert response.location.endswith("/home")


# ---------------------------------------------------------------------------
# Absolute (`start`, `end`) range — admin happy paths across all three endpoints
# ---------------------------------------------------------------------------


def _absolute_range_around(bucket: datetime) -> tuple[str, str]:
    """Return a `(start_iso, end_iso)` tuple that brackets `bucket` by ±1h.

    Returns `Z`-suffixed ISO strings so they pass through Flask's query-string
    parsing without URL-encoding the `+` in `+00:00`. Pydantic v2 datetime
    fields accept both `Z` and `+HH:MM` offsets.
    """
    start = (bucket - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (bucket + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return start, end


def test_query_top_absolute_range_returns_seeded_rows(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and one seeded row inside an absolute (start, end)
    WHEN GETing /api/metrics/query/top?start=...&end=...
    THEN the response is 200, `window` echoes null (no named window supplied),
        and the seeded row is returned with the absolute bounds reflected in
        `window_start`/`window_end`.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        bucket = _bucket_inside_window()
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=bucket,
            count=7,
        )
    start_iso, end_iso = _absolute_range_around(bucket)

    url = f"{_TOP_URL}?start={start_iso}&end={end_iso}"
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["window"] is None
    assert len(body["events"]) == 1
    assert body["events"][0]["total_count"] == 7


def test_query_timeseries_absolute_range_returns_seeded_buckets(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and one seeded UTUB_CREATED row inside an absolute range
    WHEN GETing /api/metrics/query/timeseries?event_name=...&start=...&end=...
    THEN the response is 200, `window` is null, and the bucket count matches.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        bucket = _bucket_inside_window()
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=bucket,
            count=4,
        )
    start_iso, end_iso = _absolute_range_around(bucket)

    url = (
        f"{_TIMESERIES_URL}?event_name={EventName.UTUB_CREATED.value}"
        f"&start={start_iso}&end={end_iso}&resolution=hour"
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["window"] is None
    assert body["resolution"] == "hour"
    assert sum(bucket["count"] for bucket in body["buckets"]) == 4


def test_query_summary_absolute_range_returns_by_category_list(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and seeded rows inside an absolute range
    WHEN GETing /api/metrics/query/summary?start=...&end=...
    THEN the response is 200, `window` is null, `previous_window_start` /
        `previous_window_end` reflect the equal-length preceding interval,
        and the domain category sum matches the seeded count.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        bucket = _bucket_inside_window()
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=bucket,
            count=11,
        )
    start_iso, end_iso = _absolute_range_around(bucket)

    url = f"{_SUMMARY_URL}?start={start_iso}&end={end_iso}"
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["window"] is None
    assert "previous_window_start" in body
    assert "previous_window_end" in body
    domain_row = next(
        (
            row
            for row in body["by_category"]
            if row["category"] == EventCategory.DOMAIN.value
        ),
        None,
    )
    assert domain_row is not None
    assert domain_row["current"] == 11


# ---------------------------------------------------------------------------
# Absolute-range sad paths — shared XOR validator failures across endpoints
# ---------------------------------------------------------------------------


_ABS_START_QUERY: str = "start=2026-01-01T00:00:00Z"
_ABS_END_QUERY: str = "end=2026-02-01T00:00:00Z"
_ABS_REVERSED_QUERY: str = "start=2026-02-01T00:00:00Z&end=2026-01-01T00:00:00Z"


def _admin_get(logged_in_client: FlaskClient, base_url: str, query: str):
    return logged_in_client.get(f"{base_url}?{query}", headers=_AJAX_HEADERS)


@pytest.mark.parametrize(
    "base_url,extra_required",
    [
        (_TOP_URL, ""),
        (_TIMESERIES_URL, f"&event_name={EventName.UTUB_CREATED.value}"),
        (_SUMMARY_URL, ""),
    ],
    ids=["top", "timeseries", "summary"],
)
@pytest.mark.parametrize(
    "bad_query",
    [
        # Both `window` and absolute range supplied
        f"window=day&{_ABS_START_QUERY}&{_ABS_END_QUERY}",
        # Partial range: start without end
        _ABS_START_QUERY,
        # Partial range: end without start
        _ABS_END_QUERY,
        # Neither window nor range
        "",
        # Reversed range (start > end)
        _ABS_REVERSED_QUERY,
    ],
    ids=[
        "window_and_range_together",
        "start_without_end",
        "end_without_start",
        "neither_window_nor_range",
        "reversed_range",
    ],
)
def test_query_endpoint_absolute_range_xor_failures_return_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    base_url: str,
    extra_required: str,
    bad_query: str,
) -> None:
    """
    GIVEN an admin client
    WHEN GETing any of the three /api/metrics/query/* endpoints with an
        invalid combination of `window` / `start` / `end`
    THEN the response is 400 with `error_code=INVALID_QUERY_PARAM` and the
        field-errors map contains the model-level `__root__` entry produced
        by the shared `_validate_window_xor_range` validator.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    # `extra_required` is empty for endpoints without additional required
    # fields; for timeseries it injects the mandatory event_name so the
    # 400 we observe is unambiguously the XOR failure, not a missing field.
    query = bad_query + extra_required if bad_query else extra_required.lstrip("&")

    response = _admin_get(logged_in_client, base_url, query)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    # Either the model-level XOR validator (loc=()) or the field-level
    # `event_name` failure for the timeseries empty-query case lands here;
    # the assertion only requires that there's at least one error field.
    assert body[STD_JSON.ERRORS]


# ---------------------------------------------------------------------------
# Wire format: window_start / window_end serialize as ISO-8601 with UTC offset
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _TOP_URL + "?window=day",
        _TIMESERIES_URL + "?window=day&event_name=" + EventName.UTUB_OPENED.value,
        _SUMMARY_URL + "?window=day",
    ],
    ids=["top", "timeseries", "summary"],
)
def test_query_endpoint_datetime_fields_serialize_as_iso_8601(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url: str,
) -> None:
    """
    GIVEN an admin client requesting any /api/metrics/query/* endpoint
    WHEN the response JSON is decoded
    THEN `window_start` and `window_end` are ISO-8601 strings with a
        `+00:00` UTC offset, NOT Flask's default HTTP-Date (RFC 822) format
        (which would look like "Sat, 06 Jun 2026 16:00:00 GMT"). This is
        the wire-format contract that lets TypeScript consumers `new Date`
        the value AND parse it against an ISO regex.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert _ISO_8601_UTC_REGEX.match(body["window_start"]), body["window_start"]
    assert _ISO_8601_UTC_REGEX.match(body["window_end"]), body["window_end"]


# ---------------------------------------------------------------------------
# `top` — `resource` filter cross-validation against `category`
# ---------------------------------------------------------------------------


def test_query_top_resource_without_category_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/top?window=day&resource=utub (no category)
    THEN the response is 400 with `error_code=INVALID_QUERY_PARAM` — resource
        without category is ambiguous because the SQL target column depends
        on the category (event_name for UI/Domain, endpoint for API).
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _TOP_URL + "?window=day&resource=utub", headers=_AJAX_HEADERS
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)


def test_query_top_resource_invalid_for_category_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/top?window=day&category=domain&resource=form
        (`form` does not appear in `RESOURCE_BY_CATEGORY[DOMAIN]` — domain
        covers utub, url, tag, member, auth, and search only)
    THEN the response is 400 with `error_code=INVALID_QUERY_PARAM` — the
        model_validator rejects pairs not listed in `RESOURCE_BY_CATEGORY`.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _TOP_URL + "?window=day&category=domain&resource=form",
        headers=_AJAX_HEADERS,
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)


def test_query_top_resource_with_valid_category_returns_200(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and one seeded UTUB_CREATED row inside the window
    WHEN GETing /api/metrics/query/top?window=day&category=domain&resource=utub
    THEN the response is 200, the seeded UTub row is returned, and the
        response echoes both `category` and `resource` query params.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=3,
        )

    response = logged_in_client.get(
        _TOP_URL + "?window=day&category=domain&resource=utub",
        headers=_AJAX_HEADERS,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["category"] == EventCategory.DOMAIN.value
    assert body["resource"] == "utub"
    assert len(body["events"]) == 1
    assert body["events"][0]["event_name"] == EventName.UTUB_CREATED.value


# ---------------------------------------------------------------------------
# `top` / `timeseries` — device_type query-param threading
# ---------------------------------------------------------------------------


def test_query_top_device_type_one_returns_mobile_only_200(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and three seeded UI rows: two with device_type=1
        (mobile) and one with device_type=2 (desktop), all inside the window
    WHEN GETing /api/metrics/query/top?window=day&category=ui&device_type=1
    THEN the response is 200 and only the two mobile rows are returned —
        proves `device_type` is threaded from the query schema into
        `query_service.top_events(...)` and applied as a JSONB filter.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_UTUB_SELECT,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=5,
            dimensions={"device_type": 1, "search_active": "false"},
        )
        _seed_event_with_count(
            event_name=EventName.UI_TAG_CREATE_OPEN,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=2,
            dimensions={"device_type": 1},
        )
        _seed_event_with_count(
            event_name=EventName.UI_UTUB_CREATE_OPEN,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=4,
            dimensions={"device_type": 2},
        )

    response = logged_in_client.get(
        _TOP_URL + "?window=day&category=ui&device_type=1",
        headers=_AJAX_HEADERS,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert len(body["events"]) == 2
    returned_event_names = {row["event_name"] for row in body["events"]}
    assert returned_event_names == {
        EventName.UI_UTUB_SELECT.value,
        EventName.UI_TAG_CREATE_OPEN.value,
    }


def test_query_top_device_type_invalid_value_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/top?window=day&device_type=3
    THEN the response is 400 with `error_code=INVALID_QUERY_PARAM` — the
        schema's `Literal[1, 2]` rejects any value outside {1, 2}.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _TOP_URL + "?window=day&device_type=3", headers=_AJAX_HEADERS
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)


def test_query_top_extra_unknown_query_param_still_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/top with a typo'd device-filter param
        (`device_typo=1`)
    THEN the response is 400 — proves `extra="forbid"` still rejects unknown
        keys even after the schema gained the new `device_type` field.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _TOP_URL + "?window=day&device_typo=1", headers=_AJAX_HEADERS
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_query_timeseries_device_type_one_returns_filtered_buckets_200(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and two seeded UTUB_CREATED rows inside the window:
        one with device_type=1 (mobile, count=3) and one with device_type=2
        (desktop, count=7)
    WHEN GETing /api/metrics/query/timeseries?window=day&event_name=...
        &device_type=1
    THEN the response is 200 and the bucket counts sum to 3 (only the mobile
        row) — proves `device_type` is threaded into
        `query_service.timeseries(...)`.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=3,
            dimensions={"device_type": 1},
        )
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=7,
            dimensions={"device_type": 2},
        )

    url = (
        _TIMESERIES_URL
        + "?window=day&event_name="
        + EventName.UTUB_CREATED.value
        + "&resolution=hour&device_type=1"
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["event_name"] == EventName.UTUB_CREATED.value
    assert isinstance(body["buckets"], list)
    assert sum(bucket["count"] for bucket in body["buckets"]) == 3


# ---------------------------------------------------------------------------
# `grouped-timeseries` — admin gating + window-XOR + bad group_by key + happy
# ---------------------------------------------------------------------------


_GROUPED_TIMESERIES_URL = "/api/metrics/query/grouped-timeseries"
# The only registered `group_by` projection for the ingest-batch event.
_PIPELINE_HEALTH_GROUP_BY = ["batch_size_bucket", "transport", "device_type"]
_INGEST_BATCH_EVENT: str = EventName.API_METRICS_INGEST_BATCH.value


def _grouped_url_for(
    event_name: str,
    *,
    group_by: list[str],
    window: str = "day",
) -> str:
    """Build a grouped-timeseries URL with repeated `group_by` keys.

    Matches the wire format `parse_query_args(..., multi_value_keys=...)`
    expects (one `group_by=<dim>` occurrence per dimension).
    """
    encoded_group_by = "&".join(f"group_by={key}" for key in group_by)
    return (
        f"{_GROUPED_TIMESERIES_URL}?window={window}"
        f"&event_name={event_name}&{encoded_group_by}"
    )


def test_grouped_timeseries_anonymous_returns_401(
    app: Flask, client: FlaskClient
) -> None:
    """
    GIVEN an anonymous client (no session)
    WHEN GETing /api/metrics/query/grouped-timeseries
    THEN the response is 401 with a JSON failure envelope (NOT a 302 redirect
        to splash) — mirrors the other admin-only query endpoints.
    """
    grouped_url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=["transport"])

    response = client.get(grouped_url)

    assert response.status_code == 401
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_grouped_timeseries_non_admin_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in user with the default User_Role.USER
    WHEN GETing /api/metrics/query/grouped-timeseries
    THEN the response is 404 with a JSON failure envelope (the surface is not
        advertised to non-admins) — matches the other @admin_required query
        endpoints; intentionally NOT 403.
    """
    logged_in_client, _, _, _ = login_first_user_with_register
    grouped_url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=["transport"])

    response = logged_in_client.get(grouped_url)

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_grouped_timeseries_window_xor_enforced(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/grouped-timeseries with both `window` and
        `start` supplied
    THEN the response is 400 with `error_code=INVALID_QUERY_PARAM` — the
        shared `_validate_window_xor_range` validator rejects the combo.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = (
        f"{_GROUPED_TIMESERIES_URL}?window=day&start=2026-01-01T00:00:00Z"
        f"&event_name={_INGEST_BATCH_EVENT}&group_by=transport"
    )

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)


def test_grouped_timeseries_rejects_unknown_group_by_key(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/grouped-timeseries with
        `group_by=nonexistent_dim` against an event that has no such dim
    THEN the response is 400 — `grouped_timeseries()` raises ValueError when
        a group_by entry isn't in `DIMENSION_MODELS[event].model_fields`, and
        the route handler catches it as a field-level 400.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=["nonexistent_dim"])

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "group_by" in body[STD_JSON.ERRORS]


def test_grouped_timeseries_rejects_group_by_entry_over_64_chars(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/grouped-timeseries with a `group_by` entry
        longer than 64 characters
    THEN the response is 400 with `error_code=INVALID_QUERY_PARAM` — the
        `_check_group_by_entry_shape` model validator rejects any entry whose
        length exceeds the 64-char ceiling before the route handler runs.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    over_limit_entry = "x" * 65
    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=[over_limit_entry])

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)


def test_grouped_timeseries_rejects_empty_group_by_entry(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/grouped-timeseries with an empty-string
        `group_by` entry
    THEN the response is 400 with `error_code=INVALID_QUERY_PARAM` — the
        `_check_group_by_entry_shape` model validator rejects an empty entry
        before the route handler runs.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=[""])

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)


def test_grouped_timeseries_returns_one_row_per_dim_tuple(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and three seeded API_METRICS_INGEST_BATCH rows
        spanning (transport=fetch, device_type=2), (transport=beacon,
        device_type=2), (transport=beacon, device_type=1) inside the window
    WHEN GETing /api/metrics/query/grouped-timeseries
        ?event_name=api_metrics_ingest_batch&group_by=transport&group_by=device_type
    THEN the response is 200 with one bucket entry per unique
        `(bucket, transport, device_type)` tuple, each carrying its correct
        count.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    bucket_inside = _bucket_inside_window()
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.API_METRICS_INGEST_BATCH,
            category=EventCategory.API,
            bucket_start=bucket_inside,
            count=9,
            dimensions={
                "batch_size_bucket": "1",
                "transport": "fetch",
                "device_type": 2,
            },
        )
        _seed_event_with_count(
            event_name=EventName.API_METRICS_INGEST_BATCH,
            category=EventCategory.API,
            bucket_start=bucket_inside,
            count=7,
            dimensions={
                "batch_size_bucket": "2-5",
                "transport": "beacon",
                "device_type": 2,
            },
        )
        _seed_event_with_count(
            event_name=EventName.API_METRICS_INGEST_BATCH,
            category=EventCategory.API,
            bucket_start=bucket_inside,
            count=6,
            dimensions={
                "batch_size_bucket": "1",
                "transport": "beacon",
                "device_type": 1,
            },
        )

    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=_PIPELINE_HEALTH_GROUP_BY)
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["event_name"] == _INGEST_BATCH_EVENT
    assert body["group_by"] == _PIPELINE_HEALTH_GROUP_BY
    assert body["resolution"] == "hour"
    assert body["window"] == "day"
    rows_by_dim_tuple = {
        (row["dimensions"]["transport"], row["dimensions"]["device_type"]): row["count"]
        for row in body["buckets"]
    }
    assert rows_by_dim_tuple == {
        ("fetch", 2): 9,
        ("beacon", 2): 7,
        ("beacon", 1): 6,
    }


def test_grouped_timeseries_does_not_zero_fill_missing_dim_combos(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and a single seeded API_METRICS_INGEST_BATCH row
        spanning one (transport, device_type) combination
    WHEN GETing /api/metrics/query/grouped-timeseries
        ?event_name=api_metrics_ingest_batch&group_by=transport&group_by=device_type
    THEN the response contains ONLY the one seeded `(bucket, dim-tuple)` row —
        unlike `query_timeseries`, the grouped variant deliberately does NOT
        zero-fill the cross-product of buckets × dim values (frontend handles
        missing combos as "no segment for that bucket").
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.API_METRICS_INGEST_BATCH,
            category=EventCategory.API,
            bucket_start=_bucket_inside_window(),
            count=5,
            dimensions={
                "batch_size_bucket": "1",
                "transport": "fetch",
                "device_type": 2,
            },
        )

    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=_PIPELINE_HEALTH_GROUP_BY)
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    # Exactly one row — no zero-fill for the absent (transport, device_type)
    # combinations that would appear if the grouped variant followed the
    # `timeseries` zero-fill policy.
    assert len(body["buckets"]) == 1
    only_row = body["buckets"][0]
    assert only_row["dimensions"] == {
        "batch_size_bucket": "1",
        "transport": "fetch",
        "device_type": 2,
    }
    assert only_row["count"] == 5


def _seed_ingest_batch(
    *,
    bucket_start: datetime,
    count: int,
    transport: str = "fetch",
    batch_size_bucket: str = "1",
) -> None:
    _seed_event_with_count(
        event_name=EventName.API_METRICS_INGEST_BATCH,
        category=EventCategory.API,
        bucket_start=bucket_start,
        count=count,
        dimensions={
            "batch_size_bucket": batch_size_bucket,
            "transport": transport,
            "device_type": 2,
        },
    )


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _two_hour_aligned_buckets() -> tuple[datetime, datetime]:
    first = datetime.now(timezone.utc).replace(
        minute=0, second=0, microsecond=0
    ) - timedelta(hours=3)
    return first, first + timedelta(hours=1)


def test_grouped_timeseries_sub_floor_tuple_is_returned_as_sentinel(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN API_METRICS_INGEST_BATCH rows with counts 4 (fetch), 5 (beacon) and
        9 (beacon, a different batch_size_bucket)
    WHEN GETing grouped-timeseries grouped by transport and device_type
    THEN the 4-count tuple appears only as the sentinel row (real device_type
        kept); the sentinel is below the floor so the smallest kept tuple
        (beacon, 5) is folded in (total 9); the 9-count tuple is verbatim; and
        no raw `fetch` dim leaks.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    bucket = _two_hour_aligned_buckets()[0]
    with app.app_context():
        _seed_ingest_batch(bucket_start=bucket, count=4, transport="fetch")
        _seed_ingest_batch(bucket_start=bucket, count=5, transport="beacon")
        _seed_ingest_batch(
            bucket_start=bucket, count=9, transport="beacon", batch_size_bucket="2-5"
        )

    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=_PIPELINE_HEALTH_GROUP_BY)
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    rows = response.get_json()["buckets"]
    assert [(row["dimensions"], row["count"]) for row in rows] == [
        ({"batch_size_bucket": "2-5", "transport": "beacon", "device_type": 2}, 9),
        (
            {
                "batch_size_bucket": "suppressed",
                "transport": "suppressed",
                "device_type": 2,
            },
            9,
        ),
    ]
    assert "fetch" not in response.get_data(as_text=True).split('"buckets"')[1]


def test_grouped_timeseries_partition_by_bucket_false_sums_window_wide(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a tuple at 3 in each of two buckets (total 6) and another at 2+2
    WHEN GETing with partition_by_bucket=false vs the default
    THEN false returns one sentinel of 10: the 2+2 tuple (4) is below the floor,
        so secondary suppression folds in the smallest kept tuple (6); the sum
        is preserved. The default returns only sentinel rows.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    first_bucket, second_bucket = _two_hour_aligned_buckets()
    with app.app_context():
        for bucket in (first_bucket, second_bucket):
            _seed_ingest_batch(bucket_start=bucket, count=3, transport="fetch")
        for bucket in (first_bucket, second_bucket):
            _seed_ingest_batch(bucket_start=bucket, count=2, transport="beacon")

    base_url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=_PIPELINE_HEALTH_GROUP_BY)
    collapsed = logged_in_client.get(
        f"{base_url}&partition_by_bucket=false", headers=_AJAX_HEADERS
    )
    assert collapsed.status_code == 200
    collapsed_body = collapsed.get_json()
    assert [
        (row["dimensions"]["transport"], row["count"])
        for row in collapsed_body["buckets"]
    ] == [("suppressed", 10)]
    window_start = _parse_iso(collapsed_body["window_start"])
    expected_bucket = window_start.replace(minute=0, second=0, microsecond=0)
    assert {_parse_iso(row["bucket"]) for row in collapsed_body["buckets"]} == {
        expected_bucket
    }

    for default_url in (base_url, f"{base_url}&partition_by_bucket=true"):
        default_response = logged_in_client.get(default_url, headers=_AJAX_HEADERS)
        default_rows = default_response.get_json()["buckets"]
        assert len(default_rows) == 2
        assert {row["dimensions"]["transport"] for row in default_rows} == {
            "suppressed"
        }
        assert [row["count"] for row in default_rows] == [10 - 5, 5]


def test_grouped_timeseries_partition_by_bucket_false_day_resolution_bucket(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a seeded tuple and partition_by_bucket=false with resolution=day
    THEN every row's bucket is the window start truncated to the day.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_ingest_batch(bucket_start=_two_hour_aligned_buckets()[0], count=6)

    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=_PIPELINE_HEALTH_GROUP_BY)
    response = logged_in_client.get(
        f"{url}&partition_by_bucket=false&resolution=day", headers=_AJAX_HEADERS
    )
    assert response.status_code == 200
    body = response.get_json()
    window_start = _parse_iso(body["window_start"])
    expected_bucket = window_start.replace(hour=0, minute=0, second=0, microsecond=0)
    assert body["buckets"]
    assert {_parse_iso(row["bucket"]) for row in body["buckets"]} == {expected_bucket}


def test_grouped_timeseries_partition_by_bucket_invalid_value_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a partition_by_bucket value outside pydantic's boolean spellings
    THEN the response is 400 with errors.partition_by_bucket.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=["transport"])
    response = logged_in_client.get(
        f"{url}&partition_by_bucket=maybe", headers=_AJAX_HEADERS
    )
    assert response.status_code == 400
    assert "partition_by_bucket" in response.get_json()["errors"]


def test_grouped_timeseries_allowed_projection_any_order_returns_200(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the registered Pipeline Health projection
    WHEN requested in a different key order
    THEN the response is 200 (comparison is by exact set).
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = _grouped_url_for(
        _INGEST_BATCH_EVENT,
        group_by=["device_type", "batch_size_bucket", "transport"],
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)
    assert response.status_code == 200


@pytest.mark.parametrize(
    "event_name,group_by",
    [
        # strict subsets of the registered set
        (_INGEST_BATCH_EVENT, ["transport"]),
        (_INGEST_BATCH_EVENT, ["transport", "device_type"]),
        (_INGEST_BATCH_EVENT, ["device_type"]),
        # event with no registered projection at all
        (EventName.UI_URL_ACCESS.value, ["device_type"]),
        # registered event, declared-but-unregistered dim
        (EventName.UI_FORM_CANCEL.value, ["form"]),
        # UTUB_OPENED: the pair and the device split are not registered
        (EventName.UTUB_OPENED.value, ["url_count_bucket", "age_bucket"]),
        (EventName.UTUB_OPENED.value, ["device_type"]),
    ],
)
def test_grouped_timeseries_unregistered_projection_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    event_name: str,
    group_by: list[str],
) -> None:
    """
    GIVEN a group_by that is not an exact registered projection for the event
    WHEN GETing grouped-timeseries
    THEN the response is 400 INVALID_QUERY_PARAM with errors.group_by.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = _grouped_url_for(event_name, group_by=group_by)
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)
    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "not an allowed projection" in str(body[STD_JSON.ERRORS]["group_by"])


def _seed_utub_opened_yesterday(
    app: Flask, *, count: int, url_count_bucket: str, age_bucket: str = "0-6d"
) -> None:
    yesterday = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_OPENED,
            category=EventCategory.DOMAIN,
            bucket_start=yesterday,
            count=count,
            dimensions={
                "url_count_bucket": url_count_bucket,
                "age_bucket": age_bucket,
                "device_type": 2,
            },
        )


@pytest.mark.parametrize("requested", ["hour", "day"])
@pytest.mark.parametrize("group_by_key", ["url_count_bucket", "age_bucket"])
def test_grouped_timeseries_daily_event_echoes_day_resolution(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    requested: str,
    group_by_key: str,
) -> None:
    """
    GIVEN a UTUB_OPENED cell at exactly the floor yesterday
    WHEN GETing grouped-timeseries by a bucket dim at `hour` or `day`
    THEN the response is 200, reports resolution "day" and the real label.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    _seed_utub_opened_yesterday(app, count=MIN_CELL_COUNT, url_count_bucket="6-20")

    url = (
        _grouped_url_for(
            EventName.UTUB_OPENED.value, group_by=[group_by_key], window="week"
        )
        + f"&resolution={requested}"
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["resolution"] == "day"
    assert [row["count"] for row in body["buckets"]] == [MIN_CELL_COUNT]


def test_grouped_timeseries_utub_opened_sub_floor_cell_is_sentinel(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a UTUB_OPENED size cell of MIN_CELL_COUNT - 1
    WHEN GETing grouped-timeseries by url_count_bucket
    THEN only the sentinel appears and the real label never leaks.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    _seed_utub_opened_yesterday(app, count=MIN_CELL_COUNT - 1, url_count_bucket="51+")

    url = _grouped_url_for(
        EventName.UTUB_OPENED.value, group_by=["url_count_bucket"], window="week"
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    rows = response.get_json()["buckets"]
    assert [(row["dimensions"], row["count"]) for row in rows] == [
        ({"url_count_bucket": "suppressed"}, MIN_CELL_COUNT - 1)
    ]
    assert "51+" not in response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# `flow` — admin gating + window-XOR + unknown flow_id + filter-field 400 +
# seeded happy path + pct_of_top edge cases + DD-6 null-breakdown paths
# ---------------------------------------------------------------------------


_FLOW_URL = "/api/metrics/query/flow"
_ADD_URL_FLOW: str = FlowId.ADD_URL_TO_UTUB.value
_CREATE_UTUB_FLOW: str = FlowId.CREATE_UTUB.value


def _flow_url(flow_id: str, *, window: str = "day") -> str:
    return f"{_FLOW_URL}?flow_id={flow_id}&window={window}"


def _seed_add_url_flow(bucket_start: datetime, *, with_rejections: bool) -> None:
    """Seed the four ADD_URL_TO_UTUB steps + an optional rejection breakdown.

    Counts are intentionally distinct so step-to-step mapping is unambiguous:
        step0 UI_URL_CREATE_OPEN  = 10  (funnel top / denominator)
        step1 UI_FORM_SUBMIT      = 8   (form=url_create)
        step2 API_HIT POST        = 7   (urls.create_url)
        step3 URL_ADDED_TO_UTUB   = 6
    When `with_rejections` is True, two URL_CREATE_REJECTED rows seed the
    step3 drop_breakdown (invalid_url=6, url_already_in_utub=5; both at or
    above the small-cell floor so they are returned verbatim).
    """
    _seed_event_with_count(
        event_name=EventName.UI_URL_CREATE_OPEN,
        category=EventCategory.UI,
        bucket_start=bucket_start,
        count=10,
        dimensions={"device_type": 2},
    )
    _seed_event_with_count(
        event_name=EventName.UI_FORM_SUBMIT,
        category=EventCategory.UI,
        bucket_start=bucket_start,
        count=8,
        dimensions={"trigger": "button_click", "form": "url_create", "device_type": 2},
    )
    _seed_event_with_count(
        event_name=EventName.API_HIT,
        category=EventCategory.API,
        bucket_start=bucket_start,
        count=7,
        endpoint="urls.create_url",
        method="POST",
        status_code=201,
    )
    _seed_event_with_count(
        event_name=EventName.URL_ADDED_TO_UTUB,
        category=EventCategory.DOMAIN,
        bucket_start=bucket_start,
        count=6,
        dimensions={"device_type": 2},
    )
    if with_rejections:
        _seed_event_with_count(
            event_name=EventName.URL_CREATE_REJECTED,
            category=EventCategory.DOMAIN,
            bucket_start=bucket_start,
            count=6,
            dimensions={"reason": "invalid_url", "device_type": 2},
        )
        _seed_event_with_count(
            event_name=EventName.URL_CREATE_REJECTED,
            category=EventCategory.DOMAIN,
            bucket_start=bucket_start,
            count=5,
            dimensions={"reason": "url_already_in_utub", "device_type": 2},
        )


@pytest.mark.parametrize("flow_id", [_ADD_URL_FLOW, "custom_1"])
def test_flow_anonymous_returns_401(
    app: Flask, client: FlaskClient, flow_id: str
) -> None:
    """
    GIVEN an anonymous client (no session)
    WHEN GETing /api/metrics/query/flow (built-in or custom id)
    THEN the response is 401 with a JSON failure envelope (NOT a 302 redirect),
        before any row lookup.
    """
    response = client.get(_flow_url(flow_id))

    assert response.status_code == 401
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


@pytest.mark.parametrize("flow_id", [_ADD_URL_FLOW, "custom_1"])
def test_flow_non_admin_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    flow_id: str,
) -> None:
    """
    GIVEN a logged-in user with the default User_Role.USER
    WHEN GETing /api/metrics/query/flow (built-in or custom id)
    THEN the response is 404 with a JSON failure envelope (not advertised to
        non-admins) — matches the other @admin_required query endpoints.
    """
    logged_in_client, _, _, _ = login_first_user_with_register

    response = logged_in_client.get(_flow_url(flow_id))

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_flow_admin_missing_ajax_header_redirects_to_home(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/flow WITHOUT X-Requested-With
    THEN the response is a 302 redirect to /home — `ajax_required=True` fires
        after @admin_required admits the admin user.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _flow_url(_ADD_URL_FLOW), headers={URL_VALIDATION.X_REQUESTED_WITH: ""}
    )

    assert response.status_code == 302
    assert response.location.endswith("/home")


@pytest.mark.parametrize(
    "flow_id",
    [
        "not_a_real_flow",
        "custom_0",
        "custom_007",
        "custom_-1",
        "custom_abc",
        "custom_2147483648",
        "custom_1000000000",
        "Custom_1",
        "custom_1%0A",
        "custom_",
        "login%0A",
    ],
)
def test_flow_malformed_flow_id_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    flow_id: str,
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/flow with a `flow_id` outside the id grammar
        (including ids with a trailing newline, which a `$`-anchored match
        would accept)
    THEN the response is 400 with exactly the fixed `Unknown flow id.` message
        (no regex text leaks) under the `INVALID_QUERY_PARAM` error code.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(_flow_url(flow_id), headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert body[STD_JSON.ERRORS] == {
        "flow_id": [MetricsFailureMessages.INVALID_FLOW_ID]
    }


def test_flow_window_xor_enforced(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/flow with both `window` and `start`
    THEN the response is 400 — the shared `_validate_window_xor_range`
        validator rejects the combo at the schema layer.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = f"{_FLOW_URL}?flow_id={_ADD_URL_FLOW}&window=day&start=2026-01-01T00:00:00Z"

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)


def test_flow_missing_window_and_range_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/flow with a valid `flow_id` but no `window`,
        `start`, or `end`
    THEN the response is 400 — the shared window-XOR-range validator rejects an
        empty time spec at the schema layer, surfaced as INVALID_QUERY_PARAM.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = f"{_FLOW_URL}?flow_id={_ADD_URL_FLOW}"

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)


def test_flow_invalid_window_param_returns_400_with_field_window(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/flow with a malformed `window` value
    THEN the response is 400 and the errors map keys on `window` — the FIRST
        try/except maps the `resolve_query_window` ValueError onto the window
        field specifically (isolating it from filter errors).
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    url = f"{_FLOW_URL}?flow_id={_ADD_URL_FLOW}&window=not_a_window"

    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "window" in body[STD_JSON.ERRORS]


def test_flow_invalid_filter_key_returns_400_with_field_filter(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an admin client and a FLOW whose first step carries a filter key that
        is not a valid dim on its event (simulating a FLOWS misconfiguration,
        the only way a `grouped_counts` ValueError surfaces from the second
        try/except since the registry filters are otherwise developer-controlled)
    WHEN GETing /api/metrics/query/flow for that flow
    THEN the response is 400 and the errors map keys on `filter` — the SECOND
        try/except maps the `grouped_counts` ValueError onto the filter field.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    broken_flow = FlowDefinition(
        display_name="Broken",
        steps=[
            FlowStep(
                stream="ui",
                label="Open",
                event_name=EventName.UI_URL_CREATE_OPEN,
                dim_filter=[("nonexistent_dim", "x")],
            ),
            FlowStep(
                stream="ui",
                label="Submit",
                event_name=EventName.UI_FORM_SUBMIT,
            ),
        ],
    )
    monkeypatch.setitem(FLOWS, FlowId.ADD_URL_TO_UTUB, broken_flow)

    response = logged_in_client.get(_flow_url(_ADD_URL_FLOW), headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "filter" in body[STD_JSON.ERRORS]


def test_flow_admin_happy_path_returns_steps_with_breakdown(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and a fully-seeded ADD_URL_TO_UTUB funnel (open=10,
        submit=8, api=7, domain=6) plus two URL_CREATE_REJECTED rows
    WHEN GETing /api/metrics/query/flow?flow_id=add_url_to_utub
    THEN the response is 200 with one step per FlowDefinition step, correct
        counts, capped `pct_of_top`, the domain step's reject breakdown, and
        the submit step's `breakdown=null` (its UI_FORM_CANCEL has no rows).
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_add_url_flow(_bucket_inside_window(), with_rejections=True)

    response = logged_in_client.get(_flow_url(_ADD_URL_FLOW), headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    steps = body["steps"]
    assert len(steps) == len(FLOWS[FlowId.ADD_URL_TO_UTUB].steps)

    assert [step["count"] for step in steps] == [10, 8, 7, 6]
    assert [step["stream"] for step in steps] == ["ui", "ui", "api", "domain"]
    # API step carries its display label as `event_name`, not the endpoint name.
    assert steps[2]["event_name"] == "POST .../urls"
    # pct_of_top denominated against step0 (10), capped at 1.0.
    assert steps[0]["pct_of_top"] == 1.0
    assert steps[3]["pct_of_top"] == 6 / 10

    # Submit step (index 1) has a UI_FORM_CANCEL breakdown configured, but no
    # cancel rows were seeded → DD-6 graceful-degrade to null.
    assert steps[1]["breakdown"] is None

    # Domain step (index 3) reject breakdown — two causes, pcts sum to ~1.0.
    domain_breakdown = steps[3]["breakdown"]
    assert domain_breakdown is not None
    rows_by_label = {row["label"]: row for row in domain_breakdown}
    assert rows_by_label["invalid_url"]["count"] == 6
    assert rows_by_label["url_already_in_utub"]["count"] == 5
    assert abs(sum(row["pct_of_step"] for row in domain_breakdown) - 1.0) < 1e-9


def test_flow_step_without_drop_breakdown_returns_null_breakdown(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and a seeded CREATE_UTUB funnel (ships success-only,
        the domain step has no drop_breakdown configured)
    WHEN GETing /api/metrics/query/flow?flow_id=create_utub
    THEN the domain step's `breakdown` is null (no breakdown configured) — the
        DD-6 path for a step that simply has no rejection lens.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_UTUB_CREATE_OPEN,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=4,
            dimensions={"device_type": 2},
        )
        _seed_event_with_count(
            event_name=EventName.UTUB_CREATED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=3,
            dimensions={"device_type": 2},
        )

    response = logged_in_client.get(_flow_url(_CREATE_UTUB_FLOW), headers=_AJAX_HEADERS)

    assert response.status_code == 200
    steps = response.get_json()["steps"]
    assert len(steps) == len(FLOWS[FlowId.CREATE_UTUB].steps)
    # The domain step (last) has no drop_breakdown in the registry → null.
    assert steps[-1]["breakdown"] is None


def test_flow_breakdown_is_null_when_breakdown_event_has_no_rows(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and an ADD_URL_TO_UTUB funnel seeded with only domain
        and API events (no URL_CREATE_REJECTED rows in the window)
    WHEN GETing /api/metrics/query/flow?flow_id=add_url_to_utub
    THEN the domain step's `breakdown` is null (not an empty list) — the DD-6
        graceful-degrade path: an empty raw_rows list collapses to None before
        any FlowBreakdownRow is constructed.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_add_url_flow(_bucket_inside_window(), with_rejections=False)

    response = logged_in_client.get(_flow_url(_ADD_URL_FLOW), headers=_AJAX_HEADERS)

    assert response.status_code == 200
    steps = response.get_json()["steps"]
    assert steps[3]["breakdown"] is None


def test_flow_pct_of_top_is_null_when_top_step_has_zero_count(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and an ADD_URL_TO_UTUB window where the FIRST step's
        event (UI_URL_CREATE_OPEN) has zero rows, but downstream steps do not
    WHEN GETing /api/metrics/query/flow?flow_id=add_url_to_utub
    THEN every step's `pct_of_top` is null (top_count == 0 division guard).
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_FORM_SUBMIT,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=5,
            dimensions={
                "trigger": "button_click",
                "form": "url_create",
                "device_type": 2,
            },
        )

    response = logged_in_client.get(_flow_url(_ADD_URL_FLOW), headers=_AJAX_HEADERS)

    assert response.status_code == 200
    steps = response.get_json()["steps"]
    assert steps[0]["count"] == 0
    assert all(step["pct_of_top"] is None for step in steps)


def test_flow_pct_of_top_capped_at_one_when_downstream_exceeds_denominator(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and an ADD_URL_TO_UTUB window where a downstream step
        count (submit=8) exceeds the top step count (open=5) — simulating
        per-guard dual-fire / beacon undercount of the top event
    WHEN GETing /api/metrics/query/flow?flow_id=add_url_to_utub
    THEN the downstream step's `pct_of_top` is exactly 1.0 (the min() cap), not
        greater than 1.0.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UI_URL_CREATE_OPEN,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=5,
            dimensions={"device_type": 2},
        )
        _seed_event_with_count(
            event_name=EventName.UI_FORM_SUBMIT,
            category=EventCategory.UI,
            bucket_start=_bucket_inside_window(),
            count=8,
            dimensions={
                "trigger": "button_click",
                "form": "url_create",
                "device_type": 2,
            },
        )

    response = logged_in_client.get(_flow_url(_ADD_URL_FLOW), headers=_AJAX_HEADERS)

    assert response.status_code == 200
    steps = response.get_json()["steps"]
    assert steps[0]["count"] == 5
    assert steps[1]["count"] == 8
    assert steps[1]["pct_of_top"] == 1.0


def _scalar_raising_on_third_call(
    real_scalar: Callable[..., int],
) -> Callable[..., int]:
    """Wrap `grouped_count_scalar` so its 3rd call raises `ValueError("boom")`."""
    calls = {"count": 0}

    def _stub(**kwargs: Any) -> int:
        calls["count"] += 1
        if calls["count"] == 3:
            raise ValueError("boom")
        return real_scalar(**kwargs)

    return _stub


def _breakdown_raising(**_kwargs: Any) -> NoReturn:
    raise ValueError("boom")


def test_flow_scalar_count_value_error_returns_400_with_filter_message(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an admin client and a built-in flow whose 3rd step count raises ValueError
    WHEN GETing /api/metrics/query/flow
    THEN the response is 400 with `errors == {"filter": ["boom"]}`.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    monkeypatch.setattr(
        flow_counting,
        "grouped_count_scalar",
        _scalar_raising_on_third_call(flow_counting.grouped_count_scalar),
    )

    response = logged_in_client.get(_flow_url(_ADD_URL_FLOW), headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert body[STD_JSON.ERRORS] == {"filter": ["boom"]}


def test_flow_breakdown_value_error_returns_400_with_filter_message(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an admin client and a built-in flow whose step breakdown raises ValueError
    WHEN GETing /api/metrics/query/flow
    THEN the response is 400 with `errors == {"filter": ["boom"]}`.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register
    monkeypatch.setattr(flow_counting, "grouped_count_by", _breakdown_raising)

    response = logged_in_client.get(_flow_url(_ADD_URL_FLOW), headers=_AJAX_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert body[STD_JSON.ERRORS] == {"filter": ["boom"]}


def test_count_flow_tags_scalar_failure_with_step_index(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a built-in flow whose 3rd step count raises ValueError("boom")
    WHEN count_flow runs directly
    THEN FlowCountError carries step_index 2, field steps.2, reason boom, is a
        ValueError and chains the original error as __cause__.
    """
    monkeypatch.setattr(
        flow_counting,
        "grouped_count_scalar",
        _scalar_raising_on_third_call(flow_counting.grouped_count_scalar),
    )
    window_end = utc_now()

    with app.app_context():
        with pytest.raises(FlowCountError) as exc_info:
            count_flow(
                definition=FLOWS[FlowId.ADD_URL_TO_UTUB],
                window_start=window_end - timedelta(days=1),
                window_end=window_end,
            )

    error = exc_info.value
    assert error.step_index == 2
    assert error.field == "steps.2"
    assert error.reason == "boom"
    assert str(error) == "boom"
    assert isinstance(error, ValueError)
    assert isinstance(error.__cause__, ValueError)
    assert str(error.__cause__) == "boom"


def test_count_flow_tags_breakdown_failure_with_drop_breakdown_field(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a built-in flow whose step-1 breakdown raises ValueError("boom")
    WHEN count_flow runs directly
    THEN FlowCountError has step_index 1 and field steps.1.drop_breakdown.
    """
    monkeypatch.setattr(flow_counting, "grouped_count_by", _breakdown_raising)
    window_end = utc_now()

    with app.app_context():
        with pytest.raises(FlowCountError) as exc_info:
            count_flow(
                definition=FLOWS[FlowId.ADD_URL_TO_UTUB],
                window_start=window_end - timedelta(days=1),
                window_end=window_end,
            )

    error = exc_info.value
    first_breakdown_index = next(
        step_index
        for step_index, step in enumerate(FLOWS[FlowId.ADD_URL_TO_UTUB].steps)
        if step.drop_breakdown is not None
    )
    assert error.step_index == first_breakdown_index
    assert error.field == f"steps.{first_breakdown_index}.drop_breakdown"
    assert error.reason == "boom"


def test_count_flow_reports_lowest_failing_step_when_several_fail(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GIVEN a built-in flow whose 3rd step count fails AND whose earlier step-1
        breakdown fails
    WHEN count_flow runs directly
    THEN the earlier step's breakdown failure is reported (per-step evaluation
        order), not the later step's count failure.
    """
    monkeypatch.setattr(
        flow_counting,
        "grouped_count_scalar",
        _scalar_raising_on_third_call(flow_counting.grouped_count_scalar),
    )
    monkeypatch.setattr(flow_counting, "grouped_count_by", _breakdown_raising)
    window_end = utc_now()

    with app.app_context():
        with pytest.raises(FlowCountError) as exc_info:
            count_flow(
                definition=FLOWS[FlowId.ADD_URL_TO_UTUB],
                window_start=window_end - timedelta(days=1),
                window_end=window_end,
            )

    assert exc_info.value.step_index == 1
    assert exc_info.value.field == "steps.1.drop_breakdown"


# ---------------------------------------------------------------------------
# Flow query — stored custom flows (`custom_<id>`)
# ---------------------------------------------------------------------------

_CUSTOM_FLOW_NAME = "Custom add URL"
_FLOW_INVALID = "flow_invalid"


def _add_url_steps() -> list[dict[str, Any]]:
    """Return the serialized steps of the built-in add-URL funnel (fresh copy)."""
    return serialize_flow_steps(FLOWS[FlowId.ADD_URL_TO_UTUB])["steps"]  # type: ignore[return-value]


def _insert_custom_flow(
    app: Flask, *, definition: dict[str, Any], display_name: str = _CUSTOM_FLOW_NAME
) -> int:
    """Insert one `Metric_Flows` row and return its id."""
    with app.app_context():
        row = Metric_Flows(
            display_name=display_name,
            definition=definition,
            created_by=None,
            updated_by=None,
        )
        db.session.add(row)
        db.session.commit()
        return row.id


def _get_custom_flow(logged_in_client: FlaskClient, row_id: int) -> TestResponse:
    return logged_in_client.get(
        _flow_url(format_custom_flow_id(row_id)), headers=_AJAX_HEADERS
    )


def _expected_invalid(
    app: Flask, *, definition: dict[str, Any], display_name: str
) -> dict[str, Any]:
    """Return `first_invalid_detail` of the validator's errors for a stored row."""
    with app.app_context():
        errors = validate_flow_payload({**definition, "display_name": display_name})
        assert isinstance(errors, dict)
        return first_invalid_detail(errors).model_dump()


def _assert_flow_invalid(response: Any, invalid: dict[str, Any]) -> None:
    assert response.status_code == 422
    assert response.get_json() == {"error": _FLOW_INVALID, "invalid": invalid}


def test_flow_custom_valid_row_returns_same_shape_as_built_in(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a stored custom flow mirroring the add-URL funnel and its seeded events
    WHEN GETing /api/metrics/query/flow?flow_id=custom_<id>
    THEN the response is 200 with the same counts, streams and breakdown shape
        as the built-in happy path.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_add_url_flow(_bucket_inside_window(), with_rejections=True)
    row_id = _insert_custom_flow(app, definition={"steps": _add_url_steps()})

    custom = _get_custom_flow(logged_in_client, row_id)
    built_in = logged_in_client.get(_flow_url(_ADD_URL_FLOW), headers=_AJAX_HEADERS)

    assert built_in.status_code == 200
    assert custom.status_code == 200
    steps = custom.get_json()["steps"]
    assert [step["count"] for step in steps] == [10, 8, 7, 6]
    assert [step["stream"] for step in steps] == ["ui", "ui", "api", "domain"]
    assert steps[3]["pct_of_top"] == 6 / 10
    assert steps == built_in.get_json()["steps"]


def test_flow_custom_step_dim_filter_changes_counts(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the add-URL funnel seeded plus 4 extra step-0 rows with `device_type`
        1 (so step 0 is 14 unfiltered, 10 for `device_type` 2)
    WHEN GETing a custom flow whose step 0 filters `device_type:2` and one
        without the filter
    THEN the filtered flow counts 10 with `pct_of_top` 0.6 for the last step,
        and the unfiltered flow counts 14.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    bucket = _bucket_inside_window()
    with app.app_context():
        _seed_add_url_flow(bucket, with_rejections=False)
        _seed_event_with_count(
            event_name=EventName.UI_URL_CREATE_OPEN,
            category=EventCategory.UI,
            bucket_start=bucket,
            count=4,
            dimensions={"device_type": 1},
        )
    filtered_steps = _add_url_steps()
    filtered_steps[0]["dim_filter"] = ["device_type:2"]
    filtered_id = _insert_custom_flow(app, definition={"steps": filtered_steps})
    unfiltered_id = _insert_custom_flow(
        app, definition={"steps": _add_url_steps()}, display_name="Unfiltered add URL"
    )

    filtered = _get_custom_flow(logged_in_client, filtered_id)
    unfiltered = _get_custom_flow(logged_in_client, unfiltered_id)

    assert filtered.status_code == 200
    assert unfiltered.status_code == 200
    filtered_body = filtered.get_json()["steps"]
    assert [step["count"] for step in filtered_body] == [10, 8, 7, 6]
    assert filtered_body[3]["pct_of_top"] == 6 / 10
    unfiltered_body = unfiltered.get_json()["steps"]
    assert unfiltered_body[0]["count"] == 14
    assert unfiltered_body[3]["pct_of_top"] == 6 / 14


def test_flow_custom_empty_window_returns_null_pct_of_top(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a valid custom flow and no seeded events in the window
    WHEN GETing the custom flow
    THEN the response is 200, every count is 0 and every `pct_of_top` is null.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    row_id = _insert_custom_flow(app, definition={"steps": _add_url_steps()})

    response = _get_custom_flow(logged_in_client, row_id)

    assert response.status_code == 200
    steps = response.get_json()["steps"]
    assert all(step["count"] == 0 for step in steps)
    assert all(step["pct_of_top"] is None for step in steps)


@pytest.mark.parametrize("delete_row", [False, True])
def test_flow_custom_missing_row_returns_404(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    delete_row: bool,
) -> None:
    """
    GIVEN a well-formed custom id with no row (never inserted, or inserted then
        deleted)
    WHEN GETing /api/metrics/query/flow
    THEN the response is 404 with the `Flow not found.` message.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    row_id = 999999999
    if delete_row:
        row_id = _insert_custom_flow(app, definition={"steps": _add_url_steps()})
        with app.app_context():
            Metric_Flows.query.filter_by(id=row_id).delete()
            db.session.commit()

    response = _get_custom_flow(logged_in_client, row_id)

    assert response.status_code == 404
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == MetricsFailureMessages.FLOW_NOT_FOUND


def test_flow_custom_removed_event_returns_422_naming_step(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a stored flow whose step 2 names an event that no longer exists
    WHEN GETing the custom flow
    THEN the response is the pinned 422 body naming step 2 and its event path.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    steps = _add_url_steps()
    steps = [steps[0], steps[1], {**steps[3], "event_name": "removed_event"}]
    row_id = _insert_custom_flow(app, definition={"steps": steps})

    response = _get_custom_flow(logged_in_client, row_id)

    _assert_flow_invalid(
        response,
        {
            "step_index": 2,
            "field": "steps.2.event_name",
            "reason": unknown_event_message(value="removed_event"),
        },
    )
    assert STD_JSON.STATUS not in response.get_json()


def test_flow_custom_bad_filter_key_returns_422(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a stored flow whose step 1 filters on a dimension that does not exist
    WHEN GETing the custom flow
    THEN the 422 names `steps.1.dim_filter.0`.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    steps = _add_url_steps()
    steps[1]["dim_filter"] = ["nope:1"]
    row_id = _insert_custom_flow(app, definition={"steps": steps})

    response = _get_custom_flow(logged_in_client, row_id)

    expected = _expected_invalid(
        app, definition={"steps": steps}, display_name=_CUSTOM_FLOW_NAME
    )
    assert expected["step_index"] == 1
    assert expected["field"] == "steps.1.dim_filter.0"
    _assert_flow_invalid(response, expected)
    assert STD_JSON.STATUS not in response.get_json()


@pytest.mark.parametrize(
    ("display_name", "definition", "expected_index", "expected_field"),
    [
        ("One step", {"steps": _add_url_steps()[:1]}, None, "steps"),
        ("bad\u0007name", {"steps": _add_url_steps()}, None, "display_name"),
        ("Non object steps", {"steps": [5, 6]}, 0, "steps.0"),
    ],
)
def test_flow_custom_structural_problems_return_422(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    display_name: str,
    definition: dict[str, Any],
    expected_index: int | None,
    expected_field: str,
) -> None:
    """
    GIVEN a stored flow with a structural problem (too few steps, a control
        character in the name, a non-object step)
    WHEN GETing the custom flow
    THEN the 422 carries the validator's field path, with a null `step_index`
        for flow-level paths, and the body is exactly the pinned shape.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    row_id = _insert_custom_flow(app, definition=definition, display_name=display_name)

    response = _get_custom_flow(logged_in_client, row_id)

    expected = _expected_invalid(app, definition=definition, display_name=display_name)
    assert expected["step_index"] == expected_index
    assert expected["field"] == expected_field
    assert expected["reason"]
    _assert_flow_invalid(response, expected)
    assert STD_JSON.STATUS not in response.get_json()


def test_flow_custom_errors_in_two_steps_report_the_lower_step(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a stored flow with problems in step 1 and step 3
    WHEN GETing the custom flow
    THEN the 422 `invalid` is exactly `first_invalid_detail` of the validator's
        errors (same helper, same object) and names the lower step.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    steps = _add_url_steps()
    steps[1]["dim_filter"] = ["nope:1"]
    steps[3]["event_name"] = "removed_event"
    row_id = _insert_custom_flow(app, definition={"steps": steps})
    with app.app_context():
        errors = validate_flow_payload(
            {"steps": steps, "display_name": _CUSTOM_FLOW_NAME}
        )
        assert isinstance(errors, dict)
        expected = first_invalid_detail(errors).model_dump()

    response = _get_custom_flow(logged_in_client, row_id)

    _assert_flow_invalid(response, expected)
    assert expected["step_index"] == 1


def test_flow_custom_column_display_name_overrides_stored_key(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a stored definition carrying a stale `display_name` key beside a valid
        column value
    WHEN GETing the custom flow
    THEN the column wins and the response is 200.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    row_id = _insert_custom_flow(
        app, definition={"steps": _add_url_steps(), "display_name": "bad\u0007name"}
    )

    response = _get_custom_flow(logged_in_client, row_id)

    assert response.status_code == 200


@pytest.mark.parametrize("definition", [[], [{"steps": []}], 5, "steps", None])
def test_flow_custom_non_object_definition_cannot_be_stored(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    definition: Any,
) -> None:
    """
    GIVEN a `definition` that is not a JSON object (list, scalar, null)
    WHEN inserting it into `Metric_Flows`
    THEN the database rejects it, so the flow route never has to read a
        non-dict `definition` and the 422 `flow_invalid` path stays reachable
        only for object definitions.
    """
    _, _, _, app = login_admin_user_with_register

    with app.app_context():
        db.session.add(
            Metric_Flows(
                display_name=_CUSTOM_FLOW_NAME,
                definition=definition,
                created_by=None,
                updated_by=None,
            )
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        assert Metric_Flows.query.count() == 0


def test_flow_custom_unknown_top_level_key_returns_422(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a stored definition with an unknown top-level key
    WHEN GETing the custom flow
    THEN the 422 is flow-level (`step_index` null) naming the stray key.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    row_id = _insert_custom_flow(
        app, definition={"steps": _add_url_steps(), "bogus": 1}
    )

    response = _get_custom_flow(logged_in_client, row_id)

    _assert_flow_invalid(
        response,
        {"step_index": None, "field": "bogus", "reason": UNEXPECTED_FIELD_STR},
    )


def test_flow_custom_scalar_count_error_returns_422_not_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a valid custom flow whose 3rd step count raises ValueError
    WHEN GETing the custom flow
    THEN the response is a 422 naming step 2 with the raised message.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    row_id = _insert_custom_flow(app, definition={"steps": _add_url_steps()})
    monkeypatch.setattr(
        flow_counting,
        "grouped_count_scalar",
        _scalar_raising_on_third_call(flow_counting.grouped_count_scalar),
    )

    response = _get_custom_flow(logged_in_client, row_id)

    _assert_flow_invalid(
        response, {"step_index": 2, "field": "steps.2", "reason": "boom"}
    )


def test_flow_custom_breakdown_count_error_returns_422_not_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN a valid custom flow whose step breakdown raises ValueError
    WHEN GETing the custom flow
    THEN the response is a 422 naming the first step's `drop_breakdown` path.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    steps = _add_url_steps()
    first_breakdown_index = next(
        index for index, step in enumerate(steps) if "drop_breakdown" in step
    )
    row_id = _insert_custom_flow(app, definition={"steps": steps})
    monkeypatch.setattr(flow_counting, "grouped_count_by", _breakdown_raising)

    response = _get_custom_flow(logged_in_client, row_id)

    _assert_flow_invalid(
        response,
        {
            "step_index": first_breakdown_index,
            "field": f"steps.{first_breakdown_index}.drop_breakdown",
            "reason": "boom",
        },
    )


# ---------------------------------------------------------------------------
# Gauges query endpoints — batched timeseries (auth + happy)
# ---------------------------------------------------------------------------


_GAUGES_TIMESERIES_URL = "/api/metrics/query/gauges/timeseries"


def _seed_gauge_row(
    gauge_name: GaugeName,
    sampled_at: datetime,
    *,
    value_int: int | None = None,
    value_float: float | None = None,
) -> None:
    """Seed one AnonymousGauges row through SQLAlchemy.

    ORM (not raw psycopg2) because `login_admin_user_with_register` is
    SAVEPOINT-based — a raw psycopg2 write would land outside the savepoint and
    roll back independently of the test transaction.
    """
    db.session.add(
        Anonymous_Gauges(
            gauge_name=gauge_name.value,
            sampled_at=sampled_at,
            value_int=value_int,
            value_float=value_float,
            dimensions={},
        )
    )
    db.session.commit()


@pytest.mark.parametrize(
    "url",
    [
        _GAUGES_TIMESERIES_URL + "?window=day",
    ],
)
def test_gauges_endpoints_anonymous_return_401(
    app: Flask, client: FlaskClient, url: str
) -> None:
    """
    GIVEN an anonymous client (no session)
    WHEN GETing any gauges query endpoint
    THEN the response is 401 with a JSON failure envelope (mirrors the other
        admin-only query endpoints).
    """
    response = client.get(url)

    assert response.status_code == 401
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


@pytest.mark.parametrize(
    "url",
    [
        _GAUGES_TIMESERIES_URL + "?window=day",
    ],
)
def test_gauges_endpoints_non_admin_return_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask], url: str
) -> None:
    """
    GIVEN a logged-in user with the default User_Role.USER
    WHEN GETing any gauges query endpoint
    THEN the response is 404 with a JSON failure envelope (not advertised to
        non-admins).
    """
    logged_in_client, _, _, _ = login_first_user_with_register

    response = logged_in_client.get(url)

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_gauges_timeseries_admin_happy_path_returns_batched_series(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and two gauges seeded with samples inside the window
    WHEN GETing /api/metrics/query/gauges/timeseries?window=day
    THEN the response is 200 with the batched wrapper keys (`gauges`, `window`,
        `window_start`, `window_end`), one `gauges[]` entry per seeded gauge
        carrying `gauge_name`/`kind`/`description`/`samples`, and the sample's
        `sampled_at` serializes as ISO-8601 UTC.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        sampled_at = _bucket_inside_window()
        _seed_gauge_row(GaugeName.TOTAL_USERS, sampled_at, value_int=12)
        _seed_gauge_row(GaugeName.AVG_URLS_PER_UTUB, sampled_at, value_float=4.5)

    response = logged_in_client.get(
        _GAUGES_TIMESERIES_URL + "?window=day", headers=_AJAX_HEADERS
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "gauges" in body
    assert "window" in body
    assert "window_start" in body
    assert "window_end" in body
    assert body["window"] == "day"

    series_by_name = {series["gauge_name"]: series for series in body["gauges"]}
    assert set(series_by_name) == {
        GaugeName.TOTAL_USERS.value,
        GaugeName.AVG_URLS_PER_UTUB.value,
    }

    users_series = series_by_name[GaugeName.TOTAL_USERS.value]
    assert users_series["kind"] == GAUGE_REGISTRY[GaugeName.TOTAL_USERS].kind.value
    assert (
        users_series["description"] == GAUGE_REGISTRY[GaugeName.TOTAL_USERS].description
    )
    assert users_series["samples"][0]["value_int"] == 12
    assert _ISO_8601_UTC_REGEX.match(users_series["samples"][0]["sampled_at"])

    avg_series = series_by_name[GaugeName.AVG_URLS_PER_UTUB.value]
    assert avg_series["samples"][0]["value_float"] == 4.5


def test_gauges_timeseries_returns_percentile_kind_series(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and a median gauge seeded with value_float=3.5
    WHEN GETing /api/metrics/query/gauges/timeseries?window=day
    THEN the series kind is "distribution_median", value_float is 3.5 and
        value_int is null.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_gauge_row(
            GaugeName.MEDIAN_URLS_PER_UTUB, _bucket_inside_window(), value_float=3.5
        )

    response = logged_in_client.get(
        _GAUGES_TIMESERIES_URL + "?window=day", headers=_AJAX_HEADERS
    )

    assert response.status_code == 200
    series_by_name = {
        series["gauge_name"]: series for series in response.get_json()["gauges"]
    }
    series = series_by_name[GaugeName.MEDIAN_URLS_PER_UTUB.value]
    assert series["kind"] == "distribution_median"
    assert series["samples"][0]["value_float"] == 3.5
    assert series["samples"][0]["value_int"] is None


def test_gauges_timeseries_bad_window_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/gauges/timeseries?window=bogus
    THEN the response is 400 with error_code=INVALID_QUERY_PARAM and a `window`
        field error — guards the resolve_query_window 400 path on the batched route.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _GAUGES_TIMESERIES_URL + "?window=bogus", headers=_AJAX_HEADERS
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "window" in body[STD_JSON.ERRORS]


def test_gauges_timeseries_stray_name_param_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing the batched gauges timeseries with a stray `name` query param
    THEN the response is 400 — the batched schema has no `name` field and
        `extra="forbid"` rejects it.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _GAUGES_TIMESERIES_URL + "?window=day&name=total_users",
        headers=_AJAX_HEADERS,
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


# ---------------------------------------------------------------------------
# Latency query endpoints — percentiles + timeseries (auth + happy + filters)
# ---------------------------------------------------------------------------


_LATENCY_URL = "/api/metrics/query/latency"
_LATENCY_TIMESERIES_URL = "/api/metrics/query/latency/timeseries"


def _seed_latency_row(
    observed_at: datetime,
    duration_ms: float,
    *,
    endpoint: str = "utubs.get_utub",
    method: str = "GET",
    device_type: DeviceType = DeviceType.DESKTOP,
) -> None:
    """Seed one AnonymousLatencySamples row through SQLAlchemy.

    ORM (not raw psycopg2) because `login_admin_user_with_register` is
    SAVEPOINT-based — a raw psycopg2 write would land outside the savepoint and
    roll back independently of the test transaction.
    """
    db.session.add(
        Anonymous_Latency_Samples(
            metric_name=LatencyMetricName.API_REQUEST_DURATION.value,
            endpoint=endpoint,
            method=method,
            observed_at=observed_at,
            duration_ms=duration_ms,
            dimensions={DEVICE_TYPE_DIM_KEY: int(device_type)},
        )
    )
    db.session.commit()


def _seed_latency_rollup_row(
    rollup_date: date,
    *,
    p50_ms: float = 100.0,
    p95_ms: float = 200.0,
    p99_ms: float = 300.0,
    sample_count: int = 10,
    endpoint: str = "utubs.get_utub",
    method: str = "GET",
) -> None:
    """Seed one AnonymousLatencyDailyRollups row through SQLAlchemy.

    ORM (not raw psycopg2) for the same SAVEPOINT reason as `_seed_latency_row`.
    Backs the long-window (beyond 35-day raw retention) endpoint tests where the
    summary is served from the daily rollup and marked approximate.
    """
    db.session.add(
        Anonymous_Latency_Daily_Rollups(
            metric_name=LatencyMetricName.API_REQUEST_DURATION.value,
            endpoint=endpoint,
            method=method,
            rollup_date=rollup_date,
            p50_ms=p50_ms,
            p95_ms=p95_ms,
            p99_ms=p99_ms,
            sample_count=sample_count,
            dimensions={},
        )
    )
    db.session.commit()


@pytest.mark.parametrize(
    "url",
    [
        _LATENCY_URL + "?window=day",
        _LATENCY_TIMESERIES_URL + "?window=day&endpoint=utubs.get_utub",
    ],
)
def test_latency_endpoints_anonymous_return_401(
    app: Flask, client: FlaskClient, url: str
) -> None:
    """
    GIVEN an anonymous client (no session)
    WHEN GETing either latency query endpoint
    THEN the response is 401 with a JSON failure envelope (NOT a 302 redirect),
        mirroring the other admin-only query endpoints.
    """
    response = client.get(url)

    assert response.status_code == 401
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


@pytest.mark.parametrize(
    "url",
    [
        _LATENCY_URL + "?window=day",
        _LATENCY_TIMESERIES_URL + "?window=day&endpoint=utubs.get_utub",
    ],
)
def test_latency_endpoints_non_admin_return_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask], url: str
) -> None:
    """
    GIVEN a logged-in user with the default User_Role.USER
    WHEN GETing either latency query endpoint
    THEN the response is 404 with a JSON failure envelope (not advertised to
        non-admins).
    """
    logged_in_client, _, _, _ = login_first_user_with_register

    response = logged_in_client.get(url)

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_latency_admin_happy_path_returns_percentile_rows(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and three latency samples for one (endpoint, method)
        inside the window
    WHEN GETing /api/metrics/query/latency?window=day
    THEN the response is 200 with the envelope keys (`rows`, `window`,
        `window_start`, `window_end`), one row carrying endpoint/method/p50/p95/
        p99/sample_count, and the datetimes serialize as ISO-8601 UTC.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        observed_at = _bucket_inside_window()
        for duration in (10.0, 20.0, 30.0):
            _seed_latency_row(observed_at, duration)

    response = logged_in_client.get(_LATENCY_URL + "?window=day", headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert "rows" in body
    assert body["window"] == "day"
    assert _ISO_8601_UTC_REGEX.match(body["window_start"])
    assert _ISO_8601_UTC_REGEX.match(body["window_end"])

    rows = body["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["endpoint"] == "utubs.get_utub"
    assert row["method"] == "GET"
    assert row["sample_count"] == 3
    # percentile_cont(0.5) over {10, 20, 30} == 20.0 (exact median, no interp).
    assert row["p50"] == 20.0


def test_latency_timeseries_admin_happy_path_returns_buckets(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and latency samples for one endpoint inside the window
    WHEN GETing /api/metrics/query/latency/timeseries?window=day&endpoint=...
    THEN the response is 200 with the envelope keys (`buckets`, `endpoint`,
        `method`, `window`, `window_start`, `window_end`), the bucket carrying
        the samples reports p50/p95/p99/sample_count, and buckets are zero-filled.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        observed_at = _bucket_inside_window()
        for duration in (10.0, 20.0, 30.0):
            _seed_latency_row(observed_at, duration)

    response = logged_in_client.get(
        _LATENCY_TIMESERIES_URL + "?window=day&endpoint=utubs.get_utub",
        headers=_AJAX_HEADERS,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["endpoint"] == "utubs.get_utub"
    assert "buckets" in body
    assert _ISO_8601_UTC_REGEX.match(body["window_start"])

    non_empty = [bucket for bucket in body["buckets"] if bucket["sample_count"] > 0]
    assert len(non_empty) == 1
    assert non_empty[0]["p50"] == 20.0
    # Zero-fill buckets carry null percentiles (never 0) so the chart breaks.
    empty = [bucket for bucket in body["buckets"] if bucket["sample_count"] == 0]
    assert empty
    assert empty[0]["p50"] is None


def test_latency_limit_caps_returned_rows(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and samples for two distinct endpoints in the window
    WHEN GETing /api/metrics/query/latency?window=day&limit=1
    THEN exactly one percentile row is returned (the `limit` bound takes effect).
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        observed_at = _bucket_inside_window()
        _seed_latency_row(observed_at, 100.0, endpoint="utubs.get_utub")
        _seed_latency_row(observed_at, 5.0, endpoint="urls.add_url", method="POST")

    response = logged_in_client.get(
        _LATENCY_URL + "?window=day&limit=1", headers=_AJAX_HEADERS
    )

    assert response.status_code == 200
    rows = response.get_json()["rows"]
    assert len(rows) == 1
    # Ordered by p95 desc — the slower endpoint (100ms) wins the single slot.
    assert rows[0]["endpoint"] == "utubs.get_utub"


def test_latency_endpoint_filter_narrows_rows(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and samples for two endpoints in the window
    WHEN GETing /api/metrics/query/latency with an `endpoint` filter
    THEN only rows for the filtered endpoint are returned.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        observed_at = _bucket_inside_window()
        _seed_latency_row(observed_at, 100.0, endpoint="utubs.get_utub")
        _seed_latency_row(observed_at, 5.0, endpoint="urls.add_url", method="POST")

    response = logged_in_client.get(
        _LATENCY_URL + "?window=day&endpoint=urls.add_url", headers=_AJAX_HEADERS
    )

    assert response.status_code == 200
    rows = response.get_json()["rows"]
    assert len(rows) == 1
    assert rows[0]["endpoint"] == "urls.add_url"


def test_latency_device_type_filter_narrows_rows(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and one mobile + one desktop sample for an endpoint
    WHEN GETing /api/metrics/query/latency with device_type=1 (mobile)
    THEN only the mobile sample is aggregated (sample_count == 1).
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        observed_at = _bucket_inside_window()
        _seed_latency_row(observed_at, 10.0, device_type=DeviceType.MOBILE)
        _seed_latency_row(observed_at, 20.0, device_type=DeviceType.DESKTOP)

    response = logged_in_client.get(
        _LATENCY_URL + "?window=day&device_type=1", headers=_AJAX_HEADERS
    )

    assert response.status_code == 200
    rows = response.get_json()["rows"]
    assert len(rows) == 1
    assert rows[0]["sample_count"] == 1


def test_latency_bad_window_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/latency?window=bogus
    THEN the response is 400 with error_code=INVALID_QUERY_PARAM and a `window`
        field error.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _LATENCY_URL + "?window=bogus", headers=_AJAX_HEADERS
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(MetricsErrorCodes.INVALID_QUERY_PARAM)
    assert "window" in body[STD_JSON.ERRORS]


def test_latency_window_and_range_together_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/latency with BOTH window and start+end
    THEN the response is 400 (window-XOR-range violation at the schema layer).
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _LATENCY_URL
        + "?window=day&start=2026-01-01T00:00:00%2B00:00&end=2026-02-01T00:00:00%2B00:00",
        headers=_AJAX_HEADERS,
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_latency_timeseries_missing_endpoint_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client
    WHEN GETing /api/metrics/query/latency/timeseries?window=day (no endpoint)
    THEN the response is 400 — `endpoint` is required on the timeseries schema.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _LATENCY_TIMESERIES_URL + "?window=day", headers=_AJAX_HEADERS
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE


def test_latency_year_window_returns_approximate_true_from_rollup(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and a daily rollup row dated ~40 days ago (beyond the
        35-day raw retention horizon but inside the year window)
    WHEN GETing /api/metrics/query/latency?window=year
    THEN the response is 200 with `approximate: true` and per-endpoint rows from
        the rollup — Year crosses the raw retention boundary.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        rollup_day = (datetime.now(timezone.utc) - timedelta(days=40)).date()
        _seed_latency_rollup_row(rollup_day)

    response = logged_in_client.get(
        _LATENCY_URL + "?window=year", headers=_AJAX_HEADERS
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["approximate"] is True
    assert len(body["rows"]) == 1
    assert body["rows"][0]["endpoint"] == "utubs.get_utub"


def test_latency_month_and_day_windows_return_approximate_false(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and raw samples inside the last hour
    WHEN GETing /api/metrics/query/latency for window=month and window=day
    THEN both return 200 with `approximate: false` — Month (~28-31 days) and Day
        both sit inside the 35-day raw retention and are served exactly from raw.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        observed_at = _bucket_inside_window()
        for duration in (10.0, 20.0, 30.0):
            _seed_latency_row(observed_at, duration)

    month_response = logged_in_client.get(
        _LATENCY_URL + "?window=month", headers=_AJAX_HEADERS
    )
    day_response = logged_in_client.get(
        _LATENCY_URL + "?window=day", headers=_AJAX_HEADERS
    )

    assert month_response.status_code == 200
    assert month_response.get_json()["approximate"] is False
    assert day_response.status_code == 200
    assert day_response.get_json()["approximate"] is False
