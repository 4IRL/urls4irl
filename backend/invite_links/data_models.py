from dataclasses import dataclass

from backend.invite_links.constants import InviteJoinOutcome


@dataclass(frozen=True)
class InviteJoinResult:
    """Plain-data result of ``join_via_invite``; primitives only.

    ``utub_id`` is set only for ``JOINED`` and ``ALREADY_MEMBER``; it is ``None``
    on every other outcome so a caller cannot echo a UTub id to a non-member or
    a gated actor. ``DEAD`` deliberately carries no reason (the public page is
    uniform).
    """

    outcome: InviteJoinOutcome
    utub_id: int | None
