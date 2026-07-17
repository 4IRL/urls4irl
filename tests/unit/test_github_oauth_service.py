import pytest

from backend.splash.services.oauth.github_service import select_primary_verified_email

pytestmark = pytest.mark.unit

_PRIMARY_VERIFIED_EMAIL = "primary-verified@example.com"
_SECONDARY_VERIFIED_EMAIL = "secondary-verified@example.com"
_UNVERIFIED_EMAIL = "unverified@example.com"


def test_select_primary_verified_email_picks_primary_and_verified_entry():
    """
    GIVEN a `/user/emails` payload with multiple entries, exactly one of which
        is both `primary` and `verified`
    WHEN select_primary_verified_email is called
    THEN the primary+verified entry's email is returned, regardless of its
        position in the list
    """
    emails_payload = [
        {
            "email": _SECONDARY_VERIFIED_EMAIL,
            "primary": False,
            "verified": True,
            "visibility": "public",
        },
        {
            "email": _PRIMARY_VERIFIED_EMAIL,
            "primary": True,
            "verified": True,
            "visibility": "private",
        },
        {
            "email": _UNVERIFIED_EMAIL,
            "primary": False,
            "verified": False,
            "visibility": "public",
        },
    ]

    assert select_primary_verified_email(emails_payload) == _PRIMARY_VERIFIED_EMAIL


def test_select_primary_verified_email_returns_none_for_unverified_primary():
    """
    GIVEN a `/user/emails` payload whose only `primary` entry is `verified: False`
    WHEN select_primary_verified_email is called
    THEN None is returned — an unverified primary is never trusted
    """
    emails_payload = [
        {
            "email": _PRIMARY_VERIFIED_EMAIL,
            "primary": True,
            "verified": False,
            "visibility": "public",
        }
    ]

    assert select_primary_verified_email(emails_payload) is None


def test_select_primary_verified_email_returns_none_for_verified_non_primary():
    """
    GIVEN a `/user/emails` payload with a verified entry that is not `primary`,
        and no primary entry at all
    WHEN select_primary_verified_email is called
    THEN None is returned — a verified-but-not-primary address is not trusted
    """
    emails_payload = [
        {
            "email": _SECONDARY_VERIFIED_EMAIL,
            "primary": False,
            "verified": True,
            "visibility": "public",
        }
    ]

    assert select_primary_verified_email(emails_payload) is None


def test_select_primary_verified_email_returns_none_for_empty_list():
    """
    GIVEN an empty `/user/emails` payload
    WHEN select_primary_verified_email is called
    THEN None is returned
    """
    assert select_primary_verified_email([]) is None


def test_select_primary_verified_email_skips_malformed_entries_without_raising():
    """
    GIVEN a `/user/emails` payload containing a non-dict entry and a dict entry
        whose `email` field is not a string, alongside one valid
        primary+verified entry
    WHEN select_primary_verified_email is called
    THEN the malformed entries are skipped without raising, and the valid
        entry's email is returned
    """
    emails_payload = [
        "not-a-dict-entry",
        {"email": 12345, "primary": True, "verified": True, "visibility": "public"},
        {
            "email": _PRIMARY_VERIFIED_EMAIL,
            "primary": True,
            "verified": True,
            "visibility": "public",
        },
    ]

    assert select_primary_verified_email(emails_payload) == _PRIMARY_VERIFIED_EMAIL


def test_select_primary_verified_email_returns_none_when_only_malformed_entries():
    """
    GIVEN a `/user/emails` payload containing only malformed entries (a
        non-dict entry and a dict with a non-string `email`)
    WHEN select_primary_verified_email is called
    THEN None is returned without raising
    """
    emails_payload = [
        None,
        {"email": 12345, "primary": True, "verified": True, "visibility": "public"},
    ]

    assert select_primary_verified_email(emails_payload) is None
