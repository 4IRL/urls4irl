"""Integration tests for the partial tag display preferences endpoint
(``PATCH /users/preferences/tags``).
"""

from typing import Any, Tuple
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from backend import db
from backend.models.user_preferences import (
    CollapsedTagsStyle,
    TagCountStyle,
    TagMatchMode,
    TagSort,
    User_Preferences,
)
from backend.models.users import Users
from backend.schemas.users import UpdateTagDisplayPreferencesResponseSchema
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

_LITERAL_PATH = "/users/preferences/tags"

_EXPECTED_KEYS = {
    MODELS.TAG_SORT,
    MODELS.TAG_MATCH_MODE,
    MODELS.TAG_COUNT_STYLE,
    MODELS.SHOW_TAGS_ON_COLLAPSED,
    MODELS.COLLAPSED_TAGS_STYLE,
    MODELS.TAG_DROP_OPENS_URL,
    STD_JSON.STATUS,
    STD_JSON.MESSAGE,
}

_DEFAULTS = {
    "tag_sort": TagSort.MOST_IN_VIEW,
    "tag_match_mode": TagMatchMode.ALL,
    "tag_count_style": TagCountStyle.IN_VIEW_TOTAL,
    "show_tags_on_collapsed": False,
    "collapsed_tags_style": CollapsedTagsStyle.ONE_LINE,
    "tag_drop_opens_url": True,
}

_SEEDED = {
    "tag_sort": TagSort.NAME_AZ,
    "tag_match_mode": TagMatchMode.ANY,
    "tag_count_style": TagCountStyle.HIDDEN,
    "show_tags_on_collapsed": True,
    "collapsed_tags_style": CollapsedTagsStyle.ALL,
    "tag_drop_opens_url": False,
}


def _patch(client: FlaskClient, csrf_token: str, body: Any) -> TestResponse:
    url = url_for(ROUTES.USERS.UPDATE_TAG_DISPLAY_PREFERENCES)
    assert url == _LITERAL_PATH
    return client.patch(url, json=body, headers={"X-CSRFToken": csrf_token})


def _stored_row(app: Flask, user_id: int) -> dict[str, Any] | None:
    """Re-read the stored tag columns (None when no row exists)."""
    with app.app_context():
        db.session.expire_all()
        row = User_Preferences.query.filter_by(user_id=user_id).first()
        if row is None:
            return None
        return {key: getattr(row, key) for key in _DEFAULTS}


def _seed_row(app: Flask, user_id: int) -> None:
    with app.app_context():
        db.session.add(User_Preferences(user_id=user_id, **_SEEDED))
        db.session.commit()


