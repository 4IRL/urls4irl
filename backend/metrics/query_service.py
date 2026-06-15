from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, NamedTuple

from flask import current_app
from sqlalchemy import func
from sqlalchemy.orm import Query

from backend import db
from backend.extensions.metrics.writer import MetricsWriter
from backend.metrics.dimension_models import DIMENSION_MODELS
from backend.metrics.events import (
    DEVICE_TYPE_DIM_KEY,
    DeviceType,
    EVENT_CATEGORY,
    EventCategory,
    EventName,
)
from backend.metrics.gauges import (
    GAUGE_REGISTRY,
    GaugeName,
)
from backend.metrics.resources import Resource, resource_filter_clause
from backend.models.anonymous_gauges import Anonymous_Gauges
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.models.event_registry import Event_Registry
from backend.schemas.metrics import (
    GaugeSampleSchema,
    GaugeSeries,
    GaugesTimeseriesResponseSchema,
    GroupedTimeseriesBucket,
    GroupedTimeseriesResponseSchema,
    SummaryCategoryCount,
    TimeseriesBucketSchema,
    TopEventRow,
)


class SummaryResult(NamedTuple):
    by_category: list[SummaryCategoryCount]
    last_flush_at: datetime | None
    last_event_at: datetime | None


class _EndpointMetadata(NamedTuple):
    url_pattern: str
    description: str


def _endpoint_metadata_map() -> dict[str, _EndpointMetadata]:
    """Build a {flask_endpoint_name: (url_pattern, description)} map from the active app.

    Used by `top_events()` when category=api to:
      * convert stored endpoint names (e.g. "utubs.create_url") into the
        user-facing URL patterns the dashboard renders
        ("POST /utubs/<utub_id>/urls");
      * surface the route's `@api_route(description=...)` kwarg as the
        human-readable subtitle shown beneath each API row in the top table.

    The description falls back to "" when the endpoint is no longer registered
    or the route was not decorated with `@api_route` (e.g. Flask's static-file
    routes), so the dashboard renders a blank subtitle rather than leaking the
    raw Flask endpoint name into the UI.
    """
    metadata: dict[str, _EndpointMetadata] = {}
    for rule in current_app.url_map.iter_rules():
        view_function = current_app.view_functions.get(rule.endpoint)
        description = getattr(view_function, "_api_route_description", None) or ""
        metadata[rule.endpoint] = _EndpointMetadata(
            url_pattern=rule.rule,
            description=description,
        )
    return metadata


def _device_type_filter(query: Query, device_type: DeviceType | None) -> Query:
    """Apply the `device_type` JSONB filter to `query` when set, else return as-is.

    Centralizes the JSONB-cast filter used by every query helper that supports
    `device_type=` so the four call sites cannot drift on operator, JSON key
    spelling, or cast type. Returns `query` unchanged when `device_type is None`
    so callers can always write `query = _device_type_filter(query, device_type)`.
    """
    if device_type is None:
        return query
    return query.filter(
        Anonymous_Metrics.dimensions[DEVICE_TYPE_DIM_KEY].as_integer() == device_type
    )


def _per_endpoint_counts(
    *,
    window_start: datetime,
    window_end: datetime,
    device_type: DeviceType | None = None,
) -> dict[tuple[str, str], int]:
    """Return a {(endpoint, method): count} map for api_hit rows in the window.

    api_hit is the only event that carries per-request dimensions in flat
    columns (endpoint/method/status_code, promoted at flush time). This
    helper groups by those flat columns so the API tab can drill into per-
    route counts. Rows with NULL endpoint or method are excluded — those
    represent ingest paths the dashboard cannot meaningfully attribute.
    """
    total_count = func.sum(Anonymous_Metrics.count).label("total_count")
    query = db.session.query(
        Anonymous_Metrics.endpoint,
        Anonymous_Metrics.method,
        total_count,
    ).filter(
        Anonymous_Metrics.event_name == EventName.API_HIT.value,
        Anonymous_Metrics.bucket_start >= window_start,
        Anonymous_Metrics.bucket_start < window_end,
        Anonymous_Metrics.endpoint.isnot(None),
        Anonymous_Metrics.method.isnot(None),
    )
    query = _device_type_filter(query, device_type)
    rows = query.group_by(Anonymous_Metrics.endpoint, Anonymous_Metrics.method).all()
    return {(row.endpoint, row.method): int(row.total_count) for row in rows}


