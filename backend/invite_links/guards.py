from __future__ import annotations

from backend.models.utub_invite_links import Utub_Invite_Links


def lock_invite_for_update(*, invite_id: int) -> Utub_Invite_Links | None:
    """Take the row lock on one invite link and refresh it.

    Renders ``SELECT ... FOR NO KEY UPDATE`` (same strength as
    ``lock_utub_for_update``, so a pending-invite FK check does not queue on it).
    The caller must already hold the ``Utubs`` row lock (lock order: Utubs, then
    the invite). Never commits; the lock lasts until the caller commits or rolls
    back.

    Args:
        invite_id (int): ID of the invite link.

    Returns:
        The refreshed invite, or None if it no longer exists.
    """
    return (
        Utub_Invite_Links.query.populate_existing()
        .with_for_update(key_share=True)
        .filter(Utub_Invite_Links.id == invite_id)
        .one_or_none()
    )
