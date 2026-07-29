from typing import Generator, Tuple
from unittest import mock
from urllib.parse import urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from redis import Redis

from backend.models.users import Users
from backend.schemas.users import ChangePasswordResponseSchema
from backend.users.constants import ChangePasswordErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings import model_strs
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.reset_password_strs import RESET_PASSWORD
from backend.utils.strings.user_strs import PASSWORD_CHANGE_SUCCESS, USER_FAILURE
from tests.integration.utils import assert_response_conforms_to_schema
from tests.models_for_test import valid_user_1
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support

_SPLASH_PATH = "/"
_CURRENT_PASSWORD = valid_user_1[model_strs.PASSWORD]
_NEW_PASSWORD = "NewFakePassword5678"
_WRONG_PASSWORD = "TotallyWrongPassword!23"


@pytest.fixture(autouse=True)
def _reset_reauth_failure_counter(app: Flask) -> Generator[None, None, None]:
    """Clear the worker-scoped ``reauth-fail:*`` Redis counter before and after
    every test in this module.

    The per-user re-auth lockout counter (shared with the settings OAuth-link
    gate, DD-1) survives DB teardown — only Postgres is cleared between tests,
    not the worker's Redis DB — so without this a wrong-password test would leave
    the counter elevated and 429 a later, unrelated test on the same xdist
    worker. Mirrors ``_reset_username_change_counter`` in test_change_username.py.
    """

    def _clear() -> None:
        redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
        if not redis_uri or redis_uri == "memory://":
            return
        client = Redis.from_url(redis_uri)
        try:
            keys = client.keys("reauth-fail:*")
            if keys:
                client.delete(*keys)
        finally:
            client.close()

    _clear()
    yield
    _clear()


def _change_password_payload(
    *,
    current_password: str = _CURRENT_PASSWORD,
    new_password: str = _NEW_PASSWORD,
    confirm_new_password: str = _NEW_PASSWORD,
) -> dict[str, str]:
    return {
        "currentPassword": current_password,
        "newPassword": new_password,
        "confirmNewPassword": confirm_new_password,
    }


