from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import scripts.sample_gauges as sample_gauges
from scripts.sample_gauges import (
    GAUGE_FAILURE_FLAG_KEY,
    run_sample_job,
)

pytestmark = pytest.mark.unit


def _patch_run_sample(monkeypatch, *, return_value=None, side_effect=None) -> None:
    """Replace ``sample_gauges.run_sample`` with a stub returning/raising as given."""
    stub = MagicMock(return_value=return_value, side_effect=side_effect)
    monkeypatch.setattr(sample_gauges, "run_sample", stub)


def _patch_record_success(monkeypatch) -> None:
    """Stub the best-effort liveness stamp so the unit test never touches Redis."""
    monkeypatch.setattr(sample_gauges, "_record_sample_success", MagicMock())


def _patch_env(monkeypatch) -> None:
    """Make ``resolve_notification_env`` deterministic so notifier call args are stable."""
    monkeypatch.setattr(
        sample_gauges,
        "resolve_notification_env",
        lambda: ("true", "https://discord.com/api/webhooks/1/abc"),
    )


def test_success_no_prior_failure_does_not_notify(monkeypatch):
    """
    GIVEN run_sample succeeds and no failure flag is set (delete returns 0)
    WHEN run_sample_job is invoked
    THEN no notifier call is made and the sampled count is returned.
    """
    _patch_run_sample(monkeypatch, return_value=6)
    _patch_record_success(monkeypatch)
    _patch_env(monkeypatch)

    redis_client = MagicMock()
    redis_client.delete.return_value = 0
    notifier = MagicMock()

    result = run_sample_job(
        pg_conn=MagicMock(),
        redis_client=redis_client,
        now_epoch=1_700_000_000,
        notifier=notifier,
    )

    assert result == 6
    redis_client.delete.assert_called_once_with(GAUGE_FAILURE_FLAG_KEY)
    notifier.assert_not_called()


def test_success_after_failure_emits_single_recovery(monkeypatch):
    """
    GIVEN run_sample succeeds and a failure flag was set (delete returns 1)
    WHEN run_sample_job is invoked
    THEN exactly one RECOVERED notifier call is made and the flag is cleared.
    """
    _patch_run_sample(monkeypatch, return_value=6)
    _patch_record_success(monkeypatch)
    _patch_env(monkeypatch)

    redis_client = MagicMock()
    redis_client.delete.return_value = 1
    notifier = MagicMock(return_value=0)

    result = run_sample_job(
        pg_conn=MagicMock(),
        redis_client=redis_client,
        now_epoch=1_700_000_000,
        notifier=notifier,
    )

    assert result == 6
    redis_client.delete.assert_called_once_with(GAUGE_FAILURE_FLAG_KEY)
    notifier.assert_called_once()
    sent_message = notifier.call_args.args[0]
    assert "RECOVERED" in sent_message
    assert "GAUGE_SAMPLE" in sent_message


def test_first_failure_emits_single_failure_and_reraises(monkeypatch):
    """
    GIVEN run_sample raises and the failure flag was absent (set NX returns truthy)
    WHEN run_sample_job is invoked
    THEN exactly one FAILURE notifier call carrying the error detail is made,
        the flag is set, and the original exception re-raises.
    """
    error = RuntimeError("postgres down")
    _patch_run_sample(monkeypatch, side_effect=error)
    _patch_record_success(monkeypatch)
    _patch_env(monkeypatch)

    redis_client = MagicMock()
    redis_client.set.return_value = True
    notifier = MagicMock(return_value=0)

    with pytest.raises(RuntimeError, match="postgres down"):
        run_sample_job(
            pg_conn=MagicMock(),
            redis_client=redis_client,
            now_epoch=1_700_000_000,
            notifier=notifier,
        )

    redis_client.set.assert_called_once_with(GAUGE_FAILURE_FLAG_KEY, "1", nx=True)
    notifier.assert_called_once()
    sent_message = notifier.call_args.args[0]
    assert "FAILURE" in sent_message
    assert "postgres down" in sent_message


def test_repeated_failure_suppresses_notification_but_reraises(monkeypatch):
    """
    GIVEN run_sample raises and the failure flag is already set (set NX returns falsy)
    WHEN run_sample_job is invoked
    THEN no duplicate notifier call is made but the exception still re-raises.
    """
    error = RuntimeError("postgres still down")
    _patch_run_sample(monkeypatch, side_effect=error)
    _patch_record_success(monkeypatch)
    _patch_env(monkeypatch)

    redis_client = MagicMock()
    redis_client.set.return_value = None
    notifier = MagicMock()

    with pytest.raises(RuntimeError, match="postgres still down"):
        run_sample_job(
            pg_conn=MagicMock(),
            redis_client=redis_client,
            now_epoch=1_700_000_000,
            notifier=notifier,
        )

    redis_client.set.assert_called_once_with(GAUGE_FAILURE_FLAG_KEY, "1", nx=True)
    notifier.assert_not_called()
