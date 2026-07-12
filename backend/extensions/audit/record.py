from __future__ import annotations

from backend import db
from backend.app_logger import warning_log
from backend.models.audit_log import AuditLog


def record(
    *,
    actor_id: int,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Insert one ``AuditLogs`` row and flush — never commits, never raises.

    The caller owns the final ``db.session.commit()``, so a mutation and its
    audit row land in the same transaction atomically. The insert runs inside
    a nested savepoint: if the audit write fails, only the savepoint rolls
    back — the caller's pending writes survive untouched — and the error is
    logged at warning level. Audit failures must never break the calling flow,
    and an audit failure must never commit or roll back a caller's half-done
    mutation.
    """
    try:
        with db.session.begin_nested():
            audit_entry = AuditLog(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                log_metadata=metadata,
            )
            db.session.add(audit_entry)
            db.session.flush()
    except Exception as audit_error:
        warning_log(f"audit.record failed for action={action}: {audit_error}")
