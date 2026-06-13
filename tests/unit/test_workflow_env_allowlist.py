"""Defensive contract test. Asserts every os.environ key read by the cron-invoked
Python scripts (scripts/flush_metrics.py, scripts/check_flush_liveness.py) is
covered by the ALLOW_VARS bash array in docker/startup-workflow.sh. Catches future
drift where a maintainer adds an os.environ access without updating the dump filter.
Note: this test covers only Python cron scripts (flush_metrics.py,
check_flush_liveness.py). Bash cron scripts (daily-docker.sh and its sourced
helpers) are not covered by AST walking; when adding a new bash cron line, update
ALLOW_VARS and the docker/crontab.workflow header manually.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_STARTUP_SCRIPT: Path = _PROJECT_ROOT / "docker" / "startup-workflow.sh"
_CRON_PYTHON_SCRIPTS: tuple[Path, ...] = (
    _PROJECT_ROOT / "scripts" / "flush_metrics.py",
    _PROJECT_ROOT / "scripts" / "check_flush_liveness.py",
)
_ALLOW_VARS_BLOCK_RE: re.Pattern[str] = re.compile(
    r"ALLOW_VARS=\((?P<body>.*?)\)", re.DOTALL
)
_BARE_NAME_RE: re.Pattern[str] = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _parse_allow_vars_from_shell(startup_script_path: Path) -> tuple[str, ...]:
    """Extract the ALLOW_VARS bash-array entries from startup-workflow.sh.

    Reads the file, matches the ``ALLOW_VARS=( ... )`` array literal via
    ``_ALLOW_VARS_BLOCK_RE``, splits the captured body on whitespace, strips
    empty tokens, and returns the entries as a tuple in source order.

    Example:
        >>> _parse_allow_vars_from_shell(Path("docker/startup-workflow.sh"))
        ('ACCESS_KEY', 'DEV_SERVER', 'METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS', ...)
    """
    source = startup_script_path.read_text()
    match = _ALLOW_VARS_BLOCK_RE.search(source)
    if match is None:
        return ()
    body = match.group("body")
    return tuple(token for token in body.split() if token)


def _walk_env_reads(source: str) -> frozenset[str]:
    """Collect string-literal env-var keys read in a Python source string.

    Parses ``source`` with ``ast.parse`` and walks every node, capturing the
    string-literal key from three call shapes:
      - ``os.environ["FOO"]`` (subscript with a constant string slice)
      - ``os.environ.get("FOO")`` / ``os.environ.get("FOO", default)``
      - ``os.getenv("FOO")``
    Non-literal accesses (e.g. ``os.environ[var_name]``) are skipped silently —
    this is a drift guard, not a perfect static analyzer.

    Example:
        >>> _walk_env_reads('import os\\nx = os.environ["FOO"]\\ny = os.environ.get("BAR", "z")\\n')
        frozenset({'FOO', 'BAR'})
    """
    tree = ast.parse(source)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            subscript_value = node.value
            if (
                isinstance(subscript_value, ast.Attribute)
                and subscript_value.attr == "environ"
                and isinstance(subscript_value.value, ast.Name)
                and subscript_value.value.id == "os"
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
            ):
                keys.add(node.slice.value)
        elif isinstance(node, ast.Call):
            func = node.func
            if not isinstance(func, ast.Attribute) or not node.args:
                continue
            first_arg = node.args[0]
            if not (
                isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str)
            ):
                continue
            func_owner = func.value
            is_environ_get = (
                func.attr == "get"
                and isinstance(func_owner, ast.Attribute)
                and func_owner.attr == "environ"
                and isinstance(func_owner.value, ast.Name)
                and func_owner.value.id == "os"
            )
            is_getenv = (
                func.attr == "getenv"
                and isinstance(func_owner, ast.Name)
                and func_owner.id == "os"
            )
            if is_environ_get or is_getenv:
                keys.add(first_arg.value)
    return frozenset(keys)


def test_allow_list_block_is_parseable():
    """
    GIVEN the startup-workflow.sh script
    WHEN the ALLOW_VARS array is parsed
    THEN a non-empty tuple of entries is returned.
    """
    allow_vars = _parse_allow_vars_from_shell(_STARTUP_SCRIPT)
    assert allow_vars, "ALLOW_VARS array not found or empty in startup-workflow.sh"


def test_allow_list_entries_are_uppercase_underscore_names():
    """
    GIVEN the parsed ALLOW_VARS entries
    WHEN each entry is checked against the bare-name pattern
    THEN every entry is an uppercase-underscore identifier.
    """
    allow_vars = _parse_allow_vars_from_shell(_STARTUP_SCRIPT)
    for entry in allow_vars:
        assert _BARE_NAME_RE.match(entry), f"'{entry}' is not an uppercase env-var name"


def test_allow_list_has_no_duplicates():
    """
    GIVEN the parsed ALLOW_VARS entries
    WHEN the entries are de-duplicated
    THEN no entry appears more than once.
    """
    allow_vars = _parse_allow_vars_from_shell(_STARTUP_SCRIPT)
    assert len(allow_vars) == len(set(allow_vars)), "ALLOW_VARS contains duplicates"


def test_allow_list_is_alphabetized():
    """
    GIVEN the parsed ALLOW_VARS entries
    WHEN the entries are sorted
    THEN the source order already matches alphabetical order.
    """
    allow_vars = _parse_allow_vars_from_shell(_STARTUP_SCRIPT)
    assert list(allow_vars) == sorted(allow_vars), "ALLOW_VARS is not alphabetized"


def test_allow_list_covers_flush_metrics_env_reads():
    """
    GIVEN the env-var keys read by scripts/flush_metrics.py
    WHEN they are compared against ALLOW_VARS
    THEN every read key is present in ALLOW_VARS.
    """
    allowed = frozenset(_parse_allow_vars_from_shell(_STARTUP_SCRIPT))
    reads = _walk_env_reads(_CRON_PYTHON_SCRIPTS[0].read_text())
    assert (
        reads <= allowed
    ), f"flush_metrics.py reads {sorted(reads - allowed)} not in ALLOW_VARS"


def test_allow_list_covers_check_flush_liveness_env_reads():
    """
    GIVEN the env-var keys read by scripts/check_flush_liveness.py
    WHEN they are compared against ALLOW_VARS
    THEN every read key is present in ALLOW_VARS.
    """
    allowed = frozenset(_parse_allow_vars_from_shell(_STARTUP_SCRIPT))
    reads = _walk_env_reads(_CRON_PYTHON_SCRIPTS[1].read_text())
    assert (
        reads <= allowed
    ), f"check_flush_liveness.py reads {sorted(reads - allowed)} not in ALLOW_VARS"
