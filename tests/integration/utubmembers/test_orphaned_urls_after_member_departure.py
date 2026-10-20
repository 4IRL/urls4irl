import pytest
from flask import Flask, url_for

from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.utils.all_routes import ROUTES
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.trash.trash_helpers import get_row_state, login_as_user
from tests.utils_for_test import get_utub_url_id

pytestmark = pytest.mark.members

UTUB_ID = 1
CREATOR_USER_ID = 1
PLAIN_MEMBER_USER_ID = 2
ADDER_USER_ID = 3
ADDER_URL_ID = 3


def _remove_member_via_route(app: Flask, *, actor_id: int, member_id: int) -> None:
    with login_as_user(app, actor_id) as (client, csrf_token):
        response = client.delete(
            url_for(ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=UTUB_ID, user_id=member_id),
            headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
        )
    assert response.status_code == 200


def _assert_plain_member_forbidden_while_adder_is_member(app: Flask) -> None:
    """Negative control: before the departure, user 2 may not delete user 3's URL."""
    row_id = get_utub_url_id(app, UTUB_ID, ADDER_URL_ID)
    with app.app_context():
        assert Utub_Members.query.get((UTUB_ID, PLAIN_MEMBER_USER_ID)).member_role == (
            Member_Role.MEMBER
        )
    with login_as_user(app, PLAIN_MEMBER_USER_ID) as (client, csrf_token):
        response = client.delete(
            url_for(ROUTES.URLS.DELETE_URL, utub_id=UTUB_ID, utub_url_id=row_id),
            headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
        )
    assert response.status_code == 403
    assert get_row_state(app, row_id)["deleted_at"] is None


def _assert_plain_member_can_delete_departed_adders_url(app: Flask) -> None:
    row_id = get_utub_url_id(app, UTUB_ID, ADDER_URL_ID)
    with app.app_context():
        assert Utub_Members.query.get((UTUB_ID, ADDER_USER_ID)) is None
        assert Utub_Urls.query.get(row_id).user_id == ADDER_USER_ID

    with login_as_user(app, PLAIN_MEMBER_USER_ID) as (client, csrf_token):
        response = client.delete(
            url_for(ROUTES.URLS.DELETE_URL, utub_id=UTUB_ID, utub_url_id=row_id),
            headers={URL_VALIDATION.X_CSRF_TOKEN: csrf_token},
        )

    assert response.status_code == 200
    assert get_row_state(app, row_id)["deleted_at"] is not None


def test_plain_member_deletes_url_of_member_who_left(
    add_mixed_delete_permission_urls_in_first_utub,
    app: Flask,
) -> None:
    """
    GIVEN URL 3 added by user 3, who then self-leaves UTub 1 via the members route
    WHEN plain member user 2 deletes that URL
    THEN it is 200 and the row is kept (soft-deleted) with user 3 as historical adder
    """
    _assert_plain_member_forbidden_while_adder_is_member(app)
    _remove_member_via_route(app, actor_id=ADDER_USER_ID, member_id=ADDER_USER_ID)

    _assert_plain_member_can_delete_departed_adders_url(app)


def test_plain_member_deletes_url_of_member_removed_by_manager(
    add_mixed_delete_permission_urls_in_first_utub,
    app: Flask,
) -> None:
    """
    GIVEN URL 3 added by user 3, who is then removed from UTub 1 by the creator (user 1)
    WHEN plain member user 2 deletes that URL
    THEN it is 200 and the row is kept (soft-deleted) with user 3 as historical adder
    """
    _assert_plain_member_forbidden_while_adder_is_member(app)
    _remove_member_via_route(app, actor_id=CREATOR_USER_ID, member_id=ADDER_USER_ID)

    _assert_plain_member_can_delete_departed_adders_url(app)
