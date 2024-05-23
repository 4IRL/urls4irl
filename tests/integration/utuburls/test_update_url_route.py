from flask import url_for
from flask_login import current_user
import pytest

from src.models.urls import Urls
from src.models.url_tags import Url_Tags
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import URL_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.url_strs import URL_FAILURE, URL_NO_CHANGE, URL_SUCCESS
from src.utils.url_validation import find_common_url

pytestmark = pytest.mark.urls


def test_update_valid_url_with_another_fresh_valid_url_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the creator attempts to modify the URL with a URL not already in the database via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            "csrf_token": String containing CSRF token for validation
            "url_string": String of URL to add
    THEN verify that the new URL is stored in the database with same title, the url-utub-user associations and url-tag are
        modified correctly, all other URL associations are kept consistent,
        the server sends back a 200 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE: URL_SUCCESS.URL_MODIFIED,
        URL_SUCCESS.URL : Object representing a Utub_Urls, with the following fields
        {
            "url_id": ID of URL that was modified,
            "url_string": The URL that was newly modified,
            "url_tags": An array of tag ID's associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "yahoo.com"
    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = find_common_url(NEW_FRESH_URL)
        assert Urls.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=url_in_this_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=url_in_this_utub.url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: validated_new_fresh_url,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_creator_of.id,
            url_id=url_in_this_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID])
        != url_in_this_utub.url_id
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == validated_new_fresh_url
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=url_in_this_utub.url_id,
                    url_title=current_title,
                ).all()
            )
            == 0
        )

        # Assert newest entity exist
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID])
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=new_url_id,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=new_url_id
            ).all()
        ) == len(associated_tags)


def test_update_valid_url_with_another_fresh_valid_url_as_url_member(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
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
            URL_FORM.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_FRESH_URL = "yahoo.com"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = find_common_url(NEW_FRESH_URL)
        assert Urls.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_member_of.id, user_id=current_user.id
        ).first()
        current_title = url_in_this_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=url_in_this_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: validated_new_fresh_url,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_member_of.id,
            url_id=url_in_this_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID])
        != url_in_this_utub.url_id
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == validated_new_fresh_url
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls + 1 == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=url_in_this_utub.url_id,
                    url_title=current_title,
                ).all()
            )
            == 0
        )

        # Assert newest entity exist
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID])
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=new_url_id,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=new_url_id).all()
        ) == len(associated_tags)


def test_update_valid_url_with_previously_added_url_as_utub_creator(
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
            URL_FORM.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()

        # Grab URL that already exists in database and is not in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()
        assert (
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id, url_id=url_not_in_utub.url_id
            ).first()
            is None
        )
        url_string_of_url_not_in_utub = url_not_in_utub.standalone_url.url_string
        url_id_of_url_not_in_utub = url_not_in_utub.url_id

        # Grab URL that already exists in this UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, user_id=current_user.id
        ).first()
        id_of_url_in_utub = url_in_utub.url_id
        current_title = url_in_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=url_in_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url already in UTub
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=url_in_utub.url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string_of_url_not_in_utub,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_creator_of.id,
            url_id=url_in_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID]) != id_of_url_in_utub
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID])
        == url_id_of_url_not_in_utub
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING]
        == url_string_of_url_not_in_utub
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=id_of_url_in_utub,
                    url_title=current_title,
                ).all()
            )
            == 0
        )

        # Assert newest entity exist
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=url_id_of_url_not_in_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=url_id_of_url_not_in_utub
            ).all()
        ) == len(associated_tags)


