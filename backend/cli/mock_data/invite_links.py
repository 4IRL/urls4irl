from flask_sqlalchemy import SQLAlchemy

from backend.cli.mock_constants import MOCK_INVITE_LINK_STATES, MOCK_UTUB_NAME_BASE
from backend.invite_links.constants import INVITE_LINK_DEFAULT_TTL
from backend.invite_links.token_generator import generate_invite_token
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.utils.datetime_utils import utc_now


def generate_mock_invite_links(db: SQLAlchemy) -> None:
    """Seed one example invite link per state onto the lowest-id mock UTubs.

    State ``index`` goes on the lowest-id UTub named ``MockUTub_<index + 1>``.
    A UTub that already has any invite row is skipped, so repeat runs add
    nothing. Tokens are random and never printed. Requires an app context.
    """
    now = utc_now()
    for index, state in enumerate(MOCK_INVITE_LINK_STATES):
        utub_name = f"{MOCK_UTUB_NAME_BASE}{index + 1}"
        utub: Utubs | None = (
            Utubs.query.filter(Utubs.name == utub_name).order_by(Utubs.id).first()
        )
        if utub is None:
            print(f"addmock: {utub_name} not found; skipped {state.label} invite link")
            continue

        if Utub_Invite_Links.query.filter_by(utub_id=utub.id).first() is not None:
            print(f"Already added invite link to {utub_name}")
            continue

        print(f"Adding {state.label} invite link to {utub_name}")
        expires_at = (
            now - INVITE_LINK_DEFAULT_TTL
            if state.expired
            else now + INVITE_LINK_DEFAULT_TTL
        )
        invite_link = Utub_Invite_Links(
            utub_id=utub.id,
            token=generate_invite_token(),
            created_by=utub.utub_creator,
            expires_at=expires_at,
            max_uses=state.max_uses,
        )
        invite_link.use_count = state.use_count
        if state.revoked:
            invite_link.revoked_at = now
        db.session.add(invite_link)
        db.session.flush()
        _add_mock_acceptances(db, invite_link, state.use_count)
    db.session.commit()


def _add_mock_acceptances(
    db: SQLAlchemy, invite_link: Utub_Invite_Links, count: int
) -> None:
    """Add ``count`` acceptance rows for an invite, one per non-creator member.

    Members are taken in user id order; any remainder is recorded anonymously
    (NULL user), as if that account had been erased.
    """
    member_ids: list[int] = [
        member.user_id
        for member in Utub_Members.query.filter(
            Utub_Members.utub_id == invite_link.utub_id,
            Utub_Members.user_id != invite_link.created_by,
        )
        .order_by(Utub_Members.user_id)
        .limit(count)
        .all()
    ]
    user_ids: list[int | None] = [
        *member_ids,
        *([None] * (count - len(member_ids))),
    ]
    for user_id in user_ids:
        db.session.add(
            Utub_Invite_Acceptances(
                invite_id=invite_link.id, utub_id=invite_link.utub_id, user_id=user_id
            )
        )
