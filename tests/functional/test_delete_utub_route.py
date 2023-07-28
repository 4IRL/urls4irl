import pytest
from flask_login import current_user

from models_for_test import valid_empty_utub_1
from urls4irl.models import Utub, Utub_Users, Utub_Urls, Url_Tags
from urls4irl import db
from urls4irl.utils import strings as U4I_STRINGS

REMOVE_UTUB_FORM = U4I_STRINGS.UTUB_FORM
UTUB_SUCCESS = U4I_STRINGS.UTUB_SUCCESS
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
MODEL_STRS = U4I_STRINGS.MODELS
UTUB_FAILURE = U4I_STRINGS.UTUB_FAILURE


def test_delete_existing_utub_as_creator_no_tags_urls_members(
    add_single_utub_as_user_after_logging_in,
):
    """
    GIVEN a valid existing user and a UTub they have created
    WHEN the user requests to delete the UTub via a POST to "/utub/delete/<int: utub_id>"
    THEN ensure that a 200 status code response is given, and the proper JSON response
        indicating the successful deletion of the UTub is included.
        Additionally, this user and UTub are the only existing entities so ensure that
        no UTub exist in the database, and no associations exist between UTubs and Users after deletion

    On POST with a successful deletion, the JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: UTUB_SUCCESS.UTUB_DELETED,
        UTUB_SUCCESS.UTUB_ID: Integer representing the ID of the UTub deleted,
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the description of the deleted UTub,
        UTUB_SUCCESS.UTUB_NAME: String representing the name of the deleted UTub,
    }
    """
    client, utub_id, csrf_token, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        # Get initial count of UTubs
        initial_num_utubs = len(Utub.query.all())

    delete_utub_response = client.post(
        f"/utub/delete/{utub_id}", data={REMOVE_UTUB_FORM.CSRF_TOKEN: csrf_token}
    )

    assert delete_utub_response.status_code == 200

    delete_utub_json_response = delete_utub_response.json

    # Assert JSON includes proper response on successful deletion of UTub
    assert delete_utub_json_response[STD_JSON.MESSAGE] == UTUB_SUCCESS.UTUB_DELETED
    assert delete_utub_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_utub_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == valid_empty_utub_1[UTUB_SUCCESS.UTUB_DESCRIPTION]
    )
    assert int(delete_utub_json_response[UTUB_SUCCESS.UTUB_ID]) == utub_id
    assert (
        delete_utub_json_response[UTUB_SUCCESS.UTUB_NAME]
        == valid_empty_utub_1[REMOVE_UTUB_FORM.NAME]
    )

    with app.app_context():
        # Assert no UTubs and no UTub-User associations exist in the database after deletion
        assert len(Utub.query.all()) == initial_num_utubs - 1
        assert len(Utub_Users.query.all()) == 0


