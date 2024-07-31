import json

from flask import Flask
import pytest

from src import db
from src.models.utub_tags import Utub_Tags
from src.models.urls import Urls
from src.models.utub_url_tags import Utub_Url_Tags
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_members import Utub_Members
from src.models.utub_urls import Utub_Urls
from src.utils.strings.model_strs import MODELS as MODEL_STRS
from src.utils.strings.splash_form_strs import REGISTER_FORM
import tests.models_for_test as v_models

pytestmark = pytest.mark.unit

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


def test_tag_serialization(app: Flask, every_user_makes_a_unique_utub):
    """
    GIVEN a set of valid tags
    WHEN they are generally requested from the frontend, tags data is sent, serialized as JSON
    THEN ensure that tags are serialized correctly when the serialization method is run

    The tag JSON data is output in the following format:
    {
        MODEL_STRS.ID: Integer representing the ID of the tag,
        MODEL_STRS.TAG_STRING: String representing the tag itself
    }
    """
    input_tags = (v_models.valid_tag_1, v_models.valid_tag_2, v_models.valid_tag_3)

    with app.app_context():
        for utub in Utubs.query.all():
            for idx, tag in enumerate(input_tags):
                new_tag = Utub_Tags(
                    utub_id=utub.id,
                    tag_string=tag[MODEL_STRS.TAG_STRING],
                    created_by=idx + 1,
                )
                db.session.add(new_tag)
        db.session.commit()

    with app.app_context():
        for utub in Utubs.query.all():
            utub: Utubs
            for idx, tag in enumerate(utub.utub_tags):
                json_tag = json.dumps(tag.serialized)
                valid_json_tag = json.dumps(
                    {
                        MODEL_STRS.ID: tag.id,
                        MODEL_STRS.TAG_STRING: input_tags[idx][MODEL_STRS.TAG_STRING],
                    }
                )

            assert valid_json_tag == json_tag


def test_url_serialization_without_tags():
    """
    GIVEN a valid set of URLs without tags contained within a UTub
    WHEN frontend requests a UTub's data, or if they wish to remove a URL, the backend sends
        serialized URL data, including the tags on the URL in the context of a UTub
    THEN ensure the correctly serialized data is output, with no tags associated to a URL

    The JSON output for a URL without tags is formatted as follows:
    {
        MODEL_STRS.ID: Integer representing the ID of the URL,
        MODEL_STRS.URL_STRING: String representing the URL itself,
        MODEL_STRS.TAGS: An empty array signifying no tags on this URL. URL data is requested in the context of a UTub so
            the tags contained on this URL will be specific to the UTub
    }
    """
    valid_urls = (
        v_models.valid_url_without_tag_1,
        v_models.valid_url_without_tag_2,
        v_models.valid_url_without_tag_3,
    )
    current_user_id = 0

    for v_url in valid_urls:
        new_url = Urls(
            normalized_url=v_url[MODEL_STRS.URL_STRING], current_user_id=current_user_id
        )

        new_utub_url = Utub_Urls()
        new_utub_url.standalone_url = new_url
        new_utub_url.id = v_url[MODEL_STRS.UTUB_URL_ID]
        new_utub_url.url_title = ""

        # Test a URL without any tags
        valid_url_for_json = json.dumps(v_url)

        assert json.dumps(new_utub_url.serialized(1, 1)) == valid_url_for_json


