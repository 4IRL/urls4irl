"""Route tests for ``DELETE /utubs/<utub_id>/urls/<utub_url_id>/short-link`` (revoke)."""

from __future__ import annotations

from datetime import timedelta
from typing import Tuple

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient

from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.schemas.short_links import ShortLinkRevokedResponseSchema
from backend.short_links.constants import ShortLinkErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.short_link_strs import (
    SHORT_LINK_FAILURE,
    SHORT_LINK_SUCCESS,
)
from tests.integration.short_links.short_link_helpers import (
    CREATOR_ID,
    FIRST_UTUB_ID,
    FIRST_UTUB_URL_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
    THIRD_USER_ID,
    delete_revoke,
    logged_in_as,
    set_url_adder,
    short_link_rows,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
)
from tests.utils_for_test import (
    add_short_link,
    is_string_in_logs,
    lock_utub,
    remove_member,
    set_member_role,
)

pytestmark = pytest.mark.short_links

UTUB_URL_ID_KEY: str = "utubUrlID"


def _assert_revoked(response, app: Flask) -> None:
    assert response.status_code == 200
    body = response.json
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[STD_JSON.MESSAGE] == SHORT_LINK_SUCCESS.SHORT_LINK_REVOKED
    assert body[UTUB_URL_ID_KEY] == FIRST_UTUB_URL_ID
    ShortLinkRevokedResponseSchema.model_validate(body)
    assert short_link_rows(app, FIRST_UTUB_URL_ID) == []


def test_owner_can_revoke_link_minted_by_someone_else(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN a link minted by a plain member on a URL the owner also added
    WHEN the UTub owner revokes it
    THEN 200 and the row is deleted
    """
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=THIRD_USER_ID)

    with logged_in_as(app, CREATOR_ID) as (client, csrf_token):
        response = delete_revoke(client, csrf_token)

    _assert_revoked(response, app)


def test_co_owner_can_revoke(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN a link minted by the owner and a co-owner who neither added nor minted
    WHEN the co-owner revokes it
    THEN 200 and the row is deleted
    """
    set_member_role(app, FIRST_UTUB_ID, SECOND_USER_ID, Member_Role.CO_CREATOR)
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=CREATOR_ID)

    with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
        response = delete_revoke(client, csrf_token)

    _assert_revoked(response, app)


def test_url_adder_who_did_not_mint_can_revoke(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN a plain member who added the URL and a link minted by someone else
    WHEN the adder revokes it
    THEN 200 and the row is deleted
    """
    set_url_adder(app, FIRST_UTUB_URL_ID, SECOND_USER_ID)
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=THIRD_USER_ID)

    with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
        response = delete_revoke(client, csrf_token)

    _assert_revoked(response, app)


def test_plain_member_who_minted_can_revoke(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN a plain member who minted the link but did not add the URL
    WHEN they revoke it
    THEN 200 and the row is deleted
    """
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=THIRD_USER_ID)

    with logged_in_as(app, THIRD_USER_ID) as (client, csrf_token):
        response = delete_revoke(client, csrf_token)

    _assert_revoked(response, app)


def test_plain_member_who_neither_minted_nor_added_gets_403_and_log(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask, caplog
) -> None:
    """
    GIVEN a link minted by one plain member on a URL added by the owner
    WHEN a different plain member revokes it
    THEN 403 with the exact failure body, a critical log line, and the row remains
    """
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=SECOND_USER_ID)

    with logged_in_as(app, THIRD_USER_ID) as (client, csrf_token):
        response = delete_revoke(client, csrf_token)

    assert response.status_code == 403
    assert response.json == {
        STD_JSON.STATUS: STD_JSON.FAILURE,
        STD_JSON.MESSAGE: SHORT_LINK_FAILURE.UNABLE_TO_REVOKE,
    }
    assert is_string_in_logs(
        f"User={THIRD_USER_ID} not allowed to revoke short link: "
        f"UTubURL.id={FIRST_UTUB_URL_ID} in UTub.id={FIRST_UTUB_ID}",
        caplog.records,
    )
    assert len(short_link_rows(app, FIRST_UTUB_URL_ID)) == 1


