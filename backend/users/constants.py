from enum import IntEnum


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
