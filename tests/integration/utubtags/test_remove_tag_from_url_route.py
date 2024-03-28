from flask import url_for
from flask_login import current_user

from src import db
from src.models import Utub, URLS, Utub_Urls, Utub_Users, Tags, Url_Tags
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_SUCCESS
from src.utils import strings as U4I_STRINGS


def test_remove_tag_from_url_as_utub_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to remove a tag from a URL as the creator of the current UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is removed,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : "Tag removed from URL",
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                "tag_string": String representing the tag just added
            }
        "URL" : Serialization representing the URL in this UTub, who it was added by, and associated tags IDs:
            {
                "url_id": Integer reprensenting ID of the URL the tag was added to in this UTub,
                "url_string": String representing the URL,
                "added_by": Integer representing the ID of the user who added this URL,
                "notes": "String representing the URL description,
                "url_tags": Array of integers representing all IDs of tags associated with this URL in this UTub,
                    which should not include the newly added tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
        TAGS_SUCCESS.COUNT_IN_UTUB: Integer representing number of times this tag is left in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_this_user_creator_of = utub_this_user_creator_of.id
        utub_name_this_user_creator_of = utub_this_user_creator_of.name

        # Get a URL and tag association within this UTub
        tag_url_utub_association = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_this_user_creator_of
        ).first()
        tag_id_to_remove = tag_url_utub_association.tag_id
        url_id_to_remove_tag_from = tag_url_utub_association.url_id

        # Ensure the Tag-URL-UTub association does exists any longer
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_creator_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        # Get URL serialization for checking
        initial_url_serialization = (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_this_user_creator_of,
                Utub_Urls.url_id == url_id_to_remove_tag_from,
            )
            .first()
            .serialized
        )

        # Get all Url-Tag associations count
        initial_url_tag_count = len(Url_Tags.query.all())

        # Get tag count for this UTub and tag
        tag_count = Url_Tags.query.filter_by(
            utub_id=utub_id_this_user_creator_of, tag_id=tag_id_to_remove
        ).count()

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=utub_id_this_user_creator_of,
            url_id=url_id_to_remove_tag_from,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 200
    remove_tag_response_json = remove_tag_response.json

    assert remove_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        remove_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(remove_tag_response_json[TAGS_SUCCESS.UTUB_ID])
        == utub_id_this_user_creator_of
    )
    assert (
        remove_tag_response_json[TAGS_SUCCESS.UTUB_NAME]
        == utub_name_this_user_creator_of
    )
    assert int(remove_tag_response_json[TAGS_SUCCESS.COUNT_IN_UTUB]) == tag_count - 1

    tag_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.TAG]
    url_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.URL]

    # Ensure URL-UTub serialization doesn't match what it initially was
    assert url_serialized_on_delete_response != initial_url_serialization

    with app.app_context():
        # Ensure tag still exists
        assert Tags.query.get(tag_id_to_remove) is not None
        assert (
            tag_serialized_on_delete_response
            == Tags.query.get(tag_id_to_remove).serialized
        )

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_creator_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_creator_of,
            Utub_Urls.url_id == url_id_to_remove_tag_from,
        ).first()

        # Ensure final and initial serialization do not match
        assert initial_url_serialization != final_utub_url_association.serialized

        # Ensure server sent back proper serialization
        assert (
            url_serialized_on_delete_response == final_utub_url_association.serialized
        )

        # Ensure proper number of Url-Tag associations in db
        assert len(Url_Tags.query.all()) == initial_url_tag_count - 1


