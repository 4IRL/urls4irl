"""Pin the two dev deploy callees (`dev-deploy.yml`, `dev-deploy-2.yml`) to stay identical (host-static; YAML only).

The workflows are never run, except the remote health-probe loop, which is extracted and run under bash with a
stub `curl` and `sleep`. Contracts pinned: the whole `jobs.DevDeploy` mapping, top-level permissions and
`workflow_call` secrets are equal across the files; fresh-host `mkdir -p`; `ConnectTimeout`; the fail-closed
`Verify Web Health` step.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
WORKFLOWS: Path = REPO_ROOT / ".github" / "workflows"

# `.github/` is not mounted into the `web` image, so the module skips there and runs host-side.
# The skip looks at the workflows directory, never at the files under test: a missing file must fail.
pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        not WORKFLOWS.is_dir(),
        reason="needs the repo's .github/workflows (absent inside the web container)",
    ),
]

FILE_NAMES: list[str] = ["dev-deploy.yml", "dev-deploy-2.yml"]
JOB_KEY: str = "DevDeploy"
ATTEMPTS: int = 12
HEALTH_URL: str = "http://127.0.0.1:8659/health?db=true"


def _load(name: str) -> dict[Any, Any]:
    # A missing file raises FileNotFoundError, so it fails rather than skips.
    return yaml.safe_load((WORKFLOWS / name).read_text())


def _steps(name: str) -> list[dict[str, Any]]:
    return _load(name)["jobs"][JOB_KEY]["steps"]


def _step(name: str, step_name: str) -> dict[str, Any]:
    matches = [step for step in _steps(name) if step.get("name") == step_name]
    assert len(matches) == 1, f"{name}: expected one step named {step_name!r}"
    return matches[0]


def _step_index(name: str, step_name: str) -> int:
    return [step.get("name") for step in _steps(name)].index(step_name)


def _probe_loop(run: str) -> str:
    """The remote script between the `<<'REMOTE'` line and the closing `REMOTE`, dedented."""
    lines = run.splitlines()
    start = next(idx for idx, line in enumerate(lines) if "<<'REMOTE'" in line)
    end = next(idx for idx, line in enumerate(lines) if line.strip() == "REMOTE")
    return "\n".join(line.strip() for line in lines[start + 1 : end]) + "\n"


def test_callees_do_not_drift() -> None:
    first, second = (_load(name) for name in FILE_NAMES)
    assert first["jobs"][JOB_KEY] == second["jobs"][JOB_KEY]
    assert first["permissions"] == second["permissions"]
    assert set(first[True]["workflow_call"]["secrets"]) == set(
        second[True]["workflow_call"]["secrets"]
    )


@pytest.mark.parametrize("name", FILE_NAMES)
def test_build_step_creates_dirs_idempotently(name: str) -> None:
    run = _step(name, "Build Docker Network")["run"]
    assert "mkdir -p ./secrets/" in run
    assert "mkdir -p ~/static" in run
    assert not re.search(r"mkdir \./secrets/", run.replace("mkdir -p ./secrets/", ""))
    assert run.index("mkdir -p ~/static") < run.index("tar -xf - -C ~/static")


@pytest.mark.parametrize("name", FILE_NAMES)
def test_ssh_config_has_connect_timeout(name: str) -> None:
    lines = [
        line.strip()
        for line in _step(name, "Prepare SSH Config file")["run"].splitlines()
    ]
    start = lines.index("IdentitiesOnly yes")
    end = lines.index("ServerAliveInterval 15")
    assert start < lines.index("ConnectTimeout 30") < end


@pytest.mark.parametrize("name", FILE_NAMES)
def test_health_step_is_fail_closed(name: str) -> None:
    assert _step_index(name, "Verify Web Health") > _step_index(
        name, "Verify Docker Network"
    )
    run = _step(name, "Verify Web Health")["run"]
    assert "<<'REMOTE'" in run
    assert "'bash -s'" in run
    for needle in ("curl", "--max-time", HEALTH_URL):
        assert needle in run
    assert f"seq 1 {ATTEMPTS}" in run
    assert "REMOTE" in run.splitlines()  # unstripped: terminator at column 0
    assert '"200"' in run or "= 200" in run or "200 ]" in run
    assert f"health check failed after {ATTEMPTS} attempts" in run
    assert "exit 1" in run
    assert "set -e" not in run


_sleep_calls: dict[Path, int] = {}  # tmp_path -> number of stub `sleep` invocations


def _run_probe(
    tmp_path: Path, name: str, codes: list[str]
) -> tuple[subprocess.CompletedProcess[str], int]:
    """Run the extracted remote loop with stub curl/sleep; `codes` is cycled per curl call (last repeats)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    counter = tmp_path / "count"
    counter.write_text("0")
    codes_file = tmp_path / "codes"
    codes_file.write_text("\n".join(codes) + "\n")
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/bin/bash\n"
        f'n=$(( $(cat {counter}) + 1 ))\necho "$n" > {counter}\n'
        f"total=$(wc -l < {codes_file})\n"
        "idx=$(( n > total ? total : n ))\n"
        f'entry=$(sed -n "${{idx}}p" {codes_file})\n'
        'printf "%s" "${entry%%:*}"\n'
        'exit "${entry##*:}"\n'
    )
    sleep = bin_dir / "sleep"
    sleeps = tmp_path / "sleeps"
    sleeps.write_text("")
    sleep.write_text(f'#!/bin/bash\necho "$@" >> {sleeps}\nexit 0\n')
    for stub in (curl, sleep):
        stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    script = _probe_loop(_step(name, "Verify Web Health")["run"])
    result = subprocess.run(
        ["bash", "-c", script],
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    _sleep_calls[tmp_path] = len(sleeps.read_text().splitlines())
    return result, int(counter.read_text())


@pytest.mark.parametrize("name", FILE_NAMES)
def test_probe_200_first_attempt(tmp_path: Path, name: str) -> None:
    result, calls = _run_probe(tmp_path, name, ["200:0"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert calls == 1


@pytest.mark.parametrize("name", FILE_NAMES)
def test_probe_503_then_200(tmp_path: Path, name: str) -> None:
    result, calls = _run_probe(tmp_path, name, ["503:0", "200:0"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert calls == 2


@pytest.mark.parametrize("name", FILE_NAMES)
def test_probe_always_503_fails_after_all_attempts(tmp_path: Path, name: str) -> None:
    result, calls = _run_probe(tmp_path, name, ["503:0"])
    assert result.returncode == 1, result.stdout + result.stderr
    assert calls == ATTEMPTS
    assert (
        _sleep_calls[tmp_path] == ATTEMPTS
    )  # sleeps after every failed attempt, the last included
    assert f"health check failed after {ATTEMPTS} attempts" in result.stdout


@pytest.mark.parametrize("name", FILE_NAMES)
def test_probe_curl_failure_is_not_200(tmp_path: Path, name: str) -> None:
    result, calls = _run_probe(tmp_path, name, ["000:7", "000:28", "200:0"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert calls == 3
