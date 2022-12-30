import json

import pytest

import models_for_test as v_models
from urls4irl.models import User, Utub, URLS, Tags, Url_Tags, Utub_Users, Utub_Urls

"""
Serializations to test
1) Tag objects serialized, should return their id and tag string
2) URL objects serialized, should return their id and url.
    - URL serialized objects are only returned in the context of a specific UTub, therefore
        tags are included in the serialization. Test with and without tags.
3) User object serialized, should return their id and username
4) On initial load, a user receives all their utub info serialized, an array of serialized UTubs
5) UTub object serialized, which is a giant JSON of all the info pertaining to that UTub
"""

def test_tag_serialization():
    """
    GIVEN a set of valid tags
    WHEN they are generally requested from the frontend, tags data is sent, serialized as JSON 
    THEN ensure that tags are serialized correctly when the serialization method is run

    The tag JSON data is output in the following format:
    {
        "id": Integer representing the ID of the tag,
        "tag_string": String representing the tag itself
    }
    """
    valid_tags = []
    input_tags = (v_models.valid_tag_1, v_models.valid_tag_2, v_models.valid_tag_3)

    for tag in input_tags:
        new_tag = Tags(tag_string=tag["tag_string"], id=tag['id'])
        valid_tags.append(new_tag)

    for idx, tag in enumerate(valid_tags):
        json_tag = json.dumps(tag.serialized)
        valid_json_tag = json.dumps({
            "id": idx,
            "tag_string": input_tags[idx]["tag_string"]
        })

        assert valid_json_tag == json_tag

def test_url_serialization_without_tags():
    """
    GIVEN a valid set of URLs without tags contained within a UTub 
    WHEN frontend requests a UTub's data, or if they wish to remove a URL, the backend sends
        serialized URL data, including the tags on the URL in the context of a UTub
    THEN ensure the correctly serialized data is output, with no tags associated to a URL

    The JSON output for a URL without tags is formatted as follows:
    {
        "id": Integer representing the ID of the URL,
        "url": String representing the URL itself,
        "tags": An empty array signifying no tags on this URL. URL data is requested in the context of a UTub so 
            the tags contained on this URL will be specific to the UTub
    }
    """
    valid_urls = (v_models.valid_url_without_tag_1, v_models.valid_url_without_tag_2, v_models.valid_url_without_tag_3)
    current_user_id = 0

    for v_url in valid_urls:
        new_url = URLS(normalized_url=v_url['url'], current_user_id=current_user_id)
        new_url.id = v_url['id']

        # Test a URL without any tags
        valid_url_for_json = json.dumps(v_url)

        assert json.dumps(new_url.serialized_url) == valid_url_for_json

def test_url_serialization_with_tags():
    """
    GIVEN a valid set of URLs with tags contained within a UTub
    WHEN frontend requests a UTub's data, or if they wish to remove a URL, the backend sends
        serialized URL data, including the tags on the URL in the context of a UTub
    THEN ensure the correctly serialized URL data is output, with no tags associated to a URL

    The JSON output for a URL with tags is formatted as follows:
    {
        "id": Integer representing the ID of the URL,
        "url": String representing the URL itself,
        "tags": An array containing all tag IDs relevant to this URL, which will be requested in the context of a UTub.
            An example would be: [0, 1, 2]
    }
    """
    verified_urls = (v_models.valid_url_with_tag_1, v_models.valid_url_with_tag_2, v_models.valid_url_with_tag_3)
    valid_tags = (v_models.valid_tag_1, v_models.valid_tag_2, v_models.valid_tag_3)
    
    current_user_id = 0
    new_urls = []

    for v_url in verified_urls:
        new_url = URLS(normalized_url=v_url['url'], current_user_id=current_user_id)
        new_url.id = v_url['id']

        for tag in valid_tags:
            new_tag = Tags(tag_string=tag["tag_string"], id=tag['id'])

            # Add the tag association to the URL
            new_url_tag = Url_Tags()
            new_url_tag.tag_item = new_tag
            new_url.url_tags.append(new_url_tag)

        new_urls.append(new_url)

    for idx, verified_url in enumerate(verified_urls):
        assert json.dumps(verified_url) == json.dumps(new_urls[idx].serialized_url)

def test_user_serialization_as_member_of_utub():
    """
    GIVEN a set of valid users that are members of a UTub
    WHEN a UTub's info is requested, the members of the UTub are included in the JSON response from backend.
    THEN ensure that users are serialized correctly when given as part of the UTub info

    The JSON output is formatted as follows: 
    {
        "id": Integer representing the ID of the user,
        "username": String representing the user's username
    }
    """
    valid_users = []
    member_users = (v_models.valid_user_1, v_models.valid_user_2, v_models.valid_user_3)

    for idx, inner_user in enumerate(member_users):
        new_user = User(username=inner_user["username"],
                        email=inner_user["email"],
                        plaintext_password=inner_user["password"])
        new_user.id = idx
        valid_users.append(new_user)

    for idx, test_user in enumerate(valid_users):
        json_tag = json.dumps(test_user.serialized)
        valid_json_user = json.dumps({
            "id": idx,
            "username": member_users[idx]["username"]
        })

        assert valid_json_user == json_tag

