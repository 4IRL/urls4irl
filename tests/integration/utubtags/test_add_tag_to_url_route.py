from flask import url_for
from flask_login import current_user
import pytest

from src import db
from src.models.tags import Tags
from src.models.urls import Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from tests.models_for_test import all_tag_strings
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS

pytestmark = pytest.mark.tags


def test_add_fresh_tag_to_valid_url_as_utub_creator(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator of the UTub in each UTub, and no existing tags or
        Tag-URL-UTub associations, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to add a new tag to the URL they added
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag-URL-UTub association exists where it didn't before,
        that a new Tag exists, and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            }
        TAGS_SUCCESS.URL_TAGS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub, added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id
        associated_tags = url_utub_association.associated_tags

        # Ensure this tag does not exist in the database
        init_num_of_tag_in_db = len(
            Tags.query.filter(Tags.tag_string == tag_to_add).all()
        )

        # Ensure no Tag-URL association exists in this UTub
        init_num_of_tags_on_urls = len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 200

    # Ensure json response from server is valid
    add_tag_response_json = add_tag_response.json
    new_tag_id = int(add_tag_response_json[TAGS_SUCCESS.TAG][MODEL_STRS.TAG_ID])
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_ADDED_TO_URL
    assert add_tag_response_json[TAGS_SUCCESS.TAG][MODEL_STRS.TAG_STRING] == tag_to_add
    assert sorted(add_tag_response_json[TAGS_SUCCESS.URL_TAGS]) == sorted(
        associated_tags + [new_tag_id]
    )

    with app.app_context():
        # Ensure a tag exists
        assert len(Tags.query.all()) == 1
        assert (
            len(Tags.query.filter(Tags.tag_string == tag_to_add).all())
            == init_num_of_tag_in_db + 1
        )
        assert Tags.query.filter(Tags.tag_string == tag_to_add).first() is not None

        # Ensure a Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == init_num_of_tags_on_urls + 1
        )

        # Ensure correct total count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations + 1


def test_add_fresh_tag_to_valid_url_as_utub_member(
    add_all_urls_and_users_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 users in each UTub, and no existing tags or Tag-URL-UTub associations,
        and the currently logged in user is a member of a UTub, and one URL exists in the UTub, added by another member
    WHEN the user tries to add a new tag to the URL
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag-URL-UTub association exists where it didn't before,
        that a new Tag exists, and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            }
        TAGS_SUCCESS.URL_TAGS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure no tags
        assert len(Tags.query.all()) == 0

        # Find UTub this current user is member of
        utub_user_is_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub, not added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id
        associated_tags = url_utub_association.associated_tags

        # Ensure this tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 0

        # Ensure no Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 200

    # Ensure json response from server is valid
    add_tag_response_json = add_tag_response.json
    new_tag_id = int(add_tag_response_json[TAGS_SUCCESS.TAG][MODEL_STRS.TAG_ID])
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_ADDED_TO_URL
    assert add_tag_response_json[TAGS_SUCCESS.TAG][MODEL_STRS.TAG_STRING] == tag_to_add
    assert sorted(add_tag_response_json[TAGS_SUCCESS.URL_TAGS]) == sorted(
        associated_tags + [new_tag_id]
    )

    with app.app_context():
        # Ensure a tag exists
        assert len(Tags.query.all()) == 1

        assert Tags.query.filter(Tags.tag_string == tag_to_add).first() is not None

        # Ensure a Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == 1
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations + 1


