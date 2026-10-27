"""Real two-session race test for the custom metric flow cap.

The standard ``db_transaction`` harness runs every test on ONE connection inside a
SAVEPOINT, so a genuine race cannot happen there. This test runs on ``build_app``
with real commits. With 19 saved flows, a second raw connection holds the
transaction-scoped advisory lock the create route takes before counting; two admin
create requests queue behind it, the lock is released, and exactly one of them may
land the 20th flow. A row lock cannot serialize this (both creators would lock the
same 19 rows and both insert), which is why the route uses an advisory lock.
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Callable, Generator, Tuple

import pytest
from flask import Flask
from flask_session.redis import RedisSessionInterface
from redis import Redis
from sqlalchemy import text

from backend import db
from backend.admin.constants import METRIC_FLOW_CAP_LOCK_KEY, AdminActionErrorCodes
from backend.metrics.flow_limits import FLOW_LIMITS
from backend.metrics.flow_validation import serialize_flow_steps
from backend.metrics.flows import FLOWS, FlowId
from backend.models.audit_log import AuditLog
from backend.models.metric_flows import Metric_Flows
from backend.models.users import User_Role, Users
from backend.utils.strings import model_strs
from backend.utils.strings.admin_portal_strs import (
    ADMIN_ACTION_STRINGS,
    ADMIN_AUDIT_ACTIONS,
)
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from tests.conftest import AjaxFlaskLoginClient
from tests.models_for_test import valid_user_1, valid_user_2
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.admin

_FLOWS_URL: str = "/admin/metrics/flows"
BLOCK_WAIT_SECONDS: float = 20.0
POLL_INTERVAL_SECONDS: float = 0.05
THREAD_JOIN_TIMEOUT_SECONDS: int = 30
POST_TERMINATE_JOIN_SECONDS: int = 5
UNEXPECTED_ERROR_STATUS: int = 599
ADVISORY_WAIT_SQL: str = (
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE datname = current_database() "
    "AND wait_event_type = 'Lock' AND wait_event = 'advisory'"
)

ThreadResult = Tuple[int, Any]


@pytest.fixture
def committed_admins_with_19_flows(
    build_app,
) -> Generator[Tuple[Flask, list[int]], None, None]:
    """Commit two admin users and 19 saved flows with real commits; TRUNCATE on
    teardown. Yields (app, admin_user_ids)."""
    app, _ = build_app
    steps = serialize_flow_steps(FLOWS[FlowId.ADD_URL_TO_UTUB])["steps"]
    with app.app_context():
        admin_ids: list[int] = []
        for credential in (valid_user_1, valid_user_2):
            new_user = Users(
                username=credential[model_strs.USERNAME],
                email=credential[model_strs.EMAIL].lower(),
                plaintext_password=credential[model_strs.PASSWORD],
            )
            new_user.email_validated = True
            new_user.role = User_Role.ADMIN
            db.session.add(new_user)
            db.session.commit()
            admin_ids.append(new_user.id)
        for index in range(FLOW_LIMITS.MAX_CUSTOM - 1):
            db.session.add(
                Metric_Flows(
                    display_name=f"Seeded flow {index}",
                    definition={"steps": copy.deepcopy(steps)},
                    created_by=admin_ids[0],
                    updated_by=admin_ids[0],
                )
            )
        db.session.commit()

    yield app, admin_ids

    with app.app_context():
        db.session.execute(text("SET LOCAL lock_timeout = '10s'"))
        db.session.execute(
            text(
                'TRUNCATE TABLE "Users", "MetricFlows", "AuditLogs" '
                "RESTART IDENTITY CASCADE"
            )
        )
        db.session.commit()
    if isinstance(app.session_interface, RedisSessionInterface):
        client: Redis = app.session_interface.client
        client.flushdb()


def _prepare_create(
    app: Flask, user_id: int, display_name: str
) -> Callable[[], ThreadResult]:
    """Log in as ``user_id`` now and return a callable that sends only the create POST.

    A server-side exception is reported as status 599 with its text instead of
    killing the thread.
    """
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user = Users.query.get(user_id)
    client = app.test_client(user=user)
    csrf_token = get_csrf_token(client.get("/home").get_data(), meta_tag=True)
    body = {
        "display_name": display_name,
        "steps": copy.deepcopy(
            serialize_flow_steps(FLOWS[FlowId.ADD_URL_TO_UTUB])["steps"]
        ),
    }

    def _send() -> ThreadResult:
        try:
            response = client.post(
                _FLOWS_URL, json=body, headers={"X-CSRFToken": csrf_token}
            )
            return response.status_code, response.get_json(silent=True)
        except Exception as request_error:
            return UNEXPECTED_ERROR_STATUS, repr(request_error)

    return _send


def _advisory_waiters(app: Flask) -> int:
    with app.app_context():
        with db.engine.connect() as connection:
            return int(connection.execute(text(ADVISORY_WAIT_SQL)).scalar_one())


def _terminate_stuck_backends(app: Flask) -> None:
    """Terminate this database's lock-waiting or idle-in-transaction backends so a hung
    thread cannot keep locks that would make the teardown TRUNCATE time out."""
    with app.app_context():
        with db.engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "AND (wait_event_type = 'Lock' "
                    "OR state = 'idle in transaction')"
                )
            )


def _wait_until_blocked(app: Flask, threads: list[threading.Thread]) -> None:
    """Wait until every thread waits on the advisory lock; fail if one finishes first
    (its request never queued behind the lock) or the wait times out."""
    deadline = time.monotonic() + BLOCK_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not all(thread.is_alive() for thread in threads):
            raise AssertionError(
                "a create request finished before blocking on the lock"
            )
        if _advisory_waiters(app) >= len(threads):
            return
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError("create requests never blocked on the advisory lock")


def test_concurrent_creates_at_19_flows_yield_one_201_and_one_400(
    committed_admins_with_19_flows: Tuple[Flask, list[int]],
) -> None:
    """
    GIVEN 19 saved flows and a second session holding the cap advisory lock
    WHEN two admins' create requests queue behind it and the lock is released
    THEN exactly one is 201 and the other is the cap 400; the table holds 20 rows,
         one create audit row exists and nothing deadlocks or 5xxs
    """
    app, admin_ids = committed_admins_with_19_flows
    sends = [
        _prepare_create(app, admin_ids[0], "Racing flow A"),
        _prepare_create(app, admin_ids[1], "Racing flow B"),
    ]
    results: dict[int, ThreadResult] = {}

    def _run(index: int) -> None:
        results[index] = sends[index]()

    threads = [
        threading.Thread(target=_run, args=(index,), daemon=True)
        for index in range(len(sends))
    ]
    with app.app_context():
        holder_connection = db.engine.connect()
    holder_transaction = holder_connection.begin()
    try:
        holder_connection.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": METRIC_FLOW_CAP_LOCK_KEY},
        )
        for thread in threads:
            thread.start()
        _wait_until_blocked(app, threads)
    finally:
        holder_transaction.commit()
        holder_connection.close()

    for thread in threads:
        thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)
    if any(thread.is_alive() for thread in threads):
        _terminate_stuck_backends(app)
        for thread in threads:
            thread.join(timeout=POST_TERMINATE_JOIN_SECONDS)
    assert not any(thread.is_alive() for thread in threads), "a create thread hung"

    outcomes = [results[index] for index in range(len(sends))]
    for status, body in outcomes:
        assert "deadlock" not in repr(body).lower(), f"deadlock detected: {body}"
        assert status != UNEXPECTED_ERROR_STATUS, f"unexpected error: {body}"
        assert status < 500, f"server error {status}: {body}"
    statuses = sorted(status for status, _ in outcomes)
    assert statuses == [201, 400], outcomes
    rejected_body = next(body for status, body in outcomes if status == 400)
    assert rejected_body[STD_JSON.ERROR_CODE] == (
        AdminActionErrorCodes.METRIC_FLOW_LIMIT_REACHED
    )
    assert rejected_body[STD_JSON.ERRORS] == {
        "__root__": [ADMIN_ACTION_STRINGS.METRIC_FLOW_LIMIT_REACHED]
    }
    with app.app_context():
        assert Metric_Flows.query.count() == FLOW_LIMITS.MAX_CUSTOM
        audit_actions = [row.action for row in AuditLog.query.all()]
    assert audit_actions == [ADMIN_AUDIT_ACTIONS.METRIC_FLOW_CREATE]
