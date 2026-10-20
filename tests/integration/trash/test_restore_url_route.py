from datetime import datetime
from typing import Any, Tuple
from unittest.mock import patch

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.trash import UrlRestoredResponseSchema
from backend.urls.constants import URLErrorCodes
from backend.urls.services.trash_urls import restore_trashed_url
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS, TAG_COUNTS_MODIFIED
from backend.utils.strings.trash_strs import TRASH_FAILURE, TRASH_SUCCESS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_ID, UTUB_NAME
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
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
    get_row_state,
    get_trash_url_ids,
    login_as_user,
    post_restore,
)
from tests.utils_for_test import (
    count_tag_instances_in_utub,
    get_utub_url_id,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub_url,
)

pytestmark = pytest.mark.trash


def get_trash_can_restore(client: FlaskClient) -> dict[int, bool]:
    response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)
    assert response.status_code == 200
    return {
        item[MODELS.UTUB_URL_ID]: item[MODELS.CAN_RESTORE]
        for item in response.json[MODELS.URLS]
    }


def test_adder_restores_own_url_in_place(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 added URL 2 to UTub 1 and it was trashed
    WHEN user 2 restores it in place
    THEN the response is 200 with the card, the trash fields are cleared, the adder,
        added-at, title and last-accessed are unchanged, and the row leaves the Trash list
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    before = get_row_state(app, row_id)
    assert get_trash_url_ids(client) == [row_id]

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.SUCCESS
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_SUCCESS.URL_RESTORED
    UrlRestoredResponseSchema.model_validate(response_json)
    assert response_json[UTUB_ID] == FIRST_UTUB_ID
    with app.app_context():
        assert response_json[UTUB_NAME] == Utubs.query.get(FIRST_UTUB_ID).name
    assert response_json[MODELS.RESTORED_TO_DESTINATION] is False
    card = response_json[MODELS.URL]
    assert card[MODELS.UTUB_URL_ID] == row_id
    assert card[MODELS.ADDED_BY] == SECOND_USER_ID
    assert card[MODELS.CAN_DELETE] is True
    assert card[MODELS.URL_TITLE] == before["url_title"]
    assert datetime.fromisoformat(card["addedAt"]) == before["added_at"]

    after = get_row_state(app, row_id)
    assert after["deleted_at"] is None
    assert after["deleted_by"] is None
    assert after["trashed_tag_ids"] is None
    for unchanged_field in ("user_id", "added_at", "url_title", "last_accessed"):
        assert after[unchanged_field] == before[unchanged_field]
    assert get_trash_url_ids(client) == []


@pytest.mark.parametrize("acting_user_id", [FIRST_USER_ID, THIRD_USER_ID])
def test_manager_restores_another_members_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    acting_user_id: int,
):
    """
    GIVEN user 2's URL is trashed in UTub 1 and the acting user is the creator, or a
        member promoted to CO_CREATOR
    WHEN that manager restores it
    THEN it is restored with user 2 still recorded as its adder
    """
    _, _, _, app = login_first_user_without_register
    if acting_user_id != FIRST_USER_ID:
        set_member_role(app, FIRST_UTUB_ID, acting_user_id, Member_Role.CO_CREATOR)
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)

    with login_as_user(app, acting_user_id) as (client, csrf_token):
        response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    assert response.json[MODELS.URL][MODELS.ADDED_BY] == SECOND_USER_ID
    assert response.json[MODELS.URL][MODELS.CAN_DELETE] is True
    after = get_row_state(app, row_id)
    assert after["deleted_at"] is None
    assert after["user_id"] == SECOND_USER_ID


def test_non_adder_plain_member_gets_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2's URL is trashed in UTub 1
    WHEN plain member user 3, who neither added it nor manages the UTub, restores it
    THEN the response is the unified 404 NOT_IN_TRASH and the row stays trashed
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    before = get_row_state(app, row_id)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id) == before