def test_delete_existing_utub_with_members_but_no_urls_no_tags(
    every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN a valid existing user and a UTub they have created that contains members but no URLs nor tags
    WHEN the user requests to delete the UTub via a POST to "/utub/delete/<int: utub_id>"
    THEN ensure that a 200 status code response is given, and the proper JSON response
        indicating the successful deletion of the UTub is included.
        Ensure all User-UTub associations, URL-UTub associations, and URL-Tag associations are deleted.

    On POST with a successful deletion, the JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: UTUB_SUCCESS.UTUB_DELETED,
        UTUB_SUCCESS.UTUB_ID: Integer representing the ID of the UTub deleted,
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the description of the deleted UTub,
        UTUB_SUCCESS.UTUB_NAME: String representing the name of the deleted UTub,
    }
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get the UTub this user is a creator of
        utub_user_is_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_to_delete = utub_user_is_creator_of.id
        utub_name_to_delete = utub_user_is_creator_of.name
        utub_description_to_delete = utub_user_is_creator_of.utub_description

        num_of_users_in_utub = len(utub_user_is_creator_of.members)
        initial_num_of_user_utubs_associations = len(Utub_Users.query.all())

        num_of_urls_in_utub = len(utub_user_is_creator_of.utub_urls)
        initial_num_of_url_utubs_associations = len(Utub_Urls.query.all())

        num_of_tags_in_utub = len(utub_user_is_creator_of.utub_url_tags)
        initial_num_of_url_tag_associations = len(Url_Tags.query.all())

        initial_num_utubs = len(Utub.query.all())

    delete_utub_response = client.post(
        f"/utub/delete/{utub_id_to_delete}",
        data={REMOVE_UTUB_FORM.CSRF_TOKEN: csrf_token},
    )

    assert delete_utub_response.status_code == 200

    delete_utub_json_response = delete_utub_response.json

    # Assert JSON includes proper response on successful deletion of UTub
    assert delete_utub_json_response[STD_JSON.MESSAGE] == UTUB_SUCCESS.UTUB_DELETED
    assert delete_utub_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_utub_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == utub_description_to_delete
    )
    assert int(delete_utub_json_response[UTUB_SUCCESS.UTUB_ID]) == utub_id_to_delete
    assert delete_utub_json_response[UTUB_SUCCESS.UTUB_NAME] == utub_name_to_delete

    with app.app_context():
        # Ensure proper counting in DB of deleted associations
        assert (
            len(Utub_Users.query.all())
            == initial_num_of_user_utubs_associations - num_of_users_in_utub
        )
        assert (
            len(Utub_Users.query.filter(Utub_Users.utub_id == utub_id_to_delete).all())
            == 0
        )

        assert (
            len(Utub_Urls.query.all())
            == initial_num_of_url_utubs_associations - num_of_urls_in_utub
        )
        assert (
            len(Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_delete).all())
            == 0
        )

        assert (
            len(Url_Tags.query.all())
            == initial_num_of_url_tag_associations - num_of_tags_in_utub
        )
        assert (
            len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_to_delete).all()) == 0
        )

        assert len(Utub.query.all()) == initial_num_utubs - 1


def test_delete_existing_utub_with_urls_no_tags(
    add_all_urls_and_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a valid existing user and a UTub they have created that contains members, URLs but no tags on URLs
    WHEN the user requests to delete the UTub via a POST to "/utub/delete/<int: utub_id>"
    THEN ensure that a 200 status code response is given, and the proper JSON response
        indicating the successful deletion of the UTub is included.
        Ensure all User-UTub associations, URL-UTub associations, and URL-Tag associations are deleted.

    On POST with a successful deletion, the JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: UTUB_SUCCESS.UTUB_DELETED,
        UTUB_SUCCESS.UTUB_ID: Integer representing the ID of the UTub deleted,
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the description of the deleted UTub,
        UTUB_SUCCESS.UTUB_NAME: String representing the name of the deleted UTub,
    }
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get the UTub this user is a creator of
        utub_user_is_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_to_delete = utub_user_is_creator_of.id
        utub_name_to_delete = utub_user_is_creator_of.name
        utub_description_to_delete = utub_user_is_creator_of.utub_description

        num_of_users_in_utub = len(utub_user_is_creator_of.members)
        initial_num_of_user_utubs_associations = len(Utub_Users.query.all())

        num_of_urls_in_utub = len(utub_user_is_creator_of.utub_urls)
        initial_num_of_url_utubs_associations = len(Utub_Urls.query.all())

        num_of_tags_in_utub = len(utub_user_is_creator_of.utub_url_tags)
        initial_num_of_url_tag_associations = len(Url_Tags.query.all())

        initial_num_utubs = len(Utub.query.all())

    delete_utub_response = client.post(
        f"/utub/delete/{utub_id_to_delete}",
        data={REMOVE_UTUB_FORM.CSRF_TOKEN: csrf_token},
    )

    assert delete_utub_response.status_code == 200

    delete_utub_json_response = delete_utub_response.json

    # Assert JSON includes proper response on successful deletion of UTub
    assert delete_utub_json_response[STD_JSON.MESSAGE] == UTUB_SUCCESS.UTUB_DELETED
    assert delete_utub_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_utub_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == utub_description_to_delete
    )
    assert int(delete_utub_json_response[UTUB_SUCCESS.UTUB_ID]) == utub_id_to_delete
    assert delete_utub_json_response[UTUB_SUCCESS.UTUB_NAME] == utub_name_to_delete

    with app.app_context():
        # Ensure proper counting in DB of deleted associations
        assert (
            len(Utub_Users.query.all())
            == initial_num_of_user_utubs_associations - num_of_users_in_utub
        )
        assert (
            len(Utub_Users.query.filter(Utub_Users.utub_id == utub_id_to_delete).all())
            == 0
        )

        assert (
            len(Utub_Urls.query.all())
            == initial_num_of_url_utubs_associations - num_of_urls_in_utub
        )
        assert (
            len(Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_delete).all())
            == 0
        )

        assert (
            len(Url_Tags.query.all())
            == initial_num_of_url_tag_associations - num_of_tags_in_utub
        )
        assert (
            len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_to_delete).all()) == 0
        )

        assert len(Utub.query.all()) == initial_num_utubs - 1


