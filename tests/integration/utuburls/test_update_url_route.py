import threading
from unittest import mock

from flask import url_for
from flask_login import current_user
import pytest
import redis
import requests

from src.extensions.url_validation.url_validator import (
    InvalidURLError,
    UrlValidator,
    WaybackRateLimited,
)
from src.models.urls import Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import URL_FORM
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS
from tests.utils_for_test import is_string_in_logs, is_string_in_logs_regex

pytestmark = pytest.mark.urls


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_another_fresh_valid_url_as_utub_creator(
    mock_validate_url,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify that the new URL is stored in the database with same title, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    UPDATED_URL = "https://www.yahoo.com/"
    mock_validate_url.return_value = UPDATED_URL, True
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == UPDATED_URL).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "yahoo.com",
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub.id
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == UPDATED_URL
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub.id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == current_url_id,
            ).count()
            == 0
        )

        # Assert newest entity exist
        new_url_object: Urls = Urls.query.filter(Urls.url_string == UPDATED_URL).first()
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == new_url_id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == new_url_object.id,
            ).count()
            == 1
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == new_url_id,
        ).count() == len(associated_tags)


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_another_fresh_valid_url_as_url_member(
    mock_validate_url,
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, URLs added by each member, and tags associated with each URL
    WHEN the member attempts to modify the URL with a URL not already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the new URL is stored in the database with same title, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    NEW_FINAL_URL = "https://www.yahoo.com/"
    client, csrf_token_string, _, app = login_first_user_without_register
    mock_validate_url.return_value = NEW_FINAL_URL, True

    NEW_RAW_URL = "yahoo.com"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == NEW_FINAL_URL).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id == current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: NEW_RAW_URL,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_member_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub.id
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == NEW_FINAL_URL
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub.id,
                Utub_Urls.utub_id == utub_member_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == current_url_id,
            ).first()
            is None
        )

        # Assert newest entity exist
        new_url_object: Urls = Urls.query.filter(
            Urls.url_string == NEW_FINAL_URL
        ).first()
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == new_url_id,
                Utub_Urls.utub_id == utub_member_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == new_url_object.id,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == new_url_id,
        ).count() == len(associated_tags)


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_previously_added_url_as_utub_creator(
    mock_validate_url,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in database and is not in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()

        url_string_of_url_not_in_utub = url_not_in_utub.standalone_url.url_string
        mock_validate_url.return_value = url_string_of_url_not_in_utub, True

        url_id_of_url_not_in_utub = url_not_in_utub.id

        # Grab URL that already exists in this UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_in_utub.id
        id_of_url_object_in_utub = url_in_utub.url_id
        current_title = url_in_utub.url_title

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_in_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string_of_url_not_in_utub,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == id_of_url_in_utub
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING]
        == url_string_of_url_not_in_utub
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == id_of_url_object_in_utub,
            ).first()
            is None
        )

        # Assert newest entity exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_title == current_title,
                Utub_Urls.url_id == url_id_of_url_not_in_utub,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_previously_added_url_as_url_adder(
    mock_validate_url,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with a URL already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_member_of_not_created_utub: Utub_Members = Utub_Members.query.filter(
            Utub_Members.member_role != Member_Role.CREATOR
        ).first()
        utub_id = utub_member_of_not_created_utub.utub_id
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id == current_user.id, Utub_Urls.utub_id == utub_id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id
        url_in_this_utub_id = url_in_this_utub.id

        # Get a URL that isn't in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.url_id != current_url_id, Utub_Urls.utub_id != utub_id
        ).first()
        url_string_of_url_not_in_utub: str = url_not_in_utub.standalone_url.url_string
        mock_validate_url.return_value = url_string_of_url_not_in_utub, True

        url_id_of_url_not_in_utub = url_not_in_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string_of_url_not_in_utub,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub_id
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING]
        == url_string_of_url_not_in_utub
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is None
        )

        # Assert newest entity exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == url_id_of_url_not_in_utub,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_same_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with the same URL already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        url_in_utub_string: str = url_already_in_utub.standalone_url.url_string
        current_title = url_already_in_utub.url_title
        url_object_id = url_already_in_utub.url_id

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_in_utub_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID]) == id_of_url_in_utub
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == url_in_utub_string
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == url_object_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