def test_departed_adder_cannot_restore_but_creator_can(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 trashed their own URL and then left UTub 1
    WHEN user 2 tries to restore it, and then the creator does
    THEN user 2 gets 404 NOT_IN_TRASH, the creator gets 200, and the row keeps user 2
        as its adder
    """
    creator_client, creator_csrf, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    with login_as_user(app, SECOND_USER_ID) as (departed_client, departed_csrf):
        departed_response = post_restore(
            departed_client, departed_csrf, FIRST_UTUB_ID, row_id
        )
    assert_not_in_trash_response(departed_response)
    assert get_row_state(app, row_id)["deleted_at"] is not None

    creator_response = post_restore(creator_client, creator_csrf, FIRST_UTUB_ID, row_id)
    assert creator_response.status_code == 200
    assert creator_response.json[MODELS.URL][MODELS.ADDED_BY] == SECOND_USER_ID
    after = get_row_state(app, row_id)
    assert after["deleted_at"] is None
    assert after["user_id"] == SECOND_USER_ID


def test_restore_reports_lost_tags_and_live_tag_counts(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 (shared + solo tags) and URL 2 (shared tag) are trashed, and the solo
        UTub tag is then deleted from the UTub
    WHEN user 1 restores URL 1 in place
    THEN lostTagCount is 1, only the shared tag is in appliedTags and on the card, and
        tagCountsInUtub counts only live URLs (URL 1 and URL 3, not the trashed URL 2)
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    second_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    with app.app_context():
        shared_tag_id, solo_tag_id = Utub_Urls.query.get(row_id).associated_tag_ids
        shared_tag_string: str = Utub_Tags.query.get(shared_tag_id).tag_string
        solo_tag_string: str = Utub_Tags.query.get(solo_tag_id).tag_string
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, second_row_id, deleted_by=FIRST_USER_ID)
    with app.app_context():
        db.session.delete(Utub_Tags.query.get(solo_tag_id))
        db.session.commit()

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[MODELS.LOST_TAG_COUNT] == 1
    assert response_json[MODELS.LOST_TAG_NAMES] == [solo_tag_string]
    assert [
        (tag[MODELS.ID], tag[MODELS.TAG_STRING])
        for tag in response_json[MODELS.APPLIED_TAGS]
    ] == [(shared_tag_id, shared_tag_string)]
    assert response_json[MODELS.URL][MODELS.URL_TAG_IDS] == [shared_tag_id]
    live_shared_count = 2
    assert (
        response_json[MODELS.APPLIED_TAGS][0][MODELS.TAG_APPLIED] == live_shared_count
    )
    assert response_json[TAG_COUNTS_MODIFIED] == {str(shared_tag_id): live_shared_count}
    with app.app_context():
        # The raw association count still includes the trashed URL 2's row.
        assert count_tag_instances_in_utub(FIRST_UTUB_ID, shared_tag_id) == 3
        restored_row: Utub_Urls = Utub_Urls.query.get(row_id)
        assert restored_row.trashed_tag_ids is None
        assert restored_row.trashed_tag_names is None
        assert restored_row.associated_tag_ids == [shared_tag_id]


def test_restore_reports_zero_lost_tags_when_none_were_deleted(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 (shared + solo tags) is trashed with both tags intact
    WHEN user 1 restores it
    THEN lostTagCount is 0, both tags come back and tagCountsInUtub reports both counts
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    with app.app_context():
        shared_tag_id, solo_tag_id = Utub_Urls.query.get(row_id).associated_tag_ids
        expected_tag_strings: dict[int, str] = {
            utub_tag.id: utub_tag.tag_string
            for utub_tag in Utub_Tags.query.filter(
                Utub_Tags.id.in_([shared_tag_id, solo_tag_id])
            ).all()
        }
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    response_json = response.json
    assert response_json[MODELS.LOST_TAG_COUNT] == 0
    assert response_json[MODELS.LOST_TAG_NAMES] == []
    assert {
        tag[MODELS.ID]: tag[MODELS.TAG_STRING]
        for tag in response_json[MODELS.APPLIED_TAGS]
    } == expected_tag_strings
    assert len(response_json[MODELS.APPLIED_TAGS]) == 2
    assert response_json[TAG_COUNTS_MODIFIED] == {
        str(shared_tag_id): 3,
        str(solo_tag_id): 1,
    }
    with app.app_context():
        assert (
            Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == row_id).count() == 2
        )


def test_restore_url_without_tags_has_empty_tag_payload(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 3, which carries only the shared tag, is trashed and that tag is deleted
    WHEN user 1 restores it
    THEN lostTagCount is 1 and there are no applied tags or tag counts
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 3)
    with app.app_context():
        (only_tag_id,) = Utub_Urls.query.get(row_id).associated_tag_ids
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    with app.app_context():
        db.session.delete(Utub_Tags.query.get(only_tag_id))
        db.session.commit()

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    assert response.json[MODELS.LOST_TAG_COUNT] == 1
    assert response.json[MODELS.APPLIED_TAGS] == []
    assert response.json[TAG_COUNTS_MODIFIED] == {}
    assert response.json[MODELS.URL][MODELS.URL_TAG_IDS] == []


def test_restore_names_all_lost_tags_alphabetically_after_real_trash_and_tag_delete(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 (shared + solo tags) is trashed through the delete route, and both of
        its UTub tags are then deleted from the UTub
    WHEN user 1 restores it
    THEN lostTagCount is 2 and lostTagNames lists both tag strings alphabetically
        (case-insensitive), proving the names were saved at trash time
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    with app.app_context():
        tag_ids: list[int] = Utub_Urls.query.get(row_id).associated_tag_ids
        tag_strings: list[str] = [
            Utub_Tags.query.get(tag_id).tag_string for tag_id in tag_ids
        ]
    delete_response = client.delete(
        url_for(ROUTES.URLS.DELETE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=row_id),
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )
    assert delete_response.status_code == 200
    with app.app_context():
        assert Utub_Urls.query.get(row_id).trashed_tag_names == {
            str(tag_id): tag_string for tag_id, tag_string in zip(tag_ids, tag_strings)
        }
        for tag_id in tag_ids:
            db.session.delete(Utub_Tags.query.get(tag_id))
        db.session.commit()

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    assert response.json[MODELS.LOST_TAG_COUNT] == 2
    assert response.json[MODELS.LOST_TAG_NAMES] == sorted(
        tag_strings, key=lambda tag_string: (tag_string.lower(), tag_string)
    )


def test_restore_of_row_trashed_before_names_were_saved_reports_count_only(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 was trashed with no saved tag names (a legacy row) and its solo UTub
        tag was then deleted
    WHEN user 1 restores it
    THEN lostTagCount is still 1 but lostTagNames is empty
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    with app.app_context():
        _, solo_tag_id = Utub_Urls.query.get(row_id).associated_tag_ids
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID, record_tag_names=False)
    assert get_row_state(app, row_id)["trashed_tag_names"] is None
    with app.app_context():
        db.session.delete(Utub_Tags.query.get(solo_tag_id))
        db.session.commit()

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    assert response.json[MODELS.LOST_TAG_COUNT] == 1
    assert response.json[MODELS.LOST_TAG_NAMES] == []


def test_restore_live_row_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a live (never trashed) URL in UTub 1
    WHEN user 1 restores it
    THEN the response is 404 NOT_IN_TRASH
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id)["deleted_at"] is None


def test_restore_nonexistent_row_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN no Utub_Urls row has the requested id
    WHEN user 1 restores it
    THEN the response is the same 404 NOT_IN_TRASH as for a live row
    """
    client, csrf_token, _, _ = login_first_user_without_register

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, NONEXISTENT_ID)

    assert_not_in_trash_response(response)


