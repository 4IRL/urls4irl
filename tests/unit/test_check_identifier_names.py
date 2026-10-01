"""Unit tests for `scripts/check_identifier_names.py` (run by `make lint-python`).

Each case parses a small inline source, so nothing reads the real repo.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from scripts import check_identifier_names
from tests.unit.stdlib_only_utils import assert_module_is_stdlib_only

pytestmark = pytest.mark.unit

SAMPLE_PATH = "sample.py"


def _flagged_names(source: str) -> list[str]:
    findings = check_identifier_names.find_single_letter_names(
        textwrap.dedent(source), SAMPLE_PATH
    )
    return [finding.rsplit(" ", 1)[1] for finding in findings]


@pytest.mark.parametrize(
    ("source", "expected_names"),
    [
        ("q = 1\n", ["q"]),
        ("for i in range(3):\n    pass\n", ["i"]),
        ("items = []\nkeys = [k for k in items]\n", ["k"]),
        ("double = lambda x: x\n", ["x"]),
        (
            "def func(a, /, b, *c, d, **e):\n    pass\n",
            ["a", "b", "c", "d", "e"],
        ),
        (
            "try:\n    pass\nexcept ValueError as e:\n    pass\n",
            ["e"],
        ),
        ("with open(path) as f:\n    pass\n", ["f"]),
        ("import os as o\n", ["o"]),
        ("from x import MODELS as M\n", ["M"]),
        ("print(n := 1)\n", ["n"]),
        ('from typing import TypeVar\nT = TypeVar("T")\n', ["T"]),
        (
            "match items:\n    case [a, *b]:\n        pass\n",
            ["a", "b"],
        ),
        (
            "match items:\n    case {'key': value, **r}:\n        pass\n",
            ["r"],
        ),
        ("def f():\n    pass\n", ["f"]),
        ("async def g():\n    pass\n", ["g"]),
        ("class C:\n    pass\n", ["C"]),
    ],
)
def test_flags_single_letter_bindings(source: str, expected_names: list[str]) -> None:
    """
    GIVEN source that binds a single-letter name in any binding position
    WHEN find_single_letter_names scans it
    THEN every single-letter binding is reported
    """
    assert sorted(_flagged_names(source)) == sorted(expected_names)


@pytest.mark.parametrize(
    "source",
    [
        "_ = 1\nfor _ in range(3):\n    pass\n",
        "value = 1\nfor index in range(3):\n    pass\n",
        "class Thing:\n    def __init__(self) -> None:\n        self.x = 1\n",
        "func(x=1)\n",
        "import numpy as np\nconstant = np.e\n",
        "result = x + y\n",
    ],
)
def test_does_not_flag_allowed_names(source: str) -> None:
    """
    GIVEN source with `_`, multi-letter names, attribute stores, call-site
        keywords or single-letter names that are only read
    WHEN find_single_letter_names scans it
    THEN nothing is reported
    """
    assert _flagged_names(source) == []


def test_finding_format_has_path_line_col_and_name() -> None:
    """
    GIVEN a single-letter assignment on line 2, column 4
    WHEN find_single_letter_names scans it
    THEN the finding reads `<path>:<line>:<col> <name>`
    """
    source = "if True:\n    q = 1\n"
    assert check_identifier_names.find_single_letter_names(source, SAMPLE_PATH) == [
        f"{SAMPLE_PATH}:2:4 q"
    ]


def test_main_exits_non_zero_with_findings(tmp_path: Path) -> None:
    """
    GIVEN a file containing a single-letter name
    WHEN main runs on it
    THEN it exits non-zero and the finding is printed
    """
    offending_file = tmp_path / "offending.py"
    offending_file.write_text("q = 1\n")

    with pytest.raises(SystemExit) as exit_info:
        check_identifier_names.main([str(offending_file)])

    assert exit_info.value.code not in (0, None)
    assert f"{offending_file}:1:0 q" in str(exit_info.value.code)


def test_main_exits_non_zero_naming_unparseable_file(tmp_path: Path) -> None:
    """
    GIVEN a file containing invalid Python syntax
    WHEN main runs on it
    THEN it exits non-zero and the message names the file as unparseable
    """
    broken_file = tmp_path / "broken.py"
    broken_file.write_text("def broken(:\n")

    with pytest.raises(SystemExit) as exit_info:
        check_identifier_names.main([str(broken_file)])

    assert exit_info.value.code not in (0, None)
    assert f"{broken_file}: could not parse" in str(exit_info.value.code)


def test_main_exits_zero_on_clean_input(tmp_path: Path) -> None:
    """
    GIVEN a file with only descriptive names
    WHEN main runs on it
    THEN it returns without exiting non-zero
    """
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("value = 1\n")

    check_identifier_names.main([str(clean_file)])


def test_check_identifier_names_module_is_stdlib_only() -> None:
    """
    GIVEN check_identifier_names.py, which runs on the host under bare mise python
    WHEN it is loaded in a fresh interpreter without the project root
    THEN no third-party or backend module is imported (stdlib only)
    """
    assert_module_is_stdlib_only(
        Path(check_identifier_names.__file__),
        ("flask", "sqlalchemy", "redis", "backend"),
    )
