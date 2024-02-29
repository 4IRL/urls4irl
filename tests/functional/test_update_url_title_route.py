from flask import url_for
from flask_login import current_user

from src.models import Utub, Utub_Urls, Url_Tags, URLS, User
from src.utils.url_validation import find_common_url
from src.utils import strings as U4I_STRINGS

URL_FORM = U4I_STRINGS.URL_FORM
URL_SUCCESS = U4I_STRINGS.URL_SUCCESS
STD_JSON = U4I_STRINGS.STD_JSON_RESPONSE
MODEL_STRS = U4I_STRINGS.MODELS
URL_FAILURE = U4I_STRINGS.URL_FAILURE
URL_NO_CHANGE = U4I_STRINGS.URL_NO_CHANGE
EDIT_URL_TITLE_URL = "urls.edit_url_title"

# TODO: Update title with another title as UTub creator - DONE
# TODO: Update title with another title as URL adder - DONE
# TODO: Update title with same title as UTub creator - DONE
# TODO: Update title with same title as URL adder - DONE
# TODO: Update title with another title as UTub member (not creator or adder) - DONE
# TODO: Update title with empty title - DONE
# TODO: Update title with another title as member of another UTub (not current one) - DONE
# TODO: Update title with missing title field - DONE
# TODO: Update title with missing csrf field - DONE
# TODO: Update title of URL that does not exist - DONE
# TODO: Update title of URL in UTub that does not exist


def test_update_url_title_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
            URL_FORM.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
            MODEL_STRS.ADDED_BY: Id of the user who added this, should be the user modifying it
            MODEL_STRS.URL_TITLE: String representing the URL title in this UTub
        }
        URL_SUCCESS.UTUB_ID : UTub ID where this URL exists,
        URL_SUCCESS.UTUB_NAME : Name of UTub containing this URL
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url = url_in_this_utub.url_in_utub.url_string
        current_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

        current_user_id = current_user.id

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_creator_of.id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_TITLE_MODIFIED
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.ADDED_BY]) == current_user_id
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TITLE] == NEW_TITLE
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID]) == current_url_id
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == current_url
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids
    assert int(json_response[URL_SUCCESS.UTUB_ID]) == utub_creator_of.id
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        new_url_item: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).first()
        assert new_url_item.url_title == NEW_TITLE
        assert new_url_item.url_id == current_url_id

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=current_url_id
            ).all()
        ) == len(associated_tags)


def test_update_url_title_url_adder(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URL added by the member, and tags associated with each URL
    WHEN the member attempts to modify the URL title, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
            URL_FORM.URL_STRING: The URL that was newly modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
            MODEL_STRS.ADDED_BY: Id of the user who added this, should be the user modifying it
            MODEL_STRS.URL_TITLE: String representing the URL title in this UTub
        }
        URL_SUCCESS.UTUB_ID : UTub ID where this URL exists,
        URL_SUCCESS.UTUB_NAME : Name of UTub containing this URL
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    NEW_TITLE = "This is my newest facebook.com!"
    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Verify logged in user is not creator of this UTub
        assert utub_member_of.utub_creator != current_user.id

        # Get the URL in this UTub
        url_in_this_utub = Utub_Urls.query.filter_by(
            utub_id=utub_member_of.id, user_id=current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url = url_in_this_utub.url_in_utub.url_string
        current_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_member_of.id, url_id=current_url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

        current_user_id = current_user.id

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: current_url,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_member_of.id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert json_response[STD_JSON.MESSAGE] == URL_SUCCESS.URL_TITLE_MODIFIED
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.ADDED_BY]) == current_user_id
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TITLE] == NEW_TITLE
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID]) == current_url_id
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == current_url
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids
    assert int(json_response[URL_SUCCESS.UTUB_ID]) == utub_member_of.id
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_member_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert entity exists
        new_url_id = int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID])
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=new_url_id,
                    url_title=NEW_TITLE,
                ).all()
            )
            == 1
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(utub_id=utub_member_of.id, url_id=new_url_id).all()
        ) == len(associated_tags)


def test_update_url_title_with_same_title_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with the same title, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
            URL_FORM.URL_STRING: The URL that was not modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
            MODEL_STRS.ADDED_BY: Id of the user who added this, should be the user modifying it
            MODEL_STRS.URL_TITLE: String representing the URL title in this UTub
        }
        URL_SUCCESS.UTUB_ID: UTub ID where this URL exists,
        URL_SUCCESS.UTUB_NAME: Name of UTub containing this URL
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url = url_in_this_utub.url_in_utub.url_string
        current_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

        current_user_id = current_user.id

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: current_title,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_creator_of.id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.ADDED_BY]) == current_user_id
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TITLE] == current_title
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID]) == current_url_id
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == current_url
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids
    assert int(json_response[URL_SUCCESS.UTUB_ID]) == utub_creator_of.id
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_creator_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        new_url_item: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).first()
        assert new_url_item.url_title == current_title
        assert new_url_item.url_id == current_url_id

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=current_url_id
            ).all()
        ) == len(associated_tags)


