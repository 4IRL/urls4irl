from flask import render_template, request
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from werkzeug.exceptions import NotFound

from backend.app_logger import warning_log
from backend.schemas.errors import build_message_error_response
from backend.utils.strings.api_auth_strs import API_V1_URL_PREFIX
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import FAILURE_GENERAL, STD_JSON_RESPONSE
from backend.utils.strings.url_validation_strs import URL_VALIDATION


def _is_api_v1_request() -> bool:
    """True when the current request targets the bearer-token /api/v1 surface.

    Checked in the app-level handlers because an unmatched /api/v1 path never
    enters any blueprint, so blueprint-scoped errorhandlers cannot catch it —
    API clients must receive JSON regardless of their Accept header.
    """
    return request.path.startswith(API_V1_URL_PREFIX)


def handle_403_response_from_csrf(csrf_error: CSRFError):
    user_id = -1 if not current_user.is_authenticated else current_user.id
    warning_log(f"CSRF validation failed for User={user_id}: {csrf_error.description}")
    if _is_api_v1_request():
        return build_message_error_response(
            message=FAILURE_GENERAL.NOT_AUTHORIZED, status_code=403
        )
    return (
        render_template(
            "error_pages/error_response.html",
            error_code=403,
            header=IDENTIFIERS.HTML_403,
        ),
        403,
    )


def handle_404_response(_: NotFound):
    if _is_api_v1_request() or (
        request.headers.get(URL_VALIDATION.X_REQUESTED_WITH)
        == URL_VALIDATION.XMLHTTPREQUEST
    ):
        return build_message_error_response(
            message=FAILURE_GENERAL.NOT_FOUND, status_code=404
        )

    return (
        render_template(
            "error_pages/error_response.html",
            error_code=404,
            header=IDENTIFIERS.HTML_404,
        ),
        404,
    )


def handle_429_response_default_ratelimit(_):
    if _is_api_v1_request():
        return build_message_error_response(
            message=STD_JSON_RESPONSE.TOO_MANY_REQUESTS, status_code=429
        )
    return (
        render_template(
            "error_pages/error_response.html",
            error_code=429,
            header=IDENTIFIERS.HTML_429,
        ),
        429,
    )
