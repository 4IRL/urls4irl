from flask import url_for
from flask_login import current_user
import pytest

from src import db
from src.models.urls import Urls
from src.models.url_tags import Url_Tags
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import URL_FORM
from src.utils.strings.model_strs import MODELS
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.url_strs import URL_FAILURE, URL_SUCCESS

pytestmark = pytest.mark.urls


def test_remove_url_as_utub_creator_no_tags(
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
            "urlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAGS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Get UTub of current user
    with app.app_context():
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()

        # Assert there is a URL in the UTub
        assert len(current_user_utub.utub_urls) == 1

        url_utub_user_association: Utub_Urls = current_user_utub.utub_urls[0]
        url_id_to_remove = url_utub_user_association.url_id

        # Assert the single UTUB-URL-USER association exists
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.url_id == url_id_to_remove,
                    Utub_Urls.user_id == current_user.id,
                    Utub_Urls.utub_id == current_user_utub.id,
                ).all()
            )
            == 1
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())
        url_object: Urls = url_utub_user_association.standalone_url

    # Remove URL from UTub as UTub creator
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=current_user_utub.id,
            url_id=url_id_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 200

    # Ensure JSON response is correct
    remove_url_response_json = remove_url_response.json
    assert remove_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert int(remove_url_response_json[URL_SUCCESS.UTUB_ID]) == current_user_utub.id
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_ID]
        == url_id_to_remove
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_object.url_string
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_utub_user_association.url_title
    )
    assert remove_url_response_json[MODELS.TAGS] == []

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_id_to_remove) is not None

        # Assert the URL-USER-UTUB association is deleted
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.url_id == url_id_to_remove,
                    Utub_Urls.user_id == current_user.id,
                    Utub_Urls.utub_id == current_user_utub.id,
                ).all()
            )
            == 0
        )

        # Ensure UTub has no URLs left
        current_user_utub = Utubs.query.get(current_user_utub.id)
        assert len(current_user_utub.utub_urls) == 0

        assert len(Utub_Urls.query.all()) == initial_utub_urls - 1


def test_remove_url_as_utub_member_no_tags(
    add_one_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
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
            "urlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAGS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register
    NEW_URL_TITLE = "This is my new URL title"

    with app.app_context():
        # Get first UTub where current logged in user is not the creator
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Assert there is a URL in the UTub
        assert len(current_user_utub.utub_urls) == 1
        current_url_in_utub = current_user_utub.utub_urls[0]

        # Assert current user did not add this URL
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == current_user_utub.id,
                    Utub_Urls.url_id == current_url_in_utub.url_id,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 0
        )

        # Find a URL that the current user did not add
        missing_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id != current_user.id,
            Utub_Urls.utub_id != current_user_utub.id,
        ).first()

        missing_url: Urls = missing_url_association.standalone_url

        # Have current user add the missing URL to the current UTub
        new_utub_url_association = Utub_Urls()
        new_utub_url_association.url_id = missing_url.id
        new_utub_url_association.standalone_url = missing_url
        new_utub_url_association.utub_id = current_user_utub.id
        new_utub_url_association.utub = current_user_utub
        new_utub_url_association.user_id = current_user.id
        new_utub_url_association.user_that_added_url = current_user
        new_utub_url_association.url_title = NEW_URL_TITLE

        db.session.add(new_utub_url_association)
        db.session.commit()

        # Assert this URL was added
        current_user_utub = Utubs.query.get(current_user_utub.id)
        assert len(current_user_utub.utub_urls) == 2

        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.url_id == missing_url.id,
                    Utub_Urls.utub_id == current_user_utub.id,
                    Utub_Urls.user_id == current_user.id,
                ).all()
            )
            == 1
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Remove URL from UTub as UTub member
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL, utub_id=current_user_utub.id, url_id=missing_url.id
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 200

    # Ensure JSON response is correct
    remove_url_response_json = remove_url_response.json

    assert remove_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert int(remove_url_response_json[URL_SUCCESS.UTUB_ID]) == current_user_utub.id
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_ID] == missing_url.id
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == missing_url.url_string
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == NEW_URL_TITLE
    )
    assert remove_url_response_json[MODELS.TAGS] == []

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(missing_url.id) is not None

        # Assert the URL-UTUB association is deleted
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.url_id == missing_url.id,
                    Utub_Urls.utub_id == current_user_utub.id,
                ).all()
            )
            == 0
        )

        # Ensure UTub has one left
        current_user_utub = Utubs.query.get(current_user_utub.id)
        assert len(current_user_utub.utub_urls) == 1

        assert len(Utub_Urls.query.all()) == initial_utub_urls - 1