def test_update_url_title_with_same_title_url_adder(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URL added by the member, and tags associated with each URL
    WHEN the member attempts to modify the URL title with the same title, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
            URL_FORM.URL_STRING: The URL that was not modified,
            MODEL_STRS.URL_TAGS: An array of tag ID's associated with this URL
            MODEL_STRS.ADDED_BY: Id of the user who added this, should be the user modifying it
            MODEL_STRS.URL_TITLE: String representing the URL title in this UTub
        }
        URL_SUCCESS.UTUB_ID : UTub ID where this URL exists,
        URL_SUCCESS.UTUB_NAME : Name of UTub containing this URL
    }
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        # Get UTub this user is only a member of
        utub_member_of = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Verify logged in user is not creator of this UTub
        assert utub_member_of.utub_creator != current_user.id

        # Get the URL in this UTub
        url_in_this_utub = Utub_Urls.query.filter_by(
            utub_id=utub_member_of.id, user_id=current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url = url_in_this_utub.url_in_utub.url_string
        current_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_member_of.id, url_id=current_url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

        current_user_id = current_user.id

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: current_url,
        URL_FORM.URL_TITLE: current_title,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_member_of.id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 200

    # Assert JSON response from server is valid
    json_response = edit_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert json_response[STD_JSON.MESSAGE] == URL_NO_CHANGE.URL_TITLE_NOT_MODIFIED
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.ADDED_BY]) == current_user_id
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TITLE] == current_title
    assert int(json_response[URL_SUCCESS.URL][MODEL_STRS.URL_ID]) == current_url_id
    assert json_response[URL_SUCCESS.URL][URL_FORM.URL_STRING] == current_url
    assert json_response[URL_SUCCESS.URL][MODEL_STRS.URL_TAGS] == associated_tag_ids
    assert int(json_response[URL_SUCCESS.UTUB_ID]) == utub_member_of.id
    assert json_response[URL_SUCCESS.UTUB_NAME] == utub_member_of.name

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert entity exists
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


def test_update_url_title_as_utub_member_not_adder_or_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN a valid member of a UTub that has members, URL not added by the member, and tags associated with each URL
    WHEN the member attempts to modify the URL title, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
        utub_member_of = Utub.query.filter(Utub.utub_creator != current_user.id).first()

        # Verify logged in user is not creator of this UTub
        assert utub_member_of.utub_creator != current_user.id

        # Get the URL in this UTub
        url_in_this_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_member_of.id, Utub_Urls.user_id != current_user.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url = url_in_this_utub.url_in_utub.url_string
        current_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_member_of.id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_member_of.id, url_id=current_url_id
        ).all()
        associated_tag_ids = [tag.tag_id for tag in associated_tags]

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

        current_user_id = current_user.id

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_STRING: current_url,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_member_of.id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = edit_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after not modifying URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        # Assert entity does not exist
        assert (
            len(
                Utub_Urls.query.filter_by(
                    utub_id=utub_member_of.id,
                    url_id=current_url_id,
                    url_title=NEW_TITLE,
                ).all()
            )
            == 0
        )

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_member_of.id, url_id=current_url_id
            ).all()
        ) == len(associated_tags)


def test_update_url_title_with_empty_title_as_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title to an empty title, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            URL_FORM.CSRF_TOKEN: String containing CSRF token for validation
            URL_FORM.URL_TITLE: Empty string
    THEN verify that title is modified in the database, the url-utub-user associations and url-tag are
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
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_creator_of.id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = edit_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 3
    assert (
        json_response[STD_JSON.ERRORS][URL_FAILURE.URL_TITLE]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        new_url_item: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).first()
        assert new_url_item.url_title == current_title
        assert new_url_item.url_id == current_url_id

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=current_url_id
            ).all()
        ) == len(associated_tags)


def test_update_url_title_as_member_of_other_utub(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN a member that isn't the creator/adder, but is also a creator and member of two other UTubs,
        attempts to modify the URL title to an empty title, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Get the URL of another UTub
        url_not_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_creator_of.id,
            Utub_Urls.user_id != current_user.id,
        ).first()
        utub_id = url_not_in_this_utub.utub_id
        current_url_id = url_not_in_this_utub.url_id
        current_title = url_not_in_this_utub.url_title

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_id, url_id=current_url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 403

    # Assert JSON response from server is valid
    json_response = edit_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL
    assert int(json_response[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        new_url_item: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_id, url_id=current_url_id
        ).first()
        assert new_url_item.url_title == current_title
        assert new_url_item.url_id == current_url_id

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(utub_id=utub_id, url_id=current_url_id).all()
        ) == len(associated_tags)


