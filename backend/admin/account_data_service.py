"""Admin account-data service: erasure, OAuth unlink, email-verification management.

Each function:
  - accepts keyword-only args, carries full typehints, returns FlaskResponse
  - enforces reject_self_action before any other guard or DB access
  - returns 404 via build_message_error_response when the target is missing
  - audits exactly once per successful state-changing action
  - lands all mutations and the audit row in a single db.session.commit()
  - no-ops idempotent state actions with a clear 200 message and no audit row
"""

from __future__ import annotations

from flask import current_app, url_for

from backend import db
from backend.admin.constants import AdminActionErrorCodes
from backend.admin.guards import reject_leaving_zero_active_admins, reject_self_action
from backend.admin.moderation_service import select_ownership_transfer_target
from backend.api_common.responses import FlaskResponse
from backend.api_v1.services.tokens import mark_all_refresh_tokens_revoked_for_user
from backend.extensions import audit
from backend.extensions.extension_utils import safe_get_email_sender
from backend.models.contact_form_entries import ContactFormEntries
from backend.models.email_validations import Email_Validations
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.admin_actions import AdminActionResponseSchema
from backend.schemas.errors import build_message_error_response
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON

# Tombstone identity applied by erasure. Users.username (max 25 chars) and
# Users.email are NOT NULL + unique, so erasure writes unique non-PII values
# instead of NULLs; ".invalid" is the RFC 2606 reserved TLD, so the tombstone
# address can never route mail.
TOMBSTONE_USERNAME_PREFIX: str = "deleted-user-"
TOMBSTONE_EMAIL_DOMAIN: str = "erased.invalid"


def build_tombstone_username(*, user_id: int) -> str:
    """Return the anonymized username for an erased user.

    Example: ``build_tombstone_username(user_id=42)`` -> ``"deleted-user-42"``.
    """
    return f"{TOMBSTONE_USERNAME_PREFIX}{user_id}"


def build_tombstone_email(*, user_id: int) -> str:
    """Return the anonymized email for an erased user.

    Example: ``build_tombstone_email(user_id=42)`` ->
    ``"deleted-user-42@erased.invalid"``.
    """
    return f"{build_tombstone_username(user_id=user_id)}@{TOMBSTONE_EMAIL_DOMAIN}"


def is_tombstoned(*, user: Users) -> bool:
    """True when the user has already been erased (tombstone username set)."""
    return user.username == build_tombstone_username(user_id=user.id)


