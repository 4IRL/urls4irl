from datetime import datetime, timedelta
from typing import Any, Tuple
from unittest.mock import patch

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from flask.wrappers import Response
from sqlalchemy import update

from backend import db
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_tags import Utub_Tags
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.schemas.trash import TrashEmptiedResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.trash_strs import TRASH_FAILURE, TRASH_SUCCESS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utils.strings.utub_strs import UTUB_ID
from backend.utubs.constants import UTubErrorCodes
from backend.utubs.guards import lock_trashed_utub_for_creator
from backend.utubs.services.empty_trash import _purge_trashed_url_ids
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
)
from tests.integration.trash.trash_helpers import (
    AJAX_HEADERS,
    FIRST_USER_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    SECOND_UTUB_ID,
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
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.trash

PURGED_URL_IDS_KEY = "purgedUtubUrlIDs"
PURGED_UTUB_IDS_KEY = "purgedUtubIDs"
TOTAL_PURGED_KEY = "totalPurged"
TOTAL_SKIPPED_LOCKED_KEY = "totalSkippedLocked"


def post_empty_trash(
    client: FlaskClient, csrf_token: str, body: dict[str, Any] | None
) -> Response:
    return client.post(
        url_for(ROUTES.UTUBS.EMPTY_TRASH),
        json=body,
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def get_listed_at(client: FlaskClient) -> str:
    response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)
    assert response.status_code == 200
    return response.json[MODELS.LISTED_AT]


def empty_tab(client: FlaskClient, csrf_token: str, scope: str) -> Response:
    """Empty one tab using the ``listedAt`` of a fresh read of the Trash list."""
    return post_empty_trash(
        client, csrf_token, {"scope": scope, "listedAt": get_listed_at(client)}
    )


def get_utub_deleted_at(app: Flask, utub_id: int) -> datetime | None:
    with app.app_context():
        return Utubs.query.get(utub_id).deleted_at


def get_url_tag_ids_of_row(app: Flask, utub_url_id: int) -> set[int]:
    with app.app_context():
        return {
            url_tag.utub_tag_id
            for url_tag in Utub_Url_Tags.query.filter(
                Utub_Url_Tags.utub_url_id == utub_url_id
            ).all()
        }


def count_tags_in_utub(app: Flask, utub_id: int) -> int:
    with app.app_context():
        return Utub_Tags.query.filter(Utub_Tags.utub_id == utub_id).count()


def count_urls_in_utub(app: Flask, utub_id: int) -> int:
    with app.app_context():
        return Utub_Urls.query.filter(Utub_Urls.utub_id == utub_id).count()


def count_members_in_utub(app: Flask, utub_id: int) -> int:
    with app.app_context():
        return Utub_Members.query.filter(Utub_Members.utub_id == utub_id).count()


def create_extra_utub(app: Flask, creator_id: int, name: str) -> int:
    """Add an empty UTub (creator is its only member) and return its id."""
    with app.app_context():
        creator: Users = Users.query.get(creator_id)
        new_utub = Utubs(name=name, utub_creator=creator_id, utub_description="")
        creator_membership = Utub_Members(member_role=Member_Role.CREATOR)
        creator_membership.to_user = creator
        new_utub.members.append(creator_membership)
        db.session.add(new_utub)
        db.session.commit()
        return new_utub.id


def set_row_deleted_at(app: Flask, utub_url_id: int, deleted_at: datetime) -> None:
    with app.app_context():
        utub_url: Utub_Urls = Utub_Urls.query.get(utub_url_id)
        utub_url.deleted_at = deleted_at
        db.session.commit()


def set_utub_deleted_at(app: Flask, utub_id: int, deleted_at: datetime) -> None:
    with app.app_context():
        utub: Utubs = Utubs.query.get(utub_id)
        utub.deleted_at = deleted_at
        db.session.commit()


def get_url_id_of_row(app: Flask, utub_url_id: int) -> int:
    with app.app_context():
        return Utub_Urls.query.get(utub_url_id).url_id


def add_url_row_to_utub(app: Flask, utub_id: int, url_id: int, user_id: int) -> int:
    """Attach an existing standalone URL to a UTub and return the new row's id."""
    with app.app_context():
        utub_url = Utub_Urls(
            utub_id=utub_id, url_id=url_id, user_id=user_id, url_title="Extra row"
        )
        db.session.add(utub_url)
        db.session.commit()
        return utub_url.id


def restore_row_behind_the_session(utub_url_id: int) -> None:
    """Un-trash a row with a Core statement that bypasses the ORM session.

    Stands in for a concurrent restore that committed: the session's identity map is
    left stale, as it would be, and the next statement sees the new state. A second
    engine connection cannot be used here, since the test harness keeps every write
    in one uncommitted outer transaction that other connections cannot see.
    """
    db.session.get_bind().execute(
        update(Utub_Urls)
        .where(Utub_Urls.id == utub_url_id)
        .values(deleted_at=None, deleted_by=None)
    )


def retrash_row_behind_the_session(utub_url_id: int, deleted_at: datetime) -> None:
    """Re-trash a row at ``deleted_at`` the same way as the restore helper above.

    Stands in for a restore followed by a fresh delete that both committed after the
    caller's Trash list was read.
    """
    db.session.get_bind().execute(
        update(Utub_Urls)
        .where(Utub_Urls.id == utub_url_id)
        .values(deleted_at=deleted_at)
    )


def lock_utub_behind_the_session(utub_id: int) -> None:
    """Lock a UTub the same way as ``restore_row_behind_the_session``."""
    db.session.get_bind().execute(
        update(Utubs).where(Utubs.id == utub_id).values(is_locked=True)
    )


def restore_utub_behind_the_session(utub_id: int) -> None:
    """Un-trash a UTub the same way as ``restore_row_behind_the_session``."""
    db.session.get_bind().execute(
        update(Utubs)
        .where(Utubs.id == utub_id)
        .values(deleted_at=None, deleted_by=None)
    )


def retrash_utub_behind_the_session(utub_id: int, deleted_at: datetime) -> None:
    """Re-trash a UTub at ``deleted_at`` the same way as the restore helper above."""
    db.session.get_bind().execute(
        update(Utubs).where(Utubs.id == utub_id).values(deleted_at=deleted_at)
    )


def assert_emptied_response(
    response: Response,
    *,
    scope: str,
    purged_utub_url_ids: list[int],
    purged_utub_ids: list[int],
    total_skipped_locked: int,
) -> None:
    assert response.status_code == 200
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.SUCCESS
    assert response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_SUCCESS.TRASH_EMPTIED
    TrashEmptiedResponseSchema.model_validate(response_json)
    assert response_json[MODELS.SCOPE] == scope
    assert sorted(response_json[PURGED_URL_IDS_KEY]) == sorted(purged_utub_url_ids)
    assert sorted(response_json[PURGED_UTUB_IDS_KEY]) == sorted(purged_utub_ids)
    assert response_json[TOTAL_PURGED_KEY] == len(purged_utub_url_ids) + len(
        purged_utub_ids
    )
    assert response_json[TOTAL_SKIPPED_LOCKED_KEY] == total_skipped_locked


def assert_bad_request(response: Response, *, error_fields: list[str]) -> None:
    assert response.status_code == 400
    response_json = response.json
    assert response_json[STD_JSON_RESPONSE.STATUS] == STD_JSON_RESPONSE.FAILURE
    assert (
        response_json[STD_JSON_RESPONSE.MESSAGE] == TRASH_FAILURE.UNABLE_TO_EMPTY_TRASH
    )
    assert (
        response_json[STD_JSON_RESPONSE.ERROR_CODE]
        == UTubErrorCodes.UNABLE_TO_EMPTY_TRASH_ERROR
    )
    if error_fields:
        assert sorted(response_json[STD_JSON_RESPONSE.ERRORS]) == sorted(error_fields)


# URLs tab


def test_empty_urls_tab_purges_exactly_what_the_list_shows(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the creator trashed all three URLs of UTub 1 and read the Trash list
    WHEN they empty the URLs tab with that list's listedAt
    THEN the response validates against the schema and names exactly the listed rows,
        each row and its url-tags are gone, the UTub and its tags survive and the
        URLs tab is empty afterwards
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)]
    for row_id in row_ids:
        trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    listed_ids = get_trash_url_ids(client)
    assert sorted(listed_ids) == sorted(row_ids)
    assert all(count_url_tags_of_row(app, row_id) > 0 for row_id in row_ids)

    response = empty_tab(client, csrf_token, "urls")

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=listed_ids,
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    for row_id in row_ids:
        assert not row_exists(app, row_id)
        assert count_url_tags_of_row(app, row_id) == 0
    assert utub_exists(app, FIRST_UTUB_ID)
    assert get_utub_deleted_at(app, FIRST_UTUB_ID) is None
    assert get_trash_url_ids(client) == []