def test_orphaned_url_lets_any_member_revoke(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN the URL's adder has left the UTub and the link was minted by another member
    WHEN a plain member who neither added nor minted revokes it
    THEN 200 (orphan rule: any member may act as the adder)
    """
    set_url_adder(app, FIRST_UTUB_URL_ID, SECOND_USER_ID)
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=CREATOR_ID)
    remove_member(app, FIRST_UTUB_ID, SECOND_USER_ID)

    with logged_in_as(app, THIRD_USER_ID) as (client, csrf_token):
        response = delete_revoke(client, csrf_token)

    _assert_revoked(response, app)


def test_non_member_gets_404_without_error_code(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN a user who is not a member of the UTub
    WHEN they revoke a link
    THEN the route-guard 404 carries no short-link error code and the row remains
    """
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=CREATOR_ID)
    remove_member(app, FIRST_UTUB_ID, THIRD_USER_ID)

    with logged_in_as(app, THIRD_USER_ID) as (client, csrf_token):
        response = delete_revoke(client, csrf_token)

    assert response.status_code == 404
    assert STD_JSON.ERROR_CODE not in (response.json or {})
    assert len(short_link_rows(app, FIRST_UTUB_URL_ID)) == 1


def test_url_not_in_utub_gets_404_without_error_code(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a nonexistent URL id and a URL belonging to another UTub
    WHEN the creator revokes with each
    THEN both are route-guard 404s carrying no short-link error code
    """
    client, csrf_token, _, _ = login_first_user_without_register

    other_utub_response = delete_revoke(
        client, csrf_token, utub_url_id=FIRST_UTUB_URL_ID + 1
    )
    missing_response = delete_revoke(client, csrf_token, utub_url_id=NONEXISTENT_ID)

    for response in (other_utub_response, missing_response):
        assert response.status_code == 404
        assert STD_JSON.ERROR_CODE not in (response.json or {})


def test_revoke_with_no_link_gets_404_with_error_code(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a live URL with no short link
    WHEN the owner revokes
    THEN 404 with ShortLinkErrorCodes.SHORT_LINK_NOT_FOUND
    """
    client, csrf_token, _, _ = login_first_user_without_register

    response = delete_revoke(client, csrf_token)

    assert response.status_code == 404
    assert response.json[STD_JSON.MESSAGE] == SHORT_LINK_FAILURE.SHORT_LINK_NOT_FOUND
    assert (
        int(response.json[STD_JSON.ERROR_CODE])
        == ShortLinkErrorCodes.SHORT_LINK_NOT_FOUND
    )


def test_revoke_expired_link_gets_404_with_error_code(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a URL whose link has expired
    WHEN the owner revokes
    THEN 404 with ShortLinkErrorCodes.SHORT_LINK_NOT_FOUND and the stale row is untouched
    """
    client, csrf_token, _, app = login_first_user_without_register
    add_short_link(
        app,
        FIRST_UTUB_URL_ID,
        minted_by=CREATOR_ID,
        expires_at=utc_now() - timedelta(minutes=1),
    )

    response = delete_revoke(client, csrf_token)

    assert response.status_code == 404
    assert (
        int(response.json[STD_JSON.ERROR_CODE])
        == ShortLinkErrorCodes.SHORT_LINK_NOT_FOUND
    )
    assert len(short_link_rows(app, FIRST_UTUB_URL_ID)) == 1


def test_revoke_is_allowed_in_locked_utub(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub with an active link
    WHEN the owner revokes
    THEN 200 (revoking is the safe direction) and the row is deleted
    """
    client, csrf_token, _, app = login_first_user_without_register
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=CREATOR_ID)
    lock_utub(app, FIRST_UTUB_ID)

    response = delete_revoke(client, csrf_token)

    _assert_revoked(response, app)


def test_revoke_without_csrf_token_returns_html_403(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN an active link
    WHEN the owner DELETEs the route without the CSRF token
    THEN the HTML 403 page is returned and the row remains
    """
    client, _, _, app = login_first_user_without_register
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=CREATOR_ID)

    response = client.delete(
        url_for(
            ROUTES.URLS.REVOKE_SHORT_LINK,
            utub_id=FIRST_UTUB_ID,
            utub_url_id=FIRST_UTUB_URL_ID,
        )
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert len(short_link_rows(app, FIRST_UTUB_URL_ID)) == 1


def test_revoke_emits_metric_only_on_success(
    metrics_enabled_app,
    provide_metrics_redis,
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
) -> None:
    """
    GIVEN metrics enabled and a link
    WHEN a revoke fails (no link), then another succeeds
    THEN SHORT_LINK_REVOKED goes 0 -> 1 on the success only, and the success is logged
    """
    client, csrf_token, _, app = login_first_user_without_register
    assert delete_revoke(client, csrf_token).status_code == 404
    assert count_counter_keys(provide_metrics_redis, EventName.SHORT_LINK_REVOKED) == 0
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=CREATOR_ID)

    response = delete_revoke(client, csrf_token)

    assert response.status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.SHORT_LINK_REVOKED) == 1
    assert is_string_in_logs("Revoked short link", caplog.records)
