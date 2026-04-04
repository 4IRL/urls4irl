from typing import Tuple
from unittest import mock
from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from backend import limiter
from backend.api_common.request_errors import max_length_message, min_length_message
from backend.contact.constants import CONTACT_FORM_CONSTANTS
from backend.models.contact_form_entries import ContactFormEntries
from backend.models.users import Users
from backend.schemas.contact import ContactResponseSchema
from backend.utils.all_routes import ROUTES
from backend.utils.strings.html_identifiers import IDENTIFIERS
from backend.utils.strings.json_strs import FIELD_REQUIRED_STR
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.url_validation_strs import USER_AGENT
from tests.utils_for_test import get_csrf_token

pytestmark = pytest.mark.account_and_support

MOCK_USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36"
HEADERS = {USER_AGENT: MOCK_USER_AGENT}
MOCK_SUBJECT = "Mock Contact Form Subject"
MOCK_CONTENT = "Mock Content" * 8


def test_contact_us_page_opens_logged_in_user(login_first_user_with_register):
    """
    GIVEN a logged in user
    WHEN they open the contact form page.
    THEN verify that the correct HTML is in the response.
    """

    client, _, _, _ = login_first_user_with_register

    contact_page_response = client.get(url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US))
    assert (
        '<h1 id="ContactTitle">Contact Us</h1>'.encode() in contact_page_response.data
    )


def test_contact_us_page_opens_anonymous_user(logged_out_app, client):
    """
    GIVEN an anonymous user
    WHEN they open the contact form page.
    THEN verify that the correct HTML is in the response.
    """
    contact_page_response = client.get(url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US))
    assert (
        '<h1 id="ContactTitle">Contact Us</h1>'.encode() in contact_page_response.data
    )


