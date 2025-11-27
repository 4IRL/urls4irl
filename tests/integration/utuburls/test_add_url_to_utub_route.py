import threading
from unittest import mock

import ada_url
from flask import url_for
from flask_login import current_user
import pytest

from src.extensions.url_validation.url_validator import InvalidURLError
from src.models.urls import Urls
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from src.urls.constants import URLErrorCodes
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import URL_FORM
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS
from tests.models_for_test import valid_url_strings
from tests.unit.test_url_validation import (
    FLATTENED_NORMALIZED_AND_INPUT_VALID_URLS,
    FLATTENED_URLS_WITH_DIFFERENT_PATH,
    INVALID_URLS_TO_VALIDATE,
)
from tests.utils_for_test import is_string_in_logs, is_string_in_logs_regex

pytestmark = pytest.mark.urls


def test_add_valid_url_as_utub_member(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a UTub they are a part of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, that a new Url_UTub-User association exists where it didn't before,
        with the correct URL title

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : URL_SUCCESS.URL_ADDED,
        MODEL_STRS.URL : {
            "urlString": String representing the URL ,
            "url_ID" : Integer representing the URL ID,
        },
        URL_SUCCESS.UTUB_ID : Integer representing the ID of the UTub added to,
        URL_SUCCESS.ADDED_BY : Integer representing the ID of current user who added this URL to this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        number_of_urls_in_db = Urls.query.count()
        url_id_to_add = url_to_add.id
        url_string_to_add = url_to_add.url_string
        url_title_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 200

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_ADDED
    assert int(add_url_json_response[URL_SUCCESS.UTUB_ID]) == utub_id_to_add_to
    assert int(add_url_json_response[URL_SUCCESS.ADDED_BY]) == current_user.id
    assert (
        add_url_json_response[MODEL_STRS.URL][URL_FORM.URL_STRING] == url_string_to_add
    )
    assert (
        int(add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.UTUB_URL_ID])
        == url_id_to_add
    )

    with app.app_context():
        # Ensure no new URL created
        assert Urls.query.count() == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of: Utubs = Utubs.query.get(utub_id_to_add_to)

        # Ensure URL now in UTub
        assert len(current_utub_member_of.utub_urls) > 0
        assert url_id_to_add in [url.url_id for url in current_utub_member_of.utub_urls]

        url_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_to_add_to,
            Utub_Urls.url_id == url_id_to_add,
            Utub_Urls.user_id == current_user.id,
        ).all()

        # Ensure Url-Utubs-User association exists
        assert len(url_in_utub) == 1

        # Ensure title updated appropriately
        assert url_in_utub[0].url_title == url_title_to_add

        assert Utub_Urls.query.count() == initial_utub_urls + 1


def test_add_valid_url_as_utub_creator(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a UTub they are a creator of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Url_UTub-User association exists where it didn't before

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : URL_SUCCESS.URL_ADDED,
        MODEL_STRS.URL : {
            URL_FORM.URL_STRING: String representing the URL ,
            URL_SUCCESS.UTUB_URL_ID: Integer representing the URL ID
        },
        URL_SUCCESS.UTUB_ID : Integer representing the ID of the UTub added to,
        URL_SUCCESS.ADDED_BY : Integer representing the ID of current user who added this URL to this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a creator of
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        number_of_urls_in_db = Urls.query.count()
        url_id_to_add = url_to_add.id
        url_string_to_add = url_to_add.url_string
        url_title_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }
    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 200

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_ADDED
    assert int(add_url_json_response[URL_SUCCESS.UTUB_ID]) == utub_id_to_add_to
    assert int(add_url_json_response[URL_SUCCESS.ADDED_BY]) == current_user.id
    assert (
        add_url_json_response[MODEL_STRS.URL][URL_FORM.URL_STRING] == url_string_to_add
    )
    assert (
        int(add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.UTUB_URL_ID])
        == url_id_to_add
    )

    with app.app_context():
        # Ensure no new URL created
        assert Urls.query.count() == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utubs.query.get(utub_id_to_add_to)

        # Ensure URL now in UTub
        assert len(current_utub_member_of.utub_urls) > 0
        assert url_id_to_add in [url.url_id for url in current_utub_member_of.utub_urls]

        url_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_to_add_to,
            Utub_Urls.url_id == url_id_to_add,
            Utub_Urls.user_id == current_user.id,
        ).all()

        # Ensure Url-Utubs-User association exists
        assert len(url_in_utub) == 1

        # Ensure title updated
        assert url_in_utub[0].url_title == url_title_to_add

        assert Utub_Urls.query.count() == initial_utub_urls + 1


