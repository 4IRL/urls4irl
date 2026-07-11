"""Defensive contract test for the workflow container's env-var allow-list.

ALLOW_VARS in scripts/build_container_env.py is the single source of truth for
which environment variables the cron jobs may see via /app/container_environment.
This module asserts that every env var the cron-invoked scripts actually read is
covered by ALLOW_VARS, catching future drift where a maintainer adds an access
without updating the allow-list. Coverage spans BOTH the Python cron scripts
(scripts/flush_metrics.py, scripts/check_flush_liveness.py, via AST walking) and
the bash cron scripts (scripts/daily-docker.sh and its sourced helpers, via a
reads-minus-assignments scan). It also unit-tests the pure builder functions
(URI assembly, secret loading, dump rendering) without booting the image.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from scripts.build_container_env import (
    ALLOW_VARS,
    assemble_metrics_redis_uri,
    build_env_mapping,
    read_secret_files,
    render_env_dump,
)

pytestmark = pytest.mark.unit


_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_FLUSH_METRICS_SCRIPT: Path = _PROJECT_ROOT / "scripts" / "flush_metrics.py"
_CHECK_LIVENESS_SCRIPT: Path = _PROJECT_ROOT / "scripts" / "check_flush_liveness.py"
_PURGE_AUDIT_LOG_SCRIPT: Path = _PROJECT_ROOT / "scripts" / "purge_audit_log.py"
_SAMPLE_GAUGES_SCRIPT: Path = _PROJECT_ROOT / "scripts" / "sample_gauges.py"
_NOTIFY_SCRIPT: Path = _PROJECT_ROOT / "scripts" / "notify.py"
_BASH_CRON_SCRIPTS: tuple[Path, ...] = (
    _PROJECT_ROOT / "scripts" / "daily-docker.sh",
    _PROJECT_ROOT / "scripts" / "backup-database.sh",
    _PROJECT_ROOT / "scripts" / "backup-logs.sh",
    _PROJECT_ROOT / "scripts" / "remote-object-storage.sh",
)
_BARE_NAME_RE: re.Pattern[str] = re.compile(r"^[A-Z][A-Z0-9_]*$")
_BASH_VAR_READ_RE: re.Pattern[str] = re.compile(r"\$\{?([A-Z][A-Z0-9_]*)")
_BASH_VAR_ASSIGN_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![=!<>])\b([A-Z][A-Z0-9_]*)=(?!=)"),
    re.compile(r"\bfor\s+([A-Z][A-Z0-9_]*)\s+in\b"),
    re.compile(r"\bread\s+(?:-r\s+)?([A-Z][A-Z0-9_]*)\b"),
)
_ALLOWED: frozenset[str] = frozenset(ALLOW_VARS)


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


def _bash_external_var_reads(script_paths: tuple[Path, ...]) -> frozenset[str]:
    """Find externally-sourced env vars read by a set of bash scripts.

    Scans every uppercase ``$VAR`` / ``${VAR}`` read and every assignment
    (``VAR=``, ``export VAR=``, ``local VAR=``, ``for VAR in``, ``read VAR``)
    across all ``script_paths`` as one combined unit, then returns
    ``reads - assignments``. A var that is only ever read (never assigned
    anywhere in the set, including by a parent that exports it) must come from
    /app/container_environment — so it has to be in ALLOW_VARS. Locally-assigned
    and parent-exported vars (DB_USER, LOG_FILE, …) drop out automatically, with
    no manual ignore-list. The four bash cron scripts read no shell builtins
    ($HOME/$PATH/etc.), so none leak through as false positives.

    Example:
        # daily-docker.sh reads $PRODUCTION (external) and assigns DB_USER=...
        >>> _bash_external_var_reads((Path("scripts/daily-docker.sh"),))
        frozenset({'PRODUCTION', ...})
    """
    reads: set[str] = set()
    assigned: set[str] = set()
    for script_path in script_paths:
        source = script_path.read_text()
        reads.update(match.group(1) for match in _BASH_VAR_READ_RE.finditer(source))
        for assign_re in _BASH_VAR_ASSIGN_RES:
            assigned.update(match.group(1) for match in assign_re.finditer(source))
    return frozenset(reads - assigned)


def test_allow_list_is_non_empty():
    """
    GIVEN the imported ALLOW_VARS tuple
    WHEN its length is checked
    THEN it is non-empty.
    """
    assert ALLOW_VARS, "ALLOW_VARS is empty"


def test_allow_list_entries_are_uppercase_underscore_names():
    """
    GIVEN the ALLOW_VARS entries
    WHEN each entry is checked against the bare-name pattern
    THEN every entry is an uppercase-underscore identifier.
    """
    for entry in ALLOW_VARS:
        assert _BARE_NAME_RE.match(entry), f"'{entry}' is not an uppercase env-var name"


def test_allow_list_has_no_duplicates():
    """
    GIVEN the ALLOW_VARS entries
    WHEN the entries are de-duplicated
    THEN no entry appears more than once.
    """
    assert len(ALLOW_VARS) == len(set(ALLOW_VARS)), "ALLOW_VARS contains duplicates"


def test_allow_list_is_alphabetized():
    """
    GIVEN the ALLOW_VARS entries
    WHEN the entries are sorted
    THEN the declared order already matches alphabetical order.
    """
    assert list(ALLOW_VARS) == sorted(ALLOW_VARS), "ALLOW_VARS is not alphabetized"


def test_allow_list_covers_flush_metrics_env_reads():
    """
    GIVEN the env-var keys read by scripts/flush_metrics.py
    WHEN they are compared against ALLOW_VARS
    THEN every read key is present in ALLOW_VARS.
    """
    reads = _walk_env_reads(_FLUSH_METRICS_SCRIPT.read_text())
    assert (
        reads <= _ALLOWED
    ), f"flush_metrics.py reads {sorted(reads - _ALLOWED)} not in ALLOW_VARS"


def test_allow_list_covers_sample_gauges_env_reads():
    """
    GIVEN the env-var keys read by scripts/sample_gauges.py
    WHEN they are compared against ALLOW_VARS
    THEN every read key is present in ALLOW_VARS.
    """
    reads = _walk_env_reads(_SAMPLE_GAUGES_SCRIPT.read_text())
    assert (
        reads <= _ALLOWED
    ), f"sample_gauges.py reads {sorted(reads - _ALLOWED)} not in ALLOW_VARS"


def test_allow_list_covers_purge_audit_log_env_reads():
    """
    GIVEN the env-var keys read by scripts/purge_audit_log.py
    WHEN they are compared against ALLOW_VARS
    THEN every read key is present in ALLOW_VARS.
    """
    reads = _walk_env_reads(_PURGE_AUDIT_LOG_SCRIPT.read_text())
    assert (
        reads <= _ALLOWED
    ), f"purge_audit_log.py reads {sorted(reads - _ALLOWED)} not in ALLOW_VARS"


def test_allow_list_covers_notify_env_reads():
    """
    GIVEN the env-var keys read by scripts/notify.py
    WHEN they are compared against ALLOW_VARS
    THEN every read key is present in ALLOW_VARS.
    """
    reads = _walk_env_reads(_NOTIFY_SCRIPT.read_text())
    assert (
        reads <= _ALLOWED
    ), f"notify.py reads {sorted(reads - _ALLOWED)} not in ALLOW_VARS"


def test_allow_list_covers_check_flush_liveness_env_reads():
    """
    GIVEN the env-var keys read by scripts/check_flush_liveness.py
    WHEN they are compared against ALLOW_VARS
    THEN every read key is present in ALLOW_VARS.
    """
    reads = _walk_env_reads(_CHECK_LIVENESS_SCRIPT.read_text())
    assert (
        reads <= _ALLOWED
    ), f"check_flush_liveness.py reads {sorted(reads - _ALLOWED)} not in ALLOW_VARS"


def test_allow_list_covers_bash_cron_env_reads():
    """
    GIVEN the externally-sourced env vars read by the bash cron scripts
    WHEN they are compared against ALLOW_VARS
    THEN every externally-sourced var is present in ALLOW_VARS.
    """
    external = _bash_external_var_reads(_BASH_CRON_SCRIPTS)
    assert (
        external <= _ALLOWED
    ), f"bash cron scripts read {sorted(external - _ALLOWED)} not in ALLOW_VARS"


def test_walk_env_reads_captures_all_three_call_shapes():
    """
    GIVEN a source string using subscript, environ.get, and getenv access
    WHEN the keys are walked
    THEN all three string-literal keys are captured.
    """
    source = (
        "import os\n"
        'a = os.environ["SUB"]\n'
        'b = os.environ.get("GET")\n'
        'c = os.getenv("ENV")\n'
    )
    assert _walk_env_reads(source) == frozenset({"SUB", "GET", "ENV"})


def test_bash_external_var_reads_drops_assigned_keeps_external(tmp_path: Path):
    """
    GIVEN a synthetic bash script that reads one external var and assigns then
        reads another
    WHEN the external reads are scanned
    THEN only the externally-sourced var is returned and the assigned-then-read
        var is dropped.
    """
    script_path = tmp_path / "synthetic.sh"
    script_path.write_text(
        '#!/bin/bash\necho "$EXTERNAL"\nLOCAL_VAR=computed\necho "$LOCAL_VAR"\n'
    )
    assert _bash_external_var_reads((script_path,)) == frozenset({"EXTERNAL"})


def test_assemble_metrics_redis_uri_percent_encodes_password():
    """
    GIVEN a password with URL-reserved characters, an empty password, and a
        password containing a slash
    WHEN the metrics Redis URI is assembled
    THEN reserved chars are percent-encoded, empty yields an empty userinfo, and
        '/' is left unencoded (documenting urllib.parse.quote's default).
    """
    assert (
        assemble_metrics_redis_uri(redis_password="p@ssword")
        == "redis://:p%40ssword@redis-metrics:6379/0"
    )
    assert (
        assemble_metrics_redis_uri(redis_password="")
        == "redis://:@redis-metrics:6379/0"
    )
    assert (
        assemble_metrics_redis_uri(redis_password="a/b")
        == "redis://:a/b@redis-metrics:6379/0"
    )


def test_render_env_dump_filters_to_allow_list_and_present_only():
    """
    GIVEN an env mapping with allow-listed vars, an unset allow-listed var, and a
        non-allow-listed secret
    WHEN the dump is rendered
    THEN only present allow-listed vars are emitted, in ALLOW_VARS order, and the
        non-allow-listed secret is excluded.
    """
    env_mapping = {
        "POSTGRES_DB": "u4i",
        "PRODUCTION": "true",
        "REDIS_PASSWORD": "should-not-appear",
        "ACCESS_KEY": "abc123",
    }
    dump = render_env_dump(env_mapping=env_mapping)
    assert dump == "ACCESS_KEY=abc123\nPOSTGRES_DB=u4i\nPRODUCTION=true\n"
    assert "REDIS_PASSWORD" not in dump


def test_read_secret_files_strips_trailing_newline_and_handles_missing_dir(
    tmp_path: Path,
):
    """
    GIVEN a secrets directory with files ending in a trailing newline
    WHEN the secret files are read
    THEN each value is keyed by basename with the trailing newline stripped, and
        a missing directory yields an empty mapping.
    """
    (tmp_path / "REDIS_PASSWORD").write_text("hunter2\n")
    (tmp_path / "POSTGRES_USER").write_text("u4i")
    assert read_secret_files(secrets_dir=tmp_path) == {
        "REDIS_PASSWORD": "hunter2",
        "POSTGRES_USER": "u4i",
    }
    assert read_secret_files(secrets_dir=tmp_path / "missing") == {}


def test_build_env_mapping_production_merges_secrets_and_assembles_uri():
    """
    GIVEN production mode with secrets and a pre-existing METRICS_REDIS_URI
    WHEN the env mapping is built
    THEN secrets override the base env and METRICS_REDIS_URI is re-assembled with
        the percent-encoded password.
    """
    mapping = build_env_mapping(
        base_environ={"PRODUCTION": "true", "METRICS_REDIS_URI": "stale"},
        secrets={"REDIS_PASSWORD": "p@ss", "POSTGRES_DB": "u4i"},
        production=True,
    )
    assert mapping["POSTGRES_DB"] == "u4i"
    assert mapping["METRICS_REDIS_URI"] == "redis://:p%40ss@redis-metrics:6379/0"


def test_build_env_mapping_production_absent_redis_password_yields_empty_userinfo():
    """
    GIVEN production mode with no REDIS_PASSWORD secret
    WHEN the env mapping is built
    THEN METRICS_REDIS_URI falls back to an empty userinfo.
    """
    mapping = build_env_mapping(base_environ={}, secrets={}, production=True)
    assert mapping["METRICS_REDIS_URI"] == "redis://:@redis-metrics:6379/0"


def test_build_env_mapping_non_production_passes_through():
    """
    GIVEN non-production mode
    WHEN the env mapping is built
    THEN the base environment is returned unchanged and secrets are ignored.
    """
    base = {"PRODUCTION": "false", "METRICS_REDIS_URI": "redis://compose-injected"}
    mapping = build_env_mapping(
        base_environ=base, secrets={"REDIS_PASSWORD": "ignored"}, production=False
    )
    assert mapping == base
    assert "REDIS_PASSWORD" not in mapping
