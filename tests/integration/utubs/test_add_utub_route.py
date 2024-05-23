from flask import url_for
from flask_login import current_user
import pytest

from tests.models_for_test import (
    valid_empty_utub_1,
    valid_empty_utub_2,
    valid_empty_utub_3,
)
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import UTUB_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.utub_strs import UTUB_FAILURE, UTUB_SUCCESS

pytestmark = pytest.mark.utubs


def test_add_utub_with_valid_form(login_first_user_with_register):
    """
    GIVEN a valid logged in user on the home page
    WHEN they make a new UTub for themselves and do a POST to "/utubs" with valid form data
    THEN verify that the server responds with a 200 and valid JSON, that the DB contains the UTub, and
        DB contains the correct UTub data

    POST request must contain a form with the following fields:
        UTUB_FORM.CSRF_TOKEN: String representing the CSRF token for this session and user (required)
        UTUB_FORM.UTUB_NAME: UTub name desired (required)
        UTUB_FORM.DESCRIPTION: UTub description (not required)

    On successful POST, the backend responds with a 200 status code and the following JSON:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        UTUB_SUCCESS.UTUB_ID : Integer indicating the ID of the newly created UTub
        UTUB_SUCCESS.UTUB_NAME : String representing the name of the UTub just created
        UTUB_SUCCESS.UTUB_DESCRIPTION : String representing the description of the UTub entered by the user
        UTUB_SUCCESS.UTUB_CREATOR_ID: Integer indicating the ID of the user who made this UTub"
    }
    """
    client, csrf_token, user, app = login_first_user_with_register

    # Make sure database is empty of UTubs and associated users
    with app.app_context():
        assert len(Utubs.query.all()) == 0
        assert len(Utub_Members.query.all()) == 0

    new_utub_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token,
        UTUB_FORM.UTUB_NAME: valid_empty_utub_1[UTUB_FORM.NAME],
        UTUB_FORM.UTUB_DESCRIPTION: valid_empty_utub_1[UTUB_SUCCESS.UTUB_DESCRIPTION],
    }

    new_utub_response = client.post(url_for(ROUTES.UTUBS.ADD_UTUB), data=new_utub_form)

    assert new_utub_response.status_code == 200

    # Validate the JSON response from the backend
    new_utub_response_json = new_utub_response.json
    assert new_utub_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        new_utub_response_json[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == valid_empty_utub_1[UTUB_SUCCESS.UTUB_DESCRIPTION]
    )
    assert (
        new_utub_response_json[UTUB_SUCCESS.UTUB_NAME]
        == valid_empty_utub_1[UTUB_FORM.NAME]
    )
    assert new_utub_response_json[UTUB_SUCCESS.UTUB_CREATOR_ID] == user.id

    # Validate the utub in the database
    utub_id = int(new_utub_response_json[UTUB_SUCCESS.UTUB_ID])
    with app.app_context():
        utub_from_db: Utubs = Utubs.query.get(utub_id)
        assert len(Utubs.query.all()) == 1

        # Assert database creator is the same one who made it
        assert utub_from_db.utub_creator == user.id

        # Assert that utub name and description line up in the database
        assert utub_from_db.name == valid_empty_utub_1[UTUB_FORM.NAME]
        assert (
            utub_from_db.utub_description
            == valid_empty_utub_1[UTUB_SUCCESS.UTUB_DESCRIPTION]
        )

        # Assert only one member in the UTub
        assert len(utub_from_db.members) == 1

        # Assert no urls in this UTub
        assert len(utub_from_db.utub_urls) == 0

        # Assert no tags associated with this UTub
        assert len(utub_from_db.utub_url_tags) == 0

        # Assert only one user and UTub association
        assert len(Utub_Members.query.all()) == 1

        # Assert the only Utubs-User association is valid
        current_utub_user_association: list[Utub_Members] = Utub_Members.query.all()
        assert current_utub_user_association[0].utub_id == utub_id
        assert current_utub_user_association[0].user_id == user.id


