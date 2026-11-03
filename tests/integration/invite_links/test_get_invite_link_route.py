"""Route tests for ``GET /utubs/<utub_id>/invite-link`` (manager read)."""

from __future__ import annotations

import threading
from datetime import timedelta
from typing import Any, Tuple

import psycopg2.errors
import pytest
from flask import Flask, url_for
from flask.wrappers import Response

from backend import db
from backend.invite_links.constants import InviteLinkStatus
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role
from backend.schemas.invite_links import InviteLinkResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings import model_strs
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.conftest import COMMITTED_INVITE_TOKEN
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
    logged_in_as,
)
from tests.integration.system.metrics_helpers import build_pg_conn
from tests.models_for_test import valid_user_1
from tests.utils_for_test import (
    add_invite_link,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub,
)

pytestmark = pytest.mark.invite_links

GET_THREAD_TIMEOUT_SECONDS: float = 15.0
LOCK_UTUB_SQL: str = 'SELECT id FROM "Utubs" WHERE id = %s FOR UPDATE'


def _get_invite_link(client: Any, utub_id: int = FIRST_UTUB_ID) -> Response:
    return client.get(url_for(ROUTES.INVITE_LINKS.GET_INVITE_LINK, utub_id=utub_id))


def _get_as(app: Flask, user_id: int, utub_id: int = FIRST_UTUB_ID) -> Response:
    with logged_in_as(app, user_id) as (client, _):
        return _get_invite_link(client, utub_id)


def _assert_no_error_code(response: Response) -> None:
    body = response.get_json(silent=True) or {}
    assert STD_JSON.ERROR_CODE not in body


def _invite_link_of(response: Response) -> dict[str, Any] | None:
    body = response.get_json()
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert MODELS.INVITE_LINK in body
    InviteLinkResponseSchema.model_validate(body)
    return body[MODELS.INVITE_LINK]


def test_get_returns_null_when_no_link(every_user_in_every_utub, app: Flask) -> None:
    """GIVEN a UTub with no invite rows
    WHEN its owner reads the link
    THEN it is 200 with ``inviteLink`` present and null, never 404."""
    response = _get_as(app, CREATOR_ID)

    assert response.status_code == 200
    assert _invite_link_of(response) is None


def test_get_returns_null_with_only_revoked_rows(
    every_user_in_every_utub, app: Flask
) -> None:
    """GIVEN a UTub whose only invite row is revoked
    WHEN its owner reads the link
    THEN the link is null."""
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, revoked=True)

    response = _get_as(app, CREATOR_ID)

    assert response.status_code == 200
    assert _invite_link_of(response) is None


def test_get_live_link_shape(every_user_in_every_utub, app: Flask) -> None:
    """GIVEN a live limited link with two joins
    WHEN the owner reads it
    THEN every field of the link is reported, with ISO timestamps."""
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5, use_count=2)

    response = _get_as(app, CREATOR_ID)

    assert response.status_code == 200
    link = _invite_link_of(response)
    assert link is not None
    assert len(link[MODELS.TOKEN]) == 22
    assert link[MODELS.STATUS] == InviteLinkStatus.LIVE
    assert link[MODELS.MAX_USES] == 5
    assert link[MODELS.USE_COUNT] == 2
    assert link[MODELS.CREATOR_USERNAME] == valid_user_1[model_strs.USERNAME]
    assert "T" in link[MODELS.EXPIRES_AT]
    assert "T" in link[MODELS.CREATED_AT]


def test_get_unlimited_link_reports_null_max_uses(
    every_user_in_every_utub, app: Flask
) -> None:
    """GIVEN a link with no use limit
    WHEN the owner reads it
    THEN ``maxUses`` is null."""
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    link = _invite_link_of(_get_as(app, CREATOR_ID))

    assert link is not None
    assert link[MODELS.MAX_USES] is None