def test_update_valid_url_with_same_url_as_url_adder(
    add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with the same URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE: URL_NO_CHANGE.URL_NOT_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            MODEL_STRS.URL_ID: ID of URL that was modified,
            MODEL_STRS.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TITLE: The title of the URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag objects associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_member_of_not_created_utub: Utub_Members = Utub_Members.query.filter(
            Utub_Members.member_role != Member_Role.CREATOR
        ).first()
        utub_id = utub_member_of_not_created_utub.utub_id
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id == current_user.id, Utub_Urls.utub_id == utub_id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_string = url_in_this_utub.standalone_url.url_string
        current_url_id = url_in_this_utub.url_id
        url_in_this_utub_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).all()
        associated_tag_objs = [
            {
                MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_id,
                MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
            }
            for tag in associated_tags
        ]

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: current_url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.UTUB_URL_ID])
        == url_in_this_utub_id
    )
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == current_url_string
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_objs

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


@mock.patch("src.extensions.notifications.notifications.threading.Thread")
@mock.patch(
    "src.extensions.url_validation.url_validator.UrlValidator", autospec=UrlValidator
)
@mock.patch(
    "src.extensions.url_validation.url_validator.UrlValidator._is_wayback_rate_limited"
)
@mock.patch("redis.Redis.from_url")
@mock.patch(
    "src.extensions.url_validation.url_validator.UrlValidator._perform_get_request"
)
@mock.patch(
    "src.extensions.url_validation.url_validator.UrlValidator._perform_head_request"
)
def test_update_url_when_wayback_ratelimited(
    mock_head_request,
    mock_get_request,
    mock_redis_from_url,
    mock_wayback_rate_limited,
    mock_validator,
    mock_thread,
    add_two_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and no URLs
        currently in the database or associated with the UTubs
    WHEN the user tries to update a URL in a UTub they are a creator of, but the HEAD and GET request fail,
        and Wayback is locally rate limited
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new URLs are added

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "Too many attempts, please try again in one minute.",
        STD_JSON.ERROR_CODE : 6
    }
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    mock_head_request.return_value = None
    mock_get_response = mock.Mock(spec=requests.Response)
    mock_get_response.status_code = 400
    mock_get_request.return_value = mock_get_response

    mock_redis_client = mock.MagicMock(spec=redis.Redis)
    mock_redis_from_url.return_value = mock_redis_client

    mock_wayback_rate_limited.return_value = True
    mock_validator.return_value._redis_uri = "fake://redis_uri"

    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub_that_is_creator_of = utub_creator_of.id
        url_to_update: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of
        ).first()
        utub_url_id = url_to_update.id

        # Get initial number of UTub-URL associations
        initial_urls = Urls.query.count()

    # Add the URL to the UTub
    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "yahoo.com",
    }

    update_url_string_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=id_of_utub_that_is_creator_of,
            utub_url_id=utub_url_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_response.status_code == 400

    update_url_string_response_json = update_url_string_response.json
    assert update_url_string_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        update_url_string_response_json[STD_JSON.MESSAGE]
        == URL_FAILURE.TOO_MANY_WAYBACK_ATTEMPTS
    )
    assert update_url_string_response_json[STD_JSON.ERROR_CODE] == 6

    with app.app_context():
        # Ensure new URL exists
        assert Urls.query.count() == initial_urls


@mock.patch("src.extensions.notifications.notifications.threading.Thread")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_invalid_url_as_utub_creator(
    mock_validate_url,
    mock_thread,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are not modified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_URL,
        STD_JSON.ERROR_CODE: 3
    }
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    mock_validate_url.side_effect = InvalidURLError
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        current_title = url_already_in_utub.url_title
        current_url_id = url_already_in_utub.url_id

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "AAAAA",
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


