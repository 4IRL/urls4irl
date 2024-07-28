from flask import url_for
from flask_login import current_user
import pytest

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS

pytestmark = pytest.mark.tags


def test_delete_tag_from_url_as_utub_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to delete a tag from a URL as the creator of the current UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is deleted,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "Tag deleted from URL",
        TAGS_SUCCESS.TAG : Serialization representing the deleted tag object:
            {
                MODELS.TAG_ID: Integer representing ID of deleted tag,
                TAG_FORM.TAG_STRING: String representing the tag just deleted
            }
        TAGS_SUCCESS.URL_TAG_IDS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG_STILL_IN_UTUB: Boolean for whether this tag still exists in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_this_user_creator_of = utub_this_user_creator_of.id

        # Get a URL and tag association within this UTub
        tag_url_utub_association: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_this_user_creator_of
        ).first()
        tag_id_to_delete = tag_url_utub_association.utub_tag_id
        tag_string_to_delete: str = tag_url_utub_association.utub_tag_item.tag_string
        url_id_to_delete_tag_from = tag_url_utub_association.utub_url_id

        # Get URL serialization for checking
        utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()
        associated_tags = utub_url_association.associated_tag_ids

        # Get all Url-Tag associations count
        initial_url_tag_count = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_creator_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200
    delete_tag_response_json = delete_tag_response.json

    assert delete_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.UTUB_TAG_ID])
        == tag_id_to_delete
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING]
        == tag_string_to_delete
    )
    assert sorted(delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]) == sorted(
        [val for val in associated_tags if val != tag_id_to_delete]
    )

    with app.app_context():
        # Ensure tag still exists
        assert Utub_Tags.query.get(tag_id_to_delete) is not None

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_this_user_creator_of,
                Utub_Url_Tags.utub_url_id == url_id_to_delete_tag_from,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()
        assert sorted(final_utub_url_association.associated_tag_ids) == sorted(
            delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]
        )

        # Ensure proper number of Url-Tag associations in db
        assert Utub_Url_Tags.query.count() == initial_url_tag_count - 1


def test_delete_tag_from_url_as_utub_member(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to delete a tag from a URL as a member of a UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is deleted,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "Tag deleted from URL",
        TAGS_SUCCESS.TAG : Serialization representing the deleted tag object:
            {
                MODELS.TAG_ID: Integer representing ID of deleted tag,
                TAG_FORM.TAG_STRING: String representing the tag just deleted
            }
        TAGS_SUCCESS.URL_TAG_IDS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG_STILL_IN_UTUB: Boolean for whether this tag still exists in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id

        # Get a URL and tag association within this UTub
        tag_url_utub_association: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_this_user_member_of
        ).first()
        tag_id_to_delete = tag_url_utub_association.utub_tag_id
        tag_string_to_delete: str = tag_url_utub_association.utub_tag_item.tag_string
        url_id_to_delete_tag_from = tag_url_utub_association.utub_url_id

        # Get URL serialization for checking
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of,
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()
        associated_tags = url_utub_association.associated_tag_ids

        # Get all Url-Tag associations count
        initial_url_tag_count = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_member_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200
    delete_tag_response_json = delete_tag_response.json

    assert delete_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.UTUB_TAG_ID])
        == tag_id_to_delete
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING]
        == tag_string_to_delete
    )
    assert sorted(delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]) == sorted(
        [val for val in associated_tags if val != tag_id_to_delete]
    )

    with app.app_context():
        # Ensure tag still exists
        assert Utub_Tags.query.get(tag_id_to_delete) is not None

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_this_user_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_delete_tag_from,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()
        assert sorted(final_utub_url_association.associated_tag_ids) == sorted(
            delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]
        )

        # Ensure proper number of Url-Tag associations in db
        assert Utub_Url_Tags.query.count() == initial_url_tag_count - 1


