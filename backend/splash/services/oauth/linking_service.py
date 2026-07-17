from __future__ import annotations

from typing import Any

from flask import redirect, render_template, request, session, url_for
from flask_login import current_user, login_user
from sqlalchemy.exc import IntegrityError
from werkzeug import Response as WerkzeugResponse

from backend import db, oauth
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.schemas.base import StatusMessageResponseSchema
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.schemas.users import LoginRedirectResponseSchema
from backend.splash.constants import (
    LOGIN_FAILURE_REASON_BAD_PASSWORD,
    LOGIN_FAILURE_REASON_SUSPENDED,
    LoginErrorCodes,
    OAuthLinkErrorCodes,
)
from backend.splash.services.forgot_password import provider_display_name
from backend.splash.services.oauth.constants import (
    LINK_INTENT_ACTION_LINK,
    LINK_INTENT_ACTION_PROOF,
    OAUTH_LINK_INTENT_SESSION_KEY,
    OAUTH_LINK_MAX_AGE_SECONDS,
    OAUTH_PENDING_LINK_SESSION_KEY,
    Provider,
)
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.oauth_strs import (
    CONFIRM_LINK_CONTINUE_WITH_TEXT,
    CONFIRM_LINK_EXPIRED_MESSAGE,
    CONFIRM_LINK_INVALID_MESSAGE,
    CONFIRM_LINK_OAUTH_ONLY_PROMPT,
    CONFIRM_LINK_PASSWORD_PROMPT,
    CONFIRM_LINK_SUBMIT_TEXT,
    CONFIRM_LINK_TITLE,
    LINK_ALREADY_LINKED_MESSAGE,
    LINK_FORBIDDEN_MESSAGE,
    LINK_INTENT_INVALID_MESSAGE,
    LINK_INVALID_PASSWORD_MESSAGE,
    LINK_PASSWORD_REQUIRED_MESSAGE,
    LINK_PROOF_MISMATCH_MESSAGE,
    LINK_PROVIDER_NOT_CONFIGURED_MESSAGE,
    LINK_SUBJECT_OWNED_BY_OTHER_ACCOUNT_MESSAGE,
    LINK_SUCCESS_MESSAGE,
    UNLINK_LAST_METHOD_MESSAGE,
    UNLINK_NOT_LINKED_MESSAGE,
    UNLINK_SUCCESS_MESSAGE,
)
from backend.utils.strings.user_strs import USER_FAILURE

# Settings-page query params the link flows redirect back with. Read by the
# settings template/JS to surface a success or error banner; kept as named
# constants because they are a contract between this service and the
# settings surface.
SETTINGS_LINKED_QUERY_PARAM = "linked"
SETTINGS_LINK_ERROR_QUERY_PARAM = "link_error"
LINK_ERROR_ALREADY_LINKED = "already_linked"
LINK_ERROR_SUBJECT_TAKEN = "subject_taken"
LINK_ERROR_PROOF_MISMATCH = "proof_mismatch"
LINK_ERROR_INVALID = "invalid"


