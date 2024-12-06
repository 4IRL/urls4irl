from flask import url_for
from flask_login import current_user
import pytest

from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.constants import UTUB_CONSTANTS
from src.utils.strings.form_strs import UTUB_DESCRIPTION_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.utub_strs import UTUB_FAILURE, UTUB_SUCCESS

pytestmark = pytest.mark.utubs


def test_update_valid_utub_description_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with those URLs
    WHEN the creator attempts to modify the UTub description to a new description, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN verify that the new UTub description is stored in the database, the utub-user associations are
        consistent across the change, all other UTub descriptions are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        UTUB_SUCCESS.UTUB_ID: Integer representing the UTub ID for the changed description
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the current UTub's new description
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 200

    # Ensure JSON response is correct
    update_utub_desc_json_response = update_utub_desc_response.json

    assert update_utub_desc_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert int(update_utub_desc_json_response[UTUB_SUCCESS.UTUB_ID]) == current_utub_id
    assert update_utub_desc_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION] == UPDATE_TEXT

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == UPDATE_TEXT

        all_final_utubs: list[Utubs] = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            if utub_name == current_utub_name:
                assert (
                    final_utub_names_and_descriptions[utub_name]
                    != all_utub_names_and_descriptions[utub_name]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_name]
                    == all_utub_names_and_descriptions[utub_name]
                )


def test_update_valid_empty_utub_description_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with
    WHEN the creator attempts to modify the UTub description to an empty description, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN verify that the new UTub description is stored in the database, the utub-user associations are
        consistent across the change, all other UTub descriptions are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        UTUB_SUCCESS.UTUB_ID: Integer representing the UTub ID for the changed description
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the current UTub's new description
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    UPDATE_TEXT = ""
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 200

    # Ensure JSON response is correct
    update_utub_desc_json_response = update_utub_desc_response.json

    assert update_utub_desc_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert int(update_utub_desc_json_response[UTUB_SUCCESS.UTUB_ID]) == current_utub_id
    assert update_utub_desc_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION] == UPDATE_TEXT

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == UPDATE_TEXT

        all_final_utubs: list[Utubs] = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            if utub_name == current_utub_name:
                assert (
                    final_utub_names_and_descriptions[utub_name]
                    != all_utub_names_and_descriptions[utub_name]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_name]
                    == all_utub_names_and_descriptions[utub_name]
                )


def test_update_only_spaces_utub_description_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with
    WHEN the creator attempts to modify the UTub description to a description containing only spaces, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN verify that the new UTub description is stored in the database as an empty string, the utub-user
        associations are consistent across the change, all other UTub descriptions are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        UTUB_SUCCESS.UTUB_ID: Integer representing the UTub ID for the changed description
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the current UTub's new description
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    UPDATE_TEXT = "   "
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 200

    # Ensure JSON response is correct
    update_utub_desc_json_response = update_utub_desc_response.json

    assert update_utub_desc_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert int(update_utub_desc_json_response[UTUB_SUCCESS.UTUB_ID]) == current_utub_id
    assert update_utub_desc_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION] == ""

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == ""

        all_final_utubs: list[Utubs] = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            if utub_name == current_utub_name:
                assert (
                    final_utub_names_and_descriptions[utub_name]
                    != all_utub_names_and_descriptions[utub_name]
                )
            else:
                assert (
                    final_utub_names_and_descriptions[utub_name]
                    == all_utub_names_and_descriptions[utub_name]
                )


def test_update_utub_description_with_same_description_as_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with
    WHEN the creator attempts to modify the UTub description to the same description, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN verify that the new UTub description is stored in the database, the UTub-user associations are
        consistent across the change, all other UTub descriptions are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.SUCCESS,
        UTUB_SUCCESS.UTUB_ID: Integer representing the UTub ID for the changed description
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the current UTub's previous description
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_description = utub_of_user.utub_description
        UPDATE_TEXT = current_utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 200

    # Ensure JSON response is correct
    update_utub_desc_json_response = update_utub_desc_response.json

    assert update_utub_desc_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert int(update_utub_desc_json_response[UTUB_SUCCESS.UTUB_ID]) == current_utub_id
    assert update_utub_desc_json_response[UTUB_SUCCESS.UTUB_DESCRIPTION] == UPDATE_TEXT

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == UPDATE_TEXT

        all_final_utubs: list[Utubs] = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_name]
                == all_utub_names_and_descriptions[utub_name]
            )


