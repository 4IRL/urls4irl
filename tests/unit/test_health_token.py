import pytest

from backend.system.health_checks import is_health_token_valid

pytestmark = pytest.mark.unit


def test_matching_token_is_valid() -> None:
    assert is_health_token_valid("s3cret-token", "s3cret-token") is True


def test_mismatched_token_is_invalid() -> None:
    assert is_health_token_valid("wrong-token", "s3cret-token") is False


def test_unequal_length_token_is_invalid() -> None:
    assert is_health_token_valid("s3cret", "s3cret-token") is False
    assert is_health_token_valid("s3cret-token-longer", "s3cret-token") is False


@pytest.mark.parametrize("provided", [None, ""])
def test_missing_provided_token_is_invalid(provided: str | None) -> None:
    assert is_health_token_valid(provided, "s3cret-token") is False


@pytest.mark.parametrize("expected", [None, "", "   ", "\n"])
@pytest.mark.parametrize("provided", [None, "", "   ", "anything", "s3cret-token"])
def test_unset_expected_secret_is_always_invalid(
    provided: str | None, expected: str | None
) -> None:
    assert is_health_token_valid(provided, expected) is False


def test_trailing_newline_in_expected_still_matches() -> None:
    assert is_health_token_valid("s3cret-token", "s3cret-token\n") is True


def test_non_ascii_provided_does_not_raise() -> None:
    assert is_health_token_valid("sécret-tøken-✓", "s3cret-token") is False
    assert is_health_token_valid("sécret-tøken-✓", "sécret-tøken-✓") is True
