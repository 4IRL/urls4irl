from flask import Flask, url_for
from flask_login import current_user
import pytest
from redis import Redis

from backend import db, limiter
from backend.members.constants import (
    MEMBER_ADD_DAILY_CAP,
    MEMBER_ADD_RATE_LIMIT,
    MemberAddSource,
    UTubMembersErrorCodes,
)
from backend.metrics.events import EventName
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.users import Users
from backend.models.utubs import Utubs
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import ADD_USER_FORM
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import (
    FAILURE_GENERAL,
    FIELD_REQUIRED_STR,
    STD_JSON_RESPONSE as STD_JSON,
)
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.user_strs import MEMBER_FAILURE, MEMBER_SUCCESS
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.schemas.users import UserSchema
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.utils_for_test import is_string_in_logs

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
        with app.app_context():
            new_user: Users = Users.query.filter(Users.username == other_user).first()

        added_user_response = client.post(
            url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
            json={ADD_USER_FORM.USERNAME: other_user},
            headers={"X-CSRFToken": csrf_token},
        )

        # Assert correct status code
        assert added_user_response.status_code == 200
        added_user_response_json = added_user_response.json

        # Assert JSON response is valid and contains updated data
        assert added_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
        assert added_user_response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ADDED
        UserSchema.model_validate(added_user_response_json[MEMBER_SUCCESS.MEMBER])
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


def test_add_member_to_locked_utub_is_rejected(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub containing only themselves, where the UTub is LOCKED
    WHEN the creator tries to add another valid user to their locked UTub
        - By POST to "/utubs/<int:utub_id>/members" with a valid username
    THEN the write-guard rejects the add: the server responds 403 with the locked-UTub
        JSON error (error code UTubMembersErrorCodes.UTUB_IS_LOCKED, message
        UTUB_FAILURE.UTUB_IS_LOCKED) and no new Utub_Members association is created.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        other_user: Users = Users.query.filter(
            Users.username != current_user.username
        ).first()
        username_to_add = other_user.username

        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role == Member_Role.CREATOR,
        ).first()
        utub_of_current_user: Utubs = utub_member.to_utub
        utub_id_of_current_user = utub_of_current_user.id

        # Lock the UTub
        utub_of_current_user.is_locked = True
        db.session.commit()

        # Assert-before-state: only the creator is in the UTub prior to the blocked action
        initial_users_in_utub = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id_of_current_user
        ).count()
        assert initial_users_in_utub == 1
        initial_num_user_utubs = Utub_Members.query.count()

    added_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
        json={ADD_USER_FORM.USERNAME: username_to_add},
        headers={"X-CSRFToken": csrf_token},
    )

    assert added_user_response.status_code == 403
    added_user_response_json = added_user_response.json
    assert added_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert added_user_response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
    assert (
        int(added_user_response_json[STD_JSON.ERROR_CODE])
        == UTubMembersErrorCodes.UTUB_IS_LOCKED
    )

    with app.app_context():
        # No new member association created in the locked UTub
        assert (
            Utub_Members.query.filter(
                Utub_Members.utub_id == utub_id_of_current_user
            ).count()
            == initial_users_in_utub
        )
        assert Utub_Members.query.count() == initial_num_user_utubs


def test_add_member_to_utub_records_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub (no other members) and metrics enabled
    WHEN the creator POSTs to "/utubs/<utub_id>/members" with a valid
        non-member's username
    THEN the request returns HTTP 200 AND exactly one MEMBER_ADDED
        counter key is written to the metrics Redis DB.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Pick a user not yet in the creator's UTub
        non_member: Users = Users.query.filter(Users.id != current_user.id).first()
        non_member_username = non_member.username

    # Before-state: no MEMBER_ADDED counter exists yet
    assert count_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED) == 0

    # A raw-username add (no `source` in the body) falls back to the
    # exact_username default.
    add_member_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_user_is_creator_of),
        json={ADD_USER_FORM.USERNAME: non_member_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_member_response.status_code == 200
    member_added_keys = find_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED)
    assert len(member_added_keys) == 1
    assert parse_dims(member_added_keys[0])["source"] == MemberAddSource.EXACT_USERNAME


