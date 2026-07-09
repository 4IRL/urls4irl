from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone

from flask import current_app
from redis import Redis
from sqlalchemy import text

from backend import db
from backend.app_logger import warning_log
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.metrics_strs import METRICS_REDIS

STATUS_UP: str = "up"
STATUS_DOWN: str = "down"
STATUS_NOT_CONFIGURED: str = "not configured"

_MEMORY_URI: str = "memory://"
_DISK_PROBE_PATH: str = "/"


@dataclass(frozen=True)
class HealthSnapshot:
    """Point-in-time operational health of the stack, as seen from the web
    container. All probes are independent — one failing subsystem never
    hides the status of another."""

    database_status: str
    database_connection_count: int | None
    session_redis_status: str
    metrics_redis_status: str
    disk_used_percent: float | None
    flush_last_success_at: datetime | None
    gauge_last_sample_at: datetime | None
    captured_at: datetime


def _probe_database() -> tuple[str, int | None]:
    """Return (status, active connection count) for Postgres.

    The connection count comes from ``pg_stat_activity`` and includes every
    session on the server, not just this app's pool.
    """
    try:
        db.session.execute(text("SELECT 1"))
        connection_count_row = db.session.execute(
            text("SELECT count(*) FROM pg_stat_activity")
        ).scalar()
        return STATUS_UP, int(connection_count_row)
    except Exception as database_error:
        warning_log(f"health snapshot: database probe failed: {database_error}")
        return STATUS_DOWN, None


def _probe_session_redis() -> str:
    session_redis: Redis | None = current_app.config.get("SESSION_REDIS")
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


def _probe_metrics_redis() -> tuple[str, datetime | None, datetime | None]:
    """Return (status, flush last-success, gauge last-sample) for the
    metrics Redis.

    The two timestamps are the workflow sidecar's liveness sentinels —
    ``flush_metrics.py`` and ``sample_gauges.py`` stamp them after each
    successful cron run, so they double as "sidecar cron last ran" signals
    readable from the web container.
    """
    metrics_uri: str | None = current_app.config.get(CONFIG_ENVS.METRICS_REDIS_URI)
    if not metrics_uri or metrics_uri == _MEMORY_URI:
        return STATUS_NOT_CONFIGURED, None, None
    metrics_redis: Redis | None = None
    try:
        metrics_redis = Redis.from_url(metrics_uri)
        metrics_redis.ping()
        flush_epoch = metrics_redis.get(METRICS_REDIS.FLUSH_LAST_SUCCESS_KEY)
        gauge_epoch = metrics_redis.get(METRICS_REDIS.GAUGE_LAST_SUCCESS_KEY)
        return (
            STATUS_UP,
            _epoch_bytes_to_datetime(flush_epoch),
            _epoch_bytes_to_datetime(gauge_epoch),
        )
    except Exception as redis_error:
        warning_log(f"health snapshot: metrics redis probe failed: {redis_error}")
        return STATUS_DOWN, None, None
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
    except OSError as disk_error:
        warning_log(f"health snapshot: disk probe failed: {disk_error}")
        return None


def collect_health_snapshot() -> HealthSnapshot:
    """Probe every subsystem once and return a frozen snapshot.

    Never raises: each probe degrades to a "down"/None value on failure so
    the dashboard always renders.
    """
    database_status, database_connection_count = _probe_database()
    session_redis_status = _probe_session_redis()
    metrics_redis_status, flush_last_success_at, gauge_last_sample_at = (
        _probe_metrics_redis()
    )
    return HealthSnapshot(
        database_status=database_status,
        database_connection_count=database_connection_count,
        session_redis_status=session_redis_status,
        metrics_redis_status=metrics_redis_status,
        disk_used_percent=_probe_disk_used_percent(),
        flush_last_success_at=flush_last_success_at,
        gauge_last_sample_at=gauge_last_sample_at,
        captured_at=datetime.now(timezone.utc),
    )
