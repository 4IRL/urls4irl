"""Pin the pre-deploy log dump step in `.github/workflows/prod-deploy.yml`.

The step's remote script is extracted from the workflow and run against a fake `docker` on PATH, with the
dump directory pointed at a tmp path, so the real text that ships is what gets exercised.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
WORKFLOWS: Path = REPO_ROOT / ".github" / "workflows"
PROD_DEPLOY: Path = WORKFLOWS / "prod-deploy.yml"

# `.github/` is not mounted into the `web` image, so the module skips there and runs host-side.
# The skip looks at the workflows directory, never at the file under test: a missing file must fail.
pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        not WORKFLOWS.is_dir(),
        reason="needs the repo's .github/workflows (absent inside the web container)",
    ),
]
DUMP_STEP_NAME: str = "Dump Pre-Deploy Logs"
BUILD_STEP_NAME: str = "Build Docker Network"
DUMP_DIR: str = "/home/u4i/deploy-logs"
CONTAINERS: tuple[str, ...] = ("u4i-prod-flask", "u4i-prod-workflow")
PRUNE_DAYS: int = 90
SECONDS_PER_DAY: int = 86400

# `container inspect <name>` succeeds only for names listed in FAKE_PRESENT; `logs` records its argv to
# FAKE_ARGV_LOG, exits 1 when FAKE_LOGS_FAIL is set, and otherwise prints one stdout and one stderr line so
# the test can see both streams land in the dump.
FAKE_DOCKER: str = """#!/bin/sh
case "$1" in
  container)
    case " $FAKE_PRESENT " in *" $3 "*) exit 0 ;; esac
    exit 1
    ;;
  logs)
    echo "$*" >> "$FAKE_ARGV_LOG"
    if [ -n "$FAKE_LOGS_FAIL" ]; then exit 1; fi
    echo "stdout line"
    echo "stderr line" >&2
    ;;