def test_single_field_creates_row_with_other_defaults(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(client, csrf_token, {"tagSort": "name_az"})

    assert response.status_code == 200
    body = response.get_json()
    assert_response_conforms_to_schema(
        body,
        UpdateTagDisplayPreferencesResponseSchema,
        expected_keys=_EXPECTED_KEYS,
    )
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == PREFERENCES_CHANGE_SUCCESS
    assert body[MODELS.TAG_SORT] == "name_az"
    assert body[MODELS.TAG_MATCH_MODE] == "all"
    assert body[MODELS.TAG_COUNT_STYLE] == "in_view_total"
    assert body[MODELS.SHOW_TAGS_ON_COLLAPSED] is False
    assert body[MODELS.COLLAPSED_TAGS_STYLE] == "one_line"
    assert body[MODELS.TAG_DROP_OPENS_URL] is True
    assert _stored_row(app, user.id) == dict(_DEFAULTS, tag_sort=TagSort.NAME_AZ)


def test_all_six_fields_write(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(
        client,
        csrf_token,
        {
            "tagSort": "name_az",
            "tagMatchMode": "any",
            "tagCountStyle": "hidden",
            "showTagsOnCollapsed": True,
            "collapsedTagsStyle": "all",
            "tagDropOpensUrl": False,
        },
    )

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert _stored_row(app, user.id) == _SEEDED


@pytest.mark.parametrize(
    "body, column, expected",
    [
        ({"tagSort": "newest"}, "tag_sort", TagSort.NEWEST),
        ({"tagMatchMode": "any"}, "tag_match_mode", TagMatchMode.ANY),
        ({"tagCountStyle": "hidden"}, "tag_count_style", TagCountStyle.HIDDEN),
        ({"showTagsOnCollapsed": True}, "show_tags_on_collapsed", True),
        ({"collapsedTagsStyle": "all"}, "collapsed_tags_style", CollapsedTagsStyle.ALL),
        ({"tagDropOpensUrl": False}, "tag_drop_opens_url", False),
    ],
)
def test_each_field_alone_changes_only_that_column(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    body: dict[str, Any],
    column: str,
    expected: Any,
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(client, csrf_token, body)

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert _stored_row(app, user.id) == dict(_DEFAULTS, **{column: expected})


def test_write_leaves_another_users_row_untouched(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    with app.app_context():
        db.session.add(
            Users(
                username="otherprefuser",
                email="otherprefuser@example.com",
                plaintext_password="OtherPref123!",
            )
        )
        db.session.commit()
        other_user_id = Users.query.filter_by(username="otherprefuser").one().id
    _seed_row(app, other_user_id)

    response = _patch(client, csrf_token, {"tagSort": "oldest"})

    assert response.status_code == 200
    assert _stored_row(app, other_user_id) == _SEEDED
    assert _stored_row(app, user.id) == dict(_DEFAULTS, tag_sort=TagSort.OLDEST)


def test_partial_write_leaves_other_stored_values(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(client, csrf_token, {"tagSort": "oldest"})

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[MODELS.TAG_MATCH_MODE] == "any"
    assert body[MODELS.TAG_DROP_OPENS_URL] is False
    assert _stored_row(app, user.id) == dict(_SEEDED, tag_sort=TagSort.OLDEST)


def test_no_op_with_existing_row_returns_no_change(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register
    _seed_row(app, user.id)

    response = _patch(
        client, csrf_token, {"tagSort": "name_az", "tagDropOpensUrl": False}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert body[STD_JSON.MESSAGE] == PREFERENCES_CHANGE_NO_CHANGE
    assert body[MODELS.TAG_SORT] == "name_az"
    assert body[MODELS.TAG_MATCH_MODE] == "any"
    assert _stored_row(app, user.id) == _SEEDED


def test_no_op_defaults_without_row_creates_no_row(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    client, csrf_token, user, app = login_first_user_with_register

    response = _patch(
        client,
        csrf_token,
        {"tagSort": "most_in_view", "tagDropOpensUrl": True},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert_response_conforms_to_schema(
        body,
        UpdateTagDisplayPreferencesResponseSchema,
        expected_keys=_EXPECTED_KEYS,
    )
    assert body[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert body[MODELS.TAG_SORT] == "most_in_view"
    assert _stored_row(app, user.id) is None


_BAD_BODIES = [
    {},
    {"bogus": 1},
    {"tagSort": "name_az", "bogus": 1},
    {"tagSort": "rainbow"},
    {"tagMatchMode": "some"},
    {"tagCountStyle": "all"},
    {"collapsedTagsStyle": "none"},
    {"showTagsOnCollapsed": "true"},
    {"showTagsOnCollapsed": 1},
    {"tagDropOpensUrl": "false"},
    {"tagDropOpensUrl": 0},
    {"tagSort": None},
    {"tagMatchMode": None},
    {"tagCountStyle": None},
    {"showTagsOnCollapsed": None},
    {"collapsedTagsStyle": None},
    {"tagDropOpensUrl": None},
    {"tagSort": "name_az", "tagDropOpensUrl": None},
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

    response = client.patch(_LITERAL_PATH, json={"tagSort": "name_az"})

    assert response.status_code == 403
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert _stored_row(app, user.id) is None


def test_anonymous_redirects_to_splash_with_next(client: FlaskClient) -> None:
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.patch(
        _LITERAL_PATH,
        json={"tagSort": "name_az"},
        headers={"X-CSRFToken": csrf_token},
    )

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

    response = client.patch(
        _LITERAL_PATH,
        json={"tagSort": "name_az"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302
    location = urlsplit(response.location)
    assert location.path == "/"
    assert "next" not in parse_qs(location.query)
    assert _stored_row(app, user_id) is None
