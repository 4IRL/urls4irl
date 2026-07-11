"""Integration tests for admin account-data POST endpoints.

Covered endpoints:
    POST /admin/users/<int:target_user_id>/erase
    POST /admin/users/<int:target_user_id>/oauth/<int:identity_id>/unlink
    POST /admin/users/<int:target_user_id>/email/verify
    POST /admin/users/<int:target_user_id>/email/resend
"""

from __future__ import annotations

from typing import Tuple

import pytest
from flask import Flask
from flask.testing import FlaskClient
from requests import Response

from backend import db
from backend.admin.account_data_service import (
    TOMBSTONE_EMAIL_DOMAIN,
    TOMBSTONE_USERNAME_PREFIX,
)
from backend.admin.constants import AdminActionErrorCodes
from backend.api_v1.services.tokens import issue_refresh_token
from backend.extensions.email_sender.email_sender import EmailSender
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.audit_log import AuditLog
from backend.models.contact_form_entries import ContactFormEntries
from backend.models.email_validations import Email_Validations
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.admin

_MOCK_REASON: str = "integration test account data"
_OVERLONG_REASON: str = "x" * 501
_WHITESPACE_ONLY_REASON: str = "   "

_ERASE_URL: str = "/admin/users/{target_user_id}/erase"
_OAUTH_UNLINK_URL: str = "/admin/users/{target_user_id}/oauth/{identity_id}/unlink"
_EMAIL_VERIFY_URL: str = "/admin/users/{target_user_id}/email/verify"
_EMAIL_RESEND_URL: str = "/admin/users/{target_user_id}/email/resend"

_MOCK_PROVIDER: str = "google"
_MOCK_PROVIDER_SUBJECT: str = "google-sub-12345"
_TARGET_PLAINTEXT_PASSWORD: str = "TestPass1!"