def test_restore_with_mismatched_utub_id_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in UTub 1
    WHEN user 1 restores it through the path of a different UTub they also belong to
    THEN the response is 404 NOT_IN_TRASH and the row stays trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = post_restore(client, csrf_token, SECOND_UTUB_ID, row_id)

    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id)["deleted_at"] is not None


def test_restore_twice_second_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL that user 1 already restored
    WHEN user 1 restores it again
    THEN the second request is 404 NOT_IN_TRASH
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    assert post_restore(client, csrf_token, FIRST_UTUB_ID, row_id).status_code == 200
    second_response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_not_in_trash_response(second_response)


def test_restore_already_restored_between_gate_and_service_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL that passes the route's decorators
    WHEN another request restores the row before the restore service's locked lookup
    THEN the response is 404 NOT_IN_TRASH and the first request's restore stands
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    def restore_concurrently_then_restore(**kwargs: Any) -> Any:
        with app.app_context():
            concurrent_row: Utub_Urls = Utub_Urls.query.get(row_id)
            concurrent_row.deleted_at = None
            concurrent_row.deleted_by = None
            concurrent_row.trashed_tag_ids = None
            db.session.commit()
        return restore_trashed_url(**kwargs)

    with patch(
        "backend.urls.routes.restore_trashed_url",
        side_effect=restore_concurrently_then_restore,
    ) as restore_mock:
        response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    restore_mock.assert_called_once()
    assert_not_in_trash_response(response)
    assert get_row_state(app, row_id)["deleted_at"] is None