def _per_event_counts(
    *,
    window_start: datetime,
    window_end: datetime,
    category: EventCategory | None,
    device_type: DeviceType | None = None,
) -> dict[str, int]:
    """Return a {event_name: count} map summed across a half-open window."""
    total_count = func.sum(Anonymous_Metrics.count).label("total_count")
    query = (
        db.session.query(Anonymous_Metrics.event_name, total_count)
        .join(Event_Registry, Event_Registry.name == Anonymous_Metrics.event_name)
        .filter(
            Anonymous_Metrics.bucket_start >= window_start,
            Anonymous_Metrics.bucket_start < window_end,
        )
    )
    if category is not None:
        query = query.filter(Event_Registry.category == category)
    query = _device_type_filter(query, device_type)
    rows = query.group_by(Anonymous_Metrics.event_name).all()
    return {row.event_name: int(row.total_count) for row in rows}


def _top_endpoints_for_api_hit(
    *,
    window_start: datetime,
    window_end: datetime,
    previous_window_start: datetime,
    previous_window_end: datetime,
    resource: Resource | None,
    limit: int,
    device_type: DeviceType | None = None,
) -> list[TopEventRow]:
    """Return the top api_hit rows grouped by (endpoint, method).

    Used when the API tab is the active category — api_hit is a single
    event that fans out across every HTTP route, so grouping by event_name
    collapses everything into one row. Grouping by the flat endpoint/method
    columns instead surfaces per-route hits like "POST /utubs/<utub_id>/urls".

    When `resource` is provided, narrows the result to rows whose `endpoint`
    matches the resource's URL-prefix bucket (see `Resource` taxonomy).
    """
    total_count = func.sum(Anonymous_Metrics.count).label("total_count")
    query = db.session.query(
        Anonymous_Metrics.endpoint,
        Anonymous_Metrics.method,
        total_count,
    ).filter(
        Anonymous_Metrics.event_name == EventName.API_HIT.value,
        Anonymous_Metrics.bucket_start >= window_start,
        Anonymous_Metrics.bucket_start < window_end,
        Anonymous_Metrics.endpoint.isnot(None),
        Anonymous_Metrics.method.isnot(None),
    )
    if resource is not None:
        query = query.filter(
            resource_filter_clause(category=EventCategory.API, resource=resource)
        )
    query = _device_type_filter(query, device_type)
    rows = (
        query.group_by(Anonymous_Metrics.endpoint, Anonymous_Metrics.method)
        .order_by(
            func.sum(Anonymous_Metrics.count).desc(),
            Anonymous_Metrics.endpoint.asc(),
            Anonymous_Metrics.method.asc(),
        )
        .limit(limit)
        .all()
    )
    previous_counts = _per_endpoint_counts(
        window_start=previous_window_start,
        window_end=previous_window_end,
        device_type=device_type,
    )
    endpoint_metadata = _endpoint_metadata_map()
    return [
        TopEventRow(
            event_name=(
                f"{row.method} "
                f"{endpoint_metadata[row.endpoint].url_pattern if row.endpoint in endpoint_metadata else row.endpoint}"
            ),
            category=EventCategory.API.value,
            description=(
                endpoint_metadata[row.endpoint].description
                if row.endpoint in endpoint_metadata
                else ""
            ),
            api_endpoint=row.endpoint,
            total_count=int(row.total_count),
            previous_count=previous_counts.get((row.endpoint, row.method), 0),
        )
        for row in rows
    ]


