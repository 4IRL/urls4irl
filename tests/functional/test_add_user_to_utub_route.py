import pytest
from flask_login import current_user

from urls4irl.models import Utub, Utub_Users, User, Utub_Urls, Url_Tags
from urls4irl import db
from urls4irl.utils import strings as U4I_STRINGS

ADD_USER_FORM = U4I_STRINGS.ADD_USER_FORM
USER_SUCCESS = U4I_STRINGS.USER_SUCCESS
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
MODEL_STRS = U4I_STRINGS.MODELS
USER_FAILURE = U4I_STRINGS.USER_FAILURE

def test_add_valid_users_to_utub_as_creator(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains only themselves, no URLs or tags
    WHEN the user wants to add two other valid users to their UTub by POST to "/user/add/<int: utub_id>" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 200 HTTP status code, that the database contains the newly added
        UTub-User association, and that the backend responds with the correct JSON response

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : USER_SUCCESS.USER_ADDED,
        USER_SUCCESS.USER_ID_ADDED: Integer representing ID of the user just added,
        USER_SUCCESS.UTUB_ID : Integer representing ID of the UTub the user was added to,
        USER_SUCCESS.UTUB_NAME : String representing name of the UTub the user was added to,
        USER_SUCCESS.UTUB_USERS: Array containing strings of all usernames in the UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    # Get the other users' usernames and this user's UTub, assuming 3 valid users
    with app.app_context():
        # Confirm one user per utub
        assert len(Utub.query.all()) == len(Utub_Users.query.all())
        for utub in Utub.query.all():
            assert len(utub.members) == 1

        other_usernames = User.query.filter(
            User.username != current_user.username
        ).all()
        other_usernames = [other_user.username for other_user in other_usernames]

        utub_of_current_user = Utub_Users.query.filter(
            Utub_Users.user_id == current_user.id
        ).first()
        utub_id_of_current_user = utub_of_current_user.utub_id

        # Confirm number of users in the current user's UTub is 1
        current_number_of_users_in_utub = len(
            Utub_Users.query.filter(
                Utub_Users.user_id == current_user.id,
                Utub_Users.utub_id == utub_of_current_user.utub_id,
            ).all()
        )
        assert current_number_of_users_in_utub == 1

        # Confirm current user is owner of utub
        assert utub_of_current_user.to_utub.created_by == current_user

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Add the other users to the current user's UTubs
    for other_user in other_usernames:
        add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token, ADD_USER_FORM.USERNAME: other_user}

        with app.app_context():
            new_user = User.query.filter(User.username == other_user).first()

        added_user_response = client.post(
            f"/user/add/{utub_id_of_current_user}", data=add_user_form
        )
        current_number_of_users_in_utub += 1

        # Assert correct status code
        assert added_user_response.status_code == 200
        added_user_response_json = added_user_response.json

        # Assert JSON response is valid and contains updated data
        assert added_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert added_user_response_json[STD_JSON.MESSAGE] == USER_SUCCESS.USER_ADDED
        assert int(added_user_response_json[USER_SUCCESS.USER_ID_ADDED]) == new_user.id
        assert int(added_user_response_json[USER_SUCCESS.UTUB_ID]) == utub_id_of_current_user
        assert (
            added_user_response_json[USER_SUCCESS.UTUB_NAME] == utub_of_current_user.to_utub.name
        )
        assert (
            len(added_user_response_json[USER_SUCCESS.UTUB_USERS])
            == current_number_of_users_in_utub
        )
        assert other_user in added_user_response_json[USER_SUCCESS.UTUB_USERS]

        # Assert database user-utub associations is up to date
        with app.app_context():
            assert (
                len(Utub.query.get(utub_id_of_current_user).members)
                == current_number_of_users_in_utub
            )
            current_utub = Utub.query.get(utub_id_of_current_user)
            assert new_user in [user.to_user for user in current_utub.members]
            current_users_in_utub = set(
                [user.to_user.username for user in current_utub.members]
            )
            assert other_user in current_users_in_utub

            # Ensure correct count of Utub-User associations
            assert len(Utub_Users.query.all()) == initial_num_user_utubs + 1
            initial_num_user_utubs += 1