def test_restore_in_locked_utub_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in UTub 1, which is then locked
    WHEN the creator restores it
    THEN the response is 403 UTUB_IS_LOCKED and the row is still trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = get_row_state(app, row_id)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 403
    assert response.json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert response.json[STD_JSON_RESPONSE.ERROR_CODE] == URLErrorCodes.UTUB_IS_LOCKED
    assert get_row_state(app, row_id) == before


def test_restore_in_locked_utub_by_non_actionable_viewer_is_not_in_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2's URL is trashed in UTub 1, which is then locked
    WHEN plain member user 3, who may not act on that URL, restores it
    THEN the response is 404 NOT_IN_TRASH, so the viewer never learns the UTub is locked
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert_not_in_trash_response(response)


def test_restore_into_another_utub_is_invalid_destination_while_origin_is_live(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in the live UTub 1
    WHEN user 1 restores it with a destUtubId of a different UTub
    THEN the response is 400 INVALID_DESTINATION, the row is still trashed and no
        URL_RESTORED_FROM_TRASH counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": SECOND_UTUB_ID}
    )

    assert response.status_code == 400
    assert response.json[STD_JSON_RESPONSE.MESSAGE] == TRASH_FAILURE.INVALID_DESTINATION
    assert (
        response.json[STD_JSON_RESPONSE.ERROR_CODE] == URLErrorCodes.INVALID_DESTINATION
    )
    assert get_row_state(app, row_id)["deleted_at"] is not None
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )


def test_restore_with_own_utub_as_destination_restores_in_place(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in the live UTub 1
    WHEN user 1 restores it with destUtubId equal to its own UTub
    THEN it is restored in place, not reported as moved
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": FIRST_UTUB_ID}
    )

    assert response.status_code == 200
    assert response.json[MODELS.RESTORED_TO_DESTINATION] is False
    assert get_row_state(app, row_id)["deleted_at"] is None