def top_events(
    *,
    window_start: datetime,
    window_end: datetime,
    previous_window_start: datetime,
    previous_window_end: datetime,
    category: EventCategory | None,
    limit: int,
    resource: Resource | None = None,
    device_type: DeviceType | None = None,
) -> list[TopEventRow]:
    """Return the top events by total count inside the half-open window.

    `window_start` is inclusive, `window_end` is exclusive — matches the
    convention used throughout the metrics pipeline. When `category` is
    provided, only rows in that EventCategory are considered. Rows are
    ordered by total_count descending and capped at `limit`.

    `previous_window_start`/`previous_window_end` define the equal-length
    interval immediately preceding `(start, end)` (callers compute via
    `previous_window()`). Each returned row carries `previous_count` for the
    same event in that interval; missing events get 0 so the dashboard's
    Δ-vs-prev column has a number even for newly-seen events.

    When `category == EventCategory.API`, rows are aggregated by the flat
    `(endpoint, method)` columns on api_hit rather than by event_name — api_hit
    is a single auto-instrumented event that spans every HTTP route, so a
    per-event-name aggregation collapses every endpoint into a single row.

    `resource` further narrows the result within the chosen `category`. For
    UI/Domain it filters on `event_name`; for API it filters on the route
    prefix in the `endpoint` column. Callers MUST cross-validate the
    `(category, resource)` pair before invoking (see `RESOURCE_BY_CATEGORY`).
    """
    if category is EventCategory.API:
        return _top_endpoints_for_api_hit(
            window_start=window_start,
            window_end=window_end,
            previous_window_start=previous_window_start,
            previous_window_end=previous_window_end,
            resource=resource,
            limit=limit,
            device_type=device_type,
        )

    total_count = func.sum(Anonymous_Metrics.count).label("total_count")
    query = (
        db.session.query(
            Anonymous_Metrics.event_name,
            Event_Registry.category,
            Event_Registry.description,
            total_count,
        )
        .join(Event_Registry, Event_Registry.name == Anonymous_Metrics.event_name)
        .filter(
            Anonymous_Metrics.bucket_start >= window_start,
            Anonymous_Metrics.bucket_start < window_end,
        )
    )
    if category is not None:
        query = query.filter(Event_Registry.category == category)
    if resource is not None and category is not None:
        query = query.filter(
            resource_filter_clause(category=category, resource=resource)
        )
    query = _device_type_filter(query, device_type)

    rows = (
        query.group_by(
            Anonymous_Metrics.event_name,
            Event_Registry.category,
            Event_Registry.description,
        )
        .order_by(
            func.sum(Anonymous_Metrics.count).desc(),
            Anonymous_Metrics.event_name.asc(),
        )
        .limit(limit)
        .all()
    )

    previous_counts = _per_event_counts(
        window_start=previous_window_start,
        window_end=previous_window_end,
        category=category,
        device_type=device_type,
    )

    return [
        TopEventRow(
            event_name=row.event_name,
            category=row.category.value,
            description=row.description,
            total_count=int(row.total_count),
            previous_count=previous_counts.get(row.event_name, 0),
        )
        for row in rows
    ]


_RESOLUTION_STEP: dict[Literal["hour", "day"], timedelta] = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
}


