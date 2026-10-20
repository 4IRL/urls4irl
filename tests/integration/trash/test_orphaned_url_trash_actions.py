from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend import db
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import URL_FORM
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from backend.utubs.services.trash_predicates import count_trash_rows_for_user
from tests.integration.trash.trash_helpers import (
    AJAX_HEADERS,
    FIRST_USER_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    THIRD_USER_ID,
    assert_not_in_trash_response,
    get_row_state,
    get_trash_url_ids,
    post_restore,
    post_restore_urls,
    row_exists,
)
from tests.utils_for_test import (
    get_utub_url_id,
    remove_member,
    trash_utub,
    trash_utub_url,
)

pytestmark = pytest.mark.trash

THIRD_UTUB_ID = 3


def _purge(client: FlaskClient, csrf_token: str, utub_url_id: int):
    return client.delete(
        url_for(ROUTES.URLS.PURGE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=utub_url_id),
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def _empty_urls_tab(client: FlaskClient, csrf_token: str):
    listed_at = client.get(url_for(ROUTES.UTUBS.GET_TRASH), headers=AJAX_HEADERS).json[
        MODELS.LISTED_AT
    ]
    return client.post(
        url_for(ROUTES.UTUBS.EMPTY_TRASH),
        json={"scope": "urls", "listedAt": listed_at},
        headers={**AJAX_HEADERS, URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def _trash_count(app: Flask, user_id: int) -> int:
    with app.app_context():
        return count_trash_rows_for_user(user_id=user_id)


def _orphan_and_trash_url_two(app: Flask) -> int:
    """User 2 adds URL 2 (fixture), is removed from UTub 1, and the row is trashed."""
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    trash_utub_url(app, row_id, deleted_by=1)
    return row_id


def test_plain_member_lists_and_counts_orphaned_trashed_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 reads the Trash list and the Trash count
    THEN the orphaned URL is listed and counted
    """
    client, _, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    assert get_trash_url_ids(client) == [row_id]
    assert _trash_count(app, THIRD_USER_ID) == 1


def test_plain_member_restores_orphaned_url_and_adder_is_kept(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 restores it in place
    THEN it is 200, live again, and still records user 2 as its adder (still orphaned)
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)

    assert response.status_code == 200
    after = get_row_state(app, row_id)
    assert after["deleted_at"] is None
    assert after["user_id"] == SECOND_USER_ID


def test_plain_member_purges_orphaned_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 deletes it forever
    THEN it is 200 and the row is gone
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    response = _purge(client, csrf_token, row_id)

    assert response.status_code == 200
    assert not row_exists(app, row_id)


def test_empty_trash_includes_orphaned_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 empties the URLs tab
    THEN the orphaned row is purged
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    hidden_row_id = get_utub_url_id(app, FIRST_UTUB_ID, 1)
    trash_utub_url(app, hidden_row_id, deleted_by=1)

    response = _empty_urls_tab(client, csrf_token)

    assert response.status_code == 200
    assert not row_exists(app, row_id)
    assert row_exists(app, hidden_row_id)


def test_trashed_url_of_current_member_stays_hidden_from_plain_member(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 is still a member of UTub 1 and their URL is trashed
    WHEN plain member user 3 reads, counts, restores and purges it
    THEN it is invisible and non-actionable, exactly as before the orphan rule
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    trash_utub_url(app, row_id, deleted_by=SECOND_USER_ID)
    before = get_row_state(app, row_id)

    assert get_trash_url_ids(client) == []
    assert _trash_count(app, THIRD_USER_ID) == 0
    restore_response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)
    assert_not_in_trash_response(restore_response)
    assert_not_in_trash_response(_purge(client, csrf_token, row_id))
    assert get_row_state(app, row_id) == before


def test_orphaned_url_in_trashed_utub_stays_creator_only(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 2 (an URL's adder) has left UTub 1 and the whole UTub is trashed
    WHEN plain member user 3 lists, counts, restores and purges that URL
    THEN nothing is visible or actionable: the orphan rule is live-UTub only
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=1)
    before = get_row_state(app, row_id)

    assert get_trash_url_ids(client) == []
    assert _trash_count(app, THIRD_USER_ID) == 0
    restore_response = post_restore(client, csrf_token, FIRST_UTUB_ID, row_id)
    assert_not_in_trash_response(restore_response)
    assert_not_in_trash_response(_purge(client, csrf_token, row_id))
    assert get_row_state(app, row_id) == before


def test_bulk_in_place_restore_of_orphaned_url_is_deletable_by_plain_member(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a trashed URL in UTub 1 has left the UTub
    WHEN plain member user 3 bulk-restores it in place
    THEN the restored card is deletable by user 3 and still names user 2 as its adder
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_and_trash_url_two(app)

    response = post_restore_urls(client, csrf_token, FIRST_UTUB_ID, [row_id])

    assert response.status_code == 200
    restored = response.json[MODELS.RESTORED]
    assert [card[MODELS.UTUB_URL_ID] for card in restored] == [row_id]
    assert restored[0][MODELS.CAN_DELETE] is True
    assert restored[0][MODELS.ADDED_BY] == SECOND_USER_ID


def test_destination_restore_of_orphaned_url_credits_the_restorer(
    add_mixed_delete_permission_urls_in_first_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN the adder (user 2) of a URL has left UTub 1 and UTub 3, and UTub 1 is trashed
    WHEN creator user 1 restores that URL into UTub 3
    THEN the card credits user 1 (not the departed adder) and is deletable
    """
    client, csrf_token, _, app = login_first_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 2)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)
    remove_member(app, THIRD_UTUB_ID, SECOND_USER_ID)
    trash_utub(app, FIRST_UTUB_ID, deleted_by=FIRST_USER_ID)

    response = post_restore(
        client, csrf_token, FIRST_UTUB_ID, row_id, {"destUtubId": THIRD_UTUB_ID}
    )

    assert response.status_code == 200
    card = response.json[MODELS.URL]
    assert card[MODELS.UTUB_URL_ID] == row_id
    assert card[MODELS.ADDED_BY] == FIRST_USER_ID
    assert card[MODELS.ADDED_BY] != SECOND_USER_ID
    assert card[MODELS.CAN_DELETE] is True


def test_readded_member_is_adder_again_and_their_trashed_url_is_hidden(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN user 3 added URL 3, left UTub 1 and was re-added to it, and a manager then
        trashed URL 3
    WHEN plain member user 2 reads the Trash list
    THEN URL 3 is absent, because user 3 is a member (the adder) again
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_id = get_utub_url_id(app, FIRST_UTUB_ID, 3)
    remove_member(app, FIRST_UTUB_ID, THIRD_USER_ID)
    with app.app_context():
        db.session.add(
            Utub_Members(
                utub_id=FIRST_UTUB_ID,
                user_id=THIRD_USER_ID,
                member_role=Member_Role.MEMBER,
            )
        )
        db.session.commit()

    delete_response = client.delete(
        url_for(ROUTES.URLS.DELETE_URL, utub_id=FIRST_UTUB_ID, utub_url_id=row_id),
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )
    edit_response = client.patch(
        url_for(
            ROUTES.URLS.UPDATE_URL_TITLE, utub_id=FIRST_UTUB_ID, utub_url_id=row_id
        ),
        json={URL_FORM.URL_TITLE: "Not allowed"},
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )
    assert delete_response.status_code == 403
    assert edit_response.status_code == 403

    trash_utub_url(app, row_id, deleted_by=1)

    assert get_trash_url_ids(client) == []
    assert _trash_count(app, SECOND_USER_ID) == 0
