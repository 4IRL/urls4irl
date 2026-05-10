"""Liveness healthcheck for the metrics workflow container.

Reads the ``metrics:flush:last_success_epoch`` sentinel written by
``scripts/flush_metrics.py`` after every successful flush and exits non-zero
when the sentinel is missing or older than
``METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS`` (default 180s). Wired into the
workflow service's Docker healthcheck so the container is reported unhealthy
when flushes silently break — the prior ``pgrep cron`` healthcheck only
confirmed the cron daemon was alive, not that flushes were progressing.

Standalone (stdlib + ``redis`` only) so the workflow venv does not need
Flask/SQLAlchemy installed. Matches the Redis client construction used by
``flush_metrics.py`` exactly so password handling and decode behavior stay
consistent.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import redis

LIVENESS_KEY: str = "metrics:flush:last_success_epoch"
DEFAULT_THRESHOLD_SECONDS: int = 180

# Same `printenv` dump that `startup-workflow.sh` writes and that the cron
# jobs source via `set -a && . /app/container_environment && set +a`. Docker
# spawns healthcheck commands from the *static* compose `environment:` block,
# not from the runtime env exported by the entrypoint, so this script must
# load the same dump as the cron jobs to see `METRICS_REDIS_URI`.
CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"


def _load_env_from_container_dump(path: str = CONTAINER_ENVIRONMENT_FILE) -> None:
    """Best-effort merge of the workflow container's env dump into ``os.environ``.

    Parses ``KEY=value`` lines (the format ``printenv`` writes) and only sets
    entries that are not already present in ``os.environ`` so genuine env-var
    overrides win. Silently no-ops if the file is missing — matching the cron
    pattern, which leaves env empty if the dump never landed.
    """
    dump_path = Path(path)
    if not dump_path.is_file():
        return
    try:
        for raw_line in dump_path.read_text(encoding="utf-8").splitlines():
            stripped_line = raw_line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue
            if "=" not in stripped_line:
                continue
            key, _, value = stripped_line.partition("=")
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = value
    except OSError:
        return


def _build_redis_client_from_env() -> redis.Redis:
    """Construct a metrics-DB Redis client from env vars.

    Mirrors ``scripts.flush_metrics._build_redis_client_from_env`` so password
    handling and decode behavior match exactly. Falls back to sourcing
    ``/app/container_environment`` when ``METRICS_REDIS_URI`` is missing —
    Docker spawns healthcheck commands with the static compose ``environment:``
    block, not the runtime env exported by ``startup-workflow.sh``, so without
    this fallback the production workflow container reports unhealthy.
    """
    metrics_uri = os.environ.get("METRICS_REDIS_URI")
    if not metrics_uri:
        _load_env_from_container_dump()
        metrics_uri = os.environ.get("METRICS_REDIS_URI")
    if not metrics_uri:
        raise RuntimeError("METRICS_REDIS_URI environment variable is required")
    return redis.Redis.from_url(metrics_uri)


def _resolve_threshold_seconds() -> int:
    raw_threshold = os.environ.get("METRICS_FLUSH_LIVENESS_THRESHOLD_SECONDS")
    if raw_threshold is None or raw_threshold == "":
        return DEFAULT_THRESHOLD_SECONDS
    return int(raw_threshold)


def check_liveness(
    redis_client: redis.Redis,
    threshold_seconds: int,
    now_epoch: int,
) -> tuple[int, str]:
    """Return ``(exit_code, stderr_message)`` for the healthcheck decision.

    Pure function (no side effects) so it is unit-testable with a mock Redis
    client and an injected ``now_epoch``. Callers handle the actual ``print``
    + ``sys.exit``.
    """
    raw_value = redis_client.get(LIVENESS_KEY)
    if raw_value is None:
        return (1, "missing: no successful flush recorded")

    if isinstance(raw_value, bytes):
        decoded_value = raw_value.decode("utf-8", errors="replace")
    else:
        decoded_value = str(raw_value)

    try:
        last_success_epoch = int(decoded_value)
    except ValueError:
        return (
            1,
            f"missing: liveness sentinel value is not an integer: {decoded_value!r}",
        )

    age_seconds = now_epoch - last_success_epoch
    if age_seconds > threshold_seconds:
        return (
            1,
            f"stale: {age_seconds}s old, threshold {threshold_seconds}s",
        )
    return (0, "")


def main() -> int:
    threshold_seconds = _resolve_threshold_seconds()
    redis_client = _build_redis_client_from_env()
    try:
        exit_code, stderr_message = check_liveness(
            redis_client=redis_client,
            threshold_seconds=threshold_seconds,
            now_epoch=int(time.time()),
        )
    finally:
        try:
            redis_client.close()
        except Exception:
            pass

    if stderr_message:
        print(stderr_message, file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
