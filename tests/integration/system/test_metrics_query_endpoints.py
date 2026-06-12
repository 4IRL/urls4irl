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
    assert seeded_event["previous_count"] == 0


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
    WHEN GETing /api/metrics/query/top?window=day&category=domain&resource=search
        (`search` does not appear in `RESOURCE_BY_CATEGORY[DOMAIN]` — domain
        covers utub, url, tag, member, auth only)
    THEN the response is 400 with `error_code=INVALID_QUERY_PARAM` — the
        model_validator rejects pairs not listed in `RESOURCE_BY_CATEGORY`.
    """
    logged_in_client, _, _, _ = login_admin_user_with_register

    response = logged_in_client.get(
        _TOP_URL + "?window=day&category=domain&resource=search",
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
    GIVEN an admin client and two seeded UTUB_OPENED rows inside the window:
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
            event_name=EventName.UTUB_OPENED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=3,
            dimensions={"device_type": 1},
        )
        _seed_event_with_count(
            event_name=EventName.UTUB_OPENED,
            category=EventCategory.DOMAIN,
            bucket_start=_bucket_inside_window(),
            count=7,
            dimensions={"device_type": 2},
        )

    url = (
        _TIMESERIES_URL
        + "?window=day&event_name="
        + EventName.UTUB_OPENED.value
        + "&resolution=hour&device_type=1"
    )
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["event_name"] == EventName.UTUB_OPENED.value
    assert isinstance(body["buckets"], list)
    assert sum(bucket["count"] for bucket in body["buckets"]) == 3


# ---------------------------------------------------------------------------
# `grouped-timeseries` — admin gating + window-XOR + bad group_by key + happy
# ---------------------------------------------------------------------------


_GROUPED_TIMESERIES_URL = "/api/metrics/query/grouped-timeseries"
_INGEST_BATCH_EVENT: str = EventName.API_METRICS_INGEST_BATCH.value


def _grouped_url_for(
    event_name: str,
    *,
    group_by: list[str],
    window: str = "day",
) -> str:
    """Build a grouped-timeseries URL with repeated `group_by` keys.

    Matches the wire format `_parse_query_args(..., multi_value_keys=...)`
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
            count=4,
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
            count=2,
            dimensions={
                "batch_size_bucket": "1",
                "transport": "beacon",
                "device_type": 1,
            },
        )

    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=["transport", "device_type"])
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body["event_name"] == _INGEST_BATCH_EVENT
    assert body["group_by"] == ["transport", "device_type"]
    assert body["resolution"] == "hour"
    assert body["window"] == "day"
    rows_by_dim_tuple = {
        (row["dimensions"]["transport"], row["dimensions"]["device_type"]): row["count"]
        for row in body["buckets"]
    }
    assert rows_by_dim_tuple == {
        ("fetch", 2): 4,
        ("beacon", 2): 7,
        ("beacon", 1): 2,
    }


def test_grouped_timeseries_zero_fills_buckets_with_no_data(
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
            count=1,
            dimensions={
                "batch_size_bucket": "1",
                "transport": "fetch",
                "device_type": 2,
            },
        )

    url = _grouped_url_for(_INGEST_BATCH_EVENT, group_by=["transport", "device_type"])
    response = logged_in_client.get(url, headers=_AJAX_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    # Exactly one row — no zero-fill for the absent (transport, device_type)
    # combinations that would appear if the grouped variant followed the
    # `timeseries` zero-fill policy.
    assert len(body["buckets"]) == 1
    only_row = body["buckets"][0]
    assert only_row["dimensions"] == {"transport": "fetch", "device_type": 2}
    assert only_row["count"] == 1