def test_user_utub_data_serialized_on_initial_load():
    """
    GIVEN a valid set of UTubs that a user is a member of
    WHEN the user first logs onto the website, the backends provides them with a serialized set of data
        representing all the UTubs they are apart of. 
    THEN ensure the correctly serialized data is output, as a JSON array

    The JSON array output has the following format:
    [
        {
            "id": Integer value defining the ID of the UTub,
            "name": String representing the UTub name
        }
    ]
    """
    # Start with empty UTubs, have the valid user be their creator and a member of them
    empty_utubs = (v_models.valid_empty_utub_1, v_models.valid_empty_utub_2, v_models.valid_empty_utub_3,)
    valid_user = v_models.valid_user_1
    new_user = User(username=valid_user["username"],
                email=valid_user["email"],
                plaintext_password=valid_user["password"])

    valid_utubs = []    # Array used to store the serialized utub data to validate against

    for empty_utub in empty_utubs:
        new_utub = Utub(name=empty_utub["name"], utub_creator=valid_user["id"], utub_description="")
        new_utub.id = empty_utub["id"]
        new_utub.utub_creator = valid_user["id"]

        # Add the valid user to the utub
        new_utub_user = Utub_Users()
        new_utub_user.to_user = new_user
        new_utub.members.append(new_utub_user)
        
        valid_utubs.append({
            "id": new_utub.id,
            "name": new_utub.name
        })

    assert json.dumps(valid_utubs) == json.dumps(new_user.serialized_on_initial_load)

def test_utub_data_when_user_requests():
    """
    GIVEN a valid UTub that a user if a member or creator of
    WHEN the user selects the UTub of interest, the backend sends JSON containing all relevant details of that
        UTub for the frontend to layout. 
    THEN ensure the correctly serialized data is output as JSON.

    Format of the serialized JSON data is as follows:
    {
    'id': Integer representing UTub ID,
    'name': String representing UTub name,
    'created_by': Integer representing creator ID,
    'created_at': Time UTub created, see this format (datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S")),
    'description': String representing UTub description, "" if empty,
    'members': Array containing each members information, in the following format:
        [
            {
                'id': Integer representing the user's ID,
                'username': String representing the user's username
            }
        ]
    'urls': Array containing all the URL information for this UTub, in the following format:
        [
            {
                "url_id": Integer repsenting the URL ID,
                "url_string": String representing the URL,
                "url_tags": Array containing integer IDs of all tags on this URL, such as: [1, 2, 3],
                "added_by": Integer ID of user identifying who added this,
                "notes": String representing a description of this URL in this UTub
            }
        ]
    'tags': Array containing all tag information for tags used in this UTub, in the following format:
        [
            {
                "id": Integer representing the tag ID,
                "tag_string": "String representing the tag itself
            }
        ]
    }   
    """
    # Start with empty UTub
    empty_utub = v_models.valid_utub_serialization_empty

    # Create user
    valid_user = v_models.valid_user_1
    new_user = User(username=valid_user["username"],
                email=valid_user["email"],
                plaintext_password=valid_user["password"])
    new_user.id = valid_user["id"]

    # Create the UTub
    new_utub = Utub(name=empty_utub["name"], utub_creator=valid_user["id"], utub_description="")
    new_utub.id = empty_utub["id"]
    new_utub.utub_creator = valid_user["id"]
    new_utub.created_at = empty_utub["created_at"]

    # Add the valid user to the utub
    new_utub_user = Utub_Users()
    new_utub_user.to_user = new_user
    new_utub.members.append(new_utub_user)

    # Test serialization of UTub with only creator
    assert json.dumps(v_models.valid_utub_serialization_with_only_creator) == json.dumps(new_utub.serialized)

    # Add another member
    second_user_model = v_models.valid_user_2
    second_user = User(username=second_user_model["username"],
                email=second_user_model["email"],
                plaintext_password=second_user_model["password"])
    second_user.id = second_user_model["id"]

    # Add the second valid user to the utub
    new_utub_user = Utub_Users()
    new_utub_user.to_user = second_user
    new_utub.members.append(new_utub_user)

    # Test serialization of UTub with creator and new member
    assert json.dumps(v_models.valid_utub_serialization_with_creator_and_member) == json.dumps(new_utub.serialized)

    # Add three URLs without tags to the UTub model
    valid_urls_without_tags = (v_models.valid_url_without_tag_1, v_models.valid_url_without_tag_2, v_models.valid_url_without_tag_3)
    
    all_urls = []
    for no_tag_url in valid_urls_without_tags:
        new_url_without_tags = URLS(normalized_url=no_tag_url["url"], current_user_id=second_user.id)
        new_url_without_tags.id = no_tag_url["id"]

        all_urls.append(new_url_without_tags)

        new_url = Utub_Urls()
        new_url.url_id = no_tag_url["id"]
        new_url.utub_id = new_utub.id
        new_url.url_in_utub = new_url_without_tags
        new_url.user_that_added_url = second_user
        new_url.url_notes = ""
        new_utub.utub_urls.append(new_url)

    # Test serialization of UTub with creator, member, and urls without tags
    assert json.dumps(v_models.valid_utub_serialization_with_members_urls_no_tags) == json.dumps(new_utub.serialized)

    # Add tags to each URL, id of tag will be equal to id of URL to add it to for testing
    all_tags = (v_models.valid_tag_1, v_models.valid_tag_2, v_models.valid_tag_3)

    for tag in all_tags:
        new_tag = Tags(tag_string=tag["tag_string"], id=tag['id'])

        # Add the tag association to the URL
        new_url_tag = Url_Tags()
        new_url_tag.tag_item = new_tag

        url_to_add_to = all_urls[tag["id"]]

        new_url_tag.tagged_url = url_to_add_to
        new_url_tag.utub_containing_this_tag = new_utub
        new_url_tag.utub_id = new_utub.id
        new_url_tag.tag_id = tag["id"]
        
        new_url_tag.utub_containing_this_tag = new_utub

    # Test serialization of UTub with creator, member, urls, and associated tags
    assert json.dumps(v_models.valid_utub_serialization_with_members_urls_tags) == json.dumps(new_utub.serialized)