def _truncate_to_resolution(
    dt: datetime, resolution: Literal["hour", "day"]
) -> datetime:
    """Floor a datetime to the start of its hour or day, preserving tzinfo.

    Matches Postgres `date_trunc(resolution, ts)` semantics in UTC so the keys
    produced here align byte-for-byte with the truncated keys SQL returns,
    enabling dict-lookup zero-fill in `timeseries()`.

    Examples:
        >>> _truncate_to_resolution(datetime(2026, 6, 8, 14, 37, 5), "hour")
        datetime.datetime(2026, 6, 8, 14, 0)
        >>> _truncate_to_resolution(datetime(2026, 6, 8, 14, 37, 5), "day")
        datetime.datetime(2026, 6, 8, 0, 0)
    """
    if resolution == "hour":
        return dt.replace(minute=0, second=0, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


# Why: `resolution` finer than the writer's METRICS_BUCKET_SECONDS=3600 floor
# collapses to the bucket granularity — the writer always stores hour-aligned
# rows, so sub-hour resolutions would just return the same hourly buckets.
def timeseries(
    *,
    event_name: EventName,
    window_start: datetime,
    window_end: datetime,
    resolution: Literal["hour", "day"],
    endpoint: str | None = None,
    method: str | None = None,
    device_type: DeviceType | None = None,
) -> list[TimeseriesBucketSchema]:
    """Return per-bucket counts for `event_name` inside the half-open window.

    `resolution` is a Postgres `date_trunc` field name — narrowed to the
    `Literal["hour", "day"]` set so any caller passing arbitrary text is
    flagged at type-check time, providing defense-in-depth on top of the
    Pydantic schema validation at the HTTP boundary. Buckets are returned
    in chronological order; the underlying rows are already hour-aligned
    at write time, so passing "hour" returns the raw buckets and "day"
    aggregates them.

    Zero-fills empty intervals: every resolution-aligned bucket inside
    `[window_start, window_end)` appears in the result, with count=0 when no
    rows exist for that bucket. Keeps the chart visually meaningful during
    low-traffic stretches (a Day window with one event still returns 24
    hourly buckets, all but one at zero) and removes the need for the
    frontend to know the window range to draw an x-axis.

    Optional `endpoint`/`method` narrow the series to a single api_hit
    (endpoint, method) pair — used by the admin dashboard's API tab to
    chart per-endpoint timeseries (event_name=api_hit otherwise collapses
    every API route into one aggregate series).
    """
    bucket = func.date_trunc(resolution, Anonymous_Metrics.bucket_start).label("bucket")
    query = db.session.query(
        bucket,
        func.sum(Anonymous_Metrics.count).label("count"),
    ).filter(
        Anonymous_Metrics.event_name == event_name.value,
        Anonymous_Metrics.bucket_start >= window_start,
        Anonymous_Metrics.bucket_start < window_end,
    )
    if endpoint is not None:
        query = query.filter(Anonymous_Metrics.endpoint == endpoint)
    if method is not None:
        query = query.filter(Anonymous_Metrics.method == method)
    query = _device_type_filter(query, device_type)

    rows = query.group_by(bucket).order_by(bucket).all()
    counts_by_bucket: dict[datetime, int] = {row.bucket: int(row.count) for row in rows}

    # Emit one bucket per aligned interval that overlaps the half-open window
    # `[window_start, window_end)`. The first bucket is `truncate(window_start)`
    # — possibly with `bucket_start` strictly before `window_start` — because
    # SQL `date_trunc(resolution, x)` groups rows by the same truncated key, so
    # rows in that partial leading bucket DO land here. Skipping it would emit
    # a zero where data actually exists. For hour resolution + hour-aligned
    # writes, the partial leading bucket happens to contain no rows; for day
    # resolution + an unaligned window_start, it commonly contains data.
    step = _RESOLUTION_STEP[resolution]
    first_bucket = _truncate_to_resolution(window_start, resolution)

    filled_buckets: list[TimeseriesBucketSchema] = []
    cursor = first_bucket
    while cursor < window_end:
        filled_buckets.append(
            TimeseriesBucketSchema(bucket=cursor, count=counts_by_bucket.get(cursor, 0))
        )
        cursor = cursor + step
    return filled_buckets


def _is_device_type_dim(event_name: EventName, group_by_key: str) -> bool:
    """Return True when the dim field is typed as `DeviceType` on the dim model.

    Why: the writer stores `device_type` as an integer (DeviceType IntEnum
    value) inside the JSONB `dimensions` column. Postgres' JSONB extraction
    needs `.as_integer()` for these values vs `.as_string()` for Literal-typed
    string dims. Branching on the dim model's annotation keeps the SQL
    generation aligned with the storage shape.
    """
    dim_model = DIMENSION_MODELS[event_name]
    if dim_model is None:
        return False
    field_info = dim_model.model_fields.get(group_by_key)
    if field_info is None:
        return False
    annotation = field_info.annotation
    # `Annotated[DeviceType, BeforeValidator(...)]` resolves the runtime
    # annotation to `DeviceType` itself, so a direct `is`/`issubclass` works.
    return annotation is DeviceType or (
        isinstance(annotation, type) and issubclass(annotation, DeviceType)
    )


def grouped_timeseries(
    *,
    event_name: EventName,
    group_by: list[str],
    window_start: datetime,
    window_end: datetime,
    resolution: Literal["hour", "day"],
) -> GroupedTimeseriesResponseSchema:
    """Return per-bucket counts split by a dimension tuple.

    Returns one row per `(date_trunc(bucket), group_by[0], group_by[1], ...)`
    combination inside the half-open window `[window_start, window_end)`.
    Unlike `timeseries`, this helper does NOT zero-fill empty combinations —
    the cross product of buckets × dim values can explode quickly, and the
    frontend renderer treats absent combinations as "no segment for that
    bucket".

    `group_by` must contain field names declared on
    `DIMENSION_MODELS[event_name]`. The HTTP route schema bounds the list at
    1-3 entries; this helper raises `ValueError` if any entry is unknown, so
    the route can map the error to a 400 response.
    """
    dim_model = DIMENSION_MODELS[event_name]
    valid_fields: set[str] = (
        set(dim_model.model_fields.keys()) if dim_model is not None else set()
    )
    unknown_keys = [key for key in group_by if key not in valid_fields]
    if unknown_keys:
        raise ValueError(
            f"Unknown group_by key(s) for event '{event_name.value}': "
            f"{', '.join(unknown_keys)}. Valid keys: "
            f"{', '.join(sorted(valid_fields)) or '(none)'}."
        )

    bucket_column = func.date_trunc(resolution, Anonymous_Metrics.bucket_start).label(
        "bucket"
    )
    dim_columns = []
    for group_by_index, group_by_key in enumerate(group_by):
        if _is_device_type_dim(event_name, group_by_key):
            dim_column = Anonymous_Metrics.dimensions[group_by_key].as_integer()
        else:
            dim_column = Anonymous_Metrics.dimensions[group_by_key].as_string()
        dim_columns.append(dim_column.label(f"dim{group_by_index}"))

    count_column = func.sum(Anonymous_Metrics.count).label("count")
    query = db.session.query(bucket_column, *dim_columns, count_column).filter(
        Anonymous_Metrics.event_name == event_name.value,
        Anonymous_Metrics.bucket_start >= window_start,
        Anonymous_Metrics.bucket_start < window_end,
    )
    rows = (
        query.group_by(bucket_column, *dim_columns)
        .order_by(bucket_column, *dim_columns)
        .all()
    )

    buckets: list[GroupedTimeseriesBucket] = []
    for row in rows:
        dim_values: dict[str, str | int] = {}
        for group_by_index, group_by_key in enumerate(group_by):
            raw_value = row[group_by_index + 1]
            if raw_value is None:
                # Rows missing the dim entirely shouldn't be silently grouped
                # into a NULL bucket — skip them so the response shape stays
                # consistent with declared `group_by` keys.
                break
            dim_values[group_by_key] = raw_value
        else:
            buckets.append(
                GroupedTimeseriesBucket(
                    bucket=row.bucket,
                    dimensions=dim_values,
                    count=int(row.count),
                )
            )

    return GroupedTimeseriesResponseSchema(
        event_name=event_name.value,
        window=None,
        resolution=resolution,
        window_start=window_start,
        window_end=window_end,
        group_by=list(group_by),
        buckets=buckets,
    )


_API_FLAT_COLUMNS: dict[str, object] = {
    "endpoint": Anonymous_Metrics.endpoint,
    "method": Anonymous_Metrics.method,
    "status_code": Anonymous_Metrics.status_code,
}


def _raise_on_unknown_keys(
    event_name: EventName,
    dim_filter: list[tuple[str, str]],
    group_by: str | None,
    valid_fields: set[str],
) -> None:
    """Raise `ValueError` if any filter/group_by key is outside `valid_fields`."""
    requested_keys = [dim_key for dim_key, _ in dim_filter]
    if group_by is not None:
        requested_keys.append(group_by)
    unknown_keys = [key for key in requested_keys if key not in valid_fields]
    if unknown_keys:
        raise ValueError(
            f"Unknown filter/group_by key(s) for event '{event_name.value}': "
            f"{', '.join(unknown_keys)}. Valid keys: "
            f"{', '.join(sorted(valid_fields)) or '(none)'}."
        )


def _cast_int_filter(field: str, value: str) -> int:
    """Cast an integer-typed filter value to `int` with a controlled error.

    Both `status_code` (an integer column) and `device_type` (a JSONB value
    compared via `.as_integer()`) require an integer filter value. A bare
    `int()` ValueError on a non-numeric value would leak the raw user input
    into the 400 response body, so this wraps it in a fixed-shape message
    keyed only by the field name.
    """
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"filter value for {field} must be an integer")