def test_url_serialization_with_tags(
    app: Flask, add_urls_to_database, add_tags_to_utubs
):
    """
    GIVEN a valid set of URLs with tags contained within a UTub
    WHEN frontend requests a UTub's data, or if they wish to remove a URL, the backend sends
        serialized URL data, including the tags on the URL in the context of a UTub
    THEN ensure the correctly serialized URL data is output, with no tags associated to a URL

    The JSON output for a URL with tags is formatted as follows:
    {
        MODEL_STRS.ID: Integer representing the ID of the URL,
        MODEL_STRS.URL: String representing the URL itself,
        MODEL_STRS.TAGS: An array containing all tag IDs relevant to this URL, which will be requested in the context of a UTub.
            An example would be: [0, 1, 2]
    }
    """
    verified_urls = (
        v_models.valid_url_with_tag_1,
        v_models.valid_url_with_tag_2,
        v_models.valid_url_with_tag_3,
    )

    # UTub - URL associations
    with app.app_context():
        all_utubs = Utubs.query.all()
        all_urls = Urls.query.all()

        for utub, url in zip(all_utubs, all_urls):
            new_utub_url = Utub_Urls()
            new_utub_url.utub = utub
            new_utub_url.utub_id = utub.id
            new_utub_url.id = url.id
            new_utub_url.standalone_url = url
            new_utub_url.user_id = utub.id

            db.session.add(new_utub_url)

        db.session.commit()

    # UTub-URL-Tag associations
    with app.app_context():
        all_utubs = Utubs.query.all()
        all_urls = Utub_Urls.query.all()

        for utub, url in zip(all_utubs, all_urls):
            for tag in Utub_Tags.query.filter(Utub_Tags.utub_id == utub.id).all():
                new_url_tag = Utub_Url_Tags()
                new_url_tag.utub_id = utub.id
                new_url_tag.utub_url_id = url.id
                new_url_tag.utub_tag_id = tag.id

                db.session.add(new_url_tag)

        db.session.commit()

    with app.app_context():
        all_utubs = Utubs.query.all()
        all_urls = Urls.query.all()

        for utub, url, verified_url in zip(all_utubs, all_urls, verified_urls):
            url_with_tags: Utub_Urls = Utub_Urls.query.filter(
                Utub_Urls.id == url.id, Utub_Urls.utub_id == utub.id
            ).first()
            verified_url[MODEL_STRS.URL_TAG_IDS] = [
                tag.id
                for tag in Utub_Tags.query.filter(Utub_Tags.utub_id == utub.id).all()
            ]

            assert json.dumps(verified_url) == json.dumps(
                url_with_tags.serialized(1, 1)
            )


