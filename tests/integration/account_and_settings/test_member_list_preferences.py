"""Integration tests for the partial member-list preferences endpoint
(``PATCH /users/preferences/members``).
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
    MemberSort,
    SortOrder,
    Theme,
    User_Preferences,
    UtubSort,
    ViewMode,
)
from backend.models.users import Users
from backend.schemas.users import UpdateMemberListPreferencesResponseSchema
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

_LITERAL_PATH = "/users/preferences/members"
_UTUB_PATH = "/users/preferences/utubs"

_EXPECTED_KEYS = {MODELS.MEMBER_SORT, STD_JSON.STATUS, STD_JSON.MESSAGE}

_COLUMNS = (
    "theme",
    "default_view",
    "default_sort",
    "density",
    "date_format",
    "utub_sort",
    "show_row_counts",
    "show_list_totals",
    "member_sort",
)


def _patch(
    client: FlaskClient, csrf_token: str, body: Any, path: str = _LITERAL_PATH
) -> TestResponse:
    return client.patch(path, json=body, headers={"X-CSRFToken": csrf_token})


def _stored_row(app: Flask, user_id: int) -> dict[str, Any] | None:
    """Re-read the stored preferences row (None when absent)."""
    with app.app_context():
        db.session.expire_all()
        row = User_Preferences.query.filter_by(user_id=user_id).first()
        if row is None:
            return None
        return {column: getattr(row, column) for column in _COLUMNS}


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
                member_sort=MemberSort.ROLE_THEN_NAME,
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
    "member_sort": MemberSort.ROLE_THEN_NAME,
}


def test_first_save_creates_row_with_default_other_columns(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    assert _stored_row(app, user.id) is None

    response = _patch(client, csrf_token, {"memberSort": "recently_joined"})

    assert response.status_code == 200
    body = response.get_json()
    assert_response_conforms_to_schema(
        body, UpdateMemberListPreferencesResponseSchema, expected_keys=_EXPECTED_KEYS
    )
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == PREFERENCES_CHANGE_SUCCESS
    assert body[MODELS.MEMBER_SORT] == "recently_joined"
    assert _stored_row(app, user.id) == {
        "theme": Theme.SYSTEM,
        "default_view": ViewMode.LIST,
        "default_sort": SortOrder.NEWEST,
        "density": Density.COMFORTABLE,
        "date_format": DateFormat.ISO,
        "utub_sort": UtubSort.RECENT_ACTIVITY,
        "show_row_counts": False,
        "show_list_totals": True,
        "member_sort": MemberSort.RECENTLY_JOINED,
    }


def test_save_on_existing_row_leaves_other_columns(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, {"memberSort": "name_az"})

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[MODELS.MEMBER_SORT] == "name_az"
    assert _stored_row(app, user.id) == dict(_SEEDED, member_sort=MemberSort.NAME_AZ)


def test_same_value_with_row_returns_no_change(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, {"memberSort": "role_then_name"})

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert body[STD_JSON.MESSAGE] == PREFERENCES_CHANGE_NO_CHANGE
    assert body[MODELS.MEMBER_SORT] == "role_then_name"
    assert _stored_row(app, user.id) == _SEEDED


def test_default_value_without_row_creates_no_row(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(client, csrf_token, {"memberSort": "name_az"})

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert body[MODELS.MEMBER_SORT] == "name_az"
    assert _stored_row(app, user.id) is None


def test_utub_list_route_does_not_change_member_sort(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, {"utubSort": "oldest_created"}, _UTUB_PATH)

    assert response.status_code == 200
    assert _stored_row(app, user.id) == dict(_SEEDED, utub_sort=UtubSort.OLDEST_CREATED)


def test_member_route_does_not_change_utub_list_columns(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    with app.test_request_context():
        assert url_for(ROUTES.USERS.UPDATE_MEMBER_LIST_PREFERENCES) == _LITERAL_PATH

    _patch(client, csrf_token, {"memberSort": "recently_joined"})
    row = _stored_row(app, user.id)

    assert row is not None
    assert row["utub_sort"] == UtubSort.RECENT_ACTIVITY
    assert row["show_row_counts"] is False
    assert row["show_list_totals"] is True


_BAD_BODIES = [
    {},
    {"bogus": 1},
    {"memberSort": "name_az", "bogus": 1},
    {"memberSort": "rainbow"},
    {"memberSort": None},
    {"memberSort": 1},
    {"memberSort": ""},
]


@pytest.mark.parametrize("bad_body", _BAD_BODIES)
def test_invalid_bodies_return_400_and_write_nothing(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    bad_body: dict[str, Any],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(client, csrf_token, bad_body)

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == PreferencesErrorCodes.INVALID_FORM_INPUT
    )
    assert _stored_row(app, user.id) is None


@pytest.mark.parametrize("bad_body", _BAD_BODIES)
def test_invalid_bodies_leave_existing_row_unchanged(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    bad_body: dict[str, Any],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, bad_body)

    assert response.status_code == 400
    assert _stored_row(app, user.id) == _SEEDED


def test_missing_csrf_returns_403_and_writes_nothing(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, user, app = login_first_user_with_register

    response = client.patch(_LITERAL_PATH, json={"memberSort": "recently_joined"})

    assert response.status_code == 403
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert _stored_row(app, user.id) is None


@pytest.mark.parametrize("sort_value", [sort.value for sort in MemberSort])
def test_echoes_each_sort_value(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    sort_value: str,
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, {"memberSort": sort_value})

    assert response.status_code == 200
    assert response.get_json()[MODELS.MEMBER_SORT] == sort_value


@pytest.mark.parametrize("bad_body", [None, [], "name_az"])
def test_non_object_json_bodies_return_400_and_write_nothing(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    bad_body: Any,
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(client, csrf_token, bad_body)

    assert response.status_code == 400
    assert _stored_row(app, user.id) is None


def test_wrong_csrf_returns_403_and_writes_nothing(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, _, user, app = login_first_user_with_register

    response = _patch(client, "not-a-real-token", {"memberSort": "recently_joined"})

    assert response.status_code == 403
    assert _stored_row(app, user.id) is None


def test_writes_only_the_logged_in_users_row(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    with app.app_context():
        other_ids = [
            other.id for other in Users.query.filter(Users.id != user.id).all()
        ]
        for other_id in other_ids:
            db.session.add(User_Preferences(user_id=other_id))
        db.session.commit()

    response = _patch(client, csrf_token, {"memberSort": "recently_joined"})

    assert response.status_code == 200
    for other_id in other_ids:
        other_row = _stored_row(app, other_id)
        assert other_row is not None
        assert other_row["member_sort"] == MemberSort.NAME_AZ
    row = _stored_row(app, user.id)
    assert row is not None
    assert row["member_sort"] == MemberSort.RECENTLY_JOINED


def test_anonymous_redirects_to_splash_with_next(client: FlaskClient) -> None:
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = _patch(client, csrf_token, {"memberSort": "name_az"})

    assert response.status_code == 302
    location = urlsplit(response.location)
    assert location.path == "/"
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

    response = _patch(client, csrf_token, {"memberSort": "recently_joined"})

    assert response.status_code == 302
    location = urlsplit(response.location)
    assert location.path == "/"
    assert "next" not in parse_qs(location.query)
    assert _stored_row(app, user_id) is None
