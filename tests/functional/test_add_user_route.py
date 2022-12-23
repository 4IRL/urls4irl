import pytest
from flask_login import current_user
from urls4irl.models import Utub, Utub_Users, User
from urls4irl import db

def test_add_valid_users_to_utub_as_creator(every_user_makes_a_unique_utub, login_first_user_without_register):
    """
    GIVEN a logged-in user who is creator of a UTub that contains only themselves
    WHEN the user wants to add two other valid users to their UTub by POST to "/user/add/<int: utub_id>" with
        correct form data, following the following format:
            "csrf_token": String containing CSRF token for validation
            "username": Username of the user to add
    THEN ensure that the backend responds with a 200 HTTP status code, that the database contains the newly added
        UTub-User association, and that the backend responds with the correct JSON response

    The correct JSON response is as follows:
    {
        "Status" : "Success",
        "Message" : "User added",
        "User_ID_added": Integer representing ID of the user just added,
        "UTub_ID" : Integer representing ID of the UTub the user was added to,
        "UTub_name" : String representing name of the UTub the user was added to,
        "UTub_users": Array containing strings of all usernames in the UTub
    }   
    """
    client, csrf_token, logged_in_user, app = login_first_user_without_register

    # Get the other users' usernames and this user's UTub, assuming 3 valid users
    with app.app_context():
        # Confirm one user per utub
        assert len(Utub.query.all()) == len(Utub_Users.query.all())
        for utub in Utub.query.all():
            assert len(utub.members) == 1

        other_usernames = User.query.filter(User.username!=current_user.username).all()
        other_usernames = [other_user.username for other_user in other_usernames]

        utub_of_current_user = Utub_Users.query.filter(Utub_Users.user_id==current_user.id).first()
        utub_id_of_current_user = utub_of_current_user.utub_id

        # Confirm number of users in the current user's UTub is 1
        current_number_of_users_in_utub = len(Utub_Users.query.filter(Utub_Users.user_id==current_user.id, Utub_Users.utub_id==utub_of_current_user.utub_id).all())
        assert current_number_of_users_in_utub == 1

        # Confirm current user is owner of utub
        assert utub_of_current_user.to_utub.created_by == current_user

    # Add the other users to the current user's UTubs
    for other_user in other_usernames:
        add_user_form = {
            "csrf_token": csrf_token,
            "username": other_user
        }

        with app.app_context():
            new_user = User.query.filter(User.username==other_user).first()

        added_user_response = client.post(f"/user/add/{utub_id_of_current_user}", data=add_user_form)
        current_number_of_users_in_utub += 1

        # Assert correct status code
        assert added_user_response.status_code == 200
        added_user_response_json = added_user_response.json

        # Assert JSON response is valid and contains updated data
        assert added_user_response_json["Status"] == "Success"
        assert added_user_response_json["Message"] == "User added"
        assert int(added_user_response_json["User_ID_added"]) == new_user.id
        assert int(added_user_response_json["UTub_ID"]) == utub_id_of_current_user
        assert added_user_response_json["UTub_name"] == utub_of_current_user.to_utub.name
        assert len(added_user_response_json["UTub_users"]) == current_number_of_users_in_utub
        assert other_user in added_user_response_json["UTub_users"]

        # Assert database user-utub associations is up to date
        with app.app_context():
            assert len(Utub.query.get(utub_id_of_current_user).members) == current_number_of_users_in_utub
            current_utub = Utub.query.get(utub_id_of_current_user)
            assert new_user in [user.to_user for user in current_utub.members]
            current_users_in_utub = set([user.to_user.username for user in current_utub.members])
            assert other_user in current_users_in_utub

def test_add_valid_users_to_utub_as_member(add_single_utub_as_user_without_logging_in, register_all_but_first_user, login_second_user_without_register):
    """
    GIVEN a logged-in user who is member of a UTub
    WHEN the user wants to add another other valid users to their UTub by POST to "/user/add/<int: utub_id>" with
        correct form data, following the following format:
            "csrf_token": String containing CSRF token for validation
            "username": Username of the user to add
    THEN ensure that the backend responds with a 403 HTTP status code,and the correct JSON response

    The correct JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "Not authorized",
        "Error_code": 1
    }  
    """
    client, csrf_token_string, logged_in_user, app = login_second_user_without_register
    with app.app_context():
        # Add second user to first UTub
        only_utub = Utub.query.first()
        new_utub_user_association = Utub_Users()
        new_utub_user_association.to_user = current_user
        new_utub_user_association.to_utub = only_utub
        db.session.commit()

        # Find user that isn't in the UTub
        # First get all users
        all_users = User.query.all()

        # Get the missing user from the UTub's members
        all_utub_members = only_utub.members
        all_utub_members = [user.to_user for user in all_utub_members]

        # Get the missing user
        for user in all_users:
            if user not in all_utub_members:
                missing_user = user

        # Verify the missing user is in no utubs
        assert len(Utub_Users.query.filter(Utub_Users.user_id == missing_user.id).all()) == 0

        # Verify current user isn't creator of UTub
        assert only_utub.created_by != current_user.id

    # Try to add the missing member to the UTub
    add_user_form = {
        "csrf_token": csrf_token_string,
        "username": missing_user.username
    }
        
    missing_user_id = missing_user.id
    add_user_response = client.post(f"/user/add/{only_utub.id}", data=add_user_form)

    assert add_user_response.status_code == 403
    
    add_user_response_json = add_user_response.json

    assert add_user_response_json["Status"] == "Failure"
    assert add_user_response_json["Message"] == "Not authorized"
    assert int(add_user_response_json["Error_code"]) == 1

    with app.app_context():
        assert len(Utub_Users.query.filter(Utub_Users.user_id == missing_user_id).all()) == 0

#TODO Add check for duplicate member add
#TODO Add check for add to nonexistent UTub
#TODO Add check for add to someone else's UTub
#TODO Add check for invalid form to add user to UTub
#TODO Add check for no CSRF token to add user to UTub
