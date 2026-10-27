from typing import Any

from flask import abort
from flask_login import current_user

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log, safe_add_many_logs
from backend.models.utub_members import Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.errors import build_field_error_response
from backend.schemas.utub_member_settings import (
    UtubMemberSettingsPatchError,
    merge_member_settings,
    resolve_member_settings,
)
from backend.schemas.utubs import MemberSettingsUpdatedResponseSchema
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.constants import UTubErrorCodes


def update_member_settings_if_changed(
    current_utub: Utubs, patch: dict[str, dict[str, Any]]
) -> FlaskResponse:
    """
    Merge a per-section patch into the caller's own per-UTub view overrides.

    This write is deliberately NOT lock-gated and not role-gated: the overrides
    are private to the caller (stored on their own ``Utub_Members`` row, never
    visible to or affecting other members), so the UTub lock, which protects
    shared content, has no reason to block them, and a plain member must be able
    to tailor their own view. Only the caller's membership row is locked
    (``FOR UPDATE``, so two writers patching different keys both persist); there
    is no ``Utubs`` row lock, ``Utubs.last_updated`` is not bumped, and the
    request path carries no user id, so no request can target another member.

    Commits only when the resulting overrides differ from the stored ones.

    Args:
        current_utub (Utubs): The UTub whose caller-specific settings are updated
        patch (dict): Section name -> keys to set, only for sections the caller sent

    Returns:
        FlaskResponse: The caller's full resolved settings on 200, or a 400/404 error
    """
    membership: Utub_Members | None = (
        Utub_Members.query.filter(
            Utub_Members.utub_id == current_utub.id,
            Utub_Members.user_id == current_user.id,
        )
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if membership is None:
        # Removed concurrently: release the transaction, then mask as not found.
        db.session.rollback()
        abort(404)

    raw_settings = membership.settings
    try:
        new_overrides = merge_member_settings(raw_settings, patch)
    except UtubMemberSettingsPatchError as exc:
        db.session.rollback()
        return build_field_error_response(
            message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_SETTINGS,
            errors=exc.errors,
            error_code=UTubErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
        )

    if new_overrides != raw_settings:
        # Reassign a new dict, never mutate in place (no MutableDict).
        membership.settings = new_overrides
        db.session.commit()
        safe_add_many_logs(
            [
                "User updated their member settings",
                f"UTub.id={current_utub.id}",
                f"Sections patched={sorted(patch)}",
            ]
        )
    else:
        db.session.rollback()
        safe_add_log("No change in member settings")

    return APIResponse(
        data=MemberSettingsUpdatedResponseSchema(
            utub_id=current_utub.id,
            member_settings=resolve_member_settings(new_overrides),
        )
    ).to_response()