def test_delete_tag_from_url_with_one_tag(
    add_all_urls_and_users_to_each_utub_with_one_tag, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 1 tag associated
    WHEN the user tries to delete a tag from a URL as a member of a UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is deleted,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "Tag deleted from URL",
        TAGS_SUCCESS.TAG : Serialization representing the deleted tag object:
            {
                MODELS.TAG_ID: Integer representing ID of deleted tag,
                TAG_FORM.TAG_STRING: String representing the tag just deleted
            }
        TAGS_SUCCESS.URL_TAG_IDS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG_STILL_IN_UTUB: Boolean for whether this tag still exists in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id

        # Get a URL and tag association within this UTub
        tag_url_utub_association: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_this_user_member_of
        ).first()
        tag_id_to_delete = tag_url_utub_association.utub_tag_id
        tag_string_to_delete = tag_url_utub_association.utub_tag_item.tag_string
        url_id_to_delete_tag_from = tag_url_utub_association.utub_url_id

        # Get URL serialization for checking
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
            Utub_Urls.utub_id == utub_id_this_user_member_of,
        ).first()

        associated_tags = url_utub_association.associated_tag_ids

        # Get all Url-Tag associations count
        initial_url_tag_count = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_member_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200
    delete_tag_response_json = delete_tag_response.json

    assert delete_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.UTUB_TAG_ID])
        == tag_id_to_delete
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING]
        == tag_string_to_delete
    )
    assert sorted(delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]) == sorted(
        [val for val in associated_tags if val != tag_id_to_delete]
    )

    with app.app_context():
        # Ensure tag still exists
        assert Utub_Tags.query.get(tag_id_to_delete) is not None

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_this_user_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_delete_tag_from,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()

        assert sorted(final_utub_url_association.associated_tag_ids) == sorted(
            delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]
        )

        # Ensure proper number of Url-Tag associations in db
        assert Utub_Url_Tags.query.count() == initial_url_tag_count - 1


def test_delete_last_tag_from_utub(
    add_one_url_to_each_utub_one_tag_to_each_url_all_tags_in_utub,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 1 tag associated
    WHEN the user tries to delete a tag from a URL as a member of a UTub, and the tag is not associated with any other
        URLs in that UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is deleted,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly,
        and that the response indicates the tag no longer exists in the UTub

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "Tag deleted from URL",
        TAGS_SUCCESS.TAG : Serialization representing the deleted tag object:
            {
                MODELS.TAG_ID: Integer representing ID of deleted tag,
                TAG_FORM.TAG_STRING: String representing the tag just deleted
            }
        TAGS_SUCCESS.URL_TAG_IDS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG_STILL_IN_UTUB: Boolean for whether this tag still exists in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id

        # Get a URL and tag association within this UTub
        tag_url_utub_association: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_this_user_member_of
        ).first()
        tag_id_to_delete = tag_url_utub_association.utub_tag_id
        tag_string_to_delete = tag_url_utub_association.utub_tag_item.tag_string
        url_id_to_delete_tag_from = tag_url_utub_association.utub_url_id

        # Get URL serialization for checking
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
            Utub_Urls.utub_id == utub_id_this_user_member_of,
        ).first()
        associated_tags = url_utub_association.associated_tag_ids

        # Get all Url-Tag associations count
        initial_url_tag_count = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_member_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200
    delete_tag_response_json = delete_tag_response.json

    assert delete_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.UTUB_TAG_ID])
        == tag_id_to_delete
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING]
        == tag_string_to_delete
    )
    assert sorted(delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]) == sorted(
        [val for val in associated_tags if val != tag_id_to_delete]
    )

    with app.app_context():
        # Ensure tag still exists
        assert Utub_Tags.query.get(tag_id_to_delete) is not None

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_this_user_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_delete_tag_from,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
            == 0
        )

        # Ensure no tags remain in the UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_this_user_member_of
            ).count()
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()

        assert sorted(final_utub_url_association.associated_tag_ids) == sorted(
            delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]
        )

        # Ensure proper number of Url-Tag associations in db
        assert Utub_Url_Tags.query.count() == initial_url_tag_count - 1