class _GroupedCountQuery(NamedTuple):
    """The validated, category-resolved pieces of a grouped-count query.

    `base_filters` is the half-open-window + `dim_filter` predicate list shared
    by both the scalar and grouped queries. `group_column` is the resolved
    grouping expression (flat column or JSONB extraction) when `group_by` is
    set, else `None`.
    """

    base_filters: list
    group_column: object | None


def _build_grouped_count_query(
    *,
    event_name: EventName,
    window_start: datetime,
    window_end: datetime,
    dim_filter: list[tuple[str, str]],
    group_by: str | None,
) -> _GroupedCountQuery:
    """Validate keys and resolve the filter/group expressions for one event.

    Dimension resolution is category-aware so the `/flow` fan-out can slice
    every metric stream uniformly:
      * For API-category events (`EVENT_CATEGORY[event_name] is
        EventCategory.API`), `dim_filter` / `group_by` keys are validated
        against the flat promoted columns `{"endpoint", "method",
        "status_code"}` and issued as direct column comparisons. `status_code`
        filter values are cast to `int` (it is an integer column); a
        non-numeric value raises a controlled `ValueError`.
      * For all other events, keys are validated against
        `DIMENSION_MODELS[event_name].model_fields` and applied as JSONB
        `dimensions[...]` extraction (`.as_integer()` for `device_type`,
        `.as_string()` otherwise) — mirroring `grouped_timeseries`.

    Raises `ValueError` on any unknown filter/group_by key (or a non-integer
    `status_code` / `device_type` value) so the route layer can map it to a 400.
    """
    is_api_event = EVENT_CATEGORY[event_name] is EventCategory.API
    base_filters = [
        Anonymous_Metrics.event_name == event_name.value,
        Anonymous_Metrics.bucket_start >= window_start,
        Anonymous_Metrics.bucket_start < window_end,
    ]

    if is_api_event:
        valid_fields = set(_API_FLAT_COLUMNS.keys())
        _raise_on_unknown_keys(event_name, dim_filter, group_by, valid_fields)
        for dim_key, dim_value in dim_filter:
            column = _API_FLAT_COLUMNS[dim_key]
            if dim_key == "status_code":
                base_filters.append(column == _cast_int_filter(dim_key, dim_value))
            else:
                base_filters.append(column == dim_value)
        group_column = _API_FLAT_COLUMNS[group_by] if group_by is not None else None
    else:
        dim_model = DIMENSION_MODELS[event_name]
        valid_fields = (
            set(dim_model.model_fields.keys()) if dim_model is not None else set()
        )
        _raise_on_unknown_keys(event_name, dim_filter, group_by, valid_fields)
        for dim_key, dim_value in dim_filter:
            if _is_device_type_dim(event_name, dim_key):
                base_filters.append(
                    Anonymous_Metrics.dimensions[dim_key].as_integer()
                    == _cast_int_filter(dim_key, dim_value)
                )
            else:
                base_filters.append(
                    Anonymous_Metrics.dimensions[dim_key].as_string() == dim_value
                )
        if group_by is not None:
            if _is_device_type_dim(event_name, group_by):
                group_column = Anonymous_Metrics.dimensions[group_by].as_integer()
            else:
                group_column = Anonymous_Metrics.dimensions[group_by].as_string()
        else:
            group_column = None

    return _GroupedCountQuery(base_filters=base_filters, group_column=group_column)


