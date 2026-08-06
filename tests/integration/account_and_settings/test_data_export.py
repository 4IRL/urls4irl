"""Integration tests for the guard-free user-data-export core.

Exercises the extractable-core serializer that walks every UTub the acting
user belongs to (created + joined) and emits a purpose-built export schema —
mirroring the guard-free-core pattern in ``test_account_removal_core.py`` so it
is unit/integration-testable without any HTTP/route/guard concern:

    backend.users.services.data_export_service.build_user_data_export_core

The rich seed (``seed_distinct_stats_for_user_one`` via the
``login_first_user_with_distinct_stats`` fixture) gives user 1 two created and
four member-of UTubs, so the role casing, membership breadth, and URL/tag/member
nesting can all be asserted against known counts.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from limits import RateLimitItemPerHour, RateLimitItemPerMinute, parse_many
from redis import Redis
from werkzeug.test import TestResponse

from backend import limiter
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.schemas.exports import UserDataExportResponseSchema
from backend.users.constants import DATA_EXPORT_RATE_LIMIT, DataExportErrorCodes
from backend.users.services.data_export_service import build_user_data_export_core
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from tests.conftest import AjaxFlaskLoginClient
from tests.integration.system.metrics_helpers import count_counter_keys
from tests.integration.utils import assert_response_conforms_to_schema

pytestmark = pytest.mark.account_and_support

_DATA_EXPORT_RATE_LIMIT_PER_MINUTE = 5
_DATA_EXPORT_RATE_LIMIT_PER_HOUR = 15


def _enable_limiter(app: Flask) -> None:
    """Re-arm flask-limiter for this test (globally disabled under TESTING).

    Mirrors the established pattern in
    tests/integration/splash/test_splash_auth_rate_limit.py.
    """
    original_first_request = app._got_first_request
    app._got_first_request = False
    app.config["RATELIMIT_ENABLED"] = True
    limiter.enabled = True
    limiter.init_app(app)
    app._got_first_request = original_first_request


def _disable_limiter() -> None:
    if limiter._storage is not None:
        limiter._storage.reset()
    limiter._storage = None
    limiter._limiter = None
    limiter.enabled = False
    limiter.initialized = False


def test_data_export_core_serializes_all_memberships(
    login_first_user_with_distinct_stats: Tuple[FlaskClient, Users, Flask],
) -> None:
    """The core returns the account block plus every UTub the user is a member
    of (created + joined), with lowercase ``Member_Role.value`` roles, nested
    URLs/tags/members, and no secret or session fields anywhere."""
    _logged_in_client, seeded_user, app = login_first_user_with_distinct_stats

    with app.app_context():
        acting_user: Users = Users.query.get(seeded_user.id)
        generated_at: datetime = utc_now()
        export = build_user_data_export_core(
            user=acting_user, generated_at=generated_at
        )

    # ---- Account block (no internal user ID — minimized) ----
    assert export.account.username == seeded_user.username
    assert export.account.email == seeded_user.email
    assert isinstance(export.account.member_since, datetime)
    assert export.exported_at == generated_at

    # ---- Membership breadth: 2 created + 4 member-of = 6 total ----
    assert len(export.utubs) == 6
    roles = [utub.role for utub in export.utubs]
    # Roles use the lowercase Member_Role.value form, not the enum-member name.
    assert roles.count("creator") == 2
    assert roles.count("member") == 3
    assert roles.count("cocreator") == 1

    # ---- The created "home" UTub carries the URLs, tag vocab, and members ----
    created_utubs = [utub for utub in export.utubs if utub.role == "creator"]
    home_export = max(created_utubs, key=lambda utub: len(utub.urls))
    assert len(home_export.urls) >= 5
    first_url = home_export.urls[0]
    assert first_url.url.startswith("https://")
    # Applied tags on a URL are a plain list of strings (subscript-accessed
    # from ``associated_tags``, which is list[dict], not model objects).
    assert all(
        isinstance(tag_string, str)
        for url in home_export.urls
        for tag_string in url.tags
    )
    tagged_urls = [url for url in home_export.urls if url.tags]
    assert tagged_urls, "expected at least one URL with applied tags"
    # Tag vocabulary present (>= the 7 user-1 tags seeded).
    assert len(home_export.tags) >= 7
    # Members present, attributed by username only (no internal user ID).
    assert any(
        member.username == seeded_user.username for member in home_export.members
    )
    # Attribution on URLs/tags is by username string, never an internal ID.
    assert all(
        isinstance(url.added_by, str) and url.added_by for url in home_export.urls
    )
    assert all(
        isinstance(tag.created_by, str) and tag.created_by for tag in home_export.tags
    )
    # The acting user added at least one of their own home-UTub URLs, so their
    # username surfaces as an attribution — proving usernames (not IDs) are used.
    assert any(url.added_by == seeded_user.username for url in home_export.urls)

    # ---- The CO_CREATOR membership surfaces as lowercase "cocreator" ----
    cocreator_utubs = [utub for utub in export.utubs if utub.role == "cocreator"]
    assert len(cocreator_utubs) == 1

    # ---- No secrets / session fields anywhere in the serialized payload ----
    serialized = json.dumps(export.model_dump(by_alias=True, mode="json"))
    assert "password" not in serialized
    assert "sessionsInvalidatedAt" not in serialized
    assert "pendingEmail" not in serialized

    # ---- No internal database IDs anywhere (data-minimization) ----
    serialized_payload = export.model_dump(by_alias=True, mode="json")
    assert "id" not in serialized_payload["account"]
    for utub_payload in serialized_payload["utubs"]:
        assert "id" not in utub_payload
        for member_payload in utub_payload["members"]:
            assert "userId" not in member_payload
        for url_payload in utub_payload["urls"]:
            assert "id" not in url_payload
            assert "addedByUserId" not in url_payload
        for tag_payload in utub_payload["tags"]:
            assert "id" not in tag_payload
            assert "createdByUserId" not in tag_payload


# --------------------------------------------------------------------------- #
# HTTP endpoint — GET /users/<id>/data-export
# --------------------------------------------------------------------------- #


def test_data_export_endpoint_returns_full_export(
    login_first_user_with_distinct_stats: Tuple[FlaskClient, Users, Flask],
) -> None:
    """A GET on the export route returns 200 with the standard envelope, the
    export nested under ``export``, populated ``utubs``, and the acting user's
    own account block.

    The X-Requested-With header is auto-injected by ``AjaxFlaskLoginClient`` for
    every request, satisfying ``@api_route(ajax_required=True)``.
    """
    logged_in_client, seeded_user, _app = login_first_user_with_distinct_stats

    response = logged_in_client.get(
        url_for(ROUTES.USERS.DATA_EXPORT, user_id=seeded_user.id)
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert_response_conforms_to_schema(
        response_json,
        UserDataExportResponseSchema,
        expected_keys={STD_JSON.STATUS, STD_JSON.MESSAGE, "export"},
    )
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    export = response_json["export"]
    # 2 created + 4 member-of = 6 total UTubs for user 1's distinct-stats seed.
    assert len(export["utubs"]) == 6
    assert export["account"]["username"] == seeded_user.username


def test_data_export_endpoint_unauthenticated_redirects(app: Flask) -> None:
    """An unauthenticated client hitting the export route is bounced by the
    ``@session_required`` gate (302 to splash), never reaching the handler."""
    app.test_client_class = AjaxFlaskLoginClient
    anonymous_client = app.test_client()
    with app.test_request_context():
        export_url = url_for(ROUTES.USERS.DATA_EXPORT, user_id=1)

    response = anonymous_client.get(export_url)

    assert response.status_code == 302


def test_data_export_endpoint_self_ownership_mismatch_returns_403(
    login_first_user_with_distinct_stats: Tuple[FlaskClient, Users, Flask],
) -> None:
    """A GET whose URL user_id is not the acting user is rejected 403 with the
    NOT_AUTHORIZED error code (mirrors the logout-everywhere self-ownership
    guard)."""
    logged_in_client, seeded_user, _app = login_first_user_with_distinct_stats

    response = logged_in_client.get(
        url_for(ROUTES.USERS.DATA_EXPORT, user_id=seeded_user.id + 999)
    )

    assert response.status_code == 403
    assert (
        response.get_json()[STD_JSON.ERROR_CODE] == DataExportErrorCodes.NOT_AUTHORIZED
    )


def test_data_export_endpoint_rate_limited_returns_html_429(
    login_first_user_with_distinct_stats: Tuple[FlaskClient, Users, Flask],
) -> None:
    """DD-12: the dedicated ``DATA_EXPORT_RATE_LIMIT`` (5/minute) trips on the
    6th GET within the window.

    The users blueprint has no ``/api/v1`` prefix, so a rate-limited web-AJAX
    request renders the HTML 429 page (never JSON), exactly like the splash
    routes. The limiter is globally disabled under TESTING, so it is re-armed
    for this test only and torn down in ``finally`` so the re-armed limiter
    never leaks into later tests.
    """
    logged_in_client, seeded_user, app = login_first_user_with_distinct_stats
    export_url = url_for(ROUTES.USERS.DATA_EXPORT, user_id=seeded_user.id)

    _enable_limiter(app)
    try:
        for _attempt_number in range(_DATA_EXPORT_RATE_LIMIT_PER_MINUTE):
            allowed_response = logged_in_client.get(export_url)
            assert allowed_response.status_code == 200

        rate_limited_response: TestResponse = logged_in_client.get(export_url)
        assert rate_limited_response.status_code == 429
        assert not rate_limited_response.is_json
        assert IDENTIFIERS.HTML_429 in rate_limited_response.get_data(as_text=True)
    finally:
        _disable_limiter()


def test_data_export_rate_limit_registers_15_per_hour_window() -> None:
    """DD-2: ``DATA_EXPORT_RATE_LIMIT`` is a dual-window limit, but the burst
    test above only exercises the 5/minute clause. Independently guard the
    15/hour clause so a typo like ``"15 per day"`` can't slip through unnoticed.

    Driving real requests to the hourly boundary is infeasible: the 5/minute
    clause trips on the 6th request, so the 16th request needed to breach the
    hourly window is unreachable within a single minute without faking time
    (which would destabilize the parallel suite). Instead, parse the constant
    with the exact public parser flask-limiter feeds it into
    (``limits.parse_many``) and assert it yields a genuine 15-per-hour window.
    This is a semantic check, not a substring match: ``"15 per day"`` parses to
    a ``RateLimitItemPerDay`` (failing the hourly assertion) and a malformed
    clause raises in ``parse_many``. The decorator's enforcement of this exact
    constant on the route is already proven by
    ``test_data_export_endpoint_rate_limited_returns_html_429`` above.
    """
    parsed_windows = list(parse_many(DATA_EXPORT_RATE_LIMIT))

    hourly_windows = [
        window for window in parsed_windows if isinstance(window, RateLimitItemPerHour)
    ]
    assert len(hourly_windows) == 1
    assert hourly_windows[0].amount == _DATA_EXPORT_RATE_LIMIT_PER_HOUR

    # The 5/minute clause the burst test exercises remains the other window,
    # confirming the constant is a two-window limit (not the hourly clause alone).
    minute_windows = [
        window
        for window in parsed_windows
        if isinstance(window, RateLimitItemPerMinute)
    ]
    assert len(minute_windows) == 1
    assert minute_windows[0].amount == _DATA_EXPORT_RATE_LIMIT_PER_MINUTE


# --------------------------------------------------------------------------- #
# DATA_EXPORTED domain metric (dedicated per-flow emit test — the
# DOMAIN_EVENTS_TESTED_ELSEWHERE exclusion in metrics_helpers.py promises this).
# --------------------------------------------------------------------------- #


def test_data_export_records_data_exported_metric(
    metrics_enabled_app: Flask,
    provide_metrics_redis: Redis | None,
    register_first_user,
) -> None:
    """A successful data export writes exactly one DATA_EXPORTED counter key to
    the metrics Redis DB."""
    if provide_metrics_redis is None:
        pytest.skip("metrics Redis is unavailable in this environment")

    app = metrics_enabled_app
    app.test_client_class = AjaxFlaskLoginClient
    with app.app_context():
        target: Users = Users.query.get(1)
        user_id = target.id

    assert count_counter_keys(provide_metrics_redis, EventName.DATA_EXPORTED) == 0

    with app.app_context():
        user_to_login: Users = Users.query.get(user_id)

    with app.test_request_context():
        export_url = url_for(ROUTES.USERS.DATA_EXPORT, user_id=user_id)

    with app.test_client(user=user_to_login) as logged_in_client:
        response = logged_in_client.get(export_url)
        assert response.status_code == 200

    assert count_counter_keys(provide_metrics_redis, EventName.DATA_EXPORTED) == 1
