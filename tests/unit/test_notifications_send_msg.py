from unittest import mock

import pytest
import requests

from backend.extensions.notifications.notifications import NotificationType, _send_msg

pytestmark = pytest.mark.unit

NOTIFICATIONS_MODULE = "backend.extensions.notifications.notifications"
INJECTED_ERROR_MSG = "connection reset\nWARNING forged log line"


def _logged_messages(mock_logger: mock.MagicMock) -> list[str]:
    return [call.args[0] for call in mock_logger.call_args_list]


@pytest.mark.parametrize(
    "raised_error",
    [
        requests.exceptions.ConnectionError(INJECTED_ERROR_MSG),
        RuntimeError(INJECTED_ERROR_MSG),
    ],
)
@mock.patch(f"{NOTIFICATIONS_MODULE}.logging.warning")
@mock.patch(f"{NOTIFICATIONS_MODULE}.requests.post")
def test_send_msg_failure_log_has_no_raw_newline_threaded(
    mock_post: mock.MagicMock,
    mock_warning: mock.MagicMock,
    raised_error: Exception,
) -> None:
    """
    GIVEN a threaded notification whose POST raises an exception with a newline in its message
    WHEN _send_msg handles the failure
    THEN exactly one warning is logged, containing the escaped error text and no raw CR/LF
    """
    mock_post.side_effect = raised_error

    result = _send_msg(
        url="http://notify.invalid",
        msg="hello",
        timeout=1,
        request_id="abc123def456",
        notif_type=NotificationType.THREADED_NOTIFICATIONS,
    )

    assert result is None
    logged = _logged_messages(mock_warning)
    assert len(logged) == 1
    assert "\n" not in logged[0]
    assert "\r" not in logged[0]
    assert "connection reset\\nWARNING forged log line" in logged[0]
    assert logged[0].startswith("[abc123def456] ")


@mock.patch(f"{NOTIFICATIONS_MODULE}.warning_log")
@mock.patch(f"{NOTIFICATIONS_MODULE}.requests.post")
def test_send_msg_failure_log_has_no_raw_newline_contact_form(
    mock_post: mock.MagicMock,
    mock_warning_log: mock.MagicMock,
) -> None:
    """
    GIVEN a contact-form notification whose POST raises an exception with a CRLF in its message
    WHEN _send_msg handles the failure
    THEN the warning_log message contains no raw CR/LF
    """
    mock_post.side_effect = requests.exceptions.Timeout("timed out\r\nforged")

    result = _send_msg(
        url="http://notify.invalid",
        msg="hello",
        timeout=1,
        request_id="",
        notif_type=NotificationType.CONTACT_FORM,
    )

    assert result is None
    logged = _logged_messages(mock_warning_log)
    assert len(logged) == 1
    assert "\n" not in logged[0]
    assert "\r" not in logged[0]
    assert "timed out\\r\\nforged" in logged[0]


@mock.patch(f"{NOTIFICATIONS_MODULE}.logging.info")
@mock.patch(f"{NOTIFICATIONS_MODULE}.requests.post")
def test_send_msg_success_log_sanitizes_request_id_prefix(
    mock_post: mock.MagicMock,
    mock_info: mock.MagicMock,
) -> None:
    """
    GIVEN a threaded notification whose request_id contains a newline
    WHEN _send_msg sends successfully
    THEN the success log carries the escaped request_id prefix and no raw CR/LF
    """
    mock_response = mock.Mock(status_code=204)
    mock_post.return_value = mock_response

    result = _send_msg(
        url="http://notify.invalid",
        msg="hello",
        timeout=1,
        request_id="abc\nforged",
        notif_type=NotificationType.THREADED_NOTIFICATIONS,
    )

    assert result is mock_response
    logged = _logged_messages(mock_info)
    assert len(logged) == 1
    assert "\n" not in logged[0]
    assert logged[0].startswith("[abc\\nforged] Successfully sent notification")
