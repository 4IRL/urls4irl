"""Shared helpers for the bearer-token /api/v1 integration tests."""

from __future__ import annotations

from typing import Any

from flask import Flask, g, has_app_context, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend.api_v1.services.tokens import create_access_token
from backend.models.users import Users
from backend.utils.strings.api_auth_strs import API_AUTH
from tests.integration.invite_links.invite_route_helpers import InviteRoute


def bearer(token: str) -> dict[str, str]:
    """An Authorization header dict for an access token string."""
    return {API_AUTH.AUTHORIZATION_HEADER: f"{API_AUTH.BEARER_PREFIX}{token}"}


def token_for_user(app: Flask, user_id: int) -> str:
    """Mint a fresh access token for ``user_id``."""
    with app.app_context():
        user: Users = Users.query.get(user_id)
        return create_access_token(user=user)


def clear_request_identity() -> None:
    """Drop the identity flask-login and the bearer loader cached on ``g``.

    The test app keeps one app context open for the whole test, so ``g`` outlives
    each request: after a web request the cached session user would answer a later
    bearer request (and vice versa). Call this between requests of different kinds.
    """
    if has_app_context():
        g.pop("_login_user", None)
        g.pop(API_AUTH.BEARER_AUTHENTICATED_G_KEY, None)
        # flask-wtf caches the CSRF token on ``g``; a new web session needs its own.
        g.pop("csrf_token", None)


def bearer_request_as(
    app: Flask,
    user_id: int,
    method: str,
    url: InviteRoute,
    body: Any = None,
    extra_headers: dict[str, str] | None = None,
) -> Response:
    """Send one bearer-token JSON request as ``user_id``.

    Mirrors ``request_as`` in ``invite_route_helpers.py`` for the /api/v1 surface:
    no session cookie, no CSRF token, no X-Requested-With header.
    """
    headers = {**bearer(token_for_user(app, user_id)), **(extra_headers or {})}
    clear_request_identity()
    app.test_client_class = FlaskClient
    client = app.test_client()
    with app.test_request_context():
        resolved_url = url_for(url.route, utub_id=url.utub_id)
    return client.open(resolved_url, method=method, json=body, headers=headers)
