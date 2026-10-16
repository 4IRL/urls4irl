from datetime import datetime, timedelta
from typing import Any, Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.trash import (
    TrashedUrlItemSchema,
    TrashedUtubItemSchema,
    TrashListResponseSchema,
)
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME
from scripts.trash_retention import TRASH_RETENTION_DAYS
from tests.integration.trash.trash_helpers import AJAX_HEADERS
from tests.utils_for_test import (
    get_utub_url_id,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.trash

FIRST_UTUB_ID = 1
FIRST_USER_ID = 1
SECOND_USER_ID = 2
THIRD_USER_ID = 3

URL_ITEM_KEYS = {
    MODELS.UTUB_URL_ID,
    MODELS.URL_STRING,
    MODELS.URL_TITLE,
    UTUB_ID,
    UTUB_NAME,
    MODELS.ORIGIN_UTUB_TRASHED,
    MODELS.ORIGIN_UTUB_LOCKED,
    MODELS.TRASHED_WITH_UTUB,
    MODELS.DELETED_AT,
    MODELS.EXPIRES_AT,
    MODELS.DELETED_BY,
    MODELS.DELETED_BY_USERNAME,
    MODELS.ADDED_BY,
    MODELS.ADDED_BY_USERNAME,
    MODELS.CAN_RESTORE,
    MODELS.CAN_DELETE,
}
UTUB_ITEM_KEYS = {
    UTUB_ID,
    UTUB_NAME,
    MODELS.UTUB_DESCRIPTION,
    MODELS.DELETED_AT,
    MODELS.EXPIRES_AT,
    MODELS.DELETED_BY,
    MODELS.DELETED_BY_USERNAME,
    MODELS.URL_COUNT,
    MODELS.MEMBER_COUNT,
    MODELS.IS_LOCKED,
    MODELS.CAN_RESTORE,
    MODELS.CAN_DELETE,
}
LIST_KEYS = {
    MODELS.URLS,
    MODELS.UTUBS,
    MODELS.CURRENT_USER,
    MODELS.RETENTION_DAYS,
    MODELS.LISTED_AT,
    STD_JSON_RESPONSE.STATUS,
}


def get_trash(client: FlaskClient) -> dict[str, Any]:
    response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)
    assert response.status_code == 200
    response_json: dict[str, Any] = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.SUCCESS
    # assert_response_conforms_to_schema is not used: APIResponse injects an extra
    # ``status`` key that the schema does not declare, so validate the body directly.
    TrashListResponseSchema.model_validate(response_json)
    assert set(response_json.keys()) == LIST_KEYS
    return response_json


def trashed_url_ids(response_json: dict[str, Any]) -> list[int]:
    return [item[MODELS.UTUB_URL_ID] for item in response_json[MODELS.URLS]]


def trash_first_utub_urls(app: Flask, deleted_by: int) -> dict[int, int]:
    """Trash the three URL rows of UTub 1; returns {url_id: utub_url_id}."""
    row_ids = {
        url_id: get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)
    }
    for row_id in row_ids.values():
        trash_utub_url(app, row_id, deleted_by)
    return row_ids