def test_add_then_remove_then_add_user_who_has_urls_to_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains other members
    WHEN the creator first removes another user who has added URLs, then wants to add the users back to their UTub by POST to
        "/user/add/<int: utub_id>" with correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 200 HTTP status code, that the database contains the newly added
        UTub-User association, the URL-Tag associations and UTub-URL associations are still valid,
        and that the backend responds with the correct JSON response

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : USER_SUCCESS.USER_ADDED,
        USER_SUCCESS.USER_ID_ADDED: Integer representing ID of the user just added,
        USER_SUCCESS.UTUB_ID : Integer representing ID of the UTub the user was added to,
        USER_SUCCESS.UTUB_NAME : String representing name of the UTub the user was added to,
        USER_SUCCESS.UTUB_USERS: Array containing strings of all usernames in the UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub they created
        utub_user_created = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()

        # Ensure other users in this UTub
        assert len(utub_user_created.members) > 1

        initial_num_of_users_in_utub = len(utub_user_created.members)

        # Get initial array of usernames
        initial_usernames_in_utub = [
            user.to_user.username for user in utub_user_created.members
        ]

        # Grab a sample user
        other_user_in_utub_with_urls = Utub_Users.query.filter(
            Utub_Users.user_id != current_user.id
        ).first()
        other_user_id_in_utub_with_urls = other_user_in_utub_with_urls.user_id
        other_user_username = other_user_in_utub_with_urls.to_user.username

        # Ensure this other user has URLs in the UTub
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_user_created.id,
                    Utub_Urls.user_id == other_user_id_in_utub_with_urls,
                ).all()
            )
            > 0
        )

        # Get number of URLs and tags in this UTub initially
        initial_num_of_urls_in_utub = len(
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_user_created.id).all()
        )
        initial_num_of_url_tags_in_utub = len(
            Url_Tags.query.filter(Url_Tags.utub_id == utub_user_created.id).all()
        )

        all_urls_in_utubs = len(Utub_Urls.query.all())
        all_url_tags_in_utub = len(Url_Tags.query.all())

    # Remove this user first
    remove_user_response = client.post(
        f"/user/remove/{utub_user_created.id}/{other_user_id_in_utub_with_urls}",
        data={ADD_USER_FORM.CSRF_TOKEN: csrf_token},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensure removed from UTub
    with app.app_context():
        assert (
            len(
                Utub_Users.query.filter(
                    Utub_Users.utub_id == utub_user_created.id,
                    Utub_Users.user_id == other_user_id_in_utub_with_urls,
                ).all()
            )
            == 0
        )

    # Add them back in
    add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token, ADD_USER_FORM.USERNAME: other_user_username}

    added_user_response = client.post(
        f"/user/add/{utub_user_created.id}", data=add_user_form
    )

    # Assert correct status code
    assert added_user_response.status_code == 200
    added_user_response_json = added_user_response.json

    # Assert JSON response is valid and contains updated data
    assert added_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert added_user_response_json[STD_JSON.MESSAGE] == USER_SUCCESS.USER_ADDED
    assert (
        int(added_user_response_json[USER_SUCCESS.USER_ID_ADDED])
        == other_user_id_in_utub_with_urls
    )
    assert int(added_user_response_json[USER_SUCCESS.UTUB_ID]) == utub_user_created.id
    assert added_user_response_json[USER_SUCCESS.UTUB_NAME] == utub_user_created.name
    assert len(added_user_response_json[USER_SUCCESS.UTUB_USERS]) == initial_num_of_users_in_utub
    assert set(added_user_response_json[USER_SUCCESS.UTUB_USERS]) == set(initial_usernames_in_utub)

    with app.app_context():
        # Ensure proper counts of all associations after removing then adding user who owned URLs in the UTub
        assert len(Utub_Urls.query.all()) == all_urls_in_utubs
        assert len(Url_Tags.query.all()) == all_url_tags_in_utub
        assert (
            len(Utub_Urls.query.filter(Utub_Urls.utub_id == utub_user_created.id).all())
            == initial_num_of_urls_in_utub
        )
        assert (
            len(Url_Tags.query.filter(Url_Tags.utub_id == utub_user_created.id).all())
            == initial_num_of_url_tags_in_utub
        )