# Representative URLs (non-existent target) for parametrized auth/reason guard tests.
_ALL_ACCOUNT_DATA_URLS: list[str] = [
    _ERASE_URL.format(target_user_id=9999),
    _OAUTH_UNLINK_URL.format(target_user_id=9999, identity_id=9999),
    _EMAIL_VERIFY_URL.format(target_user_id=9999),
    _EMAIL_RESEND_URL.format(target_user_id=9999),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_account(
    client: FlaskClient,
    url: str,
    csrf: str,
    reason: str | None = _MOCK_REASON,
) -> object:
    """POST an account-data endpoint with an optional reason payload."""
    payload: dict = {}
    if reason is not None:
        payload["reason"] = reason
    return client.post(url, json=payload, headers={"X-CSRFToken": csrf})


def _seed_target_user_with_password(app: Flask) -> Users:
    """Create a non-admin email-validated user with a local password."""
    with app.app_context():
        target = Users(
            username="data_target_user",
            email="data_target@test.com",
            plaintext_password=_TARGET_PLAINTEXT_PASSWORD,
        )
        target.email_validated = True
        db.session.add(target)
        db.session.commit()
        db.session.refresh(target)
        return target


def _seed_unvalidated_user(app: Flask) -> Users:
    """Create a non-admin user whose email is NOT validated."""
    with app.app_context():
        target = Users(
            username="unvalidated_target",
            email="unvalidated_target@test.com",
            plaintext_password=_TARGET_PLAINTEXT_PASSWORD,
        )
        target.email_validated = False
        db.session.add(target)
        db.session.commit()
        db.session.refresh(target)
        return target


def _seed_oauth_identity(
    app: Flask,
    target_user: Users,
    *,
    provider: str = _MOCK_PROVIDER,
    provider_subject: str = _MOCK_PROVIDER_SUBJECT,
) -> UserOAuthIdentity:
    """Attach one OAuth identity to target_user and return the row."""
    with app.app_context():
        identity = UserOAuthIdentity(
            provider=provider,
            provider_subject=provider_subject,
        )
        target_refreshed: Users = Users.query.get(target_user.id)
        target_refreshed.oauth_identities.append(identity)
        db.session.commit()
        db.session.refresh(identity)
        return identity


def _seed_email_validation_row(app: Flask, target_user: Users) -> Email_Validations:
    """Create an Email_Validations row for target_user and return it."""
    with app.app_context():
        target_refreshed: Users = Users.query.get(target_user.id)
        fresh_token: str = target_refreshed.get_email_validation_token()
        ev_row = Email_Validations(validation_token=fresh_token)
        target_refreshed.email_confirm = ev_row
        db.session.add(ev_row)
        db.session.commit()
        db.session.refresh(ev_row)
        return ev_row


def _seed_contact_entry(app: Flask, target_user: Users) -> ContactFormEntries:
    """Seed a ContactFormEntries row owned by target_user."""
    with app.app_context():
        entry = ContactFormEntries(
            subject="Test contact",
            content="Test content body",
            user_agent="Mozilla/5.0 (test)",
        )
        entry.user_id = target_user.id
        db.session.add(entry)
        db.session.commit()
        db.session.refresh(entry)
        return entry


def _seed_utub_with_target_as_sole_member(app: Flask, target_user: Users) -> Utubs:
    """Create a UTub with target_user as the only member (creator)."""
    with app.app_context():
        new_utub = Utubs(
            name="SoleUTub",
            utub_creator=target_user.id,
            utub_description="",
        )
        db.session.add(new_utub)
        db.session.flush()
        utub_member = Utub_Members(
            utub_id=new_utub.id,
            user_id=target_user.id,
            member_role=Member_Role.CREATOR,
        )
        db.session.add(utub_member)
        db.session.commit()
        db.session.refresh(new_utub)
        return new_utub


def _seed_second_regular_user(app: Flask) -> Users:
    """Create a second non-admin email-validated user."""
    with app.app_context():
        other = Users(
            username="other_regular_user",
            email="other_regular@test.com",
            plaintext_password="TestPass1!",
        )
        other.email_validated = True
        db.session.add(other)
        db.session.commit()
        db.session.refresh(other)
        return other


def _seed_refresh_token(app: Flask, target_user: Users) -> ApiRefreshTokens:
    """Issue one unrevoked refresh token for target_user."""
    with app.app_context():
        target_refreshed: Users = Users.query.get(target_user.id)
        issue_refresh_token(user=target_refreshed)
        token_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=target_user.id
        ).first()
        db.session.refresh(token_row)
        return token_row


# ---------------------------------------------------------------------------
# ERASURE: happy path — solo UTub case
# ---------------------------------------------------------------------------


def test_admin_erase_user_solo_utub_deleted(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target user who is the sole member of one UTub, has a ContactFormEntries
         row, has an OAuth identity, and has one unrevoked refresh token
    WHEN POST /admin/users/<id>/erase with a reason
    THEN 200 JSON success; username and email tombstoned; password None;
         email_validated False; sessions_invalidated_at set; refresh token revoked;
         UTub deleted (sole member); OAuth/email-validation/contact rows gone;
         one audit row with correct action, reason, and counters.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)
    solo_utub = _seed_utub_with_target_as_sole_member(app, target)
    contact_entry = _seed_contact_entry(app, target)
    refresh_token = _seed_refresh_token(app, target)
    oauth_identity = _seed_oauth_identity(app, target)
    _seed_email_validation_row(app, target)

    # Capture primary-key integers before any erase so assertions use plain ints
    # (avoids ObjectDeletedError when SQLAlchemy expunges deleted instances after
    # the SAVEPOINT restarts in the db_transaction fixture).
    contact_entry_id: int = contact_entry.id
    refresh_token_id: int = refresh_token.id
    oauth_identity_id: int = oauth_identity.id
    solo_utub_id: int = solo_utub.id

    with app.app_context():
        target_before: Users = Users.query.get(target.id)
        assert not target_before.username.startswith(TOMBSTONE_USERNAME_PREFIX)
        assert AuditLog.query.count() == 0
        assert Utubs.query.get(solo_utub_id) is not None

    response = _post_account(client, _ERASE_URL.format(target_user_id=target.id), csrf)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_ERASE_SUCCESS

    with app.app_context():
        refreshed: Users = Users.query.get(target.id)
        assert refreshed.username == f"{TOMBSTONE_USERNAME_PREFIX}{target.id}"
        assert refreshed.email == (
            f"{TOMBSTONE_USERNAME_PREFIX}{target.id}@{TOMBSTONE_EMAIL_DOMAIN}"
        )
        assert refreshed.password is None
        assert refreshed.email_validated is False
        assert refreshed.sessions_invalidated_at is not None

        assert Utubs.query.get(solo_utub_id) is None
        assert UserOAuthIdentity.query.get(oauth_identity_id) is None
        assert Email_Validations.query.filter_by(user_id=target.id).first() is None
        assert ContactFormEntries.query.filter_by(id=contact_entry_id).first() is None

        revoked_token: ApiRefreshTokens = ApiRefreshTokens.query.get(refresh_token_id)
        assert revoked_token.revoked_at is not None

        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.USER_ERASE
    assert audit_row.actor_id == admin_user.id
    assert audit_row.target_id == str(target.id)
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON
    assert audit_row.log_metadata.get("utubs_deleted") == 1
    assert audit_row.log_metadata.get("ownerships_transferred") == 0
    assert audit_row.log_metadata.get("memberships_removed") == 0


