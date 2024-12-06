from flask import url_for
from flask_login import current_user
import pytest

from src.models.urls import Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import URL_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS

pytestmark = pytest.mark.urls


def test_delete_url_as_utub_creator_no_tags(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is removed from the database,
        and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
        URL_SUCCESS.UTUB_ID : Integer representing the UTub ID where the URL was removed from,
        URL_SUCCESS.URL : Serialized information of the URL that was removed, as follows:
        {
            "utubUrlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAG_IDS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        url_utub_user_association: Utub_Urls = current_user_utub.utub_urls[0]
        url_id_to_remove = url_utub_user_association.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()
        url_object: Urls = url_utub_user_association.standalone_url

    # Remove URL from UTub as UTub creator
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub.id,
            utub_url_id=url_id_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json
    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert delete_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert int(delete_url_response_json[URL_SUCCESS.UTUB_ID]) == current_user_utub.id
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.UTUB_URL_ID]
        == url_id_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_object.url_string
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_utub_user_association.url_title
    )

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_object.id) is not None

        # Assert the URL-USER-UTUB association is deleted
        assert Utub_Urls.query.get(url_id_to_remove) is None

        # Ensure UTub has no URLs left
        current_user_utub = Utubs.query.get(current_user_utub.id)
        assert len(current_user_utub.utub_urls) == 0

        assert Utub_Urls.query.count() == initial_utub_urls - 1


def test_delete_url_as_utub_member_no_tags(
    add_all_urls_and_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in member of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is removed from the database,
        and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
        URL_SUCCESS.UTUB_ID : Integer representing the UTub ID where the URL was removed from,
        URL_SUCCESS.URL : Serialized information of the URL that was removed, as follows:
        {
            "utubUrlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAG_IDS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get URL that this user did not add to a UTub
        current_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id == current_user.id
        ).first()

        current_user_utub_id = current_url_in_utub.utub_id
        current_num_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_user_utub_id
        ).count()

        url_object: Urls = current_url_in_utub.standalone_url
        url_object_id = url_object.id
        current_url_string = url_object.url_string
        current_url_title = current_url_in_utub.url_title

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Remove URL from UTub as UTub member
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub_id,
            utub_url_id=current_url_in_utub.id,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json

    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert delete_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert int(delete_url_response_json[URL_SUCCESS.UTUB_ID]) == current_user_utub_id
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.UTUB_URL_ID]
        == current_url_in_utub.id
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == current_url_string
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == current_url_title
    )

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_object_id) is not None

        # Assert the URL-UTUB association is deleted
        assert Utub_Urls.query.get(current_url_in_utub.id) is None

        # Ensure UTub has decremented URLs
        current_user_utub = Utubs.query.get(current_user_utub_id)
        assert len(current_user_utub.utub_urls) == current_num_urls_in_utub - 1

        assert Utub_Urls.query.count() == initial_utub_urls - 1


def test_delete_url_from_utub_not_member_of(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in member of a UTub, with two other UTub the user is not a part of that also contains URLs
    WHEN the user wishes to remove the URL from another UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 403 HTTP status code, the UTub-User-URL association is not removed from the database,
        and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_DELETE_URL
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub the logged in user is not a creator of
    with app.app_context():
        utub_current_user_not_part_of = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_num_of_urls_in_utub = len(utub_current_user_not_part_of.utub_urls)

        # Get the URL to remove
        url_to_remove_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_current_user_not_part_of.id
        ).first()

        url_to_remove_id = url_to_remove_in_utub.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Remove the URL from the other user's UTub while logged in as member of another UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_current_user_not_part_of.id,
            utub_url_id=url_to_remove_id,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 403

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json
    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        delete_url_response_json[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_DELETE_URL
    )

    # Ensure database is not affected
    with app.app_context():
        utub_in_url: Utub_Urls = Utub_Urls.query.get(url_to_remove_id)
        assert (
            utub_in_url is not None
            and utub_in_url.utub_id == utub_current_user_not_part_of.id
        )
        assert Utub_Urls.query.count() == initial_utub_urls

        utub_current_user_not_part_of: Utubs = Utubs.query.get(
            utub_current_user_not_part_of.id
        )
        assert current_num_of_urls_in_utub == len(
            utub_current_user_not_part_of.utub_urls
        )


