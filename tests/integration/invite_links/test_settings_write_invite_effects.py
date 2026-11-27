"""Side effects of an owner's settings write on the UTub's invite link.

Drives the real ``PATCH /utubs/<id>/settings`` route: a tightening of who can create
links revokes a now-disallowed link, turning off co-owner previews ends a preview that
is on, both in the settings write's own transaction. A relax never revives anything.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Generator
from unittest import mock

import pytest
from flask import Flask, g, url_for
from flask.wrappers import Response

from backend import db
from backend.invite_links.guards import lock_current_invite_for_update
from backend.metrics.events import EventName
from backend.models.utub_invite_links import Utub_Invite_Links
from backend.models.utub_members import Member_Role
from backend.models.utubs import Utubs
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from tests.integration.invite_links.invite_route_helpers import rows, unrevoked
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    SECOND_USER_ID,
    logged_in_as,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import (
    add_invite_link,
    lock_utub,
    set_member_role,
    set_members_settings,
)

pytestmark = pytest.mark.invite_links

CREATORS_KEY = "invite_link_creators"
PREVIEW_KEY = "co_owners_can_enable_preview"
LOCK_SPY_TARGET = (
    "backend.invite_links.services.setting_effects.lock_current_invite_for_update"
)
REVOKED_FLAG = "inviteLinkRevoked"
PREVIEW_ENDED_FLAG = "invitePreviewEnded"
_CO = Member_Role.CO_CREATOR


@contextmanager
def _owner_session(app: Flask, user_id: int = CREATOR_ID) -> Generator[Any, None, None]:
    for cached_attr in ("_login_user", "csrf_token"):
        if hasattr(g, cached_attr):
            delattr(g, cached_attr)
    with logged_in_as(app, user_id) as session:
        yield session


def _patch(app: Flask, body: Any, user_id: int = CREATOR_ID) -> Response:
    with _owner_session(app, user_id) as (client, csrf_token):
        return client.patch(
            url_for(ROUTES.UTUBS.UPDATE_UTUB_SETTINGS, utub_id=FIRST_UTUB_ID),
            json=body,
            headers={"X-CSRFToken": csrf_token},
        )


def _creators(value: str) -> dict[str, Any]:
    return {"members": {CREATORS_KEY: value}}


def _stored(app: Flask) -> Any:
    with app.app_context():
        db.session.expire_all()
        return db.session.get(Utubs, FIRST_UTUB_ID).settings


def _set_stored(app: Flask, value: Any) -> None:
    with app.app_context():
        db.session.get(Utubs, FIRST_UTUB_ID).settings = value
        db.session.commit()


def _only_row(app: Flask) -> Utub_Invite_Links:
    found = rows(app)
    assert len(found) == 1
    return found[0]


def _seed_co_owner_link(app: Flask, **kwargs: Any) -> int:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    return add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID, **kwargs)


def _live_preview() -> dict[str, Any]:
    return {"preview_enabled": True, "preview_ends_at": utc_now() + timedelta(days=2)}


def _revoke_reasons(redis: Any) -> list[str]:
    return [
        parse_dims(key)["reason"]
        for key in find_counter_keys(redis, EventName.INVITE_LINK_REVOKED)
    ]


def _assert_flags(response: Response, *, revoked: bool, ended: bool) -> None:
    assert response.status_code == 200, response.get_json()
    assert response.json[REVOKED_FLAG] is revoked
    assert response.json[PREVIEW_ENDED_FLAG] is ended


def _patch_with_lock_spy(app: Flask, body: Any) -> tuple[Response, int]:
    with mock.patch(LOCK_SPY_TARGET, wraps=lock_current_invite_for_update) as lock_spy:
        response = _patch(app, body)
    return response, lock_spy.call_count


# --- revoke on tighten -------------------------------------------------------


def test_owner_only_revokes_live_co_owner_link_and_relax_keeps_it_revoked(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)

    response = _patch(app, _creators("owner_only"))

    _assert_flags(response, revoked=True, ended=False)
    assert unrevoked(app) == []
    assert _stored(app) == {"members": {CREATORS_KEY: "owner_only"}}
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1
    assert _revoke_reasons(provide_metrics_redis) == ["setting_change"]

    relax = _patch(app, _creators("owner_and_co_owners"))

    _assert_flags(relax, revoked=False, ended=False)
    assert unrevoked(app) == []


def test_owner_only_leaves_the_owners_own_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _patch(app, _creators("owner_only"))

    _assert_flags(response, revoked=False, ended=False)
    assert len(unrevoked(app)) == 1
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_no_one_revokes_the_owners_live_link(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _patch(app, _creators("no_one"))

    _assert_flags(response, revoked=True, ended=False)
    assert unrevoked(app) == []
    assert _revoke_reasons(provide_metrics_redis) == ["setting_change"]


def test_revoke_failure_rolls_back_the_settings_write(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)

    real_commit = db.session.commit
    with (
        mock.patch.dict(app.config, {"PROPAGATE_EXCEPTIONS": False}),
        mock.patch(
            "backend.invite_links.services.setting_effects.revoke_invite_row",
            side_effect=RuntimeError("boom"),
        ),
        mock.patch.object(db.session, "commit", wraps=real_commit) as commit_spy,
    ):
        response = _patch(app, _creators("owner_only"))

    # Never committed, so the settings write is discarded with the failed request.
    assert response.status_code >= 500
    assert commit_spy.call_count == 0


def test_expired_co_owner_link_is_revoked_silently(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app, expires_at=utc_now() - timedelta(minutes=1))

    response = _patch(app, _creators("owner_only"))

    _assert_flags(response, revoked=False, ended=False)
    assert unrevoked(app) == []
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_used_up_co_owner_link_is_revoked_silently(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app, max_uses=1, use_count=1)

    response = _patch(app, _creators("owner_only"))

    _assert_flags(response, revoked=False, ended=False)
    assert unrevoked(app) == []


def test_relax_revokes_dead_row_of_demoted_creator_with_false(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.MEMBER)
    _set_stored(app, _creators("owner_only"))

    response, lock_calls = _patch_with_lock_spy(app, _creators("owner_and_co_owners"))

    _assert_flags(response, revoked=False, ended=False)
    assert lock_calls == 1
    assert unrevoked(app) == []
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


# --- preview ending ------------------------------------------------------------


@pytest.mark.parametrize("creator_id", [CREATOR_ID, SECOND_USER_ID])
def test_turning_preview_setting_off_ends_a_live_preview(
    every_user_in_every_utub, app: Flask, creator_id: int
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: True})
    add_invite_link(app, FIRST_UTUB_ID, creator_id, **_live_preview())

    response = _patch(app, {"members": {PREVIEW_KEY: False}})

    _assert_flags(response, revoked=False, ended=True)
    row = _only_row(app)
    assert row.revoked_at is None
    assert row.preview_enabled is False
    assert row.preview_ends_at is None


def test_preview_setting_off_with_no_preview_on_reports_false(
    every_user_in_every_utub, app: Flask
) -> None:
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: True})
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _patch(app, {"members": {PREVIEW_KEY: False}})

    _assert_flags(response, revoked=False, ended=False)


def test_lapsed_stored_preview_reports_false(
    every_user_in_every_utub, app: Flask
) -> None:
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: True})
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        preview_enabled=True,
        preview_ends_at=utc_now() - timedelta(minutes=5),
    )

    response = _patch(app, {"members": {PREVIEW_KEY: False}})

    _assert_flags(response, revoked=False, ended=False)


def test_dead_unrevoked_link_has_stored_preview_cleared_but_reports_false(
    every_user_in_every_utub, app: Flask
) -> None:
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: True})
    add_invite_link(
        app,
        FIRST_UTUB_ID,
        CREATOR_ID,
        expires_at=utc_now() - timedelta(minutes=1),
        **_live_preview(),
    )

    response = _patch(app, {"members": {PREVIEW_KEY: False}})

    _assert_flags(response, revoked=False, ended=False)
    row = _only_row(app)
    assert row.revoked_at is None
    assert row.preview_enabled is False
    assert row.preview_ends_at is None


def test_demoted_creator_row_is_revoked_by_preview_write_with_no_event(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: True})
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID, **_live_preview())

    response = _patch(app, {"members": {PREVIEW_KEY: False}})

    _assert_flags(response, revoked=False, ended=False)
    assert unrevoked(app) == []
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


def test_two_key_patch_revokes_row_and_reports_preview_false(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: True})
    add_invite_link(app, FIRST_UTUB_ID, SECOND_USER_ID, **_live_preview())

    response = _patch(
        app, {"members": {CREATORS_KEY: "owner_only", PREVIEW_KEY: False}}
    )

    _assert_flags(response, revoked=True, ended=False)
    assert unrevoked(app) == []
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 1


def test_two_key_patch_keeps_owners_link_and_ends_its_preview(
    every_user_in_every_utub, app: Flask
) -> None:
    """The owner may still create under owner_only, so the creators branch leaves
    the link alone and the preview-off branch still ends its live preview."""
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: True})
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, **_live_preview())

    response = _patch(
        app, {"members": {CREATORS_KEY: "owner_only", PREVIEW_KEY: False}}
    )

    _assert_flags(response, revoked=False, ended=True)
    row = _only_row(app)
    assert row.revoked_at is None
    assert row.preview_enabled is False
    assert row.preview_ends_at is None


def test_preview_setting_off_with_no_invite_row_is_clean(
    metrics_enabled_app, provide_metrics_redis, every_user_in_every_utub, app: Flask
) -> None:
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: True})

    response = _patch(app, {"members": {PREVIEW_KEY: False}})

    _assert_flags(response, revoked=False, ended=False)
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_REVOKED) == 0


# --- no-effect writes take no invite lock --------------------------------------


@pytest.mark.parametrize(
    "body",
    [_creators("owner_and_co_owners"), {"members": {PREVIEW_KEY: False}}],
    ids=["explicit-default-creators", "explicit-default-preview"],
)
def test_explicit_default_over_absent_key_takes_no_invite_lock(
    every_user_in_every_utub, app: Flask, body: Any
) -> None:
    _seed_co_owner_link(app)

    response, lock_calls = _patch_with_lock_spy(app, body)

    _assert_flags(response, revoked=False, ended=False)
    assert lock_calls == 0
    assert len(unrevoked(app)) == 1


def test_same_value_patch_takes_no_lock_and_no_commit(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)
    set_members_settings(app, FIRST_UTUB_ID, {CREATORS_KEY: "owner_and_co_owners"})

    real_commit = db.session.commit
    with mock.patch.object(db.session, "commit", wraps=real_commit) as commit_spy:
        response, lock_calls = _patch_with_lock_spy(
            app, _creators("owner_and_co_owners")
        )

    _assert_flags(response, revoked=False, ended=False)
    assert lock_calls == 0
    assert commit_spy.call_count == 0
    assert len(unrevoked(app)) == 1


def test_empty_patch_takes_no_lock(every_user_in_every_utub, app: Flask) -> None:
    _seed_co_owner_link(app)

    response, lock_calls = _patch_with_lock_spy(app, {})

    _assert_flags(response, revoked=False, ended=False)
    assert lock_calls == 0


def test_other_section_patch_takes_no_lock_and_keeps_link(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)

    response, lock_calls = _patch_with_lock_spy(
        app, {"urls": {"allow_short_links": False}}
    )

    _assert_flags(response, revoked=False, ended=False)
    assert lock_calls == 0
    assert len(unrevoked(app)) == 1


def test_effective_change_takes_the_invite_lock_once(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)

    response, lock_calls = _patch_with_lock_spy(app, _creators("owner_only"))

    _assert_flags(response, revoked=True, ended=False)
    assert lock_calls == 1


def test_corrupt_creators_then_valid_members_write_runs_the_sweep(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)
    _set_stored(app, {"members": {CREATORS_KEY: "bogus"}})

    response, lock_calls = _patch_with_lock_spy(app, {"members": {PREVIEW_KEY: True}})

    assert response.status_code == 200
    assert lock_calls == 1
    # The write cleans the corrupt section to the default, which allows the
    # co-owner, so the sweep ran (lock taken) and the live link correctly survives.
    assert response.json[REVOKED_FLAG] is False
    assert len(unrevoked(app)) == 1


@pytest.mark.parametrize("stored_value", [True, False])
def test_same_preview_value_patch_changes_nothing(
    every_user_in_every_utub, app: Flask, stored_value: bool
) -> None:
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, _CO)
    set_members_settings(app, FIRST_UTUB_ID, {PREVIEW_KEY: stored_value})
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, **_live_preview())

    real_commit = db.session.commit
    with mock.patch.object(db.session, "commit", wraps=real_commit) as commit_spy:
        response, lock_calls = _patch_with_lock_spy(
            app, {"members": {PREVIEW_KEY: stored_value}}
        )

    _assert_flags(response, revoked=False, ended=False)
    assert lock_calls == 0
    assert commit_spy.call_count == 0
    assert _only_row(app).preview_enabled is True


def test_corrupt_creators_untouched_by_other_section_write_takes_no_lock(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)
    _set_stored(app, {"members": {CREATORS_KEY: "bogus"}})

    response, lock_calls = _patch_with_lock_spy(
        app, {"urls": {"allow_short_links": False}}
    )

    assert response.status_code == 200
    assert lock_calls == 0
    assert _stored(app)["members"] == {CREATORS_KEY: "bogus"}


# --- refused writes ---------------------------------------------------------------


def test_co_owner_refused_patch_leaves_link_and_takes_no_lock(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app, **_live_preview())

    with mock.patch(LOCK_SPY_TARGET, wraps=lock_current_invite_for_update) as lock_spy:
        response = _patch(app, _creators("no_one"), user_id=SECOND_USER_ID)

    assert response.status_code == 403
    assert lock_spy.call_count == 0
    assert len(unrevoked(app)) == 1
    assert _only_row(app).preview_enabled is True


def test_locked_utub_refused_patch_leaves_link_and_takes_no_lock(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)
    lock_utub(app, FIRST_UTUB_ID)

    response, lock_calls = _patch_with_lock_spy(app, _creators("no_one"))

    assert response.status_code == 403
    assert lock_calls == 0
    assert len(unrevoked(app)) == 1


def test_invalid_value_refused_patch_leaves_link_and_takes_no_lock(
    every_user_in_every_utub, app: Flask
) -> None:
    _seed_co_owner_link(app)

    response, lock_calls = _patch_with_lock_spy(app, _creators("nobody"))

    assert response.status_code == 400
    assert lock_calls == 0
    assert len(unrevoked(app)) == 1
