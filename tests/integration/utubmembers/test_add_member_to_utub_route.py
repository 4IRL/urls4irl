from flask import url_for
from flask_login import current_user
import pytest

from src import db
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import ADD_USER_FORM
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS
from src.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS

pytestmark = pytest.mark.members


def test_add_valid_users_to_utub_as_creator(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains only themselves, no URLs or tags
    WHEN the user wants to add two other valid users to their UTub by POST to "/utubs/<int:utub_id>/members" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 200 HTTP status code, that the database contains the newly added
        UTub-User association, and that the backend responds with the correct JSON response

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : USER_SUCCESS.USER_ADDED,
        USER_SUCCESS.UTUB_ID : Integer representing ID of the UTub the user was added to,
        USER_SUCCESS.MEMBER: {
            MODELS.USERNAME: String representing newly added member's username
            MODELS.ID: Integer representing newly added member's userID
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    # Get the other users' usernames and this user's UTub, assuming 3 valid users
    with app.app_context():
        other_usernames: list[Users] = Users.query.filter(
            Users.username != current_user.username
        ).all()
        other_usernames = [other_user.username for other_user in other_usernames]

        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role == Member_Role.CREATOR,
        ).first()
        utub_of_current_user: Utubs = utub_member.to_utub
        utub_id_of_current_user = utub_of_current_user.id

        # Confirm number of users in the current user's UTub is 1
        current_number_of_users_in_utub = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id_of_current_user,
        ).count()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Add the other users to the current user's UTubs
    for other_user in other_usernames:
        add_user_form = {
            ADD_USER_FORM.CSRF_TOKEN: csrf_token,
            ADD_USER_FORM.USERNAME: other_user,
        }

        with app.app_context():
            new_user: Users = Users.query.filter(Users.username == other_user).first()

        added_user_response = client.post(
            url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
            data=add_user_form,
        )

        # Assert correct status code
        assert added_user_response.status_code == 200
        added_user_response_json = added_user_response.json

        # Assert JSON response is valid and contains updated data
        assert added_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert added_user_response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ADDED
        assert (
            int(added_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.ID])
            == new_user.id
        )
        assert (
            added_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.USERNAME]
            == other_user
        )
        assert (
            int(added_user_response_json[MEMBER_SUCCESS.UTUB_ID])
            == utub_id_of_current_user
        )

        current_number_of_users_in_utub += 1
        initial_num_user_utubs += 1
        # Assert database user-utub associations is up to date
        with app.app_context():
            assert (
                Utub_Members.query.filter(
                    Utub_Members.utub_id == utub_id_of_current_user
                ).count()
                == current_number_of_users_in_utub
            )
            assert (
                Utub_Members.query.get((utub_id_of_current_user, new_user.id))
                is not None
            )
            other_user_obj: Users = Users.query.filter(
                Users.username == other_user
            ).first()
            assert (
                Utub_Members.query.get((utub_id_of_current_user, other_user_obj.id))
                is not None
            )

            # Ensure correct count of Utub-User associations
            assert Utub_Members.query.count() == initial_num_user_utubs


