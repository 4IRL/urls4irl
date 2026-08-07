from enum import IntEnum

# Per-IP rate limit for the authenticated data-export endpoint
# (``GET /users/<id>/data-export``). Export is the app's most expensive read —
# it traverses every UTub the user belongs to → URLs → tags → members and
# serializes the whole graph to JSON — so it carries its own dedicated limit
# rather than inheriting only the global default (20/second, 100/minute). Uses
# the multi-window comma-separated ``N per unit`` syntax (mirroring the
# contact-form limit) so a short burst and a sustained hourly abuse are both
# capped. The first bare module-level constant in this file.
DATA_EXPORT_RATE_LIMIT = "5 per minute, 15 per hour"


class ChangeUsernameErrorCodes(IntEnum):
    """Application error codes for the authenticated change-username endpoint.

    Mirrors the splash-blueprint ``*ErrorCodes`` convention (every member given
    an explicit sequential value — no ``auto()``/bare members), but lives in the
    users domain rather than ``backend/splash/constants.py`` so users-blueprint
    error codes are not coupled to the splash module.
    """

    INVALID_FORM_INPUT = 1
    USERNAME_TAKEN = 2
    RATE_LIMITED = 3


class ChangePasswordErrorCodes(IntEnum):
    """Application error codes for the authenticated change-password endpoint.

    Same home as ``ChangeUsernameErrorCodes`` (the users domain, not
    ``backend/splash/constants.py``) and the same explicit-sequential-value
    convention. ``OAUTH_ONLY_NO_PASSWORD`` is defense-in-depth for a
    password-less account reaching the endpoint (the template already hides the
    form for such accounts).
    """

    INVALID_FORM_INPUT = 1
    INVALID_PASSWORD = 2
    OAUTH_ONLY_NO_PASSWORD = 3
    TOO_MANY_ATTEMPTS = 4


class DeleteAccountErrorCodes(IntEnum):
    """Application error codes for the authenticated delete-account endpoint
    (``DELETE /users/<id>``).

    Same home as the sibling ``Change*ErrorCodes`` (the users domain, not
    ``backend/splash/constants.py``) and the same explicit-sequential-value
    convention (member 1 is always ``INVALID_FORM_INPUT``).

    ``CONFIRMATION_MISMATCH`` (DD-C) backs the typed-username confirmation
    re-check. The OAuth-only removal path returns a 200 OAuth-proof redirect
    (DD-6), not an error, so it has no error-code member here.
    """

    INVALID_FORM_INPUT = 1
    INVALID_PASSWORD = 2
    TOO_MANY_ATTEMPTS = 3
    SOLE_ADMIN_FORBIDDEN = 4
    CONFIRMATION_MISMATCH = 5


class ChangeEmailErrorCodes(IntEnum):
    """Application error codes for the authenticated change-email START endpoint
    (``PUT /users/<id>/email``).

    Same home as ``ChangeUsernameErrorCodes``/``ChangePasswordErrorCodes`` (the
    users domain, not ``backend/splash/constants.py``) and the same
    explicit-sequential-value convention. ``INVALID_FORM_INPUT`` also carries the
    DD-8 confirm-email mismatch (surfaced by the schema validator as a
    ``confirmEmail`` field error), mirroring how ``RegisterRequest`` rides its
    own route's ``INVALID_FORM_INPUT`` for the same mismatch.
    """

    INVALID_FORM_INPUT = 1
    EMAIL_TAKEN = 2
    INVALID_PASSWORD = 3
    OAUTH_ONLY_NO_PASSWORD = 4
    TOO_MANY_ATTEMPTS = 5
    RATE_LIMITED = 6
    EMAIL_SEND_FAILURE = 7


class LogoutEverywhereErrorCodes(IntEnum):
    """Application error code for the authenticated "log out everywhere" endpoint
    (``POST /users/<id>/logout-everywhere``).

    Same home as the sibling ``Change*ErrorCodes``/``DeleteAccountErrorCodes``
    (the users domain, not ``backend/splash/constants.py``) and the same
    explicit-sequential-value convention (member 1 is the sole failure mode).
    The endpoint is non-destructive and takes no request body, so its only
    failure mode is the self-ownership guard.
    """

    NOT_AUTHORIZED = 1


class PreferencesErrorCodes(IntEnum):
    """Application error code for the authenticated update-preferences endpoint
    (``PUT /users/<id>/preferences``).

    Same home as the sibling ``Change*ErrorCodes``/``DeleteAccountErrorCodes``/
    ``LogoutEverywhereErrorCodes`` (the users domain, not
    ``backend/splash/constants.py``) and the same explicit-sequential-value
    convention (member 1 is always ``INVALID_FORM_INPUT``). One shared code
    backs every failure mode: Pydantic enum-membership validation rejects an
    out-of-set value as a 400 field error before the service runs, and the
    self-ownership guard reuses the same code for its 403 (mirroring
    ``change_username``'s single-code convention).
    """

    INVALID_FORM_INPUT = 1


class DataExportErrorCodes(IntEnum):
    """Application error code for the authenticated data-export endpoint
    (``GET /users/<id>/data-export``).

    Same home as the sibling ``Change*ErrorCodes``/``DeleteAccountErrorCodes``/
    ``LogoutEverywhereErrorCodes`` (the users domain, not
    ``backend/splash/constants.py``) and the same explicit-sequential-value
    convention (member 1 is the sole failure mode). The endpoint is a
    non-mutating read that takes no request body, so its only application-level
    failure mode is the self-ownership guard.
    """

    NOT_AUTHORIZED = 1