def test_empty_urls_tab_leaves_live_rows_untouched(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN one trashed URL and two live URLs in UTub 1
    WHEN the creator empties the URLs tab
    THEN only the trashed row is deleted and the live rows keep their url-tags
    """
    client, csrf_token, _, app = login_first_user_without_register
    trashed_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    live_row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (2, 3)]
    trash_utub_url(app, trashed_row_id, deleted_by=FIRST_USER_ID)
    live_tags_before = [count_url_tags_of_row(app, row_id) for row_id in live_row_ids]

    response = empty_tab(client, csrf_token, "urls")

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[trashed_row_id],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert not row_exists(app, trashed_row_id)
    for row_id, tags_before in zip(live_row_ids, live_tags_before):
        assert row_exists(app, row_id)
        assert count_url_tags_of_row(app, row_id) == tags_before


def test_plain_member_empties_only_rows_they_can_see(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN URL 1 (added by user 1) and URL 2 (added by user 2) are both trashed in UTub 1
    WHEN plain member user 2 empties the URLs tab
    THEN only their own row is deleted; user 1's trashed row, which they cannot see,
        survives still trashed with its url-tags
    """
    client, csrf_token, _, app = login_second_user_without_register
    invisible_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    own_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, invisible_row_id, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, own_row_id, deleted_by=SECOND_USER_ID)
    invisible_before = get_row_state(app, invisible_row_id)
    invisible_tags_before = count_url_tags_of_row(app, invisible_row_id)
    assert get_trash_url_ids(client) == [own_row_id]

    response = empty_tab(client, csrf_token, "urls")

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[own_row_id],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert not row_exists(app, own_row_id)
    assert get_row_state(app, invisible_row_id) == invisible_before
    assert count_url_tags_of_row(app, invisible_row_id) == invisible_tags_before