def test_delete_existing_utub_with_urls_and_tags(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid existing user and a UTub they have created that contains members, URLs, and tags on those URLs
    WHEN the user requests to delete the UTub via a POST to "/utub/delete/<int: utub_id>"
    THEN ensure that a 200 status code response is given, and the proper JSON response
        indicating the successful deletion of the UTub is included.
        Ensure all User-UTub associations, URL-UTub associations, and URL-Tag associations are deleted.

    On POST with a successful deletion, the JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: UTUB_SUCCESS.UTUB_DELETED,
        UTUB_SUCCESS.UTUB_ID: Integer representing the ID of the UTub deleted,
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the description of the deleted UTub,
        UTUB_SUCCESS.UTUB_NAME: String representing the name of the deleted UTub,
    }
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get the UTub this user is a creator of
        utub_user_is_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_to_delete = utub_user_is_creator_of.id
        utub_name_to_delete = utub_user_is_creator_of.name
        utub_description_to_delete = utub_user_is_creator_of.utub_description

        num_of_users_in_utub = len(utub_user_is_creator_of.members)
        initial_num_of_user_utubs_associations = len(Utub_Users.query.all())

        num_of_urls_in_utub = len(utub_user_is_creator_of.utub_urls)
        initial_num_of_url_utubs_associations = len(Utub_Urls.query.all())

        num_of_tags_in_utub = len(utub_user_is_creator_of.utub_url_tags)
        initial_num_of_url_tag_associations = len(Url_Tags.query.all())

        initial_num_utubs = len(Utub.query.all())

    delete_utub_response = client.post(
        f"/utub/delete/{utub_id_to_delete}",
        data={REMOVE_UTUB_FORM.CSRF_TOKEN: csrf_token},
    )

    assert delete_utub_response.status_code == 200

    delete_utub_json_response = delete_utub_response.json

    # Assert JSON includes proper response on successful deletion of UTub
    assert delete_utub_json_response[STD_JSON.MESSAGE] == UTUB_SUCCESS.UTUB_DELETED
    assert delete_utub_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_utub_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == utub_description_to_delete
    )
    assert int(delete_utub_json_response[UTUB_SUCCESS.UTUB_ID]) == utub_id_to_delete
    assert delete_utub_json_response[UTUB_SUCCESS.UTUB_NAME] == utub_name_to_delete

    with app.app_context():
        # Ensure proper counting in DB of deleted associations
        assert (
            len(Utub_Users.query.all())
            == initial_num_of_user_utubs_associations - num_of_users_in_utub
        )
        assert (
            len(Utub_Users.query.filter(Utub_Users.utub_id == utub_id_to_delete).all())
            == 0
        )

        assert (
            len(Utub_Urls.query.all())
            == initial_num_of_url_utubs_associations - num_of_urls_in_utub
        )
        assert (
            len(Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_delete).all())
            == 0
        )

        assert (
            len(Url_Tags.query.all())
            == initial_num_of_url_tag_associations - num_of_tags_in_utub
        )
        assert (
            len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_to_delete).all()) == 0
        )

        assert len(Utub.query.all()) == initial_num_utubs - 1


