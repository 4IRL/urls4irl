"""Env-driven cross-network hostnames and session cookie name.

Each value under test is read from the environment at import time (a class
attribute or module-level constant), so every case imports the module in a
fresh interpreter with an explicitly built environment rather than
monkeypatching the already-imported one.
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]

DOCKER_BASE_URL_PROBE = (
    "from backend.utils.strings.ui_testing_strs import UI_TEST_STRINGS; "
    "print(UI_TEST_STRINGS.DOCKER_BASE_URL)"
)
VITE_URL_PROBE = (
    "from backend.config import ConfigTestUI; print(ConfigTestUI().VITE_URL)"
)
SESSION_COOKIE_NAME_PROBE = (
    "from backend.config import Config, ConfigTest; "
    "print(Config.SESSION_COOKIE_NAME); print(ConfigTest.SESSION_COOKIE_NAME)"
)

# Every key a case depends on is popped first, so a value inherited from the
# container (e.g. compose-set U4I_WEB_HOST) never leaks into a case.
CONTROLLED_KEYS = (
    "U4I_WEB_HOST",
    "U4I_SESSION_COOKIE_NAME",
    "VITE_URL",
    "VITE_INTERNAL_HOST",
    "DOCKER",
)

# ConfigTestUI() validates these in __init__.
UI_CONFIG_REQUIRED_ENV = {
    "SECRET_KEY": "test-secret",
    "MAILJET_API_KEY": "test-mailjet-key",
    "MAILJET_SECRET_KEY": "test-mailjet-secret",
    "POSTGRES_USER": "test-user",
    "POSTGRES_PASSWORD": "test-password",
    "POSTGRES_DB": "test-db",
    "POSTGRES_TEST_DB": "test-db-test",
}


def _run_probe(probe: str, env_overrides: dict[str, str]) -> list[str]:
    child_env = os.environ.copy()
    for controlled_key in CONTROLLED_KEYS:
        child_env.pop(controlled_key, None)
    child_env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, "-c", probe],
        env=child_env,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"probe failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    return result.stdout.strip().splitlines()


def test_docker_base_url_defaults_to_web() -> None:
    assert _run_probe(DOCKER_BASE_URL_PROBE, {}) == ["http://web:"]


def test_docker_base_url_follows_u4i_web_host() -> None:
    output_lines = _run_probe(DOCKER_BASE_URL_PROBE, {"U4I_WEB_HOST": "web-wt-a"})
    assert output_lines == ["http://web-wt-a:"]


def test_empty_u4i_web_host_falls_back_to_web() -> None:
    assert _run_probe(DOCKER_BASE_URL_PROBE, {"U4I_WEB_HOST": ""}) == ["http://web:"]


def test_ui_vite_url_uses_container_port_not_host_port() -> None:
    """The host port in VITE_URL is never valid in-network; the hub browser
    reaches the spoke's vite on the container port 5173."""
    ui_config_env = {
        **UI_CONFIG_REQUIRED_ENV,
        "VITE_URL": "http://localhost:5221",
        "DOCKER": "true",
        "VITE_INTERNAL_HOST": "vite-wt-a",
    }
    assert _run_probe(VITE_URL_PROBE, ui_config_env) == ["http://vite-wt-a:5173"]


def test_hub_reached_urls_never_use_bare_service_names_when_slugged() -> None:
    """Pins the slugged path the hub browser relies on.

    Compose registers every service's bare name (`web`, `vite`) as an alias on
    every network it joins, so on the shared network those names resolve to
    one container per running spoke. With the compose-set slugged env, both
    URLs the hub browser loads must use `web-<slug>`/`vite-<slug>` instead.
    """
    spoke_env = {
        **UI_CONFIG_REQUIRED_ENV,
        "U4I_WEB_HOST": "web-wt-a",
        "VITE_URL": "http://localhost:5221",
        "DOCKER": "true",
        "VITE_INTERNAL_HOST": "vite-wt-a",
    }
    web_url = _run_probe(DOCKER_BASE_URL_PROBE, spoke_env)[0]
    vite_url = _run_probe(VITE_URL_PROBE, spoke_env)[0]
    assert urlparse(web_url).hostname == "web-wt-a"
    assert urlparse(vite_url).hostname == "vite-wt-a"


def test_session_cookie_name_defaults_to_session() -> None:
    """Unset keeps Flask's default, so prod, staging, and CI are unchanged."""
    assert _run_probe(SESSION_COOKIE_NAME_PROBE, {}) == ["session", "session"]


def test_session_cookie_name_follows_env() -> None:
    output_lines = _run_probe(
        SESSION_COOKIE_NAME_PROBE, {"U4I_SESSION_COOKIE_NAME": "u4i-wt-a_session"}
    )
    assert output_lines == ["u4i-wt-a_session", "u4i-wt-a_session"]


def test_empty_session_cookie_name_falls_back_to_session() -> None:
    """A present-but-empty value must not yield a nameless session cookie."""
    output_lines = _run_probe(
        SESSION_COOKIE_NAME_PROBE, {"U4I_SESSION_COOKIE_NAME": ""}
    )
    assert output_lines == ["session", "session"]
