"""Unit tests for the _sanitize_and_reject_if_modified validator."""

import pytest

from backend.schemas.requests._sanitize import (
    INVALID_INPUT,
    _sanitize_and_reject_if_modified,
)

pytestmark = pytest.mark.unit


class TestSanitizeAndRejectIfModified:
    def test_empty_string_returns_empty_string(self):
        """Empty string is passed through so min_length produces the humanized error."""
        result = _sanitize_and_reject_if_modified("")
        assert result == ""

    def test_none_returns_none(self):
        """None is passed through unchanged."""
        result = _sanitize_and_reject_if_modified(None)
        assert result is None

    def test_clean_string_returns_unchanged(self):
        """A string that sanitization does not modify is returned as-is."""
        result = _sanitize_and_reject_if_modified("hello")
        assert result == "hello"

    def test_non_string_returns_unchanged(self):
        """Non-string values are passed through unchanged."""
        result = _sanitize_and_reject_if_modified(42)
        assert result == 42

    def test_dangerous_input_raises_value_error(self):
        """Input containing HTML/script tags is rejected with ValueError."""
        with pytest.raises(ValueError, match=INVALID_INPUT):
            _sanitize_and_reject_if_modified("<script>alert('xss')</script>")
