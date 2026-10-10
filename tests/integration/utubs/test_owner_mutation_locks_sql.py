"""Guard against a future writer dropping the per-UTub row lock.

Each owner/role-sensitive user endpoint (other than add-member, which lives in
``tests/integration/utubmembers/test_add_member_to_utub_route.py`` so it inherits
that directory's Redis flush) sends one valid request while a
``before_cursor_execute`` listener records the SQL; the test asserts a
``SELECT ... FROM "Utubs" ... FOR NO KEY UPDATE`` was emitted.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from flask import url_for
from sqlalchemy import event

from backend import db
from backend.members.constants import MemberRoleTarget
from backend.utils.all_routes import ROUTES
from backend.utils.strings.form_strs import UTUB_DESCRIPTION_FORM, UTUB_FORM

pytestmark = pytest.mark.utubs

UTUB_ID = 1
SECOND_USER_ID = 2
THIRD_USER_ID = 3

LOCK_CLAUSE = "FOR NO KEY UPDATE"


def lock_statements_seen_during(send_request: Callable[[], Any]) -> list[str]:
    """Run ``send_request`` and return the normalized statements that lock the
    ``Utubs`` row with ``FOR NO KEY UPDATE``."""
    statements: list[str] = []

    def record_statement(conn, cursor, statement, parameters, context, executemany):
        normalized = " ".join(statement.split())
        if 'FROM "Utubs"' in normalized and LOCK_CLAUSE in normalized:
            statements.append(normalized)

    # Listen on the session's live connection, not the Engine class: the harness
    # checks out a long-lived SAVEPOINT connection at fixture setup.
    connection = db.session.connection()
    event.listen(connection, "before_cursor_execute", record_statement)
    try:
        send_request()
    finally:
        event.remove(connection, "before_cursor_execute", record_statement)
    return statements


@pytest.mark.parametrize(
    "method, route, route_kwargs, body, expected_status",
    [
        (
            "patch",
            ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP,
            {},
            {"new_owner_id": SECOND_USER_ID},
            200,
        ),
        (
            "patch",
            ROUTES.MEMBERS.MODIFY_MEMBER_ROLE,
            {"user_id": SECOND_USER_ID},
            {"member_role": MemberRoleTarget.CO_CREATOR.value},
            200,
        ),
        (
            "delete",
            ROUTES.MEMBERS.REMOVE_MEMBER,
            {"user_id": THIRD_USER_ID},
            None,
            200,
        ),
        ("delete", ROUTES.UTUBS.DELETE_UTUB, {}, None, 200),
        (
            "patch",
            ROUTES.UTUBS.UPDATE_UTUB_NAME,
            {},
            {UTUB_FORM.UTUB_NAME: "Lock Test New Name"},
            200,
        ),
        (
            "patch",
            ROUTES.UTUBS.UPDATE_UTUB_DESC,
            {},
            {UTUB_DESCRIPTION_FORM.UTUB_DESCRIPTION_FOR_FORM: "Lock test new desc"},
            200,
        ),
    ],
    ids=[
        "transfer_ownership",
        "modify_member_role",
        "remove_member",
        "delete_utub",
        "update_utub_name",
        "update_utub_desc",
    ],
)
def test_user_endpoint_locks_utub_row_for_no_key_update(
    add_multiple_users_to_utub_without_logging_in,
    login_first_user_without_register,
    method,
    route,
    route_kwargs,
    body,
    expected_status,
):
    """
    GIVEN UTub 1 created by user 1 with members 2 and 3, and user 1 logged in
    WHEN user 1 sends one valid request to an owner/role-sensitive endpoint
    THEN a SELECT on "Utubs" with FOR NO KEY UPDATE is emitted
    """
    client, csrf_token, _, app = login_first_user_without_register

    with app.app_context():
        url = url_for(route, utub_id=UTUB_ID, **route_kwargs)
    request_kwargs: dict[str, Any] = {"headers": {"X-CSRFToken": csrf_token}}
    if body is not None:
        request_kwargs["json"] = body

    responses: list[Any] = []
    lock_statements = lock_statements_seen_during(
        lambda: responses.append(getattr(client, method)(url, **request_kwargs))
    )

    assert responses[0].status_code == expected_status
    assert lock_statements != []