# ---------------------------------------------------------------------------
# ERASURE: created UTub with other members — ownership transfer
# ---------------------------------------------------------------------------


def test_admin_erase_user_created_utub_ownership_transferred(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target who created a UTub with another member (CO_CREATOR)
    WHEN POST /admin/users/<id>/erase
    THEN 200; UTub survives; utub_creator set to the lowest-id CO_CREATOR;
         target membership gone; audit metadata ownerships_transferred=1.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)
    other_user = _seed_second_regular_user(app)

    with app.app_context():
        new_utub = Utubs(
            name="TransferUTub",
            utub_creator=target.id,
            utub_description="",
        )
        db.session.add(new_utub)
        db.session.flush()
        creator_member = Utub_Members(
            utub_id=new_utub.id,
            user_id=target.id,
            member_role=Member_Role.CREATOR,
        )
        co_creator_member = Utub_Members(
            utub_id=new_utub.id,
            user_id=other_user.id,
            member_role=Member_Role.CO_CREATOR,
        )
        db.session.add_all([creator_member, co_creator_member])
        db.session.commit()
        utub_id: int = new_utub.id

    with app.app_context():
        assert Utubs.query.get(utub_id).utub_creator == target.id

    response = _post_account(client, _ERASE_URL.format(target_user_id=target.id), csrf)

    assert response.status_code == 200

    with app.app_context():
        utub_after: Utubs = Utubs.query.get(utub_id)
        assert utub_after is not None
        assert utub_after.utub_creator == other_user.id

        transferred_member: Utub_Members | None = Utub_Members.query.filter_by(
            utub_id=utub_id, user_id=other_user.id
        ).first()
        assert transferred_member is not None
        assert transferred_member.member_role == Member_Role.CREATOR

        target_membership: Utub_Members | None = Utub_Members.query.filter_by(
            utub_id=utub_id, user_id=target.id
        ).first()
        assert target_membership is None

        audit_row: AuditLog | None = AuditLog.query.filter_by(
            action=ADMIN_AUDIT_ACTIONS.USER_ERASE
        ).first()
    assert audit_row is not None
    assert audit_row.log_metadata.get("ownerships_transferred") == 1
    assert audit_row.log_metadata.get("memberships_removed") == 1


# ---------------------------------------------------------------------------
# ERASURE: non-creator membership — membership row removed, UTub survives
# ---------------------------------------------------------------------------


