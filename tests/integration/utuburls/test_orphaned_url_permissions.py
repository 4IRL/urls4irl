from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from backend import db
from backend.models.users import Users
from backend.models.utub_url_tags import Utub_Url_Tags
from backend.models.utub_urls import Utub_Urls
from backend.urls.constants import BulkDeleteSkipReason
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import URL_FORM
from backend.utils.strings.model_strs import MODELS as MODEL_STRS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.trash.trash_helpers import (
    get_row_state,
    get_trash_url_ids,
    post_restore,
)
from tests.utils_for_test import (
    get_utub_url_id,
    is_string_in_logs,
    remove_member,
    trash_utub_url,
)

pytestmark = pytest.mark.urls

UTUB_ID = 1
ADDER_USER_ID = 3
UTUB_URL_IDS_FIELD = "utubUrlIds"
NEW_TITLE = "Title set by a current member"
NEW_URL_STRING = "https://www.orphan-edit-target.com/"

REQUEST_KINDS = ["delete", "url", "title"]

Login = Tuple[FlaskClient, str, Users, Flask]


def _orphan_url_three(app: Flask) -> int:
    """User 3 added URL 3 (fixture); user 3 leaves UTub 1. Returns the row id."""
    row_id = get_utub_url_id(app, UTUB_ID, 3)
    remove_member(app, UTUB_ID, ADDER_USER_ID)
    return row_id


