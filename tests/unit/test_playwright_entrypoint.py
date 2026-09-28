"""Unit tests for the hub Playwright entrypoint's pure `--count` mode.

`docker/playwright-entrypoint.sh --count FILE…` counts ESTABLISHED, non-loopback client
connections to the browser server's port (3000 = `0BB8`) in `/proc/net/tcp`-format tables. The
idle watchdog and `make playwright-rebuild`'s guard both rely on it, so these cases pin which
rows count. Tables are fed as temp files (or stdin), so this runs anywhere bash exists.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.unit

SCRIPT = Path(__file__).resolve().parents[2] / "docker" / "playwright-entrypoint.sh"

TCP_HEADER = (
    "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt"
    "   uid  timeout inode"
)
TCP6_HEADER = (
    "  sl  local_address                         remote_address"
    "                        st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode"
)
ROW_TAIL = "00000000:00000000 00:00000000 00000000  1001        0 123456 1 0000000000000000 100 0 0 10 0"

LISTEN_ROW = f"   0: 00000000:0BB8 00000000:0000 0A {ROW_TAIL}"
CLIENT_ROW = f"   1: AC130005:0BB8 AC130007:D2F0 01 {ROW_TAIL}"
SECOND_CLIENT_ROW = f"   2: AC130005:0BB8 AC130008:D2F4 01 {ROW_TAIL}"
IPV6_ANY = "00000000000000000000000000000000"
IPV6_LOOPBACK = "00000000000000000000000001000000"
IPV6_PEER = "0000000000000000FFFF00000900A8C0"


def _table(header: str, *rows: str) -> str:
    return "\n".join((header, *rows)) + "\n"


def _count(tmp_path: Path, *tables: str) -> int:
    paths = []
    for index, table in enumerate(tables):
        table_path = tmp_path / f"tcp{index}"
        table_path.write_text(table)
        paths.append(str(table_path))
    result = subprocess.run(
        ["bash", str(SCRIPT), "--count", *paths],
        capture_output=True,
        text=True,
        check=True,
    )
    return int(result.stdout.strip())


def test_listen_only_counts_zero(tmp_path: Path) -> None:
    assert _count(tmp_path, _table(TCP_HEADER, LISTEN_ROW)) == 0


def test_established_client_counts_one(tmp_path: Path) -> None:
    assert _count(tmp_path, _table(TCP_HEADER, LISTEN_ROW, CLIENT_ROW)) == 1


def test_loopback_probe_is_ignored(tmp_path: Path) -> None:
    probe_row = f"   1: 0100007F:0BB8 0100007F:9C40 01 {ROW_TAIL}"
    assert _count(tmp_path, _table(TCP_HEADER, LISTEN_ROW, probe_row)) == 0


def test_time_wait_is_ignored(tmp_path: Path) -> None:
    time_wait_row = f"   1: AC130005:0BB8 AC130007:D2F0 06 {ROW_TAIL}"
    assert _count(tmp_path, _table(TCP_HEADER, LISTEN_ROW, time_wait_row)) == 0


def test_outbound_to_other_port_is_ignored(tmp_path: Path) -> None:
    outbound_row = f"   1: AC130005:9C41 AC130009:21CB 01 {ROW_TAIL}"
    assert _count(tmp_path, _table(TCP_HEADER, LISTEN_ROW, outbound_row)) == 0


def test_remote_port_0bb8_is_ignored(tmp_path: Path) -> None:
    remote_port_row = f"   1: AC130007:D2F0 AC130005:0BB8 01 {ROW_TAIL}"
    assert _count(tmp_path, _table(TCP_HEADER, remote_port_row)) == 0


def test_tcp6_rows_counted_and_loopback_ignored(tmp_path: Path) -> None:
    tcp6_table = _table(
        TCP6_HEADER,
        f"   0: {IPV6_ANY}:0BB8 {IPV6_ANY}:0000 0A {ROW_TAIL}",
        f"   1: {IPV6_ANY}:0BB8 {IPV6_PEER}:D2F0 01 {ROW_TAIL}",
        f"   2: {IPV6_ANY}:0BB8 {IPV6_LOOPBACK}:9C40 01 {ROW_TAIL}",
    )
    assert _count(tmp_path, tcp6_table) == 1


def test_multiple_files_are_summed(tmp_path: Path) -> None:
    tcp_table = _table(TCP_HEADER, LISTEN_ROW, CLIENT_ROW, SECOND_CLIENT_ROW)
    tcp6_table = _table(
        TCP6_HEADER, f"   0: {IPV6_ANY}:0BB8 {IPV6_PEER}:D2F0 01 {ROW_TAIL}"
    )
    assert _count(tmp_path, tcp_table, tcp6_table) == 3


def test_missing_file_counts_zero(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--count", str(tmp_path / "absent")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert int(result.stdout.strip()) == 0


def test_count_without_files_is_a_usage_error() -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--count"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert result.stderr.startswith("playwright-entrypoint: ")


def test_directory_argument_fails_loudly(tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(SCRIPT), "--count", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "playwright-entrypoint: cannot read" in result.stderr
    assert result.stdout == ""


def test_stdin_dash_is_read() -> None:
    piped_tables = _table(TCP_HEADER, LISTEN_ROW, CLIENT_ROW) + _table(
        TCP6_HEADER,
        f"   0: {IPV6_ANY}:0BB8 {IPV6_PEER}:D2F0 01 {ROW_TAIL}",
        f"   1: {IPV6_ANY}:0BB8 {IPV6_LOOPBACK}:9C40 01 {ROW_TAIL}",
    )
    result = subprocess.run(
        ["bash", str(SCRIPT), "--count", "-"],
        input=piped_tables,
        capture_output=True,
        text=True,
        check=True,
    )
    assert int(result.stdout.strip()) == 2