def test_remove_tag_from_url_as_utub_member(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to remove a tag from a URL as a member of a UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is removed,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_REMOVED_FROM_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                "tag_string": String representing the tag just added
            }
        TAGS_SUCCESS.URL : Serialization representing the URL in this UTub, who it was added by, and associated tags IDs:
            {
                "url_id": Integer reprensenting ID of the URL the tag was added to in this UTub,
                "url_string": String representing the URL,
                "added_by": Integer representing the ID of the user who added this URL,
                "notes": "String representing the URL description,
                "url_tags": Array of integers representing all IDs of tags associated with this URL in this UTub,
                    which should not include the newly added tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
        TAGS_SUCCESS.COUNT_IN_UTUB: Integer representing number of times this tag is left in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id
        utub_name_this_user_member_of = utub_this_user_member_of.name

        # Get a URL and tag association within this UTub
        tag_url_utub_association = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_this_user_member_of
        ).first()
        tag_id_to_remove = tag_url_utub_association.tag_id
        url_id_to_remove_tag_from = tag_url_utub_association.url_id

        # Ensure the Tag-URL-UTub association does exists any longer
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_member_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        # Get URL serialization for checking
        initial_url_serialization = (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_this_user_member_of,
                Utub_Urls.url_id == url_id_to_remove_tag_from,
            )
            .first()
            .serialized
        )

        # Get all Url-Tag associations count
        initial_url_tag_count = len(Url_Tags.query.all())

        # Get tag count for this UTub and tag
        tag_count = Url_Tags.query.filter_by(
            utub_id=utub_id_this_user_member_of, tag_id=tag_id_to_remove
        ).count()

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=utub_id_this_user_member_of,
            url_id=url_id_to_remove_tag_from,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 200
    remove_tag_response_json = remove_tag_response.json

    assert remove_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        remove_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(remove_tag_response_json[TAGS_SUCCESS.UTUB_ID])
        == utub_id_this_user_member_of
    )
    assert (
        remove_tag_response_json[TAGS_SUCCESS.UTUB_NAME]
        == utub_name_this_user_member_of
    )
    assert int(remove_tag_response_json[TAGS_SUCCESS.COUNT_IN_UTUB]) == tag_count - 1

    tag_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.TAG]
    url_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.URL]

    # Ensure URL-UTub serialization doesn't match what it initially was
    assert url_serialized_on_delete_response != initial_url_serialization

    with app.app_context():
        # Ensure tag still exists
        assert Tags.query.get(tag_id_to_remove) is not None
        assert (
            tag_serialized_on_delete_response
            == Tags.query.get(tag_id_to_remove).serialized
        )

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_member_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of,
            Utub_Urls.url_id == url_id_to_remove_tag_from,
        ).first()

        # Ensure final and initial serialization do not match
        assert initial_url_serialization != final_utub_url_association.serialized

        # Ensure server sent back proper serialization
        assert (
            url_serialized_on_delete_response == final_utub_url_association.serialized
        )

        # Ensure proper number of Url-Tag associations in db
        assert len(Url_Tags.query.all()) == initial_url_tag_count - 1


def test_remove_tag_from_url_with_one_tag(
    add_all_urls_and_users_to_each_utub_with_one_tag, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 1 tag associated
    WHEN the user tries to remove a tag from a URL as a member of a UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is removed,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_REMOVED_FROM_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                "tag_string": String representing the tag just added
            }
        TAGS_SUCCESS.URL : Serialization representing the URL in this UTub, who it was added by, and associated tags IDs:
            {
                "url_id": Integer reprensenting ID of the URL the tag was added to in this UTub,
                "url_string": String representing the URL,
                "added_by": Integer representing the ID of the user who added this URL,
                "notes": "String representing the URL description,
                "url_tags": Array of integers representing all IDs of tags associated with this URL in this UTub,
                    which should not include the newly added tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
        TAGS_SUCCESS.COUNT_IN_UTUB: Integer representing number of times this tag is left in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id
        utub_name_this_user_member_of = utub_this_user_member_of.name

        # Get a URL and tag association within this UTub
        tag_url_utub_association = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_this_user_member_of
        ).first()
        tag_id_to_remove = tag_url_utub_association.tag_id
        url_id_to_remove_tag_from = tag_url_utub_association.url_id

        # Ensure the Tag-URL-UTub association does exist
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_member_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        # Get URL serialization for checking
        initial_url_serialization = (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_this_user_member_of,
                Utub_Urls.url_id == url_id_to_remove_tag_from,
            )
            .first()
            .serialized
        )

        # Get all Url-Tag associations count
        initial_url_tag_count = len(Url_Tags.query.all())

        # Get tag count for this UTub and tag
        tag_count = Url_Tags.query.filter_by(
            utub_id=utub_id_this_user_member_of, tag_id=tag_id_to_remove
        ).count()

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=utub_id_this_user_member_of,
            url_id=url_id_to_remove_tag_from,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 200
    remove_tag_response_json = remove_tag_response.json

    assert remove_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        remove_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(remove_tag_response_json[TAGS_SUCCESS.UTUB_ID])
        == utub_id_this_user_member_of
    )
    assert (
        remove_tag_response_json[TAGS_SUCCESS.UTUB_NAME]
        == utub_name_this_user_member_of
    )
    assert int(remove_tag_response_json[TAGS_SUCCESS.COUNT_IN_UTUB]) == tag_count - 1

    tag_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.TAG]
    url_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.URL]

    # Ensure URL-UTub serialization doesn't match what it initially was
    assert url_serialized_on_delete_response != initial_url_serialization

    with app.app_context():
        # Ensure tag still exists
        assert Tags.query.get(tag_id_to_remove) is not None
        assert (
            tag_serialized_on_delete_response
            == Tags.query.get(tag_id_to_remove).serialized
        )

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_member_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of,
            Utub_Urls.url_id == url_id_to_remove_tag_from,
        ).first()

        # Ensure final and initial serialization do not match
        assert initial_url_serialization != final_utub_url_association.serialized

        # Ensure server sent back proper serialization
        assert (
            url_serialized_on_delete_response == final_utub_url_association.serialized
        )

        # Ensure proper number of Url-Tag associations in db
        assert len(Url_Tags.query.all()) == initial_url_tag_count - 1