def test_delete_nonexistent_utub(login_first_user_with_register):
    """
    GIVEN a valid existing user and a nonexistent UTub
    WHEN the user requests to delete the UTub via a POST to "/utub/delete/1"
    THEN ensure that a 404 status code response is given when the UTub cannot be found in the database
    """
    client, csrf_token, _, app = login_first_user_with_register

    # Assert no UTubs exist before nonexistent UTub is attempted to be removed
    with app.app_context():
        assert len(Utub.query.all()) == 0

    delete_utub_response = client.post(
        f"/utub/delete/1", data={REMOVE_UTUB_FORM.CSRF_TOKEN: csrf_token}
    )

    # Ensure 404 sent back after invalid UTub id is requested
    assert delete_utub_response.status_code == 404

    # Assert no UTub exists after nonexistent UTub is attempted to be removed
    with app.app_context():
        assert len(Utub.query.all()) == 0


def test_delete_utub_with_invalid_route(login_first_user_with_register):
    """
    GIVEN a valid existing user
    WHEN the user requests to delete a UTub via a POST to "/utub/delete/InvalidRouteArgument"
    THEN ensure that a 404 status code response is given due to the invalid route used

    Correct url should be: "/utub/delete/<int: utub_id>" Where utub_id is an integer representing the ID of the UTub
        to delete
    """
    client, csrf_token, _, app = login_first_user_with_register

    # Assert no UTubs exist before nonexistent UTub is attempted to be removed
    with app.app_context():
        assert len(Utub.query.all()) == 0

    delete_utub_response = client.post(
        f"/utub/delete/InvalidRoute", data={REMOVE_UTUB_FORM.CSRF_TOKEN: csrf_token}
    )

    # Ensure 404 sent back after invalid UTub id is requested
    assert delete_utub_response.status_code == 404

    # Assert no UTub exists after nonexistent UTub is attempted to be removed
    with app.app_context():
        assert len(Utub.query.all()) == 0


