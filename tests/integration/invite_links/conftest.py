"""Shared fixtures for invite link tests that need real commits and real locks."""

from __future__ import annotations

from typing import Generator, Tuple

import pytest
from flask import Flask
from flask_session.redis import RedisSessionInterface
from redis import Redis
from sqlalchemy import text

from backend import db
from backend.invite_links.constants import INVITE_LINK_DEFAULT_TTL
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now
from backend.utils.strings import model_strs
from tests.models_for_test import valid_user_1, valid_user_2, valid_user_3

COMMITTED_INVITE_TOKEN: str = "C" * 22


@pytest.fixture
def committed_invite_utub(
    build_app,
) -> Generator[Tuple[Flask, int, int, list[int]], None, None]:
    """Commit 3 users, one UTub (user 1 is CREATOR; users 2 and 3 are NOT members)
    and one live invite created by user 1, with real commits; TRUNCATE on teardown.

    Depends on ``build_app`` only (never ``app`` / ``db_transaction``) so locks and
    cross-connection writes behave for real.

    Yields (app, utub_id, invite_id, user_ids).
    """
    app, _ = build_app
    with app.app_context():
        user_ids: list[int] = []
        for credential in (valid_user_1, valid_user_2, valid_user_3):
            new_user = Users(
                username=credential[model_strs.USERNAME],
                email=credential[model_strs.EMAIL].lower(),
                plaintext_password=credential[model_strs.PASSWORD],
            )
            new_user.email_validated = True
            db.session.add(new_user)
            db.session.commit()
            user_ids.append(new_user.id)

        new_utub = Utubs(
            name="Invite race UTub", utub_creator=user_ids[0], utub_description=""
        )
        db.session.add(new_utub)
        db.session.commit()
        utub_id: int = new_utub.id

        membership = Utub_Members(member_role=Member_Role.CREATOR)
        membership.utub_id = utub_id
        membership.user_id = user_ids[0]
        db.session.add(membership)
        db.session.commit()

        invite = Utub_Invite_Links(
            utub_id=utub_id,
            token=COMMITTED_INVITE_TOKEN,
            created_by=user_ids[0],
            expires_at=utc_now() + INVITE_LINK_DEFAULT_TTL,
            max_uses=None,
        )
        db.session.add(invite)
        db.session.commit()
        invite_id: int = invite.id

    yield app, utub_id, invite_id, user_ids

    with app.app_context():
        db.session.rollback()
        db.session.execute(text("SET LOCAL lock_timeout = '10s'"))
        db.session.execute(
            text(
                'TRUNCATE TABLE "Users", "Utubs", "UtubMembers", "UtubInviteLinks", '
                '"UtubInviteAcceptances" RESTART IDENTITY CASCADE'
            )
        )
        db.session.commit()
    if isinstance(app.session_interface, RedisSessionInterface):
        client: Redis = app.session_interface.client
        client.flushdb()