@pytest.mark.parametrize(
    "invalid_url",
    [invalid_url for invalid_url in INVALID_URLS_TO_VALIDATE if "@" not in invalid_url],
)
def test_add_invalid_url_as_utub_member(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
    invalid_url,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a nonexistant URL to a UTub they are a part of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : "Failure",
        STD_JSON.MESSAGE : "Unable to add this URL",
        STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_URL_ERROR
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Get current number of URLs
        number_of_urls_in_db = Urls.query.count()

        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Try to add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: str(invalid_url),
        URL_FORM.URL_TITLE: "This is an invalid URL",
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to),
        data=add_url_form,
        content_type="application/x-www-form-urlencoded",
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_url_json_response[STD_JSON.MESSAGE]
        == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    ), f"Failed with url={invalid_url}"
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.INVALID_URL_ERROR
    )

    with app.app_context():
        # Ensure no new URL created
        assert Urls.query.count() == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utubs.query.get(utub_id_to_add_to)

        # Ensure no URL now in UTub
        assert len(current_utub_member_of.utub_urls) == 0

        # Ensure Url-Utubs-User association does not exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_to_add_to,
                Utub_Urls.user_id == current_user.id,
            ).count()
            == 0
        )

        assert Utub_Urls.query.count() == initial_utub_urls


