import pytest

from backend.app_logger import sanitize_log_value

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("line one\nline two", "line one\\nline two"),
        ("line one\rline two", "line one\\rline two"),
        ("line one\r\nline two", "line one\\r\\nline two"),
        ("\n\r\n\r", "\\n\\r\\n\\r"),
    ],
)
def test_sanitize_log_value_neutralises_line_breaks(
    raw_value: str, expected: str
) -> None:
    """
    GIVEN a string containing CR and/or LF characters
    WHEN sanitize_log_value is called on it
    THEN every CR/LF is replaced with its escaped literal and no raw line break remains
    """
    sanitized = sanitize_log_value(raw_value)

    assert sanitized == expected
    assert "\n" not in sanitized
    assert "\r" not in sanitized


def test_sanitize_log_value_leaves_clean_string_unchanged() -> None:
    """
    GIVEN a string with no CR or LF characters
    WHEN sanitize_log_value is called on it
    THEN the exact same string is returned
    """
    clean_value = "[abc123] Successfully sent notification: status_code=204"

    assert sanitize_log_value(clean_value) == clean_value


def test_sanitize_log_value_stringifies_int() -> None:
    """
    GIVEN a non-str value such as an int
    WHEN sanitize_log_value is called on it
    THEN its str() form is returned
    """
    assert sanitize_log_value(204) == "204"


def test_sanitize_log_value_stringifies_and_sanitizes_exception() -> None:
    """
    GIVEN an exception whose message contains a CRLF-injected fake log line
    WHEN sanitize_log_value is called on the exception object
    THEN its str() form is returned with the line breaks neutralised
    """
    injected_error = ValueError("boom\r\nINFO forged log line")

    sanitized = sanitize_log_value(injected_error)

    assert sanitized == "boom\\r\\nINFO forged log line"
    assert "\n" not in sanitized
    assert "\r" not in sanitized