def test_remove_last_tag_from_utub(
    add_one_url_to_each_utub_one_tag, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 1 tag associated
    WHEN the user tries to remove a tag from a URL as a member of a UTub, and the tag is not associated with any other
        URLs in that UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is removed,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly,
        and that the response indicates the tag no longer exists in the UTub

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_REMOVED_FROM_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                "tag_string": String representing the tag just added
            }
        TAGS_SUCCESS.URL : Serialization representing the URL in this UTub, who it was added by, and associated tags IDs:
            {
                "url_id": Integer reprensenting ID of the URL the tag was added to in this UTub,
                "url_string": String representing the URL,
                "added_by": Integer representing the ID of the user who added this URL,
                "notes": "String representing the URL description,
                "url_tags": Array of integers representing all IDs of tags associated with this URL in this UTub,
                    which should not include the newly added tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
        TAGS_SUCCESS.COUNT_IN_UTUB: Integer representing number of times this tag is left in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_member_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id
        utub_name_this_user_member_of = utub_this_user_member_of.name

        # Get a URL and tag association within this UTub
        tag_url_utub_association = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_this_user_member_of
        ).first()
        tag_id_to_remove = tag_url_utub_association.tag_id
        url_id_to_remove_tag_from = tag_url_utub_association.url_id

        # Ensure the Tag-URL-UTub association does exist
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_member_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        # Get URL serialization for checking
        initial_url_serialization = (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_this_user_member_of,
                Utub_Urls.url_id == url_id_to_remove_tag_from,
            )
            .first()
            .serialized
        )

        # Get all Url-Tag associations count
        initial_url_tag_count = len(Url_Tags.query.all())

        # Get tag count for this UTub and tag
        tag_count = Url_Tags.query.filter_by(
            utub_id=utub_id_this_user_member_of, tag_id=tag_id_to_remove
        ).count()

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=utub_id_this_user_member_of,
            url_id=url_id_to_remove_tag_from,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 200
    remove_tag_response_json = remove_tag_response.json

    assert remove_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        remove_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(remove_tag_response_json[TAGS_SUCCESS.UTUB_ID])
        == utub_id_this_user_member_of
    )
    assert (
        remove_tag_response_json[TAGS_SUCCESS.UTUB_NAME]
        == utub_name_this_user_member_of
    )
    assert (
        int(remove_tag_response_json[TAGS_SUCCESS.COUNT_IN_UTUB]) == tag_count - 1 == 0
    )

    tag_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.TAG]
    url_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.URL]

    # Ensure URL-UTub serialization doesn't match what it initially was
    assert url_serialized_on_delete_response != initial_url_serialization

    with app.app_context():
        # Ensure tag still exists
        assert Tags.query.get(tag_id_to_remove) is not None
        assert (
            tag_serialized_on_delete_response
            == Tags.query.get(tag_id_to_remove).serialized
        )

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_member_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of,
            Utub_Urls.url_id == url_id_to_remove_tag_from,
        ).first()

        # Ensure final and initial serialization do not match
        assert initial_url_serialization != final_utub_url_association.serialized

        # Ensure server sent back proper serialization
        assert (
            url_serialized_on_delete_response == final_utub_url_association.serialized
        )

        # Ensure proper number of Url-Tag associations in db
        assert len(Url_Tags.query.all()) == initial_url_tag_count - 1


