"""Sort, count, payload-shape and statement-count tests for the UTub summary list.

The summary list is produced by one services helper
(``load_summary_memberships_and_counts``) behind ``/home``, ``GET /utubs`` and
``GET /api/v1/utubs``.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from sqlalchemy import event

from backend import db
from backend.models.user_preferences import User_Preferences, UtubSort
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.schemas.users import UtubSummaryListSchema
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import to_iso_milliseconds
from backend.utils.strings.json_strs import STD_JSON_RESPONSE
from backend.utils.strings.model_strs import MODELS
from backend.utubs.services.trash_predicates import (
    load_summary_memberships_and_counts,
)
from tests.integration.utubs.test_get_utubs_summary_route import (
    DEFAULT_PREFERENCES,
    ISO_MILLISECOND_UTC_REGEX,
    SUMMARY_ITEM_KEYS,
    _expected_summary_item,
    _get_summary,
    _set_user_preferences,
)
from tests.utils_for_test import (
    get_utub_url_id,
    remove_member,
    trash_utub_url,
)

pytestmark = pytest.mark.utubs

PARITY_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "utub_sort_parity.json"
)
REGEN_ENV_FLAG = "U4I_REGEN_SORT_PARITY"
REGEN_SENTINEL_PATH = PARITY_FIXTURE_PATH.with_name("REGEN_SORT_PARITY")
BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
HOME_UTUBS_DATA_REGEX = re.compile(
    r'<script id="utubs-data" type="application/json">(.*?)</script>', re.DOTALL
)


def _set_utub_rows(
    app: Flask,
    *,
    user_id: int,
    names: dict[int, str],
    created: dict[int, datetime],
    updated: dict[int, datetime],
    opened: dict[int, datetime | None],
) -> None:
    with app.app_context():
        for utub_id, name in names.items():
            utub: Utubs = Utubs.query.get(utub_id)
            utub.name = name
            utub.created_at = created[utub_id]
            utub.last_updated = updated[utub_id]
            member: Utub_Members = Utub_Members.query.get((utub_id, user_id))
            member.last_opened_at = opened[utub_id]
        db.session.commit()


def _ordered_ids(summary: dict[str, Any]) -> list[int]:
    return [item[MODELS.ID] for item in summary[MODELS.UTUBS]]


def _home_utubs_data(client: FlaskClient) -> list[dict[str, Any]]:
    response = client.get(url_for(ROUTES.UTUBS.HOME))
    assert response.status_code == 200
    match = HOME_UTUBS_DATA_REGEX.search(response.get_data(as_text=True))
    assert match is not None
    return json.loads(match.group(1))


def _seed_distinct_rows(app: Flask) -> None:
    """User 1's three UTubs: distinct names, created, updated and opened times."""
    _set_utub_rows(
        app,
        user_id=1,
        names={1: "cherry", 2: "banana", 3: "Apple"},
        created={
            1: BASE_TIME + timedelta(days=3),
            2: BASE_TIME + timedelta(days=1),
            3: BASE_TIME + timedelta(days=2),
        },
        updated={
            1: BASE_TIME + timedelta(days=25),
            2: BASE_TIME + timedelta(days=30),
            3: BASE_TIME + timedelta(days=12),
        },
        opened={
            1: BASE_TIME + timedelta(days=5),
            2: None,
            3: BASE_TIME + timedelta(days=20),
        },
    )


# Expected id order per sort for the rows seeded by ``_seed_distinct_rows``; the five
# orders are pairwise distinct so a fallback from one sort to another is caught.
EXPECTED_ORDER_BY_SORT = {
    # recency: u1=day25, u2=day30 (never opened -> updated), u3=day20
    UtubSort.RECENT_ACTIVITY: [2, 1, 3],
    # opened desc (u3 day20, u1 day5); never-opened u2 last despite the newest update
    UtubSort.LAST_OPENED: [3, 1, 2],
    UtubSort.NAME_AZ: [3, 2, 1],  # Apple, banana, cherry (case-insensitive)
    UtubSort.NEWEST_CREATED: [1, 3, 2],
    UtubSort.OLDEST_CREATED: [2, 3, 1],
}


def test_expected_orders_are_pairwise_distinct():
    """
    GIVEN the expected order per sort for the seeded rows
    WHEN compared with each other
    THEN no two sorts share an order
    """
    orders = [tuple(order) for order in EXPECTED_ORDER_BY_SORT.values()]
    assert len(set(orders)) == len(UtubSort)


