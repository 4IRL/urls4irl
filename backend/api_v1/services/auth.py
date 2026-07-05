from __future__ import annotations

from flask import current_app, url_for
from flask_login import current_user
from werkzeug.security import check_password_hash

from backend import db
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.api_v1.constants import ApiAuthErrorCodes
from backend.api_v1.services.google_tokens import verify_google_id_token
from backend.api_v1.services.tokens import (
    RefreshRotationStatus,
    create_access_token,
    issue_refresh_token,
    revoke_all_refresh_tokens_for_user,
    revoke_refresh_token_family,
    rotate_refresh_token,
)
from backend.app_logger import safe_add_log, warning_log
from backend.extensions.extension_utils import safe_get_email_sender
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.email_validations import Email_Validations
from backend.models.users import Users
from backend.schemas.api_v1 import ApiTokenPairResponseSchema, ApiUserProfileSchema
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.splash.constants import (
    LOGIN_FAILURE_REASON_BAD_PASSWORD,
    LOGIN_FAILURE_REASON_EMAIL_UNVERIFIED,
    LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION,
    LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE,
    LOGIN_FAILURE_REASON_OAUTH_ONLY,
    LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL,
    LOGIN_FAILURE_REASON_UNKNOWN_USER,
)
from backend.splash.services.oauth.account_service import (
    EmailAlreadyRegisteredError,
    find_or_create_oauth_user,
)
from backend.splash.services.oauth.constants import Provider

from backend.splash.services.oauth.google_service import resolve_preferred_username
from backend.splash.services.user_login import DUMMY_HASH
from backend.splash.services.validate_email import (
    build_response_for_email_attempts_rate_limited,
    build_response_for_max_email_attempts_sent,
    handle_email_sending_result,
)
from backend.utils.all_routes import ROUTES
from backend.utils.strings.api_auth_strs import API_AUTH_FAILURE, API_AUTH_SUCCESS
from backend.utils.strings.config_strs import CONFIG_ENVS
from backend.utils.strings.oauth_strs import (
    EMAIL_COLLISION_MESSAGE,
    UNVERIFIED_EMAIL_MESSAGE,
)
from backend.utils.strings.user_strs import USER_FAILURE

_LOGIN_METHOD_PASSWORD = "password"
_LOGIN_METHOD_GOOGLE = "google"


def _build_token_pair_response(*, user: Users) -> FlaskResponse:
    """Issue a fresh access + refresh pair (new family) for the user."""
    access_token = create_access_token(user=user)
    refresh_token = issue_refresh_token(user=user)
    return APIResponse(
        status_code=200,
        data=ApiTokenPairResponseSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=current_app.config[
                CONFIG_ENVS.API_ACCESS_TOKEN_LIFETIME_SECONDS
            ],
            user=ApiUserProfileSchema.model_validate(user),
        ),
    ).to_response()


def login_user_for_api(*, username: str, password: str) -> FlaskResponse:
    """Bearer-token login: mirrors the web login validation exactly, but
    issues a token pair instead of a session cookie.

    Per the design doc, tokens ARE issued for unvalidated-email accounts —
    the response's user.emailValidated tells the client to show its
    verify-email screen; validation-gated endpoints return 403 until then.
    """
    user: Users | None = Users.query.filter(Users.username == username).first()

    if not user:
        warning_log("User not found on /api/v1 login")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_UNKNOWN_USER},
        )
        return build_field_error_response(
            message=USER_FAILURE.UNABLE_TO_LOGIN,
            errors={"username": [USER_FAILURE.USER_NOT_EXIST]},
            error_code=ApiAuthErrorCodes.INVALID_FORM_INPUT,
        )

    if user.password is None:
        warning_log("OAuth-only user attempted password login on /api/v1")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_ONLY},
        )
        # Byte- and latency-identical to the wrong-password branch so
        # password-less (OAuth-only) accounts cannot be fingerprinted;
        # mirrors the web login service.
        check_password_hash(DUMMY_HASH, password)
        return build_field_error_response(
            message=USER_FAILURE.UNABLE_TO_LOGIN,
            errors={"password": [USER_FAILURE.INVALID_PASSWORD]},
            error_code=ApiAuthErrorCodes.INVALID_FORM_INPUT,
        )

    if not user.is_password_correct(password):
        warning_log("User entered wrong password on /api/v1 login")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
        )
        return build_field_error_response(
            message=USER_FAILURE.UNABLE_TO_LOGIN,
            errors={"password": [USER_FAILURE.INVALID_PASSWORD]},
            error_code=ApiAuthErrorCodes.INVALID_FORM_INPUT,
        )

    if not user.email_validated:
        # Tokens are still issued (unlike the web 401): LOGIN_SUCCESS is
        # reserved for the fully-validated path per the event registry, so
        # this branch records the same email_unverified failure the web does.
        warning_log(f"User={user.id} not email validated on /api/v1 login")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_EMAIL_UNVERIFIED},
        )
        return _build_token_pair_response(user=user)

    safe_add_log(f"Issuing /api/v1 token pair for User.id={user.id}")
    record_event(EventName.LOGIN_SUCCESS, dimensions={"method": _LOGIN_METHOD_PASSWORD})
    return _build_token_pair_response(user=user)


