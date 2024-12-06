import logging
import requests
import socket
from time import sleep
from typing import Tuple

from flask import Flask
from flask.testing import FlaskCliRunner

from src import create_app
from src.config import ConfigTestUI


def run_app(port: int, show_flask_logs: bool):
    """
    Runs app
    """
    config = ConfigTestUI()
    app_for_test = create_app(config)
    assert app_for_test is not None
    if not show_flask_logs:
        log = logging.getLogger("werkzeug")
        log.disabled = True
    app_for_test.run(debug=False, port=port)


def clear_db(runner: Tuple[Flask, FlaskCliRunner], debug_strings):
    # Clear db
    _, cli_runner = runner
    cli_runner.invoke(args=["managedb", "clear", "test"])
    if debug_strings:
        print("\ndb cleared")


def find_open_port(start_port: int = 1024, end_port: int = 65535) -> int:
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No available port found in the specified range.")


def ping_server(url: str, timeout: float = 2) -> bool:
    total_time = 0
    max_time = 10
    is_server_ready = False

    # Keep pinging server until status code 200 or time limit is reached
    while not is_server_ready and total_time < max_time:
        try:
            status_code = requests.get(url, timeout=timeout).status_code
        except requests.ConnectTimeout:
            sleep(timeout)
            total_time += timeout
        else:
            is_server_ready = status_code == 200

    return is_server_ready
