from flask import url_for
from flask_login import current_user

from src.models import Utub, Utub_Urls, Tags, Url_Tags
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_NO_CHANGE, TAGS_SUCCESS
from src.utils import strings as U4I_STRINGS

NEW_TAG = "Fruitilicious"


def test_modify_tag_with_fresh_tag_on_valid_url_as_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag with a tag not currently in the database
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag exists, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_MODIFIED_ON_URL,
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
                    which should include the newly added tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        utub_name_user_is_creator_of = utub_user_is_creator_of.name

        # Ensure user is in this UTub
        assert current_user in [
            user.to_user for user in utub_user_is_creator_of.members
        ]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Ensure this new tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == NEW_TAG).all()) == 0

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: NEW_TAG,
    }

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_MODIFIED_ON_URL
    assert (
        int(modify_tag_response_json[TAGS_SUCCESS.UTUB_ID]) == utub_id_user_is_creator_of
    )
    assert (
        modify_tag_response_json[TAGS_SUCCESS.UTUB_NAME] == utub_name_user_is_creator_of
    )

    url_serialization_from_server = modify_tag_response_json[TAGS_SUCCESS.URL]
    tag_serialization_from_server = modify_tag_response_json[TAGS_SUCCESS.TAG]

    with app.app_context():
        # Ensure a new tag exists
        assert len(Tags.query.all()) == num_tags + 1

        new_tag_from_server = Tags.query.filter(Tags.tag_string == NEW_TAG).first()

        # Assert tag is created
        assert new_tag_from_server is not None

        assert new_tag_from_server.serialized == tag_serialization_from_server

        url_utub_tag_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
            Utub_Urls.url_id == url_id_to_add_tag_to,
        ).first()

        assert url_utub_tag_association.serialized == url_serialization_from_server

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations


def test_modify_tag_with_fresh_tag_on_valid_url_as_utub_member(
    add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag with a tag not currently in the database
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag exists, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_MODIFIED_ON_URL,
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
                    which should include the newly added tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).all()

        i = 0
        while current_user not in [
            user.to_user for user in utubs_user_is_not_creator_of[i].members
        ]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id
        utub_name_user_is_member_of = utub_user_is_member_of.name

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Ensure this new tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == NEW_TAG).all()) == 0

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: NEW_TAG,
    }

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_MODIFIED_ON_URL
    assert (
        int(modify_tag_response_json[TAGS_SUCCESS.UTUB_ID]) == utub_id_user_is_member_of
    )
    assert (
        modify_tag_response_json[TAGS_SUCCESS.UTUB_NAME] == utub_name_user_is_member_of
    )

    url_serialization_from_server = modify_tag_response_json[TAGS_SUCCESS.URL]
    tag_serialization_from_server = modify_tag_response_json[TAGS_SUCCESS.TAG]

    with app.app_context():
        # Ensure a new tag exists
        assert len(Tags.query.all()) == num_tags + 1

        new_tag_from_server = Tags.query.filter(Tags.tag_string == NEW_TAG).first()

        # Assert tag is created
        assert new_tag_from_server is not None

        assert new_tag_from_server.serialized == tag_serialization_from_server

        url_utub_tag_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id == current_user.id,
            Utub_Urls.url_id == url_id_to_add_tag_to,
        ).first()

        assert url_utub_tag_association.serialized == url_serialization_from_server

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_member_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations


def test_modify_tag_with_other_tag_on_valid_url_as_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag by changing it to a tag already contained in the database
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_MODIFIED_ON_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag,
                TAG_FORM.TAG_STRING: String representing the tag just added
            }
        TAGS_SUCCESS.URL : Serialization representing the URL in this UTub, who it was added by, and associated tags IDs:
            {
                "url_id": Integer reprensenting ID of the URL the tag was added to in this UTub,
                "url_string": String representing the URL,
                "added_by": Integer representing the ID of the user who added this URL,
                "notes": "String representing the URL description,
                "url_tags": Array of integers representing all IDs of tags associated with this URL in this UTub,
                    which should include the tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        utub_name_user_is_creator_of = utub_user_is_creator_of.name

        # Ensure user is in this UTub
        assert current_user in [
            user.to_user for user in utub_user_is_creator_of.members
        ]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Find another tag that isn't the one already on the URL
        tag_to_replace_with = Tags.query.filter(
            Tags.tag_string != tag_on_url.tag_item.tag_string
        ).first()
        new_tag_string = tag_to_replace_with.tag_string

        # Ensure this tag does not have an association with this URL on this UTub
        assert (
            len(
                Url_Tags.query.filter_by(
                    utub_id=utub_id_user_is_creator_of,
                    url_id=url_id_to_add_tag_to,
                    tag_id=tag_to_replace_with.id,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: new_tag_string,
    }

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_MODIFIED_ON_URL
    assert (
        int(modify_tag_response_json[TAGS_SUCCESS.UTUB_ID]) == utub_id_user_is_creator_of
    )
    assert (
        modify_tag_response_json[TAGS_SUCCESS.UTUB_NAME] == utub_name_user_is_creator_of
    )

    url_serialization_from_server = modify_tag_response_json[TAGS_SUCCESS.URL]
    tag_serialization_from_server = modify_tag_response_json[TAGS_SUCCESS.TAG]

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        tag_from_server = Tags.query.get(tag_to_replace_with.id)
        assert tag_from_server.serialized == tag_serialization_from_server

        url_utub_tag_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of,
            Utub_Urls.user_id == current_user.id,
            Utub_Urls.url_id == url_id_to_add_tag_to,
        ).first()

        assert url_utub_tag_association.serialized == url_serialization_from_server

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations


def test_modify_tag_with_other_tag_on_valid_url_as_utub_member(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag with a tag not currently in the database
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.SUCCESS,
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_MODIFIED_ON_URL,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            }
        TAGS_SUCCESS.URL : Serialization representing the URL in this UTub, who it was added by, and associated tags IDs:
            {
                "url_id": Integer reprensenting ID of the URL the tag was added to in this UTub,
                "url_string": String representing the URL,
                "added_by": Integer representing the ID of the user who added this URL,
                "notes": "String representing the URL description,
                "url_tags": Array of integers representing all IDs of tags associated with this URL in this UTub,
                    which should include the newly added tag
            }
        TAGS_SUCCESS.UTUB_ID : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        TAGS_SUCCESS.UTUB_NAME: String representing name of UTub that the URL, user, and tag association is in
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).all()

        i = 0
        while current_user not in [
            user.to_user for user in utubs_user_is_not_creator_of[i].members
        ]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id
        utub_name_user_is_member_of = utub_user_is_member_of.name

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Find tag in database that isn't this tag
        tag_from_database = Tags.query.filter(
            Tags.tag_string != tag_on_url.tag_item.tag_string
        ).first()

        # Ensure this new tag does not have an association with this URL
        assert (
            len(
                Url_Tags.query.filter_by(
                    utub_id=utub_id_user_is_member_of,
                    url_id=url_id_to_add_tag_to,
                    tag_id=tag_from_database.id,
                ).all()
            )
            == 0
        )

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_from_database.tag_string,
    }

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_MODIFIED_ON_URL
    assert (
        int(modify_tag_response_json[TAGS_SUCCESS.UTUB_ID]) == utub_id_user_is_member_of
    )
    assert (
        modify_tag_response_json[TAGS_SUCCESS.UTUB_NAME] == utub_name_user_is_member_of
    )

    url_serialization_from_server = modify_tag_response_json[TAGS_SUCCESS.URL]
    tag_serialization_from_server = modify_tag_response_json[TAGS_SUCCESS.TAG]

    with app.app_context():
        # Ensure a new tag does not exist
        assert len(Tags.query.all()) == num_tags

        # Get tag from database
        tag_from_database_after_add = Tags.query.get(tag_from_database.id)
        assert tag_from_database_after_add.serialized == tag_serialization_from_server

        url_utub_tag_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id == current_user.id,
            Utub_Urls.url_id == url_id_to_add_tag_to,
        ).first()

        assert url_utub_tag_association.serialized == url_serialization_from_server

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_member_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations


def test_modify_tag_with_same_tag_on_valid_url_as_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag by changing it to the same tag
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE : TAGS_NO_CHANGE.TAG_NOT_MODIFIED,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Ensure user is in this UTub
        assert current_user in [
            user.to_user for user in utub_user_is_creator_of.members
        ]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to
        ).first()
        tag_string_on_url = tag_on_url.tag_item.tag_string
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_string_on_url,
    }

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_NO_CHANGE.TAG_NOT_MODIFIED

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            len(
                Url_Tags.query.filter_by(
                    utub_id=utub_id_user_is_creator_of,
                    url_id=url_id_to_add_tag_to,
                    tag_id=curr_tag_id_on_url,
                ).all()
            )
            == 1
        )


def test_modify_tag_with_same_tag_on_valid_url_as_utub_member(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag with the same tag
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE : TAGS_NO_CHANGE.TAG_NOT_MODIFIED,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).all()

        i = 0
        while current_user not in [
            user.to_user for user in utubs_user_is_not_creator_of[i].members
        ]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        curr_tag_string = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: curr_tag_string,
    }

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_NO_CHANGE.TAG_NOT_MODIFIED

    with app.app_context():
        # Ensure a new tag does not exist
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_member_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            len(
                Url_Tags.query.filter_by(
                    utub_id=utub_id_user_is_member_of,
                    url_id=url_id_to_add_tag_to,
                    tag_id=curr_tag_id_on_url,
                ).all()
            )
            == 1
        )


def test_modify_tag_with_tag_already_on_url_as_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag by changing it to a tag already on the URL
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "Tag already on URL",
        STD_JSON.ERROR_CODE: 2
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Ensure user is in this UTub
        assert current_user in [
            user.to_user for user in utub_user_is_creator_of.members
        ]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to
        ).first()
        tag_string_on_url = tag_on_url.tag_item.tag_string
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get tag to change to on this URL
        tag_to_change_to_on_url = Url_Tags.query.filter(
            Url_Tags.utub_id == utub_id_user_is_creator_of,
            Url_Tags.url_id == url_id_to_add_tag_to,
            Url_Tags.tag_id != curr_tag_id_on_url,
        ).first()

        tag_to_change_to_string = tag_to_change_to_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_change_to_string,
    }

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_creator_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 400

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.TAG_ALREADY_ON_URL
    assert int(modify_tag_response_json[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_creator_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            len(
                Url_Tags.query.filter_by(
                    utub_id=utub_id_user_is_creator_of,
                    url_id=url_id_to_add_tag_to,
                    tag_id=curr_tag_id_on_url,
                ).all()
            )
            == 1
        )


def test_modify_tag_on_another_utub_url(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag in another UTub
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, and the Tag-URL-UTub association is not modified

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "Only UTub members can modify tags",
        STD_JSON.ERROR_CODE : 1
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).all()

        i = 0
        while current_user in [
            user.to_user for user in utubs_user_is_not_creator_of[i].members
        ]:
            i += 1

        utub_user_is_not_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_not_member_of = utub_user_is_not_member_of.id

        # Ensure user is not in this UTub
        assert current_user not in [
            user.to_user for user in utub_user_is_not_member_of.members
        ]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_not_member_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_not_member_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_not_member_of, url_id=url_id_to_add_tag_to
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        curr_tag_string = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: curr_tag_string,
    }

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_not_member_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 404

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        modify_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.ONLY_UTUB_MEMBERS_MODIFY_TAGS
    )
    assert int(modify_tag_response_json[STD_JSON.ERROR_CODE]) == 1

    with app.app_context():
        # Ensure a new tag does not exist
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_not_member_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            len(
                Url_Tags.query.filter_by(
                    utub_id=utub_id_user_is_not_member_of,
                    url_id=url_id_to_add_tag_to,
                    tag_id=curr_tag_id_on_url,
                ).all()
            )
            == 1
        )


