"""Wiring test: the expired short-link purge is shipped and scheduled.

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
_SCRIPT_NAME: str = "purge_short_links.py"


def _active_lines(path: Path) -> list[str]:
    return [
        stripped
        for stripped in (line.strip() for line in path.read_text().splitlines())
        if stripped and not stripped.startswith("#")
    ]


def test_dockerfile_copies_the_purge_script():
    """
    GIVEN docker/Dockerfile.Workflow
    WHEN its active lines are scanned
    THEN a COPY of purge_short_links.py into /app exists.
    """
    assert any(
        line.startswith("COPY")
        and f"scripts/{_SCRIPT_NAME}" in line
        and f"/app/{_SCRIPT_NAME}" in line
        for line in _active_lines(_DOCKERFILE)
    )


def test_dockerfile_marks_the_purge_script_executable():
    """
    GIVEN docker/Dockerfile.Workflow
    WHEN its active lines are scanned
    THEN a chmod +x of /app/purge_short_links.py exists.
    """
    assert any(
        f"chmod +x /app/{_SCRIPT_NAME}" in line for line in _active_lines(_DOCKERFILE)
    )


def test_crontab_has_an_active_schedule_line_for_the_purge_script():
    """
    GIVEN docker/crontab.workflow
    WHEN its non-comment lines are scanned
    THEN a schedule line invokes /app/purge_short_links.py.
    """
    assert any(
        f"/app/{_SCRIPT_NAME}" in line and line[0] in "0123456789*"
        for line in _active_lines(_CRONTAB)
    )
