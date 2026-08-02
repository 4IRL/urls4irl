"""Reactivate-on-login for self-deactivated accounts.

A self-service account deactivation sets ``is_suspended=True`` and stamps
``Users.self_deactivated_at`` (a reversible pause). On a subsequent successful
credential/subject check, the login path calls
``maybe_reactivate_self_deactivated`` to auto-lift the deactivation before the
session/token is granted.

Lives in ``backend/utils`` (a neutral home importable by
``backend.splash.services.*``, ``backend.api_v1.services.*``, and
``backend.splash.services.oauth.*`` with no import cycle) because the six
login entry points that call it span all three packages — mirroring
``backend/utils/reauth_throttle.py``'s placement rationale.
"""

from __future__ import annotations

from backend import db
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.users import Users


def maybe_reactivate_self_deactivated(user: Users) -> bool:
    """Lift a reversible self-deactivation for ``user`` if one is in effect.

    A self-deactivated account is exactly ``is_suspended=True`` **and**
    ``self_deactivated_at is not None``. When that holds, clear both flags,
    commit, record an ``ACCOUNT_REACTIVATED`` metrics event, and return
    ``True`` — the caller then proceeds to grant the session/token.

    Returns ``False`` for every other state, covering both "not suspended"
    (nothing to do) and "admin-locked" (``is_suspended=True`` but
    ``self_deactivated_at IS NULL`` — the caller keeps its own hard-403 branch
    for that case). Must be called strictly after the entry point's own
    successful verification (password check, ID-token/claims check, or
    provider-subject match), never on a failed attempt.
    """
    if user.is_suspended and user.self_deactivated_at is not None:
        user.is_suspended = False
        user.self_deactivated_at = None
        db.session.commit()
        record_event(EventName.ACCOUNT_REACTIVATED)
        return True
    return False
