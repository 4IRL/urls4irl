import logging
import socket
from time import sleep
from typing import Optional, Tuple

import requests
from flask import Flask
from flask.testing import FlaskCliRunner
from playwright.sync_api import Browser, BrowserType
from playwright.sync_api import Error as PlaywrightError

from backend import create_app, db
from backend.config import ConfigTestUI

# Bounded chromium.connect() retry against the shared hub browser-server: at most ~48 s in total. It only rides out
# transient connect failures (e.g. the server launching a browser for a burst of workers at once). It cannot revive a
# container the idle watchdog reaped: `web` has no Docker access, so nothing here can restart it. Residual window:
# `make playwright-up` returns immediately for an already-healthy container, so one at the very end of its
# U4I_PLAYWRIGHT_IDLE_MINUTES window (default 15) can still be reaped before the first connect; the gap is at most one
# watchdog poll interval (U4I_PLAYWRIGHT_POLL_SECONDS, default 30). The final error then says to run `make playwright-up`.
PLAYWRIGHT_CONNECT_ATTEMPTS = 3
PLAYWRIGHT_CONNECT_TIMEOUT_MS = 15_000
PLAYWRIGHT_CONNECT_BACKOFF_SECONDS = 1

# Ports >= 1024 that Chromium refuses to navigate to (net::ERR_UNSAFE_PORT; kRestrictedPorts in
# net/base/port_util.cc). A worker's Flask server bound to one is unreachable for every test on that worker, e.g.
# port_probe_start's per-run jitter landing gw0 on 10080.
BROWSER_UNSAFE_PORTS = frozenset(
    {
        1719,
        1720,
        1723,
        2049,
        3659,
        4045,
        4190,
        5060,
        5061,
        6000,
        6566,
        6665,
        6666,
        6667,
        6668,
        6669,
        6679,
        6697,
        10080,
    }
)


def run_app(port: int, show_flask_logs: bool, config: Optional[ConfigTestUI] = None):
    """
    Runs app
    """
    if config is None:
        config = ConfigTestUI()
    app_for_test = create_app(config, show_test_logs=show_flask_logs)  # type: ignore
    assert app_for_test is not None
    if not show_flask_logs:
        hide_logs_for_app(app_for_test)

    with app_for_test.app_context():
        db.create_all()

    host = "0.0.0.0" if config.DOCKER else "127.0.0.1"
    app_for_test.run(
        host=host,
        debug=False,
        port=port,
        use_reloader=False,  # Prevents child process creation
        threaded=True,
        processes=1,  # Explicitly set to 1 process
    )


def hide_logs_for_app(app: Flask):
    # Hide all possible logs from showing when running tests
    # https://stackoverflow.com/a/72145406
    log = logging.getLogger("werkzeug")
    log.disabled = True
    app.logger.disabled = True

    # Remove all StreamHandlers from the app logger to prevent console output
    handlers_to_remove = []
    for handler in app.logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler, logging.NullHandler
        ):
            handlers_to_remove.append(handler)

    for handler in handlers_to_remove:
        app.logger.removeHandler(handler)

    import flask.cli

    flask.cli.show_server_banner = lambda *_: None


def clear_db(runner: Tuple[Flask, FlaskCliRunner], debug_strings):
    # Clear db
    _, cli_runner = runner
    cli_runner.invoke(args=["managedb", "clear", "test"])
    if debug_strings:
        print("\ndb cleared")


def find_open_port(start_port: int = 1024, end_port: int = 65535) -> int:
    for port in range(start_port, end_port + 1):
        if port in BROWSER_UNSAFE_PORTS:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
            try:
                probe_socket.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No available port found in the specified range.")


def connect_to_browser_server(chromium: BrowserType, ws_url: str) -> Browser:
    """Connects to the Playwright browser-server, retrying transient failures
    with a linear backoff; raises a RuntimeError naming `make playwright-up`
    once every attempt has failed."""
    last_error: Optional[PlaywrightError] = None
    for attempt in range(1, PLAYWRIGHT_CONNECT_ATTEMPTS + 1):
        try:
            return chromium.connect(ws_url, timeout=PLAYWRIGHT_CONNECT_TIMEOUT_MS)
        except PlaywrightError as connect_error:
            last_error = connect_error
            if attempt < PLAYWRIGHT_CONNECT_ATTEMPTS:
                sleep(PLAYWRIGHT_CONNECT_BACKOFF_SECONDS * attempt)
    raise RuntimeError(
        f"Could not connect to the Playwright browser server at {ws_url} after "
        f"{PLAYWRIGHT_CONNECT_ATTEMPTS} attempts. The hub playwright may have been "
        "idle-reaped: run `make playwright-up` on the host, then rerun the tests."
    ) from last_error


def ping_server(url: str, timeout: float = 2) -> bool:
    total_time = 0
    max_time = 30
    is_server_ready = False

    # Keep pinging server until status code 200 or time limit is reached
    while not is_server_ready and total_time < max_time:
        try:
            status_code = requests.get(url, timeout=timeout).status_code
        except (
            requests.ConnectTimeout,
            requests.ReadTimeout,
            requests.ConnectionError,
        ):
            sleep(timeout)
            total_time += timeout
        else:
            if status_code == 200:
                is_server_ready = True
            else:
                sleep(timeout)
                total_time += timeout

    return is_server_ready
