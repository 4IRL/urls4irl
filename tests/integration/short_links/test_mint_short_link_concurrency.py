"""Real two-connection lock-order tests for the short-link mint route.

The standard ``db_transaction`` harness runs every test on ONE connection inside a
SAVEPOINT, so a genuine lock race cannot happen there. These tests run on ``build_app``
with real commits. A second raw connection ("the earlier lock") holds the
``UtubUrls`` row lock while a real writer request and a mint request both queue on it,
then releases it. Mint's lock order is ``Utubs`` -> ``UtubUrls`` -> ``ShortLinks``, so
any writer that takes ``UtubUrls`` before ``Utubs`` closes a cycle with it and Postgres
aborts one side with ``deadlock_detected`` (a 500). Every outcome here must instead be
a 200, or a 404/403 that wrote no row.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Generator, Tuple

import pytest
from flask import Flask, url_for
from flask_session.redis import RedisSessionInterface
from redis import Redis
from sqlalchemy import text

from backend import db
from backend.models.short_links import Short_Links
from backend.models.urls import Urls
from backend.models.users import Users
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utub_urls import Utub_Urls
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.strings import model_strs
from tests.conftest import AjaxFlaskLoginClient
from tests.models_for_test import (
    valid_url_strings,
    valid_user_1,
    valid_user_2,
    valid_user_3,
)
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.short_links

OWNER_INDEX: int = 0
BLOCK_WAIT_SECONDS: float = 20.0
POLL_INTERVAL_SECONDS: float = 0.05
THREAD_JOIN_TIMEOUT_SECONDS: int = 30
POST_TERMINATE_JOIN_SECONDS: int = 5
LOCK_UTUB_URL_SQL: str = 'SELECT id FROM "UtubUrls" WHERE id = :id FOR UPDATE'
LOCK_UTUB_SQL: str = 'SELECT id FROM "Utubs" WHERE id = :id FOR UPDATE'
UNEXPECTED_ERROR_STATUS: int = 599

ThreadResult = Tuple[int, Any]


@pytest.fixture
def committed_two_url_utub(
    build_app,
) -> Generator[Tuple[Flask, int, list[int], list[int]], None, None]:
    """Commit 3 users and one UTub (owner user 1, plain members 2 and 3) holding two
    live URLs added by the owner, with real commits; TRUNCATE on teardown.

    Yields (app, utub_id, user_ids, utub_url_ids).
    """
    app, _ = build_app
    with app.app_context():
        user_ids: list[int] = []
        for credential in (valid_user_1, valid_user_2, valid_user_3):
            new_user = Users(
                username=credential[model_strs.USERNAME],
                email=credential[model_strs.EMAIL].lower(),
                plaintext_password=credential[model_strs.PASSWORD],
            )
            new_user.email_validated = True
            db.session.add(new_user)
            db.session.commit()
            user_ids.append(new_user.id)

        new_utub = Utubs(
            name="Short link race UTub", utub_creator=user_ids[0], utub_description=""
        )
        db.session.add(new_utub)
        db.session.commit()
        utub_id: int = new_utub.id

        roles = (Member_Role.CREATOR, Member_Role.MEMBER, Member_Role.MEMBER)
        for member_user_id, role in zip(user_ids, roles):
            membership = Utub_Members(member_role=role)
            membership.utub_id = utub_id
            membership.user_id = member_user_id
            db.session.add(membership)
        db.session.commit()

        utub_url_ids: list[int] = []
        for url_string in valid_url_strings[:2]:
            url = Urls(normalized_url=url_string, current_user_id=user_ids[0])
            db.session.add(url)
            db.session.commit()
            utub_url = Utub_Urls()
            utub_url.url_id = url.id
            utub_url.utub_id = utub_id
            utub_url.user_id = user_ids[0]
            utub_url.url_title = f"Race title {url.id}"
            db.session.add(utub_url)
            db.session.commit()
            utub_url_ids.append(utub_url.id)

    yield app, utub_id, user_ids, utub_url_ids

    with app.app_context():
        db.session.execute(text("SET LOCAL lock_timeout = '10s'"))
        db.session.execute(
            text(
                'TRUNCATE TABLE "Users", "Utubs", "UtubMembers", "Urls" '
                "RESTART IDENTITY CASCADE"
            )
        )
        db.session.commit()
    if isinstance(app.session_interface, RedisSessionInterface):
        client: Redis = app.session_interface.client
        client.flushdb()


def _prepare_request(
    app: Flask,
    user_id: int,
    method: str,
    url: str,
    json_body: dict[str, Any] | None = None,
) -> Callable[[], ThreadResult]:
    """Log in as ``user_id`` on a fresh client now (login and CSRF fetch included) and
    return a callable that sends only the one mutating request.

    Doing the login up front means the thread started under the held lock issues just
    the lock-taking request. A server-side exception (e.g. a propagated deadlock) is
    reported by the callable as status 599 with the exception text instead of killing
    its thread.
    """
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        user = Users.query.get(user_id)
    client = app.test_client(user=user)
    home_response = client.get("/home")
    csrf_token = get_csrf_token(home_response.get_data(), meta_tag=True)
    kwargs: dict[str, Any] = {"headers": {"X-CSRFToken": csrf_token}}
    if json_body is not None:
        kwargs["json"] = json_body

    def _send() -> ThreadResult:
        try:
            response = getattr(client, method)(url, **kwargs)
            return response.status_code, response.get_json(silent=True)
        except Exception as request_error:
            return UNEXPECTED_ERROR_STATUS, repr(request_error)

    return _send


def _blocked_backend_count(app: Flask) -> int:
    with app.app_context():
        with db.engine.connect() as connection:
            return int(
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND wait_event_type = 'Lock'"
                    )
                ).scalar_one()
            )


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


def _wait_until_blocked(
    app: Flask, thread: threading.Thread, minimum: int, label: str
) -> None:
    """Wait until ``minimum`` backends wait on a lock; fail if the thread finishes
    first (its request never queued behind the lock) or the wait times out."""
    deadline = time.monotonic() + BLOCK_WAIT_SECONDS
    while time.monotonic() < deadline:
        if not thread.is_alive():
            raise AssertionError(
                f"{label} request finished before blocking on the lock"
            )
        if _blocked_backend_count(app) >= minimum:
            return
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(f"{label} request never blocked on the lock")


def _race_writer_against_mint(
    app: Flask,
    lock_statement: str,
    locked_row_id: int,
    writer: Callable[[], ThreadResult],
    mint: Callable[[], ThreadResult],
) -> Tuple[ThreadResult, ThreadResult]:
    """Hold a row lock (``lock_statement`` on ``locked_row_id``) on a second connection,
    queue the writer then the mint behind it, release the lock and return
    (writer_result, mint_result).

    ``writer`` and ``mint`` come from ``_prepare_request`` (already logged in), so each
    thread only issues its lock-taking request. A request that finishes before it
    blocks, or never blocks, fails the test.
    """
    results: dict[str, ThreadResult] = {}

    def _run(label: str, target: Callable[[], ThreadResult]) -> None:
        results[label] = target()

    with app.app_context():
        earlier_lock_connection = db.engine.connect()
    transaction = earlier_lock_connection.begin()
    try:
        earlier_lock_connection.execute(text(lock_statement), {"id": locked_row_id})
        writer_thread = threading.Thread(
            target=_run, args=("writer", writer), daemon=True
        )
        writer_thread.start()
        _wait_until_blocked(app, writer_thread, minimum=1, label="writer")
        mint_thread = threading.Thread(target=_run, args=("mint", mint), daemon=True)
        mint_thread.start()
        _wait_until_blocked(app, mint_thread, minimum=2, label="mint")
    finally:
        transaction.commit()
        earlier_lock_connection.close()

    for thread in (writer_thread, mint_thread):
        thread.join(timeout=THREAD_JOIN_TIMEOUT_SECONDS)
    if writer_thread.is_alive() or mint_thread.is_alive():
        _terminate_stuck_backends(app)
        for thread in (writer_thread, mint_thread):
            thread.join(timeout=POST_TERMINATE_JOIN_SECONDS)
    assert not writer_thread.is_alive(), "writer thread hung"
    assert not mint_thread.is_alive(), "mint thread hung"
    return results["writer"], results["mint"]


def _short_link_codes(app: Flask, utub_url_id: int) -> list[str]:
    with app.app_context():
        return [
            row.code
            for row in db.session.query(Short_Links)
            .filter(Short_Links.utub_url_id == utub_url_id)
            .all()
        ]


def _assert_no_deadlock(*results: ThreadResult) -> None:
    """Fail when any request hit a Postgres deadlock or an unexpected server error."""
    for status, body in results:
        assert "deadlock" not in repr(body).lower(), f"deadlock detected: {body}"
        assert status != UNEXPECTED_ERROR_STATUS, f"unexpected error: {body}"
        assert status < 500, f"server error {status}: {body}"


def _assert_mint_outcome_is_safe(
    app: Flask, utub_url_id: int, mint_result: ThreadResult
) -> None:
    status, body = mint_result
    assert status in (200, 403, 404), f"mint returned {status}: {body}"
    codes = _short_link_codes(app, utub_url_id)
    if status == 200:
        assert len(codes) == 1
    else:
        assert codes == []


def _urls(app: Flask, utub_id: int, utub_url_id: int) -> dict[str, str]:
    with app.test_request_context():
        return {
            "mint": url_for(
                ROUTES.URLS.MINT_SHORT_LINK, utub_id=utub_id, utub_url_id=utub_url_id
            ),
            "update": url_for(
                ROUTES.URLS.UPDATE_URL, utub_id=utub_id, utub_url_id=utub_url_id
            ),
            "delete": url_for(
                ROUTES.URLS.DELETE_URL, utub_id=utub_id, utub_url_id=utub_url_id
            ),
            "bulk": url_for(ROUTES.URLS.DELETE_URLS_BULK, utub_id=utub_id),
            "delete_utub": url_for(ROUTES.UTUBS.DELETE_UTUB, utub_id=utub_id),
        }


def test_mint_racing_url_address_edit_never_deadlocks(
    committed_two_url_utub: Tuple[Flask, int, list[int], list[int]],
) -> None:
    """
    GIVEN a second session holding the URL row lock
    WHEN a URL address edit and a mint on the same URL queue behind it and are released
    THEN neither request is a deadlock 500; the mint is a 200 with one row
    """
    app, utub_id, user_ids, url_ids = committed_two_url_utub
    urls = _urls(app, utub_id, url_ids[0])

    writer = _prepare_request(
        app,
        user_ids[OWNER_INDEX],
        "patch",
        urls["update"],
        {"urlString": "yahoo.com"},
    )
    mint = _prepare_request(app, user_ids[OWNER_INDEX], "post", urls["mint"])

    writer_result, mint_result = _race_writer_against_mint(
        app, LOCK_UTUB_URL_SQL, url_ids[0], writer, mint
    )

    _assert_no_deadlock(writer_result, mint_result)
    assert writer_result[0] == 200, writer_result
    assert mint_result[0] == 200, mint_result
    _assert_mint_outcome_is_safe(app, url_ids[0], mint_result)


def test_mint_racing_single_url_trash_never_deadlocks(
    committed_two_url_utub: Tuple[Flask, int, list[int], list[int]],
) -> None:
    """
    GIVEN a second session holding the URL row lock
    WHEN a single URL trash and a mint on the same URL queue behind it and are released
    THEN neither request is a deadlock 500; the mint is 200 (it won) or a 404 with no row
    """
    app, utub_id, user_ids, url_ids = committed_two_url_utub
    urls = _urls(app, utub_id, url_ids[0])

    writer = _prepare_request(app, user_ids[OWNER_INDEX], "delete", urls["delete"])
    mint = _prepare_request(app, user_ids[OWNER_INDEX], "post", urls["mint"])

    writer_result, mint_result = _race_writer_against_mint(
        app, LOCK_UTUB_URL_SQL, url_ids[0], writer, mint
    )

    _assert_no_deadlock(writer_result, mint_result)
    assert writer_result[0] == 200, writer_result
    _assert_mint_outcome_is_safe(app, url_ids[0], mint_result)


def test_mint_racing_bulk_url_trash_never_deadlocks(
    committed_two_url_utub: Tuple[Flask, int, list[int], list[int]],
) -> None:
    """
    GIVEN a second session holding the URL row lock
    WHEN a bulk trash of both URLs and a mint on the first queue behind it and are released
    THEN neither request is a deadlock 500; the mint is 200 or a 404 with no row
    """
    app, utub_id, user_ids, url_ids = committed_two_url_utub
    urls = _urls(app, utub_id, url_ids[0])

    writer = _prepare_request(
        app,
        user_ids[OWNER_INDEX],
        "post",
        urls["bulk"],
        {"utubUrlIds": list(url_ids)},
    )
    mint = _prepare_request(app, user_ids[OWNER_INDEX], "post", urls["mint"])

    writer_result, mint_result = _race_writer_against_mint(
        app, LOCK_UTUB_URL_SQL, url_ids[0], writer, mint
    )

    _assert_no_deadlock(writer_result, mint_result)
    assert writer_result[0] == 200, writer_result
    _assert_mint_outcome_is_safe(app, url_ids[0], mint_result)


def test_mint_racing_utub_trash_never_deadlocks(
    committed_two_url_utub: Tuple[Flask, int, list[int], list[int]],
) -> None:
    """
    GIVEN a second session holding the UTub row lock (UTub trash only touches Utubs,
        so it would never queue behind a UtubUrls lock)
    WHEN a UTub trash and a mint on one of its URLs queue behind it and are released
    THEN neither request is a deadlock 500; the mint is 200 or a 404 with no row
    """
    app, utub_id, user_ids, url_ids = committed_two_url_utub
    urls = _urls(app, utub_id, url_ids[0])

    writer = _prepare_request(app, user_ids[OWNER_INDEX], "delete", urls["delete_utub"])
    mint = _prepare_request(app, user_ids[OWNER_INDEX], "post", urls["mint"])

    writer_result, mint_result = _race_writer_against_mint(
        app, LOCK_UTUB_SQL, utub_id, writer, mint
    )

    _assert_no_deadlock(writer_result, mint_result)
    assert writer_result[0] == 200, writer_result
    _assert_mint_outcome_is_safe(app, url_ids[0], mint_result)
