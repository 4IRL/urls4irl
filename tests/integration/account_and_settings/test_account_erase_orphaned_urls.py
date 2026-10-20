"""A URL whose adder's account was erased stays actionable by every remaining member.

Erasure tombstones the Users row in place (so ``Utub_Urls.user_id`` stays a valid FK) and
drops the memberships, which makes the adder "not a member" under the orphaned-URL rule.
"""

import pytest
from flask import Flask, url_for

from backend import db
from backend.admin.account_data_service import erase_user_core, is_tombstoned
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.trash.trash_helpers import (
    AJAX_HEADERS,
    get_row_state,
    login_as_user,
)
from tests.utils_for_test import get_utub_url_id

pytestmark = pytest.mark.account_and_support

UTUB_ID = 1


def _erase(app: Flask, user_id: int) -> None:
    with app.app_context():
        erase_user_core(target_user=Users.query.get(user_id))
        db.session.commit()
        assert is_tombstoned(user=Users.query.get(user_id))
        assert Utub_Members.query.get((UTUB_ID, user_id)) is None


def _assert_plain_member_sees_and_deletes(
    app: Flask, *, member_id: int, row_id: int, adder_id: int
) -> None:
    with app.app_context():
        assert Utub_Urls.query.get(row_id).user_id == adder_id
        assert Utub_Members.query.get((UTUB_ID, member_id)).member_role == (
            Member_Role.MEMBER
        )

    with login_as_user(app, member_id) as (client, csrf_token):
        detail = client.get(
            url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=UTUB_ID),
            headers=AJAX_HEADERS,
        )
        assert detail.status_code == 200
        entry = next(
            url for url in detail.json[MODELS.URLS] if url[MODELS.UTUB_URL_ID] == row_id
        )
        assert entry[MODELS.CAN_DELETE] is True
        assert entry[MODELS.ADDED_BY] == adder_id

        response = client.delete(
            url_for(ROUTES.URLS.DELETE_URL, utub_id=UTUB_ID, utub_url_id=row_id),
            headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
        )

    assert response.status_code == 200
    assert get_row_state(app, row_id)["deleted_at"] is not None


def test_plain_member_acts_on_url_of_erased_member(
    add_mixed_delete_permission_urls_in_first_utub,
    app: Flask,
) -> None:
    """
    GIVEN URL 3 in UTub 1 added by plain member user 3, whose account is then erased
    WHEN plain member user 2 loads the UTub and deletes that URL
    THEN `canDelete` is True with `addedByUserID` = user 3's (tombstoned) id, and delete is 200
    """
    row_id = get_utub_url_id(app, UTUB_ID, 3)
    _erase(app, 3)

    _assert_plain_member_sees_and_deletes(app, member_id=2, row_id=row_id, adder_id=3)


def test_plain_member_acts_on_url_of_erased_creator_with_ownership_transfer(
    add_one_url_and_all_users_to_each_utub_no_tags,
    app: Flask,
) -> None:
    """
    GIVEN UTub 1 (creator user 1, members 2 and 3) with URL 1 added by the creator,
        whose account is then erased (ownership transfers to user 2)
    WHEN plain member user 3 loads the UTub and deletes that URL
    THEN `canDelete` is True with `addedByUserID` = user 1, and delete is 200
    """
    row_id = get_utub_url_id(app, UTUB_ID, 1)
    _erase(app, 1)

    with app.app_context():
        assert Utubs.query.get(UTUB_ID).utub_creator == 2
    _assert_plain_member_sees_and_deletes(app, member_id=3, row_id=row_id, adder_id=1)