def _delete(client: FlaskClient, csrf_token: str, utub_url_id: int) -> TestResponse:
    return client.delete(
        url_for(ROUTES.URLS.DELETE_URL, utub_id=UTUB_ID, utub_url_id=utub_url_id),
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def _patch_string(
    client: FlaskClient, csrf_token: str, utub_url_id: int, url_string: str
) -> TestResponse:
    return client.patch(
        url_for(ROUTES.URLS.UPDATE_URL, utub_id=UTUB_ID, utub_url_id=utub_url_id),
        json={URL_FORM.URL_STRING: url_string},
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def _patch_title(
    client: FlaskClient, csrf_token: str, utub_url_id: int
) -> TestResponse:
    return client.patch(
        url_for(ROUTES.URLS.UPDATE_URL_TITLE, utub_id=UTUB_ID, utub_url_id=utub_url_id),
        json={URL_FORM.URL_TITLE: NEW_TITLE},
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )


def _send(
    kind: str, client: FlaskClient, csrf_token: str, utub_url_id: int
) -> TestResponse:
    if kind == "delete":
        return _delete(client, csrf_token, utub_url_id)
    if kind == "url":
        return _patch_string(client, csrf_token, utub_url_id, NEW_URL_STRING)
    if kind == "title":
        return _patch_title(client, csrf_token, utub_url_id)
    raise ValueError(f"unknown request kind: {kind}")


def test_plain_member_deletes_orphaned_url_and_restores_it_from_trash(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Login,
):
    """
    GIVEN URL 3 in UTub 1 whose adder (user 3) has left the UTub
    WHEN plain member user 2 deletes it
    THEN it is 200 and soft-deleted, user 2 sees it in their Trash list, and can restore it
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_id = _orphan_url_three(app)

    response = _delete(client, csrf_token, row_id)

    assert response.status_code == 200
    assert get_row_state(app, row_id)["deleted_at"] is not None
    assert row_id in get_trash_url_ids(client)

    restore_response = post_restore(client, csrf_token, UTUB_ID, row_id)

    assert restore_response.status_code == 200
    assert get_row_state(app, row_id)["deleted_at"] is None


def test_plain_member_edits_orphaned_url_string(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Login,
):
    """
    GIVEN URL 3 in UTub 1 whose adder (user 3) has left the UTub
    WHEN plain member user 2 edits its URL string
    THEN it is 200 and the row carries the new URL
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_id = _orphan_url_three(app)

    response = _patch_string(client, csrf_token, row_id, NEW_URL_STRING)

    assert response.status_code == 200
    with app.app_context():
        assert Utub_Urls.query.get(row_id).standalone_url.url_string == NEW_URL_STRING


def test_plain_member_edits_orphaned_url_title(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Login,
):
    """
    GIVEN URL 3 in UTub 1 whose adder (user 3) has left the UTub
    WHEN plain member user 2 edits its title
    THEN it is 200 and the row carries the new title
    """
    client, csrf_token, _, app = login_second_user_without_register
    row_id = _orphan_url_three(app)

    response = _patch_title(client, csrf_token, row_id)

    assert response.status_code == 200
    with app.app_context():
        assert Utub_Urls.query.get(row_id).url_title == NEW_TITLE


@pytest.mark.parametrize("kind", REQUEST_KINDS)
def test_plain_member_denied_on_url_whose_adder_is_a_current_member(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Login,
    caplog: pytest.LogCaptureFixture,
    kind: str,
):
    """
    GIVEN URL 3 in UTub 1 whose adder (user 3) is still a member
    WHEN plain member user 2 deletes it or edits its string or title
    THEN it is 403 with the adder-or-manager log line and the row is unchanged
    """
    client, csrf_token, user, app = login_second_user_without_register
    row_id = get_utub_url_id(app, UTUB_ID, 3)

    response = _send(kind, client, csrf_token, row_id)

    assert response.status_code == 403
    assert is_string_in_logs(
        f"User={user.id} not URL adder or UTub manager: UTubURL.id={row_id} in UTub.id={UTUB_ID}",
        caplog.records,
    )
    with app.app_context():
        row: Utub_Urls = Utub_Urls.query.get(row_id)
        assert not row.is_trashed
        assert row.url_title != NEW_TITLE


@pytest.mark.parametrize("kind", REQUEST_KINDS)
def test_non_member_denied_on_orphaned_url(
    add_mixed_delete_permission_urls_in_first_utub,
    login_third_user_without_register: Login,
    kind: str,
):
    """
    GIVEN URL 3 in UTub 1 whose adder (user 3) has left the UTub
    WHEN user 3, now a non-member, deletes it or edits its string or title
    THEN it is 404 exactly as for a non-member on any URL, and the row is unchanged
    """
    client, csrf_token, _, app = login_third_user_without_register
    row_id = _orphan_url_three(app)

    control_row_id = get_utub_url_id(app, UTUB_ID, 1)

    response = _send(kind, client, csrf_token, row_id)
    control_response = _send(kind, client, csrf_token, control_row_id)

    assert response.status_code == 404
    assert control_response.status_code == response.status_code
    with app.app_context():
        row: Utub_Urls = Utub_Urls.query.get(row_id)
        assert not row.is_trashed
        assert row.url_title != NEW_TITLE


def test_plain_member_revive_on_edit_of_orphaned_url_credits_reviver_and_keeps_tags(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Login,
):
    """
    GIVEN UTub 1 where URL 3 (live) and URL 2 (trashed, shared tag) were both added by
        user 3, who has left the UTub
    WHEN plain member user 2 edits URL 3's string to URL 2's string
    THEN it is 200, the revived row is credited to user 2 (response addedByUserID too),
        and keeps its old shared tag because its adder is orphaned
    """
    client, csrf_token, _, app = login_second_user_without_register
    edited_row_id = get_utub_url_id(app, UTUB_ID, 3)
    trashed_row_id = get_utub_url_id(app, UTUB_ID, 2)
    with app.app_context():
        trashed_row: Utub_Urls = Utub_Urls.query.get(trashed_row_id)
        trashed_row.user_id = ADDER_USER_ID
        trashed_url_string = trashed_row.standalone_url.url_string
        (shared_tag_id,) = trashed_row.associated_tag_ids
        Utub_Url_Tags.query.filter(Utub_Url_Tags.utub_url_id == edited_row_id).delete()
        db.session.commit()
    trash_utub_url(app, trashed_row_id, deleted_by=1)
    remove_member(app, UTUB_ID, ADDER_USER_ID)

    response = _patch_string(client, csrf_token, edited_row_id, trashed_url_string)

    assert response.status_code == 200
    assert response.json[MODEL_STRS.REVIVED_FROM_TRASH] is True
    assert response.json[MODEL_STRS.ADDED_BY] == 2
    with app.app_context():
        revived_row: Utub_Urls = Utub_Urls.query.get(trashed_row_id)
        assert revived_row.user_id == 2
        assert revived_row.associated_tag_ids == [shared_tag_id]


def test_bulk_delete_includes_orphaned_and_skips_current_member_adder_urls(
    add_mixed_delete_permission_urls_in_first_utub,
    login_second_user_without_register: Login,
):
    """
    GIVEN plain member user 2 with their own URL 2, orphaned URL 3 (adder left) and
        URL 1 (adder user 1, a current member)
    WHEN user 2 bulk-deletes all three
    THEN URL 2 and URL 3 are deleted and URL 1 is skipped as FORBIDDEN
    """
    client, csrf_token, _, app = login_second_user_without_register
    orphan_id = _orphan_url_three(app)
    own_id = get_utub_url_id(app, UTUB_ID, 2)
    member_adder_id = get_utub_url_id(app, UTUB_ID, 1)

    response = client.post(
        url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=UTUB_ID),
        json={UTUB_URL_IDS_FIELD: [own_id, orphan_id, member_adder_id]},
        headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
    )

    assert response.status_code == 200
    body = response.json
    assert body[MODEL_STRS.TOTAL_DELETED] == 2
    assert body[MODEL_STRS.TOTAL_SKIPPED] == 1
    assert {entry[MODEL_STRS.UTUB_URL_ID] for entry in body[MODEL_STRS.DELETED]} == {
        own_id,
        orphan_id,
    }
    assert body[MODEL_STRS.SKIPPED] == [
        {
            MODEL_STRS.UTUB_URL_ID: member_adder_id,
            MODEL_STRS.SKIP_REASON: BulkDeleteSkipReason.FORBIDDEN.value,
        }
    ]
    with app.app_context():
        assert Utub_Urls.query.get(own_id).is_trashed
        assert Utub_Urls.query.get(orphan_id).is_trashed
        assert not Utub_Urls.query.get(member_adder_id).is_trashed