@mock.patch("src.extensions.notifications.notifications.threading.Thread")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_invalid_url_as_url_adder(
    mock_validate_url,
    mock_thread,
    add_two_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are not modified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_VALIDATE_URL,
        STD_JSON.ERROR_CODE: 3
    }
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    mock_validate_url.side_effect = InvalidURLError
    client, csrf_token_string, _, app = login_first_user_without_register

    INVALID_URL = "AAAAA"
    with app.app_context():
        utub_member_of_not_created_utub: Utub_Members = Utub_Members.query.filter(
            Utub_Members.member_role != Member_Role.CREATOR
        ).first()
        utub_id = utub_member_of_not_created_utub.utub_id
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id == current_user.id, Utub_Urls.utub_id == utub_id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id
        url_in_this_utub_id = url_in_this_utub.id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: INVALID_URL,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub_id,
                Utub_Urls.utub_id == utub_id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_empty_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an empty URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the url-utub-user associations and url-tag are unmodified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERROR_CODE : 5
        "Errors" : Object representing the errors found in the form, with the following fields
        {
            URL_FORM.URL_STRING: Array of errors associated with the url_string field,
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_URL = ""
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        current_title = url_already_in_utub.url_title
        current_url_id = url_already_in_utub.url_id

        # Find associated tags with this url already in UTub
        associated_tags: int = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_already_in_utub.id,
        ).count()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: NEW_URL,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 5
    assert (
        json_response[STD_JSON.ERRORS][URL_FORM.URL_STRING]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == current_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_creator_of.id,
                Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
            ).count()
            == associated_tags
        )


def test_update_url_string_with_fresh_valid_url_as_another_current_utub_member(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL and did not add the URL, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code,
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "https://www.yahoo.com"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == NEW_FRESH_URL).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id != current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_this_utub_id = url_in_this_utub.id
        url_in_utub_serialized_originally = url_in_this_utub.serialized_on_get_or_update
        original_url_id = url_in_this_utub.url_id

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: NEW_FRESH_URL,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_member_of.id,
            utub_url_id=url_in_this_utub_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after not modifying URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        utub_url_object: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_in_this_utub_id,
            Utub_Urls.utub_id == utub_member_of.id,
            Utub_Urls.url_id == original_url_id,
            Utub_Urls.url_title == current_title,
        ).first()

        # Verify original entry still exists
        assert utub_url_object is not None

        # Verify original serialization still exists
        assert (
            utub_url_object.serialized_on_get_or_update
            == url_in_utub_serialized_originally
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub_id,
        ).count() == len(associated_tags)


def test_update_url_with_fresh_valid_url_as_other_utub_member(
    add_first_user_to_second_utub_and_add_tags_remove_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of another UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL in a UTub they are not a member of, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code,
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "https://www.yahoo.com"
    with app.app_context():
        # Get UTub this user is not a member of
        utub_user_not_member_of: Utubs = Utubs.query.get(3)

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == NEW_FRESH_URL).first() is None

        # Get the URL not in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        url_in_utub_serialized_originally = url_in_this_utub.serialized_on_get_or_update
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.id

        # Get number of URLs in this UTub
        num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).count()

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: NEW_FRESH_URL,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_user_not_member_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_user_not_member_of.id
            ).count()
            == num_of_urls_in_utub
        )

        # Assert url-utub association hasn't changed
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_in_this_utub.id,
                Utub_Urls.utub_id == utub_user_not_member_of.id,
                Utub_Urls.url_id == original_url_id,
                Utub_Urls.user_id == original_user_id,
            )
            .first()
            .serialized_on_get_or_update
            == url_in_utub_serialized_originally
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).count() == len(associated_tags)