def test_rows_trashed_after_listed_at_survive(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN one URL in Trash when the list is read, and a second whose deleted_at is
        after that list's listedAt
    WHEN the creator empties the URLs tab with that listedAt
    THEN only the first is deleted and the later one stays in Trash untouched
    """
    client, csrf_token, _, app = login_first_user_without_register
    listed_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    later_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, listed_row_id, deleted_by=FIRST_USER_ID)
    listed_at = get_listed_at(client)
    trash_utub_url(app, later_row_id, deleted_by=FIRST_USER_ID)
    set_row_deleted_at(
        app, later_row_id, datetime.fromisoformat(listed_at) + timedelta(seconds=1)
    )
    later_before = get_row_state(app, later_row_id)

    response = post_empty_trash(
        client, csrf_token, {"scope": "urls", "listedAt": listed_at}
    )

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[listed_row_id],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert not row_exists(app, listed_row_id)
    assert get_row_state(app, later_row_id) == later_before
    assert get_trash_url_ids(client) == [later_row_id]


def test_row_trashed_exactly_at_listed_at_is_purged(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL whose deleted_at equals the listedAt of the list read
    WHEN the creator empties the URLs tab with that listedAt
    THEN the bound is inclusive: the row and its url-tags are deleted
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    listed_at = get_listed_at(client)
    set_row_deleted_at(app, row_id, datetime.fromisoformat(listed_at))

    response = post_empty_trash(
        client, csrf_token, {"scope": "urls", "listedAt": listed_at}
    )

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[row_id],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert not row_exists(app, row_id)
    assert count_url_tags_of_row(app, row_id) == 0


def test_future_listed_at_is_clamped_to_server_time(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL whose deleted_at is an hour in the future
    WHEN the creator empties the URLs tab with a listedAt two hours in the future
    THEN the bound is clamped to the server clock, so the row survives
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    set_row_deleted_at(app, row_id, utc_now() + timedelta(hours=1))
    before = get_row_state(app, row_id)

    response = post_empty_trash(
        client,
        csrf_token,
        {"scope": "urls", "listedAt": (utc_now() + timedelta(hours=2)).isoformat()},
    )

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert get_row_state(app, row_id) == before


def test_empty_urls_tab_skips_rows_of_locked_utub(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a URL trashed in UTub 1, which is then locked
    WHEN the creator empties the URLs tab
    THEN the response is 200 with nothing purged and totalSkippedLocked == 1, and the
        row stays trashed with its url-tags and still shows in the list
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    before = get_row_state(app, row_id)
    tags_before = count_url_tags_of_row(app, row_id)
    assert tags_before > 0

    response = empty_tab(client, csrf_token, "urls")

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=1,
    )
    assert get_row_state(app, row_id) == before
    assert count_url_tags_of_row(app, row_id) == tags_before
    assert get_trash_url_ids(client) == [row_id]


def test_empty_urls_tab_purges_unlocked_utub_rows_and_skips_locked_ones_in_one_batch(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN trashed rows in a locked UTub 1 and in an unlocked second UTub of the creator
    WHEN the creator empties the URLs tab
    THEN only the unlocked UTub's rows are deleted, every locked row is counted in
        totalSkippedLocked and stays trashed with its url-tags
    """
    client, csrf_token, _, app = login_first_user_without_register
    locked_row_ids = [
        get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)
    ]
    extra_utub_id = create_extra_utub(app, FIRST_USER_ID, "Unlocked extra UTub")
    extra_row_ids = [
        add_url_row_to_utub(
            app, extra_utub_id, get_url_id_of_row(app, row_id), FIRST_USER_ID
        )
        for row_id in locked_row_ids[:2]
    ]
    for row_id in locked_row_ids + extra_row_ids:
        trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    lock_utub(app, FIRST_UTUB_ID)
    locked_before = [get_row_state(app, row_id) for row_id in locked_row_ids]
    locked_url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    assert locked_url_tags_before > 0

    response = empty_tab(client, csrf_token, "urls")

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=extra_row_ids,
        purged_utub_ids=[],
        total_skipped_locked=len(locked_row_ids),
    )
    assert not any(row_exists(app, row_id) for row_id in extra_row_ids)
    assert [get_row_state(app, row_id) for row_id in locked_row_ids] == locked_before
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == locked_url_tags_before
    assert sorted(get_trash_url_ids(client)) == sorted(locked_row_ids)


def test_plain_member_cannot_empty_rows_of_a_trashed_utub_they_do_not_own(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the creator (user 1) trashed UTub 1, so its three URLs ride along in Trash
    WHEN plain member user 2 empties the URLs tab
    THEN nothing is deleted: they do not see the rows and every row and url-tag survives
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)]
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    assert url_tags_before > 0
    assert get_trash_url_ids(client) == []

    response = empty_tab(client, csrf_token, "urls")

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert all(row_exists(app, row_id) for row_id in row_ids)
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == url_tags_before
    assert get_utub_deleted_at(app, FIRST_UTUB_ID) is not None


