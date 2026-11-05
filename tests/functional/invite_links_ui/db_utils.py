from flask import Flask

from backend import db
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utubs import Utubs
from tests.utils_for_test import add_invite_link


def mint_invite_link_in_db(
    *, app: Flask, utub_id: int, created_by: int, revoked: bool = False
) -> str:
    """Insert an invite link (live by default, or revoked) for ``utub_id`` minted by
    ``created_by`` and return its token, so a test can open the public page without
    driving the manager UI (which does not exist yet)."""
    invite_id = add_invite_link(app, utub_id, created_by, revoked=revoked)
    with app.app_context():
        invite: Utub_Invite_Links = Utub_Invite_Links.query.get(invite_id)
        return invite.token


def set_utub_description_in_db(*, app: Flask, utub_id: int, description: str) -> None:
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.utub_description = description
        db.session.commit()


def set_email_validated_in_db(*, app: Flask, user_id: int, validated: bool) -> None:
    with app.app_context():
        user: Users = Users.query.get(user_id)
        user.email_validated = validated
        db.session.commit()
