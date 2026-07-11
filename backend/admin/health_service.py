from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
import shutil

from flask import current_app
from redis import Redis
from sqlalchemy import func, text

from backend import db
from backend.app_logger import warning_log
from backend.metrics.events import EventName
from backend.metrics.latency import LatencyMetricName
from backend.metrics.query_service import latency_percentiles
from backend.models.anonymous_metrics import Anonymous_Metrics
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.metrics_strs import METRICS_REDIS

STATUS_UP: str = "up"
STATUS_DOWN: str = "down"
STATUS_NOT_CONFIGURED: str = "not configured"

_MEMORY_URI: str = "memory://"
_DISK_PROBE_PATH: str = "/"
# Flask-Session stores the live Redis client under this config key when
# SESSION_TYPE == "redis" (see backend/config.py); absent under cachelib.
_SESSION_REDIS_CONFIG_KEY: str = "SESSION_REDIS"

# Lookback windows for the derived operational stats.
_SLOWEST_ENDPOINT_WINDOW_DAYS: int = 7
_ERROR_RATE_WINDOW_HOURS: int = 24
_BUSIEST_ENDPOINT_WINDOW_HOURS: int = 24
# HTTP status at or above which a response is counted as a server-side error.
_SERVER_ERROR_STATUS_THRESHOLD: int = 500
# Flush-worker liveness threshold: a flush sentinel older than this many seconds
# means the Redis -> Postgres flush cron has not completed a run recently.
_FLUSH_STALE_THRESHOLD_SECONDS: int = 900
# Backup staleness threshold: the daily backup cron runs at 1 AM, so a
# last-success sentinel older than 26 hours (24h cadence + 2h grace) means a
# scheduled backup was missed or failed.
_BACKUP_STALE_THRESHOLD_SECONDS: int = 26 * 3600

# Host memory is read from the Linux procfs meminfo pseudo-file.
_MEMINFO_PATH: str = "/proc/meminfo"
_MEMINFO_TOTAL_KEY: str = "MemTotal"
_MEMINFO_AVAILABLE_KEY: str = "MemAvailable"


@dataclass(frozen=True)
class SlowestEndpoint:
    """The single slowest (endpoint, method) by p95 latency over the window."""

    endpoint: str
    method: str
    p95_ms: float
    approximate: bool


@dataclass(frozen=True)
class ErrorRate:
    """Server-error (5xx) share of API traffic over the recent window."""

    error_count: int
    total_count: int
    rate: float


@dataclass(frozen=True)
class BusiestEndpoint:
    """The single highest-volume (endpoint, method) by hit count over the window."""

    endpoint: str
    method: str
    hit_count: int


@dataclass(frozen=True)
class SystemResources:
    """Host-scoped CPU load average and memory utilization.

    HOST-scoped inside Docker: both signals report the Docker host's
    kernel-wide state, NOT this container's cgroup limits.
    """

    load_avg_1m: float
    memory_used_percent: float


@dataclass(frozen=True)
class HealthSnapshot:
    """Point-in-time operational health of the stack, as seen from the web
    container. All probes are independent — one failing subsystem never
    hides the status of another."""

    database_status: str
    database_connection_count: int | None
    database_max_connections: int | None
    session_redis_status: str
    metrics_redis_status: str
    disk_used_percent: float | None
    flush_last_success_at: datetime | None
    flush_lag_seconds: int | None
    flush_is_stale: bool
    gauge_last_sample_at: datetime | None
    backup_last_success_at: datetime | None
    backup_lag_seconds: int | None
    backup_is_stale: bool
    slowest_endpoint: SlowestEndpoint | None
    error_rate: ErrorRate | None
    busiest_endpoint: BusiestEndpoint | None
    system_resources: SystemResources | None
    captured_at: datetime


def _probe_database() -> tuple[str, int | None, int | None]:
    """Return (status, active connection count, max connections) for Postgres.

    The connection count comes from ``pg_stat_activity`` and includes every
    session on the server, not just this app's pool. ``max_connections`` is the
    server's configured connection ceiling (``SHOW max_connections``), so the
    dashboard can render "connections vs max".
    """
    try:
        db.session.execute(text("SELECT 1"))
        connection_count_row = db.session.execute(
            text("SELECT count(*) FROM pg_stat_activity")
        ).scalar()
        max_connections_row = db.session.execute(text("SHOW max_connections")).scalar()
        return STATUS_UP, int(connection_count_row), int(max_connections_row)
    except Exception as database_error:
        warning_log(f"health snapshot: database probe failed: {database_error}")
        return STATUS_DOWN, None, None


def _probe_session_redis() -> str:
    session_redis: Redis | None = current_app.config.get(_SESSION_REDIS_CONFIG_KEY)
    if session_redis is None:
        return STATUS_NOT_CONFIGURED
    try:
        session_redis.ping()
        return STATUS_UP
    except Exception as redis_error:
        warning_log(f"health snapshot: session redis probe failed: {redis_error}")
        return STATUS_DOWN


