from datetime import datetime, timedelta, timezone
from typing import Tuple

from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user
import pytest

from backend import db
from backend.metrics.events import EventName
from backend.models.user_preferences import SortOrder, User_Preferences
from backend.models.utub_members import Member_Role
from backend.models.utub_tags import Utub_Tags
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utubs import Utubs
from backend.models.utub_urls import Utub_Urls
from backend.utils.all_routes import ROUTES
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.utils_for_test import (
    count_tag_instances_in_utub,
    is_string_in_logs,
    set_member_role,
)

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
    assert response_json[MODELS.IS_CO_CREATOR] is False
    assert response_json[MODELS.CURRENT_USER] == current_user_id

    user_dict: dict[str, int | str] = {
        MODELS.ID: current_user_id,
        MODELS.USERNAME: current_user_username,
        MODELS.MEMBER_ROLE: Member_Role.CREATOR.value,
    }
    assert user_dict in response_json[MODELS.MEMBERS]
    assert len(response_json[MODELS.TAGS]) == 0
    assert len(response_json[MODELS.URLS]) == 0

    with app.app_context():
        utub_user_creator_of = Utubs.query.get(id_of_utub)
        assert (
            utub_user_creator_of.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_get_single_utub_records_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a logged-in user, a UTub they are a member of, and metrics enabled
    WHEN they GET "/utubs/<utub_id>"
    THEN the request succeeds with HTTP 200 AND exactly one UTUB_OPENED
        counter key is written to the metrics Redis DB.

    The setup fixture inserts the UTub directly via the ORM (bypassing
    the service layer) so no UTUB_CREATED counter is emitted during
    setup — only UTUB_OPENED should be observable.
    """
    client, utub_id, _, _ = add_single_utub_as_user_after_logging_in

    # Before-state: no UTUB_OPENED counter exists yet
    assert count_counter_keys(provide_metrics_redis, EventName.UTUB_OPENED) == 0

    get_single_utub_response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert get_single_utub_response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.UTUB_OPENED) == 1


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
    assert response_json[MODELS.IS_CO_CREATOR] is False
    assert response_json[MODELS.CURRENT_USER] == current_user_id

    user_dict: dict[str, int | str] = {
        MODELS.ID: current_user_id,
        MODELS.USERNAME: current_user_username,
        MODELS.MEMBER_ROLE: Member_Role.MEMBER.value,
    }
    assert user_dict in response_json[MODELS.MEMBERS]
    assert len(response_json[MODELS.TAGS]) == 0
    assert len(response_json[MODELS.URLS]) == 0

    with app.app_context():
        utub_user_member_of = Utubs.query.get(id_of_utub)
        assert (
            utub_user_member_of.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_get_valid_utub_as_co_creator(
    add_co_creator_to_utub_without_logging_in,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a co-creator (co-owner) of a UTub (user ID == 2)
    WHEN the user requests the details of that UTub
    THEN verify `isCreator` is False, `isCoCreator` is True, and each member
        entry carries the correct `memberRole` (creator for the owner,
        cocreator for the co-owner viewer).
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_user_co_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub = utub_user_co_creator_of.id
        creator_id = utub_user_co_creator_of.utub_creator
        current_user_id = current_user.id
        current_user_username = current_user.username

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=id_of_utub),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json

    assert response_json is not None
    assert response_json[MODELS.IS_CREATOR] is False
    assert response_json[MODELS.IS_CO_CREATOR] is True
    assert response_json[MODELS.CURRENT_USER] == current_user_id

    co_creator_dict: dict[str, int | str] = {
        MODELS.ID: current_user_id,
        MODELS.USERNAME: current_user_username,
        MODELS.MEMBER_ROLE: Member_Role.CO_CREATOR.value,
    }
    assert co_creator_dict in response_json[MODELS.MEMBERS]

    creator_entry = next(
        member
        for member in response_json[MODELS.MEMBERS]
        if member[MODELS.ID] == creator_id
    )
    assert creator_entry[MODELS.MEMBER_ROLE] == Member_Role.CREATOR.value


def test_get_valid_utub_as_creator_with_co_creator_present(
    add_co_creator_to_utub_without_logging_in,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the literal creator (user ID == 1) of a UTub that also has a co-creator
    WHEN the creator requests the details of that UTub
    THEN verify `isCreator` is True and `isCoCreator` is False (the literal-owner
        signal stays strictly literal even when co-creators exist).
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub = utub_user_creator_of.id
        current_user_id = current_user.id

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=id_of_utub),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json

    assert response_json is not None
    assert response_json[MODELS.IS_CREATOR] is True
    assert response_json[MODELS.IS_CO_CREATOR] is False
    assert response_json[MODELS.CURRENT_USER] == current_user_id

    co_creator_entry = next(
        member
        for member in response_json[MODELS.MEMBERS]
        if member[MODELS.MEMBER_ROLE] == Member_Role.CO_CREATOR.value
    )
    assert co_creator_entry[MODELS.ID] != current_user_id


def test_get_valid_utub_as_co_creator_can_delete_others_url(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a co-creator (user ID == 2) of a UTub that holds a URL added by a DIFFERENT
        member (the literal creator)
    WHEN the co-creator requests the details of that UTub
    THEN verify `isCoCreator` is True and that URL's `canDelete` is True — the client's
        canDelete snapshot must match the co-owner's server-side delete right (DD-1).
    """
    client, _, _, app = login_second_user_without_register

    with app.app_context():
        utub_user_co_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator != current_user.id
        ).first()
        id_of_utub = utub_user_co_creator_of.id
        current_user_id = current_user.id
        others_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == id_of_utub,
            Utub_Urls.user_id != current_user_id,
        ).first()
        others_url_id = others_url.id
        # Sanity: the URL was added by someone other than the co-creator viewer.
        assert others_url.user_id != current_user_id

    set_member_role(app, id_of_utub, current_user_id, Member_Role.CO_CREATOR)

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=id_of_utub),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json

    assert response_json is not None
    assert response_json[MODELS.IS_CREATOR] is False
    assert response_json[MODELS.IS_CO_CREATOR] is True

    url_entry = next(
        url
        for url in response_json[MODELS.URLS]
        if url[MODELS.UTUB_URL_ID] == others_url_id
    )
    assert url_entry[MODELS.CAN_DELETE] is True


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
    assert response_json[MODELS.CURRENT_USER] == current_user_id

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
            "addedAt": url.added_at.isoformat(),
            MODELS.ADDED_BY: url.user_id,
        }
        assert url_dict in response_json[MODELS.URLS]

    with app.app_context():
        utub_user_member_of = Utubs.query.get(id_of_utub)
        assert (
            utub_user_member_of.last_updated - initial_last_updated
        ).total_seconds() > 0


