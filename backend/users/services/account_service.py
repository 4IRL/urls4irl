from __future__ import annotations

from dataclasses import asdict
from typing import Any

from flask import current_app, session, url_for
from flask_login import current_user, logout_user
from redis import Redis
from sqlalchemy.exc import IntegrityError

from backend import db, oauth
from backend.admin.account_data_service import erase_user_core
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.extensions import audit
from backend.extensions.extension_utils import safe_get_email_sender
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.users import User_Role, Users
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.schemas.users import (
    AccountRemovalResponseSchema,
    ChangeEmailResponseSchema,
    ChangePasswordResponseSchema,
    ChangeUsernameResponseSchema,
)
from backend.splash.constants import LOGIN_FAILURE_REASON_BAD_PASSWORD
from backend.splash.services.forgot_password import provider_display_name
from backend.splash.services.oauth.constants import (
    Provider,
    REMOVAL_INTENT_ACTION_DELETE,
)
from backend.users.constants import (
    ChangeEmailErrorCodes,
    ChangePasswordErrorCodes,
    ChangeUsernameErrorCodes,
    DeleteAccountErrorCodes,
)
from backend.users.services.removal_oauth import _stash_removal_intent
from backend.utils.all_routes import OAUTH_ROUTES, ROUTES
from backend.utils.constants import USER_CONSTANTS
from backend.utils.datetime_utils import utc_now
from backend.utils.mailjet_utils import handle_mailjet_failure
from backend.utils.reauth_throttle import (
    clear_reauth_failures,
    is_reauth_locked_out,
    record_reauth_failure,
)
from backend.utils.session_utils import restamp_current_session
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.email_validation_strs import EMAILS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.user_strs import (
    ACCOUNT_AUDIT_ACTIONS,
    ACCOUNT_DELETED_SUCCESS,
    EMAIL_CHANGE_CONFIRMATION_SENT,
    EMAIL_CHANGE_NO_CHANGE,
    OAUTH_PROOF_REDIRECT_PENDING,
    PASSWORD_CHANGE_SUCCESS,
    USER_FAILURE,
    USERNAME_CHANGE_NO_CHANGE,
    USERNAME_CHANGE_SUCCESS,
)

_MEMORY_URI: str = "memory://"


def build_account_info_context() -> dict[str, Any]:
    """Build the Settings page Account-info block template context for the
    authenticated user.

    Mirrors ``build_user_stats_context()`` — no parameters, reads
    ``current_user``, returns a flat dict of read-only account details. Keys are
    namespaced ``account_*`` so they never collide with the connected-accounts
    or stats context keys. Member-since is intentionally omitted here: the
    ``settings()`` route already splats ``build_user_stats_context()``, whose
    ``stats_member_since_iso`` / ``stats_member_since_exact`` values the
    account-info block reuses (no duplicate date formatting).
    """
    # Sole-creator delete-modal context (DD-5): split the UTubs this user created
    # into those that will TRANSFER ownership on erasure (≥1 other member) versus
    # those that will be DELETED outright (solo). Deliberately NOT
    # ``stats_utubs_created`` — that count over-counts for the transfer notice
    # because it includes the solo UTubs, which are deleted rather than handed
    # off. Mirrors ``erase_user_core``'s per-UTub membership resolution.
    utubs_transferring: int = 0
    utubs_deleting_solo: int = 0
    for membership in current_user.utubs_is_member_of:
        containing_utub = membership.to_utub
        if containing_utub.utub_creator != current_user.id:
            continue
        if len(containing_utub.members) > 1:
            utubs_transferring += 1
        else:
            utubs_deleting_solo += 1

    # Danger-zone OAuth-only re-auth (Step 6 modal): the display name of the
    # linked provider the removal round-trip re-consents through, so the
    # "Re-authenticate with <provider>" button reads correctly. None for
    # password accounts (they re-auth inline, no OAuth round-trip).
    removal_proof_provider_display: str | None = None
    if current_user.password is None:
        proof_provider = _select_proof_provider()
        if proof_provider is not None:
            removal_proof_provider_display = provider_display_name(proof_provider.value)

    return {
        "account_username": current_user.username,
        "account_email": current_user.email,
        "account_email_validated": current_user.email_validated,
        # None when no change is in flight; the staged (lowercased) address
        # otherwise. Gates both the account-info pending indicator and the
        # in-form change-email warning (DD-16/DD-18) at initial page load.
        "account_pending_email": current_user.pending_email,
        # Created UTubs with ≥1 other member — ownership transfers on delete.
        "account_utubs_transferring": utubs_transferring,
        # Created solo UTubs — permanently deleted on account delete.
        "account_utubs_deleting_solo": utubs_deleting_solo,
        # Provider display name for the OAuth-only removal re-auth button.
        "account_removal_proof_provider_display": removal_proof_provider_display,
    }


