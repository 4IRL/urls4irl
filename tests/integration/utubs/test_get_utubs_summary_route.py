from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user
import pytest

from src import db
from src.models.users import Users
from src.models.utub_members import Member_Role, Utub_Members
from src.models.utubs import Utubs
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import UTUB_FORM
from src.utils.strings.model_strs import MODELS
from src.utils.strings.url_validation_strs import URL_VALIDATION
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.utubs


def test_get_utubs_if_has_no_utubs(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, with no UTubs.
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an empty array in the JSON
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json == {MODELS.UTUBS: []}


def test_get_utubs_if_has_one_utub(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, with one UTub.
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an array with one UTub in the JSON
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        all_utubs_in: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).all()
        utub_summary = {
            MODELS.UTUBS: [
                {
                    MODELS.ID: member.to_utub.id,
                    MODELS.NAME: member.to_utub.name,
                    MODELS.MEMBER_ROLE: member.member_role.value,
                }
                for member in all_utubs_in
            ]
        }

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert utub_summary == response.json


def test_get_utubs_if_has_multiple_utubs(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, and is a member of multiple UTubs .
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an array with all utubs in the JSON
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        all_utubs_in: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).all()
        utub_summary = {
            MODELS.UTUBS: [
                {
                    MODELS.ID: member.to_utub.id,
                    MODELS.NAME: member.to_utub.name,
                    MODELS.MEMBER_ROLE: member.member_role.value,
                }
                for member in all_utubs_in
            ]
        }

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert isinstance(response.json, dict)
    assert isinstance(response.json[MODELS.UTUBS], list)
    assert sorted(utub_summary[MODELS.UTUBS], key=lambda x: x[MODELS.ID]) == sorted(
        response.json[MODELS.UTUBS], key=lambda x: x[MODELS.ID]
    )


def test_get_utubs_sorted_based_on_last_updated(
    add_all_utubs_as_user_without_logging_in,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, and is a member of multiple UTubs .
    WHEN the user requests a summary of all
        their UTubs after modifying the UTubs
    THEN verify the response body contains an array with all utubs in the JSON,
        sorted by last updated
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_summary = _get_ordered_utub_summary()

    last_utub_id = int(utub_summary[MODELS.UTUBS][-1][MODELS.ID])
    last_utub_name = str(utub_summary[MODELS.UTUBS][-1][MODELS.NAME])

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert utub_summary == response.json

    utub_name_form = {
        UTUB_FORM.UTUB_NAME: last_utub_name + "88",
        UTUB_FORM.CSRF_TOKEN: csrf_token,
    }

    # Update the name of the last UTub
    response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=last_utub_id),
        data=utub_name_form,
    )
    assert response.status_code == 200

    # Check last UTub is now first
    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200
    with app.app_context():
        utub_summary = _get_ordered_utub_summary()
    assert utub_summary == response.json
    assert utub_summary[MODELS.UTUBS][0][MODELS.ID] == last_utub_id

    middle_utub_id = int(utub_summary[MODELS.UTUBS][-2][MODELS.ID])
    middle_utub_name = str(utub_summary[MODELS.UTUBS][-2][MODELS.NAME])

    utub_name_form = {
        UTUB_FORM.UTUB_NAME: middle_utub_name + "88",
        UTUB_FORM.CSRF_TOKEN: csrf_token,
    }

    # Update the name of the middle UTub
    response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=middle_utub_id),
        data=utub_name_form,
    )
    assert response.status_code == 200

    # Check middle UTub is now first
    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200
    with app.app_context():
        utub_summary = _get_ordered_utub_summary()
    assert utub_summary == response.json
    assert utub_summary[MODELS.UTUBS][0][MODELS.ID] == middle_utub_id


def _get_ordered_utub_summary() -> dict[str, list[dict[str, int | str]]]:
    all_utubs: list[Tuple[Utubs, Member_Role]] = (
        db.session.query(Utubs, Utub_Members.member_role)
        .join(Utub_Members, Utubs.id == Utub_Members.utub_id)
        .filter(Utub_Members.user_id == current_user.id)
        .order_by(Utubs.last_updated.desc())
        .all()
    )
    return {
        MODELS.UTUBS: [
            {
                MODELS.ID: utub.id,
                MODELS.NAME: utub.name,
                MODELS.MEMBER_ROLE: member.value,
            }
            for utub, member in all_utubs
        ]
    }


def test_get_utubs_without_ajax_request(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, with one UTub.
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an array with one UTub in the JSON
    """
    client, _, _, _ = login_first_user_without_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
    )

    assert response.status_code == 302


def test_get_utubs_success_logs(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a logged in user with ID == 1, and is a member of multiple UTubs .
    WHEN the user requests a summary of all their UTubs
    THEN verify the app logs are valid
    """
    client, _, user, _ = login_first_user_without_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert is_string_in_logs(f"Returning UTubs for User={user.id}", caplog.records)


def test_get_utubs_without_ajax_request_logs(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a logged in user with ID == 1, with one UTub.
    WHEN the user requests a summary of all their UTubs
    THEN verify the app logs are correct
    """
    client, _, user, _ = login_first_user_without_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
    )

    assert response.status_code == 302
    assert is_string_in_logs(
        f"User={user.id} did not make an AJAX request", caplog.records
    )
