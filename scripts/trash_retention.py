"""Single source of truth for how long Trash rows are kept before a permanent purge.

A Flask-less leaf module: it imports nothing, so both the backend (the Trash API's
``expiresAt`` countdown) and the planned Trash sweep (``scripts/purge_trash.py``)
can import it. Sharing one constant means the countdown the user sees and the day the
sweep actually deletes can never disagree.

Follows the ``scripts/purge_audit_log.py`` ``AUDIT_LOG_RETENTION_DAYS`` precedent.
"""

TRASH_RETENTION_DAYS: int = 30
