from __future__ import annotations

from flask import session

from backend.utils.datetime_utils import utc_now
from backend.utils.strings.user_strs import SESSION_ISSUED_AT_KEY


def restamp_current_session() -> None:
    """(Re-)stamp the acting Flask session's issued-at marker to *now*.

    Writes ``SESSION_ISSUED_AT_KEY`` as a UTC epoch float — the exact write the
    ``user_logged_in`` signal handler performs on every login. The
    ``user_loader`` (``backend/users/routes.py:load_user``) rejects a session
    whose issued-at predates ``Users.sessionsInvalidatedAt``; re-stamping lets
    an acting session survive an invalidation bump it triggered itself (the
    change-password flow), while the login signal reuses it as the single
    source of truth for the write.
    """
    session[SESSION_ISSUED_AT_KEY] = utc_now().timestamp()
