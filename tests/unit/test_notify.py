from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.utils.strings.metrics_strs import METRICS_REDIS
from scripts import notify
from scripts.notify import (
    DISCORD_CONTENT_MAX_CHARS,
    FLUSH_LAST_SUCCESS_KEY,
    GAUGE_LAST_SUCCESS_KEY,
    HEALTH_OK_GLYPH,
    HEALTH_STALE_GLYPH,
    HEALTH_UNKNOWN_GLYPH,
    HEALTH_STALE_AFTER_SECONDS,
    MESSAGE_PREFIX,
    RESTRICTED_CURL_BINARY,
    STATUS_FAILURE,
    STATUS_INFO,
    STATUS_SUCCESS,
    build_message,
    build_summary_message,
    clear_failure_and_should_notify_recovery,
    format_age,
    format_job_health,
    main,
    mark_failure_and_should_notify,
    read_metrics_health,
    resolve_notification_env,
    sanitize_message,
    send,
)

pytestmark = pytest.mark.unit


_FIXED_NOW_EPOCH = 1_800_000_000


# ---------------------------------------------------------------------------
# sanitize_message
# ---------------------------------------------------------------------------


def test_sanitize_message_converts_real_newline_to_escape():
    """
    GIVEN a two-line input separated by a real newline byte
    WHEN sanitized
    THEN the newline becomes the two-character backslash-n escape so it
        survives into the JSON content payload.
    """
    assert sanitize_message("line one\nline two") == "line one\\nline two"


def test_sanitize_message_replaces_double_quote_with_single():
    """
    GIVEN a string containing a double quote
    WHEN sanitized
    THEN the double quote becomes a single quote so JSON escaping is avoided.
    """
    assert sanitize_message('say "hi"') == "say 'hi'"


def test_sanitize_message_replaces_backslash_before_newline_escape():
    """
    GIVEN a filename containing both a stray double quote and a backslash
    WHEN sanitized
    THEN the backslash becomes a slash and the quote a single quote, and the
        backslash-to-slash step runs BEFORE the newline escape so the newly
        introduced backslash-n is not re-converted.
    """
    assert sanitize_message('file "name\\path"') == "file 'name/path'"


def test_sanitize_message_preserves_markdown_and_special_unicode():
    """
    GIVEN emoji, bold markdown, a middot, and an em dash
    WHEN sanitized
    THEN all pass through untouched (none are JSON-special).
    """
    raw = "🟢 **bold** · — 📊"
    assert sanitize_message(raw) == raw


def test_sanitize_message_collapses_space_runs_and_strips():
    """
    GIVEN a string with leading/trailing whitespace and internal space runs
    WHEN sanitized
    THEN runs of spaces collapse to one and edges are stripped.
    """
    assert sanitize_message("  a    b  ") == "a b"


def test_sanitize_message_truncates_to_max_chars():
    """
    GIVEN a string longer than DISCORD_CONTENT_MAX_CHARS
    WHEN sanitized
    THEN the result is truncated to at most DISCORD_CONTENT_MAX_CHARS.
    """
    raw = "a" * (DISCORD_CONTENT_MAX_CHARS + 50)
    assert len(sanitize_message(raw)) == DISCORD_CONTENT_MAX_CHARS


def test_sanitize_message_strips_dangling_backslash_after_truncation():
    """
    GIVEN a string whose sanitized form straddles the truncation boundary with
        a backslash-n escape, leaving a lone trailing backslash at position
        DISCORD_CONTENT_MAX_CHARS
    WHEN sanitized
    THEN the lone trailing backslash is stripped so it cannot escape the
        closing quote in the JSON payload.
    """
    raw = "a" * (DISCORD_CONTENT_MAX_CHARS - 1) + "\n" + "b"
    result = sanitize_message(raw)
    assert not result.endswith("\\")
    assert len(result) <= DISCORD_CONTENT_MAX_CHARS


# ---------------------------------------------------------------------------
# build_message
# ---------------------------------------------------------------------------


def test_build_message_without_detail():
    """
    GIVEN a job and status with no detail
    WHEN building the message
    THEN it is the prefix + job + status with no detail clause.
    """
    assert build_message(job="DB_BACKUP", status=STATUS_SUCCESS) == (
        f"{MESSAGE_PREFIX}DB_BACKUP SUCCESS"
    )