def test_empty_urls_tab_with_trashed_utub_purges_its_urls_but_not_the_utub(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed with its three URLs riding along
    WHEN the creator empties the URLs tab
    THEN all three rows and their url-tags are deleted, but the UTub, its members and
        its tags remain, still trashed, with urlCount 0
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)]
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    members_before = count_members_in_utub(app, FIRST_UTUB_ID)
    utub_tags_before = count_tags_in_utub(app, FIRST_UTUB_ID)
    assert utub_tags_before > 0
    assert sorted(get_trash_url_ids(client)) == sorted(row_ids)

    response = empty_tab(client, csrf_token, "urls")

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=row_ids,
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert count_urls_in_utub(app, FIRST_UTUB_ID) == 0
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == 0
    assert utub_exists(app, FIRST_UTUB_ID)
    assert get_utub_deleted_at(app, FIRST_UTUB_ID) is not None
    assert count_members_in_utub(app, FIRST_UTUB_ID) == members_before
    assert count_tags_in_utub(app, FIRST_UTUB_ID) == utub_tags_before
    trash_response = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS)
    utub_items = trash_response.json[MODELS.UTUBS]
    assert [item[UTUB_ID] for item in utub_items] == [FIRST_UTUB_ID]
    assert utub_items[0][MODELS.URL_COUNT] == 0


