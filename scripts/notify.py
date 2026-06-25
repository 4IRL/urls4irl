"""Single source of truth for every workflow-container Discord message.

The ``workflow`` container's three scheduled jobs (daily backup, every-minute
metrics flush, hourly gauge sample) all route their Discord notifications
through this module. It owns message construction, sanitization, environment
resolution, the daily-summary decision, the point-in-time metrics-health
snapshot, and the Redis-backed failure/recovery transition decisions.

Stdlib-only plus ``redis`` (already resident in ``/opt/metrics-venv``, the
workflow venv that has no Flask/SQLAlchemy). Mirrors the
``check_flush_liveness.py`` shape: pure decision functions are unit-tested with
a ``MagicMock`` Redis client and an injected ``now_epoch``; the thin impure
``send``/``main`` shims handle the real subprocess + Redis I/O.

The two sentinel keys this module reads are hardcoded literals (matching the
``check_flush_liveness.py`` precedent) because importing ``metrics_strs`` would
drag in ``backend/__init__.py`` and crash on the missing Flask install. A unit
test cross-checks the literals against ``METRICS_REDIS`` so a rename on either
side is caught.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time

import redis

MESSAGE_PREFIX: str = "DOCKER: "
CONTAINER_ENVIRONMENT_FILE: str = "/app/container_environment"
RESTRICTED_CURL_BINARY: str = "restricted_curl"
DISCORD_CONTENT_MAX_CHARS: int = 2000

STATUS_SUCCESS: str = "SUCCESS"
STATUS_FAILURE: str = "FAILURE"
STATUS_RECOVERED: str = "RECOVERED"
STATUS_INFO: str = "INFO"

STATUS_OK_GLYPH: str = "✅"
STATUS_FAIL_GLYPH: str = "❌"
STATUS_SKIP_GLYPH: str = "💤"

HEALTH_OK_GLYPH: str = "🟢"
HEALTH_STALE_GLYPH: str = "🔴"
HEALTH_UNKNOWN_GLYPH: str = "❔"

AREA_DB: str = "💾"
AREA_LOGS: str = "📄"
AREA_REMOTE: str = "☁️"
AREA_METRICS: str = "📊"

SUMMARY_TITLE_TEMPLATE: str = "**Daily Backup — {status}**"
METRICS_HEADER_TEMPLATE: str = "**Metrics — {verdict}**"
METRICS_VERDICT_HEALTHY: str = "HEALTHY"
METRICS_VERDICT_STALE: str = "STALE"
METRICS_VERDICT_UNKNOWN: str = "UNKNOWN"

DATABASE_LABEL: str = "Database"
LOGS_LABEL: str = "Logs"
REMOTE_DB_LABEL: str = "R2 daily"
REMOTE_MONTHLY_LABEL: str = "R2 monthly"
REMOTE_LOGS_LABEL: str = "R2 logs"
FLUSH_JOB_LABEL: str = "Minute Flush"
GAUGE_JOB_LABEL: str = "Hourly Snapshot"

HEALTH_STALE_AFTER_SECONDS: int = 5400
FLUSH_LAST_SUCCESS_KEY: str = "metrics:flush:last_success_epoch"
GAUGE_LAST_SUCCESS_KEY: str = "metrics:gauges:last_sample_epoch"

_REMOTE_STATUS_OK: str = "ok"
_REMOTE_STATUS_FAIL: str = "fail"
_REMOTE_STATUS_SKIP: str = "skip"
_ALLOWED_REMOTE_STATUSES: frozenset[str] = frozenset(
    (_REMOTE_STATUS_OK, _REMOTE_STATUS_FAIL, _REMOTE_STATUS_SKIP)
)

_HEALTH_STATE_HEALTHY: str = "healthy"
_HEALTH_STATE_STALE: str = "stale"
_HEALTH_STATE_UNKNOWN: str = "unknown"

_MISSING_JOB_STATUS_ERROR: str = "--job and --status are required without --summary"


def sanitize_message(raw: str) -> str:
    """Make ``raw`` safe to interpolate into ``{"content":"<raw>"}`` raw JSON.

    ``restricted_curl`` does no JSON escaping, so any unescaped ``"``, ``\\``,
    ``}`` or real newline in the message breaks the payload. Transforms, in
    order:

    1. ``"`` -> ``'`` (avoid JSON quote-escaping entirely).
    2. ``}`` -> ``)`` (a closing brace in the message would prematurely close
       the manually-built ``{"content":"<raw>"}`` JSON object in
       ``restricted-curl.sh``).
    3. Literal backslash ``\\`` -> ``/`` (neutralize stray backslashes). Runs
       BEFORE step 4 so the backslash in the newly-introduced ``\\n`` escape is
       never re-converted.
    4. Each real newline (0x0A) -> the two-character escape ``\\`` + ``n`` so
       structural line breaks survive into the JSON as valid ``\\n`` escapes
       that Discord renders as line breaks.
    5. ``\\r``, ``\\t`` and any other ASCII control char -> single space; then
       strip leading/trailing whitespace.
    6. Collapse runs of spaces to one (the escaped ``\\n`` is not whitespace, so
       line breaks survive).
    7. Truncate to ``DISCORD_CONTENT_MAX_CHARS``; if the slice ends in a lone
       (unpaired) trailing backslash, strip it so it cannot escape the closing
       quote when a ``\\n`` escape straddles the boundary.

    Examples:
        >>> sanitize_message("line one\\nline two")
        'line one\\\\nline two'
        >>> sanitize_message('file "name\\\\path"')
        "file 'name/path'"
        >>> sanitize_message("done}")
        'done)'
    """
    result = raw.replace('"', "'")
    result = result.replace("}", ")")
    result = result.replace("\\", "/")
    result = result.replace("\n", "\\n")

    result = re.sub(r"[\x00-\x1f]", " ", result).strip()
    result = re.sub(r" {2,}", " ", result)

    result = result[:DISCORD_CONTENT_MAX_CHARS]
    if result.endswith("\\") and not result.endswith("\\\\"):
        result = result[:-1]
    return result


def build_message(*, job: str, status: str, detail: str = "") -> str:
    """Build a single-line ``DOCKER: <job> <status>[ — <detail>]`` message.

    The detail clause is only appended when ``detail`` is non-empty. The result
    is passed through ``sanitize_message`` once. Pure.
    """
    message = f"{MESSAGE_PREFIX}{job} {status}"
    if detail:
        message = f"{message} — {detail}"
    return sanitize_message(message)


def _remote_glyph(status: str) -> str:
    """Map a tri-state remote status token to its glyph, validating the token."""
    if status not in _ALLOWED_REMOTE_STATUSES:
        raise ValueError(
            f"unexpected remote status {status!r}; "
            f"expected one of {sorted(_ALLOWED_REMOTE_STATUSES)}"
        )
    if status == _REMOTE_STATUS_OK:
        return STATUS_OK_GLYPH
    if status == _REMOTE_STATUS_FAIL:
        return STATUS_FAIL_GLYPH
    return STATUS_SKIP_GLYPH


def build_summary_message(
    *,
    database_ok: bool,
    logs_ok: bool,
    remote_db: str,
    remote_monthly: str,
    remote_logs: str,
) -> tuple[str, int]:
    """Build the itemized end-of-run backup digest (BACKUP SECTION ONLY).

    The three ``remote_*`` params are tri-state ``"ok" | "fail" | "skip"``
    tokens, where ``skip`` means the sub-step legitimately did not run (e.g.
    ``remote_monthly`` on a non-1st-of-month day, or a remote leg bypassed
    because its local stage failed, or the whole remote leg skipped in dev
    mode). Returns ``(message, exit_code)`` where ``exit_code == 0`` iff both
    local stages succeeded AND no remote sub-step is ``fail`` — a ``skip`` is
    not a failure. Raises ``ValueError`` on an unexpected ``remote_*`` token.

    Returns un-sanitized real-newline text; ``main()`` sanitizes the fully
    composed message (both sections joined) exactly once. Pure.
    """
    local_failed = (not database_ok) or (not logs_ok)
    remote_failed = any(
        status == _REMOTE_STATUS_FAIL
        for status in (remote_db, remote_monthly, remote_logs)
    )
    exit_code = 1 if (local_failed or remote_failed) else 0
    status_word = STATUS_FAILURE if exit_code else STATUS_SUCCESS

    db_glyph = STATUS_OK_GLYPH if database_ok else STATUS_FAIL_GLYPH
    logs_glyph = STATUS_OK_GLYPH if logs_ok else STATUS_FAIL_GLYPH

    lines = [
        SUMMARY_TITLE_TEMPLATE.format(status=status_word),
        f"{db_glyph} {AREA_DB} {DATABASE_LABEL}",
        f"{logs_glyph} {AREA_LOGS} {LOGS_LABEL}",
        f"{_remote_glyph(remote_db)} {AREA_REMOTE} {REMOTE_DB_LABEL}",
        f"{_remote_glyph(remote_monthly)} {AREA_REMOTE} {REMOTE_MONTHLY_LABEL}",
        f"{_remote_glyph(remote_logs)} {AREA_REMOTE} {REMOTE_LOGS_LABEL}",
    ]
    return "\n".join(lines), exit_code


def format_age(*, seconds: int) -> str:
    """Compact human age string.

    ``<60`` -> seconds, ``<3600`` -> whole minutes, else whole hours. Pure.

    Examples:
        >>> format_age(seconds=38)
        '38s'
        >>> format_age(seconds=750)
        '12m'
        >>> format_age(seconds=7200)
        '2h'
    """
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h"


def format_job_health(
    *,
    label: str,
    last_success_epoch: int | None,
    now_epoch: int,
    stale_after_seconds: int,
) -> tuple[str, str]:
    """Return ``(row_str, state)`` for a single metrics job's health.

    ``state`` is one of ``"healthy"``, ``"stale"``, or ``"unknown"`` and feeds
    ``read_metrics_health``'s section-verdict derivation.

    ``last_success_epoch is None`` -> ``unknown`` row (sentinel absent: the job
    has never stamped, or Redis was unreadable). Otherwise the age is the
    elapsed time since the stamp, clamped to ``0`` on clock skew; ``age <=
    stale_after_seconds`` -> ``healthy``, else ``stale``. Pure.

    Examples:
        >>> format_job_health(label="X", last_success_epoch=None,
        ...                   now_epoch=100, stale_after_seconds=90)[1]
        'unknown'
        >>> format_job_health(label="X", last_success_epoch=80,
        ...                   now_epoch=100, stale_after_seconds=90)[1]
        'healthy'
        >>> format_job_health(label="X", last_success_epoch=0,
        ...                   now_epoch=100, stale_after_seconds=90)[1]
        'stale'
    """
    if last_success_epoch is None:
        row = f"{HEALTH_UNKNOWN_GLYPH} {AREA_METRICS} {label} · unknown"
        return row, _HEALTH_STATE_UNKNOWN

    age = now_epoch - last_success_epoch
    if age < 0:
        age = 0

    if age <= stale_after_seconds:
        row = (
            f"{HEALTH_OK_GLYPH} {AREA_METRICS} {label} · "
            f"{format_age(seconds=age)} ago"
        )
        return row, _HEALTH_STATE_HEALTHY

    row = (
        f"{HEALTH_STALE_GLYPH} {AREA_METRICS} {label} · STALE "
        f"{format_age(seconds=age)} ago"
    )
    return row, _HEALTH_STATE_STALE


def _read_sentinel_epoch(redis_client: redis.Redis, key: str) -> int | None:
    """Best-effort decode of a sentinel epoch; any miss/non-int/error -> None."""
    try:
        raw_value = redis_client.get(key)
    except Exception:
        return None
    if raw_value is None:
        return None
    if isinstance(raw_value, bytes):
        decoded_value = raw_value.decode("utf-8", errors="replace")
    else:
        decoded_value = str(raw_value)
    try:
        return int(decoded_value)
    except ValueError:
        return None


def read_metrics_health(*, redis_client: redis.Redis | None, now_epoch: int) -> str:
    """Return the full METRICS SECTION string (real newlines, un-sanitized).

    Best-effort reads both sentinels (never raises). The section verdict:
    ``HEALTHY`` only when BOTH job states are ``healthy``; ``STALE`` when any
    state is ``stale`` OR ``unknown``; ``UNKNOWN`` is reserved EXCLUSIVELY for a
    falsy ``redis_client`` (Redis unreadable) and is never derived from a
    ``state="unknown"`` row.
    """
    if not redis_client:
        return (
            f"{METRICS_HEADER_TEMPLATE.format(verdict=METRICS_VERDICT_UNKNOWN)}\n"
            f"{HEALTH_UNKNOWN_GLYPH} {AREA_METRICS} metrics health unavailable"
        )

    flush_epoch = _read_sentinel_epoch(redis_client, FLUSH_LAST_SUCCESS_KEY)
    gauge_epoch = _read_sentinel_epoch(redis_client, GAUGE_LAST_SUCCESS_KEY)

    flush_row, flush_state = format_job_health(
        label=FLUSH_JOB_LABEL,
        last_success_epoch=flush_epoch,
        now_epoch=now_epoch,
        stale_after_seconds=HEALTH_STALE_AFTER_SECONDS,
    )
    gauge_row, gauge_state = format_job_health(
        label=GAUGE_JOB_LABEL,
        last_success_epoch=gauge_epoch,
        now_epoch=now_epoch,
        stale_after_seconds=HEALTH_STALE_AFTER_SECONDS,
    )

    if flush_state == _HEALTH_STATE_HEALTHY and gauge_state == _HEALTH_STATE_HEALTHY:
        verdict = METRICS_VERDICT_HEALTHY
    else:
        verdict = METRICS_VERDICT_STALE

    header = METRICS_HEADER_TEMPLATE.format(verdict=verdict)
    return f"{header}\n{flush_row}\n{gauge_row}"


def _load_env_from_container_dump(path: str | None = None) -> None:
    """Best-effort merge of the container env dump into ``os.environ``.

    Parses ``KEY=value`` lines and only sets entries not already present in
    ``os.environ`` so genuine env-var overrides win. Silently no-ops if the
    file is missing or unreadable. Mirrors
    ``flush_metrics._load_env_from_container_dump`` — needed because
    ``daily-docker.sh`` sources the dump without ``set -a``, so child processes
    do not inherit the vars. The dump path is resolved from the module-level
    ``CONTAINER_ENVIRONMENT_FILE`` at call time (so tests can monkeypatch it)
    unless an explicit ``path`` is supplied.
    """
    if path is None:
        path = CONTAINER_ENVIRONMENT_FILE
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as dump_file:
            for raw_line in dump_file.read().splitlines():
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


def resolve_notification_env() -> tuple[str, str]:
    """Return ``(production, notification_url)`` from env, falling back to dump.

    Reads ``os.environ`` first; for any of ``PRODUCTION`` / ``NOTIFICATION_URL``
    still missing, merges the container dump then re-reads. Defaults to empty
    strings when absent.
    """
    production = os.environ.get("PRODUCTION")
    notification_url = os.environ.get("NOTIFICATION_URL")
    if production is None or notification_url is None:
        _load_env_from_container_dump()
        production = os.environ.get("PRODUCTION")
        notification_url = os.environ.get("NOTIFICATION_URL")
    return production or "", notification_url or ""


def send(message: str, *, production: str, notification_url: str) -> int:
    """Deliver ``message`` to Discord via ``restricted_curl``; never raises.

    In dev (``production != "true"``) the message is echoed with the ``IGNORE``
    prefix and ``0`` returned without shelling out. In production with a webhook
    URL, ``restricted_curl POST <url> <message>`` is run and its returncode
    returned; an empty URL returns ``1``.
    """
    if production != "true":
        print(f"IGNORE, IN DEVELOPMENT: {message}")
        return 0
    if not notification_url:
        return 1
    completed = subprocess.run(
        [RESTRICTED_CURL_BINARY, "POST", notification_url, message],
        check=False,
    )
    return completed.returncode


def mark_failure_and_should_notify(
    redis_client: redis.Redis, failure_flag_key: str
) -> bool:
    """Set the failure flag with ``NX``; return ``True`` only on first failure.

    A ``True`` return means the flag was absent (this is the start of an
    outage), so exactly one failure message should be emitted. Atomic.
    """
    return bool(redis_client.set(failure_flag_key, "1", nx=True))


def clear_failure_and_should_notify_recovery(
    redis_client: redis.Redis, failure_flag_key: str
) -> bool:
    """Delete the failure flag; return ``True`` only when one was cleared.

    A ``True`` return means we were in an outage, so exactly one recovery
    message should be emitted. Atomic.
    """
    return bool(redis_client.delete(failure_flag_key))


def _build_metrics_redis_client() -> redis.Redis | None:
    """Best-effort metrics-DB Redis client; ``None`` on any failure.

    Reads ``METRICS_REDIS_URI`` from ``os.environ``; if missing, merges the
    container dump then re-reads. Any missing key, empty string, or connection
    error returns ``None`` rather than raising — the daily summary must never
    fail because the metrics Redis was unreachable. Used only by the
    ``--summary`` path.
    """
    try:
        metrics_uri = os.environ.get("METRICS_REDIS_URI")
        if not metrics_uri:
            _load_env_from_container_dump()
            metrics_uri = os.environ.get("METRICS_REDIS_URI")
        if not metrics_uri:
            return None
        return redis.Redis.from_url(metrics_uri)
    except Exception:
        return None


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workflow Discord notifier.")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--job")
    parser.add_argument("--status")
    parser.add_argument("--detail", default="")
    parser.add_argument("--database", choices=("ok", "fail"), default=_REMOTE_STATUS_OK)
    parser.add_argument("--logs", choices=("ok", "fail"), default=_REMOTE_STATUS_OK)
    parser.add_argument(
        "--remote-db", choices=("ok", "fail", "skip"), default=_REMOTE_STATUS_SKIP
    )
    parser.add_argument(
        "--remote-monthly", choices=("ok", "fail", "skip"), default=_REMOTE_STATUS_SKIP
    )
    parser.add_argument(
        "--remote-logs", choices=("ok", "fail", "skip"), default=_REMOTE_STATUS_SKIP
    )
    return parser


def main(argv: list[str]) -> int:
    """CLI entrypoint: single-message (``--job/--status``) or ``--summary``."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    if not args.summary and (not args.job or not args.status):
        parser.error(_MISSING_JOB_STATUS_ERROR)
    production, notification_url = resolve_notification_env()

    if args.summary:
        backup_section, exit_code = build_summary_message(
            database_ok=(args.database == "ok"),
            logs_ok=(args.logs == "ok"),
            remote_db=args.remote_db,
            remote_monthly=args.remote_monthly,
            remote_logs=args.remote_logs,
        )
        redis_client = _build_metrics_redis_client()
        metrics_section = read_metrics_health(
            redis_client=redis_client, now_epoch=int(time.time())
        )
        combined = backup_section + "\n\n" + metrics_section
        payload = sanitize_message(combined)
        send(payload, production=production, notification_url=notification_url)
        return exit_code

    message = build_message(job=args.job, status=args.status, detail=args.detail)
    return send(message, production=production, notification_url=notification_url)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
