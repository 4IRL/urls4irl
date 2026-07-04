from __future__ import annotations

from typing import Any

from authlib.integrations.base_client.errors import OAuthError
from flask import redirect, render_template, url_for
from flask_login import login_user
from pydantic import BaseModel
from werkzeug import Response as WerkzeugResponse

from backend import oauth
from backend.api_common.input_sanitization import sanitize_user_input
from backend.api_common.parse_request import parse_query_args
from backend.api_common.responses import FlaskResponse
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.schemas.requests.splash import GoogleOAuthCallbackQuerySchema
from backend.splash.constants import OAuthErrorCodes
from backend.splash.services.oauth.account_service import (
    EmailAlreadyRegisteredError,
    find_or_create_oauth_user,
)
from backend.splash.services.oauth.constants import Provider
from backend.splash.services.user_login import (
    _LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION,
)
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES

_GENERIC_FAILURE_MESSAGE = "Sign-in failed, please try again."
_UNVERIFIED_EMAIL_MESSAGE = (
    "Google has not verified this email address — please verify it with "
    "Google and try again."
)
_EMAIL_COLLISION_MESSAGE = (
    "Email already registered — log in with your password instead."
)
_CONSENT_DECLINED_MESSAGE = "Sign-in was cancelled."
_INVALID_CALLBACK_QUERY_MESSAGE = "Invalid Google OAuth callback request."


def initiate_google_login() -> WerkzeugResponse:
    """Kicks off the Google OAuth consent redirect."""
    redirect_uri = url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


def handle_google_callback() -> WerkzeugResponse | str | FlaskResponse:
    """Handles Google's OAuth redirect back to the app.

    Resolves the token exchange, extracts and validates the OIDC claims, and
    either logs the user in (creating an account on first sign-in) or renders
    a reject page for every failure branch (declined consent, token-exchange
    failure, unverified email, missing claims, email collision).
    """
    parsed = parse_query_args(
        GoogleOAuthCallbackQuerySchema,
        message=_INVALID_CALLBACK_QUERY_MESSAGE,
        error_code=OAuthErrorCodes.INVALID_FORM_INPUT,
    )
    if not isinstance(parsed, BaseModel):
        return parsed

    if parsed.error is not None:
        return render_template(
            "pages/splash.html",
            oauth_consent_declined=True,
            oauth_reject_message=_CONSENT_DECLINED_MESSAGE,
        )

    try:
        token = oauth.google.authorize_access_token()
    except OAuthError:
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=_GENERIC_FAILURE_MESSAGE,
        )

    userinfo: dict[str, Any] | None = token.get("userinfo")
    if userinfo is None:
        # No `openid` scope (the fake-provider branch registered with plain
        # OAuth2 scopes) means Authlib never parsed an id_token, so fall back
        # to a plain-OAuth2 GET against the configured userinfo endpoint.
        userinfo = oauth.google.userinfo(token=token)

    if userinfo.get("email_verified") is False:
        return render_template(
            "pages/splash.html",
            oauth_unverified_email=True,
            oauth_reject_message=_UNVERIFIED_EMAIL_MESSAGE,
        )

    subject: str | None = userinfo.get("sub")
    email: str | None = userinfo.get("email")
    if subject is None or email is None:
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=_GENERIC_FAILURE_MESSAGE,
        )

    preferred_username = _resolve_preferred_username(
        userinfo.get("name") or userinfo.get("given_name"), email
    )

    try:
        resolved_user = find_or_create_oauth_user(
            provider=Provider.GOOGLE,
            subject=subject,
            email=email,
            preferred_username=preferred_username,
        )
    except EmailAlreadyRegisteredError:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": _LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION},
        )
        return render_template(
            "pages/splash.html",
            oauth_email_collision=True,
            oauth_collision_provider="Google",
            oauth_reject_message=_EMAIL_COLLISION_MESSAGE,
        )

    login_user(resolved_user)
    record_event(EventName.LOGIN_SUCCESS, dimensions={"method": "google"})
    return redirect(url_for(ROUTES.UTUBS.HOME))


def _resolve_preferred_username(raw_username: str | None, email: str) -> str:
    """Sanitizes a provider-supplied display name for use as a username seed.

    Falls back to the email local-part when the raw name is missing, or when
    sanitization would change it (rather than raising, since there's no form
    field here to reject against).

    Examples:
        >>> _resolve_preferred_username("Jane Doe", "jane@example.com")
        'Jane Doe'
        >>> _resolve_preferred_username("<script>alert(1)</script>", "jane@example.com")
        'jane'
        >>> _resolve_preferred_username(None, "jane@example.com")
        'jane'
    """
    if not raw_username:
        return email.split("@", 1)[0]

    sanitized_username = sanitize_user_input(raw_username)
    if sanitized_username != raw_username:
        return email.split("@", 1)[0]
    return sanitized_username