def test_delete_tag_from_url_with_five_tags(
    add_one_url_and_all_users_to_each_utub_no_tags,
    add_tags_to_utubs,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 1 URL in each UTub, and each URL has 5 tag associated
    WHEN the user tries to delete a tag from a URL as a member of a UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is deleted,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "Tag deleted from URL",
        TAGS_SUCCESS.TAG : Serialization representing the deleted tag object:
            {
                MODELS.TAG_ID: Integer representing ID of deleted tag,
                TAG_FORM.TAG_STRING: String representing the tag just deleted
            }
        TAGS_SUCCESS.URL_TAG_IDS : Array of integers representing all IDs (including new tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG_STILL_IN_UTUB: Boolean for whether this tag still exists in this UTub
    }
    """
    MAX_NUM_TAGS = 5
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get UTub this user is member of
        utub_this_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id

        # Get all tags
        all_tags = Utub_Tags.query.all()
        num_of_tags_in_db = len(all_tags)

        # Get a URL in this UTub that this user did not add
        url_in_this_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()
        url_id_to_delete_tag_from = url_in_this_utub.id

        # Add five tags to this URL
        for idx in range(MAX_NUM_TAGS):
            previously_added_tag_to_add = all_tags[idx]
            new_url_tag_association = Utub_Url_Tags()
            new_url_tag_association.utub_tag_id = previously_added_tag_to_add.id
            new_url_tag_association.utub_url_id = url_id_to_delete_tag_from
            new_url_tag_association.utub_id = utub_id_this_user_member_of

            db.session.add(new_url_tag_association)

        db.session.commit()

        # Get ID of a tag to delete from this URL
        tag_to_delete: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_this_user_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_delete_tag_from,
        ).first()
        tag_string_to_delete: str = tag_to_delete.utub_tag_item.tag_string
        tag_id_to_delete = tag_to_delete.utub_tag_id

        # Get initial URL serialization
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of,
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()
        associated_tags = url_utub_association.associated_tag_ids

        # Get all Url-Tag associations count
        initial_url_tag_count = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_member_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200
    delete_tag_response_json = delete_tag_response.json

    assert delete_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        delete_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.UTUB_TAG_ID])
        == tag_id_to_delete
    )
    assert (
        delete_tag_response_json[TAGS_SUCCESS.UTUB_TAG][MODELS.TAG_STRING]
        == tag_string_to_delete
    )
    assert sorted(delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]) == sorted(
        [val for val in associated_tags if val != tag_id_to_delete]
    )

    with app.app_context():
        # Ensure tag still exists
        assert Utub_Tags.query.get(tag_id_to_delete) is not None
        assert Utub_Tags.query.count() == num_of_tags_in_db

        # Ensure 4 tags on this URL
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_this_user_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_delete_tag_from,
            ).count()
            == MAX_NUM_TAGS - 1
        )

        # Grab URL-UTub association
        final_utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()
        assert sorted(final_utub_url_association.associated_tag_ids) == sorted(
            delete_tag_response_json[TAGS_SUCCESS.UTUB_URL_TAG_IDS]
        )

        # Ensure proper number of Url-Tag associations in db
        assert Utub_Url_Tags.query.count() == initial_url_tag_count - 1


def test_delete_nonexistent_tag_from_url_as_utub_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to delete a nonexistent tag from a URL as the creator of the current UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 400 HTTP status code, and that the Tag-URL-UTub association still does not exist,
        that the tag does not exist exists, and that the association between URL, UTub, and Tag is recorded properly
    """
    NONEXISTENT_TAG_ID = 999
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_this_user_creator_of = utub_this_user_creator_of.id
        creator_of_utub_id = utub_this_user_creator_of.utub_creator

        # Get a valid URL within this UTub
        valid_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_creator_of
        ).first()
        url_id_to_delete_tag_from = valid_url_in_utub.id

        # Get URL serialization for checking
        initial_url_serialization = valid_url_in_utub.serialized(
            current_user.id, creator_of_utub_id
        )

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_creator_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=NONEXISTENT_TAG_ID,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 404

    with app.app_context():
        # Ensure the Tag-URL-UTub association does not exist
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_this_user_creator_of,
                Utub_Url_Tags.utub_url_id == url_id_to_delete_tag_from,
                Utub_Url_Tags.utub_tag_id == NONEXISTENT_TAG_ID,
            ).first()
            is None
        )

        # Grab URL-UTub association
        final_utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()

        # Ensure final and initial serialization do match
        assert initial_url_serialization == final_utub_url_association.serialized(
            current_user.id, creator_of_utub_id
        )


