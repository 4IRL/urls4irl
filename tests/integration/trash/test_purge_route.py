from typing import Tuple
from unittest.mock import patch

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response

from backend import db
from backend.metrics.events import EventName
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.trash import UrlPurgedResponseSchema, UtubPurgedResponseSchema
from backend.urls.constants import URLErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.trash_strs import TRASH_FAILURE, TRASH_SUCCESS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME
from backend.utubs.constants import UTubErrorCodes
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
)
from tests.integration.trash.trash_helpers import (
    AJAX_HEADERS,
    FIRST_USER_ID,
    FIRST_UTUB_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
    SECOND_UTUB_ID,
    THIRD_USER_ID,
    assert_not_in_trash_response,
    count_url_tags_in_utub,
    count_url_tags_of_row,
    get_row_state,
    get_trash_url_ids,
    get_trashed_utub_ids,
    login_as_user,
    row_exists,
    utub_exists,
)
from tests.utils_for_test import (
    get_utub_url_id,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub,
    trash_utub_url,
    unlock_utub,
)

pytestmark = pytest.mark.trash


def delete_purge_url(
    client: FlaskClient, csrf_token: str, utub_id: int, utub_url_id: int
) -> Response:
    return client.delete(
        url_for(ROUTES.URLS.PURGE_URL, utub_id=utub_id, utub_url_id=utub_url_id),
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def delete_purge_utub(client: FlaskClient, csrf_token: str, utub_id: int) -> Response:
    return client.delete(
        url_for(ROUTES.UTUBS.PURGE_UTUB, utub_id=utub_id),
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def assert_utub_not_in_trash_response(response: Response) -> None:
    assert response.status_code == 404
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_FAILURE.NOT_IN_TRASH
    assert response_json[STD_JSON_RESPONSE.ERROR_CODE] == UTubErrorCodes.NOT_IN_TRASH


def count_children(app: Flask, utub_id: int) -> dict[str, int]:
    with app.app_context():
        return {
            "utubs": Utubs.query.filter(Utubs.id == utub_id).count(),
            "members": Utub_Members.query.filter(
                Utub_Members.utub_id == utub_id
            ).count(),
            "tags": Utub_Tags.query.filter(Utub_Tags.utub_id == utub_id).count(),
            "url_tags": Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_id == utub_id
            ).count(),
            "urls": Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).count(),
        }


# URL purge


def test_adder_purges_own_trashed_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 added URL 2 (which carries the shared tag) to UTub 1 and it was trashed
    WHEN user 2 deletes it forever
    THEN the response is 200 and validates against the purged-URL schema, the
        Utub_Urls row and only its own Utub_Url_Tags rows are gone (sibling rows keep
        theirs), the Urls row and the UTub's tags remain, and the row leaves the Trash
        list
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    sibling_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    row_tags_before = count_url_tags_of_row(app, row_id)
    sibling_tags_before = count_url_tags_of_row(app, sibling_row_id)
    utub_url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    assert row_tags_before > 0
    assert sibling_tags_before > 0
    assert get_trash_url_ids(client) == [row_id]
    with app.app_context():
        tag_count_before = Utub_Tags.query.filter_by(utub_id=FIRST_UTUB_ID).count()
        url_row_count_before = Urls.query.count()
        urls_row_id = Utub_Urls.query.get(row_id).url_id

    response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.SUCCESS
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_SUCCESS.URL_PURGED
    UrlPurgedResponseSchema.model_validate(response_json)
    assert response_json[UTUB_ID] == FIRST_UTUB_ID
    assert response_json[MODELS.UTUB_URL_ID] == row_id
    assert not row_exists(app, row_id)
    assert count_url_tags_of_row(app, row_id) == 0
    assert count_url_tags_of_row(app, sibling_row_id) == sibling_tags_before
    assert (
        count_url_tags_in_utub(app, FIRST_UTUB_ID)
        == utub_url_tags_before - row_tags_before
    )
    with app.app_context():
        assert (
            Utub_Tags.query.filter_by(utub_id=FIRST_UTUB_ID).count() == tag_count_before
        )
        assert Urls.query.count() == url_row_count_before
        assert Urls.query.get(urls_row_id) is not None
    assert get_trash_url_ids(client) == []


