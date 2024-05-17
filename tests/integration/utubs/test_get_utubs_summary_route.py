from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user
import pytest

from src.models.users import Users
from src.models.utubs import Utubs
from src.utils.all_routes import ROUTES
from src.utils.strings.model_strs import MODELS

pytestmark = pytest.mark.utubs


def test_get_utubs_if_has_no_utubs(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask]
):
    """
    GIVEN a logged in user with ID == 1, with no UTubs.
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an empty array in the JSON
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get(url_for(ROUTES.UTUBS.GET_UTUBS))

    assert response.status_code == 200
    response_json = response.json
    assert response_json == []


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
        all_utubs: list[Utubs] = Utubs.query.all()
        utub_summary = [
            {MODELS.ID: utub.id, MODELS.NAME: utub.name}
            for utub in all_utubs
            if current_user.id in [member.user_id for member in utub.members]
        ]

    response = client.get(url_for(ROUTES.UTUBS.GET_UTUBS))

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
        all_utubs: list[Utubs] = Utubs.query.all()
        utub_summary = [
            {MODELS.ID: utub.id, MODELS.NAME: utub.name}
            for utub in all_utubs
            if current_user.id in [member.user_id for member in utub.members]
        ]

    response = client.get(url_for(ROUTES.UTUBS.GET_UTUBS))

    assert response.status_code == 200
    assert sorted(utub_summary, key=lambda x: x[MODELS.ID]) == sorted(
        response.json, key=lambda x: x[MODELS.ID]
    )
