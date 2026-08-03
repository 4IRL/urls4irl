from __future__ import annotations

from typing import Any

from authlib.integrations.base_client.errors import OAuthError
from flask import redirect, render_template, request, session, url_for
from flask_login import current_user, login_user
from pydantic import BaseModel
from werkzeug import Response as WerkzeugResponse

from backend import oauth
from backend.api_common.input_sanitization import sanitize_user_input
from backend.api_common.parse_request import parse_query_args
from backend.api_common.responses import FlaskResponse
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.schemas.requests.splash import GoogleOAuthCallbackQuerySchema
from backend.splash.constants import (
    LOGIN_FAILURE_REASON_OAUTH_CONSENT_DECLINED,
    LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION,
    LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE,
    LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL,
    LOGIN_FAILURE_REASON_SUSPENDED,
    OAuthErrorCodes,
)
from backend.splash.services.oauth.account_service import (
    EmailAlreadyRegisteredError,
    find_or_create_oauth_user,
)
from backend.splash.services.oauth.constants import (
    OAUTH_NEXT_SESSION_KEY,
    Provider,
)
from backend.splash.services.oauth.linking_service import (
    complete_pending_collision_link,
    handle_authenticated_oauth_callback,
    peek_valid_link_intent_for_current_user,
    settings_link_failure_redirect,
    stash_pending_collision_link,
)
from backend.splash.services.user_login import verify_and_provide_next_page
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.strings.user_strs import USER_FAILURE
from backend.utils.strings.oauth_strs import (
    CONSENT_DECLINED_MESSAGE,
    GENERIC_FAILURE_MESSAGE,
    INVALID_CALLBACK_QUERY_MESSAGE,
    UNVERIFIED_EMAIL_MESSAGE,
)


