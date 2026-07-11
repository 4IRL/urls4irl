from __future__ import annotations

import time

from flask import current_app
from redis import Redis

from backend import db
from backend.admin.constants import AdminActionErrorCodes
from backend.api_common.responses import FlaskResponse
from backend.app_logger import warning_log
from backend.db import get_missing_tables
from backend.extensions import audit
from backend.schemas.admin_actions import AdminOpsActionResponseSchema
from backend.schemas.errors import build_message_error_response
from backend.utils.short_urls import (
    ShortUrlSyncError,
    sync_short_url_domains_to_redis,
)
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts.flush_metrics import run_flush
from scripts.purge_audit_log import AUDIT_LOG_RETENTION_DAYS, run_purge
from scripts.sample_gauges import run_sample

_MEMORY_URI: str = "memory://"
# A pending backup request older than this has clearly been missed by the
# per-minute poller (workflow container down); let it age out rather than
# firing a surprise backup much later.
BACKUP_TRIGGER_TTL_SECONDS: int = 900


def _build_metrics_redis() -> Redis | None:
    """Build a metrics Redis client from config, or return None if unavailable.

    Returns None when METRICS_REDIS_URI is absent or set to the in-memory
    stub URI, matching the health-service availability check pattern.
    """
    metrics_uri: str | None = current_app.config.get(CONFIG_ENVS.METRICS_REDIS_URI)
    if not metrics_uri or metrics_uri == _MEMORY_URI:
        return None
    return Redis.from_url(metrics_uri)


def trigger_metrics_flush(*, actor_id: int, reason: str | None) -> FlaskResponse:
    """Trigger an immediate Redis-to-Postgres metrics counter flush.

    Acquires the same distributed lock the cron worker uses; returns count=0
    immediately (not an error) when another flush is already in progress and
    holds the lock. If METRICS_REDIS_URI is absent or memory://, returns 503.

    Args:
        actor_id: ID of the admin user triggering the flush.
        reason: Optional free-text reason recorded in the audit log.

    Returns:
        200 JSON envelope with count=rows flushed on success.
        503 when metrics Redis is not configured.
        500 on unexpected flush error.
    """
    metrics_redis = _build_metrics_redis()
    if metrics_redis is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_FLUSH_UNAVAILABLE,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=503,
        )

    raw_conn = db.engine.raw_connection()
    try:
        rows_flushed = run_flush(redis_client=metrics_redis, pg_conn=raw_conn)
    except Exception as flush_error:
        warning_log(f"admin ops: metrics flush failed: {flush_error}")
        audit.record(
            actor_id=actor_id,
            action=ADMIN_AUDIT_ACTIONS.OPS_METRICS_FLUSH,
            metadata={"reason": reason, "error": str(flush_error)},
        )
        db.session.commit()
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_FLUSH_ERROR,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=500,
        )
    finally:
        try:
            raw_conn.close()
        except Exception:
            pass
        try:
            metrics_redis.close()
        except Exception:
            pass

    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.OPS_METRICS_FLUSH,
        metadata={"reason": reason, "rows_flushed": rows_flushed},
    )
    db.session.commit()
    return AdminOpsActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.OPS_FLUSH_SUCCESS.format(count=rows_flushed),
        count=rows_flushed,
    ).to_response()


