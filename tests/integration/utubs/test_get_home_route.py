import json
import re
from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import db
from backend.models.user_preferences import (
    DateFormat,
    Density,
    SortOrder,
    Theme,
    User_Preferences,
    ViewMode,
)
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.utils.all_routes import ROUTES
from backend.utils.strings.utub_strs import (
    MOBILE_PANEL_QUERY_PARAM,
    UTUB_ID_QUERY_PARAM,
)
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.utubs

# Extracts the JSON payload rendered into the home page's #user-preferences-data
# script tag, mirroring the #app-config extraction in test_admin_routes_gating.py.
_USER_PREFERENCES_PATTERN = re.compile(
    rb'<script id="user-preferences-data" type="application/json">\s*(\{.*?\})\s*</script>',
    re.DOTALL,
)


def test_get_invalid_utub_on_home_page(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server resopnds with a 404 message

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    for utubid in ("5/asdf", "5.1", "9.abc", "-1"):
        client, _, _, _ = login_first_user_without_register
        url_to_get = url_for(ROUTES.UTUBS.HOME) + f"?{UTUB_ID_QUERY_PARAM}={utubid}"

        response = client.get(url_to_get)

        assert response.status_code == 404


def test_get_nonexistent_utub_on_home_page(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server resopnds with a 404 message

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    for utubid in (
        2147483648,
        999999,
    ):
        client, _, _, _ = login_first_user_without_register
        url_to_get = url_for(ROUTES.UTUBS.HOME) + f"?{UTUB_ID_QUERY_PARAM}={utubid}"

        response = client.get(url_to_get)
        assert response.status_code == 404


def test_get_home_page(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server responds with appropriate HTML

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, user, _ = login_first_user_without_register
    logged_in_username = user.username
    url_to_get = url_for(ROUTES.UTUBS.HOME)

    response = client.get(url_to_get)
    assert response.status_code == 200
    assert (
        f'<b id="loggedInAsHeader">Logged in as <span class="navLoggedInAsUsername">{logged_in_username}</span></b>'.encode()
        in response.data
    )


def test_home_page_preferences_context_reflects_stored_row(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged-in user WITH a stored UserPreferences row
    WHEN they request /home
    THEN the rendered #user-preferences-data script tag's payload reflects each
        stored preference's `.value` string (build_display_preferences_context
        has-a-row path, end-to-end through the rendered HTML).
    """
    client, _, user, app = login_first_user_without_register
    with app.app_context():
        db.session.add(
            User_Preferences(
                user_id=user.id,
                theme=Theme.DARK,
                default_view=ViewMode.CARDS,
                default_sort=SortOrder.TITLE_AZ,
                density=Density.COMPACT,
                date_format=DateFormat.EU,
            )
        )
        db.session.commit()

    response = client.get(url_for(ROUTES.UTUBS.HOME))
    assert response.status_code == 200

    match = _USER_PREFERENCES_PATTERN.search(response.data)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload["display_theme"] == Theme.DARK.value
    assert payload["display_default_view"] == ViewMode.CARDS.value
    assert payload["display_default_sort"] == SortOrder.TITLE_AZ.value
    assert payload["display_density"] == Density.COMPACT.value
    assert payload["display_date_format"] == DateFormat.EU.value


def test_home_page_preferences_context_defaults_when_no_row(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged-in user with NO stored UserPreferences row
    WHEN they request /home
    THEN the rendered #user-preferences-data payload equals each preference
        enum's default (build_display_preferences_context None-row path,
        exercised end-to-end through the rendered HTML).
    """
    client, _, _, _ = login_first_user_without_register

    response = client.get(url_for(ROUTES.UTUBS.HOME))
    assert response.status_code == 200

    match = _USER_PREFERENCES_PATTERN.search(response.data)
    assert match is not None
    payload = json.loads(match.group(1))
    assert payload["display_theme"] == Theme.SYSTEM.value
    assert payload["display_default_view"] == ViewMode.LIST.value
    assert payload["display_default_sort"] == SortOrder.NEWEST.value
    assert payload["display_density"] == Density.COMFORTABLE.value
    assert payload["display_date_format"] == DateFormat.ISO.value


def test_get_home_page_when_not_in_utub(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server responds with appropriate HTML

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, user, app = login_first_user_without_register
    with app.app_context():
        member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != user.id
        ).first()
        utub_id_not_member_of = member.utub_id

    url_to_get = (
        url_for(ROUTES.UTUBS.HOME) + f"?{UTUB_ID_QUERY_PARAM}={utub_id_not_member_of}"
    )

    response = client.get(url_to_get)
    assert response.status_code == 302
    assert is_string_in_logs(
        f"User={user.id} not a member of UTub.id={utub_id_not_member_of}",
        caplog.records,
    )


def test_get_home_page_when_in_utub(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server responds with appropriate HTML

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, user, app = login_first_user_without_register
    with app.app_context():
        member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == user.id
        ).first()
        utub_id_not_member_of = member.utub_id

    url_to_get = (
        url_for(ROUTES.UTUBS.HOME) + f"?{UTUB_ID_QUERY_PARAM}={utub_id_not_member_of}"
    )

    response = client.get(url_to_get)
    assert response.status_code == 200


def test_get_home_page_with_panel_param_when_in_utub(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is a member of a UTub, on mobile where the panel is
        persisted into the URL as `?UTubID=<id>&panel=<panel>`
    WHEN the user reloads that URL (a real server round-trip)
    THEN the server accepts the extra `panel` query param and responds 200
        (the mobile panel-persistence feature relies on the reload succeeding)
    """
    client, _, user, app = login_first_user_without_register
    with app.app_context():
        member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == user.id
        ).first()
        utub_id_member_of = member.utub_id

    for panel in ("utubs", "urls", "members"):
        url_to_get = (
            url_for(ROUTES.UTUBS.HOME)
            + f"?{UTUB_ID_QUERY_PARAM}={utub_id_member_of}"
            + f"&{MOBILE_PANEL_QUERY_PARAM}={panel}"
        )

        response = client.get(url_to_get)
        assert response.status_code == 200


def test_get_home_page_with_panel_param_and_no_utub_id(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user reloading a panel-only mobile URL (`?panel=<panel>`) with no
        UTubID — a graceful-degradation / stale-link case
    WHEN the server receives the request
    THEN it renders the home page (200) rather than erroring; the client
        resolves the no-UTub state
    """
    client, _, _, _ = login_first_user_without_register

    for panel in ("utubs", "urls", "members"):
        url_to_get = url_for(ROUTES.UTUBS.HOME) + f"?{MOBILE_PANEL_QUERY_PARAM}={panel}"

        response = client.get(url_to_get)
        assert response.status_code == 200


def test_get_home_page_rejects_unrecognized_and_repeated_params(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the /home route recognizes only UTubID and the mobile panel param
    WHEN the user requests it with an unrecognized param alongside a recognized
        one, or with a repeated recognized param
    THEN the server rejects the request with a 404
    """
    client, _, user, app = login_first_user_without_register
    with app.app_context():
        member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == user.id
        ).first()
        utub_id_member_of = member.utub_id

    invalid_query_strings = (
        f"?{UTUB_ID_QUERY_PARAM}={utub_id_member_of}&bogus=1",
        f"?{MOBILE_PANEL_QUERY_PARAM}=urls&{MOBILE_PANEL_QUERY_PARAM}=members",
        f"?{UTUB_ID_QUERY_PARAM}={utub_id_member_of}"
        f"&{MOBILE_PANEL_QUERY_PARAM}=urls&extra=1",
    )

    for invalid_query_string in invalid_query_strings:
        url_to_get = url_for(ROUTES.UTUBS.HOME) + invalid_query_string

        response = client.get(url_to_get)
        assert response.status_code == 404


def test_get_invalid_utub_on_home_page_logs(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server logs are correct
    """
    client, _, user, _ = login_first_user_without_register

    invalid_query_params_and_logs = {
        f"?{UTUB_ID_QUERY_PARAM}=9.abc": f"Invalid UTub.id=9.abc for User={user.id}",
        f"?{UTUB_ID_QUERY_PARAM}=1&{UTUB_ID_QUERY_PARAM}=2": "Too many query parameters",
        "?abc=1": f"User={user.id} | Unrecognized query parameter(s): ['abc']",
    }

    for invalid_param, log_msg in invalid_query_params_and_logs.items():
        url_to_get = url_for(ROUTES.UTUBS.HOME) + invalid_param

        response = client.get(url_to_get)

        assert response.status_code == 404
        assert is_string_in_logs(log_msg, caplog.records)