def test_delete_nonexistent_tag_from_url_as_utub_member(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to delete a nonexistent tag from a URL as the member of the current UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 400 HTTP status code, and that the Tag-URL-UTub association still does not exist,
        that the tag does not exist exists, and that the association between URL, UTub, and Tag is recorded properly
    """
    NONEXISTENT_TAG_ID = 999
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is member of
        utub_this_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id
        creator_of_utub_id = utub_this_user_member_of.utub_creator

        # Get a valid URL within this UTub
        valid_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of
        ).first()
        url_id_to_delete_tag_from = valid_url_in_utub.id

        # Get URL serialization for checking
        initial_url_serialization = valid_url_in_utub.serialized(
            current_user.id, creator_of_utub_id
        )

        # Initial number of Url-Tag associations
        initial_num_tag_url_associations = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_member_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=NONEXISTENT_TAG_ID,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 404

    with app.app_context():
        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_this_user_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_delete_tag_from,
                Utub_Url_Tags.utub_tag_id == NONEXISTENT_TAG_ID,
            ).count()
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_delete_tag_from,
        ).first()

        # Ensure final and initial serialization do match
        assert initial_url_serialization == final_utub_url_association.serialized(
            current_user.id, creator_of_utub_id
        )

        assert Utub_Url_Tags.query.count() == initial_num_tag_url_associations


def test_delete_tag_from_url_but_not_member_of_utub(
    add_one_url_to_each_utub_no_tags,
    add_tags_to_utubs,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all 1 member in each UTub, with 1 URL in each UTub, and each URL has no tags associated with it initially
    WHEN the user tries to delete a newly added tag from a URL as not a member of the UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 403 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association still exists,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.ONLY_UTUB_MEMBERS_delete_TAGS,
    }
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user not a member of
        utub_user_association_not_member_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()
        utub_id_not_member_of = utub_user_association_not_member_of.utub_id
        creator_of_utub_id = utub_user_association_not_member_of.to_utub.utub_creator

        # Grab a tag from db
        tag_to_delete: Utub_Tags = Utub_Tags.query.first()
        tag_id_to_delete = tag_to_delete.id

        # Find a URL in the database associated with this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_not_member_of
        ).first()
        url_id_in_utub = url_utub_association.id

        # Add tag to URL in UTub
        new_tag_url_association = Utub_Url_Tags()
        new_tag_url_association.utub_id = utub_id_not_member_of
        new_tag_url_association.utub_url_id = url_id_in_utub
        new_tag_url_association.utub_tag_id = tag_id_to_delete

        db.session.add(new_tag_url_association)
        db.session.commit()

        initial_url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_not_member_of,
            Utub_Urls.id == url_id_in_utub,
        ).first()

        initial_url_utub_serialization = initial_url_utub_association.serialized(
            current_user.id, creator_of_utub_id
        )

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_not_member_of,
            utub_url_id=url_id_in_utub,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 403
    delete_tag_response_json = delete_tag_response.json

    assert delete_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        delete_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.ONLY_UTUB_MEMBERS_DELETE_TAGS
    )

    with app.app_context():
        # Ensure tag exists
        assert Utub_Tags.query.get(tag_id_to_delete) is not None

        # Ensure tag exists on URL in UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_not_member_of,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
            == 1
        )

        final_url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_in_utub,
        ).first()

        assert initial_url_utub_serialization == final_url_utub_association.serialized(
            current_user.id, creator_of_utub_id
        )


def test_delete_tag_from_url_from_nonexistent_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 1 member in each UTub, with 1 URL in each UTub, and each URL has no tags associated with it initially
    WHEN the user tries to delete a a tag from a URL within a nonexistent UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the tag still exists,
        and that all associations between the URL and tags are still valid
    """
    NONEXISTENT_UTUB_ID = 999

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Grab a valid URL and tag association
        valid_url_tag_association: Utub_Url_Tags = Utub_Url_Tags.query.first()

        tag_id_to_delete = valid_url_tag_association.utub_tag_id
        url_id_to_delete = valid_url_tag_association.utub_url_id
        existing_utub_id = valid_url_tag_association.utub_id
        creator_of_existing_utub_id = (
            valid_url_tag_association.utub_containing_this_url_tag.utub_creator
        )

        num_of_url_tag_associations = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_url_id == url_id_to_delete,
            Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
        ).count()

        # Grab initial UTub-URL serialization
        initial_utub_url_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == existing_utub_id, Utub_Urls.id == url_id_to_delete
        ).first()
        initial_utub_url_serialization = initial_utub_url_association.serialized(
            current_user.id, creator_of_existing_utub_id
        )

        # Initial number of Url-Tag associations
        initial_num_tag_url_associations = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=NONEXISTENT_UTUB_ID,
            utub_url_id=url_id_to_delete,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 404

    with app.app_context():
        # Ensure the valid Tag-URL-UTub association still exists
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == existing_utub_id,
                Utub_Url_Tags.utub_url_id == url_id_to_delete,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
            == 1
        )

        # Ensure Tag still exists
        assert Utub_Tags.query.get(tag_id_to_delete) is not None

        # Ensure URL-UTub association still exists
        final_utub_url_association: Utub_Urls = Utub_Urls.query.get(url_id_to_delete)
        final_utub_url_serialization = final_utub_url_association.serialized(
            current_user.id, creator_of_existing_utub_id
        )

        assert initial_utub_url_serialization == final_utub_url_serialization

        # Ensure URL tag associations are still same count
        assert (
            num_of_url_tag_associations
            == Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == url_id_to_delete,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
        )

        assert Utub_Url_Tags.query.count() == initial_num_tag_url_associations