def test_update_nonexistent_url_as_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with each URL
    WHEN the creator attempts to modify a nonexistent URL via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the server responds with a 404 status code, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "https://www.yahoo.com"
    nonexistent_utub_url_id = 9999
    with app.app_context():
        # Get UTub this user is not a member of
        utub_member_user_not_member_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()
        utub_user_not_member_of: Utubs = utub_member_user_not_member_of.to_utub

        # Use URL not already in database
        assert Urls.query.filter(Urls.url_string == NEW_FRESH_URL).first() is None

        # Get the URL not in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_utub_serialized_originally = url_in_this_utub.serialized_on_get_or_update
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        # Get number of URLs in this UTub
        num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).count()

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: NEW_FRESH_URL,
    }

    update_url_string_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_user_not_member_of.id,
            utub_url_id=nonexistent_utub_url_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_response.status_code == 404
    assert IDENTIFIERS.HTML_404.encode() in update_url_string_response.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_user_not_member_of.id
            ).count()
            == num_of_urls_in_utub
        )

        utub_url_object: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_in_this_utub.id,
            Utub_Urls.utub_id == utub_user_not_member_of.id,
            Utub_Urls.url_id == original_url_id,
            Utub_Urls.user_id == original_user_id,
            Utub_Urls.url_title == current_title,
        ).first()

        # Assert url-utub association hasn't changed
        assert utub_url_object is not None

        assert (
            utub_url_object.serialized_on_get_or_update
            == url_in_utub_serialized_originally
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).count() == len(associated_tags)