def grouped_count_scalar(
    *,
    event_name: EventName,
    window_start: datetime,
    window_end: datetime,
    dim_filter: list[tuple[str, str]] | None = None,
) -> int:
    """Return the summed `count` of one event over a window as a scalar `int`.

    Sums every row matching the half-open window `[window_start, window_end)`
    and every `dim_filter` predicate. Returns `0` when no rows match.

    See `_build_grouped_count_query` for the category-aware key validation and
    the `ValueError` it raises on unknown / non-integer filter keys.

    Examples:
        grouped_count_scalar(
            event_name=EventName.API_HIT,
            window_start=start, window_end=end,
            dim_filter=[("endpoint", "urls.create_url"), ("method", "POST")],
        )
        -> 57
    """
    query_parts = _build_grouped_count_query(
        event_name=event_name,
        window_start=window_start,
        window_end=window_end,
        dim_filter=dim_filter or [],
        group_by=None,
    )
    count_column = func.sum(Anonymous_Metrics.count).label("count")
    total: int | None = (
        db.session.query(count_column).filter(*query_parts.base_filters).scalar()
    )
    return int(total) if total is not None else 0


def grouped_count_by(
    *,
    event_name: EventName,
    window_start: datetime,
    window_end: datetime,
    group_by: str,
    dim_filter: list[tuple[str, str]] | None = None,
) -> list[tuple[str, int]]:
    """Return per-group `(group_value, count)` pairs for one event over a window.

    Groups every row matching the half-open window `[window_start, window_end)`
    and every `dim_filter` predicate by `group_by`, returning one
    `(group_value, count)` tuple per distinct value ordered descending by
    count. Rows with a NULL group value are skipped.

    See `_build_grouped_count_query` for the category-aware key validation and
    the `ValueError` it raises on unknown / non-integer filter keys.

    Examples:
        grouped_count_by(
            event_name=EventName.UI_FORM_CANCEL,
            window_start=start, window_end=end,
            dim_filter=[("form", "utub_create")], group_by="trigger",
        )
        -> [("escape_key", 12), ("cancel_button", 4)]
    """
    query_parts = _build_grouped_count_query(
        event_name=event_name,
        window_start=window_start,
        window_end=window_end,
        dim_filter=dim_filter or [],
        group_by=group_by,
    )
    count_column = func.sum(Anonymous_Metrics.count).label("count")
    labelled_group = query_parts.group_column.label("group_value")
    rows = (
        db.session.query(labelled_group, count_column)
        .filter(*query_parts.base_filters)
        .group_by(labelled_group)
        .order_by(count_column.desc())
        .all()
    )
    return [
        (str(row.group_value), int(row.count))
        for row in rows
        if row.group_value is not None
    ]


