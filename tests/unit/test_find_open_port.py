"""Unit tests for find_open_port skipping the ports Chromium refuses to navigate to."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.functional import ui_test_setup
from tests.functional.ui_test_setup import BROWSER_UNSAFE_PORTS, find_open_port

pytestmark = pytest.mark.unit


class FakeSocket:
    """A socket whose bind always succeeds, recording every probed port."""

    bound_ports: list[int] = []

    def __init__(self, family: int, kind: int) -> None:
        pass

    def __enter__(self) -> FakeSocket:
        return self

    def __exit__(self, *exc_info: object) -> None:
        pass

    def bind(self, address: tuple[str, int]) -> None:
        FakeSocket.bound_ports.append(address[1])


@pytest.fixture(autouse=True)
def fake_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSocket.bound_ports = []
    monkeypatch.setattr(
        ui_test_setup,
        "socket",
        SimpleNamespace(socket=FakeSocket, AF_INET=0, SOCK_STREAM=0),
    )


def test_unsafe_port_is_skipped_for_the_next_free_one() -> None:
    assert find_open_port(start_port=10080) == 10081
    assert FakeSocket.bound_ports == [10081]


def test_safe_start_port_is_returned_unchanged() -> None:
    assert find_open_port(start_port=10079) == 10079


@pytest.mark.parametrize("unsafe_port", sorted(BROWSER_UNSAFE_PORTS))
def test_every_unsafe_port_is_never_bound(unsafe_port: int) -> None:
    with pytest.raises(RuntimeError, match="No available port"):
        find_open_port(start_port=unsafe_port, end_port=unsafe_port)
    assert FakeSocket.bound_ports == []
