"""Stdlib client for the 4irl-notifs hub's dead-man's-switch heartbeats.

The scheduled jobs in the workflow container (daily backup, metrics flush, gauge
sampler, purges) call ``safe_ping`` to check in with the hub; a job that fails
calls it with ``fail=True``. The workflow venv has only ``redis`` and
``psycopg2``, so this module uses the standard library alone.

Contracts:
- Never raises. ``ping`` returns ``True`` only on HTTP 200; ``safe_ping`` also
  swallows any exception from the ping path, so a job's exit code can never
  depend on the hub.
- Does nothing outside production: the ``PRODUCTION == "true"`` gate comes first
  and makes zero network calls otherwise.
- The delivery key and Access credentials are read from ``NOTIFS_KEY_DIR`` on
  every call (never cached), so a key rotated by a deploy is picked up without a
  restart. They never appear in any log line.
- Check order is fixed: ``PRODUCTION`` gate (``skip``), key directory
  (``missing_key``), base URL (``error``).
- ``PRODUCTION``, ``NOTIFS_BASE_URL`` and ``NOTIFS_KEY_DIR`` resolve from
  ``os.environ`` first, then from the ``/app/container_environment`` dump,
  because cron jobs do not inherit the compose environment.
- The network is reached only through ``urllib.request.urlopen`` looked up on
  the module at call time, so tests patch the global function.

CLI: ``python notifs_hub.py ping <check> [--fail]`` always exits 0.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NamedTuple

APP_ID: str = "urls4irl"
CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"
DEFAULT_TIMEOUT_SECONDS: float = 10.0
KEY_FILE_NAME: str = "delivery_key"
ACCESS_CLIENT_ID_FILE_NAME: str = "access_client_id"
ACCESS_CLIENT_SECRET_FILE_NAME: str = "access_client_secret"
MASK: str = "***"


class Credentials(NamedTuple):
    key: str
    access_client_id: str
    access_client_secret: str


def _read_dump_value(name: str) -> str | None:
    """Return ``name`` from the container env dump, or ``None`` if absent."""
    try:
        with open(CONTAINER_ENVIRONMENT_FILE, encoding="utf-8") as dump_file:
            for raw_line in dump_file.read().splitlines():
                stripped_line = raw_line.strip()
                if not stripped_line or stripped_line.startswith("#"):
                    continue
                key, separator, value = stripped_line.partition("=")
                if separator and key.strip() == name:
                    return value
    except OSError:
        return None
    return None


def _resolve_env(name: str) -> str:
    """Return ``name`` from ``os.environ``, falling back to the dump ('' if unset)."""
    value = os.environ.get(name)
    if value is None:
        value = _read_dump_value(name)
    return value or ""


def _mask(text: str, secrets: tuple[str, ...]) -> str:
    """Replace every non-empty secret occurrence in ``text`` with a mask."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, MASK)
    return text.replace("\n", " ").replace("\r", " ")


def _log(*, check: str, fail: bool, outcome: str, error: str = "") -> None:
    kind = "fail" if fail else "success"
    print(
        f"notifs_hub lane=heartbeat check={check} path=hub kind={kind} "
        f"outcome={outcome} error={error}",
        file=sys.stderr,
    )


def _read_one(path: Path) -> str:
    """Read a single-line file, stripping one trailing newline ('' on any error)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return ""
    return text[:-1] if text.endswith("\n") else text


def read_credentials(key_dir: Path) -> Credentials | None:
    """Read the three credential files on every call; ``None`` if any is missing/empty."""
    key = _read_one(key_dir / KEY_FILE_NAME)
    access_client_id = _read_one(key_dir / ACCESS_CLIENT_ID_FILE_NAME)
    access_client_secret = _read_one(key_dir / ACCESS_CLIENT_SECRET_FILE_NAME)
    if not (key and access_client_id and access_client_secret):
        return None
    return Credentials(
        key=key,
        access_client_id=access_client_id,
        access_client_secret=access_client_secret,
    )


def ping(
    check: str, *, fail: bool = False, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
) -> bool:
    """POST a heartbeat for ``check``; ``True`` only on HTTP 200, never raises."""
    credentials: Credentials | None = None
    try:
        if _resolve_env("PRODUCTION") != "true":
            _log(check=check, fail=fail, outcome="skip")
            return False
        key_dir_value = _resolve_env("NOTIFS_KEY_DIR")
        if key_dir_value:
            credentials = read_credentials(Path(key_dir_value))
        if credentials is None:
            _log(check=check, fail=fail, outcome="missing_key", error="missing key")
            return False
        base_url = _resolve_env("NOTIFS_BASE_URL").rstrip("/")
        if not base_url:
            _log(
                check=check,
                fail=fail,
                outcome="error",
                error="NOTIFS_BASE_URL is not set",
            )
            return False
        path = f"/v1/heartbeats/{APP_ID}/{urllib.parse.quote(check, safe='')}"
        if fail:
            path += "/fail"
        request = urllib.request.Request(
            base_url + path,
            data=b"",
            method="POST",
            headers={
                "CF-Access-Client-Id": credentials.access_client_id,
                "CF-Access-Client-Secret": credentials.access_client_secret,
                "Authorization": f"Bearer {credentials.key}",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            status = response.status
        if status == 200:
            _log(check=check, fail=fail, outcome="ok")
            return True
        _log(check=check, fail=fail, outcome=f"http_{status}")
        return False
    except urllib.error.HTTPError as http_error:
        _log(
            check=check,
            fail=fail,
            outcome=f"http_{http_error.code}",
            error=_mask(str(http_error), _secrets_of(credentials)),
        )
    except (TimeoutError, socket.timeout) as timeout_error:
        _log(
            check=check,
            fail=fail,
            outcome="timeout",
            error=_mask(str(timeout_error), _secrets_of(credentials)),
        )
    except urllib.error.URLError as url_error:
        is_timeout = isinstance(url_error.reason, (TimeoutError, socket.timeout))
        _log(
            check=check,
            fail=fail,
            outcome="timeout" if is_timeout else "error",
            error=_mask(str(url_error), _secrets_of(credentials)),
        )
    except (OSError, ValueError) as other_error:
        _log(
            check=check,
            fail=fail,
            outcome="error",
            error=_mask(str(other_error), _secrets_of(credentials)),
        )
    return False


def _secrets_of(credentials: Credentials | None) -> tuple[str, ...]:
    if credentials is None:
        return ()
    return (credentials.key, credentials.access_client_secret)


def safe_ping(
    check: str, *, fail: bool = False, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
) -> bool:
    """The entry point scheduled jobs call: ``ping`` that swallows every exception."""
    try:
        return ping(check, fail=fail, timeout_seconds=timeout_seconds)
    except Exception as unexpected_error:  # noqa: BLE001 - heartbeat must never break a job
        try:
            secrets = _secrets_of(
                read_credentials(Path(_resolve_env("NOTIFS_KEY_DIR") or "/nonexistent"))
            )
        except Exception:  # noqa: BLE001
            secrets = ()
        _log(
            check=check,
            fail=fail,
            outcome="error",
            error=_mask(
                f"{type(unexpected_error).__name__}: {unexpected_error}", secrets
            ),
        )
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a hub heartbeat ping.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ping_parser = subparsers.add_parser("ping", help="Ping a heartbeat check")
    ping_parser.add_argument("check")
    ping_parser.add_argument("--fail", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 0
    safe_ping(args.check, fail=args.fail)
    return 0


if __name__ == "__main__":
    sys.exit(main())