def test_update_url_with_fresh_valid_url_as_other_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register
):
    """
    GIVEN a valid creator of a UTub that has members, URLs, and tags associated with each URL
    WHEN the member attempts to modify the URL title and change the URL for a URL of another UTub, via a PATCH to:
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the backend denies the user, the url-utub-user associations and url-tag are not modified,
        all other URL associations are kept consistent, the server sends back a 403 HTTP status code,
        and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL,
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "https://www.yahoo.com"
    with app.app_context():
        # Get UTub this user is not a member of
        utub_member_user_not_member_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()
        utub_user_not_member_of: Utubs = utub_member_user_not_member_of.to_utub

        # Use URL not already in database
        assert Urls.query.filter(Urls.url_string == NEW_FRESH_URL).first() is None

        # Get the URL not in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_utub_serialized_originally = url_in_this_utub.serialized_on_get_or_update
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        # Get number of URLs in this UTub
        num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).count()

        # Find associated tags with this url
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: NEW_FRESH_URL,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_user_not_member_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_user_not_member_of.id
            ).count()
            == num_of_urls_in_utub
        )

        utub_url_object: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_in_this_utub.id,
            Utub_Urls.utub_id == utub_user_not_member_of.id,
            Utub_Urls.url_id == original_url_id,
            Utub_Urls.user_id == original_user_id,
            Utub_Urls.url_title == current_title,
        ).first()

        # Assert url-utub association hasn't changed
        assert utub_url_object is not None

        assert (
            utub_url_object.serialized_on_get_or_update
            == url_in_utub_serialized_originally
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_user_not_member_of.id,
            Utub_Url_Tags.utub_url_id == url_in_this_utub.id,
        ).count() == len(associated_tags)


def test_update_valid_url_with_missing_url_field_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a missing URL field, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
    THEN verify that the url-utub-user associations and url-tag are unmodified, all other URL associations are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERROR_CODE: 5,
        STD_JSON.ERRORS : Object representing the errors found in the form, with the following fields
        {
            URL_FORM.URL_STRING: Array of errors associated with the url_string field,
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        original_url_id = url_already_in_utub.url_id
        current_title = url_already_in_utub.url_title

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_already_in_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_already_in_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 5
    assert (
        json_response[STD_JSON.ERRORS][URL_FORM.URL_STRING]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == url_already_in_utub.id,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == original_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


def test_update_valid_url_with_valid_url_missing_csrf(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a missing CSRF token, and a valid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.URL_STRING: String of URL to add
    THEN the UTub-user-URL associations are consistent across the change, all URLs/URL titles titles are kept consistent,
        the server sends back a 400 HTTP status code, and the server sends back the appropriate HTML element
        indicating the CSRF token is missing
    """
    client, _, _, app = login_first_user_without_register

    NEW_URL = "yahoo.com"
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id
        original_url_id = url_already_in_utub.url_id
        current_title = url_already_in_utub.url_title

        # Find associated tags with this url already in UTub
        associated_tags: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == url_already_in_utub.id,
        ).all()

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.URL_STRING: NEW_URL,
    }

    update_url_string_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_already_in_utub.id,
        ),
        data=update_url_string_form,
    )

    # Ensure valid reponse
    assert update_url_string_response.status_code == 403
    assert update_url_string_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in update_url_string_response.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.id == id_of_url_in_utub,
                Utub_Urls.utub_id == utub_creator_of.id,
                Utub_Urls.url_id == original_url_id,
                Utub_Urls.url_title == current_title,
            ).first()
            is not None
        )

        # Check associated tags
        assert Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id,
            Utub_Url_Tags.utub_url_id == id_of_url_in_utub,
        ).count() == len(associated_tags)


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_updates_utub_last_updated(
    mock_validate_url,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL already in the database, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify the server sends back a 200 HTTP status code, and the UTub's last updated is updated

    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_creator_of.last_updated

        # Grab URL that already exists in database and is not in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()
        url_string_of_url_not_in_utub: str = url_not_in_utub.standalone_url.url_string
        mock_validate_url.return_value = url_string_of_url_not_in_utub, True

        # Grab URL that already exists in this UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string_of_url_not_in_utub,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200

    with app.app_context():
        # Assert database is consistent after newly modified URL
        current_utub: Utubs = Utubs.query.get(utub_creator_of.id)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


@mock.patch("src.extensions.notifications.notifications.threading.Thread")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_invalid_url_does_not_update_utub_last_updated(
    mock_validate_url,
    mock_thread,
    add_two_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN the server sends back a 400 HTTP status code, and the UTub last updated field is not modified
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    mock_validate_url.side_effect = InvalidURLError
    client, csrf_token_string, _, app = login_first_user_without_register

    INVALID_URL = "AAAAA"
    with app.app_context():
        utub_member_of_not_created_utub: Utub_Members = Utub_Members.query.filter(
            Utub_Members.member_role != Member_Role.CREATOR
        ).first()
        utub_member_of: Utubs = utub_member_of_not_created_utub.to_utub
        utub_id = utub_member_of_not_created_utub.utub_id
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id == current_user.id, Utub_Urls.utub_id == utub_id
        ).first()

        initial_last_updated = utub_member_of.last_updated

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: INVALID_URL,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_id)
        assert current_utub.last_updated == initial_last_updated


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_utub_url_with_url_already_in_utub(
    mock_validate_url,
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, URLs added by each member, and tags associated with each URL
    WHEN the member attempts to modify the URL with a URL already in the UTub, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN verify that the server responds with a 409 HTTP status code, the URL is not modified in the UTub, and the proper JSON response
        is given

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.URL_IN_UTUB,
        STD_JSON.ERROR_CODE: 4
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get UTub this user is member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Find URL already in UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id
        ).first()
        current_url_id = url_in_this_utub.url_id
        current_url_string = url_in_this_utub.standalone_url.url_string
        mock_validate_url.return_value = current_url_string, True

        # Find another URL in this UTub that doesn't match given URL
        other_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.url_id != current_url_id
        ).first()
        other_utub_url_id_to_update = other_url_in_utub.id
        other_url_id = other_url_in_utub.url_id

        num_of_url_tag_assocs = Utub_Url_Tags.query.count()
        num_of_urls = Urls.query.count()
        num_of_url_utubs_assocs = Utub_Urls.query.count()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: current_url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_member_of.id,
            utub_url_id=other_utub_url_id_to_update,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 409

    # Assert JSON response from server is valid
    json_response = update_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert json_response[STD_JSON.ERROR_CODE] == 4
    assert json_response[MODEL_STRS.URL_STRING] == current_url_string

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == Urls.query.count()
        assert num_of_url_tag_assocs == Utub_Url_Tags.query.count()
        assert num_of_url_utubs_assocs == Utub_Urls.query.count()

        # Assert previous entity no longer exists
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.url_id == other_url_id
            ).first()
            is not None
        )


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_fresh_valid_url_log(
    mock_validate_url,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 200 HTTP status code, and the logs are valid
    """
    UPDATED_URL = "https://www.yahoo.com/"
    mock_validate_url.return_value = UPDATED_URL, True
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        assert Urls.query.filter(Urls.url_string == UPDATED_URL).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "yahoo.com",
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200
    assert is_string_in_logs(
        "Finished checks for url_to_change_to='yahoo.com'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)

    with app.app_context():
        new_url = Urls.query.filter(Urls.url_string == UPDATED_URL).first()

    assert is_string_in_logs(f"Added new URL, URL.id={new_url.id}", caplog.records)
    assert is_string_in_logs("Added URL to UTub", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_creator_of.id}", caplog.records)
    assert is_string_in_logs(f"URL.id={new_url.id}", caplog.records)


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_existing_url_log(
    mock_validate_url,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 200 HTTP status code, and the logs are valid
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
        url_not_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()
        url_string = url_not_in_this_utub.standalone_url.url_string
        url_id = url_not_in_this_utub.url_id

    mock_validate_url.return_value = url_string, True

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200
    assert is_string_in_logs(
        f"Finished checks for url_to_change_to='{url_string}'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)

    assert is_string_in_logs(
        f"URL already exists in U4I, URL.id={url_id}", caplog.records
    )
    assert is_string_in_logs("Added URL to UTub", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_creator_of.id}", caplog.records)
    assert is_string_in_logs(f"URL.id={url_id}", caplog.records)


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_same_url_log(
    mock_validate_url,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with the same URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 409 HTTP status code, and the logs are valid
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
        url_string = url_in_this_utub.standalone_url.url_string
        url_id = url_in_this_utub.url_id

    mock_validate_url.return_value = url_string, True

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "yahoo.com",
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 409
    assert is_string_in_logs(
        "Finished checks for url_to_change_to='yahoo.com'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)

    assert is_string_in_logs(
        f"URL already exists in U4I, URL.id={url_id}", caplog.records
    )
    assert is_string_in_logs(
        f"User={user.id} tried adding URL.id={url_id} but already exists in UTub.id={utub_creator_of.id}",
        caplog.records,
    )


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_valid_url_with_same_url_before_normalization_url_log(
    mock_validate_url,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not in database but after normalization is already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 409 HTTP status code, and the logs are valid
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
        url_string = url_in_this_utub.standalone_url.url_string
        url_id = url_in_this_utub.url_id
        url_string_before_normalize = url_string.replace("https://", "")

    mock_validate_url.return_value = url_string, True

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string_before_normalize,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 409
    assert is_string_in_logs(
        f"Finished checks for url_to_change_to='{url_string_before_normalize}'",
        caplog.records,
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)

    assert is_string_in_logs(
        f"URL already exists in U4I, URL.id={url_id}", caplog.records
    )
    assert is_string_in_logs(
        f"User={user.id} tried adding URL.id={url_id} but already exists in UTub.id={utub_creator_of.id}",
        caplog.records,
    )


@mock.patch("src.extensions.notifications.notifications.threading.Thread")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_to_invalid_url_log(
    mock_validate_url,
    mock_thread,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 400 HTTP status code, and the logs are valid
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    client, csrf_token_string, user, app = login_first_user_without_register
    mock_validate_url.side_effect = InvalidURLError("Invalid URL error")

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_string = url_in_this_utub.standalone_url.url_string.replace("https://", "")

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400
    assert is_string_in_logs(
        f"Unable to validate the URL given by User={user.id}", caplog.records
    )
    assert is_string_in_logs_regex(
        r"(.*)[\s](.*)Took (\d).(\d+) ms to fail validation[\s](.*)[\s](.*)",
        caplog.records,
    )
    assert is_string_in_logs(f"url_string={url_string}", caplog.records)
    assert is_string_in_logs("Exception=Invalid URL error", caplog.records)


@mock.patch("src.extensions.notifications.notifications.threading.Thread")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_to_wayback_ratelimited_url_log(
    mock_validate_url,
    mock_thread,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 400 HTTP status code, and the logs are valid
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    client, csrf_token_string, user, app = login_first_user_without_register
    mock_validate_url.side_effect = WaybackRateLimited("Invalid URL error")

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_string = url_in_this_utub.standalone_url.url_string.replace("https://", "")

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400
    assert is_string_in_logs(
        f"Unable to validate the URL given by User={user.id}", caplog.records
    )
    assert is_string_in_logs_regex(
        r"(.*)[\s](.*)Took (\d).(\d+) ms to fail validation[\s](.*)[\s](.*)",
        caplog.records,
    )
    assert is_string_in_logs(f"url_string={url_string}", caplog.records)
    assert is_string_in_logs("Exception=Invalid URL error", caplog.records)


def test_update_to_same_url_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 200 HTTP status code, and the logs are valid
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
        url_string = url_in_this_utub.standalone_url.url_string

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 200
    assert is_string_in_logs(
        f"User={user.id} tried changing UTubURL.id={url_in_this_utub.id} to the same URL",
        caplog.records,
    )


def test_update_url_user_not_in_utub_log(
    add_two_users_and_all_urls_to_each_utub_with_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a non-member attempts to modify the URL with URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 403 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        utub_member_user_not_member_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()
        utub_user_not_member_of: Utubs = utub_member_user_not_member_of.to_utub

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        url_string = url_in_this_utub.standalone_url.url_string

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_user_not_member_of.id,
            utub_url_id=url_in_this_utub.id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 403
    assert is_string_in_logs(
        f"User={user.id} not in UTub.id={utub_user_not_member_of.id}", caplog.records
    )


def test_update_url_user_not_allowed_to_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a member attempts to modify URL they did not add with URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 403 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        url_in_this_utub_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != user.id,
            Utub_Urls.user_id != user.id,
        ).first()
        utub_id = url_in_this_utub_did_not_add.utub_id
        utub_url_id = url_in_this_utub_did_not_add.id
        url_string = url_in_this_utub_did_not_add.standalone_url.url_string

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 403
    assert is_string_in_logs(
        f"User={user.id} not allowed to modify UTubURL.id={utub_url_id} in UTub.id={utub_id}",
        caplog.records,
    )


def test_update_nonexistent_url_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a member attempts to modify nonexistent URL via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 404 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == user.id,
            Utub_Urls.user_id == user.id,
        ).first()
        utub_id = url_in_this_utub.utub_id
        utub_url_id = 9999
        url_string = url_in_this_utub.standalone_url.url_string

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 404
    assert is_string_in_logs(
        f"User={user.id} tried to change nonexistent UTubURL.id={utub_url_id} in UTub.id={utub_id}",
        caplog.records,
    )


def test_update_url_in_other_utub_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a member attempts to modify URL but gives invalid UTub ID via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 404 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == user.id,
            Utub_Urls.user_id == user.id,
        ).first()
        utub_id = url_in_this_utub.utub_id
        utub_url_id = url_in_this_utub.id
        invalid_utub: Utubs = Utubs.query.filter(Utubs.id != utub_id).first()
        invalid_utub_id = invalid_utub.id

        url_string = url_in_this_utub.standalone_url.url_string

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=invalid_utub_id,
            utub_url_id=utub_url_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 404
    assert is_string_in_logs(
        f"User={user.id} tried to change UTubURL.id={utub_url_id} that is not in UTub.id={invalid_utub_id}",
        caplog.records,
    )


def test_update_url_with_only_spaces_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a member attempts to modify URL but gives URL string with only spaces in body via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 400 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == user.id,
            Utub_Urls.user_id == user.id,
        ).first()
        utub_id = url_in_this_utub.utub_id
        utub_url_id = url_in_this_utub.id

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "  ",
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400
    assert is_string_in_logs(
        f"User={user.id} tried changing UTubURL.id={utub_url_id} to a URL with only spaces",
        caplog.records,
    )


def test_update_url_with_invalid_form_log(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN a member attempts to modify URL but gives invalid form in body via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "urlString": String of URL to add
    THEN verify the server sends back a 400 HTTP status code, and the logs are valid
    """
    client, csrf_token_string, user, app = login_first_user_without_register

    with app.app_context():
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == user.id,
            Utub_Urls.user_id == user.id,
        ).first()
        utub_id = url_in_this_utub.utub_id
        utub_url_id = url_in_this_utub.id

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_id,
            utub_url_id=utub_url_id,
        ),
        data=update_url_string_form,
    )

    assert update_url_string_form.status_code == 400
    assert is_string_in_logs(
        f"User={user.id} | Invalid form: url_string={URL_FAILURE.FIELD_REQUIRED}",
        caplog.records,
    )