def _build_rate_limit_redis() -> Redis | None:
    """Build a client on the shared enforcement Redis (``REDIS_URI``), or return
    ``None`` when Redis is unavailable.

    Mirrors ``backend/admin/ops_service.py:_build_metrics_redis`` but reads the
    shared ``REDIS_URI`` (enforcement) rather than the best-effort metrics Redis.
    Returns ``None`` when the URI is absent or the in-memory stub, so callers
    fail open (the username-change cap is anti-spam, not a security boundary).
    """
    redis_uri: str | None = current_app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == _MEMORY_URI:
        return None
    return Redis.from_url(redis_uri)


def apply_username_change(*, user_id: int, new_username: str) -> FlaskResponse:
    """Change the authenticated user's username (no password re-auth per
    Decision #1), rate-limited to ``MAX_USERNAME_CHANGES_PER_DAY`` per rolling
    24h per user via a Redis-only counter (Decision #4).

    Named ``apply_username_change`` to avoid a bare-name collision with the
    ``change_username`` route/view function on the ``users`` blueprint.

    Guard order (so a rejected/no-op attempt never burns a rate-limit slot):
    self-ownership → no-op → rate-limit precheck (fail-open) → uniqueness →
    commit (IntegrityError guard) → INCR (EXPIRE only on the first) → success.
    """
    # (1) Self-ownership: the URL user_id must be the acting user.
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=ChangeUsernameErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    # (2) No-op short-circuit: resubmitting the current username never burns a
    # slot and never touches Redis.
    if new_username == current_user.username:
        return APIResponse(
            status_code=200,
            data=ChangeUsernameResponseSchema(
                username=current_user.username,
                status=STD_JSON.NO_CHANGE,
                message=USERNAME_CHANGE_NO_CHANGE,
            ),
        ).to_response()

    rate_limit_key = f"username-change:{user_id}"
    redis_client = _build_rate_limit_redis()

    # (3) Rate-limit pre-check (fail-open): read the counter before committing so
    # the 4th change in the window is rejected without a DB write or an INCR.
    if redis_client is not None:
        try:
            current_count = int(redis_client.get(rate_limit_key) or 0)
            if current_count >= USER_CONSTANTS.MAX_USERNAME_CHANGES_PER_DAY:
                return build_message_error_response(
                    message=USER_FAILURE.USERNAME_CHANGE_RATE_LIMITED,
                    error_code=ChangeUsernameErrorCodes.RATE_LIMITED,
                    status_code=429,
                )
        except Exception as redis_error:
            current_app.logger.exception(
                "username-change rate-limit precheck failed (failing open): "
                f"{redis_error}"
            )

    # (4) Uniqueness (excluding the current user, so a no-op already returned
    # above cannot false-positive here).
    existing_user: Users | None = Users.query.filter(
        Users.username == new_username, Users.id != current_user.id
    ).first()
    if existing_user is not None:
        return build_field_error_response(
            message=USER_FAILURE.USERNAME_TAKEN,
            errors={"username": [USER_FAILURE.USERNAME_TAKEN]},
            error_code=ChangeUsernameErrorCodes.USERNAME_TAKEN,
            status_code=400,
        )

    # (5) Commit, guarding the UNIQUE-constraint race with an IntegrityError
    # rollback that surfaces the same taken-username field error.
    current_user.username = new_username
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return build_field_error_response(
            message=USER_FAILURE.USERNAME_TAKEN,
            errors={"username": [USER_FAILURE.USERNAME_TAKEN]},
            error_code=ChangeUsernameErrorCodes.USERNAME_TAKEN,
            status_code=400,
        )

    # (6) Only after a committed success, increment the counter (fail-open). The
    # EXPIRE is set only on the first INCR → fixed 24h window anchored at the
    # first change (Decision #4).
    if redis_client is not None:
        try:
            new_count = redis_client.incr(rate_limit_key)
            if new_count == 1:
                redis_client.expire(
                    rate_limit_key, USER_CONSTANTS.USERNAME_CHANGE_WINDOW_SECONDS
                )
        except Exception as redis_error:
            current_app.logger.exception(
                "username-change rate-limit increment failed (failing open): "
                f"{redis_error}"
            )

    # (7) Success.
    return APIResponse(
        status_code=200,
        data=ChangeUsernameResponseSchema(
            username=current_user.username,
            status=STD_JSON.SUCCESS,
            message=USERNAME_CHANGE_SUCCESS,
        ),
    ).to_response()


