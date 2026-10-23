from datetime import datetime, timedelta, timezone
from typing import Tuple
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user
from sqlalchemy import event, text

from backend import db
from backend.metrics.events import EventName
from backend.models.urls import Urls
from backend.models.user_preferences import SortOrder, User_Preferences
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utubs.services import read_utubs
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.settings_stub import DEFAULT_SETTINGS_DICT, STUB_KEY, patch_settings_model
from tests.utils_for_test import (
    count_tag_instances_in_utub,
    is_string_in_logs,
    remove_member,
    set_member_role,
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.utubs


def _capture_open_state(
    *, app: Flask, utub_id: int
) -> Tuple[datetime, dict[int, datetime | None]]:
    """Snapshot ``Utubs.last_updated`` and every member's ``last_opened_at``."""
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        members: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.utub_id == utub_id
        ).all()
        return utub.last_updated, {
            member.user_id: member.last_opened_at for member in members
        }


def _assert_open_recorded_only_for_caller(
    *,
    app: Flask,
    utub_id: int,
    caller_id: int,
    before: Tuple[datetime, dict[int, datetime | None]],
) -> None:
    """An open leaves ``Utubs.last_updated`` alone and stamps only the caller's row."""
    last_updated_before, opened_before = before
    after_last_updated, opened_after = _capture_open_state(app=app, utub_id=utub_id)

    assert after_last_updated == last_updated_before

    caller_before = opened_before[caller_id]
    caller_after = opened_after[caller_id]
    assert caller_after is not None
    assert caller_before is None or caller_after > caller_before

    for user_id, opened_at_before in opened_before.items():
        if user_id != caller_id:
            assert opened_after[user_id] == opened_at_before


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
        current_user_id = current_user.id
        current_user_username = current_user.username

    before_open = _capture_open_state(app=app, utub_id=id_of_utub)

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

    _assert_open_recorded_only_for_caller(
        app=app, utub_id=id_of_utub, caller_id=current_user_id, before=before_open
    )


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
        current_user_id = current_user.id
        current_user_username = current_user.username

    before_open = _capture_open_state(app=app, utub_id=id_of_utub)

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

    _assert_open_recorded_only_for_caller(
        app=app, utub_id=id_of_utub, caller_id=current_user_id, before=before_open
    )


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


