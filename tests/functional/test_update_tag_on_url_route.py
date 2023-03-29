import pytest
from flask_login import current_user

from urls4irl import db
from urls4irl.models import Utub, URLS, Utub_Urls, Utub_Users, Tags, Url_Tags
from models_for_test import all_tag_strings

def test_modify_tag_with_fresh_tag_on_valid_url_as_utub_creator(add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag with a tag not currently in the database
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag exists, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        "Status" : "Success",
        "Message" : "Tag added to this URL",
        "Tag" : Serialization representing the new tag object:
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
                    which should include the newly added tag
            }
        "UTub_ID" : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        "UTub_name": String representing name of UTub that the URL, user, and tag association is in
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    NEW_TAG = "Fruitilicious"
    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(Utub.utub_creator == current_user.id).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        utub_name_user_is_creator_of = utub_user_is_creator_of.name

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_creator_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_creator_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Ensure this new tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == NEW_TAG).all()) == 0

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : NEW_TAG,
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_creator_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json["Status"] == "Success"
    assert modify_tag_response_json["Message"] == "Tag modified on URL"
    assert int(modify_tag_response_json["UTub_ID"]) == utub_id_user_is_creator_of
    assert modify_tag_response_json["UTub_name"] == utub_name_user_is_creator_of

    url_serialization_from_server = modify_tag_response_json["URL"]
    tag_serialization_from_server = modify_tag_response_json["Tag"]

    with app.app_context():
        # Ensure a new tag exists
        assert len(Tags.query.all()) == num_tags + 1

        new_tag_from_server = Tags.query.filter(Tags.tag_string == NEW_TAG).first()

        # Assert tag is created
        assert new_tag_from_server is not None

        assert new_tag_from_server.serialized == tag_serialization_from_server

        url_utub_tag_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_creator_of,
                                                            Utub_Urls.user_id == current_user.id,
                                                            Utub_Urls.url_id == url_id_to_add_tag_to).first()

        assert url_utub_tag_association.serialized == url_serialization_from_server

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_creator_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

def test_modify_tag_with_fresh_tag_on_valid_url_as_utub_member(add_two_users_and_all_urls_to_each_utub_with_tags, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag with a tag not currently in the database
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag exists, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        "Status" : "Success",
        "Message" : "Tag added to this URL",
        "Tag" : Serialization representing the new tag object:
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
                    which should include the newly added tag
            }
        "UTub_ID" : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        "UTub_name": String representing name of UTub that the URL, user, and tag association is in
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    NEW_TAG = "Fruitilicious"
    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(Utub.utub_creator != current_user.id).all()

        i = 0
        while current_user not in [user.to_user for user in utubs_user_is_not_creator_of[i].members]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id
        utub_name_user_is_member_of = utub_user_is_member_of.name

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_member_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Ensure this new tag does not exist in the database
        assert len(Tags.query.filter(Tags.tag_string == NEW_TAG).all()) == 0

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : NEW_TAG,
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_member_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json["Status"] == "Success"
    assert modify_tag_response_json["Message"] == "Tag modified on URL"
    assert int(modify_tag_response_json["UTub_ID"]) == utub_id_user_is_member_of
    assert modify_tag_response_json["UTub_name"] == utub_name_user_is_member_of

    url_serialization_from_server = modify_tag_response_json["URL"]
    tag_serialization_from_server = modify_tag_response_json["Tag"]

    with app.app_context():
        # Ensure a new tag exists
        assert len(Tags.query.all()) == num_tags + 1

        new_tag_from_server = Tags.query.filter(Tags.tag_string == NEW_TAG).first()

        # Assert tag is created
        assert new_tag_from_server is not None

        assert new_tag_from_server.serialized == tag_serialization_from_server

        url_utub_tag_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_member_of,
                                                            Utub_Urls.user_id == current_user.id,
                                                            Utub_Urls.url_id == url_id_to_add_tag_to).first()

        assert url_utub_tag_association.serialized == url_serialization_from_server

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_member_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

