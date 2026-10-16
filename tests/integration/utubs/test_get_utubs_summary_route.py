from datetime import datetime, timedelta
from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask_login import current_user

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.users import UtubSummaryListSchema
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import UTUB_FORM
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.utils_for_test import (
    get_utub_url_id,
    is_string_in_logs,
    remove_member,
    trash_utub,
    trash_utub_url,
)

FIRST_UTUB_ID = 1
FIRST_USER_ID = 1
SECOND_USER_ID = 2
AJAX_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}

pytestmark = pytest.mark.utubs


def test_get_utubs_if_has_no_utubs(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, with no UTubs.
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an empty array in the JSON
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    response_json = response.json
    assert response_json == {
        MODELS.UTUBS: [],
        MODELS.TRASH_COUNT: 0,
        STD_JSON_RESPONSE.STATUS: STD_JSON_RESPONSE.SUCCESS,
    }


def test_get_utubs_if_has_one_utub(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, with one UTub.
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an array with one UTub in the JSON
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        all_utubs_in: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).all()
        utub_summary = {
            MODELS.UTUBS: [
                {
                    MODELS.ID: member.to_utub.id,
                    MODELS.NAME: member.to_utub.name,
                    MODELS.MEMBER_ROLE: member.member_role.value,
                    MODELS.IS_LOCKED: member.to_utub.is_locked,
                }
                for member in all_utubs_in
            ],
            MODELS.TRASH_COUNT: 0,
            STD_JSON_RESPONSE.STATUS: STD_JSON_RESPONSE.SUCCESS,
        }

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert utub_summary == response.json


def test_get_utubs_if_has_multiple_utubs(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, and is a member of multiple UTubs .
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an array with all utubs in the JSON
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        all_utubs_in: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).all()
        utub_summary = {
            MODELS.UTUBS: [
                {
                    MODELS.ID: member.to_utub.id,
                    MODELS.NAME: member.to_utub.name,
                    MODELS.MEMBER_ROLE: member.member_role.value,
                    MODELS.IS_LOCKED: member.to_utub.is_locked,
                }
                for member in all_utubs_in
            ]
        }

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert isinstance(response.json, dict)
    assert isinstance(response.json[MODELS.UTUBS], list)
    assert sorted(
        utub_summary[MODELS.UTUBS], key=lambda utub_item: utub_item[MODELS.ID]
    ) == sorted(response.json[MODELS.UTUBS], key=lambda utub_item: utub_item[MODELS.ID])


def test_get_utubs_summary_reflects_locked_state(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user who is a member of multiple UTubs, one of which
        is locked
    WHEN the user requests a summary of all their UTubs
    THEN verify the locked UTub's entry reports isLocked as True while an
        unlocked sibling UTub reports isLocked as False
    """
    client, _, _, app = login_first_user_without_register

    with app.app_context():
        members_utubs: list[Utub_Members] = Utub_Members.query.filter(
            Utub_Members.user_id == current_user.id
        ).all()
        locked_utub: Utubs = members_utubs[0].to_utub
        unlocked_utub: Utubs = members_utubs[1].to_utub
        locked_utub_id = locked_utub.id
        unlocked_utub_id = unlocked_utub.id

        # Assert-before-state: neither UTub is locked yet
        assert not locked_utub.is_locked
        assert not unlocked_utub.is_locked

        locked_utub.is_locked = True
        db.session.commit()

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert response.json is not None
    utubs_in_response = response.json[MODELS.UTUBS]

    locked_entry = next(
        entry for entry in utubs_in_response if entry[MODELS.ID] == locked_utub_id
    )
    unlocked_entry = next(
        entry for entry in utubs_in_response if entry[MODELS.ID] == unlocked_utub_id
    )
    assert locked_entry[MODELS.IS_LOCKED]
    assert not unlocked_entry[MODELS.IS_LOCKED]


def test_get_utubs_excludes_trashed_utub(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user who is a member of multiple UTubs, one of which
        is trashed
    WHEN the user requests a summary of all their UTubs
    THEN verify the trashed UTub is absent and every live UTub is present
    """
    client, _, user, app = login_first_user_without_register

    with app.app_context():
        member_utub_ids = sorted(
            membership.utub_id
            for membership in Utub_Members.query.filter(
                Utub_Members.user_id == user.id
            ).all()
        )
    trashed_utub_id = member_utub_ids[0]
    live_utub_ids = member_utub_ids[1:]
    assert len(live_utub_ids) >= 1
    trash_utub(app, trashed_utub_id, deleted_by=user.id)

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert response.json is not None
    response_utub_ids = sorted(
        utub_item[MODELS.ID] for utub_item in response.json[MODELS.UTUBS]
    )
    assert trashed_utub_id not in response_utub_ids
    assert response_utub_ids == live_utub_ids


def _get_trash_count(client: FlaskClient) -> int:
    response = client.get(url_for(ROUTES.UTUBS.GET_UTUBS), headers=AJAX_HEADERS)
    assert response.status_code == 200
    assert response.json is not None
    return response.json[MODELS.TRASH_COUNT]


def _get_trash_list_length(client: FlaskClient) -> int:
    response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)
    assert response.status_code == 200
    assert response.json is not None
    return len(response.json[MODELS.URLS]) + len(response.json[MODELS.UTUBS])


def test_get_utubs_trash_count_is_zero_with_nothing_trashed(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with live UTubs and URLs only
    WHEN the user requests a summary of all their UTubs
    THEN verify trashCount is 0
    """
    client, _, _, _ = login_first_user_without_register

    assert _get_trash_count(client) == 0


def test_get_utubs_trash_count_matches_trash_list_length(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a UTub creator who trashed one URL individually, then the whole UTub
    WHEN the user requests a summary of all their UTubs
    THEN verify trashCount is every URL row (the UTub rides its URLs along) plus the
        UTub row, and equals the length of the Trash list for the same user
    """
    client, _, user, app = login_first_user_without_register
    first_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, first_row_id, deleted_by=user.id)
    assert _get_trash_count(client) == 1

    trash_utub(app, FIRST_UTUB_ID, deleted_by=user.id)

    trash_count = _get_trash_count(client)
    assert trash_count == 4
    assert trash_count == _get_trash_list_length(client)


def test_get_utubs_trash_count_ignores_trashed_utub_for_non_creator(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed by its creator, user 1
    WHEN member user 2 requests a summary of all their UTubs
    THEN verify neither the UTub nor its ride-along URLs count for user 2
    """
    client, _, _, app = login_second_user_without_register
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)

    assert _get_trash_count(client) == _get_trash_list_length(client) == 0


def test_get_utubs_trash_count_ignores_utub_the_user_left(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed by its creator, who is then no longer a member row
    WHEN the user requests a summary of all their UTubs
    THEN verify nothing from that UTub counts
    """
    client, _, user, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, deleted_by=user.id)
    remove_member(app, FIRST_UTUB_ID, user.id)

    assert _get_trash_count(client) == _get_trash_list_length(client) == 0


def test_home_page_embeds_trash_count(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a UTub creator who trashed one URL individually, then the whole UTub
    WHEN the user loads /home
    THEN verify the trash count is embedded in its own JSON script tag
    """
    client, _, user, app = login_first_user_without_register
    trash_utub_url(app, get_utub_url_id(app, FIRST_UTUB_ID, 1), deleted_by=user.id)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=user.id)

    response = client.get(url_for(ROUTES.UTUBS.HOME))

    assert response.status_code == 200
    assert (
        b'<script id="trash-count-data" type="application/json">4</script>'
        in response.data
    )


def test_home_page_accepts_trash_view_query_param(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user
    WHEN the user loads /home?view=trash
    THEN verify the normal home page renders, with a zero trash count
    """
    client, _, _, _ = login_first_user_with_register

    response = client.get(url_for(ROUTES.UTUBS.HOME, view="trash"))

    assert response.status_code == 200
    assert (
        b'<script id="trash-count-data" type="application/json">0</script>'
        in response.data
    )


def test_get_utubs_sorted_based_on_last_updated(
    add_all_utubs_as_user_without_logging_in,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, and is a member of multiple UTubs .
    WHEN the user requests a summary of all
        their UTubs after modifying the UTubs
    THEN verify the response body contains an array with all utubs in the JSON,
        sorted by last updated
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        utub_summary = _get_ordered_utub_summary()

    last_utub_id = int(utub_summary[MODELS.UTUBS][-1][MODELS.ID])
    last_utub_name = str(utub_summary[MODELS.UTUBS][-1][MODELS.NAME])

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert utub_summary == response.json

    # Update the name of the last UTub
    response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=last_utub_id),
        json={UTUB_FORM.UTUB_NAME: last_utub_name + "88"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200

    # Check last UTub is now first
    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200
    with app.app_context():
        utub_summary = _get_ordered_utub_summary()
    assert utub_summary == response.json
    assert utub_summary[MODELS.UTUBS][0][MODELS.ID] == last_utub_id

    middle_utub_id = int(utub_summary[MODELS.UTUBS][-2][MODELS.ID])
    middle_utub_name = str(utub_summary[MODELS.UTUBS][-2][MODELS.NAME])

    # Update the name of the middle UTub
    response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=middle_utub_id),
        json={UTUB_FORM.UTUB_NAME: middle_utub_name + "88"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200

    # Check middle UTub is now first
    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200
    with app.app_context():
        utub_summary = _get_ordered_utub_summary()
    assert utub_summary == response.json
    assert utub_summary[MODELS.UTUBS][0][MODELS.ID] == middle_utub_id


def test_null_last_opened_at_falls_back_to_last_updated(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is a member of several UTubs, none opened (last_opened_at is NULL)
    WHEN the user requests a summary of all their UTubs
    THEN the order falls back to Utubs.last_updated, most recent first
    """
    client, _, user, app = login_first_user_without_register

    with app.app_context():
        memberships = Utub_Members.query.filter(Utub_Members.user_id == user.id).all()
        assert len(memberships) >= 2
        assert all(membership.last_opened_at is None for membership in memberships)
        expected_ids = [
            membership.utub_id
            for membership in sorted(
                memberships,
                key=lambda membership: membership.to_utub.last_updated,
                reverse=True,
            )
        ]

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert response.json is not None
    assert [item[MODELS.ID] for item in response.json[MODELS.UTUBS]] == expected_ids


def test_content_change_moves_utub_above_later_opened_utub(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user whose membership in one UTub has a last_opened_at later than every
        Utubs.last_updated, set directly in the DB (not via GET)
    WHEN a content change (name PATCH) later bumps a different UTub's last_updated
    THEN the changed UTub sorts above the opened one, since the key is the later of
        last_opened_at and last_updated
    """
    client, csrf_token, user, app = login_first_user_without_register

    with app.app_context():
        created_utub_ids = [
            membership.utub_id
            for membership in Utub_Members.query.filter(
                Utub_Members.user_id == user.id,
                Utub_Members.member_role == Member_Role.CREATOR,
            ).all()
        ]
        all_utubs = Utubs.query.join(
            Utub_Members, Utubs.id == Utub_Members.utub_id
        ).filter(Utub_Members.user_id == user.id)
        latest_last_updated = max(utub.last_updated for utub in all_utubs)
        changed_utub_id = created_utub_ids[0]
        opened_membership = Utub_Members.query.filter(
            Utub_Members.user_id == user.id,
            Utub_Members.utub_id != changed_utub_id,
        ).first()
        assert opened_membership is not None
        opened_utub_id = opened_membership.utub_id
        opened_membership.last_opened_at = latest_last_updated + timedelta(
            microseconds=1
        )
        changed_name = Utubs.query.get(changed_utub_id).name + "88"
        db.session.commit()

    # Before the content change, the opened UTub is first
    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200
    assert response.json is not None
    assert response.json[MODELS.UTUBS][0][MODELS.ID] == opened_utub_id

    response = client.patch(
        url_for(ROUTES.UTUBS.UPDATE_UTUB_NAME, utub_id=changed_utub_id),
        json={UTUB_FORM.UTUB_NAME: changed_name},
        headers={"X-CSRFToken": csrf_token},
    )
    assert response.status_code == 200

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200
    assert response.json is not None
    utub_ids = [item[MODELS.ID] for item in response.json[MODELS.UTUBS]]
    assert utub_ids[0] == changed_utub_id
    assert utub_ids.index(changed_utub_id) < utub_ids.index(opened_utub_id)


def test_opening_utub_moves_it_to_top_for_opener_only(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN three users who are all members of all three UTubs
    WHEN user 1 opens the UTub that is currently last in their sidebar
    THEN that UTub is first for user 1, and user 2's order is unchanged
    """
    client, _, _, app = login_first_user_without_register

    def _get_utub_ids() -> list[int]:
        response = client.get(
            url_for(ROUTES.UTUBS.GET_UTUBS),
            headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
        )
        assert response.status_code == 200
        assert response.json is not None
        return [item[MODELS.ID] for item in response.json[MODELS.UTUBS]]

    user_1_order_before = _get_utub_ids()
    utub_to_open = user_1_order_before[-1]
    assert user_1_order_before[0] != utub_to_open

    with app.app_context():
        user_2 = Users.query.get(2)
        user_2_order_before = [
            item.id
            for item in UtubSummaryListSchema.from_user(user_2, trash_count=0).utubs
        ]

    response = client.get(
        url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=utub_to_open),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )
    assert response.status_code == 200

    assert _get_utub_ids()[0] == utub_to_open

    with app.app_context():
        user_2 = Users.query.get(2)
        user_2_order_after = [
            item.id
            for item in UtubSummaryListSchema.from_user(user_2, trash_count=0).utubs
        ]
    assert user_2_order_after == user_2_order_before


def _get_ordered_utub_summary() -> dict[str, list[dict[str, int | str]] | str | int]:
    all_utubs: list[Tuple[Utubs, Member_Role, datetime | None]] = (
        db.session.query(Utubs, Utub_Members.member_role, Utub_Members.last_opened_at)
        .join(Utub_Members, Utubs.id == Utub_Members.utub_id)
        .filter(Utub_Members.user_id == current_user.id)
        .all()
    )
    all_utubs.sort(
        key=lambda row: max(row[2] or row[0].last_updated, row[0].last_updated),
        reverse=True,
    )
    return {
        STD_JSON_RESPONSE.STATUS: STD_JSON_RESPONSE.SUCCESS,
        MODELS.UTUBS: [
            {
                MODELS.ID: utub.id,
                MODELS.NAME: utub.name,
                MODELS.MEMBER_ROLE: member.value,
                MODELS.IS_LOCKED: utub.is_locked,
            }
            for utub, member, _ in all_utubs
        ],
        MODELS.TRASH_COUNT: 0,
    }


def test_get_utubs_without_ajax_request(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with ID == 1, with one UTub.
    WHEN the user requests a summary of all
        their UTubs
    THEN verify the response body contains an array with one UTub in the JSON
    """
    client, _, _, _ = login_first_user_without_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: "not-ajax"},
    )

    assert response.status_code == 302


def test_get_utubs_success_logs(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a logged in user with ID == 1, and is a member of multiple UTubs .
    WHEN the user requests a summary of all their UTubs
    THEN verify the app logs are valid
    """
    client, _, user, _ = login_first_user_without_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST},
    )

    assert response.status_code == 200
    assert is_string_in_logs(f"Returning UTubs for User={user.id}", caplog.records)


def test_get_utubs_without_ajax_request_logs(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
):
    """
    GIVEN a logged in user with ID == 1, with one UTub.
    WHEN the user requests a summary of all their UTubs
    THEN verify the app logs are correct
    """
    client, _, user, _ = login_first_user_without_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_UTUBS),
        headers={URL_VALIDATION.X_REQUESTED_WITH: "not-ajax"},
    )

    assert response.status_code == 302
    assert is_string_in_logs(
        f"User={user.id} did not make an AJAX request", caplog.records
    )
