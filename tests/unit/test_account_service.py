from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.users.services.account_service import build_account_info_context

pytestmark = pytest.mark.unit

# Where build_account_info_context reads the acting user from; patched per-case
# with a lightweight stand-in (the service reads attributes only, runs no
# queries) so the flat context dict can be asserted deterministically.
_CURRENT_USER_TARGET = "backend.users.services.account_service.current_user"


def _fake_user(*, has_password: bool) -> SimpleNamespace:
    """A minimal current_user stand-in exposing exactly the attributes
    build_account_info_context reads. ``password`` is a truthy hash string for a
    local-password account and ``None`` for an OAuth-only account."""
    return SimpleNamespace(
        username="fakeuser1234",
        email="fakeuser1234@example.com",
        email_validated=True,
        password="hashed-password-value" if has_password else None,
    )


def test_build_account_info_context_local_password_user() -> None:
    """
    GIVEN an authenticated local-password user
    WHEN build_account_info_context builds the account-info context
    THEN it returns the expected flat dict with account_has_password True and no
        member-since keys (those are reused from build_user_stats_context)
    """
    with patch(_CURRENT_USER_TARGET, _fake_user(has_password=True)):
        context = build_account_info_context()

    assert context == {
        "account_username": "fakeuser1234",
        "account_email": "fakeuser1234@example.com",
        "account_email_validated": True,
        "account_has_password": True,
    }


def test_build_account_info_context_oauth_only_user() -> None:
    """
    GIVEN an authenticated password-less (OAuth-only) user
    WHEN build_account_info_context builds the account-info context
    THEN account_has_password is False while the identity fields still render
    """
    with patch(_CURRENT_USER_TARGET, _fake_user(has_password=False)):
        context = build_account_info_context()

    assert context["account_has_password"] is False
    assert context["account_username"] == "fakeuser1234"
    assert context["account_email"] == "fakeuser1234@example.com"
    assert context["account_email_validated"] is True