def test_build_message_with_detail():
    """
    GIVEN a job, status, and detail
    WHEN building the message
    THEN the detail is appended after an em-dash separator.
    """
    assert build_message(job="DB_BACKUP", status=STATUS_FAILURE, detail="oops") == (
        f"{MESSAGE_PREFIX}DB_BACKUP FAILURE — oops"
    )


def test_build_message_info_status_single_prefix():
    """
    GIVEN STATUS_INFO and a detail
    WHEN building a DAILY INFO message
    THEN the prefix appears exactly once and the INFO constant is wired in.
    """
    assert build_message(job="DAILY", status=STATUS_INFO, detail="msg") == (
        "DOCKER: DAILY INFO — msg"
    )


# ---------------------------------------------------------------------------
# build_summary_message
# ---------------------------------------------------------------------------


def test_build_summary_message_all_ok_with_monthly_skip():
    """
    GIVEN all local stages ok, R2 daily/logs ok, R2 monthly skipped
    WHEN building the summary
    THEN exit code is 0 and the SUCCESS title with each exact row appears.
    """
    message, exit_code = build_summary_message(
        database_ok=True,
        logs_ok=True,
        remote_db="ok",
        remote_monthly="skip",
        remote_logs="ok",
    )
    assert exit_code == 0
    assert message.startswith("**Daily Backup — SUCCESS**")
    assert "✅ 💾 Database" in message
    assert "✅ 📄 Logs" in message
    assert "✅ ☁️ R2 daily" in message
    assert "💤 ☁️ R2 monthly" in message
    assert "✅ ☁️ R2 logs" in message


def test_build_summary_message_database_failure():
    """
    GIVEN the database stage failed
    WHEN building the summary
    THEN exit code is 1 with a FAILURE title and a failing database row.
    """
    message, exit_code = build_summary_message(
        database_ok=False,
        logs_ok=True,
        remote_db="ok",
        remote_monthly="skip",
        remote_logs="ok",
    )
    assert exit_code == 1
    assert message.startswith("**Daily Backup — FAILURE**")
    assert "❌ 💾 Database" in message


def test_build_summary_message_logs_failure():
    """
    GIVEN the logs stage failed
    WHEN building the summary
    THEN exit code is 1 with a failing logs row.
    """
    message, exit_code = build_summary_message(
        database_ok=True,
        logs_ok=False,
        remote_db="ok",
        remote_monthly="skip",
        remote_logs="ok",
    )
    assert exit_code == 1
    assert "❌ 📄 Logs" in message


def test_build_summary_message_remote_logs_failure():
    """
    GIVEN the R2 logs upload failed
    WHEN building the summary
    THEN exit code is 1 with a failing R2 logs row.
    """
    message, exit_code = build_summary_message(
        database_ok=True,
        logs_ok=True,
        remote_db="ok",
        remote_monthly="skip",
        remote_logs="fail",
    )
    assert exit_code == 1
    assert "❌ ☁️ R2 logs" in message


def test_build_summary_message_skip_never_fails():
    """
    GIVEN every remote destination skipped
    WHEN building the summary
    THEN exit code is 0 and skip rows render with the skip glyph.
    """
    message, exit_code = build_summary_message(
        database_ok=True,
        logs_ok=True,
        remote_db="skip",
        remote_monthly="skip",
        remote_logs="skip",
    )
    assert exit_code == 0
    assert "💤 ☁️ R2 daily" in message
    assert "💤 ☁️ R2 logs" in message


def test_build_summary_message_invalid_remote_token_raises():
    """
    GIVEN an unexpected remote status token
    WHEN building the summary
    THEN a ValueError is raised.
    """
    with pytest.raises(ValueError):
        build_summary_message(
            database_ok=True,
            logs_ok=True,
            remote_db="bogus",
            remote_monthly="skip",
            remote_logs="ok",
        )


# ---------------------------------------------------------------------------
# format_age
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "seconds,expected",
    [
        (38, "38s"),
        (59, "59s"),
        (60, "1m"),
        (750, "12m"),
        (3599, "59m"),
        (3600, "1h"),
        (7200, "2h"),
    ],
)
def test_format_age(seconds, expected):
    """
    GIVEN a number of seconds
    WHEN formatting a compact age
    THEN the unit boundaries at 60s and 3600s switch as documented.
    """
    assert format_age(seconds=seconds) == expected


# ---------------------------------------------------------------------------
# format_job_health
# ---------------------------------------------------------------------------


