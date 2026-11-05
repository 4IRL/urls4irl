"""Tests for ``resolve_invite_page`` (read-only page classifier)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from flask import Flask

from backend import db
from backend.invite_links.constants import INVITE_LINK_DEFAULT_TTL
from backend.invite_links.data_models import InvitePageResolution, InvitePageState
from backend.invite_links.services.invite_page import resolve_invite_page
from backend.models.users import Users
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.datetime_utils import utc_now
from tests.utils_for_test import lock_utub, trash_utub

pytestmark = pytest.mark.invite_links

TOKEN: str = "J" * 22
CREATOR_ID: int = 1
VISITOR_ID: int = 2
UTUB_ID: int = 1

ALL_LINK_CASES = ("live", "revoked", "expired", "used_up", "locked")
DEAD_CASES = ("revoked", "expired", "used_up", "locked")


def _make_invite(case: str = "live") -> int:
    invite = Utub_Invite_Links(
        utub_id=UTUB_ID,
        token=TOKEN,
        created_by=CREATOR_ID,
        expires_at=(
            utc_now() - timedelta(seconds=1)
            if case == "expired"
            else utc_now() + INVITE_LINK_DEFAULT_TTL
        ),
        max_uses=1 if case == "used_up" else None,
    )
    if case == "used_up":
        invite.use_count = 1
    if case == "revoked":
        invite.revoked_at = utc_now()
    db.session.add(invite)
    db.session.commit()
    return invite.id


def _prepare(app: Flask, case: str) -> int:
    with app.app_context():
        invite_id = _make_invite(case)
    if case == "locked":
        lock_utub(app, UTUB_ID)
    return invite_id


def _add_member(user_id: int) -> None:
    membership = Utub_Members(member_role=Member_Role.MEMBER)
    membership.utub_id = UTUB_ID
    membership.user_id = user_id
    db.session.add(membership)
    db.session.commit()


def _visitor() -> Users:
    return db.session.get(Users, VISITOR_ID)


def _unvalidate() -> Users:
    visitor = _visitor()
    visitor.email_validated = False
    db.session.commit()
    return visitor


def _demote_creator() -> None:
    creator = db.session.get(Utub_Members, (UTUB_ID, CREATOR_ID))
    creator.member_role = Member_Role.MEMBER
    db.session.commit()


def _dead_resolution() -> InvitePageResolution:
    return InvitePageResolution(
        state=InvitePageState.DEAD, invite=None, utub_id=None, link_live=False
    )


def _snapshot(invite_id: int) -> tuple:
    db.session.expire_all()
    invite = db.session.get(Utub_Invite_Links, invite_id)
    return (
        invite.use_count,
        invite.revoked_at,
        invite.expires_at,
        sorted(
            (membership.user_id, membership.member_role.value)
            for membership in Utub_Members.query.all()
        ),
        Utub_Invite_Acceptances.query.count(),
    )


@pytest.mark.parametrize("case", ALL_LINK_CASES)
def test_validated_member_redirects_for_every_link_state(
    app: Flask, every_user_makes_a_unique_utub, case: str
) -> None:
    """
    GIVEN a validated member and a live, revoked, expired, used-up or locked link
    WHEN the page is classified
    THEN MEMBER_REDIRECT with the utub id, no invite, and link_live of the link
    """
    _prepare(app, case)
    with app.app_context():
        _add_member(VISITOR_ID)
        result = resolve_invite_page(visitor=_visitor(), token=TOKEN)
        assert result == InvitePageResolution(
            state=InvitePageState.MEMBER_REDIRECT,
            invite=None,
            utub_id=UTUB_ID,
            link_live=case == "live",
        )


def test_validated_member_creator_demoted_redirects_not_live(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a validated member and a link whose creator is no longer a manager
    WHEN classified
    THEN MEMBER_REDIRECT with the utub id and link_live False
    """
    _prepare(app, "live")
    with app.app_context():
        _add_member(VISITOR_ID)
        _demote_creator()
        result = resolve_invite_page(visitor=_visitor(), token=TOKEN)
        assert result == InvitePageResolution(
            state=InvitePageState.MEMBER_REDIRECT,
            invite=None,
            utub_id=UTUB_ID,
            link_live=False,
        )