def _by_category(start: datetime, end: datetime) -> dict[str, int]:
    """Sum counts grouped by EventCategory inside the half-open window.

    `Event_Registry.category` is a SQLAlchemy `Enum(EventCategory, ...)`
    column, so SQLAlchemy returns Python EventCategory enum instances —
    call `.value` so the result dict is keyed by the StrEnum value
    ("api"/"domain"/"ui") rather than the enum object itself. Pydantic's
    `SummaryCategoryCount.category: str` would otherwise reject the enum.
    """
    rows = (
        db.session.query(
            Event_Registry.category,
            func.sum(Anonymous_Metrics.count).label("total"),
        )
        .join(Event_Registry, Event_Registry.name == Anonymous_Metrics.event_name)
        .filter(
            Anonymous_Metrics.bucket_start >= start,
            Anonymous_Metrics.bucket_start < end,
        )
        .group_by(Event_Registry.category)
        .all()
    )
    return {row.category.value: int(row.total) for row in rows}


def summary(
    *,
    window_start: datetime,
    window_end: datetime,
    previous_window_start: datetime,
    previous_window_end: datetime,
) -> SummaryResult:
    """Return per-category totals plus two orthogonal freshness timestamps.

    Missing categories are filled with 0 so both `current` and `previous`
    are always integers. Result is sorted by category value so the wire
    shape is deterministic across calls.

    `last_flush_at` is the flush worker's liveness sentinel — a Unix epoch
    stamped by `scripts/flush_metrics.py` on every successful run (including
    empty flushes). Reflects worker cadence, NOT data freshness: advances
    every minute regardless of traffic. Returns None when metrics are
    disabled, the sentinel is absent, or Redis is unreachable.

    `last_event_at` is `MAX(bucket_start)` across the entire
    `AnonymousMetrics` table — NOT restricted to the queried window. Reflects
    when the most recent event was bucketed: advances only when traffic
    lands. Returns None when the table is empty.

    The two are surfaced separately so an admin can distinguish "worker is
    dead" (`last_flush_at` stale) from "nobody is using the app right now"
    (`last_event_at` old, `last_flush_at` fresh).
    """
    current_dict = _by_category(window_start, window_end)
    previous_dict = _by_category(previous_window_start, previous_window_end)
    by_category_list = [
        SummaryCategoryCount(
            category=category_value,
            current=current_dict.get(category_value, 0),
            previous=previous_dict.get(category_value, 0),
        )
        for category_value in sorted({*current_dict, *previous_dict})
    ]
    last_event_at: datetime | None = db.session.query(
        func.max(Anonymous_Metrics.bucket_start)
    ).scalar()

    # Safe under multiprocess gunicorn: each worker has its own MetricsWriter instance,
    # but get_last_flush_success_epoch() reads the flush sentinel from Redis (shared
    # across all workers), so every worker sees the same last-flush timestamp.
    writer: MetricsWriter | None = current_app.extensions.get("metrics_writer")
    last_flush_at: datetime | None = None
    if writer is not None:
        last_flush_epoch = writer.get_last_flush_success_epoch()
        if last_flush_epoch is not None:
            last_flush_at = datetime.fromtimestamp(last_flush_epoch, tz=timezone.utc)

    return SummaryResult(
        by_category=by_category_list,
        last_flush_at=last_flush_at,
        last_event_at=last_event_at,
    )


