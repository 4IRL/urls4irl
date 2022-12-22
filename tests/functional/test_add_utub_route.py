import pytest
from models_for_test import valid_empty_utub_1, valid_empty_utub_2, valid_empty_utub_3
from urls4irl.models import Utub, Utub_Users


def test_requests_add_utub_with_valid_form(logged_in_user_on_home_page):
    """
    GIVEN a valid logged in user on the home page
    WHEN they make a new UTub for themselves and do a POST to "/utub/new" with valid form data
    THEN verify that the server responds with a 200 and valid JSON, that the DB contains the UTub, and
        DB contains the correct UTub data

    POST request must contain a form with the following fields:
        "csrf_token": String representing the CSRF token for this session and user (required)
        "name": UTub name desired (required)
        "description": UTub description (not required)

    On successful POST, the backend responds with a 200 status code and the following JSON:
    {
        "Status": "Success",
        "UTub_ID" : Integer indicating the ID of the newly created UTub
        "UTub_name" : String representing the name of the UTub just created
        "UTub_description" : String representing the description of the UTub entered by the user
        "UTub_creator_id": Integer indicating the ID of the user who made this UTub"
    }
    """
    client, user, csrf_token, app  = logged_in_user_on_home_page

    # Make sure database is empty of UTubs and associated users
    with app.app_context():
        assert len(Utub.query.all()) == 0
        assert len(Utub_Users.query.all()) == 0

    new_utub_form = {
        "csrf_token": csrf_token,
        "name": valid_empty_utub_1["name"],
        "description": valid_empty_utub_1["utub_description"]
    }

    new_utub_response = client.post("/utub/new", data=new_utub_form)
    
    assert new_utub_response.status_code == 200

    # Validate the JSON response from the backend
    new_utub_response_json = new_utub_response.json
    assert new_utub_response_json["Status"] == "Success"
    assert new_utub_response_json["UTub_description"] == valid_empty_utub_1["utub_description"]
    assert new_utub_response_json["UTub_name"] == valid_empty_utub_1["name"]
    assert new_utub_response_json["UTub_creator_id"] == user.id
    assert isinstance(new_utub_response_json["UTub_ID"], int)

    # Validate the utub in the database
    utub_id = int(new_utub_response_json["UTub_ID"])
    with app.app_context():
        utub_from_db = Utub.query.get_or_404(utub_id)

        # Assert database creator is the same one who made it
        assert utub_from_db.utub_creator == user.id

        # Assert that utub name and description line up in the database
        assert utub_from_db.name == valid_empty_utub_1["name"]
        assert utub_from_db.utub_description == valid_empty_utub_1["utub_description"]

        # Assert only one member in the UTub
        assert len(utub_from_db.members) == 1

        # Assert no urls in this UTub
        assert len(utub_from_db.utub_urls) == 0
        
        # Assert no tags associated with this UTub
        assert len(utub_from_db.utub_url_tags) == 0

        # Assert only one user and UTub association
        assert len(Utub_Users.query.all()) == 1

        # Assert the only Utub-User association is valid
        current_utub_user_association = Utub_Users.query.all()
        assert current_utub_user_association[0].utub_id == utub_id
        assert current_utub_user_association[0].user_id == user.id

    #TODO test new UTub displayed on user's UTub deck

def test_requests_add_utub_with_get_request(logged_in_user_on_home_page):
    """
    GIVEN a valid logged in user on the home page
    WHEN they make a new UTub for themselves and do a GET to "/utub/new" with valid form data
    THEN verify that the server responds with a 405 invalid request status code, and that no
        UTubs are added to the database
    """
    client, user, csrf_token, app  = logged_in_user_on_home_page
    new_utub_form = {
        "csrf_token": csrf_token,
        "name": valid_empty_utub_1["name"],
        "description": valid_empty_utub_1["utub_description"],
    }

    new_utub_response = client.get("/utub/new", data=new_utub_form)
    
    # Get method is not allowed
    assert new_utub_response.status_code == 405

    # Make sure no UTub in database
    with app.app_context():
        assert len(Utub.query.all()) == 0