def build_connected_accounts_context() -> dict[str, Any]:
    """Builds the settings page's Connected Accounts template context for the
    authenticated user.

    Returns a dict with:
    - ``connected_account_rows``: one row per *configured* provider —
      ``{key, display_name, linked_email (str | None), is_last_method,
      proof_provider_display (str | None), link_url, unlink_url}``
    - ``connected_accounts_has_password``: whether the account can password
      re-auth (drives which link path the UI takes)
    - ``connected_accounts_banner``: ``{"kind": "success"|"error",
      "message": str} | None`` from the ``linked``/``link_error`` redirect
      query params.
    """
    identity_email_by_provider = {
        identity.provider: identity.email for identity in current_user.oauth_identities
    }
    has_password = current_user.password is not None
    linked_count = len(current_user.oauth_identities)

    proof_provider_display: str | None = None
    if not has_password:
        proof_provider = next(
            (
                parsed_provider
                for identity in current_user.oauth_identities
                if (parsed_provider := provider_from_key(identity.provider)) is not None
                and _provider_client_registered(parsed_provider)
            ),
            None,
        )
        if proof_provider is not None:
            proof_provider_display = provider_display_name(proof_provider.value)

    connected_account_rows: list[dict[str, Any]] = []
    for provider in Provider:
        if not _provider_client_registered(provider):
            continue
        linked_email = identity_email_by_provider.get(provider.value)
        is_linked = provider.value in identity_email_by_provider
        connected_account_rows.append(
            {
                "key": provider.value,
                "display_name": provider_display_name(provider.value),
                "is_linked": is_linked,
                "linked_email": linked_email,
                "is_last_method": is_linked and not has_password and linked_count == 1,
                "proof_provider_display": (
                    proof_provider_display if not is_linked else None
                ),
                "link_url": url_for(
                    ROUTES.USERS.OAUTH_LINK,
                    user_id=current_user.id,
                    provider=provider.value,
                ),
                "unlink_url": url_for(
                    ROUTES.USERS.OAUTH_UNLINK,
                    user_id=current_user.id,
                    provider=provider.value,
                ),
            }
        )

    return {
        "connected_account_rows": connected_account_rows,
        "connected_accounts_has_password": has_password,
        "connected_accounts_banner": _build_settings_link_banner(),
    }


def _build_settings_link_banner() -> dict[str, str] | None:
    """Maps the ``linked``/``link_error`` redirect query params (set by the
    link callbacks) onto the settings-page banner content."""
    linked_provider = provider_from_key(
        request.args.get(SETTINGS_LINKED_QUERY_PARAM, "")
    )
    if linked_provider is not None:
        return {
            "kind": "success",
            "message": LINK_SUCCESS_MESSAGE.format(
                provider=provider_display_name(linked_provider.value)
            ),
        }

    link_error_messages = {
        LINK_ERROR_ALREADY_LINKED: LINK_INTENT_INVALID_MESSAGE,
        LINK_ERROR_SUBJECT_TAKEN: LINK_SUBJECT_OWNED_BY_OTHER_ACCOUNT_MESSAGE,
        LINK_ERROR_PROOF_MISMATCH: LINK_PROOF_MISMATCH_MESSAGE,
        LINK_ERROR_INVALID: LINK_INTENT_INVALID_MESSAGE,
    }
    link_error_message = link_error_messages.get(
        request.args.get(SETTINGS_LINK_ERROR_QUERY_PARAM, "")
    )
    if link_error_message is not None:
        return {"kind": "error", "message": link_error_message}
    return None


def provider_from_key(provider_key: str) -> Provider | None:
    """Parses a URL path segment into a supported Provider, or None."""
    try:
        return Provider(provider_key)
    except ValueError:
        return None


def _provider_client_registered(provider: Provider) -> bool:
    return hasattr(oauth, provider.value)


def _is_stash_expired(stash: dict[str, Any]) -> bool:
    issued_at = stash.get("issued_at")
    if not isinstance(issued_at, (int, float)):
        return True
    return (utc_now().timestamp() - float(issued_at)) > OAUTH_LINK_MAX_AGE_SECONDS


def _callback_route_for(provider: Provider) -> str:
    return (
        OAUTH_ROUTES.GOOGLE_CALLBACK
        if provider is Provider.GOOGLE
        else OAUTH_ROUTES.GITHUB_CALLBACK
    )


def _stash_link_intent(
    *, action: str, target_provider: Provider, proof_provider: Provider | None = None
) -> None:
    intent: dict[str, Any] = {
        "action": action,
        "target_provider": target_provider.value,
        "user_id": current_user.id,
        "issued_at": utc_now().timestamp(),
    }
    if proof_provider is not None:
        intent["proof_provider"] = proof_provider.value
    session[OAUTH_LINK_INTENT_SESSION_KEY] = intent


