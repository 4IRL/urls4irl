"""Parity between the markers declared in `pytest.ini` and the CI integration matrix.

A marker declared in `pytest.ini` without a `Tests-Integration` matrix row in
`.github/workflows/test.yml` is silently never run in CI. This test fails the moment
that happens, instead of waiting for a real CI run to notice.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.affected_markers import (
    PYTEST_INI,
    REPO_ROOT,
    UI_SUFFIX,
    read_declared_markers,
)

pytestmark = pytest.mark.unit

TEST_WORKFLOW: Path = REPO_ROOT / ".github" / "workflows" / "test.yml"


@pytest.mark.skipif(
    not TEST_WORKFLOW.exists(),
    reason=".github is not mounted in web; runs on the host and in CI",
)
def test_every_declared_integration_marker_has_a_ci_matrix_row() -> None:
    """
    GIVEN the markers declared in pytest.ini
    WHEN they are compared with the Tests-Integration matrix in test.yml
    THEN every non-UI marker has a matrix row, so CI actually runs it
    """
    workflow = yaml.safe_load(TEST_WORKFLOW.read_text())
    matrix_rows: list[list[object]] = workflow["jobs"]["Tests-Integration"]["strategy"][
        "matrix"
    ]["worker"]
    matrix_markers: set[str] = {str(row[1]) for row in matrix_rows}

    integration_markers: set[str] = {
        marker
        for marker in read_declared_markers(PYTEST_INI)
        if not marker.endswith(UI_SUFFIX)
    }

    missing = sorted(integration_markers - matrix_markers)
    assert not missing, (
        f"pytest.ini markers with no Tests-Integration matrix row in {TEST_WORKFLOW.name}: "
        f"{missing}"
    )