def test_format_job_health_none_is_unknown():
    """
    GIVEN a missing last-success epoch (None)
    WHEN formatting job health
    THEN the row contains "unknown" and the state is "unknown".
    """
    row, state = format_job_health(
        label="Minute Flush",
        last_success_epoch=None,
        now_epoch=_FIXED_NOW_EPOCH,
        stale_after_seconds=HEALTH_STALE_AFTER_SECONDS,
    )
    assert "unknown" in row
    assert HEALTH_UNKNOWN_GLYPH in row
    assert state == "unknown"


def test_format_job_health_fresh_is_healthy():
    """
    GIVEN a recent last-success epoch
    WHEN formatting job health
    THEN the row shows the healthy glyph + "ago" and state is "healthy".
    """
    row, state = format_job_health(
        label="Minute Flush",
        last_success_epoch=_FIXED_NOW_EPOCH - 38,
        now_epoch=_FIXED_NOW_EPOCH,
        stale_after_seconds=HEALTH_STALE_AFTER_SECONDS,
    )
    assert HEALTH_OK_GLYPH in row
    assert "ago" in row
    assert state == "healthy"


def test_format_job_health_old_is_stale():
    """
    GIVEN a last-success epoch older than the stale threshold
    WHEN formatting job health
    THEN the row shows the stale glyph + "STALE" and state is "stale".
    """
    row, state = format_job_health(
        label="Hourly Snapshot",
        last_success_epoch=_FIXED_NOW_EPOCH - (HEALTH_STALE_AFTER_SECONDS + 1),
        now_epoch=_FIXED_NOW_EPOCH,
        stale_after_seconds=HEALTH_STALE_AFTER_SECONDS,
    )
    assert HEALTH_STALE_GLYPH in row
    assert "STALE" in row
    assert state == "stale"


def test_format_job_health_negative_age_clamped():
    """
    GIVEN a last-success epoch in the future (clock skew)
    WHEN formatting job health
    THEN the age is clamped to 0 and renders "0s ago" as healthy.
    """
    row, state = format_job_health(
        label="Minute Flush",
        last_success_epoch=_FIXED_NOW_EPOCH + 500,
        now_epoch=_FIXED_NOW_EPOCH,
        stale_after_seconds=HEALTH_STALE_AFTER_SECONDS,
    )
    assert "0s ago" in row
    assert state == "healthy"


# ---------------------------------------------------------------------------
# read_metrics_health
# ---------------------------------------------------------------------------


def _redis_mock_for_keys(values: dict[str, bytes | str | None]) -> MagicMock:
    """Build a Redis mock whose GET returns values keyed by the sentinel key."""
    redis_mock = MagicMock()
    redis_mock.get.side_effect = lambda key: values.get(key)
    return redis_mock


def test_read_metrics_health_both_fresh_is_healthy():
    """
    GIVEN both sentinels fresh
    WHEN reading metrics health
    THEN the section starts with HEALTHY and shows two healthy rows.
    """
    redis_mock = _redis_mock_for_keys(
        {
            FLUSH_LAST_SUCCESS_KEY: str(_FIXED_NOW_EPOCH - 38).encode("utf-8"),
            GAUGE_LAST_SUCCESS_KEY: str(_FIXED_NOW_EPOCH - 720).encode("utf-8"),
        }
    )
    section = read_metrics_health(redis_client=redis_mock, now_epoch=_FIXED_NOW_EPOCH)
    assert section.startswith("**Metrics — HEALTHY**")
    assert section.count(HEALTH_OK_GLYPH) == 2


def test_read_metrics_health_missing_sentinel_is_stale():
    """
    GIVEN one sentinel missing
    WHEN reading metrics health
    THEN the section is STALE and the missing job row is unknown.
    """
    redis_mock = _redis_mock_for_keys(
        {
            FLUSH_LAST_SUCCESS_KEY: str(_FIXED_NOW_EPOCH - 38).encode("utf-8"),
            GAUGE_LAST_SUCCESS_KEY: None,
        }
    )
    section = read_metrics_health(redis_client=redis_mock, now_epoch=_FIXED_NOW_EPOCH)
    assert section.startswith("**Metrics — STALE**")
    assert HEALTH_UNKNOWN_GLYPH in section
    assert "unknown" in section


