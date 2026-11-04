from backend.api_common.responses import FlaskResponse


def no_store(response: FlaskResponse) -> FlaskResponse:
    """Stamp ``Cache-Control: no-store`` on a response that carries a token."""
    flask_response, status_code = response
    flask_response.headers["Cache-Control"] = "no-store"
    return flask_response, status_code
