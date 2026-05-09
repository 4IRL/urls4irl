from __future__ import annotations

import pytest

from backend.metrics.routes import _pick_csrf_token

pytestmark = pytest.mark.unit


def test_pick_csrf_token_returns_header_when_present():
    """
    GIVEN a request with a non-empty X-CSRFToken header
    WHEN _pick_csrf_token is called
    THEN the header value is returned (header has priority).
    """
    token = _pick_csrf_token(header_token="from-header", body_token=None)
    assert token == "from-header"


def test_pick_csrf_token_falls_back_to_body_when_header_missing():
    """
    GIVEN a request with no X-CSRFToken header but a body csrf_token field
    WHEN _pick_csrf_token is called
    THEN the body token is returned (sendBeacon path).
    """
    token = _pick_csrf_token(header_token=None, body_token="from-body")
    assert token == "from-body"


def test_pick_csrf_token_prefers_header_over_body():
    """
    GIVEN both header and body tokens are present
    WHEN _pick_csrf_token is called
    THEN the header token is returned (header has priority).
    """
    token = _pick_csrf_token(header_token="from-header", body_token="from-body")
    assert token == "from-header"


def test_pick_csrf_token_returns_none_when_both_missing():
    """
    GIVEN neither header nor body token is present
    WHEN _pick_csrf_token is called
    THEN None is returned.
    """
    token = _pick_csrf_token(header_token=None, body_token=None)
    assert token is None


def test_pick_csrf_token_treats_empty_string_header_as_missing():
    """
    GIVEN an empty-string X-CSRFToken header
    WHEN _pick_csrf_token is called and a body token is present
    THEN the body token is returned (empty header treated as absent).
    """
    token = _pick_csrf_token(header_token="", body_token="from-body")
    assert token == "from-body"


def test_pick_csrf_token_returns_none_when_both_empty():
    """
    GIVEN an empty header and empty body token
    WHEN _pick_csrf_token is called
    THEN None is returned (both treated as missing).
    """
    token = _pick_csrf_token(header_token="", body_token="")
    assert token is None
