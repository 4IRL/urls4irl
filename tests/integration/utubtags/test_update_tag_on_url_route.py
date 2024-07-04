from flask import url_for
from flask_login import current_user
import pytest

from src.models.tags import Tags
from src.models.urls import Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.utubs import Utubs
from src.models.utub_members import Member_Role, Utub_Members
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import TAG_FORM
from src.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from src.utils.strings.model_strs import MODELS
from src.utils.strings.tag_strs import TAGS_FAILURE, TAGS_NO_CHANGE, TAGS_SUCCESS

pytestmark = pytest.mark.tags

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
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_URL,
        TAGS_SUCCESS.URL_TAGS : Array of integers representing all IDs (including modified tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            },
        TAGS_SUCCESS.PREVIOUS_TAG: Object for old tag, with tag id and boolean indicating whether tag still exists in UTub
            {
                "id": Integer representing ID of previous tag,
                TAGS_SUCCESS.TAG_IN_UTUB: Boolean indicating whether old tag still exists in UTub
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_user_is_creator_of.last_updated
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of
        ).first()
        url_id_to_update_tag_on = url_utub_association.id
        associated_tags = url_utub_association.associated_tags

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: NEW_TAG,
    }

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_creator_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_MODIFIED_ON_URL
    )
    assert modify_tag_response_json[TAGS_SUCCESS.TAG][MODELS.TAG_STRING] == NEW_TAG
    assert (
        modify_tag_response_json[TAGS_SUCCESS.PREVIOUS_TAG][MODELS.ID]
        == curr_tag_id_on_url
    )

    with app.app_context():
        # Ensure a new tag exists
        assert Tags.query.count() == num_tags + 1

        new_tag_from_server: Tags = Tags.query.filter(
            Tags.tag_string == NEW_TAG
        ).first()

        # Assert tag is created
        assert new_tag_from_server is not None
        assert (
            int(modify_tag_response_json[TAGS_SUCCESS.TAG][MODELS.ID])
            == new_tag_from_server.id
        )
        associated_tags[associated_tags.index(curr_tag_id_on_url)] = (
            new_tag_from_server.id
        )
        assert sorted(modify_tag_response_json[TAGS_SUCCESS.URL_TAGS]) == sorted(
            associated_tags
        )

        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.id == url_id_to_update_tag_on,
        ).first()

        assert sorted(url_utub_association.associated_tags) == sorted(
            modify_tag_response_json[TAGS_SUCCESS.URL_TAGS]
        )

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        count_of_prev_tag_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.tag_id == curr_tag_id_on_url,
        ).count()
        assert (
            modify_tag_response_json[TAGS_SUCCESS.PREVIOUS_TAG][
                TAGS_SUCCESS.TAG_IN_UTUB
            ]
            == count_of_prev_tag_in_utub
            > 0
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations

        # Ensure UTub is updated
        current_utub: Utubs = Utubs.query.get(utub_id_user_is_creator_of)
        assert (current_utub.last_updated - initial_last_updated).total_seconds() > 0


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
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_URL,
        TAGS_SUCCESS.URL_TAGS : Array of integers representing all IDs (including modified tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            },
        TAGS_SUCCESS.PREVIOUS_TAG: Object for old tag, with tag id and boolean indicating whether tag still exists in UTub
            {
                "id": Integer representing ID of previous tag,
                TAGS_SUCCESS.TAG_IN_UTUB: Boolean indicating whether old tag still exists in UTub
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utub_member_user_is_not_creator_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role == Member_Role.MEMBER,
        ).first()

        utub_user_is_member_of: Utubs = utub_member_user_is_not_creator_of.to_utub
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_id_to_update_tag_on = url_utub_association.id
        associated_tags = url_utub_association.associated_tags

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: NEW_TAG,
    }

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_member_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_MODIFIED_ON_URL
    )
    assert modify_tag_response_json[TAGS_SUCCESS.TAG][MODELS.TAG_STRING] == NEW_TAG
    assert (
        modify_tag_response_json[TAGS_SUCCESS.PREVIOUS_TAG][MODELS.ID]
        == curr_tag_id_on_url
    )

    with app.app_context():
        # Ensure a new tag exists
        assert Tags.query.count() == num_tags + 1

        new_tag_from_server: Tags = Tags.query.filter(
            Tags.tag_string == NEW_TAG
        ).first()

        # Assert tag is created
        assert new_tag_from_server is not None
        assert (
            int(modify_tag_response_json[TAGS_SUCCESS.TAG][MODELS.ID])
            == new_tag_from_server.id
        )
        associated_tags[associated_tags.index(curr_tag_id_on_url)] = (
            new_tag_from_server.id
        )
        assert sorted(modify_tag_response_json[TAGS_SUCCESS.URL_TAGS]) == sorted(
            associated_tags
        )

        url_utub_association: Utub_Urls = Utub_Urls.query.get(url_id_to_update_tag_on)

        assert sorted(url_utub_association.associated_tags) == sorted(
            modify_tag_response_json[TAGS_SUCCESS.URL_TAGS]
        )

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        count_of_prev_tag_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.tag_id == curr_tag_id_on_url,
        ).count()
        assert (
            modify_tag_response_json[TAGS_SUCCESS.PREVIOUS_TAG][
                TAGS_SUCCESS.TAG_IN_UTUB
            ]
            == count_of_prev_tag_in_utub
            > 0
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations


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
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_URL,
        TAGS_SUCCESS.URL_TAGS : Array of integers representing all IDs (including modified tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            },
        TAGS_SUCCESS.PREVIOUS_TAG: Object for old tag, with tag id and boolean indicating whether tag still exists in UTub
            {
                "id": Integer representing ID of previous tag,
                TAGS_SUCCESS.TAG_IN_UTUB: Boolean indicating whether old tag still exists in UTub
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of
        ).first()
        url_id_to_update_tag_on = url_utub_association.id
        associated_tags = url_utub_association.associated_tags

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Find another tag that isn't the one already on the URL
        tag_to_replace_with: Tags = Tags.query.filter(
            Tags.tag_string != tag_on_url.tag_item.tag_string
        ).first()
        new_tag_string = tag_to_replace_with.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: new_tag_string,
    }

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_creator_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_MODIFIED_ON_URL
    )
    assert (
        modify_tag_response_json[TAGS_SUCCESS.TAG][MODELS.TAG_STRING] == new_tag_string
    )
    assert (
        modify_tag_response_json[TAGS_SUCCESS.PREVIOUS_TAG][MODELS.ID]
        == curr_tag_id_on_url
    )
    associated_tags[associated_tags.index(curr_tag_id_on_url)] = tag_to_replace_with.id
    assert sorted(modify_tag_response_json[TAGS_SUCCESS.URL_TAGS]) == sorted(
        associated_tags
    )

    with app.app_context():
        # Ensure no new tag exists
        assert Tags.query.count() == num_tags

        url_utub_association: Utub_Urls = Utub_Urls.query.get(url_id_to_update_tag_on)
        assert sorted(url_utub_association.associated_tags) == sorted(
            modify_tag_response_json[TAGS_SUCCESS.URL_TAGS]
        )

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        count_of_prev_tag_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.tag_id == curr_tag_id_on_url,
        ).count()
        assert (
            modify_tag_response_json[TAGS_SUCCESS.PREVIOUS_TAG][
                TAGS_SUCCESS.TAG_IN_UTUB
            ]
            == count_of_prev_tag_in_utub
            > 0
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations


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
        STD_JSON.MESSAGE : TAGS_SUCCESS.TAG_ADDED_TO_URL,
        TAGS_SUCCESS.URL_TAGS : Array of integers representing all IDs (including modified tag ID) of tags associated with this URL in this UTub,
        TAGS_SUCCESS.TAG : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag newly added,
                TAG_FORM.TAG_STRING: String representing the tag just added
            },
        TAGS_SUCCESS.PREVIOUS_TAG: Object for old tag, with tag id and boolean indicating whether tag still exists in UTub
            {
                "id": Integer representing ID of previous tag,
                TAGS_SUCCESS.TAG_IN_UTUB: Boolean indicating whether old tag still exists in UTub
            }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utub_member_user_is_not_creator_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role == Member_Role.MEMBER,
        ).first()

        utub_user_is_member_of: Utubs = utub_member_user_is_not_creator_of.to_utub
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of,
            Utub_Urls.user_id == current_user.id,
        ).first()
        url_id_to_update_tag_on = url_utub_association.id
        associated_tags = url_utub_association.associated_tags

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Find tag in database that isn't this tag
        tag_from_database: Tags = Tags.query.filter(
            Tags.tag_string != tag_on_url.tag_item.tag_string
        ).first()

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_from_database.tag_string,
    }

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_member_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert (
        modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_SUCCESS.TAG_MODIFIED_ON_URL
    )
    assert (
        modify_tag_response_json[TAGS_SUCCESS.TAG][MODELS.TAG_STRING]
        == tag_from_database.tag_string
    )
    assert (
        modify_tag_response_json[TAGS_SUCCESS.PREVIOUS_TAG][MODELS.ID]
        == curr_tag_id_on_url
    )
    associated_tags[associated_tags.index(curr_tag_id_on_url)] = tag_from_database.id
    assert sorted(modify_tag_response_json[TAGS_SUCCESS.URL_TAGS]) == sorted(
        associated_tags
    )

    with app.app_context():
        # Ensure a new tag does not exist
        assert Tags.query.count() == num_tags

        url_utub_association: Utub_Urls = Utub_Urls.query.get(url_id_to_update_tag_on)
        assert sorted(url_utub_association.associated_tags) == sorted(
            modify_tag_response_json[TAGS_SUCCESS.URL_TAGS]
        )

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        count_of_prev_tag_in_utub = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.tag_id == curr_tag_id_on_url,
        ).count()
        assert (
            modify_tag_response_json[TAGS_SUCCESS.PREVIOUS_TAG][
                TAGS_SUCCESS.TAG_IN_UTUB
            ]
            == count_of_prev_tag_in_utub
            > 0
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations


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
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        initial_last_updated = utub_user_is_creator_of.last_updated
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of
        ).first()
        url_id_to_update_tag_on = url_utub_association.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        tag_string_on_url: str = tag_on_url.tag_item.tag_string
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_string_on_url,
    }

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_creator_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_NO_CHANGE.TAG_NOT_MODIFIED

    with app.app_context():
        # Ensure no new tag exists
        assert Tags.query.count() == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
                Utub_Url_Tags.tag_id == curr_tag_id_on_url,
            ).count()
            == 1
        )

        # Ensure no update for UTub
        current_utub: Utubs = Utubs.query.get(utub_id_user_is_creator_of)
        assert current_utub.last_updated == initial_last_updated


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
        utub_member_user_is_not_creator_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id,
            Utub_Members.member_role == Member_Role.MEMBER,
        ).first()

        utub_user_is_member_of: Utubs = utub_member_user_is_not_creator_of.to_utub
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of
        ).first()
        url_id_to_update_tag_on = url_utub_association.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        curr_tag_string = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: curr_tag_string,
    }

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_member_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_NO_CHANGE.TAG_NOT_MODIFIED

    with app.app_context():
        # Ensure a new tag does not exist
        assert Tags.query.count() == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
                Utub_Url_Tags.tag_id == curr_tag_id_on_url,
            ).count()
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
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_creator_of
        ).first()
        url_id_to_update_tag_on = url_utub_association.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get tag to change to on this URL
        tag_to_change_to_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            Utub_Url_Tags.tag_id != curr_tag_id_on_url,
        ).first()

        tag_to_change_to_string: str = tag_to_change_to_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: tag_to_change_to_string,
    }

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_creator_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    assert modify_tag_response.status_code == 400

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert modify_tag_response_json[STD_JSON.MESSAGE] == TAGS_FAILURE.TAG_ALREADY_ON_URL
    assert int(modify_tag_response_json[STD_JSON.ERROR_CODE]) == 2

    with app.app_context():
        # Ensure no new tag exists
        assert Tags.query.count() == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_creator_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
                Utub_Url_Tags.tag_id == curr_tag_id_on_url,
            ).count()
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
        # Find UTub this current user is not member of
        utub_member_user_is_not_creator_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id,
        ).first()

        utub_user_is_not_member_of: Utubs = utub_member_user_is_not_creator_of.to_utub
        utub_id_user_is_not_member_of = utub_user_is_not_member_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_not_member_of
        ).first()
        url_id_to_update_tag_on = url_utub_association.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_not_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_not_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        curr_tag_string: str = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {
        TAG_FORM.CSRF_TOKEN: csrf_token,
        TAG_FORM.TAG_STRING: curr_tag_string,
    }

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_not_member_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    assert modify_tag_response.status_code == 403

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
        assert Tags.query.count() == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_not_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_not_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
                Utub_Url_Tags.tag_id == curr_tag_id_on_url,
            ).count()
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
    NONEXISTENT_URL_ID = 999
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_creator_of,
            utub_url_id=NONEXISTENT_URL_ID,
            tag_id=1,
        ),
        data=update_tag_form,
    )
    assert modify_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tag exists
        assert Tags.query.count() == num_tags

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations


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
    NONEXISTENT_UTUB_ID = 999
    NONEXISTENT_URL_ID = 999
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token, TAG_FORM.TAG_STRING: NEW_TAG}

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=NONEXISTENT_UTUB_ID,
            utub_url_id=NONEXISTENT_URL_ID,
            tag_id=1,
        ),
        data=update_tag_form,
    )
    assert modify_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tag exists
        assert Tags.query.count() == num_tags

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations


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
        utubs_user_is_not_creator_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).first()

        utub_user_is_member_of: Utubs = utubs_user_is_not_creator_of.to_utub
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of
        ).first()
        url_id_to_update_tag_on = url_utub_association.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {TAG_FORM.CSRF_TOKEN: csrf_token}

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_member_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
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
        assert Tags.query.count() == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
                Utub_Url_Tags.tag_id == curr_tag_id_on_url,
            ).count()
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
        utubs_user_is_not_creator_of: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id != current_user.id
        ).first()

        utub_user_is_member_of: Utubs = utubs_user_is_not_creator_of.to_utub
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Get URL that is in this UTub
        url_utub_association: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id_user_is_member_of
        ).first()
        url_in_this_utub: Urls = url_utub_association.standalone_url
        url_id_to_update_tag_on = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).count()

        # Get a tag on this URL
        tag_on_url: Utub_Url_Tags = Utub_Url_Tags.query.filter(
            Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
            Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
        ).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        tag_string_of_tag: str = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = Utub_Url_Tags.query.count()

        # Get initial number of tags
        num_tags = Tags.query.count()

    # Add tag to this URL
    update_tag_form = {TAG_FORM.TAG_STRING: tag_string_of_tag}

    modify_tag_response = client.put(
        url_for(
            ROUTES.TAGS.MODIFY_TAG,
            utub_id=utub_id_user_is_member_of,
            utub_url_id=url_id_to_update_tag_on,
            tag_id=curr_tag_id_on_url,
        ),
        data=update_tag_form,
    )

    # Ensure valid reponse
    assert modify_tag_response.status_code == 400
    assert b"<p>The CSRF token is missing.</p>" in modify_tag_response.data

    with app.app_context():
        # Ensure a new tag does not exist
        assert Tags.query.count() == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
            ).count()
            == num_of_tags_on_url
        )

        # Ensure correct count of Url-Tag associations
        assert Utub_Url_Tags.query.count() == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert (
            Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id_user_is_member_of,
                Utub_Url_Tags.utub_url_id == url_id_to_update_tag_on,
                Utub_Url_Tags.tag_id == curr_tag_id_on_url,
            ).count()
            == 1
        )