def test_update_utub_description_as_member(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions
    WHEN the member attempts to modify the UTub description to a new description, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent,
        the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response
        indicating the member is not authorized to edit the description

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "You do not have permission to edit this UTub's description",
        STD_JSON.ERROR_CODE: 1,
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the current UTub's description
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this member's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_utub_description = utub_of_user.utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 403

    # Ensure JSON response is correct
    update_utub_desc_json_response = update_utub_desc_response.json

    assert update_utub_desc_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_desc_json_response[STD_JSON.ERROR_CODE]) == 1
    assert (
        update_utub_desc_json_response[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
    )

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description
        assert final_check_utub_of_user.utub_description != UPDATE_TEXT

        all_final_utubs: list[Utubs] = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_name]
                == all_utub_names_and_descriptions[utub_name]
            )


def test_update_utub_description_as_creator_of_other_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions, and this member is creator of another UTub
    WHEN the member attempts to modify the UTub description to a new description, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent,
        the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response
        indicating the member is not authorized to edit the description

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.NOT_AUTHORIZED,
        STD_JSON.ERROR_CODE: 1,
        UTUB_SUCCESS.UTUB_DESCRIPTION: String representing the current UTub's description
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_utub_description = utub_of_user.utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 403

    # Ensure JSON response is correct
    update_utub_desc_json_response = update_utub_desc_response.json

    assert update_utub_desc_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(update_utub_desc_json_response[STD_JSON.ERROR_CODE]) == 1
    assert (
        update_utub_desc_json_response[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
    )

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description
        assert final_check_utub_of_user.utub_description != UPDATE_TEXT

        all_final_utubs: list[Utubs] = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_name]
                == all_utub_names_and_descriptions[utub_name]
            )


def test_update_utub_description_of_invalid_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions, and this member is creator of another UTub
    WHEN the member attempts to modify the UTub description of a nonexistent UTub, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent,
        the server sends back a 404 HTTP status code
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NONEXISTENT_UTUB_ID = 999
    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this creator's UTub
    with app.app_context():
        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=NONEXISTENT_UTUB_ID),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 404

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        all_final_utubs = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_name]
                == all_utub_names_and_descriptions[utub_name]
            )


def test_update_utub_description_too_long(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions
    WHEN the creator attempts to modify the UTub description to a new description that is longer than
        500 characters, via a POST to:
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent,
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response
        indicating the UTub description is too long

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: UTUB_FAILURE.UTUB_DESC_TOO_LONG,
        STD_JSON.ERROR_CODE: 3,
        STD_JSON.ERRORS: Objects representing the incorrect field, and an array of errors associated with that field.
            For example, with the missing or empty utub_description field:
            {
                UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UTUB_FAILURE.UTUB_DESC_FIELD_TOO_LONG
            }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    MAX_UTUB_DESC = UTUB_CONSTANTS.MAX_DESCRIPTION_LENGTH

    UPDATE_TEXT = "".join(["a" for _ in range(MAX_UTUB_DESC + 1)])
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_description = utub_of_user.utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 400

    # Ensure JSON response is correct
    update_utub_desc_json_response = update_utub_desc_response.json

    assert update_utub_desc_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        update_utub_desc_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UTUB_DESC_TOO_LONG
    )
    assert int(update_utub_desc_json_response[STD_JSON.ERROR_CODE]) == 3
    assert (
        update_utub_desc_json_response[STD_JSON.ERRORS][
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM
        ]
        == UTUB_FAILURE.UTUB_DESC_FIELD_TOO_LONG
    )

    # Ensure database is consistent with just updating the UTub description
    with app.app_context():
        assert Utubs.query.count() == current_num_of_utubs
        assert Utub_Members.query.count() == current_num_of_utub_users
        assert Utub_Urls.query.count() == current_num_of_utub_urls
        assert Utub_Url_Tags.query.count() == current_num_of_url_tags

        final_check_utub_of_user: Utubs = Utubs.query.get(current_utub_id)
        assert final_check_utub_of_user.name == current_utub_name
        assert final_check_utub_of_user.utub_description == current_utub_description
        assert final_check_utub_of_user.utub_description != UPDATE_TEXT

        all_final_utubs: list[Utubs] = Utubs.query.all()
        final_utub_names_and_descriptions = dict()
        for utub in all_final_utubs:
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_name]
                == all_utub_names_and_descriptions[utub_name]
            )