def test_add_member_to_utub_records_metric_search_result_source(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    login_first_user_without_register,
):
    """
    GIVEN a creator of a UTub (no other members) and metrics enabled
    WHEN the creator POSTs to add a non-member with source='search_result'
    THEN the request returns HTTP 200 AND the MEMBER_ADDED counter key carries
        the search_result source dimension.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        non_member: Users = Users.query.filter(Users.id != current_user.id).first()
        non_member_username = non_member.username

    assert count_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED) == 0

    add_member_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_user_is_creator_of),
        json={
            ADD_USER_FORM.USERNAME: non_member_username,
            "source": MemberAddSource.SEARCH_RESULT.value,
        },
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_member_response.status_code == 200
    member_added_keys = find_counter_keys(provide_metrics_redis, EventName.MEMBER_ADDED)
    assert len(member_added_keys) == 1
    assert parse_dims(member_added_keys[0])["source"] == MemberAddSource.SEARCH_RESULT


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
        headers={"X-CSRFToken": csrf_token},
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
    added_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_user_created.id),
        json={ADD_USER_FORM.USERNAME: other_user_username},
        headers={"X-CSRFToken": csrf_token},
    )

    # Assert correct status code
    assert added_user_response.status_code == 200
    added_user_response_json = added_user_response.json

    # Assert JSON response is valid and contains updated data
    assert added_user_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert added_user_response_json[STD_JSON.MESSAGE] == MEMBER_SUCCESS.MEMBER_ADDED
    UserSchema.model_validate(added_user_response_json[MEMBER_SUCCESS.MEMBER])
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

    missing_user_id = missing_user.id
    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=only_utub.id),
        json={ADD_USER_FORM.USERNAME: missing_user.username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_user_response.status_code == 403

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_user_response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.NOT_AUTHORIZED

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
    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=current_user_utub_id),
        json={ADD_USER_FORM.USERNAME: another_user_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_user_response.status_code == 400

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_user_response_json[STD_JSON.MESSAGE]
        == MEMBER_FAILURE.MEMBER_ALREADY_IN_UTUB
    )

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
    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=1),
        json={ADD_USER_FORM.USERNAME: another_user.username},
        headers={
            "X-CSRFToken": csrf_token,
            URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST,
        },
    )

    assert add_user_response.status_code == 404
    json_response = add_user_response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND

    # Make sure no UTub User associations exist
    with app.app_context():
        # Ensure correct count of Utub-User associations
        assert (
            Utub_Members.query.count() == initial_num_user_utubs
            and initial_num_user_utubs == 0
        )


def test_add_nonexistent_user_to_utub(
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
    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=only_utub.id),
        json={ADD_USER_FORM.USERNAME: "Not a registered user"},
        headers={"X-CSRFToken": csrf_token},
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
    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=another_utub.id),
        json={ADD_USER_FORM.USERNAME: test_user_to_add.username},
        headers={
            "X-CSRFToken": csrf_token,
            URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST,
        },
    )

    assert add_user_response.status_code == 404
    json_response = add_user_response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND

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

    # Try to add a member without providing a username
    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=current_user_utub.id),
        json={},
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_user_response.status_code == 400

    add_user_response_json = add_user_response.json

    assert add_user_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_user_response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.UNABLE_TO_ADD_MEMBER
    )
    assert add_user_response_json[STD_JSON.ERRORS][ADD_USER_FORM.USERNAME] == [
        FIELD_REQUIRED_STR
    ]

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
        added_user_response = client.post(
            url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
            json={ADD_USER_FORM.USERNAME: other_user},
            headers={"X-CSRFToken": csrf_token},
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
    add_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=current_user_utub_id),
        json={ADD_USER_FORM.USERNAME: another_user_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_user_response.status_code == 400

    with app.app_context():
        current_user_utub: Utubs = Utubs.query.get(current_user_utub_id)
        assert current_user_utub.last_updated == initial_last_updated


def test_add_valid_users_to_utub_success_log(
    every_user_makes_a_unique_utub, login_first_user_without_register, caplog
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains only themselves, no URLs or tags
    WHEN the user wants to add another valid user to their UTub by POST to "/utubs/<int:utub_id>/members"
    THEN ensure that the backend responds with a 200 HTTP status code and the logs are valid
    """
    client, csrf_token, _, app = login_first_user_without_register

    # Get the other users' usernames and this user's UTub, assuming 3 valid users
    with app.app_context():
        other_user: Users = Users.query.filter(
            Users.username != current_user.username
        ).first()
        other_username = other_user.username
        other_user_id = other_user.id

        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role == Member_Role.CREATOR,
        ).first()
        utub_of_current_user: Utubs = utub_member.to_utub
        utub_id_of_current_user = utub_of_current_user.id

    # Add the other users to the current user's UTubs
    added_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
        json={ADD_USER_FORM.USERNAME: other_username},
        headers={"X-CSRFToken": csrf_token},
    )

    # Assert correct status code
    assert added_user_response.status_code == 200
    assert is_string_in_logs(f"UTub.id={utub_id_of_current_user}", caplog.records)
    assert is_string_in_logs(f"Added User={other_user_id}", caplog.records)


