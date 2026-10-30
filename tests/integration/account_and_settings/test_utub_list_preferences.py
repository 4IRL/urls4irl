"""Integration tests for the partial UTub-list preferences endpoint
(``PATCH /users/preferences/utubs``).
"""

from typing import Any, Tuple
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from backend import db
from backend.models.user_preferences import (
    DateFormat,
    Density,
    SortOrder,
    Theme,
    User_Preferences,
    UtubSort,
    ViewMode,
)
from backend.models.users import Users
from backend.schemas.users import UpdateUtubListPreferencesResponseSchema
from backend.users.constants import PreferencesErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.user_strs import (
    PREFERENCES_CHANGE_NO_CHANGE,
    PREFERENCES_CHANGE_SUCCESS,
)
from tests.integration.utils import assert_response_conforms_to_schema
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support

_LITERAL_PATH = "/users/preferences/utubs"

_EXPECTED_KEYS = {
    MODELS.UTUB_SORT,
    MODELS.SHOW_ROW_COUNTS,
    MODELS.SHOW_LIST_TOTALS,
    STD_JSON.STATUS,
    STD_JSON.MESSAGE,
}

# Resolved defaults for a user with no preferences row.
_DEFAULT_SORT = UtubSort.RECENT_ACTIVITY.value
_DEFAULT_ROW_COUNTS = False
_DEFAULT_LIST_TOTALS = True


def _patch(client: FlaskClient, csrf_token: str, body: Any, app: Flask) -> TestResponse:
    url = url_for(ROUTES.USERS.UPDATE_UTUB_LIST_PREFERENCES)
    assert url == _LITERAL_PATH
    return client.patch(url, json=body, headers={"X-CSRFToken": csrf_token})


def _stored_row(app: Flask, user_id: int) -> dict[str, Any] | None:
    """Re-read the stored preferences row (None when absent)."""
    with app.app_context():
        db.session.expire_all()
        row = User_Preferences.query.filter_by(user_id=user_id).first()
        if row is None:
            return None
        return {
            "theme": row.theme,
            "default_view": row.default_view,
            "default_sort": row.default_sort,
            "density": row.density,
            "date_format": row.date_format,
            "utub_sort": row.utub_sort,
            "show_row_counts": row.show_row_counts,
            "show_list_totals": row.show_list_totals,
        }


def _seed_row(app: Flask, user_id: int) -> None:
    """Seed a non-default row (every field distinct from its default)."""
    with app.app_context():
        db.session.add(
            User_Preferences(
                user_id=user_id,
                theme=Theme.DARK,
                default_view=ViewMode.CARDS,
                default_sort=SortOrder.OLDEST,
                density=Density.COMPACT,
                date_format=DateFormat.US,
                utub_sort=UtubSort.NAME_AZ,
                show_row_counts=True,
                show_list_totals=False,
            )
        )
        db.session.commit()


_SEEDED = {
    "theme": Theme.DARK,
    "default_view": ViewMode.CARDS,
    "default_sort": SortOrder.OLDEST,
    "density": Density.COMPACT,
    "date_format": DateFormat.US,
    "utub_sort": UtubSort.NAME_AZ,
    "show_row_counts": True,
    "show_list_totals": False,
}


