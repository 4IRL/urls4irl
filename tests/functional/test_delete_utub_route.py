import pytest
from models_for_test import valid_empty_utub_1
from flask_login import current_user
from urls4irl.models import Utub, Utub_Users
from urls4irl import db

def test_delete_existing_utub_as_creator(add_single_utub_as_user_after_logging_in):
    """
    GIVEN a valid existing user and a UTub they have created
    WHEN the user requests to delete the UTub via a POST to "/utub/delete/<int: utub_id>"
    THEN ensure that a 200 status code response is given, and the proper JSON response
        indicating the successful deletion of the UTub is included.
        Additionally, this user and UTub are the only existing entities so ensure that
        no UTub exist in the database, and no associations exist between UTubs and Users after deletion

    On POST with a successful deletion, the JSON response is as follows:
    {
        "Status": "Success",
        "Message": "UTub deleted",
        "UTub_ID": Integer representing the ID of the UTub deleted,
        "UTub_description": String representing the description of the deleted UTub,
        "UTub_name": String representing the name of the deleted UTub,
    }
    """
    client, utub_id, csrf_token, app = add_single_utub_as_user_after_logging_in

    delete_utub_response = client.post(f"/utub/delete/{utub_id}", data={"csrf_token": csrf_token})

    assert delete_utub_response.status_code == 200

    delete_utub_json_response = delete_utub_response.json

    # Assert JSON includes proper response on successful deletion of UTub
    assert delete_utub_json_response["Message"] == "UTub deleted"
    assert delete_utub_json_response["Status"] == "Success"
    assert delete_utub_json_response["UTub_description"] == valid_empty_utub_1["utub_description"]
    assert int(delete_utub_json_response["UTub_ID"]) == utub_id
    assert delete_utub_json_response["UTub_name"] == valid_empty_utub_1["name"]

    with app.app_context():
        # Assert no UTubs and no UTub-User associations exist in the database after deletion
        assert len(Utub.query.all()) == 0
        assert len(Utub_Users.query.all()) == 0
    #TODO Test UTub deleted from user's home page

def test_delete_nonexistent_utub(logged_in_user_on_home_page):
    """
    GIVEN a valid existing user and a nonexistent UTub
    WHEN the user requests to delete the UTub via a POST to "/utub/delete/1"
    THEN ensure that a 404 status code response is given when the UTub cannot be found in the database
    """
    client, valid_user, csrf_token, app = logged_in_user_on_home_page

    # Assert no UTubs exist before nonexistent UTub is attempted to be removed
    with app.app_context():
        assert len(Utub.query.all()) == 0

    delete_utub_response = client.post(f"/utub/delete/1", data={"csrf_token": csrf_token})

    # Ensure 404 sent back after invalid UTub id is requested
    assert delete_utub_response.status_code == 404

def test_delete_utub_with_invalid_route(logged_in_user_on_home_page):
    """
    GIVEN a valid existing user
    WHEN the user requests to delete a UTub via a POST to "/utub/delete/InvalidRouteArgument"
    THEN ensure that a 404 status code response is given due to the invalid route used

    Correct url should be: "/utub/delete/<int: utub_id>" Where utub_id is an integer representing the ID of the UTub
        to delete
    """
    client, valid_user, csrf_token, app = logged_in_user_on_home_page

    # Assert no UTubs exist before nonexistent UTub is attempted to be removed
    with app.app_context():
        assert len(Utub.query.all()) == 0

    delete_utub_response = client.post(f"/utub/delete/InvalidRoute", data={"csrf_token": csrf_token})

    # Ensure 404 sent back after invalid UTub id is requested
    assert delete_utub_response.status_code == 404