def test_modify_tag_with_other_tag_on_valid_url_as_utub_creator(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag by changing it to a tag already contained in the database
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        "Status" : "Success",
        "Message" : "Tag added to this URL",
        "Tag" : Serialization representing the new tag object:
            {
                "id": Integer representing ID of tag,
                "tag_string": String representing the tag just added
            }
        "URL" : Serialization representing the URL in this UTub, who it was added by, and associated tags IDs:
            {
                "url_id": Integer reprensenting ID of the URL the tag was added to in this UTub,
                "url_string": String representing the URL,
                "added_by": Integer representing the ID of the user who added this URL,
                "notes": "String representing the URL description,
                "url_tags": Array of integers representing all IDs of tags associated with this URL in this UTub,
                    which should include the tag
            }
        "UTub_ID" : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        "UTub_name": String representing name of UTub that the URL, user, and tag association is in
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(Utub.utub_creator == current_user.id).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id
        utub_name_user_is_creator_of = utub_user_is_creator_of.name

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_creator_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_creator_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Find another tag that isn't the one already on the URL
        tag_to_replace_with = Tags.query.filter(Tags.tag_string != tag_on_url.tag_item.tag_string).first()
        new_tag_string = tag_to_replace_with.tag_string

        # Ensure this tag does not have an association with this URL on this UTub
        assert len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to, tag_id=tag_to_replace_with.id).all()) == 0

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : new_tag_string
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_creator_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json["Status"] == "Success"
    assert modify_tag_response_json["Message"] == "Tag modified on URL"
    assert int(modify_tag_response_json["UTub_ID"]) == utub_id_user_is_creator_of
    assert modify_tag_response_json["UTub_name"] == utub_name_user_is_creator_of

    url_serialization_from_server = modify_tag_response_json["URL"]
    tag_serialization_from_server = modify_tag_response_json["Tag"]

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        tag_from_server = Tags.query.get(tag_to_replace_with.id)
        assert tag_from_server.serialized == tag_serialization_from_server

        url_utub_tag_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_creator_of,
                                                            Utub_Urls.user_id == current_user.id,
                                                            Utub_Urls.url_id == url_id_to_add_tag_to).first()

        assert url_utub_tag_association.serialized == url_serialization_from_server

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_creator_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

def test_modify_tag_with_other_tag_on_valid_url_as_utub_member(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag with a tag not currently in the database
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        "Status" : "Success",
        "Message" : "Tag added to this URL",
        "Tag" : Serialization representing the new tag object:
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
                    which should include the newly added tag
            }
        "UTub_ID" : Integer representing the ID of the UTub that the URL, user, and tag association is in,
        "UTub_name": String representing name of UTub that the URL, user, and tag association is in
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(Utub.utub_creator != current_user.id).all()

        i = 0
        while current_user not in [user.to_user for user in utubs_user_is_not_creator_of[i].members]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id
        utub_name_user_is_member_of = utub_user_is_member_of.name

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_member_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Find tag in database that isn't this tag
        tag_from_database = Tags.query.filter(Tags.tag_string != tag_on_url.tag_item.tag_string).first()

        # Ensure this new tag does not have an association with this URL
        assert len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to, tag_id=tag_from_database.id).all()) == 0

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : tag_from_database.tag_string,
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_member_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json["Status"] == "Success"
    assert modify_tag_response_json["Message"] == "Tag modified on URL"
    assert int(modify_tag_response_json["UTub_ID"]) == utub_id_user_is_member_of
    assert modify_tag_response_json["UTub_name"] == utub_name_user_is_member_of

    url_serialization_from_server = modify_tag_response_json["URL"]
    tag_serialization_from_server = modify_tag_response_json["Tag"]

    with app.app_context():
        # Ensure a new tag does not exist 
        assert len(Tags.query.all()) == num_tags

        # Get tag from database
        tag_from_database_after_add = Tags.query.get(tag_from_database.id)
        assert tag_from_database_after_add.serialized == tag_serialization_from_server

        url_utub_tag_association = Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_member_of,
                                                            Utub_Urls.user_id == current_user.id,
                                                            Utub_Urls.url_id == url_id_to_add_tag_to).first()

        assert url_utub_tag_association.serialized == url_serialization_from_server

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_member_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

def test_modify_tag_with_same_tag_on_valid_url_as_utub_creator(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag by changing it to the same tag 
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        "Status" : "No change",
        "Message" : "Tag was not modified on this URL",
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(Utub.utub_creator == current_user.id).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_creator_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_creator_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to).first()
        tag_string_on_url = tag_on_url.tag_item.tag_string
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : tag_string_on_url
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_creator_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json["Status"] == "No change"
    assert modify_tag_response_json["Message"] == "Tag was not modified on this URL"

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_creator_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_creator_of, url_id=url_id_to_add_tag_to, tag_id=curr_tag_id_on_url).all()) == 1