def test_remove_tag_from_url_with_five_tags(
    add_five_tags_to_db_from_same_user, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 1 URL in each UTub, and each URL has 5 tag associated
    WHEN the user tries to remove a tag from a URL as a member of a UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association is removed,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_REMOVED_FROM_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                "tag_string": String representing the tag just added
            }
        TAGS_SUCCESS.URL : Serialization representing the URL in this UTub, who it was added by, and associated tags IDs:
            {
                "url_id": Integer reprensenting ID of the URL the tag was added to in this UTub,
                "url_string": String representing the URL,
                "added_by": Integer representing the ID of the user who added this URL,
                "notes": "String representing the URL description,
                "url_tags": Array of integers representing all IDs of tags associated with this URL in this UTub,
                    which should not include the newly added tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
        TAGS_SUCCESS.COUNT_IN_UTUB: Integer representing number of times this tag is left in this UTub
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get UTub this user is member of
        utub_user_is_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        utub_id_user_is_member_of = utub_user_is_member_of.id
        utub_name_this_user_member_of = utub_user_is_member_of.name

        # Get all tags
        all_tags = Tags.query.all()
        num_of_tags_in_db = len(all_tags)

        # Get a URL in this UTub that this user did not add
        url_in_this_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id != current_user.id,
        ).first()
        url_id_in_this_utub = url_in_this_utub.url_id

        # Add five tags to this URL
        for idx in range(5):
            previously_added_tag_to_add = all_tags[idx]
            new_url_tag_association = Url_Tags()
            new_url_tag_association.tag_id = previously_added_tag_to_add.id
            new_url_tag_association.url_id = url_id_in_this_utub
            new_url_tag_association.utub_id = utub_id_user_is_member_of

            db.session.add(new_url_tag_association)

        db.session.commit()

        # Ensure 5 tags on this URL
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_member_of,
                    Url_Tags.url_id == url_id_in_this_utub,
                ).all()
            )
            == 5
        )

        # Get ID of a tag to remove from this URL
        tag_to_remove = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_user_is_member_of,
            Url_Tags.url_id == url_id_in_this_utub,
        ).first()
        tag_id_to_remove = tag_to_remove.tag_id

        # Get URL serialization for checking
        initial_url_serialization = (
            Utub_Urls.query.filter(
                Utub_Urls.utub_id == utub_id_user_is_member_of,
                Utub_Urls.url_id == url_id_in_this_utub,
            )
            .first()
            .serialized
        )

        # Get all Url-Tag associations count
        initial_url_tag_count = len(Url_Tags.query.all())

        # Get tag count for this UTub and tag
        tag_count = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_member_of, tag_id=tag_id_to_remove
        ).count()

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_in_this_utub,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 200
    remove_tag_response_json = remove_tag_response.json

    assert remove_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        remove_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_REMOVED_FROM_URL
    )
    assert (
        int(remove_tag_response_json[TAGS_SUCCESS.UTUB_ID]) == utub_id_user_is_member_of
    )
    assert (
        remove_tag_response_json[TAGS_SUCCESS.UTUB_NAME]
        == utub_name_this_user_member_of
    )
    assert int(remove_tag_response_json[TAGS_SUCCESS.COUNT_IN_UTUB]) == tag_count - 1

    tag_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.TAG]
    url_serialized_on_delete_response = remove_tag_response_json[TAGS_SUCCESS.URL]

    # Ensure URL-UTub serialization doesn't match what it initially was
    assert url_serialized_on_delete_response != initial_url_serialization

    with app.app_context():
        # Ensure tag still exists
        assert Tags.query.get(tag_id_to_remove) is not None
        assert len(Tags.query.all()) == num_of_tags_in_db
        assert (
            tag_serialized_on_delete_response
            == Tags.query.get(tag_id_to_remove).serialized
        )

        # Ensure 4 tags on this URL
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_member_of,
                    Url_Tags.url_id == url_id_in_this_utub,
                ).all()
            )
            == 4
        )
        # Grab URL-UTub association
        final_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.url_id == url_id_in_this_utub,
        ).first()

        # Ensure final and initial serialization do not match
        assert initial_url_serialization != final_utub_url_association.serialized

        # Ensure server sent back proper serialization
        assert (
            url_serialized_on_delete_response == final_utub_url_association.serialized
        )

        # Ensure proper number of Url-Tag associations in db
        assert len(Url_Tags.query.all()) == initial_url_tag_count - 1


