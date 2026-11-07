"""Link-viewed metric tests for the public ``GET /invite/<token>`` page."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask

from backend.metrics.events import EventName
from tests.integration.invite_links.test_invite_page_route import (
    FIRST_UTUB_ID,
    UNKNOWN_TOKEN,
    VIEWER_ID,
    _add_member,
    _get,
    _live_token,
    _logged_in,
    _set_unvalidated,
    _token_of,
)
from tests.integration.short_links.short_link_helpers import anonymous_client
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    find_counter_keys,
    parse_dims,
    sum_counter_values,
)
from tests.utils_for_test import add_invite_link

pytestmark = pytest.mark.invite_links


def _view_dims(redis: Any) -> list[dict[str, Any]]:
    return [
        parse_dims(key)
        for key in find_counter_keys(redis, EventName.INVITE_LINK_VIEWED)
    ]


def _assert_one_view(redis: Any, viewer_state: str, outcome: str) -> None:
    dims = _view_dims(redis)
    assert len(dims) == 1
    assert dims[0]["viewer_state"] == viewer_state
    assert dims[0]["outcome"] == outcome
    assert set(dims[0]) == {"viewer_state", "outcome", "device_type"}
    assert sum_counter_values(redis, EventName.INVITE_LINK_VIEWED) == 1


def test_anonymous_live_link_counts_logged_out_valid(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _live_token(app)
    assert _get(anonymous_client(app), token).status_code == 200
    _assert_one_view(provide_metrics_redis, "logged_out", "valid")


def test_validated_non_member_on_live_link_counts_logged_in_valid(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        assert _get(client, token).status_code == 200
    _assert_one_view(provide_metrics_redis, "logged_in", "valid")


def test_unconfirmed_viewer_on_live_link_counts_logged_out_valid(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _live_token(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        _set_unvalidated(app)
        assert _get(client, token).status_code == 200
    _assert_one_view(provide_metrics_redis, "logged_out", "valid")


def test_member_redirect_on_live_link_counts_member_valid(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _live_token(app)
    _add_member(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        assert _get(client, token).status_code == 302
    _assert_one_view(provide_metrics_redis, "member", "valid")


def test_member_redirect_on_revoked_link_counts_member_dead(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _token_of(app, add_invite_link(app, FIRST_UTUB_ID, 1, revoked=True))
    _add_member(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        assert _get(client, token).status_code == 302
    _assert_one_view(provide_metrics_redis, "member", "dead")


def test_unconfirmed_member_on_dead_link_counts_logged_out_dead(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _token_of(app, add_invite_link(app, FIRST_UTUB_ID, 1, revoked=True))
    _add_member(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        _set_unvalidated(app)
        assert _get(client, token).status_code == 404
    _assert_one_view(provide_metrics_redis, "logged_out", "dead")


def test_unknown_token_counts_logged_out_dead(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    assert _get(anonymous_client(app), UNKNOWN_TOKEN).status_code == 404
    _assert_one_view(provide_metrics_redis, "logged_out", "dead")


def test_each_get_counts_exactly_once(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _live_token(app)
    client = anonymous_client(app)
    assert _get(client, token).status_code == 200
    assert _get(client, token).status_code == 200
    assert sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_VIEWED) == 2


def test_forced_rate_limited_get_emits_no_view_event(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _live_token(app)
    response = _get(anonymous_client(app), token, headers={"X-Force-Rate-Limit": "1"})
    assert response.status_code == 429
    assert count_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_VIEWED) == 0


def test_token_and_utub_id_appear_in_no_counter_key(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_makes_a_unique_utub,
    app: Flask,
) -> None:
    token = _live_token(app)
    _add_member(app)
    with _logged_in(app, VIEWER_ID) as (client, _):
        assert _get(client, token).status_code == 302
    keys = find_counter_keys(provide_metrics_redis, EventName.INVITE_LINK_VIEWED)
    assert keys
    for key in keys:
        text = key.decode() if isinstance(key, bytes) else key
        assert token not in text
        dims = parse_dims(key)
        assert set(dims) == {"viewer_state", "outcome", "device_type"}
        assert str(FIRST_UTUB_ID) not in dims.values()
        assert str(VIEWER_ID) not in dims.values()