def erase_user(*, actor_id: int, target_user_id: int, reason: str) -> FlaskResponse:
    """Erase a user account: anonymize-in-place, scrub PII, resolve memberships.

    The ``Users`` row is retained (nine FK references have no ``ondelete``,
    and ``AuditLogs.actorId`` must keep resolving) but every piece of PII is
    scrubbed from the live database immediately:

    - username -> ``deleted-user-<id>``, email -> tombstone address,
      password -> ``None``, ``email_validated`` -> ``False``
    - OAuth-identity, email-validation, and forgot-password child rows deleted
    - the user's ``ContactFormEntries`` rows deleted (bodies may hold PII)
    - web sessions invalidated + all API refresh tokens revoked

    UTub membership lifecycle is resolved per-UTub:

    - **solo UTub** (erased user is the only member): the UTub is hard-deleted
      via ORM cascade
    - **created UTub with other members**: ownership transfers to the
      deterministic remaining member (lowest-user-id CO_CREATOR, else lowest
      user id), then the erased user's membership row is removed
    - **non-creator membership**: the membership row is removed; contributed
      URLs/tags stay under the tombstone identity

    Retention lag: audit rows (90-day retention) and backups (90-day rotation)
    still contain the user's PII until they age out — a documented
    lawful-basis retention exception; the live DB is scrubbed immediately.

    Idempotent: an already-tombstoned user returns a no-op 200 with no audit
    row. Guarded: self-action 403; last-admin 403 (erasing the only active
    admin account would lock the portal out).

    Args:
        actor_id:       ID of the admin performing the action.
        target_user_id: Primary key of the user to erase.
        reason:         Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success or no-op.
        403 when actor targets themselves or the last active admin.
        404 when the target user does not exist.
    """
    self_action_error: FlaskResponse | None = reject_self_action(
        actor_id=actor_id, target_user_id=target_user_id
    )
    if self_action_error is not None:
        return self_action_error

    target_user: Users | None = Users.query.get(target_user_id)
    if target_user is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    last_admin_error: FlaskResponse | None = reject_leaving_zero_active_admins(
        target_user=target_user
    )
    if last_admin_error is not None:
        return last_admin_error

    if is_tombstoned(user=target_user):
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.ACCOUNT_ERASE_NOOP,
        ).to_response()

    utubs_deleted_count: int = 0
    ownerships_transferred_count: int = 0
    memberships_removed_count: int = 0

    # Snapshot: deleting UTubs/memberships mutates the relationship in-place.
    memberships: list[Utub_Members] = list(target_user.utubs_is_member_of)
    for membership in memberships:
        containing_utub: Utubs = membership.to_utub
        other_members: list[Utub_Members] = [
            utub_member
            for utub_member in containing_utub.members
            if utub_member.user_id != target_user_id
        ]

        if not other_members:
            # Solo UTub: unshared after erasure — delete it entirely (the
            # membership row goes with it via ORM cascade).
            db.session.delete(containing_utub)
            utubs_deleted_count += 1
            continue

        if containing_utub.utub_creator == target_user_id:
            new_owner_membership: Utub_Members = select_ownership_transfer_target(
                other_members=other_members
            )
            containing_utub.utub_creator = new_owner_membership.user_id
            new_owner_membership.member_role = Member_Role.CREATOR
            ownerships_transferred_count += 1

        db.session.delete(membership)
        containing_utub.set_last_updated()
        memberships_removed_count += 1

    # PII-bearing child rows.
    if target_user.email_confirm is not None:
        db.session.delete(target_user.email_confirm)
    if target_user.forgot_password is not None:
        db.session.delete(target_user.forgot_password)
    for oauth_identity in list(target_user.oauth_identities):
        db.session.delete(oauth_identity)
    contact_entries_deleted_count: int = ContactFormEntries.query.filter(
        ContactFormEntries.user_id == target_user_id
    ).delete(synchronize_session=False)

    # Anonymize the Users row itself.
    target_user.username = build_tombstone_username(user_id=target_user_id)
    target_user.email = build_tombstone_email(user_id=target_user_id)
    target_user.password = None
    target_user.email_validated = False

    # Kill all sessions: web via the invalidation stamp, API via bulk revoke.
    target_user.sessions_invalidated_at = utc_now()
    api_tokens_revoked_count: int = mark_all_refresh_tokens_revoked_for_user(
        user_id=target_user_id
    )

    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.USER_ERASE,
        target_type="User",
        target_id=str(target_user_id),
        metadata={
            "reason": reason,
            "utubs_deleted": utubs_deleted_count,
            "ownerships_transferred": ownerships_transferred_count,
            "memberships_removed": memberships_removed_count,
            "contact_entries_deleted": contact_entries_deleted_count,
            "api_tokens_revoked": api_tokens_revoked_count,
        },
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.ACCOUNT_ERASE_SUCCESS,
    ).to_response()


def unlink_oauth_identity(
    *, actor_id: int, target_user_id: int, identity_id: int, reason: str
) -> FlaskResponse:
    """Remove a specific OAuth identity from a user account.

    Guards:
    - Rejects self-action.
    - Returns 404 when the target user does not exist.
    - Returns 404 when no UserOAuthIdentity row matches both ``id=identity_id``
      AND ``user_id=target_user_id`` (prevents unlinking another user's identity).
    - Returns 403 when the target has no local password AND this is their only
      OAuth identity (unlinking would leave zero login methods).

    On success: deletes the identity row, audits OAUTH_UNLINK with provider in
    metadata, and commits.

    Args:
        actor_id:       ID of the admin performing the action.
        target_user_id: Primary key of the user whose identity to unlink.
        identity_id:    Primary key of the UserOAuthIdentity row to remove.
        reason:         Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success.
        403 when actor targets themselves or unlinking would leave zero credentials.
        404 when the target user or the identity row does not exist.
    """
    self_action_error: FlaskResponse | None = reject_self_action(
        actor_id=actor_id, target_user_id=target_user_id
    )
    if self_action_error is not None:
        return self_action_error

    target_user: Users | None = Users.query.get(target_user_id)
    if target_user is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    identity: UserOAuthIdentity | None = UserOAuthIdentity.query.filter_by(
        id=identity_id, user_id=target_user_id
    ).first()
    if identity is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    if target_user.password is None and len(target_user.oauth_identities) == 1:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.ACCOUNT_UNLINK_LAST_CREDENTIAL,
            error_code=AdminActionErrorCodes.LAST_CREDENTIAL_FORBIDDEN,
            status_code=403,
        )

    provider_name: str = identity.provider
    db.session.delete(identity)
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.OAUTH_UNLINK,
        target_type="User",
        target_id=str(target_user_id),
        metadata={"reason": reason, "provider": provider_name},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.ACCOUNT_UNLINK_SUCCESS.format(
            provider=provider_name
        ),
    ).to_response()