@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_page_sends_notification_logged_in_user(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user sending a contact form entry
    WHEN they submit the contact form entry
    THEN verify that the contact form entry is saved in the database and all responses are valid
    """
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=204, text=None)

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json={
            "subject": MOCK_SUBJECT,
            "content": MOCK_CONTENT,
        },
        headers={**HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == "Sent! Thanks for reaching out."
    mock_send_msg.assert_called_once()

    with app.app_context():
        assert ContactFormEntries.query.count() == 1
        contact_form_entry: ContactFormEntries = ContactFormEntries.query.first()
        _assert_valid_contact_form_entry(
            entry=contact_form_entry,
            subject=MOCK_SUBJECT,
            content=MOCK_CONTENT,
            user_agent=MOCK_USER_AGENT,
        )


@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_page_sends_notification_anonymous_user(
    mock_send_msg: mock.MagicMock, logged_out_app, client
):
    """
    GIVEN a non-logged in user sending a contact form entry
    WHEN they submit the contact form entry
    THEN verify that the contact form entry is saved in the database and all responses are valid
    """
    mock_send_msg.return_value = mock.Mock(response=True, status_code=204, text=None)

    csrf = get_csrf_token(
        client.get(url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US)).get_data(),
        meta_tag=True,
    )

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json={
            "subject": MOCK_SUBJECT,
            "content": MOCK_CONTENT,
        },
        headers={**HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == "Sent! Thanks for reaching out."
    mock_send_msg.assert_called_once()

    with logged_out_app.app_context():
        assert ContactFormEntries.query.count() == 1
        contact_form_entry: ContactFormEntries = ContactFormEntries.query.first()
        _assert_valid_contact_form_entry(
            entry=contact_form_entry,
            subject=MOCK_SUBJECT,
            content=MOCK_CONTENT,
            user_agent=MOCK_USER_AGENT,
        )


@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_page_notification_fails(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user sending a contact form entry
    WHEN they submit the contact form entry but delivery to the Discord Webhook fails
    THEN verify that the contact form entry is saved in the database and all responses are valid
    """
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=400, text=None)

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json={
            "subject": MOCK_SUBJECT,
            "content": MOCK_CONTENT,
        },
        headers={**HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 200
    assert response.content_type == "application/json"
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
    assert response_json[STD_JSON.MESSAGE] == "Sent! Thanks for reaching out."
    mock_send_msg.assert_called_once()

    with app.app_context():
        assert ContactFormEntries.query.count() == 1
        contact_form_entry: ContactFormEntries = ContactFormEntries.query.first()
        _assert_valid_contact_form_entry(
            entry=contact_form_entry,
            subject=MOCK_SUBJECT,
            content=MOCK_CONTENT,
            user_agent=MOCK_USER_AGENT,
            delivered=False,
        )


@pytest.mark.parametrize(
    "empty_field, expected_error",
    [
        ("subject", min_length_message(CONTACT_FORM_CONSTANTS.MIN_SUBJECT_LENGTH)),
        ("content", FIELD_REQUIRED_STR),
    ],
)
@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_page_form_empty_fields(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    empty_field: str,
    expected_error: str,
):
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=200, text=None)

    json_body = {
        "subject": MOCK_SUBJECT,
        "content": MOCK_CONTENT,
    }
    json_body[empty_field] = ""

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json=json_body,
        headers={**HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert empty_field in response_json[STD_JSON.ERRORS]
    assert expected_error in response_json[STD_JSON.ERRORS][empty_field]
    mock_send_msg.assert_not_called()

    with app.app_context():
        assert ContactFormEntries.query.count() == 0


@pytest.mark.parametrize(
    "missing_field",
    [
        "subject",
        "content",
    ],
)
@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_page_form_missing_fields(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    missing_field: str,
):
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=200, text=None)

    json_body = {
        "subject": MOCK_SUBJECT,
        "content": MOCK_CONTENT,
    }
    json_body.pop(missing_field)

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json=json_body,
        headers={**HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert missing_field in response_json[STD_JSON.ERRORS]
    assert FIELD_REQUIRED_STR in response_json[STD_JSON.ERRORS][missing_field]
    mock_send_msg.assert_not_called()

    with app.app_context():
        assert ContactFormEntries.query.count() == 0


@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_page_form_subject_too_short(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user submitting a contact form
    WHEN the subject is shorter than the minimum length
    THEN verify that a 400 response is returned with a min-length error for the subject field
    """
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=200, text=None)

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json={
            "subject": "Hi",
            "content": MOCK_CONTENT,
        },
        headers={**HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert "subject" in response_json[STD_JSON.ERRORS]
    expected_error = min_length_message(CONTACT_FORM_CONSTANTS.MIN_SUBJECT_LENGTH)
    assert expected_error in response_json[STD_JSON.ERRORS]["subject"]
    mock_send_msg.assert_not_called()

    with app.app_context():
        assert ContactFormEntries.query.count() == 0


@pytest.mark.parametrize(
    "over_max_field, field_max_length",
    [
        ("subject", CONTACT_FORM_CONSTANTS.MAX_SUBJECT_LENGTH),
        ("content", CONTACT_FORM_CONSTANTS.MAX_CONTENT_LENGTH),
    ],
)
@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_page_form_field_exceeds_max_length(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    over_max_field: str,
    field_max_length: int,
):
    """
    GIVEN a logged in user submitting a contact form
    WHEN a field exceeds its maximum allowed length
    THEN verify that a 400 response is returned with a max-length error for that field
    """
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=200, text=None)

    json_body = {
        "subject": MOCK_SUBJECT,
        "content": MOCK_CONTENT,
    }
    json_body[over_max_field] = "a" * (field_max_length + 1)

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json=json_body,
        headers={**HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 400
    response_json = response.get_json()
    assert response_json[STD_JSON.STATUS] == STD_JSON.FAILURE
    assert over_max_field in response_json[STD_JSON.ERRORS]
    expected_error = max_length_message(field_max_length)
    assert expected_error in response_json[STD_JSON.ERRORS][over_max_field]
    mock_send_msg.assert_not_called()

    with app.app_context():
        assert ContactFormEntries.query.count() == 0


@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_invalid_submissions_do_not_count_toward_rate_limit(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user who has submitted several invalid contact forms
    WHEN they submit a valid contact form after exceeding what would be the rate limit
    THEN verify the valid submission succeeds because invalid attempts are not rate-limited
    """
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=204, text=None)

    _enable_limiter(app)
    try:
        rate_limit_count = CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_HOUR + 1
        for _ in range(rate_limit_count):
            invalid_response = client.post(
                url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
                json={"subject": "", "content": ""},
                headers={**HEADERS, "X-CSRFToken": csrf},
            )
            assert invalid_response.status_code == 400

        valid_response = client.post(
            url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
            json={"subject": MOCK_SUBJECT, "content": MOCK_CONTENT},
            headers={**HEADERS, "X-CSRFToken": csrf},
        )

        assert valid_response.status_code == 200
        response_json = valid_response.get_json()
        assert response_json[STD_JSON.STATUS] == STD_JSON.SUCCESS
        mock_send_msg.assert_called_once()

        with app.app_context():
            assert ContactFormEntries.query.count() == 1
    finally:
        _disable_limiter()


@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_valid_submissions_are_rate_limited(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user
    WHEN they submit RATE_LIMIT_PER_HOUR valid contact forms
    THEN verify the next valid submission returns 429 Too Many Requests
    """
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=204, text=None)

    _enable_limiter(app)
    try:
        for submission_idx in range(CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_HOUR):
            response = client.post(
                url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
                json={"subject": MOCK_SUBJECT, "content": MOCK_CONTENT},
                headers={**HEADERS, "X-CSRFToken": csrf},
            )
            assert response.status_code == 200, (
                f"Submission {submission_idx + 1} of "
                f"{CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_HOUR} should succeed"
            )

        rate_limited_response = client.post(
            url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
            json={"subject": MOCK_SUBJECT, "content": MOCK_CONTENT},
            headers={**HEADERS, "X-CSRFToken": csrf},
        )

        assert rate_limited_response.status_code == 429
        assert mock_send_msg.call_count == CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_HOUR

        with app.app_context():
            assert (
                ContactFormEntries.query.count()
                == CONTACT_FORM_CONSTANTS.RATE_LIMIT_PER_HOUR
            )
    finally:
        _disable_limiter()


@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_page_form_missing_csrf_token(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=200, text=None)

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json={
            "subject": MOCK_SUBJECT,
            "content": MOCK_CONTENT,
        },
        headers=HEADERS,
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    mock_send_msg.assert_not_called()

    with app.app_context():
        assert ContactFormEntries.query.count() == 0


def _enable_limiter(app: Flask) -> None:
    """Enable the rate limiter with a properly initialized storage backend.

    Flask 3.x prevents ``before_request`` registration after the first request.
    We temporarily reset ``_got_first_request`` so ``limiter.init_app`` can
    register its ``before_request`` hook, then restore the flag.
    """
    original_first_request = app._got_first_request
    app._got_first_request = False
    app.config["RATELIMIT_ENABLED"] = True
    limiter.enabled = True
    limiter.init_app(app)
    app._got_first_request = original_first_request


def _disable_limiter() -> None:
    """Disable the rate limiter and clear its storage backend."""
    if limiter._storage is not None:
        limiter._storage.reset()
    limiter._storage = None
    limiter._limiter = None
    limiter.enabled = False
    limiter.initialized = False


def _assert_valid_contact_form_entry(
    entry: ContactFormEntries,
    subject: str,
    content: str,
    user_agent: str,
    delivered: bool = True,
):
    comparison_entry = ContactFormEntries(subject, content, user_agent)
    assert comparison_entry.user_id == entry.user_id
    assert comparison_entry.os == entry.os
    assert comparison_entry.browser == entry.browser
    assert comparison_entry.browser_version == entry.browser_version
    assert comparison_entry.device == entry.device
    assert delivered == entry.delivered
    assert comparison_entry.subject == entry.subject
    assert comparison_entry.content == entry.content
    assert comparison_entry.user_agent_hash == entry.user_agent_hash


@mock.patch("backend.extensions.notifications.notifications._send_msg")
def test_contact_us_response_conforms_to_schema(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    """
    GIVEN a logged in user submitting a valid contact form
    WHEN the server processes the submission successfully
    THEN ensure the 200 JSON response conforms to ContactResponseSchema
    """
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=204, text=None)

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US_SUBMIT),
        json={
            "subject": MOCK_SUBJECT,
            "content": MOCK_CONTENT,
        },
        headers={**HEADERS, "X-CSRFToken": csrf},
    )

    assert response.status_code == 200
    response_json = response.get_json()

    # Validate response conforms to declared schema
    validated = ContactResponseSchema.model_validate(response_json)
    assert validated is not None

    # Verify response keys match schema's aliased field names
    expected_keys = {
        field_info.alias or field_name
        for field_name, field_info in ContactResponseSchema.model_fields.items()
    }
    assert set(response_json.keys()) == expected_keys

    # Verify both status and message are present
    assert STD_JSON.STATUS in response_json
    assert STD_JSON.MESSAGE in response_json
