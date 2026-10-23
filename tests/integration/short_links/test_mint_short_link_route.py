"""Route tests for ``POST /utubs/<utub_id>/urls/<utub_url_id>/short-link`` (mint)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable, Tuple
from unittest import mock

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from sqlalchemy.exc import IntegrityError

from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Member_Role
from backend.schemas.short_links import ShortLinkResponseSchema
from backend.short_links.constants import SHORT_LINK_TTL
from backend.short_links.services import mint_short_link as mint_module
from backend.urls.constants import URLErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.datetime_utils import utc_now
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.short_link_strs import (
    SHORT_LINK_FAILURE,
    SHORT_LINK_SUCCESS,
)
from tests.integration.short_links.short_link_helpers import (
    CAN_REVOKE_KEY,
    CREATED_KEY,
    CREATOR_ID,
    EXPIRES_AT_KEY,
    FIRST_UTUB_ID,
    FIRST_UTUB_URL_ID,
    NONEXISTENT_ID,
    SECOND_USER_ID,
    SHORT_URL_KEY,
    THIRD_USER_ID,
    code_from_short_url,
    logged_in_as,
    post_mint,
    set_url_adder,
    short_link_rows,
)
from tests.integration.system.metrics_helpers import (
    count_counter_keys,
    sum_counter_values,
)
from tests.utils_for_test import (
    add_short_link,
    is_string_in_logs,
    lock_utub,
    remove_member,
    set_member_role,
    trash_utub,
    trash_utub_url,
    unlock_utub,
)

pytestmark = pytest.mark.short_links

CODE_LENGTH: int = 10
OLD_CODE: str = "OldCode123"
OTHER_URL_CODE: str = "OtherUrl12"
FRESH_CODE: str = "FreshCode1"


def _assert_success_body(body: dict[str, Any], *, created: bool) -> None:
    assert body[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert body[CREATED_KEY] is created
    assert body[STD_JSON.MESSAGE] == (
        SHORT_LINK_SUCCESS.SHORT_LINK_CREATED
        if created
        else SHORT_LINK_SUCCESS.SHORT_LINK_REUSED
    )
    assert "/s/" in body[SHORT_URL_KEY]
    assert len(code_from_short_url(body[SHORT_URL_KEY])) == CODE_LENGTH
    ShortLinkResponseSchema.model_validate(body)


def test_mint_creates_link_for_creator(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the creator of a UTub holding a live URL with no short link
    WHEN they POST the mint route
    THEN 200 with a /s/<10-char code> URL, created true, an expiry one TTL ahead,
        canRevoke true, and exactly one ShortLinks row minted by them
    """
    client, csrf_token, _, app = login_first_user_without_register
    before = utc_now()

    response = post_mint(client, csrf_token)

    assert response.status_code == 200
    body = response.json
    _assert_success_body(body, created=True)
    assert body[CAN_REVOKE_KEY] is True
    rows = short_link_rows(app)
    assert len(rows) == 1
    assert rows[0].code == code_from_short_url(body[SHORT_URL_KEY])
    assert rows[0].created_by == CREATOR_ID
    assert rows[0].utub_url_id == FIRST_UTUB_URL_ID
    assert before + SHORT_LINK_TTL <= rows[0].expires_at <= utc_now() + SHORT_LINK_TTL