def test_remove_url_from_utub_not_member_of(
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
        STD_JSON.MESSAGE : URL_FAILURE.UNABLE_TO_REMOVE_URL
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub the logged in user is not a creator of
    with app.app_context():
        utub_current_user_not_part_of = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Ensure the currently logged in user is not in this UTub
        assert current_user not in [
            user.to_user for user in utub_current_user_not_part_of.members
        ]

        # Ensure there exists a URL in this UTub
        assert len(utub_current_user_not_part_of.utub_urls) > 0
        current_num_of_urls_in_utub = len(utub_current_user_not_part_of.utub_urls)

        # Get the URL to remove
        url_to_remove_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_current_user_not_part_of.id
        ).first()
        url_to_remove = url_to_remove_in_utub.standalone_url
        url_to_remove_id = url_to_remove.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Remove the URL from the other user's UTub while logged in as member of another UTub
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=utub_current_user_not_part_of.id,
            url_id=url_to_remove_id,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 403

    # Ensure JSON response is correct
    remove_url_response_json = remove_url_response.json
    assert remove_url_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_url_response_json[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_REMOVE_URL
    )

    # Ensure database is not affected
    with app.app_context():
        utub_current_user_not_part_of = Utubs.query.filter(
            Utubs.id == utub_current_user_not_part_of.id
        ).first()

        assert (
            len(utub_current_user_not_part_of.utub_urls) == current_num_of_urls_in_utub
        )
        current_utub_urls_id = [
            url.url_id for url in utub_current_user_not_part_of.utub_urls
        ]
        assert url_to_remove_id in current_utub_urls_id

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_remove_invalid_nonexistant_url_as_utub_creator(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub
    WHEN the user wishes to remove a nonexistant URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code, and the database has no changes
    """

    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub this logged in user is a creator of
    with app.app_context():
        utub_current_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub_current_user_creator_of = utub_current_user_creator_of.id

        all_urls: list[Urls] = Urls.query.all()
        all_url_ids = [url.id for url in all_urls]
        all_urls_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_current_user_creator_of
        ).all()
        all_urls_ids_in_utub = [url.url_id for url in all_urls_in_utub]

        # Find ID of URL that doesn't exist as URL or in UTub
        id_of_url_to_remove = 0
        while (
            id_of_url_to_remove in all_url_ids
            and id_of_url_to_remove in all_urls_ids_in_utub
        ):
            id_of_url_to_remove += 1

        # Ensure not in UTub and nonexistant
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_current_user_creator_of,
                    Utub_Urls.url_id == id_of_url_to_remove,
                ).all()
            )
            == 0
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=id_of_utub_current_user_creator_of,
            url_id=id_of_url_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 404

    with app.app_context():
        # Ensure not in UTub and nonexistant
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_current_user_creator_of,
                    Utub_Urls.url_id == id_of_url_to_remove,
                ).all()
            )
            == 0
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_remove_invalid_nonexistant_url_as_utub_member(
    add_one_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a logged-in creator of a UTub
    WHEN the user wishes to remove a nonexistant URL from the UTub by making a DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>"
    THEN the server responds with a 404 HTTP status code, and the database has no changes
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    # Find the first UTub this logged in user is a creator of
    with app.app_context():
        utub_current_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub_current_user_member_of = utub_current_user_member_of.id

        all_urls: list[Urls] = Urls.query.all()
        all_url_ids = [url.id for url in all_urls]
        all_urls_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub_current_user_member_of
        ).all()
        all_urls_ids_in_utub = [url.url_id for url in all_urls_in_utub]

        # Find ID of URL that doesn't exist as URL or in UTub
        id_of_url_to_remove = 0
        while (
            id_of_url_to_remove in all_url_ids
            and id_of_url_to_remove in all_urls_ids_in_utub
        ):
            id_of_url_to_remove += 1

        # Ensure not in UTub and nonexistant
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_current_user_member_of,
                    Utub_Urls.url_id == id_of_url_to_remove,
                ).all()
            )
            == 0
        )

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=id_of_utub_current_user_member_of,
            url_id=id_of_url_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 404

    with app.app_context():
        # Ensure not in UTub and nonexistant
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == id_of_utub_current_user_member_of,
                    Utub_Urls.url_id == id_of_url_to_remove,
                ).all()
            )
            == 0
        )

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_remove_url_as_utub_creator_with_tag(
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
            "urlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAGS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
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
        current_utub_url_tags: list[Url_Tags] = current_utub.utub_url_tags
        current_url_in_utub_with_tags: Url_Tags = current_utub_url_tags[0]

        # Ensure this URL has tags associated with it
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == current_utub.id,
                    Url_Tags.url_id == current_url_in_utub_with_tags.url_id,
                ).all()
            )
            > 0
        )

        # Get the Utubs-URL association
        url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_utub.id,
            Utub_Urls.url_id == current_url_in_utub_with_tags.url_id,
        ).first()
        url_object: Urls = url_in_utub.standalone_url
        url_string_to_remove = url_object.url_string
        associated_tags = url_in_utub.associated_tags

        url_id_to_remove = current_url_in_utub_with_tags.url_id
        utub_id_to_remove_url_from = current_utub.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

        # Get initial number of Url-Tag associations
        initial_tag_urls = len(Url_Tags.query.all())

        # Get count of tags on this URL in this UTub
        tags_on_url_in_utub = len(
            Url_Tags.query.filter(
                Url_Tags.utub_id == current_utub.id,
                Url_Tags.url_id == current_url_in_utub_with_tags.url_id,
            ).all()
        )

    # Attempt to remove URL that contains tag from UTub as creator of UTub
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=utub_id_to_remove_url_from,
            url_id=url_id_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure JSON response is correct
    remove_url_response_json = remove_url_response.json
    assert remove_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert (
        int(remove_url_response_json[URL_SUCCESS.UTUB_ID]) == utub_id_to_remove_url_from
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_ID]
        == url_id_to_remove
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_string_to_remove
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_in_utub.url_title
    )

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_id_to_remove) is not None

        # Assert the URL-USER-UTUB association is deleted
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.url_id == url_id_to_remove,
                    Utub_Urls.user_id == current_user.id,
                    Utub_Urls.utub_id == utub_id_to_remove_url_from,
                ).all()
            )
            == 0
        )

        # Assert the UTUB-URL-TAG association is deleted
        tags_in_utub: list[Url_Tags] = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_to_remove_url_from,
            Url_Tags.url_id == url_id_to_remove,
        ).all()

        assert len(tags_in_utub) == 0

        assert remove_url_response_json[MODELS.TAGS] == [
            {MODELS.ID: tag_id, URL_SUCCESS.TAG_IN_UTUB: False}
            for tag_id in associated_tags
        ]

        # Ensure counts of Url-Utubs-Tag associations are correct
        assert len(Utub_Urls.query.all()) == initial_utub_urls - 1
        assert len(Url_Tags.query.all()) == initial_tag_urls - tags_on_url_in_utub


def test_remove_url_as_utub_member_with_tags(
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
            "urlID": Integer representing ID of the URL,
            "urlString": String representing the URL itself,
            "urlTitle": String representing the title associated with the URL,
        }
        URL_SUCCESS.URL_TAGS : Array of tag IDs associated with this removed URL, and booleans indicating whether that tag
            still exists in the UTub
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get first UTub where current logged in user is not the creator
        current_user_utub: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Assert there is a URL in the UTub
        assert len(current_user_utub.utub_urls) > 0

        # Find a URL this user has added
        current_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == current_user_utub.id,
            Utub_Urls.user_id == current_user.id,
        ).first()

        # Make sure this URL has tags on it
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == current_user_utub.id,
                    Url_Tags.url_id == current_url_in_utub.url_id,
                ).all()
            )
            > 0
        )

        utub_id_to_remove_url_from = current_user_utub.id
        url_id_to_remove = current_url_in_utub.url_id
        url_object: Urls = current_url_in_utub.standalone_url
        url_string_to_remove = url_object.url_string
        url_title_to_remove = current_url_in_utub.url_title
        associated_tags: list[int] = current_url_in_utub.associated_tags

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

        # Get initial number of Url-Tag associations
        initial_tag_urls = len(Url_Tags.query.all())

        # Get count of tags on this URL in this UTub
        tags_on_url_in_utub = len(
            Url_Tags.query.filter(
                Url_Tags.utub_id == current_user_utub.id,
                Url_Tags.url_id == url_id_to_remove,
            ).all()
        )

    # Remove URL from UTub as UTub member
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=utub_id_to_remove_url_from,
            url_id=url_id_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 200

    # Ensure JSON response is correct
    remove_url_response_json = remove_url_response.json

    remove_url_response_json = remove_url_response.json
    assert remove_url_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert remove_url_response_json[STD_JSON.MESSAGE] == URL_SUCCESS.URL_REMOVED
    assert (
        int(remove_url_response_json[URL_SUCCESS.UTUB_ID]) == utub_id_to_remove_url_from
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_ID]
        == url_id_to_remove
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_STRING]
        == url_string_to_remove
    )
    assert (
        remove_url_response_json[URL_SUCCESS.URL][URL_SUCCESS.URL_TITLE]
        == url_title_to_remove
    )

    # Ensure proper removal from database
    with app.app_context():
        # Assert url still in database
        assert Urls.query.get(url_id_to_remove) is not None

        # Assert the URL-USER-UTUB association is deleted
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.url_id == url_id_to_remove,
                    Utub_Urls.utub_id == utub_id_to_remove_url_from,
                ).all()
            )
            == 0
        )

        # Assert the UTUB-URL-TAG association is deleted
        tags_in_utub_on_url: list[Url_Tags] = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_to_remove_url_from,
            Url_Tags.url_id == url_id_to_remove,
        ).all()

        assert len(tags_in_utub_on_url) == 0

        tags_in_utub: list[Url_Tags] = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_to_remove_url_from
        ).all()
        tag_ids_in_utub: list[int] = [tag.tag_id for tag in tags_in_utub]
        tags_array_response = [
            {MODELS.ID: tag_id, URL_SUCCESS.TAG_IN_UTUB: tag_id in tag_ids_in_utub}
            for tag_id in associated_tags
        ]

        assert tags_array_response == remove_url_response_json[MODELS.TAGS]

        # Ensure counts of Url-Utubs-Tag associations are correct
        assert len(Utub_Urls.query.all()) == initial_utub_urls - 1
        assert len(Url_Tags.query.all()) == initial_tag_urls - tags_on_url_in_utub


def test_remove_url_from_utub_no_csrf_token(
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

        # Ensure the currently logged in user is not in this UTub and is not the creator of this UTub
        assert current_user not in [
            user.to_user for user in utub_current_user_not_part_of.members
        ]

        # Ensure there exists a URL in this UTub
        assert len(utub_current_user_not_part_of.utub_urls) > 0
        current_num_of_urls_in_utub = len(utub_current_user_not_part_of.utub_urls)

        # Get the URL to remove
        url_to_remove_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_current_user_not_part_of.id
        ).first()
        url_to_remove: Urls = url_to_remove_in_utub.standalone_url
        url_to_remove_id = url_to_remove.id

        # Get initial number of UTub-URL associations
        initial_utub_urls = len(Utub_Urls.query.all())

    # Remove the URL from the other user's UTub while logged in as member of another UTub
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=utub_current_user_not_part_of.id,
            url_id=url_to_remove_id,
        ),
        data={},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in remove_url_response.data

    # Ensure database is not affected
    with app.app_context():
        utub_current_user_not_part_of = Utubs.query.filter(
            Utubs.id == utub_current_user_not_part_of.id
        ).first()

        assert (
            len(utub_current_user_not_part_of.utub_urls) == current_num_of_urls_in_utub
        )
        current_utub_urls_id = [
            url.url_id for url in utub_current_user_not_part_of.utub_urls
        ]
        assert url_to_remove_id in current_utub_urls_id

        assert len(Utub_Urls.query.all()) == initial_utub_urls


def test_remove_url_updates_utub_last_updated(
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
        url_id_to_remove = url_utub_user_association.url_id

    # Remove URL from UTub as UTub creator
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=current_user_utub.id,
            url_id=url_id_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 200

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
            Utub_Urls.utub_id != id_of_utub_current_user_creator_of
        ).first()
        id_of_url_to_remove = url_not_in_utub.url_id

    # Attempt to remove nonexistant URL from UTub as creator of UTub
    remove_url_response = client.delete(
        url_for(
            ROUTES.URLS.REMOVE_URL,
            utub_id=id_of_utub_current_user_creator_of,
            url_id=id_of_url_to_remove,
        ),
        data={URL_FORM.CSRF_TOKEN: csrf_token_string},
    )

    # Ensure 200 HTTP status code response
    assert remove_url_response.status_code == 404

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(id_of_utub_current_user_creator_of)
        assert current_utub.last_updated == initial_last_updated