def test_read_metrics_health_stale_sentinel():
    """
    GIVEN one sentinel older than the stale threshold
    WHEN reading metrics health
    THEN the section is STALE with a stale row.
    """
    redis_mock = _redis_mock_for_keys(
        {
            FLUSH_LAST_SUCCESS_KEY: str(_FIXED_NOW_EPOCH - 38).encode("utf-8"),
            GAUGE_LAST_SUCCESS_KEY: str(
                _FIXED_NOW_EPOCH - (HEALTH_STALE_AFTER_SECONDS + 100)
            ).encode("utf-8"),
        }
    )
    section = read_metrics_health(redis_client=redis_mock, now_epoch=_FIXED_NOW_EPOCH)
    assert section.startswith("**Metrics — STALE**")
    assert HEALTH_STALE_GLYPH in section


def test_read_metrics_health_non_int_is_unknown():
    """
    GIVEN a non-integer sentinel value
    WHEN reading metrics health
    THEN that job renders an unknown row and the section is STALE.
    """
    redis_mock = _redis_mock_for_keys(
        {
            FLUSH_LAST_SUCCESS_KEY: b"not-a-number",
            GAUGE_LAST_SUCCESS_KEY: str(_FIXED_NOW_EPOCH - 720).encode("utf-8"),
        }
    )
    section = read_metrics_health(redis_client=redis_mock, now_epoch=_FIXED_NOW_EPOCH)
    assert section.startswith("**Metrics — STALE**")
    assert HEALTH_UNKNOWN_GLYPH in section
    assert "unknown" in section


def test_read_metrics_health_get_raising_is_unknown():
    """
    GIVEN redis_client.get raising for one job
    WHEN reading metrics health
    THEN the exception does not propagate and that job is unknown.
    """
    redis_mock = MagicMock()

    def _raising_get(key):
        if key == FLUSH_LAST_SUCCESS_KEY:
            raise RuntimeError("redis down")
        return str(_FIXED_NOW_EPOCH - 720).encode("utf-8")

    redis_mock.get.side_effect = _raising_get
    section = read_metrics_health(redis_client=redis_mock, now_epoch=_FIXED_NOW_EPOCH)
    assert HEALTH_UNKNOWN_GLYPH in section
    assert "unknown" in section


def test_read_metrics_health_none_client_is_unknown_fallback():
    """
    GIVEN redis_client is None (Redis unreadable)
    WHEN reading metrics health
    THEN the exact UNKNOWN fallback section is returned.
    """
    section = read_metrics_health(redis_client=None, now_epoch=_FIXED_NOW_EPOCH)
    assert section == ("**Metrics — UNKNOWN**\n❔ 📊 metrics health unavailable")


# ---------------------------------------------------------------------------
# Drift guard: hardcoded keys match METRICS_REDIS
# ---------------------------------------------------------------------------


def test_sentinel_keys_match_metrics_redis():
    """
    GIVEN notify.py's hardcoded sentinel keys
    WHEN compared with METRICS_REDIS
    THEN both match exactly so a rename on either side is caught.
    """
    assert FLUSH_LAST_SUCCESS_KEY == METRICS_REDIS.FLUSH_LAST_SUCCESS_KEY
    assert GAUGE_LAST_SUCCESS_KEY == METRICS_REDIS.GAUGE_LAST_SUCCESS_KEY


# ---------------------------------------------------------------------------
# resolve_notification_env
# ---------------------------------------------------------------------------


def test_resolve_notification_env_reads_environ(monkeypatch):
    """
    GIVEN PRODUCTION and NOTIFICATION_URL present in os.environ
    WHEN resolving notification env
    THEN both are returned directly without touching the dump.
    """
    monkeypatch.setenv("PRODUCTION", "true")
    monkeypatch.setenv("NOTIFICATION_URL", "https://discord.com/api/webhooks/1/abc")
    production, notification_url = resolve_notification_env()
    assert production == "true"
    assert notification_url == "https://discord.com/api/webhooks/1/abc"


def test_resolve_notification_env_dump_fallback(monkeypatch, tmp_path):
    """
    GIVEN env vars absent from os.environ but present in the container dump
    WHEN resolving notification env
    THEN they are loaded from the dump file.
    """
    monkeypatch.delenv("PRODUCTION", raising=False)
    monkeypatch.delenv("NOTIFICATION_URL", raising=False)
    dump_file = tmp_path / "container_environment"
    dump_file.write_text(
        "PRODUCTION=true\nNOTIFICATION_URL=https://discord.com/api/webhooks/9/xyz\n"
    )
    monkeypatch.setattr("scripts.notify.CONTAINER_ENVIRONMENT_FILE", str(dump_file))
    production, notification_url = resolve_notification_env()
    assert production == "true"
    assert notification_url == "https://discord.com/api/webhooks/9/xyz"


