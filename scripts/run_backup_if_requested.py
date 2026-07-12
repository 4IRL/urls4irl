"""Per-minute cron poller that starts an on-demand backup when requested.

The admin portal's "Trigger Backup" action sets a short-TTL flag key in the
metrics Redis (``metrics:backup:trigger_requested``). This poller consumes the
flag atomically with ``GETDEL`` and, when present, runs the same
``daily-docker.sh`` pipeline the 1 AM cron runs. A ``SET NX EX`` lock prevents
an in-flight triggered backup from overlapping a second trigger consumption.

Cross-container design note: the workflow container has no HTTP surface, so a
Redis flag polled by cron (mirroring the existing per-minute flush cron) is the
kick mechanism — no long-running subscriber daemon required. Worst-case start
delay is one cron tick (60s), which is irrelevant for an on-demand backup.

Has no Flask/SQLAlchemy dependency — only ``redis`` is imported.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("backup_trigger_poller")


def _load_module_direct(module_name: str, file_relative_to_app: str) -> ModuleType:
    """Load a backend leaf module without triggering ``backend/__init__.py``.

    Mirrors the side-loading helper in ``flush_metrics.py``: the workflow venv
    has no Flask, so the leaf file is loaded by absolute path. Probes
    ``/app/<rel>`` first (workflow container layout) then
    ``<project_root>/<rel>`` (pytest layout).
    """
    candidate_paths = [
        Path("/app") / file_relative_to_app,
        Path(__file__).resolve().parent.parent / file_relative_to_app,
    ]
    for module_path in candidate_paths:
        if module_path.is_file():
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load spec for {module_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        f"Could not locate {file_relative_to_app} on disk for module {module_name}"
    )


_metrics_strs_module = _load_module_direct(
    "_trigger_metrics_strs", "backend/utils/strings/metrics_strs.py"
)
METRICS_REDIS = _metrics_strs_module.METRICS_REDIS

# A triggered backup should comfortably finish inside this window; the lock
# auto-expires so a crashed poller can never wedge future triggers.
TRIGGER_LOCK_TTL_SECONDS: int = 3600

# Env var daily-docker.sh reads to label the Discord notification. This poller
# only ever runs on-demand admin triggers, so it always marks the run "manual".
BACKUP_TRIGGER_SOURCE_ENV: str = "BACKUP_TRIGGER_SOURCE"
MANUAL_TRIGGER_SOURCE: str = "manual"

_BACKUP_SCRIPT_CANDIDATES: tuple[Path, ...] = (
    Path("/app/daily-docker.sh"),
    Path(__file__).resolve().parent / "daily-docker.sh",
)


def consume_trigger_request(*, redis_client: redis.Redis) -> str | None:
    """Atomically read-and-remove the trigger flag; return its value or None.

    ``GETDEL`` guarantees a flag set between poller runs is consumed exactly
    once — a second concurrent poller sees ``None``.
    """
    flag_value = redis_client.getdel(METRICS_REDIS.BACKUP_TRIGGER_KEY)
    if flag_value is None:
        return None
    return flag_value.decode() if isinstance(flag_value, bytes) else str(flag_value)


def acquire_trigger_lock(*, redis_client: redis.Redis) -> bool:
    """Take the poller-side lock; False when a triggered backup is in flight."""
    return bool(
        redis_client.set(
            METRICS_REDIS.BACKUP_TRIGGER_LOCK_KEY,
            "1",
            nx=True,
            ex=TRIGGER_LOCK_TTL_SECONDS,
        )
    )


def release_trigger_lock(*, redis_client: redis.Redis) -> None:
    """Release the poller-side lock (best-effort; TTL is the backstop)."""
    try:
        redis_client.delete(METRICS_REDIS.BACKUP_TRIGGER_LOCK_KEY)
    except Exception as release_error:
        logger.warning("failed to release trigger lock: %s", release_error)


def resolve_backup_script_path() -> Path | None:
    """Locate daily-docker.sh (container layout first, then repo layout)."""
    for candidate_path in _BACKUP_SCRIPT_CANDIDATES:
        if candidate_path.is_file():
            return candidate_path
    return None


def run_backup_pipeline(*, backup_script_path: Path) -> int:
    """Run the backup pipeline synchronously; return its exit code.

    daily-docker.sh manages its own logging (per-day workflow logfile) and
    Discord notifications, so this poller only records the exit code. The
    subprocess env is tagged ``BACKUP_TRIGGER_SOURCE=manual`` so the pipeline's
    Discord messages identify this as an admin-triggered run rather than the
    nightly scheduled one.
    """
    pipeline_env = {**os.environ, BACKUP_TRIGGER_SOURCE_ENV: MANUAL_TRIGGER_SOURCE}
    completed_process = subprocess.run(
        ["/bin/bash", str(backup_script_path)], check=False, env=pipeline_env
    )
    return completed_process.returncode


def main() -> int:
    metrics_redis_uri = os.environ.get("METRICS_REDIS_URI", "")
    if not metrics_redis_uri:
        logger.error("METRICS_REDIS_URI is not set; cannot poll for backup trigger")
        return 1

    redis_client = redis.Redis.from_url(metrics_redis_uri)
    try:
        requested_epoch = consume_trigger_request(redis_client=redis_client)
        if requested_epoch is None:
            return 0

        if not acquire_trigger_lock(redis_client=redis_client):
            logger.warning(
                "backup trigger (requested at epoch %s) skipped: a triggered "
                "backup is already in flight",
                requested_epoch,
            )
            return 0

        backup_script_path = resolve_backup_script_path()
        if backup_script_path is None:
            logger.error("daily-docker.sh not found; cannot run triggered backup")
            release_trigger_lock(redis_client=redis_client)
            return 1

        logger.info(
            "backup trigger consumed (requested at epoch %s); starting %s",
            requested_epoch,
            backup_script_path,
        )
        try:
            exit_code = run_backup_pipeline(backup_script_path=backup_script_path)
        finally:
            release_trigger_lock(redis_client=redis_client)
        logger.info("triggered backup pipeline finished with exit code %d", exit_code)
        return exit_code
    finally:
        try:
            redis_client.close()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
