import ast
import re
from pathlib import Path

import pytest

from backend.invite_links import constants as invite_constants
from backend.invite_links.constants import (
    INVITE_LINK_TOKEN_LENGTH,
    INVITE_LINK_TOKEN_PATTERN,
)
from backend.invite_links.token_generator import generate_invite_token

pytestmark = pytest.mark.unit

STDLIB_ALLOWLIST: frozenset[str] = frozenset({"datetime", "__future__"})


def test_generated_tokens_match_pattern_and_length() -> None:
    """
    GIVEN the invite token generator
    WHEN many tokens are generated
    THEN each has the declared length and fullmatches the token pattern
    """
    for _ in range(2000):
        token = generate_invite_token()
        assert len(token) == INVITE_LINK_TOKEN_LENGTH
        assert re.fullmatch(INVITE_LINK_TOKEN_PATTERN, token)


def test_generated_tokens_vary() -> None:
    """
    GIVEN the invite token generator
    WHEN 200 tokens are generated
    THEN they are not all identical
    """
    assert len({generate_invite_token() for _ in range(200)}) > 1


def test_pattern_rejects_malformed_tokens() -> None:
    """
    GIVEN the token pattern
    WHEN a trailing newline, wrong length or illegal character is tested
    THEN none match
    """
    valid = "A" * INVITE_LINK_TOKEN_LENGTH
    assert re.match(INVITE_LINK_TOKEN_PATTERN, valid)
    assert not re.match(INVITE_LINK_TOKEN_PATTERN, valid + "\n")
    assert not re.match(INVITE_LINK_TOKEN_PATTERN, valid + "A")
    assert not re.match(INVITE_LINK_TOKEN_PATTERN, valid[:-1])
    assert not re.match(INVITE_LINK_TOKEN_PATTERN, valid[:-1] + "!")
    assert not re.match(INVITE_LINK_TOKEN_PATTERN, valid[:-1] + "+")


def test_constants_module_imports_only_stdlib() -> None:
    """
    GIVEN the source of backend/invite_links/constants.py
    WHEN its imports are parsed
    THEN every imported module is in the stdlib allowlist
    """
    source = Path(invite_constants.__file__).read_text()
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module is not None
            modules.add(node.module.split(".")[0])
    assert modules <= STDLIB_ALLOWLIST
