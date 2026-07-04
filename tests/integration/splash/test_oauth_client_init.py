"""Integration test for the module-level Authlib OAuth client registration.

Confirms the `oauth` singleton is an Authlib `OAuth` instance and that
`create_app` wires it into the Flask app via `oauth.init_app(app)` (verified by
the exact extensions key Authlib registers). Also confirms the Google client
itself is registered (`oauth.google`) when credentials are configured, and
that `should_register_google_oauth`'s guard condition is correct in isolation.

Note: `oauth.register(...)` is called against Authlib's process-wide `OAuth()`
registry, which persists across `create_app()` calls within the same test
process. `test_google_oauth_client_registered_with_configured_credentials`
therefore asserts against the shared session-scoped `app` fixture (which the
`build_app` fixture in `tests/conftest.py` always creates with dummy Google
credentials) rather than constructing a second, credential-less `create_app()`
to prove a negative — a second call cannot reliably prove `oauth.google` is
absent, since a prior registration in the same interpreter persists.
"""

from authlib.integrations.flask_client import OAuth
from flask import Flask, current_app
import pytest

from backend import oauth, should_register_google_oauth
from tests.conftest import TEST_GOOGLE_OAUTH_CLIENT_ID

pytestmark = pytest.mark.splash

AUTHLIB_EXTENSION_KEY = "authlib.integrations.flask_client"


def test_oauth_singleton_is_authlib_oauth_instance(app: Flask):
    """
    GIVEN the application module-level OAuth singleton (the `app` fixture
        ensures `create_app` has run)
    WHEN inspecting the singleton's type
    THEN `oauth` is an Authlib `OAuth` instance
    """
    assert isinstance(oauth, OAuth)


def test_oauth_client_registered_in_app_extensions(app: Flask):
    """
    GIVEN a created app that calls `oauth.init_app(app)` in `create_app`
    WHEN inspecting the app's registered extensions
    THEN Authlib's exact extensions key is present
    """
    with app.app_context():
        assert AUTHLIB_EXTENSION_KEY in current_app.extensions


def test_google_oauth_client_registered_with_configured_credentials(app: Flask):
    """
    GIVEN the shared test app, built with dummy Google OAuth credentials via
        `tests/conftest.py`'s `build_app` fixture
    WHEN `create_app` runs its guarded `oauth.register(name="google", ...)` call
    THEN `oauth.google` is registered and its `client_id` matches the
        configured value
    """
    with app.app_context():
        assert oauth.google is not None
        assert oauth.google.client_id == TEST_GOOGLE_OAUTH_CLIENT_ID


@pytest.mark.parametrize(
    "client_id, client_secret, expected",
    [
        ("client-id", "client-secret", True),
        ("client-id", None, False),
        (None, "client-secret", False),
        (None, None, False),
    ],
)
def test_should_register_google_oauth(
    client_id: str | None, client_secret: str | None, expected: bool
):
    """
    GIVEN four combinations of Google OAuth client_id/client_secret presence
    WHEN calling `should_register_google_oauth` directly (no `create_app()`,
        no Flask app, no Authlib registry involved)
    THEN it returns `True` only when both values are present
    """
    assert should_register_google_oauth(client_id, client_secret) is expected
