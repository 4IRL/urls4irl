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

from typing import Any

import pytest
from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import Engine

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
from backend.models.user_preferences import User_Preferences
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from tests.utils_for_test import trash_utub

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


def test_erase_core_trashed_solo_utub_deleted(app: Flask) -> None:
    """A solo UTub that is already trashed is hard-deleted exactly like a live one."""
    target = _seed_user(app, username="core_tsolo", email="core_tsolo@test.com")
    solo_utub = _seed_solo_utub(app, target)
    solo_utub_id: int = solo_utub.id
    target_id: int = target.id
    trash_utub(app, solo_utub_id, deleted_by=target_id)

    with app.app_context():
        target_refreshed: Users = Users.query.get(target_id)
        counts: ErasureCounts = erase_user_core(target_user=target_refreshed)
        db.session.commit()

    assert counts.utubs_deleted == 1
    assert counts.ownerships_transferred == 0
    assert counts.memberships_removed == 0

    with app.app_context():
        assert Utubs.query.get(solo_utub_id) is None
        assert is_tombstoned(user=Users.query.get(target_id))


def test_erase_core_trashed_shared_utub_ownership_transferred(app: Flask) -> None:
    """A trashed UTub with other members transfers ownership to the lowest-id
    co-creator and drops the erased user's membership, exactly like a live one;
    the UTub stays trashed."""
    target = _seed_user(app, username="core_tshare", email="core_tshare@test.com")
    other = _seed_user(app, username="core_tother", email="core_tother@test.com")
    target_id: int = target.id
    other_id: int = other.id

    with app.app_context():
        new_utub = Utubs(
            name="TrashedTransferUTub", utub_creator=target_id, utub_description=""
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

    trash_utub(app, utub_id, deleted_by=target_id)

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
        assert utub_after.is_trashed
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


def test_erase_core_locks_utubs_in_ascending_id_order(app: Flask) -> None:
    """erase_user_core takes the per-UTub row lock in ascending id order.

    The erased user is a member of two UTubs whose ids collide so a plain
    ``set`` of the ids iterates the HIGHER id first (CPython hashes small ints
    to themselves; with 8 slots, id % 8 picks the slot). Dropping ``sorted``
    from the implementation therefore locks them in descending order and fails
    this test.
    """
    target = _seed_user(app, username="core_lockord", email="core_lockord@test.com")
    other = _seed_user(app, username="core_lockown", email="core_lockown@test.com")
    target_id: int = target.id
    other_id: int = other.id

    # Filler UTubs (owned by ``other``) with consecutive ids: 16 of them always
    # contain a pair lo < hi with hi % 8 < lo % 8, i.e. a descending set order.
    filler_ids: list[int] = []
    with app.app_context():
        for index in range(16):
            filler = Utubs(
                name=f"LockOrder{index}", utub_creator=other_id, utub_description=""
            )
            db.session.add(filler)
            db.session.flush()
            db.session.add(
                Utub_Members(
                    utub_id=filler.id,
                    user_id=other_id,
                    member_role=Member_Role.CREATOR,
                )
            )
            filler_ids.append(filler.id)
        db.session.commit()

    low_id, high_id = next(
        (low, high)
        for low in filler_ids
        for high in filler_ids
        if low < high and list({low, high}) == [high, low]
    )

    with app.app_context():
        for member_utub_id in (low_id, high_id):
            db.session.add(
                Utub_Members(
                    utub_id=member_utub_id,
                    user_id=target_id,
                    member_role=Member_Role.MEMBER,
                )
            )
        db.session.commit()

    locked_ids: list[int] = []

    def record_statement(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        normalized = " ".join(statement.split())
        if 'FROM "Utubs"' in normalized and "FOR NO KEY UPDATE" in normalized:
            locked_ids.append(next(iter(parameters.values())))

    with app.app_context():
        target_refreshed: Users = Users.query.get(target_id)
        # Class-level listener so it sees the session's connection whichever
        # way the test harness checked it out.
        event.listen(Engine, "before_cursor_execute", record_statement)
        try:
            erase_user_core(target_user=target_refreshed)
        finally:
            event.remove(Engine, "before_cursor_execute", record_statement)
        db.session.commit()

    assert list({low_id, high_id}) == [high_id, low_id]  # precondition
    assert locked_ids == [low_id, high_id]


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
        # Display-preferences child row: in-place tombstoning fires no DB cascade,
        # so erase_user_core must delete this explicitly (Design Decision 6).
        target_refreshed.preferences = User_Preferences(user_id=target_id)
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
        assert User_Preferences.query.filter_by(user_id=target_id).first() is None
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