def test_add_duplicate_user_to_utub_log(
    every_user_in_every_utub, login_first_user_without_register, caplog
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains only themselves, no URLs or tags
    WHEN the user wants to add an already added user to their UTub by POST to "/utubs/<int:utub_id>/members"
    THEN ensure that the backend responds with a 400 HTTP status code and the logs are valid
    """
    client, csrf_token, user, app = login_first_user_without_register

    # Get the other users' usernames and this user's UTub, assuming 3 valid users
    with app.app_context():
        other_user: Users = Users.query.filter(
            Users.username != current_user.username
        ).first()
        other_username = other_user.username
        other_user_id = other_user.id

        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role == Member_Role.CREATOR,
        ).first()
        utub_of_current_user: Utubs = utub_member.to_utub
        utub_id_of_current_user = utub_of_current_user.id

    # Add the other users to the current user's UTubs
    added_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
        json={ADD_USER_FORM.USERNAME: other_username},
        headers={"X-CSRFToken": csrf_token},
    )

    # Assert correct status code
    assert added_user_response.status_code == 400
    assert is_string_in_logs(
        f"User={user.id} tried adding a User={other_user_id} already in this UTub",
        caplog.records,
    )


def test_add_user_to_utub_invalid_log(
    every_user_in_every_utub, login_first_user_without_register, caplog
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains only themselves, no URLs or tags
    WHEN the user wants to add a user to their UTub by POST to "/utubs/<int:utub_id>/members" with an invalid form
    THEN ensure that the backend responds with a 400 HTTP status code and @api_route logs the validation failure
    """
    client, csrf_token, user, app = login_first_user_without_register

    # Get the other users' usernames and this user's UTub, assuming 3 valid users
    with app.app_context():
        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role == Member_Role.CREATOR,
        ).first()
        utub_of_current_user: Utubs = utub_member.to_utub
        utub_id_of_current_user = utub_of_current_user.id

    added_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
        json={},
        headers={"X-CSRFToken": csrf_token},
    )

    assert added_user_response.status_code == 400
    assert is_string_in_logs(f"User={user.id}", caplog.records)
    assert is_string_in_logs("Invalid JSON:", caplog.records)


