"""Unit tests pinning the local Compose profile map (`docker/compose.local.yaml`).

`make up` starts only the unprofiled core; `p=ui` / `p=full` layer on the
optional services. These tests keep that map and its dependency invariant from
drifting as services are added or rewired.
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
    "playwright": {"ui", "full"},
    "workflow": {"full"},
    "cloudflared": {"tunnel"},
}


def _load_services(compose_file: Path) -> dict[str, dict[str, Any]]:
    return yaml.safe_load(compose_file.read_text())["services"]


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
    """`playwright -> vite` is fine, `web -> vite` is not (see `_dependency_violations`)."""
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