def apply_password_change(
    *, user_id: int, current_password: str, new_password: str
) -> FlaskResponse:
    """Change the authenticated user's password after current-password re-auth,
    then invalidate every OTHER session (Decision #2).

    Named ``apply_password_change`` to avoid a bare-name collision with the
    ``change_password`` route/view function on the ``users`` blueprint.

    Guard order: self-ownership (403) → OAuth-only (400, defense-in-depth) →
    brute-force lockout (429, shared per-user re-auth counter, DD-1) → re-auth
    (400 on wrong current password, recording the existing ``LOGIN_FAILURE``
    metric and a re-auth failure) → success: clear the failure counter, change
    password, bump ``sessions_invalidated_at`` and re-stamp the acting session
    so it survives, then commit.
    """
    # (1) Self-ownership: the URL user_id must be the acting user.
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=ChangePasswordErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    # (2) OAuth-only guard (defense-in-depth): the template hides the form for
    # password-less accounts. Predicate replicated locally per DD-19 (no import
    # from backend.splash.* for this check).
    if current_user.password is None:
        return build_message_error_response(
            message=USER_FAILURE.PASSWORD_CHANGE_OAUTH_ONLY,
            error_code=ChangePasswordErrorCodes.OAUTH_ONLY_NO_PASSWORD,
            status_code=400,
        )

    # (3) Brute-force lockout (DD-1): a per-user Redis counter shared with the
    # settings OAuth-link re-auth gate. Fail-open; checked before the password
    # compare so a locked-out session cannot keep guessing.
    if is_reauth_locked_out(user_id):
        return build_message_error_response(
            message=USER_FAILURE.TOO_MANY_PASSWORD_ATTEMPTS,
            error_code=ChangePasswordErrorCodes.TOO_MANY_ATTEMPTS,
            status_code=429,
        )

    # (4) Re-auth: verify the supplied current password (mirrors
    # initiate_settings_link). On failure, record a re-auth failure toward the
    # lockout + the existing LOGIN_FAILURE metric, then surface a dedicated field
    # error on `currentPassword`.
    if not current_user.is_password_correct(current_password):
        record_reauth_failure(user_id)
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
        )
        return build_field_error_response(
            message=USER_FAILURE.CURRENT_PASSWORD_INCORRECT,
            errors={"currentPassword": [USER_FAILURE.CURRENT_PASSWORD_INCORRECT]},
            error_code=ChangePasswordErrorCodes.INVALID_PASSWORD,
            status_code=400,
        )

    # (5) Success: clear the failure counter, then change the password,
    # invalidate every OTHER session by bumping sessions_invalidated_at, then
    # re-stamp the acting session so the current device survives its own
    # invalidation bump.
    clear_reauth_failures(user_id)
    current_user.change_password(new_password)
    current_user.sessions_invalidated_at = utc_now()
    restamp_current_session()
    db.session.commit()

    return APIResponse(
        status_code=200,
        data=ChangePasswordResponseSchema(
            status=STD_JSON.SUCCESS,
            message=PASSWORD_CHANGE_SUCCESS,
        ),
    ).to_response()


