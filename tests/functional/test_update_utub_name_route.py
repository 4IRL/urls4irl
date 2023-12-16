from flask import url_for
from flask_login import current_user

from src.models import Utub, Utub_Urls, Utub_Users, Url_Tags
from src.utils import strings as U4I_STRINGS

UTUB_FORM = U4I_STRINGS.UTUB_FORM
UTUB_SUCCESS = U4I_STRINGS.UTUB_SUCCESS
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
MODEL_STRS = U4I_STRINGS.MODELS
UTUB_FAILURE = U4I_STRINGS.UTUB_FAILURE


def test_update_valid_utub_name_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a new name, via a POST to
        "/utub/edit_name/<utub_id: int>" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the new UTub name is stored in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        UTUB_SUCCESS.UTUB_ID: Integer representing the UTub ID for the changed name
        UTUB_SUCCESS.UTUB_NAME: String representing the new name of the UTub
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the current UTub's new name
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_name = utub_of_user.name

        # Ensure the new name is not equal to the old name
        assert NEW_NAME != current_utub_name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.CSRF_TOKEN: csrf_token_string, UTUB_FORM.NAME: NEW_NAME}

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 200

    # Ensure JSON response is correct
    edit_utub_name_json_response = edit_utub_name_response.json

    assert edit_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert int(edit_utub_name_json_response[UTUB_SUCCESS.UTUB_ID]) == current_utub_id
    assert (
        edit_utub_name_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == current_utub_description
    )
    assert edit_utub_name_json_response[UTUB_SUCCESS.UTUB_NAME] == NEW_NAME

    # Ensure database is consistent with just updating the UTub name
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == NEW_NAME
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            if utub_desc == current_utub_description:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    != all_utub_names_and_descriptions[utub_desc]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )


def test_update_valid_utub_same_name_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to the same name, via a POST to
        "/utub/edit_name/<utub_id: int>" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub name is still identical in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        UTUB_SUCCESS.UTUB_ID: Integer representing the UTub ID for the changed name
        UTUB_SUCCESS.UTUB_NAME: String representing the name of the UTub whose name was changed
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the current UTub's new name
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        NEW_NAME = utub_of_user.name

        # Ensure the new name is  equal to the old name
        assert NEW_NAME == utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.CSRF_TOKEN: csrf_token_string, UTUB_FORM.NAME: NEW_NAME}

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 200

    # Ensure JSON response is correct
    edit_utub_name_json_response = edit_utub_name_response.json

    assert edit_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert int(edit_utub_name_json_response[UTUB_SUCCESS.UTUB_ID]) == current_utub_id
    assert (
        edit_utub_name_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION]
        == current_utub_description
    )
    assert edit_utub_name_json_response[UTUB_SUCCESS.UTUB_NAME] == NEW_NAME

    # Ensure database is consistent after user requested same name for UTub
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == NEW_NAME
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            if utub_desc == current_utub_description:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )


def test_update_utub_empty_name_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to an empty name, via a POST to
        "/utub/edit_name/<utub_id: int>" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub name is not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
        STD_JSON.ERROR_CODE: 2
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the missing name field:
            {
                UTUB_FORM.NAME: ['This field is required.']
            }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_NAME = ""
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_name = utub_of_user.name

        # Ensure the new name is  equal to the old name
        assert NEW_NAME != current_utub_name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.CSRF_TOKEN: csrf_token_string, UTUB_FORM.NAME: NEW_NAME}

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    edit_utub_name_json_response = edit_utub_name_response.json

    assert edit_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(edit_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        edit_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert (
        edit_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.NAME]
        == UTUB_FAILURE.FIELD_REQUIRED
    )

    # Ensure database is consistent after sending back invalid form response
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            if utub_desc == current_utub_description:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )


