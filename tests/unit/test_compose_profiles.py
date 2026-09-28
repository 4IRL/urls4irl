"""Unit tests pinning the local spoke Compose file (`docker/compose.local.yaml`).

`make up` starts only the unprofiled core; `p=ui` / `p=full` layer on the
optional services. These tests keep that map and its dependency invariant from
drifting as services are added or rewired, and pin the spoke's per-worktree
identity: an interpolated project name, host ports and hub-reachable aliases,
and exactly which services join the per-user shared network. The hub file is
pinned by `test_compose_hub.py`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

COMPOSE_DIR: Path = Path(__file__).resolve().parents[2] / "docker"
LOCAL_COMPOSE_FILE: Path = COMPOSE_DIR / "compose.local.yaml"
BUILT_COMPOSE_FILE: Path = COMPOSE_DIR / "compose.built.yaml"

EXPECTED_PROFILES: dict[str, set[str]] = {
    "vite": {"ui", "full"},
    "workflow": {"full"},
    "cloudflared": {"tunnel"},
}


def _load_compose(compose_file: Path) -> dict[str, Any]:
    return yaml.safe_load(compose_file.read_text())


def _load_services(compose_file: Path) -> dict[str, dict[str, Any]]:
    return _load_compose(compose_file)["services"]


def _network_names(service: dict[str, Any]) -> set[str]:
    """Networks from list-form or dict-form `networks:`; none when absent or null."""
    networks = service.get("networks") or []
    return set(networks.keys()) if isinstance(networks, dict) else set(networks)


def _shared_aliases(service: dict[str, Any]) -> list[str]:
    return service["networks"]["u4i_shared"]["aliases"]


def _profiles(service: dict[str, Any]) -> set[str]:
    return set(service.get("profiles", []))


def _depends_on_names(service: dict[str, Any]) -> list[str]:
    """Names from list-form or dict-form `depends_on` (iterating a dict yields its keys)."""
    return list(service.get("depends_on", []))


def _dependency_violations(services: dict[str, dict[str, Any]]) -> list[str]:
    """One message per `depends_on` edge onto a less-available service.

    An empty profile set means "always enabled". An edge is legal when the
    dependency is unprofiled, or when the dependent is profiled and every
    profile enabling the dependent also enables the dependency.
    """
    violations: list[str] = []
    for service_name, service in services.items():
        service_profiles = _profiles(service)
        for dependency_name in _depends_on_names(service):
            dependency_profiles = _profiles(services[dependency_name])
            if not dependency_profiles or (
                service_profiles and service_profiles <= dependency_profiles
            ):
                continue
            violations.append(
                f"{service_name} (profiles {sorted(service_profiles)}) depends on "
                f"{dependency_name} (profiles {sorted(dependency_profiles)}), "
                "which is not enabled everywhere the dependent is"
            )
    return violations


@pytest.mark.parametrize(
    ("service_name", "expected_profiles"),
    sorted(EXPECTED_PROFILES.items()),
    ids=sorted(EXPECTED_PROFILES),
)
def test_optional_services_have_expected_profiles(
    service_name: str, expected_profiles: set[str]
) -> None:
    services = _load_services(LOCAL_COMPOSE_FILE)
    assert _profiles(services[service_name]) == expected_profiles


def test_core_services_are_unprofiled() -> None:
    services = _load_services(LOCAL_COMPOSE_FILE)
    core_service_names = sorted(set(services) - set(EXPECTED_PROFILES))
    assert core_service_names, "expected at least one always-on core service"
    for service_name in core_service_names:
        assert "profiles" not in services[service_name], (
            f"{service_name} is a core service and must stay unprofiled; "
            "add it to EXPECTED_PROFILES if it is meant to be optional"
        )


def test_no_service_depends_on_a_less_available_service() -> None:
    """`workflow -> web` is fine, `web -> vite` is not (see `_dependency_violations`)."""
    services = _load_services(LOCAL_COMPOSE_FILE)
    assert _dependency_violations(services) == []


@pytest.mark.parametrize(
    ("synthetic_services", "expected_violation_count"),
    [
        pytest.param(
            {
                "web": {"depends_on": {"vite": {"condition": "service_started"}}},
                "vite": {"profiles": ["ui", "full"]},
            },
            1,
            id="unprofiled-depends-on-profiled",
        ),
        pytest.param(
            {
                "playwright": {"profiles": ["ui", "full"], "depends_on": ["workflow"]},
                "workflow": {"profiles": ["full"]},
            },
            1,
            id="list-form-wider-depends-on-narrower",
        ),
        pytest.param(
            {
                "tunnel_client": {"profiles": ["ui", "tunnel"], "depends_on": ["vite"]},
                "vite": {"profiles": ["ui", "full"]},
            },
            1,
            id="overlapping-non-subset-profiles",
        ),
        pytest.param(
            {
                "playwright": {
                    "profiles": ["ui", "full"],
                    "depends_on": {"vite": {"condition": "service_healthy"}},
                },
                "vite": {"profiles": ["ui", "full"]},
                "web": {"depends_on": ["redis"]},
                "redis": {},
            },
            0,
            id="legal-equal-profiles-and-unprofiled-dependency",
        ),
    ],
)
def test_dependency_violations_detects_illegal_edges(
    synthetic_services: dict[str, dict[str, Any]], expected_violation_count: int
) -> None:
    assert len(_dependency_violations(synthetic_services)) == expected_violation_count


def test_built_overlay_declares_no_profiles() -> None:
    """The overlay inherits profiles from the base file; a redeclaration would drift."""
    services = _load_services(BUILT_COMPOSE_FILE)
    for service_name, service in services.items():
        assert "profiles" not in service, (
            f"compose.built.yaml redeclares profiles on {service_name}"
        )


def test_built_overlay_only_overrides_base_services() -> None:
    """A service new to the overlay would lack the base file's build, env and networks."""
    base_services = _load_services(LOCAL_COMPOSE_FILE)
    assert set(_load_services(BUILT_COMPOSE_FILE)) <= set(base_services)


