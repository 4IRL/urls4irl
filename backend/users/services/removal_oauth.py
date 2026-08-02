"""Neutral home for shared self-service account-removal state mutations.

This module hosts the guard-free, HTTP-free core mutations that every
account-removal entry point shares — the password-path endpoints
(``backend.users.services.account_service``) and the OAuth-proof callback
(``backend.splash.services.oauth.linking_service``).

It lives here — importing nothing from ``account_service`` or
``linking_service`` — to keep the import graph acyclic: those two modules would
otherwise have to import from each other. Both may import one-way from this
module; this module never imports back (mirrors ``backend/utils/reactivation.py``'s
placement rationale from the storage-foundation step).
"""

from __future__ import annotations

from backend.api_v1.services.tokens import mark_all_refresh_tokens_revoked_for_user
from backend.models.users import Users
from backend.utils.datetime_utils import utc_now


def perform_self_deactivation(*, user: Users) -> None:
    """Apply the reversible self-deactivation state mutation for ``user``.

    Sets the reversible-pause flags (``is_suspended`` + a fresh
    ``self_deactivated_at`` stamp so reactivate-on-login can distinguish a
    voluntary pause from an admin lock), then kills every existing credential:
    the acting web session via the ``sessions_invalidated_at`` stamp and all
    API refresh tokens via bulk revoke.

    Unlike the change-password/email flows, this deliberately does **not**
    call ``restamp_current_session()`` — the acting session must die too. It
    carries no HTTP/guard/re-auth/logout concerns and does **not** commit; the
    caller owns re-auth, logout, the commit, and the response.
    """
    user.is_suspended = True
    user.self_deactivated_at = utc_now()
    user.sessions_invalidated_at = utc_now()
    mark_all_refresh_tokens_revoked_for_user(user_id=user.id)