def trigger_gauge_sample(*, actor_id: int, reason: str | None) -> FlaskResponse:
    """Trigger an immediate gauge sample run against all registered gauges.

    Calls run_sample() which commits its own INSERT batch, then stamps the
    GAUGE_LAST_SUCCESS_KEY sentinel on metrics Redis (best-effort, matching
    _record_sample_success in sample_gauges.py). If METRICS_REDIS_URI is
    absent or memory://, returns 503.

    Args:
        actor_id: ID of the admin user triggering the sample.
        reason: Optional free-text reason recorded in the audit log.

    Returns:
        200 JSON envelope with count=gauges sampled on success.
        503 when metrics Redis is not configured.
        500 on unexpected sample error.
    """
    metrics_redis = _build_metrics_redis()
    if metrics_redis is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_GAUGE_UNAVAILABLE,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=503,
        )

    now_epoch = int(time.time())
    raw_conn = db.engine.raw_connection()
    gauge_count: int
    try:
        gauge_count = run_sample(pg_conn=raw_conn, now_epoch=now_epoch)
    except Exception as gauge_error:
        warning_log(f"admin ops: gauge sample failed: {gauge_error}")
        audit.record(
            actor_id=actor_id,
            action=ADMIN_AUDIT_ACTIONS.OPS_GAUGE_SAMPLE,
            metadata={"reason": reason, "error": str(gauge_error)},
        )
        db.session.commit()
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_GAUGE_ERROR,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=500,
        )
    finally:
        try:
            raw_conn.close()
        except Exception:
            pass

    # Stamp the gauge liveness sentinel on metrics Redis, mirroring
    # _record_sample_success in sample_gauges.py. Best-effort: a Redis hiccup
    # here does not fail the response — the Postgres commit has already landed.
    try:
        metrics_redis.set(METRICS_REDIS.GAUGE_LAST_SUCCESS_KEY, str(now_epoch))
    except Exception as sentinel_error:
        warning_log(f"admin ops: failed to stamp gauge sentinel: {sentinel_error}")
    finally:
        try:
            metrics_redis.close()
        except Exception:
            pass

    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.OPS_GAUGE_SAMPLE,
        metadata={"reason": reason, "gauges_sampled": gauge_count},
    )
    db.session.commit()
    return AdminOpsActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.OPS_GAUGE_SUCCESS.format(count=gauge_count),
        count=gauge_count,
    ).to_response()


def trigger_audit_purge(*, actor_id: int, reason: str | None) -> FlaskResponse:
    """Run the audit-log retention purge (window-only, never purge-all).

    Writes the purge's own audit row and commits BEFORE running run_purge(),
    so the purge trigger is always on record even if run_purge fails.
    run_purge() uses a raw psycopg2 connection and commits internally.

    Window is always AUDIT_LOG_RETENTION_DAYS — the request schema carries
    no retention parameter so callers cannot extend or shrink the window.

    Args:
        actor_id: ID of the admin user triggering the purge.
        reason: Optional free-text reason recorded in the audit log.

    Returns:
        200 JSON envelope with count=rows deleted on success.
        500 on unexpected purge error.
    """
    # SELF-AUDIT FIRST: always on record, even if the purge subsequently fails.
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.OPS_AUDIT_PURGE,
        metadata={"reason": reason, "retention_days": AUDIT_LOG_RETENTION_DAYS},
    )
    db.session.commit()

    raw_conn = db.engine.raw_connection()
    deleted_count: int
    try:
        deleted_count = run_purge(
            pg_conn=raw_conn, retention_days=AUDIT_LOG_RETENTION_DAYS
        )
    except Exception as purge_error:
        warning_log(f"admin ops: audit-log purge failed: {purge_error}")
        audit.record(
            actor_id=actor_id,
            action=ADMIN_AUDIT_ACTIONS.OPS_AUDIT_PURGE,
            metadata={"reason": reason, "error": str(purge_error)},
        )
        db.session.commit()
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_PURGE_ERROR,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=500,
        )
    finally:
        try:
            raw_conn.close()
        except Exception:
            pass

    return AdminOpsActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.OPS_PURGE_SUCCESS.format(count=deleted_count),
        count=deleted_count,
    ).to_response()


def trigger_verify_tables(*, actor_id: int, reason: str | None) -> FlaskResponse:
    """Check for missing database tables (read-only).

    Uses get_missing_tables() to compare SQLAlchemy metadata against the live
    schema. Never touches the auto-repair or DROP SCHEMA path in the CLI utils.

    Args:
        actor_id: ID of the admin user requesting the check.
        reason: Optional free-text reason recorded in the audit log.

    Returns:
        200 JSON envelope with count=missing table count on success.
        500 on unexpected error.
    """
    try:
        missing_tables = get_missing_tables()
    except Exception as verify_error:
        warning_log(f"admin ops: table verification failed: {verify_error}")
        audit.record(
            actor_id=actor_id,
            action=ADMIN_AUDIT_ACTIONS.OPS_VERIFY_TABLES,
            metadata={"reason": reason, "error": str(verify_error)},
        )
        db.session.commit()
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_VERIFY_ERROR,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=500,
        )

    if missing_tables:
        message = ADMIN_ACTION_STRINGS.OPS_VERIFY_MISSING.format(
            tables=", ".join(missing_tables)
        )
    else:
        message = ADMIN_ACTION_STRINGS.OPS_VERIFY_OK

    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.OPS_VERIFY_TABLES,
        metadata={"reason": reason, "missing_tables": missing_tables},
    )
    db.session.commit()
    return AdminOpsActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=message,
        count=len(missing_tables),
    ).to_response()


