"""Fail-closed rule for who a viewer may see in a UTub's member list.

Leaf module: imports no models and no settings resolver, so schemas can import
it at module top without a cycle. It reads the RAW stored ``Utubs.settings``
value, because the resolver maps a malformed section to the default (visible).
"""

from __future__ import annotations

from typing import Any, Collection

_MANAGER_ROLES = frozenset({"creator", "cocreator"})
_PLAIN_ROLE = "member"
_CO_OWNER_ROLE = "cocreator"


def viewer_is_manager_from_role(role: str | None) -> bool | None:
    """Convert a member role value to manager (True), plain (False) or unknown (None)."""
    if not isinstance(role, str):
        return None
    if role in _MANAGER_ROLES:
        return True
    if role == _PLAIN_ROLE:
        return False
    return None


def member_list_hidden_for(*, settings: Any, viewer_is_manager: bool | None) -> bool:
    """True unless the viewer is a manager or the raw setting reads as visible."""
    if viewer_is_manager is True:
        return False
    if viewer_is_manager is not False:
        return True
    if settings is None:
        return False
    if not isinstance(settings, dict):
        return True
    if "members" not in settings:
        return False
    section = settings["members"]
    if not isinstance(section, dict):
        return True
    if "hide_member_list" not in section:
        return False
    return section["hide_member_list"] is not False


def visible_member_ids(
    *,
    settings: Any,
    viewer_is_manager: bool | None,
    utub_creator_id: int,
    viewer_id: int,
    co_owner_ids: Collection[int],
) -> set[int] | None:
    """Return None (everyone visible) or the ids the viewer may see."""
    if not member_list_hidden_for(
        settings=settings, viewer_is_manager=viewer_is_manager
    ):
        return None
    return {utub_creator_id, viewer_id} | set(co_owner_ids)


def visible_member_ids_for_utub(
    *, utub: Any, viewer_id: int, viewer_role: str | None
) -> set[int] | None:
    """``visible_member_ids`` for a Utubs row, deriving the co-owner ids itself.

    ``utub`` is duck-typed (``settings``, ``utub_creator``, ``members`` with
    ``user_id`` / ``member_role.value``) to keep this module a leaf.
    ``viewer_role`` is the viewer's ``Member_Role.value`` (None = unknown).
    """
    return visible_member_ids(
        settings=utub.settings,
        viewer_is_manager=viewer_is_manager_from_role(viewer_role),
        utub_creator_id=utub.utub_creator,
        viewer_id=viewer_id,
        co_owner_ids=[
            member.user_id
            for member in utub.members
            if member.member_role.value == _CO_OWNER_ROLE
        ],
    )
