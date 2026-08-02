"""Confirm-email-change service (Settings "change email" flow, Phase 3).

Owns the anonymous confirm step of the re-verification round-trip: the user
clicks the link mailed to their *new* address, and this service swaps the
pending email into the live ``Users.email`` column, then redirects to the
splash page carrying a closed-set outcome code as a query param.

Kept separate from ``validate_email.py`` so the destructive registration
consume path (``_handle_invalid_verification_token``, which deletes the user on
a bad token) is never reachable from here. The confirm route is anonymous — the
link is opened from the new inbox, possibly on another device — and it never
auto-logs the user in: a credential-sensitive change requires a fresh login.
"""

from __future__ import annotations

from flask import current_app, redirect, url_for
import jwt
from sqlalchemy.exc import IntegrityError
from werkzeug import Response as WerkzeugResponse
from werkzeug.exceptions import NotFound

from backend import db
from backend.app_logger import safe_add_log, warning_log
from backend.models.users import Users
from backend.splash.utils import verify_token
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.user_strs import (
    EMAIL_CHANGE_CONFIRM_INVALID,
    EMAIL_CHANGE_CONFIRM_TAKEN,
    EMAIL_CHANGE_STATUS_QUERY_PARAM,
    EMAIL_CHANGE_SUCCESS,
    EMAIL_CHANGE_SUCCESS_AUTHENTICATED,
)

# The confirm route redirects back carrying EMAIL_CHANGE_STATUS_QUERY_PARAM (the
# param key, defined in user_strs.py so it can be JS-bridged; re-exported here so
# existing `from ...change_email import EMAIL_CHANGE_STATUS_QUERY_PARAM` imports
# still resolve) set to exactly one of the closed-set outcome codes below. Read by
# splash_page() / home() and mapped to banner content by build_email_change_banner().
# Mirrors the settings OAuth-link flow's SETTINGS_LINKED_QUERY_PARAM /
# SETTINGS_LINK_ERROR_QUERY_PARAM contract, retargeted at splash (DD-1).
EMAIL_CHANGE_STATUS_SUCCESS = "success"
EMAIL_CHANGE_STATUS_INVALID = "invalid_or_expired"
EMAIL_CHANGE_STATUS_TAKEN = "taken"
EMAIL_CHANGE_STATUS_ALREADY_CONFIRMED = "already_confirmed"


def _redirect_to_splash_with_status(status_code: str) -> WerkzeugResponse:
    """Redirect to the splash page carrying one outcome code. splash_page() is
    responsible for surfacing the banner (and for forwarding the code to HOME
    when the requester is still logged in — DD-9)."""
    return redirect(
        url_for(
            ROUTES.SPLASH.SPLASH_PAGE, **{EMAIL_CHANGE_STATUS_QUERY_PARAM: status_code}
        )
    )


def build_email_change_banner(
    status_code: str, *, authenticated: bool
) -> dict[str, str] | None:
    """Map a confirm-outcome code onto banner content, or None for an
    absent/unrecognized code.

    Mirrors ``_build_settings_link_banner()``'s ``{"kind", "message"}`` shape.
    ``authenticated`` (DD-15, required so a future third call site cannot forget
    it) selects the success copy: the login-clause-free
    ``EMAIL_CHANGE_SUCCESS_AUTHENTICATED`` on the HOME/already-logged-in path,
    the login-clause ``EMAIL_CHANGE_SUCCESS`` on the anonymous splash path. Both
    success codes (SUCCESS and the already-confirmed replay) share that copy;
    the two error codes carry no login clause, so ``authenticated`` never
    affects them.
    """
    success_message = (
        EMAIL_CHANGE_SUCCESS_AUTHENTICATED if authenticated else EMAIL_CHANGE_SUCCESS
    )
    return {
        EMAIL_CHANGE_STATUS_SUCCESS: {"kind": "success", "message": success_message},
        EMAIL_CHANGE_STATUS_ALREADY_CONFIRMED: {
            "kind": "success",
            "message": success_message,
        },
        EMAIL_CHANGE_STATUS_INVALID: {
            "kind": "error",
            "message": EMAIL_CHANGE_CONFIRM_INVALID,
        },
        EMAIL_CHANGE_STATUS_TAKEN: {
            "kind": "error",
            "message": EMAIL_CHANGE_CONFIRM_TAKEN,
        },
    }.get(status_code)


