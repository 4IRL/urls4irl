"""Per-request monotonic timing — the single owner of the request clock.

Registered FIRST in ``create_app`` (above ``app_logger.init_app``) so its
``before_request`` runs ahead of any other ``before_request`` that can
short-circuit the request — notably the rate limiter, which can abort with a
429 before later hooks run. Stashing the start time first makes "the request
clock starts before anything can short-circuit" an explicit, ordered invariant
rather than incidental hook-registration order.

Both consumers — ``app_logger``'s ``after_request`` (which logs ``duration_ms``)
and the metrics ``after_request`` hook (which records latency samples) — call
``request_elapsed_ms()`` so the duration math lives in exactly one place.
"""

from __future__ import annotations

import time

from flask import Flask, g


def init_app(app: Flask) -> None:
    """Register the single ``before_request`` that stamps the request clock.

    Must be registered first in ``create_app`` so the start time is set before
    any short-circuiting hook (e.g. the rate limiter) can abort the request.
    """

    @app.before_request
    def _stash_request_start() -> None:
        # perf_counter() — monotonic; used only for the duration delta, never as a wall-clock timestamp
        g.request_start_time = time.perf_counter()


def request_elapsed_ms() -> float | None:
    """Return milliseconds elapsed since the request clock was stamped.

    Returns ``None`` when the ``before_request`` hook never ran (no request
    context or the request short-circuited before this module's hook).
    """
    start = getattr(g, "request_start_time", None)
    return None if start is None else (time.perf_counter() - start) * 1000.0
