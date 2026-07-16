from __future__ import annotations

from typing import Any

from authlib.integrations.base_client.errors import OAuthError
from flask import redirect, render_template, request, session, url_for
from flask_login import login_user
from pydantic import BaseModel
from werkzeug import Response as WerkzeugResponse

from backend import oauth
from backend.api_common.parse_request import parse_query_args
from backend.api_common.responses import FlaskResponse
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.schemas.requests.splash import GitHubOAuthCallbackQuerySchema
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
from backend.splash.services.oauth.google_service import resolve_preferred_username
from backend.splash.services.user_login import verify_and_provide_next_page
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.strings.user_strs import USER_FAILURE
from backend.utils.strings.oauth_strs import (
    CONSENT_DECLINED_MESSAGE,
    EMAIL_COLLISION_MESSAGE,
    GENERIC_FAILURE_MESSAGE,
    GITHUB_INVALID_CALLBACK_QUERY_MESSAGE,
    GITHUB_UNVERIFIED_EMAIL_MESSAGE,
)

# Relative resource paths resolved by Authlib against the registered
# `api_base_url` — `https://api.github.com/` in production, the fake
# provider's `/fake-oauth/github/` prefix under UI testing (see the GitHub
# registration branches in `backend/__init__.py`).
_GITHUB_USER_RESOURCE = "user"
_GITHUB_USER_EMAILS_RESOURCE = "user/emails"


def initiate_github_login() -> WerkzeugResponse:
    """Kicks off the GitHub OAuth consent redirect.

    Mirrors `initiate_google_login` exactly: the splash templates only render
    the button that links here when `github_oauth_enabled` is `True`, but the
    route itself is always registered, so guard against an unconfigured
    deployment where `oauth.github` was never registered.

    Stashes the `next` query param (if present) in the session so
    `handle_github_callback` can redirect back to the originally requested
    page on success.
    """
    if not hasattr(oauth, "github"):
        return redirect(url_for(ROUTES.SPLASH.SPLASH_PAGE))

    session[OAUTH_NEXT_SESSION_KEY] = request.args.get("next")
    redirect_uri = url_for(OAUTH_ROUTES.GITHUB_CALLBACK, _external=True)
    return oauth.github.authorize_redirect(redirect_uri)


def handle_github_callback() -> WerkzeugResponse | str | FlaskResponse:
    """Handles GitHub's OAuth redirect back to the app.

    GitHub is plain OAuth2 with no OIDC layer — the token carries no
    `id_token`/`userinfo` claims — so where the Google callback reads parsed
    claims off the token, this one makes two resource calls after the
    exchange:

    1. ``GET user`` — the account payload; ``id`` is the stable subject,
       ``login`` the preferred-username seed.
    2. ``GET user/emails`` — the account's email list; the address marked
       ``primary`` AND ``verified`` is the one trusted for account
       resolution. No primary+verified address → unverified-email reject
       (GitHub's equivalent of Google's ``email_verified: false``).

    Every other branch (declined consent, token-exchange failure, missing
    claims, email collision, suspension, `next` redirect) mirrors
    `handle_google_callback`.
    """
    if not hasattr(oauth, "github"):
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=GENERIC_FAILURE_MESSAGE,
        )

    stashed_next = session.pop(OAUTH_NEXT_SESSION_KEY, None)

    parsed = parse_query_args(
        GitHubOAuthCallbackQuerySchema,
        message=GITHUB_INVALID_CALLBACK_QUERY_MESSAGE,
        error_code=OAuthErrorCodes.INVALID_FORM_INPUT,
    )
    if not isinstance(parsed, BaseModel):
        return parsed

    if parsed.error is not None:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_CONSENT_DECLINED},
        )
        return render_template(
            "pages/splash.html",
            oauth_consent_declined=True,
            oauth_reject_message=CONSENT_DECLINED_MESSAGE,
        )

    try:
        token = oauth.github.authorize_access_token()
    except OAuthError:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE},
        )
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=GENERIC_FAILURE_MESSAGE,
        )

    user_payload = _fetch_github_json(_GITHUB_USER_RESOURCE, token)
    if not isinstance(user_payload, dict):
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE},
        )
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=GENERIC_FAILURE_MESSAGE,
        )

    emails_payload = _fetch_github_json(_GITHUB_USER_EMAILS_RESOURCE, token)
    if not isinstance(emails_payload, list):
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE},
        )
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=GENERIC_FAILURE_MESSAGE,
        )

    email = select_primary_verified_email(emails_payload)
    if email is None:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL},
        )
        return render_template(
            "pages/splash.html",
            oauth_unverified_email=True,
            oauth_reject_message=GITHUB_UNVERIFIED_EMAIL_MESSAGE,
        )

    github_account_id = user_payload.get("id")
    if github_account_id is None:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE},
        )
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=GENERIC_FAILURE_MESSAGE,
        )
    subject = str(github_account_id)

    preferred_username = resolve_preferred_username(
        user_payload.get("login") or user_payload.get("name"), email
    )

    try:
        resolved_user = find_or_create_oauth_user(
            provider=Provider.GITHUB,
            subject=subject,
            email=email,
            preferred_username=preferred_username,
        )
    except EmailAlreadyRegisteredError:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION},
        )
        return render_template(
            "pages/splash.html",
            oauth_email_collision=True,
            oauth_reject_message=EMAIL_COLLISION_MESSAGE,
        )

    if resolved_user.is_suspended:
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
    record_event(EventName.LOGIN_SUCCESS, dimensions={"method": "github"})

    next_page = (
        verify_and_provide_next_page({"next": stashed_next})
        if isinstance(stashed_next, str)
        else ""
    )
    redirect_url = next_page if next_page else url_for(ROUTES.UTUBS.HOME)
    return redirect(redirect_url)


def _fetch_github_json(resource_path: str, token: dict) -> Any:
    """Fetches a GitHub API resource with the exchanged token, returning the
    decoded JSON body, or `None` on a non-200 status or an undecodable body.

    The caller type-checks the returned shape (`dict` for ``user``, `list`
    for ``user/emails``) rather than trusting the provider's response.
    """
    response = oauth.github.get(resource_path, token=token)
    if response.status_code != 200:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def select_primary_verified_email(emails_payload: list[Any]) -> str | None:
    """Selects the address GitHub marks both ``primary`` and ``verified``.

    GitHub's ``GET /user/emails`` returns a list of
    ``{"email", "primary", "verified", "visibility"}`` objects. Exactly one
    address can be primary; it is only trusted here when also verified —
    an unverified primary (or a malformed entry) yields `None`, which the
    callback rejects as unverified.

    Examples:
        >>> select_primary_verified_email(
        ...     [{"email": "a@b.co", "primary": True, "verified": True}]
        ... )
        'a@b.co'
        >>> select_primary_verified_email(
        ...     [{"email": "a@b.co", "primary": True, "verified": False}]
        ... ) is None
        True
    """
    for email_entry in emails_payload:
        if not isinstance(email_entry, dict):
            continue
        if email_entry.get("primary") is not True:
            continue
        if email_entry.get("verified") is not True:
            continue
        email_value = email_entry.get("email")
        if isinstance(email_value, str) and email_value:
            return email_value
    return None