def test_modify_tag_on_invalid_url_as_utub_creator(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a nonexistent URL's tag by changing it to the same tag
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.NO_CHANGE,
        STD_JSON.MESSAGE : TAGS_NO_CHANGE.TAG_NOT_MODIFIED,
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Ensure user is in this UTub
        assert current_user in [
            user.to_user for user in utub_user_is_creator_of.members
        ]

        # Ensure invalid URL ID is nonexistent
        invalid_url_id = -1

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_creator_of,
            url_id=invalid_url_id,
            tag_id=1,
        ),
        data=add_tag_form,
    )
    assert modify_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations


def test_modify_tag_on_url_in_nonexistent_utub(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag in a nonexistent UTub
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 404 HTTP status code, proper response is sent by the server,
        and that a new Tag does not exist
    """
    client, csrf_token, _, app = login_first_user_without_register

    invalid_url_id = -1
    invalid_utub_id = -1

    with app.app_context():
        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=invalid_utub_id,
            url_id=invalid_url_id,
            tag_id=1,
        ),
        data=add_tag_form,
    )
    assert modify_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations


def test_modify_tag_with_missing_tag_field(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag but doesn't include tag field in form
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is not modified,

    Proper JSON response is as follows:
    {
        STD_JSON.STATUS : STD_JSON.FAILURE,
        STD_JSON.MESSAGE : "Unable to add tag to this URL",
        STD_JSON.ERROR_CODE : 3,
        STD_JSON.ERRORS: Object representing array of errors pertaining to relevant fields
        {
            TAG_FORM.TAG_STRING : Array of errors associated with tag_string field
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).all()

        i = 0
        while current_user not in [
            user.to_user for user in utubs_user_is_not_creator_of[i].members
        ]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    assert modify_tag_response.status_code == 400

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert (
        modify_tag_response_json[STD_JSON.MESSAGE]
        == TAGS_FAILURE.UNABLE_TO_ADD_TAG_TO_URL
    )
    assert int(modify_tag_response_json[STD_JSON.ERROR_CODE]) == 3
    assert (
        modify_tag_response_json[STD_JSON.ERRORS][TAG_FORM.TAG_STRING]
        == TAGS_FAILURE.FIELD_REQUIRED
    )

    with app.app_context():
        # Ensure a new tag does not exist
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_member_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            len(
                Url_Tags.query.filter_by(
                    utub_id=utub_id_user_is_member_of,
                    url_id=url_id_to_add_tag_to,
                    tag_id=curr_tag_id_on_url,
                ).all()
            )
            == 1
        )


def test_modify_tag_with_missing_csrf_token(
    add_two_users_and_all_urls_to_each_utub_with_one_tag,
    login_first_user_without_register,
):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag but doesn't include csrf token
        - By PUT to "/utubs/<int:utub_id>/urls/<int:url_id>/tags/<int:tag_id> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 400 HTTP status code,
        and that a new Tag does not exist and the Tag-URL-UTub association is not modified
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).all()

        i = 0
        while current_user not in [
            user.to_user for user in utubs_user_is_not_creator_of[i].members
        ]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of
        ).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(
            Url_Tags.query.filter_by(
                utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
            ).all()
        )

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(
            utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        tag_string_of_tag = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {TAG_FORM.TAG_STRING: tag_string_of_tag}

    modify_tag_response = client.put(
        url_for(
            "tags.modify_tag_on_url",
            utub_id=utub_id_user_is_member_of,
            url_id=url_id_to_add_tag_to,
            tag_id=curr_tag_id_on_url,
        ),
        data=add_tag_form,
    )

    # Ensure valid reponse
    assert modify_tag_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in modify_tag_response.data

    with app.app_context():
        # Ensure a new tag does not exist
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            len(
                Url_Tags.query.filter(
                    Url_Tags.utub_id == utub_id_user_is_member_of,
                    Url_Tags.url_id == url_id_to_add_tag_to,
                ).all()
            )
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            len(
                Url_Tags.query.filter_by(
                    utub_id=utub_id_user_is_member_of,
                    url_id=url_id_to_add_tag_to,
                    tag_id=curr_tag_id_on_url,
                ).all()
            )
            == 1
        )