def test_update_url_title_with_missing_title_field_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with a form missing the title field, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_creator_of.id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 400

    # Assert JSON response from server is valid
    json_response = edit_url_string_title_form.json
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == URL_FAILURE.UNABLE_TO_MODIFY_URL_FORM
    assert int(json_response[STD_JSON.ERROR_CODE]) == 2
    assert (
        json_response[STD_JSON.ERRORS][URL_FAILURE.URL_TITLE]
        == URL_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        new_url_item: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).first()
        assert new_url_item.url_title == current_title
        assert new_url_item.url_id == current_url_id

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=current_url_id
            ).all()
        ) == len(associated_tags)


def test_update_url_title_with_missing_csrf_field_utub_creator(
    add_one_url_and_all_users_to_each_utub_with_all_tags,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN the creator attempts to modify the URL title with a form missing the CSRF token, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
            URL_FORM.URL_TITLE: String containing a new URL title
    THEN verify that the url-utub-user associations and url-tag are unchanged all other URL associations
        are kept consistent, the server sends back a 400 HTTP status code,
        and the server sends back the appropriate HTML response

    Proper HTML response contains the following:
        "<p>The CSRF token is missing.</p>"
    """
    client, csrf_token_string, _, app = login_first_user_without_register

    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Get the URL in this UTub
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id
        ).first()
        current_title = url_in_this_utub.url_title
        current_url_id = url_in_this_utub.url_id

        num_of_url_utub_associations = len(
            Utub_Urls.query.filter_by(
                utub_id=utub_creator_of.id,
                url_id=current_url_id,
                url_title=current_title,
            ).all()
        )
        assert num_of_url_utub_associations == 1

        # Find associated tags with this url
        associated_tags = Url_Tags.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).all()

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_title_form = {URL_FORM.URL_TITLE: current_title + "AAA"}

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_creator_of.id,
            url_id=current_url_id,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in edit_url_string_title_form.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())

        new_url_item: Utub_Urls = Utub_Urls.query.filter_by(
            utub_id=utub_creator_of.id, url_id=current_url_id
        ).first()
        assert new_url_item.url_title == current_title
        assert new_url_item.url_id == current_url_id

        # Check associated tags
        assert len(
            Url_Tags.query.filter_by(
                utub_id=utub_creator_of.id, url_id=current_url_id
            ).all()
        ) == len(associated_tags)


def test_update_url_title_of_nonexistent_url(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN a member, attempts to modify the URL title of a URL that does not exist, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
    with app.app_context():
        utub_creator_of = Utub.query.filter_by(utub_creator=current_user.id).first()
        utub_id = utub_creator_of.id

        # Verify logged in user is creator of this UTub
        assert utub_creator_of.utub_creator == current_user.id

        # Get the URL of another UTub
        NONEXISTENT_URL_ID = 999

        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=utub_id,
            url_id=NONEXISTENT_URL_ID,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 404

    # Assert JSON response from server is valid
    assert U4I_STRINGS.IDENTIFIERS.HTML_404.encode() in edit_url_string_title_form.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())


def test_update_url_title_in_nonexistent_utub(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN a valid creator of a UTub that has members, URL added by the creator, and tags associated with each URL
    WHEN a member, attempts to modify the URL title of a URL in a UTub that does not exist, via a POST to:
        "/url/edit/<utub_id: int>/<url_id: int>" with valid form data, following this format:
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
        num_of_url_tag_assocs = len(Url_Tags.query.all())
        num_of_urls = len(URLS.query.all())
        num_of_url_utubs_assocs = len(Utub_Urls.query.all())

    edit_url_string_title_form = {
        URL_FORM.CSRF_TOKEN: csrf_token_string,
        URL_FORM.URL_TITLE: NEW_TITLE,
    }

    edit_url_string_title_form = client.post(
        url_for(
            EDIT_URL_TITLE_URL,
            utub_id=NONEXISTENT_UTUB_ID,
            url_id=NONEXISTENT_URL_ID,
        ),
        data=edit_url_string_title_form,
    )

    assert edit_url_string_title_form.status_code == 404

    # Assert JSON response from server is valid
    assert U4I_STRINGS.IDENTIFIERS.HTML_404.encode() in edit_url_string_title_form.data

    with app.app_context():
        # Assert database is consistent after newly modified URL
        assert num_of_urls == len(URLS.query.all())
        assert num_of_url_tag_assocs == len(Url_Tags.query.all())
        assert num_of_url_utubs_assocs == len(Utub_Urls.query.all())