from dataclasses import dataclass
from enum import StrEnum

from backend.invite_links.constants import InviteJoinOutcome
from backend.models.utub_invite_links import Utub_Invite_Links


class InvitePageState(StrEnum):
    """What the public invite page shows for a visitor and token."""

    JOIN_READY = "join_ready"
    LOGIN_REQUIRED = "login_required"
    EMAIL_UNVALIDATED = "email_unvalidated"
    MEMBER_REDIRECT = "member_redirect"
    DEAD = "dead"


@dataclass(frozen=True)
class InvitePageResolution:
    """Result of ``resolve_invite_page``.

    ``utub_id`` is set only for ``MEMBER_REDIRECT``; ``invite`` only for
    ``JOIN_READY`` and ``LOGIN_REQUIRED`` (the states that render invite details).
    ``link_live`` is the link's own liveness, independent of the state, and feeds
    the link-viewed metric.
    """

    state: InvitePageState
    invite: Utub_Invite_Links | None
    utub_id: int | None
    link_live: bool


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
