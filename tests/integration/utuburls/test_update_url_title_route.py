from flask import url_for
from flask_login import current_user
import pytest

from src.models.urls import Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import URL_FORM
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.urls


def test_update_url_title_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN verify that title is modified in the database, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_TITLE_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
            MODEL_STRS.URL_TITLE: String representing the URL title in this UTub
            MODEL_STRS.URL_STRING: String representing the URL in this UTub
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_url_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()
        associated_tag_objects = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_TITLE_MODIFIED
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TITLE] == NEW_TITLE
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == current_url_id
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objects

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        new_url_item: Utub_Urls = Utub_Urls.query.get(current_url_id)
        assert new_url_item.url_title == NEW_TITLE

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_url_adder(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URL added by the member, and tags associated with each URL
    WHEN the member attempts to modify the URL title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN verify that the new title is modified in the database, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_TITLE_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
            MODEL_STRS.URL_TITLE: String representing the URL title in this UTub
            MODEL_STRS.URL_STRING: String representing the URL in this UTub
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id == current_user.id
        ).first()
        current_url: str = url_in_this_utub.standalone_url.url_string
        current_url_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()
        associated_tag_objects = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: current_url,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_member_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_TITLE_MODIFIED
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TITLE] == NEW_TITLE
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == current_url_id
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objects

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert entity exists
        utub_url_object: Utub_Urls = Utub_Urls.query.get(current_url_id)
        assert utub_url_object.url_title == NEW_TITLE

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_with_same_title_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with the same title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of same title
    THEN verify that title is not modified in the database, the url-utub-user associations and url-tag are
        not modified, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_TITLE_NOT_MODIFIED,
        URL_SUCCESS.URL: Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was not modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
            MODEL_STRS.URL_TITLE: String representing the URL title in this UTub
            MODEL_STRS.URL_STRING: String representing the URL in this UTub
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()
        associated_tag_objects = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: current_title,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TITLE] == current_title
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == current_url_id
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objects

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        new_url_item: Utub_Urls = Utub_Urls.query.get(current_url_id)
        assert new_url_item.url_title == current_title

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_with_same_title_url_adder(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URL added by the member, and tags associated with each URL
    WHEN the member attempts to modify the URL title with the same title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of same title
    THEN verify that the title is the same in the database, the url-utub-user associations and url-tag are
        not modified, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_TITLE_NOT_MODIFIED,
        URL_SUCCESS.URL: Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was not modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
            MODEL_STRS.URL_TITLE: String representing the URL title in this UTub
            MODEL_STRS.URL_STRING: String representing the URL in this UTub
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id == current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url = url_in_this_utub.standalone_url.url_string
        current_url_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()
        associated_tag_objects = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: current_url,
        URL_FORM.URL_TITLE: current_title,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_member_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TITLE] == current_title
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == current_url_id
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objects

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert entity exists
        utub_url_object: Utub_Urls = Utub_Urls.query.get(current_url_id)
        assert utub_url_object.url_title == current_title

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_as_utub_member_not_adder_or_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URL not added by the member, and tags associated with each URL
    WHEN the member attempts to modify the URL title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN verify that the title is not modified in the database, the url-utub-user associations and url-tag are
        not modified, all other URL associations are kept consistent,
        the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_MODIFY_URL,
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id != current_user.id
        ).first()
        current_url = url_in_this_utub.standalone_url.url_string
        current_url_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: current_url,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_member_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after not modifying URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert entity does not exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == current_url_id,
                Utub_Urls.utub_id == utub_member_of.id,
                Utub_Urls.url_title == NEW_TITLE,
            ).first()
            is None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_with_empty_title_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title to an empty title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: Empty string
    THEN verify that title is not modified in the database, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERROR_CODE: 3,
        STD_JSON.ERRORS: Object containing arrays per input field indicating the error for a field
        {
            URL_FAILURE.URL_TITLE: [URL_FAILURE.FIELD_REQUIRED,]
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = ""
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 3
    assert (
        json_response[STD_JSON.ERRORS][URL_FAILURE.URL_TITLE]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        utub_url_object: Utub_Urls = Utub_Urls.query.get(current_url_id)
        assert utub_url_object.url_title == current_title

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_with_fully_sanitized_title_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title to a title that is sanitized by backend, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: Title that is fully sanitized by backend
    THEN verify the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERROR_CODE: 3,
        STD_JSON.ERRORS: Object containing arrays per input field indicating the error for a field
        {
            URL_FAILURE.URL_TITLE: [URL_FAILURE.INVALID_INPUT]
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_url_id = url_in_this_utub.id

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: '<img src="evl.jpg">',
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 3
    assert json_response[STD_JSON.ERRORS][URL_FAILURE.URL_TITLE] == [
        URL_FAILURE.INVALID_INPUT
    ]


def test_update_url_title_with_partially_sanitized_title_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title to a title that is sanitized by backend, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: Title that is fully sanitized by backend
    THEN verify the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERROR_CODE: 3,
        STD_JSON.ERRORS: Object containing arrays per input field indicating the error for a field
        {
            URL_FAILURE.URL_TITLE: [URL_FAILURE.INVALID_INPUT]
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_url_id = url_in_this_utub.id

    for url_title in (
        "<<HELLO>>",
        "<h1>Hello</h1>",
    ):
        update_url_string_title_form = {
            URL_FORM.CSRF_TOKEN: csrf_token_string,
            URL_FORM.URL_TITLE: url_title,
        }

        update_url_string_title_form = client.patch(
            url_for(
                ROUTES.URLS.UPDATE_URL_TITLE,
                utub_id=utub_creator_of.id,
                utub_url_id=current_url_id,
            ),
            data=update_url_string_title_form,
        )

        assert update_url_string_title_form.status_code == 400

        # Assert JSON response from server is valid
        json_response = update_url_string_title_form.json
        assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
        assert int(json_response[STD_JSON.ERROR_CODE]) == 3
        assert json_response[STD_JSON.ERRORS][URL_FAILURE.URL_TITLE] == [
            URL_FAILURE.INVALID_INPUT
        ]


def test_update_url_title_as_member_of_other_utub(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN a member that isn't the creator/adder, but is also a creator and member of two other UTubs,
        attempts to modify the URL title to an empty title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: Empty string
    THEN verify the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
        STD_JSON.ERROR_CODE: 1,
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com."
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL of another UTub
        url_not_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id,
            Utub_Urls.user_id != current_user.id,
        ).first()
        utub_id = url_not_in_this_utub.utub_id
        current_url_id = url_not_in_this_utub.id
        current_title = url_not_in_this_utub.url_title

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        utub_url_object: Utub_Urls = Utub_Urls.query.get(current_url_id)
        assert utub_url_object.url_title == current_title

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_with_missing_title_field_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with a form missing the title field, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
    THEN verify that title is not modified in the database, the url-utub-user associations and url-tag are
        unchanged, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERROR_CODE: 2,
        STD_JSON.ERRORS: Object containing arrays per input field indicating the error for a field
        {
            URL_FAILURE.URL_TITLE: [URL_FAILURE.FIELD_REQUIRED,]
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        json_response[STD_JSON.ERRORS][URL_FAILURE.URL_TITLE]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        utub_url_object: Utub_Urls = Utub_Urls.query.get(current_url_id)
        assert utub_url_object.url_title == current_title

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_with_missing_csrf_field_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with a form missing the CSRF token, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.URL_TITLE: String containing a new URL title
    THEN verify that the url-utub-user associations and url-tag are unchanged all other URL associations
        are kept consistent, the server sends back a 400 HTTP status code,
        and the server sends back the appropriate HTML response

    Proper HTML response contains the following:
        "<p>The CSRF token is missing.</p>"
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {URL_FORM.URL_TITLE: current_title + "AAA"}

    update_url_string_title_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_response.status_code == 403
    assert update_url_string_title_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in update_url_string_title_response.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        utub_url_object: Utub_Urls = Utub_Urls.query.get(current_url_id)
        assert utub_url_object.url_title == current_title

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == current_url_id,
        ).count() == len(associated_tags)


def test_update_url_title_of_nonexistent_url(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN a member, attempts to modify the URL title of a URL that does not exist, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: A new URL title
    THEN verify that the url-utub-user associations and url-tag are unchanged,
        all other URL associations are kept consistent, the server sends back a 404 HTTP
        status code, and the server sends back the appropriate HTML page response

    HTML Response will contain the following text:
        "404 - Invalid Request"
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NONEXISTENT_URL_ID = 999
    NEW_TITLE = "This is my newest facebook.com."
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id = utub_creator_of.id

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_id,
            utub_url_id=NONEXISTENT_URL_ID,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 404

    # Assert JSON response from server is valid
    assert IDENTIFIERS.HTML_404.encode() in update_url_string_title_form.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()


def test_update_url_title_in_nonexistent_utub(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN a member, attempts to modify the URL title of a URL in a UTub that does not exist, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: A new URL title
    THEN verify that the url-utub-user associations and url-tag are unchanged,
        all other URL associations are kept consistent, the server sends back a 404 HTTP
        status code, and the server sends back the appropriate HTML page response

    HTML Response will contain the following text:
        "404 - Invalid Request"
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com."
    NONEXISTENT_UTUB_ID = 999

    # Get the URL of another UTub
    NONEXISTENT_URL_ID = 999

    with app.app_context():
        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=NONEXISTENT_UTUB_ID,
            utub_url_id=NONEXISTENT_URL_ID,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 404

    # Assert JSON response from server is valid
    assert IDENTIFIERS.HTML_404.encode() in update_url_string_title_form.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()


def test_update_url_title_updates_utub_last_updated(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 200 HTTP status code, and the UTub's last updated field is updated
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_creator_of.last_updated

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_url_id = url_in_this_utub.id

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 200

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_creator_of.id)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


def test_update_url_title_with_same_title_does_not_update_utub_last_updated(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with the same title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of same title
    THEN the server sends back a 200 HTTP status code, and the UTub's last updated is not updated
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_creator_of.last_updated

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.id

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: current_title,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 200

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_creator_of.id)
        assert current_utub.last_updated == initial_last_updated


def test_update_url_title_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 200 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_url_id = url_in_this_utub.id

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 200
    assert is_string_in_logs("URL title updated", caplog.records)


def test_update_url_identical_title_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title to the same title, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 200 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_url_id = url_in_this_utub.id
        current_url_title = url_in_this_utub.url_title

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: current_url_title,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 200
    assert is_string_in_logs(
        f"User={user.id} tried updating to identical URL title", caplog.records
    )


def test_update_url_title_nonexistent_url_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title for a nonexistent URL, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 404 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    utub_url_id = 9999
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=utub_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 404
    assert is_string_in_logs(
        f"User={user.id} tried to modify title for nonexistent UTubURL.id={utub_url_id} from UTub.id={utub_creator_of.id}",
        caplog.records,
    )


def test_update_url_title_url_not_in_utub_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title for a URL that isn't in the prescribed UTub, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 404 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 404
    assert is_string_in_logs(
        f"User={user.id} tried to modify title for UTubURL.id={url_in_this_utub.id} that is not in UTub.id={utub_creator_of.id}",
        caplog.records,
    )


def test_update_url_title_user_not_in_utub_log(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the user attempts to modify the URL title for a UTub they aren't, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 403 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL of another UTub
        url_not_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id,
            Utub_Urls.user_id != current_user.id,
        ).first()
        utub_id = url_not_in_this_utub.utub_id
        current_url_id = url_not_in_this_utub.id

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )
    assert update_url_string_title_form.status_code == 403
    assert is_string_in_logs(f"User={user.id} not in UTub.id={utub_id}", caplog.records)


def test_update_url_title_user_not_allowed_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title for a URL when the user isn't in the URL's UTub, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 403 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id != current_user.id
        ).first()
        current_url_id = url_in_this_utub.id

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_member_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 403
    assert is_string_in_logs(
        f"User={user.id} not allowed to modify UTubURL.id={current_url_id} in UTub.id={utub_member_of.id}",
        caplog.records,
    )


def test_update_url_title_missing_title_field_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with a missing title field, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 400 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_url_id = url_in_this_utub.id

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 400
    assert is_string_in_logs(f"User={user.id} missing URL title field", caplog.records)


def test_update_url_title_empty_title_field_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with a missing title field, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>/title" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: String of new title
    THEN the server sends back a 400 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_url_id = url_in_this_utub.id

    update_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: "",
    }

    update_url_string_title_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE,
            utub_id=utub_creator_of.id,
            utub_url_id=current_url_id,
        ),
        data=update_url_string_title_form,
    )

    assert update_url_string_title_form.status_code == 400
    assert is_string_in_logs(
        f"User={user.id} | Invalid form: url_title={URL_FAILURE.FIELD_REQUIRED}",
        caplog.records,
    )
