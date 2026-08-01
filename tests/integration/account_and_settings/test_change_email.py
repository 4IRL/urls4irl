from typing import Generator, Tuple
from unittest import mock
from urllib.parse import urlsplit

import pytest
from flask import Flask, url_for
from flask.testing import FlaskClient
from redis import Redis
from requests import Response

from backend import db
from backend.models.users import Users
from backend.schemas.users import ChangeEmailResponseSchema
from backend.users.constants import ChangeEmailErrorCodes
from backend.utils.all_routes import ROUTES
from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings import model_strs
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.splash_form_strs import EMAILS_NOT_IDENTICAL
from backend.utils.strings.user_strs import (
    EMAIL_CHANGE_CONFIRMATION_SENT,
    EMAIL_CHANGE_NO_CHANGE,
    EMAIL_CHANGE_RATE_LIMITED,
    USER_FAILURE,
)
from tests.integration.utils import assert_response_conforms_to_schema
from tests.models_for_test import valid_user_1, valid_user_2
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support

_SPLASH_PATH = "/"
_CURRENT_PASSWORD = valid_user_1[model_strs.PASSWORD]
_WRONG_PASSWORD = "TotallyWrongPassword!23"
_NEW_EMAIL = "brandnewemail@example.com"

_SEND_TARGET = (
    "backend.extensions.email_sender.email_sender.EmailSender."
    "send_email_change_confirmation"
)


@pytest.fixture(autouse=True)
def _reset_rate_limit_state(app: Flask) -> Generator[None, None, None]:
    """Clear the worker-scoped ``reauth-fail:*`` and ``email-change:*`` Redis
    counters before and after every test in this module.

    Both counters survive DB teardown (only Postgres is cleared between tests,
    not the worker's Redis DB), so without this a wrong-password or successful
    change in one test would leave a counter elevated and 429 a later, unrelated
    test on the same xdist worker. Mirrors the change-username/change-password
    reset fixtures, extended with the change-email counter.
    """

    def _clear() -> None:
        redis_uri = app.config.get(CONFIG_ENVS.REDIS_URI)
        if not redis_uri or redis_uri == "memory://":
            return
        client = Redis.from_url(redis_uri)
        try:
            for pattern in ("reauth-fail:*", "email-change:*"):
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
        finally:
            client.close()

    _clear()
    yield
    _clear()


def _build_mock_email_response(status_code: int) -> Response:
    """A ``requests.Response`` stand-in matching the shape ``EmailSender``'s real
    send methods return: a status code plus a JSON body. The body matters on the
    failure path — ``handle_mailjet_failure`` calls ``.json()`` on it (the real
    ``EmailSender._mock_response_builder`` always populates one), so a body-less
    stub would raise ``JSONDecodeError`` and misrepresent production."""
    mock_response = Response()
    mock_response.status_code = status_code
    mock_response._content = b"{}"
    mock_response.encoding = "utf-8"
    return mock_response


def _change_email_payload(
    *,
    new_email: str = _NEW_EMAIL,
    confirm_email: str | None = None,
    current_password: str | None = None,
) -> dict[str, str]:
    return {
        "newEmail": new_email,
        "confirmEmail": confirm_email if confirm_email is not None else new_email,
        "currentPassword": (
            current_password if current_password is not None else _CURRENT_PASSWORD
        ),
    }


def _seed_second_user(app: Flask) -> str:
    """Seed a second email-validated user and return its (lowercased) email, for
    the uniqueness-collision assertion."""
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
    return valid_user_2["email"].lower()


