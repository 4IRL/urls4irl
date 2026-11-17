"""Pin the `HEALTH_CHECK_TOKEN` prod secret wiring.

Static checks only. The token must reach the prod `web` container (compose `web.secrets` and
the top-level `secrets:` map), be optional in `prod-deploy.yml` (so a deploy never breaks before
the repo secret exists), and never reach the workflow container (`ALLOW_VARS`).
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
import yaml

import backend.config as backend_config
from scripts.build_container_env import ALLOW_VARS

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
COMPOSE_PROD: Path = REPO_ROOT / "docker" / "compose.yaml"
PROD_DEPLOY: Path = REPO_ROOT / ".github" / "workflows" / "prod-deploy.yml"
SECRET_NAME: str = "HEALTH_CHECK_TOKEN"

# `.github/` is not mounted into the `web` image, so only the workflow assertions skip there.
# The skip looks at the workflows directory, never at the file under test: a missing file must fail.
needs_workflows = pytest.mark.skipif(
    not PROD_DEPLOY.parent.is_dir(),
    reason="needs the repo's .github/workflows (absent inside the web container)",
)

pytestmark = pytest.mark.unit


def _compose() -> dict[str, Any]:
    return yaml.safe_load(COMPOSE_PROD.read_text())


def test_health_token_in_web_secrets_list() -> None:
    """
    GIVEN the prod compose file
    WHEN the web service's secrets list is read
    THEN it includes HEALTH_CHECK_TOKEN.
    """
    assert SECRET_NAME in _compose()["services"]["web"]["secrets"]


def test_health_token_in_top_level_secrets_map() -> None:
    """
    GIVEN the prod compose file
    WHEN the top-level secrets map is read
    THEN HEALTH_CHECK_TOKEN is backed by ./secrets/HEALTH_CHECK_TOKEN.
    """
    secrets = _compose()["secrets"]
    assert secrets[SECRET_NAME] == {"file": f"./secrets/{SECRET_NAME}"}


@needs_workflows
def test_health_token_optional_in_prod_deploy() -> None:
    """
    GIVEN the prod deploy reusable workflow
    WHEN its workflow_call secrets are read
    THEN HEALTH_CHECK_TOKEN is declared with required: false.
    """
    workflow = yaml.safe_load(PROD_DEPLOY.read_text())
    # PyYAML parses the bare key `on` as True.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers["workflow_call"]["secrets"][SECRET_NAME]["required"] is False


@needs_workflows
def test_health_token_written_and_forwarded() -> None:
    """
    GIVEN the prod deploy workflow and its caller
    WHEN their text is read
    THEN the secret file is written and the caller maps PROD_HEALTH_CHECK_TOKEN.
    """
    deploy = PROD_DEPLOY.read_text()
    assert (
        f'echo "${{{{ secrets.{SECRET_NAME} }}}}" > ./secrets/{SECRET_NAME};' in deploy
    )
    caller = (PROD_DEPLOY.parent / "prod-build-and-deploy.yml").read_text()
    assert f"{SECRET_NAME}: ${{{{ secrets.PROD_{SECRET_NAME} }}}}" in caller


def test_health_token_not_in_workflow_allow_vars() -> None:
    """
    GIVEN the workflow container's env allowlist
    WHEN it is checked for HEALTH_CHECK_TOKEN
    THEN the web-only secret is absent.
    """
    assert SECRET_NAME not in ALLOW_VARS


def test_config_reads_health_check_token_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    GIVEN HEALTH_CHECK_TOKEN is set, then unset, in the environment
    WHEN backend.config is (re)loaded
    THEN Config.HEALTH_CHECK_TOKEN is the env value, then None.
    """
    try:
        monkeypatch.setenv(SECRET_NAME, "env-token")
        assert importlib.reload(backend_config).Config.HEALTH_CHECK_TOKEN == "env-token"

        monkeypatch.delenv(SECRET_NAME)
        assert importlib.reload(backend_config).Config.HEALTH_CHECK_TOKEN is None
    finally:
        monkeypatch.undo()
        importlib.reload(backend_config)