def pop_valid_link_intent_for_current_user() -> dict[str, Any] | None:
    """Pops the pending settings-link intent, returning it only when it exists,
    is unexpired, and belongs to the currently authenticated user. Always
    removes the stash — an invalid intent must not be replayable."""
    intent = session.pop(OAUTH_LINK_INTENT_SESSION_KEY, None)
    if not isinstance(intent, dict):
        return None
    if _is_stash_expired(intent):
        return None
    if intent.get("user_id") != current_user.id:
        return None
    return intent


def peek_valid_link_intent_for_current_user() -> dict[str, Any] | None:
    """Reads (without consuming) the pending settings-link intent, applying the
    same validity checks as `pop_valid_link_intent_for_current_user`."""
    intent = session.get(OAUTH_LINK_INTENT_SESSION_KEY)
    if not isinstance(intent, dict):
        return None
    if _is_stash_expired(intent) or intent.get("user_id") != current_user.id:
        session.pop(OAUTH_LINK_INTENT_SESSION_KEY, None)
        return None
    return intent


def settings_link_failure_redirect() -> WerkzeugResponse:
    """Clears any pending settings-link intent and bounces back to Settings
    with a generic link error — used by the provider callbacks when an OAuth
    failure branch (declined consent, exchange error, unverified email,
    missing claims) is hit while an authenticated link flow is in flight."""
    session.pop(OAUTH_LINK_INTENT_SESSION_KEY, None)
    return redirect(
        url_for(
            ROUTES.USERS.SETTINGS,
            **{SETTINGS_LINK_ERROR_QUERY_PARAM: LINK_ERROR_INVALID},
        )
    )