def test_add_existing_tag_to_valid_url_as_utub_creator(
    add_one_url_to_each_utub_no_tags,
    add_tags_to_database,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator of the UTub in each UTub, and no existing tags or
        Tag-URL-UTub associations, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to add a tag, that was already created by another user, to the URL they added
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag-URL-UTub association exists where it didn't before,
        that a new Tag does not exist, and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            }
        TAGS_SUCCESS.URL_TAGS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub, added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id
        associated_tags = url_utub_association.associated_tags

        # Ensure this tag exists in the database
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 1
        tag_that_exists = Tags.query.filter(Tags.tag_string == tag_to_add).first()
        tag_id_that_exists = tag_that_exists.id

        # Ensure no Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 200

    # Ensure json response from server is valid
    add_tag_response_json = add_tag_response.json
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_ADDED_TO_URL
    assert add_tag_response_json[TAGS_SUCCESS.TAG][MODEL_STRS.TAG_STRING] == tag_to_add
    assert (
        int(add_tag_response_json[TAGS_SUCCESS.TAG][MODEL_STRS.TAG_ID])
        == tag_id_that_exists
    )
    assert sorted(add_tag_response_json[TAGS_SUCCESS.URL_TAGS]) == sorted(
        associated_tags + [tag_id_that_exists]
    )

    with app.app_context():
        # Ensure a tag exists
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure a Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                    Utub_Url_Tags.tag_id == tag_that_exists.id,
                ).all()
            )
            == 1
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations + 1


def test_add_existing_tag_to_valid_url_as_utub_member(
    add_all_urls_and_users_to_each_utub_no_tags,
    add_tags_to_database,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, and no existing tags or
        Tag-URL-UTub associations, and the currently logged in user is a member (not creator) of a UTub, and 3 URLs
        exist, all added to each UTub by each member
    WHEN the user tries to add a tag, that was already added by another user, to a URL they did not add
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag-URL-UTub association exists where it didn't before,
        that a new Tag does not exist, and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            }
        TAGS_SUCCESS.URL_TAGS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Find UTub this current user is creator of
        utub_user_is_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id
        associated_tags = url_utub_association.associated_tags

        # Ensure this tag exists in the database
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 1
        tag_that_exists = Tags.query.filter(Tags.tag_string == tag_to_add).first()
        tag_id_that_exists = tag_that_exists.id

        # Ensure no Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 200

    # Ensure json response from server is valid
    add_tag_response_json = add_tag_response.json
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_ADDED_TO_URL
    assert add_tag_response_json[TAGS_SUCCESS.TAG][MODEL_STRS.TAG_STRING] == tag_to_add
    assert (
        int(add_tag_response_json[TAGS_SUCCESS.TAG][MODEL_STRS.TAG_ID])
        == tag_id_that_exists
    )
    assert sorted(add_tag_response_json[TAGS_SUCCESS.URL_TAGS]) == sorted(
        associated_tags + [tag_id_that_exists]
    )

    with app.app_context():
        # Ensure a tag exists
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure a Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                    Utub_Url_Tags.tag_id == tag_that_exists.id,
                ).all()
            )
            == 1
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations + 1