def test_update_utub_name_only_spaces_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a name with only spaces, via a POST to
        "/utub/edit_name/<utub_id: int>" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub name is not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
        STD_JSON.ERROR_CODE: 2
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the name containing only spaces:
            {
                UTUB_FORM.NAME: ['Name cannot contain only spaces or be empty.']
            }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_NAME = "    "
    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_name = utub_of_user.name

        # Ensure the new name is  equal to the old name
        assert NEW_NAME != current_utub_name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.CSRF_TOKEN: csrf_token_string, UTUB_FORM.NAME: NEW_NAME}

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    edit_utub_name_json_response = edit_utub_name_response.json

    assert edit_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(edit_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        edit_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert edit_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.NAME] == [
        "Name cannot contain only spaces or be empty."
    ]

    # Ensure database is consistent after sending back invalid form response
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            if utub_desc == current_utub_description:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )


def test_update_utub_name_as_member(
    add_multiple_users_to_utub_without_logging_in, login_second_user_without_register
):
    """
    GIVEN a valid member of a UTub that has other members, a creator
    WHEN the member attempts to modify the UTub name to a new name, via a POST to
        "/utub/edit_name/<utub_id: int>" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub name is not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "You do not have permission to edit this UTub's name"
        STD_JSON.ERROR_CODE: 1
    }
    """
    client, csrf_token_string, logged_in_user, app = login_second_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Ensure this user is not the creator
        assert utub_of_user.created_by != current_user

        # Ensure this user is in the UTub
        assert current_user in [user.to_user for user in utub_of_user.members]

        current_utub_name = utub_of_user.name

        # Ensure the new name is not equal to the old name
        assert NEW_NAME != current_utub_name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.CSRF_TOKEN: csrf_token_string, UTUB_FORM.NAME: NEW_NAME}

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 403

    # Ensure JSON response is correct
    edit_utub_name_json_response = edit_utub_name_response.json

    assert edit_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(edit_utub_name_json_response[STD_JSON.ERROR_CODE]) == 1
    assert edit_utub_name_json_response[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED

    # Ensure database is consistent with just updating the UTub name
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_desc]
                == all_utub_names_and_descriptions[utub_desc]
            )


def test_update_utub_name_as_creator_of_another_utub(
    every_user_in_every_utub, login_second_user_without_register
):
    """
    GIVEN a valid member of a UTub that has other members, a creator, URLs, and tags associated with all URLs
    WHEN the member attempts to modify the UTub name to a new name, via a POST to
        "/utub/edit_name/<utub_id: int>" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub name is not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "You do not have permission to edit this UTub's name"
        STD_JSON.ERROR_CODE: 1
    }
    """
    client, csrf_token_string, logged_in_user, app = login_second_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Ensure this user is not the creator
        assert utub_of_user.created_by != current_user

        # Ensure this user is in the UTub
        assert current_user in [user.to_user for user in utub_of_user.members]

        # Ensure this user is a creator of another UTub
        assert (
            Utub.query.filter(Utub.utub_creator == current_user.id).first() is not None
        )

        current_utub_name = utub_of_user.name

        # Ensure the new name is not equal to the old name
        assert NEW_NAME != current_utub_name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.CSRF_TOKEN: csrf_token_string, UTUB_FORM.NAME: NEW_NAME}

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 403

    # Ensure JSON response is correct
    edit_utub_name_json_response = edit_utub_name_response.json

    assert edit_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(edit_utub_name_json_response[STD_JSON.ERROR_CODE]) == 1
    assert edit_utub_name_json_response[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED

    # Ensure database is consistent with just updating the UTub name
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_desc]
                == all_utub_names_and_descriptions[utub_desc]
            )


def test_update_name_of_invalid_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name of an invalid UTub via a POST to
        "/utub/edit_name/<utub_id: int>" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub names have not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 404 HTTP status code
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register
    utub_id_to_test = 0

    with app.app_context():
        all_utubs = Utub.query.all()
        all_utub_ids = [int(utub.id) for utub in all_utubs]

        while utub_id_to_test in all_utub_ids:
            utub_id_to_test += 1

        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.NAME: utub_of_user.name + "Hello",
    }

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=utub_id_to_test), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 404

    # Ensure database is consistent after user requested same name for UTub
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            if utub_desc == current_utub_description:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )


def test_update_name_of_utub_too_long_name(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs, and that
        the max length of a UTub name is 30 characters
    WHEN the creator attempts to modify the UTub name of an invalid UTub via a POST to
        "/utub/edit_name/<utub_id: int>" with invalid form data that does not contain the UTUB_FORM.NAME field, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_FORM.NAME: New UTub name to add (longer than 30 characters)
    THEN verify that the UTub names have not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 404 HTTP status code, and the server sends back a proper JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
        STD_JSON.ERROR_CODE: 2
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the name being too long:
            {
                UTUB_FORM.NAME: ['Field must be between 1 and 30 characters long.']
            }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    MAX_UTUB_NAME = 30

    NEW_NAME = "".join(["a" for _ in range(MAX_UTUB_NAME + 1)])

    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_name = utub_of_user.name

        # Ensure new name is not equal to old name
        assert NEW_NAME != current_utub_name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.CSRF_TOKEN: csrf_token_string, UTUB_FORM.NAME: NEW_NAME}

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    edit_utub_name_json_response = edit_utub_name_response.json

    assert edit_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(edit_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        edit_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert (
        edit_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.NAME]
        == UTUB_FAILURE.UTUB_NAME_FIELD_INVALID
    )

    # Ensure database is consistent after user requested same name for UTub
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            if utub_desc == current_utub_description:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )


def test_update_name_of_utub_missing_name_field_form(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name of an invalid UTub via a POST to
        "/utub/edit_name/<utub_id: int>" with invalid form data that does not contain the UTUB_FORM.NAME field, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
    THEN verify that the UTub names have not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 404 HTTP status code, and the server sends back a proper JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
        STD_JSON.ERROR_CODE: 2
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the name containing only spaces:
            {
                UTUB_FORM.NAME: ['This field is required.']
            }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
    }

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    edit_utub_name_json_response = edit_utub_name_response.json

    assert edit_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(edit_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        edit_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert (
        edit_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.NAME]
        == UTUB_FAILURE.FIELD_REQUIRED
    )

    # Ensure database is consistent after user requested same name for UTub
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            if utub_desc == current_utub_description:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_desc]
                    == all_utub_names_and_descriptions[utub_desc]
                )


def test_update_name_of_utub_missing_csrf_token(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a new name, via a POST to
        "/utub/edit_name/<utub_id: int>" with invalid form data (missing csrf_token field), following this format:
            "utub_name": New UTub name to add
    THEN verify that the new UTub name is stored in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate HTML element
        indicating the CSRF token is missing
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user = Utub.query.filter(Utub.utub_creator == current_user.id).first()

        # Ensure this user is the creator
        assert utub_of_user.created_by == current_user

        current_utub_name = utub_of_user.name

        # Ensure the new name is not equal to the old name
        assert NEW_NAME != current_utub_name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = len(Utub.query.all())
        current_num_of_utub_users = len(Utub_Users.query.all())
        current_num_of_utub_urls = len(Utub_Urls.query.all())
        current_num_of_url_tags = len(Url_Tags.query.all())

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utub.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.NAME: NEW_NAME}

    edit_utub_name_response = client.post(
        url_for("utubs.update_utub_name", utub_id=current_utub_id), data=utub_name_form
    )

    # Ensure valid reponse
    assert edit_utub_name_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in edit_utub_name_response.data

    # Ensure database is consistent with just updating the UTub name
    with app.app_context():
        assert len(Utub.query.all()) == current_num_of_utubs
        assert len(Utub_Users.query.all()) == current_num_of_utub_users
        assert len(Utub_Urls.query.all()) == current_num_of_utub_urls
        assert len(Url_Tags.query.all()) == current_num_of_url_tags

        final_check_utub_of_user = Utub.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs = Utub.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_desc]
                == all_utub_names_and_descriptions[utub_desc]
            )
