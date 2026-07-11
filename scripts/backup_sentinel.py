"""Stamp the backup last-success sentinel in the metrics Redis.

Invoked by ``daily-docker.sh`` (best-effort, never fails the pipeline) after a
successful database backup. Has no Flask/SQLAlchemy dependency — only ``redis``
is imported, matching the other workflow-container scripts. The sentinel key is
read by the admin health dashboard (``backend/admin/health_service.py``) so the
portal can show when the last backup succeeded.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
import time
from pathlib import Path
from types import ModuleType

import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("backup_sentinel")


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
    "_backup_metrics_strs", "backend/utils/strings/metrics_strs.py"
)
METRICS_REDIS = _metrics_strs_module.METRICS_REDIS


def stamp_backup_success(*, redis_client: redis.Redis, epoch: int) -> None:
    """Set the backup last-success sentinel to ``epoch`` (no TTL).

    No TTL so a long stretch of failed backups naturally ages the value out
    past the health dashboard's staleness threshold instead of vanishing.
    """
    redis_client.set(METRICS_REDIS.BACKUP_LAST_SUCCESS_KEY, str(epoch))


def main() -> int:
    metrics_redis_uri = os.environ.get("METRICS_REDIS_URI", "")
    if not metrics_redis_uri:
        logger.error("METRICS_REDIS_URI is not set; cannot stamp backup sentinel")
        return 1
    redis_client = redis.Redis.from_url(metrics_redis_uri)
    try:
        stamp_backup_success(redis_client=redis_client, epoch=int(time.time()))
    except Exception as stamp_error:
        logger.error("failed to stamp backup sentinel: %s", stamp_error)
        return 1
    finally:
        try:
            redis_client.close()
        except Exception:
            pass
    logger.info("backup last-success sentinel stamped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
