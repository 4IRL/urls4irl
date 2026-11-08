from __future__ import annotations

from backend.api_common.responses import FlaskResponse
from backend.members.constants import UTubMembersErrorCodes
from backend.models.utubs import Utubs
from backend.schemas.errors import build_message_error_response
from backend.schemas.utub_settings import resolve_utub_settings
from backend.utils.strings.utub_strs import UTUB_FAILURE


def can_add_members(utub: Utubs, *, is_manager: bool) -> bool:
    """Single rule for who may add members and load add suggestions.

    Managers (owner and co-owners) always may. A plain member may only while the
    owner's ``members_can_add`` switch is exactly True. Fail closed: a missing or
    unresolvable setting resolves to the False default.

    Args:
        utub (Utubs): The UTub whose settings are read.
        is_manager (bool): Whether the caller is a manager of the UTub.

    Returns:
        True when the caller may add members.
    """
    if is_manager:
        return True
    return resolve_utub_settings(utub.settings).members.members_can_add is True


def member_add_refusal_response(
    utub: Utubs, *, is_manager: bool
) -> FlaskResponse | None:
    """Return the 403 errorCode 7 response when the caller may not add, else None."""
    if can_add_members(utub, is_manager=is_manager):
        return None
    return build_message_error_response(
        message=UTUB_FAILURE.NOT_AUTHORIZED,
        error_code=UTubMembersErrorCodes.MEMBER_ADD_NOT_ALLOWED,
        status_code=403,
    )
