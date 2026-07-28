from __future__ import annotations

from typing import Any

from flask_login import current_user


def build_account_info_context() -> dict[str, Any]:
    """Build the Settings page Account-info block template context for the
    authenticated user.

    Mirrors ``build_user_stats_context()`` — no parameters, reads
    ``current_user``, returns a flat dict of read-only account details. Keys are
    namespaced ``account_*`` so they never collide with the connected-accounts
    or stats context keys. Member-since is intentionally omitted here: the
    ``settings()`` route already splats ``build_user_stats_context()``, whose
    ``stats_member_since_iso`` / ``stats_member_since_exact`` values the
    account-info block reuses (no duplicate date formatting).
    """
    return {
        "account_username": current_user.username,
        "account_email": current_user.email,
        "account_email_validated": current_user.email_validated,
        "account_has_password": current_user.password is not None,
    }
