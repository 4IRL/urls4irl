from typing import Tuple
from unittest import mock
from flask import Flask, url_for
from flask.testing import FlaskClient
import pytest

from src.models.contact_form_entries import ContactFormEntries
from src.models.users import Users
from src.utils.all_routes import ROUTES
from src.utils.strings.form_strs import CONTACT_FORM
from src.utils.strings.html_identifiers import IDENTIFIERS
from src.utils.strings.json_strs import FIELD_REQUIRED_STR
from src.utils.strings.url_validation_strs import USER_AGENT
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


@mock.patch("src.extensions.notifications.notifications._send_msg")
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
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US),
        headers=HEADERS,
        data={
            CONTACT_FORM.SUBJECT: MOCK_SUBJECT,
            CONTACT_FORM.CONTENT: MOCK_CONTENT,
            CONTACT_FORM.CSRF_TOKEN: csrf,
        },
    )

    assert response.status_code == 200
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


@mock.patch("src.extensions.notifications.notifications._send_msg")
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
        client.get(url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US)).get_data()
    )

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US),
        headers=HEADERS,
        data={
            CONTACT_FORM.SUBJECT: MOCK_SUBJECT,
            CONTACT_FORM.CONTENT: MOCK_CONTENT,
            CONTACT_FORM.CSRF_TOKEN: csrf,
        },
    )

    assert response.status_code == 200
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


@mock.patch("src.extensions.notifications.notifications._send_msg")
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
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US),
        headers=HEADERS,
        data={
            CONTACT_FORM.SUBJECT: MOCK_SUBJECT,
            CONTACT_FORM.CONTENT: MOCK_CONTENT,
            CONTACT_FORM.CSRF_TOKEN: csrf,
        },
    )

    assert response.status_code == 200
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
    "empty_field",
    [
        CONTACT_FORM.SUBJECT,
        CONTACT_FORM.CONTENT,
    ],
)
@mock.patch("src.extensions.notifications.notifications._send_msg")
def test_contact_us_page_form_empty_fields(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    empty_field: str,
):
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=200, text=None)

    data = {
        CONTACT_FORM.SUBJECT: MOCK_SUBJECT,
        CONTACT_FORM.CONTENT: MOCK_CONTENT,
        CONTACT_FORM.CSRF_TOKEN: csrf,
    }
    data[empty_field] = ""

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US), headers=HEADERS, data=data
    )

    assert response.status_code == 200
    assert FIELD_REQUIRED_STR.encode() in response.data
    mock_send_msg.assert_not_called()

    with app.app_context():
        assert ContactFormEntries.query.count() == 0


@pytest.mark.parametrize(
    "missing_field",
    [
        CONTACT_FORM.SUBJECT,
        CONTACT_FORM.CONTENT,
    ],
)
@mock.patch("src.extensions.notifications.notifications._send_msg")
def test_contact_us_page_form_missing_fields(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
    missing_field: str,
):
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=200, text=None)

    data = {
        CONTACT_FORM.SUBJECT: MOCK_SUBJECT,
        CONTACT_FORM.CONTENT: MOCK_CONTENT,
        CONTACT_FORM.CSRF_TOKEN: csrf,
    }
    data.pop(missing_field)

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US), headers=HEADERS, data=data
    )

    assert response.status_code == 200
    assert FIELD_REQUIRED_STR.encode() in response.data
    mock_send_msg.assert_not_called()

    with app.app_context():
        assert ContactFormEntries.query.count() == 0


@mock.patch("src.extensions.notifications.notifications._send_msg")
def test_contact_us_page_form_missing_csrf_token(
    mock_send_msg: mock.MagicMock,
    login_first_user_with_register: Tuple[FlaskClient, str, Users, Flask],
):
    client, csrf, user, app = login_first_user_with_register
    mock_send_msg.return_value = mock.Mock(response=True, status_code=200, text=None)

    data = {
        CONTACT_FORM.SUBJECT: MOCK_SUBJECT,
        CONTACT_FORM.CONTENT: MOCK_CONTENT,
    }

    response = client.post(
        url_for(ROUTES.ACCOUNT_AND_SETTINGS.CONTACT_US), headers=HEADERS, data=data
    )

    assert response.status_code == 403
    assert response.content_type == "text/html; charset=utf-8"
    assert IDENTIFIERS.HTML_403.encode() in response.data
    mock_send_msg.assert_not_called()

    with app.app_context():
        assert ContactFormEntries.query.count() == 0


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
