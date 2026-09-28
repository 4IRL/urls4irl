"""Unit tests pinning the per-user hub Compose file (`docker/compose.hub.yaml`).

The hub holds what every spoke shares: the one Postgres cluster (`db`), its
cluster-wide provisioning one-shot (`cluster-init`), and the Playwright
browser server. It is reachable only over the external per-user network, so no
service publishes a host port or pins a container name.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

HUB_COMPOSE_FILE: Path = (
    Path(__file__).resolve().parents[2] / "docker" / "compose.hub.yaml"
)


def _load_compose() -> dict[str, Any]:
    return yaml.safe_load(HUB_COMPOSE_FILE.read_text())


def _load_services() -> dict[str, dict[str, Any]]:
    return _load_compose()["services"]


def _env_dict(service: dict[str, Any]) -> dict[str, str]:
    """A list-form `environment:` block as a dict, split on each entry's first `=`."""
    return dict(entry.split("=", 1) for entry in service.get("environment", []))


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
