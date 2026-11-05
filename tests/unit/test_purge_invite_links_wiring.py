"""Wiring test: the invite-link purge is shipped and scheduled at 5 AM.

Reads the workflow Dockerfile and crontab as text so a missing or commented-out
COPY / chmod / cron line fails the build instead of silently never running.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_DOCKERFILE: Path = _PROJECT_ROOT / "docker" / "Dockerfile.Workflow"
_CRONTAB: Path = _PROJECT_ROOT / "docker" / "crontab.workflow"
_SCRIPT_NAME: str = "purge_invite_links.py"


def _active_lines(path: Path) -> list[str]:
    return [
        stripped
        for stripped in (line.strip() for line in path.read_text().splitlines())
        if stripped and not stripped.startswith("#")
    ]


def test_dockerfile_copies_the_purge_script() -> None:
    """
    GIVEN docker/Dockerfile.Workflow
    WHEN its active lines are scanned
    THEN a COPY of purge_invite_links.py into /app exists.
    """
    assert any(
        line.startswith("COPY")
        and f"scripts/{_SCRIPT_NAME}" in line
        and f"/app/{_SCRIPT_NAME}" in line
        for line in _active_lines(_DOCKERFILE)
    )


def test_dockerfile_marks_the_purge_script_executable() -> None:
    """
    GIVEN docker/Dockerfile.Workflow
    WHEN its active lines are scanned
    THEN a chmod +x of /app/purge_invite_links.py exists.
    """
    assert any(
        f"chmod +x /app/{_SCRIPT_NAME}" in line for line in _active_lines(_DOCKERFILE)
    )


def test_crontab_runs_the_purge_script_daily_at_five_am() -> None:
    """
    GIVEN docker/crontab.workflow
    WHEN its non-comment lines are scanned
    THEN an active schedule line at minute 0, hour 5 invokes /app/purge_invite_links.py.
    """
    assert any(
        f"/app/{_SCRIPT_NAME}" in line and line.startswith("0 5 * * * ")
        for line in _active_lines(_CRONTAB)
    )
