from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_

from backend.admin.user_service import escape_like_wildcards, LIKE_ESCAPE_CHAR
from backend.models.audit_log import AuditLog
from backend.models.users import Users

DEFAULT_AUDIT_PAGE_LIMIT: int = 50


@dataclass(frozen=True)
class AuditLogFilters:
    """Normalized filter values, kept as strings for URL round-tripping."""

    actor: str = ""
    action: str = ""
    target_type: str = ""
    since: str = ""
    until: str = ""


@dataclass(frozen=True)
class AuditLogPage:
    """One page of audit-log entries, newest first."""

    entries: list[AuditLog]
    total_count: int
    filters: AuditLogFilters
    limit: int
    offset: int

    @property
    def has_previous(self) -> bool:
        return self.offset > 0

    @property
    def has_next(self) -> bool:
        return self.offset + self.limit < self.total_count

    @property
    def previous_offset(self) -> int:
        return max(self.offset - self.limit, 0)

    @property
    def next_offset(self) -> int:
        return self.offset + self.limit


def _parse_filter_date(raw_date: str) -> datetime | None:
    """Parse a ``YYYY-MM-DD`` filter input; None for blank/invalid values.

    Example: ``"2026-07-01"`` → ``datetime(2026, 7, 1)`` (naive; compared
    against tz-aware ``createdAt`` by PostgreSQL using the session
    timezone, UTC in this app).
    """
    stripped_date = raw_date.strip()
    if not stripped_date:
        return None
    try:
        return datetime.strptime(stripped_date, "%Y-%m-%d")
    except ValueError:
        return None


def query_audit_log(
    *,
    filters: AuditLogFilters,
    limit: int = DEFAULT_AUDIT_PAGE_LIMIT,
    offset: int = 0,
) -> AuditLogPage:
    """Filterable, paginated view over ``AuditLogs``, newest first.

    Filter semantics:
    - ``actor``: case-insensitive substring over the actor's username OR
      email (joined through Users).
    - ``action``: case-insensitive substring (e.g. ``"user"`` matches both
      ``admin.user.search`` and ``admin.user.view``).
    - ``target_type``: exact match (closed set of model names).
    - ``since``/``until``: inclusive ``YYYY-MM-DD`` date bounds on
      ``created_at`` — ``until`` covers the whole named day by comparing
      against the following midnight.

    Example: ``query_audit_log(filters=AuditLogFilters(action="search",
    since="2026-07-01", until="2026-07-01"))`` returns every search action
    recorded on July 1st, newest first.
    """
    audit_query = AuditLog.query
    if filters.actor.strip():
        actor_pattern = f"%{escape_like_wildcards(filters.actor.strip())}%"
        audit_query = audit_query.join(Users, AuditLog.actor_id == Users.id).filter(
            or_(
                Users.username.ilike(actor_pattern, escape=LIKE_ESCAPE_CHAR),
                Users.email.ilike(actor_pattern, escape=LIKE_ESCAPE_CHAR),
            )
        )
    if filters.action.strip():
        action_pattern = f"%{escape_like_wildcards(filters.action.strip())}%"
        audit_query = audit_query.filter(
            AuditLog.action.ilike(action_pattern, escape=LIKE_ESCAPE_CHAR)
        )
    if filters.target_type.strip():
        audit_query = audit_query.filter(
            AuditLog.target_type == filters.target_type.strip()
        )
    since_moment = _parse_filter_date(filters.since)
    if since_moment is not None:
        audit_query = audit_query.filter(AuditLog.created_at >= since_moment)
    until_moment = _parse_filter_date(filters.until)
    if until_moment is not None:
        audit_query = audit_query.filter(
            AuditLog.created_at < until_moment + timedelta(days=1)
        )
    total_count = audit_query.count()
    page_entries = (
        audit_query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return AuditLogPage(
        entries=page_entries,
        total_count=total_count,
        filters=filters,
        limit=limit,
        offset=offset,
    )