def test_add_valid_users_to_utub_as_member(
    add_single_utub_as_user_without_logging_in,
    register_all_but_first_user,
    login_second_user_without_register,
):
    """
    GIVEN a logged-in user who is member of a UTub
    WHEN the user wants to add another other valid users to their UTub by POST to "/user/add/<int: utub_id>" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 403 HTTP status code,and the correct JSON response

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : "Failure",
        STD_JSON.MESSAGE : "Not authorized",
        STD_JSON.ERROR_CODE: 1
    }
    """
    client, csrf_token_string, _, app = login_second_user_without_register
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
        assert (
            len(Utub_Users.query.filter(Utub_Users.user_id == missing_user.id).all())
            == 0
        )

        # Verify current user isn't creator of UTub
        assert only_utub.created_by != current_user.id

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Try to add the missing member to the UTub
    add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token_string, ADD_USER_FORM.USERNAME: missing_user.username}

    missing_user_id = missing_user.id
    add_user_response = client.post(f"/user/add/{only_utub.id}", data=add_user_form)

    assert add_user_response.status_code == 403

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.NOT_AUTHORIZED
    assert int(add_user_response_json[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        assert (
            len(Utub_Users.query.filter(Utub_Users.user_id == missing_user_id).all())
            == 0
        )

        # Ensure correct count of Utub-User associations
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_add_duplicate_user_to_utub(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a logged-in user who owns a UTub that has another user as a member
    WHEN the creator wants to add the same other user to their UTub by POST to "/user/add/<int: utub_id>" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 400 HTTP status code,and the correct JSON response

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "User already in UTub",
        STD_JSON.ERROR_CODE: 2
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    # Add another user to first user's UTub
    with app.app_context():
        # Get this user's UTub
        current_user_utub_user_association = Utub_Users.query.filter(
            Utub_Users.user_id == current_user.id
        ).first()
        current_user_utub = current_user_utub_user_association.to_utub
        current_user_utub_id = current_user_utub.id

        # Verify only this user in the UTub
        assert current_user_utub_user_association.to_user == current_user
        assert len(current_user_utub_user_association.to_utub.members) == 1

        # Get another user that isn't the current user
        another_user = User.query.filter(User.id != current_user.id).first()
        another_user_username = another_user.username
        another_user_id = another_user.id

        # Add this other user to the current user's UTubs
        new_user_utub_association = Utub_Users()
        new_user_utub_association.to_utub = current_user_utub
        new_user_utub_association.to_user = another_user

        db.session.commit()

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Try adding this user to the UTub again
    add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token, ADD_USER_FORM.USERNAME: another_user_username}

    add_user_response = client.post(
        f"/user/add/{current_user_utub_id}", data=add_user_form
    )

    assert add_user_response.status_code == 400

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.USER_ALREADY_IN_UTUB
    assert int(add_user_response_json[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure the user is only associated with the UTub once
        assert (
            len(
                Utub_Users.query.filter(
                    Utub_Users.user_id == another_user_id,
                    Utub_Users.utub_id == current_user_utub_id,
                ).all()
            )
            == 1
        )

        current_user_utub = Utub.query.get(current_user_utub_id)
        other_user = User.query.filter(User.username == another_user_username).first()
        current_user_utub_members = [user.to_user for user in current_user_utub.members]

        # Ensure only creator and other user in utub
        assert len(current_user_utub_members) == 2
        assert current_user in current_user_utub_members
        assert other_user in current_user_utub_members

        # Ensure correct count of Utub-User associations
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_add_user_to_nonexistant_utub(
    register_all_but_first_user, login_first_user_with_register
):
    """
    GIVEN a logged-in user and other valid registered users with no UTubs created
    WHEN the logged-in user wants to another user to a UTub (none exist) by POST to "/user/add/<int: utub_id>" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 404 HTTP status code indicating no UTub could
        be found in the database
    """
    client, csrf_token, login_user, app = login_first_user_with_register

    with app.app_context():
        # Assert no UTubs exist
        assert len(Utub.query.all()) == 0

        # Assert no UTub-User associations exist
        assert len(Utub_Users.query.all()) == 0

        # Get user that isn't current user
        another_user = User.query.filter(User.id != current_user.id).first()

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Try adding this user to a UTub
    add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token, ADD_USER_FORM.USERNAME: another_user.username}

    add_user_response = client.post(f"/user/add/1", data=add_user_form)

    assert add_user_response.status_code == 404

    # Make sure no UTub User associations exist
    with app.app_context():
        # Assert no UTub-User associations exist
        assert len(Utub_Users.query.all()) == 0

        # Ensure correct count of Utub-User associations
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_add_nonexistant_user_to_utub(
    add_single_utub_as_user_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged-in user and their single UTub and no other registered users with no UTubs created
    WHEN the logged-in user wants to another user to their UTub by POST to "/user/add/<int: utub_id>" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of an unregistered user
    THEN ensure that the backend responds with a 404 HTTP status code indicating no user could
        be found in the database
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Ensure only one user exists
        assert len(User.query.all()) == 1

        # Ensure only one UTub and one UTub-User association exists
        assert len(Utub.query.all()) == 1
        assert len(Utub_Users.query.all()) == 1

        # Get the only UTub
        only_utub = Utub.query.first()

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Try adding this user to a UTub
    add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token, ADD_USER_FORM.USERNAME: "Not a registered user"}

    add_user_response = client.post(f"/user/add/{only_utub.id}", data=add_user_form)

    assert add_user_response.status_code == 404

    with app.app_context():
        # Ensure only one user exists
        assert len(User.query.all()) == 1

        # Ensure only one UTub and one UTub-User association exists
        assert len(Utub.query.all()) == 1
        assert len(Utub_Users.query.all()) == 1

        # Ensure correct count of Utub-User associations
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_add_user_to_another_users_utub(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN three valid users, first one being logged in, and each user has their own UTub and themselves being the only member
    WHEN the logged-in user wants to add another user to another person's UTub by POST to "/user/add/<int: utub_id>" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of an unregistered user
    THEN ensure that the backend responds with a 403 HTTP status code,and the correct JSON response

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : USER_FAILURE.NOT_AUTHORIZED,
        STD_JSON.ERROR_CODE: 1
    }
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get logged in user's UTub
        current_user_utub = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()

        # Make sure logged in user is only user in this UTub
        assert len(current_user_utub.members) == 1
        assert current_user in [user.to_user for user in current_user_utub.members]

        # Get another user's UTub
        another_utub = Utub_Users.query.filter(
            Utub_Users.user_id != current_user.id
        ).first()
        user_for_another_utub = another_utub.to_user
        another_utub = another_utub.to_utub

        # Get another user to add this UTub
        test_user_to_add = User.query.filter(
            User.id != user_for_another_utub.id, User.id != current_user.id
        ).first()
        test_user_to_add = test_user_to_add

        # Make sure this user isn't in the second user's UTub
        assert test_user_to_add not in [user.to_user for user in another_utub.members]

        # Make sure logged in user isn't creator of the second user's UTub
        assert current_user.id != another_utub.created_by

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Try to add this third user to the second user's UTub, logged as the first user
    add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token, ADD_USER_FORM.USERNAME: test_user_to_add.username}

    add_user_response = client.post(f"/user/add/{another_utub.id}", data=add_user_form)

    assert add_user_response.status_code == 403

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.NOT_AUTHORIZED
    assert int(add_user_response_json[STD_JSON.ERROR_CODE]) == 1

    # Confirm third user not in second user's UTub
    with app.app_context():
        assert (
            len(
                Utub_Users.query.filter(
                    Utub_Users.user_id == test_user_to_add.id,
                    Utub_Users.utub_id == another_utub.id,
                ).all()
            )
            == 0
        )

        # Ensure correct count of Utub-User associations
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_add_user_to_utub_invalid_form(
    add_single_utub_as_user_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is member of a UTub
    WHEN the user wants to add another other valid users to their UTub by POST to "/user/add/<int: utub_id>" with
        incorrect form data (missing ADD_USER_FORM.USERNAME), following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
    THEN ensure that the backend responds with a 404 HTTP status code,and the correct JSON response

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "Unable to add that user to this UTub",
        STD_JSON.ERROR_CODE: 3,
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the missing username field:
            {
                ADD_USER_FORM.USERNAME: ['This field is required.']
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    # Get logged in user's UTub
    with app.app_context():
        current_user_utub = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Try to add this third user to the second user's UTub, logged as the first user
    add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token}

    add_user_response = client.post(
        f"/user/add/{current_user_utub.id}", data=add_user_form
    )

    assert add_user_response.status_code == 404

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.UNABLE_TO_ADD
    assert int(add_user_response_json[STD_JSON.ERROR_CODE]) == 3
    assert add_user_response_json[STD_JSON.ERRORS][ADD_USER_FORM.USERNAME] == USER_FAILURE.FIELD_REQUIRED

    with app.app_context():
        # Ensure correct count of Utub-User associations
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_add_user_to_utub_missing_csrf_token(
    add_single_utub_as_user_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is member of a UTub
    WHEN the user wants to add another other valid users to their UTub by POST to "/user/add/<int: utub_id>" with
        a missing CSRF token
    THEN ensure that the backend responds with a 404 HTTP status code,and the correct JSON response
    """
    client, csrf_token, _, app = login_first_user_without_register

    # Get logged in user's UTub
    with app.app_context():
        current_user_utub = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    add_user_response = client.post(f"/user/add/{current_user_utub.id}")

    assert add_user_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in add_user_response.data

    with app.app_context():
        # Ensure correct count of Utub-User associations
        assert len(Utub_Users.query.all()) == initial_num_user_utubs
