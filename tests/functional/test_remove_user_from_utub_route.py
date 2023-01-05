import pytest
from flask_login import current_user

from urls4irl import db
from urls4irl.models import Utub, Utub_Users, User

def test_remove_valid_user_from_utub_as_creator(add_single_user_to_utub_without_logging_in, login_first_user_without_register):
    """
    GIVEN a logged in user who is creator of a UTub that has another member in it
    WHEN the logged in user tries to remove second user by POST to "/user/remove/<int: utub_id>/<int: user_id>" with valid 
        information and a valid CSRF token
    THEN ensure the user gets removed from the UTub by checking UTub-User associations, that the server responds with a
        200 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        "Status" : "Success",
        "Message" : "User removed",
        "User_ID_removed" : Integer representing ID of user removed,
        "Username": Username of user deleted,
        "UTub_ID" : Interger representing ID of UTub the user was removed from,
        "UTub_name" : String representing name of UTub removed,
        "UTub_users": Array of string usernames of all members of UTub after the user was removed
    }
    """
    
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub, which contains two members
        current_utub = Utub.query.first()

        # Ensure creator is currently logged in
        assert current_utub.created_by == current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2

        # Grab the second user from the members
        second_user_in_utub_association = Utub_Users.query.filter(Utub_Users.utub_id == current_utub.id, Utub_Users.user_id != current_user.id).first()
        second_user_in_utub = second_user_in_utub_association.to_user

        # Ensure second user in this UTub
        assert second_user_in_utub in [user.to_user for user in current_utub.members]
        
    # Remove second user
    remove_user_response = client.post(f"/user/remove/{current_utub.id}/{second_user_in_utub.id}", data={"csrf_token": csrf_token_string})

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json["Status"] == "Success"
    assert remove_user_response_json["Message"] == "User removed"
    assert int(remove_user_response_json["User_ID_removed"]) == second_user_in_utub.id
    assert remove_user_response_json["Username"] == second_user_in_utub.username
    assert int(remove_user_response_json["UTub_ID"]) == current_utub.id
    assert remove_user_response_json["UTub_name"] == current_utub.name
    assert remove_user_response_json["UTub_users"] == [current_user.username]

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == 1

        # Ensure second user not in this UTub
        assert second_user_in_utub not in [user.to_user for user in current_utub.members]

def test_remove_self_from_utub_as_member(add_single_user_to_utub_without_logging_in, login_second_user_without_register):
    """
    GIVEN a logged in user who is a member of a UTub
    WHEN the logged in user tries to leave the UTub by POST to "/user/remove/<int: utub_id>/<int: user_id>" with valid 
        information and a valid CSRF token
    THEN ensure the user gets removed from the UTub by checking UTub-User associations, that the server responds with a
        200 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        "Status" : "Success",
        "Message" : "User removed",
        "User_ID_removed" : Integer representing ID of user removed,
        "Username": Username of user deleted,
        "UTub_ID" : Interger representing ID of UTub the user was removed from,
        "UTub_name" : String representing name of UTub removed,
        "UTub_users": Array of string usernames of all members of UTub after the user was removed
    }
    """

    client, csrf_token_string, logged_in_user, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub = Utub.query.first()

        # Ensure creator is not currently logged in user
        assert current_utub.created_by != current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2

        # Ensure second user in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

    # Remove self from UTub
    remove_user_response = client.post(f"/user/remove/{current_utub.id}/{current_user.id}", data={"csrf_token": csrf_token_string})

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json["Status"] == "Success"
    assert remove_user_response_json["Message"] == "User removed"
    assert int(remove_user_response_json["User_ID_removed"]) == current_user.id
    assert remove_user_response_json["Username"] == current_user.username
    assert int(remove_user_response_json["UTub_ID"]) == current_utub.id
    assert remove_user_response_json["UTub_name"] == current_utub.name
    assert current_user.username not in remove_user_response_json["UTub_users"]

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == 1

        # Ensure logged in user not in this UTub
        assert current_user not in [user.to_user for user in current_utub.members]

