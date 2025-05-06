from flask import url_for
from flask_login import current_user
import pytest

from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.constants import UTUB_CONSTANTS
from src.utils.strings.form_strs import UTUB_FORM
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.utub_strs import UTUB_FAILURE, UTUB_SUCCESS
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.utubs


def test_update_valid_utub_name_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a new name, via a POST to
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
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
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 200

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert int(update_utub_name_json_response[UTUB_SUCCESS.UTUB_ID]) == current_utub_id
    assert update_utub_name_json_response[UTUB_SUCCESS.UTUB_NAME] == NEW_NAME

    # Ensure database is consistent with just updating the UTub name
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == NEW_NAME
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
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
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        NEW_NAME = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 200

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert int(update_utub_name_json_response[UTUB_SUCCESS.UTUB_ID]) == current_utub_id
    assert update_utub_name_json_response[UTUB_SUCCESS.UTUB_NAME] == NEW_NAME

    # Ensure database is consistent after user requested same name for UTub
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == NEW_NAME
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub name is not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
        STD_JSON.ERROR_CODE: 2
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the missing name field:
            {
                UTUB_FORM.UTUB_NAME: ['This field is required.']
            }
    }
    """
    client, csrf_token_string, logged_in_user, app = login_first_user_without_register

    NEW_NAME = ""
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        update_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert (
        update_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.UTUB_NAME]
        == UTUB_FAILURE.FIELD_REQUIRED
    )

    # Ensure database is consistent after sending back invalid form response
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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


def test_update_utub_name_fully_sanitized(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to invalid name that is sanitized by the backend, via a POST to
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub name is not changed in the database and server responds with appropriate error message

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
        STD_JSON.ERROR_CODE: 2
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the missing name field:
            {
                UTUB_FORM.UTUB_NAME: ['Invalid input, please try again.']
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token,
        UTUB_FORM.UTUB_NAME: '<img src="evl.jpg">',
    }

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        current_utub_id = utub_of_user.id

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        update_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert update_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.UTUB_NAME] == [
        UTUB_FAILURE.INVALID_INPUT
    ]


def test_update_utub_name_partially_sanitized(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to invalid name that is sanitized by the backend, via a POST to
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub name is not changed in the database and server responds with appropriate error message

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
        STD_JSON.ERROR_CODE: 2
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the missing name field:
            {
                UTUB_FORM.UTUB_NAME: ['Invalid input, please try again.']
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        current_utub_id = utub_of_user.id

    for utub_name in (
        "<<HELLO>>",
        "<h1>Hello</h1>",
    ):

        utub_name_form = {
            UTUB_FORM.CSRF_TOKEN: csrf_token,
            UTUB_FORM.UTUB_NAME: utub_name,
        }

        update_utub_name_response = client.patch(
            url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
            data=utub_name_form,
        )

        # Ensure valid reponse
        assert update_utub_name_response.status_code == 400

        # Ensure JSON response is correct
        update_utub_name_json_response = update_utub_name_response.json

        assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert int(update_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
        assert (
            update_utub_name_json_response[STD_JSON.MESSAGE]
            == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
        )
        assert update_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.UTUB_NAME] == [
            UTUB_FAILURE.INVALID_INPUT
        ]


def test_update_utub_name_only_spaces_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a name with only spaces, via a POST to
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
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
                UTUB_FORM.UTUB_NAME: ['Name cannot contain only spaces or be empty.']
            }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_NAME = "    "
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        update_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert update_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.UTUB_NAME] == [
        "Name cannot contain only spaces or be empty."
    ]

    # Ensure database is consistent after sending back invalid form response
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
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
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 403

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_name_json_response[STD_JSON.ERROR_CODE]) == 1
    assert (
        update_utub_name_json_response[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
    )

    # Ensure database is consistent with just updating the UTub name
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
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
    client, csrf_token_string, _, app = login_second_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 403

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_name_json_response[STD_JSON.ERROR_CODE]) == 1
    assert (
        update_utub_name_json_response[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
    )

    # Ensure database is consistent with just updating the UTub name
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub names have not changed in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 404 HTTP status code
    """
    client, csrf_token_string, _, app = login_first_user_without_register
    NONEXISTENT_UTUB_ID = 999

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: utub_of_user.name + "Hello",
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=NONEXISTENT_UTUB_ID),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 404

    # Ensure database is consistent after user requested same name for UTub
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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
        "/utubs/<utub_id: int>/name" with invalid form data that does not contain the UTUB_FORM.UTUB_NAME field, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_FORM.UTUB_NAME: New UTub name to add (longer than 30 characters)
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
                UTUB_FORM.UTUB_NAME: ['Field must be between 1 and 30 characters long.']
            }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    MAX_UTUB_NAME = UTUB_CONSTANTS.MAX_NAME_LENGTH

    NEW_NAME = "".join(["a" for _ in range(MAX_UTUB_NAME + 1)])

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        update_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert (
        update_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.UTUB_NAME]
        == UTUB_FAILURE.UTUB_NAME_FIELD_INVALID
    )

    # Ensure database is consistent after user requested same name for UTub
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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
        "/utubs/<utub_id: int>/name" with invalid form data that does not contain the UTUB_FORM.UTUB_NAME field, following this format:
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
                UTUB_FORM.UTUB_NAME: ['This field is required.']
            }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    update_utub_name_json_response = update_utub_name_response.json

    assert update_utub_name_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_name_json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        update_utub_name_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_NAME
    )
    assert (
        update_utub_name_json_response[STD_JSON.ERRORS][UTUB_FORM.UTUB_NAME]
        == UTUB_FAILURE.FIELD_REQUIRED
    )

    # Ensure database is consistent after user requested same name for UTub
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
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
        "/utubs/<utub_id: int>/name" with invalid form data (missing csrf_token field), following this format:
            "utub_name": New UTub name to add
    THEN verify that the new UTub name is stored in the database, the utub-user associations are
        consistent across the change, all other UTub names are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate HTML element
        indicating the CSRF token is missing
    """
    client, _, _, app = login_first_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_name = utub_of_user.name

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.utub_description] = utub.name

    utub_name_form = {UTUB_FORM.UTUB_NAME: NEW_NAME}

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 403
    assert update_utub_name_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in update_utub_name_response.data

    # Ensure database is consistent with just updating the UTub name
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description

        all_final_utubs: list[Utubs] = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.utub_description] = utub.name

        for utub_desc in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_desc]
                == all_utub_names_and_descriptions[utub_desc]
            )


def test_update_name_updates_utub_last_updated_field(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a new name, via a POST to
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub's last-updated time is updated to show later than originally
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_id = utub_of_user.id
        initial_last_updated = utub_of_user.last_updated

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 200

    with app.app_context():
        updated_utub: Utubs = Utubs.query.filter(Utubs.id == current_utub_id).first()
        assert (updated_utub.last_updated - initial_last_updated).total_seconds() > 0


def test_same_name_does_not_update_utub_last_updated_time(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to the same name, via a POST to
        "/utubs/<utub_id: int>/name" with valid form data, following this format:
            UTUB_FORM.CSRF_TOKEN: String containing CSRF token for validation
            "utub_name": New UTub name to add
    THEN verify that the UTub's last-updated time is not updated
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name
        initial_last_updated = utub_of_user.last_updated

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: current_utub_name,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 200

    with app.app_context():
        updated_utub: Utubs = Utubs.query.filter(Utubs.id == current_utub_id).first()
        assert updated_utub.last_updated == initial_last_updated


def test_update_valid_utub_name_success_logs(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a new name, via a POST to
        "/utubs/<utub_id: int>/name" with valid form data
    THEN verify that the the logs are valid
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_NAME = "This is my new UTub name"

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: NEW_NAME,
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 200

    # Ensure JSON response is correct
    assert is_string_in_logs(f"UTub.id={current_utub_id}", caplog.records)
    assert is_string_in_logs(f"OLD UTub.name={current_utub_name}", caplog.records)
    assert is_string_in_logs(f"NEW UTub.name={NEW_NAME}", caplog.records)


def test_update_utub_name_invalid_form_logs(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a new name, via a POST to
        "/utubs/<utub_id: int>/name" with invalid form data
    THEN verify that the the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_id = utub_of_user.id

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: "",
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 400

    # Ensure JSON response is correct
    assert is_string_in_logs(f"User={user.id}", caplog.records)
    assert is_string_in_logs(
        f"Invalid form: name={UTUB_FAILURE.FIELD_REQUIRED}", caplog.records
    )


def test_update_utub_name_invalid_permission_logs(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with all URLs
    WHEN the creator attempts to modify the UTub name to a new name, via a POST to
        "/utubs/<utub_id: int>/name" with valid form data but user is not creator
    THEN verify that the the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

    utub_name_form = {
        UTUB_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_FORM.UTUB_NAME: "New",
    }

    update_utub_name_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=current_utub_id),
        data=utub_name_form,
    )

    # Ensure valid reponse
    assert update_utub_name_response.status_code == 403

    # Ensure JSON response is correct
    assert is_string_in_logs(f"User={user.id} not creator: ", caplog.records)
    assert is_string_in_logs(f"UTub.id={current_utub_id} |", caplog.records)
    assert is_string_in_logs(f"UTub.name={current_utub_name}", caplog.records)