def apply_email_change(
    *, user_id: int, new_email: str, current_password: str
) -> FlaskResponse:
    """Stage a not-yet-confirmed new email after current-password re-auth, then
    mail a confirmation link to the NEW address. The live ``email`` is untouched
    until the user clicks that link (the anonymous confirm route swaps it).

    Named ``apply_email_change`` to avoid a bare-name collision with the
    ``change_email`` route/view function on the ``users`` blueprint.

    DD-19: builds the confirm URL by route NAME via ``url_for`` and sends via the
    neutral ``email_sender`` extension — no ``backend.splash.*`` service import.

    Guard order: self-ownership (403) → OAuth-only (400) → re-auth lockout (429)
    → re-auth (400) → no-op (200) → rate-limit precheck fail-open (429, a capped
    user is rejected before any probe) → uniqueness (400; a taken-email
    rejection burns one daily slot via the shared local INCR helper so
    email-enumeration probing is bounded to MAX_EMAIL_CHANGES_PER_DAY, DD-1) →
    stage + commit → send (rollback the staging on send failure) →
    INCR-on-success (EXPIRE only on the first) → success (200).
    """
    # (1) Self-ownership: the URL user_id must be the acting user.
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=ChangeEmailErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    # (2) OAuth-only guard (defense-in-depth): the template hides the form for
    # password-less accounts. Predicate replicated locally per DD-19.
    if current_user.password is None:
        return build_message_error_response(
            message=USER_FAILURE.EMAIL_CHANGE_OAUTH_ONLY,
            error_code=ChangeEmailErrorCodes.OAUTH_ONLY_NO_PASSWORD,
            status_code=400,
        )

    # (3) Brute-force lockout: the per-user Redis counter shared with the
    # change-password / settings OAuth-link re-auth gates. Fail-open; checked
    # before the password compare so a locked-out session cannot keep guessing.
    if is_reauth_locked_out(user_id):
        return build_message_error_response(
            message=USER_FAILURE.TOO_MANY_PASSWORD_ATTEMPTS,
            error_code=ChangeEmailErrorCodes.TOO_MANY_ATTEMPTS,
            status_code=429,
        )

    # (4) Re-auth: verify the supplied current password. On failure, record a
    # re-auth failure toward the lockout + the existing LOGIN_FAILURE metric,
    # then surface a dedicated field error on ``currentPassword``.
    if not current_user.is_password_correct(current_password):
        record_reauth_failure(user_id)
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
        )
        return build_field_error_response(
            message=USER_FAILURE.CURRENT_PASSWORD_INCORRECT,
            errors={"currentPassword": [USER_FAILURE.CURRENT_PASSWORD_INCORRECT]},
            error_code=ChangeEmailErrorCodes.INVALID_PASSWORD,
            status_code=400,
        )

    # (5) No-op short-circuit: resubmitting the current email never sends an
    # email nor touches Redis. ``pending_email`` echoes whatever is currently
    # staged (None if nothing is in flight); guard 5 does not clear or touch it.
    if new_email.lower() == current_user.email:
        return APIResponse(
            status_code=200,
            data=ChangeEmailResponseSchema(
                status=STD_JSON.NO_CHANGE,
                message=EMAIL_CHANGE_NO_CHANGE,
                pending_email=current_user.pending_email,
            ),
        ).to_response()

    rate_limit_key = f"email-change:{user_id}"
    redis_client = _build_rate_limit_redis()

    def increment_rate_limit_counter() -> None:
        """Increment the per-user daily email-change counter (fail-open).

        EXPIRE is set only on the first INCR → a fixed 24h window anchored at the
        first change/probe. Kept a LOCAL closure (DD-4: no cross-function
        extraction); shared by the taken-email rejection below and the
        success path so a Redis error can never block the caller's response.
        """
        if redis_client is None:
            return
        try:
            new_count = redis_client.incr(rate_limit_key)
            if new_count == 1:
                redis_client.expire(
                    rate_limit_key, USER_CONSTANTS.EMAIL_CHANGE_WINDOW_SECONDS
                )
        except Exception as redis_error:
            current_app.logger.exception(
                "email-change rate-limit increment failed (failing open): "
                f"{redis_error}"
            )

    # (6) Rate-limit pre-check (fail-open): read the counter BEFORE the
    # uniqueness probe so a capped user is rejected 429 without a DB write, an
    # email send, an INCR, or leaking whether the probed address is taken (DD-1).
    if redis_client is not None:
        try:
            current_count = int(redis_client.get(rate_limit_key) or 0)
            if current_count >= USER_CONSTANTS.MAX_EMAIL_CHANGES_PER_DAY:
                return build_message_error_response(
                    message=USER_FAILURE.EMAIL_CHANGE_RATE_LIMITED,
                    error_code=ChangeEmailErrorCodes.RATE_LIMITED,
                    status_code=429,
                )
        except Exception as redis_error:
            current_app.logger.exception(
                "email-change rate-limit precheck failed (failing open): "
                f"{redis_error}"
            )

    # (7) Uniqueness (excluding the current user, so the no-op above cannot
    # false-positive here). The live email is what enforces uniqueness — a
    # different user's pending_email does not reserve the address. A taken-email
    # rejection increments the daily counter (fail-open) BEFORE returning, so
    # every enumeration probe burns one slot and probing is bounded to
    # MAX_EMAIL_CHANGES_PER_DAY (DD-1).
    existing_user: Users | None = Users.query.filter(
        Users.email == new_email.lower(), Users.id != current_user.id
    ).first()
    if existing_user is not None:
        increment_rate_limit_counter()
        return build_field_error_response(
            message=USER_FAILURE.EMAIL_TAKEN,
            errors={"newEmail": [USER_FAILURE.EMAIL_TAKEN]},
            error_code=ChangeEmailErrorCodes.EMAIL_TAKEN,
            status_code=400,
        )

    # (8) Clear the re-auth failure counter, stage the pending email, and commit.
    # Staging happens strictly BEFORE minting the token below (DD-5), so
    # get_email_change_token()'s self.pending_email read is always the just-staged
    # value.
    clear_reauth_failures(user_id)
    current_user.stage_email_change(new_email)
    db.session.commit()

    # (9) Send the confirmation link to the NEW address, building the confirm URL
    # by route NAME only (DD-19). On a send failure, roll back the staging so
    # nothing is left half-staged.
    confirmation_url = url_for(
        ROUTES.SPLASH.CONFIRM_EMAIL_CHANGE,
        token=current_user.get_email_change_token(),
        _external=True,
    )
    email_sender = safe_get_email_sender(current_app)
    email_result = email_sender.send_email_change_confirmation(
        new_email.lower(), current_user.username, confirmation_url
    )
    if email_result.status_code >= 500:
        current_user.pending_email = None
        db.session.commit()
        return handle_mailjet_failure(
            email_result, error_code=ChangeEmailErrorCodes.EMAIL_SEND_FAILURE
        )

    # (10) Only after a committed staging + successful send, increment the
    # counter (fail-open, EXPIRE only on the first INCR → fixed 24h window
    # anchored at the first change). DD-3 read-then-late-increment unchanged.
    increment_rate_limit_counter()

    # (11) Success — echo the staged pending_email so the client patches the
    # account-info card in place (DD-6).
    return APIResponse(
        status_code=200,
        data=ChangeEmailResponseSchema(
            status=STD_JSON.SUCCESS,
            message=EMAIL_CHANGE_CONFIRMATION_SENT,
            pending_email=current_user.pending_email,
        ),
    ).to_response()


