"""Route tests for ``PATCH /utubs/<utub_id>/invite-link`` (manager update)."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any

import pytest
from flask import Flask, url_for
from flask.wrappers import Response

from backend.invite_links.constants import (
    INVITE_LINK_MANAGE_RATE_LIMIT,
    InviteLinkErrorCodes,
    InviteLinkStatus,
)
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.invite_link_strs import INVITE_LINK_SUCCESS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.model_strs import MODELS
from tests.integration.invite_links.invite_route_helpers import (
    DEAD_STATE_IDS,
    EXPIRY_TOLERANCE,
    disable_limiter,
    enable_limiter,
    error_code_of,
    invite_url,
    link_of,
    request_as,
    rows,
    seed_dead,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    logged_in_as,
)
from tests.utils_for_test import add_invite_link

pytestmark = pytest.mark.invite_links


PER_SECOND_BATCH: int = 10


def _patch(app: Flask, body: Any) -> Response:
    return request_as(
        app,
        CREATOR_ID,
        "PATCH",
        invite_url(ROUTES.INVITE_LINKS.UPDATE_INVITE_LINK),
        body,
    )


def _expires_at(response: Response) -> datetime:
    return datetime.fromisoformat(link_of(response)[MODELS.EXPIRES_AT])


def test_update_expires_alone(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)

    response = _patch(app, {"expires_in_days": 30})

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.MESSAGE] == (
        INVITE_LINK_SUCCESS.INVITE_LINK_UPDATED
    )
    assert (
        abs(_expires_at(response) - (utc_now() + timedelta(days=30))) < EXPIRY_TOLERANCE
    )
    assert link_of(response)[MODELS.MAX_USES] == 5
    assert rows(app)[0].max_uses == 5


def test_update_max_uses_alone(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)
    before = rows(app)[0].expires_at

    response = _patch(app, {"max_uses": 10})

    assert response.status_code == 200
    assert link_of(response)[MODELS.MAX_USES] == 10
    assert rows(app)[0].expires_at == before


def test_update_both_fields(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _patch(app, {"expires_in_days": 1, "max_uses": 25})

    assert response.status_code == 200
    assert link_of(response)[MODELS.MAX_USES] == 25
    assert abs(_expires_at(response) - (utc_now() + timedelta(days=1))) < (
        EXPIRY_TOLERANCE
    )


def test_update_null_max_uses_sets_unlimited(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)

    response = _patch(app, {"max_uses": None})

    assert response.status_code == 200
    assert link_of(response)[MODELS.MAX_USES] is None
    assert rows(app)[0].max_uses is None


def test_update_absent_max_uses_is_unchanged(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)

    response = _patch(app, {"expires_in_days": 7})

    assert response.status_code == 200
    assert rows(app)[0].max_uses == 5


def test_update_shortened_expiry_is_accepted(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(
        app, FIRST_UTUB_ID, CREATOR_ID, expires_at=utc_now() + timedelta(days=30)
    )

    response = _patch(app, {"expires_in_days": 1})

    assert response.status_code == 200
    assert link_of(response)[MODELS.STATUS] == InviteLinkStatus.LIVE
    assert _expires_at(response) < utc_now() + timedelta(days=2)


def test_update_is_not_rate_limited(every_user_in_every_utub, app: Flask) -> None:
    """GIVEN the real limiter
    WHEN more PATCH calls than the manage budget are made
    THEN none is rate limited (only create/replace are)."""
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)
    attempts = int(INVITE_LINK_MANAGE_RATE_LIMIT.split(" ")[0]) + 5

    enable_limiter(app)
    try:
        with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
            url = url_for(ROUTES.INVITE_LINKS.UPDATE_INVITE_LINK, utub_id=FIRST_UTUB_ID)
            statuses: list[int] = []
            for attempt in range(attempts):
                if attempt and attempt % PER_SECOND_BATCH == 0:
                    # Stay under the app-wide 20/second default limit.
                    time.sleep(1.1)
                statuses.append(
                    client.patch(
                        url, json={"max_uses": 10}, headers={"X-CSRFToken": csrf_token}
                    ).status_code
                )
    finally:
        disable_limiter()

    assert 429 not in statuses


def test_update_sets_no_store(every_user_in_every_utub, app: Flask) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID)

    response = _patch(app, {"max_uses": 5})

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("body", [None, {}, {"expires_in_days": None}, {"max_uses": 2}])
def test_update_invalid_body_is_400_and_changes_nothing(
    every_user_in_every_utub, app: Flask, body: dict[str, Any] | None
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=5)
    before = rows(app)[0]

    response = _patch(app, body)

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.INVALID_FORM_INPUT
    after = rows(app)[0]
    assert (after.max_uses, after.expires_at) == (before.max_uses, before.expires_at)


def test_update_below_joined_is_400_and_changes_nothing(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=25, use_count=5)
    before = rows(app)[0]

    response = _patch(app, {"max_uses": 1, "expires_in_days": 30})

    assert response.status_code == 400
    assert error_code_of(response) == InviteLinkErrorCodes.USES_BELOW_JOINED
    after = rows(app)[0]
    assert (after.max_uses, after.expires_at) == (25, before.expires_at)


def test_update_equal_to_joined_is_accepted_and_used_up(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, max_uses=25, use_count=5)

    response = _patch(app, {"max_uses": 5})

    assert response.status_code == 200
    assert link_of(response)[MODELS.MAX_USES] == 5
    assert link_of(response)[MODELS.STATUS] == InviteLinkStatus.USED_UP


def test_update_without_link_is_404_with_code(
    every_user_in_every_utub, app: Flask
) -> None:
    response = _patch(app, {"max_uses": 5})

    assert response.status_code == 404
    assert error_code_of(response) == InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND


def test_update_revoked_only_is_404_with_code(
    every_user_in_every_utub, app: Flask
) -> None:
    add_invite_link(app, FIRST_UTUB_ID, CREATOR_ID, revoked=True)

    response = _patch(app, {"max_uses": 5})

    assert response.status_code == 404
    assert error_code_of(response) == InviteLinkErrorCodes.INVITE_LINK_NOT_FOUND


@pytest.mark.parametrize("state", DEAD_STATE_IDS)
def test_update_dead_row_is_409_and_changes_nothing(
    every_user_in_every_utub, app: Flask, state: str
) -> None:
    seed_dead(app, state)
    before = rows(app)[0]

    response = _patch(app, {"max_uses": 25, "expires_in_days": 30})

    assert response.status_code == 409
    assert error_code_of(response) == InviteLinkErrorCodes.DEAD_LINK_UPDATE
    after = rows(app)[0]
    assert (after.max_uses, after.expires_at, after.revoked_at) == (
        before.max_uses,
        before.expires_at,
        None,
    )


def test_update_dead_used_up_row_below_joined_is_409_not_400(
    every_user_in_every_utub, app: Flask
) -> None:
    seed_dead(app, "used_up", use_count_when_used_up=5)
    before = rows(app)[0]

    response = _patch(app, {"max_uses": 1, "expires_in_days": 30})

    assert response.status_code == 409
    assert error_code_of(response) == InviteLinkErrorCodes.DEAD_LINK_UPDATE
    after = rows(app)[0]
    assert (after.max_uses, after.expires_at, after.revoked_at) == (
        before.max_uses,
        before.expires_at,
        None,
    )
