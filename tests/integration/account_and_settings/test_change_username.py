from typing import Generator, Tuple
from unittest import mock
from urllib.parse import urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from redis import Redis

from backend import db
from backend.models.users import Users
from backend.users.constants import ChangeUsernameErrorCodes
from backend.schemas.users import ChangeUsernameResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.user_strs import (
    USER_FAILURE,
    USERNAME_CHANGE_NO_CHANGE,
    USERNAME_CHANGE_SUCCESS,
)
from tests.integration.utils import assert_response_conforms_to_schema
from tests.models_for_test import valid_user_2
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support

_SPLASH_PATH = "/"
_NEW_USERNAME = "renamed_user"


@pytest.fixture(autouse=True)
def _reset_username_change_counter(app: Flask) -> Generator[None, None, None]:
    """Clear the worker-scoped ``username-change:*`` Redis counter before and
    after every test in this module.

    The counter key survives DB teardown (only the Postgres DB is cleared
    between tests, not the worker's Redis DB), so without this a successful
    rename in one test would leave the per-user counter elevated and rate-limit
    (429) a later, unrelated success/uniqueness test on the same xdist worker.
    """

    def _clear() -> None:
        redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
        if not redis_uri or redis_uri == "memory://":
            return
        client = Redis.from_url(redis_uri)
        try:
            keys = client.keys("username-change:*")
            if keys:
                client.delete(*keys)
        finally:
            client.close()

    _clear()
    yield
    _clear()


def _seed_second_user(app: Flask) -> str:
    """Seed a second local-password user (distinct from user 1) and return its
    username, for the uniqueness-collision assertions."""
    with app.app_context():
        if Users.query.filter_by(username=valid_user_2["username"]).first() is None:
            second_user = Users(
                username=valid_user_2["username"],
                email=valid_user_2["email"].lower(),
                plaintext_password=valid_user_2["password"],
            )
            second_user.email_validated = True
            db.session.add(second_user)
            db.session.commit()
    return valid_user_2["username"]


