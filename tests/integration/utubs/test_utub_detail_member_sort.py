from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from sqlalchemy import event

from backend import db
from backend.models.user_preferences import MemberSort, User_Preferences
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.utils.all_routes import ROUTES
from backend.utils.strings.model_strs import MODELS
from backend.utils.strings.url_validation_strs import URL_VALIDATION
from tests.integration.utubs.test_get_utubs_summary_route import _set_user_preferences

pytestmark = pytest.mark.utubs

# User ids 1, 2, 3 are FakeUserName1234, CenturyUser1234, PersonalEntry1234 and UTub
# 3 is created by user 3, so the owner is alphabetically last.
UTUB_ID = 3
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
AJAX_HEADERS = {URL_VALIDATION.X_REQUESTED_WITH: URL_VALIDATION.XMLHTTPREQUEST}


def _set_joined_at(app: Flask, joined: dict[int, datetime | None]) -> None:
    with app.app_context():
        for user_id, value in joined.items():
            member: Utub_Members = Utub_Members.query.get((UTUB_ID, user_id))
            member.joined_at = value
        db.session.commit()


def _member_ids(response_json: dict[str, Any]) -> list[int]:
    return [member[MODELS.ID] for member in response_json[MODELS.MEMBERS]]


def _get_detail(
    client: FlaskClient, route: str = ROUTES.UTUBS.GET_SINGLE_UTUB
) -> dict[str, Any]:
    response = client.get(url_for(route, utub_id=UTUB_ID), headers=AJAX_HEADERS)
    assert response.status_code == 200
    assert response.json is not None
    return response.json


@pytest.mark.parametrize(
    "route", [ROUTES.UTUBS.GET_SINGLE_UTUB, ROUTES.UTUBS.REFRESH_SINGLE_UTUB]
)
def test_detail_members_follow_viewer_sort(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    route: str,
):
    """
    GIVEN a UTub owned by the alphabetically last user, with distinct join dates
    WHEN user 1 loads it under each of the three sorts
    THEN the owner is first, the rest follow the sort, and ``memberSort`` echoes it
    """
    client, _, _, app = login_first_user_without_register
    # Name order is 2 (Century) then 1 (Fake); user 1 joined after user 2.
    _set_joined_at(
        app,
        {1: BASE_TIME + timedelta(days=2), 2: BASE_TIME + timedelta(days=1), 3: None},
    )
    _set_user_preferences(app, 1, member_sort=MemberSort.NAME_AZ)
    first = _get_detail(client, route)
    assert first[MODELS.MEMBER_SORT] == "name_az"
    assert _member_ids(first) == [3, 2, 1]

    _set_user_preferences(app, 1, member_sort=MemberSort.RECENTLY_JOINED)
    second = _get_detail(client, route)
    assert second[MODELS.MEMBER_SORT] == "recently_joined"
    assert _member_ids(second) == [3, 1, 2]

    # Dates now match name order, so only the role can put user 1 ahead of user 2.
    _set_joined_at(
        app,
        {1: BASE_TIME + timedelta(days=1), 2: BASE_TIME + timedelta(days=2), 3: None},
    )
    _set_user_preferences(app, 1, member_sort=MemberSort.ROLE_THEN_NAME)
    with app.app_context():
        Utub_Members.query.get((UTUB_ID, 1)).member_role = Member_Role.CO_CREATOR
        db.session.commit()
    third = _get_detail(client, route)
    assert third[MODELS.MEMBER_SORT] == "role_then_name"
    assert _member_ids(third) == [3, 1, 2]


def test_detail_defaults_to_name_az_without_preferences_row(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a viewer with no preferences row
    WHEN they load the UTub
    THEN members are in Name A-Z order and ``memberSort`` is ``name_az``
    """
    client, _, _, app = login_first_user_without_register
    with app.app_context():
        assert (
            User_Preferences.query.filter(User_Preferences.user_id == 1).first() is None
        )
    detail = _get_detail(client)
    assert detail[MODELS.MEMBER_SORT] == "name_az"
    assert _member_ids(detail) == [3, 2, 1]


def test_joined_at_is_millisecond_iso_or_explicit_null(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN one member with a sub-millisecond join date and one with none
    WHEN the UTub detail is loaded
    THEN ``joinedAt`` is a millisecond ISO string, or an explicit null
    """
    client, _, _, app = login_first_user_without_register
    _set_joined_at(
        app,
        {
            1: datetime(2026, 2, 3, 4, 5, 6, 789987, tzinfo=timezone.utc),
            2: None,
            3: BASE_TIME,
        },
    )
    by_id = {
        member[MODELS.ID]: member for member in _get_detail(client)[MODELS.MEMBERS]
    }
    assert by_id[1][MODELS.JOINED_AT] == "2026-02-03T04:05:06.789+00:00"
    assert MODELS.JOINED_AT in by_id[2] and by_id[2][MODELS.JOINED_AT] is None
    assert by_id[3][MODELS.JOINED_AT] == "2026-01-01T00:00:00.000+00:00"


def test_recently_joined_orders_dateless_after_dated_with_owner_first(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a dateless owner, a dateless member who sorts first by name (user 2,
        Century) and a dated member who sorts last by name (user 1, Fake)
    WHEN the viewer sorts by recently joined
    THEN the owner is first, the dated member next, and the dateless member last
        (name order would be [3, 2, 1], so this cannot pass by name sorting)
    """
    client, _, _, app = login_first_user_without_register
    _set_joined_at(app, {1: BASE_TIME, 2: None, 3: None})
    _set_user_preferences(app, 1, member_sort=MemberSort.RECENTLY_JOINED)
    assert _member_ids(_get_detail(client)) == [3, 1, 2]


def _statements_during(send_request: Callable[[], Any]) -> list[str]:
    statements: list[str] = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        statements.append(" ".join(statement.split()))

    connection = db.session.connection()
    event.listen(connection, "before_cursor_execute", record_statement)
    try:
        send_request()
    finally:
        event.remove(connection, "before_cursor_execute", record_statement)
    return statements


@pytest.mark.parametrize("member_sort", list(MemberSort))
def test_detail_statement_count_does_not_grow_with_member_count(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    member_sort: MemberSort,
):
    """
    GIVEN a UTub with 1 member, then with 3 members
    WHEN the detail is read with the session emptied first, under each sort
    THEN the same number of SQL statements runs both times
    """
    client, _, _, app = login_first_user_without_register
    _set_user_preferences(app, 1, member_sort=member_sort)

    def send() -> Any:
        # Without this, identity-mapped rows would hide a lazy-load regression. The
        # logged-in ``Users`` row stays attached: flask-login caches it.
        db.session.expire_all()
        for instance in list(db.session.identity_map.values()):
            if not isinstance(instance, Users):
                db.session.expunge(instance)
        return client.get(
            url_for(ROUTES.UTUBS.GET_SINGLE_UTUB, utub_id=1), headers=AJAX_HEADERS
        )

    one_member = _statements_during(send)
    assert one_member, "listener recorded no statements"

    with app.app_context():
        for user_id in (2, 3):
            db.session.add(Utub_Members(utub_id=1, user_id=user_id))
        db.session.commit()

    three_members = _statements_during(send)
    assert len(three_members) == len(one_member), (one_member, three_members)