def test_empty_urls_tab_with_nothing_in_trash_is_a_no_op(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN nothing in Trash
    WHEN the creator empties either tab
    THEN each response is 200 with zero totals and no emptied-Trash counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)]

    urls_response = empty_tab(client, csrf_token, "urls")
    utubs_response = empty_tab(client, csrf_token, "utubs")

    assert_emptied_response(
        urls_response,
        scope="urls",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert_emptied_response(
        utubs_response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert all(row_exists(app, row_id) for row_id in row_ids)
    for event in (
        EventName.URLS_EMPTIED_FROM_TRASH,
        EventName.UTUBS_EMPTIED_FROM_TRASH,
    ):
        assert count_counter_keys(provide_metrics_redis, event) == 0


def test_row_restored_during_empty_survives_with_its_tags(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN two trashed URLs, and one is restored (by a concurrent request)
        after the candidate rows were selected but before they are deleted
    WHEN the creator empties the URLs tab
    THEN the restored row and its url-tags are untouched, only the other row is
        deleted, and the response names just the deleted row
    """
    client, csrf_token, _, app = login_first_user_without_register
    restored_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    purged_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, restored_row_id, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, purged_row_id, deleted_by=FIRST_USER_ID)
    restored_tags_before = get_url_tag_ids_of_row(app, restored_row_id)
    assert restored_tags_before
    listed_at = get_listed_at(client)

    def restore_then_purge(*, ids: list[int], listed_at: datetime) -> list[int]:
        assert sorted(ids) == sorted([restored_row_id, purged_row_id])
        restore_row_behind_the_session(restored_row_id)
        return _purge_trashed_url_ids(ids=ids, listed_at=listed_at)

    with patch(
        "backend.utubs.services.empty_trash._purge_trashed_url_ids",
        side_effect=restore_then_purge,
    ):
        response = post_empty_trash(
            client, csrf_token, {"scope": "urls", "listedAt": listed_at}
        )

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[purged_row_id],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert response.json[TOTAL_PURGED_KEY] == 1
    assert restored_row_id not in response.json[PURGED_URL_IDS_KEY]
    assert row_exists(app, restored_row_id)
    assert get_row_state(app, restored_row_id)["deleted_at"] is None
    assert get_url_tag_ids_of_row(app, restored_row_id) == restored_tags_before
    assert not row_exists(app, purged_row_id)


def test_row_retrashed_after_listed_at_during_empty_survives(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN two trashed URLs, and one is restored then trashed again (by a concurrent
        request) after the list was read, with a deleted_at after the list's listedAt,
        between the candidate select and the DELETE
    WHEN the creator empties the URLs tab
    THEN the DELETE's own listedAt bound leaves the re-trashed row and its url-tags
        untouched and only the other row is deleted
    """
    client, csrf_token, _, app = login_first_user_without_register
    retrashed_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    purged_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, retrashed_row_id, deleted_by=FIRST_USER_ID)
    trash_utub_url(app, purged_row_id, deleted_by=FIRST_USER_ID)
    retrashed_tags_before = get_url_tag_ids_of_row(app, retrashed_row_id)
    assert retrashed_tags_before
    listed_at = get_listed_at(client)
    retrashed_at = datetime.fromisoformat(listed_at) + timedelta(seconds=1)

    def retrash_then_purge(*, ids: list[int], listed_at: datetime) -> list[int]:
        assert sorted(ids) == sorted([retrashed_row_id, purged_row_id])
        retrash_row_behind_the_session(retrashed_row_id, retrashed_at)
        return _purge_trashed_url_ids(ids=ids, listed_at=listed_at)

    with patch(
        "backend.utubs.services.empty_trash._purge_trashed_url_ids",
        side_effect=retrash_then_purge,
    ):
        response = post_empty_trash(
            client, csrf_token, {"scope": "urls", "listedAt": listed_at}
        )

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[purged_row_id],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert row_exists(app, retrashed_row_id)
    assert get_row_state(app, retrashed_row_id)["deleted_at"] == retrashed_at
    assert get_url_tag_ids_of_row(app, retrashed_row_id) == retrashed_tags_before
    assert not row_exists(app, purged_row_id)


def test_utub_locked_during_empty_keeps_its_urls(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN two trashed URLs in UTub 1, and the UTub is locked (by a concurrent request)
        between the candidate select and the DELETE
    WHEN the creator empties the URLs tab
    THEN the DELETE's own locked-UTub exclusion deletes nothing: both rows and their
        url-tags survive still trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2)]
    for row_id in row_ids:
        trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    before = [get_row_state(app, row_id) for row_id in row_ids]
    url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    listed_at = get_listed_at(client)

    def lock_then_purge(*, ids: list[int], listed_at: datetime) -> list[int]:
        assert sorted(ids) == sorted(row_ids)
        lock_utub_behind_the_session(FIRST_UTUB_ID)
        return _purge_trashed_url_ids(ids=ids, listed_at=listed_at)

    with patch(
        "backend.utubs.services.empty_trash._purge_trashed_url_ids",
        side_effect=lock_then_purge,
    ):
        response = post_empty_trash(
            client, csrf_token, {"scope": "urls", "listedAt": listed_at}
        )

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert [get_row_state(app, row_id) for row_id in row_ids] == before
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == url_tags_before


def test_parent_utub_restored_during_empty_keeps_all_its_rows(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 is trashed with three URLs riding along, and the UTub is restored
        (by a concurrent request) after the candidates were selected
    WHEN the creator empties the URLs tab
    THEN nothing is deleted: every row and url-tag survives in the live UTub
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2, 3)]
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    assert url_tags_before > 0
    listed_at = get_listed_at(client)

    def restore_then_purge(*, ids: list[int], listed_at: datetime) -> list[int]:
        assert sorted(ids) == sorted(row_ids)
        restore_utub_behind_the_session(FIRST_UTUB_ID)
        return _purge_trashed_url_ids(ids=ids, listed_at=listed_at)

    with patch(
        "backend.utubs.services.empty_trash._purge_trashed_url_ids",
        side_effect=restore_then_purge,
    ):
        response = post_empty_trash(
            client, csrf_token, {"scope": "urls", "listedAt": listed_at}
        )

    assert_emptied_response(
        response,
        scope="urls",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert all(row_exists(app, row_id) for row_id in row_ids)
    assert get_utub_deleted_at(app, FIRST_UTUB_ID) is None
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == url_tags_before


# UTubs tab


def test_empty_utubs_tab_purges_utub_with_all_children(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 (members, tags, URLs and url-tags) is trashed by its creator
    WHEN the creator empties the UTubs tab
    THEN the response names UTub 1, and the UTub and every child row are gone with no
        foreign-key error
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    assert count_urls_in_utub(app, FIRST_UTUB_ID) > 0
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) > 0
    assert count_members_in_utub(app, FIRST_UTUB_ID) > 0

    response = empty_tab(client, csrf_token, "utubs")

    assert_emptied_response(
        response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[FIRST_UTUB_ID],
        total_skipped_locked=0,
    )
    assert not utub_exists(app, FIRST_UTUB_ID)
    assert count_urls_in_utub(app, FIRST_UTUB_ID) == 0
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == 0
    assert count_members_in_utub(app, FIRST_UTUB_ID) == 0
    assert get_trashed_utub_ids(client) == []


def test_empty_utubs_tab_skips_locked_and_leaves_other_users_utubs(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the creator trashed UTub 1 and a second UTub of their own (locked), and user 2
        trashed UTub 2, which user 1 does not own
    WHEN the creator empties the UTubs tab
    THEN UTub 1 is deleted, the locked UTub is skipped and counted, and user 2's
        trashed UTub is untouched
    """
    client, csrf_token, _, app = login_first_user_without_register
    locked_utub_id = create_extra_utub(app, FIRST_USER_ID, "Locked extra UTub")
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    trash_utub(app, locked_utub_id, FIRST_USER_ID)
    lock_utub(app, locked_utub_id)
    trash_utub(app, SECOND_UTUB_ID, SECOND_USER_ID)
    other_deleted_at = get_utub_deleted_at(app, SECOND_UTUB_ID)
    assert sorted(get_trashed_utub_ids(client)) == sorted(
        [FIRST_UTUB_ID, locked_utub_id]
    )

    response = empty_tab(client, csrf_token, "utubs")

    assert_emptied_response(
        response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[FIRST_UTUB_ID],
        total_skipped_locked=1,
    )
    assert not utub_exists(app, FIRST_UTUB_ID)
    assert utub_exists(app, locked_utub_id)
    assert get_utub_deleted_at(app, locked_utub_id) is not None
    assert utub_exists(app, SECOND_UTUB_ID)
    assert get_utub_deleted_at(app, SECOND_UTUB_ID) == other_deleted_at
    assert get_trashed_utub_ids(client) == [locked_utub_id]


def test_utubs_trashed_after_listed_at_survive(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 in Trash when the list is read, and a second UTub trashed after it
    WHEN the creator empties the UTubs tab with that listedAt
    THEN only UTub 1 is deleted and the later UTub stays in Trash
    """
    client, csrf_token, _, app = login_first_user_without_register
    later_utub_id = create_extra_utub(app, FIRST_USER_ID, "Trashed later UTub")
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    listed_at = get_listed_at(client)
    trash_utub(app, later_utub_id, FIRST_USER_ID)
    set_utub_deleted_at(
        app, later_utub_id, datetime.fromisoformat(listed_at) + timedelta(seconds=1)
    )

    response = post_empty_trash(
        client, csrf_token, {"scope": "utubs", "listedAt": listed_at}
    )

    assert_emptied_response(
        response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[FIRST_UTUB_ID],
        total_skipped_locked=0,
    )
    assert not utub_exists(app, FIRST_UTUB_ID)
    assert utub_exists(app, later_utub_id)
    assert get_trashed_utub_ids(client) == [later_utub_id]


def test_utub_trashed_exactly_at_listed_at_is_purged(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed UTub whose deleted_at equals the listedAt of the list read
    WHEN the creator empties the UTubs tab with that listedAt
    THEN the bound is inclusive: the UTub and its children are deleted
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    listed_at = get_listed_at(client)
    set_utub_deleted_at(app, FIRST_UTUB_ID, datetime.fromisoformat(listed_at))

    response = post_empty_trash(
        client, csrf_token, {"scope": "utubs", "listedAt": listed_at}
    )

    assert_emptied_response(
        response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[FIRST_UTUB_ID],
        total_skipped_locked=0,
    )
    assert not utub_exists(app, FIRST_UTUB_ID)
    assert count_urls_in_utub(app, FIRST_UTUB_ID) == 0


def test_utub_restored_during_empty_survives_and_is_not_counted_as_locked(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a locked UTub 1 that is trashed, a genuinely locked trashed UTub and an
        unlocked trashed UTub, and UTub 1 is restored (by a concurrent request) just
        before its row lock is taken, which leaves it locked
    WHEN the creator empties the UTubs tab
    THEN the restored UTub survives with all its children, only the unlocked UTub is
        deleted, and only the genuinely locked UTub is counted in totalSkippedLocked
    """
    client, csrf_token, _, app = login_first_user_without_register
    locked_extra_id = create_extra_utub(app, FIRST_USER_ID, "Locked extra UTub")
    other_extra_id = create_extra_utub(app, FIRST_USER_ID, "Purged extra UTub")
    lock_utub(app, FIRST_UTUB_ID)
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    trash_utub(app, locked_extra_id, FIRST_USER_ID)
    lock_utub(app, locked_extra_id)
    trash_utub(app, other_extra_id, FIRST_USER_ID)
    urls_before = count_urls_in_utub(app, FIRST_UTUB_ID)
    members_before = count_members_in_utub(app, FIRST_UTUB_ID)
    listed_at = get_listed_at(client)
    calls: list[int] = []

    def restore_first_then_lock(**kwargs: Any) -> Any:
        calls.append(kwargs["utub_id"])
        if len(calls) == 1:
            restore_utub_behind_the_session(kwargs["utub_id"])
        return lock_trashed_utub_for_creator(**kwargs)

    with patch(
        "backend.utubs.services.empty_trash.lock_trashed_utub_for_creator",
        side_effect=restore_first_then_lock,
    ):
        response = post_empty_trash(
            client, csrf_token, {"scope": "utubs", "listedAt": listed_at}
        )

    assert calls == [FIRST_UTUB_ID, locked_extra_id, other_extra_id]
    assert_emptied_response(
        response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[other_extra_id],
        total_skipped_locked=1,
    )
    assert response.json[TOTAL_PURGED_KEY] == 1
    assert utub_exists(app, FIRST_UTUB_ID)
    assert get_utub_deleted_at(app, FIRST_UTUB_ID) is None
    assert count_urls_in_utub(app, FIRST_UTUB_ID) == urls_before
    assert count_members_in_utub(app, FIRST_UTUB_ID) == members_before
    assert utub_exists(app, locked_extra_id)
    assert get_utub_deleted_at(app, locked_extra_id) is not None
    assert not utub_exists(app, other_extra_id)


def test_utub_retrashed_after_listed_at_during_empty_survives(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed UTub that is restored then trashed again (by a concurrent request)
        with a deleted_at after the list's listedAt, just before its row lock is taken
    WHEN the creator empties the UTubs tab with that listedAt
    THEN the fresh-state bound under the row lock leaves the UTub and its children
        untouched, nothing is purged and nothing is counted as locked
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    urls_before = count_urls_in_utub(app, FIRST_UTUB_ID)
    members_before = count_members_in_utub(app, FIRST_UTUB_ID)
    listed_at = get_listed_at(client)
    retrashed_at = datetime.fromisoformat(listed_at) + timedelta(seconds=1)

    def retrash_then_lock(**kwargs: Any) -> Any:
        retrash_utub_behind_the_session(kwargs["utub_id"], retrashed_at)
        return lock_trashed_utub_for_creator(**kwargs)

    with patch(
        "backend.utubs.services.empty_trash.lock_trashed_utub_for_creator",
        side_effect=retrash_then_lock,
    ):
        response = post_empty_trash(
            client, csrf_token, {"scope": "utubs", "listedAt": listed_at}
        )

    assert_emptied_response(
        response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert utub_exists(app, FIRST_UTUB_ID)
    assert get_utub_deleted_at(app, FIRST_UTUB_ID) == retrashed_at
    assert count_urls_in_utub(app, FIRST_UTUB_ID) == urls_before
    assert count_members_in_utub(app, FIRST_UTUB_ID) == members_before


def test_empty_utubs_tab_does_not_purge_a_utub_the_caller_does_not_own(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 created and trashed UTub 2, of which user 1 is only a member
    WHEN user 1 empties the UTubs tab
    THEN nothing is deleted and UTub 2 is still trashed
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, SECOND_UTUB_ID, SECOND_USER_ID)

    response = empty_tab(client, csrf_token, "utubs")

    assert_emptied_response(
        response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[],
        total_skipped_locked=0,
    )
    assert get_utub_deleted_at(app, SECOND_UTUB_ID) is not None


def test_each_user_empties_only_their_own_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTub 1 (user 1) and UTub 2 (user 2) are both trashed
    WHEN user 2 empties the UTubs tab
    THEN only UTub 2 is deleted and user 1's UTub remains trashed
    """
    _, _, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    trash_utub(app, SECOND_UTUB_ID, SECOND_USER_ID)

    with login_as_user(app, SECOND_USER_ID) as (client, csrf_token):
        response = empty_tab(client, csrf_token, "utubs")

    assert_emptied_response(
        response,
        scope="utubs",
        purged_utub_url_ids=[],
        purged_utub_ids=[SECOND_UTUB_ID],
        total_skipped_locked=0,
    )
    assert not utub_exists(app, SECOND_UTUB_ID)
    assert utub_exists(app, FIRST_UTUB_ID)
    assert get_utub_deleted_at(app, FIRST_UTUB_ID) is not None


# Validation


@pytest.mark.parametrize(
    "body, error_fields",
    [
        ({"scope": "everything", "listedAt": "2026-10-15T12:00:00+00:00"}, ["scope"]),
        ({"scope": "urls", "listedAt": "2026-10-15T12:00:00"}, ["listedAt"]),
        ({"scope": "urls", "listedAt": "not-a-date"}, ["listedAt"]),
        ({"scope": "urls"}, ["listedAt"]),
        ({"listedAt": "2026-10-15T12:00:00+00:00"}, ["scope"]),
        ({}, ["scope", "listedAt"]),
    ],
    ids=[
        "invalid_scope",
        "naive_listed_at",
        "unparseable_listed_at",
        "missing_listed_at",
        "missing_scope",
        "empty_body",
    ],
)
def test_invalid_body_is_bad_request_and_deletes_nothing(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    body: dict[str, Any],
    error_fields: list[str],
):
    """
    GIVEN a trashed URL and a trashed UTub
    WHEN the creator posts a body with a bad scope or a missing, naive or unparseable
        listedAt
    THEN the response is a 400 with field errors keyed on the offending fields and
        nothing is deleted
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)

    response = post_empty_trash(client, csrf_token, body)

    assert_bad_request(response, error_fields=error_fields)
    assert get_row_state(app, row_id) == before


def test_missing_json_body_is_bad_request(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL
    WHEN the creator posts with no JSON body at all
    THEN the response is a 400 and the row is untouched
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    before = get_row_state(app, row_id)

    response = client.post(
        url_for(ROUTES.UTUBS.EMPTY_TRASH),
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )

    assert_bad_request(response, error_fields=[])
    assert get_row_state(app, row_id) == before


def test_empty_trash_without_csrf_token_is_forbidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL
    WHEN the creator posts the empty without a CSRF token
    THEN the response is the 403 HTML page and the row is untouched
    """
    client, _, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)

    response = client.post(
        url_for(ROUTES.UTUBS.EMPTY_TRASH),
        json={"scope": "urls", "listedAt": utc_now().isoformat()},
        headers=AJAX_HEADERS,
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert row_exists(app, row_id)


# Metrics


def test_empty_urls_tab_records_metric_with_bucketed_dimensions(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN three trashed URLs, and metrics enabled
    WHEN the creator empties the URLs tab
    THEN URLS_EMPTIED_FROM_TRASH goes 0 -> 1 with the bucketed purged and skipped
        counts, and the UTubs event is not written
    """
    client, csrf_token, _, app = login_first_user_without_register
    for url_id in (1, 2, 3):
        trash_utub_url(
            app, get_utub_url_id(app, FIRST_UTUB_ID, url_id), deleted_by=FIRST_USER_ID
        )
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URLS_EMPTIED_FROM_TRASH)
        == 0
    )

    response = empty_tab(client, csrf_token, "urls")

    assert response.status_code == 200
    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.URLS_EMPTIED_FROM_TRASH
    )
    assert len(counter_keys) == 1
    dims = parse_dims(counter_keys[0])
    assert dims["purged_count_bucket"] == "2-5"
    assert dims["skipped_count_bucket"] == "0"
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUBS_EMPTIED_FROM_TRASH)
        == 0
    )


def test_empty_utubs_tab_records_metric_with_skipped_bucket(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN one trashed UTub and one trashed locked UTub, and metrics enabled
    WHEN the creator empties the UTubs tab
    THEN UTUBS_EMPTIED_FROM_TRASH goes 0 -> 1 with purged bucket "1" and skipped
        bucket "1", and the URLs event is not written
    """
    client, csrf_token, _, app = login_first_user_without_register
    locked_utub_id = create_extra_utub(app, FIRST_USER_ID, "Locked extra UTub")
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    trash_utub(app, locked_utub_id, FIRST_USER_ID)
    lock_utub(app, locked_utub_id)
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUBS_EMPTIED_FROM_TRASH)
        == 0
    )

    response = empty_tab(client, csrf_token, "utubs")

    assert response.status_code == 200
    counter_keys = find_counter_keys(
        provide_metrics_redis, EventName.UTUBS_EMPTIED_FROM_TRASH
    )
    assert len(counter_keys) == 1
    dims = parse_dims(counter_keys[0])
    assert dims["purged_count_bucket"] == "1"
    assert dims["skipped_count_bucket"] == "1"
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URLS_EMPTIED_FROM_TRASH)
        == 0
    )


def test_empty_trash_with_only_locked_items_records_no_metric(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed URL in UTub 1, which is then locked
    WHEN the creator empties the URLs tab
    THEN nothing is purged and no emptied-Trash counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub_url(
        app, get_utub_url_id(app, FIRST_UTUB_ID, 1), deleted_by=FIRST_USER_ID
    )
    lock_utub(app, FIRST_UTUB_ID)

    response = empty_tab(client, csrf_token, "urls")

    assert response.status_code == 200
    assert response.json[TOTAL_SKIPPED_LOCKED_KEY] == 1
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URLS_EMPTIED_FROM_TRASH)
        == 0
    )