def test_resolve_notification_env_defaults_when_missing(monkeypatch, tmp_path):
    """
    GIVEN env vars absent and no dump file
    WHEN resolving notification env
    THEN both default to empty strings.
    """
    monkeypatch.delenv("PRODUCTION", raising=False)
    monkeypatch.delenv("NOTIFICATION_URL", raising=False)
    monkeypatch.setattr(
        "scripts.notify.CONTAINER_ENVIRONMENT_FILE", str(tmp_path / "missing")
    )
    production, notification_url = resolve_notification_env()
    assert production == ""
    assert notification_url == ""


# ---------------------------------------------------------------------------
# send
# ---------------------------------------------------------------------------


def test_send_dev_mode_echoes_and_returns_zero(capsys):
    """
    GIVEN production != "true"
    WHEN sending
    THEN the message is echoed with the IGNORE prefix and 0 is returned,
        without shelling out.
    """
    return_code = send("hello", production="false", notification_url="anything")
    captured = capsys.readouterr()
    assert "IGNORE, IN DEVELOPMENT: hello" in captured.out
    assert return_code == 0


def test_send_prod_mode_invokes_restricted_curl(monkeypatch):
    """
    GIVEN production == "true" and a webhook URL
    WHEN sending
    THEN restricted_curl is invoked POST-style and its returncode propagates.
    """
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("scripts.notify.subprocess.run", fake_run)
    return_code = send(
        "hi",
        production="true",
        notification_url="https://discord.com/api/webhooks/1/abc",
    )
    assert return_code == 0
    fake_run.assert_called_once_with(
        [
            RESTRICTED_CURL_BINARY,
            "POST",
            "https://discord.com/api/webhooks/1/abc",
            "hi",
        ],
        check=False,
    )


def test_send_prod_mode_propagates_failure(monkeypatch):
    """
    GIVEN restricted_curl returns a non-zero code
    WHEN sending
    THEN that code propagates.
    """
    monkeypatch.setattr(
        "scripts.notify.subprocess.run",
        MagicMock(return_value=MagicMock(returncode=1)),
    )
    assert (
        send(
            "hi",
            production="true",
            notification_url="https://discord.com/api/webhooks/1/abc",
        )
        == 1
    )


def test_send_prod_mode_empty_url_returns_one():
    """
    GIVEN production == "true" but no webhook URL
    WHEN sending
    THEN 1 is returned without raising.
    """
    assert send("hi", production="true", notification_url="") == 1


# ---------------------------------------------------------------------------
# transition decisions
# ---------------------------------------------------------------------------


def test_mark_failure_first_failure_returns_true():
    """
    GIVEN the failure flag was absent (SET NX succeeds)
    WHEN marking failure
    THEN True is returned and SET was called with nx=True.
    """
    redis_mock = MagicMock()
    redis_mock.set.return_value = True
    assert mark_failure_and_should_notify(redis_mock, "flag") is True
    redis_mock.set.assert_called_once_with("flag", "1", nx=True)


def test_mark_failure_repeated_failure_returns_false():
    """
    GIVEN the failure flag already present (SET NX returns None)
    WHEN marking failure
    THEN False is returned.
    """
    redis_mock = MagicMock()
    redis_mock.set.return_value = None
    assert mark_failure_and_should_notify(redis_mock, "flag") is False


def test_clear_failure_recovery_returns_true_when_flag_cleared():
    """
    GIVEN the failure flag was present (DELETE returns 1)
    WHEN clearing failure
    THEN True is returned (emit one recovery message).
    """
    redis_mock = MagicMock()
    redis_mock.delete.return_value = 1
    assert clear_failure_and_should_notify_recovery(redis_mock, "flag") is True


def test_clear_failure_recovery_returns_false_when_no_flag():
    """
    GIVEN no failure flag (DELETE returns 0)
    WHEN clearing failure
    THEN False is returned (no recovery message).
    """
    redis_mock = MagicMock()
    redis_mock.delete.return_value = 0
    assert clear_failure_and_should_notify_recovery(redis_mock, "flag") is False


# ---------------------------------------------------------------------------
# _build_metrics_redis_client
# ---------------------------------------------------------------------------