def test_add_then_remove_then_add_user_who_has_urls_to_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains other members
    WHEN the creator first removes another user who has added URLs, then wants to add the users back to their UTub by POST to
        "/utubs/<int:utub_id>/members" with correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 200 HTTP status code, that the database contains the newly added
        UTub-User association, the URL-Tag associations and UTub-URL associations are still valid,
        and that the backend responds with the correct JSON respons            current_users_in_utub = set(
                [user.to_user.username for user in current_utub.members]
            )e

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : USER_SUCCESS.USER_ADDED,
        USER_SUCCESS.UTUB_ID : Integer representing ID of the UTub the user was added to,
        USER_SUCCESS.MEMBER: {
            MODELS.USERNAME: String representing newly added member's username
            MODELS.ID: Integer representing newly added member's userID
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub they created
        utub_user_created: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        initial_num_of_users_in_utub = len(utub_user_created.members)

        # Grab a sample user
        other_user_in_utub_with_urls: Utub_Members = [
            member
            for member in utub_user_created.members
            if member.user_id != current_user.id
        ][-1]
        other_user_id_in_utub_with_urls = other_user_in_utub_with_urls.user_id
        other_user_username = other_user_in_utub_with_urls.to_user.username

        # Get number of URLs and tags in this UTub initially
        initial_num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_created.id
        ).count()
        initial_num_of_url_tags_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_created.id
        ).count()

        all_urls_in_utubs = Utub_Urls.query.count()
        all_url_tags_in_utub = Utub_Url_Tags.query.count()

    # Remove this user first
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=utub_user_created.id,
            user_id=other_user_id_in_utub_with_urls,
        ),
        data={ADD_USER_FORM.CSRF_TOKEN: csrf_token},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensure removed from UTub
    with app.app_context():
        assert (
            Utub_Members.query.get(
                (utub_user_created.id, other_user_id_in_utub_with_urls)
            )
            is None
        )

    # Add them back in
    add_user_form = {
        ADD_USER_FORM.CSRF_TOKEN: csrf_token,
        ADD_USER_FORM.USERNAME: other_user_username,
    }

    added_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_user_created.id),
        data=add_user_form,
    )

    # Assert correct status code
    assert added_user_response.status_code == 200
    added_user_response_json = added_user_response.json

    # Assert JSON response is valid and contains updated data
    assert added_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert added_user_response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ADDED
    assert (
        int(added_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.ID])
        == other_user_id_in_utub_with_urls
    )
    assert (
        added_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.USERNAME]
        == other_user_username
    )
    assert int(added_user_response_json[MEMBER_SUCCESS.UTUB_ID]) == utub_user_created.id

    with app.app_context():
        # Ensure proper counts of all associations after removing then adding user who owned URLs in the UTub
        assert Utub_Urls.query.count() == all_urls_in_utubs
        assert Utub_Url_Tags.query.count() == all_url_tags_in_utub
        assert (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_user_created.id).count()
            == initial_num_of_urls_in_utub
        )
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_user_created.id
            ).count()
            == initial_num_of_url_tags_in_utub
        )

        assert (
            Utub_Members.query.filter(
                Utub_Members.utub_id == utub_user_created.id
            ).count()
            == initial_num_of_users_in_utub
        )


