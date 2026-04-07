from __future__ import annotations

import pytest

from backend.api_common.auth_decorators import (
    SESSION_AUTH_DECORATORS,
    email_validation_required,
    no_authenticated_users_allowed,
    url_adder_or_creator_required,
    utub_creator_required,
    utub_membership_required,
    utub_membership_with_valid_url_in_utub_required,
    utub_membership_with_valid_url_tag,
    utub_membership_with_valid_utub_tag,
)
from backend.api_common.parse_request import api_route

pytestmark = pytest.mark.unit

AUTH_DECORATOR_ATTR = "_auth_decorator"


def _dummy_fn(*args, **kwargs):
    """Plain callable used as a decoration target."""
    pass


class TestAuthDecoratorStashAttribute:
    """Verify each auth decorator stashes _auth_decorator on the wrapper."""

    def test_no_authenticated_users_allowed_stashes_name(self):
        wrapped = no_authenticated_users_allowed(_dummy_fn)
        assert hasattr(wrapped, AUTH_DECORATOR_ATTR)
        assert wrapped._auth_decorator == "no_authenticated_users_allowed"

    def test_email_validation_required_stashes_name(self):
        wrapped = email_validation_required(_dummy_fn)
        assert hasattr(wrapped, AUTH_DECORATOR_ATTR)
        assert wrapped._auth_decorator == "email_validation_required"

    def test_utub_membership_required_stashes_name(self):
        wrapped = utub_membership_required(_dummy_fn)
        assert hasattr(wrapped, AUTH_DECORATOR_ATTR)
        assert wrapped._auth_decorator == "utub_membership_required"

    def test_utub_creator_required_stashes_name(self):
        wrapped = utub_creator_required(_dummy_fn)
        assert hasattr(wrapped, AUTH_DECORATOR_ATTR)
        assert wrapped._auth_decorator == "utub_creator_required"

    def test_utub_membership_with_valid_url_in_utub_required_stashes_name(self):
        wrapped = utub_membership_with_valid_url_in_utub_required(_dummy_fn)
        assert hasattr(wrapped, AUTH_DECORATOR_ATTR)
        assert (
            wrapped._auth_decorator == "utub_membership_with_valid_url_in_utub_required"
        )

    def test_url_adder_or_creator_required_stashes_name(self):
        decorator = url_adder_or_creator_required("test message")
        wrapped = decorator(_dummy_fn)
        assert hasattr(wrapped, AUTH_DECORATOR_ATTR)
        assert wrapped._auth_decorator == "url_adder_or_creator_required"

    def test_utub_membership_with_valid_utub_tag_stashes_name(self):
        wrapped = utub_membership_with_valid_utub_tag(_dummy_fn)
        assert hasattr(wrapped, AUTH_DECORATOR_ATTR)
        assert wrapped._auth_decorator == "utub_membership_with_valid_utub_tag"

    def test_utub_membership_with_valid_url_tag_stashes_name(self):
        wrapped = utub_membership_with_valid_url_tag(_dummy_fn)
        assert hasattr(wrapped, AUTH_DECORATOR_ATTR)
        assert wrapped._auth_decorator == "utub_membership_with_valid_url_tag"


class TestChainedDecoratorStashesOutermost:
    """Verify chained decorators preserve the outermost _auth_decorator value."""

    def test_utub_creator_required_chains_preserve_outermost(self):
        """utub_creator_required chains email_validation_required -> utub_membership_required -> creator check.
        The outermost decorator name should be the one stashed."""
        wrapped = utub_creator_required(_dummy_fn)
        assert wrapped._auth_decorator == "utub_creator_required"


class TestNonAuthDecoratorLacksAttribute:
    """Verify functions without auth decorators do NOT have _auth_decorator."""

    def test_plain_function_lacks_auth_decorator_attr(self):
        assert not hasattr(_dummy_fn, AUTH_DECORATOR_ATTR)

    def test_api_route_only_lacks_auth_decorator_attr(self):
        wrapped = api_route(tags=["test"])(_dummy_fn)
        assert not hasattr(wrapped, AUTH_DECORATOR_ATTR)


class TestSessionAuthDecoratorRegistry:
    """Verify SESSION_AUTH_DECORATORS registry stays in sync with decorators."""

    def test_registry_excludes_no_authenticated_users(self):
        assert "no_authenticated_users_allowed" not in SESSION_AUTH_DECORATORS

    def test_registry_contains_all_session_auth_decorators(self):
        expected = {
            email_validation_required.__name__,
            utub_membership_required.__name__,
            utub_creator_required.__name__,
            utub_membership_with_valid_url_in_utub_required.__name__,
            utub_membership_with_valid_utub_tag.__name__,
            utub_membership_with_valid_url_tag.__name__,
            url_adder_or_creator_required.__name__,
        }
        assert SESSION_AUTH_DECORATORS == expected