def refresh_api_tokens(*, refresh_token: str) -> FlaskResponse:
    """Rotate a refresh token: new access + refresh pair in the same family.

    Replay of a superseded token revokes the whole family (reuse detection)
    and returns a distinct error code so clients can force a re-login.
    """
    rotation_result = rotate_refresh_token(presented_token=refresh_token)

    if rotation_result.status == RefreshRotationStatus.REUSE_DETECTED:
        warning_log("Refresh token reuse detected on /api/v1 — family revoked")
        return build_message_error_response(
            message=API_AUTH_FAILURE.REFRESH_TOKEN_REUSE_DETECTED,
            error_code=ApiAuthErrorCodes.REFRESH_TOKEN_REUSE_DETECTED,
            status_code=401,
        )

    if rotation_result.status == RefreshRotationStatus.INVALID:
        warning_log("Invalid refresh token presented on /api/v1")
        return build_message_error_response(
            message=API_AUTH_FAILURE.INVALID_REFRESH_TOKEN,
            error_code=ApiAuthErrorCodes.INVALID_REFRESH_TOKEN,
            status_code=401,
        )

    rotated_user: Users = rotation_result.user
    access_token = create_access_token(user=rotated_user)
    return APIResponse(
        status_code=200,
        data=ApiTokenPairResponseSchema(
            access_token=access_token,
            refresh_token=rotation_result.new_refresh_token,
            token_type="Bearer",
            expires_in=current_app.config[
                CONFIG_ENVS.API_ACCESS_TOKEN_LIFETIME_SECONDS
            ],
            user=ApiUserProfileSchema.model_validate(rotated_user),
        ),
    ).to_response()


def logout_api_device(*, refresh_token: str) -> FlaskResponse:
    """Per-device logout: revoke the presented refresh token's family."""
    if not revoke_refresh_token_family(presented_token=refresh_token):
        return build_message_error_response(
            message=API_AUTH_FAILURE.INVALID_REFRESH_TOKEN,
            error_code=ApiAuthErrorCodes.INVALID_REFRESH_TOKEN,
            status_code=401,
        )
    return APIResponse(message=API_AUTH_SUCCESS.LOGGED_OUT).to_response()


def logout_api_everywhere() -> FlaskResponse:
    """Log out everywhere: revoke every refresh token for the bearer user."""
    revoked_count = revoke_all_refresh_tokens_for_user(user_id=current_user.id)
    safe_add_log(
        f"Revoked {revoked_count} refresh tokens for User.id={current_user.id}"
    )
    return APIResponse(message=API_AUTH_SUCCESS.LOGGED_OUT_EVERYWHERE).to_response()


def resend_validation_email_for_api() -> FlaskResponse:
    """JSON-only mirror of the web resend-validation flow for bearer clients.

    Reuses the Email_Validations attempt limits and the shared Mailjet result
    handling; differs only where the web flow redirects (already-validated
    accounts get a 400 JSON envelope instead).
    """
    current_email_validation: Email_Validations = Email_Validations.query.filter(
        Email_Validations.user_id == current_user.id
    ).first_or_404()

    if current_user.email_validated:
        warning_log(f"User={current_user.id} email already validated on /api/v1")
        db.session.delete(current_email_validation)
        db.session.commit()
        return build_message_error_response(
            message=API_AUTH_FAILURE.EMAIL_ALREADY_VALIDATED,
            status_code=400,
        )

    if current_email_validation.has_too_many_email_attempts():
        return build_response_for_max_email_attempts_sent()

    has_more_attempts = current_email_validation.increment_attempt()
    db.session.commit()

    if not has_more_attempts:
        return build_response_for_email_attempts_rate_limited(current_email_validation)

    email_sender = safe_get_email_sender(current_app)
    url_for_confirmation = url_for(
        ROUTES.SPLASH.VALIDATE_EMAIL,
        token=current_email_validation.validation_token,
        _external=True,
    )
    email_send_result = email_sender.send_account_email_confirmation(
        current_user.email, current_user.username, url_for_confirmation
    )
    return handle_email_sending_result(email_send_result)


def google_auth_for_api(*, id_token: str) -> FlaskResponse:
    """Native Google sign-in: verify the SDK-issued id_token, resolve or
    create the account, and issue the same token pair as the password flow."""
    claims = verify_google_id_token(id_token=id_token)

    if claims is None:
        warning_log("Unverifiable Google id_token presented on /api/v1")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_GENERIC_FAILURE},
        )
        return build_message_error_response(
            message=API_AUTH_FAILURE.UNABLE_TO_VERIFY_GOOGLE_TOKEN,
            error_code=ApiAuthErrorCodes.INVALID_GOOGLE_TOKEN,
            status_code=401,
        )

    if not claims.email_verified:
        warning_log("Google id_token with unverified email on /api/v1")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_UNVERIFIED_EMAIL},
        )
        return build_message_error_response(
            message=UNVERIFIED_EMAIL_MESSAGE,
            error_code=ApiAuthErrorCodes.INVALID_GOOGLE_TOKEN,
            status_code=403,
        )

    preferred_username = resolve_preferred_username(claims.name, claims.email)

    try:
        resolved_user = find_or_create_oauth_user(
            provider=Provider.GOOGLE,
            subject=claims.subject,
            email=claims.email,
            preferred_username=preferred_username,
        )
    except EmailAlreadyRegisteredError:
        warning_log("Google /api/v1 sign-in email collision with local account")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_EMAIL_COLLISION},
        )
        return build_message_error_response(
            message=EMAIL_COLLISION_MESSAGE,
            error_code=ApiAuthErrorCodes.OAUTH_EMAIL_COLLISION,
            status_code=409,
        )

    record_event(EventName.LOGIN_SUCCESS, dimensions={"method": _LOGIN_METHOD_GOOGLE})
    return _build_token_pair_response(user=resolved_user)