def test_modify_tag_with_same_tag_on_valid_url_as_utub_member(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag with the same tag
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        "Status" : "No change",
        "Message" : "Tag was not modified on this URL",
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(Utub.utub_creator != current_user.id).all()

        i = 0
        while current_user not in [user.to_user for user in utubs_user_is_not_creator_of[i].members]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id
        utub_name_user_is_member_of = utub_user_is_member_of.name

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_member_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        curr_tag_string = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : curr_tag_string
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_member_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    assert modify_tag_response.status_code == 200

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json["Status"] == "No change"
    assert modify_tag_response_json["Message"] == "Tag was not modified on this URL"

    with app.app_context():
        # Ensure a new tag does not exist 
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_member_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to, tag_id=curr_tag_id_on_url).all()) == 1

def test_modify_tag_on_another_utub_url(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag in another UTub
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, and the Tag-URL-UTub association is not modified

    Proper JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "Only UTub members can modify tags",
        "Error_code" : 1
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(Utub.utub_creator != current_user.id).all()

        i = 0
        while current_user in [user.to_user for user in utubs_user_is_not_creator_of[i].members]:
            i += 1

        utub_user_is_not_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_not_member_of = utub_user_is_not_member_of.id

        # Ensure user is not in this UTub
        assert current_user not in [user.to_user for user in utub_user_is_not_member_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_not_member_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_not_member_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_not_member_of, url_id=url_id_to_add_tag_to).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        curr_tag_string = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : curr_tag_string
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_not_member_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    assert modify_tag_response.status_code == 404

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json["Status"] == "Failure"
    assert modify_tag_response_json["Message"] == "Only UTub members can modify tags"
    assert int(modify_tag_response_json["Error_code"]) == 1

    with app.app_context():
        # Ensure a new tag does not exist 
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_not_member_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_not_member_of, url_id=url_id_to_add_tag_to, tag_id=curr_tag_id_on_url).all()) == 1

def test_modify_tag_on_invalid_url_as_utub_creator(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a nonexistent URL's tag by changing it to the same tag 
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 200 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is modified,
        and that the association between URL and Tag is recorded properly

    Proper JSON response is as follows:
    {
        "Status" : "No change",
        "Message" : "Tag was not modified on this URL",
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    NEW_TAG = "Fruitilicious"
    with app.app_context():
        # Find UTub this current user is creator of
        utub_user_is_creator_of = Utub.query.filter(Utub.utub_creator == current_user.id).first()
        utub_id_user_is_creator_of = utub_user_is_creator_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_creator_of.members]

        # Ensure invalid URL ID is nonexistent
        invalid_url_id = -1

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : NEW_TAG
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_creator_of}/{invalid_url_id}/1", data=add_tag_form)
    assert modify_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

