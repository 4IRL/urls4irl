"""Pin the app-log step of the backup pipeline, `scripts/backup-logs.sh`.

The script is sourced by `daily-docker.sh`, so each test sources the real text in bash with the log paths
pointed at a tmp dir and the venv's `backup_maintenance.py` call swapped for a fake that records its argv.
"""

from __future__ import annotations

import gzip
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
BACKUP_LOGS: Path = REPO_ROOT / "scripts" / "backup-logs.sh"
MAINTENANCE_CALL: str = "/opt/metrics-venv/bin/python /app/backup_maintenance.py"
LOG_TEXT: str = "yesterday's app log\n"

FAKE_MAINTENANCE: str = """#!/bin/sh
echo "$*" >> "$FAKE_ARGV_LOG"
"""


def _source_backup_logs(
    tmp_path: Path, log_file: Path
) -> subprocess.CompletedProcess[str]:
    fake = tmp_path / "fake-maintenance"
    fake.write_text(FAKE_MAINTENANCE)
    fake.chmod(0o755)
    script = tmp_path / "backup-logs.sh"
    script.write_text(BACKUP_LOGS.read_text().replace(MAINTENANCE_CALL, str(fake)))
    env = {
        **os.environ,
        "LOG_DIR": str(log_file.parent),
        "LOG_FILE": str(log_file),
        "COMPRESSED_LOG_FILE": f"{log_file}.gz",
        "FAKE_ARGV_LOG": str(tmp_path / "maintenance-argv.log"),
    }
    return subprocess.run(
        ["bash", "-c", f'if source "{script}"; then echo SOURCED_OK; fi'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _maintenance_calls(tmp_path: Path) -> list[str]:
    return (tmp_path / "maintenance-argv.log").read_text().splitlines()


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return log_dir / "2026-11-27_daily.log"


def test_compresses_verifies_and_removes_the_daily_log(tmp_path: Path, log_file: Path):
    """
    GIVEN yesterday's uncompressed app log (the nightly run)
    WHEN backup-logs.sh is sourced
    THEN it writes the .gz, verifies it, removes the original and succeeds.
    """
    log_file.write_text(LOG_TEXT)
    compressed = Path(f"{log_file}.gz")

    result = _source_backup_logs(tmp_path, log_file)

    assert "SOURCED_OK" in result.stdout, result.stdout + result.stderr
    assert "Success: Compressed logs on host" in result.stdout
    assert gzip.decompress(compressed.read_bytes()).decode() == LOG_TEXT
    assert not log_file.exists()
    assert f"verify-dump --path {compressed} --min-size 0" in _maintenance_calls(
        tmp_path
    )


def test_reuses_the_archive_when_an_earlier_run_already_compressed_it(
    tmp_path: Path, log_file: Path
):
    """
    GIVEN the nightly run already compressed and removed yesterday's log (a later manual backup, #1060)
    WHEN backup-logs.sh is sourced
    THEN it keeps the existing archive, still verifies it and succeeds.
    """
    compressed = Path(f"{log_file}.gz")
    compressed.write_bytes(gzip.compress(LOG_TEXT.encode()))

    result = _source_backup_logs(tmp_path, log_file)

    assert "SOURCED_OK" in result.stdout, result.stdout + result.stderr
    assert f"Logs already compressed by an earlier run: {compressed}" in result.stdout
    assert "Compressing logs on host" not in result.stdout
    assert gzip.decompress(compressed.read_bytes()).decode() == LOG_TEXT
    assert f"verify-dump --path {compressed} --min-size 0" in _maintenance_calls(
        tmp_path
    )


def test_fails_when_neither_the_log_nor_its_archive_exists(
    tmp_path: Path, log_file: Path
):
    """
    GIVEN no log and no archive for yesterday
    WHEN backup-logs.sh is sourced
    THEN it reports the compression failure and returns non-zero.
    """
    result = _source_backup_logs(tmp_path, log_file)

    assert "SOURCED_OK" not in result.stdout
    assert "Error: Failure in compressing the logs" in result.stdout