@pytest.mark.parametrize("acting_user_id", [FIRST_USER_ID, THIRD_USER_ID])
def test_manager_purges_another_members_trashed_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    acting_user_id: int,
):
    """
    GIVEN user 2's URL is trashed in UTub 1 and the acting user is the creator, or a
        member promoted to CO_CREATOR
    WHEN that manager deletes it forever
    THEN the response is 200 and the row and its url-tags are gone
    """
    _, _, _, app = login_first_user_without_register
    if acting_user_id != FIRST_USER_ID:
        set_member_role(app, FIRST_UTUB_ID, acting_user_id, Member_Role.CO_CREATOR)
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    assert count_url_tags_of_row(app, row_id) > 0

    with login_as_user(app, acting_user_id) as (client, csrf_token):
        response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    assert not row_exists(app, row_id)
    assert count_url_tags_of_row(app, row_id) == 0


def test_non_adder_plain_member_cannot_purge_trashed_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2's URL is trashed in UTub 1
    WHEN plain member user 3, who neither added it nor manages the UTub, deletes it
    THEN the response is the unified 404 NOT_IN_TRASH and the row stays trashed
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    before = get_row_state(app, row_id)
    tags_before = count_url_tags_of_row(app, row_id)
    assert tags_before > 0

    response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id) == before
    assert count_url_tags_of_row(app, row_id) == tags_before


def test_departed_adder_cannot_purge_but_creator_can(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2's URL is trashed in UTub 1 and user 2 then leaves the UTub
    WHEN user 2 and then the creator delete it forever
    THEN user 2 gets 404 NOT_IN_TRASH and the creator deletes it with a 200
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    with login_as_user(app, SECOND_USER_ID) as (departed_client, departed_csrf):
        departed_response = delete_purge_url(
            departed_client, departed_csrf, FIRST_UTUB_ID, row_id
        )
    assert_not_in_trash_response(departed_response)
    assert row_exists(app, row_id)

    creator_response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert creator_response.status_code == 200
    assert not row_exists(app, row_id)


def test_purging_live_row_is_not_in_trash_and_leaves_it_untouched(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 in UTub 1 is live
    WHEN its creator deletes it forever
    THEN the response is 404 NOT_IN_TRASH and the live row and its tags are untouched
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    before = get_row_state(app, row_id)
    tags_before = count_url_tags_of_row(app, row_id)
    assert tags_before > 0

    response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id) == before
    assert count_url_tags_of_row(app, row_id) == tags_before


def test_purging_nonexistent_row_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL in UTub 1
    WHEN the creator deletes an id no Utub_Urls row has
    THEN the response is 404 NOT_IN_TRASH and the trashed row survives
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, NONEXISTENT_ID)

    assert_not_in_trash_response(response)
    assert row_exists(app, row_id)


def test_purging_row_under_another_utubs_path_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL in UTub 1, and the creator is also a member of UTub 2
    WHEN the creator deletes that row id under UTub 2's path
    THEN the response is 404 NOT_IN_TRASH (the row is not UTub 2's) and the row survives
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)

    response = delete_purge_url(client, csrf_token, SECOND_UTUB_ID, row_id)

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id) == before


def test_second_purge_of_url_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL that was already deleted forever
    WHEN the creator deletes it a second time
    THEN the second response is 404 NOT_IN_TRASH
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    first_response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)
    assert first_response.status_code == 200

    second_response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_not_in_trash_response(second_response)


