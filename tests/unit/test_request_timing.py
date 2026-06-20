from __future__ import annotations

from flask import Flask, g
import pytest

from backend.extensions.request_timing import init_app, request_elapsed_ms

pytestmark = pytest.mark.unit


def test_request_elapsed_ms_returns_none_outside_request_context():
    """
    GIVEN no active request (no `g.request_start_time` stamped)
    WHEN request_elapsed_ms is called inside a bare app_context
    THEN it returns None.
    """
    app = Flask(__name__)
    init_app(app)
    with app.app_context():
        assert not hasattr(g, "request_start_time")
        assert request_elapsed_ms() is None


def test_request_elapsed_ms_returns_non_negative_float_inside_request():
    """
    GIVEN the registered before_request hook has stamped the request clock
    WHEN request_elapsed_ms is called inside the same request
    THEN g.request_start_time is set and a non-negative float is returned.
    """
    app = Flask(__name__)

    @app.route("/ping")
    def _ping():
        return "ok"

    init_app(app)

    with app.test_request_context("/ping"):
        assert not hasattr(g, "request_start_time")
        app.preprocess_request()
        assert hasattr(g, "request_start_time")
        elapsed = request_elapsed_ms()
        assert isinstance(elapsed, float)
        assert elapsed >= 0.0


def test_init_app_registers_a_before_request_hook():
    """
    GIVEN a fresh Flask app
    WHEN request_timing.init_app is called
    THEN exactly one before_request function named _stash_request_start is
        registered.
    """
    app = Flask(__name__)
    assert not app.before_request_funcs.get(None)

    init_app(app)

    registered = app.before_request_funcs.get(None, [])
    assert any(func.__name__ == "_stash_request_start" for func in registered)