def test_add_valid_users_to_utub_as_member(
    add_single_utub_as_user_without_logging_in,
    register_all_but_first_user,
    login_second_user_without_register,
):
    """
    GIVEN a logged-in user who is member of a UTub
    WHEN the user wants to add another other valid users to their UTub by POST to "/utubs/<int:utub_id>/members" with
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
    client, csrf_token, _, app = login_second_user_without_register

    with app.app_context():
        # Add second user to first UTub
        only_utub: Utubs = Utubs.query.first()
        new_utub_user_association = Utub_Members()
        new_utub_user_association.to_user = current_user
        new_utub_user_association.to_utub = only_utub
        db.session.commit()

        # Find user that isn't in the UTub
        # First get all users
        all_users: list[Users] = Users.query.all()

        # Get the missing user from the UTub's members
        all_utub_members = only_utub.members
        all_utub_members = [user.to_user for user in all_utub_members]

        # Get the missing user
        for user in all_users:
            if user not in all_utub_members:
                missing_user = user

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Try to add the missing member to the UTub
    add_user_form = {
        ADD_USER_FORM.CSRF_TOKEN: csrf_token,
        ADD_USER_FORM.USERNAME: missing_user.username,
    }

    missing_user_id = missing_user.id
    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=only_utub.id), data=add_user_form
    )

    assert add_user_response.status_code == 403

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_user_response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.NOT_AUTHORIZED
    assert int(add_user_response_json[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        assert Utub_Members.query.get((only_utub.id, missing_user_id)) is None

        # Ensure correct count of Utub-User associations
        assert Utub_Members.query.count() == initial_num_user_utubs


def test_add_duplicate_user_to_utub(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a logged-in user who owns a UTub that has another user as a member
    WHEN the creator wants to add the same other user to their UTub by POST to "/utubs/<int:utub_id>/members" with
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
        current_user_utub_user_association: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).first()
        current_user_utub = current_user_utub_user_association.to_utub
        current_user_utub_id = current_user_utub.id

        # Get another user that isn't the current user
        another_user: Users = Users.query.filter(Users.id != current_user.id).first()
        another_user_username = another_user.username
        another_user_id = another_user.id

        # Add this other user to the current user's UTubs
        new_user_utub_association = Utub_Members()
        new_user_utub_association.to_utub = current_user_utub
        new_user_utub_association.to_user = another_user

        db.session.commit()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Try adding this user to the UTub again
    add_user_form = {
        ADD_USER_FORM.CSRF_TOKEN: csrf_token,
        ADD_USER_FORM.USERNAME: another_user_username,
    }

    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=current_user_utub_id),
        data=add_user_form,
    )

    assert add_user_response.status_code == 400

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_user_response_json[STD_JSON.MESSAGE]
        == MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB
    )
    assert int(add_user_response_json[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure the user is only associated with the UTub once
        assert (
            Utub_Members.query.filter(
                Utub_Members.user_id == another_user_id,
                Utub_Members.utub_id == current_user_utub_id,
            ).count()
            == 1
        )

        current_user_utub: Utubs = Utubs.query.get(current_user_utub_id)
        other_user: Users = Users.query.filter(
            Users.username == another_user_username
        ).first()
        current_user_utub_members = [user.to_user for user in current_user_utub.members]

        # Ensure only creator and other user in utub
        assert len(current_user_utub_members) == 2
        assert current_user in current_user_utub_members
        assert other_user in current_user_utub_members

        # Ensure correct count of Utub-User associations
        assert Utub_Members.query.count() == initial_num_user_utubs


def test_add_user_to_nonexistant_utub(
    register_all_but_first_user, login_first_user_with_register
):
    """
    GIVEN a logged-in user and other valid registered users with no UTubs created
    WHEN the logged-in user wants to another user to a UTub (none exist) by POST to "/utubs/<int:utub_id>/members" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 404 HTTP status code indicating no UTub could
        be found in the database
    """
    client, csrf_token, _, app = login_first_user_with_register

    with app.app_context():
        # Get user that isn't current user
        another_user: Users = Users.query.filter(Users.id != current_user.id).first()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Try adding this user to a UTub
    add_user_form = {
        ADD_USER_FORM.CSRF_TOKEN: csrf_token,
        ADD_USER_FORM.USERNAME: another_user.username,
    }

    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=1), data=add_user_form
    )

    assert add_user_response.status_code == 404

    # Make sure no UTub User associations exist
    with app.app_context():
        # Ensure correct count of Utub-User associations
        assert (
            Utub_Members.query.count() == initial_num_user_utubs
            and initial_num_user_utubs == 0
        )


def test_add_nonexistant_user_to_utub(
    add_single_utub_as_user_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged-in user and their single UTub and no other registered users with no UTubs created
    WHEN the logged-in user wants to another user to their UTub by POST to "/utubs/<int:utub_id>/members" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of an unregistered user
    THEN ensure that the backend responds with a 404 HTTP status code indicating no user could
        be found in the database
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub
        only_utub: Utubs = Utubs.query.first()

        # Count all user-utub associations in db
        initial_num_users = Users.query.count()
        initial_num_user_utubs = Utub_Members.query.count()
        initial_num_utubs = Utubs.query.count()

    # Try adding this user to a UTub
    add_user_form = {
        ADD_USER_FORM.CSRF_TOKEN: csrf_token,
        ADD_USER_FORM.USERNAME: "Not a registered user",
    }

    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=only_utub.id), data=add_user_form
    )

    assert add_user_response.status_code == 400

    with app.app_context():
        # Ensure only one user exists
        assert Users.query.count() == initial_num_users

        # Ensure only one UTub and one UTub-User association exists
        assert Utubs.query.count() == initial_num_utubs
        assert Utub_Members.query.count() == initial_num_user_utubs


def test_add_user_to_another_users_utub(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN three valid users, first one being logged in, and each user has their own UTub and themselves being the only member
    WHEN the logged-in user wants to add another user to another person's UTub by POST to "/utubs/<int:utub_id>/members" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of an unregistered user
    THEN ensure that the backend responds with a 403 HTTP status code,and the correct JSON response

    The correct JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : MEMBER_FAILURE.NOT_AUTHORIZED,
        STD_JSON.ERROR_CODE: 1
    }
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get another user's UTub
        another_member_in_another_utub: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()
        user_for_another_utub: Users = another_member_in_another_utub.to_user
        another_utub: Utubs = another_member_in_another_utub.to_utub

        # Get another user to add this UTub
        test_user_to_add: Users = Users.query.filter(
            Users.id != user_for_another_utub.id, Users.id != current_user.id
        ).first()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Try to add this third user to the second user's UTub, logged as the first user
    add_user_form = {
        ADD_USER_FORM.CSRF_TOKEN: csrf_token,
        ADD_USER_FORM.USERNAME: test_user_to_add.username,
    }

    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=another_utub.id),
        data=add_user_form,
    )

    assert add_user_response.status_code == 403

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_user_response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.NOT_AUTHORIZED
    assert int(add_user_response_json[STD_JSON.ERROR_CODE]) == 1

    # Confirm third user not in second user's UTub
    with app.app_context():
        assert Utub_Members.query.get((another_utub.id, test_user_to_add.id)) is None

        # Ensure correct count of Utub-User associations
        assert Utub_Members.query.count() == initial_num_user_utubs


def test_add_user_to_utub_invalid_form(
    add_single_utub_as_user_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is member of a UTub
    WHEN the user wants to add another other valid users to their UTub by POST to "/utubs/<int:utub_id>/members" with
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
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Try to add this third user to the second user's UTub, logged as the first user
    add_user_form = {ADD_USER_FORM.CSRF_TOKEN: csrf_token}

    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=current_user_utub.id),
        data=add_user_form,
    )

    assert add_user_response.status_code == 400

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_user_response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER
    )
    assert int(add_user_response_json[STD_JSON.ERROR_CODE]) == 3
    assert (
        add_user_response_json[STD_JSON.ERRORS][ADD_USER_FORM.USERNAME]
        == MEMBER_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Ensure correct count of Utub-User associations
        assert Utub_Members.query.count() == initial_num_user_utubs


def test_add_user_to_utub_missing_csrf_token(
    add_single_utub_as_user_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is member of a UTub
    WHEN the user wants to add another other valid users to their UTub by POST to "/utubs/<int:utub_id>/members" with
        a missing CSRF token
    THEN ensure that the backend responds with a 404 HTTP status code,and the correct JSON response
    """
    client, _, _, app = login_first_user_without_register

    # Get logged in user's UTub
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=current_user_utub.id)
    )

    assert add_user_response.status_code == 403
    assert add_user_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in add_user_response.data

    with app.app_context():
        # Ensure correct count of Utub-User associations
        assert Utub_Members.query.count() == initial_num_user_utubs