def test_requests_add_utub_with_invalid_form(logged_in_user_on_home_page):
    """
    GIVEN a valid logged in user on the home page
    WHEN they make a new UTub for themselves and do a POST to "/utub/new" with invalid form data
    THEN verify that the server responds with a 404 and a JSON containing error messages, and that no
        UTub has been added to the database

    On POST with an invalid form, the backend responds with a 404 status code and the following JSON:
    {
        "Status": "Failure",
        "Error_code": Integer representing the failure code, 1 for invalid form inputs
        "Message": String giving a general error message
        "Errors": Array containing objects for each field and their specific error. For example:
            [
                {
                    "name": "This field is required" - Indicates the UTub name field is missing
                }
            ]
    }
    """
    client, user, csrf_token, app = logged_in_user_on_home_page
    new_utub_form = {
        "csrf_token": csrf_token,
        "utub_name": valid_empty_utub_1["name"],    # Invalid form name, s/b  "name"
        "description": valid_empty_utub_1["utub_description"],
    }

    invalid_new_utub_response = client.post("/utub/new", data=new_utub_form)

    # Assert invalid response code
    assert invalid_new_utub_response.status_code == 404

    # Validate the JSON response from the backend indicating bad form inputs
    invalid_new_utub_response_json = invalid_new_utub_response.json
    assert invalid_new_utub_response_json["Status"] == "Failure"
    assert invalid_new_utub_response_json["Error_code"] == 1
    assert invalid_new_utub_response_json["Errors"]["name"][0] == "This field is required."
    assert invalid_new_utub_response_json["Message"] == "Unable to generate a new UTub with that information."

    # Make sure no UTub in database
    with app.app_context():
        assert len(Utub.query.all()) == 0

def test_requests_add_utub_with_no_csrf_token(logged_in_user_on_home_page):
    """
    GIVEN a valid logged in user
    WHEN they make a POST request to make a new UTub without including a form
    THEN ensure it returns with a 404 and page response indicates CSRF token is missing
    """
    
    client, user, csrf_token, app = logged_in_user_on_home_page

    invalid_new_utub_response = client.post("/utub/new")

    # Assert invalid response code
    assert invalid_new_utub_response.status_code == 400
    assert b'<p>The CSRF token is missing.</p>' in invalid_new_utub_response.data

def test_requests_add_multiple_valid_utubs(logged_in_user_on_home_page):
    """
    GIVEN a valid user on the home page
    WHEN they make multiple empty UTubs by POST'ing to "/utub/new" with valid UTub form data
    THEN ensure that the correct 200 status code and JSON response is given, as well as ensuring
        the UTub data is stored as well as the UTub-User association data
    """
    client, user, csrf_token, app  = logged_in_user_on_home_page
    valid_utubs = (valid_empty_utub_1, valid_empty_utub_2, valid_empty_utub_3,)

    for valid_utub in valid_utubs:

        new_utub_form = {
            "csrf_token": csrf_token,
            "name": valid_utub["name"],
            "description": valid_utub["utub_description"]
        }

        new_utub_response = client.post("/utub/new", data=new_utub_form)
        
        assert new_utub_response.status_code == 200

        # Validate the JSON response from the backend
        new_utub_response_json = new_utub_response.json
        assert new_utub_response_json["Status"] == "Success"
        assert new_utub_response_json["UTub_description"] == valid_utub["utub_description"]
        assert new_utub_response_json["UTub_name"] == valid_utub["name"]
        assert new_utub_response_json["UTub_creator_id"] == user.id
        assert isinstance(new_utub_response_json["UTub_ID"], int)

        # Validate the utub in the database
        utub_id = int(new_utub_response_json["UTub_ID"])
        with app.app_context():
            utub_from_db = Utub.query.get_or_404(utub_id)

            # Assert database creator is the same one who made it
            assert utub_from_db.utub_creator == user.id

            # Assert that utub name and description line up in the database
            assert utub_from_db.name == valid_utub["name"]
            assert utub_from_db.utub_description == valid_utub["utub_description"]

            # Assert only one member in the UTub
            assert len(utub_from_db.members) == 1

            # Assert no urls in this UTub
            assert len(utub_from_db.utub_urls) == 0
            
            # Assert no tags associated with this UTub
            assert len(utub_from_db.utub_url_tags) == 0
    
    # Check for all 3 test utubs added
    assert len(Utub.query.all()) == len(valid_utubs)
