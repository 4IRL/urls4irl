from flask import render_template, jsonify, make_response
from flask_login import current_user

from src.app_logger import warning_log
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import STD_JSON_RESPONSE


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
    return make_response(
        jsonify(
            {
                STD_JSON_RESPONSE.STATUS: STD_JSON_RESPONSE.FAILURE,
                STD_JSON_RESPONSE.MESSAGE: STD_JSON_RESPONSE.TOO_MANY_REQUESTS,
            }
        ),
        429,
    )