def test_user_serialization_as_member_of_utub():
    """
    GIVEN a set of valid users that are members of a UTub
    WHEN a UTub's info is requested, the members of the UTub are included in the JSON response from backend.
    THEN ensure that users are serialized correctly when given as part of the UTub info

    The JSON output is formatted as follows:
    {
        MODEL_STRS.ID: Integer representing the ID of the user,
        MODEL_STRS.USERNAME: String representing the user's username
    }
    """
    valid_users = []
    member_users = (v_models.valid_user_1, v_models.valid_user_2, v_models.valid_user_3)

    for idx, inner_user in enumerate(member_users):
        new_user = Users(
            username=inner_user[MODEL_STRS.USERNAME],
            email=inner_user[REGISTER_FORM.EMAIL],
            plaintext_password=inner_user[REGISTER_FORM.PASSWORD],
        )
        new_user.id = idx
        valid_users.append(new_user)

    for idx, test_user in enumerate(valid_users):
        json_tag = json.dumps(test_user.serialized)
        valid_json_user = json.dumps(
            {
                MODEL_STRS.ID: idx,
                MODEL_STRS.USERNAME: member_users[idx][MODEL_STRS.USERNAME],
            }
        )

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
            MODEL_STRS.ID: Integer value defining the ID of the UTub,
            MODEL_STRS.NAME: String representing the UTub name
        }
    ]
    """
    # Start with empty UTubs, have the valid user be their creator and a member of them
    empty_utubs = (
        v_models.valid_empty_utub_1,
        v_models.valid_empty_utub_2,
        v_models.valid_empty_utub_3,
    )
    valid_user = v_models.valid_user_1
    new_user = Users(
        username=valid_user[MODEL_STRS.USERNAME],
        email=valid_user[REGISTER_FORM.EMAIL],
        plaintext_password=valid_user[REGISTER_FORM.PASSWORD],
    )

    valid_utubs = []  # Array used to store the serialized utub data to validate against

    for empty_utub in empty_utubs:
        new_utub = Utubs(
            name=empty_utub[MODEL_STRS.NAME],
            utub_creator=valid_user[MODEL_STRS.ID],
            utub_description="",
        )
        new_utub.set_last_updated()
        new_utub.id = empty_utub[MODEL_STRS.ID]
        new_utub.utub_creator = valid_user[MODEL_STRS.ID]

        # Add the valid user to the utub
        new_utub_user = Utub_Members()
        new_utub_user.to_user = new_user
        new_utub.members.append(new_utub_user)

        valid_utubs.append({MODEL_STRS.ID: new_utub.id, MODEL_STRS.NAME: new_utub.name})

    # Reverse considering the serialized values will be sorted by most recently updated
    valid_utubs.reverse()
    assert json.dumps(valid_utubs) == json.dumps(new_user.serialized_on_initial_load)


def test_utub_serialized_only_creator_no_urls_no_tags(
    app: Flask, every_user_makes_a_unique_utub
):
    """
    GIVEN a valid UTub that a user is a creator of, with no urls, no other members, and no no tags
    WHEN the user selects the UTub of interest, the backend sends JSON containing all relevant details of that
        UTub for the frontend to layout.
    THEN ensure the correctly serialized data is output as JSON.

    Format of the serialized JSON data is as follows:
    {
    MODEL_STRS.ID: Integer representing UTub ID,
    MODEL_STRS.NAME: String representing UTub name,
    MODEL_STRS.CREATED_BY: Integer representing creator ID,
    MODEL_STRS.CREATED_AT: Time UTub created, see this format (datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S")),
    MODEL_STRS.DESCRIPTION: String representing UTub description, "" if empty,
    MODEL_STRS.MEMBERS: Array containing each members information, in the following format:
        [
            {
                MODEL_STRS.ID: Integer representing the user's ID,
                MODEL_STRS.USERNAME: String representing the user's username
            }
        ]
    MODEL_STRS.Urls: Array containing all the URL information for this UTub, in the following format:
        [
            {
                MODEL_STRS.URL_ID: Integer repsenting the URL ID,
                MODEL_STRS.URL_STRING: String representing the URL,
                MODEL_STRS.URL_TAG_IDS: Array containing integer IDs of all tags on this URL, such as: [1, 2, 3],
                MODEL_STRS.ADDED_BY: Integer ID of user identifying who added this,
                MODEL_STRS.URL_TITLE: String representing a description of this URL in this UTub
            }
        ]
    MODEL_STRS.TAGS: Array containing all tag information for tags used in this UTub, in the following format:
        [
            {
                MODEL_STRS.ID: Integer representing the tag ID,
                MODEL_STRS.TAG_STRING: "String representing the tag itself
            }
        ]
    }
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()

        for test_utub, utub in zip(
            v_models.valid_utub_serializations_with_only_creator, all_utubs
        ):
            test_utub[MODEL_STRS.CREATED_AT] = utub.created_at.strftime(
                "%m/%d/%Y %H:%M:%S"
            )
            utub: Utubs = utub

            # Match creator elements
            test_utub[MODEL_STRS.IS_CREATOR] = utub.serialized(1)[MODEL_STRS.IS_CREATOR]
            assert json.dumps(test_utub) == json.dumps(utub.serialized(1))


def test_utub_serialized_creator_and_members_no_urls_no_tags(
    app: Flask, every_user_in_every_utub
):
    """
    GIVEN a valid UTub that a user is a creator of and has members in it, with no urls and no tags
    WHEN the user selects the UTub of interest, the backend sends JSON containing all relevant details of that
        UTub for the frontend to layout.
    THEN ensure the correctly serialized data is output as JSON.

    Format of the serialized JSON data is as follows:
    {
    MODEL_STRS.ID: Integer representing UTub ID,
    MODEL_STRS.NAME: String representing UTub name,
    MODEL_STRS.CREATED_BY: Integer representing creator ID,
    MODEL_STRS.CREATED_AT: Time UTub created, see this format (datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S")),
    MODEL_STRS.DESCRIPTION: String representing UTub description, "" if empty,
    MODEL_STRS.MEMBERS: Array containing each members information, in the following format:
        [
            {
                MODEL_STRS.ID: Integer representing the user's ID,
                MODEL_STRS.USERNAME: String representing the user's username
            }
        ]
    MODEL_STRS.Urls: Array containing all the URL information for this UTub, in the following format:
        [
            {
                MODEL_STRS.URL_ID: Integer repsenting the URL ID,
                MODEL_STRS.URL_STRING: String representing the URL,
                MODEL_STRS.URL_TAG_IDS: Array containing integer IDs of all tags on this URL, such as: [1, 2, 3],
                MODEL_STRS.ADDED_BY: Integer ID of user identifying who added this,
                MODEL_STRS.URL_TITLE: String representing a description of this URL in this UTub
            }
        ]
    MODEL_STRS.TAGS: Array containing all tag information for tags used in this UTub, in the following format:
        [
            {
                MODEL_STRS.ID: Integer representing the tag ID,
                MODEL_STRS.TAG_STRING: "String representing the tag itself
            }
        ]
    }
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()

        for test_utub, utub in zip(
            v_models.valid_utub_serializations_with_members, all_utubs
        ):
            test_utub[MODEL_STRS.CREATED_AT] = utub.created_at.strftime(
                "%m/%d/%Y %H:%M:%S"
            )

            # Array of members needs to be sorted by ID's to match
            utub_in_data_serialized = utub.serialized(1)
            utub_in_data_serialized[MODEL_STRS.MEMBERS] = sorted(
                utub_in_data_serialized[MODEL_STRS.MEMBERS],
                key=lambda test_user: test_user[MODEL_STRS.ID],
            )

            # Match creator elements
            test_utub[MODEL_STRS.IS_CREATOR] = utub_in_data_serialized[
                MODEL_STRS.IS_CREATOR
            ]

            assert json.dumps(test_utub) == json.dumps(utub_in_data_serialized)


def test_utub_serialized_creator_and_members_and_url_no_tags(
    app: Flask, add_one_url_and_all_users_to_each_utub_no_tags
):
    """
    GIVEN a valid UTub that a user is a creator of and has members in it, with one url in it and no tags
    WHEN the user selects the UTub of interest, the backend sends JSON containing all relevant details of that
        UTub for the frontend to layout.
    THEN ensure the correctly serialized data is output as JSON.

    Format of the serialized JSON data is as follows:
    {
    MODEL_STRS.ID: Integer representing UTub ID,
    MODEL_STRS.NAME: String representing UTub name,
    MODEL_STRS.IS_CREATOR: Boolean indicating if current user is the creator
    MODEL_STRS.CREATED_BY: Integer representing creator ID,
    MODEL_STRS.CREATED_AT: Time UTub created, see this format (datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S")),
    MODEL_STRS.DESCRIPTION: String representing UTub description, "" if empty,
    MODEL_STRS.MEMBERS: Array containing each members information, in the following format:
        [
            {
                MODEL_STRS.ID: Integer representing the user's ID,
                MODEL_STRS.USERNAME: String representing the user's username
            }
        ]
    MODEL_STRS.Urls: Array containing all the URL information for this UTub, in the following format:
        [
            {
                MODEL_STRS.URL_ID: Integer repsenting the URL ID,
                MODEL_STRS.URL_STRING: String representing the URL,
                MODEL_STRS.URL_TAG_IDS: Array containing integer IDs of all tags on this URL, such as: [1, 2, 3],
                MODEL_STRS.ADDED_BY: Integer ID of user identifying who added this,
                MODEL_STRS.URL_TITLE: String representing a description of this URL in this UTub
            }
        ]
    MODEL_STRS.TAGS: Array containing all tag information for tags used in this UTub, in the following format:
        [
            {
                MODEL_STRS.ID: Integer representing the tag ID,
                MODEL_STRS.TAG_STRING: "String representing the tag itself
            }
        ]
    }
    """
    with app.app_context():
        all_utubs = Utubs.query.all()

        for test_utub, utub in zip(
            v_models.valid_utub_serializations_with_members_and_url, all_utubs
        ):
            test_utub[MODEL_STRS.CREATED_AT] = utub.created_at.strftime(
                "%m/%d/%Y %H:%M:%S"
            )

            # Array of members needs to be sorted by ID's to match
            utub_in_data_serialized = utub.serialized(1)
            utub_in_data_serialized[MODEL_STRS.MEMBERS] = sorted(
                utub_in_data_serialized[MODEL_STRS.MEMBERS],
                key=lambda test_user: test_user[MODEL_STRS.ID],
            )

            # Set boolean for deleting equivalent since not considering a user session for this test
            for idx, _ in enumerate(test_utub[MODEL_STRS.URLS]):
                test_utub[MODEL_STRS.URLS][idx][MODEL_STRS.CAN_DELETE] = (
                    utub_in_data_serialized[MODEL_STRS.URLS][idx][MODEL_STRS.CAN_DELETE]
                )

            # Set boolean for deleting equivalent since not considering a user session for this test
            for idx in range(len(test_utub[MODEL_STRS.URLS])):
                test_utub[MODEL_STRS.URLS][idx][MODEL_STRS.CAN_DELETE] = (
                    utub_in_data_serialized[MODEL_STRS.URLS][idx][MODEL_STRS.CAN_DELETE]
                )

            # Match creator elements
            test_utub[MODEL_STRS.IS_CREATOR] = utub_in_data_serialized[
                MODEL_STRS.IS_CREATOR
            ]

            assert json.dumps(test_utub) == json.dumps(utub_in_data_serialized)


def test_utub_serialized_creator_and_members_and_urls_and_tags(
    app: Flask, add_all_urls_and_users_to_each_utub_with_all_tags
):
    """
    GIVEN a valid UTub that a user is a creator of and has members in it, with all urls and 3 tags per url
    WHEN the user selects the UTub of interest, the backend sends JSON containing all relevant details of that
        UTub for the frontend to layout.
    THEN ensure the correctly serialized data is output as JSON.

    Format of the serialized JSON data is as follows:
    {
    MODEL_STRS.ID: Integer representing UTub ID,
    MODEL_STRS.NAME: String representing UTub name,
    MODEL_STRS.CREATED_BY: Integer representing creator ID,
    MODEL_STRS.CREATED_AT: Time UTub created, see this format (datetime.utcnow().strftime("%m/%d/%Y %H:%M:%S")),
    MODEL_STRS.DESCRIPTION: String representing UTub description, "" if empty,
    MODEL_STRS.MEMBERS: Array containing each members information, in the following format:
        [
            {
                MODEL_STRS.ID: Integer representing the user's ID,
                MODEL_STRS.USERNAME: String representing the user's username
            }
        ]
    MODEL_STRS.Urls: Array containing all the URL information for this UTub, in the following format:
        [
            {
                MODEL_STRS.URL_ID: Integer repsenting the URL ID,
                MODEL_STRS.URL_STRING: String representing the URL,
                MODEL_STRS.URL_TAG_IDS: Array containing integer IDs of all tags on this URL, such as: [1, 2, 3],
                MODEL_STRS.ADDED_BY: Integer ID of user identifying who added this,
                MODEL_STRS.URL_TITLE: String representing a description of this URL in this UTub
            }
        ]
    MODEL_STRS.TAGS: Array containing all tag information for tags used in this UTub, in the following format:
        [
            {
                MODEL_STRS.ID: Integer representing the tag ID,
                MODEL_STRS.TAG_STRING: "String representing the tag itself
            }
        ]
    }
    """
    with app.app_context():
        all_utubs: list[Utubs] = Utubs.query.all()
        mock_utub_data = (
            v_models.valid_utub_serializations_with_members_and_url_and_tags
        )

        # Force UtubUrl ID's to match since they're given by database
        all_utub_urls: list[Utub_Urls] = Utub_Urls.query.all()
        for test_utub, utub in zip(mock_utub_data, all_utubs):
            for idx in range(len(test_utub[MODEL_STRS.URLS])):
                test_url = test_utub[MODEL_STRS.URLS][idx]
                real_url = [
                    url
                    for url in all_utub_urls
                    if url.utub_id == test_utub[MODEL_STRS.ID]
                    and url.standalone_url.url_string == test_url[MODEL_STRS.URL_STRING]
                ][-1]
                test_utub[MODEL_STRS.URLS][idx][MODEL_STRS.UTUB_URL_ID] = real_url.id

        for test_utub, utub in zip(mock_utub_data, all_utubs):
            test_utub[MODEL_STRS.CREATED_AT] = utub.created_at.strftime(
                "%m/%d/%Y %H:%M:%S"
            )

            # Array of members needs to be sorted by ID's to match
            utub_in_data_serialized = utub.serialized(1)
            utub_in_data_serialized[MODEL_STRS.MEMBERS] = sorted(
                utub_in_data_serialized[MODEL_STRS.MEMBERS],
                key=lambda test_user: test_user[MODEL_STRS.ID],
            )

            # Array of URLs needs to be sorted by UTUB_URL_ID to match
            test_utub[MODEL_STRS.URLS] = sorted(
                test_utub[MODEL_STRS.URLS],
                key=lambda utub_url: utub_url[MODEL_STRS.UTUB_URL_ID],
            )

            # Array of Tags needs to be sorted by ID to match
            utub_in_data_serialized[MODEL_STRS.TAGS] = sorted(
                utub_in_data_serialized[MODEL_STRS.TAGS],
                key=lambda utub_tag: utub_tag[MODEL_STRS.ID],
            )

            # Array of tag IDs in URLs must also be sorted
            for idx in range(len(utub_in_data_serialized[MODEL_STRS.URLS])):
                utub_in_data_serialized[MODEL_STRS.URLS][idx][
                    MODEL_STRS.URL_TAG_IDS
                ].sort()

            # Set boolean for deleting equivalent since not considering a user session for this test
            for idx in range(len(test_utub[MODEL_STRS.URLS])):
                test_utub[MODEL_STRS.URLS][idx][MODEL_STRS.CAN_DELETE] = (
                    utub_in_data_serialized[MODEL_STRS.URLS][idx][MODEL_STRS.CAN_DELETE]
                )

            # Set deletion for UTub based on equality
            utub_in_data_serialized[MODEL_STRS.IS_CREATOR] = (
                utub_in_data_serialized[MODEL_STRS.CREATED_BY]
                == test_utub[MODEL_STRS.CREATED_BY]
            )

            assert json.dumps(test_utub) == json.dumps(utub_in_data_serialized)