@mock.patch("src.extensions.notifications.notifications.requests.post")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_invalid_url_sends_notification(
    mock_validate_url,
    mock_request_post,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add that contains an invalid URL
    THEN verify that server sends back a 400 HTTP status code and a notification is sent
    """
    notification_sent = threading.Event()

    def mock_post_with_event(*args, **kwargs):
        mock_response = type("MockResponse", (), {"status_code": 200})()
        notification_sent.set()  # Signal that the request was made
        return mock_response

    mock_request_post.side_effect = mock_post_with_event
    mock_validate_url.side_effect = InvalidURLError
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "AAAAA",
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        data=update_url_string_form,
    )

    # Wait for notification to be sent (with timeout)
    assert notification_sent.wait(
        timeout=5.0
    ), "Notification was not sent within timeout"

    assert update_url_string_form.status_code == 400

    mock_request_post.assert_called_once()


@mock.patch("src.extensions.notifications.notifications.requests.post")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_waybacked_limited_url_sends_notification(
    mock_validate_url,
    mock_request_post,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add that contains an invalid URL
    THEN verify that server sends back a 400 HTTP status code and a notification is sent
    """
    notification_sent = threading.Event()

    def mock_post_with_event(*args, **kwargs):
        mock_response = type("MockResponse", (), {"status_code": 200})()
        notification_sent.set()  # Signal that the request was made
        return mock_response

    mock_request_post.side_effect = mock_post_with_event
    mock_validate_url.side_effect = WaybackRateLimited
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "AAAAA",
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        data=update_url_string_form,
    )

    # Wait for notification to be sent (with timeout)
    assert notification_sent.wait(
        timeout=5.0
    ), "Notification was not sent within timeout"

    assert update_url_string_form.status_code == 400

    mock_request_post.assert_called_once()


@mock.patch("src.extensions.notifications.notifications.requests.post")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_update_invalidated_url_sends_notification(
    mock_validate_url,
    mock_request_post,
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add that contains an invalid URL
    THEN verify that server sends back a 400 HTTP status code and a notification is sent
    """
    notification_sent = threading.Event()

    def mock_post_with_event(*args, **kwargs):
        mock_response = type("MockResponse", (), {"status_code": 200})()
        notification_sent.set()  # Signal that the request was made
        return mock_response

    mock_request_post.side_effect = mock_post_with_event
    mock_validate_url.return_value = "AAAA", False
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id,
            Utub_Urls.user_id == current_user.id,
        ).first()
        id_of_url_in_utub = url_already_in_utub.id

    update_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "AAAAA",
    }

    update_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=id_of_url_in_utub,
        ),
        data=update_url_string_form,
    )

    # Wait for notification to be sent (with timeout)
    assert notification_sent.wait(
        timeout=5.0
    ), "Notification was not sent within timeout"

    assert update_url_string_form.status_code == 200

    mock_request_post.assert_called_once()
