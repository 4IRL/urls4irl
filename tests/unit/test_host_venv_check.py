"""Unit tests for `scripts/host_venv_check.sh` (shared by `_host-static-run` and `hooks`).

The script is run against stub python executables (tiny shell scripts that print a version), so no
real interpreter or mise is needed. Host-static: skips inside `web` (no `scripts/*.sh` run there).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SCRIPT: Path = REPO_ROOT / "scripts" / "host_venv_check.sh"
REBUILT_EXIT: int = 3
BASH: str | None = shutil.which("bash")

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        BASH is None or not SCRIPT.exists(), reason="needs bash and scripts/"
    ),
]


def _stub_python(path: Path, version_output: str, exit_code: int = 0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'#!/bin/sh\necho "{version_output}"\nexit {exit_code}\n')
    path.chmod(0o755)
    return path


def _make_venv(root: Path, version: str) -> Path:
    venv = root / "venv"
    _stub_python(venv / "bin" / "python", version)
    (venv / ".u4i-host-static.stamp").write_text("")
    return venv


def _run(root: Path, expected_python: Path) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(
        [BASH, str(SCRIPT), str(root), str(expected_python)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_mismatched_venv_is_deleted_and_the_log_names_both_versions(
    tmp_path: Path,
) -> None:
    """
    GIVEN a venv on 3.12 and a pinned python on 3.14
    WHEN the check runs
    THEN venv/ (with its stamp) is deleted, the rebuilt exit code is returned and the log names both
    """
    venv = _make_venv(tmp_path, "3.12")
    expected = _stub_python(tmp_path / "pinned" / "python", "3.14")

    result = _run(tmp_path, expected)

    assert result.returncode == REBUILT_EXIT, result.stderr
    assert not venv.exists()
    assert "3.12" in result.stdout and "3.14" in result.stdout


def test_matching_venv_is_left_untouched_without_a_log_line(tmp_path: Path) -> None:
    """
    GIVEN a venv on the pinned major.minor
    WHEN the check runs
    THEN venv/ and its stamp survive, the exit code is 0 and nothing is logged
    """
    venv = _make_venv(tmp_path, "3.14")
    expected = _stub_python(tmp_path / "pinned" / "python", "3.14")

    result = _run(tmp_path, expected)

    assert result.returncode == 0, result.stderr
    assert (venv / "bin" / "python").exists()
    assert (venv / ".u4i-host-static.stamp").exists()
    assert result.stdout == ""


def test_missing_venv_is_a_no_op(tmp_path: Path) -> None:
    """
    GIVEN no venv/ at all
    WHEN the check runs
    THEN it exits 0 and creates nothing (the caller creates the venv)
    """
    expected = _stub_python(tmp_path / "pinned" / "python", "3.14")

    result = _run(tmp_path, expected)

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "venv").exists()


def test_broken_symlink_venv_python_counts_as_a_mismatch(tmp_path: Path) -> None:
    """
    GIVEN a venv whose bin/python is a dangling symlink (the old interpreter was uninstalled)
    WHEN the check runs
    THEN venv/ is deleted
    """
    venv = _make_venv(tmp_path, "3.12")
    python = venv / "bin" / "python"
    python.unlink()
    python.symlink_to(tmp_path / "uninstalled" / "python3.12")
    expected = _stub_python(tmp_path / "pinned" / "python", "3.14")

    result = _run(tmp_path, expected)

    assert result.returncode == REBUILT_EXIT, result.stderr
    assert not venv.exists()


@pytest.mark.parametrize(
    "version_output, exit_code",
    [("3.14", 1), ("not-a-version", 0), ("", 0), ("3.14.10", 0)],
)
def test_unresolvable_expected_python_fails_closed(
    tmp_path: Path, version_output: str, exit_code: int
) -> None:
    """
    GIVEN an expected-python command that fails or prints no parseable major.minor
    WHEN the check runs
    THEN it exits nonzero (not the rebuilt code) and leaves venv/ untouched
    """
    venv = _make_venv(tmp_path, "3.12")
    expected = _stub_python(tmp_path / "pinned" / "python", version_output, exit_code)

    result = _run(tmp_path, expected)

    assert result.returncode not in (0, REBUILT_EXIT)
    assert (venv / "bin" / "python").exists()
    assert (venv / ".u4i-host-static.stamp").exists()


def test_too_few_arguments_fail_closed_with_usage(tmp_path: Path) -> None:
    """
    GIVEN only the primary root and no expected-python command
    WHEN the check runs
    THEN it exits 1 and stderr prints the usage line
    """
    assert BASH is not None

    result = subprocess.run(
        [BASH, str(SCRIPT), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "usage" in result.stderr


def test_non_directory_root_fails_closed(tmp_path: Path) -> None:
    """
    GIVEN a primary root that does not exist
    WHEN the check runs
    THEN it exits 1 and stderr names the missing directory
    """
    expected = _stub_python(tmp_path / "pinned" / "python", "3.14")
    missing = tmp_path / "no-such-root"

    result = _run(missing, expected)

    assert result.returncode == 1
    assert "not a directory" in result.stderr
    assert str(missing) in result.stderr


def test_missing_expected_python_executable_fails_closed(tmp_path: Path) -> None:
    """
    GIVEN an expected-python command that does not exist
    WHEN the check runs
    THEN it exits nonzero and leaves venv/ untouched
    """
    venv = _make_venv(tmp_path, "3.12")

    result = _run(tmp_path, tmp_path / "no-such-python")

    assert result.returncode not in (0, REBUILT_EXIT)
    assert venv.exists()
