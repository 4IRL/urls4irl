from __future__ import annotations

from logging import NullHandler, getLogger

import pytest

from backend import oauth
from backend.config import ConfigTest
from tests.utils_for_test import create_secondary_app

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("logger_name", ["backend", "cli_logger"])
def test_create_secondary_app_restores_shared_logger(logger_name: str) -> None:
    """
    GIVEN a process-wide logger that `create_app` reconfigures, set up the way
        `build_app` leaves it for `caplog` (propagate=True, a known handler list)
    WHEN a second full app is built via `create_secondary_app`
    THEN the logger's propagate flag and handlers are unchanged, so later
        tests in the same xdist worker still see app logs in `caplog`
    """
    shared_logger = getLogger(logger_name)
    original_propagate = shared_logger.propagate
    original_level = shared_logger.level
    original_handlers = shared_logger.handlers
    sentinel_handler = NullHandler()
    shared_logger.propagate = True
    shared_logger.handlers = [sentinel_handler]
    try:
        create_secondary_app(ConfigTest)

        assert shared_logger.propagate is True
        assert shared_logger.handlers == [sentinel_handler]
    finally:
        shared_logger.propagate = original_propagate
        shared_logger.setLevel(original_level)
        shared_logger.handlers = original_handlers


def test_create_secondary_app_restores_oauth_registry() -> None:
    """
    GIVEN Authlib's process-wide `oauth` registry in some prior state
    WHEN a second full app is built via `create_secondary_app` (whose
        `create_app` calls `oauth.init_app` and may `oauth.register` clients)
    THEN the registry's clients, registrations and bound app are unchanged,
        so the shared test app keeps its dummy-credential OAuth clients
    """
    registry_before = dict(oauth._registry)
    clients_before = dict(oauth._clients)
    app_before = oauth.app

    try:
        create_secondary_app(ConfigTest)

        assert oauth._registry == registry_before
        assert oauth._clients == clients_before
        assert oauth.app is app_before
    finally:
        oauth._registry = registry_before
        oauth._clients = clients_before
        oauth.app = app_before