def initiate_settings_link(
    *, user_id: int, provider_key: str, password: str | None
) -> FlaskResponse:
    """Starts linking a new OAuth provider to the authenticated user's account.

    Enforces the DECIDED linking policy before any provider round-trip:

    - **Password accounts** must re-authenticate with their password here.
    - **Password-less (OAuth-only) accounts** cannot re-auth locally, so the
      proof is an OAuth round-trip to a provider *already linked* to the
      account — the stashed intent starts at the ``proof`` stage and the
      callback upgrades it to ``link`` once the proof sign-in matches.

    On success returns a JSON body carrying the redirect URL for the OAuth
    dance entry point (``GET /oauth/<provider>/link``); the browser navigates
    there and the shared provider callback finishes the link.
    """
    if user_id != current_user.id:
        return build_message_error_response(
            message=LINK_FORBIDDEN_MESSAGE,
            error_code=OAuthLinkErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    target_provider = provider_from_key(provider_key)
    if target_provider is None:
        return build_message_error_response(
            message=LINK_PROVIDER_NOT_CONFIGURED_MESSAGE,
            error_code=OAuthLinkErrorCodes.PROVIDER_NOT_CONFIGURED,
            status_code=404,
        )
    if not _provider_client_registered(target_provider):
        return build_message_error_response(
            message=LINK_PROVIDER_NOT_CONFIGURED_MESSAGE,
            error_code=OAuthLinkErrorCodes.PROVIDER_NOT_CONFIGURED,
            status_code=400,
        )

    already_linked_providers = {
        identity.provider for identity in current_user.oauth_identities
    }
    if target_provider.value in already_linked_providers:
        return build_message_error_response(
            message=LINK_ALREADY_LINKED_MESSAGE.format(
                provider=provider_display_name(target_provider.value)
            ),
            error_code=OAuthLinkErrorCodes.ALREADY_LINKED,
            status_code=400,
        )

    if current_user.password is not None:
        if not password:
            return build_field_error_response(
                message=LINK_PASSWORD_REQUIRED_MESSAGE,
                errors={"password": [LINK_PASSWORD_REQUIRED_MESSAGE]},
                error_code=OAuthLinkErrorCodes.INVALID_FORM_INPUT,
            )
        if not current_user.is_password_correct(password):
            record_event(
                EventName.LOGIN_FAILURE,
                dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
            )
            return build_field_error_response(
                message=LINK_INVALID_PASSWORD_MESSAGE,
                errors={"password": [LINK_INVALID_PASSWORD_MESSAGE]},
                error_code=OAuthLinkErrorCodes.INVALID_PASSWORD,
            )
        _stash_link_intent(
            action=LINK_INTENT_ACTION_LINK, target_provider=target_provider
        )
        redirect_provider = target_provider
    else:
        proof_provider: Provider | None = next(
            (
                parsed_provider
                for identity in current_user.oauth_identities
                if (parsed_provider := provider_from_key(identity.provider)) is not None
                and parsed_provider is not target_provider
                and _provider_client_registered(parsed_provider)
            ),
            None,
        )
        if proof_provider is None:
            # A password-less account always has >=1 linked identity, but its
            # provider may be unconfigured in this deployment — no local
            # proof is possible, so refuse rather than silently weaken the
            # policy.
            return build_message_error_response(
                message=LINK_PROVIDER_NOT_CONFIGURED_MESSAGE,
                error_code=OAuthLinkErrorCodes.PROVIDER_NOT_CONFIGURED,
                status_code=400,
            )
        _stash_link_intent(
            action=LINK_INTENT_ACTION_PROOF,
            target_provider=target_provider,
            proof_provider=proof_provider,
        )
        redirect_provider = proof_provider

    return APIResponse(
        status_code=200,
        data=LoginRedirectResponseSchema(
            redirect_url=url_for(OAUTH_ROUTES.LINK, provider=redirect_provider.value)
        ),
    ).to_response()


def initiate_link_oauth_redirect(provider_key: str) -> WerkzeugResponse:
    """Kicks off the OAuth consent redirect for a pending settings-link intent.

    The intent (stashed by `initiate_settings_link`) must exist, be unexpired,
    belong to the current user, and name this provider as either the link
    target or the proof provider — otherwise the user is bounced back to
    Settings and the stash cleared.
    """
    provider = provider_from_key(provider_key)
    if provider is None or not _provider_client_registered(provider):
        return redirect(url_for(ROUTES.USERS.SETTINGS))

    intent = peek_valid_link_intent_for_current_user()
    if intent is None:
        return redirect(url_for(ROUTES.USERS.SETTINGS))

    intent_action = intent.get("action")
    expected_provider_value = (
        intent.get("proof_provider")
        if intent_action == LINK_INTENT_ACTION_PROOF
        else intent.get("target_provider")
    )
    if expected_provider_value != provider.value:
        session.pop(OAUTH_LINK_INTENT_SESSION_KEY, None)
        return redirect(url_for(ROUTES.USERS.SETTINGS))

    redirect_uri = url_for(_callback_route_for(provider), _external=True)
    oauth_client = getattr(oauth, provider.value)
    return oauth_client.authorize_redirect(redirect_uri)


def handle_authenticated_oauth_callback(
    *, provider: Provider, subject: str, email: str
) -> WerkzeugResponse:
    """Resolves a provider callback that arrived on an authenticated session.

    Only reachable through the settings-link flow: without a valid stashed
    intent this mirrors the old `@no_authenticated_users_allowed` behavior
    (bounce home). With one, it either verifies proof (the sign-in matched a
    provider identity already on the account, then forwards to the target
    provider's dance) or completes the link (inserts the identity row).
    """
    intent = pop_valid_link_intent_for_current_user()
    if intent is None:
        return redirect(url_for(ROUTES.UTUBS.HOME))

    intent_action = intent.get("action")

    if (
        intent_action == LINK_INTENT_ACTION_PROOF
        and intent.get("proof_provider") == provider.value
    ):
        proof_identity: UserOAuthIdentity | None = UserOAuthIdentity.query.filter_by(
            user_id=current_user.id,
            provider=provider.value,
            provider_subject=subject,
        ).first()
        if proof_identity is None:
            return redirect(
                url_for(
                    ROUTES.USERS.SETTINGS,
                    **{SETTINGS_LINK_ERROR_QUERY_PARAM: LINK_ERROR_PROOF_MISMATCH},
                )
            )
        target_provider = provider_from_key(intent.get("target_provider", ""))
        if target_provider is None:
            return redirect(url_for(ROUTES.USERS.SETTINGS))
        _stash_link_intent(
            action=LINK_INTENT_ACTION_LINK, target_provider=target_provider
        )
        return redirect(url_for(OAUTH_ROUTES.LINK, provider=target_provider.value))

    if (
        intent_action == LINK_INTENT_ACTION_LINK
        and intent.get("target_provider") == provider.value
    ):
        link_error = _insert_identity_for_user(
            user=current_user, provider=provider, subject=subject, email=email
        )
        if link_error is not None:
            return redirect(
                url_for(
                    ROUTES.USERS.SETTINGS,
                    **{SETTINGS_LINK_ERROR_QUERY_PARAM: link_error},
                )
            )
        return redirect(
            url_for(
                ROUTES.USERS.SETTINGS,
                **{SETTINGS_LINKED_QUERY_PARAM: provider.value},
            )
        )

    return redirect(url_for(ROUTES.UTUBS.HOME))


def _insert_identity_for_user(
    *, user: Users, provider: Provider, subject: str, email: str
) -> str | None:
    """Inserts a UserOAuthIdentity row for `user`, enforcing the uniqueness
    guards. Returns None on success, or a `LINK_ERROR_*` code.

    Records the OAUTH_IDENTITY_LINKED domain event on success.
    """
    existing_subject_identity: UserOAuthIdentity | None = (
        UserOAuthIdentity.query.filter_by(
            provider=provider.value, provider_subject=subject
        ).first()
    )
    if existing_subject_identity is not None:
        if existing_subject_identity.user_id == user.id:
            # Idempotent: this exact provider account is already linked here.
            return None
        return LINK_ERROR_SUBJECT_TAKEN

    already_linked_providers = {identity.provider for identity in user.oauth_identities}
    if provider.value in already_linked_providers:
        return LINK_ERROR_ALREADY_LINKED

    user.oauth_identities.append(
        UserOAuthIdentity(
            provider=provider.value, provider_subject=subject, email=email
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        # Lost a race on UNIQUE(provider, provider_subject) or
        # UNIQUE(user_id, provider) — the check-then-act guards above cannot
        # be atomic with the insert.
        db.session.rollback()
        return LINK_ERROR_INVALID
    record_event(
        EventName.OAUTH_IDENTITY_LINKED, dimensions={"provider": provider.value}
    )
    return None


def stash_pending_collision_link(
    *, provider: Provider, subject: str, email: str
) -> None:
    """Stashes the provider identity that collided with an existing local
    account's email, for the confirm-link flow to complete after a second
    proof of account ownership."""
    session[OAUTH_PENDING_LINK_SESSION_KEY] = {
        "provider": provider.value,
        "subject": subject,
        "email": email,
        "issued_at": utc_now().timestamp(),
    }


def _peek_pending_collision_link() -> dict[str, Any] | None:
    pending = session.get(OAUTH_PENDING_LINK_SESSION_KEY)
    if not isinstance(pending, dict):
        return None
    if _is_stash_expired(pending):
        session.pop(OAUTH_PENDING_LINK_SESSION_KEY, None)
        return None
    return pending


def complete_pending_collision_link(logged_in_user: Users) -> str | None:
    """Completes a pending collision link right after a successful OAuth
    sign-in, when the pending identity's email belongs to the user who just
    proved ownership of the account by signing in.

    This is the DECIDED policy's OAuth-only branch: the pending identity came
    from a real OAuth dance with the *new* provider earlier in this same
    session, and the sign-in that just completed is the round-trip proof with
    an *already-linked* provider — never an auto-link on the email claim
    alone.

    Returns the linked provider key on success, else None. Always consumes
    the stash when it matches this user (success or not — no replay).
    """
    pending = _peek_pending_collision_link()
    if pending is None:
        return None

    pending_email = pending.get("email")
    if (
        not isinstance(pending_email, str)
        or pending_email.lower() != logged_in_user.email
    ):
        return None

    session.pop(OAUTH_PENDING_LINK_SESSION_KEY, None)

    pending_provider = provider_from_key(pending.get("provider", ""))
    pending_subject = pending.get("subject")
    if pending_provider is None or not isinstance(pending_subject, str):
        return None

    link_error = _insert_identity_for_user(
        user=logged_in_user,
        provider=pending_provider,
        subject=pending_subject,
        email=pending_email,
    )
    if link_error is not None:
        return None
    return pending_provider.value


def render_confirm_link_page() -> WerkzeugResponse | str:
    """Renders the collision confirm-link page for the stashed pending
    identity.

    Password accounts get a password re-auth form; password-less accounts get
    "continue with <already-linked provider>" sign-in buttons (completing the
    link via `complete_pending_collision_link` after that sign-in).
    """
    pending = _peek_pending_collision_link()
    if pending is None:
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=CONFIRM_LINK_EXPIRED_MESSAGE,
        )

    email_owner: Users | None = Users.query.filter(
        Users.email == str(pending.get("email", "")).lower()
    ).first()
    if email_owner is None:
        session.pop(OAUTH_PENDING_LINK_SESSION_KEY, None)
        return render_template(
            "pages/splash.html",
            oauth_generic_failure=True,
            oauth_reject_message=CONFIRM_LINK_INVALID_MESSAGE,
        )

    pending_provider_key = str(pending.get("provider", ""))
    pending_provider_display = provider_display_name(pending_provider_key)
    owner_has_password = email_owner.password is not None

    login_route_by_provider = {
        Provider.GOOGLE: OAUTH_ROUTES.GOOGLE_LOGIN,
        Provider.GITHUB: OAUTH_ROUTES.GITHUB_LOGIN,
    }
    existing_login_providers = [
        {
            "key": owner_provider.value,
            "display_name": provider_display_name(owner_provider.value),
            "button_text": CONFIRM_LINK_CONTINUE_WITH_TEXT.format(
                provider=provider_display_name(owner_provider.value)
            ),
            "login_url": url_for(login_route_by_provider[owner_provider]),
        }
        for identity in email_owner.oauth_identities
        if (owner_provider := provider_from_key(identity.provider)) is not None
        and _provider_client_registered(owner_provider)
    ]

    prompt_template = (
        CONFIRM_LINK_PASSWORD_PROMPT
        if owner_has_password
        else CONFIRM_LINK_OAUTH_ONLY_PROMPT
    )
    return render_template(
        "pages/splash.html",
        is_confirming_oauth_link=True,
        confirm_link_title=CONFIRM_LINK_TITLE,
        confirm_link_prompt=prompt_template.format(
            email=pending.get("email"), provider=pending_provider_display
        ),
        confirm_link_submit_text=CONFIRM_LINK_SUBMIT_TEXT,
        confirm_link_has_password=owner_has_password,
        confirm_link_existing_providers=existing_login_providers,
    )


def confirm_link_with_password(password: str) -> FlaskResponse:
    """Completes the collision confirm-link flow for a password account:
    verifies the password of the account that owns the pending identity's
    email, inserts the identity row, and signs the user in."""
    pending = _peek_pending_collision_link()
    if pending is None:
        return build_message_error_response(
            message=CONFIRM_LINK_EXPIRED_MESSAGE,
            error_code=OAuthLinkErrorCodes.INTENT_INVALID,
        )

    email_owner: Users | None = Users.query.filter(
        Users.email == str(pending.get("email", "")).lower()
    ).first()
    if email_owner is None or email_owner.password is None:
        session.pop(OAUTH_PENDING_LINK_SESSION_KEY, None)
        return build_message_error_response(
            message=CONFIRM_LINK_INVALID_MESSAGE,
            error_code=OAuthLinkErrorCodes.INTENT_INVALID,
        )

    if not email_owner.is_password_correct(password):
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
        )
        return build_field_error_response(
            message=LINK_INVALID_PASSWORD_MESSAGE,
            errors={"password": [LINK_INVALID_PASSWORD_MESSAGE]},
            error_code=OAuthLinkErrorCodes.INVALID_PASSWORD,
        )

    if email_owner.is_suspended:
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_SUSPENDED},
        )
        return build_message_error_response(
            message=USER_FAILURE.ACCOUNT_SUSPENDED,
            error_code=LoginErrorCodes.ACCOUNT_SUSPENDED,
            status_code=403,
        )

    if not email_owner.email_validated:
        # Linking attaches a sign-in method to an account whose ownership is
        # anchored on its email — never attach before that email is verified.
        return build_message_error_response(
            message=USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
            error_code=LoginErrorCodes.ACCOUNT_NOT_EMAIL_VALIDATED,
            status_code=401,
        )

    session.pop(OAUTH_PENDING_LINK_SESSION_KEY, None)

    pending_provider = provider_from_key(str(pending.get("provider", "")))
    pending_subject = pending.get("subject")
    if pending_provider is None or not isinstance(pending_subject, str):
        return build_message_error_response(
            message=CONFIRM_LINK_INVALID_MESSAGE,
            error_code=OAuthLinkErrorCodes.INTENT_INVALID,
        )

    link_error = _insert_identity_for_user(
        user=email_owner,
        provider=pending_provider,
        subject=pending_subject,
        email=str(pending.get("email")),
    )
    if link_error is not None:
        return build_message_error_response(
            message=CONFIRM_LINK_INVALID_MESSAGE,
            error_code=OAuthLinkErrorCodes.INTENT_INVALID,
        )

    login_user(email_owner)
    record_event(EventName.LOGIN_SUCCESS, dimensions={"method": pending_provider.value})
    return APIResponse(
        status_code=200,
        data=LoginRedirectResponseSchema(redirect_url=url_for(ROUTES.UTUBS.HOME)),
    ).to_response()