def test_purge_url_in_locked_utub_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in UTub 1, which is then locked
    WHEN the creator deletes it forever
    THEN the response is 403 UTUB_IS_LOCKED and the row stays trashed with its tags
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = get_row_state(app, row_id)
    tags_before = count_url_tags_of_row(app, row_id)
    assert tags_before > 0

    response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 403
    assert response.json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response.json[STD_JSON_RESPONSE.ERROR_CODE] == URLErrorCodes.UTUB_IS_LOCKED
    assert get_row_state(app, row_id) == before
    assert count_url_tags_of_row(app, row_id) == tags_before


def test_purge_url_in_locked_utub_by_non_actionable_viewer_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2's URL is trashed in UTub 1, which is then locked
    WHEN plain member user 3, who may not act on that URL, deletes it
    THEN the response is 404 NOT_IN_TRASH, so the viewer never learns the UTub is locked
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = get_row_state(app, row_id)
    tags_before = count_url_tags_of_row(app, row_id)

    response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id) == before
    assert count_url_tags_of_row(app, row_id) == tags_before


def test_creator_purges_url_inside_trashed_utub_but_member_cannot(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed, so its live URLs are in Trash only with the UTub
    WHEN member user 2 (who added URL 2) and then the creator delete URL 2 forever
    THEN user 2 gets 404 NOT_IN_TRASH and the creator gets 200, with the UTub itself
        left in Trash
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)

    with login_as_user(app, SECOND_USER_ID) as (member_client, member_csrf):
        member_response = delete_purge_url(
            member_client, member_csrf, FIRST_UTUB_ID, row_id
        )
    assert_not_in_trash_response(member_response)
    assert row_exists(app, row_id)

    creator_response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert creator_response.status_code == 200
    assert not row_exists(app, row_id)
    assert count_url_tags_of_row(app, row_id) == 0
    assert utub_exists(app, FIRST_UTUB_ID)
    assert get_trashed_utub_ids(client) == [FIRST_UTUB_ID]


def test_purge_url_without_csrf_token_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL
    WHEN its creator sends the DELETE without a CSRF token
    THEN the response is the 403 HTML page and the row is untouched
    """
    client, _, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = client.delete(
        url_for(ROUTES.URLS.PURGE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=row_id),
        headers=AJAX_HEADERS,
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert row_exists(app, row_id)


def test_purge_url_records_metric_and_failures_do_not(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a live URL and a trashed URL in UTub 1, and metrics enabled
    WHEN the creator tries to delete the live one (404), then the trashed one while the
        UTub is locked (403), then the trashed one once it is unlocked (200)
    THEN URL_PURGED_FROM_TRASH goes 0 -> 1 only on the success
    """
    client, csrf_token, _, app = login_first_user_without_register
    live_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trashed_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, trashed_row_id, deleted_by=FIRST_USER_ID)
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_PURGED_FROM_TRASH) == 0
    )

    failed_response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, live_row_id)
    assert failed_response.status_code == 404
    lock_utub(app, FIRST_UTUB_ID)
    locked_response = delete_purge_url(
        client, csrf_token, FIRST_UTUB_ID, trashed_row_id
    )
    assert locked_response.status_code == 403
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_PURGED_FROM_TRASH) == 0
    )
    unlock_utub(app, FIRST_UTUB_ID)

    response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, trashed_row_id)

    assert response.status_code == 200
    assert (
        len(find_counter_keys(provide_metrics_redis, EventName.URL_PURGED_FROM_TRASH))
        == 1
    )


# UTub purge