@pytest.mark.parametrize(
    "invalid_url",
    [invalid_url for invalid_url in INVALID_URLS_TO_VALIDATE if "@" not in invalid_url],
)
def test_add_invalid_urls(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
    invalid_url,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a nonexistant URL to a UTub they are a creator of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_ADD_URL,
        STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_URL_ERROR
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a creator of
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get current number of URLs
        number_of_urls_in_db = Urls.query.count()

        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Try to add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: str(invalid_url),
        URL_FORM.URL_TITLE: "This is an invalid URL",
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_url_json_response[STD_JSON.MESSAGE]
        == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    ), f"Failed with url={invalid_url}"
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.INVALID_URL_ERROR
    )

    with app.app_context():
        # Ensure no new URL created
        assert Urls.query.count() == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utubs.query.get(utub_id_to_add_to)

        # Ensure no URL now in UTub
        assert len(current_utub_member_of.utub_urls) == 0

        # Ensure Url-Utubs-User association does not exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_to_add_to,
                Utub_Urls.user_id == current_user.id,
            ).count()
            == 0
        )

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_invalid_url_with_credential_as_utub_member(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with crendentials to a UTub they are a member of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION,
        STD_JSON.ERROR_CODE: URLErrorCode.URL_WITH_CREDENTIALS_ERROR
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Get current number of URLs
        number_of_urls_in_db = Urls.query.count()

        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Try to add the URL to the UTub
    invalid_url = "https://user:password@example.com"
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: invalid_url,
        URL_FORM.URL_TITLE: "This is an invalid URL with credentials",
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to),
        data=add_url_form,
        content_type="application/x-www-form-urlencoded",
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_url_json_response[STD_JSON.MESSAGE]
        == URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION
    ), f"Failed with url={invalid_url}"
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_WITH_CREDENTIALS_ERROR
    )

    with app.app_context():
        # Ensure no new URL created
        assert Urls.query.count() == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utubs.query.get(utub_id_to_add_to)

        # Ensure no URL now in UTub
        assert len(current_utub_member_of.utub_urls) == 0

        # Ensure Url-Utubs-User association does not exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_to_add_to,
                Utub_Urls.user_id == current_user.id,
            ).count()
            == 0
        )

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_invalid_url_as_utub_creator(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with crendentials to a UTub they are a creator of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response
        is sent by the server, and that no new new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION,
        STD_JSON.ERROR_CODE: URLErrorCode.URL_WITH_CREDENTIALS_ERROR
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a creator of
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get current number of URLs
        number_of_urls_in_db = Urls.query.count()

        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Try to add the URL to the UTub
    invalid_url = "https://user:password@example.com"
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: invalid_url,
        URL_FORM.URL_TITLE: "This is an invalid URL",
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_url_json_response[STD_JSON.MESSAGE]
        == URL_FAILURE.URLS_WITH_CREDENTIALS_EXCEPTION
    ), f"Failed with url={invalid_url}"
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_WITH_CREDENTIALS_ERROR
    )

    with app.app_context():
        # Ensure no new URL created
        assert Urls.query.count() == number_of_urls_in_db

        # Get the UTub again
        current_utub_member_of = Utubs.query.get(utub_id_to_add_to)

        # Ensure no URL now in UTub
        assert len(current_utub_member_of.utub_urls) == 0

        # Ensure Url-Utubs-User association does not exist
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_to_add_to,
                Utub_Urls.user_id == current_user.id,
            ).count()
            == 0
        )

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_valid_url_to_nonexistent_utub(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a nonexistent UTub
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 404 HTTP status code
    """
    NONEXISTENT_UTUB_ID = 999
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a valid URL
        valid_url_to_add: Urls = Urls.query.first()
        valid_url_string = valid_url_to_add.url_string
        valid_url_title = f"This is {valid_url_string}"

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url_string,
        URL_FORM.URL_TITLE: valid_url_title,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=NONEXISTENT_UTUB_ID), data=add_url_form
    )

    assert add_url_response.status_code == 404

    with app.app_context():
        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_valid_url_to_utub_not_a_member_of(
    add_urls_to_database, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creators in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a UTub the user is not a part of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 403 HTTP status code, the server sends back the proper
        JSON response, and no new Url-UTub-User associations are added

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_ADD_URL,
        STD_JSON.ERROR_CODE: 1
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is not a member of
        utub_member_of_utub_user_not_member_of: Utub_Members = (
            Utub_Members.query.filter(Utub_Members.user_id != current_user.id).first()
        )

        id_of_utub_not_member_of = utub_member_of_utub_user_not_member_of.utub_id

        # Get a valid URL
        valid_url_to_add: Urls = Urls.query.first()
        valid_url_string = valid_url_to_add.url_string
        valid_url_title = f"This is {valid_url_string}"

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url_string,
        URL_FORM.URL_TITLE: valid_url_title,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=id_of_utub_not_member_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 404

    with app.app_context():
        utub_not_member_of: Utubs = Utubs.query.get(id_of_utub_not_member_of)

        # Ensure URL not in UTub currently
        assert len(utub_not_member_of.utub_urls) == 0
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_not_member_of
            ).count()
            == 0
        )

        assert Utub_Urls.query.count() == initial_utub_urls


@pytest.mark.parametrize(
    "validated_url,input_url",
    [
        (validated_url, input_url)
        for (validated_url, input_url) in FLATTENED_NORMALIZED_AND_INPUT_VALID_URLS
    ],
)
def test_add_fresh_url_to_utub(
    every_user_makes_a_unique_utub,
    login_first_user_without_register,
    validated_url,
    input_url,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and no URLs
        currently in the database or associated with the UTubs
    WHEN the user tries to add a fresh and valid URL to a UTub they are a creator of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Url_UTub-User association exists, and that a new URL entity is created

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "New URL created and added to UTub",
        MODEL_STRS.URL : {
            URL_FORM.URL_STRING: String representing the URL,
            URL_SUCCESS.UTUB_URL_ID : Integer representing the URL ID
        },
        URL_SUCCESS.UTUB_ID : Integer representing the ID of the UTub added to,
        URL_SUCCESS.ADDED_BY : Integer representing the ID of current user who added this URL to this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub_that_is_creator_of = utub_creator_of.id

        initial_num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of
        ).count()

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()
        initial_urls = Urls.query.count()

    url_title_to_add = f"This is {validated_url}"

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: input_url,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=id_of_utub_that_is_creator_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 200

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_CREATED_ADDED
    assert (
        int(add_url_json_response[URL_SUCCESS.UTUB_ID]) == id_of_utub_that_is_creator_of
    )
    assert int(add_url_json_response[URL_SUCCESS.ADDED_BY]) == current_user.id

    url_id_added = int(add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.UTUB_URL_ID])
    assert (
        add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.URL_STRING]
        == ada_url.URL(validated_url).href
    )

    with app.app_context():
        # Ensure new URL exists
        assert Urls.query.count() == initial_urls + 1
        assert (
            Urls.query.filter(
                Urls.url_string == ada_url.URL(validated_url).href
            ).count()
            == 1
        )
        assert (
            Urls.query.get(url_id_added).url_string == ada_url.URL(validated_url).href
        )

        # Ensure URL now in UTub
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
                Utub_Urls.url_id == url_id_added,
            ).count()
            == initial_num_of_urls_in_utub + 1
        )

        urls_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).all()

        # Ensure title updated
        assert urls_in_utub[0].url_title == url_title_to_add

        assert Utub_Urls.query.count() == initial_utub_urls + 1


@pytest.mark.parametrize(
    "lowercase_url,valid_url",
    [
        (lowercase_url, valid_url)
        for (lowercase_url, valid_url) in FLATTENED_URLS_WITH_DIFFERENT_PATH
    ],
)
def test_add_fresh_urls_with_diff_paths_to_utub(
    every_user_makes_a_unique_utub,
    login_first_user_without_register,
    lowercase_url,
    valid_url,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and no URLs
        currently in the database or associated with the UTubs
    WHEN the user tries to add a fresh and valid URL to a UTub they are a creator of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Url_UTub-User association exists, and that a new URL entity is created

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "New URL created and added to UTub",
        MODEL_STRS.URL : {
            URL_FORM.URL_STRING: String representing the URL,
            URL_SUCCESS.UTUB_URL_ID : Integer representing the URL ID
        },
        URL_SUCCESS.UTUB_ID : Integer representing the ID of the UTub added to,
        URL_SUCCESS.ADDED_BY : Integer representing the ID of current user who added this URL to this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub_that_is_creator_of = utub_creator_of.id

        initial_num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of
        ).count()

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()
        initial_urls = Urls.query.count()

    url_title_to_add = f"This is {valid_url}"

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=id_of_utub_that_is_creator_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 200

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_CREATED_ADDED
    assert (
        int(add_url_json_response[URL_SUCCESS.UTUB_ID]) == id_of_utub_that_is_creator_of
    )
    assert int(add_url_json_response[URL_SUCCESS.ADDED_BY]) == current_user.id

    url_id_added = int(add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.UTUB_URL_ID])
    assert (
        add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.URL_STRING]
        == ada_url.URL(valid_url).href
    )
    assert (
        add_url_json_response[MODEL_STRS.URL][URL_SUCCESS.URL_STRING] != lowercase_url
    )

    with app.app_context():
        # Ensure new URL exists
        assert Urls.query.count() == initial_urls + 1
        assert (
            Urls.query.filter(Urls.url_string == ada_url.URL(valid_url).href).count()
            == 1
        )
        assert Urls.query.get(url_id_added).url_string == ada_url.URL(valid_url).href

        # Ensure URL now in UTub
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
                Utub_Urls.url_id == url_id_added,
            ).count()
            == initial_num_of_urls_in_utub + 1
        )

        urls_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).all()

        # Ensure title updated
        assert urls_in_utub[0].url_title == url_title_to_add

        assert Utub_Urls.query.count() == initial_utub_urls + 1


def test_add_duplicate_url_to_utub_as_same_user_who_added_url(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        currently in the database, with all UTubs containing all URLs
    WHEN the user tries to add a URL to a UTub that they already added the URL to, as the creator of the UTub
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 409 HTTP status code, that the proper JSON response
        is sent by the server, and that no new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "URL already in UTub",
        STD_JSON.ERROR_CODE: URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR,
        URLS_FAILURE.URL_STRING : "https://www.google.com",
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub_that_is_creator_of = utub_creator_of.id

        # Find the first URL in this UTub that this user added
        url_association_that_user_added: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()

        url_that_user_added: Urls = url_association_that_user_added.standalone_url
        url_id = url_that_user_added.id
        url_string_to_add = url_that_user_added.url_string
        url_title_to_add = url_association_that_user_added.url_title

        number_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of
        ).count()
        number_of_urls_in_db = Urls.query.count()

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=id_of_utub_that_is_creator_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 409

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
    )
    assert add_url_json_response[URL_FAILURE.URL_STRING] == url_string_to_add

    with app.app_context():
        # Ensure same number of URLs in UTub as before
        utub_to_check: Utubs = Utubs.query.get(id_of_utub_that_is_creator_of)
        assert len(utub_to_check.utub_urls) == number_of_urls_in_utub

        # Ensure Url-UTub-UAser association still contains only the one associatisn
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
                Utub_Urls.user_id == current_user.id,
                Utub_Urls.url_id == url_id,
            ).count()
            == 1
        )

        # Ensure same number of URLs as before
        assert Urls.query.count() == number_of_urls_in_db

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_duplicate_url_to_utub_as_creator_of_utub_not_url_adder(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        currently in the database, with all UTubs containing all URLs
    WHEN the user tries to add a URL to a UTub that someone else added, as the creator of the UTub
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 409 HTTP status code, that the proper JSON response
        is sent by the server, and that no new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "URL already in UTub",
        STD_JSON.ERROR_CODE: URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
        URLS_FAILURE.URL_STRING : "https://www.google.com",
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub_that_is_creator_of = utub_creator_of.id

        # Find the first URL in this UTub that this user added
        url_association_that_user_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
            Utub_Urls.user_id != current_user.id,
        ).first()

        url_that_user_did_not_add: Urls = (
            url_association_that_user_did_not_add.standalone_url
        )
        url_id = url_that_user_did_not_add.id
        url_string_to_add = url_that_user_did_not_add.url_string
        url_title_to_add = url_association_that_user_did_not_add.url_title

        number_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_creator_of
        ).count()

        number_of_urls_in_db = Urls.query.count()

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=id_of_utub_that_is_creator_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 409

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
    )
    assert add_url_json_response[URL_FAILURE.URL_STRING] == url_string_to_add

    with app.app_context():
        # Ensure same number of URLs in UTub as before
        utub_to_check: Utubs = Utubs.query.get(id_of_utub_that_is_creator_of)
        assert len(utub_to_check.utub_urls) == number_of_urls_in_utub

        # Ensure Url-UTub-UAser association still contains only the one associatisn
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_that_is_creator_of,
                Utub_Urls.url_id == url_id,
            ).count()
            == 1
        )

        # Ensure same number of URLs as before
        assert Urls.query.count() == number_of_urls_in_db

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_duplicate_url_to_utub_as_member_of_utub_not_url_adder(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        currently in the database, with all UTubs containing all URLs
    WHEN the user tries to add a URL to a UTub that someone else added, as the member of the UTub
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 409 HTTP status code, that the proper JSON response
        is sent by the server, and that no new Url_UTub-User association exists

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.URL_IN_UTUB,
        STD_JSON.ERROR_CODE: URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
        URL_FAILURE.URL_STRING : URL_FAILURE.URL_IN_UTUB,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub_that_is_member_of = utub_member_of.id

        # Find the first URL in this UTub that this user added
        url_association_that_user_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()

        url_that_user_did_not_add: Urls = (
            url_association_that_user_did_not_add.standalone_url
        )
        url_id = url_that_user_did_not_add.id
        url_string_to_add = url_that_user_did_not_add.url_string
        url_title_to_add = url_association_that_user_did_not_add.url_title

        number_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_member_of
        ).count()

        number_of_urls_in_db = Urls.query.count()

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=id_of_utub_that_is_member_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 409

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.URL_IN_UTUB
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.URL_ALREADY_IN_UTUB_ERROR
    )
    assert add_url_json_response[URL_FAILURE.URL_STRING] == url_string_to_add

    with app.app_context():
        # Ensure same number of URLs in UTub as before
        utub_to_check: Utubs = Utubs.query.get(id_of_utub_that_is_member_of)
        assert len(utub_to_check.utub_urls) == number_of_urls_in_utub

        # Ensure Url-UTub-UAser association still contains only the one associatisn
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == id_of_utub_that_is_member_of,
                Utub_Urls.url_id == url_id,
            ).count()
            == 1
        )

        # Ensure same number of URLs as before
        assert Urls.query.count() == number_of_urls_in_db

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_url_missing_url(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with an empty 'url_string' field in the form
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 404 HTTP status code, and that the proper JSON response
        is sent by the server

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: "Unable to add this URL, please check inputs",
        STD_JSON.ERROR_CODE: 4,
        "Errors": {
            URL_FORM.URL_STRING: ["This field is required."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Ensure no URLs in this UTub
        num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_utub_member_of.id
        ).count()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        url_title_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: "",
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_ADD_URL_FORM
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.INVALID_FORM_INPUT
    )
    assert (
        add_url_json_response[STD_JSON.ERRORS][URL_FORM.URL_STRING]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        assert (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_add_to).count()
            == num_of_urls_in_utub
        )

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_url_missing_url_title(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with an empty 'url_title' field in the form
    THEN ensure that the server responds with a 400 HTTP status code, and that the proper JSON response
        is sent by the server

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
        STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_FORM_INPUT,
        STD_JSON.ERRORS: {
            URL_FORM.URL_TITLE: ["This field is required."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Ensure no URLs in this UTub
        initial_num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_utub_member_of.id
        ).count()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: "",
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_ADD_URL_FORM
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.INVALID_FORM_INPUT
    )
    assert (
        add_url_json_response[STD_JSON.ERRORS][URL_FORM.URL_TITLE]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        assert (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_add_to).count()
            == initial_num_of_urls_in_utub
        )

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_url_fully_sanitized_url_title(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with an 'url_title' field that is sanitized by the backend
    THEN ensure that the server responds with a 400 HTTP status code, and that the proper JSON response
        is sent by the server

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
        STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_FORM_INPUT,
        STD_JSON.ERRORS: {
            URL_FORM.URL_TITLE: ["Invalid input, please try again."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        utub_id_to_add_to = current_utub_member_of.id

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: '<img src="evl.jpg">',
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400

    add_url_json_response = add_url_response.json
    assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_url_json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_ADD_URL_FORM
    assert (
        int(add_url_json_response[STD_JSON.ERROR_CODE])
        == URLErrorCodes.INVALID_FORM_INPUT
    )
    assert add_url_json_response[STD_JSON.ERRORS][URL_FORM.URL_TITLE] == [
        URL_FAILURE.INVALID_INPUT
    ]


def test_add_url_partially_sanitized_url_title(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with an 'url_title' field that is sanitized by the backend
    THEN ensure that the server responds with a 400 HTTP status code, and that the proper JSON response
        is sent by the server

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
        STD_JSON.ERROR_CODE: URLErrorCodes.INVALID_FORM_INPUT,
        STD_JSON.ERRORS: {
            URL_FORM.URL_TITLE: ["Invalid input, please try again."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        utub_id_to_add_to = current_utub_member_of.id

    for url_title in (
        "<<HELLO>>",
        "<h1>Hello</h1>",
    ):
        # Add the URL to the UTub
        add_url_form = {
            URL_FORM.CSRF_TOKEN: csrf_token,
            URL_FORM.URL_STRING: url_string_to_add,
            URL_FORM.URL_TITLE: url_title,
        }

        add_url_response = client.post(
            url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to),
            data=add_url_form,
        )

        assert add_url_response.status_code == 400

        add_url_json_response = add_url_response.json
        assert add_url_json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
        assert (
            add_url_json_response[STD_JSON.MESSAGE]
            == URL_FAILURE.UNABLE_TO_ADD_URL_FORM
        )
        assert (
            int(add_url_json_response[STD_JSON.ERROR_CODE])
            == URLErrorCodes.INVALID_FORM_INPUT
        )
        assert add_url_json_response[STD_JSON.ERRORS][URL_FORM.URL_TITLE] == [
            URL_FAILURE.INVALID_INPUT
        ]


def test_add_url_missing_csrf_token(
    add_urls_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a URL with an empty 'url_title' field in the form
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 404 HTTP status code, and that the proper JSON response
        is sent by the server

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL_FORM,
        STD_JSON.ERROR_CODE: 4,
        STD_JSON.ERRORS: {
            URL_FORM.URL_TITLE: ["This field is required."]
        }
    }
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Ensure no URLs in this UTub
        initial_num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_utub_member_of.id
        ).count()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        utub_id_to_add_to = current_utub_member_of.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: "",
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    # Assert invalid response code
    assert add_url_response.status_code == 403
    assert add_url_response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in add_url_response.data

    with app.app_context():
        assert (
            Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_to_add_to).count()
            == initial_num_of_urls_in_utub
        )

        assert Utub_Urls.query.count() == initial_utub_urls


def test_add_valid_url_updates_utub_last_updated(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a UTub they are a part of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code, and the UTub's
        last updated field is updated
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        initial_last_updated = current_utub_member_of.last_updated

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        url_title_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 200

    with app.app_context():
        # Get the UTub again
        current_utub_member_of: Utubs = Utubs.query.get(utub_id_to_add_to)

        assert (
            current_utub_member_of.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_add_duplicate_url_to_utub_does_not_update_utub_last_updated(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        currently in the database, with all UTubs containing all URLs
    WHEN the user tries to add a URL to a UTub that someone else added, as the member of the UTub
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 409 HTTP status code, and the last updated field
         of the UTub is not modified
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get this user's UTub
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub_that_is_member_of = utub_member_of.id

        initial_last_updated = utub_member_of.last_updated

        # Ensure user is member of this UTub
        assert current_user in [user.to_user for user in utub_member_of.members]

        # Find the first URL in this UTub that this user added
        url_association_that_user_did_not_add: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_that_is_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()

        url_that_user_did_not_add: Urls = (
            url_association_that_user_did_not_add.standalone_url
        )
        url_string_to_add = url_that_user_did_not_add.url_string
        url_title_to_add = url_association_that_user_did_not_add.url_title

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=id_of_utub_that_is_member_of),
        data=add_url_form,
    )

    assert add_url_response.status_code == 409

    with app.app_context():
        utub_to_check: Utubs = Utubs.query.get(id_of_utub_that_is_member_of)
        assert initial_last_updated == utub_to_check.last_updated


def test_add_valid_existing_url_log(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a (previously generated) URL to a UTub they are a part of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code and the logs are valid
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        url_title_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 200
    assert is_string_in_logs(
        f"Finished checks for url_string='{url_string_to_add}'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)
    assert is_string_in_logs(
        f"URL already exists in U4I, URL.id={url_to_add.id}", caplog.records
    )
    assert is_string_in_logs("Added URL to UTub", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_id_to_add_to}", caplog.records)
    assert is_string_in_logs(f"URL.id={url_to_add.id}", caplog.records)


def test_add_valid_fresh_url_log(
    every_user_in_every_utub,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a fresh URL to a UTub they are a part of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 200 HTTP status code and the logs are valid
    """
    client, csrf_token, _, app = login_first_user_without_register
    valid_url_to_add = valid_url_strings[0]

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_title_to_add = f"This is {valid_url_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 200
    assert is_string_in_logs(
        f"Finished checks for url_string='{valid_url_to_add}'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)
    assert is_string_in_logs("Added URL to UTub", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_id_to_add_to}", caplog.records)

    with app.app_context():
        new_url = Urls.query.filter(Urls.url_string == valid_url_to_add).first()
        assert is_string_in_logs(f"Added new URL, URL.id={new_url.id}", caplog.records)
        assert is_string_in_logs(f"URL.id={new_url.id}", caplog.records)


@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_add_invalid_url_log(
    mock_validate_url,
    every_user_in_every_utub,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a fresh URL to a UTub they are a part of but URL is invalid
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code and the logs are valid
    """
    client, csrf_token, user, app = login_first_user_without_register
    valid_url_to_add = valid_url_strings[0]

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_title_to_add = f"This is {valid_url_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    mock_validate_url.side_effect = InvalidURLError
    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400
    assert is_string_in_logs(
        f"Unable to validate the URL given by User={user.id}", caplog.records
    )
    assert is_string_in_logs_regex(
        r"(.*)[\s](.*)Took (\d).(\d+) ms to fail validation[\s](.*)[\s](.*)",
        caplog.records,
    )
    assert is_string_in_logs(f"url_string={valid_url_to_add}", caplog.records)


@mock.patch("src.extensions.notifications.notifications.threading.Thread")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_add_url_unknown_exception_log(
    mock_validate_url,
    mock_thread,
    every_user_in_every_utub,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a fresh URL to a UTub they are a part of but an unknown exception is raised
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code and the logs are valid
    """
    mock_thread_response = mock.MagicMock()
    mock_thread_response.start.return_value = None
    mock_thread.return_value = mock_thread_response

    client, csrf_token, user, app = login_first_user_without_register
    valid_url_to_add = valid_url_strings[0]

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_title_to_add = f"This is {valid_url_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: valid_url_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    mock_validate_url.side_effect = Exception("Unknown exception")
    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400
    assert is_string_in_logs(
        f"Unexpected exception validating the URL given by User={user.id}",
        caplog.records,
    )
    assert is_string_in_logs_regex(
        r"(.*)[\s](.*)Took (\d).(\d+) ms to fail validation[\s](.*)[\s](.*)",
        caplog.records,
    )
    assert is_string_in_logs(f"url_string={valid_url_to_add}", caplog.records)
    assert is_string_in_logs("Exception=Unknown exception", caplog.records)


def test_add_url_already_in_utub_log(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database and all URLs added to each UTub
    WHEN the user tries to add a previously added URL to a UTub they are a part of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 409 HTTP status code and the logs are valid
    """
    client, csrf_token, user, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        url_title_to_add = f"This is {url_string_to_add}"
        utub_id_to_add_to = current_utub_member_of.id

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
        URL_FORM.URL_TITLE: url_title_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 409
    assert is_string_in_logs(
        f"Finished checks for url_string='{url_string_to_add}'", caplog.records
    )
    assert is_string_in_logs_regex(r"(.*)Took (\d).(\d+) ms(.*)", caplog.records)
    assert is_string_in_logs(
        f"URL already exists in U4I, URL.id={url_to_add.id}", caplog.records
    )
    assert is_string_in_logs(
        f"User={user.id} tried adding URL.id={url_to_add.id} but already exists in UTub.id={utub_id_to_add_to}",
        caplog.records,
    )


def test_add_url_invalid_form_log(
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database and all URLs added to each UTub
    WHEN the user tries to add a previously added URL to a UTub they are a part of with missing form data
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code and the logs are valid
    """
    client, csrf_token, user, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Grab a URL to add
        url_to_add: Urls = Urls.query.first()
        url_string_to_add = url_to_add.url_string
        utub_id_to_add_to = current_utub_member_of.id

    # Add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: url_string_to_add,
    }

    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    assert add_url_response.status_code == 400
    assert is_string_in_logs(f"User={user.id}", caplog.records)
    assert is_string_in_logs(
        f"Invalid form: url_title={URL_FAILURE.FIELD_REQUIRED}", caplog.records
    )


@mock.patch("src.extensions.notifications.notifications.requests.post")
@mock.patch("src.extensions.url_validation.url_validator.UrlValidator.validate_url")
def test_add_invalid_url_sends_notification(
    mock_validate_url,
    mock_request_post,
    add_urls_to_database,
    every_user_in_every_utub,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all users in each UTub, a valid user currently logged in, and 3 URLs
        added to the database but not associated with any UTubs
    WHEN the user tries to add a invalid URL to a UTub they are a part of
        - By POST to "/utubs/<int:utub_id>/urls" where "utub_id" is an integer representing UTub ID
    THEN ensure that the server responds with a 400 HTTP status code and a notification is sent
    """
    notification_sent = threading.Event()

    def mock_post_with_event(*args, **kwargs):
        mock_response = type("MockResponse", (), {"status_code": 200})()
        notification_sent.set()  # Signal that the request was made
        return mock_response

    mock_request_post.side_effect = mock_post_with_event
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find a UTub this current user is a member of (and not creator of)
        current_utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_to_add_to = current_utub_member_of.id

    # Try to add the URL to the UTub
    add_url_form = {
        URL_FORM.CSRF_TOKEN: csrf_token,
        URL_FORM.URL_STRING: "AAAA",
        URL_FORM.URL_TITLE: "This is AAAA",
    }

    mock_validate_url.side_effect = Exception("Unknown exception")
    add_url_response = client.post(
        url_for(ROUTES.URLS.CREATE_URL, utub_id=utub_id_to_add_to), data=add_url_form
    )

    # Wait for notification to be sent (with timeout)
    assert notification_sent.wait(
        timeout=5.0
    ), "Notification was not sent within timeout"

    assert add_url_response.status_code == 400

    mock_request_post.assert_called_once()