def test_get_expired_link(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(
        app, FIRST_UTUB_ID, CREATOR_ID, expires_at=utc_now() - timedelta(minutes=1)
    )

    link = _invite_link_of(_get_as(app, CREATOR_ID))

    assert link is not None
    assert link[MODELS.STATUS] == InviteLinkStatus.EXPIRED


def test_get_used_up_link(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=1, use_count=1)

    link = _invite_link_of(_get_as(app, CREATOR_ID))

    assert link is not None
    assert link[MODELS.STATUS] == InviteLinkStatus.USED_UP


def test_get_creator_demoted_link(every_user_in_every_utub, app: Flask) -> None:
    """GIVEN a link created by a user who is now a plain member
    WHEN the owner reads it
    THEN its status is ``creator_demoted``."""
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    link = _invite_link_of(_get_as(app, CREATOR_ID))

    assert link is not None
    assert link[MODELS.STATUS] == InviteLinkStatus.CREATOR_DEMOTED


def test_get_expired_wins_over_creator_demoted(
    every_user_in_every_utub, app: Flask
) -> None:
    """GIVEN a link that is both expired and made by a demoted creator
    WHEN the owner reads it
    THEN the first matching condition, expired, is reported."""
    add_invite_link(
        app, FIRST_UTUB_ID, SECOND_USER_ID, expires_at=utc_now() - timedelta(minutes=1)
    )

    link = _invite_link_of(_get_as(app, CREATOR_ID))

    assert link is not None
    assert link[MODELS.STATUS] == InviteLinkStatus.EXPIRED


def test_get_erased_creator_is_demoted_with_null_username(
    every_user_in_every_utub, app: Flask
) -> None:
    """GIVEN a link whose creator account was erased
    WHEN the owner reads it
    THEN ``creatorUsername`` is null and the status is ``creator_demoted``."""
    add_invite_link(app, FIRST_UTUB_ID, None)

    link = _invite_link_of(_get_as(app, CREATOR_ID))

    assert link is not None
    assert link[MODELS.CREATOR_USERNAME] is None
    assert link[MODELS.STATUS] == InviteLinkStatus.CREATOR_DEMOTED


def test_get_in_locked_utub_reports_live(every_user_in_every_utub, app: Flask) -> None:
    """GIVEN a live link in a locked UTub
    WHEN the owner reads it
    THEN the read still succeeds and the status is ``live``."""
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response = _get_as(app, CREATOR_ID)

    assert response.status_code == 200
    link = _invite_link_of(response)
    assert link is not None
    assert link[MODELS.STATUS] == InviteLinkStatus.LIVE


def test_get_co_owner_allowed(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)

    response = _get_as(app, SECOND_USER_ID)

    assert response.status_code == 200
    assert _invite_link_of(response) is not None


def test_get_plain_member_forbidden(every_user_in_every_utub, app: Flask) -> None:
    """GIVEN a plain member
    WHEN they read the link
    THEN it is 403 with no ``errorCode``."""
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _get_as(app, SECOND_USER_ID)

    assert response.status_code == 403
    _assert_no_error_code(response)
    assert MODELS.TOKEN not in response.get_data(as_text=True)


def test_get_non_member_not_found(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _get_as(app, SECOND_USER_ID)

    assert response.status_code == 404
    _assert_no_error_code(response)


def test_get_trashed_utub_not_found(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    trash_utub(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _get_as(app, CREATOR_ID)

    assert response.status_code == 404
    _assert_no_error_code(response)


def test_get_missing_utub_not_found(every_user_in_every_utub, app: Flask) -> None:
    response = _get_as(app, CREATOR_ID, utub_id=NONEXISTENT_ID)

    assert response.status_code == 404
    _assert_no_error_code(response)


def test_get_sets_no_store_cache_control(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _get_as(app, CREATOR_ID)

    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "seed_kwargs",
    [
        {"expires_at_delta": timedelta(minutes=-1)},
        {"max_uses": 1, "use_count": 1},
        {"created_by": SECOND_USER_ID},
    ],
    ids=["expired", "used_up", "creator_demoted"],
)
def test_get_does_not_modify_dead_rows(
    every_user_in_every_utub, app: Flask, seed_kwargs: dict[str, Any]
) -> None:
    """GIVEN a dead-but-unrevoked link
    WHEN the owner reads it
    THEN the row is not revoked or otherwise changed."""
    delta = seed_kwargs.get("expires_at_delta")
    invite_id = add_invite_link(
        app,
        FIRST_UTUB_ID,
        seed_kwargs.get("created_by", CREATOR_ID),
        expires_at=None if delta is None else utc_now() + delta,
        max_uses=seed_kwargs.get("max_uses"),
        use_count=seed_kwargs.get("use_count", 0),
    )

    def snapshot() -> tuple[Any, ...]:
        with app.app_context():
            db.session.expire_all()
            row = db.session.get(Utub_Invite_Links, invite_id)
            return (
                row.token,
                row.created_by,
                row.expires_at,
                row.max_uses,
                row.use_count,
                row.revoked_at,
            )

    before = snapshot()
    response = _get_as(app, CREATOR_ID)

    assert response.status_code == 200
    assert snapshot() == before
    assert before[-1] is None


def test_get_does_not_block_on_held_utub_lock(
    committed_invite_utub: Tuple[Flask, int, int, list[int]],
) -> None:
    """GIVEN another session holds the ``Utubs`` row lock
    WHEN the owner reads the link
    THEN the read returns 200 without waiting for the lock."""
    app, utub_id, _, user_ids = committed_invite_utub
    results: list[Response] = []

    errors: list[BaseException] = []

    def read_link() -> None:
        try:
            with logged_in_as(app, user_ids[0]) as (client, _):
                results.append(_get_invite_link(client, utub_id))
        except BaseException as exc:  # surfaced by the assertion below
            errors.append(exc)

    lock_conn = build_pg_conn(app)
    probe_conn = build_pg_conn(app)
    try:
        with lock_conn.cursor() as cursor:
            cursor.execute(LOCK_UTUB_SQL, (utub_id,))
        # Positive control: the lock is really held, so a NOWAIT probe must fail.
        with probe_conn.cursor() as cursor:
            with pytest.raises(psycopg2.errors.LockNotAvailable):
                cursor.execute(LOCK_UTUB_SQL + " NOWAIT", (utub_id,))
        probe_conn.rollback()
        reader = threading.Thread(target=read_link, daemon=True)
        reader.start()
        reader.join(timeout=GET_THREAD_TIMEOUT_SECONDS)
        finished_while_locked = not reader.is_alive()
    finally:
        lock_conn.rollback()
        lock_conn.close()
        probe_conn.close()

    assert not errors, errors
    assert finished_while_locked, "GET blocked on the held Utubs lock"
    assert results[0].status_code == 200
    link = _invite_link_of(results[0])
    assert link is not None
    assert link[MODELS.TOKEN] == COMMITTED_INVITE_TOKEN
