from __future__ import annotations

from backend.admin.constants import AdminActionErrorCodes
from backend.api_common.responses import FlaskResponse
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
