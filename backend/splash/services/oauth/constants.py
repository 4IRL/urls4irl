from __future__ import annotations

from enum import StrEnum

# Session key both provider services use to round-trip the `next` query param
# from the login-initiation request to the provider's callback redirect. Only
# one OAuth flow can be in flight per session, so a single shared key is
# correct (and means a user switching providers mid-flow can't leak a stale
# target).
OAUTH_NEXT_SESSION_KEY = "oauth_next_target"

# Settings-initiated account linking: an authenticated user's pending link
# intent, stashed by `POST /users/<id>/oauth/link/<provider>` after
# proof-of-ownership (password re-auth for password accounts; an OAuth
# round-trip to an already-linked provider for password-less accounts) and
# consumed by the shared `/oauth/<provider>/callback`. Shape:
# {"action": "link"|"proof", "target_provider": str, "proof_provider": str?,
#  "user_id": int, "issued_at": float}
OAUTH_LINK_INTENT_SESSION_KEY = "oauth_link_intent"
LINK_INTENT_ACTION_LINK = "link"
LINK_INTENT_ACTION_PROOF = "proof"

# Collision confirm-link: the pending provider identity stashed when an OAuth
# sign-in resolves to an email already owned by an unlinked local account.
# Consumed by the `/oauth/link/confirm` page/submit (password accounts) or
# completed automatically after a successful OAuth sign-in with an
# already-linked provider (password-less accounts). Shape:
# {"provider": str, "subject": str, "email": str, "issued_at": float}
OAUTH_PENDING_LINK_SESSION_KEY = "oauth_pending_link"

# Both stashes above are proof-of-ownership tokens — keep them short-lived.
OAUTH_LINK_MAX_AGE_SECONDS = 600


class Provider(StrEnum):
    """The set of supported OAuth providers.

    Single source of truth for the ``provider`` value stored on
    ``UserOAuthIdentities.provider``. The column stays a plain string at the DB
    layer (readable, no native-enum migration tax when a provider is added); the
    OAuth account service validates every write against this enum, so an
    unsupported provider never reaches the database.

    Member values are the lowercase provider keys used in callback URLs
    (``/oauth/<provider>/callback``) and in the ``.env.example`` credential keys.
    """

    GOOGLE = "google"
    GITHUB = "github"
