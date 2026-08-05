"""Integration tests for the guard-free self-service account-removal core.

Exercises the shared state-mutation core extracted in the account-removal build
— it carries no HTTP/guard/audit/commit concerns, so these tests call it
directly inside an app context and own the commit themselves:

    backend.admin.account_data_service.erase_user_core

The erasure membership matrix mirrors
``tests/integration/admin/test_admin_account_data_actions.py`` so both the admin
caller and the self-service caller are proven against the same core behavior.
"""

from __future__ import annotations

import pytest
from flask import Flask

from backend import db
from backend.admin.account_data_service import (
    TOMBSTONE_EMAIL_DOMAIN,
    TOMBSTONE_USERNAME_PREFIX,
    ErasureCounts,
    erase_user_core,
    is_tombstoned,
)
from backend.api_v1.services.tokens import issue_refresh_token
from backend.models.api_refresh_tokens import ApiRefreshTokens
from backend.models.contact_form_entries import ContactFormEntries
from backend.models.email_validations import Email_Validations
from backend.models.forgot_passwords import Forgot_Passwords
from backend.models.user_oauth_identities import UserOAuthIdentity
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs

pytestmark = pytest.mark.account_and_support

_TARGET_PLAINTEXT_PASSWORD: str = "TestPass1!"


# ---------------------------------------------------------------------------
# Seed helpers (self-contained; mirror the admin erase suite's helpers)
# ---------------------------------------------------------------------------


def _seed_user(app: Flask, *, username: str, email: str) -> Users:
    """Create a non-admin email-validated user with a local password."""
    with app.app_context():
        user = Users(
            username=username,
            email=email,
            plaintext_password=_TARGET_PLAINTEXT_PASSWORD,
        )
        user.email_validated = True
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        return user


def _seed_solo_utub(app: Flask, creator: Users) -> Utubs:
    """Create a UTub whose only member is ``creator``."""
    with app.app_context():
        new_utub = Utubs(name="SoloUTub", utub_creator=creator.id, utub_description="")
        db.session.add(new_utub)
        db.session.flush()
        db.session.add(
            Utub_Members(
                utub_id=new_utub.id,
                user_id=creator.id,
                member_role=Member_Role.CREATOR,
            )
        )
        db.session.commit()
        db.session.refresh(new_utub)
        return new_utub


def _seed_contact_entry(app: Flask, owner: Users) -> ContactFormEntries:
    with app.app_context():
        entry = ContactFormEntries(
            subject="Test contact",
            content="Test content body",
            user_agent="Mozilla/5.0 (test)",
        )
        entry.user_id = owner.id
        db.session.add(entry)
        db.session.commit()
        db.session.refresh(entry)
        return entry


def _seed_refresh_token(app: Flask, owner: Users) -> ApiRefreshTokens:
    with app.app_context():
        owner_refreshed: Users = Users.query.get(owner.id)
        issue_refresh_token(user=owner_refreshed)
        token_row: ApiRefreshTokens = ApiRefreshTokens.query.filter_by(
            user_id=owner.id
        ).first()
        db.session.refresh(token_row)
        return token_row


# ---------------------------------------------------------------------------
# erase_user_core — membership matrix
# ---------------------------------------------------------------------------


def test_erase_core_solo_utub_deleted(app: Flask) -> None:
    """A solo UTub is hard-deleted; counts report one deletion, no transfer."""
    target = _seed_user(app, username="core_solo", email="core_solo@test.com")
    solo_utub = _seed_solo_utub(app, target)
    solo_utub_id: int = solo_utub.id
    target_id: int = target.id

    with app.app_context():
        target_refreshed: Users = Users.query.get(target_id)
        counts: ErasureCounts = erase_user_core(target_user=target_refreshed)
        db.session.commit()

    assert counts.utubs_deleted == 1
    assert counts.ownerships_transferred == 0
    assert counts.memberships_removed == 0

    with app.app_context():
        assert Utubs.query.get(solo_utub_id) is None
        refreshed: Users = Users.query.get(target_id)
        assert is_tombstoned(user=refreshed)


def test_erase_core_ownership_transferred(app: Flask) -> None:
    """A created UTub with other members transfers ownership to the lowest-id
    co-creator, and the erased user's membership row is removed."""
    target = _seed_user(app, username="core_owner", email="core_owner@test.com")
    other = _seed_user(app, username="core_other", email="core_other@test.com")
    target_id: int = target.id
    other_id: int = other.id

    with app.app_context():
        new_utub = Utubs(
            name="TransferUTub", utub_creator=target_id, utub_description=""
        )
        db.session.add(new_utub)
        db.session.flush()
        db.session.add_all(
            [
                Utub_Members(
                    utub_id=new_utub.id,
                    user_id=target_id,
                    member_role=Member_Role.CREATOR,
                ),
                Utub_Members(
                    utub_id=new_utub.id,
                    user_id=other_id,
                    member_role=Member_Role.CO_CREATOR,
                ),
            ]
        )
        db.session.commit()
        utub_id: int = new_utub.id

    with app.app_context():
        target_refreshed: Users = Users.query.get(target_id)
        counts: ErasureCounts = erase_user_core(target_user=target_refreshed)
        db.session.commit()

    assert counts.ownerships_transferred == 1
    assert counts.memberships_removed == 1
    assert counts.utubs_deleted == 0

    with app.app_context():
        utub_after: Utubs = Utubs.query.get(utub_id)
        assert utub_after is not None
        assert utub_after.utub_creator == other_id
        promoted: Utub_Members | None = Utub_Members.query.filter_by(
            utub_id=utub_id, user_id=other_id
        ).first()
        assert promoted is not None
        assert promoted.member_role == Member_Role.CREATOR
        assert (
            Utub_Members.query.filter_by(utub_id=utub_id, user_id=target_id).first()
            is None
        )