@pytest.mark.parametrize("utub_sort", list(UtubSort), ids=lambda sort: sort.value)
def test_get_utubs_orders_by_saved_sort_everywhere(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    utub_sort: UtubSort,
):
    """
    GIVEN a user in three UTubs with distinct names and timestamps and a saved sort
    WHEN the summary is read from GET /utubs, GET /api/v1/utubs (same producer) and
        the /home seed
    THEN each returns the expected order for that sort, identically
    """
    client, _, _, app = login_first_user_without_register
    _seed_distinct_rows(app)
    _set_user_preferences(app, 1, utub_sort=utub_sort)
    expected = EXPECTED_ORDER_BY_SORT[utub_sort]

    summary = _get_summary(client)
    assert _ordered_ids(summary) == expected
    assert summary[MODELS.PREFERENCES][MODELS.UTUB_SORT] == utub_sort.value
    assert [item[MODELS.ID] for item in _home_utubs_data(client)] == expected


def test_get_utubs_equal_keys_break_ties_by_id(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN three UTubs with the same name modulo case and identical timestamps
    WHEN listed under every sort
    THEN ties always resolve by ascending id
    """
    client, _, _, app = login_first_user_without_register
    _set_utub_rows(
        app,
        user_id=1,
        names={1: "Same", 2: "same", 3: "SAME"},
        created={utub_id: BASE_TIME for utub_id in (1, 2, 3)},
        updated={utub_id: BASE_TIME for utub_id in (1, 2, 3)},
        opened={utub_id: BASE_TIME for utub_id in (1, 2, 3)},
    )
    for utub_sort in UtubSort:
        _set_user_preferences(app, 1, utub_sort=utub_sort)
        assert _ordered_ids(_get_summary(client)) == [1, 2, 3], utub_sort


def test_get_utubs_sub_millisecond_difference_ties_by_id(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN two UTubs whose timestamps differ only below 1 ms (the lower id is earlier)
    WHEN listed newest-first
    THEN they tie after truncation and resolve by ascending id (an untruncated sort
        would give [2, 1, 3]), and the wire strings are equal
    """
    client, _, _, app = login_first_user_without_register
    early = BASE_TIME.replace(microsecond=100)
    late = BASE_TIME.replace(microsecond=900)
    _set_utub_rows(
        app,
        user_id=1,
        names={1: "a", 2: "b", 3: "c"},
        created={1: early, 2: late, 3: BASE_TIME - timedelta(days=1)},
        updated={1: early, 2: late, 3: BASE_TIME - timedelta(days=1)},
        opened={1: None, 2: None, 3: None},
    )
    _set_user_preferences(app, 1, utub_sort=UtubSort.NEWEST_CREATED)
    summary = _get_summary(client)
    assert _ordered_ids(summary) == [1, 2, 3]
    items = {item[MODELS.ID]: item for item in summary[MODELS.UTUBS]}
    assert items[1][MODELS.CREATED_AT] == items[2][MODELS.CREATED_AT]
    assert items[1][MODELS.LAST_UPDATED] == items[2][MODELS.LAST_UPDATED]
    assert items[1][MODELS.LAST_UPDATED] == to_iso_milliseconds(BASE_TIME)


def test_get_utubs_default_preferences_keep_todays_order(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user with no preferences row
    WHEN the summary is listed
    THEN the order is recent activity and the preferences are the defaults
    """
    client, _, _, app = login_first_user_without_register
    _seed_distinct_rows(app)
    summary = _get_summary(client)
    assert _ordered_ids(summary) == EXPECTED_ORDER_BY_SORT[UtubSort.RECENT_ACTIVITY]
    assert summary[MODELS.PREFERENCES] == DEFAULT_PREFERENCES


def test_home_seed_matches_get_utubs_order(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a non-default saved sort
    WHEN read via GET /utubs and the /home seed
    THEN both order identically (GET /api/v1/utubs shares the producer and its order
        change is pinned in the mobile_api suite)
    """
    client, _, _, app = login_first_user_without_register
    _seed_distinct_rows(app)
    _set_user_preferences(app, 1, utub_sort=UtubSort.NAME_AZ)

    web_order = _ordered_ids(_get_summary(client))
    assert web_order == EXPECTED_ORDER_BY_SORT[UtubSort.NAME_AZ]
    assert [item[MODELS.ID] for item in _home_utubs_data(client)] == web_order


def test_summary_counts_exclude_trashed_urls_and_removed_members(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN three UTubs each with one URL and all three users as members
    WHEN one URL is trashed and one member removed from another UTub
    THEN trashed URLs and removed members are not counted, and a UTub with no live
        URLs reports 0
    """
    client, _, _, app = login_first_user_without_register

    def counts() -> dict[int, tuple[int, int]]:
        return {
            item[MODELS.ID]: (item[MODELS.URL_COUNT], item[MODELS.MEMBER_COUNT])
            for item in _get_summary(client)[MODELS.UTUBS]
        }

    assert counts() == {1: (1, 3), 2: (1, 3), 3: (1, 3)}

    trash_utub_url(app, get_utub_url_id(app, 1, 1), deleted_by=1)
    remove_member(app, 2, 3)

    assert counts() == {1: (0, 3), 2: (1, 2), 3: (1, 3)}


def test_summary_payload_shape_and_iso_timestamps(
    every_user_in_every_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a user in three UTubs, opened in one only, with non-default preferences
    WHEN read via GET /utubs and the /home seed
    THEN items carry exact keys, ms-precision UTC ISO timestamps, the viewer's own
        lastOpenedAt (null when never opened) and the stored preferences
    """
    client, _, _, app = login_first_user_without_register
    _seed_distinct_rows(app)
    with app.app_context():
        other_member: Utub_Members = Utub_Members.query.get((3, 2))
        other_member.last_opened_at = BASE_TIME + timedelta(days=99)
        db.session.commit()
    _set_user_preferences(
        app,
        1,
        utub_sort=UtubSort.OLDEST_CREATED,
        show_row_counts=True,
        show_list_totals=False,
    )

    summary = _get_summary(client)
    UtubSummaryListSchema.model_validate(summary)
    assert set(summary.keys()) == {
        MODELS.UTUBS,
        MODELS.TRASH_COUNT,
        MODELS.PREFERENCES,
        STD_JSON_RESPONSE.STATUS,
    }
    assert summary[MODELS.PREFERENCES] == {
        MODELS.UTUB_SORT: "oldest_created",
        MODELS.SHOW_ROW_COUNTS: True,
        MODELS.SHOW_LIST_TOTALS: False,
    }
    items = {item[MODELS.ID]: item for item in summary[MODELS.UTUBS]}
    for item in items.values():
        assert set(item.keys()) == SUMMARY_ITEM_KEYS
        for key in (MODELS.CREATED_AT, MODELS.LAST_UPDATED):
            assert ISO_MILLISECOND_UTC_REGEX.match(item[key])
    assert items[2][MODELS.LAST_OPENED_AT] is None
    assert items[3][MODELS.LAST_OPENED_AT] == to_iso_milliseconds(
        BASE_TIME + timedelta(days=20)
    )
    assert ISO_MILLISECOND_UTC_REGEX.match(items[3][MODELS.LAST_OPENED_AT])

    home_items = {item[MODELS.ID]: item for item in _home_utubs_data(client)}
    assert home_items == items


def test_summary_items_match_expected_items(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN UTubs with URLs and members
    WHEN GET /utubs is read
    THEN every item equals the independently built expected item
    """
    client, _, _, app = login_first_user_without_register
    summary = _get_summary(client)
    with app.app_context():
        for item in summary[MODELS.UTUBS]:
            member = Utub_Members.query.get((item[MODELS.ID], 1))
            assert item == _expected_summary_item(member)


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


def _fresh_request(app: Flask, send: Callable[[], Any]) -> Callable[[], Any]:
    def run() -> Any:
        # Fixtures leave rows in the identity map; without this a lazy primary-key
        # ``to_utub`` load would issue no SQL and hide the regression.
        # The logged-in ``Users`` row stays attached: flask-login caches it on the
        # test's long-lived app context, and it is not what this test measures.
        db.session.expire_all()
        for instance in list(db.session.identity_map.values()):
            if not isinstance(instance, Users):
                db.session.expunge(instance)
        return send()

    return run


@pytest.mark.parametrize("surface", ["get_utubs", "home"])
def test_summary_statement_count_does_not_grow_with_utub_count(
    every_user_makes_a_unique_utub,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    surface: str,
):
    """
    GIVEN a user in 1 UTub, then in 3 UTubs
    WHEN the summary is built (GET /utubs, /home) with the session emptied first
    THEN the same number of SQL statements runs both times
    """
    client, _, _, app = login_first_user_without_register

    def send() -> Any:
        if surface == "home":
            return client.get(url_for(ROUTES.UTUBS.HOME))
        return _get_summary(client)

    one_utub = _statements_during(_fresh_request(app, send))
    assert one_utub, "listener recorded no statements"

    with app.app_context():
        for utub in Utubs.query.filter(Utubs.id != 1).all():
            db.session.add(Utub_Members(utub_id=utub.id, user_id=1))
        db.session.commit()

    three_utubs = _statements_during(_fresh_request(app, send))
    assert len(three_utubs) == len(one_utub), (one_utub, three_utubs)


def _parse_iso(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


def test_sort_matches_shared_parity_fixture(
    register_multiple_users,
    app: Flask,
):
    """
    GIVEN the checked-in parity fixture (frontend/home/utubs/__tests__/sort.test.ts consumes it for the client)
    WHEN the services helper sorts its inputs under each of the five sorts
    THEN the produced order equals the fixture's ``expected`` order (the Python sort is
        the source of truth; ``U4I_REGEN_SORT_PARITY=1`` rewrites ``expected``)
    """
    fixture = json.loads(PARITY_FIXTURE_PATH.read_text())
    inputs = fixture["inputs"]

    with app.app_context():
        for row in inputs:
            utub = Utubs(name=row["name"], utub_creator=1, utub_description="")
            utub.id = row["id"]
            utub.created_at = _parse_iso(row["createdAt"])
            utub.last_updated = _parse_iso(row["lastUpdated"])
            membership = Utub_Members(
                utub_id=row["id"], user_id=1, member_role=Member_Role.CREATOR
            )
            membership.last_opened_at = _parse_iso(row["lastOpenedAt"])
            utub.members.append(membership)
            db.session.add(utub)
        db.session.commit()

    # The serializer emits one millisecond string for each sub-ms pair (9/10, 11/12),
    # so the client's truncated comparison ties exactly as the Python sort does.
    with app.app_context():
        rows = load_summary_memberships_and_counts(1)
        serialized = {
            item[MODELS.ID]: item
            for item in UtubSummaryListSchema.from_user(
                memberships=rows.memberships,
                counts=rows.counts,
                preferences=rows.preferences,
                trash_count=0,
            ).model_dump(by_alias=True)[MODELS.UTUBS]
        }
    for first_id, second_id in ((9, 10), (11, 12)):
        for field in (MODELS.CREATED_AT, MODELS.LAST_UPDATED, MODELS.LAST_OPENED_AT):
            assert serialized[first_id][field] == serialized[second_id][field], (
                first_id,
                field,
            )
    assert serialized[9][MODELS.CREATED_AT] == to_iso_milliseconds(
        datetime(2026, 3, 1, tzinfo=timezone.utc)
    )

    # `make` execs into the web container without forwarding the host environment, so
    # a sentinel file next to the fixture is the make-friendly way to regenerate.
    regenerate = os.environ.get(REGEN_ENV_FLAG) == "1" or REGEN_SENTINEL_PATH.exists()
    produced: dict[str, list[int]] = {}
    for utub_sort in UtubSort:
        _set_user_preferences(app, 1, utub_sort=utub_sort)
        with app.app_context():
            rows = load_summary_memberships_and_counts(1)
            produced[utub_sort.value] = [
                membership.utub_id for membership in rows.memberships
            ]
            if not regenerate:
                assert (
                    produced[utub_sort.value] == fixture["expected"][utub_sort.value]
                ), utub_sort.value

    if regenerate:
        fixture["expected"] = produced
        PARITY_FIXTURE_PATH.write_text(json.dumps(fixture, indent=2) + "\n")


def test_user_without_preferences_row_gets_defaults_from_helper(
    every_user_in_every_utub, app: Flask
):
    """
    GIVEN a user with no User_Preferences row
    WHEN the helper loads their summary rows
    THEN the preferences are the resolved defaults
    """
    with app.app_context():
        assert User_Preferences.query.filter_by(user_id=1).first() is None
        rows = load_summary_memberships_and_counts(1)
        assert rows.preferences.model_dump(by_alias=True) == DEFAULT_PREFERENCES
        assert len(rows.memberships) == 3