def mark_email_verified(
    *, actor_id: int, target_user_id: int, reason: str
) -> FlaskResponse:
    """Mark a user's email as verified and remove any pending Email_Validations row.

    Idempotent: if the user is already email-validated, returns a clear no-op 200
    with no audit row. On a real state change, sets ``email_validated=True``,
    deletes the ``Email_Validations`` row when present, audits EMAIL_VERIFY, and
    commits everything in a single transaction.

    Args:
        actor_id:       ID of the admin performing the action.
        target_user_id: Primary key of the user to verify.
        reason:         Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success or no-op.
        403 when actor targets themselves.
        404 when the target user does not exist.
    """
    self_action_error: FlaskResponse | None = reject_self_action(
        actor_id=actor_id, target_user_id=target_user_id
    )
    if self_action_error is not None:
        return self_action_error

    target_user: Users | None = Users.query.get(target_user_id)
    if target_user is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    if target_user.email_validated:
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_VERIFY_NOOP,
        ).to_response()

    target_user.validate_email()
    if target_user.email_confirm is not None:
        db.session.delete(target_user.email_confirm)
    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.EMAIL_VERIFY,
        target_type="User",
        target_id=str(target_user_id),
        metadata={"reason": reason},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_VERIFY_SUCCESS,
    ).to_response()


def resend_verification_email(
    *, actor_id: int, target_user_id: int, reason: str
) -> FlaskResponse:
    """Send (or resend) the email-validation link for an unverified user.

    Bypasses all rate limits: creates a fresh ``Email_Validations`` row when
    absent, or resets an existing one (``reset_attempts()``, fresh token) without
    incrementing attempt counters. Sends the confirmation email exactly the same
    way the splash resend path does (``send_account_email_confirmation``). If the
    email send returns a status >= 500 the session is rolled back and a 502 error
    is returned — no DB changes are committed.

    Idempotent on the already-validated side: if the user is already
    ``email_validated``, returns a clear no-op 200 with no audit row.

    On email success: audits EMAIL_RESEND and commits everything atomically.

    Args:
        actor_id:       ID of the admin performing the action.
        target_user_id: Primary key of the user whose verification email to resend.
        reason:         Required human-readable reason recorded in the audit log.

    Returns:
        200 JSON envelope on success or already-verified no-op.
        403 when actor targets themselves.
        404 when the target user does not exist.
        502 when the verification email fails to send (changes rolled back).
    """
    self_action_error: FlaskResponse | None = reject_self_action(
        actor_id=actor_id, target_user_id=target_user_id
    )
    if self_action_error is not None:
        return self_action_error

    target_user: Users | None = Users.query.get(target_user_id)
    if target_user is None:
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.MOD_TARGET_NOT_FOUND,
            error_code=AdminActionErrorCodes.TARGET_NOT_FOUND,
            status_code=404,
        )

    if target_user.email_validated:
        return AdminActionResponseSchema(
            status=STD_JSON.SUCCESS,
            message=ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_RESEND_ALREADY_VERIFIED,
        ).to_response()

    # Create or refresh the Email_Validations row, bypassing all rate limits.
    existing_email_validation: Email_Validations | None = target_user.email_confirm
    if existing_email_validation is not None:
        existing_email_validation.reset_attempts()
        existing_email_validation.validation_token = (
            target_user.get_email_validation_token()
        )
        email_validation_row: Email_Validations = existing_email_validation
    else:
        fresh_token: str = target_user.get_email_validation_token()
        email_validation_row = Email_Validations(validation_token=fresh_token)
        target_user.email_confirm = email_validation_row
        db.session.add(email_validation_row)

    # Flush so the Email_Validations row gets an ID if new, before building the URL.
    db.session.flush()

    confirmation_url: str = url_for(
        ROUTES.SPLASH.VALIDATE_EMAIL,
        token=email_validation_row.validation_token,
        _external=True,
    )
    email_sender = safe_get_email_sender(current_app)
    email_send_result = email_sender.send_account_email_confirmation(
        target_user.email,
        target_user.username,
        confirmation_url,
    )

    if email_send_result.status_code >= 500:
        db.session.rollback()
        return build_message_error_response(
            message=ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_RESEND_FAILURE,
            error_code=AdminActionErrorCodes.EMAIL_SEND_FAILURE,
            status_code=502,
        )

    audit.record(
        actor_id=actor_id,
        action=ADMIN_AUDIT_ACTIONS.EMAIL_RESEND,
        target_type="User",
        target_id=str(target_user_id),
        metadata={"reason": reason},
    )
    db.session.commit()
    return AdminActionResponseSchema(
        status=STD_JSON.SUCCESS,
        message=ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_RESEND_SUCCESS,
    ).to_response()