def test_admin_erase_user_non_creator_membership_removed(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target who is a plain MEMBER (not creator) of another user's UTub
    WHEN POST /admin/users/<id>/erase
    THEN 200; target membership row gone; UTub and its creator untouched;
         audit metadata memberships_removed=1, utubs_deleted=0, ownerships_transferred=0.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)
    other_user = _seed_second_regular_user(app)

    with app.app_context():
        non_creator_utub = Utubs(
            name="OtherOwnerUTub",
            utub_creator=other_user.id,
            utub_description="",
        )
        db.session.add(non_creator_utub)
        db.session.flush()
        owner_member = Utub_Members(
            utub_id=non_creator_utub.id,
            user_id=other_user.id,
            member_role=Member_Role.CREATOR,
        )
        target_member = Utub_Members(
            utub_id=non_creator_utub.id,
            user_id=target.id,
            member_role=Member_Role.MEMBER,
        )
        db.session.add_all([owner_member, target_member])
        db.session.commit()
        utub_id: int = non_creator_utub.id

    with app.app_context():
        assert (
            Utub_Members.query.filter_by(utub_id=utub_id, user_id=target.id).first()
            is not None
        )

    response = _post_account(client, _ERASE_URL.format(target_user_id=target.id), csrf)

    assert response.status_code == 200

    with app.app_context():
        utub_after: Utubs = Utubs.query.get(utub_id)
        assert utub_after is not None
        assert utub_after.utub_creator == other_user.id

        target_membership: Utub_Members | None = Utub_Members.query.filter_by(
            utub_id=utub_id, user_id=target.id
        ).first()
        assert target_membership is None

        audit_row: AuditLog | None = AuditLog.query.filter_by(
            action=ADMIN_AUDIT_ACTIONS.USER_ERASE
        ).first()
    assert audit_row is not None
    assert audit_row.log_metadata.get("memberships_removed") == 1
    assert audit_row.log_metadata.get("utubs_deleted") == 0
    assert audit_row.log_metadata.get("ownerships_transferred") == 0


# ---------------------------------------------------------------------------
# ERASURE: idempotent — second erase is a no-op
# ---------------------------------------------------------------------------


def test_admin_erase_user_idempotent_noop(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an already-erased user (tombstoned)
    WHEN POST /admin/users/<id>/erase a second time
    THEN 200 no-op message; exactly one audit row from the first erase only.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)

    first_response = _post_account(
        client, _ERASE_URL.format(target_user_id=target.id), csrf
    )
    assert first_response.status_code == 200

    with app.app_context():
        assert AuditLog.query.count() == 1

    second_response = _post_account(
        client, _ERASE_URL.format(target_user_id=target.id), csrf
    )

    assert second_response.status_code == 200
    body = second_response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_ERASE_NOOP

    with app.app_context():
        assert AuditLog.query.count() == 1


# ---------------------------------------------------------------------------
# ERASURE: erased user cannot log in with old credentials
# ---------------------------------------------------------------------------


def test_admin_erase_user_tombstone_blocks_login(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target whose original username is known
    WHEN the target is erased
    THEN the original username no longer resolves to a Users row
         (tombstoned to ``deleted-user-<id>``), proving that any login attempt
         using the old username fails at the initial user-lookup stage —
         ``login_user_to_u4i`` returns the USER_NOT_EXIST error path.

    Note: attempting to drive this via an HTTP POST /login from within the
    same test function is unreliable because the ``login_admin_user_with_register``
    fixture's preserved request context leaks ``g._login_user`` into any client
    created in the same test, causing the splash-page CSRF GET to redirect rather
    than render. Asserting the tombstone-lookup constraint directly is both
    simpler and equally definitive.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)
    original_username: str = target.username

    erase_response = _post_account(
        client, _ERASE_URL.format(target_user_id=target.id), csrf
    )
    assert erase_response.status_code == 200

    # After erasure the username is tombstoned; the old username no longer
    # exists in the Users table, so login_user_to_u4i returns USER_NOT_EXIST.
    with app.app_context():
        looked_up_user: Users | None = Users.query.filter(
            Users.username == original_username
        ).first()
    assert looked_up_user is None