def test_change_username_success_updates_db_and_returns_envelope(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A valid rename returns 200 with the shared response envelope, and the
    username is actually persisted (verified in a fresh app_context)."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user_id),
        json={"username": _NEW_USERNAME},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()

    assert_response_conforms_to_schema(
        response_json,
        ChangeUsernameResponseSchema,
        expected_keys={"username", STD_JSON.STATUS, STD_JSON.MESSAGE},
    )
    # DD-17: assert the server-sourced status + banner copy the client renders.
    assert response_json["username"] == _NEW_USERNAME
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == USERNAME_CHANGE_SUCCESS

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.username == _NEW_USERNAME


def test_change_username_no_op_returns_no_change_envelope(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """DD-17: resubmitting the current username returns 200 with status
    ``No change`` and the no-op banner copy (a response-body-shape assertion,
    distinct from the counter-no-burn invariant below)."""
    client, csrf_token, user, _ = login_first_user_with_register
    current_username = user.username

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user.id),
        json={"username": current_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json["username"] == current_username
    assert response_json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert response_json[STD_JSON.MESSAGE] == USERNAME_CHANGE_NO_CHANGE


def test_change_username_missing_csrf_returns_403_html(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT without a CSRF token is rejected 403 with the HTML error page."""
    client, _, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user.id),
        json={"username": _NEW_USERNAME},
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data


@pytest.mark.parametrize(
    "bad_username",
    ["ab", "", "x" * 21],
    ids=["too_short", "empty", "too_long"],
)
def test_change_username_invalid_length_returns_400_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    bad_username: str,
) -> None:
    """Too-short / empty / too-long usernames fail schema validation → 400 with
    a ``username`` field error."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user.id),
        json={"username": bad_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert "username" in response_json[STD_JSON.ERRORS]


def test_change_username_taken_returns_400(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Renaming to a username already owned by another account is rejected 400
    with the USERNAME_TAKEN error code and field error."""
    client, csrf_token, user, app = login_first_user_with_register
    taken_username = _seed_second_user(app)

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user.id),
        json={"username": taken_username},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.ERROR_CODE] == ChangeUsernameErrorCodes.USERNAME_TAKEN
    assert USER_FAILURE.USERNAME_TAKEN in response_json[STD_JSON.ERRORS]["username"]


def test_change_username_self_ownership_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT whose URL user_id is not the acting user is rejected 403."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user.id + 999),
        json={"username": _NEW_USERNAME},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403


def test_change_username_anonymous_redirects_to_splash(client: FlaskClient) -> None:
    """An anonymous PUT (CSRF token supplied so the auth gate — not CSRF — is
    what rejects) 302-redirects to splash.

    Uses a literal path (not ``url_for``): the plain ``client`` fixture pushes
    no SERVER_NAME app-context, so ``url_for`` can't build outside a request —
    mirroring ``test_settings_page_redirects_anonymous_to_splash``.
    """
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.put(
        "/users/1/username",
        json={"username": _NEW_USERNAME},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302
    assert urlsplit(response.location).path == _SPLASH_PATH


def test_change_username_unvalidated_user_redirects(
    login_unvalidated_user: Tuple[FlaskClient, Users, Flask],
) -> None:
    """An authenticated-but-unvalidated user is redirected by the
    email_validation_required gate."""
    client, user, _ = login_unvalidated_user

    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user.id),
        json={"username": _NEW_USERNAME},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302


# --------------------------------------------------------------------------- #
# Rate-limit (Decision #4) — real Redis via provide_redis.
# --------------------------------------------------------------------------- #


def test_change_username_rate_limit_cap(
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """3 distinct successful changes return 200; the 4th returns 429 with the
    RATE_LIMITED code, and the per-user Redis counter reads ``b"3"`` with a live
    TTL within the 24h window."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id
    rate_limit_key = f"username-change:{user_id}"
    # The counter starts clean: the autouse `_reset_username_change_counter`
    # fixture clears every `username-change:*` key before this test runs.

    for index in range(3):
        response = client.put(
            url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user_id),
            json={"username": f"renamed_{index}"},
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 200

    blocked = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user_id),
        json={"username": "renamed_blocked"},
        headers={"X-CSRFToken": csrf_token},
    )
    assert blocked.status_code == 429
    assert (
        blocked.get_json()[STD_JSON.ERROR_CODE] == ChangeUsernameErrorCodes.RATE_LIMITED
    )

    assert provide_redis.get(rate_limit_key) == b"3"
    ttl = provide_redis.ttl(rate_limit_key)
    assert 0 < ttl <= 86_400


def test_change_username_rejections_do_not_burn_a_slot(
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A taken-name rejection (400) and a no-op resubmit (200 No change) never
    increment the counter — the Redis key stays absent."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    current_username = user.username
    rate_limit_key = f"username-change:{user_id}"
    # The autouse `_reset_username_change_counter` fixture guarantees a clean
    # counter, so the rate-limit precheck can't fire before the uniqueness guard.
    taken_username = _seed_second_user(app)

    taken_response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user_id),
        json={"username": taken_username},
        headers={"X-CSRFToken": csrf_token},
    )
    assert taken_response.status_code == 400
    assert provide_redis.get(rate_limit_key) is None

    no_op_response = client.put(
        url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user_id),
        json={"username": current_username},
        headers={"X-CSRFToken": csrf_token},
    )
    assert no_op_response.status_code == 200
    assert provide_redis.get(rate_limit_key) is None


def test_change_username_fails_open_when_redis_errors(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """When the rate-limit Redis client raises, the rename still succeeds (200)
    — the cap is anti-spam, not a security boundary (fail-open)."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    raising_client = mock.MagicMock()
    raising_client.get.side_effect = Exception("redis down")
    raising_client.incr.side_effect = Exception("redis down")

    with mock.patch(
        "backend.users.services.account_service._build_rate_limit_redis",
        return_value=raising_client,
    ):
        response = client.put(
            url_for(ROUTES.USERS.CHANGE_USERNAME, user_id=user_id),
            json={"username": _NEW_USERNAME},
            headers={"X-CSRFToken": csrf_token},
        )

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    with app.app_context():
        assert Users.query.get(user_id).username == _NEW_USERNAME