def test_remove_self_from_utub_as_creator(add_single_user_to_utub_without_logging_in, login_first_user_without_register):
    """
    GIVEN a logged in user who is a creator of a UTub
    WHEN the logged in user tries to leave the UTub by POST to "/user/remove/<int: utub_id>/<int: user_id>" with valid 
        information and a valid CSRF token
    THEN ensure the user does not get removed from the UTub, the server responds with a 400 HTTP status code,
        and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "UTub creator cannot remove themselves",
        "Error_code": 1
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub = Utub.query.first()

        # Ensure creator is currently logged in and is current user
        assert current_utub.created_by == current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2

        current_number_of_users_in_utub = len(current_utub.members)

        # Ensure current user also in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

    # Remove self from UTub
    remove_user_response = client.post(f"/user/remove/{current_utub.id}/{current_user.id}", data={"csrf_token": csrf_token_string})

    assert remove_user_response.status_code == 400

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json["Status"] == "Failure"
    assert remove_user_response_json["Message"] == "UTub creator cannot remove themselves"
    assert int(remove_user_response_json["Error_code"]) == 1

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user still creator of this UTub
        assert current_user == current_utub.created_by

        # Ensure logged in user still in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

def test_remove_self_from_utub_no_csrf_token_as_member(add_single_user_to_utub_without_logging_in, login_second_user_without_register):
    """
    GIVEN a logged in user who is a member of a UTub
    WHEN the logged in user tries to leave the UTub by POST to "/user/remove/<int: utub_id>/<int: user_id>" with valid 
        information and no CSRF token
    THEN ensure the user does not get removed from the UTub by checking UTub-User associations, that the server responds with a
        400 HTTP status code indicating no CSRF token included
    """

    client, csrf_token_string, logged_in_user, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub = Utub.query.first()

        # Ensure creator is not currently logged in user
        assert current_utub.created_by != current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2
        current_number_of_users_in_utub = len(current_utub.members)

        # Ensure second user in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

    # Remove self from UTub
    remove_user_response = client.post(f"/user/remove/{current_utub.id}/{current_user.id}")

    # Assert invalid response code
    assert remove_user_response.status_code == 400
    assert b'<p>The CSRF token is missing.</p>' in remove_user_response.data

    # Ensure database is correct
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user still in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

def test_remove_valid_user_from_utub_no_csrf_token_as_creator(add_single_user_to_utub_without_logging_in, login_first_user_without_register):
    """
    GIVEN a logged in user who is creator of a UTub that has another member in it
    WHEN the logged in user tries to remove second user by POST to "/user/remove/<int: utub_id>/<int: user_id>" with valid 
        information and a missing CSRF token
    THEN ensure the user does not get removed from the UTub by checking UTub-User associations, that the server responds 
        with a 400 HTTP status code indicating the CSRF token is missing
    """
    
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub = Utub.query.first()

        # Ensure creator is currently logged in
        assert current_utub.created_by == current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2
        current_number_of_users_in_utub = len(current_utub.members)

        # Grab the second user from the members
        second_user_in_utub_association = Utub_Users.query.filter(Utub_Users.utub_id == current_utub.id, Utub_Users.user_id != current_user.id).first()
        second_user_in_utub = second_user_in_utub_association.to_user

        # Ensure second user in this UTub
        assert second_user_in_utub in [user.to_user for user in current_utub.members]
        
    # Remove second user
    remove_user_response = client.post(f"/user/remove/{current_utub.id}/{second_user_in_utub.id}")

    # Assert invalid response code
    assert remove_user_response.status_code == 400
    assert b'<p>The CSRF token is missing.</p>' in remove_user_response.data

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user is still creator
        assert current_user == current_utub.created_by

        # Ensure second user still in this UTub
        assert second_user_in_utub in [user.to_user for user in current_utub.members]

def test_remove_valid_user_from_invalid_utub_as_member_or_creator(add_single_user_to_utub_without_logging_in, login_second_user_without_register):
    """
    GIVEN a valid existing user and a nonexistent UTub
    WHEN the user requests to remove themselves from the UTub via a POST to "/user/remove/<int: utub_id>/<int: user_id>"
    THEN ensure that a 404 status code response is given when the UTub cannot be found in the database
    """
    
    client, csrf_token_string, logged_in_user, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        all_current_utubs = Utub.query.all()
        
        invalid_utub_id = 0

        while invalid_utub_id in [utub.id for utub in all_current_utubs]:
            invalid_utub_id += 1

        # Ensure given UTub does not exist 
        assert invalid_utub_id not in [utub.id for utub in all_current_utubs]

    # Remove self from UTub
    remove_user_response = client.post(f"/user/remove/{invalid_utub_id}/{current_user.id}", data={"csrf_token": csrf_token_string})

    # Ensure 404 HTTP status code response
    assert remove_user_response.status_code == 404

    # Ensure 404 response is given no matter what USER ID
    for num in range(10):
        remove_user_response = client.post(f"/user/remove/{invalid_utub_id}/{num}", data={"csrf_token": csrf_token_string})

        # Ensure 404 HTTP status code response
        assert remove_user_response.status_code == 404

def test_remove_invalid_user_from_utub_as_creator(add_single_user_to_utub_without_logging_in, login_first_user_without_register):
    """
    GIVEN a creator of a UTub that is currently logged in
    WHEN the user requests to remove a nonexistent member from the UTub via a POST to "/user/remove/<int: utub_id>/<int: user_id>"
    THEN ensure that a 404 status code response is given when the user cannot be found in the UTub, and the proper JSON response is given

    Proper JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "User does not exist or not found in this UTub",
        "Error_code": 3
    }
    """
    
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub = Utub.query.first()

        # Ensure creator is currently logged in
        assert current_utub.created_by == current_user

        # Find a user id that isn't in this UTub
        user_id_not_in_utub = 0
        while user_id_not_in_utub in [user.user_id for user in current_utub.members]:
            user_id_not_in_utub += 1

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2
        
        # Ensure invalid user is not in this UTub
        assert user_id_not_in_utub not in [user.user_id for user in current_utub.members]

    # Remove self from UTub
    remove_user_response = client.post(f"/user/remove/{current_utub.id}/{user_id_not_in_utub}", data={"csrf_token": csrf_token_string})

    # Ensure 404 HTTP status code response
    assert remove_user_response.status_code == 404

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json["Status"] == "Failure"
    assert remove_user_response_json["Message"] == "User does not exist or not found in this UTub"
    assert int(remove_user_response_json["Error_code"]) == 3

def test_remove_invalid_user_from_utub_as_member(add_single_user_to_utub_without_logging_in, login_second_user_without_register):
    """
    GIVEN a member of a UTub that is currently logged in
    WHEN the user requests to remove a nonexistent member from the UTub via a POST to "/user/remove/<int: utub_id>/<int: user_id>"
    THEN ensure that a 403 status code response is given when the user cannot be found in the UTub, and the proper JSON response is given

    Proper JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "Not allowed to remove a user from this UTub",
        "Error_code": 2
    }
    """
    
    client, csrf_token_string, logged_in_user, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub = Utub.query.first()

        # Ensure current user is not creator
        assert current_user != current_utub.created_by

        # Ensure current user is a member of this UTub
        assert current_user in [user.to_user for user in current_utub.members]

        # Find a user id that isn't in this UTub
        user_id_not_in_utub = 0
        while user_id_not_in_utub in [user.user_id for user in current_utub.members]:
            user_id_not_in_utub += 1

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2
        
        # Ensure invalid user is not in this UTub
        assert user_id_not_in_utub not in [user.user_id for user in current_utub.members]

    # Remove self from UTub
    remove_user_response = client.post(f"/user/remove/{current_utub.id}/{user_id_not_in_utub}", data={"csrf_token": csrf_token_string})

    # Ensure 403 HTTP status code response
    assert remove_user_response.status_code == 403

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json["Status"] == "Failure"
    assert remove_user_response_json["Message"] == "Not allowed to remove a user from this UTub"
    assert int(remove_user_response_json["Error_code"]) == 2


def test_remove_another_member_from_same_utub_as_member(add_multiple_users_to_utub_without_logging_in, login_second_user_without_register):
    """
    GIVEN a logged in user who is a member of a UTub with another member and the creator
    WHEN the logged in user tries to remove the other member (not the creator) from the UTub by POST to 
        "/user/remove/<int: utub_id>/<int: user_id>" with valid information and a valid CSRF token
    THEN ensure the other member does not get removed from the UTub by checking UTub-User associations, 
        that the server responds with a 403 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "Not allowed to remove a user from this UTub",
        "Error_code": 2
    }
    """

    client, csrf_token_string, logged_in_user, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub, which contains three members
        current_utub = Utub.query.first()

        # Ensure creator is not currently logged in user
        assert current_utub.created_by != current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 3
        current_number_of_users_in_utub = len(current_utub.members)

        # Ensure second user in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

        # Grab other user in this UTub
        for user in current_utub.members:
            if user != current_user and user != current_utub.created_by:
                other_utub_member = user.to_user

    # Attempt to remove other user from UTub as a member
    remove_user_response = client.post(f"/user/remove/{current_utub.id}/{other_utub_member.id}", data={"csrf_token": csrf_token_string})

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 403

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json["Status"] == "Failure"
    assert remove_user_response_json["Message"] == "Not allowed to remove a user from this UTub"
    assert int(remove_user_response_json["Error_code"]) == 2

    # Ensure database is correctly updated
    with app.app_context():
        # Grab the UTub again
        current_utub = Utub.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

        # Ensure the bystander member is still in the UTub
        assert other_utub_member in [user.to_user for user in current_utub.members]
  
def test_remove_member_from_another_utub_as_creator_of_another_utub(every_user_makes_a_unique_utub, login_first_user_without_register):
    """
    GIVEN a logged in user who is a creator of a UTub, and given another UTub with a creator and member who are not
        the current logged in user

        Current logged in user is ID == 1
        Have current user be creator of UTub, and try to remove a member from another UTub
        UTUB 1 -> Creator == 1, nobody else
        UTUB 2 -> Creator == 2, contains 3

    WHEN the logged in user tries to remove the other member (not the creator) from the other UTub by POST to 
        "/user/remove/<int: utub_id>/<int: user_id>" with valid information and a valid CSRF token
    THEN ensure the other member does not get removed from the UTub by checking UTub-User associations, 
        that the server responds with a 403 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "Not allowed to remove a user from this UTub",
        "Error_code": 2
    }
    """
    
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        second_user_utub = Utub.query.get(2)

        # Assert second utub only has the second user in it
        assert len(second_user_utub.members) == 1

        # Get the third user
        third_user = User.query.get(3)

        # Assert third user not in second user's UTub
        assert third_user not in [user.to_user for user in second_user_utub.members]

        # Add third user to second user's UTub
        utub_user_association = Utub_Users()
        utub_user_association.to_user = third_user
        second_user_utub.members.append(utub_user_association)
        db.session.commit()

        # Now assert the third user in the second User's UTub
        assert len(second_user_utub.members) == 2
        assert third_user in [user.to_user for user in second_user_utub.members]

        # Ensure logged in user is not in the second user's UTub
        assert current_user not in [user.to_user for user in second_user_utub.members]

    # Try to remove the third user from second user's UTub as the first user
    remove_user_response = client.post(f"/user/remove/{second_user_utub.id}/{third_user.id}", data={"csrf_token": csrf_token_string})

    # Ensure 403 HTTP status code response
    assert remove_user_response.status_code == 403

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json["Status"] == "Failure"
    assert remove_user_response_json["Message"] == "Not allowed to remove a user from this UTub"
    assert int(remove_user_response_json["Error_code"]) == 2

    # Ensure database still shows user 3 is member of utub 2
    with app.app_context():
        second_user_utub = Utub.query.get(2)
        third_user = User.query.get(3)

        assert third_user in [user.to_user for user in second_user_utub.members]

def test_remove_member_from_another_utub_as_member_of_another_utub(add_multiple_users_to_utub_without_logging_in, login_second_user_without_register):
    """
    GIVEN a logged in user who is a member of a UTub, and given another UTub with a creator and member who are not
        the current logged in user

        Current logged in user is ID == 2
        Have current user be member of UTub, and try to remove a member from another UTub
        UTUB 1 -> Creator == 1, contains members 2 and 3

        Create UTub by user 3, include User 1
        UTUB 2 -> Creator == 3, contains 1

        Have logged in user with ID == 2 try to remove User 1 from UTub 3

    WHEN the logged in user tries to remove the other member (not the creator) from the other UTub by POST to 
        "/user/remove/<int: utub_id>/<int: user_id>" with valid information and a valid CSRF token
    THEN ensure the other member does not get removed from the UTub by checking UTub-User associations, 
        that the server responds with a 403 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "Not allowed to remove a user from this UTub",
        "Error_code": 2
    }
    """
    client, csrf_token_string, logged_in_user, app = login_second_user_without_register

    with app.app_context():
        # Get the third user
        third_user = User.query.get(3)

        # Have third user make another UTub
        new_utub_from_third_user = Utub(name="Third User's UTub", 
                                        utub_creator=third_user.id,
                                        utub_description="")
        creator = Utub_Users()
        creator.to_user = third_user
        new_utub_from_third_user.members.append(creator)

        first_user = User.query.get(1)
        
        new_utub_user = Utub_Users()
        new_utub_user.to_user = first_user
        new_utub_from_third_user.members.append(new_utub_user)

        db.session.add(new_utub_from_third_user)
        db.session.commit()

        # Ensure current user is not creator of any UTubs
        all_utubs = Utub.query.all()
        for utub in all_utubs:
            assert current_user != utub.created_by

        # Ensure current user is not member of third user's UTub
        assert current_user not in [user.to_user for user in new_utub_from_third_user.members]

        # Ensure current user is a member of a UTub
        all_utub_users = Utub_Users.query.filter(Utub_Users.user_id == current_user.id).all()
        assert len(all_utub_users) > 0

    # Try to remove the first user from second user's UTub as the first user
    remove_user_response = client.post(f"/user/remove/{new_utub_from_third_user.id}/{first_user.id}", data={"csrf_token": csrf_token_string})

    # Ensure 403 HTTP status code response
    assert remove_user_response.status_code == 403

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json["Status"] == "Failure"
    assert remove_user_response_json["Message"] == "Not allowed to remove a user from this UTub"
    assert int(remove_user_response_json["Error_code"]) == 2

    # Ensure database still shows user 1 is member of utub 2
    with app.app_context():
        third_user_utub = Utub.query.get(2)
        first_user = User.query.get(1)

        assert first_user in [user.to_user for user in third_user_utub.members]