def test_restore_without_json_body_is_bad_request(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in UTub 1
    WHEN user 1 POSTs the restore with no JSON body at all
    THEN the response is the decorator's 400 UNABLE_TO_RESTORE_URL (not the service's
        INVALID_DESTINATION) and the row is still trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = client.post(
        url_for(ROUTES.URLS.RESTORE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=row_id),
        headers={**AJAX_HEADERS, "X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert (
        response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_FAILURE.UNABLE_TO_RESTORE_URL
    )
    assert (
        response_json[STD_JSON_RESPONSE.ERROR_CODE]
        == URLErrorCodes.UNABLE_TO_RESTORE_URL_ERROR
    )
    assert (
        response_json[STD_JSON_RESPONSE.ERROR_CODE] != URLErrorCodes.INVALID_DESTINATION
    )
    assert get_row_state(app, row_id)["deleted_at"] is not None


@pytest.mark.parametrize("bad_destination", [0, -1, 2147483648])
def test_restore_with_out_of_range_destination_is_bad_request(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    bad_destination: int,
):
    """
    GIVEN a URL trashed in UTub 1
    WHEN user 1 restores it with a destUtubId that is non-positive or above the
        32-bit integer id range
    THEN the schema rejects it with a 400 whose field errors are keyed on destUtubId,
        not the service's INVALID_DESTINATION, and the row is still trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": bad_destination}
    )

    assert response.status_code == 400
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert (
        response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_FAILURE.UNABLE_TO_RESTORE_URL
    )
    assert (
        response_json[STD_JSON_RESPONSE.ERROR_CODE]
        == URLErrorCodes.UNABLE_TO_RESTORE_URL_ERROR
    )
    assert (
        response_json[STD_JSON_RESPONSE.ERROR_CODE] != URLErrorCodes.INVALID_DESTINATION
    )
    field_errors = response_json[STD_JSON_RESPONSE.ERRORS]
    assert list(field_errors) == ["destUtubId"]
    assert len(field_errors["destUtubId"]) == 1
    assert get_row_state(app, row_id)["deleted_at"] is not None


def test_restore_without_csrf_token_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in UTub 1
    WHEN user 1 POSTs the restore without a CSRF token
    THEN the response is the 403 HTML page and the row is still trashed
    """
    client, _, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = client.post(
        url_for(ROUTES.URLS.RESTORE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=row_id),
        json={},
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert get_row_state(app, row_id)["deleted_at"] is not None


def test_restore_updates_utub_last_updated(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in UTub 1
    WHEN user 1 restores it
    THEN the UTub's last_updated moves forward
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    with app.app_context():
        last_updated_before = Utubs.query.get(FIRST_UTUB_ID).last_updated

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    with app.app_context():
        assert Utubs.query.get(FIRST_UTUB_ID).last_updated > last_updated_before


def test_restore_records_url_restored_from_trash_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL and metrics enabled
    WHEN user 1 restores it in place
    THEN exactly one URL_RESTORED_FROM_TRASH counter key is written with
        restore_target "origin"
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH
    )
    assert len(counter_keys) == 1
    assert parse_dims(counter_keys[0])["restore_target"] == "origin"


def test_restore_service_failure_rolls_back_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL and the tag-count recompute raising after the row was un-trashed
    WHEN user 1 restores it
    THEN the unhandled error is a 500 (the route's UNABLE_TO_RESTORE_URL message is only
        used for request-schema failures), the failure is logged, the un-trash is rolled
        back (deleted_at and trashed_tag_ids unchanged) and no
        URL_RESTORED_FROM_TRASH counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)
    assert before["trashed_tag_ids"]

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch(
            "backend.urls.services.trash_urls.recompute_tag_counts_after_delete",
            side_effect=RuntimeError("boom"),
        ) as recompute_mock,
        patch("backend.urls.services.trash_urls.warning_log") as warning_log_mock,
    ):
        response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    recompute_mock.assert_called_once()
    warning_log_mock.assert_called_once()
    assert response.status_code == 500
    assert get_row_state(app, row_id) == before
    assert get_row_state(app, row_id)["deleted_at"] is not None
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )


