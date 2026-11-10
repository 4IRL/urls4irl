"""Pin `scripts/notifs-resolve-release-sha.sh`, the one script that picks the manifest commit.

Host-static: runs the real bash script with a stub `gh` first on PATH that logs its argv and answers from
environment variables. The script lives outside the `web` image, so the tests skip there.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        shutil.which("bash") is None,
        reason="needs bash (absent inside the web container)",
    ),
]

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SCRIPT: Path = REPO_ROOT / "scripts" / "notifs-resolve-release-sha.sh"
REPO: str = "4IRL/urls4irl"
RUN_SHA: str = "a" * 40
INPUT_SHA: str = "b" * 40
TAG_COMMIT: str = "c" * 40
ANNOTATED_OBJECT: str = "d" * 40
DEREFERENCED_COMMIT: str = "e" * 40

STUB_GH: str = """#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
[ -n "${GH_TOKEN:-}" ] || { echo "stub gh: GH_TOKEN unset" >&2; exit 9; }
[ -n "${GH_REPO:-}" ] || { echo "stub gh: GH_REPO unset" >&2; exit 9; }
case "$*" in
  "release view --json tagName --jq .tagName")
    [ -z "${STUB_NO_RELEASE:-}" ] || exit 1
    echo "${STUB_TAG:-v1.2.3}"
    ;;
  "api repos/${GH_REPO}/git/ref/tags/"*" --jq .object.type")
    [ -z "${STUB_REF_MISSING:-}" ] || exit 1
    echo "${STUB_REF_TYPE}"
    ;;
  "api repos/${GH_REPO}/git/ref/tags/"*" --jq .object.sha")
    [ -z "${STUB_REF_MISSING:-}" ] || exit 1
    echo "${STUB_REF_SHA}"
    ;;
  "api repos/${GH_REPO}/git/tags/${STUB_REF_SHA} --jq .object.type")
    echo "${STUB_TAG_OBJECT_TYPE:-commit}"
    ;;
  "api repos/${GH_REPO}/git/tags/${STUB_REF_SHA} --jq .object.sha")
    echo "${STUB_TAG_OBJECT_SHA}"
    ;;
  *)
    echo "stub gh: unexpected argv: $*" >&2
    exit 8
    ;;
