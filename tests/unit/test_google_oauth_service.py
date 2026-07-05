import pytest

from backend.splash.services.oauth.google_service import resolve_preferred_username

pytestmark = pytest.mark.unit

_EMAIL = "jane@example.com"
_EMAIL_LOCAL_PART = "jane"
_CLEAN_NAME = "Jane Doe"
_MARKUP_NAME = "<script>alert(1)</script>"


def test_resolve_preferred_username_passthrough_for_clean_name():
    """
    GIVEN a provider-supplied display name with no HTML/markup content
    WHEN resolve_preferred_username is called
    THEN the name is returned unchanged, since sanitization doesn't alter it
    """
    assert resolve_preferred_username(_CLEAN_NAME, _EMAIL) == _CLEAN_NAME


def test_resolve_preferred_username_falls_back_to_email_local_part_when_missing():
    """
    GIVEN no provider-supplied display name
    WHEN resolve_preferred_username is called
    THEN the email local-part is used as the username seed
    """
    assert resolve_preferred_username(None, _EMAIL) == _EMAIL_LOCAL_PART


def test_resolve_preferred_username_falls_back_to_email_local_part_for_markup_name():
    """
    GIVEN a provider-supplied display name containing script/markup content
    WHEN resolve_preferred_username is called
    THEN sanitization alters the raw name, so the function falls back to the
        email local-part rather than returning a sanitized-but-altered value
    """
    resolved_username = resolve_preferred_username(_MARKUP_NAME, _EMAIL)

    assert resolved_username == _EMAIL_LOCAL_PART
    assert resolved_username != _MARKUP_NAME
