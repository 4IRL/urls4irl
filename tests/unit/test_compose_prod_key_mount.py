"""Pin the production notifs key-directory mount in `docker/compose.yaml`.

`web` and `workflow` mount `/home/u4i/notifs-key` read-only at `/run/notifs`
(a directory mount, never a file mount) and carry the two hub env entries; no
other prod service mounts it, and the dev compose file never mounts it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
PROD_COMPOSE_FILE: Path = REPO_ROOT / "docker" / "compose.yaml"
DEV_COMPOSE_FILE: Path = REPO_ROOT / "docker" / "compose.dev.yaml"
KEY_MOUNT: str = "/home/u4i/notifs-key:/run/notifs:ro"
MOUNTED_SERVICES: tuple[str, ...] = ("web", "workflow")


def _services(compose_file: Path) -> dict[str, dict[str, Any]]:
    return yaml.safe_load(compose_file.read_text())["services"]


def _mounts(service: dict[str, Any]) -> list[str]:
    return [str(volume) for volume in service.get("volumes", [])]


@pytest.mark.parametrize("service_name", MOUNTED_SERVICES)
def test_service_has_exactly_one_readonly_key_mount(service_name: str):
    """
    GIVEN the prod compose file
    WHEN the web and workflow volumes are read
    THEN each has exactly the read-only key directory bind.
    """
    mounts = _mounts(_services(PROD_COMPOSE_FILE)[service_name])
    assert mounts.count(KEY_MOUNT) == 1
    assert [mount for mount in mounts if "notifs" in mount] == [KEY_MOUNT]


@pytest.mark.parametrize("service_name", MOUNTED_SERVICES)
def test_service_has_hub_env_entries(service_name: str):
    """
    GIVEN the prod compose file
    WHEN the web and workflow environment lists are read
    THEN each carries NOTIFS_BASE_URL and NOTIFS_KEY_DIR.
    """
    environment = _services(PROD_COMPOSE_FILE)[service_name]["environment"]
    assert environment.count("NOTIFS_BASE_URL=https://notifs-delivery.4irl.app") == 1
    assert environment.count("NOTIFS_KEY_DIR=/run/notifs") == 1


def test_no_other_prod_service_mounts_the_key_dir():
    """
    GIVEN the prod compose file
    WHEN every other service is inspected
    THEN none mounts the key directory.
    """
    for name, service in _services(PROD_COMPOSE_FILE).items():
        if name in MOUNTED_SERVICES:
            continue
        assert not any("notifs" in mount for mount in _mounts(service)), name


def test_dev_compose_mounts_no_key_dir():
    """
    GIVEN the dev compose file
    WHEN every service's volumes are read
    THEN none contains notifs-key or /run/notifs.
    """
    for name, service in _services(DEV_COMPOSE_FILE).items():
        for mount in _mounts(service):
            assert "notifs-key" not in mount, name
            assert "/run/notifs" not in mount, name
