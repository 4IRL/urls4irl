from flask import url_for
from flask_login import current_user
import pytest

from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS
from src.utils.strings.url_validation_strs import URL_VALIDATION
from tests.utils_for_test import is_string_in_logs

pytestmark = pytest.mark.urls


def test_get_url_in_utub(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get the URL via a GET to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the URL is retrieved from the database correctly,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_FOUND_IN_UTUB,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            "utubUrlID": ID of URL that was modified,
            "urlString": The URL that was newly modified,
            "urlTags": An array of tag objects associated with this URL
        }
    }
    """

    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Get the UTub this user is member of
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in the UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_id_in_utub = url_in_utub.id
        url_title_in_utub = url_in_utub.url_title
        url_string_in_utub = url_in_utub.standalone_url.url_string

        # Get all tags on this URL in this UTub
        tags_on_url_in_utub: list[Utub_Url_Tags] = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_creator_of.id
        ).all()
        tag_objects_on_url_in_utub = sorted(
            [
                {
                    MODEL_STRS.UTUB_TAG_ID: tag.utub_tag_item.id,
                    MODEL_STRS.TAG_STRING: tag.utub_tag_item.tag_string,
                }
                for tag in tags_on_url_in_utub
            ],
            key=lambda x: x[MODEL_STRS.UTUB_TAG_ID],
        )

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_id_in_utub,
        ),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert get_url_response.status_code == 200
    get_url_response_json = get_url_response.json

    assert get_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert get_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_FOUND_IN_UTUB

    url_object = get_url_response_json[URL_SUCCESS.URL]
    assert url_object[URL_SUCCESS.URL_STRING] == url_string_in_utub
    assert url_object[URL_SUCCESS.URL_TITLE] == url_title_in_utub
    assert url_object[URL_SUCCESS.UTUB_URL_ID] == url_id_in_utub

    sorted_tag_objects_response = sorted(
        [tag for tag in url_object[URL_SUCCESS.URL_TAGS]],
        key=lambda x: x[MODEL_STRS.UTUB_TAG_ID],
    )
    assert sorted_tag_objects_response == tag_objects_on_url_in_utub


def test_get_url_in_utub_as_not_member(
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has no other members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get a URL of a UTub they aren't a member of via a GET to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the server sends back a 403 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_RETRIEVE_URL,
    }
    """

    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Get the UTub this user is member of
        utub_not_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        url_of_utub_not_member_of: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_not_member_of.id
        ).first()
        url_id_of_utub_not_member_of = url_of_utub_not_member_of.id

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=utub_not_member_of.id,
            utub_url_id=url_id_of_utub_not_member_of,
        ),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert get_url_response.status_code == 403
    get_url_response_json = get_url_response.json

    assert get_url_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert get_url_response_json[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_RETRIEVE_URL


def test_get_nonexistent_url_in_utub(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get a nonexistent URL via a GET to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_RETRIEVE_URL,
    }
    """

    client, _, _, app = login_first_user_without_register

    NONEXISTENT_URL_ID = 999
    with app.app_context():
        # Get the UTub this user is member of
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=NONEXISTENT_URL_ID,
        ),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert get_url_response.status_code == 404
    get_url_response_json = get_url_response.json

    assert get_url_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert get_url_response_json[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_RETRIEVE_URL


def test_get_url_in_nonexistent_utub(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get a nonexistent URL via a GET to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the server sends back a 404 HTTP status code, and the server sends back the 404 page
    """

    client, _, _, app = login_first_user_without_register

    NONEXISTENT_UTUB_ID = 999
    with app.app_context():
        # Get the UTub this user is member of
        valid_url_in_utub = Utub_Urls.query.first()

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=NONEXISTENT_UTUB_ID,
            utub_url_id=valid_url_in_utub.id,
        ),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert get_url_response.status_code == 404
    assert IDENTIFIERS.HTML_404.encode() in get_url_response.data


def test_get_url_in_utub_non_ajax_request(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get a nonexistent URL via a GET to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the server sends back a 404 HTTP status code, and the server sends back the 404 page
    """

    client, _, _, app = login_first_user_without_register

    UTUB_ID = 1
    with app.app_context():
        # Get the UTub this user is member of
        valid_url_in_utub = Utub_Urls.query.first()

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=UTUB_ID,
            utub_url_id=valid_url_in_utub.id,
        ),
    )

    assert get_url_response.status_code == 404
    assert IDENTIFIERS.HTML_404.encode() in get_url_response.data


def test_get_url_in_utub_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get the URL via a GET to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the URL is retrieved from the database correctly,
        the server sends back a 200 HTTP status code, and the logs are valid
    """

    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Get the UTub this user is member of
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in the UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_id_in_utub = url_in_utub.id

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_id_in_utub,
        ),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert get_url_response.status_code == 200
    assert is_string_in_logs("Retrieved URL", caplog.records)
    assert is_string_in_logs(f"UTub.id={utub_creator_of.id}", caplog.records)
    assert is_string_in_logs(f"UTubURL.id={url_id_in_utub}", caplog.records)


def test_get_nonexistent_url_in_utub_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get a nonexistent URL via a GET to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the server sends back a 404 HTTP status code, and the logs are valid
    """

    client, _, user, app = login_first_user_without_register
    url_id_in_utub = 99999

    with app.app_context():
        # Get the UTub this user is member of
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_id_in_utub,
        ),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert get_url_response.status_code == 404
    assert is_string_in_logs(
        f"User={user.id} tried to retrieve nonexistent UTubURL.id={url_id_in_utub}",
        caplog.records,
    )


def test_get_url_in_utub_not_member_of_log(
    every_user_makes_a_unique_utub,
    add_one_url_to_each_utub_no_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get a URL in UTub they are not in via a GET to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the server sends back a 403 HTTP status code, and the logs are valid
    """

    client, _, user, app = login_first_user_without_register

    with app.app_context():
        # Get the UTub this user is member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Get the URL in the UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id
        ).first()
        url_id_in_utub = url_in_utub.id

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=utub_member_of.id,
            utub_url_id=url_id_in_utub,
        ),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert get_url_response.status_code == 403
    assert is_string_in_logs(
        f"User={user.id} tried to get UTubURL.id={url_id_in_utub} but not in UTub.id={utub_member_of.id}",
        caplog.records,
    )


def test_get_url_not_ajax_log(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
    caplog,
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to get a URL in UTub via a GET but not an XMLHTTPRequest to
        "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN verify that the server sends back a 404 HTTP status code, and the logs are valid
    """

    client, _, user, app = login_first_user_without_register

    with app.app_context():
        # Get the UTub this user is member of
        utub_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Get the URL in the UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_creator_of.id
        ).first()
        url_id_in_utub = url_in_utub.id

    get_url_response = client.get(
        url_for(
            ROUTES.URLS.GET_URL,
            utub_id=utub_creator_of.id,
            utub_url_id=url_id_in_utub,
        ),
    )

    assert get_url_response.status_code == 404
    assert is_string_in_logs(
        f"User={user.id} did not make an AJAX request", caplog.records
    )
