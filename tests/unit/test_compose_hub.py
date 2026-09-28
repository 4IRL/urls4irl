"""Unit tests pinning the per-user hub Compose file (`docker/compose.hub.yaml`).

The hub holds what every spoke shares: the one Postgres cluster (`db`), its
cluster-wide provisioning one-shot (`cluster-init`), and the Playwright
browser server. It is reachable only over the external per-user network, so no
service publishes a host port or pins a container name.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
HUB_COMPOSE_FILE: Path = REPO_ROOT / "docker" / "compose.hub.yaml"
PLAYWRIGHT_DOCKERFILE: Path = REPO_ROOT / "docker" / "Dockerfile.Playwright"
REQUIREMENTS: Path = REPO_ROOT / "requirements" / "requirements-test.txt"


def _load_compose() -> dict[str, Any]:
    return yaml.safe_load(HUB_COMPOSE_FILE.read_text())


def _load_services() -> dict[str, dict[str, Any]]:
    return _load_compose()["services"]


def _env_dict(service: dict[str, Any]) -> dict[str, str]:
    """A list-form `environment:` block as a dict, split on each entry's first `=`."""
    return dict(entry.split("=", 1) for entry in service.get("environment", []))


def _dockerfile_playwright_version() -> str:
    version_match = re.search(
        r"^ARG PLAYWRIGHT_VERSION=(\S+)$",
        PLAYWRIGHT_DOCKERFILE.read_text(),
        re.MULTILINE,
    )
    assert version_match is not None, "Dockerfile.Playwright lost its ARG default"
    return version_match.group(1)


def _dockerfile_healthcheck() -> re.Match[str]:
    """The HEALTHCHECK directive, its `\\`-continued lines joined into one logical line.

    Group 1 holds the option flags; group 2 the `node -e` script, between the first
    and last double quote of the CMD argument.
    """
    logical_text = PLAYWRIGHT_DOCKERFILE.read_text().replace("\\\n", " ")
    healthcheck_match = re.search(
        r'^HEALTHCHECK (.*?)\s+CMD node -e "(.*)"$', logical_text, re.MULTILINE
    )
    assert healthcheck_match is not None, "Dockerfile.Playwright lost its HEALTHCHECK"
    return healthcheck_match


def test_hub_services_are_db_cluster_init_and_playwright() -> None:
    assert set(_load_services()) == {"db", "cluster-init", "playwright"}


def test_hub_services_pin_no_container_name_and_publish_no_ports() -> None:
    for service_name, service in _load_services().items():
        assert "container_name" not in service, service_name
        assert "ports" not in service, service_name


def test_playwright_has_no_depends_on() -> None:
    """The spokes' web/vite are other projects: a cross-project edge is impossible."""
    assert "depends_on" not in _load_services()["playwright"]


def test_playwright_is_always_enabled() -> None:
    assert "profiles" not in _load_services()["playwright"]


def test_playwright_builds_the_derived_image() -> None:
    playwright = _load_services()["playwright"]
    assert playwright["build"] == {
        "context": "docker",
        "dockerfile": "Dockerfile.Playwright",
    }
    assert playwright["image"] == f"u4i-playwright:{_dockerfile_playwright_version()}"


# Belt-and-braces for an invocation context without the requirements/ mount; the web
# container normally has it (docker/compose.local.yaml mounts ./requirements read-only).
@pytest.mark.skipif(not REQUIREMENTS.exists(), reason="requirements/ not present")
def test_playwright_versions_agree() -> None:
    """The browser server and the pip client must speak the same Playwright protocol."""
    pin_match = re.search(
        r"^playwright==(\S+)$", REQUIREMENTS.read_text(), re.MULTILINE
    )
    assert pin_match is not None, "requirements-test.txt lost its playwright pin"
    assert _dockerfile_playwright_version() == pin_match.group(1)