def test_update_valid_url_with_previously_added_url_as_url_adder(
    add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
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
            URL_FORM.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        all_utubs_urls: list[Utub_Urls] = Utub_Urls.query.all()
        for utub_urls in all_utubs_urls:
            utub: Utubs = utub_urls.utub
            utub_members = [member.user_id for member in utub.members]

            user_in_utub: bool = current_user.id in utub_members
            user_added_url: bool = current_user.id == utub_urls.user_id
            user_not_creator: bool = current_user.id != utub.utub_creator

            if user_in_utub and user_added_url and user_not_creator:
                utub_member_of = utub
                url_in_this_utub = utub_urls
                url_id_of_url_in_this_utub = url_in_this_utub.url_id
                current_title = url_in_this_utub.url_title
                break

        # Get a URL that isn't in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.user_id != current_user.id, Utub_Urls.utub_id != utub_member_of.id
        ).first()
        url_string_of_url_not_in_utub: str = url_not_in_utub.standalone_url.url_string
        url_id_of_url_not_in_utub = url_not_in_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=url_in_this_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string_of_url_not_in_utub,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_member_of.id,
            url_id=url_in_this_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID])
        == url_id_of_url_not_in_utub
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING]
        == url_string_of_url_not_in_utub
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity no longer exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=url_id_of_url_in_this_utub,
                    url_title=current_title,
                ).all()
            )
            == 0
        )

        # Assert newest entity exist
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=url_id_of_url_not_in_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_member_of.id, url_id=url_id_of_url_not_in_utub
            ).all()
        ) == len(associated_tags)


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
            URL_FORM.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, user_id=current_user.id
        ).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        url_in_utub_string: str = url_already_in_utub.standalone_url.url_string
        current_title = url_already_in_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=url_already_in_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url already in UTub
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_in_utub_string,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_creator_of.id,
            url_id=url_already_in_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID]) == id_of_url_in_utub
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == url_in_utub_string
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=id_of_url_in_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=id_of_url_in_utub
            ).all()
        ) == len(associated_tags)


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
            URL_FORM.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        all_utubs_urls: list[Utub_Urls] = Utub_Urls.query.all()
        for utub_urls in all_utubs_urls:
            utub: Utubs = utub_urls.utub
            utub_members = [member.user_id for member in utub.members]

            user_in_utub: bool = current_user.id in utub_members
            user_added_url: bool = current_user.id == utub_urls.user_id
            user_not_creator: bool = current_user.id != utub.utub_creator

            if user_in_utub and user_added_url and user_not_creator:
                utub_member_of = utub
                url_in_this_utub = utub_urls
                url_id_of_url_in_this_utub = url_in_this_utub.url_id
                current_title = url_in_this_utub.url_title
                url_string_of_url_in_utub = url_in_this_utub.standalone_url.url_string
                break

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=url_in_this_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string_of_url_in_utub,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_member_of.id,
            url_id=url_id_of_url_in_this_utub,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_NOT_MODIFIED
    assert (
        int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID])
        == url_id_of_url_in_this_utub
    )
    assert (
        json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == url_string_of_url_in_utub
    )
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=url_id_of_url_in_this_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub
            ).all()
        ) == len(associated_tags)


def test_update_valid_url_with_invalid_url_as_utub_creator(
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
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, user_id=current_user.id
        ).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        current_title = url_already_in_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=url_already_in_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url already in UTub
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: "AAAAA",
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_creator_of.id,
            url_id=url_already_in_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=id_of_url_in_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=id_of_url_in_utub
            ).all()
        ) == len(associated_tags)


def test_update_valid_url_with_invalid_url_as_url_adder(
    add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
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
    client, csrf_token_string, _, app = login_first_user_without_register

    INVALID_URL = "AAAAA"
    with app.app_context():
        all_utubs_urls: list[Utub_Urls] = Utub_Urls.query.all()
        for utub_urls in all_utubs_urls:
            utub: Utubs = utub_urls.utub
            utub_members = [member.user_id for member in utub.members]

            user_in_utub: bool = current_user.id in utub_members
            user_added_url: bool = current_user.id == utub_urls.user_id
            user_not_creator: bool = current_user.id != utub.utub_creator

            if user_in_utub and user_added_url and user_not_creator:
                utub_member_of = utub
                url_in_this_utub = utub_urls
                url_id_of_url_in_this_utub = url_in_this_utub.url_id
                current_title = url_in_this_utub.url_title
                break

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=url_in_this_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: INVALID_URL,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_member_of.id,
            url_id=url_id_of_url_in_this_utub,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_VALIDATE_THIS_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=url_id_of_url_in_this_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_member_of.id, url_id=url_id_of_url_in_this_utub
            ).all()
        ) == len(associated_tags)


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
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

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
        utub_creator_of: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, user_id=current_user.id
        ).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        current_title = url_already_in_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=url_already_in_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url already in UTub
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: NEW_URL,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_creator_of.id,
            url_id=url_already_in_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 4
    assert (
        json_response[STD_JSON.ERRORS][URL_FORM.URL_STRING]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=id_of_url_in_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=id_of_url_in_utub
            ).all()
        ) == len(associated_tags)


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

    NEW_FRESH_URL = "yahoo.com"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = find_common_url(NEW_FRESH_URL)
        assert Urls.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id != current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_utub_serialized_originally = url_in_this_utub.serialized_on_string_edit
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=url_in_this_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: validated_new_fresh_url,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_member_of.id,
            url_id=url_in_this_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=url_in_this_utub.url_id,
                    url_title=current_title,
                ).all()
            )
            == num_of_url_utub_associations
        )

        assert (
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=original_url_id,
                user_id=original_user_id,
            )
            .first()
            .serialized_on_string_edit
            == url_in_utub_serialized_originally
        )

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=url_in_this_utub.url_id,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_member_of.id, url_id=url_in_this_utub.url_id
            ).all()
        ) == len(associated_tags)