def test_remove_nonexistent_tag_from_url_as_utub_creator(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to remove a nonexistent tag from a URL as the creator of the current UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 400 HTTP status code, and that the Tag-URL-UTub association still does not exist,
        that the tag does not exist exists, and that the association between URL, UTub, and Tag is recorded properly
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is creator of
        utub_this_user_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_this_user_creator_of = utub_this_user_creator_of.id

        # Get a tag ID that does not exist
        tag_id_to_remove = 0
        all_tags = Tags.query.all()
        all_tag_ids = [tag.id for tag in all_tags]
        while tag_id_to_remove in all_tag_ids:
            tag_id_to_remove += 1

        # Get a valid URL within this UTub
        valid_url_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_creator_of
        ).first()
        url_id_to_remove_tag_from = valid_url_in_utub.url_id

        # Ensure the Tag-URL-UTub association does not exist
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_creator_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Get URL serialization for checking
        initial_url_serialization = valid_url_in_utub.serialized

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=utub_id_this_user_creator_of,
            url_id=url_id_to_remove_tag_from,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 404

    with app.app_context():
        # Ensure tag still exists
        assert Tags.query.get(tag_id_to_remove) is None

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_creator_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_creator_of,
            Utub_Urls.url_id == url_id_to_remove_tag_from,
        ).first()

        # Ensure final and initial serialization do match
        assert initial_url_serialization == final_utub_url_association.serialized


def test_remove_nonexistent_tag_from_url_as_utub_member(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 3 members in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with
    WHEN the user tries to remove a nonexistent tag from a URL as the member of the current UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 400 HTTP status code, and that the Tag-URL-UTub association still does not exist,
        that the tag does not exist exists, and that the association between URL, UTub, and Tag is recorded properly
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get a UTub this user is member of
        utub_this_user_member_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        utub_id_this_user_member_of = utub_this_user_member_of.id

        # Get a tag ID that does not exist
        tag_id_to_remove = 0
        all_tags = Tags.query.all()
        all_tag_ids = [tag.id for tag in all_tags]
        while tag_id_to_remove in all_tag_ids:
            tag_id_to_remove += 1

        # Get a valid URL within this UTub
        valid_url_in_utub = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of
        ).first()
        url_id_to_remove_tag_from = valid_url_in_utub.url_id

        # Ensure the Tag-URL-UTub association does not exist
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_member_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Get URL serialization for checking
        initial_url_serialization = valid_url_in_utub.serialized

        # Initial number of Url-Tag associations
        initial_num_tag_url_associations = len(Url_Tags.query.all())

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=utub_id_this_user_member_of,
            url_id=url_id_to_remove_tag_from,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 404

    with app.app_context():
        # Ensure tag still exists
        assert Tags.query.get(tag_id_to_remove) is None

        # Ensure the Tag-URL-UTub association does not exist any longer
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_this_user_member_of,
                    Url_Tags.url_id == url_id_to_remove_tag_from,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Grab URL-UTub association
        final_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_this_user_member_of,
            Utub_Urls.url_id == url_id_to_remove_tag_from,
        ).first()

        # Ensure final and initial serialization do match
        assert initial_url_serialization == final_utub_url_association.serialized

        assert len(Url_Tags.query.all()) == initial_num_tag_url_associations