def test_add_duplicate_tag_to_valid_url_as_utub_creator(
    add_all_urls_and_users_to_each_utub_with_one_tag, login_first_user_without_register
):
    """
    GIVEN 3 users, 3 UTubs, 3 URLs, and 3 Tags, with only the creator of the UTub in each UTub, and the currently logged in user is a creator of a UTub,
        and 3 URLs exists in each UTub, added by the user with the same ID as the URL, and each URL has a tag on it that has the identical tag ID as the URL
    WHEN the user tries to add a tag to a URL that already has that tag on it
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response is sent by the server,
        and that no new Tag-URL-UTub association exists, that a new Tag does not exist, and that the association between URL and Tag is serialized properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : "Failure",
        STD_JSON.MESSAGE : "URL already has this tag",
        "Error_code" : 3
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        creator_of_utub_id = utub_user_is_creator_of.utub_creator

        # Get URL that is in this UTub, added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id
        url_serialization_for_check = url_utub_association.serialized(
            current_user.id, creator_of_utub_id
        )

        # Ensure tag is already on this URL and pull that tag object
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            > 0
        )

        num_of_tag_associations_with_url_in_utub = len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        tag_on_url_in_utub_association = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.url_id == url_id_to_add_tag_to,
        ).first()

        tag_on_url_in_utub = tag_on_url_in_utub_association.tag_item

        # Ensure tag exists
        assert (
            len(
                Tags.query.filter(
                    Tags.tag_string == tag_on_url_in_utub.tag_string
                ).all()
            )
            == 1
        )

        tag_to_add = tag_on_url_in_utub.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 400

    # Ensure json response from server is valid
    add_tag_response_json = add_tag_response.json
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.TAG_ALREADY_ON_URL
    assert int(add_tag_response_json[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Ensure no new tags exist
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure no new tags exist on this URL
        assert num_of_tag_associations_with_url_in_utub == len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        url_utub_tag_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
            Utub_Urls.url_id == url_id_to_add_tag_to,
        ).first()

        assert (
            url_utub_tag_association.serialized(current_user.id, creator_of_utub_id)
            == url_serialization_for_check
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_duplicate_tag_to_valid_url_as_utub_member(
    add_all_urls_and_users_to_each_utub_with_one_tag, login_first_user_without_register
):
    """
    GIVEN 3 users, 3 UTubs, 3 URLs, and 3 Tags, with only the creator of the UTub in each UTub, and the currently logged in user is a member of a UTub,
        and 3 URLs exists in each UTub, added by the user with the same ID as the URL, and each URL has a tag on it that has the identical tag ID as the URL
    WHEN the user tries to add a tag to a URL that already has that tag on it
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 400 HTTP status code, that the proper JSON response is sent by the server,
        and that no new Tag-URL-UTub association exists, that a new Tag does not exist, and that the association between URL and Tag is serialized properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.TAG_ALREADY_ON_URL,
        STD_JSON.ERROR_CODE : 3
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Find UTub this current user is creator of
        utub_user_is_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_user_is_member_of = utub_user_is_member_of.id
        creator_of_utub_id = utub_user_is_member_of.utub_creator

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub, not added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id
        url_serialization_for_check = url_utub_association.serialized(
            current_user.id, creator_of_utub_id
        )

        # Ensure tag is already on this URL and pull that tag object
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            > 0
        )

        num_of_tag_associations_with_url_in_utub = len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        tag_on_url_in_utub_association = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.url_id == url_id_to_add_tag_to,
        ).first()

        tag_on_url_in_utub = tag_on_url_in_utub_association.tag_item

        # Ensure tag exists
        assert (
            len(
                Tags.query.filter(
                    Tags.tag_string == tag_on_url_in_utub.tag_string
                ).all()
            )
            == 1
        )

        tag_to_add = tag_on_url_in_utub.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 400

    # Ensure json response from server is valid
    add_tag_response_json = add_tag_response.json
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.TAG_ALREADY_ON_URL
    assert int(add_tag_response_json[STD_JSON.ERROR_CODE]) == 3

    with app.app_context():
        # Ensure no new tags exist
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure no new tags exist on this URL
        assert num_of_tag_associations_with_url_in_utub == len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        # URLs exist in UTub only once
        url_utub_tag_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.url_id == url_id_to_add_tag_to,
        ).first()

        assert (
            url_utub_tag_association.serialized(current_user.id, creator_of_utub_id)
            == url_serialization_for_check
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_nonexistent_url_as_utub_creator(
    add_tags_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users, 3 UTubs, and 3 Tags, with every user in every UTub, and the currently logged in user is a creator of a UTub,
        and no URLs exists, but 3 Tags exist
    WHEN the user tries to add a tag to a nonexistent URL
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 404 HTTP status code, and that no new Tag-URL-UTub association exists,
        that a new Tag does not exist, that a new URL does not exist, and that the association between URL and Tag is serialized properly
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure tag exists
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 1

        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Assert no URLs exist
        assert len(Urls.query.all()) == 0
        url_id_to_add_tag_to = 1

        # Ensure no URL-Tag associations exist for this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of
                ).all()
            )
            == 0
        )

        num_of_tag_associations_with_url_in_utub = len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tags exist
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure no URLs were added
        assert len(Urls.query.all()) == 0

        # Ensure no URL-Tag associations exist for this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of
                ).all()
            )
            == 0
        )

        # Ensure no new tags exist on this URL
        assert num_of_tag_associations_with_url_in_utub == len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_nonexistent_url_as_utub_member(
    add_tags_to_database, every_user_in_every_utub, login_first_user_without_register
):
    """
    GIVEN 3 users, 3 UTubs, and 3 Tags, with every user in every UTub, and the currently logged in user is a member of a UTub,
        and no URLs exists, but 3 Tags exist
    WHEN the user tries to add a tag to a nonexistent URL
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 404 HTTP status code, and that no new Tag-URL-UTub association exists,
        that a new Tag does not exist, that a new URL does not exist, and that the association between URL and Tag is serialized properly
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure tag exists
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 1

        # Find UTub this current user is member of
        utub_user_is_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Assert no URLs exist
        assert len(Urls.query.all()) == 0
        url_id_to_add_tag_to = 1

        # Ensure no URL-Tag associations exist for this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of
                ).all()
            )
            == 0
        )

        num_of_tag_associations_with_url_in_utub = len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tags exist
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure no URLs were added
        assert len(Urls.query.all()) == 0

        # Ensure no URL-Tag associations exist for this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of
                ).all()
            )
            == 0
        )

        # Ensure no new tags exist on this URL
        assert num_of_tag_associations_with_url_in_utub == len(
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.url_id == url_id_to_add_tag_to,
            ).all()
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_url_in_nonexistent_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users, 3 UTubs, and 3 Tags, with every user in every UTub, and the currently logged in user is a member of a UTub,
        and 3 URLs exists, 3 Tags exist, and every tag exists on every URL
    WHEN the user tries to add a tag to a URL to a UTub that doesn't exist
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 404 HTTP status code, and that no new Tag-URL-UTub association exists,
        that a new Tag does not exist, that a new URL does not exist, that a new UTub does not exist,
        and that the association between URL and Tag is serialized properly
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure tag exists
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 1

        # Find UTub that doesn't exist
        utub_id_that_does_not_exist = 0
        all_utub_ids = [int(utub.id) for utub in Utubs.query.all()]

        while utub_id_that_does_not_exist in all_utub_ids:
            utub_id_that_does_not_exist += 1

        # Ensure UTub does not exist
        assert Utubs.query.get(utub_id_that_does_not_exist) is None
        num_of_utubs_in_db = len(Utubs.query.all())

        # Assert URLs exist
        assert len(Urls.query.all()) > 0
        num_of_urls_in_db = len(Urls.query.all())

        url_to_add_to: Urls = Urls.query.first()
        url_id_to_add_tag_to = url_to_add_to.id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_that_does_not_exist,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tags exist
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure no URLs were added
        assert len(Urls.query.all()) == num_of_urls_in_db

        # Ensure UTub does not exist
        assert Utubs.query.get(utub_id_that_does_not_exist) is None
        assert len(Utubs.query.all()) == num_of_utubs_in_db

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_url_in_utub_user_is_not_member_of(
    add_one_url_to_each_utub_no_tags,
    add_tags_to_database,
    login_first_user_without_register,
):
    """
    GIVEN 3 users, 3 UTubs, and 3 Tags, with only one user (the creator) in each UTub, and the currently logged in user is a creator of a UTub,
        and one URL exists in each UTub, and 3 Tags exist but are not applied to any URLs
    WHEN the user tries to add a tag to a URL in a UTub they are not a member or creator of
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 404 HTTP status code, the server sends the proper JSON response,
        and that no new Tag-URL-UTub association exists, that a new Tag does not exist, that a new URL does not exist,
        and that the association between URL and Tag is serialized properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "Unable to add tag to this URL",
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure tag exists
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 1

        # Find UTub that current user is not member of
        utub_user_association_not_member_of = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()
        utub_user_not_member_of: Utubs = utub_user_association_not_member_of.to_utub
        utub_id_that_user_not_member_of = utub_user_not_member_of.id
        creator_of_utub_id: int = utub_user_not_member_of.utub_creator

        # Ensure user not in UTub
        assert current_user not in [
            user.to_user for user in utub_user_not_member_of.members
        ]

        num_of_users_in_utub = len(utub_user_not_member_of.members)

        # Assert URLs exist
        assert len(Urls.query.all()) > 0
        num_of_urls_in_db = len(Urls.query.all())

        # Find URL in this UTub
        url_association_with_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_that_user_not_member_of
        ).first()
        url_id_for_url_in_utub: int = url_association_with_this_utub.standalone_url.id
        url_serialization_for_check = url_association_with_this_utub.serialized(
            current_user.id, creator_of_utub_id
        )

        # Ensure no tags on this URL already
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_that_user_not_member_of,
                    Utub_Url_Tags.url_id == url_id_for_url_in_utub,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_that_user_not_member_of,
            url_id=url_id_for_url_in_utub,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 403

    add_tag_response_json = add_tag_response.json
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL
    )
    assert int(add_tag_response_json[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Ensure no new tags exist
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure no URLs were added
        assert len(Urls.query.all()) == num_of_urls_in_db

        # Get UTub again
        utub_that_user_not_member_of: Utubs = Utubs.query.get(
            utub_id_that_user_not_member_of
        )
        assert num_of_users_in_utub == len(utub_that_user_not_member_of.members)

        # Ensure no tags on this URL still
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_that_user_not_member_of,
                    Utub_Url_Tags.url_id == url_id_for_url_in_utub,
                ).all()
            )
            == 0
        )

        # Ensure URL in UTub serialization is still same
        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_that_user_not_member_of,
                Utub_Urls.url_id == url_id_for_url_in_utub,
            )
            .first()
            .serialized(current_user.id, creator_of_utub_id)
            == url_serialization_for_check
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_url_not_in_utub(
    add_one_url_to_each_utub_no_tags,
    add_tags_to_database,
    login_first_user_without_register,
):
    """
    GIVEN 3 users, 3 UTubs, and 3 Tags, with only one user (the creator) in each UTub, and the currently logged in user is a creator of a UTub,
        and one URL exists in each UTub, and 3 Tags exist but are not applied to any URLs
    WHEN the user tries to add a tag to a URL that doesn't exist in their UTub
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 404 HTTP status code, and that no new Tag-URL-UTub association exists, that a new Tag does not exist,
        that a new URL does not exist, and that the association between URL and Tag is serialized properly
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure tags already in database
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure tag exists
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 1

        # Find UTub that current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Assert URLs exist
        assert len(Urls.query.all()) > 0
        num_of_urls_in_db = len(Urls.query.all())

        # Find URL that isn't in this UTub
        url_association_not_with_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id != utub_id_user_is_creator_of
        ).first()
        url_id_for_url_not_in_utub: int = (
            url_association_not_with_this_utub.standalone_url.id
        )

        # Find number of URLs in this UTub
        num_of_urls_in_utub = len(utub_user_is_creator_of.utub_urls)

        # Ensure no association between this URL and this UTub
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_user_is_creator_of,
                    Utub_Urls.url_id == url_id_for_url_not_in_utub,
                ).all()
            )
            == 0
        )

        # Ensure no association with Tags, this URL, and this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_for_url_not_in_utub,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_for_url_not_in_utub,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tags exist
        assert len(Tags.query.all()) == len(all_tag_strings)

        # Ensure no URLs were added
        assert len(Urls.query.all()) == num_of_urls_in_db

        # Ensure same number of URLs in UTub
        utub_user_is_creator_of_for_check = Utubs.query.get(utub_id_user_is_creator_of)
        assert len(utub_user_is_creator_of_for_check.utub_urls) == num_of_urls_in_utub

        # Ensure no association between this URL and this UTub
        assert (
            len(
                Utub_Urls.query.filter(
                    Utub_Urls.utub_id == utub_id_user_is_creator_of,
                    Utub_Urls.url_id == url_id_for_url_not_in_utub,
                ).all()
            )
            == 0
        )

        # Ensure no association with Tags, this URL, and this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_for_url_not_in_utub,
                ).all()
            )
            == 0
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_url_with_five_tags_as_utub_creator(
    add_five_tags_to_db_from_same_user,
    add_tags_to_database,
    login_first_user_without_register,
):
    """
    GIVEN 3 users, 3 UTubs, and 3 Tags, with all users in each UTub, and the currently logged in user is a creator of a UTub,
        one URL exists in each UTub, 8 Tags exist, and 5 tags are applied to a single URL in a UTub
    WHEN the user tries to add a tag to the same URL with 5 tags in a UTub they are a creator of
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 400 HTTP status code, the server sends the proper JSON response,
        and that no new Tag-URL-UTub association exists, that a new Tag does not exist, and that the association between URL and Tag is serialized properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "URLs can only have 5 tags max",
        STD_JSON.ERROR_CODE : 2
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Get UTub this user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        creator_of_utub_id = utub_user_is_creator_of.utub_creator

        # Get all tags
        all_tags: list[Tags] = Tags.query.all()
        num_of_tags_in_db = len(all_tags)

        # Get a URL in this UTub that this user added
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_id_in_this_utub = url_in_this_utub.url_id

        # Add five tags to this URL
        for idx in range(5):
            previously_added_tag_to_add = all_tags[idx]
            new_url_tag_association = Utub_Url_Tags()
            new_url_tag_association.tag_id = previously_added_tag_to_add.id
            new_url_tag_association.url_id = url_id_in_this_utub
            new_url_tag_association.utub_id = utub_id_user_is_creator_of

            db.session.add(new_url_tag_association)

        db.session.commit()

        # Ensure 5 tags on this URL
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_in_this_utub,
                ).all()
            )
            == 5
        )

        # Get a new tag to add
        new_tag_to_add: Tags = Tags.query.filter(Tags.tag_string == tag_to_add).first()
        new_tag_id_to_add = new_tag_to_add.id

        # Get the URL-UTub serialization for checking later
        url_serialization_for_check = (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_user_is_creator_of,
                Utub_Urls.user_id == current_user.id,
            )
            .first()
            .serialized(current_user.id, creator_of_utub_id)
        )

        # Ensure this tag isn't on the URL in this UTub already
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_in_this_utub,
                    Utub_Url_Tags.tag_id == new_tag_id_to_add,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_in_this_utub,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 400

    add_tag_response_json = add_tag_response.json
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.FIVE_TAGS_MAX
    assert int(add_tag_response_json[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure no new tags exist, accounting for additional
        assert len(Tags.query.all()) == num_of_tags_in_db

        # Ensure this tag isn't on the URL in this UTub already
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_in_this_utub,
                    Utub_Url_Tags.tag_id == new_tag_id_to_add,
                ).all()
            )
            == 0
        )

        # Ensure 5 tags on this URL
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_in_this_utub,
                ).all()
            )
            == 5
        )

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_user_is_creator_of,
                Utub_Urls.url_id == url_id_in_this_utub,
            )
            .first()
            .serialized(current_user.id, creator_of_utub_id)
            == url_serialization_for_check
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_url_with_five_tags_as_utub_member(
    add_five_tags_to_db_from_same_user,
    add_tags_to_database,
    login_second_user_without_register,
):
    """
    GIVEN 3 users, 3 UTubs, and 3 Tags, with all users in each UTub, and the currently logged in user is a member of a UTub,
        one URL exists in each UTub, 8 Tags exist, and 5 tags are applied to a single URL that this user did add
    WHEN the user tries to add a tag to the same URL with 5 tags in a UTub they are a member of
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 400 HTTP status code, the server sends the proper JSON response,
        and that no new Tag-URL-UTub association exists, that a new Tag does not exist, and that the association between URL and Tag is serialized properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.FIVE_TAGS_MAX,
        STD_JSON.ERROR_CODE : 2
    }
    """
    client, csrf_token, _, app = login_second_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Get UTub this user is member of
        utub_user_is_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_user_is_member_of = utub_user_is_member_of.id
        creator_of_utub_id = utub_user_is_member_of.utub_creator

        # Get all tags
        all_tags: list[Tags] = Tags.query.all()
        num_of_tags_in_db = len(all_tags)

        # Get a URL in this UTub that this user did not add
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()
        url_id_in_this_utub = url_in_this_utub.url_id

        # Add five tags to this URL
        for idx in range(5):
            previously_added_tag_to_add = all_tags[idx]
            new_url_tag_association = Utub_Url_Tags()
            new_url_tag_association.tag_id = previously_added_tag_to_add.id
            new_url_tag_association.url_id = url_id_in_this_utub
            new_url_tag_association.utub_id = utub_id_user_is_member_of

            db.session.add(new_url_tag_association)

        db.session.commit()

        # Ensure 5 tags on this URL
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_in_this_utub,
                ).all()
            )
            == 5
        )

        # Get a new tag to add
        new_tag_to_add = Tags.query.filter(Tags.tag_string == tag_to_add).first()
        new_tag_id_to_add = new_tag_to_add.id

        # Get the URL-UTub serialization for checking later
        url_serialization_for_check = (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_user_is_member_of,
                Utub_Urls.user_id != current_user.id,
            )
            .first()
            .serialized(current_user.id, creator_of_utub_id)
        )

        # Ensure this tag isn't on the URL in this UTub already
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_in_this_utub,
                    Utub_Url_Tags.tag_id == new_tag_id_to_add,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_in_this_utub,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 400

    add_tag_response_json = add_tag_response.json
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert add_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.FIVE_TAGS_MAX
    assert int(add_tag_response_json[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure no new tags exist, accounting for additional
        assert len(Tags.query.all()) == num_of_tags_in_db

        # Ensure this tag isn't on the URL in this UTub already
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_in_this_utub,
                    Utub_Url_Tags.tag_id == new_tag_id_to_add,
                ).all()
            )
            == 0
        )

        # Ensure 5 tags on this URL
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                    Utub_Url_Tags.url_id == url_id_in_this_utub,
                ).all()
            )
            == 5
        )

        assert (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_user_is_member_of,
                Utub_Urls.url_id == url_id_in_this_utub,
            )
            .first()
            .serialized(current_user.id, creator_of_utub_id)
            == url_serialization_for_check
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_valid_url_valid_utub_missing_tag_field(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator of the UTub in each UTub, and no existing tags or
        Tag-URL-UTub associations, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to add a new tag to the URL they added but the TAG_FORM.TAG_STRING field is missing
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 404 HTTP status code, that the proper JSON response
        is sent by the server, and that no new Tag-URL-UTub association exists where it didn't before,
        that no new Tag exists, and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
        STD_JSON.ERROR_CODE : 4,
        STD_JSON.ERRORS: {
            TAG_FORM.TAG_STRING: ["This field is required."]
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure no tags
        assert len(Tags.query.all()) == 0

        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        creator_of_utub_id = utub_user_is_creator_of.utub_creator

        # Get URL that is in this UTub, added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id
        url_serialization_for_check = url_utub_association.serialized(
            current_user.id, creator_of_utub_id
        )

        # Ensure this tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 0

        # Ensure no Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 400

    # Ensure json response from server is valid
    add_tag_response_json = add_tag_response.json
    assert add_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        add_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL
    )
    assert int(add_tag_response_json[STD_JSON.ERROR_CODE]) == 4
    assert (
        add_tag_response_json[STD_JSON.ERRORS][TAG_FORM.TAG_STRING]
        == TAGS_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Ensure no tags
        assert len(Tags.query.all()) == 0

        # Ensure same serialization for URL
        assert url_serialization_for_check == Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first().serialized(current_user.id, creator_of_utub_id)

        # Ensure this tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 0

        # Ensure no Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == 0
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_tag_to_valid_url_valid_utub_missing_csrf_token(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator of the UTub in each UTub, and no existing tags or
        Tag-URL-UTub associations, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to add a new tag to the URL they added but the TAG_FORM.CSRF_TOKEN is missing
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 404 HTTP status code, that the proper JSON response
        is sent by the server, and that no new Tag-URL-UTub association exists where it didn't before,
        that no new Tag exists, and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL,
        STD_JSON.ERROR_CODE : 4,
        STD_JSON.ERRORS: {
            TAG_FORM.TAG_STRING: ["This field is required."]
        }
    }
    """
    client, _, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Ensure no tags
        assert len(Tags.query.all()) == 0

        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        creator_of_utub_id = utub_user_is_creator_of.utub_creator

        # Get URL that is in this UTub, added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id
        url_serialization_for_check = url_utub_association.serialized(
            current_user.id, creator_of_utub_id
        )

        # Ensure this tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 0

        # Ensure no Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Utub_Url_Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    # Assert invalid response code
    assert add_tag_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in add_tag_response.data

    with app.app_context():
        # Ensure no tags
        assert len(Tags.query.all()) == 0

        # Ensure same serialization for URL
        assert url_serialization_for_check == Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first().serialized(current_user.id, creator_of_utub_id)

        # Ensure this tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == tag_to_add).all()) == 0

        # Ensure no Tag-URL association exists in this UTub
        assert (
            len(
                Utub_Url_Tags.query.filter(
                    Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Utub_Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == 0
        )

        # Ensure correct count of Url-Tag associations
        assert len(Utub_Url_Tags.query.all()) == initial_num_url_tag_associations


def test_add_fresh_tag_to_url_updates_utub_last_updated(
    add_one_url_to_each_utub_no_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator of the UTub in each UTub, and no existing tags or
        Tag-URL-UTub associations, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to add a new tag to the URL they added
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 200 HTTP status code, and the UTub's last updated
        field is updated
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_user_is_creator_of.last_updated
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub, added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 200

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_id_user_is_creator_of)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


def test_add_existing_tag_to_url_updates_utub_last_updated(
    add_one_url_to_each_utub_no_tags,
    add_tags_to_database,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator of the UTub in each UTub, and no existing tags or
        Tag-URL-UTub associations, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to add a tag, that was already created by another user, to the URL they added
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 200 HTTP status code, and the UTub's last updated
        field is updated
    """
    client, csrf_token, _, app = login_first_user_without_register
    tag_to_add = all_tag_strings[0]

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_user_is_creator_of.last_updated
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub, added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 200

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_id_user_is_creator_of)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


def test_add_duplicate_tag_to_url_does_not_update_utub_last_updated(
    add_all_urls_and_users_to_each_utub_with_one_tag, login_first_user_without_register
):
    """
    GIVEN 3 users, 3 UTubs, 3 URLs, and 3 Tags, with only the creator of the UTub in each UTub, and the currently logged in user is a creator of a UTub,
        and 3 URLs exists in each UTub, added by the user with the same ID as the URL, and each URL has a tag on it that has the identical tag ID as the URL
    WHEN the user tries to add a tag to a URL that already has that tag on it
        - By POST to "/utubs/<int:utub_id>/urls/<int:url_id>/tags where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
    THEN ensure that the server responds with a 400 HTTP status code, and the UTub's last updated field is not updated
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_user_is_creator_of.last_updated
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub, added by this user
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_add_tag_to = url_in_this_utub.id

        tag_on_url_in_utub_association = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.url_id == url_id_to_add_tag_to,
        ).first()

        tag_on_url_in_utub = tag_on_url_in_utub_association.tag_item

        # Ensure tag exists
        assert (
            len(
                Tags.query.filter(
                    Tags.tag_string == tag_on_url_in_utub.tag_string
                ).all()
            )
            == 1
        )

        tag_to_add = tag_on_url_in_utub.tag_string

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_add,
    }

    add_tag_response = client.post(
        url_for(
            ROUTES.TAGS.ADD_TAG,
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
        ),
        data=add_tag_form,
    )

    assert add_tag_response.status_code == 400

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_id_user_is_creator_of)
        assert current_utub.last_updated == initial_last_updated
