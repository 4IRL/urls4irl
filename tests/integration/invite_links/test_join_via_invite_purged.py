"""``join_via_invite`` against a really purged invite row.

Built on ``build_app`` + ``committed_invite_utub`` (real commits). The invite is
loaded, then deleted on a second raw connection (committed and closed), so the
first session's instance keeps ``id`` and ``utub_id`` while the row is gone: the
race between a caller's unlocked read and the lock.
"""

from __future__ import annotations

import pytest

from backend import db
from backend.invite_links.constants import InviteJoinOutcome
from backend.invite_links.data_models import InviteJoinResult
from backend.invite_links.services.join_via_invite import join_via_invite
from backend.models.users import Users
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from tests.integration.system.metrics_helpers import build_pg_conn

pytestmark = pytest.mark.invite_links

MEMBER_INDEX: int = 1
NON_MEMBER_INDEX: int = 2


def _purge_invite_on_second_connection(app, invite_id: int) -> None:
    pg_conn = build_pg_conn(app)
    try:
        with pg_conn.cursor() as cursor:
            cursor.execute('DELETE FROM "UtubInviteLinks" WHERE id = %s', (invite_id,))
            assert cursor.rowcount == 1
        pg_conn.commit()
    finally:
        pg_conn.close()


def test_member_with_purged_invite_gets_already_member(
    committed_invite_utub,
) -> None:
    """
    GIVEN a validated member and an invite row purged after the caller read it
    WHEN the member joins
    THEN ALREADY_MEMBER with the captured UTub id, nothing written
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    with app.app_context():
        membership = Utub_Members(member_role=Member_Role.MEMBER)
        membership.utub_id = utub_id
        membership.user_id = user_ids[MEMBER_INDEX]
        db.session.add(membership)
        db.session.commit()

        actor = db.session.get(Users, user_ids[MEMBER_INDEX])
        invite = db.session.get(Utub_Invite_Links, invite_id)
        _purge_invite_on_second_connection(app, invite_id)

        result = join_via_invite(actor, invite)
        assert result == InviteJoinResult(InviteJoinOutcome.ALREADY_MEMBER, utub_id)
        assert Utub_Invite_Acceptances.query.count() == 0


def test_non_member_with_purged_invite_gets_dead(committed_invite_utub) -> None:
    """
    GIVEN a non-member and an invite row purged after the caller read it
    WHEN the non-member joins
    THEN DEAD with no UTub id, no membership, no consumed use, no acceptance
    """
    app, utub_id, invite_id, user_ids = committed_invite_utub
    non_member_id = user_ids[NON_MEMBER_INDEX]
    with app.app_context():
        actor = db.session.get(Users, non_member_id)
        invite = db.session.get(Utub_Invite_Links, invite_id)
        _purge_invite_on_second_connection(app, invite_id)

        result = join_via_invite(actor, invite)
        assert result == InviteJoinResult(InviteJoinOutcome.DEAD, None)

        db.session.expire_all()
        assert db.session.get(Utub_Members, (utub_id, non_member_id)) is None
        assert db.session.get(Utub_Invite_Links, invite_id) is None
        assert Utub_Invite_Acceptances.query.count() == 0
