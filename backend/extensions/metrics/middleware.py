from __future__ import annotations

from flask import Flask, request
from werkzeug.wrappers import Response

from backend.extensions.metrics.writer import record_event
from backend.metrics.events import EventName
from backend.utils.all_routes import SYSTEM_ROUTES
from backend.utils.strings.config_strs import CONFIG_ENVS

_SKIP_ENDPOINTS: frozenset[str] = frozenset({"static", SYSTEM_ROUTES.HEALTH})
_METRICS_BLUEPRINT_NAME: str = "metrics"


def _should_skip(endpoint: str | None, blueprint: str | None) -> bool:
    """Return True when this request must not be recorded as an api_hit.

    Skips:
        - 404 unmatched routes (`endpoint is None`)
        - static asset endpoint and `system.health`
        - any request handled by the metrics blueprint itself (avoids
          a feedback loop on `POST /api/metrics`)
    """
    if endpoint is None:
        return True
    if endpoint in _SKIP_ENDPOINTS:
        return True
    if blueprint == _METRICS_BLUEPRINT_NAME:
        return True
    return False


def init_metrics_middleware(app: Flask) -> None:
    """Install the api_hit auto-instrumentation `after_request` handler.

    Reads `METRICS_ENABLED` at request time so toggling the flag at runtime
    (e.g. in tests) takes effect without re-initialization. Delegates to
    `record_event` which is already wrapped in log-and-drop, so no extra
    try/except is required here.
    """

    @app.after_request
    def _record_api_hit(response: Response) -> Response:
        if not app.config.get(CONFIG_ENVS.METRICS_ENABLED, False):
            return response
        if _should_skip(request.endpoint, request.blueprint):
            return response
        record_event(
            EventName.API_HIT,
            endpoint=request.endpoint,
            method=request.method,
            status_code=response.status_code,
        )
        return response