def test_update_utub_description_missing_description_field(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions
    WHEN the creator attempts to modify the UTub description, via a POST to:
        "/utubs/<utub_id: int>/description" with invalid form data that doens't contain
            the UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM field, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent,
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response
        indicating the form is invalid

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "Invalid form",
        STD_JSON.ERROR_CODE: 2,
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_description = utub_of_user.utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 400

    # Ensure JSON response is correct
    update_utub_desc_json_response = update_utub_desc_response.json

    assert update_utub_desc_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        update_utub_desc_json_response[STD_JSON.MESSAGE]
        == UTUB_FAILURE.UNABLE_TO_MODIFY_UTUB_DESC
    )
    assert int(update_utub_desc_json_response[STD_JSON.ERROR_CODE]) == 2

    # Ensure database is consistent with just updating the UTub description
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
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_name]
                == all_utub_names_and_descriptions[utub_name]
            )


def test_update_utub_description_missing_csrf_token(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with, and given only
        creators are allowed to modify UTub descriptions
    WHEN the creator attempts to modify the UTub description, via a POST to:
        "/utubs/<utub_id: int>/description" with invalid form data that doens't contain
            the UTUB_DESCRIPTION_FORM.CSRF_TOKEN field, following this format:
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN the UTub-user associations are consistent across the change, all UTub descriptions are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate HTML element
        indicating the CSRF token is missing
    """
    client, _, _, app = login_first_user_without_register

    # Grab this creator's UTub
    UPDATE_TEXT = "This is my new UTub description. 123456"
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        current_utub_description = utub_of_user.utub_description

        current_utub_id = utub_of_user.id
        current_utub_name = utub_of_user.name

        current_num_of_utubs = Utubs.query.count()
        current_num_of_utub_users = Utub_Members.query.count()
        current_num_of_utub_urls = Utub_Urls.query.count()
        current_num_of_url_tags = Utub_Url_Tags.query.count()

        # Get all UTub names and descriptions in a dictionary for checking
        all_utub_names_and_descriptions = dict()
        all_initial_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_initial_utubs:
            all_utub_names_and_descriptions[utub.name] = utub.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in update_utub_desc_response.data

    # Ensure database is consistent with just updating the UTub description
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
            final_utub_names_and_descriptions[utub.name] = utub.utub_description

        for utub_name in final_utub_names_and_descriptions:
            assert (
                final_utub_names_and_descriptions[utub_name]
                == all_utub_names_and_descriptions[utub_name]
            )


def test_update_utub_description_updates_utub_last_updated(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with those URLs
    WHEN the creator attempts to modify the UTub description to a new description, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN verify that the UTub's last updated field is updated to show later than originally
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    UPDATE_TEXT = "This is my new UTub description. 123456"
    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_of_user.last_updated

        current_utub_id = utub_of_user.id

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: UPDATE_TEXT,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 200

    with app.app_context():
        updated_utub: Utubs = Utubs.query.filter(Utubs.id == current_utub_id).first()

        assert (updated_utub.last_updated - initial_last_updated).total_seconds() > 0


def test_update_utub_desc_same_desc_does_not_update_utub_last_updated(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with those URLs
    WHEN the creator attempts to modify the UTub description to the same description, via a POST to
        "/utubs/<utub_id: int>/description" with valid form data, following this format:
            UTUB_DESCRIPTION_FORM.CSRF_TOKEN: String containing CSRF token for validation
            UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: New utub description to add
    THEN verify that the UTub's last updated field is not updated
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Grab this creator's UTub
    with app.app_context():
        utub_of_user: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_of_user.last_updated

        current_utub_id = utub_of_user.id
        current_utub_description = utub_of_user.utub_description

    utub_desc_form = {
        UTUB_DESCRIPTION_FORM.CSRF_TOKEN: csrf_token_string,
        UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: current_utub_description,
    }

    update_utub_desc_response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_DESC, utub_id=current_utub_id),
        data=utub_desc_form,
    )

    # Ensure valid reponse
    assert update_utub_desc_response.status_code == 200

    with app.app_context():
        updated_utub: Utubs = Utubs.query.filter(Utubs.id == current_utub_id).first()

        assert updated_utub.last_updated == initial_last_updated