def _epoch_bytes_to_datetime(epoch_bytes: bytes | None) -> datetime | None:
    if epoch_bytes is None:
        return None
    try:
        return datetime.fromtimestamp(int(epoch_bytes), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _probe_metrics_redis() -> (
    tuple[str, datetime | None, datetime | None, datetime | None]
):
    """Return (status, flush last-success, gauge last-sample, backup
    last-success) for the metrics Redis.

    The three timestamps are the workflow sidecar's liveness sentinels —
    ``flush_metrics.py``, ``sample_gauges.py``, and ``backup_sentinel.py``
    (via ``daily-docker.sh``) stamp them after each successful run, so they
    double as "sidecar cron last ran" signals readable from the web container.
    """
    metrics_uri: str | None = current_app.config.get(CONFIG_ENVS.METRICS_REDIS_URI)
    if not metrics_uri or metrics_uri == _MEMORY_URI:
        return STATUS_NOT_CONFIGURED, None, None, None
    metrics_redis: Redis | None = None
    try:
        metrics_redis = Redis.from_url(metrics_uri)
        metrics_redis.ping()
        flush_epoch = metrics_redis.get(METRICS_REDIS.FLUSH_LAST_SUCCESS_KEY)
        gauge_epoch = metrics_redis.get(METRICS_REDIS.GAUGE_LAST_SUCCESS_KEY)
        backup_epoch = metrics_redis.get(METRICS_REDIS.BACKUP_LAST_SUCCESS_KEY)
        return (
            STATUS_UP,
            _epoch_bytes_to_datetime(flush_epoch),
            _epoch_bytes_to_datetime(gauge_epoch),
            _epoch_bytes_to_datetime(backup_epoch),
        )
    except Exception as redis_error:
        warning_log(f"health snapshot: metrics redis probe failed: {redis_error}")
        return STATUS_DOWN, None, None, None
    finally:
        if metrics_redis is not None:
            try:
                metrics_redis.close()
            except Exception:
                pass


def _probe_disk_used_percent() -> float | None:
    try:
        disk_usage = shutil.disk_usage(_DISK_PROBE_PATH)
        return round(disk_usage.used / disk_usage.total * 100, 1)
    except Exception as disk_error:
        warning_log(f"health snapshot: disk probe failed: {disk_error}")
        return None


def _probe_slowest_endpoint() -> SlowestEndpoint | None:
    """Return the slowest (endpoint, method) by p95 over the last 7 days.

    Reuses the metrics query service's ``latency_percentiles`` (rows are already
    ordered by p95 descending), taking the top row. Returns ``None`` when there
    are no latency samples in the window.
    """
    try:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=_SLOWEST_ENDPOINT_WINDOW_DAYS)
        result = latency_percentiles(
            window_start=window_start,
            window_end=now,
            now=now,
            metric_name=LatencyMetricName.API_REQUEST_DURATION,
            limit=1,
        )
        if not result.rows:
            return None
        top_row = result.rows[0]
        return SlowestEndpoint(
            endpoint=top_row.endpoint,
            method=top_row.method,
            p95_ms=float(top_row.p95),
            approximate=result.approximate,
        )
    except Exception as slowest_error:
        warning_log(f"health snapshot: slowest endpoint probe failed: {slowest_error}")
        return None


def _probe_error_rate() -> ErrorRate | None:
    """Return the 5xx share of API_HIT traffic over the last 24 hours.

    ``rate`` is ``errors / total`` and is ``0.0`` when there was no traffic, so
    the caller never divides by zero. Returns ``None`` only on query failure.
    """
    try:
        window_start = datetime.now(timezone.utc) - timedelta(
            hours=_ERROR_RATE_WINDOW_HOURS
        )
        api_hit_in_window = (
            Anonymous_Metrics.event_name == EventName.API_HIT.value,
            Anonymous_Metrics.bucket_start >= window_start,
        )
        total_sum = (
            db.session.query(func.sum(Anonymous_Metrics.count))
            .filter(*api_hit_in_window)
            .scalar()
        )
        error_sum = (
            db.session.query(func.sum(Anonymous_Metrics.count))
            .filter(
                *api_hit_in_window,
                Anonymous_Metrics.status_code >= _SERVER_ERROR_STATUS_THRESHOLD,
            )
            .scalar()
        )
        total_count = int(total_sum) if total_sum is not None else 0
        error_count = int(error_sum) if error_sum is not None else 0
        rate = error_count / total_count if total_count > 0 else 0.0
        return ErrorRate(
            error_count=error_count,
            total_count=total_count,
            rate=rate,
        )
    except Exception as error_rate_error:
        warning_log(f"health snapshot: error rate probe failed: {error_rate_error}")
        return None