def test_add_utub_with_same_name(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN a valid logged in user on the home page
    WHEN they make a new UTub for themselves with the same name as
        a previous UTub and do a POST to "/utubs" with valid form data
    THEN verify that the server responds with a 200 and valid JSON, that the DB contains the UTub, and
        DB contains the correct UTub data

    POST request must contain a form with the following fields:
        UTUB_FORM.CSRF_TOKEN: String representing the CSRF token for this session and user (required)
        UTUB_FORM.UTUB_NAME: UTub name desired (required)
        UTUB_FORM.DESCRIPTION: UTub description (not required)

    On successful POST, the backend responds with a 200 status code and the following JSON:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        UTUB_SUCCESS.UTUB_ID : Integer indicating the ID of the newly created UTub
        UTUB_SUCCESS.UTUB_NAME : String representing the name of the UTub just created
        UTUB_SUCCESS.UTUB_DESCRIPTION : String representing the description of the UTub entered by the user
        UTUB_SUCCESS.UTUB_CREATOR_ID: Integer indicating the ID of the user who made this UTub"
    }
    """
    client, csrf_token, user, app = login_first_user_without_register

    # Make sure database is empty of UTubs and associated users
    with app.app_context():
        current_utub: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()
        current_utub_name = current_utub.name

        num_of_utubs: int = Utubs.query.count()

    new_utub_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token,
        UTUB_FORM.UTUB_NAME: current_utub_name,
        UTUB_FORM.UTUB_DESCRIPTION: valid_empty_utub_1[UTUB_SUCCESS.UTUB_DESCRIPTION],
    }

    new_utub_response = client.post(url_for(ROUTES.UTUBS.ADD_UTUB), data=new_utub_form)

    assert new_utub_response.status_code == 200

    # Validate the JSON response from the backend
    new_utub_response_json = new_utub_response.json
    assert new_utub_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        new_utub_response_json[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == valid_empty_utub_1[UTUB_SUCCESS.UTUB_DESCRIPTION]
    )
    assert (
        new_utub_response_json[UTUB_SUCCESS.UTUB_NAME]
        == valid_empty_utub_1[UTUB_FORM.NAME]
    )
    assert new_utub_response_json[UTUB_SUCCESS.UTUB_CREATOR_ID] == user.id
    assert isinstance(new_utub_response_json[UTUB_SUCCESS.UTUB_ID], int)
    utub_id = new_utub_response_json[UTUB_SUCCESS.UTUB_ID]

    # Validate the utub in the database
    with app.app_context():
        utub_from_db: Utubs = Utubs.query.get(utub_id)
        assert Utubs.query.count() == num_of_utubs + 1

        # Assert database creator is the same one who made it
        assert utub_from_db.utub_creator == user.id

        # Assert that utub name and description line up in the database
        assert utub_from_db.name == valid_empty_utub_1[UTUB_FORM.NAME]
        assert (
            utub_from_db.utub_description
            == valid_empty_utub_1[UTUB_SUCCESS.UTUB_DESCRIPTION]
        )

        # Assert only one member in the UTub
        assert len(utub_from_db.members) == 1

        # Assert no urls in this UTub
        assert len(utub_from_db.utub_urls) == 0

        # Assert no tags associated with this UTub
        assert len(utub_from_db.utub_url_tags) == 0


def test_add_utub_with_get_request(login_first_user_with_register):
    """
    GIVEN a valid logged in user on the home page
    WHEN they make a new UTub for themselves and do a GET to "/utubs" with valid form data
    THEN verify that the server responds with a 405 invalid request status code, and that no
        UTubs are added to the database
    """
    client, csrf_token, _, app = login_first_user_with_register
    new_utub_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token,
        UTUB_FORM.UTUB_NAME: valid_empty_utub_1[UTUB_FORM.NAME],
        UTUB_FORM.UTUB_DESCRIPTION: valid_empty_utub_1[UTUB_SUCCESS.UTUB_DESCRIPTION],
    }

    client.get(url_for(ROUTES.UTUBS.ADD_UTUB), data=new_utub_form)

    # Make sure no UTub in database
    with app.app_context():
        assert len(Utubs.query.all()) == 0


def test_add_utub_with_invalid_form(login_first_user_with_register):
    """
    GIVEN a valid logged in user on the home page
    WHEN they make a new UTub for themselves and do a POST to "/utubs" with invalid form data
    THEN verify that the server responds with a 404 and a JSON containing error messages, and that no
        UTub has been added to the database

    On POST with an invalid form, the backend responds with a 404 status code and the following JSON:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.ERROR_CODE: Integer representing the failure code, 1 for invalid form inputs
        STD_JSON.MESSAGE: String giving a general error message
        STD_JSON.ERRORS: Array containing objects for each field and their specific error. For example:
            [
                {
                    UTUB_FORM.UTUB_NAME: "This field is required" - Indicates the UTub name field is missing
                }
            ]
    }
    """
    client, csrf_token, _, app = login_first_user_with_register
    new_utub_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token,
        UTUB_FORM.UTUB_DESCRIPTION: valid_empty_utub_1[UTUB_FAILURE.UTUB_DESCRIPTION],
    }

    invalid_new_utub_response = client.post(
        url_for(ROUTES.UTUBS.ADD_UTUB), data=new_utub_form
    )

    # Assert invalid response code
    assert invalid_new_utub_response.status_code == 400

    # Validate the JSON response from the backend indicating bad form inputs
    invalid_new_utub_response_json = invalid_new_utub_response.json
    assert invalid_new_utub_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert invalid_new_utub_response_json[STD_JSON.ERROR_CODE] == 1
    assert (
        invalid_new_utub_response_json[STD_JSON.ERRORS][UTUB_FORM.UTUB_NAME]
        == UTUB_FAILURE.FIELD_REQUIRED
    )
    assert (
        invalid_new_utub_response_json[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MAKE_UTUB
    )

    # Make sure no UTub in database
    with app.app_context():
        assert len(Utubs.query.all()) == 0


def test_add_utub_with_no_csrf_token(login_first_user_with_register):
    """
    GIVEN a valid logged in user
    WHEN they make a POST request to make a new UTub without including a form
    THEN ensure it returns with a 400 and page response indicates CSRF token is missing
    """

    client, _, _, _ = login_first_user_with_register

    invalid_new_utub_response = client.post(url_for(ROUTES.UTUBS.ADD_UTUB))

    # Assert invalid response code
    assert invalid_new_utub_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in invalid_new_utub_response.data


def test_add_multiple_valid_utubs(login_first_user_with_register):
    """
    GIVEN a valid user on the home page
    WHEN they make multiple empty UTubs by POST'ing to "/utubs" with valid UTub form data
    THEN ensure that the correct 200 status code and JSON response is given, as well as ensuring
        the UTub data is stored as well as the UTub-User association data
    """
    client, csrf_token, user, app = login_first_user_with_register
    valid_utubs = (
        valid_empty_utub_1,
        valid_empty_utub_2,
        valid_empty_utub_3,
    )

    for valid_utub in valid_utubs:
        new_utub_form = {
            UTUB_FORM.CSRF_TOKEN: csrf_token,
            UTUB_FORM.UTUB_NAME: valid_utub[UTUB_FORM.NAME],
            UTUB_FORM.UTUB_DESCRIPTION: valid_utub[UTUB_SUCCESS.UTUB_DESCRIPTION],
        }

        new_utub_response = client.post(
            url_for(ROUTES.UTUBS.ADD_UTUB), data=new_utub_form
        )

        assert new_utub_response.status_code == 200

        # Validate the JSON response from the backend
        new_utub_response_json = new_utub_response.json
        assert new_utub_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert (
            new_utub_response_json[UTUB_SUCCESS.UTUB_DESCRIPTION]
            == valid_utub[UTUB_SUCCESS.UTUB_DESCRIPTION]
        )
        assert (
            new_utub_response_json[UTUB_SUCCESS.UTUB_NAME] == valid_utub[UTUB_FORM.NAME]
        )
        assert new_utub_response_json[UTUB_SUCCESS.UTUB_CREATOR_ID] == user.id
        assert isinstance(new_utub_response_json[UTUB_SUCCESS.UTUB_ID], int)

        # Validate the utub in the database
        utub_id = int(new_utub_response_json[UTUB_SUCCESS.UTUB_ID])
        with app.app_context():
            utub_from_db: Utubs = Utubs.query.get_or_404(utub_id)

            # Assert database creator is the same one who made it
            assert utub_from_db.utub_creator == user.id

            # Assert that utub name and description line up in the database
            assert utub_from_db.name == valid_utub[UTUB_FORM.NAME]
            assert (
                utub_from_db.utub_description
                == valid_utub[UTUB_SUCCESS.UTUB_DESCRIPTION]
            )

            # Assert only one member in the UTub
            assert len(utub_from_db.members) == 1

            # Assert no urls in this UTub
            assert len(utub_from_db.utub_urls) == 0

            # Assert no tags associated with this UTub
            assert len(utub_from_db.utub_url_tags) == 0

    # Check for all 3 test utubs added
    assert len(Utubs.query.all()) == len(valid_utubs)