def _assign_distinct_sort_values(utub: Utubs) -> None:
    """Give each of the UTub's URL rows a distinct ``added_at`` and ``url_title``
    so the three sort orders (NEWEST/OLDEST/TITLE_AZ) each produce a distinct,
    deterministic permutation — not relying on the fixture's near-simultaneous
    default timestamps."""
    base_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    # Insertion order 0,1,2; NEWEST → 0,2,1; OLDEST → 1,2,0; TITLE_AZ → 1,2,0→ a,B,C.
    per_url = [
        (base_time + timedelta(days=2), "Charlie"),
        (base_time + timedelta(days=0), "alpha"),
        (base_time + timedelta(days=1), "Bravo"),
    ]
    utub_urls = list(utub.utub_urls)
    assert len(utub_urls) == len(per_url)
    for utub_url, (added_at, url_title) in zip(utub_urls, per_url):
        utub_url.added_at = added_at
        utub_url.url_title = url_title
    db.session.commit()


@pytest.mark.parametrize(
    "sort_order",
    [SortOrder.NEWEST, SortOrder.OLDEST, SortOrder.TITLE_AZ],
    ids=["newest", "oldest", "title_az"],
)
def test_get_utub_urls_ordered_by_default_sort_preference(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    sort_order: SortOrder,
):
    """DD-36: the returned URL list is ordered server-side by the viewing user's
    saved ``default_sort`` preference — NEWEST/OLDEST by ``added_at``, TITLE_AZ by
    case-insensitive ``url_title``."""
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()
        utub_id = utub.id
        _assign_distinct_sort_values(utub)

        db.session.add(
            User_Preferences(user_id=current_user.id, default_sort=sort_order)
        )
        db.session.commit()

        refreshed_utub: Utubs = Utubs.query.get(utub_id)
        if sort_order == SortOrder.NEWEST:
            expected = sorted(
                refreshed_utub.utub_urls,
                key=lambda utub_url: utub_url.added_at,
                reverse=True,
            )
        elif sort_order == SortOrder.OLDEST:
            expected = sorted(
                refreshed_utub.utub_urls, key=lambda utub_url: utub_url.added_at
            )
        else:
            expected = sorted(
                refreshed_utub.utub_urls,
                key=lambda utub_url: utub_url.url_title.lower(),
            )
        expected_ids = [utub_url.id for utub_url in expected]

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json is not None
    actual_ids = [url[MODELS.UTUB_URL_ID] for url in response_json[MODELS.URLS]]
    assert actual_ids == expected_ids


