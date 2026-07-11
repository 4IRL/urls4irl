from __future__ import annotations

from backend.admin.constants import AdminActionErrorCodes
from backend.api_common.responses import FlaskResponse
from backend.models.users import User_Role, Users
from backend.schemas.errors import build_message_error_response
from backend.utils.strings.admin_portal_strs import ADMIN_ACTION_STRINGS


def reject_self_action(*, actor_id: int, target_user_id: int) -> FlaskResponse | None:
    """Return a 403 error response when an admin targets their own account.

    Every admin account-mutation service calls this before touching state;
    ``None`` means the action may proceed. Centralized so suspend / delete /
    force-reset / kill-sessions / erase all enforce the identical guard.
    """
    if actor_id != target_user_id:
        return None
    return build_message_error_response(
        message=ADMIN_ACTION_STRINGS.SELF_ACTION_FORBIDDEN,
        error_code=AdminActionErrorCodes.SELF_ACTION_FORBIDDEN,
        status_code=403,
    )


def reject_leaving_zero_active_admins(*, target_user: Users) -> FlaskResponse | None:
    """Return a 403 error when suspending the last active admin would leave zero admins.

    Returns None when:
    - The target is not an ADMIN (non-admins can always be acted upon without
      affecting admin coverage)
    - At least one OTHER admin exists with ``is_suspended == False``

    Returns 403 when the target IS an ADMIN and no other unsuspended admin
    exists — suspending them would leave the portal without any active admin.

    This guard is intentionally shared with the account-erasure action; test
    it at the service level since the HTTP path for suspend always has an
    active acting admin (meaning an HTTP call can never actually hit this path
    for suspend, but the invariant must hold for erasure).
    """
    if target_user.role != User_Role.ADMIN:
        return None

    other_active_admin_count: int = Users.query.filter(
        Users.role == User_Role.ADMIN,
        Users.is_suspended == False,  # noqa: E712 — SQLAlchemy column comparison
        Users.id != target_user.id,
    ).count()
    if other_active_admin_count > 0:
        return None

    return build_message_error_response(
        message=ADMIN_ACTION_STRINGS.LAST_ADMIN_FORBIDDEN,
        error_code=AdminActionErrorCodes.LAST_ADMIN_FORBIDDEN,
        status_code=403,
    )