def test_failed_restores_do_not_record_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in UTub 1 that user 3 may not act on, and a second trashed
        URL (added by user 3) in a UTub that is locked
    WHEN user 3 attempts both restores
    THEN neither the 404 nor the 403 emits URL_RESTORED_FROM_TRASH
    """
    client, csrf_token, _, app = login_third_user_without_register
    other_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    own_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 3)
    trash_utub_url(app, other_row_id, deleted_by=SECOND_USER_ID)
    trash_utub_url(app, own_row_id, deleted_by=THIRD_USER_ID)

    not_in_trash_response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, other_row_id
    )
    lock_utub(app, FIRST_UTUB_ID)
    locked_response = post_restore(client, csrf_token, FIRST_UTUB_ID, own_row_id)

    assert not_in_trash_response.status_code == 404
    assert locked_response.status_code == 403
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URL_RESTORED_FROM_TRASH)
        == 0
    )


@pytest.mark.parametrize(
    ("scenario", "acting_user_id", "expected_visible_url_numbers"),
    [
        ("plain", FIRST_USER_ID, (1, 2, 3)),
        ("plain", SECOND_USER_ID, (2,)),
        ("plain", THIRD_USER_ID, (3,)),
        ("co_creator", SECOND_USER_ID, (1, 2, 3)),
        ("co_creator", THIRD_USER_ID, (1, 2, 3)),
        ("adder_departed", FIRST_USER_ID, (1, 2, 3)),
        ("adder_departed", SECOND_USER_ID, ()),
        ("adder_departed", THIRD_USER_ID, (2, 3)),
        ("member_departed", SECOND_USER_ID, ()),
        ("member_departed", THIRD_USER_ID, ()),
        ("locked", FIRST_USER_ID, (1, 2, 3)),
        ("locked", SECOND_USER_ID, (2,)),
        ("locked", THIRD_USER_ID, (3,)),
    ],
)
def test_restore_action_agrees_with_trash_list(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    scenario: str,
    acting_user_id: int,
    expected_visible_url_numbers: Tuple[int, ...],
):
    """
    GIVEN all three URLs of UTub 1 are trashed and a visibility scenario is applied
    WHEN the acting user lists their Trash and then tries to restore every row
    THEN the listed rows are exactly the expected ones, a row absent from the list is
        404, a listed row with canRestore is 200 and a listed row without canRestore is
        403 (locked UTub), so the list and the action share one definition of
        "actionable"
    """
    _, _, _, app = login_first_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)]
    expected_visible_row_ids: set[int] = {
        get_utub_url_id(app, FIRST_UTUB_ID, url_number)
        for url_number in expected_visible_url_numbers
    }
    for row_id in row_ids:
        trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    if scenario == "co_creator":
        set_member_role(app, FIRST_UTUB_ID, acting_user_id, Member_Role.CO_CREATOR)
    elif scenario == "adder_departed":
        remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    elif scenario == "member_departed":
        remove_member(app, FIRST_UTUB_ID, acting_user_id)
    elif scenario == "locked":
        lock_utub(app, FIRST_UTUB_ID)
    else:
        assert scenario == "plain"
    expected_listed_status = 403 if scenario == "locked" else 200
    with login_as_user(app, acting_user_id) as (client, csrf_token):
        can_restore_by_row = get_trash_can_restore(client)
        assert set(can_restore_by_row) == expected_visible_row_ids

        restored_row_ids: list[int] = []
        for row_id in row_ids:
            response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)
            if row_id not in can_restore_by_row:
                assert_not_in_trash_response(response)
                continue
            assert response.status_code == expected_listed_status
            if can_restore_by_row[row_id]:
                assert response.status_code == 200
                restored_row_ids.append(row_id)
            else:
                assert (
                    response.json[STD_JSON_RESPONSE.ERROR_CODE]
                    == URLErrorCodes.UTUB_IS_LOCKED
                )
    if scenario == "plain" and acting_user_id == FIRST_USER_ID:
        assert restored_row_ids == row_ids