def test_add_user_as_member_invalid_log(
    every_user_in_every_utub, login_first_user_without_register, caplog
):
    """
    GIVEN a logged-in user who is creator of a UTub that contains only themselves, no URLs or tags
    WHEN the user wants to add a user to their UTub by POST to "/utubs/<int:utub_id>/members" with an invalid form
    THEN ensure that the backend responds with a 200 HTTP status code and the logs are valid
    """
    client, csrf_token, user, app = login_first_user_without_register

    # Get the other users' usernames and this user's UTub, assuming 3 valid users
    with app.app_context():
        other_user: Users = Users.query.filter(
            Users.username != current_user.username
        ).first()
        other_username = other_user.username

        utub_member: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role != Member_Role.CREATOR,
        ).first()
        utub_of_current_user: Utubs = utub_member.to_utub
        utub_id_of_current_user = utub_of_current_user.id

    added_user_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_of_current_user),
        json={ADD_USER_FORM.USERNAME: other_username},
        headers={"X-CSRFToken": csrf_token},
    )

    # Assert correct status code
    assert added_user_response.status_code == 403
    assert is_string_in_logs(
        f"User={user.id} not creator: UTub.id={utub_id_of_current_user}",
        caplog.records,
    )


# ===========================================================================
# Per-IP Flask-Limiter 429 on the add-member route
# ===========================================================================


def _enable_limiter(app: Flask) -> None:
    """Re-arm flask-limiter for this test (globally disabled in tests).

    Mirrors the established pattern in
    tests/integration/splash/test_splash_auth_rate_limit.py.
    """
    original_first_request = app._got_first_request
    app._got_first_request = False
    app.config["RATELIMIT_ENABLED"] = True
    limiter.enabled = True
    limiter.init_app(app)
    app._got_first_request = original_first_request


def _disable_limiter() -> None:
    if limiter._storage is not None:
        limiter._storage.reset()
    limiter._storage = None
    limiter._limiter = None
    limiter.enabled = False
    limiter.initialized = False