def test_change_password_success_updates_hash_and_survives_session(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A valid change returns 200, persists the new password hash, bumps
    ``sessions_invalidated_at``, and the acting session survives (a subsequent
    authed GET /settings is still 200 — exercising ``restamp_current_session``).
    """
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user_id),
        json=_change_password_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert_response_conforms_to_schema(
        response_json,
        ChangePasswordResponseSchema,
        expected_keys={STD_JSON.STATUS, STD_JSON.MESSAGE},
    )
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == PASSWORD_CHANGE_SUCCESS

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.is_password_correct(_NEW_PASSWORD)
        assert not refreshed.is_password_correct(_CURRENT_PASSWORD)
        assert refreshed.sessions_invalidated_at is not None

    # The acting session was re-stamped, so it survives its own invalidation.
    settings_response = client.get(url_for(ROUTES.USERS.SETTINGS))
    assert settings_response.status_code == 200


def test_change_password_wrong_current_password_returns_400_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A wrong current password fails re-auth → 400 with the INVALID_PASSWORD
    code, the dedicated CURRENT_PASSWORD_INCORRECT message (Decision #9), and a
    ``currentPassword`` field error (Decision #5). The password is unchanged."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user_id),
        json=_change_password_payload(current_password=_WRONG_PASSWORD),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert (
        response_json[STD_JSON.ERROR_CODE] == ChangePasswordErrorCodes.INVALID_PASSWORD
    )
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.CURRENT_PASSWORD_INCORRECT
    assert USER_FAILURE.CURRENT_PASSWORD_INCORRECT in (
        response_json[STD_JSON.ERRORS]["currentPassword"]
    )

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.is_password_correct(_CURRENT_PASSWORD)


def test_change_password_mismatch_returns_400(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """new != confirm fails schema validation → 400 with PASSWORDS_NOT_IDENTICAL
    on the ``confirmNewPassword`` field."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user.id),
        json=_change_password_payload(confirm_new_password="DifferentPassword99"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert RESET_PASSWORD.PASSWORDS_NOT_IDENTICAL in (
        response_json[STD_JSON.ERRORS]["confirmNewPassword"]
    )


def test_change_password_too_short_new_password_returns_400(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A too-short new password fails schema validation → 400 with a
    ``newPassword`` field error."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user.id),
        json=_change_password_payload(
            new_password="short", confirm_new_password="short"
        ),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert "newPassword" in response.get_json()[STD_JSON.ERRORS]


def test_change_password_missing_csrf_returns_403_html(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT without a CSRF token is rejected 403 with the HTML error page."""
    client, _, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user.id),
        json=_change_password_payload(),
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data


def test_change_password_oauth_only_account_returns_400(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """An OAuth-only (password-less) account is rejected 400 with the
    OAUTH_ONLY_NO_PASSWORD code (defense-in-depth; the form is hidden for such
    accounts). The fixture is now sourced from the shared conftest (Decision
    #7)."""
    client, csrf_token, user, _ = oauth_only_google_user_logged_in

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user.id),
        json=_change_password_payload(current_password="irrelevant-but-nonempty"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == ChangePasswordErrorCodes.OAUTH_ONLY_NO_PASSWORD
    )


def test_change_password_self_ownership_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT whose URL user_id is not the acting user is rejected 403."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user.id + 999),
        json=_change_password_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403


def test_change_password_anonymous_redirects_to_splash(client: FlaskClient) -> None:
    """An anonymous PUT (CSRF supplied so the auth gate — not CSRF — rejects)
    302-redirects to splash. Uses a literal path (the plain ``client`` fixture
    pushes no SERVER_NAME app-context, so ``url_for`` can't build outside a
    request)."""
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.put(
        "/users/1/password",
        json=_change_password_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302
    assert urlsplit(response.location).path == _SPLASH_PATH


def test_change_password_unvalidated_user_redirects(
    login_unvalidated_user: Tuple[FlaskClient, Users, Flask],
) -> None:
    """An authenticated-but-unvalidated user is redirected by the
    email_validation_required gate."""
    client, user, _ = login_unvalidated_user

    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user.id),
        json=_change_password_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302


# --------------------------------------------------------------------------- #
# Brute-force re-auth lockout (DD-1) — real Redis via provide_redis.
# --------------------------------------------------------------------------- #


def test_change_password_locks_out_after_max_reauth_failures(
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """``MAX_REAUTH_FAILURES`` wrong-password attempts each return 400; a further
    attempt returns 429 with the TOO_MANY_ATTEMPTS code and the shared lockout
    message — even when the (correct) current password is supplied."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id

    for _ in range(USER_CONSTANTS.MAX_REAUTH_FAILURES):
        response = client.put(
            url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user_id),
            json=_change_password_payload(current_password=_WRONG_PASSWORD),
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 400

    # A further attempt is locked out (429), regardless of the password supplied.
    blocked = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user_id),
        json=_change_password_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert blocked.status_code == 429
    blocked_json = blocked.get_json()
    assert (
        blocked_json[STD_JSON.ERROR_CODE] == ChangePasswordErrorCodes.TOO_MANY_ATTEMPTS
    )
    assert blocked_json[STD_JSON.MESSAGE] == USER_FAILURE.TOO_MANY_PASSWORD_ATTEMPTS


def test_change_password_success_clears_reauth_counter(
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A successful change clears the per-user counter (a subsequent wrong
    attempt starts fresh at 1, not at the pre-success total)."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id
    failure_key = f"reauth-fail:{user_id}"

    # A couple of wrong attempts (below the cap) accrue failures.
    for _ in range(3):
        client.put(
            url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user_id),
            json=_change_password_payload(current_password=_WRONG_PASSWORD),
            headers={"X-CSRFToken": csrf_token},
        )
    assert provide_redis.get(failure_key) == b"3"

    # A successful change clears the counter.
    success = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user_id),
        json=_change_password_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert success.status_code == 200
    assert provide_redis.get(failure_key) is None

    # The next wrong attempt (old password is now wrong) starts fresh at 1.
    fresh_fail = client.put(
        url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user_id),
        json=_change_password_payload(current_password=_CURRENT_PASSWORD),
        headers={"X-CSRFToken": csrf_token},
    )
    assert fresh_fail.status_code == 400
    assert provide_redis.get(failure_key) == b"1"


def test_change_password_fails_open_when_reauth_redis_errors(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """When the re-auth throttle Redis client raises, the change still processes
    (200) — the lockout is defense-in-depth, not the sole gate (fail-open)."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    raising_client = mock.MagicMock()
    raising_client.get.side_effect = Exception("redis down")
    raising_client.incr.side_effect = Exception("redis down")
    raising_client.delete.side_effect = Exception("redis down")

    with mock.patch(
        "backend.utils.reauth_throttle._build_reauth_redis",
        return_value=raising_client,
    ):
        response = client.put(
            url_for(ROUTES.USERS.CHANGE_PASSWORD, user_id=user_id),
            json=_change_password_payload(),
            headers={"X-CSRFToken": csrf_token},
        )

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    with app.app_context():
        assert Users.query.get(user_id).is_password_correct(_NEW_PASSWORD)
