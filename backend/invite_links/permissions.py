"""Who may create invite links and turn their preview on.

Leaf module: imports only schemas, models and ``Member_Role``; never services
or guards, so every layer can use it without an import cycle.

Fail closed: a role, rule value or branch not explicitly allowed denies. The
creators rule is read from the RAW stored settings, because the cleaned
resolver turns an invalid stored section into defaults, and for this key the
default is the most permissive value.
"""

from __future__ import annotations

from backend.models.utub_members import Member_Role
from backend.models.utubs import Utubs
from backend.schemas.utub_settings import InviteLinkCreators

_CREATORS_KEY = "invite_link_creators"


def creators_from_raw_settings(settings: dict | None) -> InviteLinkCreators | None:
    """Read the creators rule from raw stored settings.

    Absent key (or no ``members`` section) gives the default. A valid stored
    value gives that value. Anything else (unknown string, wrong type,
    non-dict section) gives ``None``, which denies everyone.
    """
    if settings is None:
        return InviteLinkCreators.OWNER_AND_CO_OWNERS
    if not isinstance(settings, dict):
        return None
    if "members" not in settings:
        return InviteLinkCreators.OWNER_AND_CO_OWNERS
    members = settings["members"]
    if not isinstance(members, dict):
        return None
    if _CREATORS_KEY not in members:
        return InviteLinkCreators.OWNER_AND_CO_OWNERS
    value = members[_CREATORS_KEY]
    if not isinstance(value, str):
        return None
    try:
        return InviteLinkCreators(value)
    except ValueError:
        return None


def creator_may_create(
    *, creators: InviteLinkCreators | None, role: Member_Role | None
) -> bool:
    """Role x rule table; anything not explicitly allowed is denied."""
    authorized = False
    if creators is None or role is None:
        return authorized
    if role == Member_Role.CREATOR:
        authorized = creators in (
            InviteLinkCreators.OWNER_AND_CO_OWNERS,
            InviteLinkCreators.OWNER_ONLY,
        )
    elif role == Member_Role.CO_CREATOR:
        authorized = creators == InviteLinkCreators.OWNER_AND_CO_OWNERS
    return authorized


def can_create_invite_links(*, utub: Utubs, role: Member_Role | None) -> bool:
    """Whether ``role`` may create, replace or edit this UTub's invite link."""
    return creator_may_create(
        creators=creators_from_raw_settings(utub.settings), role=role
    )


def can_enable_invite_preview(*, utub: Utubs, role: Member_Role | None) -> bool:
    """Whether ``role`` may turn the invite link preview on."""
    authorized = False
    if role == Member_Role.CREATOR:
        authorized = True
    elif role == Member_Role.CO_CREATOR:
        authorized = _raw_co_owner_preview_flag(utub.settings) is True
    return authorized


def co_owner_preview_from_raw_settings(settings: object) -> bool:
    """Whether raw stored settings let co-owners turn previews on (fail closed)."""
    return _raw_co_owner_preview_flag(settings) is True


def _raw_co_owner_preview_flag(settings: object) -> object:
    """The raw stored preview flag; anything not a real bool ``True`` denies.

    Read raw (not via the cleaned resolver): pydantic's lax bool coercion
    would turn a stored ``"yes"`` or ``1`` into ``True``.
    """
    if not isinstance(settings, dict):
        return None
    members = settings.get("members")
    if not isinstance(members, dict):
        return None
    return members.get("co_owners_can_enable_preview")
