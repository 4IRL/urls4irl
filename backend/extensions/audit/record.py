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
    """Insert one ``AuditLogs`` row and commit — never raises.

    Commits the current session itself because the read-only admin views
    that call it never issue their own commit. Callers must therefore not
    hold unrelated uncommitted writes when recording (admin read paths do
    not). On any failure the session is rolled back and the error is logged
    at warning level; audit failures must never break the calling flow.
    """
    try:
        audit_entry = AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            log_metadata=metadata,
        )
        db.session.add(audit_entry)
        db.session.commit()
    except Exception as audit_error:
        try:
            db.session.rollback()
        except Exception as rollback_error:
            warning_log(f"audit.record rollback failed: {rollback_error}")
        warning_log(f"audit.record failed for action={action}: {audit_error}")