def test_remove_tag_from_url_but_not_member_of_utub(
    add_one_url_to_each_utub_no_tags,
    add_tags_to_database,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with all 1 member in each UTub, with 1 URL in each UTub, and each URL has no tags associated with it initially
    WHEN the user tries to remove a newly added tag from a URL as not a member of the UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 403 HTTP status code, that the proper JSON response
        is sent by the server, and that the Tag-URL-UTub association still exists,
        that the tag still exists, and that the association between URL, UTub, and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.ONLY_UTUB_MEMBERS_REMOVE_TAGS,
    }
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user not a member of
        utub_user_association_not_member_of = Utub_Users.query.filter(
            Utub_Users.user_id != current_user.id
        ).first()
        utub_id_not_member_of = utub_user_association_not_member_of.utub_id

        # Grab a tag from db
        tag_to_add = Tags.query.first()
        tag_id_to_add = tag_to_add.id

        # Find a URL in the database associated with this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_not_member_of
        ).first()
        url_id_in_utub = url_utub_association.url_id

        # Ensure tag does not exist on URL in UTub
        assert (
            len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_not_member_of).all())
            == 0
        )

        # Add tag to URL in UTub
        new_tag_url_association = Url_Tags()
        new_tag_url_association.utub_id = utub_id_not_member_of
        new_tag_url_association.url_id = url_id_in_utub
        new_tag_url_association.tag_id = tag_id_to_add

        db.session.add(new_tag_url_association)
        db.session.commit()

        # Ensure tag exists on URL in UTub
        assert (
            len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_not_member_of).all())
            == 1
        )

        initial_url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_not_member_of,
            Utub_Urls.url_id == url_id_in_utub,
        ).first()

        initial_url_utub_serialization = initial_url_utub_association.serialized

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=utub_id_not_member_of,
            url_id=url_id_in_utub,
            tag_id=tag_id_to_add,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 403
    remove_tag_response_json = remove_tag_response.json

    assert remove_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        remove_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.ONLY_UTUB_MEMBERS_REMOVE_TAGS
    )

    with app.app_context():
        # Ensure tag exists
        assert Tags.query.get(tag_id_to_add) is not None

        # Ensure tag exists on URL in UTub
        assert (
            len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_not_member_of).all())
            == 1
        )

        final_url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_not_member_of,
            Utub_Urls.url_id == url_id_in_utub,
        ).first()

        assert initial_url_utub_serialization == final_url_utub_association.serialized


def test_remove_tag_from_url_from_nonexistent_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 1 member in each UTub, with 1 URL in each UTub, and each URL has no tags associated with it initially
    WHEN the user tries to remove a a tag from a URL within a nonexistent UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the tag still exists,
        and that all associations between the URL and tags are still valid
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this user not a member of
        nonexistent_utub_id = 0
        all_utub_ids = [utub.id for utub in Utub.query.all()]
        while nonexistent_utub_id in all_utub_ids:
            nonexistent_utub_id += 1

        # Grab a valid URL and tag association
        valid_url_tag_association = Url_Tags.query.first()

        tag_id_to_remove = valid_url_tag_association.tag_id
        url_id_to_remove = valid_url_tag_association.url_id
        existing_utub_id = valid_url_tag_association.utub_id

        # Ensure URL-Tag association exists inside a valid UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == existing_utub_id,
                    Url_Tags.url_id == url_id_to_remove,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        num_of_url_tag_associations = len(
            Url_Tags.query.filter(
                Url_Tags.url_id == url_id_to_remove, Url_Tags.tag_id == tag_id_to_remove
            ).all()
        )

        # Ensure URL-Tag association does not exist in nonexistent UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == nonexistent_utub_id,
                    Url_Tags.url_id == url_id_to_remove,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Grab initial UTub-URL serialization
        initial_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == existing_utub_id, Utub_Urls.url_id == url_id_to_remove
        ).first()
        initial_utub_url_serialization = initial_utub_url_association.serialized

        # Initial number of Url-Tag associations
        initial_num_tag_url_associations = len(Url_Tags.query.all())

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=nonexistent_utub_id,
            url_id=url_id_to_remove,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 404

    with app.app_context():
        # Ensure the valid Tag-URL-UTub association still exists
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == existing_utub_id,
                    Url_Tags.url_id == url_id_to_remove,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        # Ensure Tag still exists
        assert Tags.query.get(tag_id_to_remove) is not None

        # Ensure URL-UTub association still exists
        final_utub_url_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == existing_utub_id, Utub_Urls.url_id == url_id_to_remove
        ).first()
        final_utub_url_serialization = final_utub_url_association.serialized

        assert initial_utub_url_serialization == final_utub_url_serialization

        # Ensure URL tag associations are still same count
        assert num_of_url_tag_associations == len(
            Url_Tags.query.filter(
                Url_Tags.url_id == url_id_to_remove, Url_Tags.tag_id == tag_id_to_remove
            ).all()
        )

        assert len(Url_Tags.query.all()) == initial_num_tag_url_associations


