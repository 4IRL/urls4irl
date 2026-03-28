import pytest

from backend.schemas.errors import (
    ErrorResponse,
    build_detail_error_response,
    build_field_error_response,
    build_message_error_response,
    build_url_conflict_error_response,
)

pytestmark = pytest.mark.unit


def test_error_response_message_only(app):
    """
    GIVEN an ErrorResponse with only a message
    WHEN to_response() is called with status 400
    THEN the JSON payload equals {"status": "Failure", "message": "Not allowed."}
        with no errors, details, errorCode, or urlString keys present
    """
    error = ErrorResponse(message="Not allowed.")
    with app.app_context():
        response, status_code = error.to_response(400)
        payload = response.get_json()

    assert status_code == 400
    assert payload == {"status": "Failure", "message": "Not allowed."}
    assert "errors" not in payload
    assert "details" not in payload
    assert "errorCode" not in payload
    assert "urlString" not in payload


def test_error_response_with_field_errors(app):
    """
    GIVEN an ErrorResponse with field_errors
    WHEN to_response() is called
    THEN the payload includes the errors dict under the "errors" key
    """
    error = ErrorResponse(
        message="Bad input.",
        field_errors={"username": ["User not found."]},
    )
    with app.app_context():
        response, status_code = error.to_response(400)
        payload = response.get_json()

    assert payload["errors"] == {"username": ["User not found."]}


def test_error_response_with_error_detail(app):
    """
    GIVEN an ErrorResponse with error_detail
    WHEN to_response() is called
    THEN the payload includes the details string under the "details" key
    """
    error = ErrorResponse(
        message="Invalid URL",
        error_detail="URL contains credentials",
    )
    with app.app_context():
        response, status_code = error.to_response(400)
        payload = response.get_json()

    assert payload["details"] == "URL contains credentials"


def test_error_response_with_error_code(app):
    """
    GIVEN an ErrorResponse with error_code
    WHEN to_response() is called
    THEN the payload includes the errorCode integer under the "errorCode" key
    """
    error = ErrorResponse(message="Error occurred.", error_code=2)
    with app.app_context():
        response, status_code = error.to_response(400)
        payload = response.get_json()

    assert payload["errorCode"] == 2


def test_error_response_with_url_string(app):
    """
    GIVEN an ErrorResponse with url_string
    WHEN to_response() is called
    THEN the payload includes the urlString at the top level
    """
    error = ErrorResponse(
        message="URL conflict.",
        url_string="https://example.com",
    )
    with app.app_context():
        response, status_code = error.to_response(409)
        payload = response.get_json()

    assert payload["urlString"] == "https://example.com"


def test_error_response_excludes_none_fields(app):
    """
    GIVEN an ErrorResponse with only a message (all optional fields are None)
    WHEN to_response() is called
    THEN the errors, details, errorCode, and urlString keys are absent
    """
    error = ErrorResponse(message="Simple error.")
    with app.app_context():
        response, status_code = error.to_response(400)
        payload = response.get_json()

    assert "errors" not in payload
    assert "details" not in payload
    assert "errorCode" not in payload
    assert "urlString" not in payload


def test_error_response_status_is_failure(app):
    """
    GIVEN any ErrorResponse
    WHEN to_response() is called
    THEN the status field equals "Failure"
    """
    error = ErrorResponse(message="Any error.")
    with app.app_context():
        response, status_code = error.to_response(400)
        payload = response.get_json()

    assert payload["status"] == "Failure"


def test_build_field_error_response(app):
    """
    GIVEN a call to build_field_error_response with message, errors, and error_code
    WHEN the response is built
    THEN the payload has status, message, errorCode, and errors keys with correct
        values, and the HTTP status is 400
    """
    with app.app_context():
        response, status_code = build_field_error_response(
            message="Unable to login",
            errors={"username": ["User not found."]},
            error_code=2,
        )
        payload = response.get_json()

    assert status_code == 400
    assert payload["status"] == "Failure"
    assert payload["message"] == "Unable to login"
    assert payload["errorCode"] == 2
    assert payload["errors"] == {"username": ["User not found."]}


def test_build_field_error_response_without_error_code(app):
    """
    GIVEN a call to build_field_error_response with error_code=None
    WHEN the response is built
    THEN the errorCode key is absent from the payload
    """
    with app.app_context():
        response, status_code = build_field_error_response(
            message="Unable to login",
            errors={"username": ["User not found."]},
            error_code=None,
        )
        payload = response.get_json()

    assert status_code == 400
    assert "errorCode" not in payload
    assert payload["errors"] == {"username": ["User not found."]}


def test_build_message_error_response(app):
    """
    GIVEN a call to build_message_error_response with only a message
    WHEN the response is built
    THEN the payload has status and message only
    """
    with app.app_context():
        response, status_code = build_message_error_response(
            message="Not allowed.",
        )
        payload = response.get_json()

    assert status_code == 400
    assert payload == {"status": "Failure", "message": "Not allowed."}


def test_build_message_error_response_with_error_code(app):
    """
    GIVEN a call to build_message_error_response with error_code=1
    WHEN the response is built
    THEN the errorCode key is present in the payload
    """
    with app.app_context():
        response, status_code = build_message_error_response(
            message="Not allowed.",
            error_code=1,
        )
        payload = response.get_json()

    assert status_code == 400
    assert payload["errorCode"] == 1


def test_build_detail_error_response(app):
    """
    GIVEN a call to build_detail_error_response with message, details, and error_code
    WHEN the response is built
    THEN the details key is present as a plain string
    """
    with app.app_context():
        response, status_code = build_detail_error_response(
            message="Invalid URL",
            details="URL contains credentials",
            error_code=3,
        )
        payload = response.get_json()

    assert status_code == 400
    assert payload["details"] == "URL contains credentials"
    assert payload["message"] == "Invalid URL"
    assert payload["errorCode"] == 3


def test_build_url_conflict_error_response(app):
    """
    GIVEN a call to build_url_conflict_error_response with message, url_string,
        and error_code
    WHEN the response is built
    THEN the urlString key is present at top level and HTTP status is 409
    """
    with app.app_context():
        response, status_code = build_url_conflict_error_response(
            message="URL in UTub",
            url_string="https://example.com",
            error_code=6,
        )
        payload = response.get_json()

    assert status_code == 409
    assert payload["urlString"] == "https://example.com"
    assert payload["message"] == "URL in UTub"
    assert payload["errorCode"] == 6
