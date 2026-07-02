from __future__ import annotations

from enum import StrEnum


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