def test_build_metrics_redis_client_dump_fallback(monkeypatch):
    """
    GIVEN METRICS_REDIS_URI absent from os.environ but injected by the dump
        loader
    WHEN building the metrics Redis client
    THEN redis.Redis.from_url is called with the injected URI.
    """
    monkeypatch.delenv("METRICS_REDIS_URI", raising=False)

    def _inject_dump(*args, **kwargs):
        import os

        os.environ["METRICS_REDIS_URI"] = "redis://injected:6379/0"

    monkeypatch.setattr(notify, "_load_env_from_container_dump", _inject_dump)
    from_url_mock = MagicMock(return_value=MagicMock())
    monkeypatch.setattr(notify.redis.Redis, "from_url", from_url_mock)

    notify._build_metrics_redis_client()
    from_url_mock.assert_called_once_with("redis://injected:6379/0")
    monkeypatch.delenv("METRICS_REDIS_URI", raising=False)


def test_build_metrics_redis_client_missing_returns_none(monkeypatch):
    """
    GIVEN METRICS_REDIS_URI absent everywhere
    WHEN building the metrics Redis client
    THEN None is returned rather than raising.
    """
    monkeypatch.delenv("METRICS_REDIS_URI", raising=False)
    monkeypatch.setattr(notify, "_load_env_from_container_dump", lambda *a, **k: None)
    assert notify._build_metrics_redis_client() is None


# ---------------------------------------------------------------------------
# main --summary end-to-end
# ---------------------------------------------------------------------------


def test_main_summary_composes_both_sections_and_sanitizes(monkeypatch):
    """
    GIVEN a --summary invocation with all-ok flags and a healthy metrics client
    WHEN main runs
    THEN the message sent contains both the backup and metrics sections joined
        by a blank line, has no raw newline bytes, and the exit code matches.
    """
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("NOTIFICATION_URL", "")

    redis_mock = _redis_mock_for_keys(
        {
            FLUSH_LAST_SUCCESS_KEY: str(_FIXED_NOW_EPOCH - 38).encode("utf-8"),
            GAUGE_LAST_SUCCESS_KEY: str(_FIXED_NOW_EPOCH - 720).encode("utf-8"),
        }
    )
    monkeypatch.setattr(notify, "_build_metrics_redis_client", lambda: redis_mock)
    monkeypatch.setattr(notify.time, "time", lambda: _FIXED_NOW_EPOCH)

    send_spy = MagicMock(return_value=0)
    monkeypatch.setattr(notify, "send", send_spy)

    exit_code = main(
        [
            "--summary",
            "--database",
            "ok",
            "--logs",
            "ok",
            "--remote-db",
            "ok",
            "--remote-monthly",
            "skip",
            "--remote-logs",
            "ok",
        ]
    )

    assert exit_code == 0
    send_spy.assert_called_once()
    sent_message = send_spy.call_args.args[0]
    assert "**Daily Backup — SUCCESS**" in sent_message
    assert "**Metrics — " in sent_message
    assert "\n" not in sent_message
    assert "\\n\\n" in sent_message


def test_main_summary_failure_exit_code(monkeypatch):
    """
    GIVEN a --summary invocation where the database stage failed
    WHEN main runs
    THEN the exit code is 1 (skip/health do not flip it).
    """
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("NOTIFICATION_URL", "")
    monkeypatch.setattr(notify, "_build_metrics_redis_client", lambda: None)
    monkeypatch.setattr(notify, "send", MagicMock(return_value=0))

    exit_code = main(
        [
            "--summary",
            "--database",
            "fail",
            "--logs",
            "ok",
            "--remote-db",
            "skip",
            "--remote-monthly",
            "skip",
            "--remote-logs",
            "skip",
        ]
    )
    assert exit_code == 1


def test_main_single_message_returns_send_code(monkeypatch):
    """
    GIVEN a --job/--status single-message invocation
    WHEN main runs
    THEN send's return code is returned and Redis is never touched.
    """
    monkeypatch.setenv("PRODUCTION", "false")
    monkeypatch.setenv("NOTIFICATION_URL", "")
    build_redis_spy = MagicMock()
    monkeypatch.setattr(notify, "_build_metrics_redis_client", build_redis_spy)
    send_spy = MagicMock(return_value=0)
    monkeypatch.setattr(notify, "send", send_spy)

    exit_code = main(
        ["--job", "DB_BACKUP", "--status", "SUCCESS", "--detail", "file.gz"]
    )
    assert exit_code == 0
    build_redis_spy.assert_not_called()
    sent_message = send_spy.call_args.args[0]
    assert "DB_BACKUP SUCCESS" in sent_message
    assert "file.gz" in sent_message
