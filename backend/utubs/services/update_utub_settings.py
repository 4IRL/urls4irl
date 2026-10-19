from typing import Any

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log, safe_add_many_logs
from backend.models.utubs import Utubs
from backend.schemas.errors import build_field_error_response
from backend.schemas.utub_settings import (
    UtubSettingsPatchError,
    merge_utub_settings,
    utub_settings_overrides_changed,
)
from backend.schemas.utubs import UtubSettingsUpdatedResponseSchema
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.constants import UTubErrorCodes
from backend.utubs.guards import UtubAccess, lock_and_reauthorize


def update_utub_settings_if_changed(
    current_utub: Utubs, patch: dict[str, dict[str, Any]]
) -> FlaskResponse:
    """
    Merge a per-section settings patch into the UTub's stored sparse overrides.

    Commits only when the resulting overrides differ from the stored ones.
    ``Utubs.last_updated`` is deliberately not bumped: settings are
    configuration, not UTub content.

    Args:
        current_utub (Utubs): The UTub whose settings are being updated
        patch (dict): Section name -> keys to set, only for sections the caller sent

    Returns:
        FlaskResponse: The full resolved settings on 200, or a 400/403/404 error
    """
    auth_error: FlaskResponse | None = lock_and_reauthorize(
        current_utub,
        required_access=UtubAccess.MANAGER,
        error_code=UTubErrorCodes.UTUB_IS_LOCKED,
    )
    if auth_error is not None:
        return auth_error

    # Read after the lock: lock_and_reauthorize refreshes current_utub.
    raw_settings = current_utub.settings
    try:
        resolved_settings, new_overrides = merge_utub_settings(raw_settings, patch)
    except UtubSettingsPatchError as exc:
        return build_field_error_response(
            message=UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_SETTINGS,
            errors=exc.errors,
            error_code=UTubErrorCodes.INVALID_FORM_INPUT,
            status_code=400,
        )

    if utub_settings_overrides_changed(raw_settings, new_overrides):
        # Reassign a new dict, never mutate in place (no MutableDict).
        current_utub.settings = new_overrides
        db.session.commit()
        safe_add_many_logs(
            [
                "User updated UTub settings",
                f"UTub.id={current_utub.id}",
                f"Sections patched={sorted(patch)}",
            ]
        )
    else:
        safe_add_log("No change in UTub settings")

    return APIResponse(
        data=UtubSettingsUpdatedResponseSchema(
            utub_id=current_utub.id,
            settings=resolved_settings,
        )
    ).to_response()