def test_remove_invalid_nonexistant_url_as_utub_creator(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub
    WHEN the user wishes to remove a nonexistant URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code, and the database has no changes
    """
    NONEXISTENT_URL_IN_UTUB_ID = 999

    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub this logged in user is a creator of
    with app.app_context():
        utub_current_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub_current_user_creator_of = utub_current_user_creator_of.id

        # Ensure not in UTub and nonexistant
        assert Utub_Urls.query.get(NONEXISTENT_URL_IN_UTUB_ID) is None

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=id_of_utub_current_user_creator_of,
            utub_url_id=NONEXISTENT_URL_IN_UTUB_ID,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 404

    with app.app_context():
        # Ensure not in UTub and nonexistant
        assert Utub_Urls.query.get(NONEXISTENT_URL_IN_UTUB_ID) is None
        assert Utub_Urls.query.count() == initial_utub_urls


def test_remove_invalid_nonexistant_url_as_utub_member(
    add_one_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub
    WHEN the user wishes to remove a nonexistant URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code, and the database has no changes
    """
    NONEXISTENT_URL_IN_UTUB_ID = 999
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_current_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub_current_user_member_of = utub_current_user_member_of.id

        # Ensure not in UTub and nonexistant
        assert Utub_Urls.query.get(NONEXISTENT_URL_IN_UTUB_ID) is None

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=id_of_utub_current_user_member_of,
            utub_url_id=NONEXISTENT_URL_IN_UTUB_ID,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 404

    with app.app_context():
        # Ensure not in UTub and nonexistant
        assert Utub_Urls.query.get(NONEXISTENT_URL_IN_UTUB_ID) is None
        assert Utub_Urls.query.count() == initial_utub_urls


def test_delete_url_as_utub_creator_with_tag(
    add_all_urls_and_users_to_each_utub_with_one_tag, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub who has a valid URL in their UTub, with a single tag
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is removed from the database,
        the UTub-URL-Tag association is removed from the database, and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
        URL_SUCCESS.UTUB_ID : Integer representing the UTub ID where the URL was removed from,
        URL_SUCCESS.URL : Serialized information of the URL that was removed, as follows:
        {
            "utubUrlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAG_IDS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Find current user's UTub
        current_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Find a URL with tags on it in this UTub
        current_utub_url_tags: list[Utub_Url_Tags] = current_utub.utub_url_tags
        current_url_in_utub_with_tags: Utub_Url_Tags = current_utub_url_tags[0]

        # Get the Utubs-URL association
        url_in_utub: Utub_Urls = Utub_Urls.query.get(
            current_url_in_utub_with_tags.utub_url_id
        )
        url_object: Urls = url_in_utub.standalone_url
        url_string_to_remove = url_object.url_string

        url_id_to_remove = url_in_utub.id
        utub_id_to_delete_url_from = current_utub.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

        # Get initial number of Url-Tag associations
        initial_tag_urls = Utub_Url_Tags.query.count()

        # Get count of tags on this URL in this UTub
        tags_on_url_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == current_utub.id,
            Utub_Url_Tags.utub_url_id == current_url_in_utub_with_tags.utub_url_id,
        ).count()

    # Attempt to remove URL that contains tag from UTub as creator of UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_id_to_delete_url_from,
            utub_url_id=url_id_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    assert delete_url_response.status_code == 200

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json
    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert delete_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert (
        int(delete_url_response_json[URL_SUCCESS.UTUB_ID]) == utub_id_to_delete_url_from
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.UTUB_URL_ID]
        == url_id_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_string_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_in_utub.url_title
    )

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_id_to_remove) is not None

        # Assert the URL-USER-UTUB association is deleted
        assert Utub_Urls.query.get(url_id_to_remove) is None

        # Assert the UTUB-URL-TAG association is deleted
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_to_delete_url_from,
                Utub_Url_Tags.utub_url_id == url_id_to_remove,
            ).count()
            == 0
        )

        # Ensure counts of Url-Utubs-Tag associations are correct
        assert Utub_Urls.query.count() == initial_utub_urls - 1
        assert Utub_Url_Tags.query.count() == initial_tag_urls - tags_on_url_in_utub