def test_creator_purges_trashed_utub_with_all_children(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 holds three members, three tags, three URLs and four URL-tag rows, and
        one URL was trashed on its own before the UTub was trashed
    WHEN the creator deletes the UTub forever
    THEN the response is 200 and validates against the purged-UTub schema with the
        count of every URL row (live and trashed), no FK error occurs, every child
        row of UTub 1 is gone, other UTubs are untouched, and it leaves the Trash list
    """
    client, csrf_token, _, app = login_first_user_without_register
    trashed_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, trashed_row_id, deleted_by=SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    before = count_children(app, FIRST_UTUB_ID)
    assert all(count > 0 for count in before.values())
    other_utub_before = count_children(app, SECOND_UTUB_ID)
    with app.app_context():
        utub_name = Utubs.query.get(FIRST_UTUB_ID).name
        total_utubs_before = Utubs.query.count()
        total_urls_before = Urls.query.count()
    assert get_trashed_utub_ids(client) == [FIRST_UTUB_ID]

    response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.SUCCESS
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_SUCCESS.UTUB_PURGED
    UtubPurgedResponseSchema.model_validate(response_json)
    assert response_json[UTUB_ID] == FIRST_UTUB_ID
    assert response_json[UTUB_NAME] == utub_name
    assert response_json[MODELS.PURGED_URL_COUNT] == before["urls"]
    assert count_children(app, FIRST_UTUB_ID) == {
        "utubs": 0,
        "members": 0,
        "tags": 0,
        "url_tags": 0,
        "urls": 0,
    }
    assert count_children(app, SECOND_UTUB_ID) == other_utub_before
    with app.app_context():
        assert Utubs.query.count() == total_utubs_before - 1
        assert Urls.query.count() == total_urls_before
        assert Users.query.get(SECOND_USER_ID) is not None
    assert get_trashed_utub_ids(client) == []
    assert get_trash_url_ids(client) == []


@pytest.mark.parametrize("acting_user_id", [SECOND_USER_ID, THIRD_USER_ID])
def test_non_creator_cannot_purge_trashed_utub(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    acting_user_id: int,
):
    """
    GIVEN UTub 1 is trashed, with user 2 a plain member and user 3 a CO_CREATOR
    WHEN that member or co-creator deletes it forever
    THEN the response is the masking 404 NOT_IN_TRASH and the UTub is intact
    """
    _, _, _, app = login_first_user_without_register
    set_member_role(app, FIRST_UTUB_ID, THIRD_USER_ID, Member_Role.CO_CREATOR)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    before = count_children(app, FIRST_UTUB_ID)

    with login_as_user(app, acting_user_id) as (client, csrf_token):
        response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(response)
    assert count_children(app, FIRST_UTUB_ID) == before


def test_purging_live_utub_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is live
    WHEN its creator deletes it forever
    THEN the response is 404 NOT_IN_TRASH and nothing is deleted
    """
    client, csrf_token, _, app = login_first_user_without_register
    before = count_children(app, FIRST_UTUB_ID)

    response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(response)
    assert count_children(app, FIRST_UTUB_ID) == before


def test_purging_nonexistent_utub_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN no UTub has the requested id
    WHEN user 1 deletes it forever
    THEN the response is the same 404 NOT_IN_TRASH as for a live UTub
    """
    client, csrf_token, _, _ = login_first_user_without_register

    response = delete_purge_utub(client, csrf_token, NONEXISTENT_ID)

    assert_utub_not_in_trash_response(response)


def test_second_purge_of_utub_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 was trashed and deleted forever once
    WHEN the creator deletes it a second time
    THEN the second response is 404 NOT_IN_TRASH
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    first_response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)
    assert first_response.status_code == 200

    second_response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(second_response)


def test_purge_locked_trashed_utub_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and locked
    WHEN its creator deletes it forever
    THEN the response is 403 UTUB_IS_LOCKED and every child row survives
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = count_children(app, FIRST_UTUB_ID)

    response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)

    assert response.status_code == 403
    assert response.json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response.json[STD_JSON_RESPONSE.ERROR_CODE] == UTubErrorCodes.UTUB_IS_LOCKED
    assert count_children(app, FIRST_UTUB_ID) == before


def test_purge_locked_trashed_utub_does_not_leak_to_non_creator(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed and locked
    WHEN a plain member deletes it forever
    THEN the response is the masking 404 NOT_IN_TRASH, not the creator-only 403, and
        nothing is deleted
    """
    _, _, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = count_children(app, FIRST_UTUB_ID)

    with login_as_user(app, SECOND_USER_ID) as (client, csrf_token):
        response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)

    assert_utub_not_in_trash_response(response)
    assert count_children(app, FIRST_UTUB_ID) == before


