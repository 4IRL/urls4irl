from __future__ import annotations

import hmac
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, redirect, request, session
from itsdangerous import BadSignature, URLSafeSerializer

from backend import (
    FAKE_GITHUB_OAUTH_ACCESS_TOKEN_URL,
    FAKE_GITHUB_OAUTH_AUTHORIZE_URL,
    FAKE_GITHUB_OAUTH_USER_EMAILS_URL,
    FAKE_GITHUB_OAUTH_USER_URL,
    FAKE_GOOGLE_OAUTH_ACCESS_TOKEN_URL,
    FAKE_GOOGLE_OAUTH_AUTHORIZE_URL,
    FAKE_GOOGLE_OAUTH_USERINFO_URL,
    csrf,
)

# Registered only when `UI_TESTING` is set (see `should_register_google_oauth`/
# `should_register_github_oauth` branching in `backend/__init__.py`). Mimics
# just enough of Google's OIDC surface and GitHub's plain-OAuth2 + REST
# surface for Authlib's client to complete a real authorization-code exchange
# against a live Selenium-driven server, without ever reaching either
# provider. Both providers share one signed-code round trip: `authorize`
# stashes/signs an identity into `code`, `token` echoes it back as
# `access_token`, and the resource endpoint(s) decode it back out of the
# `Authorization: Bearer` header.
fake_oauth = Blueprint("fake_oauth", __name__)

_SIGNING_SALT = "fake-oauth-provider"
_IDENTITY_SESSION_KEY = "fake_oauth_pending_identity"
_DEFAULT_IDENTITY: dict[str, Any] = {
    "sub": "fake-oauth-default-subject",
    "email": "fake-oauth-default@example.com",
    "name": "Fake OAuth User",
    "login": "fakegithublogin",
    "email_verified": True,
}


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=_SIGNING_SALT)


@fake_oauth.route("/fake-oauth/set-identity", methods=["GET"])
def set_identity() -> tuple[str, int]:
    """Test-only endpoint: stashes the identity the next `/fake-oauth/authorize`
    (or `/fake-oauth/github/authorize`) call should mint a code for.

    Browser-driven (carries the Selenium session cookie), so it must be
    navigated to directly before clicking the app's Google/GitHub button —
    this is the only side channel available, since the `token` and
    `userinfo`/`user`/`user/emails` endpoints are called server-to-server by
    Authlib and never see the browser's session cookie. Returns a trivial 200
    body (rather than 204) so Selenium's `driver.get()` completes a normal
    page load.

    `login` is GitHub-specific (its `GET user` resource's preferred-username
    seed); the Google flow simply never reads it off the stashed identity.
    """
    session[_IDENTITY_SESSION_KEY] = {
        "sub": request.args.get("subject", _DEFAULT_IDENTITY["sub"]),
        "email": request.args.get("email", _DEFAULT_IDENTITY["email"]),
        "name": request.args.get("name", _DEFAULT_IDENTITY["name"]),
        "login": request.args.get("login", _DEFAULT_IDENTITY["login"]),
        "email_verified": request.args.get("email_verified", "true") != "false",
    }
    return "OK", 200


def _authorize_redirect() -> Response | tuple[Response, int]:
    """Shared authorization-endpoint behavior for both fake providers: reads
    the pending identity stashed via `set_identity` from the Selenium
    session, signs it into an opaque `code`, and redirects back to the app's
    callback with that code plus the original `state` — mirroring the real
    authorization-code redirect Authlib expects.
    """
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state")
    if not redirect_uri:
        return (
            jsonify(
                {
                    "error": "invalid_request",
                    "error_description": "Missing redirect_uri",
                }
            ),
            400,
        )

    identity = session.pop(_IDENTITY_SESSION_KEY, None) or _DEFAULT_IDENTITY
    code = _serializer().dumps(identity)
    separator = "&" if "?" in redirect_uri else "?"
    return redirect(f"{redirect_uri}{separator}code={code}&state={state}")


@fake_oauth.route(FAKE_GOOGLE_OAUTH_AUTHORIZE_URL, methods=["GET"])
def authorize() -> Response | tuple[Response, int]:
    """Mimics Google's authorization endpoint. See `_authorize_redirect`."""
    return _authorize_redirect()


@fake_oauth.route(FAKE_GITHUB_OAUTH_AUTHORIZE_URL, methods=["GET"])
def github_authorize() -> Response | tuple[Response, int]:
    """Mimics GitHub's authorization endpoint. See `_authorize_redirect`."""
    return _authorize_redirect()


def _reject_invalid_client_credentials(
    *, expected_client_id: str | None, expected_client_secret: str | None
) -> tuple[Response, int] | None:
    """Shared HTTP Basic auth check for both fake providers' token endpoints.
    Returns the `invalid_client` rejection response, or `None` when the
    supplied `client_id`/`client_secret` pair matches."""
    credentials = request.authorization
    if (
        credentials is None
        or not expected_client_secret
        or credentials.username != expected_client_id
        or not hmac.compare_digest(credentials.password or "", expected_client_secret)
    ):
        return jsonify({"error": "invalid_client"}), 401
    return None


