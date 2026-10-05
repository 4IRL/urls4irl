"""Host-static test pinning that `.env.example` carries every required key.

`.env.example` is the file a new contributor copies to `.env`. The compose
stack, `Config.__init__`, `ConfigTest.__init__` and `docker/db-provision.sh`
fail without these keys, so each must be an active (uncommented) line with a
non-empty value. `MOCK_EMAIL_SEND` is only a commented hint and must not be
active.

The file is not copied into the `web` image, so this skips inside the
container and runs host-side (and in CI's unit job).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
MAKEFILE: Path = REPO_ROOT / "Makefile"
ENV_EXAMPLE: Path = REPO_ROOT / ".env.example"
MAKE_BINARY: str | None = shutil.which("make")

REQUIRED_KEYS: tuple[str, ...] = (
    "SECRET_KEY",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_TEST_DB",
    "MAILJET_API_KEY",
    "MAILJET_SECRET_KEY",
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        MAKE_BINARY is None or not MAKEFILE.is_file(),
        reason="needs `make` and the repo Makefile (absent inside the web container)",
    ),
]


def _active_entries() -> dict[str, str]:
    """Return the uncommented, non-blank `KEY=value` lines of `.env.example`."""
    entries: dict[str, str] = {}
    for line in ENV_EXAMPLE.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        entries[key.strip()] = value.strip()
    return entries


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_required_key_is_active_and_non_empty(key: str) -> None:
    entries = _active_entries()
    assert key in entries, f"{key} is missing (or commented out) in .env.example"
    assert entries[key], f"{key} has an empty value in .env.example"


def test_mock_email_send_is_not_an_active_line() -> None:
    assert "MOCK_EMAIL_SEND" not in _active_entries()
