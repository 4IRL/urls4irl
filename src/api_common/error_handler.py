from flask import render_template
from flask_login import current_user

from src.app_logger import warning_log
from src.utils.strings.html_identifiers import IDENTIFIERS


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


def handle_404_response(_):
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