def test_get_utub_urls_defaults_to_newest_without_preferences_row(
    add_all_urls_and_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """DD-36: with no ``UserPreferences`` row (pre-existing user), the URL list
    defaults to NEWEST (``added_at`` descending), mirroring the None-row
    defaulting used throughout the preferences feature."""
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == current_user.id).first()
        utub_id = utub.id
        _assign_distinct_sort_values(utub)
        assert current_user.preferences is None

        refreshed_utub: Utubs = Utubs.query.get(utub_id)
        expected_ids = [
            utub_url.id
            for utub_url in sorted(
                refreshed_utub.utub_urls,
                key=lambda utub_url: utub_url.added_at,
                reverse=True,
            )
        ]

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json is not None
    actual_ids = [url[MODELS.UTUB_URL_ID] for url in response_json[MODELS.URLS]]
    assert actual_ids == expected_ids


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
    assert response_json[MODELS.CURRENT_USER] == current_user_id

    assert len(response_json[MODELS.MEMBERS]) == len(all_users)
    assert len(response_json[MODELS.TAGS]) == len(all_tags)
    assert len(response_json[MODELS.URLS]) == len(all_urls)

    for user in all_users:
        expected_role = (
            Member_Role.CREATOR.value
            if user.id == utub_user_is_creator_of.utub_creator
            else Member_Role.MEMBER.value
        )
        user_dict: dict[str, int | str] = {
            MODELS.ID: user.id,
            MODELS.USERNAME: user.username,
            MODELS.MEMBER_ROLE: expected_role,
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
            "addedAt": url.added_at.isoformat(),
            MODELS.ADDED_BY: url.user_id,
        }
        assert url_dict in response_json[MODELS.URLS]

    for tag in all_tags:
        tag_id = tag.id
        tag_dict = {
            MODELS.ID: tag_id,
            MODELS.TAG_STRING: tag.tag_string,
            MODELS.TAG_APPLIED: count_tag_instances_in_utub(id_of_utub, tag_id),
        }
        assert tag_dict in response_json[MODELS.TAGS]

    with app.app_context():
        utub_user_is_creator_of = Utubs.query.get(id_of_utub)
        assert (
            utub_user_is_creator_of.last_updated - initial_last_updated
        ).total_seconds() > 0


def test_get_utub_detail_reflects_locked_state(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a member of a UTub that has been locked
    WHEN the user requests the details of that UTub
    THEN verify the response body reports isLocked as True
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        utub_to_lock: Utubs = Utubs.query.get(utub_id)

        # Assert-before-state: the UTub is not locked yet
        assert not utub_to_lock.is_locked

        utub_to_lock.is_locked = True
        db.session.commit()

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json

    assert response_json is not None
    assert response_json[MODELS.IS_LOCKED]


def test_get_utub_detail_reflects_unlocked_state(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a member of a UTub that has not been locked
    WHEN the user requests the details of that UTub
    THEN verify the response body reports isLocked as False by default
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        utub_detail: Utubs = Utubs.query.get(utub_id)

        # Assert-before-state: the UTub is not locked
        assert not utub_detail.is_locked

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json

    assert response_json is not None
    assert not response_json[MODELS.IS_LOCKED]


def test_get_valid_utub_success_logs(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
    caplog,
):
    """
    GIVEN a creator of a newly formed UTub
    WHEN the user requests the details of that newly formed UTub
    THEN verify the app logs correctly
    """
    client, _, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        utub_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub = utub_user_creator_of.id

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=id_of_utub),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200

    assert is_string_in_logs(
        f"Retrieving UTub.id={id_of_utub} from direct route", caplog.records
    )


def test_get_valid_utub_without_ajax_request_logs(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
    caplog,
):
    """
    GIVEN a creator of a newly formed UTub
    WHEN the user requests the details of that newly formed UTub without an AJAX request
    THEN verify the app logs correctly
    """
    client, _, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        utub_user_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        id_of_utub = utub_user_creator_of.id
        current_user_id = current_user.id

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=id_of_utub),
        headers={URL_VALIDATION.X_REQUESTED_WITH: "not-ajax"},
    )

    assert response.status_code == 302
    assert is_string_in_logs(
        f"User={current_user_id} did not make an AJAX request", caplog.records
    )
