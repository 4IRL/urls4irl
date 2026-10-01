"""Unit tests for the bounded chromium.connect() retry used by the UI-test session browser."""

from typing import cast

import pytest
from playwright.sync_api import Browser, BrowserType
from playwright.sync_api import Error as PlaywrightError

from tests.functional import ui_test_setup
from tests.functional.ui_test_setup import (
    PLAYWRIGHT_CONNECT_ATTEMPTS,
    PLAYWRIGHT_CONNECT_BACKOFF_SECONDS,
    PLAYWRIGHT_CONNECT_TIMEOUT_MS,
    connect_to_browser_server,
)

pytestmark = pytest.mark.unit

WS_URL = "ws://playwright:3000/"
CONNECTED_BROWSER = cast(Browser, object())


class FakeChromium:
    """Fails the first `failures` connects with a Playwright Error, then returns a browser."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.connect_calls: list[tuple[str, float]] = []

    def connect(self, ws_endpoint: str, timeout: float) -> Browser:
        self.connect_calls.append((ws_endpoint, timeout))
        if len(self.connect_calls) <= self.failures:
            raise PlaywrightError("connect ECONNREFUSED")
        return CONNECTED_BROWSER


@pytest.fixture
def recorded_sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleeps: list[float] = []
    monkeypatch.setattr(ui_test_setup, "sleep", sleeps.append)
    return sleeps


def test_first_connect_succeeds_without_sleeping(recorded_sleeps: list[float]) -> None:
    chromium = FakeChromium(failures=0)
    browser = connect_to_browser_server(cast(BrowserType, chromium), WS_URL)
    assert browser is CONNECTED_BROWSER
    assert chromium.connect_calls == [(WS_URL, PLAYWRIGHT_CONNECT_TIMEOUT_MS)]
    assert recorded_sleeps == []


def test_transient_failures_are_retried_with_backoff(
    recorded_sleeps: list[float],
) -> None:
    chromium = FakeChromium(failures=PLAYWRIGHT_CONNECT_ATTEMPTS - 1)
    browser = connect_to_browser_server(cast(BrowserType, chromium), WS_URL)
    assert browser is CONNECTED_BROWSER
    assert len(chromium.connect_calls) == PLAYWRIGHT_CONNECT_ATTEMPTS
    assert recorded_sleeps == [
        PLAYWRIGHT_CONNECT_BACKOFF_SECONDS * attempt
        for attempt in range(1, PLAYWRIGHT_CONNECT_ATTEMPTS)
    ]


def test_exhausted_retries_name_playwright_up(recorded_sleeps: list[float]) -> None:
    chromium = FakeChromium(failures=PLAYWRIGHT_CONNECT_ATTEMPTS)
    with pytest.raises(RuntimeError, match="make playwright-up") as raised:
        connect_to_browser_server(cast(BrowserType, chromium), WS_URL)
    assert isinstance(raised.value.__cause__, PlaywrightError)
    assert len(chromium.connect_calls) == PLAYWRIGHT_CONNECT_ATTEMPTS
    # No sleep after the final attempt: fail as soon as the budget is spent.
    assert len(recorded_sleeps) == PLAYWRIGHT_CONNECT_ATTEMPTS - 1