def test_add_member_rate_limit_returns_html_429(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN the per-IP MEMBER_ADD_RATE_LIMIT (30/minute) on POST /utubs/<id>/members
    WHEN a 31st add-member request arrives within the window
    THEN a 429 is returned as the HTML 429 page (web AJAX; only /api/v1 gets JSON).

    The same non-member username is re-POSTed: the first add succeeds (200) and
    every subsequent one is a MEMBER_ALREADY_IN_UTUB 400, but flask-limiter
    counts all of them, so the 31st trips the per-IP cap.
    """
    client, csrf_token, _, app = login_first_user_without_register
    allowed_per_window = int(MEMBER_ADD_RATE_LIMIT.split("/")[0])

    with app.app_context():
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        non_member: Users = Users.query.filter(Users.id != current_user.id).first()
        non_member_username = non_member.username

    add_url = url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_user_is_creator_of)
    add_body = {ADD_USER_FORM.USERNAME: non_member_username}

    _enable_limiter(app)
    try:
        for _attempt_number in range(allowed_per_window):
            response = client.post(
                add_url, json=add_body, headers={"X-CSRFToken": csrf_token}
            )
            assert response.status_code != 429

        rate_limited_response = client.post(
            add_url, json=add_body, headers={"X-CSRFToken": csrf_token}
        )
        assert rate_limited_response.status_code == 429
        assert not rate_limited_response.is_json
        assert IDENTIFIERS.HTML_429 in rate_limited_response.get_data(as_text=True)
    finally:
        _disable_limiter()


# ===========================================================================
# Per-user fail-open Redis daily add-member cap
# ===========================================================================


def _enforcement_redis(app: Flask) -> Redis | None:
    redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == "memory://":
        return None
    return Redis.from_url(redis_uri)


def test_add_member_daily_cap_rejects_at_limit(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN the per-user daily add-member cap (MEMBER_ADD_DAILY_CAP) already
        reached for the acting user (counter seeded at the cap)
    WHEN the creator POSTs one more add-member request
    THEN it is rejected with HTTP 400 and the daily-cap error message, and no
        new member association is created.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        acting_user_id = current_user.id
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        non_member: Users = Users.query.filter(Users.id != current_user.id).first()
        non_member_username = non_member.username
        non_member_id = non_member.id

    redis_client = _enforcement_redis(app)
    if redis_client is None:
        pytest.skip("Enforcement Redis unavailable (memory:// stub) — cap not enforced")

    rate_limit_key = f"member-add-lookup:{acting_user_id}"
    redis_client.set(rate_limit_key, MEMBER_ADD_DAILY_CAP)

    add_member_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_user_is_creator_of),
        json={ADD_USER_FORM.USERNAME: non_member_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_member_response.status_code == 400
    response_json = add_member_response.json
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response_json[STD_JSON.MESSAGE] == MEMBER_FAILURE.MEMBER_ADD_RATE_LIMITED

    with app.app_context():
        # The rejected attempt created no membership row.
        assert (
            Utub_Members.query.filter(
                Utub_Members.utub_id == utub_id_user_is_creator_of,
                Utub_Members.user_id == non_member_id,
            ).count()
            == 0
        )
    redis_client.close()


def test_add_member_daily_cap_fails_open_when_redis_unavailable(
    monkeypatch, every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN the daily-cap Redis client is unavailable (helper returns None)
    WHEN the creator POSTs a valid add-member request
    THEN the add still succeeds (HTTP 200) — the cap fails open.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        non_member: Users = Users.query.filter(Users.id != current_user.id).first()
        non_member_username = non_member.username

    monkeypatch.setattr(
        "backend.members.services.create_members._build_member_rate_limit_redis",
        lambda: None,
    )

    add_member_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_user_is_creator_of),
        json={ADD_USER_FORM.USERNAME: non_member_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_member_response.status_code == 200


class _RaisingRedis:
    """Stand-in enforcement Redis whose counter ops all raise — exercises the
    fail-open try/except in create_utub_member on a LIVE (not None) client."""

    def get(self, *_args, **_kwargs):
        raise RuntimeError("redis unavailable")

    def incr(self, *_args, **_kwargs):
        raise RuntimeError("redis unavailable")

    def expire(self, *_args, **_kwargs):
        raise RuntimeError("redis unavailable")


def test_add_member_daily_cap_fails_open_on_live_redis_error(
    monkeypatch, every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a live daily-cap Redis client whose get/incr/expire all raise
    WHEN the creator POSTs a valid add-member request
    THEN the add still succeeds (HTTP 200) — the counter fails open on any
        Redis error rather than blocking the add.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        non_member: Users = Users.query.filter(Users.id != current_user.id).first()
        non_member_username = non_member.username

    monkeypatch.setattr(
        "backend.members.services.create_members._build_member_rate_limit_redis",
        lambda: _RaisingRedis(),
    )

    add_member_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_user_is_creator_of),
        json={ADD_USER_FORM.USERNAME: non_member_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert add_member_response.status_code == 200


def test_add_member_failed_probe_burns_a_slot_with_ttl(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN a creator and an enforcement Redis
    WHEN the creator probes a NONEXISTENT username (which 400s as USER_NOT_EXIST)
    THEN the per-user daily counter is still incremented (to 1) with a ~24h TTL
        — proving every attempt reaching the lookup burns a slot within a
        bounded window, so enumeration probing is capped.
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        acting_user_id = current_user.id
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

    redis_client = _enforcement_redis(app)
    if redis_client is None:
        pytest.skip("Enforcement Redis unavailable (memory:// stub) — cap not enforced")

    rate_limit_key = f"member-add-lookup:{acting_user_id}"
    assert redis_client.get(rate_limit_key) is None

    # A nonexistent BUT valid-length (<=20 char) username so the request
    # clears form validation and reaches the username lookup (the slot-burn
    # point). A 30-char probe would 400 at schema validation before the counter.
    probe_response = client.post(
        url_for(ROUTES.MEMBERS.CREATE_MEMBER, utub_id=utub_id_user_is_creator_of),
        json={ADD_USER_FORM.USERNAME: "no_such_user_xyz"},
        headers={"X-CSRFToken": csrf_token},
    )

    # A nonexistent username resolves to a 400, but the attempt still counts.
    assert probe_response.status_code == 400
    assert int(redis_client.get(rate_limit_key)) == 1
    ttl = redis_client.ttl(rate_limit_key)
    assert 0 < ttl <= 86400
    redis_client.close()
