from urllib.parse import parse_qs, urlencode, urlparse
from flask import request, url_for
from flask_login import current_user, login_user
from werkzeug.security import check_password_hash, generate_password_hash
from backend.api_common.responses import APIResponse, FlaskResponse
from backend.app_logger import safe_add_log, warning_log
from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.models.users import Users
from backend.models.utub_members import Utub_Members
from backend.schemas.errors import (
    build_field_error_response,
    build_message_error_response,
)
from backend.schemas.users import LoginRedirectResponseSchema
from backend.splash.constants import (
    LOGIN_FAILURE_REASON_BAD_PASSWORD,
    LOGIN_FAILURE_REASON_EMAIL_UNVERIFIED,
    LOGIN_FAILURE_REASON_OAUTH_ONLY,
    LOGIN_FAILURE_REASON_SUSPENDED,
    LOGIN_FAILURE_REASON_UNKNOWN_USER,
    LoginErrorCodes,
)
from backend.utils.all_routes import ROUTES
from backend.utils.strings.user_strs import USER_FAILURE
from backend.utils.strings.utub_strs import UTUB_ID_QUERY_PARAM

DUMMY_HASH = generate_password_hash("__dummy__")


def login_user_to_u4i(username: str, password: str) -> FlaskResponse:
    user: Users | None = Users.query.filter(Users.username == username).first()

    if not user:
        warning_log("User not found on login")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_UNKNOWN_USER},
        )
        return build_field_error_response(
            message=USER_FAILURE.UNABLE_TO_LOGIN,
            errors={"username": [USER_FAILURE.USER_NOT_EXIST]},
            error_code=LoginErrorCodes.INVALID_FORM_INPUT,
        )

    if user.password is None:
        warning_log("OAuth-only user attempted password login")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_OAUTH_ONLY},
        )
        # Return a response byte-identical to a genuine wrong-password attempt so
        # an attacker cannot fingerprint password-less (OAuth-only) accounts. The
        # OAuth steer lives in the shared INVALID_PASSWORD message every failed
        # login sees; only the internal metrics reason distinguishes this case.
        # Spend the same bcrypt time the wrong-password branch does so the two
        # branches are indistinguishable by wall-clock latency as well as bytes.
        # The result is intentionally discarded — only the elapsed time matters.
        check_password_hash(DUMMY_HASH, password)
        return build_field_error_response(
            message=USER_FAILURE.UNABLE_TO_LOGIN,
            errors={"password": [USER_FAILURE.INVALID_PASSWORD]},
            error_code=LoginErrorCodes.INVALID_FORM_INPUT,
        )

    if not user.is_password_correct(password):
        warning_log("User entered wrong password on login")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_BAD_PASSWORD},
        )
        return build_field_error_response(
            message=USER_FAILURE.UNABLE_TO_LOGIN,
            errors={"password": [USER_FAILURE.INVALID_PASSWORD]},
            error_code=LoginErrorCodes.INVALID_FORM_INPUT,
        )

    if user.is_suspended:
        # Blocked BEFORE login_user(): a suspended user never reaches an
        # authenticated session. Only a correct password reaches this branch,
        # so suspension status is never leaked to a guessing attacker.
        warning_log(f"Suspended User={user.id} attempted login")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_SUSPENDED},
        )
        return build_message_error_response(
            message=USER_FAILURE.ACCOUNT_SUSPENDED,
            error_code=LoginErrorCodes.ACCOUNT_SUSPENDED,
            status_code=403,
        )

    # Log in before email_validated check so unvalidated users can request a resend
    login_user(user)  # Can add Remember Me functionality here

    if not user.email_validated:
        warning_log(f"User={user.id} not email validated")
        record_event(
            EventName.LOGIN_FAILURE,
            dimensions={"reason": LOGIN_FAILURE_REASON_EMAIL_UNVERIFIED},
        )
        return build_message_error_response(
            message=USER_FAILURE.ACCOUNT_CREATED_EMAIL_NOT_VALIDATED,
            error_code=LoginErrorCodes.ACCOUNT_NOT_EMAIL_VALIDATED,
            status_code=401,
        )

    safe_add_log(f"Logging User.id={user.id} in")

    # next query param takes user to the page they wanted to originally before being logged in
    next_page = verify_and_provide_next_page(request.args.to_dict())
    redirect_url = next_page if next_page else url_for(ROUTES.UTUBS.HOME)

    record_event(EventName.LOGIN_SUCCESS, dimensions={"method": "password"})

    return APIResponse(
        status_code=200,
        data=LoginRedirectResponseSchema(redirect_url=redirect_url),
    ).to_response()


def verify_and_provide_next_page(request_args: dict[str, str]) -> str:
    url = ""
    if _has_invalid_next_query_param(request_args):
        return url

    rel_url = urlparse(request_args.get("next"))
    if rel_url.path != url_for(ROUTES.UTUBS.HOME):
        return url

    query_params = parse_qs(str(rel_url.query))
    if len(query_params) != 1 or UTUB_ID_QUERY_PARAM not in query_params:
        return url

    utub_id_vals = query_params.get(UTUB_ID_QUERY_PARAM, None)
    if not utub_id_vals or len(utub_id_vals) != 1:
        return url

    utub_id = utub_id_vals[0]

    if not utub_id.isdigit() or int(utub_id) <= 0:
        return url

    if Utub_Members.query.get((int(utub_id), current_user.id)) is None:
        return url

    url = (
        f"{url_for(ROUTES.UTUBS.HOME)}?{urlencode({UTUB_ID_QUERY_PARAM: int(utub_id)})}"
    )
    safe_add_log(f"Routing user to UTub.id={utub_id}")
    return url


def _has_invalid_next_query_param(request_args: dict[str, str]) -> bool:
    return (
        len(request_args) != 1
        or "next" not in request_args
        or not isinstance(request_args.get("next"), str)
    )
