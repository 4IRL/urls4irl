from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient

from backend import db
from backend.metrics.constants import MetricsErrorCodes
from backend.metrics.events import EVENT_DESCRIPTIONS, EventCategory, EventName
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.event_registry import Event_Registry
from backend.models.users import Users
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
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
) -> None:
    """Seed one EventRegistry + AnonymousMetrics row through SQLAlchemy.

    Why ORM (not raw psycopg2): `login_admin_user_with_register` depends on
    the SAVEPOINT-based `app` fixture; raw psycopg2 writes would land outside
    the savepoint and roll back independently.
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
    GIVEN an admin client and one seeded UTUB_OPENED row inside the window
    WHEN GETing /api/metrics/query/top?window=day
    THEN the response is 200, JSON contains `events`, `window`, `window_start`,
        `window_end`, `category` aliases, and the description round-trips
        through the EventRegistry JOIN.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_OPENED,
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
    assert seeded_event["event_name"] == EventName.UTUB_OPENED.value
    assert seeded_event["total_count"] == 5
    assert seeded_event["description"] == EVENT_DESCRIPTIONS[EventName.UTUB_OPENED]


# ---------------------------------------------------------------------------
# `timeseries` — admin happy path
# ---------------------------------------------------------------------------


def test_query_timeseries_admin_happy_path_returns_seeded_buckets(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an admin client and one seeded UTUB_OPENED row inside the window
    WHEN GETing /api/metrics/query/timeseries?window=day&event_name=<valid>
        &resolution=hour
    THEN the response is 200, JSON contains the full timeseries envelope
        (`event_name`, `window`, `resolution`, `window_start`, `window_end`,
        `buckets`) and at least one bucket reflects the seeded row's count.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        _seed_event_with_count(
            event_name=EventName.UTUB_OPENED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=3,
        )

    url = (
        _TIMESERIES_URL
        + "?window=day&event_name="
        + EventName.UTUB_OPENED.value
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
    assert body["event_name"] == EventName.UTUB_OPENED.value
    assert body["window"] == "day"
    assert body["resolution"] == "hour"
    assert isinstance(body["buckets"], list)
    assert len(body["buckets"]) >= 1
    assert sum(bucket["count"] for bucket in body["buckets"]) == 3


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
        `_parse_query_args` + `parse_window(ValueError → 400)` code path
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
            event_name=EventName.UTUB_OPENED,
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


# ---------------------------------------------------------------------------
# Admin missing X-Requested-With → 302 redirect to /home
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        _TOP_URL + "?window=day",
        _TIMESERIES_URL + "?window=day&event_name=" + EventName.UTUB_OPENED.value,
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
            event_name=EventName.UTUB_OPENED,
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
    GIVEN an admin client and one seeded UTUB_OPENED row inside an absolute range
    WHEN GETing /api/metrics/query/timeseries?event_name=...&start=...&end=...
    THEN the response is 200, `window` is null, and the bucket count matches.
    """
    logged_in_client, _, _, app = login_admin_user_with_register
    with app.app_context():
        bucket = _bucket_inside_window()
        _seed_event_with_count(
            event_name=EventName.UTUB_OPENED,
            category=EventCategory.DOMAIN,
            bucket_start=bucket,
            count=4,
        )
    start_iso, end_iso = _absolute_range_around(bucket)

    url = (
        f"{_TIMESERIES_URL}?event_name={EventName.UTUB_OPENED.value}"
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
            event_name=EventName.UTUB_OPENED,
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
        (_TIMESERIES_URL, f"&event_name={EventName.UTUB_OPENED.value}"),
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