def trigger_backup(*, actor_id: int, reason: str | None) -> FlaskResponse:
    """Request an on-demand run of the backup pipeline (cross-container).

    Sets a short-TTL trigger flag in the metrics Redis; the workflow
    container's per-minute cron poller (scripts/run_backup_if_requested.py)
    consumes it with GETDEL and runs daily-docker.sh. Idempotent: when a
    request is already pending, no new flag is set, no audit row is written
    (nothing was triggered), and a clear already-pending message is returned.

    Args:
        actor_id: ID of the admin user requesting the backup.
        reason: Optional free-text reason recorded in the audit log.

    Returns:
        200 JSON envelope on success or when a request is already pending.
        503 when metrics Redis is not configured.
        500 on unexpected Redis error.
    """
    metrics_redis = _build_metrics_redis()
    if metrics_redis is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_BACKUP_TRIGGER_UNAVAILABLE,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=503,
        )

    try:
        flag_was_set = bool(
            metrics_redis.set(
                METRICS_REDIS.BACKUP_TRIGGER_KEY,
                str(int(time.time())),
                nx=True,
                ex=BACKUP_TRIGGER_TTL_SECONDS,
            )
        )
    except Exception as trigger_error:
        warning_log(f"admin ops: backup trigger failed: {trigger_error}")
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_BACKUP_TRIGGER_ERROR,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=500,
        )
    finally:
        try:
            metrics_redis.close()
        except Exception:
            pass

    if not flag_was_set:
        return AdminOpsActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.OPS_BACKUP_TRIGGER_ALREADY_PENDING,
        ).to_response()

    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.OPS_BACKUP_TRIGGER,
        metadata={"reason": reason},
    )
    db.session.commit()
    return AdminOpsActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.OPS_BACKUP_TRIGGER_SUCCESS,
    ).to_response()


def trigger_short_urls_sync(*, actor_id: int, reason: str | None) -> FlaskResponse:
    """Regenerate the short-URL domain Redis set from the canonical GitHub list.

    Builds a Redis client from config REDIS_URI (main Redis, not metrics Redis)
    and calls sync_short_url_domains_to_redis(). Returns 503 when REDIS_URI is
    absent or memory://; returns 502 when the GitHub fetch or parse fails.

    Args:
        actor_id: ID of the admin user triggering the sync.
        reason: Optional free-text reason recorded in the audit log.

    Returns:
        200 JSON envelope with count=newly added domains on success.
        503 when Redis is not configured.
        502 when the upstream domain-list fetch fails.
        500 on unexpected error.
    """
    redis_uri: str | None = current_app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == _MEMORY_URI:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_SHORT_URLS_SYNC_UNAVAILABLE,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=503,
        )

    redis_client = Redis.from_url(redis_uri)
    added_count: int
    try:
        added_count = sync_short_url_domains_to_redis(redis_client=redis_client)
    except ShortUrlSyncError as sync_error:
        audit.record(
            actor_id=actor_id,
            action=ADMIN_AUDIT_ACTIONS.OPS_SHORT_URLS_SYNC,
            metadata={"reason": reason, "error": str(sync_error)},
        )
        db.session.commit()
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_SHORT_URLS_SYNC_ERROR,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=502,
        )
    except Exception as unexpected_error:
        warning_log(f"admin ops: short URL sync failed: {unexpected_error}")
        audit.record(
            actor_id=actor_id,
            action=ADMIN_AUDIT_ACTIONS.OPS_SHORT_URLS_SYNC,
            metadata={"reason": reason, "error": str(unexpected_error)},
        )
        db.session.commit()
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.OPS_SHORT_URLS_SYNC_ERROR,
            error_code=AdminActionErrorCodes.UNKNOWN_ERROR,
            status_code=500,
        )
    finally:
        try:
            redis_client.close()
        except Exception:
            pass

    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.OPS_SHORT_URLS_SYNC,
        metadata={"reason": reason, "added_count": added_count},
    )
    db.session.commit()
    return AdminOpsActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.OPS_SHORT_URLS_SYNC_SUCCESS.format(
            count=added_count
        ),
        count=added_count,
    ).to_response()
