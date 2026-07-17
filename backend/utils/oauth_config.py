def should_register_google_oauth(
    client_id: str | None, client_secret: str | None
) -> bool:
    """Whether both Google OAuth credentials are present, so `oauth.register(...)`
    can be safely called without Authlib raising on a `None` client_id/secret.

    Kept dependency-free (no `backend` imports) so it can be imported both by
    `backend/__init__.py` (to decide whether to register `oauth.google`) and by
    `backend/utils/constants.py` (to gate the Google OAuth button in templates)
    without introducing a circular import between the two.
    """
    return bool(client_id) and bool(client_secret)


def should_register_github_oauth(
    client_id: str | None, client_secret: str | None
) -> bool:
    """Whether both GitHub OAuth credentials are present, so `oauth.register(...)`
    can be safely called without Authlib raising on a `None` client_id/secret.

    Same contract and dependency-free constraint as
    `should_register_google_oauth` above; kept as a distinct function so each
    provider's gating reads unambiguously at its call sites.
    """
    return bool(client_id) and bool(client_secret)