def test_erase_core_non_creator_membership_removed(app: Flask) -> None:
    """A non-creator membership row is removed; the UTub and its creator stay."""
    target = _seed_user(app, username="core_member", email="core_member@test.com")
    other = _seed_user(app, username="core_creator", email="core_creator@test.com")
    target_id: int = target.id
    other_id: int = other.id

    with app.app_context():
        non_creator_utub = Utubs(
            name="OtherOwnerUTub", utub_creator=other_id, utub_description=""
        )
        db.session.add(non_creator_utub)
        db.session.flush()
        db.session.add_all(
            [
                Utub_Members(
                    utub_id=non_creator_utub.id,
                    user_id=other_id,
                    member_role=Member_Role.CREATOR,
                ),
                Utub_Members(
                    utub_id=non_creator_utub.id,
                    user_id=target_id,
                    member_role=Member_Role.MEMBER,
                ),
            ]
        )
        db.session.commit()
        utub_id: int = non_creator_utub.id

    with app.app_context():
        target_refreshed: Users = Users.query.get(target_id)
        counts: ErasureCounts = erase_user_core(target_user=target_refreshed)
        db.session.commit()

    assert counts.memberships_removed == 1
    assert counts.utubs_deleted == 0
    assert counts.ownerships_transferred == 0

    with app.app_context():
        utub_after: Utubs = Utubs.query.get(utub_id)
        assert utub_after is not None
        assert utub_after.utub_creator == other_id
        assert (
            Utub_Members.query.filter_by(utub_id=utub_id, user_id=target_id).first()
            is None
        )


def test_erase_core_child_rows_deleted_and_tokens_revoked(app: Flask) -> None:
    """Every PII child row is deleted and the refresh token is revoked; the
    returned counts report the contact entry and token tallies."""
    target = _seed_user(app, username="core_child", email="core_child@test.com")
    target_id: int = target.id
    contact_entry = _seed_contact_entry(app, target)
    refresh_token = _seed_refresh_token(app, target)
    contact_entry_id: int = contact_entry.id
    refresh_token_id: int = refresh_token.id

    with app.app_context():
        target_refreshed: Users = Users.query.get(target_id)
        # Email-validation, forgot-password, and OAuth-identity child rows.
        ev_row = Email_Validations(
            validation_token=target_refreshed.get_email_validation_token()
        )
        target_refreshed.email_confirm = ev_row
        db.session.add(ev_row)
        fp_row = Forgot_Passwords(
            reset_token=target_refreshed.get_password_reset_token()
        )
        target_refreshed.forgot_password = fp_row
        db.session.add(fp_row)
        target_refreshed.oauth_identities.append(
            UserOAuthIdentity(provider="google", provider_subject="core-child-sub")
        )
        db.session.commit()

    with app.app_context():
        target_refreshed = Users.query.get(target_id)
        counts: ErasureCounts = erase_user_core(target_user=target_refreshed)
        db.session.commit()

    assert counts.contact_entries_deleted == 1
    assert counts.api_tokens_revoked == 1

    with app.app_context():
        assert Email_Validations.query.filter_by(user_id=target_id).first() is None
        assert Forgot_Passwords.query.filter_by(user_id=target_id).first() is None
        assert UserOAuthIdentity.query.filter_by(user_id=target_id).first() is None
        assert ContactFormEntries.query.filter_by(id=contact_entry_id).first() is None
        revoked_token: ApiRefreshTokens = ApiRefreshTokens.query.get(refresh_token_id)
        assert revoked_token.revoked_at is not None


def test_erase_core_tombstones_identity_and_nulls_pending_email(app: Flask) -> None:
    """The Users row is anonymized in place — including the pending_email
    address, which the pre-refactor admin path missed (FLAG from research)."""
    target = _seed_user(app, username="core_tomb", email="core_tomb@test.com")
    target_id: int = target.id

    with app.app_context():
        target_refreshed: Users = Users.query.get(target_id)
        target_refreshed.pending_email = "pending-change@test.com"
        db.session.commit()

    with app.app_context():
        target_refreshed = Users.query.get(target_id)
        erase_user_core(target_user=target_refreshed)
        db.session.commit()

    with app.app_context():
        refreshed: Users = Users.query.get(target_id)
        assert refreshed.username == f"{TOMBSTONE_USERNAME_PREFIX}{target_id}"
        assert refreshed.email == (
            f"{TOMBSTONE_USERNAME_PREFIX}{target_id}@{TOMBSTONE_EMAIL_DOMAIN}"
        )
        assert refreshed.password is None
        assert refreshed.email_validated is False
        assert refreshed.pending_email is None
        assert refreshed.sessions_invalidated_at is not None
