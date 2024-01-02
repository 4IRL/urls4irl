from flask import render_template, jsonify, make_response
from src.utils.strings import IDENTIFIERS, STD_JSON_RESPONSE


def handle_404_response(e):
    return (
        render_template("error_pages/404_response.html", text=IDENTIFIERS.HTML_404),
        404,
    )

def handle_429_response_default_ratelimit(e):
    return make_response(
        jsonify({
        STD_JSON_RESPONSE.STATUS: STD_JSON_RESPONSE.FAILURE,
        STD_JSON_RESPONSE.MESSAGE: STD_JSON_RESPONSE.TOO_MANY_REQUESTS
    }), 429
    )
