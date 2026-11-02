from __future__ import annotations

from backend import db
from backend.app_logger import safe_add_many_logs
from backend.extensions.metrics.writer import record_event
from backend.invite_links.constants import InviteJoinOutcome
from backend.invite_links.data_models import InviteJoinResult
from backend.invite_links.guards import lock_invite_for_update
from backend.invite_links.validity import evaluate_invite, is_invite_live
from backend.members.constants import MemberAddSource
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_invite_acceptances import Utub_Invite_Acceptances
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utubs.guards import get_fresh_membership, lock_utub_for_update


def _dead() -> InviteJoinResult:
    db.session.rollback()
    return InviteJoinResult(outcome=InviteJoinOutcome.DEAD, utub_id=None)


def join_via_invite(actor: Users, invite: Utub_Invite_Links) -> InviteJoinResult:
    """Join ``actor`` to the invite's UTub through the invite link, under locks.

    Lock order: ``Utubs`` row, then the invite row, then ``Utub_Members`` writes.
    ``invite`` may have been read without a lock; only its ``id`` and ``utub_id``
    are trusted. Reads no ``current_user``, ``g`` or ``request``. Every return
    after the UTub lock rolls back or commits first, so no lock outlives the call.
    Fails closed: ``JOINED`` is reached only after every check has passed.

    Args:
        actor (Users): The user joining.
        invite (Utub_Invite_Links): The invite link being used.

    Returns:
        ``InviteJoinResult``; ``utub_id`` is set only for ``JOINED`` and
        ``ALREADY_MEMBER``.
    """
    invite_id: int = invite.id
    utub_id: int = invite.utub_id
    actor_id: int = actor.id

    # Pre-lock actor gate; deliberately not re-read under the lock (accepted race).
    if not actor.email_validated:
        return InviteJoinResult(
            outcome=InviteJoinOutcome.ACTOR_UNVALIDATED, utub_id=None
        )
    if actor.is_suspended:
        return InviteJoinResult(outcome=InviteJoinOutcome.ACTOR_SUSPENDED, utub_id=None)

    utub = lock_utub_for_update(utub_id=utub_id)
    if utub is None or utub.is_trashed:
        return _dead()

    locked_invite = lock_invite_for_update(invite_id=invite_id)

    if get_fresh_membership(utub_id=utub_id, user_id=actor_id) is not None:
        db.session.rollback()
        return InviteJoinResult(
            outcome=InviteJoinOutcome.ALREADY_MEMBER, utub_id=utub_id
        )

    if locked_invite is None or not is_invite_live(evaluate_invite(locked_invite)):
        return _dead()

    membership = Utub_Members()
    membership.utub_id = utub_id
    membership.user_id = actor_id
    membership.member_role = Member_Role.MEMBER
    db.session.add(membership)
    db.session.add(
        Utub_Invite_Acceptances(invite_id=invite_id, utub_id=utub_id, user_id=actor_id)
    )
    locked_invite.use_count = Utub_Invite_Links.use_count + 1
    utub.set_last_updated()
    db.session.commit()

    safe_add_many_logs(
        [
            "Joined UTub via invite link",
            f"UTub.id={utub_id}",
            f"Invite.id={invite_id}",
            f"Joined User={actor_id}",
        ]
    )
    record_event(
        EventName.MEMBER_ADDED,
        dimensions={"source": MemberAddSource.INVITE_LINK.value},
    )
    return InviteJoinResult(outcome=InviteJoinOutcome.JOINED, utub_id=utub_id)
