from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, redirect, request, session
from itsdangerous import BadSignature, URLSafeSerializer

from backend import csrf

# Registered only when `UI_TESTING` is set (see `should_register_google_oauth`
# branching in `backend/__init__.py`). Mimics just enough of Google's OIDC
# surface for Authlib's client to complete a real authorization-code exchange
# against a live Selenium-driven server, without ever reaching Google.
fake_oauth = Blueprint("fake_oauth", __name__)

_SIGNING_SALT = "fake-oauth-provider"
_IDENTITY_SESSION_KEY = "fake_oauth_pending_identity"
_DEFAULT_IDENTITY: dict[str, Any] = {
    "sub": "fake-oauth-default-subject",
    "email": "fake-oauth-default@example.com",
    "name": "Fake OAuth User",
    "email_verified": True,
}


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt=_SIGNING_SALT)


@fake_oauth.route("/fake-oauth/set-identity", methods=["GET"])
def set_identity() -> tuple[str, int]:
    """Test-only endpoint: stashes the identity the next `/fake-oauth/authorize`
    call should mint a code for.

    Browser-driven (carries the Selenium session cookie), so it must be
    navigated to directly before clicking the app's Google button — this is
    the only side channel available, since `/fake-oauth/token` and
    `/fake-oauth/userinfo` are called server-to-server by Authlib and never
    see the browser's session cookie. Returns a trivial 200 body (rather than
    204) so Selenium's `driver.get()` completes a normal page load.
    """
    session[_IDENTITY_SESSION_KEY] = {
        "sub": request.args.get("subject", _DEFAULT_IDENTITY["sub"]),
        "email": request.args.get("email", _DEFAULT_IDENTITY["email"]),
        "name": request.args.get("name", _DEFAULT_IDENTITY["name"]),
        "email_verified": request.args.get("email_verified", "true") != "false",
    }
    return "OK", 200


@fake_oauth.route("/fake-oauth/authorize", methods=["GET"])
def authorize():
    """Mimics Google's authorization endpoint.

    Browser-driven: reads the pending identity stashed via `set_identity` from
    the Selenium session, signs it into an opaque `code`, and redirects back
    to the app's callback with that code plus the original `state` —
    mirroring the real authorization-code redirect Authlib expects.
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


@fake_oauth.route("/fake-oauth/token", methods=["POST"])
@csrf.exempt
def token():
    """Mimics Google's token endpoint.

    Called server-to-server by Authlib's own OAuth2 client (no browser
    session available), authenticated via HTTP Basic auth per
    `token_endpoint_auth_method="client_secret_basic"` (Authlib's default when
    a client secret is registered). The identity is round-tripped by simply
    echoing the signed `code` back as the `access_token` — decoded later at
    `/fake-oauth/userinfo` from the `Authorization: Bearer` header.
    """
    credentials = request.authorization
    expected_client_id = current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
    expected_client_secret = current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if (
        credentials is None
        or credentials.username != expected_client_id
        or credentials.password != expected_client_secret
    ):
        return jsonify({"error": "invalid_client"}), 401

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


@fake_oauth.route("/fake-oauth/userinfo", methods=["GET"])
def userinfo():
    """Mimics Google's userinfo endpoint.

    Called server-to-server by Authlib's plain-OAuth2 fallback
    (`oauth.google.userinfo(token=token)`), authenticated via the
    `Authorization: Bearer <access_token>` header Authlib attaches
    automatically. Decodes the signed identity back out of the token.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "invalid_token"}), 401

    access_token = auth_header[len("Bearer ") :]
    try:
        identity: dict[str, Any] = _serializer().loads(access_token)
    except BadSignature:
        return jsonify({"error": "invalid_token"}), 401

    return jsonify(identity)
