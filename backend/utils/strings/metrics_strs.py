class METRICS_REDIS:
    COUNTER_KEY_PREFIX: str = "metrics:counter:"
    BATCH_KEY_PREFIX: str = "metrics:batch:"
    # Worker-liveness sentinel: the flush worker stamps this with the current
    # Unix epoch on every successful run (including empty flushes). Read by the
    # admin dashboard summary endpoint so the "Last flush" badge reflects the
    # worker's actual cadence rather than the most recent bucketStart (which
    # only advances when traffic lands).
    FLUSH_LAST_SUCCESS_KEY: str = "metrics:flush:last_success_epoch"