def reject_self_sole_admin(user: Users) -> FlaskResponse | None:
    """Return a 403 error response when ``user`` is the last active admin,
    otherwise ``None`` (the removal may proceed).

    Shared by the delete endpoint's service and the OAuth-proof callback re-run,
    so both enforce the identical invariant from one implementation instead of
    inline copies (DD-21). Mirrors the query in
    ``backend/admin/guards.py:reject_leaving_zero_active_admins`` but is
    self-scoped (checks ``user`` itself, not a separate actor) and deliberately
    does NOT import from ``backend.admin.guards`` — the users domain does not
    import admin-module internals (the Step-2 import-direction rule); it
    reimplements the query rather than delegating.

    Returns ``None`` when ``user`` is not an admin (the guard does not apply).
    Otherwise counts the OTHER active (unsuspended) admins; if none remain,
    removing this account would leave the portal with zero admins, so it returns
    a 403 with the literal error code ``4`` — which is
    ``SOLE_ADMIN_FORBIDDEN`` on ``DeleteAccountErrorCodes``, so this shared
    response is correct without a per-endpoint enum import.
    """
    if user.role != User_Role.ADMIN:
        return None

    other_active_admin_count: int = Users.query.filter(
        Users.role == User_Role.ADMIN,
        Users.is_suspended == False,  # noqa: E712 — SQLAlchemy column comparison
        Users.id != user.id,
    ).count()
    if other_active_admin_count > 0:
        return None

    return build_message_error_response(
        message=USER_FAILURE.SOLE_ADMIN_CANNOT_LEAVE,
        error_code=4,
        status_code=403,
    )


