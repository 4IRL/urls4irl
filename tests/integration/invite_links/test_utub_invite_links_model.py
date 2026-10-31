"""Model-level tests for UtubInviteLinks: constraints, FK actions and defaults."""

from __future__ import annotations

import pytest
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.invite_links.constants import (
    INVITE_LINK_DEFAULT_TTL,
    ONE_ACTIVE_INVITE_LINK_PER_UTUB,
    UNIQUE_INVITE_LINK_TOKEN,
)
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now

pytestmark = pytest.mark.invite_links

TOKEN_A: str = "A" * 22
TOKEN_B: str = "B" * 22
TOKEN_C: str = "C" * 22


def _utubs() -> list[Utubs]:
    utubs = db.session.query(Utubs).order_by(Utubs.id).all()
    assert len(utubs) >= 2
    return utubs


def _first_user_id() -> int:
    user = db.session.query(Users).order_by(Users.id).first()
    assert user is not None
    return user.id


def _new_link(
    utub_id: int, token: str = TOKEN_A, created_by: int | None = None
) -> Utub_Invite_Links:
    return Utub_Invite_Links(
        utub_id=utub_id,
        token=token,
        created_by=created_by if created_by is not None else _first_user_id(),
        expires_at=utc_now() + INVITE_LINK_DEFAULT_TTL,
    )


def _add_link(
    utub_id: int,
    token: str = TOKEN_A,
    created_by: int | None = None,
    revoked: bool = False,
) -> int:
    link = _new_link(utub_id, token, created_by)
    if revoked:
        link.revoked_at = utc_now()
    db.session.add(link)
    db.session.commit()
    return link.id


def _add_pending_validation(user_id: int, invite_id: int | None) -> int:
    validation = Email_Validations(validation_token="pending-token")
    validation.user_id = user_id
    validation.pending_invite_id = invite_id
    db.session.add(validation)
    db.session.commit()
    return validation.id


def _make_disposable_user() -> int:
    user = Users(
        username="disposable_creator",
        email="disposable_creator@example.com",
        plaintext_password="disposable_creator1!",
    )
    db.session.add(user)
    db.session.commit()
    return user.id