def confirm_email_change_for_user(token: str) -> WerkzeugResponse:
    """Confirm a pending email change and swap it into the live email column.

    Anonymous-reachable. Always issues an HTTP redirect to the splash page
    carrying a single outcome code — never renders a template directly and never
    logs the user in.

    Args:
        token (str): The purpose-keyed change-email JWT from the confirm link.

    Returns:
        (WerkzeugResponse): Redirect to splash with the outcome query param.
    """
    # (1) DD-2: verify_token resolves the user via first_or_404(), which raises
    # werkzeug NotFound directly (not a VerifyTokenResponse(user=None)) when the
    # token's username no longer maps to a row. A validly-signed but
    # wrong-purpose token (e.g. a validate-email or password-reset JWT minted
    # with the same SECRET_KEY) lacks the CHANGE_EMAIL claim, so verify_token's
    # payload[token_key] lookup raises KeyError before returning — catch it here
    # too so a mistakenly-clicked link redirects INVALID rather than 500ing.
    # Never call the registration consume path's user-deleting
    # _handle_invalid_verification_token here.
    try:
        verify_result = verify_token(token, EMAILS.CHANGE_EMAIL)
    except (NotFound, KeyError):
        warning_log("Change-email token invalid or resolved to no user")
        return _redirect_to_splash_with_status(EMAIL_CHANGE_STATUS_INVALID)

    if verify_result.is_expired or verify_result.failed_due_to_exception:
        return _redirect_to_splash_with_status(EMAIL_CHANGE_STATUS_INVALID)

    user = verify_result.user
    if user is None:
        return _redirect_to_splash_with_status(EMAIL_CHANGE_STATUS_INVALID)

    # (2) No pending email → already confirmed, or a replayed single-use token
    # (single-use is enforced by clearing pending_email on confirm — including
    # the TOCTOU/race TAKEN paths, so a replay after a taken-email outcome also
    # lands here as ALREADY_CONFIRMED rather than re-attempting the swap). No-op.
    if user.pending_email is None:
        return _redirect_to_splash_with_status(EMAIL_CHANGE_STATUS_ALREADY_CONFIRMED)

    # (3) DD-5 stale-token guard: independently re-decode the token (the same
    # decode verify_token already made) to read the target-email claim, and
    # reject if the user has since staged a *different* pending email — the
    # earlier token has been superseded. Done locally so the shared verify_token
    # / VerifyTokenResponse primitive stays untouched (Step 1's note).
    try:
        token_payload = jwt.decode(
            token,
            key=current_app.config[CONFIG_ENVS.SECRET_KEY],
            algorithms=[EMAILS.ALGORITHM],
        )
    except jwt.PyJWTError:
        return _redirect_to_splash_with_status(EMAIL_CHANGE_STATUS_INVALID)

    if token_payload.get(EMAILS.CHANGE_EMAIL_TARGET) != user.pending_email:
        warning_log(f"Superseded change-email token for User={user.id}")
        return _redirect_to_splash_with_status(EMAIL_CHANGE_STATUS_INVALID)

    # (4) TOCTOU uniqueness re-check: another account may have taken the pending
    # address between staging and now. Clear the now-unusable pending email.
    existing_owner: Users | None = Users.query.filter(
        Users.email == user.pending_email, Users.id != user.id
    ).first()
    if existing_owner is not None:
        return _clear_pending_and_redirect_taken(user)

    # (5) Finalize the swap, invalidating every session tied to the account
    # (DD-3 — no acting session to preserve on this anonymous route, so no
    # restamp). Guard the UNIQUE-constraint race with an IntegrityError rollback
    # that surfaces the same TAKEN outcome (DD-4), never a 500.
    try:
        user.finalize_email_change()
        user.sessions_invalidated_at = utc_now()
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _clear_pending_and_redirect_taken(user)

    safe_add_log(f"User={user.id} confirmed email change")
    return _redirect_to_splash_with_status(EMAIL_CHANGE_STATUS_SUCCESS)


def _clear_pending_and_redirect_taken(user: Users) -> WerkzeugResponse:
    """Clear a no-longer-usable pending email and redirect with TAKEN.

    Used by both the TOCTOU pre-check and the IntegrityError race guard so a
    replayed token finds nothing pending and no-ops rather than retrying a swap
    that can never succeed.
    """
    user.pending_email = None
    db.session.commit()
    return _redirect_to_splash_with_status(EMAIL_CHANGE_STATUS_TAKEN)
