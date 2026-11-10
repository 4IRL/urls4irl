"""Pin the notifs key-directory step in `.github/workflows/prod-deploy.yml`.

Static checks only (YAML plus string order); the remote command is never run. The step must
come before "Build Docker Network" so a failure aborts before `docker login`, `./secrets/`
and any plaintext secret, and it must be failure-visible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
PROD_DEPLOY: Path = REPO_ROOT / ".github" / "workflows" / "prod-deploy.yml"
KEY_DIR: str = "/home/u4i/notifs-key"
MANUAL_COMMAND: str = f"sudo chgrp 1001 {KEY_DIR}"
SCRIPT_NAME: str = "notifs-key-write.sh"
BUILD_STEP_NAME: str = "Build Docker Network"


def _steps() -> list[dict[str, Any]]:
    workflow = yaml.safe_load(PROD_DEPLOY.read_text())
    return workflow["jobs"]["ProdDeploy"]["steps"]


def _key_dir_step() -> dict[str, Any]:
    matches = [
        step for step in _steps() if f"mkdir -p {KEY_DIR}" in step.get("run", "")
    ]
    assert len(matches) == 1
    return matches[0]


def _index(name: str) -> int:
    return next(
        index for index, step in enumerate(_steps()) if step.get("name") == name
    )


def test_key_dir_step_precedes_build_docker_network():
    """
    GIVEN the production deploy steps
    WHEN the key-directory step and the build step are located
    THEN the key step is earlier, and login, ./secrets/ and compose up all live in the later step.
    """
    steps = _steps()
    key_index = steps.index(_key_dir_step())
    build_index = _index(BUILD_STEP_NAME)
    build_run = steps[build_index]["run"]

    assert key_index < build_index
    assert "docker login" in build_run
    assert "mkdir -p ./secrets/" in build_run
    assert "up --build -d" in build_run
    for step in steps[:build_index]:
        assert "docker login" not in step.get("run", "")
        assert "./secrets/" not in step.get("run", "")


def test_script_is_copied_alongside_compose_before_the_key_step():
    """
    GIVEN the scp step
    WHEN its command is read
    THEN it copies the key-write script next to compose.yaml, before the key step.
    """
    steps = _steps()
    scp_index = next(
        index for index, step in enumerate(steps) if "scp " in step.get("run", "")
    )

    assert f"scripts/{SCRIPT_NAME}" in steps[scp_index]["run"]
    assert "docker/compose.yaml" in steps[scp_index]["run"]
    assert scp_index < steps.index(_key_dir_step())


def test_key_step_commands_run_in_order():
    """
    GIVEN the key-directory step
    WHEN its command text is read
    THEN mkdir, chmod, chgrp and --check appear in that order.
    """
    run = _key_dir_step()["run"]
    positions = [
        run.index(f"mkdir -p {KEY_DIR}"),
        run.index(f"chmod 2750 {KEY_DIR}"),
        run.index("--entrypoint chgrp"),
        run.index(f"--check {KEY_DIR}"),
    ]

    assert positions == sorted(positions)


def test_chgrp_is_guarded_and_manual_fallback_is_named():
    """
    GIVEN the key-directory step
    WHEN the chgrp is located
    THEN it sits inside the group-not-1001 check and the image-present check, with the manual command in the else.
    """
    run = _key_dir_step()["run"]
    group_check = run.index('!= "1001"')
    image_check = run.index("docker image inspect ghcr.io/4irl/u4i-workflow:latest")
    chgrp = run.index("--entrypoint chgrp")
    manual = run.index(MANUAL_COMMAND)

    assert group_check < image_check < chgrp < manual
    assert "docker pull" not in run
    assert "--user 0" in run


def test_failure_propagates():
    """
    GIVEN the key-directory step
    WHEN its remote script is read
    THEN it starts with set -e and exits non-zero explicitly after --check, with no bare ;-chain.
    """
    run = _key_dir_step()["run"]
    remote = run.split("'", 1)[1]
    commands = [line.strip() for line in remote.splitlines() if line.strip()]

    assert commands[0] == "set -e"
    check_line = next(line for line in commands if "--check" in line)
    assert check_line.endswith("|| exit 1")
    assert ";" not in remote.replace("; then", "").replace(";;", "")


def test_prod_deploy_does_not_grant_id_token():
    """
    GIVEN prod-deploy.yml
    WHEN its permissions are read
    THEN id-token is not requested.
    """
    workflow = yaml.safe_load(PROD_DEPLOY.read_text())

    assert "id-token" not in workflow.get("permissions", {})
