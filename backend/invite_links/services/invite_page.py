from __future__ import annotations

from backend.invite_links.data_models import InvitePageResolution, InvitePageState
from backend.invite_links.lookup import find_invite_by_token
from backend.invite_links.validity import evaluate_invite, is_invite_live
from backend.models.users import Users
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.utubs.guards import get_fresh_membership


def _resolution(
    state: InvitePageState,
    *,
    link_live: bool,
    invite: Utub_Invite_Links | None = None,
    utub_id: int | None = None,
) -> InvitePageResolution:
    return InvitePageResolution(
        state=state, invite=invite, utub_id=utub_id, link_live=link_live
    )


def resolve_invite_page(*, visitor: Users | None, token: str) -> InvitePageResolution:
    """Classify a visitor and token into an invite page state; pure read.

    No locks, commits, metrics or ``current_user``/``request`` access. ``visitor``
    is ``None`` for an anonymous visitor. Fails closed: every branch not named
    below returns ``DEAD``.

    Args:
        visitor (Users | None): The viewing user, or None when anonymous.
        token (str): The raw token from the request path.

    Returns:
        InvitePageResolution: The page state, plus the invite (only for
        ``LOGIN_REQUIRED``/``JOIN_READY``), the utub id (only for
        ``MEMBER_REDIRECT``) and whether the link itself is currently live.
    """
    invite = find_invite_by_token(token)
    if invite is None:
        return _resolution(InvitePageState.DEAD, link_live=False)

    # Checked first: evaluate_invite orders the trashed check after the creator check.
    if invite.utub.is_trashed:
        return _resolution(InvitePageState.DEAD, link_live=False)

    link_live = is_invite_live(evaluate_invite(invite))

    if visitor is None:
        if link_live:
            return _resolution(
                InvitePageState.LOGIN_REQUIRED, link_live=True, invite=invite
            )
        return _resolution(InvitePageState.DEAD, link_live=False)

    if visitor.is_suspended:
        return _resolution(InvitePageState.DEAD, link_live=link_live)

    is_member = (
        get_fresh_membership(utub_id=invite.utub_id, user_id=visitor.id) is not None
    )

    # An unconfirmed account never holds a session (load_user rejects it), but fail
    # closed if one reaches here.
    if not visitor.email_validated:
        return _resolution(InvitePageState.DEAD, link_live=link_live)

    if is_member:
        return _resolution(
            InvitePageState.MEMBER_REDIRECT,
            link_live=link_live,
            utub_id=invite.utub_id,
        )
    if link_live:
        return _resolution(InvitePageState.JOIN_READY, link_live=True, invite=invite)
    return _resolution(InvitePageState.DEAD, link_live=False)
