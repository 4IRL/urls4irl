"""Eager invite link revoke on member removal, leave and demotion (web + /api/v1).

Drives the real routes: the link created by the removed, leaving or demoted user is
revoked in the same transaction, anything else leaves the link untouched.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Callable, Generator
from unittest.mock import patch

import pytest
from flask import Flask, g, url_for
from flask.wrappers import Response

from backend import db
from backend.invite_links.services.lifecycle import revoke_invite_link_created_by
from backend.invite_links.services.manage_invite_link import revoke_invite_row
from backend.invite_links.validity import InviteState
from backend.metrics.events import EventName
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role, Utub_Members
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.invite_route_helpers import (
    rows,
    state_of_current,
    unrevoked,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    THIRD_USER_ID,
    logged_in_as,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import add_invite_link, set_member_role

pytestmark = pytest.mark.members

_CO = Member_Role.CO_CREATOR


@contextmanager
def _session_as(app: Flask, user_id: int) -> Generator[tuple[Any, str], None, None]:
    """``logged_in_as`` after dropping the per-request caches that leak between
    sequential clients (the harness keeps one app context alive per test)."""
    for cached_attr in ("_login_user", "csrf_token"):
        if hasattr(g, cached_attr):
            delattr(g, cached_attr)
    with logged_in_as(app, user_id) as session:
        yield session


def _remove(app: Flask, actor_id: int, target_id: int) -> Response:
    with _session_as(app, actor_id) as (client, csrf_token):
        return client.delete(
            url_for(
                ROUTES.MEMBERS.REMOVE_MEMBER, utub_id=FIRST_UTUB_ID, user_id=target_id
            ),
            headers={"X-CSRFToken": csrf_token},
        )


def _set_role(app: Flask, target_id: int, role: str) -> Response:
    with _session_as(app, CREATOR_ID) as (client, csrf_token):
        return client.patch(
            url_for(
                ROUTES.MEMBERS.MODIFY_MEMBER_ROLE,
                utub_id=FIRST_UTUB_ID,
                user_id=target_id,
            ),
            json={"member_role": role},
            headers={"X-CSRFToken": csrf_token},
        )


def _transfer(app: Flask, actor_id: int, new_owner_id: int) -> Response:
    with _session_as(app, actor_id) as (client, csrf_token):
        return client.patch(
            url_for(ROUTES.MEMBERS.TRANSFER_UTUB_OWNERSHIP, utub_id=FIRST_UTUB_ID),
            json={"new_owner_id": new_owner_id},
            headers={"X-CSRFToken": csrf_token},
        )


def _get_link(app: Flask, user_id: int) -> Any:
    with _session_as(app, user_id) as (client, _):
        response = client.get(
            url_for(ROUTES.INVITE_LINKS.GET_INVITE_LINK, utub_id=FIRST_UTUB_ID)
        )
    assert response.status_code == 200
    return response.get_json()[MODELS.INVITE_LINK]


def _revoked_count(app: Flask) -> int:
    return len([row for row in rows(app) if row.revoked_at is not None])


def _revoke_events(redis: Any) -> list[str]:
    """Reasons of the recorded revoke events; asserts exactly one was emitted."""
    assert sum_counter_values(redis, EventName.INVITE_LINK_REVOKED) == 1
    return [
        parse_dims(key)["reason"]
        for key in find_counter_keys(redis, EventName.INVITE_LINK_REVOKED)
    ]


# --- helper -----------------------------------------------------------------


def test_helper_revokes_matching_row(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    with app.app_context():
        assert (
            revoke_invite_link_created_by(
                utub_id=FIRST_UTUB_ID, creator_id=SECOND_USER_ID
            )
            is True
        )
        db.session.rollback()


def test_helper_flushes_revoked_at_without_committing(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    with app.app_context():
        revoke_invite_link_created_by(utub_id=FIRST_UTUB_ID, creator_id=SECOND_USER_ID)
        invite = Utub_Invite_Links.query.filter_by(utub_id=FIRST_UTUB_ID).one()
        assert invite.revoked_at is not None
        db.session.rollback()

    assert len(unrevoked(app)) == 1


def test_helper_false_when_no_unrevoked_row(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID, revoked=True)

    with app.app_context():
        assert (
            revoke_invite_link_created_by(
                utub_id=FIRST_UTUB_ID, creator_id=SECOND_USER_ID
            )
            is False
        )
    assert _revoked_count(app) == 1


def test_helper_false_when_other_creator(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    with app.app_context():
        assert (
            revoke_invite_link_created_by(
                utub_id=FIRST_UTUB_ID, creator_id=SECOND_USER_ID
            )
            is False
        )
    assert len(unrevoked(app)) == 1


def test_helper_ignores_null_creator_row(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, None)

    with app.app_context():
        assert (
            revoke_invite_link_created_by(
                utub_id=FIRST_UTUB_ID, creator_id=SECOND_USER_ID
            )
            is False
        )
    assert len(unrevoked(app)) == 1


def test_helper_applies_regardless_of_creator_role(
    every_user_in_every_utub, app: Flask
) -> None:
    """A plain-member creator (already demoted) can still own an unrevoked row."""
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    with app.app_context():
        assert (
            revoke_invite_link_created_by(
                utub_id=FIRST_UTUB_ID, creator_id=SECOND_USER_ID
            )
            is True
        )
        db.session.rollback()


# --- removal and leave ------------------------------------------------------


def test_owner_removes_co_owner_who_created_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _remove(app, CREATOR_ID, SECOND_USER_ID)

    assert response.status_code == 200
    assert unrevoked(app) == []
    assert _get_link(app, CREATOR_ID) is None
    assert _revoke_events(provide_metrics_redis) == ["role_change"]
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1


def test_co_owner_leaving_revokes_their_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _remove(app, SECOND_USER_ID, SECOND_USER_ID)

    assert response.status_code == 200
    assert unrevoked(app) == []
    assert _revoke_events(provide_metrics_redis) == ["role_change"]


def test_removing_creator_with_expired_unrevoked_link_revokes_it(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        SECOND_USER_ID,
        expires_at=utc_now() - timedelta(days=1),
    )
    assert _revoked_count(app) == 0

    response = _remove(app, CREATOR_ID, SECOND_USER_ID)

    assert response.status_code == 200
    assert unrevoked(app) == []
    assert _revoked_count(app) == 1
    assert _revoke_events(provide_metrics_redis) == ["role_change"]


def test_removing_co_owner_who_did_not_create_link_leaves_it(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _remove(app, CREATOR_ID, SECOND_USER_ID)

    assert response.status_code == 200
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_plain_member_leaving_leaves_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _remove(app, THIRD_USER_ID, THIRD_USER_ID)

    assert response.status_code == 200
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_rejected_removal_leaves_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _remove(app, THIRD_USER_ID, SECOND_USER_ID)

    assert response.status_code == 403
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_locked_utub_removal_leaves_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)
    with app.app_context():
        Utubs.query.get(FIRST_UTUB_ID).is_locked = True
        db.session.commit()

    response = _remove(app, CREATOR_ID, SECOND_USER_ID)

    assert response.status_code == 403
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


# --- demotion ---------------------------------------------------------------


def test_demoting_creating_co_owner_revokes(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _set_role(app, SECOND_USER_ID, "member")

    assert response.status_code == 200
    assert unrevoked(app) == []
    assert _get_link(app, CREATOR_ID) is None
    assert _revoke_events(provide_metrics_redis) == ["role_change"]
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1


def test_demoting_a_different_co_owner_leaves_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    set_member_role(app, FIRST_UTUB_ID, THIRD_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _set_role(app, THIRD_USER_ID, "member")

    assert response.status_code == 200
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_promotion_leaves_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _set_role(app, SECOND_USER_ID, "cocreator")

    assert response.status_code == 200
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_noop_role_change_leaves_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _set_role(app, SECOND_USER_ID, "cocreator")

    assert response.status_code == 200
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_locked_utub_demotion_leaves_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)
    with app.app_context():
        Utubs.query.get(FIRST_UTUB_ID).is_locked = True
        db.session.commit()

    response = _set_role(app, SECOND_USER_ID, "member")

    assert response.status_code == 403
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_demoting_the_owner_is_rejected_and_leaves_link(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _set_role(app, CREATOR_ID, "member")

    assert response.status_code == 400
    assert len(unrevoked(app)) == 1


# --- ownership transfer -----------------------------------------------------


@pytest.mark.parametrize("target_is_co_owner", [False, True])
def test_transfer_keeps_former_owners_link_live(
    every_user_in_every_utub, app: Flask, target_is_co_owner: bool
) -> None:
    if target_is_co_owner:
        set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _transfer(app, CREATOR_ID, SECOND_USER_ID)

    assert response.status_code == 200
    assert len(unrevoked(app)) == 1
    assert state_of_current(app) is InviteState.LIVE


def test_transfer_then_new_owner_removes_former_owner_revokes(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    assert _transfer(app, CREATOR_ID, SECOND_USER_ID).status_code == 200
    assert state_of_current(app) is InviteState.LIVE

    response = _remove(app, SECOND_USER_ID, CREATOR_ID)

    assert response.status_code == 200
    assert unrevoked(app) == []
    assert _revoke_events(provide_metrics_redis) == ["role_change"]


# --- transaction atomicity --------------------------------------------------


def _fail_commit_request(app: Flask, send: Callable[[], Response]) -> Response:
    stamped_before_commit: list[bool] = []

    def revoke_and_record(invite: Utub_Invite_Links) -> None:
        revoke_invite_row(invite)
        stamped_before_commit.append(invite.revoked_at is not None)

    with (
        patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        patch.object(db.session, "commit", side_effect=RuntimeError("boom")),
        patch(
            "backend.invite_links.services.lifecycle.revoke_invite_row",
            side_effect=revoke_and_record,
        ) as revoke_spy,
        patch("backend.members.services.delete_members.record_event") as del_emit,
        patch("backend.members.services.modify_member_role.record_event") as mod_emit,
    ):
        response = send()
    revoke_spy.assert_called_once()
    assert stamped_before_commit == [True]
    for emit in (del_emit, mod_emit):
        assert all(
            call.args[0] is not EventName.INVITE_LINK_REVOKED
            for call in emit.call_args_list
        )
        emit.assert_not_called()
    with app.app_context():
        db.session.rollback()
    return response


def test_failed_commit_on_removal_rolls_back_revoke(
    every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _fail_commit_request(
        app, lambda: _remove(app, CREATOR_ID, SECOND_USER_ID)
    )

    assert response.status_code == 500
    assert len(unrevoked(app)) == 1
    with app.app_context():
        db.session.expire_all()
        assert Utub_Members.query.get((FIRST_UTUB_ID, SECOND_USER_ID)) is not None


def test_failed_commit_on_demotion_rolls_back_revoke(
    every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID)

    response = _fail_commit_request(
        app, lambda: _set_role(app, SECOND_USER_ID, "member")
    )

    assert response.status_code == 500
    assert len(unrevoked(app)) == 1
    with app.app_context():
        db.session.expire_all()
        member = Utub_Members.query.get((FIRST_UTUB_ID, SECOND_USER_ID))
        assert member.member_role == _CO
