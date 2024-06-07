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
from src.utils.strings.form_strs import GENERAL_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS
from src.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS

pytestmark = pytest.mark.members


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
        USER_SUCCESS.MEMBER : {
            MODELS.ID : Integer representing ID of user removed,
            MODELS.USERNAME: Username of user deleted,
        }
        USER_SUCCESS.UTUB_ID : Interger representing ID of UTub the user was removed from,
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub, which contains two members
        current_utub: Utubs = Utubs.query.first()

        # Grab the second user from the members
        second_user_in_utub_association: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == current_utub.id,
            Utub_Members.user_id != current_user.id,
        ).first()
        second_user_in_utub: Users = second_user_in_utub_association.to_user

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

        # Count all user-utub associations in utub
        initial_num_users_in_utub = Utub_Members.query.filter(
            Utub_Members.utub_id == current_utub.id
        ).count()

    # Remove second user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=second_user_in_utub.id,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_user_response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_REMOVED
    assert (
        int(remove_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.ID])
        == second_user_in_utub.id
    )
    assert (
        remove_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.USERNAME]
        == second_user_in_utub.username
    )
    assert int(remove_user_response_json[MEMBER_SUCCESS.UTUB_ID]) == current_utub.id

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utubs.query.first()
        assert len(current_utub.members) == initial_num_users_in_utub - 1

        # Ensure second user not in this UTub
        assert Utub_Members.query.get((current_utub.id, second_user_in_utub.id)) is None

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs - 1


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
        USER_SUCCESS.MEMBER : {
            MODELS.ID : Integer representing ID of user removed,
            MODELS.USERNAME: Username of user deleted,
        }
        USER_SUCCESS.UTUB_ID : Interger representing ID of UTub the user was removed from,
    }
    """

    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub: Utubs = Utubs.query.first()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()
        initial_num_users_in_utub = Utub_Members.query.filter(
            Utub_Members.utub_id == current_utub.id
        ).count()

        current_user_id = current_user.id
        current_user_username = current_user.username

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=current_user_id,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_user_response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_REMOVED
    assert (
        int(remove_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.ID])
        == current_user_id
    )
    assert (
        remove_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.USERNAME]
        == current_user_username
    )
    assert int(remove_user_response_json[MEMBER_SUCCESS.UTUB_ID]) == current_utub.id

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utubs.query.first()
        assert len(current_utub.members) == initial_num_users_in_utub - 1

        # Ensure logged in user not in this UTub
        assert (
            Utub_Members.query.get(
                (
                    current_utub.id,
                    current_user_id,
                )
            )
            is None
        )

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs - 1


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
        USER_SUCCESS.MEMBER : {
            MODELS.ID : Integer representing ID of user removed,
            MODELS.USERNAME: Username of user deleted,
        }
        USER_SUCCESS.UTUB_ID : Interger representing ID of UTub the user was removed from,
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get this creator's UTub
        current_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab another user from the members
        second_user_in_utub_association: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == current_utub.id,
            Utub_Members.user_id != current_user.id,
        ).first()
        second_user_in_utub: Users = second_user_in_utub_association.to_user

        # Get initial counts of URLs, Tags, and relative associations in the database
        current_num_of_urls_in_utub = len(current_utub.utub_urls)
        current_num_of_url_tags_in_utub = len(current_utub.utub_url_tags)

        all_urls_utub_associations = Utub_Urls.query.count()
        all_urls_tag_associations = Utub_Url_Tags.query.count()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Remove second user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=second_user_in_utub.id,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_user_response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_REMOVED
    assert (
        int(remove_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.ID])
        == second_user_in_utub.id
    )
    assert (
        remove_user_response_json[MEMBER_SUCCESS.MEMBER][MODELS.USERNAME]
        == second_user_in_utub.username
    )
    assert int(remove_user_response_json[MEMBER_SUCCESS.UTUB_ID]) == current_utub.id

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()

        # Ensure second user not in this UTub
        assert Utub_Members.query.get((current_utub.id, second_user_in_utub.id)) is None

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs - 1

        # Ensure URL-UTub associations aren't removed
        assert (
            Utub_Urls.query.filter(Utub_Urls.utub_id == current_utub.id).count()
            == current_num_of_urls_in_utub
        )

        # Ensure URL-Tag associations aren't removed
        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_id == current_utub.id).count()
            == current_num_of_url_tags_in_utub
        )

        # Ensure all associations still correct
        assert Utub_Url_Tags.query.count() == all_urls_tag_associations
        assert Utub_Urls.query.count() == all_urls_utub_associations


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
        STD_JSON.MESSAGE : MEMBER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF,
        STD_JSON.ERROR_CODE: 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub: Utubs = Utubs.query.first()

        current_number_of_users_in_utub = len(current_utub.members)

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=current_user.id,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    assert remove_user_response.status_code == 400

    # Ensore JSON response is correct
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_user_response_json[STD_JSON.MESSAGE]
        == MEMBER_FAILURE.CREATOR_CANNOT_REMOVE_THEMSELF
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 1

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utubs.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user still creator of this UTub
        assert current_user.id == current_utub.utub_creator

        # Ensure logged in user still in this UTub
        assert Utub_Members.query.get((current_utub.id, current_user.id)) is not None

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs


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
        current_utub: Utubs = Utubs.query.first()

        # Ensure multiple users in this Utubs
        current_number_of_users_in_utub = len(current_utub.members)

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=current_user.id,
        ),
    )

    # Assert invalid response code
    assert remove_user_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in remove_user_response.data

    # Ensure database is correct
    with app.app_context():
        current_utub = Utubs.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user still in this UTub
        assert Utub_Members.query.get((current_utub.id, current_user.id))

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs


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
        current_utub: Utubs = Utubs.query.first()

        # Ensure multiple users in this Utubs
        current_number_of_users_in_utub = len(current_utub.members)

        # Grab the second user from the members
        second_user_in_utub_association: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == current_utub.id,
            Utub_Members.user_id != current_user.id,
        ).first()
        second_user_in_utub = second_user_in_utub_association.to_user

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Remove second user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=current_user.id,
        ),
    )

    # Assert invalid response code
    assert remove_user_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in remove_user_response.data

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utubs.query.first()
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user is still creator
        assert current_user.id == current_utub.utub_creator

        # Ensure second user still in this UTub
        assert (
            Utub_Members.query.get((current_utub.id, second_user_in_utub.id))
            is not None
        )

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs


def test_remove_valid_user_from_invalid_utub_as_member_or_creator(
    add_single_user_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a valid existing user and a nonexistent UTub
    WHEN the user requests to remove themselves from the UTub via a DELETE to "/utubs/<int:utub_id>/members/<int:user_id>"
    THEN ensure that a 404 status code response is given when the UTub cannot be found in the database
    """
    NONEXISTENT_UTUB_ID = 999

    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=NONEXISTENT_UTUB_ID,
            user_id=current_user.id,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 404 HTTP status code response
    assert remove_user_response.status_code == 404

    # Ensure 404 response is given no matter what USER ID
    for num in range(10):
        remove_user_response = client.delete(
            url_for(
                ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=NONEXISTENT_UTUB_ID, user_id=num
            ),
            data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
        )

        # Ensure 404 HTTP status code response
        assert remove_user_response.status_code == 404

    with app.app_context():
        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs


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
        STD_JSON.MESSAGE : MEMBER_FAILURE.USER_NOT_IN_UTUB,
        STD_JSON.ERROR_CODE: 3
    }
    """
    NONEXISTENT_USER_ID = 999

    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        current_utub_member_count = len(current_utub.members)

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Remove self from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=NONEXISTENT_USER_ID,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 404 HTTP status code response
    assert remove_user_response.status_code == 404

    # Ensure proper JSON response
    remove_user_response_json = remove_user_response.json
    assert remove_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_user_response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_NOT_IN_UTUB
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs
        assert (
            current_utub_member_count
            == Utub_Members.query.filter(
                Utub_Members.utub_id == current_utub.id
            ).count()
        )


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
        STD_JSON.MESSAGE : MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        STD_JSON.ERROR_CODE: 2
    }
    """
    NONEXISTENT_USER_ID = 999
    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.member_role != Member_Role.CREATOR
        ).first()
        current_utub: Utubs = current_utub_member.to_utub
        current_utub_member_count = len(current_utub.members)

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Remove invalid user from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=NONEXISTENT_USER_ID,
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
        == MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs
        assert (
            current_utub_member_count
            == Utub_Members.query.filter(
                Utub_Members.utub_id == current_utub.id
            ).count()
        )


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
        STD_JSON.MESSAGE : MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        STD_JSON.ERROR_CODE: 2
    }
    """

    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        # Get the only UTub, which contains three members
        current_utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.member_role == Member_Role.MEMBER
        ).first()
        current_utub: Utubs = current_utub_member.to_utub

        # Ensure multiple users in this Utubs
        current_number_of_users_in_utub = len(current_utub.members)

        # Grab other user in this UTub
        other_utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.member_role == Member_Role.MEMBER,
            Utub_Members.user_id != current_user.id,
        ).first()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Attempt to remove other user from UTub as a member
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=other_utub_member.user_id,
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
        == MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 2

    # Ensure database is correctly updated
    with app.app_context():
        # Grab the UTub again
        current_utub = Utubs.query.get(current_utub.id)
        assert len(current_utub.members) == current_number_of_users_in_utub

        # Ensure logged in user in this UTub
        assert Utub_Members.query.get((current_utub.id, current_user.id)) is not None

        # Ensure the bystander member is still in the UTub
        assert (
            Utub_Members.query.get((current_utub.id, other_utub_member.user_id))
            is not None
        )

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs


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
        STD_JSON.MESSAGE : MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        STD_JSON.ERROR_CODE: 2
    }
    """

    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        second_user_utub_id = 2
        second_user_utub = Utubs.query.get(second_user_utub_id)

        # Get the third user
        third_user_id = 3
        third_user = Users.query.get(third_user_id)

        # Add third user to second user's UTub
        utub_user_association = Utub_Members()
        utub_user_association.to_user = third_user
        utub_user_association.utub_id = second_user_utub_id
        second_user_utub.members.append(utub_user_association)
        db.session.commit()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Try to remove the third user from second user's UTub as the first user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=second_user_utub_id,
            user_id=third_user_id,
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
        == MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 2

    # Ensure database still shows user 3 is member of utub 2
    with app.app_context():
        second_user_utub: Utubs = Utubs.query.get(second_user_utub_id)
        third_user: Users = Users.query.get(third_user_id)

        assert Utub_Members.query.get((second_user_utub.id, third_user.id)) is not None

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs


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
        STD_JSON.MESSAGE : MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE,
        STD_JSON.ERROR_CODE: 2
    }
    """
    client, csrf_token_string, _, app = login_second_user_without_register

    with app.app_context():
        # Get the third user
        third_user_id = 3
        third_user: Users = Users.query.get(third_user_id)

        # Have third user make another UTub
        new_utub_from_third_user: Utubs = Utubs(
            name="Third User's UTub", utub_creator=third_user_id, utub_description=""
        )
        creator = Utub_Members()
        creator.to_user = third_user
        creator.member_role = Member_Role.CREATOR
        new_utub_from_third_user.members.append(creator)

        first_user_id = 1
        first_user = Users.query.get(first_user_id)

        new_utub_user = Utub_Members()
        new_utub_user.to_user = first_user
        new_utub_from_third_user.members.append(new_utub_user)

        db.session.add(new_utub_from_third_user)
        db.session.commit()

        # Ensure current user is a member of a UTub
        current_utub_member_count = Utub_Members.query.filter(
            Utub_Members.utub_id == new_utub_from_third_user.id
        ).count()

        # Count all user-utub associations in db
        initial_num_user_utubs = Utub_Members.query.count()

    # Try to remove the first user from second user's UTub as the first user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=new_utub_from_third_user.id,
            user_id=first_user_id,
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
        == MEMBER_FAILURE.INVALID_PERMISSION_TO_REMOVE
    )
    assert int(remove_user_response_json[STD_JSON.ERROR_CODE]) == 2

    # Ensure database still shows user 1 is member of utub 2
    with app.app_context():
        third_user_utub: Utubs = Utubs.query.get(2)
        first_user: Users = Users.query.get(1)

        assert Utub_Members.query.get((third_user_utub.id, first_user.id)) is not None

        # Ensure counts of Utubs-User associations is correct
        assert Utub_Members.query.count() == initial_num_user_utubs
        assert (
            current_utub_member_count
            == Utub_Members.query.filter(
                Utub_Members.utub_id == new_utub_from_third_user.id
            ).count()
        )


def test_remove_valid_user_from_utub_updates_utub_last_updated(
    add_single_user_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a logged in user who is creator of a UTub that has another member in it, with no URLs or tags in the UTub
    WHEN the logged in user tries to remove second user by DELETE to "/utubs/<int:utub_id>/members/<int:user_id>" with valid
        information and a valid CSRF token
    THEN ensure the server responds with a 200 HTTP status code, and the UTub's last updated is updated
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub, which contains two members
        current_utub: Utubs = Utubs.query.first()
        initial_last_updated = current_utub.last_updated

        # Grab the second user from the members
        second_user_in_utub_association: Utub_Members = Utub_Members.query.filter(
            Utub_Members.utub_id == current_utub.id,
            Utub_Members.user_id != current_user.id,
        ).first()
        second_user_in_utub: Users = second_user_in_utub_association.to_user

    # Remove second user
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub.id,
            user_id=second_user_in_utub.id,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure HTTP response code is correct
    assert remove_user_response.status_code == 200

    # Ensure database is correctly updated
    with app.app_context():
        current_utub = Utubs.query.first()
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


def test_remove_invalid_user_from_utub_does_not_update_utub(
    add_single_user_to_utub_without_logging_in, login_first_user_without_register
):
    """
    GIVEN a creator of a UTub that is currently logged in
    WHEN the user requests to remove a nonexistent member from the UTub via a DELETE to "/utubs/<int:utub_id>/members/<int:user_id>"
    THEN ensure that a 404 status code response is given when the user cannot be found in the UTub, and the proper JSON response is given

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : MEMBER_FAILURE.USER_NOT_IN_UTUB,
        STD_JSON.ERROR_CODE: 3
    }
    """
    NONEXISTENT_USER_ID = 999

    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get the only UTub with two members
        current_utub: Utubs = Utubs.query.first()
        current_utub_id = current_utub.id
        initial_last_updated = current_utub.last_updated

    # Remove invalid user from UTub
    remove_user_response = client.delete(
        url_for(
            ROUTES.MEMBERS.REMOVE_MEMBER,
            utub_id=current_utub_id,
            user_id=NONEXISTENT_USER_ID,
        ),
        data={GENERAL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 404 HTTP status code response
    assert remove_user_response.status_code == 404

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(current_utub_id)
        assert current_utub.last_updated == initial_last_updated
