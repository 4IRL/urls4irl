from flask import url_for
from flask_login import current_user

from src import db
from src.models import Utub, Utub_Users, User, Utub_Urls, Url_Tags
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import GENERAL_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.user_strs import USER_FAILURE, USER_SUCCESS


def test_remove_valid_user_from_utub_as_creator(
    add_single_user_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged in user who is creator of a UTub that has another member in it, with no URLs or tags in the UTub
    WHEN the logged in user tries to remove second user by DELETE to "/utubs/<int:utub_id>/members/<int:user_id>" with valid
        information and a valid CSRF token
    THEN ensure the user gets removed from the UTub by checking UTub-User associations, that the server responds with a
        200 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : USER_SUCCESS.USER_REMOVED,
        USER_SUCCESS.USER_ID_REMOVED : Integer representing ID of user removed,
        USER_SUCCESS.USERNAME_REMOVED: Username of user deleted,
        USER_SUCCESS.UTUB_ID : Interger representing ID of UTub the user was removed from,
        USER_SUCCESS.UTUB_NAME : String representing name of UTub removed,
        USER_SUCCESS.UTUB_USERS: Array of string usernames of all members of UTub after the user was removed
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub, which contains two members
        current_utub = Utub.query.first()

        # Ensure creator is currently logged in
        assert current_utub.created_by == current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2

        # Grab the second user from the members
        second_user_in_utub_association = Utub_Users.query.filter(
            Utub_Users.utub_id == current_utub.id, Utub_Users.user_id != current_user.id
        ).first()
        second_user_in_utub = second_user_in_utub_association.to_user

        # Ensure second user in this UTub
        assert second_user_in_utub in [user.to_user for user in current_utub.members]

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Remove second user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=second_user_in_utub.id
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_user_response_json[STD_JSON.MESSAGE] == USER_SUCCESS.USER_REMOVED
    assert (
        int(remove_user_response_json[USER_SUCCESS.USER_ID_REMOVED])
        == second_user_in_utub.id
    )
    assert (
        remove_user_response_json[USER_SUCCESS.USERNAME_REMOVED]
        == second_user_in_utub.username
    )
    assert int(remove_user_response_json[USER_SUCCESS.UTUB_ID]) == current_utub.id
    assert remove_user_response_json[USER_SUCCESS.UTUB_NAME] == current_utub.name
    assert remove_user_response_json[USER_SUCCESS.UTUB_USERS] == [current_user.username]

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == 1

        # Ensure second user not in this UTub
        assert second_user_in_utub not in [
            user.to_user for user in current_utub.members
        ]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs - 1


def test_remove_self_from_utub_as_member(
    add_single_user_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a logged in user who is a member of a UTub
    WHEN the logged in user tries to leave the UTub by DELETE to "/utubs/<int:utub_id>/members/<int:user_id>" with valid
        information and a valid CSRF token
    THEN ensure the user gets removed from the UTub by checking UTub-User associations, that the server responds with a
        200 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : USER_SUCCESS.USER_REMOVED,
        USER_SUCCESS.USER_ID_REMOVED : Integer representing ID of user removed,
        USER_SUCCESS.USERNAME_REMOVED: Username of user deleted,
        USER_SUCCESS.UTUB_ID : Interger representing ID of UTub the user was removed from,
        USER_SUCCESS.UTUB_NAME : String representing name of UTub removed,
        USER_SUCCESS.UTUB_USERS: Array of string usernames of all members of UTub after the user was removed
    }
    """

    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub = Utub.query.first()

        # Ensure creator is not currently logged in user
        assert current_utub.created_by != current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2

        # Ensure second user in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

        current_user_id = int(current_user.id)
        current_user_username = current_user.username

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=current_user_id),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_user_response_json[STD_JSON.MESSAGE] == USER_SUCCESS.USER_REMOVED
    # breakpoint()
    assert (
        int(remove_user_response_json[USER_SUCCESS.USER_ID_REMOVED]) == current_user_id
    )
    assert (
        remove_user_response_json[USER_SUCCESS.USERNAME_REMOVED]
        == current_user_username
    )
    assert int(remove_user_response_json[USER_SUCCESS.UTUB_ID]) == current_utub.id
    assert remove_user_response_json[USER_SUCCESS.UTUB_NAME] == current_utub.name
    assert (
        current_user_username not in remove_user_response_json[USER_SUCCESS.UTUB_USERS]
    )

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == 1

        # Ensure logged in user not in this UTub
        assert current_user not in [user.to_user for user in current_utub.members]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs - 1


def test_remove_valid_user_with_urls_from_utub_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a logged in user who is creator of a UTub that has another member in it, and this user has added URLs that also have tags
        associated with them
    WHEN the logged in user tries to remove second user by DELETE to "/utubs/<int:utub_id>/members/<int:user_id>" with valid
        information and a valid CSRF token
    THEN ensure the user gets removed from the UTub by checking UTub-User associations, that the server responds with a
        200 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : USER_SUCCESS.USER_REMOVED,
        USER_SUCCESS.USER_ID_REMOVED : Integer representing ID of user removed,
        USER_SUCCESS.USERNAME_REMOVED: Username of user deleted,
        USER_SUCCESS.UTUB_ID : Interger representing ID of UTub the user was removed from,
        USER_SUCCESS.UTUB_NAME : String representing name of UTub removed,
        USER_SUCCESS.UTUB_USERS: Array of string usernames of all members of UTub after the user was removed
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get this creator's UTub
        current_utub = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure creator is currently logged in
        assert current_utub.created_by == current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) > 1

        # Grab another user from the members
        second_user_in_utub_association = Utub_Users.query.filter(
            Utub_Users.utub_id == current_utub.id, Utub_Users.user_id != current_user.id
        ).first()
        second_user_in_utub = second_user_in_utub_association.to_user

        # Ensure this user has URLs associated with them in UTub
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_utub.id,
                    Utub_Urls.user_id == second_user_in_utub.id,
                ).all()
            )
            > 0
        )
        example_url_of_user = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_utub.id,
            Utub_Urls.user_id == second_user_in_utub.id,
        ).first()

        # Ensure this user has URLs that have tags associated with them
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == current_utub.id,
                    Url_Tags.url_id == example_url_of_user.url_id,
                ).all()
            )
            > 0
        )

        # Get initial counts of URLs, Tags, and relative associations in the database
        current_num_of_urls_in_utub = len(current_utub.utub_urls)
        current_num_of_url_tags_in_utub = len(current_utub.utub_url_tags)

        all_urls_utub_associations = len(Utub_Urls.query.all())
        all_urls_tag_associations = len(Url_Tags.query.all())

        # Ensure second user in this UTub
        assert second_user_in_utub in [user.to_user for user in current_utub.members]

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Remove second user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=second_user_in_utub.id
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_user_response_json[STD_JSON.MESSAGE] == USER_SUCCESS.USER_REMOVED
    assert (
        int(remove_user_response_json[USER_SUCCESS.USER_ID_REMOVED])
        == second_user_in_utub.id
    )
    assert (
        remove_user_response_json[USER_SUCCESS.USERNAME_REMOVED]
        == second_user_in_utub.username
    )
    assert int(remove_user_response_json[USER_SUCCESS.UTUB_ID]) == current_utub.id
    assert remove_user_response_json[USER_SUCCESS.UTUB_NAME] == current_utub.name

    current_users_in_utub = remove_user_response_json[USER_SUCCESS.UTUB_USERS]

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure proper serialization of user usernames that are left in the UTub
        assert current_users_in_utub == [
            user.to_user.username for user in current_utub.members
        ]

        # Ensure second user not in this UTub
        assert second_user_in_utub.id not in [
            user.user_id for user in current_utub.members
        ]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs - 1

        # Ensure URL-UTub associations aren't removed
        assert (
            len(Utub_Urls.query.filter(Utub_Urls.utub_id == current_utub.id).all())
            == current_num_of_urls_in_utub
        )

        # Ensure URL-Tag associations aren't removed
        assert (
            len(Url_Tags.query.filter(Url_Tags.utub_id == current_utub.id).all())
            == current_num_of_url_tags_in_utub
        )

        # Ensure all associations still correct
        assert len(Url_Tags.query.all()) == all_urls_tag_associations
        assert len(Utub_Urls.query.all()) == all_urls_utub_associations


def test_remove_self_from_utub_as_creator(
    add_single_user_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged in user who is a creator of a UTub
    WHEN the logged in user tries to leave the UTub by DELETE to "/utubs/<int:utub_id>/members/<int:user_id>" with valid
        information and a valid CSRF token
    THEN ensure the user does not get removed from the UTub, the server responds with a 400 HTTP status code,
        and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : USER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF,
        STD_JSON.ERROR_CODE: 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

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

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=current_user.id),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    assert remove_user_response.status_code == 400

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_user_response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 1

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user still creator of this UTub
        assert current_user == current_utub.created_by

        # Ensure logged in user still in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_remove_self_from_utub_no_csrf_token_as_member(
    add_single_user_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a logged in user who is a member of a UTub
    WHEN the logged in user tries to leave the UTub by DELETE to "/utubs/<int:utub_id>/members/<int:user_id>" with valid
        information and no CSRF token
    THEN ensure the user does not get removed from the UTub by checking UTub-User associations, that the server responds with a
        400 HTTP status code indicating no CSRF token included
    """

    client, _, _, app = login_second_user_without_register

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

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=current_user.id),
    )

    # Assert invalid response code
    assert remove_user_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in remove_user_response.data

    # Ensure database is correct
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user still in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_remove_valid_user_from_utub_no_csrf_token_as_creator(
    add_single_user_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged in user who is creator of a UTub that has another member in it
    WHEN the logged in user tries to remove second user by DELETE to "/utubs/<int:utub_id>/members/<int:user_id>" with valid
        information and a missing CSRF token
    THEN ensure the user does not get removed from the UTub by checking UTub-User associations, that the server responds
        with a 400 HTTP status code indicating the CSRF token is missing
    """

    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub = Utub.query.first()

        # Ensure creator is currently logged in
        assert current_utub.created_by == current_user

        # Ensure multiple users in this Utub
        assert len(current_utub.members) == 2
        current_number_of_users_in_utub = len(current_utub.members)

        # Grab the second user from the members
        second_user_in_utub_association = Utub_Users.query.filter(
            Utub_Users.utub_id == current_utub.id, Utub_Users.user_id != current_user.id
        ).first()
        second_user_in_utub = second_user_in_utub_association.to_user

        # Ensure second user in this UTub
        assert second_user_in_utub in [user.to_user for user in current_utub.members]

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Remove second user
    remove_user_response = client.delete(
        url_for(ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=current_user.id),
    )

    # Assert invalid response code
    assert remove_user_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in remove_user_response.data

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utub.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user is still creator
        assert current_user == current_utub.created_by

        # Ensure second user still in this UTub
        assert second_user_in_utub in [user.to_user for user in current_utub.members]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_remove_valid_user_from_invalid_utub_as_member_or_creator(
    add_single_user_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a valid existing user and a nonexistent UTub
    WHEN the user requests to remove themselves from the UTub via a DELETE to "/utubs/<int:utub_id>/members/<int:user_id>"
    THEN ensure that a 404 status code response is given when the UTub cannot be found in the database
    """

    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        all_current_utubs = Utub.query.all()

        invalid_utub_id = 0

        while invalid_utub_id in [utub.id for utub in all_current_utubs]:
            invalid_utub_id += 1

        # Ensure given UTub does not exist
        assert invalid_utub_id not in [utub.id for utub in all_current_utubs]

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=invalid_utub_id, user_id=current_user.id),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 404 HTTP status code response
    assert remove_user_response.status_code == 404

    # Ensure 404 response is given no matter what USER ID
    for num in range(10):
        remove_user_response = client.delete(
            url_for(ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=invalid_utub_id, user_id=num),
            data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
        )

        # Ensure 404 HTTP status code response
        assert remove_user_response.status_code == 404

    with app.app_context():
        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_remove_invalid_user_from_utub_as_creator(
    add_single_user_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub that is currently logged in
    WHEN the user requests to remove a nonexistent member from the UTub via a DELETE to "/utubs/<int:utub_id>/members/<int:user_id>"
    THEN ensure that a 404 status code response is given when the user cannot be found in the UTub, and the proper JSON response is given

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : USER_FAILURE.USER_NOT_IN_UTUB,
        STD_JSON.ERROR_CODE: 3
    }
    """

    client, csrf_token_string, _, app = login_first_user_without_register

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
        assert user_id_not_in_utub not in [
            user.user_id for user in current_utub.members
        ]

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=user_id_not_in_utub
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 404 HTTP status code response
    assert remove_user_response.status_code == 404

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert remove_user_response_json[STD_JSON.MESSAGE] == USER_FAILURE.USER_NOT_IN_UTUB
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_remove_invalid_user_from_utub_as_member(
    add_single_user_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a member of a UTub that is currently logged in
    WHEN the user requests to remove a nonexistent member from the UTub via a DELETE to "/utubs/<int:utub_id>/members/<int:user_id>"
    THEN ensure that a 403 status code response is given when the user cannot be found in the UTub, and the proper JSON response is given

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : USER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        STD_JSON.ERROR_CODE: 2
    }
    """

    client, csrf_token_string, _, app = login_second_user_without_register

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
        assert user_id_not_in_utub not in [
            user.user_id for user in current_utub.members
        ]

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=user_id_not_in_utub
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 403 HTTP status code response
    assert remove_user_response.status_code == 403

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_user_response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_remove_another_member_from_same_utub_as_member(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a logged in user who is a member of a UTub with another member and the creator
    WHEN the logged in user tries to remove the other member (not the creator) from the UTub by DELETE to
        "/utubs/<int:utub_id>/members/<int:user_id>" with valid information and a valid CSRF token
    THEN ensure the other member does not get removed from the UTub by checking UTub-User associations,
        that the server responds with a 403 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : USER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        STD_JSON.ERROR_CODE: 2
    }
    """

    client, csrf_token_string, _, app = login_second_user_without_register

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

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Attempt to remove other user from UTub as a member
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=current_utub.id, user_id=other_utub_member.id
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 403

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_user_response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 2

    # Ensure database is correctly updated
    with app.app_context():
        # Grab the UTub again
        current_utub = Utub.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user in this UTub
        assert current_user in [user.to_user for user in current_utub.members]

        # Ensure the bystander member is still in the UTub
        assert other_utub_member in [user.to_user for user in current_utub.members]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_remove_member_from_another_utub_as_creator_of_another_utub(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a logged in user who is a creator of a UTub, and given another UTub with a creator and member who are not
        the current logged in user

        Current logged in user is ID == 1
        Have current user be creator of UTub, and try to remove a member from another UTub
        UTUB 1 -> Creator == 1, nobody else
        UTUB 2 -> Creator == 2, contains 3

    WHEN the logged in user tries to remove the other member (not the creator) from the other UTub by DELETE to
        "/utubs/<int:utub_id>/members/<int:user_id>" with valid information and a valid CSRF token
    THEN ensure the other member does not get removed from the UTub by checking UTub-User associations,
        that the server responds with a 403 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : USER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        STD_JSON.ERROR_CODE: 2
    }
    """

    client, csrf_token_string, _, app = login_first_user_without_register

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

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Try to remove the third user from second user's UTub as the first user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=second_user_utub.id, user_id=third_user.id
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 403 HTTP status code response
    assert remove_user_response.status_code == 403

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_user_response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 2

    # Ensure database still shows user 3 is member of utub 2
    with app.app_context():
        second_user_utub = Utub.query.get(2)
        third_user = User.query.get(3)

        assert third_user in [user.to_user for user in second_user_utub.members]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs


def test_remove_member_from_another_utub_as_member_of_another_utub(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a logged in user who is a member of a UTub, and given another UTub with a creator and member who are not
        the current logged in user

        Current logged in user is ID == 2
        Have current user be member of UTub, and try to remove a member from another UTub
        UTUB 1 -> Creator == 1, contains members 2 and 3

        Create UTub by user 3, include User 1
        UTUB 2 -> Creator == 3, contains 1

        Have logged in user with ID == 2 try to remove User 1 from UTub 3

    WHEN the logged in user tries to remove the other member (not the creator) from the other UTub by DELETE to
        "/utubs/<int:utub_id>/members/<int:user_id>" with valid information and a valid CSRF token
    THEN ensure the other member does not get removed from the UTub by checking UTub-User associations,
        that the server responds with a 403 HTTP status code, and that the server sends back the proper JSON response

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : USER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        STD_JSON.ERROR_CODE: 2
    }
    """
    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        # Get the third user
        third_user = User.query.get(3)

        # Have third user make another UTub
        new_utub_from_third_user = Utub(
            name="Third User's UTub", utub_creator=third_user.id, utub_description=""
        )
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
        assert current_user not in [
            user.to_user for user in new_utub_from_third_user.members
        ]

        # Ensure current user is a member of a UTub
        all_utub_users = Utub_Users.query.filter(
            Utub_Users.user_id == current_user.id
        ).all()
        assert len(all_utub_users) > 0

        # Count all user-utub associations in db
        initial_num_user_utubs = len(Utub_Users.query.all())

    # Try to remove the first user from second user's UTub as the first user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=new_utub_from_third_user.id,
            user_id=first_user.id,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 403 HTTP status code response
    assert remove_user_response.status_code == 403

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_user_response_json[STD_JSON.MESSAGE]
        == USER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 2

    # Ensure database still shows user 1 is member of utub 2
    with app.app_context():
        third_user_utub = Utub.query.get(2)
        first_user = User.query.get(1)

        assert first_user in [user.to_user for user in third_user_utub.members]

        # Ensure counts of Utub-User associations is correct
        assert len(Utub_Users.query.all()) == initial_num_user_utubs
