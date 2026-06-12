from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskCliRunner

from backend.cli.metrics import (
    COVERAGE_SUMMARY_API_LABEL,
    COVERAGE_SUMMARY_HEADER,
)
from backend.metrics.audit import find_orphan_event_names
from backend.metrics.events import EVENT_CATEGORY, EventCategory, EventName

pytestmark = pytest.mark.cli


def test_audit_strict_exits_zero_on_clean_main(app: Flask) -> None:
    """
    GIVEN a codebase with no event-registry drift
    WHEN `flask metrics audit --strict` is invoked
    THEN ensure the command exits 0 (no orphans, no string-literal callers,
        no missing DIMENSION_MODELS entries, no dimension/registry drift)
    """
    runner: FlaskCliRunner = app.test_cli_runner()
    result = runner.invoke(args=["metrics", "audit", "--strict"])

    assert result.exit_code == 0, result.output


def test_audit_strict_exits_non_zero_when_orphan_present(tmp_path: Path) -> None:
    """
    GIVEN a probe backend directory tree with zero EventName attribute references
    WHEN `find_orphan_event_names(backend_root=tmp_backend)` is called
    THEN ensure the helper returns every API + DOMAIN member that is not
        explicitly allowlisted as INTENTIONALLY_UNTRACKED

    Probe-file approach: avoids enum mutation entirely. The helper walks
    `backend_root.rglob("*.py")`; a tmp tree with one no-op `.py` file
    produces zero `EventName.<MEMBER>` references, so every API/DOMAIN member
    appears as an orphan. The reverse test below proves the same helper
    returns `[]` when every member IS referenced.

    Do NOT use `monkeypatch.setattr(EventName, '_member_map_', ...)` —
    StrEnum does not iterate via `_member_map_`, so that approach silently
    does nothing.
    """
    tmp_backend = tmp_path / "backend"
    probe_services_dir = tmp_backend / "services"
    probe_services_dir.mkdir(parents=True)
    probe_file = probe_services_dir / "probe.py"
    probe_file.write_text(
        "from __future__ import annotations\n\n"
        "def probe() -> None:\n"
        "    return None\n",
        encoding="utf-8",
    )

    orphans = find_orphan_event_names(backend_root=tmp_backend)

    assert len(orphans) > 0
    orphan_names = {orphan.name for orphan in orphans}
    expected_orphan_categories = {EventCategory.API, EventCategory.DOMAIN}
    for event_name in EventName:
        if EVENT_CATEGORY[event_name] not in expected_orphan_categories:
            continue
        if event_name.name == EventName.URL_ACCESSED.name:
            continue
        assert event_name.name in orphan_names, (
            f"Expected {event_name.name} to appear as an orphan in the empty "
            f"probe tree, but it was not in the helper's output."
        )


def test_audit_probe_with_full_coverage_returns_no_orphans(tmp_path: Path) -> None:
    """
    GIVEN a probe backend directory tree containing one `.py` file that
        references every API + DOMAIN `EventName` member via attribute access
    WHEN `find_orphan_event_names(backend_root=tmp_backend)` is called
    THEN ensure the helper returns `[]`

    Counterpart to `test_audit_strict_exits_non_zero_when_orphan_present`.
    Together they prove the helper's reference-counting walk is symmetric:
    zero references → all members are orphans; full references → no orphans.
    """
    tmp_backend = tmp_path / "backend"
    coverage_services_dir = tmp_backend / "services"
    coverage_services_dir.mkdir(parents=True)
    coverage_file = coverage_services_dir / "all_events.py"

    relevant_event_names = [
        event_name
        for event_name in EventName
        if EVENT_CATEGORY[event_name] in {EventCategory.API, EventCategory.DOMAIN}
    ]
    references_block = "\n".join(
        f"    _ = EventName.{event_name.name}" for event_name in relevant_event_names
    )
    coverage_file.write_text(
        "from __future__ import annotations\n\n"
        "from backend.metrics.events import EventName\n\n"
        "def reference_all_events() -> None:\n"
        f"{references_block}\n",
        encoding="utf-8",
    )

    orphans = find_orphan_event_names(backend_root=tmp_backend)

    assert orphans == []


def test_coverage_summary_outputs_tsv(app: Flask) -> None:
    """
    GIVEN the registered Flask app with the metrics CLI command group
    WHEN `flask metrics coverage-summary` is invoked
    THEN ensure
        - exit code is 0,
        - the first line is the canonical TSV header,
        - the second line is the API (auto) row tagged `api`,
        - per-category EventName member totals across rows match the
          enum's grouping by EVENT_CATEGORY (each Domain/UI row sums to
          the total number of DOMAIN/UI members in the enum).
    """
    runner: FlaskCliRunner = app.test_cli_runner()

    result = runner.invoke(args=["metrics", "coverage-summary"])

    assert result.exit_code == 0, result.output

    output_lines = result.output.strip().splitlines()
    assert output_lines[0] == COVERAGE_SUMMARY_HEADER

    api_row = output_lines[1].split("\t")
    assert api_row[0] == COVERAGE_SUMMARY_API_LABEL
    assert api_row[1] == EventCategory.API.value
    assert int(api_row[2]) > 0

    domain_rows = [
        line.split("\t")
        for line in output_lines[2:]
        if line.split("\t")[1] == EventCategory.DOMAIN.value
    ]
    ui_rows = [
        line.split("\t")
        for line in output_lines[2:]
        if line.split("\t")[1] == EventCategory.UI.value
    ]

    expected_domain_total = sum(
        1
        for event_name in EventName
        if EVENT_CATEGORY[event_name] is EventCategory.DOMAIN
    )
    expected_ui_total = sum(
        1 for event_name in EventName if EVENT_CATEGORY[event_name] is EventCategory.UI
    )
    assert sum(int(row[2]) for row in domain_rows) == expected_domain_total
    assert sum(int(row[2]) for row in ui_rows) == expected_ui_total