def test_remove_tag_from_nonexistent_url_utub(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 1 member in each UTub, with 3 URLs in each UTub, and each URL has 3 tags associated with it
    WHEN the user tries to remove a a tag from a nonexistent URL within a UTub
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the tag still exists, and the UTub
        still has proper associations with the valid tag
    """

    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find URL that does not exist
        nonexistent_url_id = 0
        all_url_ids = [utub.id for utub in URLS.query.all()]
        while nonexistent_url_id in all_url_ids:
            nonexistent_url_id += 1

        # Grab a valid URL and tag association
        valid_url_tag_association = Url_Tags.query.first()

        tag_id_to_remove = valid_url_tag_association.tag_id
        url_id_to_remove = valid_url_tag_association.url_id
        existing_utub_id = valid_url_tag_association.utub_id

        # Ensure URL-Tag association exists inside UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == existing_utub_id,
                    Url_Tags.url_id == url_id_to_remove,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        # Ensure nonexistent URL does not have URL-Tag association in valid UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == existing_utub_id,
                    Url_Tags.url_id == nonexistent_url_id,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        # Initial number of Url-Tag associations
        initial_num_tag_url_associations = len(Url_Tags.query.all())

    # Remove tag from this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
    }

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=existing_utub_id,
            url_id=nonexistent_url_id,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    assert remove_tag_response.status_code == 404

    with app.app_context():
        # Ensure the valid Tag-URL-UTub association still exists
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == existing_utub_id,
                    Url_Tags.url_id == url_id_to_remove,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        # Ensure Tag still exists
        assert Tags.query.get(tag_id_to_remove) is not None

        # Ensure nonexistent URL does not have URL-Tag association in valid UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == existing_utub_id,
                    Url_Tags.url_id == nonexistent_url_id,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 0
        )

        assert len(Url_Tags.query.all()) == initial_num_tag_url_associations


def test_remove_tag_with_no_csrf_token(
    add_all_urls_and_users_to_each_utub_with_all_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with all 1 member in each UTub, with 1 URL in each UTub, and each URL has no tags associated with it initially
    WHEN the user tries to remove a tag from a URL without including the CSRF token
        - By DELETE to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to remove tag from,
            "tag_id": An integer representing Tag ID to remove from the URL
    THEN ensure that the server responds with a 400 HTTP status code, that the server sends back the proper
        HTML element indicating a missing CSRF token, and that all valid associations still exist for the tags

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : TAGS_FAILURE.ONLY_UTUB_MEMBERS_REMOVE_TAGS,
    }
    """

    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Grab a valid URL and tag association
        valid_url_tag_association = Url_Tags.query.first()

        tag_id_to_remove = valid_url_tag_association.tag_id
        url_id_to_remove = valid_url_tag_association.url_id
        existing_utub_id = valid_url_tag_association.utub_id

        # Ensure URL-Tag association exists inside UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == existing_utub_id,
                    Url_Tags.url_id == url_id_to_remove,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        # Initial number of Url-Tag associations
        initial_num_tag_url_associations = len(Url_Tags.query.all())

    # Remove tag from this URL
    add_tag_form = {}

    remove_tag_response = client.delete(
        url_for(
            ROUTES.TAGS.REMOVE_TAG,
            utub_id=existing_utub_id,
            url_id=url_id_to_remove,
            tag_id=tag_id_to_remove,
        ),
        data=add_tag_form,
    )

    # Assert invalid response code
    assert remove_tag_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in remove_tag_response.data

    with app.app_context():
        # Ensure the valid Tag-URL-UTub association still exists
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == existing_utub_id,
                    Url_Tags.url_id == url_id_to_remove,
                    Url_Tags.tag_id == tag_id_to_remove,
                ).all()
            )
            == 1
        )

        assert len(Url_Tags.query.all()) == initial_num_tag_url_associations