def test_only_sort_changes_only_sort_and_creates_row(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = _patch(client, csrf_token, {"utubSort": "name_az"}, app)

    assert response.status_code == 200
    body = response.get_json()
    assert_response_conforms_to_schema(
        body, UpdateUtubListPreferencesResponseSchema, expected_keys=_EXPECTED_KEYS
    )
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == PREFERENCES_CHANGE_SUCCESS
    assert body[MODELS.UTUB_SORT] == "name_az"
    assert body[MODELS.SHOW_ROW_COUNTS] is _DEFAULT_ROW_COUNTS
    assert body[MODELS.SHOW_LIST_TOTALS] is _DEFAULT_LIST_TOTALS

    row = _stored_row(app, user_id)
    assert row is not None
    assert row["utub_sort"] == UtubSort.NAME_AZ
    assert row["show_row_counts"] is _DEFAULT_ROW_COUNTS
    assert row["show_list_totals"] is _DEFAULT_LIST_TOTALS
    assert row["theme"] == Theme.SYSTEM
    assert row["default_view"] == ViewMode.LIST
    assert row["default_sort"] == SortOrder.NEWEST
    assert row["density"] == Density.COMFORTABLE
    assert row["date_format"] == DateFormat.ISO


def test_only_sort_leaves_other_stored_values(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, {"utubSort": "oldest_created"}, app)

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    expected = dict(_SEEDED, utub_sort=UtubSort.OLDEST_CREATED)
    assert _stored_row(app, user.id) == expected


def test_no_op_with_existing_row_returns_no_change(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(
        client,
        csrf_token,
        {"utubSort": "name_az", "showRowCounts": True, "showListTotals": False},
        app,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert body[STD_JSON.MESSAGE] == PREFERENCES_CHANGE_NO_CHANGE
    assert _stored_row(app, user.id) == _SEEDED


def test_no_op_defaults_without_row_creates_no_row(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(
        client,
        csrf_token,
        {
            "utubSort": _DEFAULT_SORT,
            "showRowCounts": _DEFAULT_ROW_COUNTS,
            "showListTotals": _DEFAULT_LIST_TOTALS,
        },
        app,
    )

    assert response.status_code == 200
    body = response.get_json()
    assert_response_conforms_to_schema(
        body, UpdateUtubListPreferencesResponseSchema, expected_keys=_EXPECTED_KEYS
    )
    assert body[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert body[MODELS.UTUB_SORT] == _DEFAULT_SORT
    assert body[MODELS.SHOW_ROW_COUNTS] is _DEFAULT_ROW_COUNTS
    assert body[MODELS.SHOW_LIST_TOTALS] is _DEFAULT_LIST_TOTALS
    assert _stored_row(app, user.id) is None


def test_mixed_body_writes_only_changed_field(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(
        client,
        csrf_token,
        {"utubSort": "last_opened", "showRowCounts": True},
        app,
    )

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert _stored_row(app, user.id) == dict(_SEEDED, utub_sort=UtubSort.LAST_OPENED)


def test_echo_uses_resolved_values_not_request_values(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, {"showRowCounts": False}, app)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[MODELS.UTUB_SORT] == "name_az"
    assert body[MODELS.SHOW_ROW_COUNTS] is False
    assert body[MODELS.SHOW_LIST_TOTALS] is False
    assert _stored_row(app, user.id) == dict(_SEEDED, show_row_counts=False)


@pytest.mark.parametrize(
    "bad_body",
    [
        {},
        {"bogus": 1},
        {"utubSort": "name_az", "bogus": 1},
        {"showRowCounts": "true"},
        {"showRowCounts": 1},
        {"showListTotals": "false"},
        {"showListTotals": 0},
        {"utubSort": "rainbow"},
        {"utubSort": None},
        {"showRowCounts": None},
        {"showListTotals": None},
        {"utubSort": "name_az", "showRowCounts": None},
    ],
)
def test_invalid_bodies_return_400_and_write_nothing(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    bad_body: dict[str, Any],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(client, csrf_token, bad_body, app)

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == PreferencesErrorCodes.INVALID_FORM_INPUT
    )
    assert _stored_row(app, user.id) is None


@pytest.mark.parametrize(
    "bad_body",
    [
        {},
        {"bogus": 1},
        {"showRowCounts": "true"},
        {"utubSort": "rainbow"},
        {"utubSort": None},
        {"showRowCounts": None},
        {"showListTotals": None},
    ],
)
def test_invalid_bodies_leave_existing_row_unchanged(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    bad_body: dict[str, Any],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, bad_body, app)

    assert response.status_code == 400
    assert _stored_row(app, user.id) == _SEEDED


def test_missing_csrf_returns_403_and_writes_nothing(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, user, app = login_first_user_with_register

    response = client.patch(_LITERAL_PATH, json={"utubSort": "name_az"})

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert _stored_row(app, user.id) is None


def test_missing_csrf_leaves_existing_row_unchanged(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = client.patch(_LITERAL_PATH, json={"utubSort": "oldest_created"})

    assert response.status_code == 403
    assert _stored_row(app, user.id) == _SEEDED


def test_partial_no_op_echoes_all_stored_values(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, {"utubSort": "name_az"}, app)

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert body[MODELS.UTUB_SORT] == "name_az"
    assert body[MODELS.SHOW_ROW_COUNTS] is True
    assert body[MODELS.SHOW_LIST_TOTALS] is False
    assert _stored_row(app, user.id) == _SEEDED


def test_anonymous_redirects_to_splash_with_next(client: FlaskClient) -> None:
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.patch(
        _LITERAL_PATH,
        json={"utubSort": "name_az"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302
    location = urlsplit(response.location)
    assert location.path == "/"
    # The unauthorized_handler appends a trailing "?" to the next target.
    assert [
        target.rstrip("?") for target in parse_qs(location.query).get("next", [])
    ] == [_LITERAL_PATH]


def test_unvalidated_email_redirects_to_splash_and_writes_nothing(
    login_unvalidated_user: Tuple[FlaskClient, Users, Flask],
) -> None:
    client, user, app = login_unvalidated_user
    user_id = user.id

    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.patch(
        _LITERAL_PATH,
        json={"utubSort": "name_az"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302
    location = urlsplit(response.location)
    # email_validation_required redirects to the splash page (which then shows
    # the confirm-email state), without a next target.
    assert location.path == "/"
    assert "next" not in parse_qs(location.query)
    assert _stored_row(app, user_id) is None


def test_existing_put_preferences_still_round_trips(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Regression: the settings page PUT is unchanged and leaves the
    UTub-list preferences at their stored values."""
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = client.put(
        url_for(ROUTES.USERS.UPDATE_PREFERENCES, user_id=user.id),
        json={
            MODELS.THEME: Theme.LIGHT.value,
            MODELS.DEFAULT_VIEW: ViewMode.LIST.value,
            MODELS.DEFAULT_SORT: SortOrder.NEWEST.value,
            MODELS.DENSITY: Density.COMFORTABLE.value,
            MODELS.DATE_FORMAT: DateFormat.EU.value,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    row = _stored_row(app, user.id)
    assert row is not None
    assert row["theme"] == Theme.LIGHT
    assert row["date_format"] == DateFormat.EU
    assert row["utub_sort"] == UtubSort.NAME_AZ
    assert row["show_row_counts"] is True
    assert row["show_list_totals"] is False
