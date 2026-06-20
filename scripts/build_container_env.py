"""Build the cron environment dump for the metrics workflow container.

Single source of truth for which environment variables the cron jobs may see.
Invoked once at container start by docker/startup-workflow.sh, this module reads
the compose-injected environment (and, in production, the Docker secret files
under /run/secrets), assembles METRICS_REDIS_URI with a percent-encoded
password, filters everything down to ALLOW_VARS, and writes the KEY=value dump
to /app/container_environment. The bash entrypoint then tightens the file mode
and ownership.

Keeping the logic here rather than inline in the bash entrypoint lets the
allow-list filter and URI assembly be unit-tested without booting the container
image, and makes ALLOW_VARS the one place every drift check reads.
"""

from __future__ import annotations

import os
import urllib.parse
from collections.abc import Mapping
from pathlib import Path

ALLOW_VARS: tuple[str, ...] = (
    "ACCESS_KEY",
    "DEV_SERVER",
    "METRICS_BUCKET_SECONDS",
    "METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS",
    "METRICS_REDIS_URI",
    "NOTIFICATION_URL",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "POSTGRES_PASSWORD",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "PRODUCTION",
    "R2_ENDPOINT",
    "SECRET_ACCESS_KEY",
)
METRICS_REDIS_HOST_PATH: str = "redis-metrics:6379/0"
CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"
SECRETS_DIR: str = "/run/secrets"


def assemble_metrics_redis_uri(*, redis_password: str) -> str:
    """Build the metrics Redis URI with a percent-encoded password.

    Mirrors the assembly in backend/config.py for the web container. The
    password is percent-encoded so URL-reserved characters (@, :, #, ?) do not
    produce a malformed URI. Note urllib.parse.quote does NOT encode '/' by
    default, so a password containing '/' is left as-is.

    Examples:
        >>> assemble_metrics_redis_uri(redis_password="p@ssword")
        'redis://:p%40ssword@redis-metrics:6379/0'
        >>> assemble_metrics_redis_uri(redis_password="")
        'redis://:@redis-metrics:6379/0'
    """
    encoded_password = urllib.parse.quote(redis_password)
    return f"redis://:{encoded_password}@{METRICS_REDIS_HOST_PATH}"


def read_secret_files(*, secrets_dir: Path) -> dict[str, str]:
    """Read Docker secret files into a ``{basename: contents}`` mapping.

    Each regular file under ``secrets_dir`` becomes one entry keyed by its
    basename, with surrounding whitespace stripped. Beyond matching the bash
    ``secret_value=$(cat …)`` trailing-newline drop, ``.strip()`` also removes
    any embedded leading/trailing newline so a malformed secret cannot inject a
    spurious ``KEY=value`` line into the env dump. A missing directory yields an
    empty mapping.

    Example:
        Given /run/secrets/REDIS_PASSWORD containing "hunter2\\n":
        >>> read_secret_files(secrets_dir=Path("/run/secrets"))
        {'REDIS_PASSWORD': 'hunter2'}
    """
    secrets: dict[str, str] = {}
    if not secrets_dir.is_dir():
        return secrets
    for secret_file in sorted(secrets_dir.iterdir()):
        if secret_file.is_file():
            secrets[secret_file.name] = secret_file.read_text(encoding="utf-8").strip()
    return secrets


def build_env_mapping(
    *,
    base_environ: Mapping[str, str],
    secrets: Mapping[str, str],
    production: bool,
) -> dict[str, str]:
    """Merge secrets into the base environment and assemble the Redis URI.

    In production the Docker secrets override the compose-injected environment
    and METRICS_REDIS_URI is assembled from the REDIS_PASSWORD secret (an unset
    password falls back to an empty string, matching the prior bash behavior).
    Outside production the base environment is returned unchanged — secrets are
    not mounted and METRICS_REDIS_URI flows through from compose.
    """
    env_mapping: dict[str, str] = dict(base_environ)
    if production:
        env_mapping.update(secrets)
        env_mapping["METRICS_REDIS_URI"] = assemble_metrics_redis_uri(
            redis_password=secrets.get("REDIS_PASSWORD", "")
        )
    return env_mapping


def render_env_dump(*, env_mapping: Mapping[str, str]) -> str:
    """Render the allow-listed, present-only ``KEY=value`` dump.

    Iterates ALLOW_VARS in order and emits one ``KEY=value`` line per variable
    present in ``env_mapping`` — replicating the bash ``${!var+x}`` present-only
    filter and array ordering so the on-disk dump is byte-identical to the prior
    shell implementation. Variables outside ALLOW_VARS (the raw REDIS_PASSWORD,
    container metadata) are never emitted.

    Example:
        >>> render_env_dump(env_mapping={"PRODUCTION": "true", "REDIS_PASSWORD": "x"})
        'PRODUCTION=true\\n'
    """
    return "".join(
        f"{var}={env_mapping[var]}\n" for var in ALLOW_VARS if var in env_mapping
    )


def write_env_dump(*, dump: str) -> None:
    """Write the env dump to CONTAINER_ENVIRONMENT_FILE at mode 600 atomically.

    Uses ``os.open`` with ``O_CREAT`` and an explicit ``0o600`` mode so the file
    is never world-readable, even briefly, between creation and the entrypoint's
    follow-up ``chmod`` — closing the TOCTOU window that ``Path.write_text`` (which
    creates at the process umask) would otherwise leave open. ``O_TRUNC`` clears
    any stale contents; the mode argument is only honored when the file is newly
    created, so a pre-existing file keeps its mode and the entrypoint's explicit
    ``chmod 600`` remains the backstop.
    """
    file_descriptor = os.open(
        CONTAINER_ENVIRONMENT_FILE,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as dump_file:
        dump_file.write(dump)


def main() -> None:
    production = os.environ.get("PRODUCTION") == "true"
    secrets = read_secret_files(secrets_dir=Path(SECRETS_DIR)) if production else {}
    env_mapping = build_env_mapping(
        base_environ=os.environ, secrets=secrets, production=production
    )
    write_env_dump(dump=render_env_dump(env_mapping=env_mapping))


if __name__ == "__main__":
    main()