# Service failure


def test_empty_urls_tab_service_failure_rolls_back_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN two trashed URLs with url-tags, and the commit raising after the DELETE ran
    WHEN the creator empties the URLs tab
    THEN the unhandled error is a 500, the failure is logged once, both rows and their
        url-tags survive still trashed and no counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_ids = [get_utub_url_id(app, FIRST_UTUB_ID, url_id) for url_id in (1, 2)]
    for row_id in row_ids:
        trash_utub_url(app, row_id, deleted_by=FIRST_USER_ID)
    before = [get_row_state(app, row_id) for row_id in row_ids]
    url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    listed_at = get_listed_at(client)

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch.object(db.session, "commit", side_effect=RuntimeError("boom")),
        patch("backend.utubs.services.empty_trash.warning_log") as warning_log_mock,
    ):
        response = post_empty_trash(
            client, csrf_token, {"scope": "urls", "listedAt": listed_at}
        )

    warning_log_mock.assert_called_once()
    assert response.status_code == 500
    assert [get_row_state(app, row_id) for row_id in row_ids] == before
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == url_tags_before
    assert sorted(get_trash_url_ids(client)) == sorted(row_ids)
    assert (
        count_counter_keys(provide_metrics_redis, EventName.URLS_EMPTIED_FROM_TRASH)
        == 0
    )


