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

from dataclasses import asdict
from typing import Any

from flask import session
from flask_login import current_user

from backend.admin.account_data_service import erase_user_core
from backend.api_v1.services.tokens import mark_all_refresh_tokens_revoked_for_user
from backend.extensions import audit
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.splash.services.oauth.constants import (
    OAUTH_LINK_INTENT_SESSION_KEY,
    Provider,
    REMOVAL_INTENT_ACTION_DEACTIVATE,
    REMOVAL_INTENT_ACTION_DELETE,
)
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.user_strs import ACCOUNT_AUDIT_ACTIONS


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


def _stash_removal_intent(
    *, action: str, user_id: int, proof_provider: Provider
) -> None:
    """Stash a pending OAuth-proof account-removal intent in the session.

    Mirrors ``linking_service._stash_link_intent`` but writes the removal
    dict shape (DD-6): a removal has no link target, so there is **no**
    ``target_provider`` field — only the ``proof_provider`` the callback must
    match. Reuses the shared ``OAUTH_LINK_INTENT_SESSION_KEY`` (only one OAuth
    flow can be in flight per session); the generic
    ``pop_valid_link_intent_for_current_user`` /
    ``peek_valid_link_intent_for_current_user`` readers already satisfy this
    shape (they key off ``issued_at``/``user_id`` only).

    Lives here rather than in ``linking_service`` so ``account_service`` can
    import it one-way, keeping the import graph acyclic (DD-20).
    """
    session[OAUTH_LINK_INTENT_SESSION_KEY] = {
        "action": action,
        "user_id": user_id,
        "proof_provider": proof_provider.value,
        "issued_at": utc_now().timestamp(),
    }


def execute_removal_intent(
    *, intent: dict[str, Any], provider: Provider, subject: str
) -> bool:
    """Execute a stashed removal intent once its OAuth-proof round-trip returns.

    Thin dispatcher for the authenticated OAuth callback (DD-20): it first
    re-verifies the returned ``subject`` matches a ``UserOAuthIdentity`` already
    on ``current_user`` (the same proof check the link PROOF branch performs,
    reimplemented here so this neutral module need not import
    ``linking_service``). On mismatch it performs **no** mutation and returns
    ``False``. Otherwise it dispatches on ``intent["action"]`` — a reversible
    self-deactivation or an irreversible GDPR erasure (recording the same
    self-actor audit trail the password-path delete records, DD-4) — and returns
    ``True``.

    Like ``perform_self_deactivation``/``erase_user_core`` it does **not**
    commit: the OAuth-callback caller owns the commit, logout, and redirect
    (Flask-response/session concerns stay in ``linking_service``).
    """
    proof_identity: UserOAuthIdentity | None = UserOAuthIdentity.query.filter_by(
        user_id=current_user.id,
        provider=provider.value,
        provider_subject=subject,
    ).first()
    if proof_identity is None:
        return False

    intent_action = intent.get("action")
    if intent_action == REMOVAL_INTENT_ACTION_DEACTIVATE:
        perform_self_deactivation(user=current_user)
        record_event(EventName.ACCOUNT_DEACTIVATED)
        return True

    if intent_action == REMOVAL_INTENT_ACTION_DELETE:
        # Capture the PK as an int before the erase so the post-erase audit
        # never dereferences a detached/expired ORM instance (ObjectDeletedError).
        erased_user_id: int = current_user.id
        counts = erase_user_core(target_user=current_user)
        audit.record(
            actor_id=erased_user_id,
            action=ACCOUNT_AUDIT_ACTIONS.SELF_ACCOUNT_ERASE,
            target_type="User",
            target_id=str(erased_user_id),
            metadata=asdict(counts),
        )
        record_event(EventName.ACCOUNT_DELETED)
        return True

    return False