def _probe_busiest_endpoint() -> BusiestEndpoint | None:
    """Return the highest-volume (endpoint, method) API_HIT over the last 24h.

    A direct grouped query is used rather than the query service's
    ``_top_endpoints_for_api_hit`` helper: that helper requires previous-window
    parameters and rewrites the endpoint into a user-facing URL pattern, whereas
    the health card needs only the raw top (endpoint, method, count).
    """
    try:
        window_start = datetime.now(timezone.utc) - timedelta(
            hours=_BUSIEST_ENDPOINT_WINDOW_HOURS
        )
        hit_count = func.sum(Anonymous_Metrics.count).label("hit_count")
        top_row = (
            db.session.query(
                Anonymous_Metrics.endpoint,
                Anonymous_Metrics.method,
                hit_count,
            )
            .filter(
                Anonymous_Metrics.event_name == EventName.API_HIT.value,
                Anonymous_Metrics.bucket_start >= window_start,
                Anonymous_Metrics.endpoint.isnot(None),
                Anonymous_Metrics.method.isnot(None),
            )
            .group_by(Anonymous_Metrics.endpoint, Anonymous_Metrics.method)
            .order_by(hit_count.desc())
            .limit(1)
            .one_or_none()
        )
        if top_row is None:
            return None
        return BusiestEndpoint(
            endpoint=top_row.endpoint,
            method=top_row.method,
            hit_count=int(top_row.hit_count),
        )
    except Exception as busiest_error:
        warning_log(f"health snapshot: busiest endpoint probe failed: {busiest_error}")
        return None


def _parse_meminfo_value(meminfo_text: str, key: str) -> int | None:
    """Return the integer kB value for a ``/proc/meminfo`` key, or None if absent.

    ``/proc/meminfo`` lines look like ``MemTotal:       16334028 kB``; this
    finds the line starting with ``<key>:`` and reads its numeric field.

    Examples:
        >>> _parse_meminfo_value("MemTotal: 2048 kB\\nMemFree: 512 kB", "MemTotal")
        2048
        >>> _parse_meminfo_value("MemTotal: 2048 kB", "MemAvailable")
        None
    """
    for line in meminfo_text.splitlines():
        if line.startswith(f"{key}:"):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    return None


def _probe_system_resources() -> SystemResources | None:
    """Return host CPU load average (1-min) and memory utilization percent.

    HOST-scoped inside Docker: ``os.getloadavg()`` and ``/proc/meminfo`` report
    the Docker host's kernel-wide load and memory, NOT this container's cgroup
    limits. Every failure mode (non-Linux ``getloadavg``, missing/unreadable
    ``/proc/meminfo``, unparseable fields) degrades to ``None`` without raising.
    """
    try:
        load_avg_1m = os.getloadavg()[0]
    except (AttributeError, OSError):
        return None
    try:
        with open(_MEMINFO_PATH, "r", encoding="utf-8") as meminfo_file:
            meminfo_text = meminfo_file.read()
    except OSError:
        return None
    memory_total_kb = _parse_meminfo_value(meminfo_text, _MEMINFO_TOTAL_KEY)
    memory_available_kb = _parse_meminfo_value(meminfo_text, _MEMINFO_AVAILABLE_KEY)
    if memory_total_kb is None or memory_available_kb is None or memory_total_kb <= 0:
        return None
    memory_used_percent = round(
        (memory_total_kb - memory_available_kb) / memory_total_kb * 100, 1
    )
    return SystemResources(
        load_avg_1m=load_avg_1m,
        memory_used_percent=memory_used_percent,
    )


def collect_health_snapshot() -> HealthSnapshot:
    """Probe every subsystem once and return a frozen snapshot.

    Never raises: each probe degrades to a "down"/None value on failure so
    the dashboard always renders.
    """
    captured_at = datetime.now(timezone.utc)
    database_status, database_connection_count, database_max_connections = (
        _probe_database()
    )
    session_redis_status = _probe_session_redis()
    (
        metrics_redis_status,
        flush_last_success_at,
        gauge_last_sample_at,
        backup_last_success_at,
    ) = _probe_metrics_redis()

    flush_lag_seconds: int | None = None
    flush_is_stale: bool = False
    if flush_last_success_at is not None:
        flush_lag_seconds = int((captured_at - flush_last_success_at).total_seconds())
        flush_is_stale = flush_lag_seconds > _FLUSH_STALE_THRESHOLD_SECONDS

    backup_lag_seconds: int | None = None
    backup_is_stale: bool = False
    if backup_last_success_at is not None:
        backup_lag_seconds = int((captured_at - backup_last_success_at).total_seconds())
        backup_is_stale = backup_lag_seconds > _BACKUP_STALE_THRESHOLD_SECONDS

    return HealthSnapshot(
        database_status=database_status,
        database_connection_count=database_connection_count,
        database_max_connections=database_max_connections,
        session_redis_status=session_redis_status,
        metrics_redis_status=metrics_redis_status,
        disk_used_percent=_probe_disk_used_percent(),
        flush_last_success_at=flush_last_success_at,
        flush_lag_seconds=flush_lag_seconds,
        flush_is_stale=flush_is_stale,
        gauge_last_sample_at=gauge_last_sample_at,
        backup_last_success_at=backup_last_success_at,
        backup_lag_seconds=backup_lag_seconds,
        backup_is_stale=backup_is_stale,
        slowest_endpoint=_probe_slowest_endpoint(),
        error_rate=_probe_error_rate(),
        busiest_endpoint=_probe_busiest_endpoint(),
        system_resources=_probe_system_resources(),
        captured_at=captured_at,
    )
