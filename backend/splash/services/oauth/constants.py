from __future__ import annotations

from enum import StrEnum

# Session key both provider services use to round-trip the `next` query param
# from the login-initiation request to the provider's callback redirect. Only
# one OAuth flow can be in flight per session, so a single shared key is
# correct (and means a user switching providers mid-flow can't leak a stale
# target).
OAUTH_NEXT_SESSION_KEY = "oauth_next_target"


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