def test_trashed_utub_member_is_dead(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a validated member of a trashed UTub
    WHEN classified
    THEN DEAD with no invite or utub id
    """
    _prepare(app, "live")
    with app.app_context():
        _add_member(VISITOR_ID)
    trash_utub(app, UTUB_ID, CREATOR_ID)
    with app.app_context():
        result = resolve_invite_page(visitor=_visitor(), token=TOKEN)
        assert result == _dead_resolution()


def test_trashed_utub_unvalidated_member_and_anonymous_are_dead(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a trashed UTub
    WHEN an unvalidated member and an anonymous visitor are classified
    THEN both get DEAD
    """
    _prepare(app, "live")
    with app.app_context():
        _add_member(VISITOR_ID)
        _unvalidate()
    trash_utub(app, UTUB_ID, CREATOR_ID)
    with app.app_context():
        for visitor in (_visitor(), None):
            result = resolve_invite_page(visitor=visitor, token=TOKEN)
            assert result == _dead_resolution()


def test_validated_non_member_live_is_join_ready(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link and a validated non-member
    WHEN classified
    THEN JOIN_READY with the invite, no utub id, link_live True
    """
    invite_id = _prepare(app, "live")
    with app.app_context():
        result = resolve_invite_page(visitor=_visitor(), token=TOKEN)
        assert result.state is InvitePageState.JOIN_READY
        assert result.invite.id == invite_id
        assert result.utub_id is None
        assert result.link_live is True


@pytest.mark.parametrize("case", DEAD_CASES)
def test_validated_non_member_dead_link_is_dead(
    app: Flask, every_user_makes_a_unique_utub, case: str
) -> None:
    """
    GIVEN a dead link and a validated non-member
    WHEN classified
    THEN DEAD with invite and utub id None
    """
    _prepare(app, case)
    with app.app_context():
        result = resolve_invite_page(visitor=_visitor(), token=TOKEN)
        assert result == _dead_resolution()


def test_creator_demoted_link_is_dead_for_non_member(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a link whose creator is no longer a manager
    WHEN a non-member and an anonymous visitor are classified
    THEN both get DEAD
    """
    _prepare(app, "live")
    with app.app_context():
        _demote_creator()
        for visitor in (_visitor(), None):
            result = resolve_invite_page(visitor=visitor, token=TOKEN)
            assert result == _dead_resolution()


def test_anonymous_live_is_login_required(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link and an anonymous visitor
    WHEN classified
    THEN LOGIN_REQUIRED with the invite
    """
    invite_id = _prepare(app, "live")
    with app.app_context():
        result = resolve_invite_page(visitor=None, token=TOKEN)
        assert result.state is InvitePageState.LOGIN_REQUIRED
        assert result.invite.id == invite_id
        assert result.utub_id is None
        assert result.link_live is True


@pytest.mark.parametrize("case", DEAD_CASES)
def test_anonymous_dead_link_is_dead(
    app: Flask, every_user_makes_a_unique_utub, case: str
) -> None:
    """
    GIVEN a dead link and an anonymous visitor
    WHEN classified
    THEN DEAD
    """
    _prepare(app, case)
    with app.app_context():
        result = resolve_invite_page(visitor=None, token=TOKEN)
        assert result == _dead_resolution()


def test_unvalidated_non_member_live_link_is_email_unvalidated(
    app: Flask, every_user_makes_a_unique_utub
) -> None:
    """
    GIVEN a live link and an unvalidated non-member
    WHEN classified
    THEN EMAIL_UNVALIDATED, no invite details, link_live True
    """
    _prepare(app, "live")
    with app.app_context():
        visitor = _unvalidate()
        result = resolve_invite_page(visitor=visitor, token=TOKEN)
        assert result == InvitePageResolution(
            state=InvitePageState.EMAIL_UNVALIDATED,
            invite=None,
            utub_id=None,
            link_live=True,
        )


@pytest.mark.parametrize("case", ALL_LINK_CASES)
def test_unvalidated_member_is_email_unvalidated(
    app: Flask, every_user_makes_a_unique_utub, case: str
) -> None:
    """
    GIVEN an unvalidated member of a non-trashed UTub, any link state
    WHEN classified
    THEN EMAIL_UNVALIDATED (never MEMBER_REDIRECT), link_live per the link
    """
    _prepare(app, case)
    with app.app_context():
        _add_member(VISITOR_ID)
        visitor = _unvalidate()
        result = resolve_invite_page(visitor=visitor, token=TOKEN)
        assert result == InvitePageResolution(
            state=InvitePageState.EMAIL_UNVALIDATED,
            invite=None,
            utub_id=None,
            link_live=case == "live",
        )


@pytest.mark.parametrize("case", DEAD_CASES)
def test_unvalidated_non_member_dead_link_is_dead(
    app: Flask, every_user_makes_a_unique_utub, case: str
) -> None:
    """
    GIVEN an unvalidated non-member and a dead link
    WHEN classified
    THEN DEAD
    """
    _prepare(app, case)
    with app.app_context():
        visitor = _unvalidate()
        result = resolve_invite_page(visitor=visitor, token=TOKEN)
        assert result == _dead_resolution()


@pytest.mark.parametrize("token", ("K" * 22, "short", "!" * 22, ""))
def test_unvalidated_visitor_unknown_or_malformed_token_is_dead(
    app: Flask, every_user_makes_a_unique_utub, token: str
) -> None:
    """
    GIVEN an unvalidated visitor and an unknown or malformed token
    WHEN classified
    THEN DEAD (never EMAIL_UNVALIDATED)
    """
    _prepare(app, "live")
    with app.app_context():
        visitor = _unvalidate()
        result = resolve_invite_page(visitor=visitor, token=token)
        assert result == _dead_resolution()


@pytest.mark.parametrize("is_member", (True, False))
@pytest.mark.parametrize("case", ("live", "revoked", "trashed"))
def test_suspended_visitor_is_dead(
    app: Flask, every_user_makes_a_unique_utub, case: str, is_member: bool
) -> None:
    """
    GIVEN a suspended Users object (defensive path; web sessions are anonymous)
    WHEN classified against a live, revoked or trashed-UTub link
    THEN DEAD with no invite or utub id; link_live is the link's own liveness
         (False when trashed)
    """
    _prepare(app, "live" if case == "trashed" else case)
    if is_member:
        with app.app_context():
            _add_member(VISITOR_ID)
    if case == "trashed":
        trash_utub(app, UTUB_ID, CREATOR_ID)
    with app.app_context():
        visitor = _visitor()
        visitor.is_suspended = True
        result = resolve_invite_page(visitor=visitor, token=TOKEN)
        assert result == InvitePageResolution(
            state=InvitePageState.DEAD,
            invite=None,
            utub_id=None,
            link_live=case == "live",
        )
        db.session.rollback()


def test_unknown_token_is_dead(app: Flask, every_user_makes_a_unique_utub) -> None:
    """
    GIVEN a well-formed token with no row
    WHEN classified for a member-capable user and anonymous
    THEN DEAD with link_live False
    """
    _prepare(app, "live")
    with app.app_context():
        for visitor in (_visitor(), None):
            result = resolve_invite_page(visitor=visitor, token="K" * 22)
            assert result == _dead_resolution()


@pytest.mark.parametrize("token", ("short", "!" * 22, "", "J" * 23))
def test_malformed_token_is_dead_without_query(
    app: Flask, every_user_makes_a_unique_utub, token: str
) -> None:
    """
    GIVEN a malformed token
    WHEN classified
    THEN DEAD, and the Utub_Invite_Links table is never queried
    """
    _prepare(app, "live")
    with app.app_context():
        with patch("backend.invite_links.lookup.Utub_Invite_Links") as model:
            result = resolve_invite_page(visitor=_visitor(), token=token)
            assert not model.mock_calls
        assert result == _dead_resolution()


@pytest.mark.parametrize("case", (*ALL_LINK_CASES, "unvalidated", "trashed"))
@pytest.mark.parametrize("as_member", (True, False))
def test_classifier_writes_nothing(
    app: Flask, every_user_makes_a_unique_utub, case: str, as_member: bool
) -> None:
    """
    GIVEN any link state and visitor kind
    WHEN classified
    THEN the invite row, use_count, members and acceptances are unchanged
    """
    invite_id = _prepare(app, case if case in ALL_LINK_CASES else "live")
    with app.app_context():
        if as_member:
            _add_member(VISITOR_ID)
        if case == "unvalidated":
            _unvalidate()
    if case == "trashed":
        trash_utub(app, UTUB_ID, CREATOR_ID)
    with app.app_context():
        visitor = _visitor()
        before = _snapshot(invite_id)
        for who in (visitor, None):
            resolve_invite_page(visitor=who, token=TOKEN)
        assert not db.session.new
        assert not db.session.dirty
        assert _snapshot(invite_id) == before