def unlink_provider(*, user_id: int, provider_key: str) -> FlaskResponse:
    """Disconnects an OAuth provider from the authenticated user's account.

    Mirrors the admin portal's last-credential guard
    (`backend/admin/account_data_service.py:unlink_oauth_identity`): a
    password-less account may never drop its final identity.
    """
    if user_id != current_user.id:
        return build_message_error_response(
            message=LINK_FORBIDDEN_MESSAGE,
            error_code=OAuthLinkErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    provider = provider_from_key(provider_key)
    if provider is None:
        return build_message_error_response(
            message=LINK_PROVIDER_NOT_CONFIGURED_MESSAGE,
            error_code=OAuthLinkErrorCodes.PROVIDER_NOT_CONFIGURED,
            status_code=404,
        )

    identity: UserOAuthIdentity | None = UserOAuthIdentity.query.filter_by(
        user_id=current_user.id, provider=provider.value
    ).first()
    if identity is None:
        return build_message_error_response(
            message=UNLINK_NOT_LINKED_MESSAGE.format(
                provider=provider_display_name(provider.value)
            ),
            error_code=OAuthLinkErrorCodes.NOT_LINKED,
            status_code=404,
        )

    if current_user.password is None and len(current_user.oauth_identities) == 1:
        return build_message_error_response(
            message=UNLINK_LAST_METHOD_MESSAGE,
            error_code=OAuthLinkErrorCodes.LAST_METHOD,
            status_code=403,
        )

    db.session.delete(identity)
    db.session.commit()
    record_event(
        EventName.OAUTH_IDENTITY_UNLINKED, dimensions={"provider": provider.value}
    )
    return APIResponse(
        status_code=200,
        data=StatusMessageResponseSchema(
            status=STD_JSON.SUCCESS,
            message=UNLINK_SUCCESS_MESSAGE.format(
                provider=provider_display_name(provider.value)
            ),
        ),
    ).to_response()
