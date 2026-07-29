from __future__ import annotations

from flask import current_app
from redis import Redis

from backend.utils.constants import USER_CONSTANTS
from backend.utils.strings.config_strs import CONFIG_ENVS

_MEMORY_URI: str = "memory://"


def _build_reauth_redis() -> Redis | None:
    """Build a client on the shared enforcement Redis (``REDIS_URI``), or return
    ``None`` when Redis is unavailable.

    Mirrors ``backend/users/services/account_service.py:_build_rate_limit_redis``
    — reads the shared ``REDIS_URI`` and returns ``None`` for an unset URI or the
    in-memory stub, so every caller fails open.

    Lives in ``backend/utils`` (a neutral home importable by both
    ``backend.users.services.*`` and ``backend.splash.services.*`` with no import
    cycle) because the per-user re-auth lockout is shared by the change-password
    gate and the settings OAuth-link gate (DD-1).
    """
    redis_uri: str | None = current_app.config.get(CONFIG_ENVS.REDIS_URI)
    if not redis_uri or redis_uri == _MEMORY_URI:
        return None
    return Redis.from_url(redis_uri)


def _reauth_failure_key(user_id: int) -> str:
    """The per-user failure-counter key, shared across both re-auth gates so the
    same password being guessed on either surface trips one lockout."""
    return f"reauth-fail:{user_id}"


def is_reauth_locked_out(user_id: int) -> bool:
    """Whether ``user_id`` has exceeded ``MAX_REAUTH_FAILURES`` failed re-auth
    attempts within the current window.

    Fail-open: any Redis error is logged and treated as not-locked-out (the
    lockout is defense-in-depth on top of the per-IP limiter, never the sole
    gate).
    """
    redis_client = _build_reauth_redis()
    if redis_client is None:
        return False
    try:
        current_count = int(redis_client.get(_reauth_failure_key(user_id)) or 0)
        return current_count >= USER_CONSTANTS.MAX_REAUTH_FAILURES
    except Exception as redis_error:
        current_app.logger.exception(
            f"reauth lockout precheck failed (failing open): {redis_error}"
        )
        return False


def record_reauth_failure(user_id: int) -> None:
    """Increment ``user_id``'s failed-re-auth counter, anchoring a fixed
    ``REAUTH_LOCKOUT_WINDOW_SECONDS`` window on the first failure (EXPIRE set only
    when the INCR result is ``1``). Fail-open: any Redis error is logged and
    treated as a no-op."""
    redis_client = _build_reauth_redis()
    if redis_client is None:
        return
    try:
        failure_key = _reauth_failure_key(user_id)
        new_count = redis_client.incr(failure_key)
        if new_count == 1:
            redis_client.expire(
                failure_key, USER_CONSTANTS.REAUTH_LOCKOUT_WINDOW_SECONDS
            )
    except Exception as redis_error:
        current_app.logger.exception(
            f"reauth failure record failed (failing open): {redis_error}"
        )


def clear_reauth_failures(user_id: int) -> None:
    """Delete ``user_id``'s failed-re-auth counter after a successful re-auth.
    Fail-open: any Redis error is logged and treated as a no-op."""
    redis_client = _build_reauth_redis()
    if redis_client is None:
        return
    try:
        redis_client.delete(_reauth_failure_key(user_id))
    except Exception as redis_error:
        current_app.logger.exception(
            f"reauth failure clear failed (failing open): {redis_error}"
        )