def _get_can_delete_and_adder(
    *, client: FlaskClient, route: str, utub_id: int, utub_url_id: int
) -> Tuple[bool, int]:
    response = client.get(
        url_for(route, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200
    assert response.json is not None
    entry = next(
        url
        for url in response.json[MODELS.URLS]
        if url[MODELS.UTUB_URL_ID] == utub_url_id
    )
    return entry[MODELS.CAN_DELETE], entry[MODELS.ADDED_BY]


def test_utub_detail_can_delete_follows_orphan_rule_for_plain_member(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL added by member user 3, viewed by plain member user 2
    WHEN the adder is removed, then re-added to the UTub
    THEN `canDelete` (on GET and refresh) is False while the adder is a member, True
        once they are gone (with `addedByUserID` kept), and False again after re-adding
    """
    client, _, _, app = login_second_user_without_register
    adder_id = 3

    with app.app_context():
        utub: Utubs = Utubs.query.filter(Utubs.utub_creator == 1).first()
        utub_id = utub.id
        utub_url: Utub_Urls = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).first()
        utub_url.user_id = adder_id
        utub_url_id = utub_url.id
        db.session.commit()

    for route in (ROUTES.UTUBS.GET_SINGLE_UTUB, ROUTES.UTUBS.REFRESH_SINGLE_UTUB):
        assert _get_can_delete_and_adder(
            client=client, route=route, utub_id=utub_id, utub_url_id=utub_url_id
        ) == (False, adder_id)

    remove_member(app, utub_id, adder_id)

    for route in (ROUTES.UTUBS.GET_SINGLE_UTUB, ROUTES.UTUBS.REFRESH_SINGLE_UTUB):
        assert _get_can_delete_and_adder(
            client=client, route=route, utub_id=utub_id, utub_url_id=utub_url_id
        ) == (True, adder_id)

    with app.app_context():
        db.session.add(Utub_Members(utub_id=utub_id, user_id=adder_id))
        db.session.commit()

    for route in (ROUTES.UTUBS.GET_SINGLE_UTUB, ROUTES.UTUBS.REFRESH_SINGLE_UTUB):
        assert _get_can_delete_and_adder(
            client=client, route=route, utub_id=utub_id, utub_url_id=utub_url_id
        ) == (False, adder_id)


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


def test_get_trashed_utub_as_creator_is_404(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN the creator of a UTub that has been moved to trash
    WHEN the creator requests the details of that UTub
    THEN verify the server responds with a 404, exactly as for a deleted UTub
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        creator_user_id = current_user.id

    trash_utub(app, utub_id, deleted_by=creator_user_id)

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 404
    json_response = response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND


def test_get_trashed_utub_as_non_creator_member_is_404(
    every_user_in_every_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a UTub created by user 1 and trashed by them, where user 2 is a plain member
    WHEN user 2 (a non-creator member, not the deleter) requests the details of that UTub
    THEN verify the membership decorator responds with a 404
    """
    client, _, user, app = login_second_user_without_register

    with app.app_context():
        member_row: Utub_Members = Utub_Members.query.filter(
            Utub_Members.user_id == user.id,
            Utub_Members.member_role == Member_Role.MEMBER,
        ).first()
        trashed_utub_id = member_row.utub_id
        deleter_id = Utubs.query.get(trashed_utub_id).utub_creator

    trash_utub(app, trashed_utub_id, deleted_by=deleter_id)

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=trashed_utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 404
    json_response = response.get_json()
    assert json_response[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert json_response[STD_JSON.MESSAGE] == FAILURE_GENERAL.NOT_FOUND


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
        current_user_id = current_user.id

    before_open = _capture_open_state(app=app, utub_id=id_of_utub)

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
            MODELS.SHORT_LINK_EXPIRES_AT: None,
            MODELS.CAN_REVOKE_SHORT_LINK: False,
        }
        assert url_dict in response_json[MODELS.URLS]

    _assert_open_recorded_only_for_caller(
        app=app, utub_id=id_of_utub, caller_id=current_user_id, before=before_open
    )


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
        current_user_id = current_user.id

    before_open = _capture_open_state(app=app, utub_id=id_of_utub)

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
            MODELS.SHORT_LINK_EXPIRES_AT: None,
            MODELS.CAN_REVOKE_SHORT_LINK: False,
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

    _assert_open_recorded_only_for_caller(
        app=app, utub_id=id_of_utub, caller_id=current_user_id, before=before_open
    )


def test_get_single_utub_when_membership_deleted_concurrently_does_not_500(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a logged-in member whose UtubMembers row is deleted after the auth
        decorator loads it but before the service records the open
    WHEN they GET "/utubs/<utub_id>"
    THEN the bulk UPDATE affects 0 rows and the response is still 200
    """
    client, utub_id, _, _ = add_single_utub_as_user_after_logging_in
    real_record_open = read_utubs._record_utub_opened_by

    def delete_membership_then_record(*, utub_id: int, user_id: int) -> None:
        db.session.execute(
            text(
                'DELETE FROM "UtubMembers" '
                'WHERE "utubID" = :utub_id AND "userID" = :user_id'
            ),
            {"utub_id": utub_id, "user_id": user_id},
        )
        real_record_open(utub_id=utub_id, user_id=user_id)

    with mock.patch(
        "backend.utubs.services.read_utubs._record_utub_opened_by",
        side_effect=delete_membership_then_record,
    ):
        response = client.get(
            url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
            headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
        )

    assert response.status_code == 200


def test_get_utub_excludes_trashed_url(
    add_all_urls_and_users_to_each_utub_with_all_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a member of a UTub whose URLs all carry every tag, where one URL is in the
        trash
    WHEN the user requests the details of that UTub
    THEN verify the trashed URL is absent from the URL list, and each tag's
        tagApplied count counts only the live URLs
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        utub_user_is_creator_of: Utubs = Utubs.query.filter(
            Utubs.utub_creator == current_user.id
        ).first()
        utub_id = utub_user_is_creator_of.id
        creator_user_id = current_user.id
        utub_urls_in_utub: list[Utub_Urls] = Utub_Urls.query.filter(
            Utub_Urls.utub_id == utub_id
        ).all()
        trashed_utub_url_id = utub_urls_in_utub[0].id
        live_utub_url_ids = sorted(utub_url.id for utub_url in utub_urls_in_utub[1:])
        tag_ids_on_trashed_url = utub_urls_in_utub[0].associated_tag_ids
        assert len(tag_ids_on_trashed_url) > 0
        raw_counts_before = {
            tag_id: count_tag_instances_in_utub(utub_id, tag_id)
            for tag_id in tag_ids_on_trashed_url
        }

    trash_utub_url(app, trashed_utub_url_id, deleted_by=creator_user_id)

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json is not None

    returned_url_ids = sorted(
        url[MODELS.UTUB_URL_ID] for url in response_json[MODELS.URLS]
    )
    assert trashed_utub_url_id not in returned_url_ids
    assert returned_url_ids == live_utub_url_ids

    tags_by_id = {tag[MODELS.ID]: tag for tag in response_json[MODELS.TAGS]}
    for tag_id in tag_ids_on_trashed_url:
        # count_tag_instances_in_utub is a raw count, so the trashed row is excluded
        # by hand
        assert tags_by_id[tag_id][MODELS.TAG_APPLIED] == raw_counts_before[tag_id] - 1


def _get_detail_json(client: FlaskClient, utub_id: int) -> dict:
    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_id),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200
    assert response.json is not None
    return response.json


def test_get_utub_detail_null_settings_returns_defaults(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a UTub whose settings column is NULL
    WHEN a member requests the UTub detail
    THEN `settings` holds the resolved defaults
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in

    with app.app_context():
        assert Utubs.query.get(utub_id).settings is None

    response_json = _get_detail_json(client, utub_id)

    assert response_json[MODELS.SETTINGS] == DEFAULT_SETTINGS_DICT


def test_get_utub_detail_stored_override_merged_with_defaults(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    GIVEN a UTub with a stored override and a stubbed settings model
    WHEN a member requests the UTub detail
    THEN the override is merged over defaults and the stub's field is serialized
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in
    patch_settings_model(monkeypatch)

    response_json = _get_detail_json(client, utub_id)
    assert response_json[MODELS.SETTINGS]["urls"] == {STUB_KEY: False}

    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.settings = {"urls": {STUB_KEY: True}}
        db.session.commit()

    response_json = _get_detail_json(client, utub_id)
    assert response_json[MODELS.SETTINGS] == {
        "utubs": {},
        "members": {},
        "tags": {},
        "urls": {STUB_KEY: True},
    }


def test_get_utub_detail_takes_no_row_lock(
    add_single_utub_as_user_after_logging_in: Tuple[FlaskClient, int, str, Flask],
):
    """
    GIVEN a UTub
    WHEN a member requests the UTub detail
    THEN no FOR UPDATE / FOR NO KEY UPDATE statement is issued on Utubs
    """
    client, utub_id, _, app = add_single_utub_as_user_after_logging_in
    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    with app.app_context():
        engine = db.engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        _get_detail_json(client, utub_id)
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert statements
    assert not [
        statement
        for statement in statements
        if "FOR UPDATE" in statement.upper() or "FOR NO KEY UPDATE" in statement.upper()
    ]


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
