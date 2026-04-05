from flask import render_template, request
from flask_login import current_user
from werkzeug.exceptions import NotFound

from backend.app_logger import warning_log
from backend.schemas.errors import build_message_error_response
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import FAILURE_GENERAL
from backend.utils.strings.url_validation_strs import URL_VALIDATION


def handle_403_response_from_csrf(_):
    user_id = -1 if not current_user.is_authenticated else current_user.id
    warning_log(f"CSRF token expired for User={user_id}")
    return (
        render_template(
            "error_pages/error_response.html",
            error_code=403,
            header=IDENTIFIERS.HTML_403,
        ),
        403,
    )


def handle_404_response(_: NotFound):
    if (
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
    return (
        render_template(
            "error_pages/error_response.html",
            error_code=429,
            header=IDENTIFIERS.HTML_429,
        ),
        429,
    )
