from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.urls.constants import URLErrorCodes
from backend.utils.strings.json_strs import STD_JSON_RESPONSE as STD_JSON
from backend.utils.strings.utub_strs import UTUB_FAILURE
from backend.utubs.guards import reject_if_utub_locked

pytestmark = pytest.mark.unit


def test_reject_if_utub_locked_returns_none_when_unlocked():
    """An unlocked UTub short-circuits to None without building a response."""
    utub = MagicMock()
    utub.is_locked = False

    assert reject_if_utub_locked(utub, error_code=URLErrorCodes.UTUB_IS_LOCKED) is None


def test_reject_if_utub_locked_returns_403_with_passed_error_code_when_locked(app):
    """A locked UTub yields a 403 carrying the caller's own error_code + message."""
    utub = MagicMock()
    utub.is_locked = True

    with app.app_context():
        response, status_code = reject_if_utub_locked(
            utub, error_code=URLErrorCodes.UTUB_IS_LOCKED
        )
        payload = response.get_json()

    assert status_code == 403
    assert payload[STD_JSON.ERROR_CODE] == URLErrorCodes.UTUB_IS_LOCKED
    assert payload[STD_JSON.MESSAGE] == UTUB_FAILURE.UTUB_IS_LOCKED