def test_defaults(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN a new invite link with only the required fields
    WHEN it is committed
    THEN use_count is 0, max_uses and revoked_at are NULL, created_at is set
    """
    with app.app_context():
        link_id = _add_link(_utubs()[0].id)
        link = db.session.get(Utub_Invite_Links, link_id)
        assert link is not None
        assert link.use_count == 0
        assert link.max_uses is None
        assert link.revoked_at is None
        assert link.created_at is not None

        raw_use_count = db.session.execute(
            text('SELECT "useCount" FROM "UtubInviteLinks" WHERE id = :id'),
            {"id": link_id},
        ).scalar_one()
        assert raw_use_count == 0


def test_second_active_link_for_same_utub_rejected(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an unrevoked invite link on a UTub
    WHEN a second unrevoked link is added to the same UTub
    THEN an IntegrityError naming the one-active index is raised
    """
    with app.app_context():
        utub_id = _utubs()[0].id
        _add_link(utub_id, TOKEN_A)
        db.session.add(_new_link(utub_id, TOKEN_B))
        with pytest.raises(IntegrityError) as exc_info:
            db.session.commit()
        db.session.rollback()
        assert ONE_ACTIVE_INVITE_LINK_PER_UTUB in str(exc_info.value)


def test_revoked_links_do_not_block_new_active_link(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN two revoked links on one UTub
    WHEN a new active link is added, and another UTub gets its own active link
    THEN all inserts succeed
    """
    with app.app_context():
        first_utub_id, second_utub_id = (utub.id for utub in _utubs()[:2])
        _add_link(first_utub_id, TOKEN_A, revoked=True)
        _add_link(first_utub_id, TOKEN_B, revoked=True)
        _add_link(first_utub_id, TOKEN_C)
        _add_link(second_utub_id, "D" * 22)
        assert db.session.query(Utub_Invite_Links).count() == 4


def test_duplicate_token_rejected_even_across_revoked_rows(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a revoked link with a token
    WHEN another link reuses that token
    THEN an IntegrityError naming the unique token constraint is raised
    """
    with app.app_context():
        first_utub_id, second_utub_id = (utub.id for utub in _utubs()[:2])
        _add_link(first_utub_id, TOKEN_A, revoked=True)
        db.session.add(_new_link(second_utub_id, TOKEN_A))
        with pytest.raises(IntegrityError) as exc_info:
            db.session.commit()
        db.session.rollback()
        assert UNIQUE_INVITE_LINK_TOKEN in str(exc_info.value)


def test_deleting_creator_sets_created_by_null(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an invite link created by a user with no other rows
    WHEN that user is deleted
    THEN the invite row remains with created_by NULL
    """
    with app.app_context():
        creator_id = _make_disposable_user()
        link_id = _add_link(_utubs()[0].id, created_by=creator_id)

        db.session.execute(
            text('DELETE FROM "Users" WHERE id = :id'), {"id": creator_id}
        )
        db.session.commit()
        db.session.expire_all()

        link = db.session.get(Utub_Invite_Links, link_id)
        assert link is not None
        assert link.created_by is None
        assert link.creator is None


def test_deleting_invite_nulls_pending_reference_and_keeps_validation(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an Email_Validations row referencing an invite link
    WHEN the invite row is deleted
    THEN the validation row survives with pending_invite_id NULL
    """
    with app.app_context():
        link_id = _add_link(_utubs()[0].id)
        validation_id = _add_pending_validation(_first_user_id(), link_id)

        db.session.execute(
            text('DELETE FROM "UtubInviteLinks" WHERE id = :id'), {"id": link_id}
        )
        db.session.commit()
        db.session.expire_all()

        validation = db.session.get(Email_Validations, validation_id)
        assert validation is not None
        assert validation.pending_invite_id is None


def test_revoked_invite_keeps_reference_and_token_readable(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a pending validation referencing an invite link
    WHEN the link is revoked
    THEN the reference is kept and the raw token is readable via pending_invite
    """
    with app.app_context():
        link_id = _add_link(_utubs()[0].id)
        validation_id = _add_pending_validation(_first_user_id(), link_id)

        link = db.session.get(Utub_Invite_Links, link_id)
        assert link is not None
        link.revoked_at = utc_now()
        db.session.commit()
        db.session.expire_all()

        validation = db.session.get(Email_Validations, validation_id)
        assert validation is not None
        assert validation.pending_invite_id == link_id
        assert validation.pending_invite.token == TOKEN_A


@pytest.mark.parametrize("use_orm", [False, True])
def test_deleting_utub_removes_invites_and_nulls_pending_reference(
    app: Flask, every_user_makes_a_unique_utub, use_orm: bool
) -> None:
    """
    GIVEN a UTub with an invite link referenced by a pending validation
    WHEN the UTub is deleted (raw SQL, then ORM)
    THEN the invite row is removed, the reference is NULL and the validation survives
    """
    with app.app_context():
        utub = _utubs()[0]
        utub_id = utub.id
        link_id = _add_link(utub_id)
        validation_id = _add_pending_validation(_first_user_id(), link_id)

        if use_orm:
            db.session.delete(utub)
        else:
            # Child rows are not ORM-cascaded by raw SQL, so clear members first
            db.session.execute(
                text('DELETE FROM "UtubMembers" WHERE "utubID" = :id'),
                {"id": utub_id},
            )
            db.session.execute(
                text('DELETE FROM "Utubs" WHERE id = :id'), {"id": utub_id}
            )
        db.session.commit()
        db.session.expire_all()

        assert db.session.get(Utub_Invite_Links, link_id) is None
        validation = db.session.get(Email_Validations, validation_id)
        assert validation is not None
        assert validation.pending_invite_id is None


def test_email_validation_constructs_without_pending_invite_and_delete_keeps_invite(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an Email_Validations built with only a token
    THEN pending_invite_id is None; and deleting a validation that references
        an invite leaves the invite row intact
    """
    with app.app_context():
        assert Email_Validations(validation_token="t").pending_invite_id is None

        link_id = _add_link(_utubs()[0].id)
        validation_id = _add_pending_validation(_first_user_id(), link_id)

        validation = db.session.get(Email_Validations, validation_id)
        assert validation is not None
        db.session.delete(validation)
        db.session.commit()

        assert db.session.get(Utub_Invite_Links, link_id) is not None


def test_expiry_is_required(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN an invite link whose expires_at is NULL
    WHEN committed
    THEN an IntegrityError is raised (every link expires)
    """
    with app.app_context():
        link = _new_link(_utubs()[0].id)
        link.expires_at = None  # type: ignore[assignment]
        db.session.add(link)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
