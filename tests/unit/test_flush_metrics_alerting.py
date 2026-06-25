from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.flush_metrics import (
    FLUSH_FAILURE_FLAG_KEY,
    run_flush_job,
)

pytestmark = pytest.mark.unit


def _patch_run_flush(monkeypatch, *, return_value=None, side_effect=None) -> None:
    """Replace ``flush_metrics.run_flush`` with a stub returning/raising as given."""
    import scripts.flush_metrics as flush_metrics

    stub = MagicMock(return_value=return_value, side_effect=side_effect)
    monkeypatch.setattr(flush_metrics, "run_flush", stub)


def _patch_env(monkeypatch) -> None:
    """Make ``resolve_notification_env`` deterministic so notifier call args are stable."""
    import scripts.flush_metrics as flush_metrics

    monkeypatch.setattr(
        flush_metrics,
        "resolve_notification_env",
        lambda: ("true", "https://discord.com/api/webhooks/1/abc"),
    )


def test_success_no_prior_failure_does_not_notify(monkeypatch):
    """
    GIVEN run_flush succeeds and no failure flag is set (delete returns 0)
    WHEN run_flush_job is invoked
    THEN no notifier call is made and the upserted count is returned.
    """
    _patch_run_flush(monkeypatch, return_value=7)
    _patch_env(monkeypatch)

    redis_client = MagicMock()
    redis_client.delete.return_value = 0
    notifier = MagicMock()

    result = run_flush_job(
        redis_client=redis_client, pg_conn=MagicMock(), notifier=notifier
    )

    assert result == 7
    redis_client.delete.assert_called_once_with(FLUSH_FAILURE_FLAG_KEY)
    notifier.assert_not_called()


def test_success_after_failure_emits_single_recovery(monkeypatch):
    """
    GIVEN run_flush succeeds and a failure flag was set (delete returns 1)
    WHEN run_flush_job is invoked
    THEN exactly one RECOVERED notifier call is made and the flag is cleared.
    """
    _patch_run_flush(monkeypatch, return_value=3)
    _patch_env(monkeypatch)

    redis_client = MagicMock()
    redis_client.delete.return_value = 1
    notifier = MagicMock(return_value=0)

    result = run_flush_job(
        redis_client=redis_client, pg_conn=MagicMock(), notifier=notifier
    )

    assert result == 3
    redis_client.delete.assert_called_once_with(FLUSH_FAILURE_FLAG_KEY)
    notifier.assert_called_once()
    sent_message = notifier.call_args.args[0]
    assert "RECOVERED" in sent_message
    assert "METRICS_FLUSH" in sent_message


def test_first_failure_emits_single_failure_and_reraises(monkeypatch):
    """
    GIVEN run_flush raises and the failure flag was absent (set NX returns truthy)
    WHEN run_flush_job is invoked
    THEN exactly one FAILURE notifier call carrying the error detail is made,
        the flag is set, and the original exception re-raises.
    """
    error = RuntimeError("postgres down")
    _patch_run_flush(monkeypatch, side_effect=error)
    _patch_env(monkeypatch)

    redis_client = MagicMock()
    redis_client.set.return_value = True
    notifier = MagicMock(return_value=0)

    with pytest.raises(RuntimeError, match="postgres down"):
        run_flush_job(redis_client=redis_client, pg_conn=MagicMock(), notifier=notifier)

    redis_client.set.assert_called_once_with(FLUSH_FAILURE_FLAG_KEY, "1", nx=True)
    notifier.assert_called_once()
    sent_message = notifier.call_args.args[0]
    assert "FAILURE" in sent_message
    assert "postgres down" in sent_message


def test_repeated_failure_suppresses_notification_but_reraises(monkeypatch):
    """
    GIVEN run_flush raises and the failure flag is already set (set NX returns falsy)
    WHEN run_flush_job is invoked
    THEN no duplicate notifier call is made but the exception still re-raises.
    """
    error = RuntimeError("postgres still down")
    _patch_run_flush(monkeypatch, side_effect=error)
    _patch_env(monkeypatch)

    redis_client = MagicMock()
    redis_client.set.return_value = None
    notifier = MagicMock()

    with pytest.raises(RuntimeError, match="postgres still down"):
        run_flush_job(redis_client=redis_client, pg_conn=MagicMock(), notifier=notifier)

    redis_client.set.assert_called_once_with(FLUSH_FAILURE_FLAG_KEY, "1", nx=True)
    notifier.assert_not_called()