def test_second_mint_returns_same_link_unchanged(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a URL that already has an active short link
    WHEN the mint route is POSTed again
    THEN 200 with the same code, created false and an unchanged expiresAt
    """
    client, csrf_token, _, app = login_first_user_without_register
    first_body = post_mint(client, csrf_token).json

    response = post_mint(client, csrf_token)

    assert response.status_code == 200
    body = response.json
    _assert_success_body(body, created=False)
    assert body[SHORT_URL_KEY] == first_body[SHORT_URL_KEY]
    assert body[EXPIRES_AT_KEY] == first_body[EXPIRES_AT_KEY]
    assert len(short_link_rows(app)) == 1


def test_mint_after_expiry_issues_new_code_and_old_code_is_gone(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a URL whose short link has expired (backdated expiresAt)
    WHEN a member mints again
    THEN 200 with created true and a different code, exactly one row remains, and it
        no longer carries the old code
    """
    client, csrf_token, _, app = login_first_user_without_register
    add_short_link(
        app,
        FIRST_UTUB_URL_ID,
        minted_by=SECOND_USER_ID,
        code=OLD_CODE,
        expires_at=utc_now() - timedelta(minutes=1),
    )

    response = post_mint(client, csrf_token)

    assert response.status_code == 200
    body = response.json
    _assert_success_body(body, created=True)
    new_code = code_from_short_url(body[SHORT_URL_KEY])
    assert new_code != OLD_CODE
    rows = short_link_rows(app)
    assert [row.code for row in rows] == [new_code]
    assert rows[0].created_by == CREATOR_ID
    assert rows[0].expires_at > utc_now()


@pytest.mark.parametrize(
    "acting_user_id, role",
    [
        pytest.param(CREATOR_ID, Member_Role.CREATOR, id="owner"),
        pytest.param(SECOND_USER_ID, Member_Role.CO_CREATOR, id="co_owner"),
        pytest.param(SECOND_USER_ID, Member_Role.MEMBER, id="minter_member"),
    ],
)
def test_mint_can_revoke_true_for_manager_and_minter(
    add_one_url_and_all_users_to_each_utub_no_tags,
    app: Flask,
    acting_user_id: int,
    role: Member_Role,
) -> None:
    """
    GIVEN URL 1 added by the creator, and a minter in the given role
    WHEN that user mints
    THEN canRevoke is true (owner, co-owner, or the minter themselves)
    """
    if acting_user_id != CREATOR_ID:
        set_member_role(app, FIRST_UTUB_ID, acting_user_id, role)

    with logged_in_as(app, acting_user_id) as (client, csrf_token):
        response = post_mint(client, csrf_token)

    assert response.status_code == 200
    assert response.json[CAN_REVOKE_KEY] is True


def test_mint_can_revoke_true_for_plain_member_who_added_the_url_on_reuse(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN URL 1 added by a plain member and a link minted by the creator
    WHEN the plain adder mints again (reusing the link)
    THEN canRevoke is true through the adder arm alone: they are neither manager nor
        the minter
    """
    set_url_adder(app, FIRST_UTUB_URL_ID, SECOND_USER_ID)
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=CREATOR_ID)

    with logged_in_as(app, SECOND_USER_ID) as (client, csrf_token):
        response = post_mint(client, csrf_token)

    assert response.status_code == 200
    _assert_success_body(response.json, created=False)
    assert response.json[CAN_REVOKE_KEY] is True


def test_mint_can_revoke_false_for_plain_member_reusing_others_link(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN a link minted by the creator (who is also the URL adder)
    WHEN a plain member who neither added the URL nor minted the link mints again
    THEN 200 reusing the link with canRevoke false
    """
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=CREATOR_ID)

    with logged_in_as(app, THIRD_USER_ID) as (client, csrf_token):
        response = post_mint(client, csrf_token)

    assert response.status_code == 200
    _assert_success_body(response.json, created=False)
    assert response.json[CAN_REVOKE_KEY] is False


def test_mint_forced_single_code_collision_still_succeeds(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN another URL's link already holds the first generated code
    WHEN the generator returns that code once and then a fresh one
    THEN the retry loop recovers: 200 with the fresh code and one new row
    """
    client, csrf_token, _, app = login_first_user_without_register
    other_url_id = FIRST_UTUB_URL_ID + 1
    add_short_link(app, other_url_id, minted_by=CREATOR_ID, code=OTHER_URL_CODE)

    with mock.patch.object(
        mint_module,
        "generate_short_link_code",
        side_effect=[OTHER_URL_CODE, FRESH_CODE],
    ):
        response = post_mint(client, csrf_token)

    assert response.status_code == 200
    assert code_from_short_url(response.json[SHORT_URL_KEY]) == FRESH_CODE
    assert [row.code for row in short_link_rows(app, FIRST_UTUB_URL_ID)] == [FRESH_CODE]


def test_mint_all_retries_colliding_returns_generic_500_and_no_row(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN another URL's link holds the code every attempt generates
    WHEN all 5 attempts collide
    THEN the response is the generic 500 and no row is written for the URL
    """
    client, csrf_token, _, app = login_first_user_without_register
    add_short_link(
        app, FIRST_UTUB_URL_ID + 1, minted_by=CREATOR_ID, code=OTHER_URL_CODE
    )

    with mock.patch.object(
        mint_module, "generate_short_link_code", return_value=OTHER_URL_CODE
    ) as generator:
        response = post_mint(client, csrf_token)

    assert generator.call_count == 5
    assert response.status_code == 500
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert response.json[STD_JSON.MESSAGE] == SHORT_LINK_FAILURE.SOMETHING_WENT_WRONG
    assert short_link_rows(app, FIRST_UTUB_URL_ID) == []


def test_mint_unrelated_integrity_error_propagates_and_writes_no_row(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the savepoint insert raises an IntegrityError naming an unrelated constraint
    WHEN the mint handles it
    THEN the error propagates (fail closed, no retry) and no ShortLinks row is left
    """
    client, csrf_token, _, app = login_first_user_without_register
    add_short_link(
        app, FIRST_UTUB_URL_ID + 1, minted_by=CREATOR_ID, code=OTHER_URL_CODE
    )

    with mock.patch.object(
        mint_module, "generate_short_link_code", return_value=OTHER_URL_CODE
    ) as generator:
        with mock.patch.object(
            mint_module, "_violated_constraint", return_value="unrelated_constraint"
        ):
            with pytest.raises(IntegrityError):
                post_mint(client, csrf_token)

    assert generator.call_count == 1
    assert short_link_rows(app, FIRST_UTUB_URL_ID) == []


def test_concurrent_first_mint_returns_winner_with_one_row(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a competing first mint already committed a row, but the existing-row lookup
        misses it once (the race window)
    WHEN this mint inserts and hits the per-URL unique constraint
    THEN 200 with the winner's code, created false, and exactly one row
    """
    client, csrf_token, _, app = login_first_user_without_register
    add_short_link(app, FIRST_UTUB_URL_ID, minted_by=SECOND_USER_ID, code=OLD_CODE)
    real_lookup = mint_module._lock_existing_short_link
    lookups: list[int] = []

    def _miss_once(*, utub_url_id: int) -> Any:
        lookups.append(utub_url_id)
        if len(lookups) == 1:
            return None
        return real_lookup(utub_url_id=utub_url_id)

    with mock.patch.object(mint_module, "_lock_existing_short_link", _miss_once):
        response = post_mint(client, csrf_token)

    assert response.status_code == 200
    body = response.json
    _assert_success_body(body, created=False)
    assert code_from_short_url(body[SHORT_URL_KEY]) == OLD_CODE
    assert [row.code for row in short_link_rows(app)] == [OLD_CODE]


def _trash_before_real_lock(
    app: Flask, trash: Callable[[], None]
) -> Callable[..., Any]:
    """Wrap ``lock_and_reauthorize`` so ``trash`` commits after the route guards passed
    but before the service takes its locks."""
    real_lock = mint_module.lock_and_reauthorize

    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        trash()
        return real_lock(*args, **kwargs)

    return _wrapper


def test_mint_racing_url_trash_returns_404_and_writes_no_row(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the URL is trashed (committed) after the route guards passed
    WHEN the mint service takes its locks
    THEN 404 and no ShortLinks row
    """
    client, csrf_token, _, app = login_first_user_without_register
    wrapper = _trash_before_real_lock(
        app, lambda: trash_utub_url(app, FIRST_UTUB_URL_ID, deleted_by=CREATOR_ID)
    )

    with mock.patch.object(mint_module, "lock_and_reauthorize", wrapper):
        response = post_mint(client, csrf_token)

    assert response.status_code == 404
    assert short_link_rows(app) == []


def test_mint_racing_utub_trash_returns_404_and_writes_no_row(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the UTub is trashed (committed) after the route guards passed
    WHEN the mint service takes its locks
    THEN 404 and no ShortLinks row
    """
    client, csrf_token, _, app = login_first_user_without_register
    wrapper = _trash_before_real_lock(
        app, lambda: trash_utub(app, FIRST_UTUB_ID, deleted_by=CREATOR_ID)
    )

    with mock.patch.object(mint_module, "lock_and_reauthorize", wrapper):
        response = post_mint(client, csrf_token)

    assert response.status_code == 404
    assert short_link_rows(app) == []


def test_mint_in_locked_utub_returns_403_with_lock_error(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a locked UTub
    WHEN a member mints
    THEN 403 with URLErrorCodes.UTUB_IS_LOCKED and no row
    """
    client, csrf_token, _, app = login_first_user_without_register
    lock_utub(app, FIRST_UTUB_ID)

    response = post_mint(client, csrf_token)

    assert response.status_code == 403
    assert response.json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert int(response.json[STD_JSON.ERROR_CODE]) == URLErrorCodes.UTUB_IS_LOCKED
    assert short_link_rows(app) == []


def test_mint_by_non_member_returns_404(
    add_one_url_and_all_users_to_each_utub_no_tags, app: Flask
) -> None:
    """
    GIVEN a user who is not a member of the UTub
    WHEN they mint for one of its URLs
    THEN 404 and no row
    """
    remove_member(app, FIRST_UTUB_ID, THIRD_USER_ID)

    with logged_in_as(app, THIRD_USER_ID) as (client, csrf_token):
        response = post_mint(client, csrf_token)

    assert response.status_code == 404
    assert short_link_rows(app) == []


def test_mint_for_trashed_url_returns_404(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a trashed URL
    WHEN a member mints for it
    THEN 404 and no row
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub_url(app, FIRST_UTUB_URL_ID, deleted_by=CREATOR_ID)

    response = post_mint(client, csrf_token)

    assert response.status_code == 404
    assert short_link_rows(app) == []


def test_mint_in_trashed_utub_returns_404(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a trashed UTub
    WHEN a member mints for one of its URLs
    THEN 404 and no row
    """
    client, csrf_token, _, app = login_first_user_without_register
    trash_utub(app, FIRST_UTUB_ID, deleted_by=CREATOR_ID)

    response = post_mint(client, csrf_token)

    assert response.status_code == 404
    assert short_link_rows(app) == []


def test_mint_with_url_from_another_utub_returns_404(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a URL that belongs to a different UTub than the path's
    WHEN a member mints with the mismatched ids
    THEN 404 and no row
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = post_mint(client, csrf_token, utub_url_id=FIRST_UTUB_URL_ID + 1)
    nonexistent_response = post_mint(client, csrf_token, utub_url_id=NONEXISTENT_ID)

    assert response.status_code == 404
    assert nonexistent_response.status_code == 404
    assert short_link_rows(app) == []


def test_mint_without_csrf_token_returns_html_403(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN a logged-in member
    WHEN they POST the mint route without the CSRF token
    THEN the HTML 403 page is returned and no row is written
    """
    client, _, _, app = login_first_user_without_register

    response = client.post(
        url_for(
            ROUTES.URLS.MINT_SHORT_LINK,
            utub_id=FIRST_UTUB_ID,
            utub_url_id=FIRST_UTUB_URL_ID,
        )
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    assert short_link_rows(app) == []


def test_mint_forced_rate_limit_returns_429(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN the test hook that forces a rate-limit response (the limiter itself is
        disabled under TESTING)
    WHEN a member mints with the X-Force-Rate-Limit header
    THEN 429 and no row
    """
    client, csrf_token, _, app = login_first_user_without_register

    response = client.post(
        url_for(
            ROUTES.URLS.MINT_SHORT_LINK,
            utub_id=FIRST_UTUB_ID,
            utub_url_id=FIRST_UTUB_URL_ID,
        ),
        headers={"X-CSRFToken": csrf_token, "X-Force-Rate-Limit": "1"},
    )

    assert response.status_code == 429
    assert short_link_rows(app) == []


def test_anonymous_mint_is_redirected_like_other_guarded_routes(
    add_one_url_and_all_users_to_each_utub_no_tags,
    load_login_page: Tuple[FlaskClient, str],
    app: Flask,
) -> None:
    """
    GIVEN an anonymous caller holding a valid CSRF token from the splash page
    WHEN they POST the mint route
    THEN the existing unauthenticated response is returned (the 302 redirect to the
        splash page, as the bulk restore route gives) and no row is written; the
        rate-limit key function is proven separately by its unit test
    """
    client, csrf_token = load_login_page

    response = post_mint(client, csrf_token)

    assert response.status_code == 302
    assert short_link_rows(app) == []


def test_mint_success_emits_metric_once_and_reuse_or_failure_do_not(
    metrics_enabled_app,
    provide_metrics_redis,
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """
    GIVEN metrics enabled and a locked-then-unlocked UTub
    WHEN a mint fails (locked), then succeeds, then is reused
    THEN SHORT_LINK_MINTED goes 0 -> 1 on the creating mint only
    """
    client, csrf_token, _, app = login_first_user_without_register
    assert count_counter_keys(provide_metrics_redis, EventName.SHORT_LINK_MINTED) == 0
    lock_utub(app, FIRST_UTUB_ID)
    assert post_mint(client, csrf_token).status_code == 403
    assert count_counter_keys(provide_metrics_redis, EventName.SHORT_LINK_MINTED) == 0
    unlock_utub(app, FIRST_UTUB_ID)

    assert post_mint(client, csrf_token).status_code == 200
    assert count_counter_keys(provide_metrics_redis, EventName.SHORT_LINK_MINTED) == 1

    assert post_mint(client, csrf_token).json[CREATED_KEY] is False
    assert sum_counter_values(provide_metrics_redis, EventName.SHORT_LINK_MINTED) == 1


def test_mint_logs_success(
    add_one_url_and_all_users_to_each_utub_no_tags,
    login_first_user_without_register: Tuple[FlaskClient, str, Users, Flask],
    caplog,
) -> None:
    """
    GIVEN a member of a UTub
    WHEN they mint a link
    THEN the success log lines name the user, UTub and URL
    """
    client, csrf_token, _, _ = login_first_user_without_register

    post_mint(client, csrf_token)

    assert is_string_in_logs("Minted short link", caplog.records)
    assert is_string_in_logs(f"UTubURL.id={FIRST_UTUB_URL_ID}", caplog.records)
