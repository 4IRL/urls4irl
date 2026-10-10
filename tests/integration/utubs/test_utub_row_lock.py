from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from flask import g
from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from werkzeug.exceptions import NotFound

from backend import db
from backend.api_common.responses import FlaskResponse
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.constants import UTubErrorCodes
from backend.utubs.guards import (
    UtubAccess,
    get_fresh_membership,
    lock_and_reauthorize,
    lock_utub_for_update,
)
from tests.utils_for_test import is_string_in_logs, set_member_role

pytestmark = pytest.mark.utubs

UTUB_ID = 1
ERROR_CODE = UTubErrorCodes.UTUB_IS_LOCKED


def _raw(statement: str) -> None:
    db.session.execute(text(statement))


def _reauthorize(
    utub: Utubs, caller_id: int, access: UtubAccess
) -> FlaskResponse | None:
    with mock.patch("backend.utubs.guards.current_user", SimpleNamespace(id=caller_id)):
        return lock_and_reauthorize(utub, required_access=access, error_code=ERROR_CODE)


def test_lock_utub_for_update_refreshes_stale_creator(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a UTub already loaded into the identity map
    WHEN its creator is changed out-of-band and the UTub is locked
    THEN the same cached instance is returned with the refreshed creator
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)
        assert utub.utub_creator == 1
        _raw('UPDATE "Utubs" SET "utubCreator" = 2 WHERE id = 1')

        locked = lock_utub_for_update(utub_id=UTUB_ID)

        assert locked is utub
        assert utub.utub_creator == 2


