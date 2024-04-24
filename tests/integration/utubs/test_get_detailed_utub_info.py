from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user
import pytest

from src.models import Tags, URLS, User, Utub
from src.utils.all_routes import ROUTES
from src.utils.strings.model_strs import MODELS

pytestmark = pytest.mark.utubs


def test_get_valid_utub_as_creator(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask]
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
        utub_user_creator_of: Utub = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()
        id_of_utub = utub_user_creator_of.id

    response = client.get(_build_get_utub_route(id_of_utub))

    assert response.status_code == 200
    response_json = response.json

    assert response_json[MODELS.ID] == id_of_utub
    assert response_json[MODELS.CREATED_BY] == current_user.id
    assert response_json[MODELS.DESCRIPTION] == utub_user_creator_of.utub_description
    assert response_json[MODELS.NAME] == utub_user_creator_of.name
    assert response_json[MODELS.IS_CREATOR] == (
        current_user.id == utub_user_creator_of.utub_creator
    )

    user_dict: dict[str, int | str] = {
        MODELS.ID: current_user.id,
        MODELS.USERNAME: current_user.username,
    }
    assert user_dict in response_json[MODELS.MEMBERS]
    assert len(response_json[MODELS.TAGS]) == 0
    assert len(response_json[MODELS.URLS]) == 0


def test_get_valid_utub_as_member(
    add_single_user_to_utub_without_logging_in,
    login_second_user_without_register: Tuple[FlaskClient, str, User, Flask],
):
    """
    GIVEN a member of a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the propery `isCreator` shows as False, and all other JSON data is given appropriately

    Args:
        add_single_utub_as_user_after_logging_in (Tuple[FlaskClient, int, str, Flask]): Fixture to create a new UTub for current user
        login_second_user_without_register: Tuple[FlaskClient, str, User, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_user_member_of: Utub = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        id_of_utub = utub_user_member_of.id

    response = client.get(_build_get_utub_route(id_of_utub))

    assert response.status_code == 200
    response_json = response.json

    assert response_json[MODELS.ID] == id_of_utub
    assert response_json[MODELS.CREATED_BY] != current_user.id
    assert response_json[MODELS.DESCRIPTION] == utub_user_member_of.utub_description
    assert response_json[MODELS.NAME] == utub_user_member_of.name
    assert response_json[MODELS.IS_CREATOR] == (
        current_user.id == utub_user_member_of.utub_creator
    )

    user_dict: dict[str, int | str] = {
        MODELS.ID: current_user.id,
        MODELS.USERNAME: current_user.username,
    }
    assert user_dict in response_json[MODELS.MEMBERS]
    assert len(response_json[MODELS.TAGS]) == 0
    assert len(response_json[MODELS.URLS]) == 0


def test_get_valid_utub_as_not_member(
    every_user_makes_a_unique_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, User, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server resopnds with a 404 message

    Args:
        every_user_makes_a_unique_utub (None): Fixture to create a new UTub for every user, with no members but the creators
        login_second_user_without_register: Tuple[FlaskClient, str, User, Flask]): Fixture to login in the member instead of UTub creator
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_user_member_of: Utub = Utub.query.filter(
            Utub.utub_creator != current_user.id
        ).first()
        id_of_utub = utub_user_member_of.id

    response = client.get(_build_get_utub_route(id_of_utub))

    assert response.status_code == 404


def test_get_valid_utub_with_members_urls_tags(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, User, Flask],
):
    """
    GIVEN a user who is not a member a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the server resopnds with a 404 message

    Args:
        add_all_urls_and_users_to_each_utub_with_all_tags (None): Fixture to create a new UTub for every user, with all users
            added as members, all URLs added, and every URL having every tag associated with it
        login_first_user_without_register: Tuple[FlaskClient, str, User, Flask]): Fixture to login in the user
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        all_tags: list[Tags] = Tags.query.all()
        all_urls: list[URLS] = URLS.query.all()
        all_users: list[User] = User.query.all()

        utub_user_is_creator_of: Utub = Utub.query.filter(
            Utub.utub_creator == current_user.id
        ).first()

    response = client.get(_build_get_utub_route(utub_user_is_creator_of.id))
    assert response.status_code == 200

    response_json = response.json

    assert response_json[MODELS.ID] == utub_user_is_creator_of.id
    assert response_json[MODELS.CREATED_BY] == current_user.id
    assert response_json[MODELS.DESCRIPTION] == utub_user_is_creator_of.utub_description
    assert response_json[MODELS.NAME] == utub_user_is_creator_of.name
    assert response_json[MODELS.IS_CREATOR] == (
        current_user.id == utub_user_is_creator_of.utub_creator
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

    for url in all_urls:
        url_dict = {
            MODELS.ADDED_BY: url.created_by,
            MODELS.URL_ID: url.id,
            MODELS.URL_STRING: url.url_string,
            MODELS.URL_TAGS: sorted([tag.id for tag in all_tags]),
            MODELS.URL_TITLE: f"This is {url.url_string}",
        }
        assert url_dict in response_json[MODELS.URLS]

    for tag in all_tags:
        tag_dict = {MODELS.ID: tag.id, MODELS.TAG_STRING: tag.tag_string}
        assert tag_dict in response_json[MODELS.TAGS]


def _build_get_utub_route(utub_id: int) -> str:
    return url_for(ROUTES.UTUBS.HOME, UTubID=utub_id)