def test_get_trash_when_nothing_is_trashed(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user with no trashed URLs or UTubs
    WHEN the user requests their Trash
    THEN the lists are empty and the retention window, user and read time are reported
    """
    client, _, user, _ = login_first_user_with_register

    before_request = utc_now()
    response_json = get_trash(client)
    after_request = utc_now()

    assert response_json[MODELS.URLS] == []
    assert response_json[MODELS.UTUBS] == []
    assert response_json[MODELS.RETENTION_DAYS] == TRASH_RETENTION_DAYS == 30
    assert response_json[MODELS.CURRENT_USER] == user.id
    assert (
        before_request
        <= datetime.fromisoformat(response_json[MODELS.LISTED_AT])
        <= after_request
    )


def test_get_trash_ignores_live_rows(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user who is a member of UTubs holding only live URLs
    WHEN the user requests their Trash
    THEN nothing is listed
    """
    client, _, _, _ = login_first_user_without_register

    response_json = get_trash(client)

    assert response_json[MODELS.URLS] == []
    assert response_json[MODELS.UTUBS] == []


def test_get_trash_creator_sees_every_trashed_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN three URLs added by users 1, 2 and 3 to UTub 1, all trashed
    WHEN the UTub creator requests their Trash
    THEN all three rows are listed with their exact item shape and restore/delete rights
    """
    client, _, user, app = login_first_user_without_register
    row_ids = trash_first_utub_urls(app, deleted_by=FIRST_USER_ID)

    response_json = get_trash(client)

    assert sorted(trashed_url_ids(response_json)) == sorted(row_ids.values())
    assert response_json[MODELS.UTUBS] == []
    for item in response_json[MODELS.URLS]:
        assert set(item.keys()) == URL_ITEM_KEYS
        TrashedUrlItemSchema.model_validate(item)
        assert item[UTUB_ID] == FIRST_UTUB_ID
        assert item[MODELS.ORIGIN_UTUB_TRASHED] is False
        assert item[MODELS.ORIGIN_UTUB_LOCKED] is False
        assert item[MODELS.TRASHED_WITH_UTUB] is False
        assert item[MODELS.DELETED_BY] == user.id
        assert item[MODELS.DELETED_BY_USERNAME] == user.username
        assert item[MODELS.CAN_RESTORE] is True
        assert item[MODELS.CAN_DELETE] is True


def test_get_trash_member_sees_only_urls_they_added(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN three trashed URLs in UTub 1, of which user 2 added one
    WHEN plain member user 2 requests their Trash
    THEN only the URL they added is listed, with that adder attribution
    """
    client, _, user, app = login_second_user_without_register
    row_ids = trash_first_utub_urls(app, deleted_by=FIRST_USER_ID)

    response_json = get_trash(client)

    assert trashed_url_ids(response_json) == [row_ids[2]]
    item = response_json[MODELS.URLS][0]
    assert item[MODELS.ADDED_BY] == user.id
    assert item[MODELS.ADDED_BY_USERNAME] == user.username
    assert item[MODELS.DELETED_BY] == FIRST_USER_ID
    assert response_json[MODELS.UTUBS] == []


def test_get_trash_co_creator_sees_every_trashed_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN three trashed URLs in UTub 1 and user 3 promoted to CO_CREATOR
    WHEN user 3 requests their Trash
    THEN all three URLs are listed, but no trashed UTubs (they did not create UTub 1)
    """
    client, _, _, app = login_third_user_without_register
    row_ids = trash_first_utub_urls(app, deleted_by=FIRST_USER_ID)
    set_member_role(app, FIRST_UTUB_ID, THIRD_USER_ID, Member_Role.CO_CREATOR)

    response_json = get_trash(client)

    assert sorted(trashed_url_ids(response_json)) == sorted(row_ids.values())
    assert response_json[MODELS.UTUBS] == []


def test_get_trash_member_without_own_urls_sees_nothing(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN only the URL added by user 2 is trashed in UTub 1
    WHEN plain member user 3 requests their Trash
    THEN nothing is listed, since they neither added it nor co-manage the UTub
    """
    client, _, _, app = login_third_user_without_register
    trash_utub_url(app, get_utub_url_id(app, FIRST_UTUB_ID, 2), SECOND_USER_ID)

    response_json = get_trash(client)

    assert response_json[MODELS.URLS] == []
    assert response_json[MODELS.UTUBS] == []


def test_get_trash_hides_urls_from_departed_member(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 trashed the URL they added and then left UTub 1
    WHEN user 2 requests their Trash
    THEN the URL is no longer listed, since they lost access to the origin UTub
    """
    client, _, _, app = login_second_user_without_register
    trash_utub_url(app, get_utub_url_id(app, FIRST_UTUB_ID, 2), SECOND_USER_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response_json = get_trash(client)

    assert response_json[MODELS.URLS] == []


def test_get_trash_departed_members_url_still_visible_to_creator(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 trashed the URL they added and then left UTub 1
    WHEN the UTub creator requests their Trash
    THEN the URL is listed, attributed to the departed adder
    """
    client, _, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, SECOND_USER_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response_json = get_trash(client)

    assert trashed_url_ids(response_json) == [row_id]
    assert response_json[MODELS.URLS][0][MODELS.ADDED_BY] == SECOND_USER_ID


def test_get_trash_hides_trashed_url_with_null_deleted_by(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL row whose deleted_by is NULL (never written by the services)
        next to a properly trashed one
    WHEN the UTub creator requests their Trash
    THEN only the properly trashed row is listed: the deleter join fails closed
    """
    client, _, _, app = login_first_user_without_register
    orphan_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    listed_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, orphan_row_id, FIRST_USER_ID)
    trash_utub_url(app, listed_row_id, FIRST_USER_ID)
    with app.app_context():
        orphan_row: Utub_Urls = Utub_Urls.query.get(orphan_row_id)
        orphan_row.deleted_by = None
        db.session.commit()

    response_json = get_trash(client)

    assert trashed_url_ids(response_json) == [listed_row_id]


def test_get_trash_hides_trashed_utub_whose_creator_membership_is_gone(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and its creator's membership row is then removed
    WHEN the creator requests their Trash
    THEN neither the UTub nor its URLs are listed: the membership join fails closed
    """
    client, _, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    remove_member(app, FIRST_UTUB_ID, FIRST_USER_ID)

    response_json = get_trash(client)

    assert response_json[MODELS.UTUBS] == []
    assert response_json[MODELS.URLS] == []


def test_get_trash_lists_trashed_utub_and_its_live_urls(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1, holding three live URLs and three members, is trashed by its creator
    WHEN the creator requests their Trash
    THEN the UTub is listed with its counts and deleter, and so are its live URLs,
        flagged as trashed with the UTub and sharing the UTub's deletedAt
    """
    client, _, user, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    with app.app_context():
        utub: Utubs = Utubs.query.get(FIRST_UTUB_ID)
        utub_deleted_at = utub.deleted_at
        utub_name = utub.name

    response_json = get_trash(client)

    assert len(response_json[MODELS.UTUBS]) == 1
    utub_item = response_json[MODELS.UTUBS][0]
    assert set(utub_item.keys()) == UTUB_ITEM_KEYS
    TrashedUtubItemSchema.model_validate(utub_item)
    assert utub_item[UTUB_ID] == FIRST_UTUB_ID
    assert utub_item[UTUB_NAME] == utub_name
    assert utub_item[MODELS.URL_COUNT] == 3
    assert utub_item[MODELS.MEMBER_COUNT] == 3
    assert utub_item[MODELS.DELETED_BY] == user.id
    assert utub_item[MODELS.DELETED_BY_USERNAME] == user.username
    assert utub_item[MODELS.IS_LOCKED] is False
    assert utub_item[MODELS.CAN_RESTORE] is True
    assert utub_item[MODELS.CAN_DELETE] is True
    assert datetime.fromisoformat(utub_item[MODELS.DELETED_AT]) == utub_deleted_at

    assert len(response_json[MODELS.URLS]) == 3
    for item in response_json[MODELS.URLS]:
        assert item[UTUB_ID] == FIRST_UTUB_ID
        assert item[MODELS.ORIGIN_UTUB_TRASHED] is True
        assert item[MODELS.TRASHED_WITH_UTUB] is True
        assert item[MODELS.DELETED_BY] == user.id
        assert datetime.fromisoformat(item[MODELS.DELETED_AT]) == utub_deleted_at


def test_get_trash_trashed_utub_hidden_from_non_creator(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed by its creator, user 1
    WHEN member user 2 requests their Trash
    THEN neither the UTub nor its live URLs are listed
    """
    client, _, _, app = login_second_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)

    response_json = get_trash(client)

    assert response_json[MODELS.UTUBS] == []
    assert response_json[MODELS.URLS] == []


def test_get_trash_trashed_utub_hidden_from_co_creator(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed by its creator, and user 3 is promoted to CO_CREATOR
    WHEN co-creator user 3 requests their Trash
    THEN neither the UTub nor its live URLs are listed, since only the creator acts on it
    """
    client, _, _, app = login_third_user_without_register
    set_member_role(app, FIRST_UTUB_ID, THIRD_USER_ID, Member_Role.CO_CREATOR)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)

    response_json = get_trash(client)

    assert response_json[MODELS.URLS] == []
    assert response_json[MODELS.UTUBS] == []


def test_get_trash_utub_url_count_excludes_individually_trashed_urls(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN one of UTub 1's three URLs is trashed on its own, then the UTub is trashed
    WHEN the creator requests their Trash
    THEN the UTub's urlCount counts only the two live URLs, while the individually
        trashed URL is still listed with its own earlier clock
    """
    client, _, _, app = login_first_user_without_register
    own_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, own_row_id, SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    with app.app_context():
        own_deleted_at = Utub_Urls.query.get(own_row_id).deleted_at
        utub_deleted_at = Utubs.query.get(FIRST_UTUB_ID).deleted_at

    response_json = get_trash(client)

    assert len(response_json[MODELS.UTUBS]) == 1
    utub_item = response_json[MODELS.UTUBS][0]
    assert utub_item[MODELS.URL_COUNT] == 2
    assert datetime.fromisoformat(utub_item[MODELS.DELETED_AT]) == utub_deleted_at
    items = {item[MODELS.UTUB_URL_ID]: item for item in response_json[MODELS.URLS]}
    assert len(items) == 3
    assert (
        datetime.fromisoformat(items[own_row_id][MODELS.DELETED_AT]) == own_deleted_at
    )
    assert own_deleted_at != utub_deleted_at


def test_get_trash_url_trashed_before_utub_keeps_its_own_clock(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2's URL is trashed on its own, then UTub 1 is trashed afterwards
    WHEN the creator requests their Trash
    THEN that URL keeps its earlier deletedAt and deleter and is not trashedWithUtub,
        while the other URLs take the UTub's deletedAt
    """
    client, _, _, app = login_first_user_without_register
    own_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, own_row_id, SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    with app.app_context():
        own_deleted_at = Utub_Urls.query.get(own_row_id).deleted_at
        utub_deleted_at = Utubs.query.get(FIRST_UTUB_ID).deleted_at
    assert own_deleted_at < utub_deleted_at

    response_json = get_trash(client)

    items = {item[MODELS.UTUB_URL_ID]: item for item in response_json[MODELS.URLS]}
    assert len(items) == 3
    own_item = items[own_row_id]
    assert own_item[MODELS.TRASHED_WITH_UTUB] is False
    assert own_item[MODELS.ORIGIN_UTUB_TRASHED] is True
    assert own_item[MODELS.DELETED_BY] == SECOND_USER_ID
    assert datetime.fromisoformat(own_item[MODELS.DELETED_AT]) == own_deleted_at
    for row_id, item in items.items():
        if row_id == own_row_id:
            continue
        assert item[MODELS.TRASHED_WITH_UTUB] is True
        assert item[MODELS.DELETED_BY] == FIRST_USER_ID
        assert datetime.fromisoformat(item[MODELS.DELETED_AT]) == utub_deleted_at


def test_get_trash_orders_newest_first(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL rows of UTub 1 trashed one after another
    WHEN the creator requests their Trash
    THEN the most recently trashed URL is listed first
    """
    client, _, _, app = login_first_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)]
    for row_id in row_ids:
        trash_utub_url(app, row_id, FIRST_USER_ID)

    response_json = get_trash(client)

    assert trashed_url_ids(response_json) == list(reversed(row_ids))


@pytest.mark.parametrize("utub_is_trashed", [False, True])
def test_get_trash_locked_origin_utub_blocks_restore_and_delete(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    utub_is_trashed: bool,
):
    """
    GIVEN UTub 1 is locked, with its URLs trashed on their own or along with the UTub
    WHEN the creator requests their Trash
    THEN every URL (and the UTub, if trashed) reports originUtubLocked with
        canRestore and canDelete both false
    """
    client, _, _, app = login_first_user_without_register
    if utub_is_trashed:
        trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    else:
        trash_first_utub_urls(app, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response_json = get_trash(client)

    assert len(response_json[MODELS.URLS]) == 3
    for item in response_json[MODELS.URLS]:
        assert item[MODELS.ORIGIN_UTUB_LOCKED] is True
        assert item[MODELS.CAN_RESTORE] is False
        assert item[MODELS.CAN_DELETE] is False
    if utub_is_trashed:
        utub_item = response_json[MODELS.UTUBS][0]
        assert utub_item[MODELS.IS_LOCKED] is True
        assert utub_item[MODELS.CAN_RESTORE] is False
        assert utub_item[MODELS.CAN_DELETE] is False


def test_get_trash_locked_trashed_utub_is_listed_but_not_actionable(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and then locked
    WHEN the creator requests their Trash
    THEN the UTub is still listed, flagged isLocked, with canRestore and canDelete false
    """
    client, _, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response_json = get_trash(client)

    assert len(response_json[MODELS.UTUBS]) == 1
    utub_item = response_json[MODELS.UTUBS][0]
    assert utub_item[UTUB_ID] == FIRST_UTUB_ID
    assert utub_item[MODELS.IS_LOCKED] is True
    assert utub_item[MODELS.CAN_RESTORE] is False
    assert utub_item[MODELS.CAN_DELETE] is False


def test_get_trash_unlocked_origin_utub_allows_restore_and_delete(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is unlocked and has trashed URLs
    WHEN the creator requests their Trash
    THEN each URL reports originUtubLocked false with canRestore and canDelete true
    """
    client, _, _, app = login_first_user_without_register
    trash_first_utub_urls(app, deleted_by=FIRST_USER_ID)

    response_json = get_trash(client)

    for item in response_json[MODELS.URLS]:
        assert item[MODELS.ORIGIN_UTUB_LOCKED] is False
        assert item[MODELS.CAN_RESTORE] is True
        assert item[MODELS.CAN_DELETE] is True


def test_get_trash_expiry_is_retention_window_after_deletion(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL and a trashed UTub
    WHEN the creator requests their Trash
    THEN each item's expiresAt is exactly TRASH_RETENTION_DAYS after its deletedAt
    """
    client, _, _, app = login_first_user_without_register
    trash_utub_url(app, get_utub_url_id(app, FIRST_UTUB_ID, 2), SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)

    response_json = get_trash(client)

    items = response_json[MODELS.URLS] + response_json[MODELS.UTUBS]
    assert items
    for item in items:
        deleted_at = datetime.fromisoformat(item[MODELS.DELETED_AT])
        expires_at = datetime.fromisoformat(item[MODELS.EXPIRES_AT])
        assert expires_at - deleted_at == timedelta(days=TRASH_RETENTION_DAYS)


def test_get_trash_rejects_non_ajax_request(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user
    WHEN they request the Trash with a non-AJAX X-Requested-With header
    THEN they are redirected to the home page rather than served JSON
    """
    client, _, _, _ = login_first_user_without_register

    response = client.get(
        url_for(ROUTES.UTUBS.GET_TRASH),
        headers={URL_VALIDATION.X_REQUESTED_WITH: "not-ajax"},
    )

    assert response.status_code == 302
    assert response.location == url_for(ROUTES.UTUBS.HOME)