def _select_proof_provider() -> Provider | None:
    """Pick an already-linked provider to serve as the OAuth-proof round-trip
    target for a password-less account's removal re-auth (DD-6).

    Returns the first linked identity that parses to a supported ``Provider``
    **and** is registered (configured) in this deployment — mirroring the
    proof-provider selection in ``initiate_settings_link`` /
    ``build_connected_accounts_context`` so this redirect targets the same
    provider the settings page shows and never dead-ends at an unconfigured
    provider dance. Returns ``None`` only when no linked identity is usable
    (unreachable in practice — a password-less account always keeps at least one
    linked, valid identity, since the unlink guard forbids dropping the last
    sign-in method).
    """
    for identity in current_user.oauth_identities:
        try:
            candidate_provider = Provider(identity.provider)
        except ValueError:
            continue
        if hasattr(oauth, candidate_provider.value):
            return candidate_provider
    return None


def _initiate_oauth_proof_removal(*, action: str) -> FlaskResponse:
    """Stash a removal intent for the authenticated password-less account and
    return the 200 redirect that starts the OAuth-proof round-trip (DD-6).

    Used by the delete OAuth-only branch to stash the intent shape and return an
    ``AccountRemovalResponseSchema`` redirect into ``GET /oauth/<provider>/link``;
    the authenticated callback executes the stashed removal. Kept as a helper (a
    single caller today) so the OAuth-proof initiation stays separable from the
    delete guard flow.
    """
    proof_provider = _select_proof_provider()
    if proof_provider is None:
        # Unreachable for a real password-less account; refuse rather than
        # redirect into a dead provider dance.
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=DeleteAccountErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    _stash_removal_intent(
        action=action,
        user_id=current_user.id,
        proof_provider=proof_provider,
    )
    return APIResponse(
        status_code=200,
        data=AccountRemovalResponseSchema(
            status=STD_JSON.SUCCESS,
            message=OAUTH_PROOF_REDIRECT_PENDING,
            redirect_url=url_for(OAUTH_ROUTES.LINK, provider=proof_provider.value),
        ),
    ).to_response()


