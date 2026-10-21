import re

import pytest

from backend.short_links.code_generator import generate_short_link_code
from backend.short_links.constants import SHORT_LINK_MINT_MAX_ATTEMPTS, SHORT_LINK_TTL

pytestmark = pytest.mark.unit

CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")


def test_generated_codes_are_always_ten_alphanumeric_chars() -> None:
    """
    GIVEN the code generator
    WHEN many codes are generated
    THEN each is exactly 10 characters matching ^[A-Za-z0-9]{10}$
    """
    for _ in range(2000):
        assert CODE_PATTERN.fullmatch(generate_short_link_code())


def test_generated_codes_vary() -> None:
    """
    GIVEN the code generator
    WHEN 200 codes are generated
    THEN they are not all identical (CSPRNG draw, not a constant)
    """
    assert len({generate_short_link_code() for _ in range(200)}) > 1


def test_constants() -> None:
    """
    GIVEN the short-link constants
    THEN the TTL is 7 days and mint retries are capped at 5
    """
    assert SHORT_LINK_TTL.days == 7
    assert SHORT_LINK_MINT_MAX_ATTEMPTS == 5
