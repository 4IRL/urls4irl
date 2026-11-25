"""Parity between `make generate-types` and the `types-staleness.yml` CI job.

CI regenerates the committed `frontend/types/` files and diffs them, so the job must
run the same generate commands, to the same paths, and prettier the same files as the
Makefile recipe. `metrics-flows.ts` (and its generate-flows step) is deliberately left
to `event-coverage-staleness.yml`.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
MAKEFILE: Path = REPO_ROOT / "Makefile"
WORKFLOW: Path = REPO_ROOT / ".github" / "workflows" / "types-staleness.yml"

FLOWS_FILE: str = "frontend/types/metrics-flows.ts"
CONTAINER_ROOT: str = "/code/u4i/"
FLASK_GENERATE: re.Pattern[str] = re.compile(
    r"(?:flask|\$\(FLASK\)) ((?:openapi|metrics) generate[\w-]*) --output (\S+?)(?: --strict)?\"?$"
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        not (MAKEFILE.is_file() and WORKFLOW.is_file()),
        reason="needs the repo Makefile and workflow (absent inside the web container)",
    ),
]


def _recipe_lines() -> list[str]:
    lines: list[str] = MAKEFILE.read_text(encoding="utf-8").splitlines()
    start: int = next(
        index for index, line in enumerate(lines) if line.startswith("generate-types:")
    )
    recipe: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith("\t"):
            break
        recipe.append(line.strip())
    return recipe


def _flask_generates(lines: list[str], *, prefix: str) -> dict[str, str]:
    """Map each `flask <group> generate*` subcommand to its repo-relative output path."""
    generates: dict[str, str] = {}
    for line in lines:
        match = FLASK_GENERATE.search(line)
        if match is None:
            continue
        subcommand, output = match.group(1), match.group(2)
        generates[subcommand] = output.removeprefix(prefix)
    return generates


def _makefile_prettier_files() -> set[str]:
    for line in _recipe_lines():
        if "prettier --write" in line:
            return set(line.split("prettier --write", 1)[1].split())
    raise AssertionError("no prettier --write line in generate-types")


def _workflow_run_lines() -> list[str]:
    return [
        line.strip().removeprefix("run:").strip()
        for line in WORKFLOW.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("run:")
    ]


def _workflow_prettier_files() -> set[str]:
    for line in _workflow_run_lines():
        if "prettier --write" in line:
            return {
                f"frontend/{path}"
                for path in line.split("prettier --write", 1)[1].split()
            }
    raise AssertionError("no prettier --write step in types-staleness.yml")


def test_workflow_runs_the_makefile_generate_commands() -> None:
    """
    GIVEN the Makefile generate-types recipe and the staleness workflow
    WHEN their flask generate commands are compared (minus the flows file)
    THEN the workflow runs the same commands to the same output paths
    """
    makefile_generates: dict[str, str] = _flask_generates(
        _recipe_lines(), prefix=CONTAINER_ROOT
    )
    makefile_generates = {
        command: output
        for command, output in makefile_generates.items()
        if output != FLOWS_FILE
    }
    workflow_generates: dict[str, str] = _flask_generates(
        _workflow_run_lines(), prefix=""
    )
    assert "openapi generate-error-codes" in makefile_generates
    assert len(makefile_generates) >= 6
    assert workflow_generates == makefile_generates


def test_workflow_prettier_list_matches_the_makefile() -> None:
    """
    GIVEN the prettier file lists in the Makefile and the workflow
    WHEN they are compared (minus the flows file)
    THEN they are identical
    """
    expected: set[str] = _makefile_prettier_files() - {FLOWS_FILE}
    assert _workflow_prettier_files() == expected


def test_workflow_leaves_the_flows_file_to_the_event_coverage_job() -> None:
    """
    GIVEN the staleness workflow
    WHEN its generate commands are inspected
    THEN it omits generate-flows while the Makefile still prettiers the flows file
    """
    generates: dict[str, str] = _flask_generates(_workflow_run_lines(), prefix="")
    assert "metrics generate-flows" not in generates
    assert FLOWS_FILE in _makefile_prettier_files()


def test_workflow_disables_metrics_recording() -> None:
    """
    GIVEN the staleness workflow
    WHEN its env is read
    THEN METRICS_ENABLED is set to false
    """
    pattern: re.Pattern[str] = re.compile(
        r"^\s*METRICS_ENABLED:\s*['\"]?false['\"]?\s*$", re.MULTILINE
    )
    assert pattern.search(WORKFLOW.read_text(encoding="utf-8"))