def test_playwright_dockerfile_healthcheck_matches_compose() -> None:
    """Dockerfile HEALTHCHECK (standalone runs) and compose healthcheck (up --wait) never drift."""
    healthcheck = _load_services()["playwright"]["healthcheck"]
    dockerfile_healthcheck = _dockerfile_healthcheck()
    assert dockerfile_healthcheck.group(2) == healthcheck["test"][-1]
    dockerfile_options = dict(
        option.removeprefix("--").split("=", 1)
        for option in dockerfile_healthcheck.group(1).split()
    )
    assert dockerfile_options == {
        option_name.replace("_", "-"): str(option_value)
        for option_name, option_value in healthcheck.items()
        if option_name != "test"
    }


def test_playwright_has_no_command_override() -> None:
    """The derived image's entrypoint owns the start (the idle-reaping supervisor)."""
    assert "command" not in _load_services()["playwright"]


def test_playwright_healthcheck_is_a_node_tcp_probe() -> None:
    """A ws server never answers a plain HTTP GET: the probe only checks connect()."""
    healthcheck = _load_services()["playwright"]["healthcheck"]
    assert healthcheck["test"][:3] == ["CMD", "node", "-e"]
    probe_script = healthcheck["test"][-1]
    assert "connect(3000" in probe_script
    assert "127.0.0.1" in probe_script
    assert "http" not in probe_script
    assert "start_interval" in healthcheck
    assert "start_period" in healthcheck


def test_playwright_is_never_auto_restarted() -> None:
    """An idle-reaped (exited 0) server must stay down until `make playwright-up`."""
    assert _load_services()["playwright"].get("restart", "no") == "no"


def test_playwright_idle_minutes_is_interpolated() -> None:
    assert (
        "U4I_PLAYWRIGHT_IDLE_MINUTES=${U4I_PLAYWRIGHT_IDLE_MINUTES:-15}"
        in _load_services()["playwright"]["environment"]
    )


def test_playwright_keeps_init() -> None:
    """tini reaps the browser processes the supervisor's server leaves behind."""
    assert _load_services()["playwright"]["init"] is True


def test_db_bootstraps_no_app_database() -> None:
    """No bootstrap app DB: each spoke's db-init creates its own U4I_DEV_DB."""
    assert _env_dict(_load_services()["db"])["POSTGRES_DB"] == "postgres"


def test_capacity_interlocks_are_interpolated_into_the_hub() -> None:
    services = _load_services()
    db_command = services["db"]["command"]
    assert "max_connections=${U4I_PG_MAX_CONN" in db_command
    assert "shared_buffers=${U4I_PG_SHARED_BUFFERS_MB" in db_command
    cluster_init_env = _env_dict(services["cluster-init"])
    assert cluster_init_env["U4I_PG_TEST_CONN_LIMIT"].startswith(
        "${U4I_PG_TEST_CONN_LIMIT"
    )
    assert cluster_init_env["U4I_TEST_ROLE"].startswith("${U4I_TEST_ROLE")


def test_cluster_init_is_the_profiled_cluster_scope_one_shot() -> None:
    cluster_init = _load_services()["cluster-init"]
    cluster_init_env = _env_dict(cluster_init)
    assert cluster_init_env["U4I_PROVISION_SCOPE"] == "cluster"
    assert cluster_init_env["PGHOST"] == "db"
    assert "U4I_DEV_DB" not in cluster_init_env
    assert cluster_init["profiles"] == ["init"]
    assert cluster_init["depends_on"] == {"db": {"condition": "service_healthy"}}


def test_hub_project_name_is_interpolated() -> None:
    assert _load_compose()["name"].startswith("${U4I_HUB_PROJECT:?")


def test_shared_network_is_external() -> None:
    shared_network = _load_compose()["networks"]["u4i_shared"]
    assert shared_network["external"] is True
    assert shared_network["name"].startswith("${U4I_SHARED_NET")


def test_every_hub_service_joins_only_the_shared_network() -> None:
    for service_name, service in _load_services().items():
        assert service["networks"] == ["u4i_shared"], service_name