def test_purge_utub_without_csrf_token_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed
    WHEN its creator sends the DELETE without a CSRF token
    THEN the response is the 403 HTML page and the UTub is intact
    """
    client, _, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)

    response = client.delete(
        url_for(ROUTES.UTUBS.PURGE_UTUB, utub_id=FIRST_UTUB_ID),
        headers=AJAX_HEADERS,
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert utub_exists(app, FIRST_UTUB_ID)


def test_purge_utub_records_metric_and_failures_do_not(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a live UTub, then a trashed-and-locked UTub, then the same UTub unlocked, and
        metrics enabled
    WHEN the creator tries to delete it each time
    THEN UTUB_PURGED_FROM_TRASH stays at 0 for the 404 and the 403, and goes to 1 on
        the success
    """
    client, csrf_token, _, app = login_first_user_without_register
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUB_PURGED_FROM_TRASH) == 0
    )

    live_response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    locked_response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)
    assert live_response.status_code == 404
    assert locked_response.status_code == 403
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUB_PURGED_FROM_TRASH) == 0
    )

    unlock_utub(app, FIRST_UTUB_ID)

    response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)

    assert response.status_code == 200
    assert (
        len(find_counter_keys(provide_metrics_redis, EventName.UTUB_PURGED_FROM_TRASH))
        == 1
    )


# Service failure


def test_purge_url_service_failure_rolls_back_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL with url-tags, and the commit raising after the url-tag rows were
        bulk-deleted and the Utub_Urls row was marked for deletion
    WHEN the creator deletes it forever
    THEN the unhandled error is a 500, the failure is logged once, everything is rolled
        back (row state and url-tag rows unchanged, still in Trash) and no
        URL_PURGED_FROM_TRASH counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)
    row_tags_before = count_url_tags_of_row(app, row_id)
    utub_url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    assert row_tags_before > 0

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch.object(db.session, "commit", side_effect=RuntimeError("boom")),
        patch("backend.urls.services.trash_urls.warning_log") as warning_log_mock,
    ):
        response = delete_purge_url(client, csrf_token, FIRST_UTUB_ID, row_id)

    warning_log_mock.assert_called_once()
    assert response.status_code == 500
    assert row_exists(app, row_id)
    assert get_row_state(app, row_id) == before
    assert count_url_tags_of_row(app, row_id) == row_tags_before
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == utub_url_tags_before
    assert get_trash_url_ids(client) == [row_id]
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_PURGED_FROM_TRASH) == 0
    )


def test_purge_utub_service_failure_rolls_back_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed UTub with children, and the commit raising after the UTub was marked
        for deletion
    WHEN the creator deletes it forever
    THEN the unhandled error is a 500, the failure is logged once, every child row
        survives, the UTub is still in Trash and no UTUB_PURGED_FROM_TRASH counter is
        written
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    before = count_children(app, FIRST_UTUB_ID)
    assert all(count > 0 for count in before.values())

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch.object(db.session, "commit", side_effect=RuntimeError("boom")),
        patch("backend.utubs.services.trash_utubs.warning_log") as warning_log_mock,
    ):
        response = delete_purge_utub(client, csrf_token, FIRST_UTUB_ID)

    warning_log_mock.assert_called_once()
    assert response.status_code == 500
    assert count_children(app, FIRST_UTUB_ID) == before
    assert get_trashed_utub_ids(client) == [FIRST_UTUB_ID]
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUB_PURGED_FROM_TRASH) == 0
    )