def test_lock_utub_for_update_refreshes_member_roles(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a member row already loaded into the identity map
    WHEN its role is changed out-of-band and the UTub is locked
    THEN the cached member instance shows the refreshed role
    """
    with app.app_context():
        member: Utub_Members = Utub_Members.query.get((UTUB_ID, 2))
        assert member.member_role == Member_Role.MEMBER
        _raw(
            'UPDATE "UtubMembers" SET "memberRole" = \'CO_CREATOR\' '
            'WHERE "utubID" = 1 AND "userID" = 2'
        )

        lock_utub_for_update(utub_id=UTUB_ID)

        assert member.member_role == Member_Role.CO_CREATOR


def test_lock_utub_for_update_missing_returns_none(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a UTub id that does not exist
    WHEN the UTub is locked
    THEN None is returned
    """
    with app.app_context():
        assert lock_utub_for_update(utub_id=999) is None


def test_lock_utub_for_update_emits_for_no_key_update(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a UTub
    WHEN it is locked
    THEN a SELECT on the Utubs table with FOR NO KEY UPDATE is emitted
    """
    statements: list[str] = []

    def capture(
        conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        statements.append(statement)

    with app.app_context():
        connection = db.session.connection()
        event.listen(connection, "before_cursor_execute", capture)
        try:
            lock_utub_for_update(utub_id=UTUB_ID)
        finally:
            event.remove(connection, "before_cursor_execute", capture)

    assert any(
        'FROM "Utubs"' in statement and "FOR NO KEY UPDATE" in statement
        for statement in statements
    )


def test_get_fresh_membership_returns_none_after_out_of_band_delete(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a member row cached in the identity map
    WHEN the row is deleted out-of-band
    THEN get_fresh_membership returns None instead of the stale cached instance
    """
    with app.app_context():
        assert Utub_Members.query.get((UTUB_ID, 3)) is not None
        _raw('DELETE FROM "UtubMembers" WHERE "utubID" = 1 AND "userID" = 3')

        assert get_fresh_membership(utub_id=UTUB_ID, user_id=3) is None


def test_lock_and_reauthorize_owner_revoked_returns_403(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a stale UTub whose creator was changed out-of-band
    WHEN the former creator re-authorizes for OWNER access
    THEN a 403 NOT_AUTHORIZED response is returned
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)
        _raw('UPDATE "Utubs" SET "utubCreator" = 2 WHERE id = 1')

        with app.test_request_context():
            response, status_code = _reauthorize(utub, 1, UtubAccess.OWNER)

            assert status_code == 403
            assert response.get_json()[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED


def test_lock_and_reauthorize_manager_demoted_returns_403(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a co-creator whose cached membership was demoted out-of-band
    WHEN they re-authorize for MANAGER access
    THEN a 403 NOT_AUTHORIZED response is returned and g.is_manager is False
    """
    set_member_role(app, UTUB_ID, 2, Member_Role.CO_CREATOR)

    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)
        member: Utub_Members = Utub_Members.query.get((UTUB_ID, 2))
        assert member.member_role == Member_Role.CO_CREATOR
        _raw(
            'UPDATE "UtubMembers" SET "memberRole" = \'MEMBER\' '
            'WHERE "utubID" = 1 AND "userID" = 2'
        )

        with app.test_request_context():
            g.is_manager = True
            response, status_code = _reauthorize(utub, 2, UtubAccess.MANAGER)

            assert status_code == 403
            assert response.get_json()[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED
            assert g.is_manager is False


def test_lock_and_reauthorize_member_removed_aborts_404(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a member removed from the UTub out-of-band
    WHEN they re-authorize for MEMBER access
    THEN a 404 is raised
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)
        assert Utub_Members.query.get((UTUB_ID, 3)) is not None
        _raw('DELETE FROM "UtubMembers" WHERE "utubID" = 1 AND "userID" = 3')

        with app.test_request_context():
            with pytest.raises(NotFound):
                _reauthorize(utub, 3, UtubAccess.MEMBER)


def test_lock_and_reauthorize_trashed_utub_aborts_404(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a UTub trashed out-of-band after it was loaded as live
    WHEN the owner re-authorizes
    THEN a 404 is raised
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)
        _raw('UPDATE "Utubs" SET "deletedAt" = now() WHERE id = 1')

        with app.test_request_context():
            with pytest.raises(NotFound):
                _reauthorize(utub, 1, UtubAccess.OWNER)


def test_lock_and_reauthorize_locked_utub_authorized_caller_gets_locked_error(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN an admin-locked UTub
    WHEN an authorized caller re-authorizes
    THEN a 403 UTUB_IS_LOCKED response with the passed error code is returned
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)
        _raw('UPDATE "Utubs" SET "isLocked" = true WHERE id = 1')

        with app.test_request_context():
            response, status_code = _reauthorize(utub, 1, UtubAccess.OWNER)

            assert status_code == 403
            json_response = response.get_json()
            assert json_response[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
            assert json_response[STD_JSON.ERROR_CODE] == ERROR_CODE


def test_lock_and_reauthorize_locked_utub_unauthorized_caller_not_disclosed(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN an admin-locked UTub
    WHEN a non-owner re-authorizes for OWNER access
    THEN NOT_AUTHORIZED is returned, so the locked state is not disclosed
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)
        _raw('UPDATE "Utubs" SET "isLocked" = true WHERE id = 1')

        with app.test_request_context():
            response, status_code = _reauthorize(utub, 2, UtubAccess.OWNER)

            assert status_code == 403
            assert response.get_json()[STD_JSON.MESSAGE] == UTUB_FAILURE.NOT_AUTHORIZED


def test_lock_and_reauthorize_locked_utub_removed_member_aborts_404(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN an admin-locked UTub and a caller whose membership was deleted
    WHEN they re-authorize
    THEN a 404 is raised (membership is checked before the locked state)
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)
        _raw('UPDATE "Utubs" SET "isLocked" = true WHERE id = 1')
        _raw('DELETE FROM "UtubMembers" WHERE "utubID" = 1 AND "userID" = 3')

        with app.test_request_context():
            with pytest.raises(NotFound):
                _reauthorize(utub, 3, UtubAccess.MEMBER)


def test_lock_and_reauthorize_happy_path_returns_none(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN the UTub owner
    WHEN they re-authorize for OWNER access
    THEN None is returned and g.is_manager is True
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)

        with app.test_request_context():
            g.is_manager = False
            assert _reauthorize(utub, 1, UtubAccess.OWNER) is None
            assert g.is_manager is True


def test_lock_and_reauthorize_manager_happy_path_returns_none(
    app, add_multiple_users_to_utub_without_logging_in
):
    """
    GIVEN a co-creator of the UTub
    WHEN they re-authorize for MANAGER access
    THEN None is returned and g.is_manager is True
    """
    set_member_role(app, UTUB_ID, 2, Member_Role.CO_CREATOR)

    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)

        with app.test_request_context():
            g.is_manager = False
            assert _reauthorize(utub, 2, UtubAccess.MANAGER) is None
            assert g.is_manager is True


@pytest.mark.parametrize(
    "access,caller_id,expected_log",
    [
        (UtubAccess.OWNER, 2, "User=2 not owner: UTub.id=1"),
        (UtubAccess.MANAGER, 3, "User=3 not manager: UTub.id=1"),
    ],
)
def test_lock_and_reauthorize_logs_critical_on_not_authorized(
    app,
    add_multiple_users_to_utub_without_logging_in,
    caplog,
    access,
    caller_id,
    expected_log,
):
    """
    GIVEN a caller lacking the required role
    WHEN they re-authorize
    THEN a 403 is returned and the decorator-format critical log is emitted
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)

        with app.test_request_context():
            _, status_code = _reauthorize(utub, caller_id, access)

        assert status_code == 403
        assert is_string_in_logs(expected_log, caplog.records)


def test_lock_and_reauthorize_no_log_on_happy_path(
    app, add_multiple_users_to_utub_without_logging_in, caplog
):
    """
    GIVEN the UTub owner
    WHEN they re-authorize successfully
    THEN no not-owner / not-manager critical log is emitted
    """
    with app.app_context():
        utub: Utubs = Utubs.query.get(UTUB_ID)

        with app.test_request_context():
            assert _reauthorize(utub, 1, UtubAccess.OWNER) is None

        assert not is_string_in_logs("not owner", caplog.records)
        assert not is_string_in_logs("not manager", caplog.records)