def test_add_valid_users_updates_utub_last_updated(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains only themselves, no URLs or tags
    WHEN the user wants to add two other valid users to their UTub by POST to "/utubs/<int:utub_id>/members" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 200 HTTP status code, and the UTub in the database
        shows its last updated field has been updated
    """
    client, csrf_token, _, app = login_first_user_without_register

    # Get the other users' usernames and this user's UTub, assuming 3 valid users
    with app.app_context():
        other_users: list[Users] = Users.query.filter(
            Users.username != current_user.username
        ).all()
        other_usernames = [other_user.username for other_user in other_users]

        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).first()
        utub_of_current_user: Utubs = utub_member.to_utub
        utub_id_of_current_user = utub_of_current_user.id
        last_updated = utub_of_current_user.last_updated

    # Add the other users to the current user's UTubs
    for other_user in other_usernames:
        add_user_form = {
            ADD_USER_FORM.CSRF_TOKEN: csrf_token,
            ADD_USER_FORM.USERNAME: other_user,
        }

        added_user_response = client.post(
            url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
            data=add_user_form,
        )

        # Assert correct status code
        assert added_user_response.status_code == 200

        # Assert database user-utub associations is up to date
        with app.app_context():
            current_utub: Utubs = Utubs.query.get(utub_id_of_current_user)
            assert (current_utub.last_updated - last_updated).total_seconds() > 0
            last_updated = current_utub.last_updated


def test_add_duplicate_user_to_utub_does_not_update_utub_last_updated(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a logged-in user who owns a UTub that has another user as a member
    WHEN the creator wants to add the same other user to their UTub by POST to "/utubs/<int:utub_id>/members" with
        correct form data, following the following format:
            ADD_USER_FORM.CSRF_TOKEN: String containing CSRF token for validation
            ADD_USER_FORM.USERNAME: Username of the user to add
    THEN ensure that the backend responds with a 400 HTTP status code, and the UTub's last updated is not changed
    """
    client, csrf_token, _, app = login_first_user_without_register

    # Add another user to first user's UTub
    with app.app_context():
        # Get this user's UTub
        current_user_utub_user_association: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).first()
        current_user_utub = current_user_utub_user_association.to_utub
        current_user_utub_id = current_user_utub.id

        # Get another user that isn't the current user
        another_user: Users = Users.query.filter(Users.id != current_user.id).first()
        another_user_username = another_user.username

        # Add this other user to the current user's UTubs
        new_user_utub_association = Utub_Members()
        new_user_utub_association.to_utub = current_user_utub
        new_user_utub_association.to_user = another_user

        db.session.commit()
        current_user_utub = Utubs.query.get(current_user_utub_id)
        initial_last_updated = current_user_utub.last_updated

    # Try adding this user to the UTub again
    add_user_form = {
        ADD_USER_FORM.CSRF_TOKEN: csrf_token,
        ADD_USER_FORM.USERNAME: another_user_username,
    }

    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=current_user_utub_id),
        data=add_user_form,
    )

    assert add_user_response.status_code == 400

    with app.app_context():
        current_user_utub: Utubs = Utubs.query.get(current_user_utub_id)
        assert current_user_utub.last_updated == initial_last_updated