def apply_account_deletion(
    *, user_id: int, current_password: str | None, confirm_username: str
) -> FlaskResponse:
    """Irreversibly delete (GDPR-erase) the authenticated password account, then
    log the acting session out.

    Adapts the tested admin erasure core (``erase_user_core``): the ``Users`` row
    is tombstoned in place (nine non-nullable FKs forbid a hard delete), PII child
    rows are dropped, UTub memberships are resolved (solo→delete, created-with-
    others→ownership transfer, non-creator→remove), and every session/refresh
    token is revoked. A **new self-actor GDPR-erasure audit trail** (DD-4) is
    recorded under the users-domain ``ACCOUNT_AUDIT_ACTIONS.SELF_ACCOUNT_ERASE``
    action, distinguishing a self-delete from an admin-initiated erase.

    Guard order (documented numbered comments): self-ownership (403) → sole-admin
    (403, shared ``reject_self_sole_admin`` helper, DD-21) → typed-username
    confirmation re-check (400 field error, DD-C — defense-in-depth against a
    client-gated-only submit) → OAuth-only branch (200 redirect into the
    OAuth-proof round-trip, DD-6 — a password-less account re-consents through an
    already-linked provider and the callback executes the stashed erasure) →
    re-auth lockout (429) → current-password re-auth (400 field error, records the
    existing ``LOGIN_FAILURE`` metric + a re-auth failure) → success: clear the
    failure counter, erase, record the self-actor audit row + ``ACCOUNT_DELETED``
    metric, commit, log out, and return the splash redirect target.
    """
    # (1) Self-ownership: the URL user_id must be the acting user.
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=DeleteAccountErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    # (2) Sole-admin guard (DD-21): the last active admin cannot remove their own
    # account — it would leave the portal with zero admins.
    sole_admin_error = reject_self_sole_admin(current_user)
    if sole_admin_error is not None:
        return sole_admin_error

    # (3) Typed-username confirmation re-check (DD-C): the modal client-gates its
    # submit on an exact-username match, but re-verify server-side as
    # defense-in-depth so a crafted request can never skip the confirmation.
    if confirm_username.strip() != current_user.username:
        return build_field_error_response(
            message=USER_FAILURE.DELETE_CONFIRMATION_MISMATCH,
            errors={"confirmUsername": [USER_FAILURE.DELETE_CONFIRMATION_MISMATCH]},
            error_code=DeleteAccountErrorCodes.CONFIRMATION_MISMATCH,
            status_code=400,
        )

    # (4) OAuth-only branch (DD-6): a password-less account cannot re-auth
    # inline, so it re-proves identity via an OAuth round-trip through an
    # already-linked provider. Stash the removal intent and 200-redirect the
    # client into GET /oauth/<provider>/link; the authenticated callback executes
    # the stashed erasure. The typed-username confirmation (guard 3) is already
    # re-checked above, so the OAuth-proof path is gated by it too.
    if current_user.password is None:
        return _initiate_oauth_proof_removal(action=REMOVAL_INTENT_ACTION_DELETE)

    # (5) Brute-force lockout: the shared per-user Redis counter. Fail-open;
    # checked before the password compare so a locked-out session cannot keep
    # guessing.
    if is_reauth_locked_out(user_id):
        return build_message_error_response(
            message=USER_FAILURE.TOO_MANY_PASSWORD_ATTEMPTS,
            error_code=DeleteAccountErrorCodes.TOO_MANY_ATTEMPTS,
            status_code=429,
        )

    # (6) Re-auth: verify the supplied current password. A missing/empty
    # ``currentPassword`` on a password account (the schema makes the field
    # optional so OAuth-only accounts can omit it) is treated as a failed re-auth
    # — short-circuited before ``is_password_correct`` so it never receives
    # ``None``. On any failure, record a re-auth failure toward the lockout + the
    # existing LOGIN_FAILURE metric, then surface a ``currentPassword`` field
    # error.
    if not current_password or not current_user.is_password_correct(current_password):
        record_reauth_failure(user_id)
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
        )
        return build_field_error_response(
            message=USER_FAILURE.CURRENT_PASSWORD_INCORRECT,
            errors={"currentPassword": [USER_FAILURE.CURRENT_PASSWORD_INCORRECT]},
            error_code=DeleteAccountErrorCodes.INVALID_PASSWORD,
            status_code=400,
        )

    # (7) Success: clear the failure counter, then erase. Capture the PK as an int
    # BEFORE the erase so the post-commit audit/response never dereferences a
    # detached/expired ORM instance (ObjectDeletedError).
    clear_reauth_failures(user_id)
    erased_user_id: int = current_user.id
    counts = erase_user_core(target_user=current_user)

    # New self-actor GDPR-erasure audit trail (DD-4): unlike the admin path there
    # is no separate ``reason`` to merge in, so the metadata is ``asdict(counts)``
    # verbatim. ``audit.record`` flushes into the caller's transaction; the commit
    # below lands the erasure and the audit row atomically.
    audit.record(
        actor_id=erased_user_id,
        action=ACCOUNT_AUDIT_ACTIONS.SELF_ACCOUNT_ERASE,
        target_type="User",
        target_id=str(erased_user_id),
        metadata=asdict(counts),
    )
    record_event(EventName.ACCOUNT_DELETED)
    db.session.commit()
    logout_user()
    if EMAILS.EMAIL_VALIDATED_SESS_KEY in session.keys():
        session.pop(EMAILS.EMAIL_VALIDATED_SESS_KEY)

    return APIResponse(
        status_code=200,
        data=AccountRemovalResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ACCOUNT_DELETED_SUCCESS,
            redirect_url=url_for(ROUTES.SPLASH.SPLASH_PAGE),
        ),
    ).to_response()
