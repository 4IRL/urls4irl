"""Unit tests pinning the Makefile's Compose profile wiring via `make -n` dry runs.

A dry run prints each recipe line without executing it, so these tests need no
Docker, mise or running stack: they assert on the compose commands `up`,
`up-built`, `down`, `build` and `restart` would run, and on the parse-time
validation of `p=` / `c=`. The profile map itself is pinned by
`test_compose_profiles.py`.

The Makefile is not copied into the `web` image and the image has no `make`, so
these tests skip inside the container and run host-side (and in CI's unit job).
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
MAKEFILE: Path = REPO_ROOT / "Makefile"
MAKE_BINARY: str | None = shutil.which("make")

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        MAKE_BINARY is None or not MAKEFILE.is_file(),
        reason="needs `make` and the repo Makefile (absent inside the web container)",
    ),
]

# Inherited make state (e.g. pytest launched from a make recipe) must not leak an outer p/c/d into the dry run.
INHERITED_MAKE_VARIABLES: frozenset[str] = frozenset(
    {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES", "p", "c", "d"}
)
ALL_PROFILES_FLAG: str = "--profile '*'"


def _dry_run(*make_args: str) -> subprocess.CompletedProcess[str]:
    assert MAKE_BINARY is not None
    clean_env = {
        name: value
        for name, value in os.environ.items()
        if name not in INHERITED_MAKE_VARIABLES
    }
    return subprocess.run(
        [MAKE_BINARY, "--no-print-directory", "-n", *make_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=clean_env,
        check=False,
    )


def _successful_dry_run(*make_args: str) -> str:
    result = _dry_run(*make_args)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _single_line_containing(output: str, marker: str) -> str:
    matching_lines = [line for line in output.splitlines() if marker in line]
    assert len(matching_lines) == 1, (
        f"expected one line containing {marker!r}, got: {matching_lines}"
    )
    return matching_lines[0]


def _compose_up_line(output: str) -> str:
    return _single_line_containing(output, " up --build ")


def _profile_narrow_config_line(output: str) -> str:
    return _single_line_containing(output, " config --services")


def test_up_with_ui_profile_passes_it_to_compose() -> None:
    up_line = _compose_up_line(_successful_dry_run("up", "p=ui"))
    assert "--profile ui " in up_line


def test_up_without_profile_starts_only_the_core() -> None:
    output = _successful_dry_run("up")
    assert "--profile" not in _compose_up_line(output)
    assert "--profile" not in _profile_narrow_config_line(output)


@pytest.mark.parametrize(
    ("make_args", "expected_profile"),
    [
        pytest.param(("up-built",), "ui", id="defaults-to-ui"),
        pytest.param(("up-built", "p=full"), "full", id="explicit-full"),
    ],
)
def test_up_built_narrows_and_starts_the_same_profile(
    make_args: tuple[str, ...], expected_profile: str
) -> None:
    output = _successful_dry_run(*make_args)
    expected_flag = f"--profile {expected_profile} "
    assert expected_flag in _profile_narrow_config_line(output)
    up_line = _compose_up_line(output)
    assert "-f docker/compose.built.yaml" in up_line
    assert expected_flag in up_line


@pytest.mark.parametrize(
    ("profile_value", "expected_message"),
    [
        pytest.param("bogus", "p must be one of", id="unknown-profile"),
        pytest.param("ui full", "p takes one profile", id="two-profiles"),
    ],
)
def test_up_rejects_invalid_profile(profile_value: str, expected_message: str) -> None:
    result = _dry_run("up", f"p={profile_value}")
    assert result.returncode != 0
    assert expected_message in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("make_target", "variable_name", "expected_message"),
    [
        pytest.param("up", "p", "p must not contain '$'", id="p"),
        pytest.param("restart", "c", "c must not contain '$'", id="c"),
    ],
)
@pytest.mark.parametrize(
    "function_syntax",
    [
        pytest.param("$({call})", id="parens"),
        pytest.param("${{{call}}}", id="braces"),
    ],
)
def test_dollar_bearing_variable_is_rejected_before_expansion(
    tmp_path: Path,
    make_target: str,
    variable_name: str,
    expected_message: str,
    function_syntax: str,
) -> None:
    probe_file = tmp_path / "probe"
    payload = function_syntax.format(call=f"shell touch {probe_file}")
    result = _dry_run(make_target, f"{variable_name}=ui{payload}")
    assert result.returncode != 0
    assert expected_message in result.stderr
    assert not probe_file.exists(), "the embedded $(shell …) ran before the guard"


def test_restart_requires_a_service() -> None:
    result = _dry_run("restart")
    assert result.returncode != 0
    assert "c=<service> is required" in result.stderr


def test_restart_reaches_every_profile() -> None:
    restart_line = _single_line_containing(
        _successful_dry_run("restart", "c=playwright"), " restart "
    )
    assert f"{ALL_PROFILES_FLAG} restart playwright" in restart_line


@pytest.mark.parametrize("make_target", ["down", "build"])
def test_lifecycle_targets_reach_every_profile(make_target: str) -> None:
    lifecycle_line = _single_line_containing(
        _successful_dry_run(make_target), f" {make_target}"
    )
    assert lifecycle_line.endswith(f"{ALL_PROFILES_FLAG} {make_target}")