def initiate_google_login() -> WerkzeugResponse:
    """Kicks off the Google OAuth consent redirect.

    The splash templates only render the button that links here when
    `google_oauth_enabled` is `True` (`should_register_google_oauth`,
    surfaced via `backend.utils.constants.provide_config_for_constants`), but
    this route itself is always registered, so it's still reachable directly
    in an unconfigured deployment. Guards against that here rather than
    relying on the button being hidden as the only line of defense — without
    it, `oauth.google` would raise `AttributeError` (Authlib's registry has
    no client registered under that name).

    Stashes the `next` query param (if present) in the session so
    `handle_google_callback` can redirect back to the originally requested
    page on success, mirroring the password-login `next` handling in
    `user_login.py`.
    """
    if not hasattr(oauth, "google"):
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))

    session[OAUTH_NEXT_SESSION_KEY] = request.args.get("next")
    redirect_uri = url_for(OAUTH_ROUTES.GOOGLE_CALLBACK, _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


def handle_google_callback() -> WerkzeugResponse | str | FlaskResponse:
    """Handles Google's OAuth redirect back to the app.

    Resolves the token exchange, extracts and validates the OIDC claims, and
    either logs the user in (creating an account on first sign-in) or renders
    a reject page for every failure branch (declined consent, token-exchange
    failure, unverified email, missing claims, email collision).

    Guards against an unconfigured `oauth.google` the same way
    `initiate_google_login` does; see the note there. Reachable here if a
    request arrives with a stale/bookmarked callback URL after credentials
    were removed mid-session.

    Authenticated sessions are only served here for the settings-link flow
    (Google OAuth apps share one callback URL between sign-in and linking):
    with a valid link intent the resolved subject/email feed
    `handle_authenticated_oauth_callback`; without one the request bounces
    home, preserving the old `@no_authenticated_users_allowed` behavior.
    """
    if not hasattr(oauth, "google"):
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=GENERIC_FAILURE_MESSAGE,
        )

    if (
        current_user.is_authenticated
        and peek_valid_link_intent_for_current_user() is None
    ):
        return redirect(url_for(ROUTES.UTUBS.HOME))

    stashed_next = session.pop(OAUTH_NEXT_SESSION_KEY, None)

    parsed = parse_query_args(
        GoogleOAuthCallbackQuerySchema,
        message=INVALID_CALLBACK_QUERY_MESSAGE,
        error_code=OAuthErrorCodes.INVALID_FORM_INPUT,
    )
    if not isinstance(parsed, BaseModel):
        return parsed

    if parsed.error is not None:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_CONSENT_DECLINED},
        )
        if current_user.is_authenticated:
            return settings_link_failure_redirect()
        return render_template(
            "pages/splash.html",
            oauth_consent_declined=True,
            oauth_reject_message=CONSENT_DECLINED_MESSAGE,
        )

    try:
        token = oauth.google.authorize_access_token()
    except OAuthError:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE},
        )
        if current_user.is_authenticated:
            return settings_link_failure_redirect()
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=GENERIC_FAILURE_MESSAGE,
        )

    userinfo: dict[str, Any] | None = token.get("userinfo")
    if userinfo is None:
        # No `openid` scope (the fake-provider branch registered with plain
        # OAuth2 scopes) means Authlib never parsed an id_token, so fall back
        # to a plain-OAuth2 GET against the configured userinfo endpoint.
        userinfo = oauth.google.userinfo(token=token)

    if userinfo.get("email_verified") is not True:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL},
        )
        if current_user.is_authenticated:
            return settings_link_failure_redirect()
        return render_template(
            "pages/splash.html",
            oauth_unverified_email=True,
            oauth_reject_message=UNVERIFIED_EMAIL_MESSAGE,
        )

    subject: str | None = userinfo.get("sub")
    email: str | None = userinfo.get("email")
    if subject is None or email is None:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE},
        )
        if current_user.is_authenticated:
            return settings_link_failure_redirect()
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=GENERIC_FAILURE_MESSAGE,
        )

    if current_user.is_authenticated:
        return handle_authenticated_oauth_callback(
            provider=Provider.GOOGLE, subject=subject, email=email
        )

    preferred_username = resolve_preferred_username(
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
        # DECIDED policy: never auto-link on the provider's email claim, and
        # never just reject — stash the pending identity and route to the
        # confirm-link page, where a second proof of local-account ownership
        # (password re-auth, or a sign-in with an already-linked provider)
        # completes the link.
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION},
        )
        stash_pending_collision_link(
            provider=Provider.GOOGLE, subject=subject, email=email
        )
        return redirect(url_for(OAUTH_ROUTES.CONFIRM_LINK_PAGE))

    if resolved_user.is_suspended:
        # Suspended accounts never reach an authenticated session; mirrors
        # the password-login gate. Rendered through the shared OAuth reject
        # banner so the splash page shows the suspension message.
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_SUSPENDED},
        )
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=USER_FAILURE.ACCOUNT_SUSPENDED,
        )

    login_user(resolved_user)
    record_event(EventName.LOGIN_SUCCESS, dimensions={"method": "google"})
    # Completes a collision confirm-link for a password-less account: this
    # sign-in with an already-linked provider is the required second proof of
    # account ownership (no-op when no unexpired pending link matches).
    complete_pending_collision_link(resolved_user)

    next_page = (
        # Synthetic single-key dict reusing verify_and_provide_next_page's
        # validation contract (user_login.py) rather than real request.args.
        verify_and_provide_next_page({"next": stashed_next})
        if isinstance(stashed_next, str)
        else ""
    )
    redirect_url = next_page if next_page else url_for(ROUTES.UTUBS.HOME)
    return redirect(redirect_url)


def resolve_preferred_username(raw_username: str | None, email: str) -> str:
    """Sanitizes a provider-supplied display name for use as a username seed.

    Falls back to the email local-part when the raw name is missing, or when
    sanitization would change it (rather than raising, since there's no form
    field here to reject against).

    Examples:
        >>> resolve_preferred_username("Jane Doe", "jane@example.com")
        'Jane Doe'
        >>> resolve_preferred_username("<script>alert(1)</script>", "jane@example.com")
        'jane'
        >>> resolve_preferred_username(None, "jane@example.com")
        'jane'
    """
    if not raw_username:
        return email.split("@", 1)[0]

    sanitized_username = sanitize_user_input(raw_username)
    if sanitized_username != raw_username:
        return email.split("@", 1)[0]
    return sanitized_username
