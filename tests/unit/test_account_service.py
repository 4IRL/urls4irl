from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.users.services.account_service import build_account_info_context

pytestmark = pytest.mark.unit

# Where build_account_info_context reads the acting user from; patched per-case
# with a lightweight stand-in (the service reads attributes only, runs no
# queries) so the flat context dict can be asserted deterministically.
_CURRENT_USER_TARGET = "backend.users.services.account_service.current_user"


def _fake_user(
    *, has_password: bool, pending_email: str | None = None
) -> SimpleNamespace:
    """A minimal current_user stand-in exposing the identity attributes
    build_account_info_context reads. ``password`` is a truthy hash string for a
    local-password account and ``None`` for an OAuth-only account, keeping the two
    scenarios distinct even though the context no longer surfaces that flag.
    ``pending_email`` mirrors the staged-change column (None when no change is in
    flight). ``utubs_is_member_of`` and ``oauth_identities`` are empty so the
    sole-creator transfer/solo counts resolve to 0 and the OAuth-only proof
    provider resolves to None — the membership matrix and proof-provider
    selection are exercised by the integration suites, not this unit test."""
    return SimpleNamespace(
        username="fakeuser1234",
        email="fakeuser1234@example.com",
        email_validated=True,
        password="hashed-password-value" if has_password else None,
        pending_email=pending_email,
        utubs_is_member_of=[],
        oauth_identities=[],
    )


def test_build_account_info_context_local_password_user() -> None:
    """
    GIVEN an authenticated local-password user with no pending email change
    WHEN build_account_info_context builds the account-info context
    THEN it returns the expected flat dict with no member-since keys (those are
        reused from build_user_stats_context) and a None pending-email
    """
    with patch(_CURRENT_USER_TARGET, _fake_user(has_password=True)):
        context = build_account_info_context()

    assert context == {
        "account_username": "fakeuser1234",
        "account_email": "fakeuser1234@example.com",
        "account_email_validated": True,
        "account_pending_email": None,
        "account_utubs_transferring": 0,
        "account_utubs_deleting_solo": 0,
        "account_removal_proof_provider_display": None,
    }


def test_build_account_info_context_oauth_only_user() -> None:
    """
    GIVEN an authenticated password-less (OAuth-only) user
    WHEN build_account_info_context builds the account-info context
    THEN the identity fields still render
    """
    with patch(_CURRENT_USER_TARGET, _fake_user(has_password=False)):
        context = build_account_info_context()

    assert context["account_username"] == "fakeuser1234"
    assert context["account_email"] == "fakeuser1234@example.com"
    assert context["account_email_validated"] is True
    assert context["account_pending_email"] is None


def test_build_account_info_context_surfaces_pending_email() -> None:
    """
    GIVEN an authenticated user with a staged pending email change
    WHEN build_account_info_context builds the account-info context
    THEN account_pending_email echoes the staged (lowercased) address so the
        template can render the pending-change indicator (DD-18)
    """
    with patch(
        _CURRENT_USER_TARGET,
        _fake_user(has_password=True, pending_email="new@example.com"),
    ):
        context = build_account_info_context()

    assert context["account_pending_email"] == "new@example.com"