# ---------------------------------------------------------------------------
# ERASURE: self-action returns 403
# ---------------------------------------------------------------------------


def test_admin_erase_user_self_action_returns_403(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin
    WHEN POST /admin/users/<own-id>/erase
    THEN 403 with SELF_ACTION_FORBIDDEN; no audit row.
    """
    client, csrf, admin_user, app = login_admin_user_with_register

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = _post_account(
        client, _ERASE_URL.format(target_user_id=admin_user.id), csrf
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.SELF_ACTION_FORBIDDEN

    with app.app_context():
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# UNLINK: happy path — user has a password, identity deleted
# ---------------------------------------------------------------------------


def test_admin_oauth_unlink_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target with a local password and one OAuth identity
    WHEN POST /admin/users/<id>/oauth/<identity_id>/unlink with a reason
    THEN 200 JSON success; identity row deleted; audit row OAUTH_UNLINK with provider.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)
    identity = _seed_oauth_identity(app, target)

    with app.app_context():
        assert UserOAuthIdentity.query.get(identity.id) is not None
        assert AuditLog.query.count() == 0

    response = _post_account(
        client,
        _OAUTH_UNLINK_URL.format(target_user_id=target.id, identity_id=identity.id),
        csrf,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_UNLINK_SUCCESS.format(
        provider=_MOCK_PROVIDER
    )

    with app.app_context():
        assert UserOAuthIdentity.query.get(identity.id) is None

        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.OAUTH_UNLINK
    assert audit_row.actor_id == admin_user.id
    assert audit_row.target_id == str(target.id)
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("provider") == _MOCK_PROVIDER
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


# ---------------------------------------------------------------------------
# UNLINK: last-credential guard — 403 when no password and only one identity
# ---------------------------------------------------------------------------


def test_admin_oauth_unlink_last_credential_returns_403(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target with password=None and exactly one OAuth identity
    WHEN POST /admin/users/<id>/oauth/<identity_id>/unlink
    THEN 403 with LAST_CREDENTIAL_FORBIDDEN; identity row survives; no audit row.
    """
    client, csrf, _, app = login_admin_user_with_register

    with app.app_context():
        oauth_only = Users(
            username="oauth_only_target",
            email="oauth_only_target@test.com",
            plaintext_password=None,
        )
        oauth_only.email_validated = True
        db.session.add(oauth_only)
        db.session.commit()
        oauth_only_id: int = oauth_only.id

        real_identity = UserOAuthIdentity(
            provider=_MOCK_PROVIDER,
            provider_subject="last-cred-sub",
        )
        refreshed_oauth_only: Users = Users.query.get(oauth_only_id)
        refreshed_oauth_only.oauth_identities.append(real_identity)
        db.session.commit()
        db.session.refresh(real_identity)
        identity_id: int = real_identity.id

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = _post_account(
        client,
        _OAUTH_UNLINK_URL.format(target_user_id=oauth_only_id, identity_id=identity_id),
        csrf,
    )

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_UNLINK_LAST_CREDENTIAL
    assert body[STD_JSON.ERROR_CODE] == int(
        AdminActionErrorCodes.LAST_CREDENTIAL_FORBIDDEN
    )

    with app.app_context():
        assert UserOAuthIdentity.query.get(identity_id) is not None
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# UNLINK: no-password but TWO identities — unlink succeeds (one remains)
# ---------------------------------------------------------------------------


def test_admin_oauth_unlink_two_identities_no_password_succeeds(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target with password=None and TWO OAuth identities
    WHEN POST /admin/users/<id>/oauth/<first_identity_id>/unlink
    THEN 200 success; first identity deleted; second identity survives; audit row written.
    """
    client, csrf, _, app = login_admin_user_with_register

    with app.app_context():
        oauth_user = Users(
            username="oauth_two_ids",
            email="oauth_two_ids@test.com",
            plaintext_password=None,
        )
        oauth_user.email_validated = True
        db.session.add(oauth_user)
        db.session.commit()
        oauth_user_id: int = oauth_user.id

        identity_one = UserOAuthIdentity(
            provider="google",
            provider_subject="google-two-ids-sub-1",
        )
        identity_two = UserOAuthIdentity(
            provider="github",
            provider_subject="github-two-ids-sub-2",
        )
        refreshed_oauth_user: Users = Users.query.get(oauth_user_id)
        refreshed_oauth_user.oauth_identities.extend([identity_one, identity_two])
        db.session.commit()
        db.session.refresh(identity_one)
        db.session.refresh(identity_two)
        identity_one_id: int = identity_one.id
        identity_two_id: int = identity_two.id

    response = _post_account(
        client,
        _OAUTH_UNLINK_URL.format(
            target_user_id=oauth_user_id, identity_id=identity_one_id
        ),
        csrf,
    )

    assert response.status_code == 200

    with app.app_context():
        assert UserOAuthIdentity.query.get(identity_one_id) is None
        assert UserOAuthIdentity.query.get(identity_two_id) is not None
        assert AuditLog.query.count() == 1


# ---------------------------------------------------------------------------
# UNLINK: identity belongs to a different user — 404
# ---------------------------------------------------------------------------


def test_admin_oauth_unlink_wrong_user_identity_returns_404(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a target user and an OAuth identity belonging to a DIFFERENT user
    WHEN POST /admin/users/<target_id>/oauth/<other_user_identity_id>/unlink
    THEN 404; identity survives; no audit row.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)
    other_user = _seed_second_regular_user(app)
    other_identity = _seed_oauth_identity(
        app,
        other_user,
        provider="github",
        provider_subject="github-other-sub",
    )

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = _post_account(
        client,
        _OAUTH_UNLINK_URL.format(
            target_user_id=target.id, identity_id=other_identity.id
        ),
        csrf,
    )

    assert response.status_code == 404

    with app.app_context():
        assert UserOAuthIdentity.query.get(other_identity.id) is not None
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# EMAIL VERIFY: happy path — unvalidated user with Email_Validations row
# ---------------------------------------------------------------------------


def test_admin_email_verify_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an unvalidated target with an Email_Validations row
    WHEN POST /admin/users/<id>/email/verify with a reason
    THEN 200 JSON success; email_validated=True; Email_Validations row deleted;
         one audit row EMAIL_VERIFY with reason.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    target = _seed_unvalidated_user(app)
    _seed_email_validation_row(app, target)

    with app.app_context():
        target_before: Users = Users.query.get(target.id)
        assert not target_before.email_validated
        assert Email_Validations.query.filter_by(user_id=target.id).first() is not None
        assert AuditLog.query.count() == 0

    response = _post_account(
        client, _EMAIL_VERIFY_URL.format(target_user_id=target.id), csrf
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_VERIFY_SUCCESS

    with app.app_context():
        refreshed: Users = Users.query.get(target.id)
        assert refreshed.email_validated is True
        assert Email_Validations.query.filter_by(user_id=target.id).first() is None

        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.EMAIL_VERIFY
    assert audit_row.actor_id == admin_user.id
    assert audit_row.target_id == str(target.id)
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


# ---------------------------------------------------------------------------
# EMAIL VERIFY: idempotent — already verified, no audit row
# ---------------------------------------------------------------------------


def test_admin_email_verify_already_verified_noop(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a user whose email is already validated
    WHEN POST /admin/users/<id>/email/verify
    THEN 200 no-op message; no audit row written; email_validated remains True.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)

    with app.app_context():
        assert Users.query.get(target.id).email_validated is True
        assert AuditLog.query.count() == 0

    response = _post_account(
        client, _EMAIL_VERIFY_URL.format(target_user_id=target.id), csrf
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_VERIFY_NOOP

    with app.app_context():
        assert AuditLog.query.count() == 0
        assert Users.query.get(target.id).email_validated is True


# ---------------------------------------------------------------------------
# EMAIL RESEND: happy path
# ---------------------------------------------------------------------------


def test_admin_email_resend_happy_path(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an unvalidated target with an Email_Validations row at the attempt cap
    WHEN POST /admin/users/<id>/email/resend with a reason
    THEN 200 JSON success; Email_Validations row refreshed (attempts reset, new token);
         one audit row EMAIL_RESEND.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    target = _seed_unvalidated_user(app)
    _seed_email_validation_row(app, target)

    with app.app_context():
        # Bump attempts to the cap to prove bypass works.
        refreshed_ev: Email_Validations = Email_Validations.query.filter_by(
            user_id=target.id
        ).first()
        old_token: str = refreshed_ev.validation_token
        refreshed_ev.attempts = 5
        db.session.commit()

    with app.app_context():
        assert Email_Validations.query.filter_by(user_id=target.id).first() is not None
        assert AuditLog.query.count() == 0

    response = _post_account(
        client, _EMAIL_RESEND_URL.format(target_user_id=target.id), csrf
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_RESEND_SUCCESS

    with app.app_context():
        ev_after: Email_Validations | None = Email_Validations.query.filter_by(
            user_id=target.id
        ).first()
        assert ev_after is not None
        assert ev_after.attempts == 0
        assert ev_after.validation_token != old_token

        audit_row: AuditLog | None = AuditLog.query.first()
    assert audit_row is not None
    assert audit_row.action == ADMIN_AUDIT_ACTIONS.EMAIL_RESEND
    assert audit_row.actor_id == admin_user.id
    assert audit_row.target_id == str(target.id)
    assert audit_row.log_metadata is not None
    assert audit_row.log_metadata.get("reason") == _MOCK_REASON


# ---------------------------------------------------------------------------
# EMAIL RESEND: already-validated — no-op, no audit
# ---------------------------------------------------------------------------


def test_admin_email_resend_already_verified_noop(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a user whose email is already validated
    WHEN POST /admin/users/<id>/email/resend
    THEN 200 no-op message; no audit row written.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_target_user_with_password(app)

    with app.app_context():
        assert Users.query.get(target.id).email_validated is True
        assert AuditLog.query.count() == 0

    response = _post_account(
        client, _EMAIL_RESEND_URL.format(target_user_id=target.id), csrf
    )

    assert response.status_code == 200
    body = response.get_json()
    assert (
        body[STD_JSON.MESSAGE]
        == ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_RESEND_ALREADY_VERIFIED
    )

    with app.app_context():
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# EMAIL RESEND: email send failure — 502, rollback, no audit row
# ---------------------------------------------------------------------------


def test_admin_email_resend_email_failure_rollback(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN an unvalidated target and the email sender monkeypatched to return 500
    WHEN POST /admin/users/<id>/email/resend
    THEN 502 with EMAIL_SEND_FAILURE error code; no audit row; attempts/token unchanged.
    """
    client, csrf, _, app = login_admin_user_with_register
    target = _seed_unvalidated_user(app)
    _seed_email_validation_row(app, target)

    with app.app_context():
        ev_before: Email_Validations = Email_Validations.query.filter_by(
            user_id=target.id
        ).first()
        token_before: str = ev_before.validation_token
        attempts_before: int = ev_before.attempts

    failing_email_response = Response()
    failing_email_response.status_code = 500

    monkeypatch.setattr(
        EmailSender,
        "send_account_email_confirmation",
        lambda self, *args, **kwargs: failing_email_response,
    )

    response = _post_account(
        client, _EMAIL_RESEND_URL.format(target_user_id=target.id), csrf
    )

    assert response.status_code == 502
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.ACCOUNT_EMAIL_RESEND_FAILURE
    assert body[STD_JSON.ERROR_CODE] == int(AdminActionErrorCodes.EMAIL_SEND_FAILURE)

    with app.app_context():
        assert AuditLog.query.count() == 0
        ev_after: Email_Validations = Email_Validations.query.filter_by(
            user_id=target.id
        ).first()
        assert ev_after is not None
        assert ev_after.validation_token == token_before
        assert ev_after.attempts == attempts_before


# ---------------------------------------------------------------------------
# Self-action guard: erase, email verify, and email resend return 403
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url_template",
    [
        _ERASE_URL,
        _EMAIL_VERIFY_URL,
        _EMAIL_RESEND_URL,
    ],
)
def test_admin_account_data_self_action_returns_403(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    url_template: str,
) -> None:
    """
    GIVEN a logged-in admin
    WHEN POSTing any account-data endpoint targeting their own user ID
    THEN 403 with SELF_ACTION_FORBIDDEN; no audit row.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    url: str = url_template.format(target_user_id=admin_user.id)

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = _post_account(client, url, csrf)

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.SELF_ACTION_FORBIDDEN

    with app.app_context():
        assert AuditLog.query.count() == 0


def test_admin_oauth_unlink_self_action_returns_403(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in admin
    WHEN POSTing the OAuth unlink endpoint targeting their own user ID
    THEN 403 with SELF_ACTION_FORBIDDEN (the guard fires before any identity
         lookup, so the identity id does not need to exist); no audit row.
    """
    client, csrf, admin_user, app = login_admin_user_with_register
    unlink_url: str = _OAUTH_UNLINK_URL.format(
        target_user_id=admin_user.id, identity_id=99999
    )

    with app.app_context():
        assert AuditLog.query.count() == 0

    response = _post_account(client, unlink_url, csrf)

    assert response.status_code == 403
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert body[STD_JSON.MESSAGE] == ADMIN_ACTION_STRINGS.SELF_ACTION_FORBIDDEN

    with app.app_context():
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# 404 for unknown target user
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_DATA_URLS)
def test_admin_account_data_missing_target_returns_404(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in admin and a non-existent target user ID
    WHEN POSTing any account-data endpoint with that ID
    THEN 404; no audit row written.
    """
    client, csrf, _, app = login_admin_user_with_register

    response = _post_account(client, account_url, csrf)

    assert response.status_code == 404

    with app.app_context():
        assert AuditLog.query.count() == 0


# ---------------------------------------------------------------------------
# Required-reason validation: missing / whitespace / overlong
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_DATA_URLS)
def test_admin_account_data_missing_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in admin sending no reason field
    WHEN POSTing any account-data endpoint
    THEN 400 JSON (AdminReasonRequiredRequest rejects missing reason).
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_account(client, account_url, csrf, reason=None)

    assert response.status_code == 400


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_DATA_URLS)
def test_admin_account_data_whitespace_only_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in admin sending a whitespace-only reason
    WHEN POSTing any account-data endpoint
    THEN 400 JSON.
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_account(client, account_url, csrf, reason=_WHITESPACE_ONLY_REASON)

    assert response.status_code == 400


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_DATA_URLS)
def test_admin_account_data_overlong_reason_returns_400(
    login_admin_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in admin sending a 501-character reason
    WHEN POSTing any account-data endpoint
    THEN 400 JSON.
    """
    client, csrf, _, _ = login_admin_user_with_register

    response = _post_account(client, account_url, csrf, reason=_OVERLONG_REASON)

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Auth guard: non-admin returns 404, anonymous returns 401
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_DATA_URLS)
def test_admin_account_data_non_admin_returns_404(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    account_url: str,
) -> None:
    """
    GIVEN a logged-in non-admin user
    WHEN POSTing any account-data endpoint
    THEN 404 (admin_required hides the admin surface from non-admins).
    """
    client, csrf, _, _ = login_first_user_with_register

    response = _post_account(client, account_url, csrf)

    assert response.status_code == 404


@pytest.mark.parametrize("account_url", _ALL_ACCOUNT_DATA_URLS)
def test_admin_account_data_anonymous_returns_401(
    client: FlaskClient,
    account_url: str,
) -> None:
    """
    GIVEN an unauthenticated session
    WHEN POSTing any account-data endpoint with a valid CSRF token
    THEN 401 JSON.
    """
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.post(
        account_url,
        json={"reason": _MOCK_REASON},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 401
