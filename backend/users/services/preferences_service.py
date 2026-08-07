from __future__ import annotations

from typing import Any

from flask_login import current_user

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.models.user_preferences import (
    DateFormat,
    Density,
    SortOrder,
    Theme,
    User_Preferences,
    ViewMode,
)
from backend.schemas.errors import build_message_error_response
from backend.schemas.users import UpdatePreferencesResponseSchema
from backend.users.constants import PreferencesErrorCodes
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.user_strs import (
    PREFERENCES_CHANGE_NO_CHANGE,
    PREFERENCES_CHANGE_SUCCESS,
    USER_FAILURE,
)


def build_display_preferences_context() -> dict[str, Any]:
    """Build the Settings Display panel template context for the authenticated
    user.

    Mirrors ``build_user_stats_context()`` — no parameters, reads
    ``current_user``, returns a flat dict of ``display_``-prefixed strings so the
    keys never collide with the connected-accounts / stats / account-info context
    keys. Each value is the stored enum's lowercase ``.value`` string so the
    template can mark the matching control selected/checked. Every field defaults
    to its enum default when the ``UserPreferences`` row is absent (pre-existing
    users), so the missing-row state is always well-defined.
    """
    preferences: User_Preferences | None = current_user.preferences
    theme = preferences.theme if preferences is not None else Theme.SYSTEM
    default_view = (
        preferences.default_view if preferences is not None else ViewMode.LIST
    )
    default_sort = (
        preferences.default_sort if preferences is not None else SortOrder.NEWEST
    )
    density = preferences.density if preferences is not None else Density.COMFORTABLE
    date_format = preferences.date_format if preferences is not None else DateFormat.ISO
    return {
        "display_theme": theme.value,
        "display_default_view": default_view.value,
        "display_default_sort": default_sort.value,
        "display_density": density.value,
        "display_date_format": date_format.value,
    }


def apply_preferences_change(
    *,
    user_id: int,
    theme: Theme,
    default_view: ViewMode,
    default_sort: SortOrder,
    density: Density,
    date_format: DateFormat,
) -> FlaskResponse:
    """Persist the authenticated user's display/view preferences, creating the
    1:1 ``UserPreferences`` row on first save.

    Guard order mirrors ``apply_username_change``'s check-then-mutate order so a
    rejected/no-op attempt never touches the session: self-ownership (403) →
    snapshot-then-compare no-op (200 ``No change``, BEFORE any mutation, so no
    row is created for a no-op on a pre-existing user) → create-or-update +
    commit (200 ``Success``). Enum-membership validation already happened in the
    request schema, so every incoming value here is a valid enum member.
    """
    # (1) Self-ownership: the URL user_id must be the acting user.
    if user_id != current_user.id:
        return build_message_error_response(
            message=USER_FAILURE.NOT_AUTHORIZED,
            error_code=PreferencesErrorCodes.INVALID_FORM_INPUT,
            status_code=403,
        )

    # (2) Snapshot-then-compare no-op check, BEFORE any mutation. Read the
    # existing values first (each preference's enum default when the row is None),
    # and short-circuit when every field matches — no row is created and nothing
    # is added to the session on this path.
    preferences: User_Preferences | None = current_user.preferences
    existing_theme = preferences.theme if preferences is not None else Theme.SYSTEM
    existing_default_view = (
        preferences.default_view if preferences is not None else ViewMode.LIST
    )
    existing_default_sort = (
        preferences.default_sort if preferences is not None else SortOrder.NEWEST
    )
    existing_density = (
        preferences.density if preferences is not None else Density.COMFORTABLE
    )
    existing_date_format = (
        preferences.date_format if preferences is not None else DateFormat.ISO
    )

    if (
        existing_theme == theme
        and existing_default_view == default_view
        and existing_default_sort == default_sort
        and existing_density == density
        and existing_date_format == date_format
    ):
        return APIResponse(
            status_code=200,
            data=UpdatePreferencesResponseSchema(
                theme=theme.value,
                default_view=default_view.value,
                default_sort=default_sort.value,
                density=density.value,
                date_format=date_format.value,
                status=STD_JSON.NO_CHANGE,
                message=PREFERENCES_CHANGE_NO_CHANGE,
            ),
        ).to_response()

    # (3) Only past the no-op check, create-or-update the row. ``preferences`` may
    # still be None here (pre-existing user's first save) → instantiate and add.
    if preferences is None:
        preferences = User_Preferences(user_id=current_user.id)
        db.session.add(preferences)
    preferences.theme = theme
    preferences.default_view = default_view
    preferences.default_sort = default_sort
    preferences.density = density
    preferences.date_format = date_format
    db.session.commit()

    return APIResponse(
        status_code=200,
        data=UpdatePreferencesResponseSchema(
            theme=theme.value,
            default_view=default_view.value,
            default_sort=default_sort.value,
            density=density.value,
            date_format=date_format.value,
            status=STD_JSON.SUCCESS,
            message=PREFERENCES_CHANGE_SUCCESS,
        ),
    ).to_response()