def test_delete_url_as_utub_member_with_tags(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in member of a UTub who has added a valid URL to their UTub, with tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, the UTub-User-URL association is removed from the database,
        the UTub-URL-Tag association is removed from the database, and the server sends back the correct JSON reponse

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_REMOVED,
        URL_SUCCESS.UTUB_ID : Integer representing the UTub ID where the URL was removed from,
        URL_SUCCESS.URL : Serialized information of the URL that was removed, as follows:
        {
            "utubUrlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAG_IDS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get first UTub where current logged in user is not the creator
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Find a URL this user has added
        current_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_user_utub.id,
            Utub_Urls.user_id == current_user.id,
        ).first()

        utub_id_to_delete_url_from = current_user_utub.id
        url_id_to_remove = current_url_in_utub.id
        url_object: Urls = current_url_in_utub.standalone_url
        url_string_to_remove = url_object.url_string
        url_title_to_remove = current_url_in_utub.url_title

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

        # Get initial number of Url-Tag associations
        initial_tag_urls = Utub_Url_Tags.query.count()

        # Get count of tags on this URL in this UTub
        tags_on_url_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == current_user_utub.id,
            Utub_Url_Tags.utub_url_id == url_id_to_remove,
        ).count()

    # Remove URL from UTub as UTub member
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_id_to_delete_url_from,
            utub_url_id=url_id_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200

    # Ensure JSON response is correct
    delete_url_response_json = delete_url_response.json

    delete_url_response_json = delete_url_response.json
    assert delete_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert delete_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert (
        int(delete_url_response_json[URL_SUCCESS.UTUB_ID]) == utub_id_to_delete_url_from
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.UTUB_URL_ID]
        == url_id_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_string_to_remove
    )
    assert (
        delete_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_title_to_remove
    )

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_object.id) is not None

        # Assert the URL-USER-UTUB association is deleted
        assert Utub_Urls.query.get(url_id_to_remove) is None

        # Assert the UTUB-URL-TAG association is deleted
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_to_delete_url_from,
                Utub_Url_Tags.utub_url_id == url_id_to_remove,
            ).count()
            == 0
        )

        # Ensure counts of Url-Utubs-Tag associations are correct
        assert Utub_Urls.query.count() == initial_utub_urls - 1
        assert Utub_Url_Tags.query.count() == initial_tag_urls - tags_on_url_in_utub


def test_delete_url_from_utub_no_csrf_token(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in member of a UTub, with two other UTub the user is not a part of that also contains URLs
    WHEN the user wishes to remove the URL from another UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>",
        where the DELETE does not contain a valid CSRF token
    THEN the server responds with a 400 HTTP status code, the UTub-User-URL association is not removed from the database,
        and the server sends back an HTML element indicating a missing CSRF token
    """
    client, _, _, app = login_first_user_without_register

    # Find the first UTub the logged in user is not a creator of
    with app.app_context():
        utub_current_user_not_part_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        current_num_of_urls_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_current_user_not_part_of.id
        ).count()

        # Get the URL to remove
        url_to_remove_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_current_user_not_part_of.id
        ).first()
        url_to_remove_id = url_to_remove_in_utub.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = Utub_Urls.query.count()

    # Remove the URL from the other user's UTub while logged in as member of another UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=utub_current_user_not_part_of.id,
            utub_url_id=url_to_remove_id,
        ),
        data={},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in delete_url_response.data

    # Ensure database is not affected
    with app.app_context():
        utub_current_user_not_part_of = Utubs.query.filter(
            Utubs.id == utub_current_user_not_part_of.id
        ).first()

        assert (
            len(utub_current_user_not_part_of.utub_urls) == current_num_of_urls_in_utub
        )
        current_utub_urls_id = [
            url.id for url in utub_current_user_not_part_of.utub_urls
        ]
        assert url_to_remove_id in current_utub_urls_id

        assert Utub_Urls.query.count() == initial_utub_urls


def test_delete_url_updates_utub_last_updated(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub who has added a valid URL to their UTub, with no tags
    WHEN the creator wishes to remove the URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 200 HTTP status code, and the UTub's last updated field is updated
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = current_user_utub.last_updated

        url_utub_user_association: Utub_Urls = current_user_utub.utub_urls[0]
        url_id_to_remove = url_utub_user_association.id

    # Remove URL from UTub as UTub creator
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=current_user_utub.id,
            utub_url_id=url_id_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 200

    # Ensure proper removal from database
    with app.app_context():
        current_user_utub = Utubs.query.get(current_user_utub.id)
        assert (
            current_user_utub.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_remove_invalid_url_does_not_update_utub_last_updated(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub
    WHEN the user wishes to remove a nonexistant URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code, and the UTub's last updated field is not updated
    """

    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub this logged in user is a creator of
    with app.app_context():
        utub_current_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_current_user_creator_of.last_updated
        id_of_utub_current_user_creator_of = utub_current_user_creator_of.id

        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != id_of_utub_current_user_creator_of,
        ).first()
        id_of_url_to_remove = url_not_in_utub.id

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    delete_url_response = client.delete(
        url_for(
            ROUTES.URLS.DELETE_URL,
            utub_id=id_of_utub_current_user_creator_of,
            utub_url_id=id_of_url_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert delete_url_response.status_code == 404

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(id_of_utub_current_user_creator_of)
        assert current_utub.last_updated == initial_last_updated