@fake_oauth.route(FAKE_GOOGLE_OAUTH_ACCESS_TOKEN_URL, methods=["POST"])
@csrf.exempt
def token() -> Response | tuple[Response, int]:
    """Mimics Google's token endpoint.

    Called server-to-server by Authlib's own OAuth2 client (no browser
    session available), authenticated via HTTP Basic auth per
    `token_endpoint_auth_method="client_secret_basic"` (Authlib's default when
    a client secret is registered). The identity is round-tripped by simply
    echoing the signed `code` back as the `access_token` — decoded later at
    `/fake-oauth/userinfo` from the `Authorization: Bearer` header.
    """
    credential_rejection = _reject_invalid_client_credentials(
        expected_client_id=current_app.config.get("GOOGLE_OAUTH_CLIENT_ID"),
        expected_client_secret=current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET"),
    )
    if credential_rejection is not None:
        return credential_rejection

    code = request.form.get("code")
    if not code:
        return (
            jsonify({"error": "invalid_grant", "error_description": "Missing code"}),
            400,
        )

    try:
        _serializer().loads(code)
    except BadSignature:
        return jsonify({"error": "invalid_grant"}), 400

    return jsonify(
        {
            "access_token": code,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "email profile",
        }
    )


@fake_oauth.route(FAKE_GITHUB_OAUTH_ACCESS_TOKEN_URL, methods=["POST"])
@csrf.exempt
def github_token() -> Response | tuple[Response, int]:
    """Mimics GitHub's token endpoint.

    Same round-trip as the Google `token` endpoint above (echo the signed
    `code` back as `access_token`), but validates
    `GITHUB_OAUTH_CLIENT_ID`/`GITHUB_OAUTH_CLIENT_SECRET` and returns GitHub's
    scope/token-type shape rather than Google's.
    """
    credential_rejection = _reject_invalid_client_credentials(
        expected_client_id=current_app.config.get("GITHUB_OAUTH_CLIENT_ID"),
        expected_client_secret=current_app.config.get("GITHUB_OAUTH_CLIENT_SECRET"),
    )
    if credential_rejection is not None:
        return credential_rejection

    code = request.form.get("code")
    if not code:
        return (
            jsonify({"error": "invalid_grant", "error_description": "Missing code"}),
            400,
        )

    try:
        _serializer().loads(code)
    except BadSignature:
        return jsonify({"error": "invalid_grant"}), 400

    return jsonify(
        {
            "access_token": code,
            "token_type": "bearer",
            "scope": "read:user,user:email",
        }
    )


def _decode_bearer_identity() -> dict[str, Any] | tuple[Response, int]:
    """Shared Bearer-token decode logic for Google's `userinfo` endpoint and
    GitHub's `user`/`user/emails` resource endpoints. Called server-to-server,
    authenticated via the `Authorization: Bearer <access_token>` header
    Authlib attaches automatically. Decodes the signed identity back out of
    the token, or returns the `invalid_token` rejection response.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "invalid_token"}), 401

    access_token = auth_header[len("Bearer ") :]
    try:
        identity: dict[str, Any] = _serializer().loads(access_token)
    except BadSignature:
        return jsonify({"error": "invalid_token"}), 401

    return identity


@fake_oauth.route(FAKE_GOOGLE_OAUTH_USERINFO_URL, methods=["GET"])
def userinfo() -> Response | tuple[Response, int]:
    """Mimics Google's userinfo endpoint.

    Called server-to-server by Authlib's plain-OAuth2 fallback
    (`oauth.google.userinfo(token=token)`). See `_decode_bearer_identity`.
    """
    identity = _decode_bearer_identity()
    if not isinstance(identity, dict):
        return identity
    return jsonify(identity)


@fake_oauth.route(FAKE_GITHUB_OAUTH_USER_URL, methods=["GET"])
def github_user() -> Response | tuple[Response, int]:
    """Mimics GitHub's `GET /user` resource.

    Called server-to-server via `oauth.github.get("user", token=token)`
    (relative to the registered `api_base_url`). See
    `_decode_bearer_identity`. Returns GitHub's `/user` shape — `id` is the
    stable subject, `login` the preferred-username seed; `email` is always
    `None` here since GitHub's `/user` resource only reports it when a user
    has made their primary email public, and `handle_github_callback` always
    resolves the trusted email from `GET user/emails` instead.
    """
    identity = _decode_bearer_identity()
    if not isinstance(identity, dict):
        return identity
    return jsonify(
        {
            "id": identity["sub"],
            "login": identity["login"],
            "name": identity["name"],
            "email": None,
        }
    )


@fake_oauth.route(FAKE_GITHUB_OAUTH_USER_EMAILS_URL, methods=["GET"])
def github_user_emails() -> Response | tuple[Response, int]:
    """Mimics GitHub's `GET /user/emails` resource.

    Called server-to-server via `oauth.github.get("user/emails", token=token)`.
    See `_decode_bearer_identity`. Returns a single-entry list matching
    GitHub's `{"email", "primary", "verified", "visibility"}` shape, always
    marked `primary` — the fake provider only ever stashes one email per
    identity — with `verified` taken from the stashed `email_verified` flag
    so UI tests can exercise the unverified-email reject branch.
    """
    identity = _decode_bearer_identity()
    if not isinstance(identity, dict):
        return identity
    return jsonify(
        [
            {
                "email": identity["email"],
                "primary": True,
                "verified": identity["email_verified"],
                "visibility": "private",
            }
        ]
    )