def test_delete_utub_as_not_member_or_creator(every_user_makes_a_unique_utub, login_first_user_without_register):
    """
    GIVEN three sets of users, with each user having created their own UTub
    WHEN one user tries to delete the other two users' UTubs via POST to "/utub/dete/<int: utub_id>"
    THEN ensure response status code is 403, and proper JSON response indicating error is given

    JSON response should be formatted as follows:
    {
        "Status" : "Failure",
        "Message": "You don't have permission to delete this UTub!"
    }
    """
    client, csrf_token, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        # Get the UTubs from the database that this member is not a part of
        user_not_in_these_utubs = Utub_Users.query.filter(Utub_Users.user_id != current_user.id).with_entities(Utub_Users.utub_id).all()
        
        # Make sure that only 2 utubs-user associations exist, one for each utub/user combo
        assert len(user_not_in_these_utubs) == 2    

    for utub_not_in in user_not_in_these_utubs:
        delete_utub_response = client.post(f"/utub/delete/{utub_not_in.utub_id}", data={"csrf_token": csrf_token})
        
        assert delete_utub_response.status_code == 403

        delete_utub_response_json = delete_utub_response.json

        assert delete_utub_response_json["Status"] == "Failure"
        assert delete_utub_response_json["Message"] == "You don't have permission to delete this UTub!"

        with app.app_context():
            user_not_in_these_utubs = Utub_Users.query.filter(Utub_Users.user_id != current_user.id).with_entities(Utub_Users.utub_id).all()
        
            # Make sure that only 2 utubs-user associations exist, one for each utub/user combo
            assert len(user_not_in_these_utubs) == 2    

    with app.app_context():
        # Make sure all 3 test UTubs are still available in the database
        assert len(Utub.query.all()) == 3
        assert len(Utub_Users.query.all()) == 3

def test_delete_utub_as_member_only(every_user_makes_a_unique_utub, login_first_user_without_register):
    """
    GIVEN three sets of users, with each user having created their own UTub
    WHEN one user who is a member of all three UTubs, 
        tries to delete the other two users' UTubs via POST to "/utub/dete/<int: utub_id>"
    THEN ensure response status code is 403, and proper JSON response indicating error is given

    JSON response should be formatted as follows:
    {
        "Status" : "Failure",
        "Message": "You don't have permission to delete this UTub!"
    }
    """
    client, csrf_token, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        # Get the UTubs from the database that this member is not a part of
        user_not_in_these_utubs = Utub_Users.query.filter(Utub_Users.user_id != current_user.id).with_entities(Utub_Users.utub_id).all()
        
        # Make sure that only 2 utubs-user associations exist, one for each utub/user combo
        assert len(user_not_in_these_utubs) == 2

        # Add the current logged in user to the UTub's it is not a part of
        for utub_not_part_of in user_not_in_these_utubs:
            utub_to_join = utub_not_part_of.utub_id
            new_utub_user_association = Utub_Users(utub_id=utub_to_join, user_id=logged_in_user.id)
            new_utub_user_association.to_user = current_user
            new_utub_user_association.to_utub = Utub.query.get(utub_to_join)
            db.session.add(new_utub_user_association)
            db.session.commit()

        # Assert current user is in all UTubs
        all_utubs = Utub.query.all()
        for utub in all_utubs:
            assert len(Utub_Users.query.filter(Utub_Users.user_id == current_user.id, Utub_Users.utub_id == utub.id).all()) == 1

    # The logged in user should now be a member of the utubs they weren't a part of before
    only_member_in_these_utubs = user_not_in_these_utubs

    for utub_not_in in only_member_in_these_utubs:
        delete_utub_response = client.post(f"/utub/delete/{utub_not_in.utub_id}", data={"csrf_token": csrf_token})
        
        assert delete_utub_response.status_code == 403

        delete_utub_response_json = delete_utub_response.json

        assert delete_utub_response_json["Status"] == "Failure"
        assert delete_utub_response_json["Message"] == "You don't have permission to delete this UTub!"

        with app.app_context():
            user_not_in_these_utubs = Utub_Users.query.filter(Utub_Users.user_id != current_user.id).with_entities(Utub_Users.utub_id).all()
            
    with app.app_context():
        # Make sure all 3 test UTubs are still available in the database
        assert len(Utub.query.all()) == 3