def test_empty_utubs_tab_service_failure_rolls_back_and_records_nothing(
    metrics_enabled_app,
    provide_metrics_redis,
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a trashed UTub with children, and the commit raising after it was marked for
        deletion
    WHEN the creator empties the UTubs tab
    THEN the unhandled error is a 500, the failure is logged once, the UTub and every
        child row survive and it is still in Trash, and no counter is written
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, FIRST_USER_ID)
    urls_before = count_urls_in_utub(app, FIRST_UTUB_ID)
    url_tags_before = count_url_tags_in_utub(app, FIRST_UTUB_ID)
    members_before = count_members_in_utub(app, FIRST_UTUB_ID)
    listed_at = get_listed_at(client)

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch.object(db.session, "commit", side_effect=RuntimeError("boom")),
        patch("backend.utubs.services.empty_trash.warning_log") as warning_log_mock,
    ):
        response = post_empty_trash(
            client, csrf_token, {"scope": "utubs", "listedAt": listed_at}
        )

    warning_log_mock.assert_called_once()
    assert response.status_code == 500
    assert count_urls_in_utub(app, FIRST_UTUB_ID) == urls_before
    assert count_url_tags_in_utub(app, FIRST_UTUB_ID) == url_tags_before
    assert count_members_in_utub(app, FIRST_UTUB_ID) == members_before
    assert get_trashed_utub_ids(client) == [FIRST_UTUB_ID]
    assert (
        count_counter_keys(provide_metrics_redis, EventName.UTUBS_EMPTIED_FROM_TRASH)
        == 0
    )