esac
"""


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(PROD_DEPLOY.read_text())
    return workflow["jobs"]["ProdDeploy"]["steps"]


def _index(name: str) -> int:
    return next(
        index for index, step in enumerate(_steps()) if step.get("name") == name
    )


def _remote_script() -> str:
    run = _steps()[_index(DUMP_STEP_NAME)]["run"]
    assert run.count("'") == 2, "the remote script must not contain single quotes"
    return run.split("'", 2)[1]


def _run_remote(
    tmp_path: Path,
    dump_dir: Path,
    present: str,
    fail: bool = False,
    prune_fails: bool = False,
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    fake = bin_dir / "docker"
    fake.write_text(FAKE_DOCKER)
    fake.chmod(0o755)
    if prune_fails:
        # The script calls find only for the prune.
        fake_find = bin_dir / "find"
        fake_find.write_text("#!/bin/sh\nexit 1\n")
        fake_find.chmod(0o755)
    script = _remote_script().replace(DUMP_DIR, str(dump_dir))
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_PRESENT": present,
        "FAKE_ARGV_LOG": str(tmp_path / "docker-argv.log"),
        "FAKE_LOGS_FAIL": "1" if fail else "",
    }
    return subprocess.run(
        ["bash", "-c", script], env=env, capture_output=True, text=True, check=False
    )


def test_dump_step_precedes_build_docker_network():
    """
    GIVEN the production deploy steps
    WHEN the dump step and the build step are located
    THEN the dump runs first, and the build step no longer dumps logs itself.
    """
    assert _index(DUMP_STEP_NAME) < _index(BUILD_STEP_NAME)
    assert "docker logs" not in _steps()[_index(BUILD_STEP_NAME)]["run"]


def test_remote_script_is_failure_visible_and_uses_the_fixed_dir():
    """
    GIVEN the dump step's remote script
    WHEN its commands are read
    THEN it starts with set -e, writes under the fixed host dir and dumps every app container.
    """
    remote = _remote_script()
    commands = [line.strip() for line in remote.splitlines() if line.strip()]

    assert commands[0] == "set -e"
    assert f"mkdir -p {DUMP_DIR}" in remote
    for container in CONTAINERS:
        assert container in remote


def test_log_directory_secret_is_gone():
    """
    GIVEN every workflow file
    WHEN its text is read
    THEN none still references the PROD_LOG_DIRECTORY secret.
    """
    for workflow in WORKFLOWS.glob("*.yml"):
        assert "PROD_LOG_DIRECTORY" not in workflow.read_text(), workflow.name


def test_dumps_both_streams_of_every_present_container(tmp_path: Path):
    """
    GIVEN both app containers exist
    WHEN the remote script runs
    THEN each gets one dump file holding its stdout and stderr lines.
    """
    dump_dir = tmp_path / "deploy-logs"

    result = _run_remote(tmp_path, dump_dir, present=" ".join(CONTAINERS))

    assert result.returncode == 0, result.stderr
    stamps = set()
    for container in CONTAINERS:
        dumps = list(dump_dir.glob(f"{container}_*.log"))
        assert len(dumps) == 1
        match = re.fullmatch(rf"{container}_(\d{{8}}T\d{{6}}Z)\.log", dumps[0].name)
        assert match, dumps[0].name
        stamps.add(match.group(1))
        assert dumps[0].read_text().splitlines() == ["stdout line", "stderr line"]
        assert f"dumped {container}: 2 lines" in result.stdout
    assert len(stamps) == 1
    recorded = (tmp_path / "docker-argv.log").read_text().splitlines()
    assert recorded == [f"logs --timestamps --since=24h {name}" for name in CONTAINERS]


def test_no_containers_skips_both_and_succeeds(tmp_path: Path):
    """
    GIVEN neither app container exists (a fresh host)
    WHEN the remote script runs
    THEN both are reported as skipped and the step succeeds.
    """
    result = _run_remote(tmp_path, tmp_path / "deploy-logs", present="")

    assert result.returncode == 0, result.stderr
    for container in CONTAINERS:
        assert f"skipped {container}: no such container" in result.stdout


def test_failing_docker_logs_aborts_the_step(tmp_path: Path):
    """
    GIVEN `docker logs` fails
    WHEN the remote script runs
    THEN it exits non-zero before reaching the second container.
    """
    result = _run_remote(
        tmp_path, tmp_path / "deploy-logs", present=" ".join(CONTAINERS), fail=True
    )

    assert result.returncode != 0
    assert "u4i-prod-workflow" not in result.stdout


def test_missing_container_is_skipped_not_fatal(tmp_path: Path):
    """
    GIVEN only the flask container exists
    WHEN the remote script runs
    THEN flask is dumped, workflow is reported as skipped and the step still succeeds.
    """
    dump_dir = tmp_path / "deploy-logs"

    result = _run_remote(tmp_path, dump_dir, present="u4i-prod-flask")

    assert result.returncode == 0, result.stderr
    assert len(list(dump_dir.glob("u4i-prod-flask_*.log"))) == 1
    assert not list(dump_dir.glob("u4i-prod-workflow_*.log"))
    assert "skipped u4i-prod-workflow: no such container" in result.stdout


def test_unwritable_dump_dir_fails_the_step(tmp_path: Path):
    """
    GIVEN the dump directory path is occupied by a regular file
    WHEN the remote script runs
    THEN it exits non-zero instead of carrying on silently.
    """
    blocker = tmp_path / "deploy-logs"
    blocker.write_text("not a directory")

    result = _run_remote(tmp_path, blocker, present=" ".join(CONTAINERS))

    assert result.returncode != 0
    assert "dumped" not in result.stdout


def test_prunes_only_dumps_older_than_the_retention(tmp_path: Path):
    """
    GIVEN one dump older than the retention and one recent dump
    WHEN the remote script runs
    THEN the old dump is deleted and the recent one is kept.
    """
    dump_dir = tmp_path / "deploy-logs"
    dump_dir.mkdir()
    old = dump_dir / "u4i-prod-flask_20260101T000000Z.log"
    recent = dump_dir / "u4i-prod-flask_20261120T000000Z.log"
    inside_window = dump_dir / "u4i-prod-flask_20260901T000000Z.log"
    old_other = dump_dir / "notes.txt"
    subdir = dump_dir / "archive"
    subdir.mkdir()
    old_nested = subdir / "u4i-prod-flask_20260101T000000Z.log"
    for path in (old, recent, inside_window, old_other, old_nested):
        path.write_text(path.name)
    now = time.time()
    stale = now - (PRUNE_DAYS + 5) * SECONDS_PER_DAY
    for path in (old, old_other, old_nested):
        os.utime(path, (stale, stale))
    inside = now - (PRUNE_DAYS - 5) * SECONDS_PER_DAY
    os.utime(inside_window, (inside, inside))

    result = _run_remote(tmp_path, dump_dir, present="")

    assert result.returncode == 0, result.stderr
    assert f"-mtime +{PRUNE_DAYS}" in _remote_script()
    assert not old.exists()
    assert recent.exists()
    assert inside_window.exists()
    assert old_other.exists()
    assert old_nested.exists()


def test_failing_prune_only_warns(tmp_path: Path):
    """
    GIVEN the prune `find` fails
    WHEN the remote script runs
    THEN the dumps are still written, the step succeeds and a WARNING is printed.
    """
    dump_dir = tmp_path / "deploy-logs"

    result = _run_remote(
        tmp_path, dump_dir, present=" ".join(CONTAINERS), prune_fails=True
    )

    assert result.returncode == 0, result.stderr
    for container in CONTAINERS:
        assert len(list(dump_dir.glob(f"{container}_*.log"))) == 1
    assert "WARNING: pruning old deploy log dumps failed" in result.stdout
