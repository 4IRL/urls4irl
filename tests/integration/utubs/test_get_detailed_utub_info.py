from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user
import pytest

from src.models.utub_tags import Utub_Tags
from src.models.urls import Urls
from src.models.users import Users
from src.models.utubs import Utubs
from src.models.utub_urls import Utub_Urls
from src.utils.all_routes import ROUTES
from src.utils.strings.model_strs import MODELS
from src.utils.strings.url_validation_strs import URL_VALIDATION

pytestmark = pytest.mark.utubs


def test_get_valid_utub_as_creator(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a creator of a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the propery `isCreator` shows as True, and all other JSON data is given appropriately

    Args:
        add_single_utub_as_user_after_logging_in (Tuple[FlaskClient, int, str, Flask]): Fixture to create a new UTub for current user
    """
    client, _, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        utub_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub = utub_user_creator_of.id
        initial_last_updated = utub_user_creator_of.last_updated
        current_user_id = current_user.id
        current_user_username = current_user.username

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=id_of_utub),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json

    assert response_json is not None
    assert response_json[MODELS.ID] == id_of_utub
    assert response_json[MODELS.CREATED_BY] == current_user_id
    assert response_json[MODELS.DESCRIPTION] == utub_user_creator_of.utub_description
    assert response_json[MODELS.NAME] == utub_user_creator_of.name
    assert response_json[MODELS.IS_CREATOR] == (
        current_user_id == utub_user_creator_of.utub_creator
    )

    user_dict: dict[str, int | str] = {
        MODELS.ID: current_user_id,
        MODELS.USERNAME: current_user_username,
    }
    assert user_dict in response_json[MODELS.MEMBERS]
    assert len(response_json[MODELS.TAGS]) == 0
    assert len(response_json[MODELS.URLS]) == 0

    with app.app_context():
        utub_user_creator_of = Utubs.query.get(id_of_utub)
        assert (
            utub_user_creator_of.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_get_valid_utub_as_member(
    add_single_user_to_utub_without_logging_in,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a member of a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the propery `isCreator` shows as False, and all other JSON data is given appropriately

    Args:
        add_single_utub_as_user_after_logging_in (Tuple[FlaskClient, int, str, Flask]): Fixture to create a new UTub for current user
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub = utub_user_member_of.id
        initial_last_updated = utub_user_member_of.last_updated
        current_user_id = current_user.id
        current_user_username = current_user.username

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=id_of_utub),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json

    assert response_json is not None
    assert response_json[MODELS.ID] == id_of_utub
    assert response_json[MODELS.CREATED_BY] != current_user_id
    assert response_json[MODELS.DESCRIPTION] == utub_user_member_of.utub_description
    assert response_json[MODELS.NAME] == utub_user_member_of.name
    assert response_json[MODELS.IS_CREATOR] == (
        current_user_id == utub_user_member_of.utub_creator
    )

    user_dict: dict[str, int | str] = {
        MODELS.ID: current_user_id,
        MODELS.USERNAME: current_user_username,
    }
    assert user_dict in response_json[MODELS.MEMBERS]
    assert len(response_json[MODELS.TAGS]) == 0
    assert len(response_json[MODELS.URLS]) == 0

    with app.app_context():
        utub_user_member_of = Utubs.query.get(id_of_utub)
        assert (
            utub_user_member_of.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_get_valid_utub_as_not_member(
    every_user_makes_a_unique_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server resopnds with a 404 message

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_user_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub = utub_user_member_of.id

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=id_of_utub),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 404


def test_get_valid_utub_with_members_urls_no_tags(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is a member of a UTub with only one URL and no tags
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server responds with a 200 message, and proper JSON response

    Args:
        add_one_url_and_all_users_to_each_utub_no_tags (None): Fixture to create a new UTub for every user, with all users
            added as members, all URLs added, and every URL having every tag associated with it
        login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the user
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_member_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub = utub_user_is_member_of.id
        all_urls_in_utub: list[Utub_Urls] = utub_user_is_member_of.utub_urls
        only_url_in_utub: Utub_Urls = all_urls_in_utub[-1]
        standalone_url: Urls = only_url_in_utub.standalone_url
        initial_last_updated = utub_user_is_member_of.last_updated
        current_user_id = current_user.id

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_user_is_member_of.id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200

    response_json = response.json

    assert response_json is not None
    assert response_json[MODELS.ID] == utub_user_is_member_of.id
    assert response_json[MODELS.CREATED_BY] != current_user_id
    assert response_json[MODELS.DESCRIPTION] == utub_user_is_member_of.utub_description
    assert response_json[MODELS.NAME] == utub_user_is_member_of.name
    assert response_json[MODELS.IS_CREATOR] == (
        current_user_id == utub_user_is_member_of.utub_creator
    )

    # Clarify that this user did not add the URL to the UTub
    assert only_url_in_utub.user_id != current_user_id

    for url in all_urls_in_utub:
        url_dict = {
            MODELS.CAN_DELETE: current_user_id == url.user_id
            or current_user_id == utub_user_is_member_of.utub_creator,
            MODELS.UTUB_URL_ID: url.id,
            MODELS.URL_STRING: standalone_url.url_string,
            MODELS.URL_TAG_IDS: [],
            MODELS.URL_TITLE: url.url_title,
        }
        assert url_dict in response_json[MODELS.URLS]

    with app.app_context():
        utub_user_member_of = Utubs.query.get(id_of_utub)
        assert (
            utub_user_member_of.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_get_valid_utub_with_members_urls_tags(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is a member of a UTub with members, urls, and tags on URLs
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server resopnds with a 200 message, and proper JSON response

    Args:
        add_all_urls_and_users_to_each_utub_with_all_tags (None): Fixture to create a new UTub for every user, with all users
            added as members, all URLs added, and every URL having every tag associated with it
        login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask]): Fixture to login in the user
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        all_urls: list[Urls] = Urls.query.all()
        all_users: list[Users] = Users.query.all()

        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub = utub_user_is_creator_of.id
        all_urls_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_user_is_creator_of.id
        ).all()

        all_tags: list[Utub_Tags] = Utub_Tags.query.filter(
            Utub_Tags.utub_id == utub_user_is_creator_of.id
        ).all()
        initial_last_updated = utub_user_is_creator_of.last_updated
        current_user_id = current_user.id

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_user_is_creator_of.id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200

    response_json = response.json

    assert response_json is not None
    assert response_json[MODELS.ID] == utub_user_is_creator_of.id
    assert response_json[MODELS.CREATED_BY] == current_user_id
    assert response_json[MODELS.DESCRIPTION] == utub_user_is_creator_of.utub_description
    assert response_json[MODELS.NAME] == utub_user_is_creator_of.name
    assert response_json[MODELS.IS_CREATOR] == (
        current_user_id == utub_user_is_creator_of.utub_creator
    )

    assert len(response_json[MODELS.MEMBERS]) == len(all_users)
    assert len(response_json[MODELS.TAGS]) == len(all_tags)
    assert len(response_json[MODELS.URLS]) == len(all_urls)

    for user in all_users:
        user_dict: dict[str, int | str] = {
            MODELS.ID: user.id,
            MODELS.USERNAME: user.username,
        }
        assert user_dict in response_json[MODELS.MEMBERS]

    for url in all_urls_in_utub:
        url_string = [
            url_object for url_object in all_urls if url_object.id == url.url_id
        ][-1].url_string
        url_dict = {
            MODELS.CAN_DELETE: current_user_id == url.id
            or current_user_id == utub_user_is_creator_of.utub_creator,
            MODELS.UTUB_URL_ID: url.id,
            MODELS.URL_STRING: url_string,
            MODELS.URL_TAG_IDS: sorted([tag.id for tag in all_tags]),
            MODELS.URL_TITLE: f"This is {url_string}",
        }
        assert url_dict in response_json[MODELS.URLS]

    for tag in all_tags:
        tag_dict = {MODELS.ID: tag.id, MODELS.TAG_STRING: tag.tag_string}
        assert tag_dict in response_json[MODELS.TAGS]

    with app.app_context():
        utub_user_is_creator_of = Utubs.query.get(id_of_utub)
        assert (
            utub_user_is_creator_of.last_updated - initial_last_updated
        ).total_seconds() > 0