def test_modify_tag_on_url_in_nonexistent_utub(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a creator of a UTub, and one
        URL exists in each UTub, added by the creator
    WHEN the user tries to modify a URL's tag in a nonexistent UTub
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 404 HTTP status code, proper response is sent by the server, 
        and that a new Tag does not exist
    """
    client, csrf_token, _, app = login_first_user_without_register

    NEW_TAG = "Fruitilicious"
    invalid_url_id = -1
    invalid_utub_id = -1

    with app.app_context():
        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token,
        "tag_string" : NEW_TAG
    }

    modify_tag_response = client.post(f"/tag/url/modify/{invalid_utub_id}/{invalid_url_id}/1", data=add_tag_form)
    assert modify_tag_response.status_code == 404

    with app.app_context():
        # Ensure no new tag exists
        assert len(Tags.query.all()) == num_tags

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

def test_modify_tag_with_missing_tag_field(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag but doesn't include tag field in form
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 404 HTTP status code, that the proper JSON response
        is sent by the server, and that a new Tag does not exist, the Tag-URL-UTub association is not modified,

    Proper JSON response is as follows:
    {
        "Status" : "Failure",
        "Message" : "Unable to add tag to this URL",
        "Error_code" : 2,
        "Errors": Object representing array of errors pertaining to relevant fields
        {
            "tag_string" : Array of errors associated with tag_string field
        }
    }
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(Utub.utub_creator != current_user.id).all()

        i = 0
        while current_user not in [user.to_user for user in utubs_user_is_not_creator_of[i].members]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_member_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).first()
        curr_tag_id_on_url = tag_on_url.tag_id

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "csrf_token" : csrf_token
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_member_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    assert modify_tag_response.status_code == 404

    # Ensure json response from server is valid
    modify_tag_response_json = modify_tag_response.json
    assert modify_tag_response_json["Status"] == "Failure"
    assert modify_tag_response_json["Message"] == "Unable to add tag to this URL"
    assert int(modify_tag_response_json["Error_code"]) == 2
    assert modify_tag_response_json["Errors"]["tag_string"] == ["This field is required."]

    with app.app_context():
        # Ensure a new tag does not exist 
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_member_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to, tag_id=curr_tag_id_on_url).all()) == 1

def test_modify_tag_with_missing_csrf_token(add_two_users_and_all_urls_to_each_utub_with_one_tag, login_first_user_without_register):
    """
    GIVEN 3 users and 3 UTubs, with only the creator and member of the UTub in each UTub, with two URLs added, one per user,
        with all tags on each URL, and the currently logged in user is a member of a UTub, and one
        URL exists in each UTub, added by the member
    WHEN the user tries to modify a URL's tag but doesn't include csrf token
        - By POST to "/tag/url/modify/<utub_id: int>/<url_id: int>/<iag_id: int> where:
            "utub_id" : An integer representing UTub ID,
            "url_id": An integer representing URL ID to add tag to
            "tag_id": An integer representing the tag currently on the URL
    THEN ensure that the server responds with a 400 HTTP status code,
        and that a new Tag does not exist and the Tag-URL-UTub association is not modified
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        # Find UTub this current user is member of
        utubs_user_is_not_creator_of = Utub.query.filter(Utub.utub_creator != current_user.id).all()

        i = 0
        while current_user not in [user.to_user for user in utubs_user_is_not_creator_of[i].members]:
            i += 1

        utub_user_is_member_of = utubs_user_is_not_creator_of[i]
        utub_id_user_is_member_of = utub_user_is_member_of.id

        # Ensure user is in this UTub
        assert current_user in [user.to_user for user in utub_user_is_member_of.members]

        # Get URL that is in this UTub
        url_utub_association =  Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id_user_is_member_of).first()
        url_in_this_utub = url_utub_association.url_in_utub
        url_id_to_add_tag_to = url_in_this_utub.id

        # Find number of tags on this URL in this UTub
        num_of_tags_on_url = len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).all())

        # Get a tag on this URL
        tag_on_url = Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to).first()
        curr_tag_id_on_url = tag_on_url.tag_id
        tag_string_of_tag = tag_on_url.tag_item.tag_string

        # Get initial num of Url-Tag associations
        initial_num_url_tag_associations = len(Url_Tags.query.all())

        # Get initial number of tags
        num_tags = len(Tags.query.all())

    # Add tag to this URL
    add_tag_form = {
        "tag_string" : tag_string_of_tag
    }

    modify_tag_response = client.post(f"/tag/url/modify/{utub_id_user_is_member_of}/{url_id_to_add_tag_to}/{curr_tag_id_on_url}", data=add_tag_form)

    #Ensure valid reponse
    assert modify_tag_response.status_code == 400
    assert b'<p>The CSRF token is missing.</p>' in modify_tag_response.data

    with app.app_context():
        # Ensure a new tag does not exist 
        assert len(Tags.query.all()) == num_tags

        # Ensure number of Tag-URL association do not change on this URL in this UTub
        assert len(Url_Tags.query.filter(Url_Tags.utub_id == utub_id_user_is_member_of,
                                            Url_Tags.url_id == url_id_to_add_tag_to).all()) == num_of_tags_on_url 

        # Ensure correct count of Url-Tag associations
        assert len(Url_Tags.query.all()) == initial_num_url_tag_associations

        # Ensure tag still exists attached to this URL
        assert len(Url_Tags.query.filter_by(utub_id=utub_id_user_is_member_of, url_id=url_id_to_add_tag_to, tag_id=curr_tag_id_on_url).all()) == 1