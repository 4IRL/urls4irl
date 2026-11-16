"""Link-viewed metric tests for the public ``GET /invite/<token>`` page."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from flask import Flask

from backend.invite_links.constants import INVITE_LINK_PREVIEW_MAX_URLS
from backend.metrics.events import EventName
from backend.utils.datetime_utils import utc_now
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
from tests.integration.invite_links.test_invite_preview_page import (
    _get as _get_preview_page,
)
from tests.integration.invite_links.test_invite_preview_page import (
    _get_anon,
    _preview_link,
    _remove_member,
    _seed_url,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    THIRD_USER_ID,
    anonymous_client,
    logged_in_as,
)
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


# --- Preview-viewed metric (state 3) ----------------------------------------------


def _preview_dims(redis: Any) -> list[dict[str, Any]]:
    return [
        parse_dims(key)
        for key in find_counter_keys(redis, EventName.INVITE_LINK_PREVIEW_VIEWED)
    ]


def _seed_preview_urls(app: Flask, count: int) -> None:
    base = utc_now() - timedelta(hours=1)
    for index in range(count):
        _seed_url(
            app,
            url=f"https://example.com/metric-{index}",
            title=f"Metric {index}",
            added_at=base + timedelta(minutes=index),
        )


def _assert_no_preview_key(redis: Any) -> None:
    assert count_counter_keys(redis, EventName.INVITE_LINK_PREVIEW_VIEWED) == 0


@pytest.mark.parametrize(
    ("url_count", "list_state"),
    [
        (0, "empty"),
        (1, "full"),
        (INVITE_LINK_PREVIEW_MAX_URLS, "full"),
        (INVITE_LINK_PREVIEW_MAX_URLS + 1, "truncated"),
    ],
)
def test_state_three_get_counts_one_preview_view(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
    url_count: int,
    list_state: str,
) -> None:
    """
    GIVEN a live preview-on link and a UTub with url_count URLs
    WHEN an anonymous visitor GETs the invite page
    THEN exactly one preview key with the closed dims is counted, and the
        regular view event still counts once as logged_out/valid
    """
    _seed_preview_urls(app, url_count)
    token = _preview_link(app)

    assert _get_anon(app, token).status_code == 200

    dims = _preview_dims(provide_metrics_redis)
    assert len(dims) == 1
    assert dims[0]["list_state"] == list_state
    assert set(dims[0]) == {"list_state", "device_type"}
    assert (
        sum_counter_values(provide_metrics_redis, EventName.INVITE_LINK_PREVIEW_VIEWED)
        == 1
    )
    _assert_one_view(provide_metrics_redis, "logged_out", "valid")


def test_preview_off_emits_no_preview_key(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    token = _preview_link(app, preview_enabled=False, preview_ends_at=None)
    assert _get_anon(app, token).status_code == 200
    _assert_no_preview_key(provide_metrics_redis)


def test_expired_window_emits_no_preview_key(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    token = _preview_link(app, preview_ends_at=utc_now() - timedelta(minutes=1))
    assert _get_anon(app, token).status_code == 200
    _assert_no_preview_key(provide_metrics_redis)


def test_logged_in_visitor_emits_no_preview_key(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    _remove_member(app, THIRD_USER_ID)
    token = _preview_link(app)
    with logged_in_as(app, THIRD_USER_ID) as (client, _):
        assert _get_preview_page(client, token).status_code == 200
    _assert_no_preview_key(provide_metrics_redis)


def test_dead_link_emits_no_preview_key(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    token = _preview_link(app, revoked=True)
    assert _get_anon(app, token).status_code == 404
    _assert_no_preview_key(provide_metrics_redis)


def test_forced_rate_limited_preview_get_emits_no_preview_key(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    token = _preview_link(app)
    response = _get(anonymous_client(app), token, headers={"X-Force-Rate-Limit": "1"})
    assert response.status_code == 429
    _assert_no_preview_key(provide_metrics_redis)


def test_token_and_ids_appear_in_no_preview_key(
    metrics_enabled_app,
    provide_metrics_redis,
    every_user_in_every_utub,
    app: Flask,
) -> None:
    _seed_preview_urls(app, 2)
    token = _preview_link(app)
    assert _get_anon(app, token).status_code == 200
    keys = find_counter_keys(
        provide_metrics_redis, EventName.INVITE_LINK_PREVIEW_VIEWED
    )
    assert keys
    for key in keys:
        text = key.decode() if isinstance(key, bytes) else key
        assert token not in text
        dims = parse_dims(key)
        assert set(dims) == {"list_state", "device_type"}
        assert str(FIRST_UTUB_ID) not in dims.values()
        assert str(CREATOR_ID) not in dims.values()
