"""Model-level tests for UtubInviteAcceptances: grouping and FK actions."""

from __future__ import annotations

import pytest
from flask import Flask
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend import db
from backend.invite_links.constants import INVITE_LINK_DEFAULT_TTL
from backend.models.users import Users
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now

pytestmark = pytest.mark.invite_links


def _utubs() -> list[Utubs]:
    utubs = db.session.query(Utubs).order_by(Utubs.id).all()
    assert len(utubs) >= 2
    return utubs


def _first_user_id() -> int:
    user = db.session.query(Users).order_by(Users.id).first()
    assert user is not None
    return user.id


def _add_invite(utub_id: int, token: str = "A" * 22) -> int:
    link = Utub_Invite_Links(
        utub_id=utub_id,
        token=token,
        created_by=_first_user_id(),
        expires_at=utc_now() + INVITE_LINK_DEFAULT_TTL,
    )
    db.session.add(link)
    db.session.commit()
    return link.id


def _add_acceptance(invite_id: int, utub_id: int, user_id: int | None) -> int:
    acceptance = Utub_Invite_Acceptances(
        invite_id=invite_id, utub_id=utub_id, user_id=user_id
    )
    db.session.add(acceptance)
    db.session.commit()
    return acceptance.id


def _make_disposable_user() -> int:
    user = Users(
        username="disposable_joiner",
        email="disposable_joiner@example.com",
        plaintext_password="disposable_joiner1!",
    )
    db.session.add(user)
    db.session.commit()
    return user.id


def _acceptance_count(invite_id: int) -> int:
    return (
        db.session.query(Utub_Invite_Acceptances).filter_by(invite_id=invite_id).count()
    )


def test_acceptances_group_by_invite_with_or_without_user(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN several acceptances for one invite, some with a NULL user
    WHEN querying by invite id
    THEN all of them are returned and accepted_at is set
    """
    with app.app_context():
        utub_id = _utubs()[0].id
        invite_id = _add_invite(utub_id)
        other_invite_id = _add_invite(_utubs()[1].id, "B" * 22)
        _add_acceptance(invite_id, utub_id, _first_user_id())
        _add_acceptance(invite_id, utub_id, None)
        _add_acceptance(other_invite_id, _utubs()[1].id, None)

        rows = db.session.query(Utub_Invite_Acceptances).filter_by(invite_id=invite_id)
        assert rows.count() == 2
        assert all(row.accepted_at is not None for row in rows)
        assert {row.user_id is None for row in rows} == {True, False}
        assert _acceptance_count(other_invite_id) == 1

        anonymous_acceptance = rows.filter(
            Utub_Invite_Acceptances.user_id.is_(None)
        ).one()
        assert anonymous_acceptance.invite.id == invite_id
        assert anonymous_acceptance.utub.id == utub_id
        assert anonymous_acceptance.user is None


def test_acceptance_with_nonexistent_invite_is_rejected(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an acceptance pointing at an invite id that does not exist
    WHEN it is committed
    THEN the foreign key rejects it with an IntegrityError and nothing is stored
    """
    with app.app_context():
        utub_id = _utubs()[0].id
        missing_invite_id = (
            db.session.query(db.func.max(Utub_Invite_Links.id)).scalar() or 0
        ) + 1000

        with pytest.raises(IntegrityError):
            _add_acceptance(missing_invite_id, utub_id, None)
        db.session.rollback()

        assert _acceptance_count(missing_invite_id) == 0


def test_revoking_invite_keeps_acceptances(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN an invite with acceptances
    WHEN the invite is revoked
    THEN its acceptance rows are unchanged
    """
    with app.app_context():
        utub_id = _utubs()[0].id
        invite_id = _add_invite(utub_id)
        _add_acceptance(invite_id, utub_id, _first_user_id())

        invite = db.session.get(Utub_Invite_Links, invite_id)
        assert invite is not None
        invite.revoked_at = utc_now()
        db.session.commit()

        assert _acceptance_count(invite_id) == 1


@pytest.mark.parametrize("use_orm", [False, True])
def test_deleting_user_keeps_acceptance_anonymous(
    app: Flask, every_user_makes_a_unique_utub, use_orm: bool
) -> None:
    """
    GIVEN an acceptance by a user
    WHEN that user is deleted (raw SQL, then ORM)
    THEN the row stays with user_id NULL and invite_id / utub_id intact
    """
    with app.app_context():
        utub_id = _utubs()[0].id
        invite_id = _add_invite(utub_id)
        user_id = _make_disposable_user()
        acceptance_id = _add_acceptance(invite_id, utub_id, user_id)

        if use_orm:
            user = db.session.get(Users, user_id)
            assert user is not None
            db.session.delete(user)
        else:
            db.session.execute(
                text('DELETE FROM "Users" WHERE id = :id'), {"id": user_id}
            )
        db.session.commit()
        db.session.expire_all()

        acceptance = db.session.get(Utub_Invite_Acceptances, acceptance_id)
        assert acceptance is not None
        assert acceptance.user_id is None
        assert acceptance.invite_id == invite_id
        assert acceptance.utub_id == utub_id


@pytest.mark.parametrize("use_orm", [False, True])
def test_deleting_invite_removes_acceptances(
    app: Flask, every_user_makes_a_unique_utub, use_orm: bool
) -> None:
    """
    GIVEN an invite with acceptances
    WHEN the invite is deleted (raw SQL, then ORM)
    THEN its acceptances are removed
    """
    with app.app_context():
        utub_id = _utubs()[0].id
        invite_id = _add_invite(utub_id)
        _add_acceptance(invite_id, utub_id, _first_user_id())
        _add_acceptance(invite_id, utub_id, None)

        if use_orm:
            invite = db.session.get(Utub_Invite_Links, invite_id)
            assert invite is not None
            db.session.delete(invite)
        else:
            db.session.execute(
                text('DELETE FROM "UtubInviteLinks" WHERE id = :id'),
                {"id": invite_id},
            )
        db.session.commit()
        db.session.expire_all()

        assert _acceptance_count(invite_id) == 0


@pytest.mark.parametrize("use_orm", [False, True])
def test_deleting_utub_removes_acceptances(
    app: Flask, every_user_makes_a_unique_utub, use_orm: bool
) -> None:
    """
    GIVEN a UTub whose invite has acceptances
    WHEN the UTub is deleted (raw SQL, then ORM)
    THEN the invite and its acceptances are removed
    """
    with app.app_context():
        utub = _utubs()[0]
        utub_id = utub.id
        invite_id = _add_invite(utub_id)
        _add_acceptance(invite_id, utub_id, _first_user_id())

        if use_orm:
            db.session.delete(utub)
        else:
            db.session.execute(
                text('DELETE FROM "UtubMembers" WHERE "utubID" = :id'),
                {"id": utub_id},
            )
            db.session.execute(
                text('DELETE FROM "Utubs" WHERE id = :id'), {"id": utub_id}
            )
        db.session.commit()
        db.session.expire_all()

        assert _acceptance_count(invite_id) == 0
        assert db.session.get(Utub_Invite_Links, invite_id) is None
