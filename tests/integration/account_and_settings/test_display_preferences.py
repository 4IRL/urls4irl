"""Integration tests for the authenticated update-preferences endpoint
(``PUT /users/<id>/preferences``).

Copies the ``test_change_username.py`` structure: happy path (persisted), no-op
(``No change`` on a pre-existing user whose defaults already match), 403
self-ownership, 400 bad enum, and the missing-CSRF 403 HTML page.
"""

from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.models.user_preferences import (
    DateFormat,
    Density,
    SortOrder,
    Theme,
    ViewMode,
)
from backend.models.users import Users
from backend.schemas.users import UpdatePreferencesResponseSchema
from backend.users.constants import PreferencesErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS as M
from backend.utils.strings.user_strs import (
    PREFERENCES_CHANGE_NO_CHANGE,
    PREFERENCES_CHANGE_SUCCESS,
)
from tests.integration.utils import assert_response_conforms_to_schema

pytestmark = pytest.mark.account_and_support

# Non-default values (so the happy-path write is observably a change from the
# enum defaults a pre-existing user has).
_VALID_PAYLOAD = {
    M.THEME: Theme.DARK.value,
    M.DEFAULT_VIEW: ViewMode.CARDS.value,
    M.DEFAULT_SORT: SortOrder.OLDEST.value,
    M.DENSITY: Density.COMPACT.value,
    M.DATE_FORMAT: DateFormat.US.value,
}

# The enum defaults every pre-existing (no-row) user carries — a PUT of these is
# a no-op.
_DEFAULT_PAYLOAD = {
    M.THEME: Theme.SYSTEM.value,
    M.DEFAULT_VIEW: ViewMode.LIST.value,
    M.DEFAULT_SORT: SortOrder.NEWEST.value,
    M.DENSITY: Density.COMFORTABLE.value,
    M.DATE_FORMAT: DateFormat.ISO.value,
}

_EXPECTED_KEYS = {
    M.THEME,
    M.DEFAULT_VIEW,
    M.DEFAULT_SORT,
    M.DENSITY,
    M.DATE_FORMAT,
    STD_JSON.STATUS,
    STD_JSON.MESSAGE,
}


def test_update_preferences_success_creates_row_and_returns_envelope(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A valid PUT returns 200 with the echo envelope and creates/persists the
    1:1 UserPreferences row with the submitted values."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.UPDATE_PREFERENCES, user_id=user_id),
        json=_VALID_PAYLOAD,
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()

    assert_response_conforms_to_schema(
        response_json,
        UpdatePreferencesResponseSchema,
        expected_keys=_EXPECTED_KEYS,
    )
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == PREFERENCES_CHANGE_SUCCESS
    assert response_json[M.THEME] == Theme.DARK.value
    assert response_json[M.DEFAULT_VIEW] == ViewMode.CARDS.value
    assert response_json[M.DEFAULT_SORT] == SortOrder.OLDEST.value
    assert response_json[M.DENSITY] == Density.COMPACT.value
    assert response_json[M.DATE_FORMAT] == DateFormat.US.value

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.preferences is not None
        assert refreshed.preferences.theme == Theme.DARK
        assert refreshed.preferences.default_view == ViewMode.CARDS
        assert refreshed.preferences.default_sort == SortOrder.OLDEST
        assert refreshed.preferences.density == Density.COMPACT
        assert refreshed.preferences.date_format == DateFormat.US


def test_update_preferences_no_op_returns_no_change_and_creates_no_row(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT of the enum defaults for a pre-existing (no-row) user short-circuits
    as ``No change`` and creates no UserPreferences row."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.UPDATE_PREFERENCES, user_id=user_id),
        json=_DEFAULT_PAYLOAD,
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert response_json[STD_JSON.MESSAGE] == PREFERENCES_CHANGE_NO_CHANGE

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.preferences is None


def test_update_preferences_self_ownership_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT whose URL user_id is not the acting user is rejected 403."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.UPDATE_PREFERENCES, user_id=user.id + 999),
        json=_VALID_PAYLOAD,
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == PreferencesErrorCodes.INVALID_FORM_INPUT
    )


def test_update_preferences_invalid_enum_returns_400_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """An out-of-set enum value fails schema validation → 400 with a ``theme``
    field error, before the service runs."""
    client, csrf_token, user, _ = login_first_user_with_register

    bad_payload = dict(_VALID_PAYLOAD)
    bad_payload[M.THEME] = "rainbow"

    response = client.put(
        url_for(ROUTES.USERS.UPDATE_PREFERENCES, user_id=user.id),
        json=bad_payload,
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert M.THEME in response_json[STD_JSON.ERRORS]


def test_update_preferences_missing_csrf_returns_403_html(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT without a CSRF token is rejected 403 with the HTML error page."""
    client, _, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.UPDATE_PREFERENCES, user_id=user.id),
        json=_VALID_PAYLOAD,
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