def _gauge_sample_from_row(row: Anonymous_Gauges) -> GaugeSampleSchema:
    """Build one `GaugeSampleSchema` from a stored gauge row.

    `value_float` is stored as `Numeric(20, 6)`, which SQLAlchemy returns as a
    `Decimal`; cast it to `float` so the response serializes as a JSON number
    rather than a string. `value_int` is already a Python `int`.
    """
    return GaugeSampleSchema(
        sampled_at=row.sampled_at,
        value_int=row.value_int,
        value_float=None if row.value_float is None else float(row.value_float),
    )


def gauges_timeseries_all(
    *,
    window: str | None,
    window_start: datetime,
    window_end: datetime,
) -> GaugesTimeseriesResponseSchema:
    """Return every gauge's windowed sample series in one batched response.

    Selects all `Anonymous_Gauges` rows whose `sampled_at` falls in the
    half-open window `[window_start, window_end)`, ordered by
    `("gaugeName", "sampledAt")`, then groups them per gauge in a single scan.
    Each `GaugeSeries` folds in the gauge's `kind` + `description` (read inline
    from `GAUGE_REGISTRY`) so the dashboard needs no separate metadata
    round-trip to render a card. A gauge with no rows in the window is
    simply absent from `gauges` — the renderer pads nothing.

    Mirrors `grouped_timeseries`'s batched envelope shape: the route threads the
    original `window` query value back into the response so the wire payload
    reflects the client's request shape.
    """
    rows = (
        db.session.query(Anonymous_Gauges)
        .filter(
            Anonymous_Gauges.sampled_at >= window_start,
            Anonymous_Gauges.sampled_at < window_end,
        )
        .order_by(Anonymous_Gauges.gauge_name, Anonymous_Gauges.sampled_at)
        .all()
    )

    samples_by_gauge: dict[str, list[GaugeSampleSchema]] = {}
    for row in rows:
        samples_by_gauge.setdefault(row.gauge_name, []).append(
            _gauge_sample_from_row(row)
        )

    gauge_series: list[GaugeSeries] = []
    # Emit in GaugeName declaration order so the dashboard's chart order is
    # deterministic regardless of insertion order in the table.
    for gauge_name in GaugeName:
        samples = samples_by_gauge.get(gauge_name.value)
        if not samples:
            continue
        gauge_series.append(
            GaugeSeries(
                gauge_name=gauge_name.value,
                kind=GAUGE_REGISTRY[gauge_name].kind.value,
                description=GAUGE_REGISTRY[gauge_name].description,
                samples=samples,
            )
        )

    return GaugesTimeseriesResponseSchema(
        window=window,
        window_start=window_start,
        window_end=window_end,
        gauges=gauge_series,
    )


def gauge_timeseries_one(
    *,
    gauge_name: GaugeName,
    window_start: datetime,
    window_end: datetime,
) -> list[GaugeSampleSchema]:
    """Return one gauge's window-filtered samples, ordered by `sampled_at`.

    A per-name helper backing the `flask metrics gauge-timeseries --name` CLI
    only — the batched HTTP endpoint never calls this. Selects rows where
    `gaugeName == gauge_name.value` and `sampledAt` is in the half-open window
    `[window_start, window_end)`.
    """
    rows = (
        db.session.query(Anonymous_Gauges)
        .filter(
            Anonymous_Gauges.gauge_name == gauge_name.value,
            Anonymous_Gauges.sampled_at >= window_start,
            Anonymous_Gauges.sampled_at < window_end,
        )
        .order_by(Anonymous_Gauges.sampled_at)
        .all()
    )
    return [_gauge_sample_from_row(row) for row in rows]