@pytest.mark.parametrize(
    "compose_file", [LOCAL_COMPOSE_FILE, BUILT_COMPOSE_FILE], ids=["local", "built"]
)
def test_local_services_declare_no_container_name(compose_file: Path) -> None:
    """A fixed container name would collide as soon as a second spoke starts."""
    for service_name, service in _load_services(compose_file).items():
        assert "container_name" not in service, (
            f"{compose_file.name} pins container_name on {service_name}"
        )


def test_local_project_name_is_interpolated() -> None:
    assert _load_compose(LOCAL_COMPOSE_FILE)["name"].startswith("${U4I_PROJECT:?")


def test_built_overlay_declares_no_project_name() -> None:
    assert "name" not in _load_compose(BUILT_COMPOSE_FILE)


def test_local_host_ports_are_interpolated() -> None:
    services = _load_services(LOCAL_COMPOSE_FILE)
    assert services["web"]["ports"] == ["${U4I_WEB_PORT:-8659}:5000"]
    assert services["vite"]["ports"] == ["${U4I_VITE_PORT:-5173}:5173"]
    assert (
        "VITE_URL=http://localhost:${U4I_VITE_PORT:-5173}"
        in services["web"]["environment"]
    )


def test_shared_network_members_are_exactly_web_vite_workflow_db_init() -> None:
    """redis, redis-metrics and cloudflared stay off it: their bare names would be ambiguous there."""
    services = _load_services(LOCAL_COMPOSE_FILE)
    shared_members = {
        service_name
        for service_name, service in services.items()
        if "u4i_shared" in _network_names(service)
    }
    assert shared_members == {"web", "vite", "workflow", "db-init"}


@pytest.mark.parametrize("service_name", ["web", "vite", "workflow"])
def test_shared_members_with_datastores_keep_the_default_network(
    service_name: str,
) -> None:
    """Joining u4i_shared must not drop the default network, where redis/redis-metrics live."""
    services = _load_services(LOCAL_COMPOSE_FILE)
    assert "default" in _network_names(services[service_name])


