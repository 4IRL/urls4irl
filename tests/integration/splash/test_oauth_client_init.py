"""Integration test for the module-level Authlib OAuth client registration.

Confirms the `oauth` singleton is an Authlib `OAuth` instance and that
`create_app` wires it into the Flask app via `oauth.init_app(app)` (verified by
the exact extensions key Authlib registers). No provider is registered in this
phase — Google lands in Phase 2, GitHub in Phase 3.
"""

from authlib.integrations.flask_client import OAuth
from flask import Flask, current_app
import pytest

from backend import oauth

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