def test_update_url_with_fresh_valid_url_as_other_utub_member(
    add_first_user_to_second_utub_and_add_tags_remove_first_utub,
    login_first_user_without_register,
):
    """
    GIVEN a valid member of a UTub that has members, URLs, and tags associated with each URL
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

    NEW_FRESH_URL = "yahoo.com"
    with app.app_context():
        # Get UTub this user is not a member of
        utub_user_not_member_of: Utubs = Utubs.query.get(3)

        all_utubs: list[Utubs] = Utubs.query.all()
        for utub in all_utubs:
            assert current_user.id != utub.utub_creator

        # Verify logged in user is not member of this UTub
        assert current_user.id not in [
            chosen_utub_member.user_id
            for chosen_utub_member in utub_user_not_member_of.members
        ]

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = find_common_url(NEW_FRESH_URL)
        assert Urls.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL not in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_utub_serialized_originally = url_in_this_utub.serialized_on_string_edit
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_user_not_member_of.id,
                url_id=url_in_this_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Get number of URLs in this UTub
        num_of_urls_in_utub = len(
            Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id).all()
        )

        # Find associated tags with this url
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: validated_new_fresh_url,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_user_not_member_of.id,
            url_id=url_in_this_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        assert (
            len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id).all())
            == num_of_urls_in_utub
        )

        # Assert url-utub association hasn't changed
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_user_not_member_of.id,
                    url_id=url_in_this_utub.url_id,
                    url_title=current_title,
                ).all()
            )
            == num_of_url_utub_associations
        )
        assert (
            Utub_Urls.query.filter_by(
                utub_id=utub_user_not_member_of.id,
                url_id=original_url_id,
                user_id=original_user_id,
            )
            .first()
            .serialized_on_string_edit
            == url_in_utub_serialized_originally
        )

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_user_not_member_of.id,
                    url_id=url_in_this_utub.url_id,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id
            ).all()
        ) == len(associated_tags)


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

    NEW_FRESH_URL = "yahoo.com"
    with app.app_context():
        # Get UTub this user is not a member of
        all_utubs: list[Utubs] = Utubs.query.all()
        i = 0
        while (
            current_user.id
            in [utub_member.user_id for utub_member in all_utubs[i].members]
            and current_user.id == all_utubs[i].utub_creator
        ):
            i += 1

        utub_user_not_member_of = all_utubs[i]

        # Verify logged in user is not member of this UTub
        assert current_user.id not in [
            chosen_utub_member.user_id
            for chosen_utub_member in utub_user_not_member_of.members
        ]

        # Verify user is creator of a UTub
        i = 0
        while all_utubs[i].utub_creator != current_user.id:
            i += 1

        assert all_utubs[i].utub_creator == current_user.id

        # Verify URL to modify to is not already in database
        validated_new_fresh_url = find_common_url(NEW_FRESH_URL)
        assert Urls.query.filter_by(url_string=validated_new_fresh_url).first() is None

        # Get the URL not in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_not_member_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        url_in_utub_serialized_originally = url_in_this_utub.serialized_on_string_edit
        original_user_id = url_in_this_utub.user_id
        original_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_user_not_member_of.id,
                url_id=url_in_this_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Get number of URLs in this UTub
        num_of_urls_in_utub = len(
            Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id).all()
        )

        # Find associated tags with this url
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: validated_new_fresh_url,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_user_not_member_of.id,
            url_id=url_in_this_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        assert (
            len(Utub_Urls.query.filter_by(utub_id=utub_user_not_member_of.id).all())
            == num_of_urls_in_utub
        )

        # Assert url-utub association hasn't changed
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_user_not_member_of.id,
                    url_id=url_in_this_utub.url_id,
                    url_title=current_title,
                ).all()
            )
            == num_of_url_utub_associations
        )
        assert (
            Utub_Urls.query.filter_by(
                utub_id=utub_user_not_member_of.id,
                url_id=original_url_id,
                user_id=original_user_id,
            )
            .first()
            .serialized_on_string_edit
            == url_in_utub_serialized_originally
        )

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_user_not_member_of.id,
                    url_id=url_in_this_utub.url_id,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_user_not_member_of.id, url_id=url_in_this_utub.url_id
            ).all()
        ) == len(associated_tags)


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
        the server sends back a 404 HTTP status code, and the server sends back the appropriate JSON response

    Proper JSON is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM,
        STD_JSON.ERRORS : Object representing the errors found in the form, with the following fields
        {
            URL_FORM.URL_STRING: Array of errors associated with the url_string field,
        }
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, user_id=current_user.id
        ).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        current_title = url_already_in_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=url_already_in_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url already in UTub
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_creator_of.id,
            url_id=url_already_in_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = edit_url_string_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 4
    assert (
        json_response[STD_JSON.ERRORS][URL_FORM.URL_STRING]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=id_of_url_in_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=id_of_url_in_utub
            ).all()
        ) == len(associated_tags)


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
        utub_creator_of: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()

        # Grab URL that already exists in this UTub
        url_already_in_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, user_id=current_user.id
        ).first()
        id_of_url_in_utub = url_already_in_utub.url_id
        current_title = url_already_in_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=url_already_in_utub.url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url already in UTub
        associated_tags: list[Url_Tags] = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=url_already_in_utub.url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(Urls.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_form = {
        URL_FORM.URL_STRING: NEW_URL,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_creator_of.id,
            url_id=url_already_in_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    # Ensure valid reponse
    assert edit_url_string_form.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in edit_url_string_form.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(Urls.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert previous entity exists
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_creator_of.id,
                    url_id=id_of_url_in_utub,
                    url_title=current_title,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=id_of_url_in_utub
            ).all()
        ) == len(associated_tags)


def test_update_valid_url_updates_utub_last_updated(
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
        utub_creator_of: Utubs = Utubs.query.filter_by(
            utub_creator=current_user.id
        ).first()
        initial_last_updated = utub_creator_of.last_updated

        # Grab URL that already exists in database and is not in this UTub
        url_not_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id
        ).first()
        assert (
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id, url_id=url_not_in_utub.url_id
            ).first()
            is None
        )
        url_string_of_url_not_in_utub: str = url_not_in_utub.standalone_url.url_string

        # Grab URL that already exists in this UTub
        url_in_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, user_id=current_user.id
        ).first()

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: url_string_of_url_not_in_utub,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_creator_of.id,
            url_id=url_in_utub.url_id,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 200

    with app.app_context():
        # Assert database is consistent after newly modified URL
        current_utub: Utubs = Utubs.query.get(utub_creator_of.id)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


def test_update_valid_url_with_invalid_url_does_not_update_utub_last_updated(
    add_two_url_and_all_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, a single URL, and tags associated with that URL
    WHEN the url adder attempts to modify the URL with an invalid URL, via a PATCH to
        "/utubs/<int:utub_id>/urls/<int:url_id>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_STRING: String of URL to add
    THEN the server sends back a 400 HTTP status code, and the UTub last updated field is not modified
    """

    client, csrf_token_string, _, app = login_first_user_without_register

    INVALID_URL = "AAAAA"
    with app.app_context():
        all_utubs_urls: list[Utub_Urls] = Utub_Urls.query.all()
        for utub_urls in all_utubs_urls:
            utub: Utubs = utub_urls.utub
            utub_members = [member.user_id for member in utub.members]

            user_in_utub: bool = current_user.id in utub_members
            user_added_url: bool = current_user.id == utub_urls.user_id
            user_not_creator: bool = current_user.id != utub.utub_creator

            if user_in_utub and user_added_url and user_not_creator:
                utub_member_of = utub
                url_in_this_utub = utub_urls
                url_id_of_url_in_this_utub = url_in_this_utub.url_id
                break

        initial_last_updated = utub_member_of.last_updated

    edit_url_string_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: INVALID_URL,
    }

    edit_url_string_form = client.patch(
        url_for(
            ROUTES.URLS.EDIT_URL,
            utub_id=utub_member_of.id,
            url_id=url_id_of_url_in_this_utub,
        ),
        data=edit_url_string_form,
    )

    assert edit_url_string_form.status_code == 400

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_member_of.id)
        assert current_utub.last_updated == initial_last_updated