def test_delete_tag_from_nonexistent_url_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 1 member in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with it
    WHEN the user tries to delete a a tag from a nonexistent URL within a UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the tag still exists, and the UTub
        still has proper associations with the valid tag
    """
    NONEXISTENT_URL_ID = 999

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Grab a valid URL and tag association
        valid_url_tag_association: Utub_Url_Tags = Utub_Url_Tags.query.first()

        tag_id_to_delete = valid_url_tag_association.utub_tag_id
        url_id_to_delete = valid_url_tag_association.utub_url_id
        existing_utub_id = valid_url_tag_association.utub_id

        # Initial number of Url-Tag associations
        initial_num_tag_url_associations = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=existing_utub_id,
            utub_url_id=NONEXISTENT_URL_ID,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 404

    with app.app_context():
        # Ensure the valid Tag-URL-UTub association still exists
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == existing_utub_id,
                Utub_Url_Tags.utub_url_id == url_id_to_delete,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
            == 1
        )

        # Ensure Tag still exists
        assert Utub_Tags.query.get(tag_id_to_delete) is not None

        # Ensure nonexistent URL does not have URL-Tag association in valid UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == existing_utub_id,
                Utub_Url_Tags.utub_url_id == NONEXISTENT_URL_ID,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).first()
            is None
        )

        assert Utub_Url_Tags.query.count() == initial_num_tag_url_associations


def test_delete_tag_with_no_csrf_token(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 1 member in each UTub, with 1 URL in each UTub, and each URL has no tags associated with it initially
    WHEN the user tries to delete a tag from a URL without including the CSRF token
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 400 HTTP status code, that the server sends back the proper
        HTML element indicating a missing CSRF token, and that all valid associations still exist for the tags

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.ONLY_UTUB_MEMBERS_delete_TAGS,
    }
    """

    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Grab a valid URL and tag association
        valid_url_tag_association: Utub_Url_Tags = Utub_Url_Tags.query.first()

        tag_id_to_delete = valid_url_tag_association.utub_tag_id
        url_id_to_delete = valid_url_tag_association.utub_url_id
        existing_utub_id = valid_url_tag_association.utub_id

        # Initial number of Url-Tag associations
        initial_num_tag_url_associations = Utub_Url_Tags.query.count()

    # delete tag from this URL
    delete_tag_form = {}

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=existing_utub_id,
            utub_url_id=url_id_to_delete,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    # Assert invalid response code
    assert delete_tag_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in delete_tag_response.data

    with app.app_context():
        # Ensure the valid Tag-URL-UTub association still exists
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == existing_utub_id,
                Utub_Url_Tags.utub_url_id == url_id_to_delete,
                Utub_Url_Tags.utub_tag_id == tag_id_to_delete,
            ).count()
            == 1
        )

        assert Utub_Url_Tags.query.count() == initial_num_tag_url_associations


def test_delete_tag_from_url_updates_utub_last_updated(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to delete a tag from a URL as the creator of the current UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 200 HTTP status code, and the UTub's last updated
        field is updated
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_this_user_creator_of.last_updated
        utub_id_this_user_creator_of = utub_this_user_creator_of.id

        # Get a URL and tag association within this UTub
        tag_url_utub_association: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_this_user_creator_of
        ).first()
        tag_id_to_delete = tag_url_utub_association.utub_tag_id
        url_id_to_delete_tag_from = tag_url_utub_association.utub_url_id

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_creator_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=tag_id_to_delete,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 200

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_id_this_user_creator_of)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


def test_delete_nonexistent_tag_from_url_does_not_update_utub_last_updated(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to delete a nonexistent tag from a URL as the creator of the current UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:utub_url_tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "urlID": An integer representing URL ID to delete tag from,
            "utub_url_tag_id": An integer representing Tag ID to delete from the URL
    THEN ensure that the server responds with a 400 HTTP status code, and that the UTub's last updated field
        is not updated
    """
    NONEXISTENT_TAG_ID = 999
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_this_user_creator_of.last_updated
        utub_id_this_user_creator_of = utub_this_user_creator_of.id

        # Get a valid URL within this UTub
        valid_url_in_utub: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_creator_of
        ).first()
        url_id_to_delete_tag_from = valid_url_in_utub.id

    # delete tag from this URL
    delete_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    delete_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.DELETE_TAG,
            utub_id=utub_id_this_user_creator_of,
            utub_url_id=url_id_to_delete_tag_from,
            utub_url_tag_id=NONEXISTENT_TAG_ID,
        ),
        data=delete_tag_form,
    )

    assert delete_tag_response.status_code == 404

    with app.app_context():
        current_utub: Utubs = Utubs.query.get(utub_id_this_user_creator_of)
        assert current_utub.last_updated == initial_last_updated