@mock.patch(_SEND_TARGET)
def test_change_email_success_stages_pending_and_sends_to_new_address(
    mock_send: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A valid change returns 200 conforming to ChangeEmailResponseSchema, stages
    the (lowercased) pending email WITHOUT touching the live email or
    email_validated, and sends the confirmation to the NEW address exactly once.
    """
    mock_send.return_value = _build_mock_email_response(200)
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    with app.app_context():
        live_email = Users.query.get(user_id).email

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert_response_conforms_to_schema(
        response_json,
        ChangeEmailResponseSchema,
        expected_keys={STD_JSON.STATUS, STD_JSON.MESSAGE, model_strs.PENDING_EMAIL},
    )
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == EMAIL_CHANGE_CONFIRMATION_SENT
    assert response_json[model_strs.PENDING_EMAIL] == _NEW_EMAIL

    with app.app_context():
        refreshed: Users = Users.query.get(user_id)
        assert refreshed.email == live_email
        assert refreshed.pending_email == _NEW_EMAIL
        assert refreshed.email_validated is True

    mock_send.assert_called_once()
    assert mock_send.call_args.args[0] == _NEW_EMAIL


@mock.patch(_SEND_TARGET)
def test_change_email_mixed_case_new_email_is_lowercased_on_stage(
    mock_send: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The service lowercases the mixed-case local part on store and the send
    recipient is the fully-lowercased address.

    Note: the confirm field must match ``new_email`` *after* ``EmailStr``
    normalizes it (which lowercases only the domain), so both fields use the same
    already-domain-lowercase string; the service's own ``.lower()`` is what
    lowercases the local part into ``pending_email``.
    """
    mock_send.return_value = _build_mock_email_response(200)
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(new_email="MixedCase@example.com"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    with app.app_context():
        assert Users.query.get(user_id).pending_email == "mixedcase@example.com"
    assert mock_send.call_args.args[0] == "mixedcase@example.com"


@mock.patch(_SEND_TARGET)
def test_change_email_no_op_same_email_returns_200_no_change_no_send(
    mock_send: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Resubmitting the current email returns 200 No-change, stages nothing, and
    never sends an email."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    with app.app_context():
        live_email = Users.query.get(user_id).email

    # Resubmit the exact live (already-lowercased) email in both fields. The
    # no-op guard's own ``new_email.lower()`` comparison is what matches it to
    # the stored live email.
    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(new_email=live_email),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.NO_CHANGE
    assert response_json[STD_JSON.MESSAGE] == EMAIL_CHANGE_NO_CHANGE
    assert response_json[model_strs.PENDING_EMAIL] is None

    with app.app_context():
        assert Users.query.get(user_id).pending_email is None
    mock_send.assert_not_called()


@mock.patch(_SEND_TARGET)
def test_change_email_wrong_password_returns_400_field_error_no_staging(
    mock_send: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A wrong current password fails re-auth → 400 INVALID_PASSWORD with a
    ``currentPassword`` field error; nothing is staged and no email is sent."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(current_password=_WRONG_PASSWORD),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.ERROR_CODE] == ChangeEmailErrorCodes.INVALID_PASSWORD
    assert response_json[STD_JSON.MESSAGE] == USER_FAILURE.CURRENT_PASSWORD_INCORRECT
    assert USER_FAILURE.CURRENT_PASSWORD_INCORRECT in (
        response_json[STD_JSON.ERRORS]["currentPassword"]
    )

    with app.app_context():
        assert Users.query.get(user_id).pending_email is None
    mock_send.assert_not_called()


def test_change_email_malformed_email_returns_400_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A malformed new email fails schema validation → 400 with a ``newEmail``
    field error."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user.id),
        json=_change_email_payload(new_email="not-an-email"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert "newEmail" in response.get_json()[STD_JSON.ERRORS]


def test_change_email_mismatch_returns_400_confirm_field_error(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """DD-10: newEmail != confirmEmail fails the confirm_email validator → 400
    with EMAILS_NOT_IDENTICAL keyed under ``confirmEmail`` (mirrors
    test_change_password_mismatch_returns_400)."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user.id),
        json=_change_email_payload(
            new_email=_NEW_EMAIL, confirm_email="different@example.com"
        ),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert EMAILS_NOT_IDENTICAL in response_json[STD_JSON.ERRORS]["confirmEmail"]


@mock.patch(_SEND_TARGET)
def test_change_email_taken_email_returns_400_field_error(
    mock_send: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A new email already owned by another account → 400 EMAIL_TAKEN field error
    on ``newEmail``; nothing staged, no email sent."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    taken_email = _seed_second_user(app)

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(new_email=taken_email),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.ERROR_CODE] == ChangeEmailErrorCodes.EMAIL_TAKEN
    assert USER_FAILURE.EMAIL_TAKEN in response_json[STD_JSON.ERRORS]["newEmail"]

    with app.app_context():
        assert Users.query.get(user_id).pending_email is None
    mock_send.assert_not_called()


def test_change_email_oauth_only_account_returns_400(
    oauth_only_google_user_logged_in: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """An OAuth-only (password-less) account is rejected 400 with the
    OAUTH_ONLY_NO_PASSWORD code (defense-in-depth; the form is hidden)."""
    client, csrf_token, user, _ = oauth_only_google_user_logged_in

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user.id),
        json=_change_email_payload(current_password="irrelevant-but-nonempty"),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == ChangeEmailErrorCodes.OAUTH_ONLY_NO_PASSWORD
    )


def test_change_email_self_ownership_mismatch_returns_403(
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A PUT whose URL user_id is not the acting user is rejected 403."""
    client, csrf_token, user, _ = login_first_user_with_register

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user.id + 999),
        json=_change_email_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 403


def test_change_email_anonymous_redirects_to_splash(client: FlaskClient) -> None:
    """An anonymous PUT (CSRF supplied so the auth gate — not CSRF — rejects)
    302-redirects to splash. Uses a literal path (the plain ``client`` fixture
    pushes no SERVER_NAME app-context)."""
    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.put(
        "/users/1/email",
        json=_change_email_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302
    assert urlsplit(response.location).path == _SPLASH_PATH


def test_change_email_unvalidated_user_redirects(
    login_unvalidated_user: Tuple[FlaskClient, Users, Flask],
) -> None:
    """An authenticated-but-unvalidated user is redirected by the
    email_validation_required gate."""
    client, user, _ = login_unvalidated_user

    splash_response = client.get("/")
    csrf_token = get_csrf_token(splash_response.get_data(), meta_tag=True)

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user.id),
        json=_change_email_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 302


@mock.patch(_SEND_TARGET)
def test_change_email_send_failure_rolls_back_staging(
    mock_send: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A Mailjet send failure (>=500) returns the error envelope with
    EMAIL_SEND_FAILURE and rolls the staged pending email back to None so nothing
    is left half-staged."""
    mock_send.return_value = _build_mock_email_response(502)
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id

    response = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(),
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 400
    assert (
        response.get_json()[STD_JSON.ERROR_CODE]
        == ChangeEmailErrorCodes.EMAIL_SEND_FAILURE
    )
    with app.app_context():
        assert Users.query.get(user_id).pending_email is None


# --------------------------------------------------------------------------- #
# Re-auth lockout + per-day rate limit + fail-open — real Redis via provide_redis.
# --------------------------------------------------------------------------- #


def test_change_email_locks_out_after_max_reauth_failures(
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """``MAX_REAUTH_FAILURES`` wrong-password attempts each return 400; a further
    attempt returns 429 TOO_MANY_ATTEMPTS — even with the correct password."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id

    for _ in range(USER_CONSTANTS.MAX_REAUTH_FAILURES):
        response = client.put(
            url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
            json=_change_email_payload(current_password=_WRONG_PASSWORD),
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 400

    blocked = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert blocked.status_code == 429
    assert (
        blocked.get_json()[STD_JSON.ERROR_CODE]
        == ChangeEmailErrorCodes.TOO_MANY_ATTEMPTS
    )


@mock.patch(_SEND_TARGET)
def test_change_email_success_clears_reauth_counter(
    mock_send: mock.MagicMock,
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """A successful change clears the per-user re-auth counter (a subsequent wrong
    attempt starts fresh at 1)."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    mock_send.return_value = _build_mock_email_response(200)
    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id
    failure_key = f"reauth-fail:{user_id}"

    for _ in range(3):
        client.put(
            url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
            json=_change_email_payload(current_password=_WRONG_PASSWORD),
            headers={"X-CSRFToken": csrf_token},
        )
    assert provide_redis.get(failure_key) == b"3"

    success = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(),
        headers={"X-CSRFToken": csrf_token},
    )
    assert success.status_code == 200
    assert provide_redis.get(failure_key) is None


@mock.patch(_SEND_TARGET)
def test_change_email_per_day_rate_limit_cap(
    mock_send: mock.MagicMock,
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """MAX_EMAIL_CHANGES_PER_DAY successful changes return 200; the next returns
    429 RATE_LIMITED, and the per-user Redis counter reads the cap with a live
    TTL within the 24h window."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    mock_send.return_value = _build_mock_email_response(200)
    client, csrf_token, user, _ = login_first_user_with_register
    user_id = user.id
    rate_limit_key = f"email-change:{user_id}"

    for index in range(USER_CONSTANTS.MAX_EMAIL_CHANGES_PER_DAY):
        response = client.put(
            url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
            json=_change_email_payload(new_email=f"new_{index}@example.com"),
            headers={"X-CSRFToken": csrf_token},
        )
        assert response.status_code == 200

    blocked = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(new_email="new_blocked@example.com"),
        headers={"X-CSRFToken": csrf_token},
    )
    assert blocked.status_code == 429
    blocked_json = blocked.get_json()
    assert blocked_json[STD_JSON.ERROR_CODE] == ChangeEmailErrorCodes.RATE_LIMITED
    assert blocked_json[STD_JSON.MESSAGE] == EMAIL_CHANGE_RATE_LIMITED

    assert (
        provide_redis.get(rate_limit_key)
        == str(USER_CONSTANTS.MAX_EMAIL_CHANGES_PER_DAY).encode()
    )
    ttl = provide_redis.ttl(rate_limit_key)
    assert 0 < ttl <= USER_CONSTANTS.EMAIL_CHANGE_WINDOW_SECONDS


@mock.patch(_SEND_TARGET)
def test_change_email_taken_probes_bounded_by_per_day_cap(
    mock_send: mock.MagicMock,
    provide_redis: Redis | None,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """Email-enumeration is bounded to the daily cap (DD-1): each of
    ``MAX_EMAIL_CHANGES_PER_DAY`` taken-email probes returns 400 EMAIL_TAKEN and
    burns one slot, so the next attempt — taken or not — returns 429
    RATE_LIMITED. No confirmation email is ever sent for a taken probe."""
    if provide_redis is None:
        pytest.skip("Requires a real Redis instance (Docker stack)")

    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    taken_email = _seed_second_user(app)
    rate_limit_key = f"email-change:{user_id}"

    for _ in range(USER_CONSTANTS.MAX_EMAIL_CHANGES_PER_DAY):
        probe = client.put(
            url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
            json=_change_email_payload(new_email=taken_email),
            headers={"X-CSRFToken": csrf_token},
        )
        assert probe.status_code == 400
        assert (
            probe.get_json()[STD_JSON.ERROR_CODE] == ChangeEmailErrorCodes.EMAIL_TAKEN
        )

    # The cap is now reached from taken probes alone; the next attempt is
    # rejected at the precheck before any uniqueness probe or send.
    blocked = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(new_email=taken_email),
        headers={"X-CSRFToken": csrf_token},
    )
    assert blocked.status_code == 429
    assert blocked.get_json()[STD_JSON.ERROR_CODE] == ChangeEmailErrorCodes.RATE_LIMITED

    # A fresh (untaken) address is likewise blocked — proving the bound is the
    # daily cap, not an artifact of the address being taken.
    blocked_fresh = client.put(
        url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
        json=_change_email_payload(new_email="never_probed@example.com"),
        headers={"X-CSRFToken": csrf_token},
    )
    assert blocked_fresh.status_code == 429
    assert (
        blocked_fresh.get_json()[STD_JSON.ERROR_CODE]
        == ChangeEmailErrorCodes.RATE_LIMITED
    )

    assert (
        provide_redis.get(rate_limit_key)
        == str(USER_CONSTANTS.MAX_EMAIL_CHANGES_PER_DAY).encode()
    )
    mock_send.assert_not_called()


@mock.patch(_SEND_TARGET)
def test_change_email_fails_open_when_rate_limit_redis_errors(
    mock_send: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """When the rate-limit Redis client raises, the change still succeeds (200) —
    the cap is anti-spam, not a security boundary (fail-open)."""
    mock_send.return_value = _build_mock_email_response(200)
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
            url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
            json=_change_email_payload(),
            headers={"X-CSRFToken": csrf_token},
        )

    assert response.status_code == 200
    assert response.get_json()[STD_JSON.STATUS] == STD_JSON.SUCCESS
    with app.app_context():
        assert Users.query.get(user_id).pending_email == _NEW_EMAIL


@mock.patch(_SEND_TARGET)
def test_change_email_taken_branch_fails_open_when_rate_limit_redis_errors(
    mock_send: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
) -> None:
    """The taken-email slot-burn INCR (DD-1) is fail-open: when the rate-limit
    Redis client raises, a taken-email probe still returns its 400 EMAIL_TAKEN
    field error (not a 500) — a Redis outage must never block the response."""
    client, csrf_token, user, app = login_first_user_with_register
    user_id = user.id
    taken_email = _seed_second_user(app)

    raising_client = mock.MagicMock()
    raising_client.get.side_effect = Exception("redis down")
    raising_client.incr.side_effect = Exception("redis down")

    with mock.patch(
        "backend.users.services.account_service._build_rate_limit_redis",
        return_value=raising_client,
    ):
        response = client.put(
            url_for(ROUTES.USERS.CHANGE_EMAIL, user_id=user_id),
            json=_change_email_payload(new_email=taken_email),
            headers={"X-CSRFToken": csrf_token},
        )

    assert response.status_code == 400
    assert response.get_json()[STD_JSON.ERROR_CODE] == ChangeEmailErrorCodes.EMAIL_TAKEN
    with app.app_context():
        assert Users.query.get(user_id).pending_email is None
    mock_send.assert_not_called()