esac
"""


@pytest.fixture
def stub_env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(STUB_GH)
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "gh.log"
    log.write_text("")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("STUB_", "EVENT_", "RUN_HEAD", "INPUT_SHA", "GH_"))
    }
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    env["STUB_LOG"] = str(log)
    env["GH_TOKEN"] = "token-value"
    env["GH_REPO"] = REPO
    return env


def _run(env: dict[str, str], **extra: str) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), "scripts/notifs-resolve-release-sha.sh is missing"
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env={**env, **extra},
        capture_output=True,
        text=True,
        check=False,
    )


def _gh_calls(env: dict[str, str]) -> list[str]:
    return Path(env["STUB_LOG"]).read_text().splitlines()


def test_workflow_run_prints_head_sha_without_gh_calls(stub_env: dict[str, str]):
    """
    GIVEN a workflow_run event with a head sha
    WHEN the script runs
    THEN it prints that sha and makes no gh call.
    """
    result = _run(
        stub_env, EVENT_NAME="workflow_run", RUN_HEAD_SHA=RUN_SHA, INPUT_SHA=""
    )

    assert result.returncode == 0
    assert result.stdout == f"{RUN_SHA}\n"
    assert _gh_calls(stub_env) == []


def test_dispatch_with_input_sha_prints_it_without_gh_calls(stub_env: dict[str, str]):
    """
    GIVEN a workflow_dispatch with an explicit sha
    WHEN the script runs
    THEN it prints that sha and makes no gh call.
    """
    result = _run(
        stub_env, EVENT_NAME="workflow_dispatch", RUN_HEAD_SHA="", INPUT_SHA=INPUT_SHA
    )

    assert result.returncode == 0
    assert result.stdout == f"{INPUT_SHA}\n"
    assert _gh_calls(stub_env) == []


def test_dispatch_without_sha_resolves_lightweight_tag(stub_env: dict[str, str]):
    """
    GIVEN a dispatch with an empty sha and a lightweight release tag (ref object type commit)
    WHEN the script runs
    THEN it prints the tag's commit and never dereferences a tag object.
    """
    result = _run(
        stub_env,
        EVENT_NAME="workflow_dispatch",
        RUN_HEAD_SHA="",
        INPUT_SHA="",
        STUB_REF_TYPE="commit",
        STUB_REF_SHA=TAG_COMMIT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{TAG_COMMIT}\n"
    assert not any("git/tags/" in call for call in _gh_calls(stub_env))


def test_dispatch_without_sha_dereferences_annotated_tag(stub_env: dict[str, str]):
    """
    GIVEN a dispatch with an empty sha and an annotated release tag (ref object type tag)
    WHEN the script runs
    THEN it prints the commit the tag object points at.
    """
    result = _run(
        stub_env,
        EVENT_NAME="workflow_dispatch",
        RUN_HEAD_SHA="",
        INPUT_SHA="",
        STUB_REF_TYPE="tag",
        STUB_REF_SHA=ANNOTATED_OBJECT,
        STUB_TAG_OBJECT_TYPE="commit",
        STUB_TAG_OBJECT_SHA=DEREFERENCED_COMMIT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"{DEREFERENCED_COMMIT}\n"
    assert any(f"git/tags/{ANNOTATED_OBJECT}" in call for call in _gh_calls(stub_env))


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param({"STUB_NO_RELEASE": "1"}, id="no-published-release"),
        pytest.param(
            {"STUB_REF_MISSING": "1", "STUB_REF_TYPE": "commit"}, id="missing-ref"
        ),
        pytest.param(
            {"STUB_REF_TYPE": "blob", "STUB_REF_SHA": TAG_COMMIT},
            id="unknown-object-type",
        ),
        pytest.param(
            {
                "STUB_REF_TYPE": "tag",
                "STUB_REF_SHA": ANNOTATED_OBJECT,
                "STUB_TAG_OBJECT_TYPE": "tree",
                "STUB_TAG_OBJECT_SHA": DEREFERENCED_COMMIT,
            },
            id="annotated-tag-not-a-commit",
        ),
        pytest.param(
            {"STUB_REF_TYPE": "commit", "STUB_REF_SHA": "not-a-sha"},
            id="release-commit-not-40-hex",
        ),
    ],
)
def test_release_lookup_failures_fail_closed(
    stub_env: dict[str, str], extra: dict[str, str]
):
    """
    GIVEN a dispatch with an empty sha and a release lookup that cannot resolve
    WHEN the script runs
    THEN it exits non-zero with no stdout (never a fallback to main).
    """
    result = _run(
        stub_env,
        EVENT_NAME="workflow_dispatch",
        RUN_HEAD_SHA="",
        INPUT_SHA="",
        **extra,
    )

    assert result.returncode != 0
    assert result.stdout == ""


@pytest.mark.parametrize(
    ("event", "run_sha", "input_sha"),
    [
        pytest.param("push", RUN_SHA, INPUT_SHA, id="unknown-event"),
        pytest.param("", RUN_SHA, INPUT_SHA, id="empty-event"),
        pytest.param("workflow_run", "", INPUT_SHA, id="empty-run-head-sha"),
        pytest.param("workflow_run", "A" * 40, "", id="run-sha-uppercase"),
        pytest.param("workflow_run", "a" * 39, "", id="run-sha-short"),
        pytest.param("workflow_dispatch", "", "b" * 41, id="input-sha-long"),
        pytest.param("workflow_dispatch", "", "g" * 40, id="input-sha-not-hex"),
    ],
)
def test_bad_inputs_fail_closed(
    stub_env: dict[str, str], event: str, run_sha: str, input_sha: str
):
    """
    GIVEN an unknown event, an empty workflow_run sha, or a sha that is not 40 lowercase hex characters
    WHEN the script runs
    THEN it exits non-zero with no stdout and makes no gh call.
    """
    result = _run(stub_env, EVENT_NAME=event, RUN_HEAD_SHA=run_sha, INPUT_SHA=input_sha)

    assert result.returncode != 0
    assert result.stdout == ""
    assert _gh_calls(stub_env) == []