def test_web_session_cookie_name_is_project_scoped() -> None:
    web_environment = _load_services(LOCAL_COMPOSE_FILE)["web"]["environment"]
    cookie_env = next(
        entry
        for entry in web_environment
        if entry.startswith("U4I_SESSION_COOKIE_NAME=")
    )
    assert cookie_env.startswith("U4I_SESSION_COOKIE_NAME=${U4I_PROJECT")
    assert cookie_env.endswith("_session")


@pytest.mark.parametrize(
    ("service_name", "alias_variable"),
    [("web", "U4I_WEB_HOST"), ("vite", "U4I_VITE_HOST")],
)
def test_web_and_vite_have_slugged_aliases(
    service_name: str, alias_variable: str
) -> None:
    """The hub browser reaches each spoke by its slugged alias, never the ambiguous bare name."""
    service = _load_services(LOCAL_COMPOSE_FILE)[service_name]
    aliases = _shared_aliases(service)
    assert len(aliases) == 1
    assert aliases[0].startswith(f"${{{alias_variable}")
    environment = service["environment"]
    assert any(
        entry.startswith(f"{alias_variable}=${{{alias_variable}")
        for entry in environment
    ), environment


def test_vite_localhost_alias_stays_on_the_default_network() -> None:
    vite_networks = _load_services(LOCAL_COMPOSE_FILE)["vite"]["networks"]
    assert vite_networks["default"]["aliases"] == ["localhost"]
    assert "localhost" not in _shared_aliases(
        _load_services(LOCAL_COMPOSE_FILE)["vite"]
    )


def test_shared_network_is_external() -> None:
    shared_network = _load_compose(LOCAL_COMPOSE_FILE)["networks"]["u4i_shared"]
    assert shared_network["external"] is True
    assert shared_network["name"].startswith("${U4I_SHARED_NET")


def test_spoke_never_depends_on_a_service_outside_its_file() -> None:
    """db and playwright live in compose.hub.yaml: make-target ordering replaces those edges."""
    services = _load_services(LOCAL_COMPOSE_FILE)
    for service_name, service in services.items():
        for dependency_name in _depends_on_names(service):
            assert dependency_name in services, (
                f"{service_name} depends on {dependency_name}, which is not in this file"
            )


def test_vite_runs_as_the_host_user() -> None:
    """Built-mode `vite build` (and `make vite-build`) write dist into the checkout: root-owned files block
    `git worktree remove`. The image re-owns /app to the same ids, so they must be its build args too."""
    vite = _load_services(LOCAL_COMPOSE_FILE)["vite"]
    assert vite["user"] == "${HOST_UID:-1001}:${HOST_GID:-1001}"
    assert vite["build"]["args"] == {
        "HOST_UID": "${HOST_UID:-1001}",
        "HOST_GID": "${HOST_GID:-1001}",
    }
    assert "user" not in _load_services(BUILT_COMPOSE_FILE)["vite"]


def test_vite_mounts_static_not_a_missing_dist() -> None:
    """Docker creates a missing bind-mount source as root, which the non-root vite could not write into."""
    vite_volumes = _load_services(LOCAL_COMPOSE_FILE)["vite"]["volumes"]
    assert "./backend/static:/app/backend/static" in vite_volumes
    assert not [volume for volume in vite_volumes if "static/dist" in volume]


def test_web_reaches_hub_services_by_their_hub_names() -> None:
    web_environment = _load_services(LOCAL_COMPOSE_FILE)["web"]["environment"]
    assert "PLAYWRIGHT_WS_URL=ws://playwright:3000/" in web_environment


def test_spoke_db_init_provisions_only_its_own_dev_db() -> None:
    db_init_environment = _load_services(LOCAL_COMPOSE_FILE)["db-init"]["environment"]
    assert "U4I_PROVISION_SCOPE=spoke" in db_init_environment
    assert "PGHOST=db" in db_init_environment
    cluster_only_keys = ("LEGACY_DEV_DB=", "U4I_TEST_ROLE=", "U4I_PG_TEST_CONN_LIMIT=")
    assert not [
        entry for entry in db_init_environment if entry.startswith(cluster_only_keys)
    ]