def test_delete_utub_with_no_csrf_token(add_single_utub_as_user_after_logging_in):
    """
    GIVEN a valid existing user with a single UTub, utub ID == 1
    WHEN the user requests to delete a UTub via a POST to "/utub/delete/1" without a CSRF token included
    THEN ensure that a 400 status code response is given due to not including the CSRF
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    # Assert 1 UTub exists before nonexistent UTub is attempted to be removed
    with app.app_context():
        assert len(Utub.query.all()) == 1

    delete_utub_response = client.post(f"/utub/delete/{utub_id}")

    # Ensure 400 sent back after no csrf token included
    assert delete_utub_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in delete_utub_response.data

    # Assert 1 UTub exists after nonexistent UTub is attempted to be removed
    with app.app_context():
        assert len(Utub.query.all()) == 1


def test_delete_utub_as_not_member_or_creator(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN three sets of users, with each user having created their own UTub
    WHEN one user tries to delete the other two users' UTubs via POST to "/utub/dete/<int: utub_id>"
    THEN ensure response status code is 403, and proper JSON response indicating error is given

    JSON response should be formatted as follows:
    {
        STD_JSON.STATUS : "Failure",
        STD_JSON.MESSAGE: "You don't have permission to delete this UTub!"
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get the UTubs from the database that this member is not a part of
        user_not_in_these_utubs = (
            Utub_Users.query.filter(Utub_Users.user_id != current_user.id)
            .with_entities(Utub_Users.utub_id)
            .all()
        )
        assert len(Utub.query.all()) == 3
        assert len(Utub_Users.query.all()) == 3

        # Make sure that only 2 utubs-user associations exist, one for each utub/user combo
        assert len(user_not_in_these_utubs) == 2

    for utub_not_in in user_not_in_these_utubs:
        delete_utub_response = client.post(
            f"/utub/delete/{utub_not_in.utub_id}",
            data={REMOVE_UTUB_FORM.CSRF_TOKEN: csrf_token},
        )

        assert delete_utub_response.status_code == 403

        delete_utub_response_json = delete_utub_response.json

        assert delete_utub_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert (
            delete_utub_response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
        )

        with app.app_context():
            user_not_in_these_utubs = (
                Utub_Users.query.filter(Utub_Users.user_id != current_user.id)
                .with_entities(Utub_Users.utub_id)
                .all()
            )

            # Make sure that only 2 utubs-user associations exist, one for each utub/user combo
            assert len(user_not_in_these_utubs) == 2

    with app.app_context():
        # Make sure all 3 test UTubs are still available in the database
        assert len(Utub.query.all()) == 3
        assert len(Utub_Users.query.all()) == 3


def test_delete_utub_as_member_only(
    every_user_makes_a_unique_utub, login_first_user_without_register
):
    """
    GIVEN three sets of users, with each user having created their own UTub
    WHEN one user who is a member of all three UTubs,
        tries to delete the other two users' UTubs via POST to "/utub/dete/<int: utub_id>"
    THEN ensure response status code is 403, and proper JSON response indicating error is given

    JSON response should be formatted as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "You don't have permission to delete this UTub!"
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get the UTubs from the database that this member is not a part of
        user_not_in_these_utubs = (
            Utub_Users.query.filter(Utub_Users.user_id != current_user.id)
            .with_entities(Utub_Users.utub_id)
            .all()
        )

        # Make sure that only 2 utubs-user associations exist, one for each utub/user combo
        assert len(user_not_in_these_utubs) == 2

        # Add the current logged in user to the UTub's it is not a part of
        for utub_not_part_of in user_not_in_these_utubs:
            utub_to_join = utub_not_part_of.utub_id
            new_utub_user_association = Utub_Users(utub_id=utub_to_join, user_id=_.id)
            new_utub_user_association.to_user = current_user
            new_utub_user_association.to_utub = Utub.query.get(utub_to_join)
            db.session.add(new_utub_user_association)
            db.session.commit()

        # Assert current user is in all UTubs
        all_utubs = Utub.query.all()
        for utub in all_utubs:
            assert (
                len(
                    Utub_Users.query.filter(
                        Utub_Users.user_id == current_user.id,
                        Utub_Users.utub_id == utub.id,
                    ).all()
                )
                == 1
            )

        initial_num_utubs = len(Utub.query.all())

    # The logged in user should now be a member of the utubs they weren't a part of before
    only_member_in_these_utubs = user_not_in_these_utubs

    for utub_not_in in only_member_in_these_utubs:
        delete_utub_response = client.post(
            f"/utub/delete/{utub_not_in.utub_id}",
            data={REMOVE_UTUB_FORM.CSRF_TOKEN: csrf_token},
        )

        assert delete_utub_response.status_code == 403

        delete_utub_response_json = delete_utub_response.json

        assert delete_utub_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert (
            delete_utub_response_json[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
        )

        with app.app_context():
            user_not_in_these_utubs = (
                Utub_Users.query.filter(Utub_Users.user_id != current_user.id)
                .with_entities(Utub_Users.utub_id)
                .all()
            )

    with app.app_context():
        # Make sure all 3 test UTubs are still available in the database
        assert len(Utub.query.all()) == initial_num_utubs
