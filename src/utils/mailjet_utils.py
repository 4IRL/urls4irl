import requests

from src.api_common.responses import APIResponse, FlaskResponse
from src.app_logger import error_log
from src.utils.strings.email_validation_strs import EMAILS


def handle_mailjet_failure(
    email_result: requests.Response, error_code: int = 1
) -> FlaskResponse:
    """
    Handles a failure from the Mailjet service.

    Args:
        email_result (requests.Response): A Response from the request sent to the Mailjet service.

    Response:
        (FlaskResponse): JSON response and HTTP status code
    """
    json_response = email_result.json()
    message = json_response.get(EMAILS.MESSAGES, EMAILS.ERROR_WITH_MAILJET)

    if message == EMAILS.ERROR_WITH_MAILJET:
        errors = message
    else:
        errors = message.get(EMAILS.MAILJET_ERRORS, EMAILS.ERROR_WITH_MAILJET)

    error_log(f"(4) Email failed to send: {errors}")

    return APIResponse(
        status_code=400,
        error_code=error_code,
        message=f"{EMAILS.ERROR_WITH_MAILJET} | {errors}",
    ).to_response()
