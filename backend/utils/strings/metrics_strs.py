class METRICS_REDIS:
    COUNTER_KEY_PREFIX: str = "metrics:counter:"
    BATCH_KEY_PREFIX: str = "metrics:batch:"
    # Worker-liveness sentinel: the flush worker stamps this with the current
    # Unix epoch on every successful run (including empty flushes). Read by the
    # admin dashboard summary endpoint so the "Last flush" badge reflects the
    # worker's actual cadence rather than the most recent bucketStart (which
    # only advances when traffic lands).
    FLUSH_LAST_SUCCESS_KEY: str = "metrics:flush:last_success_epoch"
    # Gauge-sampler liveness sentinel: the standalone gauge sampler stamps this
    # with the current Unix epoch after each successful sample run (Redis ->
    # observability only; the workflow container's single healthcheck stays
    # check_flush_liveness.py). Written best-effort, so a Redis hiccup after a
    # successful Postgres commit does not fail the sample run.
    GAUGE_LAST_SUCCESS_KEY: str = "metrics:gauges:last_sample_epoch"
    # Prefix for raw latency-sample list keys: one Redis list per
    # (bucket, metric, endpoint, method, device) drained to AnonymousLatencySamples.
    LATENCY_KEY_PREFIX: str = "metrics:latency:"
    # Retention-prune sentinel: the flush worker stamps this with the current
    # Unix epoch after each successful prune so the daily prune runs at most once
    # per day. Deliberately under the `metrics:prune:` prefix (not
    # `metrics:latency:`) so it can never match the `metrics:latency:*` drain
    # glob — a collision would make the flush worker parse this sentinel as a
    # sample key and silently discard it, breaking the prune guard.
    LATENCY_LAST_PRUNE_KEY: str = "metrics:prune:latency_last_epoch"
    # Daily-rollup sentinel: the flush worker stamps this with the current Unix
    # epoch after each successful nightly rollup build so the rollup runs at most
    # once per LATENCY_ROLLUP_INTERVAL_SECONDS. Deliberately under the
    # `metrics:rollup:` prefix (not `metrics:latency:`) so it can never match the
    # `metrics:latency:*` drain glob — a collision would make the flush worker
    # parse this sentinel as a sample key and silently discard it.
    LATENCY_LAST_ROLLUP_KEY: str = "metrics:rollup:latency_last_epoch"
    # Backup last-success sentinel: daily-docker.sh stamps this (via
    # backup_sentinel.py) with the current Unix epoch after a successful
    # database backup. Read by the admin health dashboard. Deliberately under
    # the `metrics:backup:` prefix so it can never match the counter/latency
    # drain globs.
    BACKUP_LAST_SUCCESS_KEY: str = "metrics:backup:last_success_epoch"
    # On-demand backup trigger flag: the admin portal sets this (with a TTL so
    # stale requests age out); the workflow container's per-minute cron poller
    # (run_backup_if_requested.py) consumes it with GETDEL and starts the
    # backup pipeline.
    BACKUP_TRIGGER_KEY: str = "metrics:backup:trigger_requested"
    # Poller-side lock so an in-flight triggered backup cannot overlap another
    # trigger consumption (SET NX EX, TTL below in the poller script).
    BACKUP_TRIGGER_LOCK_KEY: str = "metrics:backup:trigger_lock"
